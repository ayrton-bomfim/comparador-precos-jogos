"""
Aplica as alterações de estrutura em bancos que já existem.

Cada migração pode ser executada mais de uma vez sem efeito colateral.
Instalações novas não precisam disto: criar_tabelas.py já cria tudo atualizado.

Execução, a partir da raiz do projeto:

    python -m backend.ferramentas.migrar_banco            (banco do .env)
    set DESCTRL_ENV=dev && python -m backend.ferramentas.migrar_banco   (banco local)
"""

from sqlalchemy import text

from ..banco_dados import engine

MIGRACOES = [
    (
        "2026-11-17: vitrine aceita indicações da curadoria na seção da comunidade",
        """
        ALTER TABLE vitrine_itens DROP CONSTRAINT IF EXISTS vitrine_itens_tipo_check;
        ALTER TABLE vitrine_itens ADD CONSTRAINT vitrine_itens_tipo_check CHECK (
            tipo IN ('estudio_brasileiro', 'jogo_brasileiro', 'oportunidade', 'curadoria_comunidade')
        );
        ALTER TABLE vitrine_itens DROP CONSTRAINT IF EXISTS vitrine_item_conteudo;
        ALTER TABLE vitrine_itens ADD CONSTRAINT vitrine_item_conteudo CHECK (
            (tipo = 'estudio_brasileiro' AND nome IS NOT NULL AND jogo_id IS NULL)
            OR (tipo IN ('jogo_brasileiro', 'oportunidade', 'curadoria_comunidade') AND jogo_id IS NOT NULL)
        );
        """,
    ),
    (
        "2026-11-17: visão materializada com o preço atual de cada jogo por loja",
        """
        CREATE MATERIALIZED VIEW IF NOT EXISTS precos_atuais AS
        WITH ultimo AS (
            SELECT DISTINCT ON (jogo_id, loja)
                jogo_id,
                CASE WHEN lower(plataforma) = 'steam' THEN 'steam' ELSE 'epic' END AS loja,
                preco_atual,
                desconto
            FROM historico_precos
            WHERE lower(plataforma) IN ('steam', 'epic', 'epic games', 'epic games store')
            ORDER BY jogo_id, loja, data_coleta DESC
        )
        SELECT
            jogo_id,
            max(preco_atual) FILTER (WHERE loja = 'steam') AS preco_steam,
            max(desconto) FILTER (WHERE loja = 'steam') AS desconto_steam,
            max(preco_atual) FILTER (WHERE loja = 'epic') AS preco_epic,
            max(desconto) FILTER (WHERE loja = 'epic') AS desconto_epic
        FROM ultimo
        GROUP BY jogo_id;
        CREATE UNIQUE INDEX IF NOT EXISTS precos_atuais_jogo_id ON precos_atuais (jogo_id);
        """,
    ),
    (
        "2026-11-23: identidade entre lojas (ITAD) e registro de mesclagens",
        """
        ALTER TABLE jogos ADD COLUMN IF NOT EXISTS itad_id VARCHAR(40);
        CREATE INDEX IF NOT EXISTS ix_jogos_itad_id ON jogos (itad_id);
        CREATE TABLE IF NOT EXISTS mesclagens_jogos (
            id BIGSERIAL PRIMARY KEY,
            jogo_mantido_id INTEGER NOT NULL,
            jogo_removido_id INTEGER NOT NULL,
            nome_mantido VARCHAR(255),
            nome_removido VARCHAR(255),
            steam_id VARCHAR(50),
            epic_id VARCHAR(255),
            itad_id VARCHAR(40),
            criterio VARCHAR(40) NOT NULL,
            detalhes JSONB,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
    ),
]


def migrar():
    with engine.begin() as conexao:
        banco = conexao.execute(text("SELECT current_database()")).scalar()
        print(f"Banco: {banco}")
        for descricao, sql in MIGRACOES:
            conexao.execute(text(sql))
            print(f"  OK  {descricao}")
    print("Migrações concluídas.")


if __name__ == "__main__":
    migrar()
