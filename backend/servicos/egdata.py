"""
Serviço mínimo para consulta de preço atual da EGDATA.

Responsabilidade:
    - consultar o endpoint de preço atual;
    - normalizar preços de centavos para reais;
    - identificar a promoção atualmente aplicada;
    - retornar o início/fim da promoção quando a fonte informar.

Não altera banco de dados.
"""

from datetime import datetime

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


def normalizar_resposta_preco(dados, offer_id):
    """Converte a resposta de /offers/{id}/price no contrato da aplicação.

    Retorna None quando a resposta não traz preço original e atual.
    """
    preco = (dados or {}).get("price") or {}

    original = converter_preco(preco.get("originalPrice"))
    atual = converter_preco(preco.get("discountPrice"))

    if original is None or atual is None:
        return None

    promocao = _encontrar_promocao(dados.get("appliedRules"), offer_id)

    # O percentual é sempre calculado a partir dos próprios preços (ver
    # comentário em buscar_preco_atual sobre o caso Watch Dogs 2).
    return {
        "offer_id": dados.get("offerId") or offer_id,
        "preco": atual,
        "preco_sem_desconto": original,
        "desconto": int(calcular_desconto(original, atual) or 0),
        "promocao_inicio": promocao["inicio"],
        "promocao_fim": promocao["fim"],
        "promocao_id": promocao["id"],
        "promocao_nome": promocao["nome"],
        "updated_at": converter_data(dados.get("updatedAt")),
    }


# Consulta por oferta. A EGDATA anuncia limite de 1.200 requisições por
# minuto, mas aplica "tarpit" a consultas em sequência (resposta 204 após
# ~5s, cabeçalho X-Egdata-Mitigation). Por isso ela é só a fonte reserva da
# Epic, consultada uma oferta por vez e em volume limitado; o 204 se resolve
# tentando de novo depois de alguns segundos.
EGDATA_WORKERS = 1
EGDATA_MAX_TENTATIVAS = 4
EGDATA_ESPERA_INICIAL = 3.0


def buscar_precos_por_oferta(offer_ids, country="BR", workers=EGDATA_WORKERS, progresso=None):
    """Consulta o preço de várias ofertas em paralelo controlado.

    Retorna (precos, sem_preco, falhas):
        precos: {offer_id: dados normalizados}
        sem_preco: offer_ids que a EGDATA respondeu sem preço válido (ou 404)
        falhas: {offer_id: motivo} para erros que persistiram após as tentativas
    """
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    sessao = requests.Session()
    sessao.headers.update({"Accept": "application/json", "User-Agent": "DESCTRL-Coleta/1.0"})

    def consultar(offer_id):
        espera = EGDATA_ESPERA_INICIAL
        motivo = None
        for _ in range(EGDATA_MAX_TENTATIVAS):
            try:
                resposta = sessao.get(
                    EGDATA_PRECO_URL.format(offer_id=offer_id),
                    params={"country": country},
                    timeout=30,
                )
            except requests.RequestException as erro:
                motivo = type(erro).__name__
            else:
                if resposta.status_code == 200:
                    try:
                        return offer_id, "ok", normalizar_resposta_preco(resposta.json(), offer_id)
                    except ValueError:
                        motivo = "JSON inválido"
                elif resposta.status_code == 404:
                    return offer_id, "ok", None
                else:
                    motivo = f"HTTP {resposta.status_code}"
                    try:
                        espera = max(espera, float(resposta.headers.get("Retry-After")))
                    except (TypeError, ValueError):
                        pass
            time.sleep(espera)
            espera = min(espera * 2, 30.0)
        return offer_id, "falha", motivo

    precos, sem_preco, falhas = {}, set(), {}
    ids = list(dict.fromkeys(str(o) for o in offer_ids if o))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futuros = [executor.submit(consultar, offer_id) for offer_id in ids]
        for concluidos, futuro in enumerate(as_completed(futuros), 1):
            offer_id, situacao, resultado = futuro.result()
            if situacao == "falha":
                falhas[offer_id] = resultado
            elif resultado is None:
                sem_preco.add(offer_id)
            else:
                precos[offer_id] = resultado
            if progresso:
                progresso(concluidos, len(ids), len(falhas))

    return precos, sem_preco, falhas


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
