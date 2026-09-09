"""
Script de salvamento de jogos da Steam.

Este script coleta dados da Steam para todos os jogos da lista
e salva ou atualiza no banco de dados.
"""

import sys
import os
import asyncio
import re
from datetime import datetime
from coletores.steam_coletor import SteamColetor
from banco_dados import SessionLocal
from modelos import Jogo

# Adiciona o diretório pai ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def salvar_jogos_steam():
    """
    Coleta jogos da Steam e salva ou atualiza no banco de dados.

    Para cada jogo, verifica se ja existe pelo steam_id.
    Se existir, atualiza os dados. Se nao, insere um novo registro.
    """
    print("=" * 50)
    print("COLETANDO DADOS DA STEAM")
    print("=" * 50)

    coletor = SteamColetor()
    dados = await coletor.coletar_precos()

    if not dados.get("jogos"):
        print("Nenhum jogo coletado.")
        return

    db = SessionLocal()
    adicionados = 0
    atualizados = 0

    try:
        for dados_jogo in dados["jogos"]:
            # Preco base (preco sem desconto)
            preco_str = dados_jogo.get("preco_sem_desconto")
            if preco_str in ("Grátis", "N/A", None):
                preco_str = dados_jogo["preco"]

            if preco_str in ("Grátis", "N/A"):
                preco_num = 0
            else:
                try:
                    preco_num = float(preco_str.replace("R$", "").replace(",", ".").strip())
                except (ValueError, AttributeError):
                    preco_num = 0

            # Data de lancamento
            data_lanc = None
            if dados_jogo.get("data_lancamento"):
                data_str = dados_jogo["data_lancamento"].strip()

                meses_map = {
                    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
                    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
                    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
                    "december": 12
                }

                padroes = [
                    (r'(\d{1,2})\s*[/-]?\s*([A-Za-z]{3,})\.?\s*,?\s*(\d{4})', 1, 2, 3),
                    (r'(\d{4})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{1,2})', 3, 2, 1),
                    (r'(\d{1,2})\s*[/-]\s*(\d{1,2})\s*[/-]\s*(\d{4})', 1, 2, 3),
                    (r'(\d{1,2})\s*de\s*([A-Za-z]{3,})\s*de\s*(\d{4})', 1, 2, 3),
                ]

                for padrao, dia_idx, mes_idx, ano_idx in padroes:
                    match = re.search(padrao, data_str, re.IGNORECASE)
                    if match:
                        try:
                            dia = int(match.group(dia_idx))
                            mes_str = match.group(mes_idx).lower()
                            ano = int(match.group(ano_idx))

                            mes = None
                            if mes_str.isdigit():
                                mes = int(mes_str)
                            else:
                                for nome_mes, num_mes in meses_map.items():
                                    if mes_str.startswith(nome_mes[:3]) or mes_str in nome_mes:
                                        mes = num_mes
                                        break

                            if mes and 1 <= mes <= 12 and 1 <= dia <= 31 and 1000 <= ano <= 2100:
                                data_lanc = datetime(ano, mes, dia).date()
                                break
                        except (ValueError, AttributeError):
                            continue

                if data_lanc is None:
                    formatos = [
                        "%d %b, %Y", "%d %b %Y", "%d %b. %Y",
                        "%d/%b/%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"
                    ]
                    for fmt in formatos:
                        try:
                            data_lanc = datetime.strptime(data_str, fmt).date()
                            break
                        except ValueError:
                            continue

                if data_lanc is None:
                    print(f"  Data nao reconhecida: '{data_str}'")

            # Verifica se o jogo ja existe
            existing = db.query(Jogo).filter(Jogo.steam_id == dados_jogo["id"]).first()

            if existing:
                # Atualiza jogo existente
                existing.nome = dados_jogo["nome"]
                existing.desenvolvedor = dados_jogo.get("desenvolvedor", "N/A")
                existing.publicadora = dados_jogo.get("publicadora", "N/A")
                existing.genero = dados_jogo.get("genero", "N/A")
                existing.data_lancamento = data_lanc
                existing.descricao_steam = dados_jogo.get("descricao", "")
                existing.url_imagem_steam = dados_jogo.get("url_imagem", "")
                existing.url_steam = dados_jogo["url"]
                existing.preco_base_steam = preco_num
                existing.updated_at = datetime.now()

                atualizados += 1
                print(f"Atualizado: {dados_jogo['nome']}")
                print(f"  {data_lanc or 'N/A'} | R$ {preco_num:.2f}")
                print(f"  {dados_jogo.get('desenvolvedor', 'N/A')} | "
                      f"{dados_jogo.get('genero', 'N/A')}")
            else:
                # Insere novo jogo
                novo_jogo = Jogo(
                    steam_id=dados_jogo["id"],
                    nome=dados_jogo["nome"],
                    desenvolvedor=dados_jogo.get("desenvolvedor", "N/A"),
                    publicadora=dados_jogo.get("publicadora", "N/A"),
                    genero=dados_jogo.get("genero", "N/A"),
                    data_lancamento=data_lanc,
                    descricao_steam=dados_jogo.get("descricao", ""),
                    url_imagem_steam=dados_jogo.get("url_imagem", ""),
                    url_steam=dados_jogo["url"],
                    preco_base_steam=preco_num,
                )
                db.add(novo_jogo)
                adicionados += 1
                print(f"Adicionado: {dados_jogo['nome']}")
                print(f"  {data_lanc or 'N/A'} | R$ {preco_num:.2f}")
                print(f"  {dados_jogo.get('desenvolvedor', 'N/A')} | "
                      f"{dados_jogo.get('genero', 'N/A')}")

        db.commit()

        print("\n" + "=" * 50)
        print("RESUMO")
        print("=" * 50)
        print(f"  Adicionados: {adicionados}")
        print(f"  Atualizados: {atualizados}")
        print(f"  Total: {len(dados['jogos'])} jogos processados")

    except Exception as erro:
        db.rollback()
        print(f"Erro ao salvar: {erro}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(salvar_jogos_steam())