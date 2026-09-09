"""
Módulo de agendamento de coleta automatizada.

Este módulo gerencia a execução periódica dos coletores de dados,
permitindo que a coleta de preços ocorra automaticamente em intervalos
definidos, sem intervenção manual.
"""

import asyncio
import time
import schedule
from .steam_coletor import SteamColetor
from .epic_coletor import EpicColetor


class AgendadorColeta:
    """
    Agenda e executa a coleta automatizada de preços.

    Atributos:
        steam (SteamColetor): Instância do coletor da Steam.
        epic (EpicColetor): Instância do coletor da Epic Games Store.
    """

    def __init__(self):
        """Inicializa os coletores para ambas as plataformas."""
        self.steam = SteamColetor()
        self.epic = EpicColetor()

    def iniciar(self):
        """
        Inicia o agendamento da coleta diária.

        A coleta é programada para ocorrer diariamente às 03:00.
        O loop principal mantém a aplicação em execução verificando
        tarefas pendentes a cada 60 segundos.
        """
        print("Agendador de coleta iniciado.")
        print("Coleta programada para rodar diariamente às 03:00")

        schedule.every().day.at("03:00").do(self._executar_coleta)

        while True:
            schedule.run_pending()
            time.sleep(60)

    def _executar_coleta(self):
        """
        Executa a coleta em ambas as plataformas.

        Este método é chamado automaticamente pelo agendador.
        Cria um novo loop de eventos para executar as tarefas assíncronas.
        """
        print("Iniciando coleta programada...")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._coletar_ambas())
        except Exception as erro:
            print(f"Erro durante a coleta programada: {erro}")

    async def _coletar_ambas(self):
        """
        Coleta dados de ambas as plataformas simultaneamente.

        Returns:
            dict: Dicionário com os resultados da Steam e da Epic.
        """
        steam_resultado = await self.steam.coletar_precos()
        epic_resultado = await self.epic.coletar_precos()

        total_jogos_steam = len(steam_resultado.get("jogos", []))
        total_jogos_epic = len(epic_resultado.get("jogos", []))

        print(f"Coleta concluída: {total_jogos_steam} jogos (Steam), "
              f"{total_jogos_epic} jogos (Epic)")

        return {
            "steam": steam_resultado,
            "epic": epic_resultado
        }