"""
Módulo de rotas para consulta de jogos.

Este módulo define os endpoints da API para listar jogos
e obter detalhes de um jogo específico.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from banco_dados import get_db
from modelos import Jogo


router = APIRouter(prefix="/api/jogos", tags=["jogos"])


@router.get("/")
async def listar_jogos(db: Session = Depends(get_db)):
    """
    Lista todos os jogos cadastrados no banco de dados.

    Args:
        db (Session): Sessão do banco de dados (injetada automaticamente).

    Returns:
        list: Lista de jogos com informações resumidas.
    """
    jogos = db.query(Jogo).all()

    return [
        {
            "id": jogo.id,
            "nome": jogo.nome,
            "steam_id": jogo.steam_id,
            "epic_id": jogo.epic_id,
            "desenvolvedor": jogo.desenvolvedor,
            "genero": jogo.genero,
            "preco_base_steam": float(jogo.preco_base_steam) if jogo.preco_base_steam else None,
            "preco_base_epic": float(jogo.preco_base_epic) if jogo.preco_base_epic else None,
            "url_steam": jogo.url_steam,
            "url_epic": jogo.url_epic,
        }
        for jogo in jogos
    ]


@router.get("/{jogo_id}")
async def obter_jogo(jogo_id: int, db: Session = Depends(get_db)):
    """
    Obtém detalhes completos de um jogo específico.

    Args:
        jogo_id (int): Identificador interno do jogo.
        db (Session): Sessão do banco de dados (injetada automaticamente).

    Returns:
        dict: Dados completos do jogo.

    Raises:
        HTTPException: Se o jogo não for encontrado (status 404).
    """
    jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()

    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    return {
        "id": jogo.id,
        "nome": jogo.nome,
        "steam_id": jogo.steam_id,
        "epic_id": jogo.epic_id,
        "desenvolvedor": jogo.desenvolvedor,
        "publicadora": jogo.publicadora,
        "genero": jogo.genero,
        "data_lancamento": jogo.data_lancamento.isoformat() if jogo.data_lancamento else None,
        "descricao_steam": jogo.descricao_steam,
        "descricao_epic": jogo.descricao_epic,
        "url_imagem_steam": jogo.url_imagem_steam,
        "url_imagem_epic": jogo.url_imagem_epic,
        "url_steam": jogo.url_steam,
        "url_epic": jogo.url_epic,
        "preco_base_steam": float(jogo.preco_base_steam) if jogo.preco_base_steam else None,
        "preco_base_epic": float(jogo.preco_base_epic) if jogo.preco_base_epic else None,
        "created_at": jogo.created_at.isoformat() if jogo.created_at else None,
        "updated_at": jogo.updated_at.isoformat() if jogo.updated_at else None,
    }


@router.get("/buscar/{termo}")
async def buscar_jogos(termo: str, db: Session = Depends(get_db)):
    """
    Busca jogos pelo nome (busca parcial).

    Args:
        termo (str): Termo de busca.
        db (Session): Sessão do banco de dados (injetada automaticamente).

    Returns:
        list: Lista de jogos que correspondem ao termo.
    """
    jogos = db.query(Jogo).filter(Jogo.nome.ilike(f"%{termo}%")).all()

    return [
        {
            "id": jogo.id,
            "nome": jogo.nome,
            "steam_id": jogo.steam_id,
            "epic_id": jogo.epic_id,
            "desenvolvedor": jogo.desenvolvedor,
            "genero": jogo.genero,
            "preco_base_steam": float(jogo.preco_base_steam) if jogo.preco_base_steam else None,
            "preco_base_epic": float(jogo.preco_base_epic) if jogo.preco_base_epic else None,
        }
        for jogo in jogos
    ]