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
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_

from ...banco_dados import SessionLocal
from ...modelos import Jogo, EpicOferta, HistoricoPreco
from ...servicos.egdata import buscar_preco_atual


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


class _BuscaCatalogoEpic:
    """
    Consulta o endpoint de busca da EGDATA em lote.

    A busca já devolve o preço regional junto de cada oferta, evitando
    uma chamada /offers/{id}/price para cada jogo.
    """

    URL = "https://api.egdata.app/search/v2/search"
    PAIS = "BR"
    LOCALE = "pt-BR"
    LIMITE = 100
    PAUSA_PAGINA = 0.15
    MAX_TENTATIVAS = 4
    TIMEOUT = 30

    def __init__(self):
        import requests

        self.session = requests.Session()
        self.session.headers.update(
            {"Content-Type": "application/json"}
        )

    def _buscar_pagina(self, offer_type, pagina):
        payload = {
            "offerType": offer_type,
            "sortBy": "lastModifiedDate",
            "sortDir": "desc",
            "page": pagina,
            "limit": self.LIMITE,
        }

        ultima_erro = None

        for tentativa in range(1, self.MAX_TENTATIVAS + 1):
            try:
                resposta = self.session.post(
                    self.URL,
                    params={
                        "country": self.PAIS,
                        "locale": self.LOCALE,
                    },
                    json=payload,
                    timeout=self.TIMEOUT,
                )

                if resposta.status_code == 429:
                    retry_after = resposta.headers.get("Retry-After")

                    try:
                        espera = float(retry_after)
                    except (TypeError, ValueError):
                        espera = min(2.0 * tentativa, 10.0)

                    print(
                        f"  ⚠️ EGDATA respondeu 429 na página "
                        f"{pagina} ({offer_type}). "
                        f"Aguardando {espera:.1f}s..."
                    )
                    import time

                    time.sleep(espera)
                    continue

                resposta.raise_for_status()
                dados = resposta.json()

                ofertas = dados.get("offers") or []
                total = int(dados.get("total") or 0)

                return ofertas, total

            except Exception as erro:
                ultima_erro = erro

                if tentativa >= self.MAX_TENTATIVAS:
                    break

                import time

                espera = min(2.0 * tentativa, 10.0)
                print(
                    f"  ⚠️ Falha na página {pagina} ({offer_type}): "
                    f"{erro}. Retry em {espera:.1f}s..."
                )
                time.sleep(espera)

        raise RuntimeError(
            f"Falha ao consultar página {pagina} ({offer_type}) "
            f"após {self.MAX_TENTATIVAS} tentativas: {ultima_erro}"
        )

    def coletar_precos(self, offer_ids):
        """
        Retorna {offer_id: dados_normalizados} para os offer IDs solicitados.

        A busca é feita por BASE_GAME, EDITION e EXPERIENCE, conforme o catálogo atual.
        """
        import time

        restantes = {str(offer_id) for offer_id in offer_ids}
        resultados = {}

        for offer_type in ("BASE_GAME", "EDITION", "EXPERIENCE"):
            primeira_pagina = True
            pagina = 1
            total_tipo = None

            while True:
                ofertas, total = self._buscar_pagina(
                    offer_type,
                    pagina,
                )

                if total_tipo is None:
                    total_tipo = total

                print(
                    f"  Busca {offer_type}: página {pagina} "
                    f"({len(ofertas)} ofertas)"
                )

                for oferta in ofertas:
                    offer_id = str(oferta.get("id") or "").strip()

                    if not offer_id or offer_id not in restantes:
                        continue

                    dados = self._normalizar_oferta(oferta, offer_id)

                    if dados is None:
                        continue

                    resultados[offer_id] = dados
                    restantes.discard(offer_id)

                if not ofertas:
                    break

                paginas_total = max(
                    1,
                    (total_tipo + self.LIMITE - 1) // self.LIMITE,
                )

                if pagina >= paginas_total:
                    break

                pagina += 1
                time.sleep(self.PAUSA_PAGINA)

        return resultados, restantes

    @staticmethod
    def _normalizar_oferta(oferta, offer_id):
        """
        Converte o bloco de preço da busca para o mesmo contrato usado por
        buscar_preco_atual().
        """
        from ...servicos.egdata import (
            _encontrar_promocao,
            calcular_desconto,
            converter_data,
            converter_preco,
        )

        bloco = oferta.get("price") or {}
        preco = bloco.get("price") or {}

        original = converter_preco(preco.get("originalPrice"))
        atual = converter_preco(preco.get("discountPrice"))

        if original is None or atual is None:
            return None

        promocao = _encontrar_promocao(
            bloco.get("appliedRules"),
            offer_id,
        )

        desconto = calcular_desconto(
            original,
            atual,
        )

        return {
            "offer_id": oferta.get("id") or offer_id,
            "preco": atual,
            "preco_sem_desconto": original,
            "desconto": int(desconto or 0),
            "promocao_inicio": promocao["inicio"],
            "promocao_fim": promocao["fim"],
            "promocao_id": promocao["id"],
            "promocao_nome": promocao["nome"],
            "updated_at": converter_data(
                bloco.get("updatedAt")
            ),
        }


