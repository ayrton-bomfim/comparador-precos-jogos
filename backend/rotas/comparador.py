"""
Módulo de rotas para comparação de preços entre plataformas.

Resolve o identificador recebido para o registro do catálogo antes de chamar
os coletores, evitando confundir o ID interno do DESCTRL com o AppID da Steam.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..banco_dados import get_db
from ..modelos import Jogo
from ..coletores.steam_coletor import SteamColetor
from ..coletores.epic_coletor import EpicColetor


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/comparar", tags=["comparacao"])


@router.get("/")
async def listar_plataformas():
    """
    Lista as plataformas disponíveis para comparação.

    Returns:
        dict: Lista das plataformas e status da API.
    """
    return {
        "plataformas": ["Steam", "Epic Games Store"],
        "status": "online",
    }


def _erro_plataforma(plataforma: str, mensagem: str) -> dict:
    """Monta uma resposta explícita quando não há preço confirmado."""
    return {"plataforma": plataforma, "erro": mensagem}


def _epic_retornou_verificacao(dados: dict) -> bool:
    """Impede que uma página de verificação seja apresentada como um jogo."""
    texto = " ".join(
        str(dados.get(campo) or "")
        for campo in ("nome", "descricao", "url")
    ).lower()
    marcadores = (
        "complete uma verificação de segurança",
        "complete uma verificacao de seguranca",
        "security check",
        "verify you are human",
    )
    return any(marcador in texto for marcador in marcadores) or (
        str(dados.get("nome") or "").strip().lower() == "mais uma etapa"
    )


@router.get("/{jogo_identificador}")
async def comparar_preco(
    jogo_identificador: str,
    db: Session = Depends(get_db),
):
    """
    Compara os preços de um jogo nas duas plataformas.

    O identificador pode ser o ID interno do DESCTRL, o AppID da Steam,
    um epic_id cadastrado ou um slug da Epic.
    """
    identificador = jogo_identificador.strip()
    if not identificador:
        raise HTTPException(status_code=400, detail="Identificador do jogo vazio.")

    try:
        jogo = None

        # IDs numéricos priorizam o ID interno do catálogo. Se não existir,
        # tenta-se localizar o registro pelo AppID real da Steam.
        if identificador.isdigit():
            jogo = db.query(Jogo).filter(Jogo.id == int(identificador)).first()
            if jogo is None:
                jogo = db.query(Jogo).filter(Jogo.steam_id == identificador).first()
        else:
            jogo = (
                db.query(Jogo)
                .filter(
                    (Jogo.steam_id == identificador)
                    | (Jogo.epic_id == identificador)
                    | (Jogo.nome.ilike(identificador))
                )
                .first()
            )

        steam_coletor = SteamColetor()
        epic_coletor = EpicColetor()

        if jogo is None:
            # Mantém suporte a slugs/URLs da Epic que não estejam no catálogo.
            if identificador.startswith("http") or not identificador.isdigit():
                dados_epic = await epic_coletor.coletar_jogo(identificador)
                if _epic_retornou_verificacao(dados_epic):
                    dados_epic = _erro_plataforma(
                        "Epic Games",
                        "A loja retornou uma verificação de segurança; preço não confirmado.",
                    )
                return {
                    "jogo": identificador,
                    "steam": _erro_plataforma(
                        "Steam",
                        "Jogo não encontrado no catálogo do DESCTRL.",
                    ),
                    "epic": dados_epic,
                }

            raise HTTPException(status_code=404, detail="Jogo não encontrado no catálogo.")

        nome_jogo = (jogo.nome or identificador).strip()

        if jogo.steam_id:
            preco_steam = await steam_coletor.coletar_jogo(jogo.steam_id)
        else:
            preco_steam = _erro_plataforma(
                "Steam",
                "Este jogo não possui AppID da Steam cadastrado.",
            )

        # A URL cadastrada é preferível, pois epic_id pode não ser um slug.
        epic_url = (jogo.url_epic or "").strip()
        epic_id = (jogo.epic_id or "").strip()

        if epic_url.startswith("http"):
            preco_epic = await epic_coletor.coletar_jogo(epic_url)
        elif epic_id and epic_id.upper() != "EXCLUSIVO_STEAM":
            preco_epic = await epic_coletor.coletar_jogo(epic_id)
        elif jogo.steam_id:
            # Usa o mapeamento legado apenas quando não há vínculo no banco.
            preco_epic = await epic_coletor.coletar_jogo_por_steam_id(jogo.steam_id)
        else:
            preco_epic = _erro_plataforma(
                "Epic Games",
                "Este jogo não possui vínculo confirmado com a Epic Games Store.",
            )

        if _epic_retornou_verificacao(preco_epic):
            preco_epic = _erro_plataforma(
                "Epic Games",
                "A loja retornou uma verificação de segurança; preço não confirmado.",
            )

        return {
            "jogo": nome_jogo,
            "jogo_id": jogo.id,
            "steam": preco_steam,
            "epic": preco_epic,
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("Falha ao comparar preços para o identificador %s.", identificador)
        raise HTTPException(
            status_code=500,
            detail="Não foi possível comparar os preços no momento.",
        )
