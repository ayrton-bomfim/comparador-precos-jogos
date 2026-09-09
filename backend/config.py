"""
Módulo de configuração da aplicação.

Carrega variáveis de ambiente do arquivo .env e disponibiliza
as configurações centralizadas para os demais módulos.
"""

import os
from dotenv import load_dotenv

# Carrega variáveis do arquivo .env
load_dotenv()


class Settings:
    """
    Configurações da aplicação.

    Atributos:
        DATABASE_URL: String de conexão com o PostgreSQL.
        SCRAPER_HEADLESS: Define se o navegador deve rodar em modo headless.
        SCRAPER_TIMEOUT: Tempo máximo de espera para operações de scraping (ms).
        REQUEST_DELAY: Intervalo entre requisições (segundos).
        API_HOST: Host onde a API será executada.
        API_PORT: Porta onde a API será executada.
        DEBUG: Ativa o modo de depuração.
    """

    # ==========================================================================
    # Banco de Dados
    # ==========================================================================
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://localhost:5432/comparador_precos"
    )

    # ==========================================================================
    # Coleta de Dados (Scraping)
    # ==========================================================================
    SCRAPER_HEADLESS: bool = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"
    SCRAPER_TIMEOUT: int = int(os.getenv("SCRAPER_TIMEOUT", "30000"))
    REQUEST_DELAY: int = int(os.getenv("REQUEST_DELAY", "2"))

    # ==========================================================================
    # API
    # ==========================================================================
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"


# Instância única das configurações para uso em toda a aplicação
settings = Settings()