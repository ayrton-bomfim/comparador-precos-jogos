# -*- coding: utf-8 -*-
"""
Importador de histórico ITAD -> historico_precos.

Versão com checkpoint automático para continuar o backfill entre execuções.

SEGURANÇA:
- Por padrão, executa em MODO SIMULAÇÃO.
- Para gravar no PostgreSQL, é necessário usar: --executar
- Não altera o coletor diário coletar_historico.py.
- Importa somente eventos Steam/BR da ITAD anteriores ao primeiro
  registro local de cada jogo.
- Somente jogos com steam_disponibilidade_br = DISPONIVEL entram.
- Eventos repetidos em datas diferentes são preservados.
- promoções não recebem ID/nome/tipo/início/fim porque o endpoint de
  histórico testado não fornece esses dados.
- data_coleta é armazenada como horário local de Brasília sem timezone,
  para manter compatibilidade com o campo atual HistoricoPreco.data_coleta.
- O importador é idempotente para o mesmo jogo + plataforma + timestamp
  + preço + preço original + desconto.
- O limite da ITAD é controlado por uma janela deslizante de 5 minutos:
  no máximo 1000 requisições HTTP nessa janela.
- Em HTTP 429, respeita Retry-After quando fornecido.
"""

import argparse
import json
import os
import time
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv
from sqlalchemy import func

from backend.banco_dados import SessionLocal
from backend.modelos import Jogo, HistoricoPreco


ITAD_HISTORY_URL = "https://api.isthereanydeal.com/games/history/v2"
ITAD_LOOKUP_URL = "https://api.isthereanydeal.com/games/lookup/v1"

JOGOS_PROCESSADOS = {
    "1145360": "Hades",
    "1868140": "DAVE THE DIVER",
    "1593500": "God of War",
    "1174180": "Red Dead Redemption 2",
}

COUNTRY = "BR"
STEAM_SHOP_ID = 61
SINCE = "2020-01-01T00:00:00Z"

TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")

# Limite informado pela ITAD: 1000 requisições por 5 minutos.
ITAD_MAX_REQUESTS = 1000
ITAD_WINDOW_SECONDS = 5 * 60

# Controle persistente do progresso do backfill.
# Os 450 primeiros DISPONIVEL já foram processados na execução anterior.
ARQUIVO_CHECKPOINT = "itad_backfill_checkpoint.json"
LOTE_JA_PROCESSADO = 450
LOTE_AUTOMATICO = 450
PAUSA_ENTRE_LOTES_SEGUNDOS = 5 * 60


class LimitadorITAD:
    """Controla as requisições ITAD em uma janela deslizante de 5 minutos."""

    def __init__(self, max_requests=ITAD_MAX_REQUESTS, window_seconds=ITAD_WINDOW_SECONDS):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps = deque()

    def esperar(self):
        agora = time.monotonic()

        while self.timestamps and agora - self.timestamps[0] >= self.window_seconds:
            self.timestamps.popleft()

        if len(self.timestamps) >= self.max_requests:
            espera = self.window_seconds - (agora - self.timestamps[0]) + 1
            espera = max(espera, 1)
            print(
                f"\n[ITAD] Limite de {self.max_requests} requisições atingido. "
                f"Aguardando {espera:.0f}s para a próxima janela de 5 minutos..."
            )
            time.sleep(espera)

            agora = time.monotonic()
            while self.timestamps and agora - self.timestamps[0] >= self.window_seconds:
                self.timestamps.popleft()

        self.timestamps.append(time.monotonic())

    @property
    def usadas(self):
        agora = time.monotonic()
        while self.timestamps and agora - self.timestamps[0] >= self.window_seconds:
            self.timestamps.popleft()
        return len(self.timestamps)


def moeda(valor):
    if valor is None:
        return "N/A"
    return f"R$ {float(valor):.2f}".replace(".", ",")


def api_key():
    load_dotenv()
    chave = os.getenv("ITAD_API_KEY")

    if not chave:
        raise RuntimeError("ITAD_API_KEY não encontrada no .env.")

    return chave


