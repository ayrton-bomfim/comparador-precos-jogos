# -*- coding: utf-8 -*-
"""
Coleta histórica da Epic usando EGDATA.

Esta versão substitui a coleta histórica baseada no Playwright/GraphQL,
mas mantém a mesma função pública `coletar_historico_epic()` para não
quebrar chamadas existentes do projeto/agendador.

Regras do histórico:
    - usa EpicOferta.offer_id;
    - consulta o preço atual na EGDATA;
    - registra preço, preço original, desconto e dados da promoção;
    - NÃO cria registro apenas porque a data da coleta mudou;
    - cria novo registro quando algum dado relevante do estado mudar;
    - mantém um erro isolado por jogo sem interromper a coleta dos demais.

O EpicScraper antigo permanece no projeto e pode continuar sendo usado
como legado/fallback em testes específicos.
"""

import asyncio
from datetime import datetime

from sqlalchemy import and_

from ...banco_dados import SessionLocal
from ...modelos import Jogo, EpicOferta, HistoricoPreco
from ...servicos.egdata import buscar_preco_atual


def _formatar_moeda(valor):
    """Formata um valor numérico em reais no padrão brasileiro."""
    if valor is None:
        return "N/A"
    return f"R$ {float(valor):.2f}".replace(".", ",")


def dados_relevantes_mudaram(ultimo, dados):
    """
    Compara o estado atual da EGDATA com o último estado salvo.

    A data/hora da coleta NÃO participa da comparação.
    """
    if ultimo is None:
        return True, "Primeiro registro na Epic via EGDATA"

    preco_atual = round(float(dados["preco"]), 2)
    preco_anterior = round(float(ultimo.preco_atual), 2)

    if abs(preco_atual - preco_anterior) > 0.01:
        return (
            True,
            f"Preço alterado ({_formatar_moeda(preco_anterior)} -> "
            f"{_formatar_moeda(preco_atual)})",
        )

    original_atual = dados.get("preco_sem_desconto")
    original_atual = (
        round(float(original_atual), 2)
        if original_atual is not None
        else None
    )

    original_anterior = ultimo.preco_sem_desconto
    original_anterior = (
        round(float(original_anterior), 2)
        if original_anterior is not None
        else None
    )

    if original_atual != original_anterior:
        return True, "Preço original alterado"

    desconto_atual = int(dados.get("desconto") or 0)
    desconto_anterior = int(ultimo.desconto or 0)

    if desconto_atual != desconto_anterior:
        return (
            True,
            f"Desconto alterado ({desconto_anterior}% -> {desconto_atual}%)",
        )

    comparacoes_promocao = (
        ("promocao_id", "Identificador da promoção alterado"),
        ("promocao_nome", "Nome da promoção alterado"),
        ("promocao_inicio", "Início da promoção alterado"),
        ("promocao_fim", "Fim da promoção alterado"),
    )

    for campo, motivo in comparacoes_promocao:
        valor_anterior = getattr(ultimo, campo, None)
        valor_atual = dados.get(campo)

        if valor_anterior != valor_atual:
            return True, motivo

    return False, ""


def buscar_ultima_historico_epic(db, jogo_id):
    """Retorna o último estado salvo do jogo na Epic."""
    return (
        db.query(HistoricoPreco)
        .filter(
            and_(
                HistoricoPreco.jogo_id == jogo_id,
                HistoricoPreco.plataforma == "Epic",
            )
        )
        .order_by(HistoricoPreco.id.desc())
        .first()
    )


async def coletar_historico_epic():
    """
    Coleta o estado atual de todos os jogos com oferta Epic ativa.

    A função mantém o mesmo nome do coletor anterior para preservar
    integrações existentes.
    """
    print("=" * 70)
    print("COLETANDO HISTÓRICO DA EPIC — EGDATA")
    print("=" * 70)
    print("Fonte de preço atual: EGDATA")
    print("Histórico: somente alterações relevantes")
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print()

    db = SessionLocal()

    novos = 0
    ignorados = 0
    erros = 0

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
            .order_by(Jogo.id.asc(), EpicOferta.id.asc())
            .all()
        )

        print(
            f"Encontrados {len(jogos_ofertas)} jogos/ofertas ativos na Epic."
        )
        print()

        if not jogos_ofertas:
            print("Nenhuma oferta Epic ativa encontrada.")
            return

        for indice, (jogo, oferta) in enumerate(jogos_ofertas, 1):
            print(
                f"[{indice}/{len(jogos_ofertas)}] "
                f"{jogo.nome}"
            )
            print(f"  Offer ID: {oferta.offer_id}")

            try:
                dados = buscar_preco_atual(oferta.offer_id)

                ultimo = buscar_ultima_historico_epic(
                    db,
                    jogo.id,
                )

                deve_criar, motivo = dados_relevantes_mudaram(
                    ultimo,
                    dados,
                )

                print(
                    f"  Atual: R$ {dados['preco']:.2f} | "
                    f"Original: R$ {dados['preco_sem_desconto']:.2f} | "
                    f"Desconto: {dados['desconto']}%"
                )

                print(
                    f"  Promoção: "
                    f"{dados.get('promocao_nome') or 'Nenhuma'}"
                )

                if (
                    dados.get("promocao_inicio")
                    or dados.get("promocao_fim")
                ):
                    inicio = (
                        dados["promocao_inicio"].isoformat()
                        if dados.get("promocao_inicio")
                        else "N/A"
                    )
                    fim = (
                        dados["promocao_fim"].isoformat()
                        if dados.get("promocao_fim")
                        else "N/A"
                    )
                    print(f"  Período: {inicio} -> {fim}")

                if not deve_criar:
                    print("  Ação: ignorado — nenhuma alteração relevante.")
                    ignorados += 1
                    print()
                    await asyncio.sleep(0.15)
                    continue

                historico = HistoricoPreco(
                    jogo_id=jogo.id,
                    nome_jogo=jogo.nome,
                    plataforma="Epic",
                    preco_atual=dados["preco"],
                    preco_sem_desconto=dados["preco_sem_desconto"],
                    desconto=dados["desconto"],
                    data_coleta=datetime.now(),
                    promocao_id=dados.get("promocao_id"),
                    promocao_nome=dados.get("promocao_nome"),
                    promocao_inicio=dados.get("promocao_inicio"),
                    promocao_fim=dados.get("promocao_fim"),
                )

                db.add(historico)

                if dados["preco_sem_desconto"] is not None:
                    jogo.preco_base_epic = dados["preco_sem_desconto"]

                db.commit()

                print(f"  Ação: registro criado — {motivo}.")
                novos += 1

                await asyncio.sleep(0.25)

            except Exception as erro:
                db.rollback()
                erros += 1
                print(f"  Ação: erro — {erro}")

            print()

        print("=" * 70)
        print("RESUMO DA COLETA DA EPIC — EGDATA")
        print("=" * 70)
        print(f"  Novos registros: {novos}")
        print(f"  Ignorados: {ignorados}")
        print(f"  Erros: {erros}")
        print(f"  Total processado: {len(jogos_ofertas)}")
        print(f"  Fim: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    except Exception as erro:
        db.rollback()
        print()
        print("=" * 70)
        print("ERRO GERAL DA COLETA EPIC")
        print("=" * 70)
        print(f"  {erro}")
        raise

    finally:
        db.close()


# Nome explícito para novos usos, mantendo compatibilidade com o nome antigo.
coletar_historico_epic_egdata = coletar_historico_epic


if __name__ == "__main__":
    asyncio.run(coletar_historico_epic())
