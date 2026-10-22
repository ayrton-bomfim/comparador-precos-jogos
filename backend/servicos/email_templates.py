"""Renderizador HTML dos e-mails de alerta de preço do DESCTRL."""
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

URL_PREFERENCIAS_PADRAO = (
    "https://desctrl.com.br/perfil?aba=configuracoes"
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

    return texto


def _imagem_opcional(valor: str | None) -> str:
    """Gera a imagem somente quando a URL é válida."""
    if not valor or not str(valor).strip():
        return ""

    try:
        url = _url(valor, "imagem_jogo_url")
    except EmailTemplateError:
        return ""

    return (
        '<img src="{url}" alt="" width="112" '
        'style="display:block;width:112px;max-width:100%;height:auto;'
        'border:0;border-radius:10px;" />'
    ).format(url=url)


def renderizar_alerta_preco(
    *,
    nome_jogo: str,
    imagem_jogo_url: str | None,
    loja_nome: str,
    desconto_percentual: int | float,
    preco_anterior: str,
    preco_atual: str,
    oferta_url: str,
    data_consulta: str | None = None,
    preferencias_url: str = URL_PREFERENCIAS_PADRAO,
    preheader: str | None = None,
) -> str:
    """Monta o HTML do alerta sem enviar o e-mail."""
    try:
        desconto = float(desconto_percentual)
    except (TypeError, ValueError) as exc:
        raise EmailTemplateError("O desconto precisa ser numérico.") from exc

    if not 0 <= desconto <= 100:
        raise EmailTemplateError("O desconto precisa estar entre 0 e 100.")

    jogo = _texto(nome_jogo, "nome_jogo")
    loja = _texto(loja_nome, "loja_nome")
    anterior = _texto(preco_anterior, "preco_anterior")
    atual = _texto(preco_atual, "preco_atual")
    url_oferta = _url(oferta_url, "oferta_url")
    url_preferencias = _url(preferencias_url, "preferencias_url")

    data = _texto(
        data_consulta
        or datetime.now().astimezone().strftime("%d/%m/%Y às %H:%M"),
        "data_consulta",
    )
    resumo = _texto(
        preheader or f"{nome_jogo}: agora por {preco_atual} na loja {loja_nome}.",
        "preheader",
    )

    imagem = _imagem_opcional(imagem_jogo_url)

    cards_html = f"""
          <tr>
            <td style="padding:20px 32px 8px;">
              <table role="presentation" width="100%" cellspacing="0"
                     cellpadding="0" border="0"
                     style="width:100%;border-collapse:separate;
                            border-spacing:0;background-color:#0F0E16;
                            border:1px solid #30264B;border-radius:12px;">
                <tr>
                  <td style="padding:18px;">
                    <table role="presentation" width="100%" cellspacing="0"
                           cellpadding="0" border="0">
                      <tr>
                        <td valign="top" style="padding-right:14px;">
                          <p style="margin:0 0 8px;color:#C4B5FD;
                                    font-size:11px;line-height:16px;
                                    font-weight:700;text-transform:uppercase;">
                            {loja}
                          </p>
                          <h2 style="margin:0;color:#FFFFFF;font-size:19px;
                                     line-height:25px;font-weight:800;">
                            {jogo}
                          </h2>
                        </td>
                        <td valign="top" align="right" width="112"
                            style="width:112px;">
                          {imagem}
                        </td>
                      </tr>
                    </table>

                    <table role="presentation" width="100%" cellspacing="0"
                           cellpadding="0" border="0"
                           style="margin-top:18px;border-top:1px solid #30264B;">
                      <tr>
                        <td style="padding-top:15px;">
                          <p style="margin:0;color:#A78BFA;font-size:12px;
                                    line-height:18px;font-weight:700;">
                            {desconto:g}% de desconto
                          </p>
                          <p style="margin:5px 0 0;color:#A39CB5;
                                    font-size:13px;line-height:19px;
                                    text-decoration:line-through;">
                            {anterior}
                          </p>
                          <p style="margin:0;color:#FFFFFF;font-size:29px;
                                    line-height:37px;font-weight:800;">
                            {atual}
                          </p>
                        </td>
                        <td valign="middle" align="right"
                            style="padding-top:15px;">
                          <a href="{url_oferta}"
                             style="display:inline-block;padding:12px 16px;
                                    background-color:#8B5CF6;border-radius:9px;
                                    color:#FFFFFF;text-decoration:none;
                                    font-size:13px;line-height:18px;
                                    font-weight:700;">
                            Ver oferta
                          </a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:14px 0 0;color:#A39CB5;
                              font-size:11px;line-height:17px;">
                      Consulta realizada em {data}
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
    """

    valores = {
        "assunto": f"Alerta de preço: {nome_jogo}",
        "aviso_rodape": "Este alerta foi enviado porque uma condição de preço foi atingida.",
        "cards_html": cards_html,
        "mais_html": "",
        "eyebrow": "ALERTA DE PREÇO",
        "titulo": "O preço que você acompanha mudou!",
        "subtitulo": f"{jogo} está disponível por {atual} na {loja}.",
        "preferencias_url": url_preferencias,
        "preheader": resumo,
    }

    html_template = Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))

    # O template atual ainda possui um link de descadastro, mas não existe
    # mecanismo de descadastro individual implementado. Removemos esse link
    # do HTML em vez de apresentar uma ação que não funciona.
    html_base = html_template.safe_substitute(
        {**valores, "descadastrar_url": url_preferencias}
    )

    html_base = html_base.replace(
        '&nbsp;┬À&nbsp;\n'
        '                <a href="$descadastrar_url" style="color:#C4B5FD; text-decoration:underline;">Parar de receber alertas por e-mail</a>',
        "",
    )

    return html_base
