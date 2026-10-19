"""
Módulo principal da API.
Este módulo configura a aplicação FastAPI, registra os roteadores e define os endpoints de saúde.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from .seguranca.rate_limit import limiter
import os
from .rotas import (
    jogos, comparador, auth, admin, curadoria, favoritos,
    conquistas, alertas_preco, notificacoes, seguranca_conta, feedback
)

app = FastAPI(
    title="Comparador de Precos de Jogos",
    description="API para comparar precos de jogos na Steam e Epic Games Store",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
# Informe as origens permitidas em CORS_ORIGINS, separadas por vírgula.
# Na ausência da variável, mantém os endereços locais usados no desenvolvimento.
_origens_padrao = (
    "http://localhost:5173,http://127.0.0.1:5173,"
    "http://localhost:5174,http://127.0.0.1:5174,"
    "http://localhost:3000,http://127.0.0.1:3000"
)
CORS_ORIGINS = [
    origem.strip().rstrip("/")
    for origem in os.getenv("CORS_ORIGINS", _origens_padrao).split(",")
    if origem.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(jogos.router)
app.include_router(comparador.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(curadoria.router)
app.include_router(favoritos.router)
app.include_router(conquistas.router)
app.include_router(alertas_preco.router)
app.include_router(notificacoes.router)
app.include_router(seguranca_conta.router)
app.include_router(feedback.router)
app.include_router(feedback.admin_router)

@app.get("/")
def root():
    return {"mensagem": "API do Comparador de Precos", "versao": "1.0.0", "docs": "/docs", "redoc": "/redoc"}

@app.get("/health")
def health_check():
    return {"status": "online"}
