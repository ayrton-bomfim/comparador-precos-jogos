"""
Infraestrutura comum do DESCTRL Manager e do executor da coleta.

Só usa a biblioteca padrão: o Manager (EXE) importa este módulo sem levar
SQLAlchemy, Playwright etc. Quem fala com o banco é o executor, rodando no
Python do projeto (venv).
"""

import ctypes
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

NOME_TAREFA = "DESCTRL - Coleta diaria"
HORARIO_PADRAO = "14:05"
SSH_HOST_PADRAO = "ec2-user@56.125.98.189"
API_URL_PADRAO = "https://api.desctrl.com.br/health"
PORTA_BANCO_REMOTA = 5432
LOGS_MANTIDOS = 60
TAMANHO_MAXIMO_LOG_MANAGER = 2 * 1024 * 1024

SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DESANEXADO = SEM_JANELA | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


# ---------------------------------------------------------------- caminhos

def _encontrar_raiz():
    """Pasta do projeto, inclusive quando o Manager roda como EXE."""
    if getattr(sys, "frozen", False):
        inicio = Path(sys.executable).resolve().parent
    else:
        inicio = Path(__file__).resolve().parent
    for pasta in (inicio, *inicio.parents):
        if (pasta / "backend" / "coletores" / "agendador.py").is_file():
            return pasta
    raise RuntimeError(
        f"Não encontrei a pasta do projeto a partir de {inicio}. "
        "O Manager precisa ficar dentro da pasta do projeto."
    )


RAIZ = _encontrar_raiz()
PASTA_LOGS = RAIZ / "logs"
PASTA_LOGS_COLETA = PASTA_LOGS / "coleta"
ARQUIVO_TRAVA = PASTA_LOGS_COLETA / "em_execucao.json"
ARQUIVO_HISTORICO = PASTA_LOGS / "execucoes_coleta.jsonl"
PASTA_MANAGER = RAIZ / "backend" / "desctrl_manager"
ARQUIVO_LOG_MANAGER = PASTA_MANAGER / "logs" / "manager.log"
ARQUIVO_CONFIG = PASTA_MANAGER / "logs" / "config.json"
CHAVE_SSH_PADRAO = str(RAIZ.parent / "desctrl-aws.pem")

ETAPAS = (
    ("steam", "Steam"),
    ("epic", "Epic"),
    ("alertas", "Alertas de preço"),
    ("limpeza", "Limpeza de promoções"),
    ("precos_atuais", "Preços atuais do catálogo"),
)


# ------------------------------------------------------------ configuração

