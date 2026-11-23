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
import csv
import requests

# Adiciona a raiz do projeto ao path ANTES dos imports do backend.
ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
    )
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, and_, cast, Date, insert, text, update
from dotenv import load_dotenv
from backend.coletores.steam_coletor import SteamColetor
from backend.banco_dados import SessionLocal
from backend.modelos import Jogo, HistoricoPreco

# Reutiliza a classificação de disponibilidade regional do coletor de dados
# Steam. O módulo não executa sua rotina principal ao ser importado.
from backend.coletores.coletar_dados_steam import (
    processar_jogo as processar_disponibilidade_steam_br,
)

load_dotenv()


STEAM_APP_LIST_URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"
OVERLAP_HOURS = 48
PRIMEIRA_JANELA_DIAS = 30
STEAM_API_KEY_NAMES = ["STEAM_API_KEY", "STEAM_WEB_API_KEY", "STEAM_KEY"]

# Consulta individual (AppDetails -> página da loja): usada somente quando o
# GetItems não traz preço ou quando não foi possível identificar o pacote do
# próprio jogo. O AppDetails aceita ~200 consultas a cada 5 minutos.
FALLBACK_INTERVAL_SECONDS = 1.5
# Teto de consultas individuais por execução. Se o GetItems estiver fora do
# ar, isso evita que a coleta volte a levar horas; o restante fica para o
# dia seguinte e a execução é marcada como parcial.
MAX_FALLBACKS_POR_EXECUCAO = 300
# Jogo DISPONIVEL sem preço já verificado individualmente há menos destes
# dias não é consultado de novo. Sem isso, os mesmos ~100 jogos (fora de
# venda, sem conclusão de disponibilidade) custavam ~14 min todo dia.
REVERIFICAR_SEM_PRECO_DIAS = 7
COMMIT_PROGRESSO_A_CADA = 100
# Abaixo desta fração de jogos com preço obtido, a etapa é marcada como falha.
COBERTURA_MINIMA = 0.9
# Até esta fração de erros a etapa conta como concluída com avisos.
TOLERANCIA_ERROS = 0.01
# Quantas mudanças são detalhadas no log; as demais entram só no resumo.
EXEMPLOS_NO_LOG = 15

