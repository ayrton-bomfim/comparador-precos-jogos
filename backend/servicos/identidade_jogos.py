"""
Regras para reconhecer o mesmo jogo em lojas diferentes.

A evidência principal é o ID de jogo do IsThereAnyDeal (ITAD), que é o mesmo
para todas as lojas. Como o ITAD erra em títulos genéricos (ex.: ofertas
chamadas só "Deluxe Edition"), o vínculo só é aceito automaticamente quando
os nomes também são parecidos.
"""

import re
import unicodedata
from difflib import SequenceMatcher

from .itad import SHOP_EPIC, SHOP_STEAM, ids_loja_por_itad, mapear_ids_loja

LIMIAR_NOME = 0.9


def chave_nome(nome):
    """Nome sem acentos, símbolos e pontuação, para comparação.

    ™/®/© são removidos antes da normalização (senão "™" vira "tm") e "&"
    equivale a "and" ("Bread & Fred" = "Bread and Fred").
    """
    texto = re.sub(r"[™®©]", "", nome or "").replace("&", " and ")
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", texto)


def similaridade(nome_a, nome_b):
    a, b = chave_nome(nome_a), chave_nome(nome_b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def nomes_compativeis(nome_a, nome_b):
    return similaridade(nome_a, nome_b) >= LIMIAR_NOME


def appids_steam_das_ofertas_epic(offer_ids):
    """{offer_id Epic: (itad_id, [AppIDs Steam])} pelo ITAD.

    Ofertas que o ITAD não reconhece ficam de fora. Só AppIDs de jogo
    ("app/"), nunca pacotes ("sub/").
    """
    offer_para_itad = {o: i for o, i in mapear_ids_loja(offer_ids, SHOP_EPIC).items() if i}
    steam_por_itad = ids_loja_por_itad(sorted(set(offer_para_itad.values())), SHOP_STEAM)
    return {
        offer_id: (
            itad_id,
            [i.split("/", 1)[1] for i in steam_por_itad.get(itad_id, []) if i.startswith("app/")],
        )
        for offer_id, itad_id in offer_para_itad.items()
    }
