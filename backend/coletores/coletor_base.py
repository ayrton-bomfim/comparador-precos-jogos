from abc import ABC, abstractmethod
from playwright.async_api import async_playwright
import asyncio

class ColetorBase(ABC):
    """Classe base para todos os coletores de jogos"""
    
    def __init__(self):
        self.headless = True  # True = roda em segundo plano
        self.timeout = 60000  # 60 segundos (aumentei para dar tempo)
    
    @abstractmethod
    async def coletar_precos(self):
        """Coleta os preços de todos os jogos em destaque"""
        pass
    
    @abstractmethod
    async def coletar_jogo(self, jogo_id):
        """Coleta dados de um jogo específico"""
        pass
    
    @abstractmethod
    async def coletar_promocoes(self):
        """Coleta jogos em promoção"""
        pass
    
    async def _abrir_pagina(self, url):
        """Abre uma página e retorna o navegador e a página"""
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=self.headless)
        page = await browser.new_page()
        
        # Configurar timeout
        page.set_default_timeout(self.timeout)
        
        # Ir para a URL
        await page.goto(url, timeout=self.timeout)
        
        # Aguardar a página carregar completamente
        await page.wait_for_load_state("networkidle", timeout=self.timeout)
        
        # Retorna o playwright, browser e page para gerenciar o fechamento
        return playwright, browser, page