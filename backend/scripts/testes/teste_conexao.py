import psycopg2
from config import settings

try:
    print("🔄 Tentando conectar ao banco de dados...")
    print(f"🔗 URL: {settings.DATABASE_URL}")  # CUIDADO: Isso mostrará sua senha no terminal!
    
    conn = psycopg2.connect(settings.DATABASE_URL)
    print("✅ Conexão bem-sucedida!")
    conn.close()
except Exception as e:
    print("❌ Erro ao conectar:")
    print(f"Tipo do erro: {type(e).__name__}")
    print(f"Mensagem: {e}")