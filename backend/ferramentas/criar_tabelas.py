"""
Cria a estrutura do banco de dados em uma instalação nova.

Cria somente as tabelas que ainda não existem: tabelas já criadas não são
alteradas e nenhum dado é apagado. Por isso, é seguro executar em um banco
que já esteja em uso.

Inclui:
- todas as tabelas mapeadas em backend/modelos.py;
- vitrine_itens, usada pela curadoria da página inicial por SQL direto;
- estudios_brasileiros, preenchida por importar_estudios_idj.

Execução, a partir da raiz do projeto:

    python -m backend.ferramentas.criar_tabelas
"""

from sqlalchemy import inspect, text

from ..banco_dados import engine
# Importar a Base a partir de modelos garante que todas as tabelas estejam registradas.
from ..modelos import Base
from .importar_estudios_idj import DDL as DDL_ESTUDIOS_BRASILEIROS


DDL_VITRINE_ITENS = """
CREATE TABLE IF NOT EXISTS vitrine_itens (
    id BIGSERIAL PRIMARY KEY,
    tipo VARCHAR(40) NOT NULL
        CHECK (tipo IN ('estudio_brasileiro', 'jogo_brasileiro', 'oportunidade')),
    nome VARCHAR(255),
    jogo_id INTEGER REFERENCES jogos(id) ON DELETE CASCADE,
    inicio_em TIMESTAMPTZ,
    fim_em TIMESTAMPTZ,
    prioridade INTEGER NOT NULL DEFAULT 0,
    ativo BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT vitrine_item_conteudo CHECK (
        (tipo = 'estudio_brasileiro' AND nome IS NOT NULL AND jogo_id IS NULL)
        OR (tipo IN ('jogo_brasileiro', 'oportunidade') AND jogo_id IS NOT NULL)
    ),
    CONSTRAINT vitrine_item_periodo CHECK (
        fim_em IS NULL OR inicio_em IS NULL OR fim_em > inicio_em
    )
);
CREATE INDEX IF NOT EXISTS ix_vitrine_itens_jogo
ON vitrine_itens (jogo_id) WHERE jogo_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_vitrine_itens_tipo_ativo_periodo
ON vitrine_itens (tipo, ativo, inicio_em, fim_em, prioridade DESC);
"""


def criar_tabelas():
    antes = set(inspect(engine).get_table_names())

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conexao:
        conexao.execute(text(DDL_VITRINE_ITENS))
        conexao.execute(text(DDL_ESTUDIOS_BRASILEIROS))

    depois = set(inspect(engine).get_table_names())
    novas = sorted(depois - antes)

    if novas:
        print(f"Tabelas criadas ({len(novas)}): {', '.join(novas)}")
    else:
        print("Nenhuma tabela nova: a estrutura já estava completa.")
    print(f"Total de tabelas no banco: {len(depois)}")


if __name__ == "__main__":
    criar_tabelas()
