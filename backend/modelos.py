from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DECIMAL,
    Date,
    DateTime,
    Text,
    ForeignKey,
    Boolean,
    UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from .banco_dados import Base


TIMEZONE_BRASILIA = timezone(timedelta(hours=-3))


def now_brasilia() -> datetime:
    return datetime.now(TIMEZONE_BRASILIA)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    senha_hash = Column(String(255), nullable=False)
    # Versão usada para invalidar JWTs emitidos antes de uma mudança de senha.
    versao_sessao = Column(Integer, nullable=False, default=0, server_default="0")
    # Horário da última atividade humana reconhecida na sessão.
    ultima_atividade_sessao = Column(DateTime, nullable=True)
    role = Column(String(20), nullable=False, default="user", index=True)
    ativo = Column(Boolean, nullable=False, default=True)
    email_verificado = Column(Boolean, nullable=False, default=False)
    # Preferências de notificação persistidas por conta.
    notificacao_email = Column(Boolean, nullable=False, default=False)
    notificacao_site = Column(Boolean, nullable=False, default=False)
    notificacao_preferencias_configuradas = Column(Boolean, nullable=False, default=False)
    # Identificador estável fornecido pelo Google; NULL para contas convencionais.
    google_sub = Column(String(255), unique=True, nullable=True, index=True)
    # Recomendação temporária da comunidade: no máximo um jogo por usuário.
    jogo_recomendado_id = Column(Integer, ForeignKey("jogos.id", ondelete="SET NULL"), nullable=True, index=True)
    criado_em = Column(DateTime, nullable=False, default=now_brasilia)


