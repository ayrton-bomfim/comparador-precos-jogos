"""
COLETOR COMPLETO DE DADOS STEAM

Objetivo
--------
Consultar o Steam AppDetails para todos os jogos que possuem steam_id
na tabela `jogos` e atualizar os dados Steam já existentes no modelo.

Também classifica a disponibilidade INDIVIDUAL do jogo na Steam Brasil:

    DISPONIVEL
    GRATUITO
    INDISPONIVEL
    INDETERMINADO

Regras de disponibilidade
-------------------------
1. type != "game":
       não é tratado como jogo comercial; não grava disponibilidade.
2. is_free == True:
       GRATUITO
3. price_overview.currency == "BRL" e existe preço final:
       DISPONIVEL
4. Sem preço próprio:
       consulta a página individual da loja com cc=br.
5. Se a página indicar indisponibilidade regional:
       INDISPONIVEL
6. Caso não exista evidência suficiente:
       INDETERMINADO

IMPORTANTE
----------
- Bundles/pacotes não contam como disponibilidade individual.
- Nenhum dado é marcado como atualizado antes de o AppDetails ser
  considerado válido e os dados serem preparados para gravação.
- HTTP 429 recebe retry com backoff e pausa adicional.
- O progresso é salvo em CSV. Um jogo só entra como concluído no
  checkpoint depois de uma resposta válida ter sido processada.
- O script NÃO apaga dados antigos antes de receber uma resposta válida.
- A flag `steam_conteudo_adulto` não é alterada por este coletor, pois
  ela pertence à lógica editorial do projeto.
- O script usa apenas as colunas que já existem em `jogos`, incluindo
  `steam_disponibilidade_br`.

Execução
--------
A partir da raiz do projeto:

    python coletar_dados_steam_completo.py

O script pode ser interrompido com Ctrl+C e executado novamente.
Os registros concluídos no CSV de checkpoint serão ignorados.

Para uma nova coleta do zero, apague:
    coleta_steam_completa_checkpoint.csv

ANTES DE EXECUTAR
-----------------
Confirme que `backend/modelos.py` contém:

    steam_disponibilidade_br = Column(String(30), nullable=True)

e que a coluna já existe no PostgreSQL.
"""

import argparse
import csv
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock, local

import requests
from sqlalchemy.exc import SQLAlchemyError

from backend.banco_dados import SessionLocal
from backend.modelos import Jogo


# ============================================================
# CONFIGURAÇÃO
# ============================================================

URL_APPDETAILS = "https://store.steampowered.com/api/appdetails"
URL_STORE = "https://store.steampowered.com/app/{steam_id}/"

ARQUIVO_CHECKPOINT = "coleta_steam_completa_checkpoint.csv"

# Começamos conservadores por causa dos 429 encontrados na coleta anterior.
WORKERS = 3
INTERVALO_MINIMO_REQUISICAO = 0.75

TIMEOUT = 30
TENTATIVAS = 5

# Depois de vários 429 seguidos, todos os workers aguardam.
MAX_429_CONSECUTIVOS = 5
PAUSA_APOS_MUITOS_429 = 60

# Commit em lotes no banco.
BATCH_DB = 25

# O script reprocessa inclusive os 144 registros que já tinham
# alguns dados, porque a coleta anterior foi considerada incompleta.
# O checkpoint controla a retomada desta NOVA coleta.
REPROCESSAR_TODOS = True


# ============================================================
# CHECKPOINT
# ============================================================

COLUNAS_CHECKPOINT = [
    "jogo_id",
    "steam_id",
    "classificacao",
    "http_status_appdetails",
    "http_status_store",
    "erro",
]


# ============================================================
# HTTP / RATE LIMIT
# ============================================================

_thread_local = local()

rate_lock = Lock()
estado_rate = {
    "ultimo_inicio": 0.0,
    "consecutivos_429": 0,
}


def obter_sessao_http():
    if not hasattr(_thread_local, "session"):
        _thread_local.session = requests.Session()
        _thread_local.session.headers.update({
            "User-Agent": (
                "ComparadorPrecosJogos/1.0 "
                "(coleta-dados-steam)"
            )
        })

    return _thread_local.session


