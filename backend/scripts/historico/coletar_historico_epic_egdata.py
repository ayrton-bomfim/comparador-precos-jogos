"""
Coleta histórica da Epic usando EGDATA para o preço atual.

Regras:
    - usa EpicOferta.offer_id já cadastrado;
    - consulta /offers/{offer_id}/price?country=BR;
    - registra preço, preço original, desconto e dados da promoção;
    - NÃO cria registro apenas porque a data da coleta mudou;
    - cria novo histórico quando algum dado relevante do estado do preço/promoção mudar.
"""

import asyncio
from datetime import datetime

from sqlalchemy import and_

from ...banco_dados import SessionLocal
from ...modelos import Jogo, EpicOferta, HistoricoPreco
from ...servicos.egdata import buscar_preco_atual


def dados_relevantes_mudaram(ultimo, dados):
    """Retorna (True, motivo) quando o estado atual difere do último registro."""
    if ultimo is None:
        return True, "Primeiro registro na Epic via EGDATA"

    preco_atual = round(float(dados["preco"]), 2)
    preco_anterior = round(float(ultimo.preco_atual), 2)

    if abs(preco_atual - preco_anterior) > 0.01:
        return (
            True,
            f"Preço mudou (R$ {preco_anterior:.2f} -> R$ {preco_atual:.2f})",
        )

    original_atual = (
        round(float(dados["preco_sem_desconto"]), 2)
        if dados["preco_sem_desconto"] is not None
        else None
    )
    original_anterior = (
        round(float(ultimo.preco_sem_desconto), 2)
        if ultimo.preco_sem_desconto is not None
        else None
    )

    if original_atual != original_anterior:
        return True, "Preço original mudou"

    desconto_atual = int(dados["desconto"] or 0)
    desconto_anterior = int(ultimo.desconto or 0)

    if desconto_atual != desconto_anterior:
        return (
            True,
            f"Desconto mudou ({desconto_anterior}% -> {desconto_atual}%)",
        )

    comparacoes_promocao = (
        ("promocao_id", "Identificador da promoção mudou"),
        ("promocao_nome", "Nome da promoção mudou"),
        ("promocao_inicio", "Início da promoção mudou"),
        ("promocao_fim", "Fim da promoção mudou"),
    )

    for campo, motivo in comparacoes_promocao:
        valor_anterior = getattr(ultimo, campo, None)
        valor_atual = dados.get(campo)

        if valor_anterior != valor_atual:
            return True, motivo

    return False, ""


async def coletar_historico_epic_egdata():
    print("=" * 70)
    print("COLETANDO HISTÓRICO EPIC — EGDATA")
    print("=" * 70)
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print()

    db = SessionLocal()

    try:
        jogos_ofertas = (
            db.query(Jogo, EpicOferta)
            .join(
                EpicOferta,
                EpicOferta.jogo_id == Jogo.id,
            )
            .filter(
                and_(
                    EpicOferta.ativo.is_(True),
                    Jogo.epic_id.isnot(None),
                    Jogo.epic_id != "EXCLUSIVO_STEAM",
                )
            )
            .all()
        )

        print(f"{len(jogos_ofertas)} jogos com oferta Epic cadastrada")

        novos = 0
        ignorados = 0
        erros = 0

        for indice, (jogo, oferta) in enumerate(jogos_ofertas, 1):
            print(
                f"[{indice}/{len(jogos_ofertas)}] "
                f"{jogo.nome} | offerId={oferta.offer_id}"
            )

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

                agora = datetime.now()

                deve_criar, motivo = dados_relevantes_mudaram(
                    ultimo,
                    dados,
                )

                if not deve_criar:
                    print("  Sem mudança relevante.")
                    ignorados += 1
                    await asyncio.sleep(0.15)
                    continue

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

                print(f"  {motivo}")
                print(
                    f"  Preço: R$ {dados['preco']:.2f} | "
                    f"Original: R$ {dados['preco_sem_desconto']:.2f} | "
                    f"Desconto: {dados['desconto']}%"
                )

                if dados["promocao_id"] or dados["promocao_nome"]:
                    print(
                        f"  Promoção: {dados['promocao_nome'] or 'N/A'} "
                        f"(ID: {dados['promocao_id'] or 'N/A'})"
                    )

                if dados["promocao_inicio"] or dados["promocao_fim"]:
                    inicio = (
                        dados["promocao_inicio"].isoformat()
                        if dados["promocao_inicio"]
                        else "N/A"
                    )
                    fim = (
                        dados["promocao_fim"].isoformat()
                        if dados["promocao_fim"]
                        else "N/A"
                    )
                    print(f"  Período: {inicio} -> {fim}")

                novos += 1
                await asyncio.sleep(0.25)

            except Exception as erro:
                db.rollback()
                erros += 1
                print(f"  ERRO: {erro}")

        print()
        print("=" * 70)
        print("RESUMO")
        print("=" * 70)
        print(f"  Novos registros: {novos}")
        print(f"  Ignorados: {ignorados}")
        print(f"  Erros: {erros}")
        print(f"  Total: {len(jogos_ofertas)}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(coletar_historico_epic_egdata())
