"""
Script de coleta de histórico de preços da Epic Games Store.

Este script percorre todos os jogos cadastrados na Epic,
consulta seus preços atuais e registra as variações na tabela de histórico.
"""

import sys
import os
import asyncio
from datetime import datetime
from sqlalchemy import func, and_, cast, Date
from coletores.epic_coletor import EpicScraper
from banco_dados import SessionLocal
from modelos import Jogo, HistoricoPreco

# Adiciona o diretório pai ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def coletar_historico_epic():
    """
    Coleta os precos atuais de todos os jogos disponiveis na Epic
    e salva no historico.

    Um novo registro e criado apenas se houve mudanca de preco (com tolerancia
    de R$ 0,01), mudanca de desconto, ou se a data da ultima coleta e diferente
    da data atual.
    """
    print("=" * 50)
    print("COLETANDO HISTORICO DE PRECOS (EPIC)")
    print("Novo registro: mudanca ou dia diferente")
    print("=" * 50)
    print(f"Inicio: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    scraper = EpicScraper()
    await scraper.iniciar()

    db = SessionLocal()
    hoje = datetime.now().date()

    try:
        # Busca apenas jogos com epic_id valido
        jogos = db.query(Jogo).filter(
            and_(
                Jogo.epic_id.isnot(None),
                Jogo.epic_id != "EXCLUSIVO_STEAM"
            )
        ).all()

        print(f"\n{len(jogos)} jogos encontrados na Epic")

        if not jogos:
            print("Nenhum jogo encontrado na Epic.")
            return

        alterados = 0
        erros = 0
        ignorados = 0

        for i, jogo in enumerate(jogos, 1):
            print(f"\n[{i}/{len(jogos)}] Coletando: {jogo.nome} (Epic ID: {jogo.epic_id})")

            try:
                dados = await scraper.coletar_jogo(jogo.epic_id)

                if "erro" in dados:
                    print(f"  Erro: {dados['erro']}")
                    erros += 1
                    continue

                # Conversao de precos
                preco_str = dados.get("preco", "N/A")
                if preco_str == "Grátis" or preco_str == "N/A":
                    preco_num = 0.0
                else:
                    try:
                        preco_num = float(preco_str.replace("R$", "").replace(",", ".").strip())
                    except (ValueError, AttributeError):
                        preco_num = 0.0

                preco_original_str = dados.get("preco_sem_desconto", "N/A")
                if preco_original_str == "Grátis" or preco_original_str == "N/A":
                    preco_original_num = 0.0
                else:
                    try:
                        preco_original_num = float(
                            preco_original_str.replace("R$", "").replace(",", ".").strip()
                        )
                    except (ValueError, AttributeError):
                        preco_original_num = 0.0

                # Extrai o desconto
                desconto_str = dados.get("desconto", "0%")
                try:
                    desconto = int(desconto_str.replace("%", "")) if desconto_str else 0
                except ValueError:
                    desconto = 0

                # Busca o ultimo registro para este jogo na Epic
                ultimo_registro = db.query(HistoricoPreco).filter(
                    and_(
                        HistoricoPreco.jogo_id == jogo.id,
                        HistoricoPreco.plataforma == "Epic"
                    )
                ).order_by(HistoricoPreco.data_coleta.desc()).first()

                # Verifica se deve criar novo registro
                deve_criar = False
                motivo = ""

                if ultimo_registro is None:
                    deve_criar = True
                    motivo = "Primeiro registro na Epic"
                else:
                    preco_atual_float = float(preco_num)
                    preco_anterior_float = float(ultimo_registro.preco_atual)

                    preco_atual_arredondado = round(preco_atual_float, 2)
                    preco_anterior_arredondado = round(preco_anterior_float, 2)
                    diferenca_preco = abs(preco_atual_arredondado - preco_anterior_arredondado)

                    # Verifica mudanca de preco (tolerancia de 1 centavo)
                    if diferenca_preco > 0.01:
                        deve_criar = True
                        motivo = (
                            f"Preco mudou (R$ {preco_anterior_arredondado:.2f} "
                            f"-> R$ {preco_atual_arredondado:.2f})"
                        )
                    # Verifica mudanca de desconto
                    elif desconto != ultimo_registro.desconto:
                        deve_criar = True
                        motivo = f"Desconto mudou ({ultimo_registro.desconto}% -> {desconto}%)"
                    # Verifica se e um dia diferente
                    else:
                        data_ultimo = ultimo_registro.data_coleta.date()
                        if data_ultimo != hoje:
                            deve_criar = True
                            motivo = f"Dia diferente (ultimo: {data_ultimo.strftime('%d/%m/%Y')})"

                if not deve_criar:
                    print(f"  Sem mudancas hoje (R$ {preco_num:.2f}, {desconto}%)")
                    ignorados += 1
                    continue

                # Cria novo registro de historico
                historico = HistoricoPreco(
                    jogo_id=jogo.id,
                    nome_jogo=jogo.nome,
                    plataforma="Epic",
                    preco_atual=preco_num,
                    preco_sem_desconto=preco_original_num,
                    desconto=desconto,
                    data_coleta=datetime.now()
                )

                db.add(historico)

                print(f"  {motivo}")
                print(f"  Novo registro: R$ {preco_num:.2f} "
                      f"(original: R$ {preco_original_num:.2f}, {desconto}% off)")
                alterados += 1

                # Atualiza o preco base do jogo na Epic
                if preco_original_num > 0:
                    jogo.preco_base_epic = preco_original_num
                    jogo.updated_at = datetime.now()

                await asyncio.sleep(0.3)

            except Exception as erro:
                print(f"  Erro: {erro}")
                erros += 1

        db.commit()

        print("\n" + "=" * 50)
        print("RESUMO DA COLETA (EPIC)")
        print("=" * 50)
        print(f"  Novos registros: {alterados}")
        print(f"  Ignorados (sem mudanca): {ignorados}")
        print(f"  Erros: {erros}")
        print(f"  Total: {len(jogos)}")
        print(f"  Fim: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    except Exception as erro:
        db.rollback()
        print(f"\nErro geral: {erro}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        await scraper.fechar()


async def verificar_historico_epic():
    """Verifica quantos registros de historico da Epic existem por dia."""
    db = SessionLocal()
    try:
        count = db.query(HistoricoPreco).filter(
            HistoricoPreco.plataforma == "Epic"
        ).count()

        ultimo = db.query(HistoricoPreco).filter(
            HistoricoPreco.plataforma == "Epic"
        ).order_by(HistoricoPreco.data_coleta.desc()).first()

        por_dia = db.query(
            cast(HistoricoPreco.data_coleta, Date).label("data"),
            func.count(HistoricoPreco.id).label("total")
        ).filter(
            HistoricoPreco.plataforma == "Epic"
        ).group_by("data").order_by("data").all()

        print(f"\nHISTORICO EPIC:")
        print(f"  Total de registros: {count}")
        print(f"  Dias com registros: {len(por_dia)}")

        if ultimo:
            print(f"  Ultima coleta: {ultimo.data_coleta.strftime('%d/%m/%Y %H:%M')}")
            print(f"  Ultimo preco: R$ {ultimo.preco_atual:.2f}")

        if por_dia:
            print("\n  Registros por dia:")
            for item in por_dia[-5:]:
                print(f"    {item[0].strftime('%d/%m/%Y')}: {item[1]} registros")

    finally:
        db.close()


async def limpar_historico_epic_duplicado():
    """
    Remove registros duplicados da Epic do mesmo dia,
    mantendo apenas o mais recente.
    """
    db = SessionLocal()
    try:
        print("Removendo registros duplicados da Epic do mesmo dia...")

        duplicatas = db.query(
            HistoricoPreco.jogo_id,
            HistoricoPreco.plataforma,
            cast(HistoricoPreco.data_coleta, Date).label("data"),
            func.count(HistoricoPreco.id).label("total")
        ).filter(
            HistoricoPreco.plataforma == "Epic"
        ).group_by(
            HistoricoPreco.jogo_id,
            HistoricoPreco.plataforma,
            cast(HistoricoPreco.data_coleta, Date)
        ).having(func.count(HistoricoPreco.id) > 1).all()

        if not duplicatas:
            print("  Nenhuma duplicata encontrada.")
            return

        print(f"  Encontradas {len(duplicatas)} duplicatas")

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
        print("  Duplicatas removidas.")

    except Exception as erro:
        db.rollback()
        print(f"  Erro: {erro}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(coletar_historico_epic())