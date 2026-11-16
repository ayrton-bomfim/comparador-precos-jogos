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
