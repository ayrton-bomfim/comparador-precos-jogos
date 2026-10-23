"""Rotas de autenticação e identificação do usuário atual."""

from datetime import datetime, timedelta, timezone
from typing import Annotated
import os
import re
import secrets
import logging
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from sqlalchemy import func
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from ..banco_dados import get_db
from ..modelos import HistoricoNomeUsuario, Usuario
from ..seguranca.rate_limit import limiter
from ..servicos.email_service import EmailServiceError
from .seguranca_conta import _criar_token, _url_frontend, _enviar_link
from ..seguranca.autenticacao import (
    autenticar_usuario,
    criar_access_token,
    obter_usuario_atual,
    hash_password,
)


router = APIRouter(prefix="/api/auth", tags=["autenticacao"])

logger = logging.getLogger(__name__)


class TokenResposta(BaseModel):
    access_token: str
    token_type: str


class UsuarioResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None = None
    role: str
    ativo: bool
    email_verificado: bool = False
    google_vinculado: bool = False


class GoogleLoginRequisicao(BaseModel):
    credential: str


class CadastroRequisicao(BaseModel):
    username: str
    email: str
    senha: str
    confirmar_senha: str


class GoogleCadastroRequisicao(BaseModel):
    credential: str
    username: str
    senha: str
    confirmar_senha: str


class CadastroResposta(BaseModel):
    mensagem: str
    username: str



class DisponibilidadeUsernameResposta(BaseModel):
    disponivel: bool
    mensagem: str


class AlterarUsernameRequisicao(BaseModel):
    username: str


class AlterarUsernameResposta(BaseModel):
    mensagem: str
    username: str
    username_anterior: str
    reservado_ate: datetime


class NomeRecuperavelResposta(BaseModel):
    id: int
    username_anterior: str
    alterado_em: datetime
    reservado_ate: datetime

    model_config = ConfigDict(from_attributes=True)


class RecuperarUsernameRequisicao(BaseModel):
    historico_id: int


class RecuperarUsernameResposta(BaseModel):
    mensagem: str
    username: str
    username_substituido_reservado_ate: datetime


def _agora_brasilia() -> datetime:
    """Retorna a data/hora de Brasília sem timezone, conforme as colunas SQL."""
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)


