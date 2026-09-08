import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import asyncio
import re
from datetime import datetime
from coletores.steam_coletor import SteamColetor
from banco_dados import SessionLocal
from modelos import Jogo


async def salvar_jogos_steam():
    """Coleta jogos da Steam e SALVA OU ATUALIZA no banco de dados"""
    
    print("🎮 Coletando jogos da Steam...")
    coletor = SteamColetor()
    dados = await coletor.coletar_precos()
    
    if not dados.get('jogos'):
        print("❌ Nenhum jogo coletado!")
        return
    
    db = SessionLocal()
    adicionados = 0
    atualizados = 0
    
    try:
        for jogo_data in dados['jogos']:
            # 🔹 PREÇO BASE = preço sem desconto (preço cheio)
            preco_str = jogo_data.get('preco_sem_desconto')
            if preco_str == 'Grátis' or preco_str == 'N/A' or preco_str is None:
                preco_str = jogo_data['preco']
            
            if preco_str == 'Grátis' or preco_str == 'N/A':
                preco_num = 0
            else:
                try:
                    preco_num = float(preco_str.replace('R$', '').replace(',', '.').strip())
                except:
                    preco_num = 0
            
            # 🔹 DATA DE LANÇAMENTO - INICIALIZA PRIMEIRO!
            data_lanc = None  # ⬅️ 4 espaços de indentação
            
            if jogo_data.get('data_lancamento'):  # ⬅️ 4 espaços
                data_str = jogo_data['data_lancamento'].strip()  # ⬅️ 8 espaços
                
                meses_map = {  # ⬅️ 8 espaços
                    'jan': 1, 'fev': 2, 'mar': 3, 'abr': 4, 'mai': 5, 'jun': 6,
                    'jul': 7, 'ago': 8, 'set': 9, 'out': 10, 'nov': 11, 'dez': 12,
                    'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
                    'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                
                padroes = [  # ⬅️ 8 espaços
                    (r'(\d{1,2})\s*[/-]?\s*([A-Za-z]{3,})\.?\s*,?\s*(\d{4})', 1, 2, 3),
                    (r'(\d{4})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{1,2})', 3, 2, 1),
                    (r'(\d{1,2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{4})', 1, 2, 3),
                    (r'(\d{1,2})\s*de\s*([A-Za-z]{3,})\s*de\s*(\d{4})', 1, 2, 3),
                ]
                
                for padrao, dia_idx, mes_idx, ano_idx in padroes:  # ⬅️ 8 espaços
                    match = re.search(padrao, data_str, re.IGNORECASE)  # ⬅️ 12 espaços
                    if match:  # ⬅️ 12 espaços
                        try:  # ⬅️ 16 espaços
                            dia = int(match.group(dia_idx))  # ⬅️ 20 espaços
                            mes_str = match.group(mes_idx).lower()  # ⬅️ 20 espaços
                            ano = int(match.group(ano_idx))  # ⬅️ 20 espaços
                            
                            mes = None  # ⬅️ 20 espaços
                            if mes_str.isdigit():  # ⬅️ 20 espaços
                                mes = int(mes_str)  # ⬅️ 24 espaços
                            else:  # ⬅️ 20 espaços
                                for nome, num in meses_map.items():  # ⬅️ 24 espaços
                                    if mes_str.startswith(nome[:3]) or mes_str in nome:  # ⬅️ 28 espaços
                                        mes = num  # ⬅️ 32 espaços
                                        break  # ⬅️ 32 espaços
                            
                            if mes and 1 <= mes <= 12 and 1 <= dia <= 31 and 1000 <= ano <= 2100:  # ⬅️ 20 espaços
                                data_lanc = datetime(ano, mes, dia).date()  # ⬅️ 24 espaços
                                break  # ⬅️ 24 espaços
                        except:  # ⬅️ 16 espaços
                            continue  # ⬅️ 20 espaços
                
                if data_lanc is None:  # ⬅️ 8 espaços
                    formatos = ['%d %b, %Y', '%d %b %Y', '%d %b. %Y', '%d/%b/%Y', '%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']  # ⬅️ 12 espaços
                    for fmt in formatos:  # ⬅️ 12 espaços
                        try:  # ⬅️ 16 espaços
                            data_lanc = datetime.strptime(data_str, fmt).date()  # ⬅️ 20 espaços
                            break  # ⬅️ 20 espaços
                        except:  # ⬅️ 16 espaços
                            continue  # ⬅️ 20 espaços
                
                if data_lanc is None:  # ⬅️ 8 espaços
                    print(f"   ⚠️ Data não reconhecida: '{data_str}'")  # ⬅️ 12 espaços

            
            # 🔹 VERIFICA se o jogo já existe
            existing = db.query(Jogo).filter(Jogo.steam_id == jogo_data['id']).first()
            
            if existing:
                # 🔄 ATUALIZA o jogo existente
                existing.nome = jogo_data['nome']
                existing.desenvolvedor = jogo_data.get('desenvolvedor', 'N/A')
                existing.publicadora = jogo_data.get('publicadora', 'N/A')
                existing.genero = jogo_data.get('genero', 'N/A')
                existing.data_lancamento = data_lanc
                existing.descricao = jogo_data.get('descricao', '')
                existing.url_imagem = jogo_data.get('url_imagem', '')
                existing.url_steam = jogo_data['url']
                existing.preco_base_steam = preco_num
                existing.updated_at = datetime.now()
                
                atualizados += 1
                print(f"🔄 Jogo atualizado: {jogo_data['nome']}")
                print(f"   📅 {data_lanc or 'N/A'} | R$ {preco_num:.2f}")
                print(f"   🏷️  {jogo_data.get('desenvolvedor', 'N/A')} | {jogo_data.get('genero', 'N/A')}")
            else:
                # ➕ INSERE novo jogo
                novo_jogo = Jogo(
                    steam_id=jogo_data['id'],
                    nome=jogo_data['nome'],
                    desenvolvedor=jogo_data.get('desenvolvedor', 'N/A'),
                    publicadora=jogo_data.get('publicadora', 'N/A'),
                    genero=jogo_data.get('genero', 'N/A'),
                    data_lancamento=data_lanc,
                    descricao=jogo_data.get('descricao', ''),
                    url_imagem=jogo_data.get('url_imagem', ''),
                    url_steam=jogo_data['url'],
                    preco_base_steam=preco_num,
                )
                db.add(novo_jogo)
                adicionados += 1
                print(f"✅ Jogo adicionado: {jogo_data['nome']}")
                print(f"   📅 {data_lanc or 'N/A'} | R$ {preco_num:.2f}")
                print(f"   🏷️  {jogo_data.get('desenvolvedor', 'N/A')} | {jogo_data.get('genero', 'N/A')}")
        
        db.commit()
        print(f"\n🎉 RESUMO:")
        print(f"   📥 {adicionados} jogos adicionados")
        print(f"   🔄 {atualizados} jogos atualizados")
        print(f"   📊 Total: {len(dados['jogos'])} jogos processados")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Erro ao salvar: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(salvar_jogos_steam())