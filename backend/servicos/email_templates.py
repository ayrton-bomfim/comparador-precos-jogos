"""Renderizador de HTML para e-mails de alerta de preço do DESCTRL.

Este módulo apenas monta o HTML. Não envia e-mails e não depende de Resend,
SMTP ou qualquer provedor específico.
"""
from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from string import Template
from urllib.parse import urlparse


_TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "templates"
    / "email_alerta_preco.html"
)


class EmailTemplateError(ValueError):
    """Erro de validação dos dados usados no modelo de e-mail."""


def _texto(valor: object, campo: str) -> str:
    if valor is None or not str(valor).strip():
        raise EmailTemplateError(f"O campo '{campo}' é obrigatório.")
    return escape(str(valor).strip(), quote=True)


def _url(valor: object, campo: str) -> str:
    texto = _texto(valor, campo)
    parsed = urlparse(str(valor).strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise EmailTemplateError(
            f"O campo '{campo}' precisa ser uma URL absoluta http ou https."
        )
    return escape(str(valor).strip(), quote=True)


def renderizar_alerta_preco(
    *,
    nome_jogo: str,
    imagem_jogo_url: str,
    loja_nome: str,
    desconto_percentual: int | float,
    preco_anterior: str,
    preco_atual: str,
    oferta_url: str,
    data_consulta: str | None = None,
    preferencias_url: str = "https://desctrl.com.br/",
    preheader: str | None = None,
) -> str:
    """Retorna o HTML pronto para ser enviado por qualquer provedor.

    Preços devem ser fornecidos já formatados, por exemplo: 'R$ 199,90'.
    O desconto deve ser numérico e estar entre 0 e 100.
    """
    try:
        desconto = float(desconto_percentual)
    except (TypeError, ValueError) as exc:
        raise EmailTemplateError("O desconto precisa ser numérico.") from exc

    if not 0 <= desconto <= 100:
        raise EmailTemplateError("O desconto precisa estar entre 0 e 100.")

    data = data_consulta or datetime.now().astimezone().strftime("%d/%m/%Y às %H:%M")
    resumo = preheader or (
        f"{nome_jogo}: agora por {preco_atual} na loja {loja_nome}."
    )

    valores = {
        "nome_jogo": _texto(nome_jogo, "nome_jogo"),
        "imagem_jogo_url": _url(imagem_jogo_url, "imagem_jogo_url"),
        "loja_nome": _texto(loja_nome, "loja_nome"),
        "desconto_percentual": f"{desconto:g}",
        "preco_anterior": _texto(preco_anterior, "preco_anterior"),
        "preco_atual": _texto(preco_atual, "preco_atual"),
        "oferta_url": _url(oferta_url, "oferta_url"),
        "data_consulta": _texto(data, "data_consulta"),
        "preferencias_url": _url(preferencias_url, "preferencias_url"),
        "preheader": _texto(resumo, "preheader"),
    }

    html_template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    return html_template.substitute(valores)
