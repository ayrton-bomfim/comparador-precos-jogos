"""
Monta o e-mail de alerta de preço do DESCTRL.

Regra principal:
  - 1 jogo  -> card grande (capa em destaque)
  - 2+ jogos -> UM único e-mail com cards compactos (até MAX_JOGOS; o resto
                vira o link "Ver mais N promoções")

Uso:
    assunto, html, texto = montar_email(jogos, consultado_em="22/10/2026 às 14:30", ...)

Rodar este arquivo direto gera preview_1_jogo.html e preview_3_jogos.html
para você abrir no navegador.
"""
from __future__ import annotations

from dataclasses import dataclass
from email.message import EmailMessage
from html import escape
from pathlib import Path
from string import Template
from typing import Optional

MAX_JOGOS = 5
LAYOUT = Path(__file__).with_name("email_alerta_preco.html")


@dataclass
class Jogo:
    nome: str
    loja: str                       # loja onde a oferta foi encontrada (ex.: "Steam")
    preco_atual: str                # já formatado (ex.: "R$ 29,90")
    oferta_url: str
    imagem_url: str                 # 1 jogo: use banner HORIZONTAL (a capa vertical da Epic fica enorme)
    preco_anterior: Optional[str] = None     # preço base, já formatado
    desconto: Optional[int] = None           # percentual inteiro (ex.: 70)
    outra_loja: Optional[str] = None         # ex.: "Epic"
    outra_preco: Optional[str] = None        # ex.: "R$ 59,90"
    menor_historico: bool = False
    melhor_entre_lojas: bool = False
    termina_em: Optional[str] = None         # ex.: "30/10 às 14h"
    preco_alvo: Optional[str] = None         # preço-alvo definido pelo usuário
    parar_url: Optional[str] = None          # link "parar de acompanhar este jogo"


# ---------------------------------------------------------------- peças ------

def _selo(texto: str, bg: str, fg: str) -> str:
    return (
        f'<span style="display:inline-block; margin:0 6px 6px 0; padding:5px 9px; '
        f'border-radius:6px; background-color:{bg}; color:{fg}; font-size:12px; '
        f'line-height:16px; font-weight:800;">{escape(texto)}</span>'
    )


def _selos(j: Jogo, margem_topo: int) -> str:
    s = []
    if j.desconto:
        s.append(_selo(f"-{j.desconto}%", "#3B1D69", "#DDD0FF"))
    if j.menor_historico:
        s.append(_selo("Menor preço histórico", "#123B2E", "#A7F3D0"))
    if j.melhor_entre_lojas:
        s.append(_selo("Melhor preço entre as lojas", "#1E2F57", "#BFDBFE"))
    if not s:
        return ""
    return f'<p style="margin:{margem_topo}px 0 0; line-height:0;">{"".join(s)}</p>'


def _preco(j: Jogo, tamanho: int, linha: int, classe: str = "") -> str:
    antes = ""
    if j.preco_anterior:
        antes = (
            '<p style="margin:10px 0 0; color:#A39CB5; font-size:13px; line-height:18px;">'
            f'<span style="text-decoration:line-through;">{escape(j.preco_anterior)}</span>'
            '&nbsp; preço base</p>'
        )
    atual = (
        f'<p class="{classe}" style="margin:4px 0 0; color:#C4B5FD; font-size:{tamanho}px; '
        f'line-height:{linha}px; font-weight:800; letter-spacing:-0.5px;">{escape(j.preco_atual)}</p>'
    )
    return antes + atual


def _extras(j: Jogo, margem_topo: int) -> str:
    linhas = []
    if j.outra_loja and j.outra_preco:
        linhas.append(f"Na {escape(j.outra_loja)}: <strong style=\"color:#FFFFFF;\">{escape(j.outra_preco)}</strong>")
    if j.termina_em:
        linhas.append(f"Promoção até <strong style=\"color:#FFFFFF;\">{escape(j.termina_em)}</strong>")
    if j.preco_alvo:
        linhas.append(f"Seu preço-alvo: <strong style=\"color:#FFFFFF;\">{escape(j.preco_alvo)}</strong>")
    if not linhas:
        return ""
    corpo = "<br>".join(linhas)
    return (
        f'<p style="margin:{margem_topo}px 0 0; color:#C9C5D8; font-size:13px; line-height:21px;">'
        f"{corpo}</p>"
    )


