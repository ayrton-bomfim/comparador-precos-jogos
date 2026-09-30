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
from ..lista_jogos import get_epic_slug
from ..modelos import EpicOferta


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
        """Calcula o percentual de desconto sem confundir dado ausente com 0%."""
        if preco_atual in (None, "N/A") or preco_original in (None, "N/A"):
            return "N/A"

        if preco_atual == "Grátis" and preco_original == "Grátis":
            return "0%"

        try:
            atual = float(preco_atual.replace("R$", "").replace(".", "").replace(",", ".").strip())
            original = float(preco_original.replace("R$", "").replace(".", "").replace(",", ".").strip())
            if original > 0:
                desconto = round(((original - atual) / original) * 100)
                return f"{max(0, desconto)}%"
        except (ValueError, AttributeError):
            pass

        return "0%"

    async def _passar_verificacao_idade(self, page):
        """
        Passa pela tela de verificação de idade da Epic.

        Estrutura atual (2026-09):
          - Botões "DD", "MM", "AAAA" que abrem dropdowns
          - Dias: botões com texto "01".."31"
          - Meses: botões com texto "01".."12"
          - Anos: botões com texto (ex: "1990")
          - Botão "Continuar" (#btn_age_continue) fica disabled até completar
        """
        try:
            if await page.locator("text=Insira sua data de nascimento").count() == 0:
                return False

            print("🔞 Tela de verificação de idade detectada.")

            # ---------- Helper: escolhe uma opção do dropdown ----------
            async def escolher_opcao(label_botao: str, valor: str, nome_passo: str):
                """
                Clica no botão com o label (DD/MM/AAAA) e depois no botão
                com o valor exato. Retorna True se conseguiu.
                """
                try:
                    # Acha o botão de label usando has_text (mais confiável)
                    botao_label = page.locator("button", has_text=label_botao)
                    count = await botao_label.count()
                    if count == 0:
                        print(f"   ⚠️ [{nome_passo}] Botão '{label_botao}' não encontrado.")
                        return False

                    # Se o label já foi preenchido (ex: botão mostra "15" em vez de "DD"),
                    # então o passo já foi concluído
                    texto_atual = (await botao_label.first.text_content() or "").strip()
                    if texto_atual == valor:
                        print(f"   ℹ️ [{nome_passo}] Já preenchido com {valor}.")
                        return True

                    # Clica para abrir o dropdown
                    await botao_label.first.click(timeout=3000)
                    await page.wait_for_timeout(800)

                    # Procura o botão com o valor exato
                    opcao = page.locator("button", has_text=valor)
                    n_opcoes = await opcao.count()
                    print(f"   🔎 [{nome_passo}] {n_opcoes} botões com texto '{valor}' após clicar em '{label_botao}'.")

                    # Filtra pra pegar só os que têm texto EXATO (evita "15" pegar "150")
                    for i in range(n_opcoes):
                        btn = opcao.nth(i)
                        try:
                            txt = (await btn.text_content() or "").strip()
                            if txt == valor:
                                await btn.click(timeout=3000)
                                await page.wait_for_timeout(500)
                                print(f"   ✅ [{nome_passo}] Selecionado '{valor}'.")
                                return True
                        except Exception:
                            continue

                    print(f"   ⚠️ [{nome_passo}] Opção '{valor}' não encontrada nos botões.")
                    return False

                except Exception as e:
                    print(f"   ⚠️ [{nome_passo}] Erro: {e}")
                    return False

            # ---------- Passo 1: dia ----------
            await escolher_opcao("DD", "15", "dia")

            # ---------- Passo 2: mês ----------
            await escolher_opcao("MM", "06", "mês")

            # ---------- Passo 3: ano ----------
            await escolher_opcao("AAAA", "1990", "ano")

                        # ---------- Passo 4: continuar ----------
            try:
                botao_continuar = page.locator("#btn_age_continue")
                if await botao_continuar.count() == 0:
                    botao_continuar = page.locator("button", has_text="Continuar").first

                # Espera o botão sair do disabled (até 8s)
                for tentativa in range(16):
                    is_disabled = await botao_continuar.get_attribute("disabled")
                    if is_disabled is None:
                        break
                    await page.wait_for_timeout(500)

                is_disabled = await botao_continuar.get_attribute("disabled")
                if is_disabled is not None:
                    print("   ⚠️ Botão Continuar continua disabled após 8s. Tentando mesmo assim...")

                await botao_continuar.click(timeout=3000)
                await page.wait_for_timeout(1500)
                print("   ✅ Botão Continuar clicado.")
            except Exception as e:
                print(f"   ⚠️ Erro no passo Continuar: {e}")
                return False

            # ---------- Confirma que o modal sumiu ----------
            await page.wait_for_timeout(1500)
            if await page.locator("text=Insira sua data de nascimento").count() > 0:
                print("   ⚠️ Modal de idade ainda presente.")
                return False

            print("   ✅ Verificação de idade concluída com sucesso.")
            return True

        except Exception as erro:
            print(f"Erro na verificação de idade: {erro}")
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
                                    # Não assumir que o preço atual é o original.
                                    # Ausência de preço original deve permanecer como N/A.
                                    preco_original = "N/A"

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

    Utiliza interceptação de respostas GraphQL para capturar preço e
    metadados (desenvolvedora, publicadora, descrição, gênero, imagem)
    de forma estruturada, com fallback para extração direta do DOM
    quando a interceptação não é concluída a tempo.
    """

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.playwright = None
        self.timeout = 60000

        # Número máximo de tentativas para obter
        # offerId e sandboxId antes do fallback.
        self.max_tentativas_mapping = 3

        # Tempo máximo de espera por tentativa.
        self.timeout_mapping = 10.0

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
        """Calcula o percentual de desconto sem confundir dado ausente com 0%."""
        if preco_atual in (None, "N/A") or preco_original in (None, "N/A"):
            return "N/A"

        if preco_atual == "Grátis" and preco_original == "Grátis":
            return "0%"

        try:
            atual = float(preco_atual.replace("R$", "").replace(".", "").replace(",", ".").strip())
            original = float(preco_original.replace("R$", "").replace(".", "").replace(",", ".").strip())
            if original > 0:
                desconto = round(((original - atual) / original) * 100)
                return f"{max(0, desconto)}%"
        except (ValueError, AttributeError):
            pass

        return "0%"

    async def _passar_verificacao_idade(self, page):
        """
        Passa pela tela de verificação de idade da Epic.

        Estrutura atual (2026-09):
          - Botões "DD", "MM", "AAAA" que abrem dropdowns
          - Dias: botões com texto "01".."31"
          - Meses: botões com texto "01".."12"
          - Anos: botões com texto (ex: "1990")
          - Botão "Continuar" (#btn_age_continue) fica disabled até completar
        """
        try:
            if await page.locator("text=Insira sua data de nascimento").count() == 0:
                return False

            print("🔞 Tela de verificação de idade detectada.")

            # ---------- Helper: escolhe uma opção do dropdown ----------
            async def escolher_opcao(label_botao: str, valor: str, nome_passo: str):
                """
                Clica no botão com o label (DD/MM/AAAA) e depois no botão
                com o valor exato. Retorna True se conseguiu.
                """
                try:
                    # Acha o botão de label usando has_text (mais confiável)
                    botao_label = page.locator("button", has_text=label_botao)
                    count = await botao_label.count()
                    if count == 0:
                        print(f"   ⚠️ [{nome_passo}] Botão '{label_botao}' não encontrado.")
                        return False

                    # Se o label já foi preenchido (ex: botão mostra "15" em vez de "DD"),
                    # então o passo já foi concluído
                    texto_atual = (await botao_label.first.text_content() or "").strip()
                    if texto_atual == valor:
                        print(f"   ℹ️ [{nome_passo}] Já preenchido com {valor}.")
                        return True

                    # Clica para abrir o dropdown
                    await botao_label.first.click(timeout=3000)
                    await page.wait_for_timeout(800)

                    # Procura o botão com o valor exato
                    opcao = page.locator("button", has_text=valor)
                    n_opcoes = await opcao.count()
                    print(f"   🔎 [{nome_passo}] {n_opcoes} botões com texto '{valor}' após clicar em '{label_botao}'.")

                    # Filtra pra pegar só os que têm texto EXATO (evita "15" pegar "150")
                    for i in range(n_opcoes):
                        btn = opcao.nth(i)
                        try:
                            txt = (await btn.text_content() or "").strip()
                            if txt == valor:
                                await btn.click(timeout=3000)
                                await page.wait_for_timeout(500)
                                print(f"   ✅ [{nome_passo}] Selecionado '{valor}'.")
                                return True
                        except Exception:
                            continue

                    print(f"   ⚠️ [{nome_passo}] Opção '{valor}' não encontrada nos botões.")
                    return False

                except Exception as e:
                    print(f"   ⚠️ [{nome_passo}] Erro: {e}")
                    return False

            # ---------- Passo 1: dia ----------
            await escolher_opcao("DD", "15", "dia")

            # ---------- Passo 2: mês ----------
            await escolher_opcao("MM", "06", "mês")

            # ---------- Passo 3: ano ----------
            await escolher_opcao("AAAA", "1990", "ano")

                        # ---------- Passo 4: continuar ----------
            try:
                botao_continuar = page.locator("#btn_age_continue")
                if await botao_continuar.count() == 0:
                    botao_continuar = page.locator("button", has_text="Continuar").first

                # Espera o botão sair do disabled (até 8s)
                for tentativa in range(16):
                    is_disabled = await botao_continuar.get_attribute("disabled")
                    if is_disabled is None:
                        break
                    await page.wait_for_timeout(500)

                is_disabled = await botao_continuar.get_attribute("disabled")
                if is_disabled is not None:
                    print("   ⚠️ Botão Continuar continua disabled após 8s. Tentando mesmo assim...")

                await botao_continuar.click(timeout=3000)
                await page.wait_for_timeout(1500)
                print("   ✅ Botão Continuar clicado.")
            except Exception as e:
                print(f"   ⚠️ Erro no passo Continuar: {e}")
                return False

            # ---------- Confirma que o modal sumiu ----------
            await page.wait_for_timeout(1500)
            if await page.locator("text=Insira sua data de nascimento").count() > 0:
                print("   ⚠️ Modal de idade ainda presente.")
                return False

            print("   ✅ Verificação de idade concluída com sucesso.")
            return True

        except Exception as erro:
            print(f"Erro na verificação de idade: {erro}")
            return False

    async def _detectar_gratuito(self, page) -> bool:
            """
            Detecta se o jogo é gratuito com base no botão de aquisição
            principal da página.

            Evita considerar o jogo gratuito apenas porque palavras como
            "gratuito" ou "free" aparecem em textos secundários da página.
            """
            conteudo_principal = page.locator("main")

            # Sinal principal: botão "Obter"
            try:
                botao_obter = conteudo_principal.get_by_role(
                    "button",
                    name="Obter",
                    exact=True
                )

                if await botao_obter.count() > 0:
                    return True

            except Exception:
                pass

            return False

    async def coletar_jogo(self, slug: str, jogo_id: int = None, db=None) -> dict:
            """
            Coleta preço e metadados via GraphQL ativo (page.evaluate + fetch).
            """
            url = f"https://store.epicgames.com/pt-BR/p/{slug}"

            mapping_result = {
                "offerId": None,
                "sandboxId": None,
                "hashes": {},
            }

            # -------------------------------------------------------------
            # CACHE DE OFERTA
            # -------------------------------------------------------------
            # Quando o jogo já possui uma oferta Epic ativa no banco,
            # reutiliza offerId e sandboxId e evita a descoberta via mapping.
            oferta_cacheada = False

            if db is not None and jogo_id is not None:
                oferta = (
                    db.query(EpicOferta)
                    .filter(
                        EpicOferta.jogo_id == jogo_id,
                        EpicOferta.ativo.is_(True)
                    )
                    .first()
                )

                if oferta:
                    mapping_result["offerId"] = oferta.offer_id
                    mapping_result["sandboxId"] = oferta.sandbox_id
                    oferta_cacheada = True

                    print(
                        "   💾 Oferta Epic encontrada no banco."
                    )
                    print(
                        f"      offerId={oferta.offer_id}"
                    )
                    print(
                        f"      sandboxId={oferta.sandbox_id}"
                    )

            mapping_capturado = asyncio.Event()

            async def handle_mapping(response):
                if "/graphql" not in response.url:
                    return

                # ---------------------------------------------------------
                # Identifica a operação e captura o hash da persisted query
                # ---------------------------------------------------------
                params = parse_qs(urlparse(response.url).query)
                operation = params.get("operationName", [None])[0]

                extensions = params.get("extensions", [None])[0]

                if operation and extensions:
                    try:
                        ext = json.loads(extensions)

                        sha = (
                            ext
                            .get("persistedQuery", {})
                            .get("sha256Hash")
                        )

                        if sha:
                            mapping_result["hashes"][operation] = sha

                    except (json.JSONDecodeError, TypeError, AttributeError):
                        pass

                # ---------------------------------------------------------
                # Lê a resposta GraphQL
                # ---------------------------------------------------------
                try:
                    if response.status != 200:
                        return

                    dados = await response.json()

                except Exception:
                    return

                # ---------------------------------------------------------
                # Procura StorePageMapping independentemente da operação
                # ---------------------------------------------------------
                try:
                    store_mapping = (
                        dados
                        .get("data", {})
                        .get("StorePageMapping", {})
                        .get("mapping")
                        or {}
                    )

                    if not store_mapping:
                        return

                    # -----------------------------------------------------
                    # Identifica o pageSlug retornado
                    # -----------------------------------------------------
                    page_slug = store_mapping.get("pageSlug")

                    # -----------------------------------------------------
                    # Confirma que o mapping pertence à página atual.
                    #
                    # getMappingByPageSlug já é específico da página.
                    # Para outras operações, validamos o slug quando
                    # ele estiver disponível.
                    # -----------------------------------------------------
                    if operation != "getMappingByPageSlug":
                        if page_slug and page_slug != slug:
                            return

                    mappings = store_mapping.get("mappings") or {}

                    offer_id = (
                        mappings.get("offerId")
                        or store_mapping.get("offerId")
                    )

                    sandbox_id = store_mapping.get("sandboxId")

                    # -----------------------------------------------------
                    # DIAGNÓSTICO
                    #
                    # Só imprime quando encontramos StorePageMapping.
                    # Isso permite verificar exatamente o que chegou.
                    # -----------------------------------------------------
                    print(
                        f"   [MAPPING] Encontrado | "
                        f"operação={operation} | "
                        f"pageSlug={page_slug} | "
                        f"offerId={offer_id} | "
                        f"sandboxId={sandbox_id}"
                    )

                    # -----------------------------------------------------
                    # Atualiza offerId
                    # -----------------------------------------------------
                    if offer_id and not mapping_result["offerId"]:
                        mapping_result["offerId"] = offer_id

                        print(
                            f"   [MAPPING] ✅ offerId salvo: "
                            f"{mapping_result['offerId']}"
                        )

                    # -----------------------------------------------------
                    # Atualiza sandboxId
                    # -----------------------------------------------------
                    if sandbox_id and not mapping_result["sandboxId"]:
                        mapping_result["sandboxId"] = sandbox_id

                        print(
                            f"   [MAPPING] ✅ sandboxId salvo: "
                            f"{mapping_result['sandboxId']}"
                        )
                    # -----------------------------------------------------
                    # Mostra o estado atual do mapping_result
                    # -----------------------------------------------------
                    print(
                        f"   [MAPPING] Estado atual: "
                        f"offerId={mapping_result['offerId']} | "
                        f"sandboxId={mapping_result['sandboxId']} | "
                        f"event={mapping_capturado.is_set()}"
                    )

                    # -----------------------------------------------------
                    # Só considera o mapping capturado quando temos
                    # os dois identificadores necessários.
                    # -----------------------------------------------------
                    if (
                        mapping_result["offerId"]
                        and mapping_result["sandboxId"]
                    ):
                        if not mapping_capturado.is_set():
                            print(
                                "   [MAPPING] 🎯 MAPPING COMPLETO!"
                            )

                            print(
                                f"   [MAPPING] offerId="
                                f"{mapping_result['offerId']}"
                            )

                            print(
                                f"   [MAPPING] sandboxId="
                                f"{mapping_result['sandboxId']}"
                            )

                        mapping_capturado.set()

                        print(
                            f"   [MAPPING] ✅ Event setado: "
                            f"{mapping_capturado.is_set()}"
                        )

                except (AttributeError, TypeError) as erro:
                    print(
                        f"   [MAPPING] ⚠️ Erro ao processar mapping: "
                        f"{erro}"
                    )
            self.page.on("response", handle_mapping)

            try:
                print(f"Acessando: {url}")

                try:
                    await self.page.goto(
                        url,
                        timeout=self.timeout,
                        wait_until="domcontentloaded"
                    )
                except Exception as erro:
                    print(f"   ⚠️ Erro ao carregar página: {erro}")

                    try:
                        await self.page.reload(timeout=30000)
                    except Exception:
                        pass

                await self.page.wait_for_timeout(500)

                passou = await self._passar_verificacao_idade(self.page)

                if not passou:
                    await self.page.wait_for_timeout(1000)
                    passou = await self._passar_verificacao_idade(self.page)

                if await self.page.locator(
                    "text=Insira sua data de nascimento"
                ).count() > 0:
                    print(
                        f"   🚨 Verificação de idade ainda ativa para "
                        f"'{slug}', pulando GraphQL."
                    )
                    return await self._coletar_com_fallback(slug)

                # ---------------------------------------------------------
                # Se a oferta já está no banco, não é necessário descobrir
                # novamente o mapping.
                # ---------------------------------------------------------
                max_tentativas_mapping = 3
                timeout_mapping = 10.0
                mapping_capturado_com_sucesso = False

                if oferta_cacheada:
                    print(
                        "   ⚡ Usando oferta armazenada. "
                        "Mapping via Playwright será ignorado."
                    )
                    mapping_capturado_com_sucesso = True

                else:
                    # ---------------------------------------------------------
                    # Tenta capturar o mapping até 3 vezes.
                    #
                    # A primeira tentativa aproveita as requisições
                    # GraphQL realizadas durante o carregamento da página.
                    #
                    # As tentativas seguintes recarregam a página para
                    # provocar um novo ciclo de requisições GraphQL.
                    # ---------------------------------------------------------

                    for tentativa in range(
                        1,
                        max_tentativas_mapping + 1
                    ):
                        print(
                            f"   🔄 Tentativa de mapping "
                            f"{tentativa}/{max_tentativas_mapping}"
                        )

                        # -----------------------------------------------------
                        # A partir da segunda tentativa, recarrega a página
                        # para gerar novas requisições GraphQL.
                        # -----------------------------------------------------
                        if tentativa > 1:
                            print(
                                "   🔄 Recarregando página para nova "
                                "tentativa de GraphQL..."
                            )

                            mapping_capturado.clear()

                            try:
                                await self.page.reload(
                                    timeout=self.timeout,
                                    wait_until="domcontentloaded"
                                )

                                await self.page.wait_for_timeout(800)

                            except Exception as erro:
                                print(
                                    f"   ⚠️ Erro ao recarregar página: {erro}"
                                )
                                continue

                            # -------------------------------------------------
                            # Verifica novamente a tela de idade após o reload.
                            # -------------------------------------------------
                            passou = await self._passar_verificacao_idade(
                                self.page
                            )

                            if not passou:
                                await self.page.wait_for_timeout(1000)

                                passou = await self._passar_verificacao_idade(
                                    self.page
                                )

                            if await self.page.locator(
                                "text=Insira sua data de nascimento"
                            ).count() > 0:
                                print(
                                    "   ⚠️ Verificação de idade continua "
                                    "ativa após reload."
                                )
                                continue

                        # -----------------------------------------------------
                        # Aguarda o listener capturar o mapping.
                        # -----------------------------------------------------
                        try:
                            await asyncio.wait_for(
                                mapping_capturado.wait(),
                                timeout=timeout_mapping
                            )

                        except asyncio.TimeoutError:
                            print(
                                f"   ⚠️ Mapping não capturado na "
                                f"tentativa {tentativa}."
                            )

                        # -----------------------------------------------------
                        # Verifica se temos os dois identificadores necessários.
                        # -----------------------------------------------------
                        if (
                            mapping_result["offerId"]
                            and mapping_result["sandboxId"]
                        ):
                            print(
                                f"   ✅ Mapping capturado com sucesso "
                                f"na tentativa {tentativa}."
                            )

                            print(
                                f"      offerId={mapping_result['offerId']}"
                            )

                            print(
                                f"      sandboxId={mapping_result['sandboxId']}"
                            )

                            mapping_capturado_com_sucesso = True
                            break

                        if tentativa < max_tentativas_mapping:
                            print(
                                "   🔁 Mapping ainda não disponível. "
                                "Nova tentativa será realizada."
                            )

            finally:
                self.page.remove_listener(
                    "response",
                    handle_mapping
                )

            # -------------------------------------------------------------
            # Se nenhuma das tentativas conseguiu capturar o mapping,
            # utiliza o fallback.
            # -------------------------------------------------------------
            if not mapping_capturado_com_sucesso:
                print(
                    f"   ⚠️ offerId/sandboxId não capturados após "
                    f"{max_tentativas_mapping} tentativas."
                )

                print("   🔄 Recorrendo ao fallback.")

                return await self._coletar_com_fallback(slug)

            # -------------------------------------------------------------
            # Recupera os IDs capturados pelo mapping.
            # -------------------------------------------------------------
            offer_id = mapping_result["offerId"]
            sandbox_id = mapping_result["sandboxId"]

            # -------------------------------------------------------------
            # Recupera os hashes das operações GraphQL.
            # Se não forem encontrados durante a interceptação,
            # utiliza os hashes conhecidos como fallback.
            # -------------------------------------------------------------
            hash_catalogo = mapping_result["hashes"].get(
                "getCatalogOffer",
                "0bd79d7aaf89de3693abb813eec8b664321fab84037cbb968730631c8afe9a9d",
            )

            hash_preco = mapping_result["hashes"].get(
                "getPriceWithAccount",
                "1e6adef859bbc41a1d99e9543b5f0d3879dd14a25868398842d149a268db6933",
            )

            try:
                resultado_js = await self.page.evaluate(
                    """
                    async ({ offerId, sandboxId, hashCatalogo, hashPreco }) => {
                        const montarUrl = (operationName, variables, hash) => {
                            const params = new URLSearchParams({
                                operationName,
                                variables: JSON.stringify(variables),
                                extensions: JSON.stringify({
                                    persistedQuery: { version: 1, sha256Hash: hash }
                                }),
                            });
                            return `/graphql?${params.toString()}`;
                        };

                        const urlCatalogo = montarUrl(
                            "getCatalogOffer",
                            { locale: "pt-BR", country: "BR", sandboxId, offerId },
                            hashCatalogo
                        );
                        const urlPreco = montarUrl(
                            "getPriceWithAccount",
                            {
                                country: "BR",
                                locale: "pt-BR",
                                namespace: sandboxId,
                                calculateTax: false,
                                lineOffers: [{ offerId, quantity: 1 }],
                            },
                            hashPreco
                        );

                        const [respCatalogo, respPreco] = await Promise.all([
                            fetch(urlCatalogo, { credentials: "include" }),
                            fetch(urlPreco, { credentials: "include" }),
                        ]);

                        return {
                            catalogo: await respCatalogo.json(),
                            preco: await respPreco.json(),
                        };
                    }
                    """,
                    {
                        "offerId": offer_id,
                        "sandboxId": sandbox_id,
                        "hashCatalogo": hash_catalogo,
                        "hashPreco": hash_preco,
                    },
                )
            except Exception as erro:
                print(f"   ⚠️ Erro na chamada ativa via navegador para '{slug}': {erro}")
                return await self._coletar_com_fallback(slug)

            for fonte, resposta in (("catálogo", resultado_js.get("catalogo", {})),
                                    ("preço", resultado_js.get("preco", {}))):
                for erro in resposta.get("errors", []) or []:
                    msg = str(erro.get("message", ""))
                    if "PersistedQueryNotFound" in msg or "persistedQuery" in msg.lower():
                        op = erro.get("extensions", {}).get("operationName", "desconhecida")
                        print(f"   🚨 ALERTA: hash expirada na Epic para '{op}' (fonte: {fonte}).")

            catalogo = (
                resultado_js.get("catalogo", {})
                .get("data", {})
                .get("Catalog", {})
                .get("catalogOffer")
                or {}
            )
            total_price = (
                resultado_js.get("preco", {})
                .get("data", {})
                .get("PriceEngine", {})
                .get("priceWithAccount", {})
                .get("totalPrice")
            )

            if not total_price and catalogo.get("price", {}).get("totalPrice"):
                total_price = catalogo["price"]["totalPrice"]

            if not catalogo or not total_price:
                print(f"   ⚠️ Dados incompletos para '{slug}', recorrendo ao fallback.")
                return await self._coletar_com_fallback(slug)

            original = total_price.get("originalPrice")
            discount_price = total_price.get("discountPrice")

            # Não usar "or original" aqui: preço 0 é válido e representa uma
            # oferta gratuita, podendo inclusive resultar em 100% de desconto.
            if original is None:
                print(f"   ⚠️ originalPrice ausente para '{slug}'.")
                return await self._coletar_com_fallback(slug)

            atual = original if discount_price is None else discount_price

            if original <= 0:
                preco_atual_str = "Grátis"
                preco_original_str = "Grátis"
                desconto_pct = 0
            else:
                preco_atual_str = f"R$ {atual / 100:.2f}".replace(".", ",")
                preco_original_str = f"R$ {original / 100:.2f}".replace(".", ",")
                desconto_pct = round(((original - atual) / original) * 100)
                desconto_pct = max(0, min(100, desconto_pct))

            imagem = next(
                (img["url"] for img in catalogo.get("keyImages", [])
                if img.get("type") == "OfferImageWide"),
                None,
            )

            genero = ", ".join(
                t["name"] for t in catalogo.get("tags", [])
                if t.get("groupName") == "genre"
            ) or None

            return {
                "plataforma": "Epic Games",
                "nome": catalogo.get("title"),
                "url": url,
                "preco": preco_atual_str,
                "preco_sem_desconto": preco_original_str,
                "desconto": f"{desconto_pct}%",
                "desenvolvedor": catalogo.get("developerDisplayName"),
                "publicadora": catalogo.get("publisherDisplayName"),
                "data_lancamento": catalogo.get("releaseDate"),
                "descricao": catalogo.get("description"),
                "genero": genero,
                "url_imagem": imagem,

                "epic_offer_id": offer_id,
                "epic_sandbox_id": sandbox_id,
                "epic_titulo": catalogo.get("title"),
                "epic_tipo": catalogo.get("offerType"),

                "fonte": "GraphQL (chamada ativa via navegador)",
                "revisao_manual": False,
            }

    async def _coletar_com_fallback(self, slug: str) -> dict:
        """
        Medida paliativa: recorre ao fallback de seletores CSS.
        """
        resultado = await self.coletar_jogo_navegador(slug)

        if "erro" in resultado:
            return {
                "plataforma": "Epic Games",
                "nome": None,
                "url": f"https://store.epicgames.com/pt-BR/p/{slug}",
                "preco": None,
                "preco_sem_desconto": None,
                "desconto": None,
                "desenvolvedor": None,
                "publicadora": None,
                "data_lancamento": None,
                "descricao": None,
                "genero": None,
                "url_imagem": None,
                "fonte": "Falha total na captura",
                "revisao_manual": True,
                "motivo_fallback": "Falha total na captura dos dados",
            }

        resultado["revisao_manual"] = True
        resultado["fonte"] = "Navegador (Fallback - requer revisão manual)"
        resultado["motivo_fallback"] = "GraphQL indisponível ou dados incompletos"
        return resultado

    async def coletar_jogo_navegador(self, slug):
        """
        Fallback: coleta dados usando seletores CSS no navegador.

        Usado apenas quando a interceptação GraphQL (preço + catálogo)
        não é concluída a tempo. Note que este método não captura
        desenvolvedor/publicadora/gênero/data de lançamento, já que
        esses campos dependem dos dados estruturados do GraphQL —
        nesse caso, ficam como None no retorno.

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
                "desenvolvedor": None,
                "publicadora": None,
                "data_lancamento": None,
                "descricao": descricao,
                "genero": None,
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

async def testar_precos_epic():
    """Testa a captura de preços de jogos pagos da Epic."""

    print("=" * 60)
    print("TESTE DE PREÇOS - EPIC GAMES")
    print("=" * 60)

    scraper = EpicScraper()
    await scraper.iniciar()

    jogos_teste = [
        ("red-dead-redemption-2", "Red Dead Redemption 2"),
        ("cyberpunk-2077", "Cyberpunk 2077"),
        ("hogwarts-legacy", "Hogwarts Legacy"),
        ("the-witcher-3-wild-hunt", "The Witcher 3"),
        ("star-wars-jedi-survivor", "Star Wars Jedi: Survivor"),
    ]

    try:
        for i, (slug, nome_esperado) in enumerate(jogos_teste, 1):

            print("\n" + "-" * 60)
            print(f"[{i}/5] {nome_esperado}")
            print(f"Slug: {slug}")
            print("-" * 60)

            try:
                dados = await scraper.coletar_jogo(slug)

                if "erro" in dados:
                    print(f"❌ ERRO: {dados['erro']}")
                    continue

                print(f"Nome retornado: {dados.get('nome')}")
                print(f"Preço atual: {dados.get('preco')}")
                print(f"Preço original: {dados.get('preco_sem_desconto')}")
                print(f"Desconto: {dados.get('desconto')}")
                print(f"Fonte: {dados.get('fonte')}")
                print(f"Revisão manual: {dados.get('revisao_manual')}")

            except Exception as erro:
                print(f"❌ ERRO AO TESTAR: {erro}")

    finally:
        await scraper.fechar()

    print("\n" + "=" * 60)
    print("TESTE FINALIZADO")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(testar_precos_epic())
