"""Recebimento público de denúncias de jogos e sugestões da comunidade."""
from typing import Optional, Annotated
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from ..banco_dados import get_db
from ..modelos import (
    Jogo, Usuario, AuditoriaConteudo, AuditoriaConteudoHistorico,
    SugestaoUsuario, now_brasilia,
)
from ..seguranca.autenticacao import obter_admin_atual
from ..seguranca.rate_limit import limiter

router = APIRouter(prefix="/api/comunidade", tags=["comunidade"])
admin_router = APIRouter(prefix="/api/admin/feedback", tags=["feedback-admin"])
AdminDep = Annotated[Usuario, Depends(obter_admin_atual)]

MOTIVOS = {
    "Conteúdo sensível", "Fora do catálogo", "Duplicado ou redundante",
    "Indisponível ou removido", "Problemas de qualidade ou integridade", "Outros",
    "Preço ou informações incorretas", "Jogo duplicado ou edição incorreta",
    "Jogo indisponível ou removido da loja", "Outro problema",
}


class DenunciaEntrada(BaseModel):
    jogo_id: int
    motivo: str = Field(min_length=2, max_length=255)
    observacao: Optional[str] = Field(default=None, max_length=2000)


class SugestaoEntrada(BaseModel):
    tipo: str = Field(default="melhoria", max_length=40)
    pagina_origem: str = Field(min_length=1, max_length=500)
    descricao: str = Field(min_length=5, max_length=5000)


@router.post("/denuncias-jogos")
@limiter.limit("5/hour")
def denunciar_jogo(
    request: Request,
    dados: DenunciaEntrada,
    db: Session = Depends(get_db),
):
    """Registra uma denúncia para revisão; não exclui o jogo automaticamente."""
    motivo = dados.motivo.strip()
    if motivo not in MOTIVOS:
        raise HTTPException(status_code=422, detail="Selecione um motivo válido para a denúncia.")

    jogo = db.query(Jogo).filter(Jogo.id == dados.jogo_id).with_for_update().first()
    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado ou já retirado do catálogo.")
    if jogo.status_auditoria == "excluido":
        raise HTTPException(status_code=409, detail="Este jogo já está fora do catálogo.")

    observacao_denuncia = (dados.observacao or "").strip() or "Denúncia enviada pela comunidade."
    auditoria = (
        db.query(AuditoriaConteudo)
        .filter(AuditoriaConteudo.jogo_id == jogo.id)
        .with_for_update()
        .first()
    )

    if auditoria is not None and auditoria.status == "pendente":
        raise HTTPException(
            status_code=409,
            detail="Este jogo já está aguardando análise. A denúncia não alterou a auditoria existente.",
        )

    status_anterior = auditoria.status if auditoria else None
    if auditoria is None:
        auditoria = AuditoriaConteudo(
            jogo_id=jogo.id,
            nome_jogo=jogo.nome,
            status="pendente",
            origem="denuncia",
            motivo=motivo,
            observacao=observacao_denuncia,
            criado_por=None,
            decidido_por=None,
            decidido_em=None,
        )
        db.add(auditoria)
        db.flush()
    else:
        # Uma denúncia pode reabrir uma decisão anterior, mas nunca a substitui
        # por uma exclusão automática. O histórico mantém a decisão anterior.
        auditoria.nome_jogo = jogo.nome
        auditoria.status = "pendente"
        auditoria.origem = "denuncia"
        auditoria.motivo = motivo
        observacao_anterior = (auditoria.observacao or "").strip()
        auditoria.observacao = (
            f"{observacao_anterior}\n\nNova denúncia da comunidade: {observacao_denuncia}"
            if observacao_anterior
            else observacao_denuncia
        )
        auditoria.decidido_por = None
        auditoria.decidido_em = None

    jogo.status_auditoria = "pendente"
    db.add(AuditoriaConteudoHistorico(
        auditoria_id=auditoria.id,
        jogo_id=jogo.id,
        nome_jogo=jogo.nome,
        status_anterior=status_anterior,
        status_novo="pendente",
        motivo=motivo,
        observacao=observacao_denuncia,
        usuario_id=None,
    ))
    db.commit()
    return {
        "mensagem": "Denúncia registrada e encaminhada para análise. O jogo não foi excluído automaticamente.",
        "jogo_id": jogo.id,
    }


@router.post("/sugestoes")
@limiter.limit("5/hour")
def enviar_sugestao(
    request: Request,
    dados: SugestaoEntrada,
    db: Session = Depends(get_db),
):
    tipo = dados.tipo.strip().lower()
    if tipo not in {"melhoria", "funcionalidade", "interface", "outro"}:
        tipo = "outro"
    pagina = dados.pagina_origem.strip()
    descricao = dados.descricao.strip()
    if not pagina or len(descricao) < 5:
        raise HTTPException(status_code=422, detail="Informe a página de origem e uma sugestão com pelo menos 5 caracteres.")
    sugestao = SugestaoUsuario(tipo=tipo, pagina_origem=pagina, descricao=descricao)
    db.add(sugestao)
    db.commit()
    return {"mensagem": "Sugestão enviada. Obrigado por ajudar a melhorar o DESCTRL!", "id": sugestao.id}


class AtualizarFeedbackEntrada(BaseModel):
    concluido: bool


@admin_router.get("")
def listar_feedbacks(
    admin: AdminDep,
    status_filtro: str = Query(default="pendente", alias="status", pattern="^(pendente|concluido|todos)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    consulta = db.query(SugestaoUsuario).options(joinedload(SugestaoUsuario.usuario))
    if status_filtro != "todos":
        consulta = consulta.filter(SugestaoUsuario.status == status_filtro)
    total = consulta.count()
    itens = (consulta.order_by(SugestaoUsuario.criada_em.desc(), SugestaoUsuario.id.desc())
             .offset((page - 1) * page_size).limit(page_size).all())
    return {
        "items": [{
            "id": item.id,
            "tipo": item.tipo,
            "pagina_origem": item.pagina_origem,
            "descricao": item.descricao,
            "status": item.status,
            "criada_em": item.criada_em.isoformat() if item.criada_em else None,
            "concluida_em": item.concluida_em.isoformat() if item.concluida_em else None,
            "usuario_nome": item.usuario.username if item.usuario else None,
        } for item in itens],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@admin_router.patch("/{sugestao_id}/concluir")
def atualizar_feedback(
    sugestao_id: int,
    dados: AtualizarFeedbackEntrada,
    admin: AdminDep,
    db: Session = Depends(get_db),
):
    sugestao = db.query(SugestaoUsuario).filter(SugestaoUsuario.id == sugestao_id).with_for_update().first()
    if sugestao is None:
        raise HTTPException(status_code=404, detail="Feedback não encontrado.")
    sugestao.status = "concluido" if dados.concluido else "pendente"
    sugestao.concluida_em = now_brasilia() if dados.concluido else None
    db.add(sugestao)
    db.commit()
    return {"mensagem": "Feedback atualizado.", "id": sugestao.id, "status": sugestao.status}
