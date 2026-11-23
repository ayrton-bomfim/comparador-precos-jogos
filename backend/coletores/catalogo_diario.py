"""
Atualização diária do catálogo (etapa "catalogo", roda antes dos preços).

1. Steam, jogos novos: IStoreService/GetAppList só com o que mudou desde a
   última execução (if_modified_since). Apps novos viram jogos.
2. Steam, disponibilidade no Brasil: IStoreBrowseService/GetItems em lote
   (50 por consulta) para jogos novos, nunca classificados e, em rodízio, os
   que estão fora de venda. Estados:
       DISPONIVEL     preço próprio em reais (inclui pré-venda)
       GRATUITO       is_free
       EM_BREVE       ainda não lançado (coming soon), sem preço
       INDISPONIVEL   bloqueado para o Brasil
       INDETERMINADO  lançado, mas sem preço próprio
   Quem passa a DISPONIVEL entra na coleta de preços que vem logo depois.
3. Epic, jogos novos: busca da EGDATA ordenada pela última modificação, só
   até a última execução; o cadastro liga cada oferta ao jogo da Steam pelo
   ITAD antes de criar um jogo novo.

Jogos novos com conteúdo sexual explícito na classificação da Steam
(descritores 3 e 4) entram na Curadoria como pendentes e ficam ocultos até
a revisão. Desenvolvedora ou publicadora igual a um estúdio da tabela
estudios_brasileiros marca o jogo como brasileiro.

Execução avulsa:
    python -m backend.coletores.catalogo_diario [--sem-epic] [--limite-reavaliacao N]
"""

import argparse
import json
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy import text

from ..banco_dados import SessionLocal
from ..modelos import Jogo, SteamCatalogo
from ..servicos.identidade_jogos import chave_nome
from .steam_coletor import _eh_pacote_do_jogo, escolher_opcao_compra

URL_APPLIST = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
URL_GETITEMS = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1/"
URL_IMAGENS = "https://shared.akamai.steamstatic.com/store_item_assets/"

MARCO_STEAM = "steam_applist_desde"
MARCO_EPIC = "epic_busca_desde"

LOTE_GETITEMS = 50
WORKERS_GETITEMS = 4
TENTATIVAS = 6
REAVALIAR_DIAS = 3          # EM_BREVE / INDETERMINADO / INDISPONIVEL
REAVALIAR_GRATUITO_DIAS = 30
LIMITE_REAVALIACAO = 25_000  # por dia; os ~55 mil fora de venda giram em ~3 dias
DESCRITORES_ADULTOS = {3, 4}  # conteúdo sexual explícito / nudez frequente
MOTIVO_SENSIVEL = "Conteúdo sensível"
EXEMPLOS = 12

ESTADOS_ROTATIVOS = ("EM_BREVE", "INDETERMINADO", "INDISPONIVEL")


# ------------------------------------------------------------------ marcos

def ler_marco(db, chave):
    return db.execute(text("SELECT valor FROM controle_coleta WHERE chave = :c"), {"c": chave}).scalar()


def gravar_marco(db, chave, valor):
    db.execute(text("""
        INSERT INTO controle_coleta (chave, valor, atualizado_em) VALUES (:c, :v, now())
        ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor, atualizado_em = now()
    """), {"c": chave, "v": str(valor)})


# --------------------------------------------------------------- HTTP Steam

def _get_com_retentativa(sessao, url, params, timeout=60):
    espera = 5.0
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = sessao.get(url, params=params, timeout=timeout)
            if resposta.status_code == 429 or resposta.status_code >= 500:
                raise requests.HTTPError(f"HTTP {resposta.status_code}", response=resposta)
            resposta.raise_for_status()
            return resposta.json()
        except (requests.RequestException, ValueError) as erro:
            if tentativa == TENTATIVAS:
                raise
            retry_after = getattr(getattr(erro, "response", None), "headers", {}).get("Retry-After")
            try:
                pausa = float(retry_after) if retry_after else espera
            except ValueError:
                pausa = espera
            time.sleep(min(pausa, 60))
            espera = min(espera * 2, 60)


