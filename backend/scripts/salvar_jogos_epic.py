"""
Script de salvamento de jogos da Epic Games Store.

Este script percorre a lista de jogos da Steam, busca os slugs
correspondentes na Epic Games Store e salva os dados no banco.
"""

import sys
import os
import asyncio
from datetime import datetime
from coletores.epic_coletor import EpicScraper
from banco_dados import SessionLocal
from modelos import Jogo
from lista_jogos import JOGOS_STEAM, get_epic_slug

# Adiciona o diretório pai ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def salvar_jogos_epic():
    """
    Coleta dados da Epic Games Store para todos os jogos da lista
    e salva ou atualiza no banco de dados.

    Jogos nao disponiveis na Epic recebem epic_id = None.
    Jogos gratuitos recebem preco_base_epic = 0.00.
    """
    print("=" * 50)
    print("COLETANDO JOGOS DA EPIC GAMES STORE")
    print("=" * 50)

    scraper = EpicScraper()
    await scraper.iniciar()

    db = SessionLocal()

    atualizados = 0
    erros = 0
    exclusivos = 0

    total_jogos = len(JOGOS_STEAM)

    try:
        for i, steam_id in enumerate(JOGOS_STEAM, 1):
            epic_slug = get_epic_slug(steam_id)

            print(f"\n[{i}/{total_jogos}] Steam ID: {steam_id}")

            # Jogos exclusivos Steam
            if epic_slug is None:
                print("  Exclusivo Steam (epic_id = NULL)")

                jogo = db.query(Jogo).filter(Jogo.steam_id == str(steam_id)).first()

                if jogo:
                    jogo.epic_id = None
                    jogo.updated_at = datetime.now()
                    print(f"  Atualizado: {jogo.nome}")
                    exclusivos += 1
                else:
                    novo_jogo = Jogo(
                        steam_id=str(steam_id),
                        epic_id=None,
                        nome=f"Jogo {steam_id}",
                    )
                    db.add(novo_jogo)
                    print(f"  Inserido: {novo_jogo.nome}")
                    exclusivos += 1

                continue

            print(f"  Slug: {epic_slug}")

            try:
                dados = await scraper.coletar_jogo(epic_slug)

                if "erro" in dados:
                    print(f"  Erro: {dados['erro']}")
                    erros += 1
                    continue

                jogo = db.query(Jogo).filter(Jogo.steam_id == str(steam_id)).first()

                if jogo:
                    # Atualiza dados existentes
                    jogo.epic_id = epic_slug
                    jogo.descricao_epic = dados.get("descricao", "")
                    jogo.url_imagem_epic = dados.get("url_imagem", "")
                    jogo.url_epic = dados.get("url", "")

                    # Preco base
                    if dados.get("preco") == "Grátis":
                        jogo.preco_base_epic = 0.00
                    else:
                        preco_original_str = dados.get("preco_sem_desconto", "N/A")
                        if preco_original_str != "N/A":
                            try:
                                preco_base = float(
                                    preco_original_str.replace("R$", "").replace(",", ".").strip()
                                )
                                jogo.preco_base_epic = preco_base
                            except (ValueError, AttributeError):
                                pass

                    jogo.updated_at = datetime.now()

                    print(f"  Atualizado: {jogo.nome}")
                    if jogo.preco_base_epic is not None:
                        print(f"    Preco base: R$ {jogo.preco_base_epic:.2f}")
                    else:
                        print(f"    Preco base: N/A")
                    atualizados += 1

                else:
                    # Insere novo jogo
                    novo_jogo = Jogo(
                        steam_id=str(steam_id),
                        epic_id=epic_slug,
                        nome=dados.get("nome", "N/A"),
                        descricao_epic=dados.get("descricao", ""),
                        url_imagem_epic=dados.get("url_imagem", ""),
                        url_epic=dados.get("url", ""),
                    )

                    if dados.get("preco") == "Grátis":
                        novo_jogo.preco_base_epic = 0.00
                    else:
                        preco_original_str = dados.get("preco_sem_desconto", "N/A")
                        if preco_original_str != "N/A":
                            try:
                                preco_base = float(
                                    preco_original_str.replace("R$", "").replace(",", ".").strip()
                                )
                                novo_jogo.preco_base_epic = preco_base
                            except (ValueError, AttributeError):
                                pass

                    db.add(novo_jogo)
                    print(f"  Inserido: {novo_jogo.nome}")
                    atualizados += 1

                await asyncio.sleep(0.8)

            except Exception as erro:
                print(f"  Erro: {erro}")
                erros += 1

        db.commit()

        print("\n" + "=" * 50)
        print("RESUMO")
        print("=" * 50)
        print(f"  Atualizados/Inseridos: {atualizados}")
        print(f"  Exclusivos Steam (epic_id = NULL): {exclusivos}")
        print(f"  Erros: {erros}")
        print(f"  Total: {total_jogos}")

    except Exception as erro:
        db.rollback()
        print(f"\nErro ao salvar: {erro}")
    finally:
        db.close()
        await scraper.fechar()


if __name__ == "__main__":
    asyncio.run(salvar_jogos_epic())
