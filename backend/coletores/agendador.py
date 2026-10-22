# -*- coding: utf-8 -*-
"""
Agendador de coleta diária de preços.

Fluxo diário:
1. Steam -> histórico via IStoreBrowseService/GetItems em lote.
2. Epic  -> histórico via EGDATA.

Modos de execução:
- sem argumentos: mantém um agendador residente e executa no horário configurado.
- --agora: executa uma coleta imediatamente e encerra.

O horário padrão é 03:00 e pode ser alterado pela variável
COLETA_HORARIO no arquivo .env.
"""

import argparse
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path

import schedule

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

from ..scripts.historico.coletar_historico import coletar_historico_precos
from ..scripts.historico.coletar_historico_epic import coletar_historico_epic


HORARIO_PADRAO = "03:00"
ARQUIVO_LOG_EXECUCOES = (
    Path(__file__).resolve().parents[2] / "logs" / "execucoes_coleta.jsonl"
)


def _registrar_execucao(registro):
    """Registra uma linha JSON por execução sem mascarar falhas da coleta."""
    try:
        ARQUIVO_LOG_EXECUCOES.parent.mkdir(parents=True, exist_ok=True)
        with ARQUIVO_LOG_EXECUCOES.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
    except Exception as erro:
        print(f"AVISO: não foi possível gravar o log da coleta: {erro}")


def obter_horario_coleta():
    """Obtém o horário da coleta a partir do .env ou usa 03:00."""
    if load_dotenv:
        load_dotenv()

    horario = os.getenv("COLETA_HORARIO", HORARIO_PADRAO).strip()

    try:
        datetime.strptime(horario, "%H:%M")
    except ValueError:
        print(
            f"Horário inválido em COLETA_HORARIO={horario!r}. "
            f"Usando {HORARIO_PADRAO}."
        )
        horario = HORARIO_PADRAO

    return horario


class AgendadorColeta:
    """Coordena a coleta diária de histórico das duas plataformas."""

    def __init__(self, horario=None):
        self.horario = horario or obter_horario_coleta()
        self._coleta_em_execucao = False

    def iniciar(self):
        """Mantém o processo ativo e executa a coleta diariamente."""
        print("=" * 60)
        print("AGENDADOR DE COLETA DIÁRIA")
        print("=" * 60)
        print(f"Horário configurado: {self.horario}")
        print("Steam: IStoreBrowseService/GetItems em lote")
        print("Epic: EGDATA")
        print("Pressione Ctrl+C para encerrar o agendador.")
        print("=" * 60)

        schedule.clear("coleta_diaria")
        schedule.every().day.at(self.horario).do(
            self._executar_coleta,
        ).tag("coleta_diaria")

        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nAgendador encerrado pelo usuário.")

    def executar_agora(self):
        """Executa uma coleta imediatamente e encerra o processo."""
        self._executar_coleta()

    def _executar_coleta(self):
        """Executa a rotina assíncrona completa uma única vez."""
        if self._coleta_em_execucao:
            print("Já existe uma coleta em execução. Ignorando nova chamada.")
            return

        self._coleta_em_execucao = True
        inicio = datetime.now()

        print("\n" + "=" * 60)
        print("INÍCIO DA COLETA")
        print(f"Data/hora: {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
        print("=" * 60)

        resultado = None
        erro_execucao = None
        status_geral = "falha"

        try:
            resultado = asyncio.run(self._coletar_ambas())
            status_etapas = [
                valor.get("status")
                for valor in resultado.values()
                if isinstance(valor, dict) and valor.get("status")
            ]
            if "falha" in status_etapas:
                status_geral = "falha"
            elif "parcial" in status_etapas:
                status_geral = "parcial"
            elif any(status in {"sem_ofertas", "sem_itens"} for status in status_etapas):
                status_geral = "concluida_com_avisos"
            else:
                status_geral = "concluida"

            print(f"Status geral da execução: {status_geral}")
        except Exception as erro:
            erro_execucao = f"{type(erro).__name__}: {erro}"
            print(f"ERRO GERAL NA COLETA: {erro}")
            raise
        finally:
            fim = datetime.now()
            duracao = fim - inicio
            _registrar_execucao({
                "inicio": inicio.isoformat(timespec="seconds"),
                "fim": fim.isoformat(timespec="seconds"),
                "duracao_segundos": round(duracao.total_seconds(), 2),
                "status": status_geral,
                "erro": erro_execucao,
                "etapas": resultado,
            })
            print("=" * 60)
            print(
                f"FIM DA COLETA: {fim.strftime('%d/%m/%Y %H:%M:%S')}"
            )
            print(f"Duração: {duracao}")
            print(f"Log: {ARQUIVO_LOG_EXECUCOES}")
            print("=" * 60)
            self._coleta_em_execucao = False

    async def _coletar_ambas(self):
        """
        Executa as duas rotinas de histórico.

        Steam:
            coletar_historico_precos() já faz a consulta GetItems em lote.

        Epic:
            coletar_historico_epic() usa EGDATA e é assíncrona.
        """
        print("\n[1/4] Coleta histórica da Steam")
        resultado_steam = await coletar_historico_precos()
        print(f"Resultado Steam: {resultado_steam}")

        print("\n[2/4] Coleta histórica da Epic (EGDATA)")
        resultado_epic = await coletar_historico_epic()

        print("\n[3/4] Avaliação dos alertas de preço e envio de e-mails")
        from .avaliador_alertas_preco import avaliar_alertas_preco
        resultado_alertas = await asyncio.to_thread(avaliar_alertas_preco)
        print(f"Alertas avaliados: {resultado_alertas}")

        print("\n[4/4] Encerramento de recomendações com promoções finalizadas")
        from backend.scripts.expirar_recomendacoes_comunidade import expirar_recomendacoes
        resultado_recomendacoes = await asyncio.to_thread(expirar_recomendacoes)
        print(f"Recomendações expiradas: {resultado_recomendacoes}")

        return {
            "steam": resultado_steam or {
                "status": "sem_resumo",
                "fonte": "Steam",
            },
            "epic": resultado_epic or {
                "status": "sem_resumo",
                "fonte": "EGDATA",
            },
            "alertas_preco": resultado_alertas,
            "recomendacoes_comunidade": resultado_recomendacoes,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Agendador da coleta diária de preços."
    )
    parser.add_argument(
        "--agora",
        action="store_true",
        help="executa a coleta imediatamente e encerra.",
    )

    args = parser.parse_args()
    agendador = AgendadorColeta()

    if args.agora:
        agendador.executar_agora()
    else:
        agendador.iniciar()


if __name__ == "__main__":
    main()
