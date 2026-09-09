"""
Módulo de coleta de dados da Epic Games Store.

Este módulo contém o coletor principal (EpicColetor) e o scraper otimizado
(EpicScraper) para captura de preços e metadados da Epic Games Store.
"""

import asyncio
import re
import json
from urllib.parse import urlparse, parse_qs
from playwright.async_api import async_playwright
from .coletor_base import ColetorBase
from lista_jogos import get_epic_slug


class EpicColetor(ColetorBase):
    """
    Coletor para a Epic Games Store utilizando Playwright.

    Implementa a coleta de dados com configurações anti-detecção
    e fallback para extração direta do conteúdo da página.
    """

    def __init__(self):
        super().__init__()
        self.url_base = "https://store.epicgames.com/pt-BR/"

    def _formatar_preco(self, texto):
        """
        Extrai e formata o preço a partir de um texto.

        Args:
            texto (str): Texto contendo o preço.

        Returns:
            str: Preço formatado ("R$ XX,XX", "Grátis" ou "N/A").
        """
        if not texto:
            return "N/A"

        if any(termo in texto.lower() for termo in ["grátis", "gratuito", "free"]):
            return "Grátis"

        numeros = re.sub(r"[^0-9,.]", "", texto)
        if not numeros:
            return "N/A"

        numeros = numeros.replace(",", ".")
        try:
            return f"R$ {float(numeros):.2f}".replace(".", ",")
        except ValueError:
            return "N/A"

    def _calcular_desconto(self, preco_atual, preco_original):
        """
        Calcula o percentual de desconto com base nos preços.

        Args:
            preco_atual (str): Preço atual.
            preco_original (str): Preço original.

        Returns:
            str: Percentual de desconto ("XX%" ou "0%").
        """
        if preco_atual == "N/A" or preco_original == "N/A":
            return "0%"

        if preco_atual == "Grátis" or preco_original == "Grátis":
            return "0%"

        try:
            atual = float(preco_atual.replace("R$", "").replace(",", ".").strip())
            original = float(preco_original.replace("R$", "").replace(",", ".").strip())
            if original > 0 and atual < original:
                return f"{round(((original - atual) / original) * 100)}%"
        except (ValueError, AttributeError):
            pass

        return "0%"

    async def _passar_verificacao_idade(self, page):
        """
        Detecta e passa pela tela de verificacao de idade da Epic.

        Args:
            page: Objeto Page do Playwright.

        Returns:
            bool: True se conseguiu passar, False caso contrario.
        """
        try:
            if await page.locator("text=Insira sua data de nascimento").count() == 0:
                return False

            print("Tela de verificacao de idade detectada.")

            # Estrategia 1: Campos de entrada
            try:
                await page.fill('input[placeholder="DD"]', "01", timeout=2000)
                await page.fill('input[placeholder="MM"]', "01", timeout=2000)
                await page.fill('input[placeholder="AAAA"]', "1990", timeout=2000)
                await page.click('button:has-text("Continuar")', timeout=2000)
                await page.wait_for_timeout(500)
                print("Verificacao de idade concluida (campos).")
                return True
            except Exception:
                pass

            # Estrategia 2: Botoes numericos
            try:
                botoes_dia = await page.locator('button:has-text("01")').all()
                if botoes_dia:
                    await botoes_dia[0].click()

                botoes_mes = await page.locator('button:has-text("Janeiro")').all()
                if botoes_mes:
                    await botoes_mes[0].click()
                else:
                    botoes_mes = await page.locator('button:has-text("01")').all()
                    if len(botoes_mes) > 1:
                        await botoes_mes[1].click()

                botoes_ano = await page.locator('button:has-text("1990")').all()
                if botoes_ano:
                    await botoes_ano[0].click()

                await page.click('button:has-text("Continuar")', timeout=2000)
                await page.wait_for_timeout(500)
                print("Verificacao de idade concluida (botoes).")
                return True
            except Exception:
                pass

            # Estrategia 3: Clica em qualquer botao "Continuar"
            try:
                await page.click('button:has-text("Continuar")', timeout=2000)
                await page.wait_for_timeout(500)
                print("Verificacao de idade concluida (direta).")
                return True
            except Exception:
                pass

            return False

        except Exception as erro:
            print(f"Erro na verificacao de idade: {erro}")
            return False

    async def coletar_precos(self):
        """Coleta os precos dos jogos em destaque na Epic."""
        print("Coletando precos da Epic Games Store...")
        return await self.coletar_destaques(limite=10)

    async def coletar_promocoes(self):
        """Coleta jogos em promocao na Epic."""
        print("Coletando promocoes da Epic Games Store...")
        return await self.coletar_destaques(limite=10)

    async def coletar_jogo_por_steam_id(self, steam_id):
        """
        Coleta um jogo da Epic a partir do Steam ID.

        Args:
            steam_id (int): Identificador do jogo na Steam.

        Returns:
            dict: Dados do jogo ou erro.
        """
        slug = get_epic_slug(steam_id)
        if slug is None:
            return {"erro": f"Jogo {steam_id} nao disponivel na Epic Games Store"}
        return await self.coletar_jogo(slug)

    async def coletar_jogo(self, url_ou_id):
        """
        Coleta dados de um jogo especifico na Epic.

        Args:
            url_ou_id (str): URL ou slug do jogo.

        Returns:
            dict: Dados do jogo.
        """
        if url_ou_id.startswith("http"):
            url = url_ou_id
        else:
            url = f"{self.url_base}p/{url_ou_id}"

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ]
            )

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="pt-BR"
            )
            page = await context.new_page()

            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            try:
                print(f"Acessando: {url}")
                await page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")

                await page.wait_for_timeout(800)
                await self._passar_verificacao_idade(page)
                await page.wait_for_timeout(1000)
                await page.mouse.move(100, 100)
                await page.wait_for_timeout(300)

                # Nome do jogo
                nome = "N/A"
                try:
                    await page.wait_for_selector("h1", timeout=10000)
                    nome = await page.locator("h1").first.text_content()
                    nome = nome.strip() if nome else "N/A"
                except Exception:
                    pass

                # Precos
                preco_atual = "N/A"
                preco_original = "N/A"

                try:
                    # Verifica se e gratuito
                    gratuito = False
                    textos_gratis = ["grátis", "gratuito", "free", "acesso gratuito", "free access"]
                    for termo in textos_gratis:
                        if await page.locator(f"text={termo}").count() > 0:
                            gratuito = True
                            break

                    if gratuito:
                        preco_atual = "Grátis"
                        preco_original = "Grátis"
                    else:
                        seletores_preco = [
                            'strong:has-text("R$")',
                            'span[class*="price"]',
                            'div[class*="price"] strong',
                            ".eds_1ypbntdb strong",
                            "span.css-4jky3p",
                        ]

                        preco_encontrado = None
                        for seletor in seletores_preco:
                            try:
                                elemento = page.locator(seletor).first
                                if await elemento.count() > 0:
                                    texto = await elemento.text_content()
                                    if texto and "R$" in texto:
                                        preco_encontrado = texto
                                        break
                            except Exception:
                                continue

                        if preco_encontrado:
                            preco_atual = self._formatar_preco(preco_encontrado)
                        else:
                            elementos = await page.locator("text=R$").all()
                            for elemento in elementos:
                                try:
                                    estilo = await elemento.evaluate(
                                        "el => window.getComputedStyle(el).textDecoration"
                                    )
                                    if "line-through" not in estilo:
                                        texto = await elemento.text_content()
                                        if texto and "R$" in texto:
                                            preco_atual = self._formatar_preco(texto)
                                            break
                                except Exception:
                                    continue

                        # Preco original
                        if preco_atual != "N/A":
                            elementos = await page.locator("text=R$").all()
                            for elemento in elementos:
                                try:
                                    estilo = await elemento.evaluate(
                                        "el => window.getComputedStyle(el).textDecoration"
                                    )
                                    if "line-through" in estilo:
                                        texto = await elemento.text_content()
                                        if texto and "R$" in texto:
                                            preco_original = self._formatar_preco(texto)
                                            break
                                except Exception:
                                    continue

                            if preco_original == "N/A":
                                possiveis_originais = await page.locator("text=De: R$").all()
                                if possiveis_originais:
                                    for elemento in possiveis_originais:
                                        texto = await elemento.text_content()
                                        if "R$" in texto:
                                            preco_original = self._formatar_preco(
                                                texto.replace("De:", "").strip()
                                            )
                                            break

                                if preco_original == "N/A":
                                    preco_original = preco_atual

                except Exception as erro:
                    print(f"Erro ao capturar preco: {erro}")

                # Imagem
                imagem = "N/A"
                try:
                    await page.wait_for_selector('div[data-testid="picture"] img', timeout=5000)
                    imagem = await page.locator('div[data-testid="picture"] img').get_attribute("src")
                    if imagem and "svg" in imagem:
                        imagem = "N/A"
                except Exception:
                    pass

                if imagem == "N/A":
                    try:
                        imagens = await page.locator("img").all()
                        for img in imagens:
                            src = await img.get_attribute("src")
                            if src and "unrealengine" in src and not src.endswith(".svg"):
                                imagem = src
                                break
                    except Exception:
                        pass

                # Descricao
                descricao = "N/A"
                try:
                    paragrafos = await page.locator("p").all_text_contents()
                    for p in paragrafos:
                        if len(p) > 50 and "R$" not in p and not p.startswith("©"):
                            descricao = p.strip()
                            break
                except Exception:
                    pass

                desconto = self._calcular_desconto(preco_atual, preco_original)

                await browser.close()

                return {
                    "plataforma": "Epic Games",
                    "nome": nome,
                    "url": url,
                    "preco": preco_atual,
                    "preco_sem_desconto": preco_original,
                    "desconto": desconto,
                    "descricao": descricao,
                    "url_imagem": imagem,
                }

            except Exception as erro:
                print(f"Erro ao coletar jogo da Epic: {erro}")
                await browser.close()
                return {"erro": str(erro)}

    async def coletar_destaques(self, limite=10):
        """
        Coleta os jogos em destaque na pagina inicial.

        Args:
            limite (int): Numero maximo de jogos a coletar.

        Returns:
            dict: Dicionario com os jogos em destaque.
        """
        print("Coletando jogos em destaque da Epic...")

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                ]
            )

            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
                locale="pt-BR"
            )
            page = await context.new_page()

            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            try:
                await page.goto(self.url_base, timeout=self.timeout, wait_until="domcontentloaded")
                await page.wait_for_timeout(800)
                await self._passar_verificacao_idade(page)
                await page.wait_for_timeout(2000)

                try:
                    await page.wait_for_selector('a[data-testid="store-card"]', timeout=10000)
                except Exception:
                    await page.wait_for_selector('a[class*="store-card"]', timeout=5000)

                links = await page.locator('a[data-testid="store-card"]').all()
                if not links:
                    links = await page.locator('a[class*="store-card"]').all()

                resultados = []
                for i, link in enumerate(links[:limite]):
                    try:
                        href = await link.get_attribute("href")
                        if href:
                            if href.startswith("/"):
                                href = f"https://store.epicgames.com{href}"

                            print(f"[{i+1}] Coletando: {href}")
                            jogo = await self.coletar_jogo(href)
                            if "erro" not in jogo:
                                resultados.append(jogo)
                            await asyncio.sleep(0.8)
                    except Exception as erro:
                        print(f"Erro ao processar link: {erro}")

                await browser.close()
                return {"plataforma": "Epic Games", "jogos": resultados}

            except Exception as erro:
                print(f"Erro ao coletar destaques da Epic: {erro}")
                await browser.close()
                return {"erro": str(erro)}


