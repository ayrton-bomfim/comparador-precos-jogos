import schedule  
import asyncio  
import time  
from .steam_coletor import SteamColetor  
from .epic_coletor import EpicColetor  
  
class AgendadorColeta:  
    """Agenda a coleta automatica de precos"""  
  
    def __init__(self):  
        self.steam = SteamColetor()  
        self.epic = EpicColetor()  
  
    def iniciar(self):  
        """Inicia o agendamento"""  
        print("? Agendador iniciado!")  
        print("?? Coleta programada para rodar diariamente as 03:00")  
  
        schedule.every().day.at("03:00").do(self.coletar_tudo)  
  
        while True:  
            schedule.run_pending()  
            time.sleep(60)  
  
    def coletar_tudo(self):  
        """Executa a coleta em ambas as plataformas"""  
        print("?? Iniciando coleta programada...")  
        try:  
            loop = asyncio.new_event_loop()  
            asyncio.set_event_loop(loop)  
            loop.run_until_complete(self.coletar_ambas())  
        except Exception as e:  
            print(f"? Erro na coleta: {e}")  
  
    async def coletar_ambas(self):  
        """Coleta dados de ambas as plataformas"""  
        steam_result = await self.steam.coletar_precos()  
        epic_result = await self.epic.coletar_precos()  
        print("? Coleta concluida!")  
