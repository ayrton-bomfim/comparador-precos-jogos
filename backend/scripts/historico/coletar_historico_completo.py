# -*- coding: utf-8 -*-
"""
Cópia temporária do coletor diário da Steam.

Com --todos-null-disponibilidade-br, executa o mesmo fluxo completo de preços,
promoções, disponibilidade e histórico para todos os jogos cujo status de
disponibilidade BR está NULL. O coletor diário oficial permanece intocado.
"""

import sys
import os
import asyncio
import argparse
import csv
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

# Reutiliza a classificação regional corrigida do coletor v10.
# O v10 não executa sua rotina principal ao ser importado.
try:
    from coletar_dados_steam_completo_v10 import (
        processar_jogo as processar_disponibilidade_steam_br,
    )
except ImportError as erro_import:
    raise ImportError(
        "Não foi possível importar o coletor v10. Salve "
        "coletar_dados_steam_completo_v10.py na raiz do projeto."
    ) from erro_import

load_dotenv()


STEAM_APP_LIST_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
OVERLAP_HOURS = 48
PRIMEIRA_JANELA_DIAS = 30
STEAM_API_KEY_NAMES = ["STEAM_API_KEY", "STEAM_WEB_API_KEY", "STEAM_KEY"]

# Fallback individual: usado somente quando o GetItems não resolve
# o preço ou quando detectamos uma mudança de estado que precisa
# de confirmação antes de gravar no histórico.
FALLBACK_INTERVAL_SECONDS = 2.0
COMMIT_PROGRESSO_A_CADA = 100

# Evita reconsultar diariamente casos sem conclusão ou explicitamente
# indisponíveis, que serão avaliados manualmente. Para registros sem status,
# reutiliza steam_dados_atualizados_em como intervalo mínimo de revisão.
DISPONIBILIDADE_BR_REVALIDAR_APOS_DIAS = 30
ARQUIVO_DISPONIBILIDADE_BR = os.path.join(
    ROOT_DIR, "coleta_disponibilidade_br_diaria.csv"
)
STATUS_DISPONIBILIDADE_BR_VALIDOS = {
    "DISPONIVEL", "GRATUITO", "INDISPONIVEL", "INDETERMINADO"
}


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


def _disponibilidade_precisa_de_verificacao(jogo, forcar=False):
    """Decide quando o processo diário deve consultar a disponibilidade regional.

    - DISPONIVEL/GRATUITO: só revalida se a coleta diária não conseguiu
      confirmar preço, ou seja, quando forcar=True.
    - INDISPONIVEL/INDETERMINADO: não reconsulta automaticamente; ficam para
      revisão individual conforme a regra do projeto.
    - NULL: consulta quando nunca foi atualizado ou quando o último dado
      Steam tem pelo menos 30 dias.
    """
    status = (getattr(jogo, "steam_disponibilidade_br", None) or "").upper()

    if status in {"INDISPONIVEL", "INDETERMINADO"}:
        return False

    if forcar:
        return status in {"DISPONIVEL", "GRATUITO"}

    if status:
        return False

    ultima_atualizacao = getattr(jogo, "steam_dados_atualizados_em", None)
    if ultima_atualizacao is None:
        return True

    agora = (
        datetime.now(ultima_atualizacao.tzinfo)
        if ultima_atualizacao.tzinfo
        else datetime.now()
    )
    return (agora - ultima_atualizacao) >= timedelta(
        days=DISPONIBILIDADE_BR_REVALIDAR_APOS_DIAS
    )


def _registrar_diagnostico_disponibilidade(linha):
    """Acrescenta o resultado da verificação ao CSV para auditoria manual."""
    existe = os.path.exists(ARQUIVO_DISPONIBILIDADE_BR)
    campos = [
        "data_verificacao", "modo_execucao", "jogo_id", "steam_id", "nome",
        "status_anterior", "status_novo", "observacao",
        "classificacao_execucao", "http_status_appdetails",
        "http_status_store", "steam_is_free", "preco_base_steam", "erro",
    ]
    with open(
        ARQUIVO_DISPONIBILIDADE_BR,
        "a",
        newline="",
        encoding="utf-8-sig",
    ) as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos)
        if not existe or os.path.getsize(ARQUIVO_DISPONIBILIDADE_BR) == 0:
            escritor.writeheader()
        escritor.writerow({campo: linha.get(campo, "") for campo in campos})