def _agora_sessao_utc() -> datetime:
    """Retorna UTC sem timezone para a coluna ultima_atividade_sessao."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validar_username(username: str) -> str:
    username = username.strip()
    if len(username) < 3 or len(username) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O nome de usuário precisa ter entre 3 e 100 caracteres.",
        )
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Use apenas letras sem acento, números, ponto, hífen ou sublinhado no nome de usuário.",
        )
    return username


def _username_em_uso_ou_reservado(
    db: Session,
    username: str,
    agora: datetime,
    excluir_usuario_id: int | None = None,
    excluir_historico_id: int | None = None,
) -> bool:
    consulta_usuarios = db.query(Usuario).filter(
        func.lower(Usuario.username) == username.lower()
    )
    if excluir_usuario_id is not None:
        consulta_usuarios = consulta_usuarios.filter(Usuario.id != excluir_usuario_id)
    if consulta_usuarios.first():
        return True

    consulta_reservas = db.query(HistoricoNomeUsuario.id).filter(
        func.lower(HistoricoNomeUsuario.username_anterior) == username.lower(),
        HistoricoNomeUsuario.reservado_ate > agora,
        HistoricoNomeUsuario.recuperado_em.is_(None),
    )
    if excluir_historico_id is not None:
        consulta_reservas = consulta_reservas.filter(
            HistoricoNomeUsuario.id != excluir_historico_id
        )
    reserva_ativa = consulta_reservas.first()
    return reserva_ativa is not None


@router.get("/username-disponivel", response_model=DisponibilidadeUsernameResposta)
@limiter.limit("30/minute")
async def verificar_username_disponivel(
    request: Request,
    username: str,
    db: Session = Depends(get_db),
):
    """Verifica se o nome está livre e não possui reserva vigente."""
    username = username.strip()
    if len(username) < 3:
        return DisponibilidadeUsernameResposta(
            disponivel=False,
            mensagem="Quase lá! O nome precisa ter pelo menos 3 caracteres.",
        )
    if len(username) > 100:
        return DisponibilidadeUsernameResposta(
            disponivel=False,
            mensagem="Gostamos de nomes criativos, mas esse ficou comprido demais!",
        )
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return DisponibilidadeUsernameResposta(
            disponivel=False,
            mensagem="Opa! Use apenas letras sem acento, números, ponto, hífen ou sublinhado.",
        )

    agora = _agora_brasilia()
    if _username_em_uso_ou_reservado(db, username, agora):
        return DisponibilidadeUsernameResposta(
            disponivel=False,
            mensagem="Esse nome já está em uso ou reservado temporariamente.",
        )
    return DisponibilidadeUsernameResposta(
        disponivel=True,
        mensagem="Tudo certo! Esse nome pode ser seu.",
    )


@router.post("/cadastro", response_model=CadastroResposta, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def cadastrar_usuario(
    request: Request,
    dados: CadastroRequisicao,
    db: Session = Depends(get_db),
):
    """Cria uma conta comum. O papel nunca é recebido do cliente."""
    username = dados.username.strip()
    email = dados.email.strip().lower()

    if len(username) < 3 or len(username) > 100:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Quase lá! Confira se o nome tem entre 3 e 100 caracteres.",
        )

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Opa! Esse símbolo não é permitido por aqui.",
        )

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Esse e-mail parece estar incompleto. Dá uma conferida?",
        )

    if len(dados.senha) < 6 or len(dados.senha) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A senha precisa ter entre 6 e 128 caracteres.",
        )

    if dados.senha != dados.confirmar_senha:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="As senhas não estão iguais. Dá uma conferida!",
        )

    agora = _agora_brasilia()
    if _username_em_uso_ou_reservado(db, username, agora):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse nome já está em uso ou reservado temporariamente. Escolha outro.",
        )

    email_existente = db.query(Usuario).filter(
        func.lower(Usuario.email) == email
    ).first()
    if email_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse e-mail já tem uma conta por aqui. Tente entrar nela.",
        )

    usuario = Usuario(
        username=username,
        email=email,
        senha_hash=hash_password(dados.senha),
        role="user",
        ativo=True,
    )
    db.add(usuario)
    try:
        # O flush gera o ID necessário para associar o token à conta antes do commit.
        db.flush()
        token_confirmacao = _criar_token(db, usuario, "confirmar_email")
        url_confirmacao = _url_frontend("/confirmar-email", token_confirmacao)
        _enviar_link(
            email,
            "Confirme seu e-mail no DESCTRL",
            "Confirme seu e-mail",
            "Sua conta DESCTRL foi criada. Confirme este endereço para liberar os recursos que dependem de um e-mail verificado.",
            url_confirmacao,
        )
        db.commit()
        db.refresh(usuario)
    except EmailServiceError as exc:
        db.rollback()
        logger.exception("Falha ao enviar confirmação de e-mail durante o cadastro.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Não foi possível enviar o e-mail de confirmação agora. Sua conta não foi criada; tente novamente mais tarde.",
        ) from exc
    except Exception as exc:
        db.rollback()
        logger.exception("Falha ao criar conta ou preparar confirmação de e-mail.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível criar a conta. Confira se o nome de usuário ou e-mail já está cadastrado e tente novamente.",
        ) from exc

    return CadastroResposta(
        mensagem="Conta criada! Enviamos um link de confirmação para seu e-mail. Confira também a pasta de spam antes de entrar.",
        username=usuario.username,
    )


@router.put("/username", response_model=AlterarUsernameResposta)
async def alterar_username(
    dados: AlterarUsernameRequisicao,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Altera o nome e reserva o anterior por 14 dias corridos."""
    novo_username = _validar_username(dados.username)
    agora = _agora_brasilia()

    if novo_username.lower() == usuario.username.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esse já é o seu nome de usuário atual.",
        )

    if _username_em_uso_ou_reservado(db, novo_username, agora, excluir_usuario_id=usuario.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse nome já está em uso ou reservado temporariamente. Escolha outro.",
        )

    nome_anterior = usuario.username
    reservado_ate = agora + timedelta(days=14)
    historico = HistoricoNomeUsuario(
        usuario_id=usuario.id,
        username_anterior=nome_anterior,
        alterado_em=agora,
        reservado_ate=reservado_ate,
        recuperado_em=None,
    )
    usuario.username = novo_username
    db.add(historico)

    try:
        db.commit()
        db.refresh(usuario)
        db.refresh(historico)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível alterar o nome. Ele pode ter sido ocupado por outra conta; tente novamente.",
        )

    return AlterarUsernameResposta(
        mensagem="Nome alterado. O nome anterior ficará reservado para você por 14 dias corridos.",
        username=usuario.username,
        username_anterior=nome_anterior,
        reservado_ate=reservado_ate,
    )


