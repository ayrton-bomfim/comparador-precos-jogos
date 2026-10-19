# -*- coding: utf-8 -*-
"""
Enriquecimento seguro de metadados Steam para o DESCTRL.

Regras:
- Considera apenas DISPONIVEL/GRATUITO e ignora jogos excluídos na auditoria.
- Compara cada retorno com o valor atual do banco antes de contar/gravar alterações.
- Nunca substitui dados por respostas vazias.
- Não altera nome canônico, preços, disponibilidade BR, steam_is_free,
  steam_conteudo_adulto, status_auditoria ou histórico de preços.
- Processa em lotes limitados para não enfileirar todo o catálogo de uma vez.
- A simulação não grava no banco nem avança o checkpoint.
- O checkpoint registra somente consultas válidas concluídas em modo de gravação.

Execute na raiz do projeto:
    python coletar_metadados_steam_pt_v5.py --limite 10 --simular
    python coletar_metadados_steam_pt_v5.py --limite 10
    python coletar_metadados_steam_pt_v5.py
"""

import argparse
import csv
import html
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from types import SimpleNamespace

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from sqlalchemy import case, func, or_
from backend.banco_dados import SessionLocal
from backend.modelos import Jogo
from coletar_dados_steam_completo_v10 import (
    buscar_appdetails,
    normalizar_texto,
    parse_data_lancamento,
    extrair_developer,
    extrair_publishers,
    extrair_generos,
    extrair_imagem_header,
    extrair_ratings,
    extrair_content_descriptors,
    extrair_supported_languages,
    extrair_content_notes,
    extrair_requisitos,
)

CHECKPOINT = os.path.join(ROOT_DIR, "coleta_metadados_steam_checkpoint.csv")
WORKERS_PADRAO = 4
LOTE_CONSULTAS = 40
LOTE_BANCO = 25

CAMPOS_METADADOS = (
    "desenvolvedor",
    "publicadora",
    "genero",
    "data_lancamento",
    "descricao_steam",
    "url_steam",
    "url_imagem_steam",
    "steam_required_age",
    "steam_metacritic_score",
    "steam_website",
    "steam_platforms",
    "steam_categories",
    "steam_genres",
    "steam_ratings",
    "steam_content_descriptors",
    "steam_supported_languages",
    "steam_content_notes",
    "steam_pc_requirements",
    "steam_mac_requirements",
    "steam_linux_requirements",
)

CAMPOS_CHECKPOINT = [
    "data_execucao", "jogo_id", "steam_id", "nome",
    "classificacao", "campos_atualizados", "erro",
]


def obter_argumentos():
    parser = argparse.ArgumentParser(
        description="Enriquece metadados Steam sem sobrescrever dados válidos."
    )
    parser.add_argument("--limite", type=int, default=None,
                        help="Máximo de jogos consultados nesta execução.")
    parser.add_argument("--simular", action="store_true",
                        help="Mostra alterações reais previstas, sem gravar no banco.")
    parser.add_argument("--workers", type=int, default=WORKERS_PADRAO,
                        help=f"Consultas concorrentes (padrão: {WORKERS_PADRAO}).")
    parser.add_argument("--lote-consultas", type=int, default=LOTE_CONSULTAS,
                        help=f"Jogos por lote HTTP (padrão: {LOTE_CONSULTAS}).")
    parser.add_argument("--reprocessar", action="store_true",
                        help="Ignora o checkpoint e consulta novamente os elegíveis.")
    args = parser.parse_args()
    if args.limite is not None and args.limite <= 0:
        parser.error("--limite deve ser maior que zero.")
    if args.workers <= 0:
        parser.error("--workers deve ser maior que zero.")
    if args.lote_consultas <= 0:
        parser.error("--lote-consultas deve ser maior que zero.")
    return args