def _botao(url: str, rotulo: str, largura: int = 220, altura: int = 46, fonte: int = 15) -> str:
    """Botão 'à prova de balas': VML no Outlook desktop, <a> estilizado no resto."""
    href = escape(url, quote=True)
    rot = escape(rotulo)
    return (
        "<!--[if mso]>"
        f'<v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" xmlns:w="urn:schemas-microsoft-com:office:word" '
        f'href="{href}" style="height:{altura}px; v-text-anchor:middle; width:{largura}px;" '
        f'arcsize="18%" stroke="f" fillcolor="#7C3AED"><w:anchorlock/>'
        f'<center style="color:#FFFFFF; font-family:Arial,sans-serif; font-size:{fonte}px; font-weight:bold;">{rot}</center>'
        "</v:roundrect><![endif]-->"
        "<!--[if !mso]><!-->"
        f'<a href="{href}" target="_blank" style="display:inline-block; padding:{(altura - fonte * 1.35) / 2:.0f}px 22px; '
        f"background-color:#7C3AED; border:1px solid #7C3AED; border-radius:8px; color:#FFFFFF; "
        f'font-size:{fonte}px; line-height:{round(fonte * 1.35)}px; font-weight:800; text-decoration:none;">{rot}</a>'
        "<!--<![endif]-->"
    )


def _link_parar(j: Jogo) -> str:
    if not j.parar_url:
        return ""
    return (
        '<p style="margin:14px 0 0; font-size:12px; line-height:18px;">'
        f'<a href="{escape(j.parar_url, quote=True)}" style="color:#A39CB5; text-decoration:underline;">'
        "Parar de acompanhar este jogo</a></p>"
    )


def _linha(card: str, topo: int = 22) -> str:
    """Envolve um card numa linha da tabela principal."""
    return (
        f'<tr><td class="content-pad" style="padding:{topo}px 32px 0;">{card}</td></tr>'
    )


# --------------------------------------------------------------- cards -------

_CARD_ABRE = (
    '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
    'bgcolor="#0F0E16" style="border-collapse:separate; border-spacing:0; overflow:hidden; '
    'border:1px solid #39304F; border-radius:12px; background-color:#0F0E16;">'
)


def _card_grande(j: Jogo, consultado_em: str) -> str:
    return _CARD_ABRE + (
        '<tr><td align="center" bgcolor="#0F0E16" style="padding:0;">'
        f'<img class="game-image" src="{escape(j.imagem_url, quote=True)}" width="534" '
        f'alt="Capa de {escape(j.nome, quote=True)}" '
        'style="display:block; width:100%; max-width:534px; height:auto; border:0; outline:none; '
        'text-decoration:none; color:#F8F7FF; font-size:16px;"></td></tr>'
        '<tr><td style="padding:20px 22px 22px;">'
        f'<p style="margin:0 0 7px; color:#B9B2CD; font-size:12px; line-height:18px; text-transform:uppercase; '
        f'letter-spacing:1.1px;">Oferta encontrada em {escape(j.loja)}</p>'
        f'<h2 style="margin:0; color:#FFFFFF; font-size:22px; line-height:29px; font-weight:800;">{escape(j.nome)}</h2>'
        + _selos(j, 14)
        + _preco(j, 36, 42, "price-current")
        + _extras(j, 14)
        + f'<p style="margin:12px 0 0; color:#A7A0B9; font-size:12px; line-height:18px;">'
          f"Preço consultado em {escape(consultado_em)}. O valor pode mudar na loja.</p>"
        + '<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:20px;">'
          "<tr><td>" + _botao(j.oferta_url, "Ver oferta na loja") + "</td></tr></table>"
        + _link_parar(j)
        + "</td></tr></table>"
    )


