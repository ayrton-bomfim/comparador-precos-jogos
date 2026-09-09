"""
Script de diagnóstico para interceptação de requisições da Epic Games Store.

Este script abre a página de um jogo na Epic e intercepta todas as
requisições de rede para identificar onde os dados de preço são carregados.
"""

import sys
import os
import asyncio
import json
from playwright.async_api import async_playwright

# Adiciona o diretório pai ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def testar_todas_requisicoes():
    """
    Testa a interceptacao de todas as requisicoes para encontrar
    onde estao os dados de preco da Epic Games Store.

    Os resultados sao salvos em um arquivo JSON para analise posterior.
    """
    print("=" * 50)
    print("TESTE DE INTERCEPTACAO DE REQUISICOES (EPIC)")
    print("=" * 50)

    slug = "marvels-spider-man-2"
    url = f"https://store.epicgames.com/pt-BR/p/{slug}"

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

        requisicoes_encontradas = []

        async def handle_response(response):
            """
            Intercepta e processa as respostas das requisicoes.

            Filtra apenas respostas com status 200 e URLs que podem
            conter dados de preco.
            """
            try:
                url_res = response.url
                status = response.status

                palavras_chave = [
                    "price", "offer", "product", "catalog",
                    "game", "store", "api", "graphql", "v1", "v2"
                ]

                if status == 200 and any(p in url_res.lower() for p in palavras_chave):
                    try:
                        conteudo = await response.text()
                        if len(conteudo) > 0 and conteudo.strip().startswith(("{", "[")):
                            print(f"\nRequisicao encontrada: {url_res}")
                            print(f"  Status: {status}")
                            print(f"  Tamanho: {len(conteudo)} bytes")

                            try:
                                dados = json.loads(conteudo)
                                requisicoes_encontradas.append({
                                    "url": url_res,
                                    "dados": dados
                                })

                                texto = json.dumps(dados, indent=2, ensure_ascii=False)
                                print("  Conteudo (primeiros 500 caracteres):")
                                print(texto[:500])

                                def buscar_preco(obj, caminho=""):
                                    """Busca recursivamente por campos de preco."""
                                    if isinstance(obj, dict):
                                        for chave, valor in obj.items():
                                            novo_caminho = f"{caminho}.{chave}" if caminho else chave

                                            if "price" in chave.lower() or "preco" in chave.lower():
                                                print(f"  Campo de preco: {novo_caminho} = {valor}")

                                            if isinstance(valor, (int, float)) and valor > 100:
                                                print(f"  Numero grande: {novo_caminho} = {valor}")

                                            buscar_preco(valor, novo_caminho)

                                    elif isinstance(obj, list):
                                        for i, item in enumerate(obj):
                                            buscar_preco(item, f"{caminho}[{i}]")

                                buscar_preco(dados)

                            except json.JSONDecodeError:
                                pass
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("response", handle_response)

        print(f"\nNavegando para: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(5000)

        print("\n" + "=" * 50)
        print("RESUMO")
        print("=" * 50)
        print(f"  Requisicoes com dados JSON: {len(requisicoes_encontradas)}")

        if requisicoes_encontradas:
            arquivo_saida = "requisicoes_epic.json"
            with open(arquivo_saida, "w", encoding="utf-8") as arquivo:
                json.dump(requisicoes_encontradas, arquivo, indent=2, ensure_ascii=False)
            print(f"\nDados salvos em: {arquivo_saida}")
        else:
            html = await page.content()
            with open("pagina_epic.html", "w", encoding="utf-8") as arquivo:
                arquivo.write(html)
            print("\nNenhuma requisicao JSON encontrada.")
            print("HTML da pagina salvo em: pagina_epic.html")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(testar_todas_requisicoes())