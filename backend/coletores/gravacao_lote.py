"""
Gravação em lote compartilhada pelas coletas.

O UPDATE em lote do ORM (`db.execute(update(Jogo), [...])`) vira um
executemany no psycopg2, ou seja, uma ida ao banco por linha. Pelo túnel SSH
isso custava ~70 ms por jogo (7,8 mil jogos = 9 min). Aqui cada bloco de até
1000 jogos é um único UPDATE.
"""

from sqlalchemy import text

COLUNAS_PRECO_BASE = {"preco_base_steam", "preco_base_epic"}
TAMANHO_BLOCO = 1000


def atualizar_precos_base(db, coluna, precos_por_jogo, agora):
    """Grava {jogo_id: preço} em `jogos.<coluna>` e atualiza `updated_at`.

    Não faz commit. Retorna quantos jogos foram enviados.
    """
    if coluna not in COLUNAS_PRECO_BASE:
        raise ValueError(f"Coluna não permitida: {coluna}")

    itens = [(int(jogo_id), preco) for jogo_id, preco in precos_por_jogo.items()]
    for inicio in range(0, len(itens), TAMANHO_BLOCO):
        bloco = itens[inicio:inicio + TAMANHO_BLOCO]
        db.execute(
            text(f"""
                UPDATE jogos AS j
                SET {coluna} = v.preco, updated_at = :agora
                FROM unnest(CAST(:ids AS integer[]), CAST(:precos AS numeric[])) AS v(id, preco)
                WHERE j.id = v.id
            """),
            {
                "ids": [jogo_id for jogo_id, _ in bloco],
                "precos": [preco for _, preco in bloco],
                "agora": agora,
            },
        )
    return len(itens)
