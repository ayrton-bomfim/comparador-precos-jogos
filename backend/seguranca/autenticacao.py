"""Autenticação e autorização da API.

A autenticação usa usuário/senha para emitir um JWT Bearer.
As senhas nunca são armazenadas em texto puro: são derivadas com
scrypt usando salt aleatório.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..banco_dados import get_db
from ..modelos import Usuario


ALGORITHM = "HS256"
SESSION_IDLE_TIMEOUT_HOURS = 6
ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "360")
)
if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES deve ser maior que zero.")


def _obter_secret_key() -> str:
    secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if not secret:
        raise RuntimeError(
            "JWT_SECRET_KEY não configurada. Defina uma chave forte no ambiente."
        )
    if len(secret.encode("utf-8")) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY deve ter pelo menos 32 bytes. Gere uma chave aleatória forte."
        )
    return secret


# OAuth2PasswordBearer faz o FastAPI esperar o header Authorization: Bearer <token>.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


CUSTO_SCRYPT_N = 2**14
CUSTO_SCRYPT_R = 8
CUSTO_SCRYPT_P = 1
TAMANHO_SALT = 16
TAMANHO_DERIVADO = 64


def hash_password(password: str) -> str:
    """Gera um hash scrypt com salt aleatório."""
    if not password:
        raise ValueError("A senha não pode ser vazia.")

    salt = os.urandom(TAMANHO_SALT)
    derivado = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=CUSTO_SCRYPT_N,
        r=CUSTO_SCRYPT_R,
        p=CUSTO_SCRYPT_P,
        dklen=TAMANHO_DERIVADO,
    )

    return (
        f"scrypt${CUSTO_SCRYPT_N}${CUSTO_SCRYPT_R}${CUSTO_SCRYPT_P}$"
        f"{base64.urlsafe_b64encode(salt).decode()}$"
        f"{base64.urlsafe_b64encode(derivado).decode()}"
    )


def verify_password(password: str, password_hash: str) -> bool:
    """Confere uma senha contra um hash scrypt armazenado."""
    try:
        algoritmo, n, r, p, salt_b64, hash_b64 = password_hash.split("$", 5)
        if algoritmo != "scrypt":
            return False

        salt = base64.urlsafe_b64decode(salt_b64.encode())
        esperado = base64.urlsafe_b64decode(hash_b64.encode())
        recebido = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(esperado),
        )
        return hmac.compare_digest(recebido, esperado)
    except (ValueError, TypeError):
        return False


def criar_access_token(usuario: Usuario) -> str:
    """Cria um JWT com identificação e papel do usuário."""
    agora = datetime.now(timezone.utc)
    expiracao = agora + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(usuario.id),
        "username": usuario.username,
        "role": usuario.role,
        "sv": int(getattr(usuario, "versao_sessao", 0) or 0),
        "iat": agora,
        "exp": expiracao,
    }

    return jwt.encode(payload, _obter_secret_key(), algorithm=ALGORITHM)


def autenticar_usuario(
    db: Session,
    username: str,
    password: str,
) -> Usuario | None:
    """Retorna o usuário autenticado ou None."""
    username_normalizado = username.strip().lower()
    usuario = (
        db.query(Usuario)
        .filter(func.lower(Usuario.username) == username_normalizado)
        .first()
    )

    if not usuario or not usuario.ativo:
        return None

    if not verify_password(password, usuario.senha_hash):
        return None

    return usuario


async def obter_usuario_atual(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Session = Depends(get_db),
) -> Usuario:
    """Valida o JWT e carrega o usuário atual do banco."""
    erro = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não autenticado.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            _obter_secret_key(),
            algorithms=[ALGORITHM],
        )
        usuario_id = payload.get("sub")
        versao_token = payload.get("sv")
        # Tokens emitidos antes deste mecanismo não possuem "sv" e devem ser renovados.
        if not usuario_id or type(versao_token) is not int or versao_token < 0:
            raise erro
        usuario_id = int(usuario_id)
    except (jwt.InvalidTokenError, ValueError, RuntimeError):
        raise erro

    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()

    if not usuario or not usuario.ativo:
        raise erro

    if versao_token != int(getattr(usuario, "versao_sessao", 0) or 0):
        raise erro

    # O banco usa DateTime sem fuso; armazenamos UTC sem tzinfo para manter
    # comparações consistentes com a coluna ultima_atividade_sessao.
    agora = datetime.now(timezone.utc).replace(tzinfo=None)
    ultima_atividade = usuario.ultima_atividade_sessao

    # Inicializa sessões antigas/recém-autenticadas que ainda não têm atividade.
    # A rota de renovação atualizará este horário apenas quando for chamada
    # pelo fluxo explícito de atividade do frontend.
    if ultima_atividade is None:
        usuario.ultima_atividade_sessao = agora
        db.commit()
    else:
        if ultima_atividade.tzinfo is not None:
            ultima_atividade = ultima_atividade.astimezone(timezone.utc).replace(tzinfo=None)

        if agora - ultima_atividade >= timedelta(hours=SESSION_IDLE_TIMEOUT_HOURS):
            raise erro

    return usuario


async def obter_admin_atual(
    usuario: Annotated[Usuario, Depends(obter_usuario_atual)],
) -> Usuario:
    """Garante que o usuário autenticado possui papel de administrador."""
    if usuario.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores.",
        )

    return usuario
