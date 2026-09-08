from fastapi import APIRouter

router = APIRouter(prefix="/api/jogos", tags=["jogos"])

@router.get("/")
async def listar_jogos():
    """Lista todos os jogos (em desenvolvimento)"""
    return {"mensagem": "Lista de jogos - Em desenvolvimento"}

@router.get("/{jogo_id}")
async def obter_jogo(jogo_id: int):
    """Obtém detalhes de um jogo específico"""
    return {"jogo_id": jogo_id, "nome": "Jogo Exemplo", "status": "Em desenvolvimento"}