"""Alteração de e-mail e senha com tokens temporários enviados por e-mail."""
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import re
import secrets
from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..banco_dados import get_db
from ..config import settings
from ..modelos import Usuario, TokenSegurancaUsuario
from ..seguranca.autenticacao import obter_usuario_atual, hash_password, verify_password
from ..servicos.email_service import enviar_email, EmailServiceError
from ..servicos.email_templates_seguranca import renderizar_email_seguranca
from ..seguranca.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["seguranca-da-conta"])
TOKEN_TTL_MINUTOS = 30
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

class SolicitarEmail(BaseModel):
    novo_email: str = Field(min_length=3, max_length=255)
    senha_atual: str = Field(min_length=1, max_length=128)

class ConfirmarToken(BaseModel):
    token: str = Field(min_length=20, max_length=200)

class AlterarSenha(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=128)
    nova_senha: str = Field(min_length=8, max_length=128)
    confirmar_senha: str = Field(min_length=8, max_length=128)

class SolicitarRecuperacao(BaseModel):
    email: str = Field(min_length=3, max_length=255)

class RedefinirSenha(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    nova_senha: str = Field(min_length=8, max_length=128)
    confirmar_senha: str = Field(min_length=8, max_length=128)

def _agora():
    return datetime.now(timezone.utc)

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def _criar_token(db: Session, usuario: Usuario, finalidade: str, email_pendente: str | None = None) -> str:
    # Invalida tokens anteriores da mesma finalidade para esta conta.
    db.query(TokenSegurancaUsuario).filter(
        TokenSegurancaUsuario.usuario_id == usuario.id,
        TokenSegurancaUsuario.finalidade == finalidade,
        TokenSegurancaUsuario.usado_em.is_(None),
    ).update({TokenSegurancaUsuario.usado_em: _agora()}, synchronize_session=False)
    bruto = secrets.token_urlsafe(36)
    db.add(TokenSegurancaUsuario(
        usuario_id=usuario.id, finalidade=finalidade, email_pendente=email_pendente,
        token_hash=_hash_token(bruto), expira_em=_agora() + timedelta(minutes=TOKEN_TTL_MINUTOS),
    ))
    db.flush()
    return bruto

def _url_frontend(caminho: str, token: str) -> str:
    base = settings.FRONTEND_URL
    return f"{base}{caminho}?{urlencode({'token': token})}"

def _enviar_link(destinatario: str, assunto: str, titulo: str, explicacao: str, url: str):
    """Envia link usando a identidade visual aprovada no alerta de preço."""
    titulo_normalizado = titulo.strip().lower()
    if "novo e-mail" in titulo_normalizado:
        preheader = "Confirme o novo endereço de e-mail da sua conta DESCTRL."
        chamada = "Confirmação de segurança"
        texto_botao = "Confirmar novo e-mail"
    elif "confirme seu e-mail" in titulo_normalizado:
        preheader = "Confirme seu endereço de e-mail para concluir a configuração da conta DESCTRL."
        chamada = "Confirmação de e-mail"
        texto_botao = "Confirmar meu e-mail"
    else:
        preheader = "Use o link seguro para redefinir a senha da sua conta DESCTRL."
        chamada = "Proteção da sua conta"
        texto_botao = "Redefinir minha senha"

    html = renderizar_email_seguranca(
        preheader=preheader,
        titulo=titulo,
        chamada=chamada,
        explicacao=explicacao,
        texto_botao=texto_botao,
        url=url,
        validade_minutos=TOKEN_TTL_MINUTOS,
    )
    enviar_email(destinatario, assunto, html)

def _token_valido(db: Session, bruto: str, finalidade: str):
    registro = db.query(TokenSegurancaUsuario).filter(
        TokenSegurancaUsuario.token_hash == _hash_token(bruto),
        TokenSegurancaUsuario.finalidade == finalidade,
        TokenSegurancaUsuario.usado_em.is_(None),
        TokenSegurancaUsuario.expira_em > _agora(),
    ).first()
    if not registro:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado. Solicite um novo link.")
    return registro

@router.post("/email/confirmacao/reenviar")
@limiter.limit("3/hour")
def reenviar_confirmacao_email(
    request: Request,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Reenvia a confirmação do endereço atual para uma conta não verificada."""
    if usuario.email_verificado:
        return {"mensagem": "Seu endereço de e-mail já está confirmado.", "email_verificado": True}
    if not usuario.email or not EMAIL_RE.match(usuario.email):
        raise HTTPException(status_code=400, detail="Sua conta não possui um endereço de e-mail válido.")

    token = _criar_token(db, usuario, "confirmar_email")
    url = _url_frontend("/confirmar-email", token)
    try:
        _enviar_link(
            usuario.email,
            "Confirme seu e-mail no DESCTRL",
            "Confirme seu e-mail",
            "Confirme o endereço de e-mail associado à sua conta DESCTRL. Esse passo libera recursos que dependem de um endereço confirmado.",
            url,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Falha ao reenviar confirmação de e-mail via Resend.")
        raise HTTPException(
            status_code=502,
            detail="Não foi possível enviar o e-mail de confirmação. Tente novamente mais tarde.",
        ) from exc

    return {"mensagem": "Enviamos um novo link de confirmação para o seu e-mail.", "email_verificado": False}


@router.post("/email/solicitar-alteracao")
@limiter.limit("3/hour")
def solicitar_alteracao_email(request: Request, payload: SolicitarEmail, usuario: Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    novo_email = payload.novo_email.strip().lower()
    if not EMAIL_RE.match(novo_email):
        raise HTTPException(status_code=422, detail="Informe um endereço de e-mail válido.")
    if not usuario.senha_hash or not verify_password(payload.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    if usuario.email and usuario.email.lower() == novo_email:
        raise HTTPException(status_code=400, detail="O novo e-mail é igual ao atual.")
    existente = db.query(Usuario).filter(Usuario.email == novo_email, Usuario.id != usuario.id).first()
    if existente:
        raise HTTPException(status_code=409, detail="Este e-mail já está associado a outra conta.")
    token = _criar_token(db, usuario, "alterar_email", novo_email)
    url = _url_frontend("/confirmar-email", token)
    try:
        _enviar_link(novo_email, "Confirme seu novo e-mail no DESCTRL", "Confirme seu novo e-mail", "Recebemos uma solicitação para alterar o e-mail da sua conta DESCTRL. O endereço atual continuará ativo até a confirmação.", url)
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Falha ao enviar confirmação de alteração de e-mail via Resend.")
        raise HTTPException(status_code=502, detail="Não foi possível enviar o e-mail de confirmação. Tente novamente mais tarde.") from exc
    return {"mensagem": "Enviamos um link de confirmação para o novo endereço."}

@router.post("/email/confirmar")
@limiter.limit("10/minute")
def confirmar_email(request: Request, payload: ConfirmarToken, db: Session = Depends(get_db)):
    # O mesmo componente frontend atende à confirmação inicial e à alteração de endereço.
    registro = db.query(TokenSegurancaUsuario).filter(
        TokenSegurancaUsuario.token_hash == _hash_token(payload.token),
        TokenSegurancaUsuario.finalidade.in_(("alterar_email", "confirmar_email")),
        TokenSegurancaUsuario.usado_em.is_(None),
        TokenSegurancaUsuario.expira_em > _agora(),
    ).first()
    if not registro:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado. Solicite um novo link.")

    usuario = db.query(Usuario).filter(Usuario.id == registro.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="Conta não encontrada.")

    if registro.finalidade == "confirmar_email":
        usuario.email_verificado = True
        registro.usado_em = _agora()
        db.commit()
        return {
            "mensagem": "E-mail confirmado com sucesso. Agora você pode receber alertas por e-mail.",
            "email": usuario.email,
            "email_verificado": True,
            "tipo_confirmacao": "email_atual",
        }

    if not registro.email_pendente or not EMAIL_RE.match(registro.email_pendente):
        raise HTTPException(status_code=400, detail="Solicitação de alteração inválida.")
    existente = db.query(Usuario).filter(
        Usuario.email == registro.email_pendente,
        Usuario.id != registro.usuario_id,
    ).first()
    if existente:
        raise HTTPException(status_code=409, detail="Este e-mail já está associado a outra conta.")

    usuario.email = registro.email_pendente
    usuario.email_verificado = True
    registro.usado_em = _agora()
    db.commit()
    return {
        "mensagem": "E-mail alterado e confirmado com sucesso.",
        "email": usuario.email,
        "email_verificado": True,
        "tipo_confirmacao": "alteracao_email",
    }

@router.post("/senha/alterar")
def alterar_senha(payload: AlterarSenha, usuario: Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    if not verify_password(payload.senha_atual, usuario.senha_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    if payload.nova_senha != payload.confirmar_senha:
        raise HTTPException(status_code=422, detail="A confirmação da nova senha não corresponde.")
    if payload.nova_senha == payload.senha_atual:
        raise HTTPException(status_code=400, detail="A nova senha deve ser diferente da atual.")
    usuario.senha_hash = hash_password(payload.nova_senha)
    usuario.versao_sessao = (usuario.versao_sessao or 0) + 1
    db.commit()
    return {"mensagem": "Senha alterada com sucesso."}

@router.post("/senha/recuperar")
@limiter.limit("3/hour")
def solicitar_recuperacao_senha(request: Request, payload: SolicitarRecuperacao, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    resposta = {"mensagem": "Se houver uma conta com esse e-mail, enviaremos instruções para redefinir a senha."}
    usuario = db.query(Usuario).filter(Usuario.email == email, Usuario.ativo.is_(True)).first()
    if not usuario:
        return resposta
    token = _criar_token(db, usuario, "recuperar_senha")
    url = _url_frontend("/redefinir-senha", token)
    try:
        _enviar_link(email, "Redefina sua senha do DESCTRL", "Redefinição de senha", "Recebemos uma solicitação para redefinir a senha da sua conta DESCTRL.", url)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Falha ao enviar e-mail de recuperação de senha via Resend.")
        # Não revelar se a conta existe nem detalhes do provedor de e-mail.
    return resposta

@router.post("/senha/redefinir")
@limiter.limit("10/minute")
def redefinir_senha(request: Request, payload: RedefinirSenha, db: Session = Depends(get_db)):
    if payload.nova_senha != payload.confirmar_senha:
        raise HTTPException(status_code=422, detail="A confirmação da nova senha não corresponde.")
    registro = _token_valido(db, payload.token, "recuperar_senha")
    usuario = db.query(Usuario).filter(Usuario.id == registro.usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="Conta não encontrada.")
    usuario.senha_hash = hash_password(payload.nova_senha)
    usuario.versao_sessao = (usuario.versao_sessao or 0) + 1
    registro.usado_em = _agora()
    # Invalidar demais tokens de recuperação pendentes da conta.
    db.query(TokenSegurancaUsuario).filter(
        TokenSegurancaUsuario.usuario_id == usuario.id,
        TokenSegurancaUsuario.finalidade == "recuperar_senha",
        TokenSegurancaUsuario.id != registro.id,
        TokenSegurancaUsuario.usado_em.is_(None),
    ).update({TokenSegurancaUsuario.usado_em: _agora()}, synchronize_session=False)
    db.commit()
    return {"mensagem": "Senha redefinida com sucesso. Você já pode entrar com a nova senha."}
