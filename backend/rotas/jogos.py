"""
Módulo de rotas para consulta de jogos.

Este módulo define os endpoints da API para listar jogos
e obter detalhes de um jogo específico.
"""

from fastapi import APIRouter, Depends, HTTPException
import requests
from sqlalchemy.orm import Session
from ..banco_dados import get_db
from ..modelos import Jogo, HistoricoPreco
from ..coletores.steam_coletor import SteamColetor


router = APIRouter(prefix="/api/jogos", tags=["jogos"])


def _normalizar_plataforma(plataforma):
    """
    Normaliza os nomes das plataformas usados no histórico.

    O histórico da Epic pode estar gravado como "Epic",
    enquanto versões da API podem procurar "Epic Games".
    Todos esses formatos passam a ser tratados como a mesma plataforma.
    """
    valor = (plataforma or "").strip().lower()

    if valor == "steam":
        return "steam"

    if valor in {"epic", "epic games", "epic games store"}:
        return "epic"

    return valor


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

    # Recupera o registro mais recente de cada plataforma para que
    # a listagem também possa informar o desconto atual.
    historicos = (
        db.query(HistoricoPreco)
        .order_by(HistoricoPreco.data_coleta.desc())
        .all()
    )

    ultimos_dados = {}

    for registro in historicos:
        chave = (
            registro.jogo_id,
            _normalizar_plataforma(registro.plataforma),
        )

        if chave not in ultimos_dados:
            ultimos_dados[chave] = {
                "desconto": registro.desconto or 0,
                "preco_atual": (
                    float(registro.preco_atual)
                    if registro.preco_atual is not None
                    else None
                ),
            }

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
            "url_imagem_steam": jogo.url_imagem_steam,
            "url_imagem_epic": jogo.url_imagem_epic,
            "preco_atual_steam": (
                ultimos_dados.get((jogo.id, "steam"), {}).get("preco_atual")
            ),
            "preco_atual_epic": (
                ultimos_dados.get((jogo.id, "epic"), {}).get("preco_atual")
            ),
            "desconto_steam": (
                ultimos_dados.get((jogo.id, "steam"), {}).get("desconto", 0)
            ),
            "desconto_epic": (
                ultimos_dados.get((jogo.id, "epic"), {}).get("desconto", 0)
            ),
            "visualizacoes": jogo.visualizacoes,
        }
        for jogo in jogos
    ]


@router.get("/{jogo_id}/historico")
async def obter_historico_jogo(jogo_id: int, db: Session = Depends(get_db)):
    """
    Obtém o histórico de preços de um jogo.
    """
    jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()

    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    historico = (
        db.query(HistoricoPreco)
        .filter(HistoricoPreco.jogo_id == jogo_id)
        .order_by(HistoricoPreco.data_coleta.asc())
        .all()
    )

    return [
        {
            "id": registro.id,
            "jogo_id": registro.jogo_id,
            "nome_jogo": registro.nome_jogo,
            "plataforma": registro.plataforma,
            "preco_atual": float(registro.preco_atual) if registro.preco_atual is not None else None,
            "preco_sem_desconto": float(registro.preco_sem_desconto) if registro.preco_sem_desconto is not None else None,
            "desconto": registro.desconto or 0,
            "data_coleta": registro.data_coleta.isoformat() if registro.data_coleta else None,
        }
        for registro in historico
    ]


@router.get("/{jogo_id}/midia")
async def obter_midia_jogo(jogo_id: int, db: Session = Depends(get_db)):
    """
    Obtém screenshots e vídeos da Steam diretamente, sem salvar no banco.
    """
    jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()

    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    if not jogo.steam_id:
        return {
            "screenshots": [],
            "videos": [],
        }

    url = (
        "https://store.steampowered.com/api/appdetails"
        f"?appids={jogo.steam_id}&l=portuguese&cc=br"
    )

    try:
        resposta = requests.get(url, timeout=15)
        resposta.raise_for_status()
        dados = resposta.json()

        dados_brutos = next(iter(dados.values()), None)

        if not dados_brutos or not dados_brutos.get("success", False):
            return {
                "screenshots": [],
                "videos": [],
            }

        dados_jogo = dados_brutos.get("data") or {}

        screenshots = [
            {
                "id": imagem.get("id"),
                "thumbnail": imagem.get("path_thumbnail"),
                "url": imagem.get("path_full"),
            }
            for imagem in dados_jogo.get("screenshots", [])
            if imagem.get("path_full")
        ]

        videos = [
            {
                "id": video.get("id"),
                "nome": video.get("name"),
                "thumbnail": video.get("thumbnail"),
                "webm": video.get("webm", {}),
                "mp4": video.get("mp4", {}),
                "destaque": video.get("highlight", False),
            }
            for video in dados_jogo.get("movies", [])
            if video.get("thumbnail")
        ]

        return {
            "screenshots": screenshots,
            "videos": videos,
        }

    except requests.exceptions.Timeout:
        print(f"Timeout ao buscar mídia da Steam para o jogo {jogo_id}")
        return {
            "screenshots": [],
            "videos": [],
        }

    except requests.exceptions.RequestException as erro:
        print(f"Erro de conexão ao buscar mídia da Steam para o jogo {jogo_id}: {erro}")
        return {
            "screenshots": [],
            "videos": [],
        }

    except Exception as erro:
        print(f"Erro inesperado ao buscar mídia da Steam para o jogo {jogo_id}: {erro}")
        return {
            "screenshots": [],
            "videos": [],
        }


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

    jogo.visualizacoes += 1
    db.commit()
    db.refresh(jogo)

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
        "visualizacoes": jogo.visualizacoes,
        "created_at": jogo.created_at.isoformat() if jogo.created_at else None,
        "updated_at": jogo.updated_at.isoformat() if jogo.updated_at else None,
    }


def _descricao_valida(descricao):
    if not descricao:
        return False

    valor = descricao.strip()
    return valor and valor.upper() not in {"N/A", "NÃO INFORMADO"}


@router.get("/{jogo_id}/descricao")
async def obter_descricao(jogo_id: int, db: Session = Depends(get_db)):
    """
    Obtém a descrição atual da Steam e usa o banco como fallback.
    """
    jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()

    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    # Fallback: descrição já armazenada no banco.
    if _descricao_valida(jogo.descricao_steam):
        descricao_fallback = jogo.descricao_steam
        fonte_fallback = "Steam (banco de dados)"
    elif _descricao_valida(jogo.descricao_epic):
        descricao_fallback = jogo.descricao_epic
        fonte_fallback = "Epic Games Store (banco de dados)"
    else:
        descricao_fallback = None
        fonte_fallback = None

    # Fonte principal: Steam em tempo real.
    if jogo.steam_id:
        try:
            coletor = SteamColetor()
            dados_steam = await coletor.coletar_jogo(jogo.steam_id)
            descricao_steam = dados_steam.get("descricao")

            if _descricao_valida(descricao_steam):
                return {
                    "fonte": "Steam",
                    "descricao": descricao_steam,
                    "atualizada": True,
                }
        except Exception as erro:
            print(f"Não foi possível obter descrição atual da Steam para o jogo {jogo_id}: {erro}")

    # Se a Steam falhar, mantém a experiência usando o dado persistido.
    return {
        "fonte": fonte_fallback,
        "descricao": descricao_fallback,
        "atualizada": False,
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
            "url_imagem_steam": jogo.url_imagem_steam,
            "url_imagem_epic": jogo.url_imagem_epic,
        }
        for jogo in jogos
    ]
