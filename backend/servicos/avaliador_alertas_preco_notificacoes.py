# -*- coding: utf-8 -*-
"""Avalia alertas ativos após as coletas e envia e-mails quando a condição muda para verdadeira."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import joinedload

from ..banco_dados import SessionLocal
from ..modelos import AlertaPreco, HistoricoPreco, Jogo, Usuario, NotificacaoUsuario
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
        return jogo.url_steam or (f"https://store.steampowered.com/app/{jogo.steam_id}/" if jogo.steam_id else None)
    return jogo.url_epic


def _imagem(jogo: Jogo, loja: str) -> str:
    if loja == "steam" and jogo.url_imagem_steam:
        return jogo.url_imagem_steam
    if loja == "epic" and jogo.url_imagem_epic:
        return jogo.url_imagem_epic
    if jogo.steam_id:
        return f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{jogo.steam_id}/header.jpg"
    # O template exige URL absoluta; imagem genérica do site como último recurso.
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
        return float((Decimal(str(base)) - Decimal(str(atual))) / Decimal(str(base)) * 100)
    return 0.0


def _condicao_atendida(alerta: AlertaPreco, historico: HistoricoPreco) -> bool:
    if alerta.condicao == "promocao":
        return _desconto(historico) > 0
    return alerta.preco_alvo is not None and Decimal(str(historico.preco_atual)) <= Decimal(str(alerta.preco_alvo))


def avaliar_alertas_preco() -> dict[str, int]:
    """Avalia as últimas observações de cada loja e envia no máximo um e-mail por ciclo contínuo da condição."""
    db = SessionLocal()
    resultado = {"avaliados": 0, "condicoes_atendidas": 0, "enviados": 0, "notificacoes_site": 0, "falhas": 0, "sem_historico": 0}
    try:
        alertas = (
            db.query(AlertaPreco)
            .options(joinedload(AlertaPreco.jogo), joinedload(AlertaPreco.usuario))
            .filter(AlertaPreco.ativo.is_(True))
            .all()
        )
        for alerta in alertas:
            resultado["avaliados"] += 1
            jogo = alerta.jogo or db.query(Jogo).filter(Jogo.id == alerta.jogo_id).first()
            usuario = alerta.usuario or db.query(Usuario).filter(Usuario.id == alerta.usuario_id).first()
            if not jogo or not usuario:
                continue

            observacoes = []
            for loja in (alerta.lojas or []):
                if loja not in {"steam", "epic"}:
                    continue
                historico = (
                    db.query(HistoricoPreco)
                    .filter(HistoricoPreco.jogo_id == alerta.jogo_id, HistoricoPreco.plataforma == loja)
                    .order_by(HistoricoPreco.data_coleta.desc(), HistoricoPreco.id.desc())
                    .first()
                )
                if historico is not None:
                    observacoes.append((loja, historico))
            if not observacoes:
                resultado["sem_historico"] += 1
                continue

            correspondencias = [(loja, h) for loja, h in observacoes if _condicao_atendida(alerta, h)]
            if not correspondencias:
                # Rearma o alerta quando a condição deixa de valer.
                alterado = False
                if alerta.ultima_condicao_ativa:
                    alerta.ultima_condicao_ativa = False; alterado = True
                if alerta.ultima_condicao_site_ativa:
                    alerta.ultima_condicao_site_ativa = False; alterado = True
                if alterado: db.commit()
                continue

            resultado["condicoes_atendidas"] += 1
            loja, historico = min(correspondencias, key=lambda item: Decimal(str(item[1].preco_atual)))
            # Canal do site independente do e-mail. O estado separado evita duplicatas por coleta.
            if usuario.notificacao_site and not alerta.ultima_condicao_site_ativa:
                try:
                    preco_txt = _dinheiro(historico.preco_atual)
                    titulo = f"Preço atualizado: {jogo.nome}" if alerta.condicao == "preco_alvo" else f"Promoção encontrada: {jogo.nome}"
                    mensagem = (f"{jogo.nome} atingiu seu preço-alvo de {_dinheiro(alerta.preco_alvo)} na {NOMES_LOJAS[loja]} (agora {preco_txt})."
                                if alerta.condicao == "preco_alvo" else f"{jogo.nome} está com { _desconto(historico):.0f}% de desconto na {NOMES_LOJAS[loja]} (agora {preco_txt}).")
                    db.add(NotificacaoUsuario(usuario_id=usuario.id, tipo="preco", titulo=titulo, mensagem=mensagem,
                        link=f"/jogos/{jogo.id}", jogo_id=jogo.id,
                        dados={"loja": loja, "loja_nome": NOMES_LOJAS[loja], "preco_atual": str(historico.preco_atual),
                               "preco_alvo": str(alerta.preco_alvo) if alerta.preco_alvo is not None else None, "condicao": alerta.condicao}))
                    alerta.ultima_condicao_site_ativa = True
                    db.commit()
                    resultado["notificacoes_site"] += 1
                except Exception as erro:
                    db.rollback()
                    resultado["falhas"] += 1
                    print(f"[ALERTA] Falha ao registrar notificação no site para usuário {usuario.id}, jogo {jogo.id}: {erro}")
                    continue

            # O e-mail mantém seu próprio estado para funcionar independentemente do canal do site.
            if alerta.ultima_condicao_ativa:
                continue
            if not usuario.notificacao_email or not usuario.email_verificado or not usuario.email:
                continue
            url = _url_loja(jogo, loja)
            if not url:
                print(f"[ALERTA] Sem URL válida para {jogo.nome} ({loja}); envio ignorado.")
                continue
            preco_base = historico.preco_sem_desconto or (jogo.preco_base_steam if loja == "steam" else jogo.preco_base_epic) or historico.preco_atual
            desconto = _desconto(historico)
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
                    data_consulta=(historico.data_coleta.strftime("%d/%m/%Y às %H:%M") if historico.data_coleta else None),
                    preheader=(f"{jogo.nome} atingiu o preço-alvo de {_dinheiro(alerta.preco_alvo)}." if alerta.condicao == "preco_alvo" else f"{jogo.nome} está em promoção na {NOMES_LOJAS[loja]}!"),
                )
                alerta.ultima_condicao_ativa = True
                alerta.ultima_notificacao_em = datetime.now()
                alerta.ultima_notificacao_preco = historico.preco_atual
                alerta.ultima_notificacao_loja = loja
                db.commit()
                resultado["enviados"] += 1
                print(f"[ALERTA] E-mail enviado: {usuario.email} | {jogo.nome} | {NOMES_LOJAS[loja]} | {_dinheiro(historico.preco_atual)}")
            except Exception as erro:
                db.rollback()
                resultado["falhas"] += 1
                print(f"[ALERTA] Falha ao enviar para usuário {usuario.id}, jogo {jogo.id}: {erro}")
        return resultado
    finally:
        db.close()