def get_json(url, params, chave, limitador):
    tentativas_429 = 0

    while True:
        limitador.esperar()

        resposta = requests.get(
            url,
            params=params,
            headers={"ITAD-API-Key": chave},
            timeout=30,
        )

        if resposta.status_code != 429:
            resposta.raise_for_status()
            return resposta.json()

        tentativas_429 += 1

        retry_after_raw = resposta.headers.get("Retry-After")
        try:
            retry_after = float(retry_after_raw) if retry_after_raw else 60.0
        except (TypeError, ValueError):
            retry_after = 60.0

        # Margem pequena para não voltar exatamente no limite.
        retry_after = max(retry_after, 1.0) + 1.0

        print(
            f"\n[ITAD] HTTP 429. Retry-After={retry_after - 1:.0f}s. "
            f"Aguardando {retry_after:.0f}s antes de tentar novamente."
        )
        time.sleep(retry_after)

        if tentativas_429 >= 5:
            raise RuntimeError(
                "ITAD continuou retornando HTTP 429 após 5 tentativas."
            )


def buscar_itad_id(steam_id, chave, limitador):
    dados = get_json(
        ITAD_LOOKUP_URL,
        {"key": chave, "appid": steam_id},
        chave,
        limitador,
    )

    if isinstance(dados, dict):
        if dados.get("id"):
            return dados["id"]

        game = dados.get("game")
        if isinstance(game, dict) and game.get("id"):
            return game["id"]

    if isinstance(dados, list) and dados:
        primeiro = dados[0]
        if isinstance(primeiro, dict):
            return primeiro.get("id")

    return None