@router.get("/username-recuperaveis", response_model=list[NomeRecuperavelResposta])
async def listar_usernames_recuperaveis(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Lista os nomes anteriores que esta conta ainda pode recuperar."""
    agora = _agora_brasilia()
    registros = (
        db.query(HistoricoNomeUsuario)
        .filter(
            HistoricoNomeUsuario.usuario_id == usuario.id,
            HistoricoNomeUsuario.reservado_ate > agora,
            HistoricoNomeUsuario.recuperado_em.is_(None),
        )
        .order_by(HistoricoNomeUsuario.alterado_em.desc())
        .all()
    )
    return registros


@router.post("/username/recuperar", response_model=RecuperarUsernameResposta)
async def recuperar_username(
    dados: RecuperarUsernameRequisicao,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Recupera um nome reservado e reserva o nome que está sendo substituído."""
    agora = _agora_brasilia()
    registro = (
        db.query(HistoricoNomeUsuario)
        .filter(
            HistoricoNomeUsuario.id == dados.historico_id,
            HistoricoNomeUsuario.usuario_id == usuario.id,
            HistoricoNomeUsuario.reservado_ate > agora,
            HistoricoNomeUsuario.recuperado_em.is_(None),
        )
        .with_for_update()
        .first()
    )

    if not registro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Esse nome não está mais reservado para sua conta ou o prazo de 14 dias terminou.",
        )

    nome_a_recuperar = registro.username_anterior
    if _username_em_uso_ou_reservado(
        db,
        nome_a_recuperar,
        agora,
        excluir_usuario_id=usuario.id,
        excluir_historico_id=registro.id,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível recuperar esse nome porque ele está em uso ou reservado por outra conta.",
        )

    nome_atual = usuario.username
    prazo_nome_atual = agora + timedelta(days=14)
    nova_reserva = HistoricoNomeUsuario(
        usuario_id=usuario.id,
        username_anterior=nome_atual,
        alterado_em=agora,
        reservado_ate=prazo_nome_atual,
        recuperado_em=None,
    )

    registro.recuperado_em = agora
    usuario.username = nome_a_recuperar
    db.add(nova_reserva)

    try:
        db.commit()
        db.refresh(usuario)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível recuperar o nome. Atualize a página e tente novamente.",
        )

    return RecuperarUsernameResposta(
        mensagem="Nome recuperado com sucesso. O nome que você usava antes ficará reservado por mais 14 dias.",
        username=usuario.username,
        username_substituido_reservado_ate=prazo_nome_atual,
    )


