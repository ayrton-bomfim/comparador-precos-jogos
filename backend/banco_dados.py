from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# Criar a engine de conexão
engine = create_engine(settings.DATABASE_URL)

# Criar a fábrica de sessões
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base para os modelos
Base = declarative_base()

def get_db():
    """Função para injetar a sessão do banco nas rotas"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()