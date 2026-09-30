"""
Serviço mínimo para consulta de preço atual da EGDATA.

Responsabilidade:
    - consultar o endpoint de preço atual;
    - normalizar preços de centavos para reais;
    - identificar a promoção atualmente aplicada;
    - retornar o início/fim da promoção quando a fonte informar.

Não altera banco de dados.
"""

from datetime import datetime, timezone

import requests


EGDATA_PRECO_URL = "https://api.egdata.app/offers/{offer_id}/price"


def converter_preco(valor):
    """Converte centavos para reais."""
    if valor is None:
        return None
    return round(float(valor) / 100, 2)


def converter_data(data_iso):
    """Converte ISO 8601 para datetime com timezone."""
    if not data_iso:
        return None

    try:
        return datetime.fromisoformat(
            data_iso.replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        return None


def calcular_desconto(original, atual):
    """Calcula o desconto efetivo quando a API não informar um percentual."""
    if original is None or atual is None or original <= 0:
        return 0

    desconto = round(((original - atual) / original) * 100)
    return max(0, min(100, desconto))


def _encontrar_promocao(applied_rules, offer_id):
    """
    Procura uma regra promocional ativa aplicável à oferta.

    Retorna:
        {
            "inicio": datetime | None,
            "fim": datetime | None,
            "desconto": int | None,
            "id": str | None,
            "nome": str | None,
        }
    """
    if not isinstance(applied_rules, list):
        return {
            "inicio": None,
            "fim": None,
            "desconto": None,
            "id": None,
            "nome": None,
        }

    candidatos = []

    for regra in applied_rules:
        if not isinstance(regra, dict):
            continue

        if regra.get("promotionStatus") not in (None, "ACTIVE"):
            continue

        promotion = regra.get("promotionSetting") or {}
        discount_setting = regra.get("discountSetting") or {}

        ofertas = promotion.get("discountOffers") or []
        ids = {
            item.get("offerId")
            for item in ofertas
            if isinstance(item, dict) and item.get("offerId")
        }

        if ids and offer_id not in ids:
            continue

        desconto = discount_setting.get("discountPercentage")

        candidatos.append(
            {
                "inicio": converter_data(regra.get("startDate")),
                "fim": converter_data(regra.get("endDate")),
                "desconto": int(desconto) if desconto is not None else None,
                "id": regra.get("id"),
                "nome": regra.get("name"),
            }
        )

    if not candidatos:
        return {
            "inicio": None,
            "fim": None,
            "desconto": None,
            "id": None,
            "nome": None,
        }

    # Quando houver mais de uma regra aplicável, prioriza a que
    # fornece percentual explícito; em empate, mantém a primeira.
    candidatos.sort(
        key=lambda item: (
            item["desconto"] is None,
            item["inicio"] is None,
        )
    )

    return candidatos[0]


def buscar_preco_atual(offer_id, country="BR"):
    """
    Consulta o preço atual da oferta na EGDATA.

    Retorna uma estrutura já normalizada para a aplicação:
        {
            "offer_id": str,
            "preco": float,
            "preco_sem_desconto": float,
            "desconto": int,
            "promocao_inicio": datetime | None,
            "promocao_fim": datetime | None,
            "promocao_id": str | None,
            "promocao_nome": str | None,
            "updated_at": datetime | None,
        }
    """
    url = EGDATA_PRECO_URL.format(offer_id=offer_id)

    resposta = requests.get(
        url,
        params={"country": country},
        timeout=30,
    )
    resposta.raise_for_status()

    dados = resposta.json()

    preco = dados.get("price") or {}

    original = converter_preco(preco.get("originalPrice"))
    atual = converter_preco(preco.get("discountPrice"))

    if original is None or atual is None:
        raise ValueError("A EGDATA não retornou preços válidos.")

    promocao = _encontrar_promocao(
        dados.get("appliedRules"),
        offer_id,
    )

    # O desconto apresentado ao histórico deve representar a diferença
    # efetiva entre o preço original e o preço atual.
    #
    # A EGDATA também pode retornar um `discountPercentage` dentro de
    # `appliedRules`, mas o valor dessa regra pode não corresponder ao
    # desconto efetivamente aplicado ao preço final. O caso do Watch Dogs 2
    # demonstrou essa divergência: os preços indicavam 95%, enquanto a regra
    # retornava 5%.
    #
    # Por isso, o percentual usado pela aplicação é sempre calculado a partir
    # dos próprios preços.
    desconto = calcular_desconto(original, atual)

    return {
        "offer_id": dados.get("offerId") or offer_id,
        "preco": atual,
        "preco_sem_desconto": original,
        "desconto": int(desconto or 0),
        "promocao_inicio": promocao["inicio"],
        "promocao_fim": promocao["fim"],
        "promocao_id": promocao["id"],
        "promocao_nome": promocao["nome"],
        "updated_at": converter_data(dados.get("updatedAt")),
    }
