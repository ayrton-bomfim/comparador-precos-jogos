"""Integração entre o modelo de alerta de preço e o serviço de envio.

A montagem do HTML continua independente do provedor. Este módulo é a camada
que combina o renderizador com o serviço de envio atualmente configurado.
"""
from __future__ import annotations

from typing import Any

from backend.servicos.email_service import enviar_email
from backend.servicos.email_templates import renderizar_alerta_preco


def enviar_alerta_preco(
    *,
    destinatario: str,
    nome_jogo: str,
    imagem_jogo_url: str,
    loja_nome: str,
    desconto_percentual: int | float,
    preco_anterior: str,
    preco_atual: str,
    oferta_url: str,
    data_consulta: str | None = None,
    preferencias_url: str = "https://desctrl.com.br/perfil?aba=configuracoes",
    preheader: str | None = None,
) -> dict[str, Any]:
    """Renderiza e envia um alerta de preço.

    Os preços devem vir já formatados, por exemplo, 'R$ 99,90'.
    Esta função não consulta o banco nem escolhe destinatários: recebe os dados
    já preparados pelo chamador e os encaminha ao serviço de e-mail existente.
    """
    html_email = renderizar_alerta_preco(
        nome_jogo=nome_jogo,
        imagem_jogo_url=imagem_jogo_url,
        loja_nome=loja_nome,
        desconto_percentual=desconto_percentual,
        preco_anterior=preco_anterior,
        preco_atual=preco_atual,
        oferta_url=oferta_url,
        data_consulta=data_consulta,
        preferencias_url=preferencias_url,
        preheader=preheader,
    )
    assunto = f"Alerta de preço: {nome_jogo}"
    return enviar_email(
        destinatario=destinatario,
        assunto=assunto,
        html=html_email,
    )
