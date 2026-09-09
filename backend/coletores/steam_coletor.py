"""
Módulo de coleta de dados da Steam.

Este módulo contém o coletor para a plataforma Steam,
utilizando a API oficial com fallback para scraping direto
quando necessário.
"""

import asyncio
import re
import requests
from datetime import datetime
from .coletor_base import ColetorBase
from lista_jogos import JOGOS_STEAM


class SteamColetor(ColetorBase):
    """
    Coletor para a plataforma Steam.

    Utiliza a API oficial da Steam como fonte primária de dados,
    com fallback para scraping direto da página do jogo quando
    a API não retorna informações de preço.
    """

    def __init__(self):
        super().__init__()
        self.timeout = 30000
        self.url_base = "https://store.steampowered.com"
        self.api_base = "https://store.steampowered.com/api"
        self._cache_precos = {}

    def _limpar_descricao(self, texto):
        """
        Remove tags HTML e limpa o texto da descricao.

        Args:
            texto (str): Texto original com tags HTML.

        Returns:
            str: Texto limpo, sem tags HTML.
        """
        if not texto:
            return "N/A"

        texto = re.sub(r"<[^>]+>", "", texto)
        texto = re.sub(r"&[a-zA-Z]+;", " ", texto)
        texto = re.sub(r"\s+", " ", texto)
        texto = texto.strip()

        return texto if texto else "N/A"

    def _formatar_preco(self, valor):
        """
        Formata o preco para exibicao padronizada.

        Args:
            valor (int, float, str): Valor do preco em centavos ou string.

        Returns:
            str: Preco formatado ("R$ XX,XX", "Grátis" ou "N/A").
        """
        if valor is None:
            return "N/A"

        if isinstance(valor, (int, float)):
            if valor == 0:
                return "Grátis"
            if valor < 1000:
                return f"R$ {valor:.2f}".replace(".", ",")
            return f"R$ {valor/100:.2f}".replace(".", ",")

        if isinstance(valor, str):
            match = re.search(r"[\d,.]+", valor)
            if match:
                numero = match.group().replace(".", "").replace(",", ".")
                try:
                    return f"R$ {float(numero):.2f}".replace(".", ",")
                except ValueError:
                    pass

            if "grátis" in valor.lower() or "free" in valor.lower():
                return "Grátis"

            return valor.strip()

        return "N/A"

    async def _scrape_preco_direto(self, jogo_id):
        """
        Realiza scraping direto da pagina do jogo para obter o preco.

        Args:
            jogo_id (int): Identificador do jogo na Steam.

        Returns:
            str: Preco do jogo ou "N/A" se nao encontrado.
        """
        if jogo_id in self._cache_precos:
            return self._cache_precos[jogo_id]

        try:
            url = f"https://store.steampowered.com/app/{jogo_id}/"
            playwright = None
            browser = None
            page = None

            try:
                playwright, browser, page = await self._abrir_pagina(url)
                await page.wait_for_selector(".game_purchase_action", timeout=15000)

                preco = None

                # Tenta diferentes seletores de preco
                seletores = [
                    ".discount_final_price",
                    ".game_purchase_price",
                    ".game_purchase_action .price",
                ]

                for seletor in seletores:
                    try:
                        preco = await page.locator(seletor).text_content()
                        if preco:
                            break
                    except Exception:
                        continue

                # Verifica se e gratuito
                if not preco:
                    try:
                        botao = await page.locator(
                            ".game_purchase_action .btn_add_to_cart"
                        ).text_content()
                        if botao and any(termo in botao for termo in ["Jogar", "Play", "Instalar"]):
                            preco = "Grátis"
                    except Exception:
                        pass

                # Ultimo recurso: verificar no HTML
                if not preco:
                    try:
                        html = await page.content()
                        if "Grátis" in html or "Free" in html:
                            preco = "Grátis"
                    except Exception:
                        pass

                resultado = preco.strip() if preco else "N/A"
                self._cache_precos[jogo_id] = resultado
                return resultado

            finally:
                if page:
                    await page.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()

        except Exception as erro:
            print(f"Scraping falhou para o jogo {jogo_id}: {erro}")
            return "N/A"

    async def coletar_jogo(self, jogo_id):
        """
        Coleta dados de um jogo especifico na Steam.

        Args:
            jogo_id (int): Identificador do jogo na Steam.

        Returns:
            dict: Dicionario com os dados do jogo.
        """
        print(f"Buscando jogo na Steam: {jogo_id}")

        try:
            url = f"{self.api_base}/appdetails?appids={jogo_id}&l=portuguese&cc=br"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            dados = response.json()

            # Verifica se a chave do jogo existe
            if str(jogo_id) not in dados:
                print(f"Jogo {jogo_id} nao encontrado na API.")
                return {"plataforma": "Steam", "erro": "Jogo nao encontrado na API"}

            dados_brutos = dados[str(jogo_id)]

            # Verifica se a resposta foi bem-sucedida
            if not dados_brutos or not dados_brutos.get("success", False):
                print(f"Jogo {jogo_id} nao encontrado (success=False).")
                return {"plataforma": "Steam", "erro": "Jogo nao encontrado"}

            dados_jogo = dados_brutos.get("data")
            if not dados_jogo:
                print(f"Jogo {jogo_id} sem dados disponiveis.")
                return {"plataforma": "Steam", "erro": "Dados do jogo vazios"}

            # Extrai informacoes de preco
            preco_dados = dados_jogo.get("price_overview", {})
            is_free = dados_jogo.get("is_free", False)

            preco_atual = "N/A"
            preco_original = "N/A"
            desconto = "0%"

            if is_free:
                preco_atual = "Grátis"
                preco_original = "Grátis"
            elif preco_dados:
                preco_atual = self._formatar_preco(preco_dados.get("final"))
                preco_original = self._formatar_preco(preco_dados.get("initial"))
                desconto = f"{preco_dados.get('discount_percent', 0)}%"

            # Trata descricao
            descricao_bruta = (
                dados_jogo.get("about_the_game", "") or
                dados_jogo.get("detailed_description", "") or
                dados_jogo.get("short_description", "") or
                "N/A"
            )

            if len(descricao_bruta) < 20 or descricao_bruta == "N/A":
                descricao_bruta = dados_jogo.get("short_description", "N/A")

            descricao_limpa = self._limpar_descricao(descricao_bruta)

            if descricao_limpa == "N/A" or len(descricao_limpa) < 10:
                descricao_limpa = dados_jogo.get("short_description", "N/A")
                descricao_limpa = re.sub(r"<[^>]+>", "", descricao_limpa)
                descricao_limpa = descricao_limpa.strip()
                if not descricao_limpa:
                    descricao_limpa = "N/A"

            # Monta o resultado
            resultado = {
                "plataforma": "Steam",
                "id": str(jogo_id),
                "nome": dados_jogo.get("name", "N/A"),
                "preco": preco_atual,
                "preco_sem_desconto": preco_original,
                "desconto": desconto,
                "descricao": descricao_limpa,
                "url": f"https://store.steampowered.com/app/{jogo_id}/",
                "gratuito": is_free,
                "desenvolvedor": (
                    dados_jogo.get("developers", ["N/A"])[0]
                    if dados_jogo.get("developers") else "N/A"
                ),
                "publicadora": (
                    dados_jogo.get("publishers", ["N/A"])[0]
                    if dados_jogo.get("publishers") else "N/A"
                ),
                "genero": (
                    ", ".join([g["description"] for g in dados_jogo.get("genres", [])])
                    if dados_jogo.get("genres") else "N/A"
                ),
                "data_lancamento": dados_jogo.get("release_date", {}).get("date", None),
                "url_imagem": dados_jogo.get("header_image", "N/A"),
            }

            # Avaliacao (Metacritic)
            if "metacritic" in dados_jogo:
                resultado["avaliacao"] = (
                    f"{dados_jogo['metacritic'].get('score', 'N/A')}/100"
                )
            else:
                resultado["avaliacao"] = "N/A"

            return resultado

        except requests.exceptions.Timeout:
            print(f"Timeout ao buscar jogo {jogo_id}")
            return {"plataforma": "Steam", "erro": "Timeout"}

        except requests.exceptions.RequestException as erro:
            print(f"Erro de conexao: {erro}")
            return {"plataforma": "Steam", "erro": f"Erro de conexao: {erro}"}

        except Exception as erro:
            print(f"Erro inesperado ao buscar jogo {jogo_id}: {erro}")
            return {"plataforma": "Steam", "erro": f"Erro inesperado: {erro}"}

    async def coletar_precos(self):
        """
        Coleta precos dos jogos da lista definida.

        Returns:
            dict: Dicionario com os jogos coletados.
        """
        print("Coletando dados da Steam...")

        try:
            resultados = []
            for jogo_id in JOGOS_STEAM:
                dados_jogo = await self.coletar_jogo(jogo_id)
                if "erro" not in dados_jogo and dados_jogo.get("nome") != "N/A":
                    resultados.append(dados_jogo)

                await asyncio.sleep(1.5)

            return {"plataforma": "Steam", "jogos": resultados}

        except Exception as erro:
            print(f"Erro na coleta da Steam: {erro}")
            return {"plataforma": "Steam", "erro": str(erro)}

    async def coletar_promocoes(self):
        """
        Coleta jogos em promocao na Steam.

        Returns:
            dict: Dicionario com os jogos em promocao.
        """
        print("Coletando promocoes da Steam...")

        try:
            url = "https://store.steampowered.com/api/featuredcategories?l=portuguese&cc=br"
            response = requests.get(url)
            dados = response.json()

            promocoes = []

            featured = dados.get("featured", {}).get("items", [])
            if not featured:
                featured = dados.get("specials", {}).get("items", [])

            for jogo in featured[:10]:
                if jogo.get("id"):
                    jogo_id = jogo["id"]
                    detalhes = await self.coletar_jogo(jogo_id)
                    if "erro" not in detalhes:
                        promocoes.append({
                            "nome": detalhes.get("nome", "N/A"),
                            "preco_promocional": detalhes.get("preco", "N/A"),
                            "desconto": detalhes.get("desconto", "N/A"),
                            "url": f"https://store.steampowered.com/app/{jogo_id}/",
                        })

            return {"plataforma": "Steam", "promocoes": promocoes, "total": len(promocoes)}

        except Exception as erro:
            print(f"Erro ao coletar promocoes da Steam: {erro}")
            return {"plataforma": "Steam", "erro": str(erro)}


# =============================================================================
# FUNCAO DE TESTE
# =============================================================================

async def testar_steam():
    """Funcao de teste para o scraper da Steam."""
    coletor = SteamColetor()

    print("=" * 50)
    print("TESTANDO SCRAPER DA STEAM")
    print("=" * 50)

    print("\nColetando jogos em destaque...")
    destaques = await coletor.coletar_precos()

    jogos = destaques.get("jogos", [])
    print(f"{len(jogos)} jogos coletados.")

    if jogos:
        print("\nJOGOS COLETADOS:")
        for jogo in jogos:
            gratuito = " (GRATIS)" if jogo.get("gratuito") else ""
            preco = jogo.get("preco", "N/A")
            desconto = jogo.get("desconto", "0%")
            print(f"  - {jogo['nome']}: {preco}{gratuito} ({desconto})")

    print("\n" + "=" * 50)
    print("TESTE CONCLUIDO.")
    print("=" * 50)

    return destaques


if __name__ == "__main__":
    asyncio.run(testar_steam())