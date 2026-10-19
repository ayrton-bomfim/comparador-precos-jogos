# -*- coding: utf-8 -*-
"""
Script de coleta de histórico de preços da Steam.

Este script percorre todos os jogos cadastrados, consulta seus preços
atuais na Steam e registra as variações na tabela de histórico.
"""

import sys
import os
import asyncio
import argparse
import requests

# Adiciona a raiz do projeto ao path ANTES dos imports do backend.
ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "..",
    )
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from datetime import datetime, timedelta, timezone
from sqlalchemy import func, and_, cast, Date
from dotenv import load_dotenv
from backend.coletores.steam_coletor import SteamColetor
from backend.banco_dados import SessionLocal
from backend.modelos import Jogo, HistoricoPreco

load_dotenv()


STEAM_APP_LIST_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
OVERLAP_HOURS = 48
PRIMEIRA_JANELA_DIAS = 30
STEAM_API_KEY_NAMES = ["STEAM_API_KEY", "STEAM_WEB_API_KEY", "STEAM_KEY"]

# Fallback individual: usado somente quando o GetItems não resolve
# o preço ou quando detectamos uma mudança de estado que precisa
# de confirmação antes de gravar no histórico.
FALLBACK_INTERVAL_SECONDS = 2.0


def _obter_chave_steam():
    for nome in STEAM_API_KEY_NAMES:
        chave = os.getenv(nome)
        if chave:
            return chave
    raise RuntimeError(
        "Chave da Steam não encontrada. Defina STEAM_API_KEY "
        "(ou STEAM_WEB_API_KEY/STEAM_KEY) no .env."
    )


def _obter_ultima_coleta_steam(db):
    return (
        db.query(func.max(HistoricoPreco.data_coleta))
        .filter(HistoricoPreco.plataforma == "Steam")
        .scalar()
    )


def _obter_janela_incremental(db, primeira_coleta=False):
    agora_utc = datetime.now(timezone.utc)

    if primeira_coleta:
        inicio = agora_utc - timedelta(
            days=PRIMEIRA_JANELA_DIAS,
            hours=OVERLAP_HOURS,
        )
        print(
            f"\nPrimeira coleta incremental: usando janela máxima de "
            f"{PRIMEIRA_JANELA_DIAS + OVERLAP_HOURS / 24:.0f} dias "
            f"({PRIMEIRA_JANELA_DIAS} dias + {OVERLAP_HOURS}h de overlap)."
        )
        return inicio

    ultima_coleta = _obter_ultima_coleta_steam(db)

    if ultima_coleta is None:
        inicio = agora_utc - timedelta(
            days=PRIMEIRA_JANELA_DIAS,
            hours=OVERLAP_HOURS,
        )
        print(
            f"\nNenhum histórico Steam encontrado. Usando janela máxima de "
            f"{PRIMEIRA_JANELA_DIAS + OVERLAP_HOURS / 24:.0f} dias."
        )
        return inicio

    if ultima_coleta.tzinfo is None:
        ultima_coleta = ultima_coleta.replace(tzinfo=timezone.utc)
    else:
        ultima_coleta = ultima_coleta.astimezone(timezone.utc)

    inicio = ultima_coleta - timedelta(hours=OVERLAP_HOURS)

    print(
        f"\nÚltima data_coleta Steam: "
        f"{ultima_coleta.strftime('%d/%m/%Y %H:%M:%S UTC')}"
    )
    print(
        f"Janela incremental: "
        f"{inicio.strftime('%d/%m/%Y %H:%M:%S UTC')} "
        f"até {agora_utc.strftime('%d/%m/%Y %H:%M:%S UTC')}"
    )

    return inicio