class Jogo(Base):
    __tablename__ = "jogos"

    id = Column(Integer, primary_key=True, index=True)

    # Relação entre jogo-base e suas edições/variantes.
    # O jogo-base possui jogo_base_id = NULL.
    jogo_base_id = Column(
        Integer,
        ForeignKey("jogos.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Identificadores
    steam_id = Column(String(50), unique=True, nullable=True)
    epic_id = Column(String(255), unique=True, nullable=True)

    # Dados específicos das plataformas
    descricao_steam = Column(Text)
    descricao_epic = Column(Text)

    url_imagem_steam = Column(String(500))
    url_imagem_epic = Column(String(500))

    # Dados gerais
    nome = Column(String(255), nullable=False)
    desenvolvedor = Column(String(255))
    # Classificação pré-calculada com base nos estúdios brasileiros ativos.
    eh_brasileiro = Column(Boolean, nullable=False, default=False, server_default="false")
    publicadora = Column(String(255))
    genero = Column(String(255))
    data_lancamento = Column(Date)

    # URLs e preços de referência
    url_steam = Column(String(500))
    url_epic = Column(String(500))

    preco_base_steam = Column(DECIMAL(10, 2))
    preco_base_epic = Column(DECIMAL(10, 2))

    # Controle do enriquecimento dos dados da Steam.
    # Preenchido somente quando o appdetails foi processado com sucesso.
    steam_dados_atualizados_em = Column(DateTime, nullable=True)
    steam_disponibilidade_br = Column(String(30), nullable=True)

    # Metadados adicionais da Steam obtidos pelo appdetails.
    steam_required_age = Column(Integer, nullable=True)
    steam_is_free = Column(Boolean, nullable=True)
    steam_metacritic_score = Column(Integer, nullable=True)
    steam_website = Column(Text, nullable=True)

    steam_platforms = Column(JSONB, nullable=True)
    steam_categories = Column(JSONB, nullable=True)
    steam_genres = Column(JSONB, nullable=True)
    steam_ratings = Column(JSONB, nullable=True)
    steam_content_descriptors = Column(JSONB, nullable=True)
    steam_supported_languages = Column(Text, nullable=True)

    steam_content_notes = Column(Text, nullable=True)

    # Requisitos de sistema da Steam.
    steam_pc_requirements = Column(JSONB, nullable=True)
    steam_mac_requirements = Column(JSONB, nullable=True)
    steam_linux_requirements = Column(JSONB, nullable=True)

    # Sinal automático de conteúdo adulto.
    # A decisão editorial será controlada separadamente por status_auditoria.
    steam_conteudo_adulto = Column(Boolean, nullable=False, default=False)
    status_auditoria = Column(
        String(20),
        nullable=False,
        default="nao_avaliado",
        index=True
    )

    # Auditoria
    created_at = Column(DateTime, default=now_brasilia)
    updated_at = Column(
        DateTime,
        default=now_brasilia,
        onupdate=now_brasilia
    )
    visualizacoes = Column(Integer, nullable=False, default=0)

    # Relação autorreferente: um jogo-base pode possuir várias edições.
    jogo_base = relationship(
        "Jogo",
        remote_side=[id],
        foreign_keys=[jogo_base_id],
        back_populates="edicoes"
    )

    edicoes = relationship(
        "Jogo",
        foreign_keys=[jogo_base_id],
        back_populates="jogo_base"
    )

    # Histórico
    historico = relationship(
        "HistoricoPreco",
        back_populates="jogo",
        cascade="all, delete-orphan"
    )

    # Catálogo da Epic
    catalogo_epic = relationship(
        "EpicCatalogo",
        back_populates="jogo",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # Ofertas da Epic
    ofertas_epic = relationship(
        "EpicOferta",
        back_populates="jogo",
        cascade="all, delete-orphan"
    )

    # Catálogo da Steam
    catalogo_steam = relationship(
        "SteamCatalogo",
        back_populates="jogo",
        uselist=False,
        cascade="all, delete-orphan"
    )

    # Auditoria/curadoria editorial de conteúdo.
    auditoria_conteudo = relationship(
        "AuditoriaConteudo",
        back_populates="jogo",
        uselist=False,
        cascade="all, delete-orphan"
    )


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id = Column(Integer, primary_key=True, index=True)

    jogo_id = Column(
        Integer,
        ForeignKey("jogos.id", ondelete="CASCADE"),
        nullable=False
    )

    nome_jogo = Column(String(255), nullable=False)
    plataforma = Column(String(20), nullable=False)

    preco_atual = Column(DECIMAL(10, 2), nullable=False)
    preco_sem_desconto = Column(DECIMAL(10, 2))

    desconto = Column(Integer, default=0)
    data_coleta = Column(DateTime, default=now_brasilia)

    # Dados da promoção informados pela fonte, quando disponíveis.
    # Usados posteriormente para análise de duração, recorrência e campanhas.
    promocao_id = Column(String(100), nullable=True)
    promocao_nome = Column(String(255), nullable=True)
    promocao_tipo = Column(String(100), nullable=True)
    promocao_inicio = Column(DateTime(timezone=True), nullable=True)
    promocao_fim = Column(DateTime(timezone=True), nullable=True)

    jogo = relationship(
        "Jogo",
        back_populates="historico"
    )


class EpicCatalogo(Base):
    __tablename__ = "epic_catalogo"

    id = Column(Integer, primary_key=True, index=True)

    jogo_id = Column(
        Integer,
        ForeignKey("jogos.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Nome recebido da Epic, mantido para facilitar conferências e consultas.
    nome = Column(String(255), nullable=True)

    epic_id = Column(String(255), unique=True, nullable=True)
    epic_offer_id = Column(String(100), unique=True, nullable=True)
    epic_namespace = Column(String(100))

    seller_id = Column(String(100))
    seller_nome = Column(String(255))
    locale = Column(String(20))

    pre_purchase = Column(Boolean, default=False)

    release_date = Column(DateTime(timezone=True))
    pc_release_date = Column(DateTime(timezone=True))
    creation_date = Column(DateTime(timezone=True))
    last_modified_date = Column(DateTime(timezone=True))

    categorias = Column(JSONB)
    tags = Column(JSONB)

    ativo = Column(Boolean, default=True)

    created_at = Column(DateTime, default=now_brasilia)
    updated_at = Column(
        DateTime,
        default=now_brasilia,
        onupdate=now_brasilia
    )

    jogo = relationship(
        "Jogo",
        back_populates="catalogo_epic"
    )


class SteamCatalogo(Base):
    __tablename__ = "steam_catalogo"

    id = Column(Integer, primary_key=True, index=True)

    jogo_id = Column(
        Integer,
        ForeignKey("jogos.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    # Identificador do aplicativo na Steam.
    steam_id = Column(
        String(50),
        unique=True,
        nullable=False
    )

    # Dados atualmente fornecidos pelo índice GetAppList.
    nome = Column(String(255), nullable=True)

    last_modified = Column(BigInteger, nullable=True)
    price_change_number = Column(BigInteger, nullable=True)

    ativo = Column(Boolean, default=True)

    created_at = Column(DateTime, default=now_brasilia)
    updated_at = Column(
        DateTime,
        default=now_brasilia,
        onupdate=now_brasilia
    )

    jogo = relationship(
        "Jogo",
        back_populates="catalogo_steam"
    )


class EpicOferta(Base):
    __tablename__ = "epic_ofertas"

    id = Column(Integer, primary_key=True, index=True)

    jogo_id = Column(
        Integer,
        ForeignKey("jogos.id", ondelete="CASCADE"),
        nullable=False
    )

    offer_id = Column(
        String(100),
        unique=True,
        nullable=False
    )

    sandbox_id = Column(
        String(100),
        nullable=False
    )

    titulo = Column(
        String(255),
        nullable=False
    )

    tipo = Column(
        String(50)
    )

    ativo = Column(
        Boolean,
        default=True
    )

    jogo = relationship(
        "Jogo",
        back_populates="ofertas_epic"
    )


class AuditoriaConteudo(Base):
    """
    Registro editorial de auditoria do conteúdo de um jogo.

    Registro editorial unificado para análise e decisão sobre o conteúdo
    dos jogos. A entrada pode ter origem manual ou automática, e a decisão
    editorial é mantida separadamente dos sinais técnicos das plataformas.
    """

    __tablename__ = "auditorias_conteudo"

    id = Column(Integer, primary_key=True, index=True)

    jogo_id = Column(
        Integer,
        ForeignKey("jogos.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Snapshot do nome no momento da auditoria.
    nome_jogo = Column(String(255), nullable=False)

    # Estados usados pela auditoria editorial.
    # "restrito" representa uma decisão específica para conteúdo sensível.
    status = Column(
        String(20),
        nullable=False,
        default="pendente",
        index=True,
    )

    # Origem da entrada na fila.
    # Ex.: manual, steam, epic, migracao.
    origem = Column(
        String(20),
        nullable=False,
        default="manual",
    )

    motivo = Column(
        String(255),
        nullable=True,
    )

    observacao = Column(
        Text,
        nullable=True,
    )

    # Galeria usada pela tela de curadoria.
    imagens = Column(
        JSONB,
        nullable=True,
    )

    criado_por = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )

    decidido_por = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
    )

    criado_em = Column(
        DateTime,
        nullable=False,
        default=now_brasilia,
    )

    decidido_em = Column(
        DateTime,
        nullable=True,
    )

    jogo = relationship(
        "Jogo",
        back_populates="auditoria_conteudo",
    )

    criador = relationship(
        "Usuario",
        foreign_keys=[criado_por],
    )

    decisor = relationship(
        "Usuario",
        foreign_keys=[decidido_por],
    )

    historico = relationship(
        "AuditoriaConteudoHistorico",
        back_populates="auditoria",
        cascade="all, delete-orphan",
        order_by="AuditoriaConteudoHistorico.criado_em",
    )


class AuditoriaConteudoHistorico(Base):
    """
    Histórico das alterações de status da auditoria editorial.
    """

    __tablename__ = "auditorias_conteudo_historico"

    id = Column(Integer, primary_key=True, index=True)

    auditoria_id = Column(
        Integer,
        ForeignKey(
            "auditorias_conteudo.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    jogo_id = Column(
        Integer,
        ForeignKey(
            "jogos.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    nome_jogo = Column(String(255), nullable=False)

    status_anterior = Column(
        String(20),
        nullable=True,
    )

    status_novo = Column(
        String(20),
        nullable=False,
    )

    motivo = Column(
        String(255),
        nullable=True,
    )

    observacao = Column(
        Text,
        nullable=True,
    )

    usuario_id = Column(
        Integer,
        ForeignKey(
            "usuarios.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    criado_em = Column(
        DateTime,
        nullable=False,
        default=now_brasilia,
    )

    auditoria = relationship(
        "AuditoriaConteudo",
        back_populates="historico",
    )

    usuario = relationship(
        "Usuario",
        foreign_keys=[usuario_id],
    )


class Favorito(Base):
    __tablename__ = "favoritos"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    jogo_id = Column(Integer, ForeignKey("jogos.id", ondelete="CASCADE"), nullable=False, index=True)
    # Cópias dos nomes para facilitar conferência direta na tabela favoritos.
    usuario_nome = Column(String(100), nullable=False)
    jogo_nome = Column(String(255), nullable=False)
    criado_em = Column(DateTime, nullable=False, default=now_brasilia)

    __table_args__ = (
        UniqueConstraint("usuario_id", "jogo_id", name="uq_favoritos_usuario_jogo"),
    )
    usuario = relationship("Usuario")
    jogo = relationship("Jogo")


class HistoricoNomeUsuario(Base):
    """Histórico de nomes anteriores e reservas temporárias de username."""

    __tablename__ = "historico_nomes_usuario"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username_anterior = Column(String(100), nullable=False)
    alterado_em = Column(DateTime, nullable=False, default=lambda: datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None))
    reservado_ate = Column(DateTime, nullable=False)
    recuperado_em = Column(DateTime, nullable=True)

    usuario = relationship("Usuario")


class Conquista(Base):
    """Estado individual de uma conquista para um usuário."""

    __tablename__ = "conquistas"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo = Column(String(80), nullable=False)
    grupo = Column(Integer, nullable=False)
    nome = Column(String(120), nullable=False)
    descricao = Column(Text, nullable=False)
    dica = Column(Text, nullable=True)
    xp = Column(Integer, nullable=False, default=0)
    progresso = Column(Integer, nullable=False, default=0)
    meta = Column(Integer, nullable=False, default=1)
    tipo_recompensa = Column(String(30), nullable=True)
    ordem = Column(Integer, nullable=False, default=1)
    desbloqueada_em = Column(DateTime, nullable=True)
    criada_em = Column(DateTime, nullable=False, default=now_brasilia)
    dados = Column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        UniqueConstraint("usuario_id", "codigo", name="uq_conquistas_usuario_codigo"),
    )
    usuario = relationship("Usuario")


class HistoricoFavorito(Base):
    """Mantém o registro do primeiro favorito de cada jogo por usuário."""

    __tablename__ = "historico_favoritos"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    jogo_id = Column(Integer, ForeignKey("jogos.id", ondelete="CASCADE"), nullable=False)
    jogo_nome = Column(String(255), nullable=False)
    primeiro_favoritado_em = Column(DateTime, nullable=False, default=now_brasilia)

    __table_args__ = (
        UniqueConstraint("usuario_id", "jogo_id", name="uq_historico_favoritos_usuario_jogo"),
    )
    usuario = relationship("Usuario")
    jogo = relationship("Jogo")

class AlertaPreco(Base):
    """Configuração de alerta de preço de um usuário para um jogo favorito."""
    __tablename__ = "alertas_preco"
    __table_args__ = (
        UniqueConstraint("usuario_id", "jogo_id", name="uq_alerta_preco_usuario_jogo"),
    )
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    jogo_id = Column(Integer, ForeignKey("jogos.id", ondelete="CASCADE"), nullable=False, index=True)
    ativo = Column(Boolean, nullable=False, default=True)
    lojas = Column(JSONB, nullable=False, default=lambda: ["steam", "epic"])
    condicao = Column(String(20), nullable=False, default="preco_alvo")
    preco_alvo = Column(DECIMAL(10, 2), nullable=True)
    criado_em = Column(DateTime, nullable=False, default=now_brasilia)
    atualizado_em = Column(DateTime, nullable=False, default=now_brasilia, onupdate=now_brasilia)
    # Estado de borda para evitar repetir o mesmo alerta enquanto a condição continua verdadeira.
    ultima_condicao_ativa = Column(Boolean, nullable=False, default=False)
    # Estado separado para não duplicar notificações no site nem bloquear o canal de e-mail.
    ultima_condicao_site_ativa = Column(Boolean, nullable=False, default=False)
    ultima_notificacao_em = Column(DateTime, nullable=True)
    ultima_notificacao_preco = Column(DECIMAL(10, 2), nullable=True)
    ultima_notificacao_loja = Column(String(20), nullable=True)
    usuario = relationship("Usuario")
    jogo = relationship("Jogo")


class NotificacaoUsuario(Base):
    """Histórico persistente de notificações recebidas por uma conta."""
    __tablename__ = "notificacoes_usuario"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False, index=True)  # preco | conquista
    titulo = Column(String(180), nullable=False)
    mensagem = Column(Text, nullable=False)
    link = Column(String(500), nullable=True)
    jogo_id = Column(Integer, ForeignKey("jogos.id", ondelete="SET NULL"), nullable=True, index=True)
    dados = Column(JSONB, nullable=False, default=dict)
    lida = Column(Boolean, nullable=False, default=False, index=True)
    criada_em = Column(DateTime, nullable=False, default=now_brasilia, index=True)

    usuario = relationship("Usuario")
    jogo = relationship("Jogo")


class TokenSegurancaUsuario(Base):
    """Token temporário de uso único para operações sensíveis da conta."""
    __tablename__ = "tokens_seguranca_usuario"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    usuario_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    finalidade = Column(String(30), nullable=False, index=True)
    email_pendente = Column(String(255), nullable=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expira_em = Column(DateTime(timezone=True), nullable=False, index=True)
    usado_em = Column(DateTime(timezone=True), nullable=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    usuario = relationship("Usuario")



class SugestaoUsuario(Base):
    """Sugestões de melhoria enviadas pela comunidade."""
    __tablename__ = "sugestoes_usuarios"

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(40), nullable=False, default="melhoria")
    pagina_origem = Column(String(500), nullable=False)
    descricao = Column(Text, nullable=False)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True)
    criada_em = Column(DateTime, nullable=False, default=now_brasilia)
    status = Column(String(20), nullable=False, default="pendente", server_default="pendente", index=True)
    concluida_em = Column(DateTime, nullable=True)

    usuario = relationship("Usuario")