def _verificar_disponibilidade_br_diaria(
    db,
    jogo,
    tentados,
    resumo,
    motivo,
    forcar=False,
    simular=False,
    forcar_null=False,
):
    """Aplica a mesma classificação regional do coletor v10 sem mexer no histórico.

    Só grava status se AppDetails e a eventual verificação da página da loja
    retornarem uma classificação válida. Erros/429 preservam o estado existente.
    """
    if jogo.id in tentados:
        return False

    # Na varredura especial, todos os registros selecionados começaram com
    # disponibilidade NULL. Esses casos devem passar pelo classificador v10
    # mesmo que steam_dados_atualizados_em seja recente.
    status_atual = getattr(jogo, "steam_disponibilidade_br", None)
    if not (forcar_null and status_atual is None):
        if not _disponibilidade_precisa_de_verificacao(jogo, forcar=forcar):
            return False

    tentados.add(jogo.id)
    status_anterior = getattr(jogo, "steam_disponibilidade_br", None)
    print(
        f"  Verificando disponibilidade BR via v10 ({motivo})..."
    )

    resultado = processar_disponibilidade_steam_br(jogo)
    classificacao_execucao = resultado.get("classificacao") or ""
    dados_status = resultado.get("dados") or {}
    status_novo = dados_status.get("steam_disponibilidade_br")
    observacao = dados_status.get("steam_disponibilidade_br_observacao") or ""
    erro = resultado.get("erro") or ""

    if classificacao_execucao in {"OK", "NAO_E_GAME"}:
        if status_novo in STATUS_DISPONIBILIDADE_BR_VALIDOS:
            # Não rebaixar status positivo apenas por uma consulta inconclusiva.
            if status_anterior in {"DISPONIVEL", "GRATUITO"} and status_novo == "INDETERMINADO":
                resumo["nao_classificados_com_sucesso"] += 1
                print(
                    f"  Verificação inconclusiva; mantendo status anterior "
                    f"{status_anterior}. Evidência: {observacao or '-'}"
                )
            else:
                jogo.steam_disponibilidade_br = status_novo
                if hasattr(jogo, "steam_is_free") and "steam_is_free" in dados_status:
                    jogo.steam_is_free = dados_status.get("steam_is_free")
                resumo["verificacoes_ok"] += 1
                resumo[f"status_{status_novo.lower()}"] += 1
                print(
                    f"  Disponibilidade BR: {status_anterior or 'NULL'} -> "
                    f"{status_novo} | evidência: {observacao or '-'}"
                )
        else:
            # AppDetails respondeu com sucesso, mas não classificou um jogo
            # comercial (ex.: type != game). Não inventa status. Atualizar a
            # data da verificação evita repetir o mesmo AppID diariamente.
            resumo["nao_classificados_com_sucesso"] += 1
            print(
                f"  AppDetails processado sem status comercial: "
                f"{observacao or 'tipo diferente de game'}"
            )
        jogo.steam_dados_atualizados_em = datetime.now()
    else:
        # Não apagar nem substituir status em erro de rede/429.
        resumo["erros_disponibilidade"] += 1
        print(
            f"  Disponibilidade não atualizada: {classificacao_execucao} "
            f"{erro or ''}".rstrip()
        )

    _registrar_diagnostico_disponibilidade({
        "data_verificacao": datetime.now().isoformat(timespec="seconds"),
        "modo_execucao": "SIMULACAO" if simular else "APLICACAO",
        "jogo_id": jogo.id,
        "steam_id": jogo.steam_id,
        "nome": jogo.nome,
        "status_anterior": status_anterior or "",
        "status_novo": status_novo or "",
        "observacao": observacao,
        "classificacao_execucao": classificacao_execucao,
        "http_status_appdetails": resultado.get("http_status_appdetails") or "",
        "http_status_store": resultado.get("http_status_store") or "",
        "steam_is_free": dados_status.get("steam_is_free", ""),
        "preco_base_steam": dados_status.get("preco_base_steam", ""),
        "erro": erro,
    })

    # Retorna a mesma resposta para evitar consultas redundantes no fluxo diário.
    return {
        "classificacao_execucao": classificacao_execucao,
        "status_novo": status_novo,
        "observacao": observacao,
        "dados": dados_status,
        "erro": erro,
    }


