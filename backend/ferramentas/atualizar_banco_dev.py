"""
Copia o banco de produção (AWS) para o banco local de desenvolvimento.

Origem:  DATABASE_URL do .env      (produção, via túnel SSH)
Destino: DATABASE_URL do .env.dev  (PostgreSQL local)

O que é copiado:
- toda a estrutura (tabelas, índices, funções, sequências);
- os dados de catálogo, preços, histórico, auditorias e vitrine.

O que NÃO é copiado (dados pessoais): usuários, tokens, favoritos, alertas,
notificações, conquistas e sugestões. As referências de auditoria a usuários
ficam em branco. Crie um administrador local depois com:

    set DESCTRL_ENV=dev
    python -m backend.ferramentas.criar_admin

A produção é apenas lida. O banco local é APAGADO e recriado a cada execução.

Execução, a partir da raiz do projeto (com o túnel da AWS aberto):

    python -m backend.ferramentas.atualizar_banco_dev
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

PROJECT_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_DUMP = PROJECT_DIR / "logs" / "desctrl_producao.dump"
HOSTS_LOCAIS = {"localhost", "127.0.0.1", "::1"}

TABELAS_PESSOAIS = [
    "usuarios",
    "tokens_seguranca_usuario",
    "historico_nomes_usuario",
    "favoritos",
    "historico_favoritos",
    "alertas_preco",
    "notificacoes_usuario",
    "conquistas",
    "sugestoes_usuarios",
]

# Executado entre os dados e as restrições: remove referências a usuários
# que não foram copiados, para que as chaves estrangeiras possam ser criadas.
LIMPEZA_REFERENCIAS = """
UPDATE auditorias_conteudo SET criado_por = NULL, decidido_por = NULL;
UPDATE auditorias_conteudo_historico SET usuario_id = NULL;
"""


def _ler_url(arquivo):
    caminho = PROJECT_DIR / arquivo
    if not caminho.exists():
        sys.exit(f"Arquivo {arquivo} não encontrado na raiz do projeto.")
    url = dotenv_values(caminho).get("DATABASE_URL")
    if not url:
        sys.exit(f"DATABASE_URL não definida em {arquivo}.")
    return make_url(url)


def _ferramenta(nome):
    encontrado = shutil.which(nome)
    if encontrado:
        return encontrado
    candidatos = sorted(
        glob.glob(rf"C:\Program Files\PostgreSQL\*\bin\{nome}.exe"),
        key=lambda c: int(Path(c).parts[-3]) if Path(c).parts[-3].isdigit() else 0,
    )
    if candidatos:
        return candidatos[-1]
    sys.exit(f"{nome} não encontrado. Instale o PostgreSQL ou adicione o bin ao PATH.")


def _conexao(url):
    """Argumentos de conexão sem senha (a senha vai por PGPASSWORD)."""
    args = ["-h", url.host or "localhost", "-p", str(url.port or 5432),
            "-U", url.username, "-d", url.database]
    env = dict(os.environ, PGPASSWORD=url.password or "")
    return args, env


def _executar(comando, env, etapa, tolerar_erros=False):
    inicio = time.perf_counter()
    print(f"\n>> {etapa}...")
    resultado = subprocess.run(comando, env=env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    duracao = time.perf_counter() - inicio
    saida = (resultado.stderr or "").strip()
    if resultado.returncode != 0:
        if not tolerar_erros:
            print(saida[-3000:])
            sys.exit(f"Falha em: {etapa}")
        print(f"   Concluído com avisos ({duracao:.0f}s):")
        print("   " + saida[-1500:].replace("\n", "\n   "))
    else:
        print(f"   OK ({duracao:.0f}s)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--manter-dump", action="store_true",
                        help="Mantém logs/desctrl_producao.dump após a restauração.")
    parser.add_argument("--reaproveitar-dump", action="store_true",
                        help="Restaura o dump existente sem baixar de novo da produção.")
    parser.add_argument("--sim", action="store_true",
                        help="Não pede confirmação antes de apagar o banco local.")
    args = parser.parse_args()

    origem = _ler_url(".env")
    destino = _ler_url(".env.dev")

    if destino.host not in HOSTS_LOCAIS:
        sys.exit(f"Por segurança, o destino precisa ser local (host atual: {destino.host}).")
    if (origem.host, origem.port, origem.database) == (destino.host, destino.port, destino.database):
        sys.exit("Origem e destino apontam para o mesmo banco. Abortando.")

    print("=" * 60)
    print("ATUALIZAR BANCO LOCAL DE DESENVOLVIMENTO")
    print(f"Origem (somente leitura): {origem.host}:{origem.port}/{origem.database}")
    print(f"Destino (será recriado):  {destino.host}:{destino.port}/{destino.database}")
    print("=" * 60)
    if not args.sim:
        if input("Digite SIM para continuar: ").strip() != "SIM":
            sys.exit("Cancelado.")

    pg_dump = _ferramenta("pg_dump")
    pg_restore = _ferramenta("pg_restore")
    ARQUIVO_DUMP.parent.mkdir(parents=True, exist_ok=True)

    if not (args.reaproveitar_dump and ARQUIVO_DUMP.exists()):
        conexao_origem, env_origem = _conexao(origem)
        comando = [pg_dump, *conexao_origem, "-Fc", "--no-owner", "--no-privileges",
                   "-f", str(ARQUIVO_DUMP)]
        for tabela in TABELAS_PESSOAIS:
            comando.append(f"--exclude-table-data=public.{tabela}")
        _executar(comando, env_origem, "Baixando cópia da produção (pg_dump)")
        print(f"   Tamanho do dump: {ARQUIVO_DUMP.stat().st_size / 1024 / 1024:.0f} MB")

    motor = create_engine(destino)
    with motor.begin() as conexao:
        conexao.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conexao.execute(text("CREATE SCHEMA public"))
    print("\n>> Banco local limpo.")

    conexao_destino, env_destino = _conexao(destino)
    base = [pg_restore, *conexao_destino, "--no-owner", "--no-privileges"]
    # Avisos como "must be owner of extension" são esperados e não afetam os dados.
    _executar([*base, "--section=pre-data", str(ARQUIVO_DUMP)], env_destino,
              "Criando a estrutura", tolerar_erros=True)
    _executar([*base, "--section=data", "--jobs=4", str(ARQUIVO_DUMP)], env_destino,
              "Copiando os dados")
    with motor.begin() as conexao:
        conexao.execute(text(LIMPEZA_REFERENCIAS))
    print("\n>> Referências a usuários removidas das auditorias.")
    _executar([*base, "--section=post-data", "--jobs=4", str(ARQUIVO_DUMP)], env_destino,
              "Criando índices e restrições")

    with motor.connect() as conexao:
        conexao.execute(text("ANALYZE"))
        tabelas = conexao.execute(text(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
        )).scalar()
        jogos = conexao.execute(text("SELECT count(*) FROM jogos")).scalar()
        historico = conexao.execute(text("SELECT count(*) FROM historico_precos")).scalar()
        restricoes = conexao.execute(text(
            "SELECT count(*) FROM pg_constraint WHERE connamespace='public'::regnamespace AND contype='f'"
        )).scalar()

    if not args.manter_dump:
        ARQUIVO_DUMP.unlink(missing_ok=True)

    print("\n" + "=" * 60)
    print(f"Banco local pronto: {tabelas} tabelas, {jogos:,} jogos, "
          f"{historico:,} registros de histórico, {restricoes} chaves estrangeiras.")
    print("Próximo passo (uma vez): criar o admin local com DESCTRL_ENV=dev "
          "python -m backend.ferramentas.criar_admin")
    print("=" * 60)


if __name__ == "__main__":
    main()
