from fastapi import APIRouter
from coletores.steam_coletor import SteamColetor
from coletores.epic_coletor import EpicColetor
import asyncio

router = APIRouter(prefix="/api/comparar", tags=["comparacao"])

@router.get("/{jogo_nome}")
async def comparar_jogo(jogo_nome: str):
    """Compara o preço de um jogo na Steam e na Epic"""
    steam = SteamColetor()
    epic = EpicColetor()
    
    preco_steam = await steam.coletar_jogo(jogo_nome)
    preco_epic = await epic.coletar_jogo(jogo_nome)
    
    return {
        "jogo": jogo_nome,
        "steam": preco_steam,
        "epic": preco_epic
    }

@router.get("/")
async def listar_lojas():
    """Lista as lojas disponíveis para comparação"""
    return {
        "lojas": ["Steam", "Epic Games Store"],
        "status": "online"
    }

@router.get("/testar/steam")
async def testar_steam():
    """Endpoint para testar o scraper da Steam"""
    coletor = SteamColetor()
    resultados = await coletor.coletar_precos()
    return resultados