def _classificar_por_getitems(jogo, dados, tentados, resumo):
    """Usa preço retornado pelo GetItems em contexto BR como evidência positiva."""
    status_atual = (getattr(jogo, "steam_disponibilidade_br", None) or "").upper()
    if status_atual or not dados or "erro" in dados:
        return False

    preco_texto = str(dados.get("preco") or "").strip()
    preco_lower = preco_texto.lower()
    if preco_lower in {"grátis", "gratis", "free"}:
        status_novo = "GRATUITO"
        is_free = True
        observacao = "GetItems com contexto BR retornou o jogo como gratuito"
    else:
        preco = _parse_preco(dados.get("preco"))
        if preco is None or preco <= 0:
            return False
        status_novo = "DISPONIVEL"
        is_free = False
        observacao = "GetItems com contexto BR retornou preço próprio"

    jogo.steam_disponibilidade_br = status_novo
    if hasattr(jogo, "steam_is_free"):
        jogo.steam_is_free = is_free
    tentados.add(jogo.id)
    resumo["verificacoes_ok"] += 1
    resumo[f"status_{status_novo.lower()}"] += 1
    print(
        f"  Disponibilidade BR: NULL -> {status_novo} | evidência: {observacao}"
    )
    _registrar_diagnostico_disponibilidade({
        "data_verificacao": datetime.now().isoformat(timespec="seconds"),
        "modo_execucao": "APLICACAO",
        "jogo_id": jogo.id,
        "steam_id": jogo.steam_id,
        "nome": jogo.nome,
        "status_anterior": "",
        "status_novo": status_novo,
        "observacao": observacao,
        "classificacao_execucao": "OK_GETITEMS",
        "http_status_appdetails": "",
        "http_status_store": "",
        "steam_is_free": is_free,
        "preco_base_steam": getattr(jogo, "preco_base_steam", None),
        "erro": "",
    })
    return True


def _preco_from_verificacao_disponibilidade(resultado):
    """Reutiliza os dados de preço da resposta AppDetails usada na classificação."""
    if not resultado:
        return None
    dados = resultado.get("dados") or {}
    status = dados.get("steam_disponibilidade_br")
    atual = dados.get("steam_preco_atual_brl")
    original = dados.get("steam_preco_original_brl")
    desconto = dados.get("steam_desconto_percentual", 0)

    if status == "GRATUITO":
        return {
            "preco": "Grátis",
            "preco_sem_desconto": "Grátis",
            "desconto": "0%",
            "fonte": "APPDETAILS_V10_REUTILIZADO",
        }
    if status != "DISPONIVEL" or atual is None:
        return None
    if original is None:
        original = atual
    return {
        "preco": _formatar_moeda(atual),
        "preco_sem_desconto": _formatar_moeda(original),
        "desconto": f"{int(desconto or 0)}%",
        "fonte": "APPDETAILS_V10_REUTILIZADO",
    }


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