def carregar_concluidos():
    concluidos = set()
    if not os.path.exists(CHECKPOINT):
        return concluidos
    with open(CHECKPOINT, "r", encoding="utf-8-sig", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha.get("classificacao") == "OK" and linha.get("steam_id"):
                concluidos.add(linha["steam_id"].strip())
    return concluidos


def salvar_checkpoint(resultado, campos_atualizados):
    existe = os.path.exists(CHECKPOINT) and os.path.getsize(CHECKPOINT) > 0
    with open(CHECKPOINT, "a", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS_CHECKPOINT)
        if not existe:
            escritor.writeheader()
        escritor.writerow({
            "data_execucao": datetime.now().isoformat(timespec="seconds"),
            "jogo_id": resultado.get("jogo_id", ""),
            "steam_id": resultado.get("steam_id", ""),
            "nome": resultado.get("_nome_catalogo", ""),
            "classificacao": resultado.get("classificacao", ""),
            "campos_atualizados": ",".join(campos_atualizados),
            "erro": resultado.get("erro", ""),
        })


def valor_util(valor):
    """Identifica valores úteis, inclusive JSON com estruturas vazias aninhadas.

    Preserva 0 e False como valores válidos. Um objeto como
    {"ids": [], "notes": null} ou requisitos com strings vazias é considerado vazio.
    """
    if valor is None:
        return False
    if isinstance(valor, str):
        texto = valor.strip()
        return bool(texto) and texto.lower() not in {
            "n/a", "null", "none", "não informado", "nao informado"
        }
    if isinstance(valor, dict):
        return any(valor_util(item) for item in valor.values())
    if isinstance(valor, (list, tuple, set)):
        return any(valor_util(item) for item in valor)
    # Zero e False podem ser valores legítimos, por exemplo score ou plataforma.
    return True


def parece_portugues(texto):
    """
    Heurística conservadora para descrições. Remove HTML antes de pontuar.
    Não é um detector linguístico perfeito; casos ambíguos são rejeitados.
    """
    if not isinstance(texto, str):
        return False

    texto = html.unescape(texto)
    texto = re.sub(r"<[^>]*>", " ", texto)
    texto = re.sub(r"\s+", " ", texto).lower()
    texto = " " + texto.strip() + " "

    if len(texto.strip()) < 40:
        return False

    marcadores_pt = (
        " de ", " que ", " para ", " com ", " uma ", " um ", " os ", " as ",
        " você ", " seu ", " sua ", " jogo ", " jogue ", " não ", " mais ",
        " dos ", " das ", " pela ", " pelo ", " está ", " este ", " nesta ",
        " experiência ", " mundo ", " história ", " jogadores ", " descubra ",
        " explore ", " mergulhe ", " aventura ", " conteúdo ", " através ",
        " neste ", " sua jornada ", " você pode ", " bem-vindo ",
    )
    marcadores_en = (
        " the ", " and ", " with ", " you ", " your ", " this ", " that ",
        " for ", " from ", " into ", " experience ", " world ", " story ",
        " players ", " discover ", " explore ", " adventure ", " content ",
        " through ", " in this ", " is a ", " are ", " will ", " can ",
    )
    pontos_pt = sum(1 for marcador in marcadores_pt if marcador in texto)
    pontos_en = sum(1 for marcador in marcadores_en if marcador in texto)
    tem_acentos_pt = any(caractere in texto for caractere in "ãõáéíóúâêôç")

    return pontos_pt >= 2 and (
        pontos_pt > pontos_en or
        (tem_acentos_pt and pontos_pt >= pontos_en)
    )


def valor_json_vazio(coluna, formatos_vazios=()):
    """Condição SQLAlchemy para JSON nulo/vazio e formatos aninhados sem conteúdo."""
    condicoes = [coluna.is_(None), coluna == [], coluna == {}]
    condicoes.extend(coluna == formato for formato in formatos_vazios)
    return or_(*condicoes)


def valores_iguais(atual, novo):
    """Compara valores comuns do SQLAlchemy, incluindo JSONB e datas."""
    if atual == novo:
        return True
    if isinstance(atual, str) and isinstance(novo, str):
        return atual.strip() == novo.strip()
    return False


def obter_alteracoes(jogo, dados):
    alteracoes = {}
    for campo in CAMPOS_METADADOS:
        if campo not in dados:
            continue
        novo = dados[campo]
        if not valor_util(novo):
            continue
        atual = getattr(jogo, campo, None)

        # Preferimos português quando a API o fornece. Se não houver uma
        # descrição identificada como português, aceitamos a descrição não vazia
        # retornada pela Steam (normalmente inglês). Nunca substituímos uma
        # descrição portuguesa existente por uma descrição não portuguesa.
        if campo == "descricao_steam":
            novo_pt = parece_portugues(novo)
            atual_pt = valor_util(atual) and parece_portugues(atual)
            if atual_pt and not novo_pt:
                continue

        if not valores_iguais(atual, novo):
            alteracoes[campo] = novo
    return alteracoes


def consultar(registro):
    """
    Consulta somente AppDetails (l=portuguese, cc=br via buscar_appdetails).
    Não consulta a página da loja porque esta rotina não atualiza preço nem
    disponibilidade. Isso reduz tráfego e tende a acelerar o enriquecimento.
    """
    resultado = {
        "jogo_id": registro["id"],
        "steam_id": str(registro["steam_id"]),
        "_nome_catalogo": registro["nome"],
        "classificacao": "",
        "erro": "",
        "dados": None,
        "_descricao_api": None,
    }

    try:
        app = buscar_appdetails(str(registro["steam_id"]))
        if app.get("status") != "OK":
            resultado["classificacao"] = app.get("status") or "APPDETAILS_INVALIDO"
            resultado["erro"] = f"AppDetails status={app.get('status')}"
            return resultado

        data = app.get("data") or {}
        if data.get("type") != "game":
            resultado["classificacao"] = "NAO_E_GAME"
            return resultado

        descricao = normalizar_texto(data.get("detailed_description"))
        resultado["_descricao_api"] = descricao
        resultado["classificacao"] = "OK"
        resultado["dados"] = {
            "desenvolvedor": extrair_developer(data),
            "publicadora": extrair_publishers(data),
            "genero": extrair_generos(data),
            "data_lancamento": parse_data_lancamento(
                (data.get("release_date") or {}).get("date")
            ),
            "descricao_steam": descricao,
            "url_steam": f"https://store.steampowered.com/app/{registro['steam_id']}/",
            "url_imagem_steam": extrair_imagem_header(data),
            "steam_required_age": (
                int(data["required_age"])
                if str(data.get("required_age", "")).isdigit()
                else None
            ),
            "steam_metacritic_score": (
                (data.get("metacritic") or {}).get("score")
            ),
            "steam_website": normalizar_texto(data.get("website")),
            "steam_platforms": data.get("platforms"),
            "steam_categories": data.get("categories"),
            "steam_genres": data.get("genres"),
            "steam_ratings": extrair_ratings(data),
            "steam_content_descriptors": extrair_content_descriptors(data),
            "steam_supported_languages": extrair_supported_languages(data),
            "steam_content_notes": extrair_content_notes(data),
            "steam_pc_requirements": extrair_requisitos(data, "pc"),
            "steam_mac_requirements": extrair_requisitos(data, "mac"),
            "steam_linux_requirements": extrair_requisitos(data, "linux"),
        }
        return resultado
    except Exception as erro:
        resultado["classificacao"] = "ERRO_CONSULTA"
        resultado["erro"] = repr(erro)[:500]
        return resultado


def selecionar_registros(db, concluidos, args):
    # A descrição ausente recebe prioridade máxima. Em seguida vêm outras
    # lacunas básicas, metadados adicionais e, por último, jogos completos.
    descricao_ausente = or_(
        Jogo.descricao_steam.is_(None),
        func.trim(Jogo.descricao_steam) == "",
    )

    basicos_ausentes = or_(
        Jogo.desenvolvedor.is_(None),
        func.trim(func.coalesce(Jogo.desenvolvedor, "")) == "",
        Jogo.publicadora.is_(None),
        func.trim(func.coalesce(Jogo.publicadora, "")) == "",
        Jogo.genero.is_(None),
        func.trim(func.coalesce(Jogo.genero, "")) == "",
        Jogo.data_lancamento.is_(None),
        Jogo.url_imagem_steam.is_(None),
        func.trim(func.coalesce(Jogo.url_imagem_steam, "")) == "",
        valor_json_vazio(Jogo.steam_platforms),
        valor_json_vazio(Jogo.steam_categories),
        valor_json_vazio(Jogo.steam_genres),
    )

    adicionais_ausentes = or_(
        Jogo.steam_metacritic_score.is_(None),
        Jogo.steam_supported_languages.is_(None),
        func.trim(func.coalesce(Jogo.steam_supported_languages, "")) == "",
        Jogo.steam_website.is_(None),
        func.trim(func.coalesce(Jogo.steam_website, "")) == "",
        valor_json_vazio(Jogo.steam_pc_requirements, (
            {"minimum": "", "recommended": ""},
            {"minimum": None, "recommended": None},
        )),
        valor_json_vazio(Jogo.steam_mac_requirements, (
            {"minimum": "", "recommended": ""},
            {"minimum": None, "recommended": None},
        )),
        valor_json_vazio(Jogo.steam_linux_requirements, (
            {"minimum": "", "recommended": ""},
            {"minimum": None, "recommended": None},
        )),
        valor_json_vazio(Jogo.steam_ratings),
        valor_json_vazio(Jogo.steam_content_descriptors, (
            {"ids": [], "notes": None},
            {"ids": [], "notes": ""},
        )),
    )

    prioridade = case(
        (descricao_ausente, 0),
        (basicos_ausentes, 1),
        (adicionais_ausentes, 2),
        else_=3,
    )

    consulta = (
        db.query(Jogo.id, Jogo.steam_id, Jogo.nome)
        .filter(
            Jogo.steam_id.isnot(None),
            Jogo.steam_disponibilidade_br.in_(["DISPONIVEL", "GRATUITO"]),
            func.lower(func.trim(func.coalesce(Jogo.status_auditoria, ""))) != "excluido",
        )
        .order_by(prioridade, Jogo.id)
        .yield_per(500)
    )

    selecionados = []
    elegiveis = 0
    pendentes = 0
    for jogo_id, steam_id, nome in consulta:
        if not str(steam_id or "").strip():
            continue
        elegiveis += 1
        if not args.reprocessar and str(steam_id).strip() in concluidos:
            continue
        pendentes += 1
        if args.limite is None or len(selecionados) < args.limite:
            selecionados.append({"id": jogo_id, "steam_id": str(steam_id), "nome": nome})
    return selecionados, elegiveis, pendentes


def processar_lote(db, registros, args, contadores, resumo):
    resultados = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futuros = {executor.submit(consultar, reg): reg for reg in registros}
        for futuro in as_completed(futuros):
            registro = futuros[futuro]
            try:
                resultado = futuro.result()
            except Exception as erro:
                resultado = {
                    "jogo_id": registro["id"],
                    "steam_id": registro["steam_id"],
                    "_nome_catalogo": registro["nome"],
                    "classificacao": "ERRO_INESPERADO",
                    "erro": repr(erro)[:500],
                    "dados": None,
                }
            classificacao = resultado.get("classificacao", "ERRO_SEM_CLASSIFICACAO")
            resumo[classificacao] = resumo.get(classificacao, 0) + 1
            contadores["consultados"] += 1
            if classificacao == "OK":
                contadores["ok"] += 1
            else:
                contadores["erros"] += 1
                print(f"[{classificacao}] {registro['nome']} "
                      f"(Steam {registro['steam_id']}): {resultado.get('erro') or ''}")
            resultados.append(resultado)

    # Compara contra o estado atual do banco; a simulação e a gravação usam a mesma regra.
    preparados = []
    for resultado in resultados:
        if resultado.get("classificacao") != "OK":
            continue
        jogo = db.get(Jogo, resultado["jogo_id"])
        if jogo is None:
            print(f"[AVISO] Jogo id={resultado['jogo_id']} não encontrado no banco.")
            continue
        dados_retorno = resultado.get("dados") or {}
        descricao_nova = dados_retorno.get("descricao_steam")
        descricao_atual = getattr(jogo, "descricao_steam", None)
        descricao_atual_vazia = not valor_util(descricao_atual)
        descricao_api_presente = valor_util(descricao_nova)
        descricao_pt = parece_portugues(descricao_nova) if descricao_api_presente else False

        if descricao_atual_vazia:
            contadores["descricao_atual_vazia"] += 1
        if descricao_api_presente:
            contadores["descricao_api_presente"] += 1
            if descricao_pt:
                contadores["descricao_pt_aceita"] += 1
            else:
                contadores["descricao_rejeitada_idioma"] += 1

        alteracoes = obter_alteracoes(jogo, dados_retorno)
        contadores["campos_diferentes"] += len(alteracoes)
        if args.simular:
            nomes = ", ".join(sorted(alteracoes)) if alteracoes else "nenhum"
            print(f"[SIMULAÇÃO] {resultado.get('_nome_catalogo')} | "
                  f"campos que realmente mudariam: {len(alteracoes)}")
            if alteracoes:
                print(f"    Campos: {nomes}")
            if descricao_atual_vazia or descricao_api_presente:
                trecho = ""
                if descricao_api_presente:
                    trecho = html.unescape(re.sub(r"<[^>]*>", " ", descricao_nova))
                    trecho = re.sub(r"\s+", " ", trecho).strip()[:140]
                decisao = (
                    "PORTUGUÊS detectado" if descricao_pt else
                    "DESCRIÇÃO mantida como alternativa (idioma não confirmado)" if descricao_api_presente
                    else "Steam não retornou descrição"
                )
                print(f"    Descrição: {decisao}" + (f" | trecho: {trecho}" if trecho else ""))
        else:
            for campo, valor in alteracoes.items():
                setattr(jogo, campo, valor)
            # Marca a data da consulta válida sem tocar em updated_at.
            jogo.steam_dados_atualizados_em = datetime.now()
        preparados.append((resultado, list(alteracoes.keys())))

    if args.simular:
        db.rollback()
    else:
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        for resultado, campos in preparados:
            salvar_checkpoint(resultado, campos)


def main():
    args = obter_argumentos()
    print("=" * 88)
    print("ENRIQUECIMENTO DE METADADOS STEAM | DESCTRL")
    print("=" * 88)
    print("Filtro: disponibilidade DISPONIVEL/GRATUITO e auditoria diferente de EXCLUIDO")
    print(f"Workers: {args.workers} | Lote de consultas: {args.lote_consultas}")
    print(f"Simulação: {'SIM' if args.simular else 'NÃO'}")
    print(f"Checkpoint: {CHECKPOINT}")
    print("Descrições: prioriza ausentes; aceita alternativa não vazia quando necessário, sem substituir português por outro idioma.")
    print("JSON: estruturas aninhadas sem conteúdo são tratadas como vazias.")
    print("Preços, disponibilidade, nome canônico, conteúdo adulto e auditoria ficam intocados.")
    print()

    concluidos = set() if args.reprocessar or args.simular else carregar_concluidos()
    db = SessionLocal()
    try:
        registros, elegiveis, pendentes = selecionar_registros(db, concluidos, args)
        print(f"Jogos elegíveis (excluídos na auditoria removidos): {elegiveis:,}")
        print(f"Pendentes após checkpoint: {pendentes:,}")
        print(f"Selecionados nesta execução: {len(registros):,}")
        if not registros:
            print("Nenhum jogo elegível para processar.")
            return

        contadores = {
            "consultados": 0, "ok": 0, "erros": 0, "campos_diferentes": 0,
            "descricao_atual_vazia": 0, "descricao_api_presente": 0,
            "descricao_pt_aceita": 0, "descricao_rejeitada_idioma": 0,
        }
        resumo = {}
        for inicio in range(0, len(registros), args.lote_consultas):
            lote = registros[inicio:inicio + args.lote_consultas]
            processar_lote(db, lote, args, contadores, resumo)
            print(f"Progresso: {contadores['consultados']}/{len(registros)} "
                  f"| AppDetails OK: {contadores['ok']} | erros: {contadores['erros']} "
                  f"| campos diferentes: {contadores['campos_diferentes']}")

        print("\n" + "=" * 88)
        print("RESUMO")
        print("=" * 88)
        print(f"Consultados: {contadores['consultados']}")
        print(f"AppDetails válidos: {contadores['ok']}")
        print(f"Erros/respostas não válidas: {contadores['erros']}")
        print(f"Campos que realmente diferem: {contadores['campos_diferentes']}")
        print(f"Jogos consultados com descrição atual vazia: {contadores['descricao_atual_vazia']}")
        print(f"Steam retornou descrição não vazia: {contadores['descricao_api_presente']}")
        print(f"Descrições identificadas como português: {contadores['descricao_pt_aceita']}")
        print(f"Descrições alternativas retornadas pela Steam (idioma não confirmado): {contadores['descricao_rejeitada_idioma']}")
        print(f"Modo: {'SIMULAÇÃO, nenhuma alteração persistida' if args.simular else 'GRAVAÇÃO'}")
        for classificacao, quantidade in sorted(resumo.items()):
            print(f"  {classificacao}: {quantidade}")
        print(f"Checkpoint: {CHECKPOINT}")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Execução interrompida. Consulte o checkpoint para retomar.")
