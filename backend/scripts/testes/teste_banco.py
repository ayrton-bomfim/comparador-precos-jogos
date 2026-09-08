from banco_dados import SessionLocal
from modelos import Jogo

def testar_conexao():
    try:
        db = SessionLocal()
        print("✅ Conexão com o banco estabelecida!")
        
        count = db.query(Jogo).count()
        print(f"📊 Jogos no banco: {count}")
        
        db.close()
        return True
    except Exception as e:
        print(f"❌ Erro na conexão: {e}")
        return False

if __name__ == "__main__":
    testar_conexao()