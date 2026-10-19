"""Configuração compartilhada de limite de requisições HTTP."""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Usa o IP do cliente direto. Em produção atrás de proxy, configure o proxy
# confiável no servidor de implantação antes de confiar em cabeçalhos forwarded.
limiter = Limiter(key_func=get_remote_address)