def esperar_intervalo():
    """
    Controla um intervalo GLOBAL entre requisições.

    Os workers podem processar respostas em paralelo, mas não disparam
    requisições simultaneamente.
    """
    with rate_lock:
        agora = time.monotonic()

        espera = (
            INTERVALO_MINIMO_REQUISICAO
            - (agora - estado_rate["ultimo_inicio"])
        )

        if espera > 0:
            time.sleep(espera)

        estado_rate["ultimo_inicio"] = time.monotonic()


def registrar_resposta_http(status_code):
    with rate_lock:
        if status_code == 429:
            estado_rate["consecutivos_429"] += 1

            if (
                estado_rate["consecutivos_429"]
                >= MAX_429_CONSECUTIVOS
            ):
                print(
                    "\n[RATE LIMIT] Muitos HTTP 429. "
                    f"Pausando {PAUSA_APOS_MUITOS_429}s...\n"
                )

                # A pausa ocorre sob o lock para impedir que outro
                # worker continue disparando requisições durante a espera.
                time.sleep(PAUSA_APOS_MUITOS_429)

                estado_rate["consecutivos_429"] = 0

        elif status_code is not None:
            estado_rate["consecutivos_429"] = 0


def request_get(url, **kwargs):
    ultimo_erro = None

    for tentativa in range(1, TENTATIVAS + 1):
        try:
            esperar_intervalo()

            resposta = obter_sessao_http().get(
                url,
                timeout=TIMEOUT,
                **kwargs,
            )

            registrar_resposta_http(resposta.status_code)

            if resposta.status_code == 429:
                retry_after = resposta.headers.get("Retry-After")

                if retry_after:
                    try:
                        espera = float(retry_after)
                    except ValueError:
                        espera = min(10 * tentativa, 60)
                else:
                    espera = min(10 * tentativa, 60)

                ultimo_erro = RuntimeError(
                    f"HTTP 429 - tentativa {tentativa}/{TENTATIVAS}"
                )

                if tentativa < TENTATIVAS:
                    print(
                        f"[429] Aguardando {espera:.1f}s "
                        f"antes da tentativa {tentativa + 1}..."
                    )
                    time.sleep(espera)
                    continue

                raise ultimo_erro

            if resposta.status_code in (500, 502, 503, 504):
                ultimo_erro = RuntimeError(
                    f"HTTP {resposta.status_code} "
                    f"- tentativa {tentativa}/{TENTATIVAS}"
                )

                if tentativa < TENTATIVAS:
                    time.sleep(min(5 * tentativa, 30))
                    continue

                raise ultimo_erro

            return resposta

        except requests.RequestException as erro:
            ultimo_erro = erro

            if tentativa < TENTATIVAS:
                espera = min(5 * tentativa, 30)
                time.sleep(espera)

    if ultimo_erro:
        raise ultimo_erro

    raise RuntimeError("Falha HTTP sem erro identificado.")


# ============================================================
# PARSERS
# ============================================================

def normalizar_texto(valor):
    if valor is None:
        return None

    if isinstance(valor, str):
        valor = valor.strip()

    return valor if valor != "" else None


