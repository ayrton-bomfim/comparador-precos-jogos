"""
Módulo de definição dos modelos ORM.

Este módulo define as classes que mapeiam as tabelas do banco de dados
utilizando o SQLAlchemy, incluindo as relações entre elas.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DECIMAL, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from banco_dados import Base

# =============================================================================
# Configuração de Fuso Horário
# =============================================================================

# Fuso horário de Brasília (UTC-3)
TIMEZONE_BRASILIA = timezone(timedelta(hours=-3))


def now_brasilia() -> datetime:
    """
    Retorna a data e hora atual no fuso horário de Brasília.

    Returns:
        datetime: Data e hora atuais com fuso horário UTC-3.
    """
    return datetime.now(TIMEZONE_BRASILIA)


# =============================================================================
# Modelos
# =============================================================================

class Jogo(Base):
    """
    Modelo da tabela 'jogos'.

    Armazena os dados cadastrais dos jogos, incluindo informações
    específicas de cada plataforma (Steam e Epic Games Store).
    """

    __tablename__ = "jogos"

    # -------------------------------------------------------------------------
    # Identificadores
    # -------------------------------------------------------------------------
    id = Column(Integer, primary_key=True, index=True)
    steam_id = Column(String(50), unique=True, nullable=True)
    epic_id = Column(String(50), unique=True, nullable=True)

    # -------------------------------------------------------------------------
    # Dados Específicos por Plataforma
    # -------------------------------------------------------------------------
    descricao_steam = Column(Text)
    descricao_epic = Column(Text)
    url_imagem_steam = Column(String(500))
    url_imagem_epic = Column(String(500))

    # -------------------------------------------------------------------------
    # Dados Comuns
    # -------------------------------------------------------------------------
    nome = Column(String(255), nullable=False)
    desenvolvedor = Column(String(255))
    publicadora = Column(String(255))
    genero = Column(String(255))
    data_lancamento = Column(Date)

    # -------------------------------------------------------------------------
    # URLs e Preços
    # -------------------------------------------------------------------------
    url_steam = Column(String(500))
    url_epic = Column(String(500))
    preco_base_steam = Column(DECIMAL(10, 2))
    preco_base_epic = Column(DECIMAL(10, 2))

    # -------------------------------------------------------------------------
    # Controle de Auditoria
    # -------------------------------------------------------------------------
    created_at = Column(DateTime, default=now_brasilia)
    updated_at = Column(DateTime, default=now_brasilia, onupdate=now_brasilia)

    # -------------------------------------------------------------------------
    # Relacionamentos
    # -------------------------------------------------------------------------
    historico = relationship(
        "HistoricoPreco",
        back_populates="jogo",
        cascade="all, delete-orphan"
    )


class HistoricoPreco(Base):
    """
    Modelo da tabela 'historico_precos'.

    Registra as variações de preço de cada jogo ao longo do tempo,
    permitindo a análise de evolução e padrões promocionais.
    """

    __tablename__ = "historico_precos"

    # -------------------------------------------------------------------------
    # Identificadores
    # -------------------------------------------------------------------------
    id = Column(Integer, primary_key=True, index=True)
    jogo_id = Column(Integer, ForeignKey("jogos.id", ondelete="CASCADE"))

    # -------------------------------------------------------------------------
    # Dados do Registro
    # -------------------------------------------------------------------------
    nome_jogo = Column(String(255), nullable=False)
    plataforma = Column(String(20), nullable=False)
    preco_atual = Column(DECIMAL(10, 2), nullable=False)
    preco_sem_desconto = Column(DECIMAL(10, 2))
    desconto = Column(Integer, default=0)
    data_coleta = Column(DateTime, default=now_brasilia)

    # -------------------------------------------------------------------------
    # Relacionamentos
    # -------------------------------------------------------------------------
    jogo = relationship("Jogo", back_populates="historico")