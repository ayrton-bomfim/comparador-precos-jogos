"""
Preço atual de cada jogo por loja, guardado na visão materializada `precos_atuais`.

Ordenar ou filtrar o catálogo por preço exigiria percorrer todo o histórico
(mais de 2 milhões de linhas) a cada página. A visão faz esse trabalho uma vez;
ela é atualizada pela rotina diária e, se a coleta rodar por fora, a própria
API a atualiza em segundo plano quando fica antiga.
"""

import threading
import time

from sqlalchemy import column, table, text

from ..banco_dados import engine

precos_atuais = table(
    "precos_atuais",
    column("jogo_id"),
    column("preco_steam"),
    column("desconto_steam"),
    column("preco_epic"),
    column("desconto_epic"),
)

_INTERVALO_SEGUNDOS = 3600
_estado = {"ultima": 0.0, "rodando": False}
_trava = threading.Lock()


def atualizar_precos_atuais():
    """Recalcula a visão sem bloquear quem está lendo (leva alguns segundos)."""
    inicio = time.monotonic()
    with engine.begin() as conexao:
        conexao.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY precos_atuais"))
    _estado["ultima"] = time.monotonic()
    return {"status": "ok", "segundos": round(time.monotonic() - inicio, 1)}


def garantir_precos_recentes():
    """Dispara uma atualização em segundo plano se a última tiver mais de 1 hora.

    A requisição atual segue com os dados já existentes; não espera a atualização.
    """
    if time.monotonic() - _estado["ultima"] < _INTERVALO_SEGUNDOS:
        return
    with _trava:
        if _estado["rodando"] or time.monotonic() - _estado["ultima"] < _INTERVALO_SEGUNDOS:
            return
        _estado["rodando"] = True

    def tarefa():
        try:
            atualizar_precos_atuais()
        except Exception as erro:  # a página continua com os dados anteriores
            print(f"Falha ao atualizar precos_atuais: {erro}")
            _estado["ultima"] = time.monotonic()
        finally:
            _estado["rodando"] = False

    threading.Thread(target=tarefa, daemon=True).start()