def eventos_itad(itad_id, chave, limitador):
    dados = get_json(
        ITAD_HISTORY_URL,
        {
            "key": chave,
            "id": itad_id,
            "country": COUNTRY,
            "shops": str(STEAM_SHOP_ID),
            "since": SINCE,
        },
        chave,
        limitador,
    )

    if isinstance(dados, list):
        eventos = dados
    elif isinstance(dados, dict):
        eventos = []

        for campo in ("history", "data", "prices"):
            if isinstance(dados.get(campo), list):
                eventos = dados[campo]
                break
    else:
        eventos = []

    resultado = []

    for evento in eventos:
        shop = evento.get("shop") or {}

        if str(shop.get("id")) != str(STEAM_SHOP_ID):
            continue

        deal = evento.get("deal") or {}
        price = deal.get("price") or {}
        regular = deal.get("regular") or {}

        if price.get("amount") is None:
            continue

        timestamp_raw = evento.get("timestamp")

        if not timestamp_raw:
            continue

        try:
            timestamp = datetime.fromisoformat(
                timestamp_raw.replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            continue

        if timestamp.tzinfo is None:
            raise ValueError(
                f"Timestamp ITAD sem timezone: {timestamp_raw}"
            )

        preco_atual = Decimal(str(price["amount"])).quantize(
            Decimal("0.01")
        )

        preco_sem_desconto = (
            Decimal(str(regular["amount"])).quantize(
                Decimal("0.01")
            )
            if regular.get("amount") is not None
            else None
        )

        resultado.append(
            {
                "timestamp": timestamp,
                "timestamp_utc": timestamp.astimezone(timezone.utc),
                "preco_atual": preco_atual,
                "preco_sem_desconto": preco_sem_desconto,
                "desconto": int(deal.get("cut") or 0),
            }
        )

    resultado.sort(key=lambda x: x["timestamp_utc"])

    return resultado


def local_para_aware_brasilia(valor):
    if valor.tzinfo is not None:
        return valor.astimezone(TZ_BRASILIA)

    return valor.replace(tzinfo=TZ_BRASILIA)


def itad_para_data_coleta(timestamp):
    """
    Converte o timestamp com timezone da ITAD para horário de Brasília
    e remove o timezone para compatibilidade com DateTime sem timezone.
    """
    return timestamp.astimezone(TZ_BRASILIA).replace(tzinfo=None)


def estado(preco_atual, preco_sem_desconto, desconto):
    return (
        Decimal(str(preco_atual)).quantize(Decimal("0.01"))
        if preco_atual is not None
        else None,
        Decimal(str(preco_sem_desconto)).quantize(Decimal("0.01"))
        if preco_sem_desconto is not None
        else None,
        int(desconto or 0),
    )


def registro_ja_existe(db, jogo_id, data_coleta, preco_atual,
                       preco_sem_desconto, desconto):
    registros = (
        db.query(HistoricoPreco)
        .filter(
            HistoricoPreco.jogo_id == jogo_id,
            func.lower(HistoricoPreco.plataforma) == "steam",
            HistoricoPreco.data_coleta == data_coleta,
        )
        .all()
    )

    alvo = estado(
        preco_atual,
        preco_sem_desconto,
        desconto,
    )

    for registro in registros:
        if estado(
            registro.preco_atual,
            registro.preco_sem_desconto,
            registro.desconto,
        ) == alvo:
            return True

    return False


def carregar_checkpoint():
    if not os.path.exists(ARQUIVO_CHECKPOINT):
        return set()

    with open(ARQUIVO_CHECKPOINT, "r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)

    return {str(steam_id) for steam_id in dados.get("steam_ids_processados", [])}


def salvar_checkpoint(steam_ids_processados):
    dados = {
        "steam_ids_processados": sorted(steam_ids_processados),
    }

    arquivo_temporario = ARQUIVO_CHECKPOINT + ".tmp"
    with open(arquivo_temporario, "w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=2)

    os.replace(arquivo_temporario, ARQUIVO_CHECKPOINT)


def inicializar_checkpoint(jogos):
    """Marca como já processado o lote de 450 concluído na execução anterior."""
    checkpoint = carregar_checkpoint()

    if checkpoint:
        return checkpoint

    jogos_lista = list(jogos.values())
    primeiros = jogos_lista[:LOTE_JA_PROCESSADO]
    checkpoint = {str(jogo.steam_id) for jogo in primeiros}
    salvar_checkpoint(checkpoint)

    print(
        f"[CHECKPOINT] Inicializado com {len(checkpoint)} jogos já processados "
        f"da execução anterior."
    )

    return checkpoint


def carregar_jogos(db):
    query = (
        db.query(Jogo)
        .filter(
            Jogo.steam_id.isnot(None),
            Jogo.steam_disponibilidade_br == "DISPONIVEL",
        )
        .order_by(Jogo.id.asc())
    )

    jogos = query.all()
    return {str(jogo.steam_id): jogo for jogo in jogos}


def processar_jogo(db, jogo, steam_id, chave, executar, limitador):
    print("\n" + "=" * 105)
    print(f"JOGO: {jogo.nome}")
    print(f"Steam ID: {steam_id}")
    print(f"DB ID: {jogo.id}")
    print(f"Disponibilidade BR: {jogo.steam_disponibilidade_br}")

    if jogo.steam_disponibilidade_br != "DISPONIVEL":
        print(
            "IGNORADO: somente jogos com "
            "steam_disponibilidade_br = DISPONIVEL entram no piloto."
        )
        return {
            "candidatos": 0,
            "novos": 0,
            "existentes": 0,
            "gravados": 0,
            "ignorado": True,
        }

    registros = (
        db.query(HistoricoPreco)
        .filter(
            HistoricoPreco.jogo_id == jogo.id,
            func.lower(HistoricoPreco.plataforma) == "steam",
        )
        .order_by(HistoricoPreco.data_coleta.asc())
        .all()
    )

    if not registros:
        print("IGNORADO: não há histórico local para definir o corte.")
        return {
            "candidatos": 0,
            "novos": 0,
            "existentes": 0,
            "gravados": 0,
            "ignorado": True,
        }

    primeiro_local = local_para_aware_brasilia(
        registros[0].data_coleta
    )
    primeiro_local_utc = primeiro_local.astimezone(timezone.utc)

    print(f"Primeiro histórico local: {registros[0].data_coleta}")
    print(f"Corte UTC: {primeiro_local_utc.isoformat()}")

    itad_id = buscar_itad_id(steam_id, chave, limitador)

    if not itad_id:
        print("ERRO: ID ITAD não encontrado.")
        return {
            "candidatos": 0,
            "novos": 0,
            "existentes": 0,
            "gravados": 0,
            "ignorado": False,
        }

    eventos = eventos_itad(itad_id, chave, limitador)

    candidatos = [
        evento
        for evento in eventos
        if evento["timestamp_utc"] < primeiro_local_utc
    ]

    print(f"ITAD ID: {itad_id}")
    print(f"Eventos ITAD Steam/BR: {len(eventos)}")
    print(f"Candidatos de backfill: {len(candidatos)}")

    novos = []
    existentes = []

    for evento in candidatos:
        data_coleta = itad_para_data_coleta(evento["timestamp"])

        if registro_ja_existe(
            db,
            jogo.id,
            data_coleta,
            evento["preco_atual"],
            evento["preco_sem_desconto"],
            evento["desconto"],
        ):
            existentes.append(evento)
        else:
            novos.append(evento)

    print(f"Já existentes no banco: {len(existentes)}")
    print(f"Novos registros: {len(novos)}")

    if novos:
        print("\nPrimeiros 5 registros que serão importados:")
        for evento in novos[:5]:
            print(
                f"  {evento['timestamp'].isoformat()} | "
                f"{moeda(evento['preco_atual'])} | "
                f"original={moeda(evento['preco_sem_desconto'])} | "
                f"{evento['desconto']}%"
            )

        print("\nÚltimos 5 registros que serão importados:")
        for evento in novos[-5:]:
            print(
                f"  {evento['timestamp'].isoformat()} | "
                f"{moeda(evento['preco_atual'])} | "
                f"original={moeda(evento['preco_sem_desconto'])} | "
                f"{evento['desconto']}%"
            )

    gravados = 0

    if executar and novos:
        for evento in novos:
            data_coleta = itad_para_data_coleta(evento["timestamp"])

            historico = HistoricoPreco(
                jogo_id=jogo.id,
                nome_jogo=jogo.nome,
                plataforma="Steam",
                preco_atual=evento["preco_atual"],
                preco_sem_desconto=evento["preco_sem_desconto"],
                desconto=evento["desconto"],
                data_coleta=data_coleta,
                promocao_id=None,
                promocao_nome=None,
                promocao_tipo=None,
                promocao_inicio=None,
                promocao_fim=None,
            )

            db.add(historico)
            gravados += 1

        db.commit()

        print(f"\nCOMMIT REALIZADO: {gravados} registros.")

    elif executar:
        print("\nNenhum registro novo para gravar.")
    else:
        print("\nSIMULAÇÃO: nenhum registro foi gravado.")

    return {
        "candidatos": len(candidatos),
        "novos": len(novos),
        "existentes": len(existentes),
        "gravados": gravados,
        "ignorado": False,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill de histórico Steam usando ITAD, com controle de 1000 requisições por 5 minutos."
    )
    parser.add_argument(
        "--executar",
        action="store_true",
        help="Grava os novos registros no PostgreSQL.",
    )
    parser.add_argument(
        "--limite-jogos",
        type=int,
        default=None,
        help="Limita quantos jogos DISPONIVEL serão processados nesta execução.",
    )

    args = parser.parse_args()

    chave = api_key()
    db = SessionLocal()

    try:
        modo = "EXECUÇÃO REAL" if args.executar else "SIMULAÇÃO"

        print("=" * 105)
        print("IMPORTADOR DE HISTÓRICO ITAD")
        print(modo)
        print("=" * 105)

        if args.executar:
            print(
                "\nATENÇÃO: esta execução fará INSERT no "
                "PostgreSQL somente dos registros novos."
            )
        else:
            print(
                "\nNenhuma alteração será feita no PostgreSQL."
            )

        jogos = carregar_jogos(db)
        checkpoint = inicializar_checkpoint(jogos)

        jogos_pendentes = [
            jogo
            for jogo in jogos.values()
            if str(jogo.steam_id) not in checkpoint
        ]

        if args.limite_jogos is not None:
            if args.limite_jogos <= 0:
                raise ValueError("--limite-jogos deve ser maior que zero.")
            limite_total = min(args.limite_jogos, len(jogos_pendentes))
        else:
            limite_total = len(jogos_pendentes)

        print(f"Jogos DISPONIVEL encontrados: {len(jogos)}")
        print(f"Já processados pelo backfill: {len(checkpoint)}")
        print(f"Ainda pendentes: {len(jogos_pendentes)}")
        print(f"Limite total desta execução: {limite_total}")
        print(f"Tamanho máximo de cada lote: {LOTE_AUTOMATICO}")
        print(f"Pausa entre lotes: {PAUSA_ENTRE_LOTES_SEGUNDOS // 60} minutos")
        print(
            f"Limite ITAD: {ITAD_MAX_REQUESTS} requisições por "
            f"{ITAD_WINDOW_SECONDS // 60} minutos."
        )

        total_candidatos = 0
        total_novos = 0
        total_existentes = 0
        total_gravados = 0
        total_ignorados = 0
        total_erros = 0
        total_processados = 0
        total_lotes = 0

        for inicio in range(0, limite_total, LOTE_AUTOMATICO):
            fim = min(inicio + LOTE_AUTOMATICO, limite_total)
            jogos_lote = jogos_pendentes[inicio:fim]
            total_lotes += 1

            print("\n" + "=" * 105)
            print(f"LOTE {total_lotes}")
            print(f"Jogos deste lote: {len(jogos_lote)}")
            print(f"Progresso geral: {inicio + 1}-{fim}/{limite_total}")
            print("=" * 105)

            limitador = LimitadorITAD()

            for indice_lote, jogo in enumerate(jogos_lote, start=1):
                steam_id = str(jogo.steam_id)

                print("\n" + "#" * 105)
                print(f"PROGRESSO DO LOTE: {indice_lote}/{len(jogos_lote)}")
                print(f"PROGRESSO GERAL: {inicio + indice_lote}/{limite_total}")
                print(
                    f"Requisições ITAD na janela atual: "
                    f"{limitador.usadas}/{ITAD_MAX_REQUESTS}"
                )

                try:
                    resultado = processar_jogo(
                        db, jogo, steam_id, chave, args.executar, limitador
                    )

                    total_processados += 1
                    total_candidatos += resultado["candidatos"]
                    total_novos += resultado["novos"]
                    total_existentes += resultado["existentes"]
                    total_gravados += resultado["gravados"]

                    if resultado["ignorado"]:
                        total_ignorados += 1

                    checkpoint.add(steam_id)
                    salvar_checkpoint(checkpoint)

                except Exception as erro:
                    db.rollback()
                    total_erros += 1
                    print(
                        f"ERRO AO PROCESSAR {jogo.nome} "
                        f"(Steam {steam_id}): {erro}"
                    )
                    print("Continuando para o próximo jogo.")

            restantes_apos_lote = limite_total - fim
            if restantes_apos_lote > 0:
                print("\n" + "-" * 105)
                print(
                    f"LOTE {total_lotes} CONCLUÍDO. "
                    f"Aguardando {PAUSA_ENTRE_LOTES_SEGUNDOS // 60} minutos "
                    f"antes do próximo lote."
                )
                print(f"Restantes nesta execução: {restantes_apos_lote}")
                print("-" * 105)
                time.sleep(PAUSA_ENTRE_LOTES_SEGUNDOS)

        print("\n" + "=" * 105)
        print("RESUMO")
        print("=" * 105)
        print(f"Total de candidatos: {total_candidatos}")
        print(f"Total já existente: {total_existentes}")
        print(f"Total de novos registros: {total_novos}")
        print(f"Total gravado: {total_gravados}")
        print(f"Jogos ignorados: {total_ignorados}")
        print(f"Jogos processados: {total_processados}")
        print(f"Erros de processamento: {total_erros}")
        print(f"Total de lotes executados: {total_lotes}")

        if args.executar:
            print("\nExecução concluída.")
        else:
            print("\nSIMULAÇÃO CONCLUÍDA.")
            print(
                "Para gravar, somente depois de conferirmos esta saída, "
                "use: python -m importar_historico_itad_v3_continuar --executar"
            )

    except Exception:
        if args.executar:
            db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
