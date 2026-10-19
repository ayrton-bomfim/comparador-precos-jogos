# -*- coding: utf-8 -*-
"""
Diagnóstico somente de leitura para o GTA San Andreas Definitive Edition na Epic.

O que faz:
- Consulta a oferta EGDATA informada.
- Lê o preço-base e os últimos históricos Epic do jogo no PostgreSQL.
- Aplica a regra local do coletor para classificar o preço retornado.
- Não faz INSERT, UPDATE, DELETE, commit ou coleta do catálogo.

Execute na pasta do projeto onde os imports backend funcionam:
    python diagnostico_gta_epic_somente_leitura.py
"""

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import requests

JOGO_ID = 58081
OFFER_ID = "996f775f25dc4930bea90f4e51199689"
ENDPOINT = f"https://api.egdata.app/offers/{OFFER_ID}/price"
PAIS = "BR"

# Regra copiada da versão do coletor em análise, para o diagnóstico ser
# independente do caminho de importação dos módulos do projeto.
IDADE_MAXIMA_PRECO_ZERO_DIAS = 30


def preco_zero_suspeito(preco, original, promocao_id, promocao_nome, updated_at):
    """Replica a regra de rejeição do coletor para o resultado da API."""
    try:
        preco = float(preco)
        original = float(original)
    except (TypeError, ValueError):
        return False, "preço ausente ou não numérico; regra 0/0 não aplicada"

    if preco != 0 or original != 0:
        return False, "preço não é 0/0"

    if promocao_id or promocao_nome:
        return False, "promoção identificada"

    if updated_at is None:
        return True, "preço 0/0 sem data de atualização"

    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)

    idade = datetime.now(timezone.utc) - updated_at
    if idade.total_seconds() > IDADE_MAXIMA_PRECO_ZERO_DIAS * 86400:
        return True, f"preço 0/0 com atualização antiga ({idade.days} dias)"

    return False, f"preço 0/0 com atualização recente ({idade.days} dias)"


def parse_data(valor):
    if not valor or not isinstance(valor, str):
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


def consultar_egdata():
    print("1) CONSULTA EGDATA")
    print(f"Endpoint: {ENDPOINT}?country={PAIS}")
    resposta = requests.get(
        ENDPOINT,
        params={"country": PAIS},
        timeout=25,
        headers={"Accept": "application/json", "User-Agent": "DESCTRL-readonly-diagnostic/1.0"},
    )
    print(f"HTTP: {resposta.status_code}")
    resposta.raise_for_status()
    payload = resposta.json()

    # Compatibilidade com as estruturas observadas: price wrapper ou objeto direto.
    bloco = payload.get("price") if isinstance(payload, dict) else None
    if not isinstance(bloco, dict):
        bloco = payload if isinstance(payload, dict) else {}

    price = bloco.get("price") if isinstance(bloco.get("price"), dict) else bloco
    original = price.get("originalPrice", bloco.get("originalPrice"))
    atual = price.get("discountPrice", bloco.get("discountPrice"))
    updated_at = parse_data(bloco.get("updatedAt") or payload.get("updatedAt") if isinstance(payload, dict) else None)

    promo_id = bloco.get("promotionId") or bloco.get("promotion_id")
    promo_nome = bloco.get("promotionName") or bloco.get("promotion_name")
    regras = bloco.get("appliedRules")
    if isinstance(regras, list) and regras:
        promo_id = promo_id or "appliedRules-presente"

    suspeito, motivo = preco_zero_suspeito(atual / 100 if isinstance(atual, (int, float)) else atual,
                                           original / 100 if isinstance(original, (int, float)) else original,
                                           promo_id, promo_nome, updated_at)

    # Valores são impressos em centavos e reais para deixar a conversão explícita.
    def em_reais(v):
        if v is None:
            return "não informado"
        return f"R$ {float(v) / 100:.2f}" if isinstance(v, (int, float)) else str(v)

    print(f"Preço atual bruto: {atual!r} | convertido: {em_reais(atual)}")
    print(f"Preço original bruto: {original!r} | convertido: {em_reais(original)}")
    print(f"Atualizado em: {updated_at.isoformat() if updated_at else 'não informado/inválido'}")
    print(f"Identificador de promoção: {promo_id or 'nenhum'}")
    print(f"Nome de promoção: {promo_nome or 'nenhum'}")
    print(f"Regra 0/0: {'REJEITAR' if suspeito else 'NÃO REJEITAR'} ({motivo})")
    return {
        "http": resposta.status_code,
        "atual_bruto": atual,
        "original_bruto": original,
        "updated_at": updated_at.isoformat() if updated_at else None,
        "promo_id": promo_id,
        "promo_nome": promo_nome,
        "suspeito": suspeito,
        "motivo": motivo,
        "payload": payload,
    }


