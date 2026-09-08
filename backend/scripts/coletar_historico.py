import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from datetime import datetime
from sqlalchemy import func, and_, cast, Date
from coletores.steam_coletor import SteamColetor
from banco_dados import SessionLocal
from modelos import Jogo, HistoricoPreco


async def coletar_historico_precos():
    """
    Coleta os preços atuais de TODOS os jogos no banco
    e salva no histórico se:
    1) O preço mudou (tolerância de 1 centavo)
    2) O desconto mudou
    3) A data da última coleta é diferente de hoje
    """
    
    print("=" * 50)
    print("📊 COLETANDO HISTÓRICO DE PREÇOS")
    print("   (Novo registro: mudança OU dia diferente)")
    print("=" * 50)
    print(f"🕐 Início: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    db = SessionLocal()
    coletor = SteamColetor()
    hoje = datetime.now().date()
    
    try:
        jogos = db.query(Jogo).filter(Jogo.steam_id.isnot(None)).all()
        print(f"\n📋 {len(jogos)} jogos encontrados no banco")
        
        if not jogos:
            print("❌ Nenhum jogo encontrado! Execute salvar_jogos.py primeiro.")
            return
        
        alterados = 0
        erros = 0
        ignorados = 0
        
        for i, jogo in enumerate(jogos, 1):
            print(f"\n[{i}/{len(jogos)}] 🔍 Coletando: {jogo.nome} (ID: {jogo.steam_id}")
            
            try:
                dados = await coletor.coletar_jogo(jogo.steam_id)
                
                if 'erro' in dados:
                    print(f"   ❌ Erro: {dados['erro']}")
                    erros += 1
                    continue
                
                # Converte preços
                preco_str = dados.get('preco', 'N/A')
                if preco_str == 'Grátis' or preco_str == 'N/A':
                    preco_num = 0.0
                else:
                    try:
                        preco_num = float(preco_str.replace('R$', '').replace(',', '.').strip())
                    except:
                        preco_num = 0.0
                
                preco_original_str = dados.get('preco_sem_desconto', 'N/A')
                if preco_original_str == 'Grátis' or preco_original_str == 'N/A':
                    preco_original_num = 0.0
                else:
                    try:
                        preco_original_num = float(preco_original_str.replace('R$', '').replace(',', '.').strip())
                    except:
                        preco_original_num = 0.0
                
                desconto = int(dados.get('desconto', '0%').replace('%', '')) if dados.get('desconto') else 0
                
                # 🔍 BUSCA O ÚLTIMO REGISTRO
                ultimo_registro = db.query(HistoricoPreco).filter(
                    and_(
                        HistoricoPreco.jogo_id == jogo.id,
                        HistoricoPreco.plataforma == 'Steam'
                    )
                ).order_by(HistoricoPreco.data_coleta.desc()).first()
                
                # 🔄 VERIFICA SE DEVE CRIAR NOVO REGISTRO
                deve_criar = False
                motivo = ""
                
                if ultimo_registro is None:
                    deve_criar = True
                    motivo = "Primeiro registro"
                else:
                    # 🔧 CONVERTE PARA FLOAT E ARREDONDA
                    preco_atual_float = float(preco_num)
                    preco_anterior_float = float(ultimo_registro.preco_atual)
                    
                    preco_atual_arredondado = round(preco_atual_float, 2)
                    preco_anterior_arredondado = round(preco_anterior_float, 2)
                    diferenca_preco = abs(preco_atual_arredondado - preco_anterior_arredondado)
                    
                    # 1️⃣ VERIFICA MUDANÇAS DE PREÇO (tolerância de 1 centavo)
                    if diferenca_preco > 0.01:
                        deve_criar = True
                        motivo = f"Preço mudou (R$ {preco_anterior_arredondado:.2f} → R$ {preco_atual_arredondado:.2f})"
                    # 2️⃣ VERIFICA MUDANÇAS DE DESCONTO
                    elif desconto != ultimo_registro.desconto:
                        deve_criar = True
                        motivo = f"Desconto mudou ({ultimo_registro.desconto}% → {desconto}%)"
                    else:
                        # 3️⃣ VERIFICA SE É UM DIA DIFERENTE
                        data_ultimo = ultimo_registro.data_coleta.date()
                        if data_ultimo != hoje:
                            deve_criar = True
                            motivo = f"Dia diferente (último: {data_ultimo.strftime('%d/%m/%Y')})"
                
                if not deve_criar:
                    print(f"   ⏭️ Sem mudanças hoje (R$ {preco_num:.2f}, {desconto}%)")
                    ignorados += 1
                    continue
                
                # ➕ CRIA NOVO REGISTRO
                historico = HistoricoPreco(
                    jogo_id=jogo.id,
                    nome_jogo=jogo.nome,
                    plataforma='Steam',
                    preco_atual=preco_num,
                    preco_sem_desconto=preco_original_num,
                    desconto=desconto,
                    data_coleta=datetime.now()
                )
                
                db.add(historico)
                
                print(f"   ✅ {motivo}")
                print(f"   📊 Novo registro: R$ {preco_num:.2f} (original: R$ {preco_original_num:.2f}, {desconto}% off)")
                alterados += 1
                
                if preco_original_num > 0:
                    jogo.preco_base_steam = preco_original_num
                    jogo.updated_at = datetime.now()
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"   ❌ Erro: {e}")
                erros += 1
        
        db.commit()
        
        print("\n" + "=" * 50)
        print("📊 RESUMO DA COLETA")
        print("=" * 50)
        print(f"   📝 Novos registros: {alterados}")
        print(f"   ⏭️ Ignorados (sem mudança): {ignorados}")
        print(f"   ❌ Erros: {erros}")
        print(f"   📊 Total: {len(jogos)}")
        print(f"   🕐 Fim: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
    except Exception as e:
        db.rollback()
        print(f"\n❌ Erro geral: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


async def verificar_historico():
    """Verifica quantos registros de histórico existem por dia"""
    db = SessionLocal()
    try:
        count = db.query(HistoricoPreco).count()
        ultimo = db.query(HistoricoPreco).order_by(HistoricoPreco.data_coleta.desc()).first()
        
        por_dia = db.query(
            cast(HistoricoPreco.data_coleta, Date).label('data'),
            func.count(HistoricoPreco.id).label('total')
        ).group_by('data').order_by('data').all()
        
        print(f"\n📊 HISTÓRICO ATUAL:")
        print(f"   Total de registros: {count}")
        print(f"   Dias com registros: {len(por_dia)}")
        if ultimo:
            print(f"   Última coleta: {ultimo.data_coleta.strftime('%d/%m/%Y %H:%M')}")
            print(f"   Último preço: R$ {ultimo.preco_atual:.2f} ({ultimo.plataforma})")
        
        if por_dia:
            print("\n   📅 Registros por dia:")
            for item in por_dia[-5:]:
                print(f"      {item[0].strftime('%d/%m/%Y')}: {item[1]} registros")
    finally:
        db.close()


async def limpar_historico_duplicado():
    """Remove registros duplicados do mesmo dia (mantém o mais recente)"""
    db = SessionLocal()
    try:
        print("🧹 Removendo registros duplicados do mesmo dia...")
        
        duplicatas = db.query(
            HistoricoPreco.jogo_id,
            HistoricoPreco.plataforma,
            cast(HistoricoPreco.data_coleta, Date).label('data'),
            func.count(HistoricoPreco.id).label('total')
        ).group_by(
            HistoricoPreco.jogo_id,
            HistoricoPreco.plataforma,
            cast(HistoricoPreco.data_coleta, Date)
        ).having(func.count(HistoricoPreco.id) > 1).all()
        
        if not duplicatas:
            print("   ✅ Nenhuma duplicata encontrada!")
            return
        
        print(f"   ⚠️ Encontradas {len(duplicatas)} duplicatas")
        
        for dup in duplicatas:
            subq = db.query(HistoricoPreco.id).filter(
                and_(
                    HistoricoPreco.jogo_id == dup.jogo_id,
                    HistoricoPreco.plataforma == dup.plataforma,
                    cast(HistoricoPreco.data_coleta, Date) == dup.data
                )
            ).order_by(HistoricoPreco.data_coleta.desc()).offset(1).subquery()
            
            db.query(HistoricoPreco).filter(
                HistoricoPreco.id.in_(subq)
            ).delete(synchronize_session=False)
        
        db.commit()
        print(f"   ✅ Duplicatas removidas!")
        
    except Exception as e:
        db.rollback()
        print(f"   ❌ Erro: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import asyncio
    asyncio.run(coletar_historico_precos())