def _buscar_apps_steam_modificados(data_inicio):
    chave = _obter_chave_steam()
    timestamp = int(data_inicio.timestamp())

    params = {
        "key": chave,
        "if_modified_since": timestamp,
        "include_games": "true",
        "include_dlc": "false",
        "include_software": "false",
        "include_videos": "false",
        "include_hardware": "false",
        "max_results": 50000,
    }

    inicio = datetime.now()
    response = requests.get(
        STEAM_APP_LIST_URL,
        params=params,
        timeout=60,
    )
    response.raise_for_status()

    payload = response.json().get("response", {})
    apps = payload.get("apps") or []

    print("\n" + "=" * 60)
    print("STEAM - GETAPPLIST")
    print("=" * 60)
    print(f"  HTTP: {response.status_code}")
    print(f"  Apps modificados: {len(apps):,}")
    print(f"  more_items: {payload.get('more_items')}")
    print(f"  last_appid: {payload.get('last_appid')}")
    print(f"  Tempo: {(datetime.now() - inicio).total_seconds():.3f}s")

    if payload.get("more_items"):
        raise RuntimeError(
            "GetAppList retornou more_items=true. "
            "A paginação ainda não está implementada neste coletor; "
            "a execução foi interrompida para evitar perda de candidatos."
        )

    return {
        str(app["appid"])
        for app in apps
        if app.get("appid") is not None
    }


def _formatar_moeda(valor):
    """Formata um valor numérico em reais no padrão brasileiro."""
    if valor is None:
        return "N/A"
    return f"R$ {float(valor):.2f}".replace(".", ",")


def _parse_preco(preco_str):
    """Converte preços formatados em reais para float, aceitando pt-BR e en-US."""
    if preco_str in (None, "N/A"):
        return None

    if isinstance(preco_str, (int, float)):
        return round(float(preco_str), 2)

    valor = str(preco_str).strip()
    if not valor:
        return None

    if valor.lower() in {"grátis", "gratis", "free"}:
        return 0.0

    valor = valor.replace("R$", "").replace("BRL", "").strip()

    # Normaliza formatos como 278,40 / 278.40 / 1.299,90 / 1,299.90.
    if "," in valor and "." in valor:
        if valor.rfind(",") > valor.rfind("."):
            valor = valor.replace(".", "").replace(",", ".")
        else:
            valor = valor.replace(",", "")
    elif "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    else:
        # Ponto isolado é tratado como separador decimal.
        valor = valor.replace(" ", "")

    try:
        return round(float(valor), 2)
    except (ValueError, TypeError):
        return None


def _extrair_preco_fallback(dados):
    """Converte a resposta de fallback para valores numéricos."""
    preco_num = _parse_preco(dados.get("preco"))
    preco_original_num = _parse_preco(
        dados.get("preco_sem_desconto")
    )

    if preco_num is None:
        return None, None, None

    if preco_original_num is None:
        preco_original_num = preco_num

    desconto_str = dados.get("desconto", "0%")
    try:
        desconto = int(
            str(desconto_str).replace("%", "").replace("-", "").strip()
        )
    except (ValueError, AttributeError):
        desconto = 0

    return (
        round(float(preco_num), 2),
        round(float(preco_original_num), 2),
        desconto,
    )


async def _executar_fallback_preco(coletor, jogo):
    """
    Executa o fallback individual de forma sequencial e controlada.
    Não é chamado para todos os jogos, somente para casos necessários.
    """
    print(
        f"  Fallback individual para Steam ID {jogo.steam_id}..."
    )

    dados = await coletor.coletar_fallback_preco(jogo.steam_id)

    await asyncio.sleep(FALLBACK_INTERVAL_SECONDS)

    return dados


def _carregar_ultimos_historicos_steam(db, jogo_ids):
    """
    Carrega de uma vez o último histórico Steam de cada jogo.

    Evita uma consulta SQL individual para cada jogo durante o processamento.
    A lógica de escolha do último registro continua sendo baseada em
    data_coleta, como no fluxo original.
    """
    if not jogo_ids:
        return {}

    historicos = (
        db.query(HistoricoPreco)
        .filter(
            HistoricoPreco.jogo_id.in_(jogo_ids),
            HistoricoPreco.plataforma == "Steam",
        )
        .order_by(
            HistoricoPreco.jogo_id.asc(),
            HistoricoPreco.data_coleta.desc(),
        )
        .all()
    )

    ultimos = {}

    for historico in historicos:
        if historico.jogo_id not in ultimos:
            ultimos[historico.jogo_id] = historico

    return ultimos