@router.post("/login", response_model=TokenResposta)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db),
):
    """Autentica usuário e retorna um token Bearer JWT."""
    usuario = autenticar_usuario(
        db,
        form_data.username,
        form_data.password,
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario.ultima_atividade_sessao = _agora_sessao_utc()
    db.commit()

    return TokenResposta(
        access_token=criar_access_token(usuario),
        token_type="bearer",
    )




def _username_google_disponivel(db: Session, base_username: str) -> str:
    """Gera um username compatível com as regras atuais sem reutilizar nomes reservados."""
    candidato = re.sub(r"[^A-Za-z0-9_.-]", "", base_username)[:80].strip("._-")
    if len(candidato) < 3:
        candidato = "jogador"
    agora = _agora_brasilia()
    if not _username_em_uso_ou_reservado(db, candidato, agora):
        return candidato
    for _ in range(1000):
        sufixo = secrets.token_hex(3)
        prefixo = candidato[: 100 - len(sufixo) - 1]
        tentativa = f"{prefixo}_{sufixo}"
        if not _username_em_uso_ou_reservado(db, tentativa, agora):
            return tentativa
    raise HTTPException(status_code=500, detail="Não foi possível gerar um nome de usuário. Tente novamente.")


@router.post("/google")
@limiter.limit("10/minute")
async def login_google(
    request: Request,
    dados: GoogleLoginRequisicao,
    db: Session = Depends(get_db),
):
    """
    Valida o ID token do Google.
    - Se a identidade já estiver vinculada, autentica.
    - Se for uma identidade nova, informa que o cadastro precisa ser concluído.
    Nenhuma conta nova é criada neste endpoint.
    """
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login com Google ainda não está configurado no servidor.",
        )

    try:
        info = google_id_token.verify_oauth2_token(
            dados.credential,
            google_requests.Request(),
            client_id,
        )
    except ValueError as erro:
        print(
            f"[GOOGLE AUTH DIAGNOSTICO] {type(erro).__name__}: {erro!s}",
            flush=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar sua autenticação com o Google.",
        )

    google_sub = info.get("sub")
    email = (info.get("email") or "").strip().lower()
    email_verificado = info.get("email_verified") is True
    if not google_sub or not email or not email_verificado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="O Google precisa confirmar seu endereço de e-mail.",
        )

    usuario = db.query(Usuario).filter(Usuario.google_sub == google_sub).first()
    if usuario:
        if not usuario.ativo:
            raise HTTPException(status_code=403, detail="Esta conta está desativada.")
        usuario.ultima_atividade_sessao = _agora_sessao_utc()
        db.commit()
        return TokenResposta(
            access_token=criar_access_token(usuario),
            token_type="bearer",
        ).model_dump()

    # Não vinculamos contas convencionais automaticamente só por coincidência de e-mail.
    usuario_existente = db.query(Usuario).filter(
        func.lower(Usuario.email) == email
    ).first()
    if usuario_existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conta com esse e-mail. Entre com sua conta atual e vincule o Google nas configurações do perfil.",
        )

    # O frontend solicitará username e senha e finalizará o cadastro em endpoint próprio.
    # O token Google não é salvo nem ecoado na resposta; o cliente já o possui e será
    # validado novamente ao concluir o cadastro.
    return {
        "cadastro_pendente": True,
        "email": email,
        "mensagem": "Escolha seu nome de usuário e crie uma senha para concluir o cadastro.",
    }