def consultar_banco_somente_leitura():
    print("\n2) POSTGRESQL — SOMENTE LEITURA")
    # Descobre a raiz do projeto a partir da localização deste script.
    # Isso permite executar o arquivo tanto da raiz quanto de backend/scripts/historico.
    import sys

    script_path = Path(__file__).resolve()
    projeto_root = next(
        (pai for pai in script_path.parents if (pai / "backend").is_dir()),
        None,
    )
    if projeto_root is None:
        raise RuntimeError(
            "Não encontrei a raiz do projeto (pasta que contém 'backend'). "
            "Coloque este script dentro de backend/scripts/historico."
        )

    if str(projeto_root) not in sys.path:
        sys.path.insert(0, str(projeto_root))

    # O projeto pode expor os módulos como pacote 'backend' ou como módulos
    # diretamente dentro da pasta backend, conforme a estrutura de execução.
    from sqlalchemy import text

    print(f"Raiz detectada: {projeto_root}")
    print(f"Pasta backend existe: {(projeto_root / 'backend').is_dir()}")
    print(f"banco_dados.py existe: {(projeto_root / 'backend' / 'banco_dados.py').is_file()}")
    print(f"sys.path[0]: {sys.path[0]}")

    try:
        from backend.banco_dados import SessionLocal
    except ModuleNotFoundError as erro_import:
        # Não tentar um segundo import às cegas: se banco_dados.py ou uma das
        # suas dependências internas falhar, a mensagem original é mais útil.
        raise RuntimeError(
            "Não foi possível importar backend.banco_dados.SessionLocal. "
            f"Erro original: {type(erro_import).__name__}: {erro_import}. "
            "Confira se backend/banco_dados.py existe e se os imports internos "
            "desse arquivo usam o mesmo padrão de pacote do projeto."
        ) from erro_import

    db = SessionLocal()
    try:
        # Transação explicitamente read-only no PostgreSQL. Sem commit.
        db.execute(text("SET TRANSACTION READ ONLY"))

        jogo = db.execute(
            text("""
                SELECT id, nome, epic_id, url_epic, preco_base_epic
                FROM jogos
                WHERE id = :jogo_id
            """),
            {"jogo_id": JOGO_ID},
        ).mappings().first()

        if not jogo:
            print(f"Jogo id={JOGO_ID} não encontrado.")
            return {"jogo": None, "historicos": []}

        print(f"Jogo: id={jogo['id']} | nome={jogo['nome']}")
        print(f"epic_id: {jogo['epic_id']}")
        print(f"url_epic: {jogo['url_epic']}")
        print(f"preco_base_epic: {jogo['preco_base_epic']!r}")

        ofertas = db.execute(
            text("""
                SELECT id, offer_id, ativo
                FROM epic_ofertas
                WHERE jogo_id = :jogo_id
                ORDER BY id
            """),
            {"jogo_id": JOGO_ID},
        ).mappings().all()
        print(f"Ofertas Epic vinculadas: {len(ofertas)}")
        for oferta in ofertas:
            print(f"  oferta_id={oferta['id']} | offer_id={oferta['offer_id']} | ativo={oferta['ativo']}")

        historicos = db.execute(
            text("""
                SELECT id, plataforma, preco_atual, preco_sem_desconto,
                       desconto, data_coleta, promocao_id, promocao_nome
                FROM historico_precos
                WHERE jogo_id = :jogo_id AND plataforma = 'Epic'
                ORDER BY id DESC
                LIMIT 10
            """),
            {"jogo_id": JOGO_ID},
        ).mappings().all()

        print(f"Últimos históricos Epic: {len(historicos)}")
        for h in historicos:
            print(
                f"  histórico={h['id']} | atual={h['preco_atual']} | "
                f"original={h['preco_sem_desconto']} | desconto={h['desconto']}% | "
                f"coleta={h['data_coleta']} | promo_id={h['promocao_id']} | "
                f"promo_nome={h['promocao_nome']}"
            )

        return {
            "jogo": dict(jogo),
            "ofertas": [dict(x) for x in ofertas],
            "historicos": [dict(x) for x in historicos],
        }
    finally:
        db.close()


def main():
    print("=" * 72)
    print("DIAGNÓSTICO GTA / EPIC — SOMENTE LEITURA")
    print("Sem INSERT, UPDATE, DELETE, commit ou coleta completa.")
    print("=" * 72)

    try:
        egdata = consultar_egdata()
    except Exception as exc:
        print(f"\nFalha na consulta EGDATA: {type(exc).__name__}: {exc}")
        egdata = None

    try:
        banco = consultar_banco_somente_leitura()
    except Exception as exc:
        print(f"\nFalha na consulta ao PostgreSQL: {type(exc).__name__}: {exc}")
        banco = None

    print("\n3) RESUMO")
    if egdata:
        print(f"EGDATA: HTTP {egdata['http']} | suspeito={egdata['suspeito']} | {egdata['motivo']}")
    if banco:
        jogo = banco.get("jogo")
        if jogo:
            print(f"Banco: preço-base Epic={jogo.get('preco_base_epic')!r}; históricos Epic={len(banco.get('historicos', []))}")
    print("\nDiagnóstico concluído. Nenhuma gravação foi solicitada pelo script.")


if __name__ == "__main__":
    main()