async def coletar_historico_precos(primeira_coleta=False):
    """
    Coleta preços/promoções da Steam em lote e salva somente mudanças reais.

    Os últimos históricos Steam são carregados em uma única consulta SQL
    antes do processamento, evitando uma consulta individual por jogo.

    Um novo registro é criado quando muda pelo menos um dos campos de estado:
    - preço atual;
    - preço original;
    - desconto;
    - promoção (ID, nome, tipo, início ou fim).

    A simples mudança de dia/data_coleta não cria um novo registro.
    """
    print("=" * 60)
    print("COLETANDO HISTÓRICO DE PREÇOS (STEAM)")
    print("Consulta principal: IStoreBrowseService/GetItems em lote")
    print("Fallback: página individual Steam -> AppDetails, somente quando necessário")
    print("Novo registro: mudança de estado do preço/promoção")
    print("=" * 60)
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    db = SessionLocal()
    coletor = SteamColetor()

    try:
        inicio_janela = _obter_janela_incremental(db, primeira_coleta)
        apps_modificados = _buscar_apps_steam_modificados(inicio_janela)

        jogos_catalogo = (
            db.query(Jogo)
            .filter(Jogo.steam_id.isnot(None))
            .all()
        )

        ids_catalogo = {str(jogo.steam_id) for jogo in jogos_catalogo}

        jogos = [
            jogo
            for jogo in jogos_catalogo
            if str(jogo.steam_id) in apps_modificados
        ]

        print(f"\nJogos com Steam no banco: {len(jogos_catalogo):,}")
        print(f"Jogos candidatos encontrados no catálogo: {len(jogos):,}")
        print(f"Apps Steam fora do catálogo: {len(apps_modificados - ids_catalogo):,}")

        if not jogos:
            print("Nenhum jogo do catálogo foi modificado na janela consultada.")
            db.commit()
            return

        ids = [jogo.steam_id for jogo in jogos]
        dados_lote = await coletor.coletar_precos_lote(ids)

        print("\nCarregando últimos históricos da Steam em uma única consulta...")
        ultimos_historicos = _carregar_ultimos_historicos_steam(
            db,
            [jogo.id for jogo in jogos],
        )
        print(
            f"Últimos históricos carregados: "
            f"{len(ultimos_historicos)} jogos."
        )

        alterados = 0
        erros = 0
        ignorados = 0

        for i, jogo in enumerate(jogos, 1):
            print(
                f"\n[{i}/{len(jogos)}] "
                f"Processando: {jogo.nome} "
                f"(Steam ID: {jogo.steam_id})"
            )

            try:
                dados = dados_lote.get(str(jogo.steam_id))

                # GetItems continua sendo a fonte principal.
                # Quando não existe preço utilizável, usamos o fallback
                # individual controlado: página Steam -> AppDetails.
                if not dados or dados.get("preco") in ("N/A", None):
                    dados_fallback = await _executar_fallback_preco(
                        coletor,
                        jogo,
                    )

                    preco_fb, preco_original_fb, desconto_fb = (
                        _extrair_preco_fallback(dados_fallback)
                    )

                    if preco_fb is None:
                        print(
                            "  Fallback não conseguiu determinar o preço. "
                            "Ignorando nesta execução."
                        )
                        ignorados += 1
                        continue

                    print(
                        f"  Fallback resolveu o preço: "
                        f"{_formatar_moeda(preco_fb)} "
                        f"(fonte={dados_fallback.get('fonte', 'desconhecida')})"
                    )

                    dados = {
                        **(dados or {}),
                        "preco": dados_fallback.get("preco"),
                        "preco_sem_desconto": (
                            dados_fallback.get("preco_sem_desconto")
                        ),
                        "desconto": dados_fallback.get("desconto"),
                    }

                if "erro" in dados:
                    erro = dados.get("erro", "Dados não disponíveis")
                    print(f"  Erro retornado pelo GetItems: {erro}")
                    erros += 1
                    continue

                # Conversão de preço atual
                preco_str = dados.get("preco", "N/A")

                preco_num = _parse_preco(preco_str)

                if preco_num is None:
                    print(
                        "  Preço indisponível. "
                        "O histórico não será atualizado."
                    )
                    ignorados += 1
                    continue

                # Conversão de preço original
                preco_original_str = dados.get(
                    "preco_sem_desconto",
                    "N/A",
                )

                preco_original_num = _parse_preco(preco_original_str)

                if preco_original_num is None:
                    preco_original_num = preco_num

                desconto_str = dados.get("desconto", "0%")
                try:
                    desconto = (
                        int(desconto_str.replace("%", ""))
                        if desconto_str
                        else 0
                    )
                except (ValueError, AttributeError):
                    desconto = 0

                # Dados da promoção retornados pelo GetItems.
                promocao_id = dados.get("promocao_id")
                promocao_nome = dados.get("promocao_nome")
                promocao_tipo = dados.get("promocao_tipo")
                promocao_inicio = dados.get("promocao_inicio")
                promocao_fim = dados.get("promocao_fim")

                ultimo_registro = ultimos_historicos.get(jogo.id)

                deve_criar = False
                motivos = []

                if ultimo_registro is None:
                    deve_criar = True
                    motivos.append("Primeiro registro")
                else:
                    preco_atual_float = round(float(preco_num), 2)
                    preco_anterior_float = round(
                        float(ultimo_registro.preco_atual),
                        2,
                    )

                    if abs(
                        preco_atual_float - preco_anterior_float
                    ) > 0.01:
                        deve_criar = True
                        motivos.append(
                            "Preço alterado "
                            f"(R$ {preco_anterior_float:.2f} -> "
                            f"R$ {preco_atual_float:.2f})"
                        )

                    preco_original_anterior = (
                        float(ultimo_registro.preco_sem_desconto)
                        if ultimo_registro.preco_sem_desconto is not None
                        else None
                    )

                    if (
                        preco_original_anterior is None
                        and preco_original_num is not None
                    ):
                        deve_criar = True
                        motivos.append(
                            "Preço original passou a ser informado"
                        )
                    elif (
                        preco_original_anterior is not None
                        and preco_original_num is not None
                        and abs(
                            round(preco_original_num, 2)
                            - round(preco_original_anterior, 2)
                        ) > 0.01
                    ):
                        deve_criar = True
                        motivos.append(
                            f"Preço original alterado "
                            f"({_formatar_moeda(preco_original_anterior)} -> "
                            f"{_formatar_moeda(preco_original_num)})"
                        )

                    if desconto != (ultimo_registro.desconto or 0):
                        deve_criar = True
                        motivos.append(
                            "Desconto alterado "
                            f"({ultimo_registro.desconto or 0}% -> {desconto}%)"
                        )

                    if promocao_id != ultimo_registro.promocao_id:
                        deve_criar = True
                        motivos.append("ID da promoção alterado")

                    if promocao_nome != ultimo_registro.promocao_nome:
                        deve_criar = True
                        motivos.append("Nome da promoção alterado")

                    if promocao_tipo != ultimo_registro.promocao_tipo:
                        deve_criar = True
                        motivos.append("Tipo da promoção alterado")

                    if (
                        promocao_inicio
                        != ultimo_registro.promocao_inicio
                    ):
                        deve_criar = True
                        motivos.append("Início da promoção alterado")

                    if promocao_fim != ultimo_registro.promocao_fim:
                        deve_criar = True
                        motivos.append("Fim da promoção alterado")

                if not deve_criar:
                    print(
                        f"  Nenhuma mudança de estado "
                        f"({_formatar_moeda(preco_num)}, {desconto}%, "
                        f"promoção={promocao_tipo or 'nenhuma'})"
                    )
                    ignorados += 1
                    continue

                # A mudança detectada pelo GetItems será confirmada por uma
                # fonte individual antes de entrar no histórico.
                #
                # Isso protege casos como:
                # GetItems -> R$ 13,99
                # Página Steam -> R$ 39,99
                #
                # A confirmação é feita somente quando já existe uma mudança
                # real a registrar, evitando scraping em massa.
                dados_confirmacao = await _executar_fallback_preco(
                    coletor,
                    jogo,
                )

                (
                    preco_confirmado,
                    preco_original_confirmado,
                    desconto_confirmado,
                ) = _extrair_preco_fallback(dados_confirmacao)

                if preco_confirmado is not None:
                    if abs(preco_confirmado - preco_num) > 0.01:
                        print(
                            "  ATENÇÃO: divergência entre GetItems e "
                            "fonte individual."
                        )
                        print(
                            f"    GetItems: "
                            f"{_formatar_moeda(preco_num)}"
                        )
                        print(
                            f"    Confirmado: "
                            f"{_formatar_moeda(preco_confirmado)}"
                        )

                        preco_num = preco_confirmado
                        preco_original_num = (
                            preco_original_confirmado
                            if preco_original_confirmado is not None
                            else preco_confirmado
                        )
                        desconto = desconto_confirmado

                        # Recalcula a mudança contra o último histórico para
                        # evitar gravar uma falsa alteração causada apenas
                        # pelo GetItems.
                        if ultimo_registro is not None:
                            preco_anterior_float = round(
                                float(ultimo_registro.preco_atual),
                                2,
                            )

                            if abs(
                                preco_num - preco_anterior_float
                            ) <= 0.01:
                                deve_criar = False
                                print(
                                    "  Divergência descartada: a fonte "
                                    "individual confirma o preço anterior."
                                )

                if not deve_criar:
                    ignorados += 1
                    continue

                historico = HistoricoPreco(
                    jogo_id=jogo.id,
                    nome_jogo=jogo.nome,
                    plataforma="Steam",
                    preco_atual=preco_num,
                    preco_sem_desconto=preco_original_num,
                    desconto=desconto,
                    data_coleta=datetime.now(),
                    promocao_id=promocao_id,
                    promocao_nome=promocao_nome,
                    promocao_tipo=promocao_tipo,
                    promocao_inicio=promocao_inicio,
                    promocao_fim=promocao_fim,
                )

                db.add(historico)

                print("  " + " | ".join(motivos))
                print(
                    f"  Novo registro: {_formatar_moeda(preco_num)} "
                    f"(original: {_formatar_moeda(preco_original_num)}, "
                    f"desconto de {desconto}%)"
                )

                if promocao_tipo:
                    print(
                        f"  Tipo de promoção Steam: {promocao_tipo}"
                    )

                if promocao_fim:
                    print(
                        "  Fim da promoção: "
                        f"{promocao_fim.strftime('%d/%m/%Y %H:%M UTC')}"
                    )

                alterados += 1

                if preco_original_num > 0:
                    jogo.preco_base_steam = preco_original_num
                    jogo.updated_at = datetime.now()

            except Exception as erro:
                print(f"  Erro: {erro}")
                erros += 1

        db.commit()

        print("\n" + "=" * 60)
        print("RESUMO DA COLETA")
        print("=" * 60)
        print(f"  Novos registros: {alterados}")
        print(f"  Ignorados (sem mudança): {ignorados}")
        print(f"  Erros: {erros}")
        print(f"  Total: {len(jogos)}")
        print(
            f"  Fim: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

    except Exception as erro:
        db.rollback()
        print(f"\nErro geral: {erro}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


async def verificar_historico():
    """Verifica quantos registros de historico existem por dia."""
    db = SessionLocal()
    try:
        count = db.query(HistoricoPreco).count()
        ultimo = db.query(HistoricoPreco).order_by(HistoricoPreco.data_coleta.desc()).first()

        por_dia = db.query(
            cast(HistoricoPreco.data_coleta, Date).label("data"),
            func.count(HistoricoPreco.id).label("total")
        ).group_by("data").order_by("data").all()

        print(f"\nHISTORICO ATUAL:")
        print(f"  Total de registros: {count}")
        print(f"  Dias com registros: {len(por_dia)}")

        if ultimo:
            print(f"  Ultima coleta: {ultimo.data_coleta.strftime('%d/%m/%Y %H:%M')}")
            print(f"  Ultimo preco: R$ {ultimo.preco_atual:.2f} ({ultimo.plataforma})")

        if por_dia:
            print("\n  Registros por dia:")
            for item in por_dia[-5:]:
                print(f"    {item[0].strftime('%d/%m/%Y')}: {item[1]} registros")

    finally:
        db.close()


async def limpar_historico_duplicado():
    """
    Remove somente registros com o mesmo estado completo.

    Registros diferentes no mesmo dia são preservados, pois podem
    representar mudanças reais de preço ou promoção.
    """
    db = SessionLocal()

    try:
        print(
            "Procurando duplicatas exatas no histórico "
            "(sem apagar mudanças legítimas no mesmo dia)..."
        )

        campos_estado = [
            HistoricoPreco.jogo_id,
            HistoricoPreco.plataforma,
            HistoricoPreco.preco_atual,
            HistoricoPreco.preco_sem_desconto,
            HistoricoPreco.desconto,
            HistoricoPreco.promocao_id,
            HistoricoPreco.promocao_nome,
            HistoricoPreco.promocao_tipo,
            HistoricoPreco.promocao_inicio,
            HistoricoPreco.promocao_fim,
        ]

        duplicatas = (
            db.query(
                *campos_estado,
                func.count(HistoricoPreco.id).label("total"),
            )
            .group_by(*campos_estado)
            .having(func.count(HistoricoPreco.id) > 1)
            .all()
        )

        if not duplicatas:
            print("  Nenhuma duplicata exata encontrada.")
            return

        print(
            f"  Encontrados {len(duplicatas)} grupos de "
            "duplicatas exatas."
        )

        for dup in duplicatas:
            filtros = [
                HistoricoPreco.jogo_id == dup.jogo_id,
                HistoricoPreco.plataforma == dup.plataforma,
                HistoricoPreco.preco_atual == dup.preco_atual,
                HistoricoPreco.preco_sem_desconto == dup.preco_sem_desconto,
                HistoricoPreco.desconto == dup.desconto,
                HistoricoPreco.promocao_id == dup.promocao_id,
                HistoricoPreco.promocao_nome == dup.promocao_nome,
                HistoricoPreco.promocao_tipo == dup.promocao_tipo,
                HistoricoPreco.promocao_inicio == dup.promocao_inicio,
                HistoricoPreco.promocao_fim == dup.promocao_fim,
            ]

            registros = (
                db.query(HistoricoPreco)
                .filter(and_(*filtros))
                .order_by(HistoricoPreco.data_coleta.desc())
                .all()
            )

            for registro in registros[1:]:
                db.delete(registro)

        db.commit()
        print("  Duplicatas exatas removidas.")

    except Exception as erro:
        db.rollback()
        print(f"  Erro: {erro}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Coleta incremental do histórico de preços da Steam."
    )
    parser.add_argument(
        "--primeira-coleta",
        action="store_true",
        help="Usa a janela máxima de 30 dias + 48h de overlap nesta execução.",
    )
    args = parser.parse_args()
    asyncio.run(
        coletar_historico_precos(
            primeira_coleta=args.primeira_coleta
        )
    )