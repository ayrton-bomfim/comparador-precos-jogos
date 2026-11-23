# -*- coding: utf-8 -*-
"""
Coleta histórica da Epic usando EGDATA.

Mantém a função pública `coletar_historico_epic()` usada pelo agendador.

Regras do histórico:
    - usa EpicOferta.offer_id;
    - consulta o preço atual de cada oferta na EGDATA (/offers/{id}/price);
    - registra preço, preço original, desconto e dados da promoção;
    - NÃO cria registro apenas porque a data da coleta mudou;
    - cria novo registro quando algum dado relevante do estado mudar;
    - mantém um erro isolado por jogo sem interromper a coleta dos demais.

O EpicScraper antigo permanece no projeto e pode continuar sendo usado
como legado/fallback em testes específicos.
"""

import argparse
import asyncio
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, insert, text

from ..banco_dados import SessionLocal
from ..modelos import HistoricoPreco
from .gravacao_lote import atualizar_precos_base as gravar_precos_base
from ..servicos.egdata import buscar_precos_por_oferta
from ..servicos.itad import buscar_precos_epic


# Abaixo desta fração de ofertas respondidas, a etapa é marcada como falha.
COBERTURA_MINIMA = 0.9
# Quantas mudanças são detalhadas no log; as demais entram só no resumo.
EXEMPLOS_NO_LOG = 15
# Teto de consultas à EGDATA (fonte reserva) por execução.
MAX_CONSULTAS_EGDATA = 300
# Variação do preço cheio (vs. último registro) que torna um preço do ITAD
# suspeito de mapeamento errado.
VARIACAO_SUSPEITA_ORIGINAL = 0.2

# Um preço zero sem promoção e sem atualização recente pode ser um dado
# obsoleto da fonte, e não uma confirmação de que o jogo é gratuito.
IDADE_MAXIMA_PRECO_ZERO_DIAS = 30


def _preco_zero_sem_confirmacao_recente(dados, agora=None):
    """Identifica preço 0/0 sem evidência recente suficiente.

    A regra é deliberadamente restrita a preço atual e original iguais a zero,
    sem promoção identificada. Preços positivos e zeros associados a promoção
    não são bloqueados por esta validação.
    """
    try:
        atual = float(dados.get("preco"))
        original = float(dados.get("preco_sem_desconto"))
    except (TypeError, ValueError):
        return False

    if atual != 0 or original != 0:
        return False

    if dados.get("promocao_id") or dados.get("promocao_nome"):
        return False

    atualizado_em = dados.get("updated_at")
    if atualizado_em is None:
        return True

    if atualizado_em.tzinfo is None:
        atualizado_em = atualizado_em.replace(tzinfo=timezone.utc)

    agora = agora or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)

    return agora - atualizado_em > timedelta(days=IDADE_MAXIMA_PRECO_ZERO_DIAS)


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

    # Só o fim da promoção é comparado: é o único campo de promoção usado pelo
    # site (regra única de promoção) e o único informado pelas duas fontes
    # (ITAD e EGDATA). ID, nome e início continuam gravados quando a fonte os
    # fornece, mas sua ausência não deve gerar registro novo.
    fim_anterior = _minuto_utc(getattr(ultimo, "promocao_fim", None))
    fim_atual = _minuto_utc(dados.get("promocao_fim"))
    if fim_anterior != fim_atual:
        return True, "Fim da promoção alterado"

    return False, ""


def _minuto_utc(valor):
    """Normaliza datas de fim de promoção para comparação (UTC, ao minuto)."""
    if valor is None:
        return None
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc).replace(second=0, microsecond=0)


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


def _carregar_ofertas_ativas(db):
    """Ofertas Epic ativas com o jogo correspondente (só as colunas usadas)."""
    return db.execute(text("""
        SELECT j.id AS jogo_id, j.nome, o.offer_id
        FROM epic_ofertas o
        JOIN jogos j ON j.id = o.jogo_id
        WHERE o.ativo IS TRUE
          AND j.epic_id IS NOT NULL
          AND j.epic_id <> 'EXCLUSIVO_STEAM'
        ORDER BY j.id, o.id
    """)).all()


