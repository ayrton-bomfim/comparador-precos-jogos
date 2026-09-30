# debug_idade2.py
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(locale="pt-BR")
        page = await context.new_page()

        await page.goto(
            "https://store.epicgames.com/pt-BR/p/hogwarts-legacy",
            wait_until="domcontentloaded",
            timeout=60000,
        )
        await page.wait_for_timeout(3000)

        # Clica no botão DD (o [3] da lista anterior)
        print("\n=== CLICANDO EM DD ===")
        dd = page.locator("button", has_text="DD").first
        await dd.click()
        await page.wait_for_timeout(1000)

        print("\n=== BOTÕES APÓS CLICAR EM DD ===")
        botoes = await page.locator("button").all()
        for i, btn in enumerate(botoes[:30]):
            texto = await btn.text_content()
            texto = texto.strip()[:40] if texto else ""
            if texto:
                print(f"  [{i}] '{texto}'")

        # Tenta clicar no dia 15
        print("\n=== TENTANDO CLICAR NO DIA 15 ===")
        try:
            dia = page.locator("button", has_text="15").first
            if await dia.count() > 0:
                await dia.click()
                await page.wait_for_timeout(1000)
                print("Clique no dia 15 OK")
        except Exception as e:
            print(f"Erro: {e}")

        # Clica em MM
        print("\n=== CLICANDO EM MM ===")
        mm = page.locator("button", has_text="MM").first
        if await mm.count() > 0:
            await mm.click()
            await page.wait_for_timeout(1000)

        print("\n=== BOTÕES APÓS CLICAR EM MM ===")
        botoes = await page.locator("button").all()
        for i, btn in enumerate(botoes[:30]):
            texto = await btn.text_content()
            texto = texto.strip()[:40] if texto else ""
            if texto:
                print(f"  [{i}] '{texto}'")

        # Tenta clicar em Junho
        print("\n=== TENTANDO CLICAR EM JUNHO ===")
        try:
            mes = page.locator("button", has_text="Junho").first
            if await mes.count() > 0:
                await mes.click()
                await page.wait_for_timeout(1000)
                print("Clique em Junho OK")
            else:
                print("Botão 'Junho' não encontrado")
        except Exception as e:
            print(f"Erro: {e}")

        # Clica em AAAA
        print("\n=== CLICANDO EM AAAA ===")
        aaaa = page.locator("button", has_text="AAAA").first
        if await aaaa.count() > 0:
            await aaaa.click()
            await page.wait_for_timeout(1000)

        # Tenta clicar em 1990
        print("\n=== TENTANDO CLICAR EM 1990 ===")
        try:
            ano = page.locator("button", has_text="1990").first
            if await ano.count() > 0:
                await ano.click()
                await page.wait_for_timeout(1000)
                print("Clique em 1990 OK")
            else:
                print("Botão '1990' não encontrado")
        except Exception as e:
            print(f"Erro: {e}")

        # Clica em Continuar
        print("\n=== CLICANDO EM CONTINUAR ===")
        cont = page.locator("button", has_text="Continuar").first
        if await cont.count() > 0:
            await cont.click()
            await page.wait_for_timeout(2000)
            print("Clique em Continuar OK")

        # Verifica se o modal sumiu
        print("\n=== MODAL AINDA ESTÁ LÁ? ===")
        count = await page.locator("text=Insira sua data de nascimento").count()
        print(f"Ocorrências: {count}")

        print("\nPressione Enter para fechar...")
        input()

        await browser.close()

asyncio.run(main())