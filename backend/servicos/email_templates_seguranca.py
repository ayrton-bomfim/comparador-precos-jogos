"""Templates de e-mails de segurança com a identidade visual do alerta de preço DESCTRL."""
from html import escape

def renderizar_email_seguranca(preheader: str, titulo: str, chamada: str, explicacao: str,
                               texto_botao: str, url: str, validade_minutos: int = 30) -> str:
    """Renderiza e-mail transacional usando a paleta e a estrutura do alerta de preço."""
    preheader_html = escape(preheader)
    titulo_html = escape(titulo)
    chamada_html = escape(chamada)
    explicacao_html = escape(explicacao)
    botao_html = escape(texto_botao)
    url_html = escape(url, quote=True)
    return f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <meta name="supported-color-schemes" content="dark">
  <title>{titulo_html}</title>
  <style>
    @media screen and (max-width: 600px) {{
      .email-shell {{ width: 100% !important; }}
      .content-pad {{ padding-left: 20px !important; padding-right: 20px !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#0B0B0F;font-family:Arial,Helvetica,sans-serif;color:#F8F7FF;-webkit-text-size-adjust:100%;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;mso-hide:all;">{preheader_html}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;border-collapse:collapse;background-color:#0B0B0F;">
    <tr><td align="center" style="padding:28px 12px;">
      <table role="presentation" class="email-shell" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;border-collapse:separate;border-spacing:0;background-color:#15131F;border:1px solid #30264B;border-radius:16px;overflow:hidden;">
        <tr><td class="content-pad" style="padding:26px 32px 22px;border-bottom:1px solid #30264B;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0"><tr>
            <td align="left" style="font-size:23px;line-height:28px;font-weight:800;letter-spacing:-0.6px;"><span style="color:#F8F7FF;">DES</span><span style="color:#A78BFA;">CTRL</span></td>
            <td align="right" style="font-size:11px;line-height:16px;color:#C4B5FD;text-transform:uppercase;letter-spacing:1.3px;">Segurança da conta</td>
          </tr></table>
        </td></tr>
        <tr><td class="content-pad" style="padding:28px 32px 10px;">
          <p style="margin:0 0 8px;color:#C4B5FD;font-size:12px;line-height:18px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;">{chamada_html}</p>
          <h1 style="margin:0;color:#FFFFFF;font-size:27px;line-height:34px;font-weight:800;letter-spacing:-0.5px;">{titulo_html}</h1>
          <p style="margin:12px 0 0;color:#C9C5D8;font-size:15px;line-height:23px;">{explicacao_html}</p>
        </td></tr>
        <tr><td class="content-pad" style="padding:22px 32px 0;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border-collapse:separate;border-spacing:0;border:1px solid #39304F;border-radius:12px;background-color:#0F0E16;">
            <tr><td style="padding:22px;">
              <p style="margin:0;color:#B9B2CD;font-size:13px;line-height:21px;">Por segurança, este link expira em <strong style="color:#F8F7FF;">{validade_minutos} minutos</strong> e só pode ser usado uma vez.</p>
              <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin-top:22px;border-collapse:separate;"><tr>
                <td align="center" bgcolor="#8B5CF6" style="border-radius:8px;">
                  <a href="{url_html}" target="_blank" style="display:inline-block;padding:14px 22px;border:1px solid #8B5CF6;border-radius:8px;color:#FFFFFF;font-size:15px;line-height:20px;font-weight:800;text-decoration:none;">{botao_html}</a>
                </td>
              </tr></table>
            </td></tr>
          </table>
        </td></tr>
        <tr><td class="content-pad" style="padding:24px 32px 28px;">
          <p style="margin:0;color:#B9B2CD;font-size:13px;line-height:21px;">Se você não solicitou esta operação, ignore esta mensagem. Nenhuma alteração será feita sem a confirmação pelo link.</p>
          <p style="margin:16px 0 0;color:#8E879F;font-size:12px;line-height:19px;">DESCTRL · Compare preços, escolha o melhor momento.</p>
          <p style="margin:12px 0 0;color:#8E879F;font-size:12px;line-height:19px;word-break:break-all;">Se o botão não funcionar, copie este endereço no navegador:<br><a href="{url_html}" style="color:#C4B5FD;text-decoration:underline;">{url_html}</a></p>
        </td></tr>
      </table>
      <table role="presentation" class="email-shell" width="600" cellspacing="0" cellpadding="0" border="0" style="width:100%;max-width:600px;border-collapse:collapse;">
        <tr><td align="center" style="padding:18px 20px 0;color:#777187;font-size:11px;line-height:17px;">Este é um e-mail automático do DESCTRL, enviado para proteger sua conta.</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>'''
