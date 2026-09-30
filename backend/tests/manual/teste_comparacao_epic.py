"""
Teste comparativo: EpicScraper (Playwright/GraphQL) x EGDATA.

Este teste e SOMENTE de leitura. Nao grava nada no banco.

Execucao a partir da raiz do projeto:
    python -m backend.tests.manual.teste_comparacao_epic
"""

import asyncio

from backend.coletores.epic_coletor import EpicScraper
from backend.servicos.egdata import buscar_preco_atual


JOGOS_TESTE = [
    {
        "nome": "The Witcher 3",
        "slug": "the-witcher-3-wild-hunt",
        "offer_id": "9064fdd49de04718abe631788ad5a759",
    },
    {
        "nome": "Hades",
        "slug": "hades",
        "offer_id": "2ae6edb2223c4f8c97e9839b5b6497bb",
    },
    {
        "nome": "Destiny 2",
        "slug": "destiny-2",
        "offer_id": "ee334739f5044a61be45528bd1d6b672",
    },
]


def normalizar_preco(valor):
    """Converte formatos do EpicScraper/EGDATA para float ou None."""
    if valor is None:
        return None

    if isinstance(valor, (int, float)):
        return round(float(valor), 2)

    texto = str(valor).strip()

    if texto.lower() in {"grátis", "gratis", "free"}:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace(" ", "")
        .replace(".", "")
        .replace(",", ".")
    )

    try:
        return round(float(texto), 2)
    except ValueError:
        return None


def normalizar_desconto(valor):
    if valor is None:
        return None

    if isinstance(valor, (int, float)):
        return int(round(float(valor)))

    texto = str(valor).replace("%", "").strip()

    try:
        return int(round(float(texto)))
    except ValueError:
        return None


def fmt_preco(valor):
    if valor is None:
        return "N/A"
    return f"R$ {valor:.2f}".replace(".", ",")


def fmt_diff(valor):
    if valor is None:
        return "N/A"
    sinal = "+" if valor > 0 else ""
    return f"{sinal}{valor:.2f}".replace(".", ",")


async def executar():
    print("=" * 72)
    print("COMPARACAO EPIC: PLAYWRIGHT/GRAPHQL x EGDATA")
    print("TESTE SOMENTE DE LEITURA - NENHUM REGISTRO SERA GRAVADO")
    print("=" * 72)

    scraper = EpicScraper()
    resultados = []

    await scraper.iniciar()

    try:
        for jogo in JOGOS_TESTE:
            print(f"\n[{jogo['nome']}]")

            antigo = None
            novo = None

            # ------------------------------------------------------------
            # Fonte atual: Playwright / GraphQL
            # ------------------------------------------------------------
            try:
                antigo = await scraper.coletar_jogo(jogo["slug"])
            except Exception as erro:
                antigo = {"erro": str(erro)}

            # ------------------------------------------------------------
            # Nova fonte: EGDATA
            # ------------------------------------------------------------
            try:
                novo = buscar_preco_atual(jogo["offer_id"])
            except Exception as erro:
                novo = {"erro": str(erro)}

            preco_antigo = None
            original_antigo = None
            desconto_antigo = None

            if antigo and "erro" not in antigo:
                preco_antigo = normalizar_preco(antigo.get("preco"))
                original_antigo = normalizar_preco(
                    antigo.get("preco_sem_desconto")
                )
                desconto_antigo = normalizar_desconto(antigo.get("desconto"))

            preco_novo = None
            original_novo = None
            desconto_novo = None

            if novo and "erro" not in novo:
                preco_novo = normalizar_preco(novo.get("preco"))
                original_novo = normalizar_preco(
                    novo.get("preco_sem_desconto")
                )
                desconto_novo = normalizar_desconto(novo.get("desconto"))

            print("  FONTE ATUAL")
            if antigo and "erro" in antigo:
                print(f"    Erro: {antigo['erro']}")
            else:
                print(f"    Preco:     {fmt_preco(preco_antigo)}")
                print(f"    Original:  {fmt_preco(original_antigo)}")
                print(f"    Desconto:  {desconto_antigo}%")
                print(f"    Fonte:     {antigo.get('fonte', 'N/A')}")

            print("  EGDATA")
            if novo and "erro" in novo:
                print(f"    Erro: {novo['erro']}")
            else:
                print(f"    Preco:     {fmt_preco(preco_novo)}")
                print(f"    Original:  {fmt_preco(original_novo)}")
                print(f"    Desconto:  {desconto_novo}%")
                print(f"    Promocao:  {novo.get('promocao_nome') or 'Nenhuma'}")
                print(f"    Inicio:    {novo.get('promocao_inicio') or 'N/A'}")
                print(f"    Fim:       {novo.get('promocao_fim') or 'N/A'}")

            if (
                antigo
                and "erro" not in antigo
                and novo
                and "erro" not in novo
            ):
                diferenca_preco = None
                if preco_antigo is not None and preco_novo is not None:
                    diferenca_preco = preco_novo - preco_antigo

                diferenca_original = None
                if original_antigo is not None and original_novo is not None:
                    diferenca_original = original_novo - original_antigo

                desconto_igual = desconto_antigo == desconto_novo
                preco_igual = (
                    diferenca_preco is not None
                    and abs(diferenca_preco) < 0.01
                )
                original_igual = (
                    diferenca_original is not None
                    and abs(diferenca_original) < 0.01
                )

                consistente = preco_igual and original_igual and desconto_igual

                print("  COMPARACAO")
                print(f"    Diferenca preco:    {fmt_diff(diferenca_preco)}")
                print(f"    Diferenca original: {fmt_diff(diferenca_original)}")
                print(
                    "    Desconto igual:     "
                    f"{'SIM' if desconto_igual else 'NAO'}"
                )
                print(
                    "    Resultado:           "
                    f"{'CONSISTENTE' if consistente else 'DIVERGENCIA'}"
                )

                resultados.append((jogo["nome"], consistente))

    finally:
        await scraper.fechar()

    print("\n" + "=" * 72)
    print("RESUMO")
    print("=" * 72)

    for nome, consistente in resultados:
        status = "OK" if consistente else "DIVERGENCIA"
        print(f"  {nome:<20} {status}")

    if resultados and all(consistente for _, consistente in resultados):
        print("\nTodos os precos/descontos comparados ficaram consistentes.")
        print("A proxima etapa pode ser a troca gradual da coleta atual pela EGDATA.")
    else:
        print("\nExiste pelo menos uma divergencia. Nao troque a fonte antiga ainda.")


if __name__ == "__main__":
    asyncio.run(executar())
