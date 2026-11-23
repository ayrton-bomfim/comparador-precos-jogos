"""
Executor da coleta diária neste computador.

Chamado pelo DESCTRL Manager (botão) e pela tarefa agendada do Windows:

    venv\\Scripts\\python.exe -m backend.desctrl_manager.executor [--etapas steam,epic] [--origem manual]

O que ele faz, nesta ordem:
1. recusa começar se já houver outra coleta rodando (trava com o PID);
2. abre o túnel SSH até o PostgreSQL da AWS, se ele ainda não estiver aberto;
3. roda as etapas do agendador e grava tudo em logs/coleta/coleta_AAAAMMDD_HHMMSS.log;
4. fecha o túnel que abriu, solta a trava e apaga logs além dos 60 mais recentes.

Sempre usa o banco de produção (.env), a menos que receba --ambiente dev.
"""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime

from . import infra


class _Duplicador:
    """Escreve no arquivo de log e, se houver, também no console."""

    def __init__(self, arquivo, console):
        self.arquivo = arquivo
        self.console = console
        self.encoding = "utf-8"

    def write(self, texto):
        self.arquivo.write(texto)
        self.arquivo.flush()
        if self.console:
            try:
                self.console.write(texto)
            except Exception:
                pass
        return len(texto)

    def flush(self):
        self.arquivo.flush()

    def isatty(self):
        return False


def _preparar_ambiente(ambiente):
    if ambiente == "dev":
        os.environ["DESCTRL_ENV"] = "dev"
    else:
        os.environ.pop("DESCTRL_ENV", None)
    os.environ["PYTHONIOENCODING"] = "utf-8"


def _garantir_tunel(ambiente):
    """Abre o túnel se o banco é o da AWS via localhost e a porta está fechada."""
    if ambiente == "dev":
        return None
    host, porta, banco = infra.destino_banco()
    if host not in {"localhost", "127.0.0.1"}:
        return None
    if infra.porta_aberta("127.0.0.1", porta):
        print(f"Túnel até o banco já aberto (127.0.0.1:{porta} -> {banco}).")
        return None
    print(f"Abrindo túnel SSH 127.0.0.1:{porta} -> {infra.ler_config()['ssh_host']}:5432 ...")
    processo = infra.abrir_tunel(infra.ler_config(), porta)
    print("Túnel aberto.")
    return processo


def testar_banco(ambiente):
    _preparar_ambiente(ambiente)
    tunel = None
    try:
        tunel = _garantir_tunel(ambiente)
        from sqlalchemy import text
        from backend.banco_dados import engine

        with engine.connect() as conexao:
            banco = conexao.execute(text("SELECT current_database()")).scalar()
            usuario = conexao.execute(text("SELECT current_user")).scalar()
            jogos = conexao.execute(text("SELECT count(*) FROM jogos")).scalar()
        engine.dispose()
        total = f"{jogos:,}".replace(",", ".")
        print(f"Conexão OK: banco={banco}, usuário={usuario}, jogos={total}")
        return 0
    except Exception as erro:
        print(f"Falha na conexão: {type(erro).__name__}: {erro}")
        return 1
    finally:
        if tunel:
            tunel.terminate()


def executar(etapas, origem, ambiente):
    _preparar_ambiente(ambiente)
    infra.PASTA_LOGS_COLETA.mkdir(parents=True, exist_ok=True)

    atual = infra.execucao_atual()
    if atual:
        print(f"Já existe uma coleta em andamento (PID {atual['pid']}, desde {atual['inicio']}).")
        return 2

    inicio = datetime.now()
    arquivo_log = infra.PASTA_LOGS_COLETA / f"coleta_{inicio:%Y%m%d_%H%M%S}.log"
    infra.ARQUIVO_TRAVA.write_text(json.dumps({
        "pid": os.getpid(),
        "inicio": inicio.isoformat(timespec="seconds"),
        "etapas": etapas or [chave for chave, _ in infra.ETAPAS],
        "origem": origem,
        "ambiente": ambiente,
        "log": str(arquivo_log),
    }, ensure_ascii=False), encoding="utf-8")

    stdout_original, stderr_original = sys.stdout, sys.stderr
    tunel = None
    codigo = 1
    with open(arquivo_log, "w", encoding="utf-8", buffering=1) as log:
        sys.stdout = _Duplicador(log, stdout_original)
        sys.stderr = _Duplicador(log, stderr_original)
        try:
            print(f"DESCTRL - coleta {origem} iniciada em {inicio:%d/%m/%Y %H:%M:%S}")
            tunel = _garantir_tunel(ambiente)
            from backend.coletores.agendador import AgendadorColeta

            status = AgendadorColeta().executar_agora(etapas, origem=origem, arquivo_log=arquivo_log)
            codigo = 0 if status in {"concluida", "concluida_com_avisos"} else 1
        except BaseException as erro:
            print(f"\nFALHA NA EXECUÇÃO: {type(erro).__name__}: {erro}")
            traceback.print_exc()
            if not isinstance(erro, Exception):
                raise
        finally:
            if tunel:
                tunel.terminate()
                print("Túnel SSH fechado.")
            sys.stdout, sys.stderr = stdout_original, stderr_original
            try:
                infra.ARQUIVO_TRAVA.unlink()
            except OSError:
                pass
            infra.limpar_logs_antigos()
    return codigo


def main():
    parser = argparse.ArgumentParser(description="Executa a coleta do DESCTRL neste computador.")
    parser.add_argument("--etapas", default="", help="etapas separadas por vírgula (padrão: todas)")
    parser.add_argument("--origem", default="manual", choices=["manual", "agendada"])
    parser.add_argument("--ambiente", default="producao", choices=["producao", "dev"])
    parser.add_argument("--testar-banco", action="store_true", help="só testa a conexão e sai")
    args = parser.parse_args()

    if args.testar_banco:
        raise SystemExit(testar_banco(args.ambiente))

    etapas = [e.strip() for e in args.etapas.split(",") if e.strip()]
    validas = {chave for chave, _ in infra.ETAPAS}
    invalidas = [e for e in etapas if e not in validas]
    if invalidas:
        parser.error(f"etapa(s) desconhecida(s): {', '.join(invalidas)}")
    raise SystemExit(executar(etapas, args.origem, args.ambiente))


if __name__ == "__main__":
    main()