def _card_compacto(j: Jogo) -> str:
    return _CARD_ABRE + (
        "<tr>"
        '<td width="96" valign="top" style="padding:16px 0 16px 16px;">'
        f'<img src="{escape(j.imagem_url, quote=True)}" width="96" alt="Capa de {escape(j.nome, quote=True)}" '
        'style="display:block; width:96px; height:auto; border:0; border-radius:8px; color:#F8F7FF; font-size:12px;"></td>'
        '<td valign="top" style="padding:16px;">'
        f'<p style="margin:0 0 4px; color:#B9B2CD; font-size:11px; line-height:16px; text-transform:uppercase; '
        f'letter-spacing:1px;">{escape(j.loja)}</p>'
        f'<h2 style="margin:0; color:#FFFFFF; font-size:17px; line-height:23px; font-weight:800;">{escape(j.nome)}</h2>'
        + _selos(j, 10)
        + _preco(j, 24, 30)
        + _extras(j, 8)
        + '<table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:12px;">'
          "<tr><td>" + _botao(j.oferta_url, "Ver oferta", largura=130, altura=38, fonte=14) + "</td></tr></table>"
        + _link_parar(j)
        + "</td></tr></table>"
    )


# ------------------------------------------------------------- montagem ------

def _textos(jogos: list[Jogo]) -> dict[str, str]:
    """Assunto, preheader, eyebrow, título e subtítulo conforme a quantidade de jogos."""
    n = len(jogos)
    if n == 1:
        j = jogos[0]
        titulo = (
            f"{j.nome} chegou ao seu preço-alvo"
            if j.preco_alvo
            else f"{j.nome} caiu para {j.preco_atual}"
        )
        pre = f"Oferta na {j.loja}" + (f" com {j.desconto}% de desconto" if j.desconto else "")
        return {
            "assunto": f"{titulo} · DESCTRL",
            "eyebrow": "Promoção detectada",
            "titulo": titulo,
            "subtitulo": f"Encontramos esta oferta na {j.loja}.",
            "preheader": pre,
        }
    nomes = ", ".join(j.nome for j in jogos[:3]) + ("…" if n > 3 else "")
    titulo = f"{n} jogos da sua lista entraram em promoção"
    return {
        "assunto": f"{titulo} · DESCTRL",
        "eyebrow": "Promoções detectadas",
        "titulo": titulo,
        "subtitulo": "Reunimos tudo em um único e-mail para não lotar sua caixa de entrada.",
        "preheader": nomes,
    }


def _texto_puro(jogos: list[Jogo], t: dict[str, str], consultado_em: str,
                preferencias_url: str, descadastrar_url: str,
                ver_todos_url: Optional[str], restantes: int) -> str:
    linhas = [t["titulo"], t["subtitulo"], ""]
    for j in jogos:
        linhas.append(f"{j.nome} - {j.preco_atual} ({j.loja})")
        if j.preco_anterior:
            linhas.append(f"  Preço base: {j.preco_anterior}" + (f" (-{j.desconto}%)" if j.desconto else ""))
        if j.outra_loja and j.outra_preco:
            linhas.append(f"  Na {j.outra_loja}: {j.outra_preco}")
        if j.menor_historico:
            linhas.append("  Menor preço histórico")
        if j.termina_em:
            linhas.append(f"  Promoção até {j.termina_em}")
        if j.preco_alvo:
            linhas.append(f"  Seu preço-alvo: {j.preco_alvo}")
        linhas.append(f"  Ver oferta: {j.oferta_url}")
        linhas.append("")
    if restantes and ver_todos_url:
        linhas += [f"+ {restantes} promoções: {ver_todos_url}", ""]
    linhas += [
        f"Preços consultados em {consultado_em}. Valores informativos, podem mudar na loja.",
        f"Gerenciar alertas: {preferencias_url}",
        f"Parar de receber alertas por e-mail: {descadastrar_url}",
    ]
    return "\n".join(linhas)


