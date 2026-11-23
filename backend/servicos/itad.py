"""
Consulta de preços atuais pela API do IsThereAnyDeal (ITAD).

Usado como fonte principal dos preços da Epic Games Store no Brasil:
- /lookup/id/shop/16/v1 converte offer IDs da Epic em IDs de jogo do ITAD
  (até 500 por requisição);
- /games/prices/v3 devolve o preço atual por loja (até 200 jogos por
  requisição).

Todo o catálogo Epic (~6,5 mil ofertas) é resolvido em cerca de 50
requisições. O limite informado pelo ITAD é de 1.000 requisições a cada
5 minutos.

Não altera o banco de dados.
"""

import os
import time
from datetime import datetime

import requests

ITAD_BASE = "https://api.isthereanydeal.com"
SHOP_EPIC = 16
SHOP_STEAM = 61
LOTE_LOOKUP = 500
LOTE_PRECOS = 200
MAX_TENTATIVAS = 4


def _chave():
    chave = os.getenv("ITAD_API_KEY")
    if not chave:
        raise RuntimeError("ITAD_API_KEY não encontrada no .env.")
    return chave


def _post(sessao, caminho, params, corpo):
    espera = 5.0
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        resposta = sessao.post(f"{ITAD_BASE}{caminho}", params=params, json=corpo, timeout=60)
        if resposta.status_code == 429 or resposta.status_code >= 500:
            if tentativa == MAX_TENTATIVAS:
                resposta.raise_for_status()
            try:
                espera = max(espera, float(resposta.headers.get("Retry-After")))
            except (TypeError, ValueError):
                pass
            time.sleep(min(espera, 120))
            espera *= 2
            continue
        resposta.raise_for_status()
        return resposta.json()
    raise RuntimeError(f"ITAD {caminho}: tentativas esgotadas")


def _data(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def mapear_ids_loja(ids_loja, shop_id):
    """{id na loja: id ITAD ou None}."""
    sessao = requests.Session()
    params = {"key": _chave()}
    ids = list(dict.fromkeys(str(i) for i in ids_loja if i))
    mapa = {}
    for inicio in range(0, len(ids), LOTE_LOOKUP):
        mapa.update(_post(sessao, f"/lookup/id/shop/{shop_id}/v1", params, ids[inicio:inicio + LOTE_LOOKUP]))
    return mapa


def ids_loja_por_itad(itad_ids, shop_id):
    """{id ITAD: [ids na loja]} — caminho inverso de mapear_ids_loja.

    Para a Steam os ids vêm como "app/123" (jogo) ou "sub/456" (pacote).
    """
    sessao = requests.Session()
    params = {"key": _chave()}
    ids = list(dict.fromkeys(i for i in itad_ids if i))
    mapa = {}
    for inicio in range(0, len(ids), LOTE_LOOKUP):
        resposta = _post(sessao, f"/lookup/shop/{shop_id}/id/v1", params, ids[inicio:inicio + LOTE_LOOKUP])
        mapa.update({chave: valor or [] for chave, valor in resposta.items()})
    return mapa


def buscar_precos_loja(itad_ids, shop_id, country="BR"):
    """{id ITAD: dados normalizados} com o preço atual na loja informada.

    Jogos que a loja não vende no país simplesmente não aparecem.
    """
    sessao = requests.Session()
    params = {
        "key": _chave(),
        "country": country,
        "shops": str(shop_id),
        "deals": "false",
        "vouchers": "false",
    }
    ids = list(dict.fromkeys(itad_ids))
    precos = {}
    for inicio in range(0, len(ids), LOTE_PRECOS):
        for jogo in _post(sessao, "/games/prices/v3", params, ids[inicio:inicio + LOTE_PRECOS]):
            oferta = next(
                (d for d in jogo.get("deals") or [] if (d.get("shop") or {}).get("id") == shop_id),
                None,
            )
            if not oferta:
                continue
            atual = (oferta.get("price") or {}).get("amount")
            original = (oferta.get("regular") or {}).get("amount")
            if atual is None or original is None:
                continue
            atual = round(float(atual), 2)
            original = round(float(original), 2)
            desconto = 0
            if original > 0:
                desconto = max(0, min(100, round((original - atual) / original * 100)))
            precos[jogo["id"]] = {
                "preco": atual,
                "preco_sem_desconto": original,
                "desconto": int(desconto),
                "promocao_id": None,
                "promocao_nome": None,
                "promocao_inicio": None,
                "promocao_fim": _data(oferta.get("expiry")) if desconto else None,
                "updated_at": _data(oferta.get("timestamp")),
                "fonte": "ITAD",
            }
    return precos


def buscar_precos_epic(offer_ids, country="BR"):
    """Preços atuais da Epic por offer ID.

    Retorna (precos, sem_mapeamento, sem_preco):
        precos: {offer_id: dados normalizados}
        sem_mapeamento: offers que o ITAD não reconhece ou que compartilham o
            mesmo jogo ITAD com outra oferta (ex.: edição e jogo base). Nesses
            casos o preço do ITAD pode ser o de outra edição, então a oferta
            deve ser consultada em outra fonte.
        sem_preco: offers reconhecidas, mas sem preço da Epic no país.
    """
    mapa = mapear_ids_loja(offer_ids, SHOP_EPIC)

    ofertas_por_jogo = {}
    for offer_id, itad_id in mapa.items():
        if itad_id:
            ofertas_por_jogo.setdefault(itad_id, []).append(offer_id)

    unicos = {itad_id: ofertas[0] for itad_id, ofertas in ofertas_por_jogo.items() if len(ofertas) == 1}
    sem_mapeamento = {
        str(offer_id) for offer_id in offer_ids
        if not mapa.get(str(offer_id)) or mapa[str(offer_id)] not in unicos
    }

    precos_jogo = buscar_precos_loja(list(unicos), SHOP_EPIC, country)

    precos = {}
    sem_preco = set()
    for itad_id, offer_id in unicos.items():
        dados = precos_jogo.get(itad_id)
        if dados is None:
            sem_preco.add(offer_id)
        else:
            precos[offer_id] = {**dados, "offer_id": offer_id, "itad_id": itad_id}

    return precos, sem_mapeamento, sem_preco
