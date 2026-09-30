"""
Teste do coletor da Steam.

Este arquivo testa a coleta sem salvar nada no banco de dados.
"""

import asyncio

from ...coletores.steam_coletor import SteamColetor


JOGOS_TESTE = {
    1145360: "Hades",
    1868140: "DAVE THE DIVER",
    1085660: "Destiny 2",
    359550: "Rainbow Six Siege",
}


def validar_resultado(steam_id, nome_esperado, resultado):
    """
    Valida o resultado retornado pelo coletor.
    """

    erros = []

    # ---------------------------------------------------------
    # Verifica se houve erro
    # ---------------------------------------------------------

    if "erro" in resultado:
        erros.append(f"erro retornado: {resultado['erro']}")
        return erros

    # ---------------------------------------------------------
    # Campos básicos
    # ---------------------------------------------------------

    nome = resultado.get("nome")
    preco = resultado.get("preco")
    preco_original = resultado.get("preco_sem_desconto")
    desconto = resultado.get("desconto")
    gratuito = resultado.get("gratuito")

    if not nome or nome == "N/A":
        erros.append("nome não foi encontrado")

    if preco is None or preco == "N/A":
        erros.append("preço atual não foi encontrado")

    if preco_original is None or preco_original == "N/A":
        erros.append("preço sem desconto não foi encontrado")

    if desconto is None:
        erros.append("desconto não foi encontrado")

    if gratuito is None:
        erros.append("campo 'gratuito' não foi encontrado")

    # ---------------------------------------------------------
    # Regra para jogos gratuitos
    # ---------------------------------------------------------

    if gratuito is True:
        if preco != "Grátis":
            erros.append(
                f"jogo marcado como gratuito, "
                f"mas preço retornado foi: {preco}"
            )

        if preco_original != "Grátis":
            erros.append(
                f"jogo marcado como gratuito, "
                f"mas preço original retornado foi: {preco_original}"
            )

    # ---------------------------------------------------------
    # Verifica formato do desconto
    # ---------------------------------------------------------

    if desconto and not str(desconto).endswith("%"):
        erros.append(
            f"desconto com formato inesperado: {desconto}"
        )

    return erros


async def testar_coleta():
    """
    Testa a coleta pela API da Steam.
    """

    coletor = SteamColetor()

    print("=" * 70)
    print("TESTE DO STEAM COLETOR")
    print("=" * 70)

    total = 0
    aprovados = 0
    reprovados = 0

    for steam_id, nome_esperado in JOGOS_TESTE.items():

        total += 1

        print("\n" + "-" * 70)
        print(f"Steam ID: {steam_id}")
        print(f"Esperado: {nome_esperado}")
        print("-" * 70)

        resultado = await coletor.coletar_jogo(steam_id)

        erros = validar_resultado(
            steam_id,
            nome_esperado,
            resultado
        )

        # -----------------------------------------------------
        # Exibe resultado
        # -----------------------------------------------------

        if "erro" in resultado:

            print("❌ ERRO")
            print(f"Mensagem: {resultado['erro']}")

        else:

            print(f"Nome:              {resultado.get('nome')}")
            print(f"Preço atual:       {resultado.get('preco')}")
            print(f"Preço sem desconto:{resultado.get('preco_sem_desconto')}")
            print(f"Desconto:          {resultado.get('desconto')}")
            print(f"Gratuito:          {resultado.get('gratuito')}")
            print(f"Desenvolvedor:     {resultado.get('desenvolvedor')}")
            print(f"Publicadora:       {resultado.get('publicadora')}")
            print(f"Data lançamento:   {resultado.get('data_lancamento')}")

        # -----------------------------------------------------
        # Resultado da validação
        # -----------------------------------------------------

        if erros:
            reprovados += 1

            print("\n❌ TESTE REPROVADO")

            for erro in erros:
                print(f"   - {erro}")

        else:
            aprovados += 1
            print("\n✅ TESTE APROVADO")

        # Pequena pausa para não fazer várias requisições seguidas
        await asyncio.sleep(1)

    # ---------------------------------------------------------
    # Resumo
    # ---------------------------------------------------------

    print("\n")
    print("=" * 70)
    print("RESUMO")
    print("=" * 70)

    print(f"Total:       {total}")
    print(f"Aprovados:   {aprovados}")
    print(f"Reprovados:  {reprovados}")

    if reprovados == 0:
        print("\n✅ TODOS OS TESTES PASSARAM")
    else:
        print("\n⚠️ EXISTEM TESTES QUE PRECISAM SER INVESTIGADOS")


async def testar_fallback():
    """
    Testa diretamente o scraping da página da Steam.

    Atenção:
    Este teste chama o método de fallback diretamente.
    """

    coletor = SteamColetor()

    jogos = [
        (1145360, "Hades"),
        (1868140, "DAVE THE DIVER"),
        (1085660, "Destiny 2"),
        (359550, "Rainbow Six Siege"),
    ]

    print("\n")
    print("=" * 70)
    print("TESTE DO FALLBACK DE SCRAPING")
    print("=" * 70)

    for steam_id, nome_esperado in jogos:
        print("\n" + "-" * 70)
        print(f"Steam ID: {steam_id}")
        print(f"Esperado: {nome_esperado}")
        print("Abrindo página da Steam...")

        resultado = await coletor._scrape_preco_direto(steam_id)

        print(f"\nPreço encontrado pelo scraping: {resultado}")

        if resultado.get("preco") == "N/A":
            print("❌ FALLBACK NÃO ENCONTROU O PREÇO")
        else:
            print("✅ FALLBACK CONSEGUIU ENCONTRAR UM VALOR")


async def main():
    await testar_coleta()

    # ---------------------------------------------------------
    # O fallback é testado separadamente por enquanto,
    # pois ainda não está integrado ao fluxo principal.
    # ---------------------------------------------------------

    await testar_fallback()


if __name__ == "__main__":
    asyncio.run(main())