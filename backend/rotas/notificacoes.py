"""API autenticada para histórico permanente de notificações."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..banco_dados import get_db
from ..modelos import NotificacaoUsuario
from ..seguranca.autenticacao import obter_usuario_atual

router = APIRouter(prefix="/api/notificacoes", tags=["notificações"])

def serializar(n):
    return {"id": n.id, "tipo": n.tipo, "titulo": n.titulo, "mensagem": n.mensagem,
            "link": n.link, "jogo_id": n.jogo_id, "dados": n.dados or {}, "lida": bool(n.lida),
            "criada_em": n.criada_em.isoformat() if n.criada_em else None}

@router.get("")
def listar_notificacoes(tipo: str = Query(default="todas", pattern="^(todas|preco|conquista|recomendacao)$"),
                       apenas_nao_lidas: bool = False, limite: int = Query(default=100, ge=1, le=200),
                       db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    consulta = db.query(NotificacaoUsuario).filter(NotificacaoUsuario.usuario_id == usuario.id)
    if tipo != "todas": consulta = consulta.filter(NotificacaoUsuario.tipo == tipo)
    if apenas_nao_lidas: consulta = consulta.filter(NotificacaoUsuario.lida.is_(False))
    itens = consulta.order_by(NotificacaoUsuario.criada_em.desc(), NotificacaoUsuario.id.desc()).limit(limite).all()
    nao_lidas = db.query(NotificacaoUsuario).filter(NotificacaoUsuario.usuario_id == usuario.id, NotificacaoUsuario.lida.is_(False)).count()
    return {"notificacoes": [serializar(n) for n in itens], "nao_lidas": nao_lidas}

@router.patch("/{notificacao_id}/ler")
def marcar_lida(notificacao_id: int, db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    item = db.query(NotificacaoUsuario).filter(NotificacaoUsuario.id == notificacao_id, NotificacaoUsuario.usuario_id == usuario.id).first()
    if item is None: raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    item.lida = True; db.commit()
    return {"ok": True, "id": item.id, "lida": True}

@router.patch("/ler-todas")
def marcar_todas_lidas(db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    quantidade = db.query(NotificacaoUsuario).filter(NotificacaoUsuario.usuario_id == usuario.id, NotificacaoUsuario.lida.is_(False)).update({NotificacaoUsuario.lida: True}, synchronize_session=False)
    db.commit()
    return {"ok": True, "atualizadas": quantidade}
