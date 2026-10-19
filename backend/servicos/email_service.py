"""Serviço central de envio de e-mails via Resend para o DESCTRL.

A chave da API é lida do ambiente; nunca coloque segredos diretamente neste arquivo.
"""
import os
from typing import Any

import resend
from dotenv import load_dotenv

load_dotenv()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = os.getenv("RESEND_FROM_EMAIL", "onboarding@resend.dev").strip()


class EmailServiceError(RuntimeError):
    """Erro controlado ao tentar enviar um e-mail."""


def enviar_email(destinatario: str, assunto: str, html: str) -> dict[str, Any]:
    """Envia um e-mail transacional e retorna os dados de resposta do Resend.

    Requer RESEND_API_KEY no ambiente. O remetente padrão de onboarding é útil
    para o teste inicial; para produção, configure um remetente de domínio verificado.
    """
    if not RESEND_API_KEY:
        raise EmailServiceError(
            "RESEND_API_KEY não está configurada. Adicione-a ao arquivo .env do backend."
        )

    if not destinatario or not destinatario.strip():
        raise ValueError("O endereço do destinatário é obrigatório.")
    if not assunto or not assunto.strip():
        raise ValueError("O assunto do e-mail é obrigatório.")
    if not html or not html.strip():
        raise ValueError("O conteúdo HTML do e-mail é obrigatório.")

    resend.api_key = RESEND_API_KEY

    try:
        resposta = resend.Emails.send({
            "from": RESEND_FROM_EMAIL,
            "to": [destinatario.strip()],
            "subject": assunto.strip(),
            "html": html,
        })
        if isinstance(resposta, dict):
            return resposta
        # Compatibilidade com versões do SDK que retornam objetos de resposta.
        if hasattr(resposta, "model_dump"):
            return resposta.model_dump()
        if hasattr(resposta, "__dict__"):
            return dict(resposta.__dict__)
        return {"resposta": str(resposta)}
    except Exception as exc:
        raise EmailServiceError(f"Falha ao enviar e-mail pelo Resend: {exc}") from exc