# Evita reconsultar diariamente casos sem conclusão ou explicitamente
# indisponíveis, que serão avaliados manualmente. Para registros sem status,
# reutiliza steam_dados_atualizados_em como intervalo mínimo de revisão.
DISPONIBILIDADE_BR_REVALIDAR_APOS_DIAS = 30
ARQUIVO_DISPONIBILIDADE_BR = os.path.join(
    ROOT_DIR, "logs", "coleta_disponibilidade_br_diaria.csv"
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
    os.makedirs(os.path.dirname(ARQUIVO_DISPONIBILIDADE_BR), exist_ok=True)
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
    db, jogo, tentados, resumo, motivo, forcar=False, simular=False
):
    """Aplica a mesma classificação regional do coletor de dados Steam sem mexer no histórico.

    Só grava status se AppDetails e a eventual verificação da página da loja
    retornarem uma classificação válida. Erros/429 preservam o estado existente.
    """
    if jogo.id in tentados:
        return False

    if not _disponibilidade_precisa_de_verificacao(jogo, forcar=forcar):
        return False

    tentados.add(jogo.id)
    status_anterior = getattr(jogo, "steam_disponibilidade_br", None)
    print(
        f"  Verificando disponibilidade BR via AppDetails ({motivo})..."
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


def _carregar_candidatos_diarios(db):
    """Jogos DISPONIVEL na Steam BR, exceto os excluídos pela curadoria.

    Carrega só as colunas usadas na comparação. Antes, 190 mil linhas
    completas (descrições, requisitos em JSON etc.) eram trazidas como
    objetos ORM, e cada commit as expirava, gerando uma consulta ao banco por
    jogo no restante do laço.
    """
    return db.execute(text("""
        SELECT j.id, j.nome, j.steam_id, j.steam_dados_atualizados_em
        FROM jogos j
        WHERE j.steam_id IS NOT NULL
          AND upper(j.steam_disponibilidade_br) = 'DISPONIVEL'
          AND NOT EXISTS (
              SELECT 1 FROM auditorias_conteudo a
              WHERE a.jogo_id = j.id AND a.status = 'excluido'
          )
        ORDER BY j.id
    """)).all()


def _carregar_ultimos_estados_steam(db):
    """Último estado Steam de cada jogo, em uma única consulta."""
    linhas = db.execute(text("""
        SELECT DISTINCT ON (jogo_id)
               jogo_id, preco_atual, preco_sem_desconto, desconto,
               promocao_id, promocao_nome, promocao_tipo,
               promocao_inicio, promocao_fim
        FROM historico_precos
        WHERE plataforma = 'Steam'
        ORDER BY jogo_id, data_coleta DESC, id DESC
    """)).all()
    return {linha.jogo_id: linha for linha in linhas}


def _estado_de_dados(dados):
    """Converte a resposta da Steam no estado comparável com o histórico."""
    preco = _parse_preco(dados.get("preco"))
    if preco is None:
        return None

    original = _parse_preco(dados.get("preco_sem_desconto"))
    if original is None:
        original = preco

    try:
        desconto = int(str(dados.get("desconto") or "0").replace("%", "").replace("-", "").strip() or 0)
    except ValueError:
        desconto = 0

    return {
        "preco_atual": preco,
        "preco_sem_desconto": original,
        "desconto": desconto,
        **_promocao_de_dados(dados),
    }


def _promocao_de_dados(dados):
    """Campos de promoção informados pelo GetItems (vazios se não houver)."""
    dados = dados or {}
    return {
        campo: dados.get(campo)
        for campo in (
            "promocao_id", "promocao_nome", "promocao_tipo",
            "promocao_inicio", "promocao_fim",
        )
    }


def _motivos_mudanca(ultimo, estado):
    """Lista as mudanças de estado; vazia quando nada relevante mudou.

    A simples mudança de dia não gera registro.
    """
    if ultimo is None:
        return ["Primeiro registro"]

    motivos = []
    preco_anterior = round(float(ultimo.preco_atual), 2)
    if abs(estado["preco_atual"] - preco_anterior) > 0.01:
        motivos.append(
            f"Preço alterado (R$ {preco_anterior:.2f} -> R$ {estado['preco_atual']:.2f})"
        )

    if ultimo.preco_sem_desconto is None:
        motivos.append("Preço original passou a ser informado")
    elif abs(estado["preco_sem_desconto"] - round(float(ultimo.preco_sem_desconto), 2)) > 0.01:
        motivos.append("Preço original alterado")

    if estado["desconto"] != (ultimo.desconto or 0):
        motivos.append(f"Desconto alterado ({ultimo.desconto or 0}% -> {estado['desconto']}%)")

    for campo, rotulo in (
        ("promocao_id", "ID da promoção alterado"),
        ("promocao_nome", "Nome da promoção alterado"),
        ("promocao_tipo", "Tipo da promoção alterado"),
        ("promocao_inicio", "Início da promoção alterado"),
        ("promocao_fim", "Fim da promoção alterado"),
    ):
        if estado[campo] != getattr(ultimo, campo):
            motivos.append(rotulo)

    return motivos


def _aplicar_preco_confirmado(estado, dados_confirmacao):
    """Substitui preço/original/desconto pelos da fonte individual."""
    preco, original, desconto = _extrair_preco_fallback(dados_confirmacao or {})
    if preco is None:
        return None
    if not desconto:
        # A fonte individual não vê promoção: não herda a do GetItems.
        estado = {**estado, **_promocao_de_dados(None)}
    return {
        **estado,
        "preco_atual": preco,
        "preco_sem_desconto": original if original is not None else preco,
        "desconto": desconto,
    }


def _resumo_disponibilidade_vazio():
    return {
        "verificacoes_ok": 0,
        "status_disponivel": 0,
        "status_gratuito": 0,
        "status_indisponivel": 0,
        "status_indeterminado": 0,
        "nao_classificados_com_sucesso": 0,
        "erros_disponibilidade": 0,
    }


async def _coletar_precos_diarios(db, coletor, limite_jogos=None):
    """Coleta diária: GetItems em lote, comparação em memória e gravação em lote.

    Consultas individuais (AppDetails) ficam restritas a:
    - jogos sem preço no GetItems (até MAX_FALLBACKS_POR_EXECUCAO);
    - mudanças em que não foi possível identificar o pacote do próprio jogo.
    """
    inicio = time.monotonic()
    agora = datetime.now()

    total_catalogo = db.execute(
        text("SELECT count(*) FROM jogos WHERE steam_id IS NOT NULL")
    ).scalar()
    candidatos = _carregar_candidatos_diarios(db)
    total_candidatos = len(candidatos)
    if limite_jogos is not None:
        candidatos = candidatos[:limite_jogos]

    print(f"\nJogos com Steam no banco: {total_catalogo:,}")
    print(f"Jogos elegíveis (DISPONIVEL, fora da exclusão): {total_candidatos:,}")
    if limite_jogos is not None:
        print(f"Limite desta execução: {limite_jogos}")
    print(f"Seleção carregada em {time.monotonic() - inicio:.1f}s")

    if not candidatos:
        db.commit()
        return {
            "status": "sem_itens",
            "fonte": "Steam",
            "modo": "historico_precos",
            "total_catalogo": total_catalogo,
            "total_candidatos": total_candidatos,
            "total_processado": 0,
            "novos_registros": 0,
            "ignorados": 0,
            "erros": 0,
        }

    dados_lote = await coletor.coletar_precos_lote([c.steam_id for c in candidatos])

    t_hist = time.monotonic()
    ultimos = _carregar_ultimos_estados_steam(db)
    print(f"Últimos estados carregados: {len(ultimos):,} jogos ({time.monotonic() - t_hist:.1f}s)")

    novos = []
    precos_base = {}
    sem_preco = []
    a_confirmar = []
    ignorados = 0
    erros_lote = 0
    motivos_contagem = Counter()

    def registrar(candidato, estado, motivos):
        novos.append({
            "jogo_id": candidato.id,
            "nome_jogo": candidato.nome,
            "plataforma": "Steam",
            "data_coleta": agora,
            **estado,
        })
        for motivo in motivos:
            motivos_contagem[motivo.split(" (")[0]] += 1
        if len(novos) <= EXEMPLOS_NO_LOG:
            print(f"  [{candidato.steam_id}] {candidato.nome}: {' | '.join(motivos)}")
        if estado["preco_sem_desconto"] > 0:
            precos_base[candidato.id] = estado["preco_sem_desconto"]

    print(f"\nComparando com o histórico (primeiras {EXEMPLOS_NO_LOG} mudanças):")
    for candidato in candidatos:
        steam_id = str(candidato.steam_id)
        if steam_id in coletor.ids_lotes_falhos:
            erros_lote += 1
            continue

        dados = dados_lote.get(steam_id)
        estado = _estado_de_dados(dados) if dados and "erro" not in dados else None
        if estado is None:
            sem_preco.append(candidato)
            continue

        motivos = _motivos_mudanca(ultimos.get(candidato.id), estado)
        if not motivos:
            ignorados += 1
            continue

        if not dados.get("opcao_confiavel", True):
            a_confirmar.append((candidato, estado, motivos))
            continue

        registrar(candidato, estado, motivos)

    def gravar_pendentes():
        """Grava os registros novos e o preço base em poucas instruções."""
        gravados = 0
        while novos:
            bloco = novos[:1000]
            db.execute(insert(HistoricoPreco), bloco)
            del novos[:1000]
            gravados += len(bloco)
        if precos_base:
            db.execute(
                update(Jogo),
                [
                    {"id": jogo_id, "preco_base_steam": valor, "updated_at": agora}
                    for jogo_id, valor in precos_base.items()
                ],
            )
            precos_base.clear()
        db.commit()
        return gravados

    gravados = gravar_pendentes()
    print(
        f"\nGravados {gravados:,} registros do lote "
        f"({time.monotonic() - inicio:.0f}s desde o início)."
    )

    # Mudanças sem pacote do jogo identificado: confirma pelo AppDetails.
    confirmadas = descartadas = 0
    if a_confirmar:
        print(f"\nConfirmando {len(a_confirmar)} mudança(s) sem pacote do jogo identificado...")
    for candidato, estado, motivos in a_confirmar:
        confirmacao = await _executar_fallback_preco(coletor, candidato)
        estado_confirmado = _aplicar_preco_confirmado(estado, confirmacao)
        if estado_confirmado is None:
            descartadas += 1
            continue
        motivos = _motivos_mudanca(ultimos.get(candidato.id), estado_confirmado)
        if motivos:
            confirmadas += 1
            registrar(candidato, estado_confirmado, motivos)
        else:
            descartadas += 1
            ignorados += 1

    # Jogos sem preço no GetItems: AppDetails -> página da loja e, se nada
    # funcionar, revalida a disponibilidade regional.
    resumo_disponibilidade = _resumo_disponibilidade_vazio()
    disponibilidade_tentados = set()
    resolvidos_fallback = 0
    limite_reverificacao = agora - timedelta(days=REVERIFICAR_SEM_PRECO_DIAS)
    a_verificar = [
        c for c in sem_preco
        if c.steam_dados_atualizados_em is None
        or c.steam_dados_atualizados_em.replace(tzinfo=None) < limite_reverificacao
    ]
    sem_preco_em_espera = len(sem_preco) - len(a_verificar)
    sem_preco_nao_verificados = max(0, len(a_verificar) - MAX_FALLBACKS_POR_EXECUCAO)
    if sem_preco:
        print(
            f"\nSem preço no GetItems: {len(sem_preco)} jogo(s); "
            f"{sem_preco_em_espera} verificados há menos de {REVERIFICAR_SEM_PRECO_DIAS} dias; "
            f"consultando {min(len(a_verificar), MAX_FALLBACKS_POR_EXECUCAO)} individualmente"
            + (f" ({sem_preco_nao_verificados} ficam para a próxima execução)" if sem_preco_nao_verificados else "")
            + "..."
        )
    for candidato in a_verificar[:MAX_FALLBACKS_POR_EXECUCAO]:
        dados_fallback = await _executar_fallback_preco(coletor, candidato)
        estado = _aplicar_preco_confirmado(
            _promocao_de_dados(dados_lote.get(str(candidato.steam_id))),
            dados_fallback,
        )
        if estado is None:
            jogo = db.get(Jogo, candidato.id)
            _verificar_disponibilidade_br_diaria(
                db,
                jogo,
                disponibilidade_tentados,
                resumo_disponibilidade,
                motivo="preço não confirmado pelo GetItems/fallback",
                forcar=True,
            )
            ignorados += 1
            continue

        resolvidos_fallback += 1
        motivos = _motivos_mudanca(ultimos.get(candidato.id), estado)
        if motivos:
            registrar(candidato, estado, motivos)
        else:
            ignorados += 1

    gravados += gravar_pendentes()

    duracao = time.monotonic() - inicio
    com_preco = len(candidatos) - erros_lote - len(sem_preco) + resolvidos_fallback
    cobertura = com_preco / len(candidatos) if candidatos else 1.0
    erros = erros_lote + sem_preco_nao_verificados

    print("\n" + "=" * 60)
    print("RESUMO DA COLETA STEAM")
    print("=" * 60)
    print(f"  Jogos consultados: {len(candidatos):,}")
    print(f"  Com preço obtido: {com_preco:,} ({cobertura:.1%})")
    print(f"  Novos registros: {gravados:,}")
    print(f"  Sem mudança: {ignorados:,}")
    print(f"  Em lotes que falharam: {erros_lote:,}")
    print(
        f"  Sem preço no GetItems: {len(sem_preco):,} (resolvidos individualmente: "
        f"{resolvidos_fallback}; aguardando reverificação: {sem_preco_em_espera})"
    )
    print(f"  Mudanças confirmadas pelo AppDetails: {confirmadas} (descartadas: {descartadas})")
    if motivos_contagem:
        print("  Motivos: " + ", ".join(f"{m}={q}" for m, q in motivos_contagem.most_common()))
    print(
        "  Disponibilidade revalidada: "
        f"ok={resumo_disponibilidade['verificacoes_ok']}, "
        f"erros={resumo_disponibilidade['erros_disponibilidade']}"
    )
    print(f"  Duração: {duracao:.0f}s")

    if cobertura < COBERTURA_MINIMA:
        status = "falha"
    elif erros > len(candidatos) * TOLERANCIA_ERROS:
        status = "parcial"
    elif erros or resumo_disponibilidade["erros_disponibilidade"]:
        status = "concluida_com_avisos"
    else:
        status = "concluida"

    return {
        "status": status,
        "fonte": "Steam",
        "modo": "historico_precos",
        "total_catalogo": total_catalogo,
        "total_candidatos": total_candidatos,
        "total_processado": len(candidatos),
        "com_preco": com_preco,
        "cobertura": round(cobertura, 4),
        "novos_registros": gravados,
        "ignorados": ignorados,
        "erros": erros,
        "lotes_falhos_ids": erros_lote,
        "sem_preco_getitems": len(sem_preco),
        "sem_preco_em_espera": sem_preco_em_espera,
        "resolvidos_fallback": resolvidos_fallback,
        "confirmacoes": {"confirmadas": confirmadas, "descartadas": descartadas},
        "resumo_disponibilidade": resumo_disponibilidade,
        "erros_disponibilidade": resumo_disponibilidade["erros_disponibilidade"],
        "duracao_segundos": round(duracao, 1),
    }


async def coletar_historico_precos(
    primeira_coleta=False,
    limite_jogos=None,
    somente_disponibilidade_br=False,
    simular_disponibilidade_br=False,
):
    """
    Coleta preços/promoções da Steam e salva somente mudanças reais.

    Um novo registro é criado quando muda pelo menos um dos campos de estado:
    preço atual, preço original, desconto ou promoção (ID, nome, tipo,
    início ou fim). A simples mudança de dia não cria registro.

    Com somente_disponibilidade_br=True, apenas reavalia a disponibilidade
    regional dos apps modificados recentemente, sem tocar no histórico.
    """
    print("=" * 60)
    print("COLETANDO HISTÓRICO DE PREÇOS (STEAM)")
    print("Consulta principal: IStoreBrowseService/GetItems em lote")
    print("Preço: pacote do próprio jogo (bundles são ignorados)")
    print("Consulta individual: só sem preço no lote ou pacote não identificado")
    print("Novo registro: mudança de estado do preço/promoção")
    print("=" * 60)
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    db = SessionLocal()
    coletor = SteamColetor()

    try:
        if not somente_disponibilidade_br:
            return await _coletar_precos_diarios(db, coletor, limite_jogos)

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
            and (getattr(jogo, "steam_disponibilidade_br", None) or "").upper()
            != "GRATUITO"
        ]
        jogos = [
            jogo for jogo in jogos
            if _disponibilidade_precisa_de_verificacao(jogo, forcar=False)
        ]

        if limite_jogos is not None:
            jogos = jogos[:limite_jogos]

        print(f"\nJogos com Steam no banco: {len(jogos_catalogo):,}")
        print(f"Apps Steam fora do catálogo: {len(apps_modificados - ids_catalogo):,}")

        if not jogos:
            print("Nenhum candidato elegível para verificação de disponibilidade BR nesta execução.")
            if simular_disponibilidade_br:
                db.rollback()
            else:
                db.commit()
            return {
                "status": "sem_itens",
                "fonte": "Steam",
                "modo": "somente_disponibilidade_br",
                "total_catalogo": len(jogos_catalogo),
                "total_processado": 0,
                "novos_registros": 0,
                "ignorados": 0,
                "erros": 0,
            }

        print("\nMODO SOMENTE DISPONIBILIDADE BR")
        print(f"Candidatos elegíveis: {len(jogos):,}")
        print(f"Simulação sem gravar no PostgreSQL: {simular_disponibilidade_br}")

        resumo_disponibilidade = _resumo_disponibilidade_vazio()
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
        erros_disponibilidade = resumo_disponibilidade["erros_disponibilidade"]
        return {
            "status": "parcial" if erros_disponibilidade else "concluida",
            "fonte": "Steam",
            "modo": "somente_disponibilidade_br",
            "total_processado": len(jogos),
            "novos_registros": 0,
            "ignorados": resumo_disponibilidade["nao_classificados_com_sucesso"],
            "erros": erros_disponibilidade,
            "resumo_disponibilidade": resumo_disponibilidade,
        }

    except Exception as erro:
        db.rollback()
        print(f"\nErro geral: {erro}")
        import traceback
        traceback.print_exc()
        raise

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

        print("\nHISTORICO ATUAL:")
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
    args = parser.parse_args()

    if args.limite_jogos is not None and args.limite_jogos <= 0:
        parser.error("--limite-jogos deve ser maior que zero.")
    if args.simular_disponibilidade_br and not args.somente_disponibilidade_br:
        parser.error("--simular-disponibilidade-br exige --somente-disponibilidade-br.")

    asyncio.run(
        coletar_historico_precos(
            primeira_coleta=args.primeira_coleta,
            limite_jogos=args.limite_jogos,
            somente_disponibilidade_br=args.somente_disponibilidade_br,
            simular_disponibilidade_br=args.simular_disponibilidade_br,
        )
    )
