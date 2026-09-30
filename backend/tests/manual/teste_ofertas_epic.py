import asyncio
import json
import re

from ...coletores.epic_coletor import EpicScraper


JOGOS_TESTE = [
    {
        "nome": "Hades",
        "slug": "hades",
    },
    {
        "nome": "God of War",
        "slug": "god-of-war",
    },
    {
        "nome": "It Takes Two",
        "slug": "it-takes-two",
    },
    {
        "nome": "Cyberpunk 2077",
        "slug": "cyberpunk-2077",
    },
    {
        "nome": "Hogwarts Legacy",
        "slug": "hogwarts-legacy",
    },
]


async def testar_jogo(scraper, jogo):
    nome = jogo["nome"]
    slug = jogo["slug"]

    print("\n" + "=" * 90)
    print(f"TESTANDO: {nome}")
    print(f"Slug: {slug}")
    print("=" * 90)

    mapping = {
        "offerId": None,
        "sandboxId": None,
    }

    catalogos = {}
    catalogo = None

    try:
        page = scraper.page

        async def capturar_mapping(response):
            nonlocal catalogo
            if "/graphql" not in response.url:
                return

            try:
                operation_name = response.url.split("operationName=")[1].split("&")[0]

                if operation_name != "getMappingByPageSlug":
                    return

                dados = await response.json()

                mapping_data = (
                    dados
                    .get("data", {})
                    .get("StorePageMapping", {})
                    .get("mapping")
                )

                if not mapping_data:
                    return

                mappings = mapping_data.get("mappings") or {}

                offer_id = mappings.get("offerId")
                sandbox_id = mapping_data.get("sandboxId")

                if offer_id:
                    mapping["offerId"] = offer_id

                if sandbox_id:
                    mapping["sandboxId"] = sandbox_id

                # O catálogo pode ter chegado antes do mapping.
                # Se já temos esse catálogo armazenado, recuperamos agora.
                if mapping["offerId"] in catalogos:
                    catalogo = catalogos[mapping["offerId"]]

                print("\n[MAPPING ENCONTRADO]")
                print(f"pageSlug:  {mapping_data.get('pageSlug')}")
                print(f"offerId:   {mapping['offerId']}")
                print(f"sandboxId: {mapping['sandboxId']}")

            except Exception:
                pass

        async def capturar_catalogo(response):
            nonlocal catalogo

            if "/graphql" not in response.url:
                return

            try:
                operation_name = response.url.split("operationName=")[1].split("&")[0]

                if operation_name != "getCatalogOffer":
                    return

                dados = await response.json()

                catalog_offer = (
                    dados
                    .get("data", {})
                    .get("Catalog", {})
                    .get("catalogOffer")
                )

                if not catalog_offer:
                    return

                offer_id = catalog_offer.get("id")

                # Só aceitamos o catálogo depois que o mapping
                # já tiver informado o offerId principal.
                if not offer_id:
                    return

                catalogos[offer_id] = catalog_offer

                print("\n[CATÁLOGO ENCONTRADO]")
                print(f"ID:         {catalog_offer.get('id')}")
                print(f"Título:     {catalog_offer.get('title')}")
                print(f"Offer type: {catalog_offer.get('offerType')}")
                print(f"Namespace:  {catalog_offer.get('namespace')}")

                # Se o mapping já foi encontrado, podemos selecionar imediatamente.
                if mapping["offerId"] == offer_id:
                    catalogo = catalog_offer

            except Exception:
                pass

        page.on("response", capturar_mapping)
        page.on("response", capturar_catalogo)

        url = f"https://store.epicgames.com/pt-BR/p/{slug}"

        print(f"\nAcessando: {url}")

        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=scraper.timeout
        )

        # A página pode continuar fazendo requisições depois do carregamento.
        await page.wait_for_timeout(15000)

        # ------------------------------------------------------------------
        # Resultado
        # ------------------------------------------------------------------

        print("\n" + "-" * 90)
        print("RESULTADO")
        print("-" * 90)

        if not mapping["offerId"]:
            print("❌ Mapping não encontrado.")
            return {
                "nome": nome,
                "slug": slug,
                "status": "MAPPING_NAO_ENCONTRADO",
            }

        print(f"✅ offerId encontrado: {mapping['offerId']}")
        print(f"✅ sandboxId encontrado: {mapping['sandboxId']}")

        if not catalogo:
            print("❌ getCatalogOffer não confirmou o offerId.")
            return {
                "nome": nome,
                "slug": slug,
                "offerId": mapping["offerId"],
                "sandboxId": mapping["sandboxId"],
                "status": "CATALOGO_NAO_ENCONTRADO",
            }

        titulo = catalogo.get("title")
        offer_type = catalogo.get("offerType")

        preco = None

        price = catalogo.get("price")

        if price:
            total_price = price.get("totalPrice") or {}
            preco = total_price.get("discountPrice")

        print(f"✅ Título:     {titulo}")
        print(f"✅ Offer type: {offer_type}")

        if preco is not None:
            print(f"✅ Preço:      {preco / 100:.2f}".replace(".", ","))
        else:
            print("⚠️ Preço não encontrado no catalogOffer.")

        if offer_type == "BASE_GAME":
            print("✅ A oferta está marcada como BASE_GAME.")
        else:
            print(f"⚠️ A oferta NÃO é BASE_GAME: {offer_type}")

        return {
            "nome": nome,
            "slug": slug,
            "offerId": mapping["offerId"],
            "sandboxId": mapping["sandboxId"],
            "titulo": titulo,
            "offerType": offer_type,
            "preco": preco,
            "status": "OK",
        }

    except Exception as erro:
        print(f"\n❌ ERRO: {erro}")

        return {
            "nome": nome,
            "slug": slug,
            "status": "ERRO",
            "erro": str(erro),
        }


async def main():
    print("=" * 90)
    print("TESTE DE OFERTA PRINCIPAL DA EPIC")
    print("=" * 90)

    scraper = EpicScraper()

    resultados = []

    try:
        await scraper.iniciar()

        for jogo in JOGOS_TESTE:
            resultado = await testar_jogo(scraper, jogo)
            resultados.append(resultado)

            # Pequena pausa entre os jogos.
            await asyncio.sleep(3)

        print("\n\n" + "=" * 90)
        print("RESUMO FINAL")
        print("=" * 90)

        for resultado in resultados:
            print(f"\n{resultado['nome']}")
            print("-" * 50)

            print(f"Status:    {resultado.get('status')}")
            print(f"Offer ID:  {resultado.get('offerId')}")
            print(f"Sandbox:   {resultado.get('sandboxId')}")
            print(f"Título:    {resultado.get('titulo')}")
            print(f"Tipo:      {resultado.get('offerType')}")

            if resultado.get("preco") is not None:
                print(
                    f"Preço:     R$ {resultado['preco'] / 100:.2f}"
                    .replace(".", ",")
                )

        print("\n" + "=" * 90)
        print("JSON")
        print("=" * 90)

        print(
            json.dumps(
                resultados,
                indent=4,
                ensure_ascii=False
            )
        )

    except Exception as erro:
        print(f"\n❌ ERRO GERAL: {erro}")

    finally:
        if scraper.browser:
            await scraper.browser.close()

        if scraper.playwright:
            await scraper.playwright.stop()

        print("\nNavegador fechado.")


if __name__ == "__main__":
    asyncio.run(main())