def ler_config():
    config = {
        "ssh_host": SSH_HOST_PADRAO,
        "ssh_chave": CHAVE_SSH_PADRAO,
        "api_url": API_URL_PADRAO,
        "horario": HORARIO_PADRAO,
    }
    try:
        config.update(json.loads(ARQUIVO_CONFIG.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return config


def salvar_config(config):
    ARQUIVO_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO_CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _valor_env(nome):
    """Lê uma variável do .env da raiz (formato simples CHAVE=valor)."""
    for arquivo in (RAIZ / ".env", RAIZ / "backend" / ".env"):
        try:
            linhas = arquivo.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for linha in linhas:
            linha = linha.strip()
            if linha.startswith(f"{nome}="):
                return linha.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def destino_banco():
    """(host, porta, banco) do DATABASE_URL de produção, sem a senha."""
    url = _valor_env("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL não está definida no .env da raiz do projeto.")
    partes = urlsplit(url)
    return partes.hostname or "localhost", partes.port or 5432, partes.path.lstrip("/")


# ------------------------------------------------------------------ python

def python_do_projeto(sem_janela=False):
    """Python do venv do projeto (pythonw.exe quando não deve abrir janela)."""
    nome = "pythonw.exe" if sem_janela else "python.exe"
    for pasta in ("venv", ".venv", "backend/venv", "backend/.venv"):
        candidato = RAIZ / pasta / "Scripts" / nome
        if candidato.is_file():
            return str(candidato)
    encontrado = shutil.which("pythonw" if sem_janela else "python")
    if encontrado:
        return encontrado
    raise RuntimeError("Não encontrei o Python do projeto (pasta venv) nem um Python no PATH.")


# ------------------------------------------------------------------- túnel

def porta_aberta(host, porta, timeout=1.0):
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except OSError:
        return False


def abrir_tunel(config, porta_local):
    """Abre `ssh -N -L porta_local:127.0.0.1:5432` e espera a porta responder."""
    if not shutil.which("ssh"):
        raise RuntimeError("O executável ssh não foi encontrado no PATH do Windows.")
    chave = config["ssh_chave"]
    if not os.path.isfile(chave):
        raise RuntimeError(f"Chave SSH não encontrada: {chave}")
    processo = subprocess.Popen(
        [
            "ssh", "-N", "-i", chave,
            "-o", "BatchMode=yes",
            "-o", "ExitOnForwardFailure=yes",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=4",
            "-o", "ConnectTimeout=15",
            "-L", f"{porta_local}:127.0.0.1:{PORTA_BANCO_REMOTA}",
            config["ssh_host"],
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        creationflags=SEM_JANELA,
    )
    limite = time.monotonic() + 25
    while time.monotonic() < limite:
        if processo.poll() is not None:
            erro = (processo.stderr.read() or b"").decode("utf-8", "replace").strip()
            raise RuntimeError(f"O túnel SSH não abriu: {erro or f'código {processo.returncode}'}")
        if porta_aberta("127.0.0.1", porta_local):
            return processo
        time.sleep(0.5)
    processo.kill()
    raise RuntimeError("O túnel SSH não respondeu em 25 segundos.")


# ---------------------------------------------------------------- processos

def processo_ativo(pid):
    """Verdadeiro se o PID existe e não terminou (Windows)."""
    if not pid:
        return False
    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED_INFORMATION
    if not handle:
        return False
    try:
        codigo = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(codigo)):
            return False
        return codigo.value == 259  # STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def execucao_atual():
    """Dados da coleta em andamento (de qualquer origem) ou None."""
    try:
        dados = json.loads(ARQUIVO_TRAVA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return dados if processo_ativo(dados.get("pid")) else None


def iniciar_coleta(etapas=None, origem="manual"):
    """Dispara o executor em segundo plano, independente do Manager."""
    if execucao_atual():
        raise RuntimeError("Já existe uma coleta em andamento.")
    comando = [python_do_projeto(sem_janela=True), "-m", "backend.desctrl_manager.executor",
               "--origem", origem]
    if etapas:
        comando += ["--etapas", ",".join(etapas)]
    return subprocess.Popen(
        comando, cwd=str(RAIZ), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=DESANEXADO, close_fds=True,
    )


def parar_coleta():
    """Encerra a coleta em andamento e o túnel aberto por ela."""
    atual = execucao_atual()
    if not atual:
        return False
    subprocess.run(["taskkill", "/PID", str(atual["pid"]), "/T", "/F"],
                   capture_output=True, creationflags=SEM_JANELA)
    try:
        ARQUIVO_TRAVA.unlink()
    except OSError:
        pass
    return True


def testar_banco():
    """Roda o teste de conexão no Python do projeto. Retorna (ok, mensagem)."""
    processo = subprocess.run(
        [python_do_projeto(), "-X", "utf8", "-m", "backend.desctrl_manager.executor", "--testar-banco"],
        cwd=str(RAIZ), capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=90, creationflags=SEM_JANELA, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    saida = (processo.stdout or "").strip().splitlines()
    mensagem = saida[-1] if saida else (processo.stderr or "").strip()[-500:]
    return processo.returncode == 0, mensagem


# --------------------------------------------------------------- histórico

def historico(limite=100):
    """Execuções registradas, da mais recente para a mais antiga."""
    try:
        linhas = ARQUIVO_HISTORICO.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    execucoes = []
    for linha in reversed(linhas):
        try:
            registro = json.loads(linha)
        except ValueError:
            continue
        if (registro.get("ambiente") or "producao") != "producao":
            continue
        execucoes.append(registro)
        if len(execucoes) >= limite:
            break
    return execucoes


def ultimas_linhas(arquivo, quantidade=200):
    try:
        with open(arquivo, "rb") as f:
            f.seek(0, os.SEEK_END)
            tamanho = f.tell()
            f.seek(max(0, tamanho - 256 * 1024))
            texto = f.read().decode("utf-8", "replace")
    except OSError:
        return []
    return texto.splitlines()[-quantidade:]


def limpar_logs_antigos():
    arquivos = sorted(PASTA_LOGS_COLETA.glob("coleta_*.log"))
    for arquivo in arquivos[:-LOGS_MANTIDOS]:
        try:
            arquivo.unlink()
        except OSError:
            pass


def registrar_manager(mensagem):
    """Log do próprio Manager, com rotação simples (2 MB, 1 arquivo antigo)."""
    linha = f"{datetime.now():%Y-%m-%d %H:%M:%S} {mensagem}\n"
    try:
        ARQUIVO_LOG_MANAGER.parent.mkdir(parents=True, exist_ok=True)
        if ARQUIVO_LOG_MANAGER.exists() and ARQUIVO_LOG_MANAGER.stat().st_size > TAMANHO_MAXIMO_LOG_MANAGER:
            antigo = ARQUIVO_LOG_MANAGER.with_suffix(".log.1")
            if antigo.exists():
                antigo.unlink()
            ARQUIVO_LOG_MANAGER.rename(antigo)
        with ARQUIVO_LOG_MANAGER.open("a", encoding="utf-8") as f:
            f.write(linha)
    except OSError:
        pass
    return linha.rstrip()


# ----------------------------------------------------- tarefa do Windows

def _powershell(script, timeout=30):
    processo = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, creationflags=SEM_JANELA,
    )
    if processo.returncode:
        raise RuntimeError((processo.stderr or processo.stdout).strip()[-800:])
    return processo.stdout.strip()


def _ps_texto(valor):
    return "'" + str(valor).replace("'", "''") + "'"


def agendar_coleta_diaria(horario):
    """Cria/atualiza a tarefa do Agendador de Tarefas do Windows."""
    datetime.strptime(horario, "%H:%M")
    script = f"""
$acao = New-ScheduledTaskAction -Execute {_ps_texto(python_do_projeto(sem_janela=True))} `
    -Argument '-m backend.desctrl_manager.executor --origem agendada' `
    -WorkingDirectory {_ps_texto(RAIZ)}
$gatilho = New-ScheduledTaskTrigger -Daily -At {_ps_texto(horario)}
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 3)
Register-ScheduledTask -TaskName {_ps_texto(NOME_TAREFA)} -Action $acao -Trigger $gatilho `
    -Settings $config -Description 'Coleta diária de preços do DESCTRL (criada pelo DESCTRL Manager).' `
    -Force | Out-Null
"""
    _powershell(script)


def remover_agendamento():
    _powershell(f"Unregister-ScheduledTask -TaskName {_ps_texto(NOME_TAREFA)} -Confirm:$false")


def estado_agendamento():
    """{'existe', 'ativa', 'horario', 'proxima', 'ultima', 'ultimo_resultado'}."""
    script = f"""
$t = Get-ScheduledTask -TaskName {_ps_texto(NOME_TAREFA)} -ErrorAction SilentlyContinue
if (-not $t) {{ '{{"existe": false}}'; exit 0 }}
$i = $t | Get-ScheduledTaskInfo
[pscustomobject]@{{
  existe = $true
  ativa = ($t.State -ne 'Disabled')
  estado = [string]$t.State
  horario = ([datetime]$t.Triggers[0].StartBoundary).ToString('HH:mm')
  proxima = if ($i.NextRunTime) {{ $i.NextRunTime.ToString('dd/MM/yyyy HH:mm') }} else {{ '' }}
  ultima = if ($i.LastRunTime -and $i.LastRunTime.Year -gt 2000) {{ $i.LastRunTime.ToString('dd/MM/yyyy HH:mm') }} else {{ '' }}
  ultimo_resultado = $i.LastTaskResult
}} | ConvertTo-Json -Compress
"""
    return json.loads(_powershell(script) or '{"existe": false}')