def parse_data_lancamento(release_date):
    """
    A Steam normalmente fornece datas como:
        '25 Oct, 2024'

    Se a data não puder ser interpretada, retorna None.
    """
    if not release_date:
        return None

    texto = str(release_date).strip()

    formatos = [
        "%d %b, %Y",
        "%d %B, %Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]

    for formato in formatos:
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue

    return None


def extrair_imagem_header(data):
    return normalizar_texto(data.get("header_image"))


def extrair_developer(data):
    developers = data.get("developers") or []

    if isinstance(developers, list):
        valores = [
            str(item).strip()
            for item in developers
            if item
        ]
        if valores:
            return ", ".join(valores)

    return None


def extrair_publishers(data):
    publishers = data.get("publishers") or []

    if isinstance(publishers, list):
        valores = [
            str(item).strip()
            for item in publishers
            if item
        ]
        if valores:
            return ", ".join(valores)

    return None


def extrair_generos(data):
    generos = data.get("genres") or []

    if not isinstance(generos, list):
        return None

    nomes = []

    for item in generos:
        if isinstance(item, dict):
            nome = item.get("description")
            if nome:
                nomes.append(str(nome).strip())

    return ", ".join(nomes) if nomes else None


def extrair_supported_languages(data):
    valor = data.get("supported_languages")

    if not valor:
        return None

    # Mantemos o HTML original retornado pela Steam.
    return str(valor)


def extrair_content_notes(data):
    valor = data.get("content_notes")

    if not valor:
        return None

    return str(valor)


def extrair_requisitos(data, plataforma):
    requisitos = data.get(f"{plataforma}_requirements")

    if not requisitos:
        return None

    return requisitos


def extrair_ratings(data):
    ratings = data.get("ratings")

    if not ratings:
        return None

    return ratings


def extrair_content_descriptors(data):
    valor = data.get("content_descriptors")

    if not valor:
        return None

    return valor


# ============================================================
# DISPONIBILIDADE BR
# ============================================================

def pagina_indica_indisponibilidade_br(html):
    texto = (html or "").lower()

    sinais = [
        "indisponível em português (brasil)",
        "indisponivel em portugues (brasil)",
        "indisponível no seu país",
        "indisponivel no seu pais",
        "não disponível no seu país",
        "nao disponivel no seu pais",
        "not available in your region",
        "not available in your country",
    ]

    encontrados = [
        sinal
        for sinal in sinais
        if sinal in texto
    ]

    return encontrados


def classificar_disponibilidade(data, html_store=None):
    """
    Retorna:
        classificacao,
        observacao
    """
    if data.get("type") != "game":
        return None, "type diferente de game"

    if data.get("is_free") is True:
        return "GRATUITO", "is_free=true"

    price = data.get("price_overview") or {}

    if (
        price.get("currency") == "BRL"
        and price.get("final") is not None
    ):
        return "DISPONIVEL", "preço próprio em BRL"

    # Sem preço próprio:
    # bundles/packages não são considerados.
    if html_store is None:
        return "INDETERMINADO", "sem preço próprio; página da loja não consultada"

    sinais = pagina_indica_indisponibilidade_br(html_store)

    if sinais:
        return (
            "INDISPONIVEL",
            " | ".join(sinais),
        )

    return (
        "INDETERMINADO",
        "sem preço próprio e sem sinal conclusivo de indisponibilidade",
    )


# ============================================================
# CONSULTAS STEAM
# ============================================================

def buscar_appdetails(steam_id):
    resposta = request_get(
        URL_APPDETAILS,
        params={
            "appids": steam_id,
            "l": "portuguese",
            "cc": "br",
        },
    )

    payload = resposta.json()

    item = payload.get(str(steam_id))

    if not isinstance(item, dict):
        raise RuntimeError(
            "Resposta AppDetails sem entrada para o AppID."
        )

    if item.get("success") is not True:
        return {
            "status": "APPDETAILS_SUCCESS_FALSE",
            "http_status": resposta.status_code,
            "data": None,
        }

    data = item.get("data")

    if not isinstance(data, dict):
        raise RuntimeError(
            "AppDetails retornou success=true, mas data não é objeto."
        )

    return {
        "status": "OK",
        "http_status": resposta.status_code,
        "data": data,
    }


def buscar_pagina_loja(steam_id):
    resposta = request_get(
        URL_STORE.format(steam_id=steam_id),
        params={
            "cc": "br",
            "l": "brazilian",
        },
    )

    return resposta.status_code, resposta.text


# ============================================================
# PREPARAÇÃO DO RESULTADO
# ============================================================

def processar_jogo(jogo):
    steam_id = str(jogo.steam_id)

    resultado = {
        "jogo_id": jogo.id,
        "steam_id": steam_id,
        "classificacao": "",
        "http_status_appdetails": "",
        "http_status_store": "",
        "erro": "",
        "dados": None,
    }

    try:
        app = buscar_appdetails(steam_id)

        resultado["http_status_appdetails"] = app["http_status"]

        if app["status"] != "OK":
            resultado["classificacao"] = app["status"]
            return resultado

        data = app["data"]

        # Não é jogo.
        if data.get("type") != "game":
            resultado["classificacao"] = "NAO_E_GAME"
            resultado["dados"] = {
                "nome": normalizar_texto(data.get("name")),
                "steam_is_free": bool(data.get("is_free", False)),
                "steam_disponibilidade_br": None,
            }
            return resultado

        html_store = None

        price = data.get("price_overview") or {}

        precisa_consultar_loja = not (
            data.get("is_free") is True
            or (
                price.get("currency") == "BRL"
                and price.get("final") is not None
            )
        )

        if precisa_consultar_loja:
            status_store, html_store = buscar_pagina_loja(steam_id)
            resultado["http_status_store"] = status_store

        disponibilidade, observacao = classificar_disponibilidade(
            data,
            html_store,
        )

        preco_base = None

        if (
            price.get("currency") == "BRL"
            and price.get("initial") is not None
        ):
            preco_base = price.get("initial", 0) / 100

        # A classificação é preparada somente depois que toda a consulta
        # necessária terminou com sucesso.
        resultado["classificacao"] = "OK"
        resultado["dados"] = {
            "nome": normalizar_texto(data.get("name")),
            "desenvolvedor": extrair_developer(data),
            "publicadora": extrair_publishers(data),
            "genero": extrair_generos(data),
            "data_lancamento": parse_data_lancamento(
                (data.get("release_date") or {}).get("date")
            ),
            "descricao_steam": normalizar_texto(
                data.get("detailed_description")
            ),
            "url_steam": (
                f"https://store.steampowered.com/app/{steam_id}/"
            ),
            "preco_base_steam": preco_base,
            "url_imagem_steam": extrair_imagem_header(data),

            "steam_required_age": (
                int(data["required_age"])
                if str(data.get("required_age", "")).isdigit()
                else None
            ),
            "steam_is_free": bool(data.get("is_free", False)),
            "steam_metacritic_score": (
                (data.get("metacritic") or {}).get("score")
            ),
            "steam_website": normalizar_texto(
                data.get("website")
            ),
            "steam_platforms": data.get("platforms"),
            "steam_categories": data.get("categories"),
            "steam_genres": data.get("genres"),
            "steam_ratings": extrair_ratings(data),
            "steam_content_descriptors": (
                extrair_content_descriptors(data)
            ),
            "steam_supported_languages": (
                extrair_supported_languages(data)
            ),
            "steam_content_notes": extrair_content_notes(data),

            "steam_pc_requirements": extrair_requisitos(
                data,
                "pc",
            ),
            "steam_mac_requirements": extrair_requisitos(
                data,
                "mac",
            ),
            "steam_linux_requirements": extrair_requisitos(
                data,
                "linux",
            ),

            "steam_disponibilidade_br": disponibilidade,
            "steam_disponibilidade_br_observacao": observacao,

            "steam_release_state": (
                (data.get("release_date") or {}).get("coming_soon")
            ),
        }

        return resultado

    except requests.HTTPError as erro:
        resultado["classificacao"] = "ERRO_HTTP"
        resultado["erro"] = str(erro)[:500]
        return resultado

    except requests.RequestException as erro:
        resultado["classificacao"] = "ERRO_REQUISICAO"
        resultado["erro"] = str(erro)[:500]
        return resultado

    except Exception as erro:
        resultado["classificacao"] = "ERRO_INESPERADO"
        resultado["erro"] = repr(erro)[:500]
        return resultado


# ============================================================
# CHECKPOINT
# ============================================================

def inicializar_checkpoint():
    if os.path.exists(ARQUIVO_CHECKPOINT):
        return

    with open(
        ARQUIVO_CHECKPOINT,
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=COLUNAS_CHECKPOINT,
        )
        escritor.writeheader()


def carregar_concluidos():
    concluidos = set()

    if not os.path.exists(ARQUIVO_CHECKPOINT):
        return concluidos

    with open(
        ARQUIVO_CHECKPOINT,
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as arquivo:
        leitor = csv.DictReader(arquivo)

        for linha in leitor:
            classificacao = (
                linha.get("classificacao") or ""
            )

            # Só pulamos registros que realmente terminaram com sucesso.
            if classificacao in (
                "OK",
                "NAO_E_GAME",
            ):
                steam_id = (
                    linha.get("steam_id") or ""
                ).strip()

                if steam_id:
                    concluidos.add(steam_id)

    return concluidos


def salvar_checkpoint(resultado):
    if resultado["classificacao"] not in (
        "OK",
        "NAO_E_GAME",
    ):
        return

    with open(
        ARQUIVO_CHECKPOINT,
        "a",
        encoding="utf-8-sig",
        newline="",
    ) as arquivo:
        escritor = csv.DictWriter(
            arquivo,
            fieldnames=COLUNAS_CHECKPOINT,
        )

        escritor.writerow({
            "jogo_id": resultado["jogo_id"],
            "steam_id": resultado["steam_id"],
            "classificacao": resultado["classificacao"],
            "http_status_appdetails": (
                resultado["http_status_appdetails"]
            ),
            "http_status_store": (
                resultado["http_status_store"]
            ),
            "erro": resultado["erro"],
        })


# ============================================================
# BANCO
# ============================================================

def aplicar_dados(db, resultado):
    if resultado["classificacao"] not in (
        "OK",
        "NAO_E_GAME",
    ):
        return False

    jogo = db.get(Jogo, resultado["jogo_id"])

    if jogo is None:
        raise RuntimeError(
            f"Jogo id={resultado['jogo_id']} não encontrado."
        )

    dados = resultado["dados"] or {}

    campos = [
        "nome",
        "desenvolvedor",
        "publicadora",
        "genero",
        "data_lancamento",
        "descricao_steam",
        "url_steam",
        "preco_base_steam",
        "url_imagem_steam",
        "steam_required_age",
        "steam_is_free",
        "steam_metacritic_score",
        "steam_website",
        "steam_platforms",
        "steam_categories",
        "steam_genres",
        "steam_ratings",
        "steam_content_descriptors",
        "steam_supported_languages",
        "steam_content_notes",
        "steam_pc_requirements",
        "steam_mac_requirements",
        "steam_linux_requirements",
        "steam_disponibilidade_br",
    ]

    for campo in campos:
        if campo in dados:
            setattr(jogo, campo, dados[campo])

    # Só marcamos a data quando a resposta foi considerada válida
    # e os dados chegaram até esta etapa de gravação.
    jogo.steam_dados_atualizados_em = datetime.now()

    return True


# ============================================================
# MAIN
# ============================================================

def obter_limite():
    parser = argparse.ArgumentParser(
        description="Coleta completa de dados da Steam."
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Quantidade máxima de jogos a processar nesta execução.",
    )
    args = parser.parse_args()

    if args.limite is not None and args.limite <= 0:
        parser.error("--limite deve ser maior que zero.")

    return args.limite


def main():
    limite = obter_limite()
    print("=" * 110)
    print("COLETA COMPLETA DE DADOS STEAM")
    print("=" * 110)
    print(f"Workers: {WORKERS}")
    print(
        f"Intervalo mínimo global entre requisições: "
        f"{INTERVALO_MINIMO_REQUISICAO:.2f}s"
    )
    print(f"Checkpoint: {ARQUIVO_CHECKPOINT}")
    if limite is not None:
        print(f"Limite solicitado: {limite}")
    else:
        print("Limite solicitado: nenhum (execução completa)")
    print()
    print("O script:")
    print("- atualiza somente depois de uma resposta válida;")
    print("- trata HTTP 429 com backoff;")
    print("- não considera bundles como venda individual;")
    print("- grava a disponibilidade individual na Steam Brasil;")
    print("- preserva steam_conteudo_adulto;")
    print("- permite retomada pelo checkpoint.")
    print()

    inicializar_checkpoint()
    concluidos = carregar_concluidos()

    print(
        f"Registros concluídos no checkpoint: "
        f"{len(concluidos)}"
    )

    db = SessionLocal()

    try:
        jogos = (
            db.query(
                Jogo.id,
                Jogo.steam_id,
                Jogo.nome,
            )
            .filter(Jogo.steam_id.isnot(None))
            .order_by(Jogo.id)
            .all()
        )

        total = len(jogos)

        if REPROCESSAR_TODOS:
            pendentes = [
                jogo
                for jogo in jogos
                if str(jogo.steam_id) not in concluidos
            ]
        else:
            pendentes = [
                jogo
                for jogo in jogos
                if (
                    str(jogo.steam_id) not in concluidos
                    and jogo.steam_dados_atualizados_em is None
                )
            ]

        total_pendentes = len(pendentes)

        if limite is not None:
            pendentes = pendentes[:limite]

        print(f"Total com steam_id: {total}")
        print(f"Pendentes encontrados: {total_pendentes}")
        if limite is not None:
            print(f"Limite desta execução: {limite}")
        print(f"Serão processados agora: {len(pendentes)}")
        print()

        if not pendentes:
            print("Nenhum registro pendente.")
            return

        resumo = {}
        processados = 0
        sucesso_db = 0
        erros = 0
        buffer_db = []

        with ThreadPoolExecutor(
            max_workers=WORKERS
        ) as executor:

            futuros = {
                executor.submit(
                    processar_jogo,
                    jogo,
                ): jogo
                for jogo in pendentes
            }

            try:
                for futuro in as_completed(futuros):
                    jogo = futuros[futuro]

                    try:
                        resultado = futuro.result()

                    except Exception as erro:
                        resultado = {
                            "jogo_id": jogo.id,
                            "steam_id": str(jogo.steam_id),
                            "classificacao": "ERRO_INESPERADO",
                            "http_status_appdetails": "",
                            "http_status_store": "",
                            "erro": repr(erro)[:500],
                            "dados": None,
                        }

                    classificacao = (
                        resultado["classificacao"]
                    )

                    resumo[classificacao] = (
                        resumo.get(classificacao, 0) + 1
                    )

                    processados += 1

                    if classificacao in (
                        "OK",
                        "NAO_E_GAME",
                    ):
                        buffer_db.append(resultado)
                        salvar_checkpoint(resultado)

                    else:
                        erros += 1

                    if len(buffer_db) >= BATCH_DB:
                        try:
                            for item in buffer_db:
                                if aplicar_dados(db, item):
                                    sucesso_db += 1

                            db.commit()
                            buffer_db.clear()

                        except SQLAlchemyError:
                            db.rollback()
                            raise

                    if (
                        processados % 100 == 0
                        or processados == len(pendentes)
                    ):
                        print(
                            f"Progresso: "
                            f"{processados}/{len(pendentes)} "
                            f"({processados / len(pendentes) * 100:.2f}%) "
                            f"| DB: {sucesso_db} "
                            f"| erros: {erros}"
                        )

            except KeyboardInterrupt:
                print()
                print(
                    "Ctrl+C recebido. Cancelando tarefas "
                    "pendentes e salvando o que já estiver "
                    "confirmado no banco..."
                )

                executor.shutdown(
                    wait=False,
                    cancel_futures=True,
                )

                # Grava o lote já preparado.
                if buffer_db:
                    for item in buffer_db:
                        aplicar_dados(db, item)

                    db.commit()
                    sucesso_db += len(buffer_db)
                    buffer_db.clear()

                raise

        # Grava o restante do lote.
        if buffer_db:
            for item in buffer_db:
                if aplicar_dados(db, item):
                    sucesso_db += 1

            db.commit()
            buffer_db.clear()

        print()
        print("=" * 110)
        print("COLETA CONCLUÍDA")
        print("=" * 110)
        print(f"Total consultado nesta execução: {processados}")
        print(f"Registros gravados no banco: {sucesso_db}")
        print(f"Erros: {erros}")
        print()

        for classificacao, quantidade in sorted(
            resumo.items(),
            key=lambda item: (-item[1], item[0]),
        ):
            print(
                f"{classificacao:<30}: {quantidade}"
            )

        print()
        print(
            f"Checkpoint: {ARQUIVO_CHECKPOINT}"
        )

    except KeyboardInterrupt:
        print()
        print("Execução interrompida pelo usuário.")
        print(
            "Os registros confirmados no checkpoint podem "
            "ser retomados na próxima execução."
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
