import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import json
import os
import shutil
import subprocess
import threading
import urllib.request
import queue
import sys
import time
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

APP_NAME = "DESCTRL Manager"
SSH_KEY_DEFAULT = r"C:\Users\ayrto\Desktop\Universidade Paulista\7º Semestre\Trabalho de Curso II\Projeto\desctrl-aws.pem"
SSH_HOST_DEFAULT = "ec2-user@56.125.98.189"
API_URL_DEFAULT = "https://api.desctrl.com.br/health"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
LOG_DIR = PROJECT_ROOT / "backend" / "desctrl_manager" / "logs"
LOG_FILE = LOG_DIR / "manager.log"
DB_TUNNEL_HOST = "127.0.0.1"
DB_TUNNEL_PORT = 5433
DB_NAME_AWS = "desctrl"
DB_USER_AWS = "desctrl_app"


class DesctrlManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1180x760")
        self.minsize(980, 650)
        self.configure(bg="#0d1018")
        self.c = {
            "bg": "#0d1018", "sidebar": "#111622", "panel": "#171d2b",
            "panel2": "#1e2637", "line": "#293249", "text": "#f0f3fa",
            "muted": "#929db4", "purple": "#8977ff", "purple_hover": "#a194ff",
            "green": "#45d6a0", "amber": "#f0bd62", "red": "#ff6b7a", "blue": "#6ea8fe",
        }
        self.ssh_key = SSH_KEY_DEFAULT
        self.ssh_host = SSH_HOST_DEFAULT
        self.api_url = API_URL_DEFAULT
        self.status_labels = {}
        self.nav_buttons = {}
        self.collection_process = None
        self.scheduler_process = None
        self.log_queue = queue.Queue()
        self.schedule_var = tk.StringVar(value="03:00")
        self._styles()
        self._layout()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.show_page("Visão geral")
        self._update_clock()
        self._poll_log_queue()

    def _styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", font=("Segoe UI", 10))
        s.configure("TFrame", background=self.c["bg"])
        s.configure("Card.TFrame", background=self.c["panel"])
        s.configure("Sidebar.TFrame", background=self.c["sidebar"])
        s.configure("TLabel", background=self.c["bg"], foreground=self.c["text"])
        s.configure("Muted.TLabel", background=self.c["bg"], foreground=self.c["muted"])
        s.configure("CardTitle.TLabel", background=self.c["panel"], foreground=self.c["muted"], font=("Segoe UI", 10))
        s.configure("CardValue.TLabel", background=self.c["panel"], foreground=self.c["text"], font=("Segoe UI Semibold", 17))
        s.configure("Section.TLabel", background=self.c["bg"], foreground=self.c["text"], font=("Segoe UI Semibold", 16))
        s.configure("Small.TLabel", background=self.c["panel"], foreground=self.c["muted"], font=("Segoe UI", 9))
        s.configure("TButton", background=self.c["panel2"], foreground=self.c["text"], borderwidth=0, padding=(12, 9), focusthickness=0)
        s.map("TButton", background=[("active", self.c["line"])])
        s.configure("Accent.TButton", background=self.c["purple"], foreground="#ffffff", borderwidth=0, padding=(14, 10), font=("Segoe UI Semibold", 10))
        s.map("Accent.TButton", background=[("active", self.c["purple_hover"])])
        s.configure("Nav.TButton", background=self.c["sidebar"], foreground=self.c["muted"], anchor="w", padding=(14, 11), borderwidth=0)
        s.map("Nav.TButton", background=[("active", self.c["panel2"])], foreground=[("active", self.c["text"])])
        s.configure("Treeview", background=self.c["panel"], fieldbackground=self.c["panel"], foreground=self.c["text"], rowheight=32, borderwidth=0)
        s.configure("Treeview.Heading", background=self.c["panel2"], foreground=self.c["muted"], relief="flat", padding=(10, 8))
        s.map("Treeview", background=[("selected", self.c["purple"])], foreground=[("selected", "#ffffff")])

    def _layout(self):
        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True)
        sidebar = ttk.Frame(shell, style="Sidebar.TFrame", padding=(14, 22))
        sidebar.pack(side="left", fill="y")
        sidebar.configure(width=230)
        sidebar.pack_propagate(False)
        brand = tk.Frame(sidebar, bg=self.c["sidebar"])
        brand.pack(fill="x", padx=5, pady=(0, 28))
        tk.Label(brand, text="◈", bg=self.c["sidebar"], fg=self.c["purple"], font=("Segoe UI", 25, "bold")).pack(side="left")
        bt = tk.Frame(brand, bg=self.c["sidebar"])
        bt.pack(side="left", padx=(9, 0))
        tk.Label(bt, text="DESCTRL", bg=self.c["sidebar"], fg=self.c["text"], font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tk.Label(bt, text="MANAGER", bg=self.c["sidebar"], fg=self.c["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(sidebar, text="WORKSPACE", bg=self.c["sidebar"], fg="#68748d", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12, pady=(0, 8))
        for label, glyph in [("Visão geral", "▦"), ("Coletas", "⇄"), ("Agendamento", "◷"), ("Logs e histórico", "≡"), ("Configurações", "⚙")]:
            btn = ttk.Button(sidebar, text=f"{glyph}   {label}", style="Nav.TButton", command=lambda n=label: self.show_page(n))
            btn.pack(fill="x", pady=2)
            self.nav_buttons[label] = btn
        tk.Frame(sidebar, bg=self.c["sidebar"]).pack(fill="both", expand=True)
        tk.Frame(sidebar, bg=self.c["line"], height=1).pack(fill="x", pady=(12, 12))
        tk.Label(sidebar, text="AMBIENTE", bg=self.c["sidebar"], fg="#68748d", font=("Segoe UI", 8, "bold")).pack(anchor="w", padx=12)
        tk.Label(sidebar, text="●  AWS · diagnóstico sob demanda", bg=self.c["sidebar"], fg=self.c["muted"], font=("Segoe UI", 9)).pack(anchor="w", padx=12, pady=(8, 2))

        self.main = ttk.Frame(shell, padding=(28, 22, 28, 22))
        self.main.pack(side="left", fill="both", expand=True)
        top = ttk.Frame(self.main)
        top.pack(fill="x", pady=(0, 24))
        self.breadcrumb = ttk.Label(top, text="WORKSPACE / VISÃO GERAL", style="Muted.TLabel")
        self.breadcrumb.pack(side="left")
        self.clock = ttk.Label(top, text="", style="Muted.TLabel")
        self.clock.pack(side="right")
        self.page_host = ttk.Frame(self.main)
        self.page_host.pack(fill="both", expand=True)

    def _card(self, parent, title, value, detail, accent, col, key):
        card = ttk.Frame(parent, style="Card.TFrame", padding=(17, 16))
        card.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 10, 0))
        tk.Frame(card, bg=accent, height=3).pack(fill="x", pady=(0, 14))
        ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
        lab = ttk.Label(card, text=value, style="CardValue.TLabel")
        lab.pack(anchor="w", pady=(10, 5))
        ttk.Label(card, text=detail, style="Small.TLabel", wraplength=170).pack(anchor="w")
        self.status_labels[key] = lab

    def _panel(self, parent, title, subtitle=None):
        p = ttk.Frame(parent, style="Card.TFrame", padding=18)
        ttk.Label(p, text=title, background=self.c["panel"], foreground=self.c["text"], font=("Segoe UI Semibold", 12)).pack(anchor="w")
        if subtitle:
            ttk.Label(p, text=subtitle, background=self.c["panel"], foreground=self.c["muted"], font=("Segoe UI", 9)).pack(anchor="w", pady=(5, 0))
        return p

    def show_page(self, name):
        for nav, btn in self.nav_buttons.items():
            btn.configure(style="Accent.TButton" if nav == name else "Nav.TButton")
        for child in self.page_host.winfo_children():
            child.destroy()
        self.breadcrumb.configure(text=f"WORKSPACE / {name.upper()}")
        if name == "Visão geral":
            self._page_dashboard()
        elif name == "Coletas":
            self._page_collections()
        elif name == "Agendamento":
            self._page_schedule()
        elif name == "Logs e histórico":
            self._page_logs()
        else:
            self._page_settings()

    def _page_collections(self):
        ttk.Label(self.page_host, text="Central de coletas", style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.page_host, text="A execução acontece neste computador. O banco utilizado é o PostgreSQL da AWS pelo túnel SSH.", style="Muted.TLabel", wraplength=850).pack(anchor="w", pady=(5, 18))
        p = self._panel(self.page_host, "Destino da coleta", "A conexão é validada antes de iniciar qualquer processo.")
        p.pack(fill="x", pady=(0, 14))
        ttk.Label(p, text="Banco: desctrl  ·  Usuário: desctrl_app  ·  Túnel local: 127.0.0.1:5434", background=self.c["panel"], foreground=self.c["text"]).pack(anchor="w")
        actions = ttk.Frame(p, style="Card.TFrame")
        actions.pack(fill="x", pady=(14, 0))
        ttk.Button(actions, text="Testar conexão com AWS", command=self.test_database).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="Executar coleta completa agora", style="Accent.TButton", command=self.run_collection_now).pack(side="left")
        status = "Em execução" if self.collection_process and self.collection_process.poll() is None else "Parada"
        self.collection_status = ttk.Label(p, text=f"Coleta manual: {status}", background=self.c["panel"], foreground=self.c["muted"])
        self.collection_status.pack(anchor="w", pady=(12, 0))
        note = self._panel(self.page_host, "Antes de executar", "A coleta completa pode atualizar preços, histórico e alertas no banco.")
        note.pack(fill="x")
        ttk.Label(note, text="O botão pede confirmação e impede duas coletas manuais simultâneas. O agendador da EC2 permanece desativado.", background=self.c["panel"], foreground=self.c["muted"], wraplength=800).pack(anchor="w", pady=(8, 0))

    def _page_schedule(self):
        ttk.Label(self.page_host, text="Agendamento local", style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.page_host, text="O agendador roda no Windows. Ele não liga nem altera serviços na EC2.", style="Muted.TLabel", wraplength=850).pack(anchor="w", pady=(5, 18))
        p = self._panel(self.page_host, "Rotina diária", "Horário local do seu computador, formato 24 horas.")
        p.pack(fill="x", pady=(0, 14))
        row = ttk.Frame(p, style="Card.TFrame")
        row.pack(fill="x", pady=(12, 0))
        ttk.Label(row, text="Executar todos os dias às", background=self.c["panel"], foreground=self.c["text"]).pack(side="left")
        ttk.Entry(row, textvariable=self.schedule_var, width=8).pack(side="left", padx=10)
        ttk.Button(row, text="Iniciar agendador neste PC", style="Accent.TButton", command=self.start_local_scheduler).pack(side="left", padx=(0, 8))
        ttk.Button(row, text="Parar agendador", command=self.stop_local_scheduler).pack(side="left")
        self.scheduler_status = ttk.Label(p, text=self._scheduler_status_text(), background=self.c["panel"], foreground=self.c["muted"])
        self.scheduler_status.pack(anchor="w", pady=(14, 0))
        info = self._panel(self.page_host, "Como funciona", "O Manager precisa permanecer aberto para o agendamento continuar ativo.")
        info.pack(fill="x")
        ttk.Label(info, text="Se o computador desligar ou entrar em suspensão, a rotina não executará. A coleta na nuvem continua desativada.", background=self.c["panel"], foreground=self.c["muted"], wraplength=800).pack(anchor="w", pady=(8, 0))

    def _page_logs(self):
        ttk.Label(self.page_host, text="Logs e histórico", style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.page_host, text=f"Registro local: {LOG_FILE}", style="Muted.TLabel", wraplength=850).pack(anchor="w", pady=(5, 14))
        p = self._panel(self.page_host, "Eventos recentes", "Saída dos processos e verificações realizadas pelo Manager.")
        p.pack(fill="both", expand=True)
        row = ttk.Frame(p, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="Atualizar", command=self.refresh_logs).pack(side="left")
        ttk.Button(row, text="Abrir arquivo de log", command=self.open_log_file).pack(side="left", padx=8)
        self.logs_text = tk.Text(p, height=22, bg="#0a0d14", fg="#cbd5e1", insertbackground="#fff", relief="flat", font=("Consolas", 9), wrap="word")
        self.logs_text.pack(fill="both", expand=True, pady=(12, 0))
        self.refresh_logs()

    def _page_settings(self):
        ttk.Label(self.page_host, text="Configurações", style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.page_host, text="Configuração operacional do Manager.", style="Muted.TLabel").pack(anchor="w", pady=(5, 18))
        p = self._panel(self.page_host, "Infraestrutura", "Os valores abaixo são locais ao Manager.")
        p.pack(fill="x")
        for label, value in (("Host SSH", self.ssh_host), ("Chave SSH", self.ssh_key), ("API", self.api_url), ("Arquivo .env", str(ENV_FILE)), ("Banco remoto", "desctrl / desctrl_app"), ("Túnel", "127.0.0.1:5434 → PostgreSQL da EC2")):
            ttk.Label(p, text=f"{label}: {value}", background=self.c["panel"], foreground=self.c["text"], wraplength=850).pack(anchor="w", pady=4)
        ttk.Label(p, text="A senha nunca é exibida nem gravada pelo Manager. A conexão utiliza a senha já presente no .env local.", background=self.c["panel"], foreground=self.c["muted"], wraplength=850).pack(anchor="w", pady=(12, 0))

    def _database_url(self):
        if not ENV_FILE.is_file():
            raise FileNotFoundError(f"Arquivo .env não encontrado: {ENV_FILE}")
        values = dotenv_values(ENV_FILE)
        raw_url = values.get("DATABASE_URL")
        if not raw_url:
            raise RuntimeError("DATABASE_URL não está definida no .env da raiz do projeto.")
        return make_url(raw_url).set(host=DB_TUNNEL_HOST, port=DB_TUNNEL_PORT, database=DB_NAME_AWS, username=DB_USER_AWS)

    def _collector_environment(self, schedule_time=None):
        env = os.environ.copy()
        env["DATABASE_URL"] = self._database_url().render_as_string(hide_password=False)

        # Garante que o processo filho consiga imprimir nomes de jogos
        # com caracteres fora da codificação padrão do Windows.
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        if schedule_time:
            env["COLETA_HORARIO"] = schedule_time
        return env

    def test_database(self):
        def worker():
            try:
                engine = create_engine(self._database_url(), connect_args={"connect_timeout": 5}, pool_pre_ping=True)
                with engine.connect() as conn:
                    db = conn.execute(text("SELECT current_database()")).scalar()
                    user = conn.execute(text("SELECT current_user")).scalar()
                    server = conn.execute(text("SELECT inet_server_addr()::text || ':' || inet_server_port()::text")).scalar()
                engine.dispose()
                self._log(f"[OK] Banco remoto acessível: banco={db}, usuário={user}, servidor={server}")
                self.after(0, lambda: messagebox.showinfo("Conexão validada", f"Conexão de leitura OK.\nBanco: {db}\nUsuário: {user}\nServidor: {server}"))
            except Exception as exc:
                self._log(f"[ERRO] Teste de conexão: {type(exc).__name__}: {exc}")
                self.after(0, lambda err=str(exc): messagebox.showerror("Falha na conexão", f"Não foi possível conectar ao banco pelo túnel 127.0.0.1:5434.\n\n{err}"))
        threading.Thread(target=worker, daemon=True).start()

    def run_collection_now(self):
        if self.collection_process and self.collection_process.poll() is None:
            messagebox.showwarning("Coleta em andamento", "Já existe uma coleta manual em execução.")
            return
        if self.scheduler_process and self.scheduler_process.poll() is None:
            messagebox.showwarning("Agendador ativo", "Pare o agendador local antes de iniciar uma coleta manual, para evitar execuções simultâneas.")
            return
        if not messagebox.askyesno("Confirmar coleta", "Executar a rotina completa agora?\n\nEla pode atualizar dados de jogos, histórico de preços e alertas no banco da AWS."):
            return
        try:
            env = self._collector_environment()
        except Exception as exc:
            messagebox.showerror("Configuração inválida", f"Não consegui preparar a conexão com o banco.\n\n{exc}")
            return
        self._launch_process(["--agora"], env, scheduler=False)

    def start_local_scheduler(self):
        if self.scheduler_process and self.scheduler_process.poll() is None:
            messagebox.showinfo("Agendador ativo", "O agendador local já está em execução.")
            return
        if self.collection_process and self.collection_process.poll() is None:
            messagebox.showwarning("Coleta em andamento", "Aguarde a coleta manual terminar antes de iniciar o agendador.")
            return
        schedule_time = self.schedule_var.get().strip()
        try:
            datetime.strptime(schedule_time, "%H:%M")
            env = self._collector_environment(schedule_time)
        except ValueError:
            messagebox.showerror("Horário inválido", "Informe o horário no formato HH:MM, por exemplo 03:00.")
            return
        except Exception as exc:
            messagebox.showerror("Configuração inválida", f"Não consegui preparar a conexão com o banco.\n\n{exc}")
            return
        if not messagebox.askyesno("Iniciar agendador local", f"Iniciar a rotina diária neste computador às {schedule_time}?\n\nO Manager precisa permanecer aberto e o computador ligado."):
            return
        self._launch_process([], env, scheduler=True)

    def stop_local_scheduler(self):
        proc = self.scheduler_process
        if not proc or proc.poll() is not None:
            messagebox.showinfo("Agendador parado", "Não há agendador local em execução.")
            return
        if messagebox.askyesno("Parar agendador", "Deseja parar o agendador local?"):
            proc.terminate()
            self._log("[INFO] Solicitação para parar o agendador local.")
            self.after(500, self._refresh_process_status)

    def _launch_process(self, args, env, scheduler):
        command = [sys.executable, "-m", "backend.coletores.agendador"] + list(args)
        try:
            proc = subprocess.Popen(command, cwd=str(PROJECT_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception as exc:
            messagebox.showerror("Não foi possível iniciar", str(exc))
            self._log(f"[ERRO] Falha ao iniciar processo: {type(exc).__name__}: {exc}")
            return
        if scheduler:
            self.scheduler_process = proc
            self._log(f"[INFO] Agendador local iniciado às {self.schedule_var.get().strip()}. PID={proc.pid}")
        else:
            self.collection_process = proc
            self._log(f"[INFO] Coleta manual iniciada. PID={proc.pid}")
        threading.Thread(target=self._read_process_output, args=(proc, "Agendador" if scheduler else "Coleta"), daemon=True).start()
        self.after(500, self._refresh_process_status)

    def _read_process_output(self, proc, label):
        try:
            for line in proc.stdout:
                self._log(f"[{label}] {line.rstrip()}")
        except Exception as exc:
            self._log(f"[ERRO] Leitura de saída de {label}: {exc}")
        finally:
            code = proc.wait()
            self._log(f"[INFO] {label} finalizado com código {code}.")
            self.after(0, self._refresh_process_status)

    def _scheduler_status_text(self):
        if self.scheduler_process and self.scheduler_process.poll() is None:
            return f"Agendador local ativo (PID {self.scheduler_process.pid})."
        return "Agendador local parado."

    def _refresh_process_status(self):
        if hasattr(self, "scheduler_status") and self.scheduler_status.winfo_exists():
            self.scheduler_status.configure(text=self._scheduler_status_text())
        if hasattr(self, "collection_status") and self.collection_status.winfo_exists():
            running = self.collection_process and self.collection_process.poll() is None
            self.collection_status.configure(text="Coleta manual: Em execução" if running else "Coleta manual: Parada")
        if self.collection_process and self.collection_process.poll() is not None:
            self.collection_process = None
        if self.scheduler_process and self.scheduler_process.poll() is not None:
            self.scheduler_process = None

    def _poll_log_queue(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if hasattr(self, "logs_text") and self.logs_text.winfo_exists():
                    self.logs_text.configure(state="normal")
                    self.logs_text.insert("end", line + "\n")
                    self.logs_text.see("end")
                    self.logs_text.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(250, self._poll_log_queue)

    def _log(self, message):
        line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {message}"
        self.log_queue.put(line)
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with LOG_FILE.open("a", encoding="utf-8") as file:
                file.write(line + "\n")
        except OSError:
            pass

    def refresh_logs(self):
        if not hasattr(self, "logs_text") or not self.logs_text.winfo_exists():
            return
        self.logs_text.configure(state="normal")
        self.logs_text.delete("1.0", "end")
        try:
            if LOG_FILE.exists():
                self.logs_text.insert("end", "\n".join(LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-500:]))
            else:
                self.logs_text.insert("end", "Nenhum evento registrado ainda.")
        except OSError as exc:
            self.logs_text.insert("end", f"Não foi possível ler o log: {exc}")
        self.logs_text.configure(state="disabled")

    def open_log_file(self):
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        if not LOG_FILE.exists():
            LOG_FILE.touch()
        try:
            os.startfile(str(LOG_FILE))
        except Exception as exc:
            messagebox.showerror("Não foi possível abrir", str(exc))

    def _on_close(self):
        active = [label for label, proc in (("coleta manual", self.collection_process), ("agendador local", self.scheduler_process)) if proc and proc.poll() is None]
        if active:
            if not messagebox.askyesno("Sair do Manager", "Estes processos estão ativos: " + ", ".join(active) + ". Deseja encerrá-los?"):
                return
            for proc in (self.collection_process, self.scheduler_process):
                if proc and proc.poll() is None:
                    proc.terminate()
        self.destroy()

    def _page_dashboard(self):
        ttk.Label(self.page_host, text="Visão geral", style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.page_host, text="Resumo operacional do DESCTRL em um só lugar.", style="Muted.TLabel").pack(anchor="w", pady=(5, 8))
        ttk.Label(self.page_host, text="Coletas: Windows local  ·  Banco: PostgreSQL AWS via túnel SSH  ·  Agendador EC2: desativado", style="Muted.TLabel", wraplength=850).pack(anchor="w", pady=(0, 16))
        cards = ttk.Frame(self.page_host)
        cards.pack(fill="x")
        for i in range(4):
            cards.columnconfigure(i, weight=1, uniform="cards")
        self._card(cards, "API", "Não verificada", "api.desctrl.com.br/health", self.c["blue"], 0, "api")
        self._card(cards, "Agendador AWS", "Não verificado", "desctrl-coleta.service", self.c["amber"], 1, "scheduler")
        self._card(cards, "API na EC2", "Não verificada", "desctrl-api.service", self.c["purple"], 2, "api_service")
        self._card(cards, "Disco EC2", "Não verificado", "Uso do volume raiz", self.c["green"], 3, "disk")
        row = ttk.Frame(self.page_host)
        row.pack(fill="both", expand=True, pady=(18, 0))
        row.columnconfigure(0, weight=3)
        row.columnconfigure(1, weight=2)
        p = self._panel(row, "Diagnóstico", "Último resultado da verificação de infraestrutura.")
        p.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.diagnostic_text = tk.Text(p, height=9, bg="#0a0d14", fg="#cbd5e1", insertbackground="#fff", relief="flat", font=("Consolas", 10), wrap="word")
        self.diagnostic_text.pack(fill="both", expand=True, pady=(14, 0))
        self.diagnostic_text.insert("end", "Nenhuma verificação executada nesta sessão.\nA verificação é somente leitura: não inicia coletas e não altera serviços.")
        self.diagnostic_text.configure(state="disabled")
        quick = self._panel(row, "Ações rápidas", "Diagnóstico remoto somente de leitura.")
        quick.grid(row=0, column=1, sticky="nsew")
        self.check_button = ttk.Button(quick, text="◉  Verificar infraestrutura", style="Accent.TButton", command=self.check_infrastructure)
        self.check_button.pack(fill="x", pady=(15, 8))
        ttk.Button(quick, text="⇄  Abrir central de coletas", command=lambda: self.show_page("Coletas")).pack(fill="x", pady=4)
        ttk.Button(quick, text="◷  Ver agendamento", command=lambda: self.show_page("Agendamento")).pack(fill="x", pady=4)
        tk.Frame(quick, bg=self.c["line"], height=1).pack(fill="x", pady=(18, 12))
        tk.Label(quick, text="SEGURANÇA", bg=self.c["panel"], fg=self.c["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(quick, text="Nenhuma senha é exibida ou armazenada pelo painel.", bg=self.c["panel"], fg=self.c["text"], wraplength=230, justify="left").pack(anchor="w", pady=(6, 0))

    def _simple_page(self, title, description):
        ttk.Label(self.page_host, text=title, style="Section.TLabel").pack(anchor="w")
        ttk.Label(self.page_host, text=description, style="Muted.TLabel", wraplength=700).pack(anchor="w", pady=(8, 20))
        p = self._panel(self.page_host, "Estado", "As ações operacionais serão conectadas depois do diagnóstico.")
        p.pack(fill="x")

    def check_infrastructure(self):
        if not shutil.which("ssh"):
            messagebox.showerror("SSH não encontrado", "O executável ssh não foi encontrado no PATH do Windows.")
            return
        if not os.path.isfile(self.ssh_key):
            messagebox.showerror("Chave SSH não encontrada", f"Não encontrei a chave:\n{self.ssh_key}")
            return
        self.check_button.configure(state="disabled", text="Verificando...")
        self._set_diag_text("Verificação em andamento...\n1. Consultando endpoint público da API.\n2. Consultando serviços e recursos da EC2 por SSH.\n")
        threading.Thread(target=self._diagnostic_worker, daemon=True).start()

    def _diagnostic_worker(self):
        results = []
        values = {}
        try:
            req = urllib.request.Request(self.api_url, headers={"User-Agent": "DESCTRL-Manager/1.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                payload = response.read(65536).decode("utf-8", errors="replace")
                data = json.loads(payload)
                if response.status == 200 and data.get("status") == "online":
                    values["api"] = ("Online", self.c["green"])
                    results.append("[OK] API pública: HTTP 200, status online")
                else:
                    values["api"] = ("Resposta inesperada", self.c["amber"])
                    results.append(f"[AVISO] API pública: HTTP {response.status}; resposta {payload[:200]}")
        except Exception as e:
            values["api"] = ("Falha", self.c["red"])
            results.append(f"[ERRO] API pública: {type(e).__name__}: {e}")

        remote_script = r"""
printf 'HOST=%s\\n' "$(hostname)"
printf 'API_SERVICE=%s\\n' "$(systemctl is-active desctrl-api.service 2>/dev/null || true)"
printf 'SCHEDULER_ACTIVE=%s\\n' "$(systemctl is-active desctrl-coleta.service 2>/dev/null || true)"
printf 'SCHEDULER_ENABLED=%s\\n' "$(systemctl is-enabled desctrl-coleta.service 2>/dev/null || true)"
free -b | awk '/^Mem:/ {printf "MEMORY=%s %s %s\\n", $2, $3, $7}'
free -b | awk '/^Swap:/ {printf "SWAP=%s %s\\n", $2, $3}'
df -B1 / | awk 'NR==2 {printf "DISK=%s %s %s\\n", $2, $3, $4}'
"""
        cmd = ["ssh", "-i", self.ssh_key, "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
               "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=2", self.ssh_host, remote_script]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25, encoding="utf-8", errors="replace")
            if proc.returncode:
                raise RuntimeError(proc.stderr.strip() or f"SSH retornou código {proc.returncode}")
            parsed = {}
            # Algumas respostas SSH chegam com "\\n" literal em vez de quebras reais.
            normalized_stdout = proc.stdout.replace("\\r\\n", "\\n")
            normalized_stdout = normalized_stdout.replace("\\n", "\n")
            for line in normalized_stdout.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    parsed[k.strip()] = v.strip()
            api_service = parsed.get("API_SERVICE", "desconhecido")
            sched_active = parsed.get("SCHEDULER_ACTIVE", "desconhecido")
            sched_enabled = parsed.get("SCHEDULER_ENABLED", "desconhecido")
            values["api_service"] = ("Ativo" if api_service == "active" else api_service, self.c["green"] if api_service == "active" else self.c["red"])
            values["scheduler"] = (f"{sched_active} / {sched_enabled}", self.c["green"] if sched_active == "inactive" and sched_enabled == "disabled" else self.c["amber"])
            results.append(f"[OK] SSH: conectado a {parsed.get('HOST', 'instância AWS')}")
            results.append(f"[{'OK' if api_service == 'active' else 'AVISO'}] Serviço da API: {api_service}")
            results.append(f"[{'OK' if sched_active == 'inactive' and sched_enabled == 'disabled' else 'AVISO'}] Agendador: ativo={sched_active}; habilitado={sched_enabled}")
            mem = parsed.get("MEMORY", "").split()
            if len(mem) >= 3:
                total, used, avail = map(int, mem[:3])
                results.append(f"[INFO] RAM: {used/1024**3:.2f} GB usados de {total/1024**3:.2f} GB; disponível {avail/1024**3:.2f} GB")
            swap = parsed.get("SWAP", "").split()
            if len(swap) >= 2:
                total, used = map(int, swap[:2])
                results.append(f"[INFO] Swap: {used/1024**3:.2f} GB usados de {total/1024**3:.2f} GB")
            disk = parsed.get("DISK", "").split()
            if len(disk) >= 3:
                total, used, free = map(int, disk[:3])
                values["disk"] = (f"{free/1024**3:.1f} GB livres", self.c["green"] if free/total > .15 else self.c["amber"])
                results.append(f"[INFO] Disco raiz: {used/total*100:.1f}% usado; {free/1024**3:.1f} GB livres")
        except Exception as e:
            values["api_service"] = ("Falha SSH", self.c["red"])
            values["scheduler"] = ("Sem conexão", self.c["red"])
            results.append(f"[ERRO] Diagnóstico SSH: {type(e).__name__}: {e}")
        self.after(0, lambda: self._apply_diagnostic(values, results))

    def _set_diag_text(self, text):
        if hasattr(self, "diagnostic_text"):
            self.diagnostic_text.configure(state="normal")
            self.diagnostic_text.delete("1.0", "end")
            self.diagnostic_text.insert("end", text)
            self.diagnostic_text.configure(state="disabled")

    def _apply_diagnostic(self, values, results):
        for key, pair in values.items():
            if key in self.status_labels:
                self.status_labels[key].configure(text=pair[0], foreground=pair[1])
        report = f"Verificação concluída em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n" + "\n".join(results)
        self._set_diag_text(report)
        self.check_button.configure(state="normal", text="◉  Verificar infraestrutura")

    def _update_clock(self):
        self.clock.configure(text=datetime.now().strftime("%d/%m/%Y  %H:%M:%S"))
        self.after(1000, self._update_clock)


if __name__ == "__main__":
    DesctrlManager().mainloop()
