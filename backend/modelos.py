from datetime import datetime, timezone, timedelta

from sqlalchemy import (
    Column,
    Integer,
    String,
    DECIMAL,
    Date,
    DateTime,
    Text,
    ForeignKey,
    Boolean
)
from sqlalchemy.orm import relationship

from .banco_dados import Base


TIMEZONE_BRASILIA = timezone(timedelta(hours=-3))


def now_brasilia() -> datetime:
    return datetime.now(TIMEZONE_BRASILIA)


class Jogo(Base):
    __tablename__ = "jogos"

    id = Column(Integer, primary_key=True, index=True)

    # Identificadores
    steam_id = Column(String(50), unique=True, nullable=True)
    epic_id = Column(String(50), unique=True, nullable=True)

    # Dados específicos das plataformas
    descricao_steam = Column(Text)
    descricao_epic = Column(Text)

    url_imagem_steam = Column(String(500))
    url_imagem_epic = Column(String(500))

    # Dados gerais
    nome = Column(String(255), nullable=False)
    desenvolvedor = Column(String(255))
    publicadora = Column(String(255))
    genero = Column(String(255))
    data_lancamento = Column(Date)

    # URLs e preços de referência
    url_steam = Column(String(500))
    url_epic = Column(String(500))

    preco_base_steam = Column(DECIMAL(10, 2))
    preco_base_epic = Column(DECIMAL(10, 2))

    # Auditoria
    created_at = Column(DateTime, default=now_brasilia)
    updated_at = Column(
        DateTime,
        default=now_brasilia,
        onupdate=now_brasilia
    )
    visualizacoes = Column(Integer, nullable=False, default=0)

    # Histórico
    historico = relationship(
        "HistoricoPreco",
        back_populates="jogo",
        cascade="all, delete-orphan"
    )

    # Ofertas da Epic
    ofertas_epic = relationship(
        "EpicOferta",
        back_populates="jogo",
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
