from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rotas import jogos, comparador

app = FastAPI(
    title="Comparador de Precos de Jogos",
    description="API para comparar precos de jogos na Steam e Epic Games Store",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jogos.router)
app.include_router(comparador.router)

@app.get("/")
def raiz():
    return {"mensagem": "API do Comparador de Precos", "versao": "1.0.0"}

@app.get("/saude")
def saude():
    return {"status": "online", "mensagem": "API esta funcionando!"}