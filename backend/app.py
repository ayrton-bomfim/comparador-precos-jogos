"""
Módulo principal da API.

Este módulo configura a aplicação FastAPI, registra os roteadores
e define os endpoints de verificação de saúde da API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .rotas import jogos, comparador


app = FastAPI(
    title="Comparador de Precos de Jogos",
    description="API para comparar precos de jogos na Steam e Epic Games Store",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Permite que o frontend seja acessado tanto por localhost
# quanto por 127.0.0.1.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro dos roteadores da API
app.include_router(jogos.router)
app.include_router(comparador.router)


@app.get("/")
def root():
    """
    Endpoint raiz da API.
    Retorna uma mensagem de boas-vindas e a versao da aplicacao.
    """
    return {
        "mensagem": "API do Comparador de Precos",
        "versao": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


@app.get("/health")
def health_check():
    """
    Endpoint de verificacao de saude da API.
    Utilizado para monitoramento e testes de conectividade.
    """
    return {"status": "online"}