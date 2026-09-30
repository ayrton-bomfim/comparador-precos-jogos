"""
Piloto da coleta histórica Epic via EGDATA.

Grava no PostgreSQL somente os três jogos usados na validação:
    - The Witcher 3
    - Hades
    - Destiny 2

A regra de histórico NÃO cria registro apenas pela mudança da data de coleta.
"""

import asyncio
from datetime import datetime

from sqlalchemy import and_

from ...banco_dados import SessionLocal
from ...modelos import Jogo, EpicOferta, HistoricoPreco
from ...servicos.egdata import buscar_preco_atual
from ...scripts.historico.coletar_historico_epic_egdata import (
    dados_relevantes_mudaram,
)

OFERTAS_TESTE = {
    "The Witcher 3": "9064fdd49de04718abe631788ad5a759",
    "Hades": "2ae6edb2223c4f8c97e9839b5b6497bb",
    "Destiny 2": "ee334739f5044a61be45528bd1d6b672",
}


async def main():
    print("=" * 70)
    print("PILOTO — HISTÓRICO EPIC COM EGDATA")
    print("=" * 70)
    print("Somente as ofertas de teste: The Witcher 3, Hades e Destiny 2")
    print("Nenhum outro jogo será processado.")
    print()

    db = SessionLocal()

    try:
        resultados = []

        for nome_teste, offer_id in OFERTAS_TESTE.items():
            resultado = (
                db.query(Jogo, EpicOferta)
                .join(
                    EpicOferta,
                    EpicOferta.jogo_id == Jogo.id,
                )
                .filter(
                    and_(
                        EpicOferta.offer_id == offer_id,
                        EpicOferta.ativo.is_(True),
                    )
                )
                .first()
            )

            if resultado is None:
                print(
                    f"ATENÇÃO: oferta não encontrada no banco: "
                    f"{nome_teste} | offerId={offer_id}"
                )
            else:
                resultados.append(resultado)

        print()

        if not resultados:
            print("Nenhuma das ofertas de teste foi encontrada.")
            return

        for jogo, oferta in resultados:
            print("-" * 70)
            print(f"Jogo: {jogo.nome}")
            print(f"Offer ID: {oferta.offer_id}")

            try:
                dados = buscar_preco_atual(oferta.offer_id)

                ultimo = (
                    db.query(HistoricoPreco)
                    .filter(
                        and_(
                            HistoricoPreco.jogo_id == jogo.id,
                            HistoricoPreco.plataforma == "Epic",
                        )
                    )
                    .order_by(HistoricoPreco.data_coleta.desc())
                    .first()
                )

                deve_criar, motivo = dados_relevantes_mudaram(
                    ultimo,
                    dados,
                )

                print(
                    f"Atual: R$ {dados['preco']:.2f} | "
                    f"Original: R$ {dados['preco_sem_desconto']:.2f} | "
                    f"Desconto: {dados['desconto']}%"
                )
                print(
                    f"Promoção: {dados['promocao_nome'] or 'Nenhuma'}"
                )

                if dados["promocao_inicio"] or dados["promocao_fim"]:
                    print(
                        f"Período: "
                        f"{dados['promocao_inicio'] or 'N/A'} -> "
                        f"{dados['promocao_fim'] or 'N/A'}"
                    )

                if not deve_criar:
                    print("AÇÃO: ignorado — sem mudança relevante.")
                    continue

                agora = datetime.now()

                historico = HistoricoPreco(
                    jogo_id=jogo.id,
                    nome_jogo=jogo.nome,
                    plataforma="Epic",
                    preco_atual=dados["preco"],
                    preco_sem_desconto=dados["preco_sem_desconto"],
                    desconto=dados["desconto"],
                    data_coleta=agora,
                    promocao_id=dados["promocao_id"],
                    promocao_nome=dados["promocao_nome"],
                    promocao_inicio=dados["promocao_inicio"],
                    promocao_fim=dados["promocao_fim"],
                )

                db.add(historico)

                if dados["preco_sem_desconto"] is not None:
                    jogo.preco_base_epic = dados["preco_sem_desconto"]

                db.commit()

                print(f"AÇÃO: registro criado — {motivo}")

            except Exception as erro:
                db.rollback()
                print(f"ERRO: {erro}")

        print()
        print("=" * 70)
        print("PILOTO CONCLUÍDO")
        print("=" * 70)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