def _carregar_ultimos_estados_epic(db):
    """Último estado Epic de cada jogo, em uma única consulta."""
    linhas = db.execute(text("""
        SELECT DISTINCT ON (jogo_id)
               jogo_id, preco_atual, preco_sem_desconto, desconto,
               promocao_id, promocao_nome, promocao_inicio, promocao_fim
        FROM historico_precos
        WHERE plataforma = 'Epic'
        ORDER BY jogo_id, id DESC
    """)).all()
    return {linha.jogo_id: linha for linha in linhas}


def _registro_historico(oferta, dados, agora):
    return {
        "jogo_id": oferta.jogo_id,
        "nome_jogo": oferta.nome,
        "plataforma": "Epic",
        "preco_atual": dados["preco"],
        "preco_sem_desconto": dados["preco_sem_desconto"],
        "desconto": dados["desconto"],
        "data_coleta": agora,
        "promocao_id": dados.get("promocao_id"),
        "promocao_nome": dados.get("promocao_nome"),
        "promocao_inicio": dados.get("promocao_inicio"),
        "promocao_fim": dados.get("promocao_fim"),
    }


def _diagnosticar_tamanhos(registro):
    """Campos textuais acima de 255 caracteres (o banco recusaria o registro).

    Não truncamos o valor automaticamente, pois isso alteraria o dado.
    """
    return [
        (campo, len(registro[campo]))
        for campo in ("nome_jogo", "promocao_id", "promocao_nome")
        if isinstance(registro.get(campo), str) and len(registro[campo]) > 255
    ]


def _gravar_registros(db, registros, precos_base, agora):
    """Grava em lote; se o lote falhar, grava um a um para isolar o problema.

    Retorna (salvos, erros).
    """
    if not registros:
        return 0, 0

    def atualizar_precos_base(ids):
        valores = {jogo_id: precos_base[jogo_id] for jogo_id in ids if jogo_id in precos_base}
        if valores:
            gravar_precos_base(db, "preco_base_epic", valores, agora)

    try:
        for inicio in range(0, len(registros), 1000):
            db.execute(insert(HistoricoPreco), registros[inicio:inicio + 1000])
        atualizar_precos_base({r["jogo_id"] for r in registros})
        db.commit()
        return len(registros), 0
    except Exception as erro_lote:
        db.rollback()
        print(f"  ⚠️ Falha ao gravar o lote ({erro_lote}); gravando registro por registro.")

    salvos = erros = 0
    for registro in registros:
        problemas = _diagnosticar_tamanhos(registro)
        if problemas:
            erros += 1
            detalhes = ", ".join(f"{campo}={tamanho} caracteres" for campo, tamanho in problemas)
            print(f"  ⚠️ Registro rejeitado por tamanho: {registro['nome_jogo']} ({detalhes})")
            continue
        try:
            db.execute(insert(HistoricoPreco), [registro])
            atualizar_precos_base({registro["jogo_id"]})
            db.commit()
            salvos += 1
        except Exception as erro:
            db.rollback()
            erros += 1
            print(f"  ⚠️ Registro rejeitado: {registro['nome_jogo']} (jogo_id={registro['jogo_id']}): {erro}")
    return salvos, erros