def _carregar_ultimos_historicos(db, jogos_ofertas):
    """
    Carrega de uma vez o último histórico Epic de cada jogo.
    Evita uma consulta SQL por oferta.
    """
    jogo_ids = {jogo.id for jogo, _ in jogos_ofertas}

    if not jogo_ids:
        return {}

    historicos = (
        db.query(HistoricoPreco)
        .filter(
            and_(
                HistoricoPreco.jogo_id.in_(jogo_ids),
                HistoricoPreco.plataforma == "Epic",
            )
        )
        .order_by(
            HistoricoPreco.jogo_id.asc(),
            HistoricoPreco.id.desc(),
        )
        .all()
    )

    ultimos = {}
    for historico in historicos:
        if historico.jogo_id not in ultimos:
            ultimos[historico.jogo_id] = historico

    return ultimos

def _criar_historico(jogo, dados):
    """Cria uma nova instância de HistoricoPreco a partir dos dados coletados."""
    return HistoricoPreco(
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


def _diagnosticar_tamanhos(jogo, dados):
    """
    Identifica valores textuais que excedem 255 caracteres.

    O banco atualmente reportou StringDataRightTruncation em uma coluna
    varchar(255). Não truncamos o valor automaticamente, pois isso alteraria
    o dado histórico. Apenas informamos o campo suspeito.
    """
    campos = {
        "nome_jogo": jogo.nome,
        "plataforma": "Epic",
        "promocao_id": dados.get("promocao_id"),
        "promocao_nome": dados.get("promocao_nome"),
    }

    return [
        (campo, valor)
        for campo, valor in campos.items()
        if isinstance(valor, str) and len(valor) > 255
    ]


def _salvar_lote_com_fallback(db, pendencias):
    """
    Tenta salvar o lote inteiro.

    Se um único registro quebrar o commit, faz rollback e salva os registros
    individualmente. Assim, um registro inválido não derruba os outros 99.
    Retorna (salvos, erros).
    """
    if not pendencias:
        return 0, 0

    try:
        for item in pendencias:
            db.add(_criar_historico(item["jogo"], item["dados"]))
            preco_base = item["dados"].get("preco_sem_desconto")
            if preco_base is not None and float(preco_base) > 0:
                item["jogo"].preco_base_epic = preco_base

        db.commit()
        return len(pendencias), 0

    except Exception as erro_lote:
        db.rollback()

        print(
            "  ⚠️ Falha ao salvar o lote. "
            "O lote será reprocessado registro por registro."
        )
        print(f"  Motivo do lote: {erro_lote}")

        salvos = 0
        erros = 0

        for item in pendencias:
            jogo = item["jogo"]
            dados = item["dados"]

            problemas = _diagnosticar_tamanhos(jogo, dados)
            if problemas:
                detalhes = ", ".join(
                    f"{campo}={len(valor)} caracteres"
                    for campo, valor in problemas
                )
                print(
                    f"  ⚠️ Registro rejeitado por tamanho: "
                    f"{jogo.nome} ({detalhes})"
                )
                erros += 1
                continue

            try:
                db.add(_criar_historico(jogo, dados))

                preco_base = dados.get("preco_sem_desconto")
                if preco_base is not None and float(preco_base) > 0:
                    jogo.preco_base_epic = preco_base

                db.commit()
                salvos += 1

            except Exception as erro:
                db.rollback()
                erros += 1
                print(
                    f"  ⚠️ Registro rejeitado: {jogo.nome} "
                    f"(jogo_id={jogo.id})"
                )
                print(f"     {erro}")

        print(
            f"  ✓ Fallback concluído: {salvos} salvos, "
            f"{erros} rejeitados."
        )

        return salvos, erros




async def coletar_historico_epic():
    """
    Coleta o estado atual das ofertas Epic ativas.

    Otimizações:
        1. Últimos históricos carregados em uma única consulta SQL.
        2. Preços obtidos pelo endpoint de busca da EGDATA em lotes de 100.
        3. Registros persistidos em lotes.

    A busca em lote devolve o preço regional junto da oferta, reduzindo
    milhares de requisições individuais para aproximadamente uma centena.
    """
    TAMANHO_LOTE_COMMIT = 100

    print("=" * 70)
    print("COLETANDO HISTÓRICO DA EPIC — EGDATA")
    print("=" * 70)
    print("Fonte de preço atual: EGDATA")
    print("Consulta de preço: busca de catálogo em lote")
    print("Histórico: somente alterações relevantes")
    print(f"Commit em lotes de: {TAMANHO_LOTE_COMMIT}")
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print()

    db = SessionLocal()

    novos = 0
    ignorados = 0
    erros = 0
    pendentes_commit = 0
    pendencias = []

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

        total = len(jogos_ofertas)

        print(
            f"Encontrados {total} jogos/ofertas ativos na Epic."
        )
        print()

        if not jogos_ofertas:
            print("Nenhuma oferta Epic ativa encontrada.")
            return

        ultimos_historicos = _carregar_ultimos_historicos(
            db,
            jogos_ofertas,
        )

        offer_ids = {
            str(oferta.offer_id)
            for _, oferta in jogos_ofertas
            if oferta.offer_id
        }

        print(
            f"Consultando preços de {len(offer_ids)} offer IDs "
            "por páginas de catálogo..."
        )

        busca = _BuscaCatalogoEpic()
        precos, faltantes = await asyncio.to_thread(
            busca.coletar_precos,
            offer_ids,
        )

        print()
        print(
            f"✓ Preços encontrados em lote: {len(precos)}/{len(offer_ids)}"
        )

        if faltantes:
            print(
                f"⚠️ Offer IDs não encontrados na busca: "
                f"{len(faltantes)}"
            )

        print()

        for indice, (jogo, oferta) in enumerate(
            jogos_ofertas,
            1,
        ):
            print(
                f"[{indice}/{total}] "
                f"{jogo.nome}"
            )
            print(f"  Offer ID: {oferta.offer_id}")

            try:
                dados = precos.get(str(oferta.offer_id))

                if dados is None:
                    erros += 1
                    print(
                        "  Ação: erro — oferta não retornada "
                        "pela busca de catálogo."
                    )
                    print()
                    continue

                atualizado_em = dados.get("updated_at")
                if atualizado_em is not None:
                    print(f"  Atualização informada pela EGDATA: {atualizado_em.isoformat()}")

                if _preco_zero_sem_confirmacao_recente(dados):
                    print(
                        "  Ação: ignorado — preço 0/0 sem promoção e sem "
                        f"atualização recente (limite: {IDADE_MAXIMA_PRECO_ZERO_DIAS} dias)."
                    )
                    ignorados += 1
                    print()
                    continue

                ultimo = ultimos_historicos.get(jogo.id)

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
                    print(
                        f"  Período: {inicio} -> {fim}"
                    )

                if not deve_criar:
                    print(
                        "  Ação: ignorado — "
                        "nenhuma alteração relevante."
                    )
                    ignorados += 1
                    print()
                    continue

                pendencias.append(
                    {
                        "jogo": jogo,
                        "dados": dados,
                        "motivo": motivo,
                    }
                )
                pendentes_commit += 1

                print(
                    f"  Ação: registro preparado — "
                    f"{motivo}."
                )

                if pendentes_commit >= TAMANHO_LOTE_COMMIT:
                    salvos_lote, erros_lote = _salvar_lote_com_fallback(
                        db,
                        pendencias,
                    )
                    novos += salvos_lote
                    erros += erros_lote
                    pendencias = []
                    pendentes_commit = 0
                    print("  ✓ Lote processado.")

                print()

            except Exception as erro:
                db.rollback()
                erros += 1
                print(f"  Ação: erro — {erro}")
                print()

        if pendentes_commit:
            salvos_lote, erros_lote = _salvar_lote_com_fallback(
                db,
                pendencias,
            )
            novos += salvos_lote
            erros += erros_lote
            print(
                f"✓ Último lote processado "
                f"({pendentes_commit} registros)."
            )

        print("=" * 70)
        print("RESUMO DA COLETA DA EPIC — EGDATA")
        print("=" * 70)
        print(f"  Novos registros: {novos}")
        print(f"  Ignorados: {ignorados}")
        print(f"  Erros: {erros}")
        print(f"  Total processado: {total}")
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
