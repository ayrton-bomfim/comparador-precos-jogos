"""
Módulo de configuração do banco de dados.

Este módulo gerencia a conexão com o PostgreSQL, fornecendo
a engine, a fábrica de sessões e a base para os modelos SQLAlchemy.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Engine de conexão com o banco de dados
engine = create_engine(settings.DATABASE_URL)

# Fábrica de sessões para interação com o banco
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Classe base para definição dos modelos ORM
Base = declarative_base()


def get_db():
    """
    Gerencia a sessão do banco de dados em requisições.

    Esta função é utilizada como dependência do FastAPI,
    garantindo que a sessão seja aberta antes da requisição
    e fechada após seu término.

    Yields:
        Session: Sessão ativa do SQLAlchemy.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()