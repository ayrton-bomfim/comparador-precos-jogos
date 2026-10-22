# -*- coding: utf-8 -*-
"""Avalia alertas de preço e trata notificações por e-mail e no site."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import joinedload

from ..banco_dados import SessionLocal
from ..modelos import (
    AlertaPreco,
    HistoricoPreco,
    Jogo,
    NotificacaoUsuario,
    Usuario,
)
from .email_alertas import enviar_alerta_preco

NOMES_LOJAS = {"steam": "Steam", "epic": "Epic Games Store"}


def _dinheiro(valor) -> str:
    numero = Decimal(str(valor or 0)).quantize(Decimal("0.01"))
    inteiro, centavos = f"{numero:.2f}".split(".")
    grupos = []
    while inteiro:
        grupos.append(inteiro[-3:])
        inteiro = inteiro[:-3]
    return "R$ " + ".".join(reversed(grupos)) + "," + centavos


def _url_loja(jogo: Jogo, loja: str) -> str | None:
    if loja == "steam":
        return jogo.url_steam or (
            f"https://store.steampowered.com/app/{jogo.steam_id}/"
            if jogo.steam_id
            else None
        )
    return jogo.url_epic


def _imagem(jogo: Jogo, loja: str) -> str:
    if loja == "steam" and jogo.url_imagem_steam:
        return jogo.url_imagem_steam
    if loja == "epic" and jogo.url_imagem_epic:
        return jogo.url_imagem_epic
    if jogo.steam_id:
        return (
            "https://shared.akamai.steamstatic.com/store_item_assets/"
            f"steam/apps/{jogo.steam_id}/header.jpg"
        )
    return "https://desctrl.com.br/favicon.ico"


def _desconto(historico: HistoricoPreco) -> float:
    if historico.desconto is not None:
        try:
            desconto_informado = max(0.0, min(100.0, float(historico.desconto)))
            if desconto_informado > 0:
                return desconto_informado
        except (TypeError, ValueError):
            pass

    base = historico.preco_sem_desconto
    atual = historico.preco_atual
    if base and Decimal(str(base)) > Decimal(str(atual)):
        return float(
            (Decimal(str(base)) - Decimal(str(atual)))
            / Decimal(str(base))
            * 100
        )
    return 0.0


def _condicao_atendida(alerta: AlertaPreco, historico: HistoricoPreco) -> bool:
    if alerta.condicao == "promocao":
        return _desconto(historico) > 0
    return (
        alerta.preco_alvo is not None
        and Decimal(str(historico.preco_atual))
        <= Decimal(str(alerta.preco_alvo))
    )


def _criar_notificacao_site(
    *,
    alerta_id: int,
    usuario_id: int,
    jogo_id: int,
    nome_jogo: str,
    condicao: str,
    preco_alvo,
    loja: str,
    preco_atual,
    desconto: float,
) -> bool:
    """Cria a notificação em uma sessão própria, isolando falhas do e-mail."""
    db_site = SessionLocal()
    try:
        # O bloqueio reduz o risco de duas execuções criarem a mesma notificação.
        alerta_site = (
            db_site.query(AlertaPreco)
            .filter(AlertaPreco.id == alerta_id)
            .with_for_update()
            .first()
        )
        usuario_site = (
            db_site.query(Usuario)
            .filter(Usuario.id == usuario_id)
            .first()
        )

        if (
            alerta_site is None
            or not alerta_site.ativo
            or usuario_site is None
            or not usuario_site.notificacao_site
            or alerta_site.ultima_condicao_site_ativa
        ):
            return False

        preco_txt = _dinheiro(preco_atual)
        if condicao == "preco_alvo":
            titulo = f"Preço atualizado: {nome_jogo}"
            mensagem = (
                f"{nome_jogo} atingiu seu preço-alvo de "
                f"{_dinheiro(preco_alvo)} na {NOMES_LOJAS[loja]} "
                f"(agora {preco_txt})."
            )
        else:
            titulo = f"Promoção encontrada: {nome_jogo}"
            mensagem = (
                f"{nome_jogo} está com {desconto:.0f}% de desconto "
                f"na {NOMES_LOJAS[loja]} (agora {preco_txt})."
            )

        db_site.add(
            NotificacaoUsuario(
                usuario_id=usuario_id,
                tipo="preco",
                titulo=titulo,
                mensagem=mensagem,
                link=f"/jogos/{jogo_id}",
                jogo_id=jogo_id,
                dados={
                    "loja": loja,
                    "loja_nome": NOMES_LOJAS[loja],
                    "preco_atual": str(preco_atual),
                    "preco_alvo": (
                        str(preco_alvo) if preco_alvo is not None else None
                    ),
                    "condicao": condicao,
                },
            )
        )
        alerta_site.ultima_condicao_site_ativa = True
        db_site.commit()
        return True
    except Exception:
        db_site.rollback()
        raise
    finally:
        db_site.close()


def avaliar_alertas_preco() -> dict[str, int]:
    """Avalia alertas e processa e-mail e notificação no site separadamente."""
    db = SessionLocal()
    resultado = {
        "avaliados": 0,
        "condicoes_atendidas": 0,
        "enviados": 0,
        "notificacoes_site": 0,
        "falhas": 0,
        "sem_historico": 0,
    }

    try:
        # Inclui alertas inativos para rearmar seus estados, se necessário.
        alertas = (
            db.query(AlertaPreco)
            .options(
                joinedload(AlertaPreco.jogo),
                joinedload(AlertaPreco.usuario),
            )
            .all()
        )

        for alerta in alertas:
            if not alerta.ativo:
                alterado = False
                if alerta.ultima_condicao_ativa:
                    alerta.ultima_condicao_ativa = False
                    alterado = True
                if alerta.ultima_condicao_site_ativa:
                    alerta.ultima_condicao_site_ativa = False
                    alterado = True
                if alterado:
                    try:
                        db.commit()
                    except Exception as erro:
                        db.rollback()
                        resultado["falhas"] += 1
                        print(
                            f"[ALERTA] Falha ao rearmar alerta inativo "
                            f"{alerta.id}: {erro}"
                        )
                continue

            resultado["avaliados"] += 1
            jogo = alerta.jogo or db.query(Jogo).filter(
                Jogo.id == alerta.jogo_id
            ).first()
            usuario = alerta.usuario or db.query(Usuario).filter(
                Usuario.id == alerta.usuario_id
            ).first()
            if not jogo or not usuario:
                continue

            observacoes = []
            for loja in (alerta.lojas or []):
                if loja not in {"steam", "epic"}:
                    continue
                historico = (
                    db.query(HistoricoPreco)
                    .filter(
                        HistoricoPreco.jogo_id == alerta.jogo_id,
                        HistoricoPreco.plataforma == loja,
                    )
                    .order_by(
                        HistoricoPreco.data_coleta.desc(),
                        HistoricoPreco.id.desc(),
                    )
                    .first()
                )
                if historico is not None:
                    observacoes.append((loja, historico))

            if not observacoes:
                resultado["sem_historico"] += 1
                # Sem dados novos, não presumimos que a condição deixou de valer.
                continue

            correspondencias = [
                (loja, historico)
                for loja, historico in observacoes
                if _condicao_atendida(alerta, historico)
            ]

            if not correspondencias:
                alterado = False
                if alerta.ultima_condicao_ativa:
                    alerta.ultima_condicao_ativa = False
                    alterado = True
                if alerta.ultima_condicao_site_ativa:
                    alerta.ultima_condicao_site_ativa = False
                    alterado = True
                if alterado:
                    try:
                        db.commit()
                    except Exception as erro:
                        db.rollback()
                        resultado["falhas"] += 1
                        print(
                            f"[ALERTA] Falha ao rearmar alerta {alerta.id}: "
                            f"{erro}"
                        )
                continue

            resultado["condicoes_atendidas"] += 1
            loja, historico = min(
                correspondencias,
                key=lambda item: Decimal(str(item[1].preco_atual)),
            )
            desconto = _desconto(historico)

            # Canal do site: a sessão separada impede uma falha aqui de
            # cancelar alterações ou impedir a tentativa de envio do e-mail.
            if usuario.notificacao_site and not alerta.ultima_condicao_site_ativa:
                try:
                    criada = _criar_notificacao_site(
                        alerta_id=alerta.id,
                        usuario_id=usuario.id,
                        jogo_id=jogo.id,
                        nome_jogo=jogo.nome,
                        condicao=alerta.condicao,
                        preco_alvo=alerta.preco_alvo,
                        loja=loja,
                        preco_atual=historico.preco_atual,
                        desconto=desconto,
                    )
                    if criada:
                        alerta.ultima_condicao_site_ativa = True
                        resultado["notificacoes_site"] += 1
                except Exception as erro:
                    resultado["falhas"] += 1
                    print(
                        "[ALERTA] Falha ao registrar notificação no site "
                        f"para usuário {usuario.id}, jogo {jogo.id}: {erro}"
                    )

            # O estado do e-mail é independente do estado da notificação no site.
            if alerta.ultima_condicao_ativa:
                continue
            if (
                not usuario.notificacao_email
                or not usuario.email_verificado
                or not usuario.email
            ):
                continue

            url = _url_loja(jogo, loja)
            if not url:
                print(
                    f"[ALERTA] Sem URL válida para {jogo.nome} ({loja}); "
                    "envio ignorado."
                )
                continue

            preco_base = (
                historico.preco_sem_desconto
                or (
                    jogo.preco_base_steam
                    if loja == "steam"
                    else jogo.preco_base_epic
                )
                or historico.preco_atual
            )

            try:
                enviar_alerta_preco(
                    destinatario=usuario.email,
                    nome_jogo=jogo.nome,
                    imagem_jogo_url=_imagem(jogo, loja),
                    loja_nome=NOMES_LOJAS[loja],
                    desconto_percentual=desconto,
                    preco_anterior=_dinheiro(preco_base),
                    preco_atual=_dinheiro(historico.preco_atual),
                    oferta_url=url,
                    data_consulta=(
                        historico.data_coleta.strftime("%d/%m/%Y às %H:%M")
                        if historico.data_coleta
                        else None
                    ),
                    preheader=(
                        f"{jogo.nome} atingiu o preço-alvo "
                        f"de {_dinheiro(alerta.preco_alvo)}."
                        if alerta.condicao == "preco_alvo"
                        else (
                            f"{jogo.nome} está em promoção "
                            f"na {NOMES_LOJAS[loja]}!"
                        )
                    ),
                )
                alerta.ultima_condicao_ativa = True
                alerta.ultima_notificacao_em = datetime.now()
                alerta.ultima_notificacao_preco = historico.preco_atual
                alerta.ultima_notificacao_loja = loja
                db.commit()
                resultado["enviados"] += 1
                print(
                    f"[ALERTA] E-mail enviado: {usuario.email} | {jogo.nome} "
                    f"| {NOMES_LOJAS[loja]} | "
                    f"{_dinheiro(historico.preco_atual)}"
                )
            except Exception as erro:
                db.rollback()
                resultado["falhas"] += 1
                print(
                    f"[ALERTA] Falha ao enviar para usuário {usuario.id}, "
                    f"jogo {jogo.id}: {erro}"
                )

        return resultado
    finally:
        db.close()
