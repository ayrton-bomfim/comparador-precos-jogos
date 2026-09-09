"""
Módulo de rotas para comparação de preços entre plataformas.

Este módulo define os endpoints da API para comparar preços
de jogos entre a Steam e a Epic Games Store.
"""

from fastapi import APIRouter, HTTPException
from coletores.steam_coletor import SteamColetor
from coletores.epic_coletor import EpicColetor


router = APIRouter(prefix="/api/comparar", tags=["comparacao"])


@router.get("/")
async def listar_plataformas():
    """
    Lista as plataformas disponíveis para comparação.

    Returns:
        dict: Lista de plataformas e status da API.
    """
    return {
        "plataformas": ["Steam", "Epic Games Store"],
        "status": "online"
    }


@router.get("/{jogo_identificador}")
async def comparar_preco(jogo_identificador: str):
    """
    Compara o preço de um jogo nas duas plataformas.

    Args:
        jogo_identificador (str): Nome, ID ou slug do jogo.

    Returns:
        dict: Preços do jogo na Steam e na Epic.
    """
    steam_coletor = SteamColetor()
    epic_coletor = EpicColetor()

    try:
        preco_steam = await steam_coletor.coletar_jogo(jogo_identificador)
        preco_epic = await epic_coletor.coletar_jogo(jogo_identificador)

        return {
            "jogo": jogo_identificador,
            "steam": preco_steam,
            "epic": preco_epic
        }

    except Exception as erro:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao comparar preços: {str(erro)}"
        )


@router.get("/testar/steam")
async def testar_coletor_steam():
    """
    Endpoint de teste para o coletor da Steam.

    Returns:
        dict: Resultados da coleta de preços da Steam.
    """
    coletor = SteamColetor()
    resultados = await coletor.coletar_precos()
    return resultados


@router.get("/testar/epic")
async def testar_coletor_epic():
    """
    Endpoint de teste para o coletor da Epic.

    Returns:
        dict: Resultados da coleta de preços da Epic.
    """
    from coletores.epic_coletor import EpicScraper

    scraper = EpicScraper()
    await scraper.iniciar()

    try:
        slugs = ["hades", "red-dead-redemption-2"]
        resultados = {}

        for slug in slugs:
            dados = await scraper.coletar_jogo(slug)
            if "erro" not in dados:
                resultados[slug] = {
                    "nome": dados.get("nome"),
                    "preco": dados.get("preco"),
                    "preco_sem_desconto": dados.get("preco_sem_desconto"),
                    "desconto": dados.get("desconto"),
                }

        return {"plataforma": "Epic Games", "jogos": resultados}

    finally:
        await scraper.fechar()