async def coletar_historico_precos(
    primeira_coleta=False,
    limite_jogos=None,
    somente_disponibilidade_br=False,
    simular_disponibilidade_br=False,
    todos_null_disponibilidade_br=False,
):
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
    print("Fallback: AppDetails -> página individual Steam, somente quando necessário")
    print("Disponibilidade BR: classificação do v10 para status ausente e casos suspeitos")
    print("INDETERMINADO/INDISPONIVEL: não reconsultados automaticamente; ficam para revisão manual")
    if todos_null_disponibilidade_br:
        print("MODO ESPECIAL: processar todos os jogos com steam_disponibilidade_br = NULL")
        print("Mantém o fluxo completo de preço, promoção e histórico; ignora o filtro GetAppList")
    print("Novo registro: mudança de estado do preço/promoção")
    print("=" * 60)
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    db = SessionLocal()
    coletor = SteamColetor()

    try:
        if todos_null_disponibilidade_br:
            # Não consulta GetAppList neste modo: a ideia é incluir TODOS os
            # jogos locais com status regional NULL, independentemente de
            # quando a Steam diz que o AppID foi modificado.
            apps_modificados = set()
            print("\nFiltro incremental GetAppList ignorado nesta varredura especial.")
        else:
            inicio_janela = _obter_janela_incremental(db, primeira_coleta)
            apps_modificados = _buscar_apps_steam_modificados(inicio_janela)

        jogos_catalogo = (
            db.query(Jogo)
            .filter(Jogo.steam_id.isnot(None))
            .all()
        )

        ids_catalogo = {str(jogo.steam_id) for jogo in jogos_catalogo}

        if todos_null_disponibilidade_br:
            # Seleção exata de NULL no banco, sem excluir jogos gratuitos:
            # o preço/status real deles será determinado pelo mesmo fluxo diário.
            jogos = [
                jogo
                for jogo in jogos_catalogo
                if getattr(jogo, "steam_disponibilidade_br", None) is None
            ]
        else:
            # Fluxo diário original, preservado sem alteração.
            jogos = [
                jogo
                for jogo in jogos_catalogo
                if str(jogo.steam_id) in apps_modificados
                and (getattr(jogo, "steam_disponibilidade_br", None) or "").upper()
                != "GRATUITO"
            ]

        total_candidatos_diarios = len(jogos)
        if somente_disponibilidade_br:
            # O modo separado usa apenas os candidatos sem status regional
            # recente. Não consulta GetItems nem cria registros de histórico.
            jogos = [
                jogo for jogo in jogos
                if _disponibilidade_precisa_de_verificacao(jogo, forcar=False)
            ]

        if limite_jogos is not None:
            jogos = jogos[:limite_jogos]

        print(f"\nJogos com Steam no banco: {len(jogos_catalogo):,}")
        if todos_null_disponibilidade_br:
            print(f"Jogos com steam_disponibilidade_br NULL: {total_candidatos_diarios:,}")
        else:
            print(f"Jogos candidatos encontrados no catálogo: {total_candidatos_diarios:,}")
            print(f"Apps Steam fora do catálogo: {len(apps_modificados - ids_catalogo):,}")
        if limite_jogos is not None:
            print(f"Limite desta execução: {limite_jogos}")

        if not jogos:
            if somente_disponibilidade_br:
                print("Nenhum candidato elegível para verificação de disponibilidade BR nesta execução.")
                if simular_disponibilidade_br:
                    db.rollback()
                else:
                    db.commit()
            else:
                print("Nenhum jogo do catálogo foi modificado na janela consultada.")
                db.commit()
            return

        if somente_disponibilidade_br:
            print("\nMODO SOMENTE DISPONIBILIDADE BR")
            print(f"Candidatos elegíveis: {len(jogos):,}")
            print(f"Simulação sem gravar no PostgreSQL: {simular_disponibilidade_br}")

            resumo_disponibilidade = {
                "verificacoes_ok": 0,
                "status_disponivel": 0,
                "status_gratuito": 0,
                "status_indisponivel": 0,
                "status_indeterminado": 0,
                "nao_classificados_com_sucesso": 0,
                "erros_disponibilidade": 0,
            }
            disponibilidade_tentados = set()

            for i, jogo in enumerate(jogos, 1):
                print(
                    f"\n[{i}/{len(jogos)}] {jogo.nome} "
                    f"(Steam ID: {jogo.steam_id})"
                )
                _verificar_disponibilidade_br_diaria(
                    db,
                    jogo,
                    disponibilidade_tentados,
                    resumo_disponibilidade,
                    motivo="modo somente disponibilidade",
                    forcar=False,
                    simular=simular_disponibilidade_br,
                )
                if not simular_disponibilidade_br and i % COMMIT_PROGRESSO_A_CADA == 0:
                    db.commit()
                    print(f"  [CHECKPOINT] Disponibilidade salva: {i}/{len(jogos)}")

            if simular_disponibilidade_br:
                db.rollback()
                print("\nSIMULAÇÃO: nenhuma alteração foi gravada no PostgreSQL.")
            else:
                db.commit()
                print("\nAtualizações de disponibilidade confirmadas no PostgreSQL.")

            print(f"CSV de diagnóstico: {ARQUIVO_DISPONIBILIDADE_BR}")
            print(
                "Resumo: "
                f"OK={resumo_disponibilidade['verificacoes_ok']}, "
                f"erros={resumo_disponibilidade['erros_disponibilidade']}, "
                f"não classificáveis={resumo_disponibilidade['nao_classificados_com_sucesso']}"
            )
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
        disponibilidade_tentados = set()
        resumo_disponibilidade = {
            "verificacoes_ok": 0,
            "status_disponivel": 0,
            "status_gratuito": 0,
            "status_indisponivel": 0,
            "status_indeterminado": 0,
            "nao_classificados_com_sucesso": 0,
            "erros_disponibilidade": 0,
        }

        for i, jogo in enumerate(jogos, 1):
            print(
                f"\n[{i}/{len(jogos)}] "
                f"Processando: {jogo.nome} "
                f"(Steam ID: {jogo.steam_id})"
            )

            try:
                dados = dados_lote.get(str(jogo.steam_id))

                # GetItems já foi consultado em lote com country_code=BR.
                # Se retornou preço próprio ou gratuito, usamos isso como
                # evidência positiva e evitamos outro AppDetails individual.
                _classificar_por_getitems(
                    jogo,
                    dados,
                    disponibilidade_tentados,
                    resumo_disponibilidade,
                )

                # Sem evidência positiva no lote, aplica o classificador v10.
                # INDETERMINADO/INDISPONIVEL continuam reservados para revisão.
                resultado_disponibilidade = _verificar_disponibilidade_br_diaria(
                    db,
                    jogo,
                    disponibilidade_tentados,
                    resumo_disponibilidade,
                    motivo="status ausente/desatualizado",
                    forcar=False,
                    forcar_null=todos_null_disponibilidade_br,
                )

                # GetItems continua sendo a fonte principal.
                # Quando não existe preço utilizável, usamos o fallback
                # individual controlado: AppDetails -> página Steam.
                if not dados or dados.get("preco") in ("N/A", None):
                    status_regional = (
                        getattr(jogo, "steam_disponibilidade_br", None) or ""
                    ).upper()

                    # Não repetir AppDetails + Playwright quando a consulta
                    # regional já deixou o caso inconclusivo/indisponível.
                    if status_regional in {"INDETERMINADO", "INDISPONIVEL"}:
                        print(
                            f"  Fallback ignorado: status regional {status_regional}; "
                            "caso reservado para revisão manual."
                        )
                        ignorados += 1
                        continue

                    # Se o v10 já consultou AppDetails e obteve preço, reutiliza-o.
                    dados_fallback = _preco_from_verificacao_disponibilidade(
                        resultado_disponibilidade
                    )
                    if dados_fallback is None:
                        dados_fallback = await _executar_fallback_preco(
                            coletor,
                            jogo,
                        )

                    preco_fb, preco_original_fb, desconto_fb = (
                        _extrair_preco_fallback(dados_fallback)
                    )

                    if preco_fb is None:
                        # Se o jogo já constava como comercializado, mas tanto
                        # GetItems quanto o fallback falharam em obter preço,
                        # revalidamos o status regional. Em caso de erro/429,
                        # o status atual é preservado.
                        _verificar_disponibilidade_br_diaria(
                            db,
                            jogo,
                            disponibilidade_tentados,
                            resumo_disponibilidade,
                            motivo="preço não confirmado pelo GetItems/fallback",
                            forcar=True,
                            forcar_null=todos_null_disponibilidade_br,
                        )
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
                    _verificar_disponibilidade_br_diaria(
                        db,
                        jogo,
                        disponibilidade_tentados,
                        resumo_disponibilidade,
                        motivo="preço não interpretável na coleta diária",
                        forcar=True,
                    )
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
            finally:
                # Checkpoint periódico para não perder horas de progresso se
                # a coleta for interrompida durante a primeira varredura.
                if i % COMMIT_PROGRESSO_A_CADA == 0:
                    db.commit()
                    print(f"  [CHECKPOINT] Progresso salvo: {i}/{len(jogos)} jogos")

        db.commit()

        print("\n" + "=" * 60)
        print("RESUMO DA COLETA")
        print("=" * 60)
        print(f"  Novos registros: {alterados}")
        print(f"  Ignorados (sem mudança): {ignorados}")
        print(f"  Erros: {erros}")
        print(f"  Total: {len(jogos)}")
        print("\n  DISPONIBILIDADE STEAM BR:")
        print(f"    Verificações válidas: {resumo_disponibilidade['verificacoes_ok']}")
        print(f"    Disponível: {resumo_disponibilidade['status_disponivel']}")
        print(f"    Gratuito: {resumo_disponibilidade['status_gratuito']}")
        print(f"    Indisponível: {resumo_disponibilidade['status_indisponivel']}")
        print(f"    Indeterminado: {resumo_disponibilidade['status_indeterminado']}")
        print(
            "    Sem classificação comercial (resposta válida): "
            f"{resumo_disponibilidade['nao_classificados_com_sucesso']}"
        )
        print(f"    Erros de verificação: {resumo_disponibilidade['erros_disponibilidade']}")
        print(f"    Diagnóstico CSV: {ARQUIVO_DISPONIBILIDADE_BR}")
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
    parser.add_argument(
        "--limite-jogos",
        type=int,
        default=None,
        help="Limita o número de candidatos processados nesta execução.",
    )
    parser.add_argument(
        "--somente-disponibilidade-br",
        action="store_true",
        help="Verifica apenas a disponibilidade regional, sem coletar preços ou gravar histórico.",
    )
    parser.add_argument(
        "--simular-disponibilidade-br",
        action="store_true",
        help="Com --somente-disponibilidade-br, não grava as alterações no PostgreSQL.",
    )
    parser.add_argument(
        "--todos-null-disponibilidade-br",
        action="store_true",
        help=(
            "Executa a coleta completa de preço/promoção/histórico para todos "
            "os jogos Steam com steam_disponibilidade_br NULL, sem filtro GetAppList."
        ),
    )
    args = parser.parse_args()

    if args.limite_jogos is not None and args.limite_jogos <= 0:
        parser.error("--limite-jogos deve ser maior que zero.")
    if args.simular_disponibilidade_br and not args.somente_disponibilidade_br:
        parser.error("--simular-disponibilidade-br exige --somente-disponibilidade-br.")
    if args.todos_null_disponibilidade_br and args.somente_disponibilidade_br:
        parser.error(
            "--todos-null-disponibilidade-br executa a coleta completa; "
            "não use junto com --somente-disponibilidade-br."
        )

    asyncio.run(
        coletar_historico_precos(
            primeira_coleta=args.primeira_coleta,
            limite_jogos=args.limite_jogos,
            somente_disponibilidade_br=args.somente_disponibilidade_br,
            simular_disponibilidade_br=args.simular_disponibilidade_br,
            todos_null_disponibilidade_br=args.todos_null_disponibilidade_br,
        )
    )
