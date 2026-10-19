"""Rotas protegidas exclusivamente para administradores."""

from fastapi import APIRouter, Depends

from ..modelos import Usuario
from ..seguranca.autenticacao import obter_admin_atual


router = APIRouter(prefix="/api/admin", tags=["administracao"])
