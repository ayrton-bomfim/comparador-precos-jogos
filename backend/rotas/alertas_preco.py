"""CRUD autenticado das configurações de alerta de preço."""
from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from ..banco_dados import get_db
from ..modelos import AlertaPreco, Favorito, Jogo
from ..seguranca.autenticacao import obter_usuario_atual
router = APIRouter(prefix="/api/alertas-preco", tags=["alertas de preço"])
class AlertaPrecoEntrada(BaseModel):
    ativo: bool = True
    lojas: list[Literal["steam", "epic"]] = Field(..., min_items=1, max_items=2)
    condicao: Literal["promocao", "preco_alvo"] = "preco_alvo"
    preco_alvo: Decimal | None = Field(default=None, ge=0, le=10000, max_digits=10, decimal_places=2)
    @validator("lojas")
    def lojas_sem_duplicidade(cls, valor):
        if not valor or len(set(valor)) != len(valor): raise ValueError("Selecione uma ou duas lojas, sem duplicidades.")
        return valor
    @validator("preco_alvo", always=True)
    def preco_obrigatorio_para_alvo(cls, valor, values):
        if values.get("condicao") == "preco_alvo" and valor is None: raise ValueError("Informe o preço desejado.")
        return None if values.get("condicao") == "promocao" else valor
def serializar(a):
    return {"id":a.id,"jogo_id":a.jogo_id,"ativo":a.ativo,"lojas":a.lojas or [],"condicao":a.condicao,"preco_alvo":float(a.preco_alvo) if a.preco_alvo is not None else None,"criado_em":a.criado_em.isoformat() if a.criado_em else None,"atualizado_em":a.atualizado_em.isoformat() if a.atualizado_em else None}
@router.get("")
def listar_alertas(db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    itens=db.query(AlertaPreco).filter(AlertaPreco.usuario_id==usuario.id).all()
    return {"alertas":[serializar(a) for a in itens]}


class PreferenciasNotificacaoEntrada(BaseModel):
    email: bool = False
    site: bool = False


@router.get("/preferencias")
def obter_preferencias_notificacao(db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    return {
        "email": bool(usuario.notificacao_email),
        "site": bool(usuario.notificacao_site),
        "configuradas": bool(usuario.notificacao_preferencias_configuradas),
        "email_verificado": bool(usuario.email_verificado),
    }


@router.put("/preferencias")
def salvar_preferencias_notificacao(entrada: PreferenciasNotificacaoEntrada, db: Session = Depends(get_db), usuario=Depends(obter_usuario_atual)):
    # O backend é a fonte de verdade: nunca habilita e-mail para endereço não verificado.
    usuario.notificacao_email = bool(entrada.email and usuario.email_verificado)
    usuario.notificacao_site = bool(entrada.site)
    usuario.notificacao_preferencias_configuradas = True
    db.commit()
    db.refresh(usuario)
    return {
        "ok": True,
        "email": bool(usuario.notificacao_email),
        "site": bool(usuario.notificacao_site),
        "configuradas": True,
        "email_verificado": bool(usuario.email_verificado),
    }


@router.put("/{jogo_id}")
def salvar_alerta(jogo_id:int, entrada:AlertaPrecoEntrada, db:Session=Depends(get_db), usuario=Depends(obter_usuario_atual)):
    jogo=db.query(Jogo).filter(Jogo.id==jogo_id).first()
    if not jogo: raise HTTPException(status_code=404,detail="Jogo não encontrado.")
    favorito=db.query(Favorito).filter(Favorito.usuario_id==usuario.id,Favorito.jogo_id==jogo_id).first()
    if not favorito: raise HTTPException(status_code=400,detail="Adicione o jogo aos favoritos antes de configurar um alerta.")
    if "steam" in entrada.lojas and not jogo.steam_id: raise HTTPException(status_code=400,detail="Este jogo não possui oferta identificada na Steam.")
    if "epic" in entrada.lojas and (not jogo.epic_id or jogo.epic_id=="EXCLUSIVO_STEAM"): raise HTTPException(status_code=400,detail="Este jogo não possui oferta identificada na Epic Games Store.")
    a=db.query(AlertaPreco).filter(AlertaPreco.usuario_id==usuario.id,AlertaPreco.jogo_id==jogo_id).first()
    if a is None: a=AlertaPreco(usuario_id=usuario.id,jogo_id=jogo_id); db.add(a)
    a.ativo=entrada.ativo; a.lojas=list(entrada.lojas); a.condicao=entrada.condicao; a.preco_alvo=entrada.preco_alvo
    # Alterar a configuração reabilita a avaliação da condição.
    a.ultima_condicao_ativa = False
    db.commit(); db.refresh(a)
    return {"ok":True,"alerta":serializar(a)}
@router.delete("/{jogo_id}")
def excluir_alerta(jogo_id:int, db:Session=Depends(get_db), usuario=Depends(obter_usuario_atual)):
    a=db.query(AlertaPreco).filter(AlertaPreco.usuario_id==usuario.id,AlertaPreco.jogo_id==jogo_id).first()
    if a is None:return {"ok":True,"removido":False}
    db.delete(a);db.commit();return {"ok":True,"removido":True}