@router.post("/google/cadastro", response_model=TokenResposta, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/hour")
async def cadastrar_com_google(
    request: Request,
    dados: GoogleCadastroRequisicao,
    db: Session = Depends(get_db),
):
    """Conclui o cadastro Google somente após validar username e senha definidos pelo usuário."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login com Google ainda não está configurado no servidor.",
        )

    try:
        info = google_id_token.verify_oauth2_token(
            dados.credential, google_requests.Request(), client_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A autenticação Google expirou ou não pôde ser validada. Clique no Google novamente.",
        )

    google_sub = info.get("sub")
    email = (info.get("email") or "").strip().lower()
    email_verificado = info.get("email_verified") is True
    if not google_sub or not email or not email_verificado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="O Google precisa confirmar seu endereço de e-mail.",
        )

    # Rejeita se a identidade ou o e-mail já tiverem sido usados desde a etapa inicial.
    usuario_google = db.query(Usuario).filter(Usuario.google_sub == google_sub).first()
    if usuario_google:
        if not usuario_google.ativo:
            raise HTTPException(status_code=403, detail="Esta conta está desativada.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Essa conta Google já possui cadastro. Volte à tela de login e entre com ela.",
        )

    usuario_email = db.query(Usuario).filter(func.lower(Usuario.email) == email).first()
    if usuario_email:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma conta com esse e-mail. Entre na conta existente e vincule o Google nas configurações.",
        )

    username = _validar_username(dados.username)
    if _username_em_uso_ou_reservado(db, username, _agora_brasilia()):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esse nome já está em uso ou reservado temporariamente. Escolha outro.",
        )

    if len(dados.senha) < 6 or len(dados.senha) > 128:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A senha precisa ter entre 6 e 128 caracteres.",
        )
    if dados.senha != dados.confirmar_senha:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="As senhas não estão iguais. Dá uma conferida!",
        )

    usuario = Usuario(
        username=username,
        email=email,
        senha_hash=hash_password(dados.senha),
        role="user",
        ativo=True,
        email_verificado=True,
        google_sub=google_sub,
        ultima_atividade_sessao=_agora_sessao_utc(),
    )
    db.add(usuario)
    try:
        db.commit()
        db.refresh(usuario)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível concluir o cadastro. Confira se o nome ou e-mail já está cadastrado e tente novamente.",
        )

    return TokenResposta(
        access_token=criar_access_token(usuario),
        token_type="bearer",
    )


@router.post("/google/vincular")
async def vincular_conta_google(
    dados: GoogleLoginRequisicao,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Vincula explicitamente o Google à conta já autenticada, sem alterar seu papel."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Login com Google ainda não está configurado no servidor.",
        )

    try:
        info = google_id_token.verify_oauth2_token(
            dados.credential, google_requests.Request(), client_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não foi possível validar sua autenticação com o Google.",
        )

    google_sub = info.get("sub")
    email_google = (info.get("email") or "").strip().lower()
    email_verificado = info.get("email_verified") is True

    if not google_sub or not email_google or not email_verificado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="O Google precisa confirmar seu endereço de e-mail.",
        )

    email_conta = (usuario.email or "").strip().lower()
    if not email_conta or email_google != email_conta:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Entre com a conta DESCTRL cujo e-mail corresponde à conta Google que deseja vincular.",
        )

    outra_conta = (
        db.query(Usuario)
        .filter(Usuario.google_sub == google_sub, Usuario.id != usuario.id)
        .first()
    )
    if outra_conta:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Essa conta Google já está vinculada a outro usuário do DESCTRL.",
        )

    if usuario.google_sub and usuario.google_sub != google_sub:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta conta DESCTRL já está vinculada a outra conta Google.",
        )

    usuario.google_sub = google_sub
    usuario.email_verificado = True
    try:
        db.commit()
        db.refresh(usuario)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível vincular a conta Google. Atualize a página e tente novamente.",
        )

    return {"mensagem": "Conta Google vinculada com sucesso."}



@router.get("/me", response_model=UsuarioResposta)
async def meu_usuario(
    usuario: Usuario = Depends(obter_usuario_atual),
):
    """Retorna os dados do usuário autenticado, sem a senha."""
    return UsuarioResposta(
        id=usuario.id,
        username=usuario.username,
        email=usuario.email,
        role=usuario.role,
        ativo=usuario.ativo,
        email_verificado=bool(getattr(usuario, "email_verificado", False)),
        google_vinculado=bool(getattr(usuario, "google_sub", None)),
    )

@router.post("/session/refresh", response_model=TokenResposta)
async def renovar_sessao(
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Registra atividade explícita do frontend e renova a sessão válida."""
    usuario.ultima_atividade_sessao = _agora_sessao_utc()
    db.add(usuario)
    db.commit()
    db.refresh(usuario)

    return TokenResposta(
        access_token=criar_access_token(usuario),
        token_type="bearer",
    )
