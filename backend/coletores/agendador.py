# -*- coding: utf-8 -*-
"""
Agendador de coleta diária de preços.

Fluxo diário:
1. Steam -> histórico via IStoreBrowseService/GetItems em lote.
2. Epic  -> histórico via ITAD em lote (EGDATA como reserva).
3. Alertas de preço, limpeza de promoções encerradas e precos_atuais.

Cada loja informa a cobertura (fração do catálogo com preço obtido). Abaixo
de 90%, a etapa é marcada como falha, para que quebras de fonte não passem
despercebidas como "parcial".

Modos de execução:
- sem argumentos: mantém um agendador residente e executa no horário configurado.
- --agora: executa uma coleta imediatamente e encerra.
- --etapas steam,epic,...: com --agora, executa só as etapas escolhidas
  (steam, epic, alertas, limpeza, precos_atuais), na ordem padrão.

No uso diário, quem dispara a coleta é o DESCTRL Manager
(backend/desctrl_manager/executor.py), que abre o túnel, evita execuções
simultâneas e guarda um log por execução.

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

from .coletar_historico import coletar_historico_precos
from .coletar_historico_epic import coletar_historico_epic


HORARIO_PADRAO = "03:00"
ARQUIVO_LOG_EXECUCOES = (
    Path(__file__).resolve().parents[2] / "logs" / "execucoes_coleta.jsonl"
)

# Ordem fixa das etapas: (chave, título exibido no log).
ETAPAS = (
    ("steam", "Coleta histórica da Steam"),
    ("epic", "Coleta histórica da Epic (ITAD + EGDATA)"),
    ("alertas", "Avaliação dos alertas de preço e envio de e-mails"),
    ("limpeza", "Limpeza de promoções encerradas (recomendações e vitrine)"),
    ("precos_atuais", "Atualização dos preços atuais usados no catálogo"),
)
CHAVES_ETAPAS = tuple(chave for chave, _ in ETAPAS)

# Chave da etapa -> nome usado no resumo e no registro de execuções.
NOME_RESULTADO = {
    "steam": "steam",
    "epic": "epic",
    "alertas": "alertas_preco",
    "limpeza": "recomendacoes_comunidade",
    "precos_atuais": "precos_atuais",
}


def normalizar_etapas(etapas):
    """Valida a lista de etapas e devolve na ordem padrão (todas se vazia)."""
    if not etapas:
        return list(CHAVES_ETAPAS)
    desconhecidas = [e for e in etapas if e not in CHAVES_ETAPAS]
    if desconhecidas:
        raise ValueError(
            f"Etapa(s) desconhecida(s): {', '.join(desconhecidas)}. "
            f"Use: {', '.join(CHAVES_ETAPAS)}."
        )
    return [chave for chave in CHAVES_ETAPAS if chave in etapas]


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
        print("Epic: ITAD em lote (EGDATA como reserva)")
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

    def executar_agora(self, etapas=None, origem="manual", arquivo_log=None):
        """Executa a coleta (ou só as etapas pedidas) e retorna o status geral."""
        return self._executar_coleta(etapas, origem, arquivo_log)

    def _executar_coleta(self, etapas=None, origem="agendador", arquivo_log=None):
        """Executa a rotina assíncrona uma única vez."""
        etapas = normalizar_etapas(etapas)
        if self._coleta_em_execucao:
            print("Já existe uma coleta em execução. Ignorando nova chamada.")
            return

        self._coleta_em_execucao = True
        inicio = datetime.now()

        print("\n" + "=" * 60)
        print("INÍCIO DA COLETA")
        print(f"Data/hora: {inicio.strftime('%d/%m/%Y %H:%M:%S')}")
        print(f"Etapas: {', '.join(etapas)} | origem: {origem}")
        print("=" * 60)

        resultado = None
        erro_execucao = None
        status_geral = "falha"

        try:
            resultado = asyncio.run(self._executar_etapas(etapas))
            status_etapas = [
                valor.get("status")
                for valor in resultado.values()
                if isinstance(valor, dict) and valor.get("status")
            ]
            if "falha" in status_etapas:
                status_geral = "falha"
            elif "parcial" in status_etapas:
                status_geral = "parcial"
            elif any(
                status in {"sem_ofertas", "sem_itens", "concluida_com_avisos"}
                for status in status_etapas
            ):
                status_geral = "concluida_com_avisos"
            else:
                status_geral = "concluida"

            print("\nResumo por etapa:")
            for nome, valor in resultado.items():
                if not isinstance(valor, dict):
                    continue
                detalhes = [f"status={valor.get('status', '-')}"]
                if "cobertura" in valor:
                    detalhes.append(f"cobertura={valor['cobertura']:.1%}")
                if "novos_registros" in valor:
                    detalhes.append(f"novos={valor['novos_registros']}")
                if "duracao_segundos" in valor:
                    detalhes.append(f"{valor['duracao_segundos']:.0f}s")
                print(f"  {nome}: " + ", ".join(detalhes))
            print(f"Status geral da execução: {status_geral}")
        except Exception as erro:
            erro_execucao = f"{type(erro).__name__}: {erro}"
            print(f"ERRO GERAL NA COLETA: {erro}")
            raise
        finally:
            fim = datetime.now()
            duracao = fim - inicio
            _registrar_execucao({
                "ambiente": os.getenv("DESCTRL_ENV") or "producao",
                "inicio": inicio.isoformat(timespec="seconds"),
                "fim": fim.isoformat(timespec="seconds"),
                "duracao_segundos": round(duracao.total_seconds(), 2),
                "status": status_geral,
                "erro": erro_execucao,
                "origem": origem,
                "etapas_solicitadas": etapas,
                "log": str(arquivo_log) if arquivo_log else None,
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

        return status_geral

    async def _executar_etapas(self, etapas):
        """Executa as etapas pedidas, na ordem padrão, e devolve os resultados."""
        titulos = dict(ETAPAS)
        resultados = {}
        for indice, chave in enumerate(etapas, start=1):
            print(f"\n[{indice}/{len(etapas)}] {titulos[chave]}")
            resultados[NOME_RESULTADO[chave]] = await self._executar_etapa(chave)
        return resultados

    async def _executar_etapa(self, chave):
        if chave == "steam":
            resultado = await coletar_historico_precos()
            print(f"Resultado Steam: {resultado}")
            return resultado or {"status": "sem_resumo", "fonte": "Steam"}

        if chave == "epic":
            resultado = await coletar_historico_epic()
            return resultado or {"status": "sem_resumo", "fonte": "ITAD+EGDATA"}

        if chave == "alertas":
            from backend.servicos.avaliador_alertas_preco import avaliar_alertas_preco
            resultado = await asyncio.to_thread(avaliar_alertas_preco)
            print(f"Alertas avaliados: {resultado}")
            return resultado

        if chave == "limpeza":
            from backend.servicos.expirar_recomendacoes_comunidade import expirar_recomendacoes
            resultado = await asyncio.to_thread(expirar_recomendacoes)
            print(f"Limpeza de promoções: {resultado}")
            return resultado

        from backend.servicos.precos_atuais import atualizar_precos_atuais
        try:
            resultado = await asyncio.to_thread(atualizar_precos_atuais)
        except Exception as erro:
            resultado = {"status": "falha", "erro": str(erro)}
        print(f"Preços atuais: {resultado}")
        return resultado


def main():
    parser = argparse.ArgumentParser(
        description="Agendador da coleta diária de preços."
    )
    parser.add_argument(
        "--agora",
        action="store_true",
        help="executa a coleta imediatamente e encerra.",
    )

    parser.add_argument(
        "--etapas",
        default="",
        help=f"com --agora, executa só estas etapas (separadas por vírgula): {', '.join(CHAVES_ETAPAS)}",
    )

    args = parser.parse_args()
    agendador = AgendadorColeta()

    if args.agora:
        etapas = [e.strip() for e in args.etapas.split(",") if e.strip()]
        status = agendador.executar_agora(etapas)
        raise SystemExit(0 if status in {"concluida", "concluida_com_avisos"} else 1)
    else:
        agendador.iniciar()


if __name__ == "__main__":
    main()
