"""
Módulo com a classe base para coletores de dados.

Define a estrutura comum que todos os coletores de plataformas
(Steam, Epic Games Store, etc.) devem seguir, garantindo
consistência na implementação.
"""

from abc import ABC, abstractmethod
from playwright.async_api import async_playwright


class ColetorBase(ABC):
    """
    Classe base abstrata para coletores de dados de jogos.

    Fornece a estrutura básica e métodos auxiliares para a coleta
    de informações em plataformas de distribuição digital.

    Atributos:
        headless (bool): Se o navegador deve rodar em modo headless.
        timeout (int): Tempo máximo de espera para operações (ms).
    """

    def __init__(self, headless: bool = True, timeout: int = 60000):
        """
        Inicializa o coletor com as configurações padrão.

        Args:
            headless (bool): Modo headless do navegador. Padrão True.
            timeout (int): Timeout para operações em milissegundos. Padrão 60000.
        """
        self.headless = headless
        self.timeout = timeout

    @abstractmethod
    async def coletar_precos(self):
        """
        Coleta os preços dos jogos em destaque.

        Deve ser implementado por cada plataforma específica.

        Returns:
            dict: Dicionário com os dados coletados.
        """
        pass

    @abstractmethod
    async def coletar_jogo(self, identificador):
        """
        Coleta dados de um jogo específico.

        Args:
            identificador (str or int): Identificador do jogo na plataforma.

        Returns:
            dict: Dicionário com os dados do jogo.
        """
        pass

    @abstractmethod
    async def coletar_promocoes(self):
        """
        Coleta jogos em promoção.

        Returns:
            dict: Dicionário com os jogos em promoção.
        """
        pass

    async def _abrir_pagina(self, url: str):
        """
        Abre uma página no navegador e retorna os recursos gerenciados.

        Este método é um auxiliar para os coletores que necessitam
        de navegação direta em páginas web.

        Args:
            url (str): URL da página a ser aberta.

        Returns:
            tuple: (playwright, browser, page) para gerenciamento do ciclo de vida.

        Example:
            >>> playwright, browser, page = await self._abrir_pagina("https://...")
            >>> # ... realizar operações ...
            >>> await page.close()
            >>> await browser.close()
            >>> await playwright.stop()
        """
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(headless=self.headless)
        page = await browser.new_page()

        page.set_default_timeout(self.timeout)

        await page.goto(url, timeout=self.timeout)
        await page.wait_for_load_state("networkidle", timeout=self.timeout)

        return playwright, browser, page