# =============================================================================
# EPIC SCRAPER COM INTERCEPTACAO GRAPHQL
# =============================================================================

class EpicScraper:
    """
    Scraper otimizado para Epic Games Store.

    Utiliza interceptacao de respostas GraphQL para capturar precos
    de forma mais eficiente, com fallback para extracao direta.
    """

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.timeout = 60000

    async def iniciar(self):
        """Inicia o navegador e cria o contexto."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )

        self.context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="pt-BR"
        )

        self.page = await self.context.new_page()
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        print("Navegador iniciado com sucesso.")

    def _formatar_preco(self, texto):
        """Formata o preco a partir de um texto."""
        if not texto:
            return "N/A"

        if any(termo in texto.lower() for termo in ["grátis", "gratuito", "free"]):
            return "Grátis"

        numeros = re.sub(r"[^0-9,.]", "", texto)
        if not numeros:
            return "N/A"

        numeros = numeros.replace(",", ".")
        try:
            return f"R$ {float(numeros):.2f}".replace(".", ",")
        except ValueError:
            return "N/A"

    def _calcular_desconto(self, preco_atual, preco_original):
        """Calcula o percentual de desconto."""
        if preco_atual == "N/A" or preco_original == "N/A":
            return "0%"

        if preco_atual == "Grátis" or preco_original == "Grátis":
            return "0%"

        try:
            atual = float(preco_atual.replace("R$", "").replace(",", ".").strip())
            original = float(preco_original.replace("R$", "").replace(",", ".").strip())
            if original > 0 and atual < original:
                return f"{round(((original - atual) / original) * 100)}%"
        except (ValueError, AttributeError):
            pass

        return "0%"

    async def _passar_verificacao_idade(self, page):
        """Passa pela tela de verificacao de idade."""
        try:
            if await page.locator("text=Insira sua data de nascimento").count() == 0:
                return False

            print("Tela de verificacao de idade detectada.")

            try:
                await page.fill('input[placeholder="DD"]', "01", timeout=2000)
                await page.fill('input[placeholder="MM"]', "01", timeout=2000)
                await page.fill('input[placeholder="AAAA"]', "1990", timeout=2000)
                await page.click('button:has-text("Continuar")', timeout=2000)
                await page.wait_for_timeout(500)
                print("Verificacao de idade concluida.")
                return True
            except Exception:
                pass

            try:
                botoes_dia = await page.locator('button:has-text("01")').all()
                if botoes_dia:
                    await botoes_dia[0].click()

                botoes_mes = await page.locator('button:has-text("Janeiro")').all()
                if botoes_mes:
                    await botoes_mes[0].click()

                botoes_ano = await page.locator('button:has-text("1990")').all()
                if botoes_ano:
                    await botoes_ano[0].click()

                await page.click('button:has-text("Continuar")', timeout=2000)
                await page.wait_for_timeout(500)
                print("Verificacao de idade concluida.")
                return True
            except Exception:
                pass

            try:
                await page.click('button:has-text("Continuar")', timeout=2000)
                await page.wait_for_timeout(500)
                print("Verificacao de idade concluida.")
                return True
            except Exception:
                pass

            return False

        except Exception as erro:
            print(f"Erro na verificacao de idade: {erro}")
            return False

    async def _detectar_gratuito(self, page) -> bool:
        """
        Detecta se o jogo e gratuito baseado no botao de acao principal.

        Args:
            page: Objeto Page do Playwright.

        Returns:
            bool: True se o jogo e gratuito, False caso contrario.
        """
        conteudo_principal = page.locator("main")

        # Sinal primario: botao com texto "Obter"
        try:
            botao_obter = conteudo_principal.get_by_role("button", name="Obter", exact=True)
            if await botao_obter.count() > 0:
                return True
        except Exception:
            pass

        # Reforco: frases especificas
        frases_gratuito = [
            "gratuito",
            "jogar gratis",
            "free to play",
            "acesso gratuito",
            "free access",
        ]

        for frase in frases_gratuito:
            if await conteudo_principal.locator(f"text={frase}").count() > 0:
                return True

        return False

    async def coletar_jogo(self, slug: str) -> dict:
        """
        Coleta dados de um jogo com interceptacao GraphQL e fallback.

        Args:
            slug (str): Slug do jogo na Epic.

        Returns:
            dict: Dados do jogo.
        """
        url = f"https://store.epicgames.com/pt-BR/p/{slug}"
        respostas_preco = {}
        offer_id_principal = {"valor": None}
        preco_capturado = asyncio.Event()

        async def handle_response(response):
            """Intercepta respostas GraphQL."""
            if "/graphql" not in response.url:
                return

            params = parse_qs(urlparse(response.url).query)
            operation = params.get("operationName", [None])[0]

            try:
                if operation == "getMappingByPageSlug":
                    dados = await response.json()
                    mapping = dados.get("data", {}).get("StorePageMapping", {}).get("mapping") or {}
                    offer_id_principal["valor"] = mapping.get("mappings", {}).get("offerId")
                    if offer_id_principal["valor"] and offer_id_principal["valor"] in respostas_preco:
                        preco_capturado.set()

                elif operation == "getPriceWithAccount":
                    variaveis = json.loads(params.get("variables", ["{}"])[0])
                    line_offers = variaveis.get("lineOffers", [])
                    if line_offers:
                        offer_id = line_offers[0].get("offerId")
                        respostas_preco[offer_id] = await response.json()
                        if offer_id == offer_id_principal["valor"]:
                            preco_capturado.set()
            except Exception:
                pass

        self.page.on("response", handle_response)

        try:
            print(f"Acessando: {url}")

            try:
                await self.page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            except Exception as erro:
                print(f"Erro ao carregar pagina: {erro}")
                try:
                    await self.page.reload(timeout=30000)
                except Exception:
                    pass

            await self.page.wait_for_timeout(500)
            await self._passar_verificacao_idade(self.page)

            # Nome do jogo
            nome = "N/A"
            try:
                await self.page.wait_for_selector("h1", timeout=10000)
                texto = await self.page.locator("h1").first.text_content()
                nome = texto.strip() if texto else "N/A"
            except Exception:
                pass

            # Aguarda o preco (maximo 12 segundos)
            try:
                await asyncio.wait_for(preco_capturado.wait(), timeout=12.0)
            except asyncio.TimeoutError:
                pass

        finally:
            self.page.remove_listener("response", handle_response)

        offer_id = offer_id_principal["valor"]
        dados_offer = respostas_preco.get(offer_id) if offer_id else None

        if dados_offer:
            total_price = (
                dados_offer.get("data", {})
                .get("PriceEngine", {})
                .get("priceWithAccount", {})
                .get("totalPrice")
            )
            if total_price:
                original = total_price.get("originalPrice", 0)
                atual = total_price.get("discountPrice", 0)
                desconto_pct = round(((original - atual) / original) * 100) if original > 0 else 0

                return {
                    "plataforma": "Epic Games",
                    "nome": nome,
                    "url": url,
                    "preco": f"R$ {atual/100:.2f}".replace(".", ",") if atual > 0 else "Grátis",
                    "preco_sem_desconto": f"R$ {original/100:.2f}".replace(".", ",") if original > 0 else "Grátis",
                    "desconto": f"{desconto_pct}%",
                    "fonte": "GraphQL (interceptado do navegador)",
                }

        print("Preco nao capturado via GraphQL, usando fallback.")
        return await self.coletar_jogo_navegador(slug)

    async def coletar_jogo_navegador(self, slug):
        """
        Fallback: coleta dados usando seletores CSS no navegador.

        Args:
            slug (str): Slug do jogo na Epic.

        Returns:
            dict: Dados do jogo.
        """
        url = f"https://store.epicgames.com/pt-BR/p/{slug}"
        print(f"Fallback acessando: {url}")

        try:
            try:
                await self.page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            except Exception as erro:
                print(f"Erro ao carregar pagina (fallback): {erro}")
                try:
                    await self.page.reload(timeout=30000)
                except Exception:
                    pass

            await self.page.wait_for_timeout(800)
            await self._passar_verificacao_idade(self.page)
            await self.page.wait_for_timeout(1000)
            await self.page.mouse.move(100, 100)
            await self.page.wait_for_timeout(300)

            # Nome
            nome = "N/A"
            try:
                await self.page.wait_for_selector("h1", timeout=10000)
                nome = await self.page.locator("h1").first.text_content()
                nome = nome.strip() if nome else "N/A"
            except Exception:
                pass

            preco_atual = "N/A"
            preco_original = "N/A"
            conteudo_principal = self.page.locator("main")

            try:
                # Deteccao de gratuidade
                gratuito = await self._detectar_gratuito(self.page)

                if gratuito:
                    preco_atual = "Grátis"
                    preco_original = "Grátis"
                else:
                    # Seletores de preco
                    seletores_preco = [
                        'strong:has-text("R$")',
                        'span[class*="price"]',
                        'div[class*="price"] strong',
                        ".eds_1ypbntdb strong",
                        "span.css-4jky3p",
                    ]

                    preco_encontrado = None
                    for seletor in seletores_preco:
                        try:
                            elemento = conteudo_principal.locator(seletor).first
                            if await elemento.count() > 0:
                                texto = await elemento.text_content()
                                if texto and "R$" in texto:
                                    preco_encontrado = texto
                                    break
                        except Exception:
                            continue

                    if preco_encontrado:
                        preco_atual = self._formatar_preco(preco_encontrado)
                    else:
                        elementos = await conteudo_principal.locator("text=R$").all()
                        for elemento in elementos:
                            try:
                                estilo = await elemento.evaluate(
                                    "el => window.getComputedStyle(el).textDecoration"
                                )
                                if "line-through" not in estilo:
                                    texto = await elemento.text_content()
                                    if texto and "R$" in texto:
                                        preco_atual = self._formatar_preco(texto)
                                        break
                            except Exception:
                                continue

                    # Preco original
                    if preco_atual != "N/A" and preco_atual != "Grátis":
                        elementos = await conteudo_principal.locator("text=R$").all()
                        for elemento in elementos:
                            try:
                                estilo = await elemento.evaluate(
                                    "el => window.getComputedStyle(el).textDecoration"
                                )
                                if "line-through" in estilo:
                                    texto = await elemento.text_content()
                                    if texto and "R$" in texto:
                                        preco_original = self._formatar_preco(texto)
                                        break
                            except Exception:
                                continue

                        if preco_original == "N/A":
                            possiveis_originais = await conteudo_principal.locator("text=De: R$").all()
                            if possiveis_originais:
                                for elemento in possiveis_originais:
                                    texto = await elemento.text_content()
                                    if "R$" in texto:
                                        preco_original = self._formatar_preco(
                                            texto.replace("De:", "").strip()
                                        )
                                        break

                            if preco_original == "N/A":
                                preco_original = preco_atual

            except Exception as erro:
                print(f"Erro ao capturar preco: {erro}")

            # Imagem
            imagem = "N/A"
            try:
                await self.page.wait_for_selector('div[data-testid="picture"] img', timeout=5000)
                imagem = await self.page.locator('div[data-testid="picture"] img').get_attribute("src")
                if imagem and "svg" in imagem:
                    imagem = "N/A"
            except Exception:
                pass

            if imagem == "N/A":
                try:
                    imagens = await self.page.locator("img").all()
                    for img in imagens:
                        src = await img.get_attribute("src")
                        if src and "unrealengine" in src and not src.endswith(".svg"):
                            imagem = src
                            break
                except Exception:
                    pass

            # Descricao
            descricao = "N/A"
            try:
                paragrafos = await self.page.locator("p").all_text_contents()
                for p in paragrafos:
                    if len(p) > 50 and "R$" not in p and not p.startswith("©"):
                        descricao = p.strip()
                        break
            except Exception:
                pass

            desconto = self._calcular_desconto(preco_atual, preco_original)

            return {
                "plataforma": "Epic Games",
                "nome": nome,
                "url": url,
                "preco": preco_atual,
                "preco_sem_desconto": preco_original,
                "desconto": desconto,
                "descricao": descricao,
                "url_imagem": imagem,
                "fonte": "Navegador (Fallback)",
            }

        except Exception as erro:
            print(f"Erro ao coletar {slug} (navegador): {erro}")
            return {"erro": str(erro)}

    async def fechar(self):
        """Fecha o navegador e finaliza o Playwright."""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("Navegador fechado.")


# =============================================================================
# FUNCOES DE TESTE
# =============================================================================

async def testar_epic():
    """Testa o coletor principal da Epic."""
    coletor = EpicColetor()

    print("=" * 50)
    print("TESTANDO SCRAPER DA EPIC GAMES")
    print("=" * 50)

    print("\nTeste 1: Coletando Hades...")
    jogo = await coletor.coletar_jogo("hades")
    print(f"\nJogo encontrado:")
    print(f"  Nome: {jogo.get('nome')}")
    print(f"  Preco atual: {jogo.get('preco')}")
    print(f"  Preco original: {jogo.get('preco_sem_desconto')}")
    print(f"  Desconto: {jogo.get('desconto')}")

    print("\nTeste 2: Coletando Rainbow Six Siege...")
    jogo2 = await coletor.coletar_jogo("rainbow-six-siege-x")
    print(f"\nJogo encontrado:")
    print(f"  Nome: {jogo2.get('nome')}")
    print(f"  Preco atual: {jogo2.get('preco')}")
    print(f"  Preco original: {jogo2.get('preco_sem_desconto')}")
    print(f"  Desconto: {jogo2.get('desconto')}")

    print("\n" + "=" * 50)
    print("TESTE CONCLUIDO.")


async def testar_epic_scraper():
    """Testa o scraper otimizado com interceptacao GraphQL."""
    print("=" * 50)
    print("TESTANDO EPIC SCRAPER COM GRAPHQL")
    print("=" * 50)

    scraper = EpicScraper()
    await scraper.iniciar()

    try:
        slugs = [
            "marvels-spider-man-2",
            "hades",
            "rainbow-six-siege-x",
            "dave-the-diver-ed092a",
            "destiny-2",
            "god-of-war",
            "god-of-war-ragnarok-3ca641",
        ]

        for slug in slugs:
            print(f"\nColetando: {slug}")
            dados = await scraper.coletar_jogo(slug)

            if "erro" in dados:
                print(f"  Erro: {dados['erro']}")
            else:
                print(f"  Nome: {dados.get('nome')}")
                print(f"  Preco: {dados.get('preco')}")
                print(f"  Original: {dados.get('preco_sem_desconto')}")
                print(f"  Desconto: {dados.get('desconto')}")
                print(f"  Fonte: {dados.get('fonte', 'Desconhecida')}")

    finally:
        await scraper.fechar()

    print("\n" + "=" * 50)
    print("TESTE CONCLUIDO.")


if __name__ == "__main__":
    asyncio.run(testar_epic_scraper())