import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/comparador_precos")
    
    # Scraping
    SCRAPER_HEADLESS = os.getenv("SCRAPER_HEADLESS", "true").lower() == "true"
    SCRAPER_TIMEOUT = int(os.getenv("SCRAPER_TIMEOUT", "30000"))
    REQUEST_DELAY = int(os.getenv("REQUEST_DELAY", "2"))
    
    # API
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"

settings = Settings()