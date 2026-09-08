from sqlalchemy import Column, Integer, String, DECIMAL, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta
from banco_dados import Base

# Fuso horário de Brasília (UTC-3)
BRASILIA = timezone(timedelta(hours=-3))

def now_brasilia():
    return datetime.now(BRASILIA)

class Jogo(Base):
    __tablename__ = "jogos"

    id = Column(Integer, primary_key=True, index=True)
    steam_id = Column(String(50), unique=True, nullable=True)
    epic_id = Column(String(50), unique=True, nullable=True)
    nome = Column(String(255), nullable=False)
    desenvolvedor = Column(String(255))
    publicadora = Column(String(255))
    genero = Column(String(255))
    data_lancamento = Column(Date)
    descricao = Column(Text)           # SEM LIMITE!
    url_imagem = Column(String(500))
    url_steam = Column(String(500))
    url_epic = Column(String(500))
    preco_base_steam = Column(DECIMAL(10, 2))
    preco_base_epic = Column(DECIMAL(10, 2))
    created_at = Column(DateTime, default=now_brasilia)
    updated_at = Column(DateTime, default=now_brasilia, onupdate=now_brasilia)

    historico = relationship("HistoricoPreco", back_populates="jogo", cascade="all, delete-orphan")


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id = Column(Integer, primary_key=True, index=True)
    jogo_id = Column(Integer, ForeignKey("jogos.id", ondelete="CASCADE"))
    nome_jogo = Column(String(255)) 
    plataforma = Column(String(20), nullable=False)
    preco_atual = Column(DECIMAL(10, 2), nullable=False)
    preco_sem_desconto = Column(DECIMAL(10, 2))
    desconto = Column(Integer, default=0)
    data_coleta = Column(DateTime, default=now_brasilia)

    jogo = relationship("Jogo", back_populates="historico")