async def coletar_historico_epic(limite_ofertas=None):
    """
    Coleta o estado atual das ofertas Epic ativas.

    Fonte principal: ITAD (preços em lote). Fonte reserva: EGDATA, oferta a
    oferta, só para o que o ITAD não resolve. A busca paginada da EGDATA usada
    antes deixou de funcionar em 06/11/2026 (303/429 e tarpit), e a coleta
    passou a encontrar só ~9% das ofertas.

    Args:
        limite_ofertas: consulta só as N primeiras ofertas (para testes).
    """
    inicio = time.monotonic()
    agora = datetime.now()

    print("=" * 70)
    print("COLETANDO HISTÓRICO DA EPIC — ITAD + EGDATA")
    print("=" * 70)
    print("Fonte principal: ITAD em lote; reserva: EGDATA por oferta")
    print("Histórico: somente alterações relevantes")
    print(f"Início: {agora.strftime('%d/%m/%Y %H:%M')}")
    print()

    if limite_ofertas is not None and limite_ofertas < 1:
        raise ValueError("limite_ofertas deve ser maior que zero.")

    db = SessionLocal()

    try:
        ofertas = _carregar_ofertas_ativas(db)
        total_catalogo = len(ofertas)
        if limite_ofertas is not None:
            ofertas = ofertas[:limite_ofertas]

        print(f"Ofertas ativas na Epic: {total_catalogo}")
        if limite_ofertas is not None:
            print(f"Modo de teste: {len(ofertas)} ofertas")

        if not ofertas:
            return {
                "status": "sem_ofertas",
                "fonte": "EGDATA",
                "total_catalogo": total_catalogo,
                "total_processado": 0,
                "novos_registros": 0,
                "ignorados": 0,
                "erros": 0,
            }

        offer_ids = [str(oferta.offer_id) for oferta in ofertas]
        ultimos = _carregar_ultimos_estados_epic(db)

        # 1) ITAD: catálogo inteiro em ~50 requisições.
        precos, sem_mapeamento, sem_preco_itad = await asyncio.to_thread(
            buscar_precos_epic, offer_ids
        )
        print(
            f"ITAD: {len(precos)} preços, {len(sem_mapeamento)} ofertas sem "
            f"correspondência única, {len(sem_preco_itad)} sem preço Epic BR "
            f"({time.monotonic() - inicio:.0f}s)"
        )

        # 2) EGDATA, uma oferta por vez, só para o que o ITAD não resolveu e
        # pode estar à venda: sem correspondência no ITAD, ou com último preço
        # conhecido acima de zero. A EGDATA aplica tarpit em consultas em
        # massa, por isso o volume é limitado.
        jogo_por_oferta = {str(o.offer_id): o.jogo_id for o in ofertas}

        def ultimo_preco_positivo(offer_id):
            ultimo = ultimos.get(jogo_por_oferta.get(offer_id))
            return ultimo is not None and float(ultimo.preco_atual or 0) > 0

        # O ITAD às vezes associa a oferta ao jogo errado (ex.: uma "Deluxe
        # Edition" genérica ligada à Deluxe de outro jogo). Preço cheio muito
        # diferente do último conhecido é tratado como suspeito e conferido na
        # EGDATA antes de entrar no histórico. Sem registro anterior não há
        # como comparar, então o primeiro registro também é conferido.
        suspeitas = []
        for offer_id, dados in list(precos.items()):
            ultimo = ultimos.get(jogo_por_oferta.get(offer_id))
            original_anterior = float(ultimo.preco_sem_desconto or 0) if ultimo else 0
            if ultimo is None or (
                original_anterior > 0
                and abs(dados["preco_sem_desconto"] / original_anterior - 1) > VARIACAO_SUSPEITA_ORIGINAL
            ):
                suspeitas.append(offer_id)
                del precos[offer_id]
        if suspeitas:
            print(
                f"ITAD: {len(suspeitas)} preço(s) sem histórico ou com preço cheio "
                f">{VARIACAO_SUSPEITA_ORIGINAL:.0%} diferente do último; conferindo na EGDATA."
            )

        reserva_total = sorted(
            (sem_mapeamento | {o for o in sem_preco_itad if ultimo_preco_positivo(o)}) - set(suspeitas)
        )
        # Rodízio: a cada dia consulta uma fatia diferente, de modo que toda a
        # reserva é revista a cada ceil(total / vagas) dias sem precisar
        # guardar estado. As suspeitas sempre entram.
        vagas = max(0, MAX_CONSULTAS_EGDATA - len(suspeitas))
        fatias = max(1, -(-len(reserva_total) // vagas)) if vagas else 1
        fatia = agora.toordinal() % fatias
        reserva = suspeitas + (reserva_total[fatia * vagas:(fatia + 1) * vagas] if vagas else [])
        em_rodizio = len(reserva_total) + len(suspeitas) - len(reserva)
        sem_preco = sem_preco_itad - set(reserva_total)
        falhas = {}
        if reserva:
            print(f"EGDATA (reserva): consultando {len(reserva)} oferta(s)...")
            marco = max(1, len(reserva) // 5)

            def progresso(concluidos, total, qtd_falhas):
                if concluidos % marco == 0 or concluidos == total:
                    print(f"  EGDATA: {concluidos}/{total} ({time.monotonic() - inicio:.0f}s, {qtd_falhas} falhas)")

            precos_egdata, sem_preco_egdata, falhas = await asyncio.to_thread(
                buscar_precos_por_oferta, reserva, workers=1, progresso=progresso
            )
            precos.update(precos_egdata)
            sem_preco |= sem_preco_egdata

        print(
            f"\n✓ Preços obtidos: {len(precos)}/{len(offer_ids)} "
            f"(sem preço: {len(sem_preco)}, falhas: {len(falhas)}"
            + (f", em rodízio para outros dias: {em_rodizio}" if em_rodizio else "")
            + ")"
        )
        if falhas:
            print("  Motivos das falhas: " + ", ".join(
                f"{motivo}={qtd}" for motivo, qtd in Counter(falhas.values()).most_common()
            ))
        fontes = Counter(dados.get("fonte", "EGDATA") for dados in precos.values())

        registros = []
        precos_base = {}
        ignorados = 0
        zeros_ignorados = 0
        motivos = Counter()

        print(f"\nComparando com o histórico (primeiras {EXEMPLOS_NO_LOG} mudanças):")
        for oferta in ofertas:
            dados = precos.get(str(oferta.offer_id))
            if dados is None:
                continue

            if _preco_zero_sem_confirmacao_recente(dados):
                zeros_ignorados += 1
                ignorados += 1
                continue

            deve_criar, motivo = dados_relevantes_mudaram(ultimos.get(oferta.jogo_id), dados)
            if not deve_criar:
                ignorados += 1
                continue

            registros.append(_registro_historico(oferta, dados, agora))
            motivos[motivo.split(" (")[0]] += 1
            if dados["preco_sem_desconto"] is not None and float(dados["preco_sem_desconto"]) > 0:
                precos_base[oferta.jogo_id] = dados["preco_sem_desconto"]
            if len(registros) <= EXEMPLOS_NO_LOG:
                print(
                    f"  {oferta.nome}: {motivo} — R$ {dados['preco']:.2f} "
                    f"(original R$ {dados['preco_sem_desconto']:.2f}, {dados['desconto']}%)"
                )

        novos, erros_gravacao = _gravar_registros(db, registros, precos_base, agora)

        duracao = time.monotonic() - inicio
        consultadas = len(offer_ids)
        avaliadas = consultadas - em_rodizio
        respondidas = avaliadas - len(falhas)
        cobertura = len(precos) / avaliadas if avaliadas else 1.0
        erros = len(falhas) + erros_gravacao

        print("=" * 70)
        print("RESUMO DA COLETA DA EPIC")
        print("=" * 70)
        print(f"  Ofertas consultadas: {consultadas}")
        print(f"  Com preço: {len(precos)} ({cobertura:.1%}) — " + ", ".join(f"{f}={q}" for f, q in fontes.most_common()))
        print(f"  Sem preço Epic BR (gratuitos/fora de venda): {len(sem_preco)}")
        print(f"  Reserva EGDATA em rodízio (vistas em outro dia): {em_rodizio} de {len(reserva_total)}")
        print(f"  Falhas de consulta: {len(falhas)}")
        print(f"  Novos registros: {novos}")
        print(f"  Sem mudança: {ignorados} (preço 0/0 antigo ignorado: {zeros_ignorados})")
        if motivos:
            print("  Motivos: " + ", ".join(f"{m}={q}" for m, q in motivos.most_common()))
        print(f"  Duração: {duracao:.0f}s")

        if avaliadas and respondidas / avaliadas < COBERTURA_MINIMA:
            status = "falha"
        elif erros > avaliadas * 0.01:
            status = "parcial"
        elif erros:
            status = "concluida_com_avisos"
        else:
            status = "concluida"

        return {
            "status": status,
            "fonte": "ITAD+EGDATA",
            "fontes": dict(fontes),
            "total_catalogo": total_catalogo,
            "total_processado": consultadas,
            "novos_registros": novos,
            "ignorados": ignorados,
            "erros": erros,
            "offer_ids_consultados": consultadas,
            "precos_encontrados": len(precos),
            "sem_preco": len(sem_preco),
            "reserva_em_rodizio": em_rodizio,
            "offer_ids_faltantes": len(falhas),
            "cobertura": round(cobertura, 4),
            "duracao_segundos": round(duracao, 1),
        }

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
    parser = argparse.ArgumentParser(
        description="Coleta incremental do histórico de preços da Epic via EGDATA."
    )
    parser.add_argument(
        "--limite-ofertas",
        type=int,
        default=None,
        help="Limita a quantidade de ofertas processadas nesta execução.",
    )
    args = parser.parse_args()
    if args.limite_ofertas is not None and args.limite_ofertas < 1:
        parser.error("--limite-ofertas deve ser maior que zero.")
    asyncio.run(coletar_historico_epic(limite_ofertas=args.limite_ofertas))
