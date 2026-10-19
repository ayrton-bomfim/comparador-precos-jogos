"""Favoritos persistentes por usuário autenticado, com histórico para conquistas."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..banco_dados import get_db
from ..modelos import Conquista, Favorito, HistoricoFavorito, Jogo, HistoricoPreco
from ..seguranca.autenticacao import obter_usuario_atual
from .conquistas import garantir_catalogo, desbloquear

router = APIRouter(prefix="/api/favoritos", tags=["favoritos"])


def _precos_atuais(db: Session, jogo_ids: list[int]) -> dict:
    if not jogo_ids:
        return {}
    sub = (
        db.query(
            HistoricoPreco.jogo_id.label("jogo_id"),
            HistoricoPreco.plataforma.label("plataforma"),
            func.max(HistoricoPreco.data_coleta).label("ultima"),
        )
        .filter(HistoricoPreco.jogo_id.in_(jogo_ids))
        .group_by(HistoricoPreco.jogo_id, HistoricoPreco.plataforma)
        .subquery()
    )
    rows = (
        db.query(HistoricoPreco)
        .join(
            sub,
            (HistoricoPreco.jogo_id == sub.c.jogo_id)
            & (HistoricoPreco.plataforma == sub.c.plataforma)
            & (HistoricoPreco.data_coleta == sub.c.ultima),
        )
        .all()
    )
    saida = {}
    for r in rows:
        plataforma = (r.plataforma or "").lower()
        if plataforma == "steam":
            chave = "steam"
        elif plataforma in ("epic", "epic games", "epic games store"):
            chave = "epic"
        else:
            continue
        saida.setdefault(r.jogo_id, {})[chave] = {
            "preco": float(r.preco_atual) if r.preco_atual is not None else None,
            "desconto": int(r.desconto or 0),
        }
    return saida


def _menores_precos_historicos(db: Session, jogo_ids: list[int], precos_atuais: dict) -> dict:
    """Marca menor preço apenas quando há ao menos dois registros comparáveis por loja."""
    if not jogo_ids:
        return {}
    rows = (
        db.query(
            HistoricoPreco.jogo_id,
            HistoricoPreco.plataforma,
            func.min(HistoricoPreco.preco_atual).label("menor_preco"),
            func.count(HistoricoPreco.id).label("quantidade"),
        )
        .filter(HistoricoPreco.jogo_id.in_(jogo_ids), HistoricoPreco.preco_atual >= 0)
        .group_by(HistoricoPreco.jogo_id, HistoricoPreco.plataforma)
        .all()
    )
    resultado = {}
    for row in rows:
        plataforma = (row.plataforma or "").lower()
        chave = "steam" if plataforma == "steam" else (
            "epic" if plataforma in ("epic", "epic games", "epic games store") else None
        )
        if not chave or row.quantidade < 2:
            continue
        atual = precos_atuais.get(row.jogo_id, {}).get(chave, {}).get("preco")
        if atual is None:
            continue
        eh_menor = round(float(atual), 2) == round(float(row.menor_preco), 2)
        resultado.setdefault(row.jogo_id, {})[chave] = eh_menor
    return resultado


def _atualizar_conquistas_colecao(db: Session, usuario_id: int) -> None:
    """Atualiza progresso com base nos jogos distintos já favoritados historicamente."""
    total = (
        db.query(func.count(HistoricoFavorito.id))
        .filter(HistoricoFavorito.usuario_id == usuario_id)
        .scalar()
        or 0
    )
    metas = (
        ("primeiro_da_colecao", 1),
        ("colecao_em_formacao", 5),
        ("cofre_de_jogos", 20),
    )
    for codigo, meta in metas:
        conquista = (
            db.query(Conquista)
            .filter_by(usuario_id=usuario_id, codigo=codigo)
            .with_for_update()
            .first()
        )
        if not conquista:
            continue
        conquista.progresso = min(total, meta)
        if total >= meta:
            desbloquear(db, usuario_id, codigo)


def _sincronizar_favoritos_atuais(db: Session, usuario_id: int) -> None:
    """Inclui favoritos atuais antigos no histórico, sem duplicar registros."""
    favoritos_atuais = (
        db.query(Favorito, Jogo)
        .join(Jogo, Jogo.id == Favorito.jogo_id)
        .filter(Favorito.usuario_id == usuario_id)
        .all()
    )
    existentes = {
        row[0]
        for row in db.query(HistoricoFavorito.jogo_id)
        .filter(HistoricoFavorito.usuario_id == usuario_id)
        .all()
    }
    for favorito, jogo in favoritos_atuais:
        if jogo.id not in existentes:
            db.add(
                HistoricoFavorito(
                    usuario_id=usuario_id,
                    jogo_id=jogo.id,
                    jogo_nome=jogo.nome,
                )
            )
            existentes.add(jogo.id)

    garantir_catalogo(db, usuario_id)
    _atualizar_conquistas_colecao(db, usuario_id)


def _serializar(db: Session, favoritos: list[Favorito]) -> list[dict]:
    ids = [f.jogo_id for f in favoritos]
    precos = _precos_atuais(db, ids)
    menores_historicos = _menores_precos_historicos(db, ids, precos)
    jogos = {j.id: j for j in db.query(Jogo).filter(Jogo.id.in_(ids)).all()} if ids else {}
    resultado = []
    for fav in favoritos:
        j = jogos.get(fav.jogo_id)
        if not j:
            continue
        p = precos.get(j.id, {})
        resultado.append({
            "id": j.id,
            "nome": j.nome,
            "desenvolvedor": j.desenvolvedor,
            "publicadora": j.publicadora,
            "genero": j.genero,
            "steam_id": j.steam_id,
            "epic_id": j.epic_id,
            "imagem": j.url_imagem_epic or j.url_imagem_steam or (
                f"https://cdn.akamai.steamstatic.com/steam/apps/{j.steam_id}/header.jpg"
                if j.steam_id else None
            ),
            "url_steam": j.url_steam,
            "url_epic": j.url_epic,
            "preco_steam": p.get("steam", {}).get(
                "preco", float(j.preco_base_steam) if j.preco_base_steam is not None else None
            ),
            "preco_epic": p.get("epic", {}).get(
                "preco", float(j.preco_base_epic) if j.preco_base_epic is not None else None
            ),
            "desconto_steam": p.get("steam", {}).get("desconto", 0),
            "desconto_epic": p.get("epic", {}).get("desconto", 0),
            "menor_preco_historico_steam": menores_historicos.get(j.id, {}).get("steam", False),
            "menor_preco_historico_epic": menores_historicos.get(j.id, {}).get("epic", False),
            "criado_em": fav.criado_em.isoformat() if fav.criado_em else None,
        })
    return resultado


@router.get("")
def listar_favoritos(db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    _sincronizar_favoritos_atuais(db, usuario.id)
    favoritos = (
        db.query(Favorito)
        .filter(Favorito.usuario_id == usuario.id)
        .order_by(Favorito.criado_em.desc())
        .all()
    )
    db.commit()
    return {"favoritos": _serializar(db, favoritos), "total": len(favoritos)}


@router.get("/ids")
def listar_ids_favoritos(db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    _sincronizar_favoritos_atuais(db, usuario.id)
    ids = [
        r[0]
        for r in db.query(Favorito.jogo_id)
        .filter(Favorito.usuario_id == usuario.id)
        .all()
    ]
    db.commit()
    return {"ids": ids}


@router.post("/{jogo_id}", status_code=status.HTTP_201_CREATED)
def adicionar_favorito(jogo_id: int, db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()
    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")

    garantir_catalogo(db, usuario.id)

    existente = (
        db.query(Favorito)
        .filter(Favorito.usuario_id == usuario.id, Favorito.jogo_id == jogo_id)
        .first()
    )
    if existente:
        # Garante também que um favorito pré-existente esteja no histórico.
        historico = (
            db.query(HistoricoFavorito)
            .filter_by(usuario_id=usuario.id, jogo_id=jogo_id)
            .first()
        )
        if not historico:
            db.add(HistoricoFavorito(usuario_id=usuario.id, jogo_id=jogo_id, jogo_nome=jogo.nome))
        _atualizar_conquistas_colecao(db, usuario.id)
        db.commit()
        return {"ok": True, "favorito": True, "mensagem": "Jogo já estava nos favoritos."}

    db.add(Favorito(
        usuario_id=usuario.id,
        jogo_id=jogo_id,
        usuario_nome=usuario.username,
        jogo_nome=jogo.nome,
    ))

    historico = (
        db.query(HistoricoFavorito)
        .filter_by(usuario_id=usuario.id, jogo_id=jogo_id)
        .first()
    )
    if not historico:
        db.add(HistoricoFavorito(
            usuario_id=usuario.id,
            jogo_id=jogo_id,
            jogo_nome=jogo.nome,
        ))

    _atualizar_conquistas_colecao(db, usuario.id)
    db.commit()
    return {"ok": True, "favorito": True}


@router.delete("/{jogo_id}")
def remover_favorito(jogo_id: int, db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    favorito = (
        db.query(Favorito)
        .filter(Favorito.usuario_id == usuario.id, Favorito.jogo_id == jogo_id)
        .first()
    )
    if favorito:
        db.delete(favorito)
        db.commit()
    return {"ok": True, "favorito": False}
