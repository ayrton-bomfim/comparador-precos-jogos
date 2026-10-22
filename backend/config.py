"""
Módulo de configuração da aplicação.

Carrega explicitamente as variáveis do arquivo backend/.env e disponibiliza
as configurações centralizadas para os demais módulos.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Caminho explícito: funciona independentemente do diretório de execução.
BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"
load_dotenv(dotenv_path=ENV_FILE, override=False)


class Settings:
    """Configurações centralizadas da aplicação."""

    # Banco de Dados
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost:5432/comparador_precos"
    )

    # Coleta de Dados
    SCRAPER_HEADLESS: bool = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"
    SCRAPER_TIMEOUT: int = int(os.getenv("SCRAPER_TIMEOUT", "30000"))
    REQUEST_DELAY: int = int(os.getenv("REQUEST_DELAY", "2"))

    # API
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"}

    # URLs e e-mail
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")
    RESEND_FROM_EMAIL: str = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()


settings = Settings()