def montar_email(
    jogos: list[Jogo],
    *,
    consultado_em: str,
    preferencias_url: str,
    descadastrar_url: str,
    ver_todos_url: Optional[str] = None,
) -> tuple[str, str, str]:
    """Retorna (assunto, html, texto_puro). Um único e-mail, qualquer que seja a quantidade de jogos."""
    if not jogos:
        raise ValueError("Nenhum jogo para enviar.")

    total = len(jogos)
    t = _textos(jogos)                      # textos usam o total real, não o recortado
    exibidos = jogos[:MAX_JOGOS]
    restantes = total - len(exibidos)

    if total == 1:
        cards = _linha(_card_grande(exibidos[0], consultado_em))
        aviso = "Você está recebendo este e-mail porque acompanha este jogo no DESCTRL."
    else:
        cards = "".join(_linha(_card_compacto(j), topo=18 if i else 22) for i, j in enumerate(exibidos))
        cards += _linha(
            '<p style="margin:0; color:#A7A0B9; font-size:12px; line-height:18px;">'
            f"Preços consultados em {escape(consultado_em)}. Os valores podem mudar na loja.</p>",
            topo=14,
        )
        aviso = "Você está recebendo este e-mail porque acompanha estes jogos no DESCTRL."

    mais = ""
    if restantes and ver_todos_url:
        mais = _linha(
            '<table role="presentation" cellspacing="0" cellpadding="0" border="0"><tr><td>'
            + _botao(ver_todos_url, f"Ver mais {restantes} promoç{'ão' if restantes == 1 else 'ões'}", largura=240)
            + "</td></tr></table>",
            topo=18,
        )

    html = Template(LAYOUT.read_text(encoding="utf-8")).safe_substitute(
        assunto=escape(t["assunto"]),
        preheader=escape(t["preheader"]) + "&zwnj;&nbsp;" * 60,   # evita puxar texto do corpo na prévia
        eyebrow=escape(t["eyebrow"]),
        titulo=escape(t["titulo"]),
        subtitulo=escape(t["subtitulo"]),
        cards_html=cards,
        mais_html=mais,
        aviso_rodape=escape(aviso),
        preferencias_url=escape(preferencias_url, quote=True),
        descadastrar_url=escape(descadastrar_url, quote=True),
    )
    texto = _texto_puro(exibidos, t, consultado_em, preferencias_url, descadastrar_url, ver_todos_url, restantes)
    return t["assunto"], html, texto


def montar_mensagem(destinatario: str, remetente: str, assunto: str, html: str, texto: str,
                    descadastrar_url: str) -> EmailMessage:
    """Mensagem multipart (texto + HTML) com cabeçalhos de descadastro de um clique."""
    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = remetente
    msg["To"] = destinatario
    msg["List-Unsubscribe"] = f"<{descadastrar_url}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"   # exige endpoint que aceite POST
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    return msg


# --------------------------------------------------------------- preview -----

if __name__ == "__main__":
    base = dict(
        consultado_em="22/10/2026 às 14:30",
        preferencias_url="https://desctrl.example/conta/alertas",
        descadastrar_url="https://desctrl.example/alertas/cancelar?t=abc123",
        ver_todos_url="https://desctrl.example/favoritos",
    )
    exemplo = [
        Jogo("Hollow Knight", "Steam", "R$ 14,99", "https://store.steampowered.com/app/367520",
             "https://cdn.example/hk-banner.jpg", preco_anterior="R$ 46,99", desconto=68,
             outra_loja="Epic", outra_preco="R$ 46,99", menor_historico=True, melhor_entre_lojas=True,
             termina_em="30/10 às 14h", parar_url="https://desctrl.example/favoritos/remover/1"),
        Jogo("Hades", "Epic", "R$ 36,99", "https://store.epicgames.com/p/hades",
             "https://cdn.example/hades.jpg", preco_anterior="R$ 73,99", desconto=50, preco_alvo="R$ 40,00",
             parar_url="https://desctrl.example/favoritos/remover/2"),
        Jogo("Celeste", "Steam", "R$ 19,99", "https://store.steampowered.com/app/504230",
             "https://cdn.example/celeste.jpg"),
    ]
    for nome, lista in (("preview_1_jogo.html", exemplo[:1]), ("preview_3_jogos.html", exemplo)):
        assunto, html, texto = montar_email(lista, **base)
        Path(nome).write_text(html, encoding="utf-8")
        print(f"{nome}: {assunto}")
