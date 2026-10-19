"""
Módulo de rotas para comparação de preços entre plataformas.

Este módulo define os endpoints da API para comparar preços
de jogos entre a Steam e a Epic Games Store.
"""

import logging

from fastapi import APIRouter, HTTPException
from ..coletores.steam_coletor import SteamColetor
from ..coletores.epic_coletor import EpicColetor


logger = logging.getLogger(__name__)

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

    except Exception:
        logger.exception("Falha ao comparar preços.")
        raise HTTPException(
            status_code=500,
            detail="Não foi possível comparar os preços no momento."
        )