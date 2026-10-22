"""Serviço central de envio de e-mails via Resend para o DESCTRL.

A chave da API é lida do ambiente; nunca coloque segredos diretamente neste arquivo.
"""
import os
from typing import Any

import resend

from ..config import settings  # Garante o carregamento explícito de backend/.env.

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()
RESEND_FROM_EMAIL = settings.RESEND_FROM_EMAIL


class EmailServiceError(RuntimeError):
    """Erro controlado ao tentar enviar um e-mail."""


def enviar_email(destinatario: str, assunto: str, html: str) -> dict[str, Any]:
    """Envia e-mail transacional via Resend.

    Em produção, configure RESEND_API_KEY e RESEND_FROM_EMAIL no arquivo
    backend/.env. O remetente padrão de onboarding é destinado apenas a testes.
    """
    if not RESEND_API_KEY:
        raise EmailServiceError(
            "RESEND_API_KEY não está configurada. Adicione-a ao arquivo .env do backend."
        )

    if not destinatario or not destinatario.strip():
        raise ValueError("O endereço de e-mail do destinatário é obrigatório.")
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
        if hasattr(resposta, "model_dump"):
            return resposta.model_dump()
        if hasattr(resposta, "__dict__"):
            return dict(resposta.__dict__)
        return {"resposta": str(resposta)}
    except Exception as exc:
        raise EmailServiceError(f"Falha ao enviar e-mail pelo Resend: {exc}") from exc
