"""
Script de verificação de slugs da Epic Games Store.

Este script valida quais slugs mapeados para a Epic Games Store
estão ativos e retornam uma página válida.
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from playwright.async_api import async_playwright
from lista_jogos import JOGOS_STEAM, get_epic_slug


async def verificar_slugs():
    """
    Verifica quais slugs da Epic Games Store estão ativos.

    Para cada jogo na lista, o script acessa a página correspondente
    na Epic e verifica se ela existe ou redireciona para "não encontrado".
    """
    print("VERIFICANDO SLUGS DA EPIC")
    print("=" * 50)

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

        for steam_id in JOGOS_STEAM:
            slug = get_epic_slug(steam_id)

            if slug is None:
                print(f"Exclusivo Steam: {steam_id}")
                continue

            print(f"Testando: {steam_id} -> {slug}")

            try:
                url = f"https://store.epicgames.com/pt-BR/p/{slug}"

                await page.goto(url, timeout=30000, wait_until="domcontentloaded")
                await page.wait_for_timeout(1500)

                if "not-found" in page.url or "404" in await page.title():
                    print("  STATUS: NAO ENCONTRADO")
                else:
                    try:
                        titulo = await page.locator("h1").first.text_content(timeout=3000)
                        print(f"  STATUS: OK - {titulo.strip() if titulo else 'Jogo encontrado'}")
                    except Exception:
                        print("  STATUS: OK (pagina de restricao de idade)")

            except Exception as erro:
                print(f"  ERRO: {erro}")

            await asyncio.sleep(0.3)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(verificar_slugs())