def _chave_steam():
    chave = os.getenv("STEAM_API_KEY") or os.getenv("STEAM_KEY")
    if not chave:
        raise RuntimeError("STEAM_API_KEY não definida no .env.")
    return chave


def buscar_apps_modificados(desde):
    """Jogos (só type game) criados ou modificados na Steam desde `desde` (unix)."""
    sessao = requests.Session()
    chave = _chave_steam()
    apps, ultimo = [], None
    while True:
        entrada = {
            "include_games": True, "include_dlc": False, "include_software": False,
            "include_videos": False, "include_hardware": False,
            "max_results": 50000, "if_modified_since": int(desde),
        }
        if ultimo:
            entrada["last_appid"] = ultimo
        resposta = _get_com_retentativa(
            sessao, URL_APPLIST, {"key": chave, "input_json": json.dumps(entrada)}
        ).get("response", {})
        apps += resposta.get("apps") or []
        if not resposta.get("have_more_results") or not resposta.get("last_appid"):
            return apps
        ultimo = resposta["last_appid"]


def buscar_itens_steam(appids, progresso=None):
    """{appid: item do GetItems} com dados de compra, lançamento e imagens."""
    sessao = requests.Session()
    lotes = [appids[i:i + LOTE_GETITEMS] for i in range(0, len(appids), LOTE_GETITEMS)]
    contexto = {"language": "brazilian", "country_code": "BR", "steam_realm": 1}
    pedido = {"include_basic_info": True, "include_release": True,
              "include_all_purchase_options": True, "include_assets": True}
    itens, falhas = {}, []

    def consultar(lote):
        entrada = {"ids": [{"appid": int(a)} for a in lote], "context": contexto, "data_request": pedido}
        dados = _get_com_retentativa(sessao, URL_GETITEMS, {"input_json": json.dumps(entrada)}, timeout=45)
        return {str(i.get("appid")): i for i in dados.get("response", {}).get("store_items") or []}

    feitos = 0
    with ThreadPoolExecutor(max_workers=WORKERS_GETITEMS) as executor:
        futuros = {executor.submit(consultar, lote): lote for lote in lotes}
        for futuro in as_completed(futuros):
            try:
                itens.update(futuro.result())
            except Exception:
                falhas.extend(futuros[futuro])
            feitos += 1
            if progresso and (feitos % max(1, len(lotes) // 10) == 0 or feitos == len(lotes)):
                progresso(feitos, len(lotes))
    return itens, falhas


# ----------------------------------------------------------- classificação

def classificar_item(item):
    """Estado de disponibilidade no Brasil a partir do GetItems (None = sem resposta)."""
    if not item or item.get("success") != 1:
        return None
    if item.get("is_free"):
        return "GRATUITO"
    opcao, _ = escolher_opcao_compra(item)
    if opcao and _eh_pacote_do_jogo(opcao) and opcao.get("final_price_in_cents") is not None:
        return "DISPONIVEL"
    if (item.get("release") or {}).get("is_coming_soon") or item.get("is_coming_soon"):
        return "EM_BREVE"
    if item.get("unvailable_for_country_restriction") or item.get("visible") is False:
        return "INDISPONIVEL"
    return "INDETERMINADO"


def _data_lancamento(item):
    """Só datas exatas: 'A ser anunciada' e 'ano X' não viram data."""
    lancamento = item.get("release") or {}
    unix = lancamento.get("steam_release_date")
    exibicao = lancamento.get("coming_soon_display")
    if not unix or (lancamento.get("is_coming_soon") and exibicao not in (None, "date_full")):
        return None
    try:
        return datetime.fromtimestamp(int(unix), tz=timezone.utc).date()
    except (ValueError, OSError, OverflowError):
        return None


def _imagem(item):
    assets = item.get("assets") or {}
    formato, header = assets.get("asset_url_format"), assets.get("header")
    if formato and header:
        return URL_IMAGENS + formato.replace("${FILENAME}", header)
    return None


def _nomes(basic, campo):
    nomes = ", ".join(p.get("name", "") for p in (basic.get(campo) or []) if p.get("name"))
    return nomes[:255] or None


def dados_do_item(item):
    basic = item.get("basic_info") or {}
    return {
        "status": classificar_item(item),
        "gratis": bool(item.get("is_free")),
        "lancamento": _data_lancamento(item),
        "desenvolvedor": _nomes(basic, "developers"),
        "publicadora": _nomes(basic, "publishers"),
        "imagem": _imagem(item),
        "adulto": bool(DESCRITORES_ADULTOS & set(item.get("content_descriptorids") or [])),
    }


# --------------------------------------------------------- Steam: novos

def descobrir_steam(db):
    """Cadastra os apps novos da Steam. Retorna (resumo, ids de jogos novos)."""
    desde = ler_marco(db, MARCO_STEAM)
    if desde is None:
        ultimo = db.execute(text("SELECT max(last_modified) FROM steam_catalogo")).scalar() or 0
        desde = max(0, int(ultimo) - 86400)
    desde = int(desde)
    inicio_consulta = int(time.time())
    print(f"Steam: apps criados ou modificados desde {datetime.fromtimestamp(desde):%d/%m/%Y %H:%M}...")
    apps = buscar_apps_modificados(desde)

    por_id = {str(a["appid"]): a for a in apps if a.get("appid")}
    existentes = dict(db.execute(
        text("SELECT steam_id, id FROM jogos WHERE steam_id = ANY(:ids)"), {"ids": list(por_id)}
    ).all())
    novos_ids = [i for i in por_id if i not in existentes]

    novos = []
    for steam_id in novos_ids:
        app = por_id[steam_id]
        nome = (app.get("name") or f"Steam App {steam_id}").strip()
        jogo = Jogo(steam_id=steam_id, nome=nome[:255], url_steam=f"https://store.steampowered.com/app/{steam_id}/")
        novos.append((jogo, app, nome))
    db.add_all([jogo for jogo, _, _ in novos])
    db.flush()
    db.add_all([
        SteamCatalogo(jogo_id=jogo.id, steam_id=jogo.steam_id, nome=nome,
                      last_modified=app.get("last_modified"),
                      price_change_number=app.get("price_change_number"), ativo=True)
        for jogo, app, nome in novos
    ])

    # Apps já conhecidos: só atualiza o índice (nome da Steam e marcadores).
    conhecidos = [por_id[i] for i in por_id if i in existentes]
    for inicio in range(0, len(conhecidos), 5000):
        bloco = conhecidos[inicio:inicio + 5000]
        db.execute(text("""
            UPDATE steam_catalogo AS c
            SET nome = v.nome, last_modified = v.mod, price_change_number = v.pcn, updated_at = now()
            FROM unnest(CAST(:ids AS text[]), CAST(:nomes AS text[]), CAST(:mods AS bigint[]),
                        CAST(:pcns AS bigint[])) AS v(steam_id, nome, mod, pcn)
            WHERE c.steam_id = v.steam_id
        """), {
            "ids": [str(a["appid"]) for a in bloco],
            "nomes": [a.get("name") for a in bloco],
            "mods": [a.get("last_modified") for a in bloco],
            "pcns": [a.get("price_change_number") for a in bloco],
        })

    gravar_marco(db, MARCO_STEAM, inicio_consulta - 6 * 3600)
    db.commit()
    print(f"Steam: {len(apps):,} apps modificados; {len(novos):,} jogos novos cadastrados.")
    for jogo, _, _ in novos[:EXEMPLOS]:
        print(f"  + [{jogo.steam_id}] {jogo.nome}")
    return {"apps_modificados": len(apps), "novos": len(novos)}, [jogo.id for jogo, _, _ in novos]


# ------------------------------------------------- Steam: disponibilidade

def _candidatos(db, ids_novos, limite):
    return db.execute(text("""
        SELECT j.id, j.steam_id, j.nome, j.steam_disponibilidade_br AS status,
               j.desenvolvedor, j.publicadora,
               EXISTS (SELECT 1 FROM auditorias_conteudo a WHERE a.jogo_id = j.id) AS tem_auditoria
        FROM jogos j
        WHERE j.steam_id ~ '^[0-9]+$'
          AND NOT EXISTS (SELECT 1 FROM auditorias_conteudo a
                          WHERE a.jogo_id = j.id AND a.status = 'excluido')
          AND (
               j.id = ANY(:novos)
            OR j.steam_disponibilidade_br IS NULL
            OR (j.steam_disponibilidade_br = 'EM_BREVE' AND j.data_lancamento <= current_date + 1)
            OR (j.steam_disponibilidade_br = ANY(:rotativos)
                AND (j.steam_dados_atualizados_em IS NULL
                     OR j.steam_dados_atualizados_em < now() - make_interval(days => :dias)))
            OR (j.steam_disponibilidade_br = 'GRATUITO'
                AND (j.steam_dados_atualizados_em IS NULL
                     OR j.steam_dados_atualizados_em < now() - make_interval(days => :dias_gratis)))
          )
        ORDER BY (j.id = ANY(:novos) OR j.steam_disponibilidade_br IS NULL) DESC,
                 (j.steam_disponibilidade_br = 'EM_BREVE' AND j.data_lancamento <= current_date + 1) DESC,
                 j.steam_dados_atualizados_em NULLS FIRST
        LIMIT :limite
    """), {
        "novos": ids_novos or [], "rotativos": list(ESTADOS_ROTATIVOS), "dias": REAVALIAR_DIAS,
        "dias_gratis": REAVALIAR_GRATUITO_DIAS, "limite": len(ids_novos or []) + limite,
    }).all()


def _estudios_brasileiros(db):
    try:
        nomes = db.execute(text("SELECT nome FROM estudios_brasileiros WHERE coalesce(ativo, true)")).scalars()
        return {chave_nome(n) for n in nomes if n}
    except Exception:
        db.rollback()
        return set()


def _eh_brasileiro(estudios, *campos):
    return any(chave_nome(parte) in estudios
               for campo in campos for parte in (campo or "").split(",") if parte.strip())


def _gravar_classificacao(db, linhas, agora):
    for inicio in range(0, len(linhas), 2000):
        bloco = linhas[inicio:inicio + 2000]
        coluna = lambda chave: [linha[chave] for linha in bloco]  # noqa: E731
        db.execute(text("""
            UPDATE jogos AS j SET
                steam_disponibilidade_br = v.status,
                steam_is_free = v.gratis,
                data_lancamento = coalesce(v.lancamento, j.data_lancamento),
                desenvolvedor = coalesce(nullif(j.desenvolvedor, ''), v.desenvolvedor),
                publicadora = coalesce(nullif(j.publicadora, ''), v.publicadora),
                url_imagem_steam = coalesce(nullif(j.url_imagem_steam, ''), v.imagem),
                steam_conteudo_adulto = j.steam_conteudo_adulto OR v.adulto,
                steam_dados_atualizados_em = :agora,
                updated_at = :agora
            FROM unnest(CAST(:ids AS integer[]), CAST(:status AS text[]), CAST(:gratis AS boolean[]),
                        CAST(:lancamento AS date[]), CAST(:desenvolvedor AS text[]),
                        CAST(:publicadora AS text[]), CAST(:imagem AS text[]), CAST(:adulto AS boolean[]))
                 AS v(id, status, gratis, lancamento, desenvolvedor, publicadora, imagem, adulto)
            WHERE j.id = v.id
        """), {
            "agora": agora, "ids": coluna("id"), "status": coluna("status"), "gratis": coluna("gratis"),
            "lancamento": coluna("lancamento"), "desenvolvedor": coluna("desenvolvedor"),
            "publicadora": coluna("publicadora"), "imagem": coluna("imagem"), "adulto": coluna("adulto"),
        })


def _enviar_para_curadoria(db, jogos):
    """Jogos com conteúdo sexual explícito: pendentes (e ocultos) na Curadoria."""
    observacao = ("Enviado automaticamente: a classificação da Steam indica conteúdo sexual "
                  "explícito ou nudez frequente. O jogo fica oculto até a revisão.")
    for jogo_id, nome, imagem in jogos:
        auditoria_id = db.execute(text("""
            INSERT INTO auditorias_conteudo (jogo_id, nome_jogo, status, origem, motivo, observacao, imagens)
            VALUES (:j, :n, 'pendente', 'automatico', :m, :o, CAST(:img AS jsonb))
            RETURNING id
        """), {"j": jogo_id, "n": nome[:255], "m": MOTIVO_SENSIVEL, "o": observacao,
               "img": json.dumps([imagem] if imagem else [])}).scalar()
        db.execute(text("""
            INSERT INTO auditorias_conteudo_historico
                (auditoria_id, jogo_id, nome_jogo, status_anterior, status_novo, motivo, observacao)
            VALUES (:a, :j, :n, NULL, 'pendente', :m, :o)
        """), {"a": auditoria_id, "j": jogo_id, "n": nome[:255], "m": MOTIVO_SENSIVEL, "o": observacao})
        db.execute(text("UPDATE jogos SET status_auditoria = 'pendente' "
                        "WHERE id = :j AND status_auditoria = 'nao_avaliado'"), {"j": jogo_id})


def classificar_steam(db, ids_novos, limite_reavaliacao):
    candidatos = _candidatos(db, ids_novos, limite_reavaliacao)
    novos = set(ids_novos)
    print(f"\nSteam: classificando disponibilidade de {len(candidatos):,} jogos "
          f"({len(novos):,} novos, demais em rodízio)...")
    if not candidatos:
        return {"consultados": 0}

    inicio = time.monotonic()
    itens, falhas = buscar_itens_steam(
        [c.steam_id for c in candidatos],
        progresso=lambda f, t: print(f"  GetItems: {f}/{t} lotes ({time.monotonic() - inicio:.0f}s)"),
    )
    estudios = _estudios_brasileiros(db)
    agora = datetime.now(timezone.utc)

    linhas, transicoes, lancados, adultos, brasileiros = [], Counter(), [], [], []
    for candidato in candidatos:
        item = itens.get(candidato.steam_id)
        if not item:
            continue
        dados = dados_do_item(item)
        if dados["status"] is None:
            continue
        linhas.append({"id": candidato.id, **dados})
        anterior = candidato.status or "SEM_CLASSIFICACAO"
        if anterior != dados["status"]:
            transicoes[f"{anterior} -> {dados['status']}"] += 1
            if anterior == "EM_BREVE" and dados["status"] in {"DISPONIVEL", "GRATUITO"}:
                lancados.append(candidato.nome)
        # Vai aparecer no site agora (jogo novo, ou que saiu de um estado
        # oculto para à venda/gratuito)? Se tiver conteúdo sexual explícito e
        # nunca passou pela Curadoria, fica pendente e oculto até a revisão.
        passa_a_aparecer = candidato.id in novos or (
            anterior not in {"DISPONIVEL", "GRATUITO"} and dados["status"] in {"DISPONIVEL", "GRATUITO"}
        )
        if passa_a_aparecer and dados["adulto"] and not candidato.tem_auditoria:
            adultos.append((candidato.id, candidato.nome, dados["imagem"]))
        if candidato.id in novos and estudios and _eh_brasileiro(
            estudios, dados["desenvolvedor"], dados["publicadora"]
        ):
            brasileiros.append(candidato.id)

    _gravar_classificacao(db, linhas, agora)
    _enviar_para_curadoria(db, adultos)
    if brasileiros:
        db.execute(text("UPDATE jogos SET eh_brasileiro = true WHERE id = ANY(:ids)"), {"ids": brasileiros})
    db.commit()

    estados = Counter(linha["status"] for linha in linhas)
    print(f"Steam: {len(linhas):,} classificados em {time.monotonic() - inicio:.0f}s; "
          f"sem resposta: {len(candidatos) - len(linhas):,} (lotes falhos: {len(falhas):,}).")
    print("  Estados: " + ", ".join(f"{k}={v:,}" for k, v in estados.most_common()))
    if transicoes:
        print("  Mudanças: " + ", ".join(f"{k}={v:,}" for k, v in transicoes.most_common()))
    for nome in lancados[:EXEMPLOS]:
        print(f"  lançado: {nome}")
    if adultos:
        print(f"  {len(adultos)} jogo(s) enviados à Curadoria por conteúdo sensível (ficam ocultos até a revisão).")
    if brasileiros:
        print(f"  {len(brasileiros)} jogo(s) novo(s) de estúdio brasileiro.")
    return {
        "consultados": len(candidatos), "classificados": len(linhas),
        "sem_resposta": len(candidatos) - len(linhas), "lotes_falhos_ids": len(falhas),
        "estados": dict(estados), "mudancas": dict(transicoes), "lancados": len(lancados),
        "enviados_curadoria": len(adultos), "brasileiros_novos": len(brasileiros),
    }


# ------------------------------------------------------------- Epic: novos

def descobrir_epic(db):
    from ..ferramentas.cadastrar_catalogo_epic import cadastrar_catalogo
    from .epic_catalogo import EpicCatalogo

    desde = ler_marco(db, MARCO_EPIC)
    if desde is None:
        ultimo = db.execute(text("SELECT max(last_modified_date) FROM epic_catalogo")).scalar()
        base = (ultimo or datetime.now(timezone.utc)) - timedelta(days=1)
        desde = base.strftime("%Y-%m-%dT%H:%M:%SZ")
    inicio_consulta = datetime.now(timezone.utc)
    print(f"\nEpic: ofertas modificadas desde {desde[:16].replace('T', ' ')} (EGDATA)...")

    # Pausa de 3s entre páginas: a EGDATA segura (tarpit) consultas em sequência rápida.
    resultado = EpicCatalogo(pausa_paginas=3.0).coletar(desde=desde)
    jogos = resultado.get("jogos") or []
    print(f"Epic: {resultado.get('ofertas_recebidas', 0)} ofertas modificadas, {len(jogos)} jogos aproveitáveis.")

    resumo = {"ofertas_modificadas": resultado.get("ofertas_recebidas", 0), "aproveitaveis": len(jogos)}
    if jogos:
        cadastro = cadastrar_catalogo(db, jogos)
        resumo.update({k: v for k, v in cadastro.items() if isinstance(v, int)})
    gravar_marco(db, MARCO_EPIC, (inicio_consulta - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ"))
    db.commit()
    return resumo


# ---------------------------------------------------------------- etapa

def atualizar_catalogo(com_epic=True, limite_reavaliacao=LIMITE_REAVALIACAO):
    """Etapa diária. Cada parte é independente: a falha de uma não impede as outras."""
    inicio = time.monotonic()
    print("=" * 60)
    print("ATUALIZAÇÃO DO CATÁLOGO (jogos novos e disponibilidade)")
    print("=" * 60)
    resultado, falhas = {}, []
    db = SessionLocal()
    try:
        ids_novos = []
        for nome, tarefa in (
            ("steam_novos", lambda: descobrir_steam(db)),
            ("steam_disponibilidade", lambda: classificar_steam(db, ids_novos, limite_reavaliacao)),
            ("epic_novos", (lambda: descobrir_epic(db)) if com_epic else None),
        ):
            if tarefa is None:
                continue
            try:
                saida = tarefa()
                if nome == "steam_novos":
                    saida, ids_novos = saida
                resultado[nome] = saida
            except Exception as erro:
                db.rollback()
                falhas.append(nome)
                resultado[nome] = {"erro": f"{type(erro).__name__}: {erro}"}
                print(f"⚠️ {nome}: {type(erro).__name__}: {erro}")
    finally:
        db.close()

    resultado["duracao_segundos"] = round(time.monotonic() - inicio, 1)
    resultado["novos_registros"] = (
        (resultado.get("steam_novos") or {}).get("novos", 0)
        + (resultado.get("epic_novos") or {}).get("jogos_novos", 0)
    )
    resultado["status"] = "falha" if len(falhas) == 3 else ("parcial" if falhas else "concluida")
    print(f"\nCatálogo: status={resultado['status']} em {resultado['duracao_segundos']:.0f}s")
    return resultado


def main():
    parser = argparse.ArgumentParser(description="Atualiza o catálogo: jogos novos e disponibilidade.")
    parser.add_argument("--sem-epic", action="store_true")
    parser.add_argument("--limite-reavaliacao", type=int, default=LIMITE_REAVALIACAO)
    args = parser.parse_args()
    atualizar_catalogo(com_epic=not args.sem_epic, limite_reavaliacao=args.limite_reavaliacao)


if __name__ == "__main__":
    main()
