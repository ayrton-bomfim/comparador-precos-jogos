"""
DESCTRL Manager: painel para rodar e acompanhar a coleta diária neste PC.

A coleta em si roda no executor (backend/desctrl_manager/executor.py), um
processo separado no Python do projeto. Por isso ela continua se o Manager
for fechado, e o Manager mostra também as coletas disparadas pela tarefa
agendada do Windows.

Executar: py app.py      Gerar EXE: build.bat
"""

import json
import os
import re
import subprocess
import threading
import tkinter as tk
import urllib.request
from datetime import datetime
from tkinter import messagebox, ttk

try:
    from . import infra
except ImportError:  # executado como script ou EXE
    import infra

APP_NAME = "DESCTRL Manager"

CORES = {
    "bg": "#0d1018", "sidebar": "#111622", "panel": "#171d2b", "panel2": "#1e2637",
    "line": "#293249", "text": "#f0f3fa", "muted": "#929db4", "dim": "#68748d",
    "purple": "#8977ff", "purple_hover": "#a194ff", "green": "#45d6a0",
    "amber": "#f0bd62", "red": "#ff6b7a", "blue": "#6ea8fe", "log": "#0a0d14",
}

STATUS = {
    "concluida": ("Concluída", "green"),
    "concluida_com_avisos": ("Concluída com avisos", "amber"),
    "parcial": ("Parcial", "amber"),
    "falha": ("Falha", "red"),
}

RESULTADO_TAREFA = {
    0: "concluída",
    1: "terminou com falha",
    2: "não iniciou (outra coleta em andamento)",
    267009: "em execução",
    267011: "ainda não rodou",
}

RE_ETAPA = re.compile(r"^\[(\d+)/(\d+)\]\s+(.+)$")
RE_PROGRESSO = re.compile(r"(GetItems|EGDATA):\s+(\d+)/(\d+)")

PAGINAS = (
    ("Painel", "▦"),
    ("Executar", "▶"),
    ("Histórico", "≡"),
    ("Agendamento", "◷"),
    ("Infraestrutura", "◉"),
    ("Configurações", "⚙"),
)


def formatar_duracao(segundos):
    if segundos is None:
        return "—"
    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos, seg = divmod(resto, 60)
    if horas:
        return f"{horas}h {minutos:02d}min"
    if minutos:
        return f"{minutos}min {seg:02d}s"
    return f"{seg}s"


def formatar_data(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return "—"


def numero(valor):
    return f"{valor:,}".replace(",", ".")


def porcentagem(valor):
    return f"{valor:.1%}".replace(".", ",")


def dados_loja(registro, chave):
    """(cobertura, novos) da loja na execução, ou None se ela não rodou."""
    etapa = (registro.get("etapas") or {}).get(chave)
    if not isinstance(etapa, dict) or "cobertura" not in etapa:
        return None
    return porcentagem(etapa["cobertura"]), numero(etapa.get("novos_registros", 0))


def resumo_loja(registro, chave):
    dados = dados_loja(registro, chave)
    return f"{dados[0]} · +{dados[1]}" if dados else "—"


class Manager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1220x800")
        self.minsize(1020, 680)
        self.configure(bg=CORES["bg"])
        self.config_manager = infra.ler_config()

        self.pagina_atual = None
        self.botoes_nav = {}
        self.execucao = None          # dados da trava da coleta em andamento
        self.log_aberto = None        # arquivo de log acompanhado
        self.log_posicao = 0
        self.log_linhas = []
        self.progresso = {"etapa": 0, "total": 0, "titulo": "", "fracao": 0.0}
        self.agendamento = None
        self.widgets = {}

        self._estilos()
        self._estrutura()
        self.protocol("WM_DELETE_WINDOW", self._fechar)
        self.mostrar("Painel")
        self._ciclo_agendamento()
        self._tick()

    # ------------------------------------------------------------ visual

    def _estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        c = CORES
        s.configure(".", font=("Segoe UI", 10), background=c["bg"], foreground=c["text"])
        s.configure("TFrame", background=c["bg"])
        s.configure("Card.TFrame", background=c["panel"])
        s.configure("Sidebar.TFrame", background=c["sidebar"])
        s.configure("TLabel", background=c["bg"], foreground=c["text"])
        s.configure("Muted.TLabel", background=c["bg"], foreground=c["muted"])
        s.configure("Titulo.TLabel", background=c["bg"], foreground=c["text"], font=("Segoe UI Semibold", 17))
        s.configure("TButton", background=c["panel2"], foreground=c["text"], borderwidth=0, padding=(12, 8))
        s.map("TButton", background=[("active", c["line"]), ("disabled", c["panel"])],
              foreground=[("disabled", c["dim"])])
        s.configure("Accent.TButton", background=c["purple"], foreground="#ffffff", padding=(14, 9),
                    font=("Segoe UI Semibold", 10))
        s.map("Accent.TButton", background=[("active", c["purple_hover"]), ("disabled", c["panel2"])],
              foreground=[("disabled", c["dim"])])
        s.configure("Perigo.TButton", background=c["panel2"], foreground=c["red"], padding=(12, 8))
        s.map("Perigo.TButton", background=[("active", c["line"]), ("disabled", c["panel"])],
              foreground=[("disabled", c["dim"])])
        s.configure("Nav.TButton", background=c["sidebar"], foreground=c["muted"], anchor="w",
                    padding=(14, 10), borderwidth=0)
        s.map("Nav.TButton", background=[("active", c["panel2"])], foreground=[("active", c["text"])])
        s.configure("NavAtivo.TButton", background=c["panel2"], foreground=c["text"], anchor="w",
                    padding=(14, 10), borderwidth=0, font=("Segoe UI Semibold", 10))
        s.configure("Treeview", background=c["panel"], fieldbackground=c["panel"], foreground=c["text"],
                    rowheight=30, borderwidth=0, bordercolor=c["panel"], lightcolor=c["panel"],
                    darkcolor=c["panel"])
        s.configure("Treeview.Heading", background=c["panel2"], foreground=c["muted"], relief="flat",
                    padding=(8, 7))
        s.map("Treeview", background=[("selected", c["purple"])], foreground=[("selected", "#ffffff")])
        s.configure("Coleta.Horizontal.TProgressbar", troughcolor=c["panel2"], background=c["purple"],
                    bordercolor=c["panel2"], lightcolor=c["purple"], darkcolor=c["purple"], thickness=10)
        s.configure("TCheckbutton", background=c["panel"], foreground=c["text"],
                    indicatorbackground=c["panel2"], indicatorforeground="#ffffff", indicatorrelief="flat")
        s.map("TCheckbutton", background=[("active", c["panel"])],
              indicatorbackground=[("selected", c["purple"]), ("active", c["line"])])
        s.configure("Vertical.TScrollbar", background=c["panel2"], troughcolor=c["log"], bordercolor=c["log"],
                    arrowcolor=c["muted"], lightcolor=c["panel2"], darkcolor=c["panel2"])
        s.map("Vertical.TScrollbar", background=[("active", c["line"])])
        s.configure("TEntry", fieldbackground=c["panel2"], foreground=c["text"], insertcolor=c["text"],
                    bordercolor=c["line"], padding=6)

    def _estrutura(self):
        c = CORES
        casca = ttk.Frame(self)
        casca.pack(fill="both", expand=True)

        lateral = ttk.Frame(casca, style="Sidebar.TFrame", padding=(14, 22))
        lateral.pack(side="left", fill="y")
        lateral.configure(width=232)
        lateral.pack_propagate(False)

        marca = tk.Frame(lateral, bg=c["sidebar"])
        marca.pack(fill="x", padx=5, pady=(0, 26))
        tk.Label(marca, text="◈", bg=c["sidebar"], fg=c["purple"], font=("Segoe UI", 24, "bold")).pack(side="left")
        textos = tk.Frame(marca, bg=c["sidebar"])
        textos.pack(side="left", padx=(9, 0))
        tk.Label(textos, text="DESCTRL", bg=c["sidebar"], fg=c["text"], font=("Segoe UI Semibold", 16)).pack(anchor="w")
        tk.Label(textos, text="MANAGER", bg=c["sidebar"], fg=c["muted"], font=("Segoe UI", 8, "bold")).pack(anchor="w")

        for nome, glifo in PAGINAS:
            botao = ttk.Button(lateral, text=f"{glifo}   {nome}", style="Nav.TButton",
                               command=lambda n=nome: self.mostrar(n))
            botao.pack(fill="x", pady=1)
            self.botoes_nav[nome] = botao

        tk.Frame(lateral, bg=c["sidebar"]).pack(fill="both", expand=True)
        tk.Frame(lateral, bg=c["line"], height=1).pack(fill="x", pady=(10, 12))
        self.lbl_estado = tk.Label(lateral, text="○  Nenhuma coleta rodando", bg=c["sidebar"], fg=c["muted"],
                                   font=("Segoe UI", 9), anchor="w", justify="left", wraplength=190)
        self.lbl_estado.pack(fill="x", padx=8)
        self.lbl_proxima = tk.Label(lateral, text="◷  Agendamento: verificando...", bg=c["sidebar"],
                                    fg=c["muted"], font=("Segoe UI", 9), anchor="w", justify="left",
                                    wraplength=190)
        self.lbl_proxima.pack(fill="x", padx=8, pady=(6, 0))
        tk.Label(lateral, text="Banco: produção (AWS)", bg=c["sidebar"], fg=c["dim"],
                 font=("Segoe UI", 8)).pack(anchor="w", padx=8, pady=(10, 0))

        self.principal = ttk.Frame(casca, padding=(28, 22, 28, 22))
        self.principal.pack(side="left", fill="both", expand=True)

    def _cabecalho(self, titulo, subtitulo):
        ttk.Label(self.principal, text=titulo, style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self.principal, text=subtitulo, style="Muted.TLabel", wraplength=900).pack(anchor="w", pady=(4, 16))

    def _painel(self, pai, titulo, subtitulo=None):
        painel = ttk.Frame(pai, style="Card.TFrame", padding=16)
        tk.Label(painel, text=titulo, bg=CORES["panel"], fg=CORES["text"],
                 font=("Segoe UI Semibold", 12)).pack(anchor="w")
        if subtitulo:
            tk.Label(painel, text=subtitulo, bg=CORES["panel"], fg=CORES["muted"], font=("Segoe UI", 9),
                     wraplength=880, justify="left").pack(anchor="w", pady=(3, 0))
        return painel

    def _cartao(self, pai, coluna, titulo, chave, cor):
        cartao = ttk.Frame(pai, style="Card.TFrame", padding=(16, 14))
        cartao.grid(row=0, column=coluna, sticky="nsew", padx=(0 if coluna == 0 else 10, 0))
        tk.Frame(cartao, bg=CORES[cor], height=3).pack(fill="x", pady=(0, 12))
        tk.Label(cartao, text=titulo, bg=CORES["panel"], fg=CORES["muted"], font=("Segoe UI", 9)).pack(anchor="w")
        valor = tk.Label(cartao, text="—", bg=CORES["panel"], fg=CORES["text"], font=("Segoe UI Semibold", 14),
                         anchor="w", justify="left", wraplength=210)
        valor.pack(anchor="w", pady=(6, 2))
        detalhe = tk.Label(cartao, text="", bg=CORES["panel"], fg=CORES["muted"], font=("Segoe UI", 9),
                           anchor="w", justify="left", wraplength=210)
        detalhe.pack(anchor="w")
        self.widgets[f"{chave}_valor"] = valor
        self.widgets[f"{chave}_detalhe"] = detalhe

    def _caixa_log(self, pai, altura):
        caixa = tk.Text(pai, height=altura, bg=CORES["log"], fg="#cbd5e1", relief="flat",
                        font=("Consolas", 9), wrap="none", padx=10, pady=8, insertbackground="#fff")
        barra = ttk.Scrollbar(pai, orient="vertical", command=caixa.yview)
        caixa.configure(yscrollcommand=barra.set, state="disabled")
        barra.pack(side="right", fill="y", pady=(12, 0))
        caixa.pack(fill="both", expand=True, pady=(12, 0))
        caixa.tag_configure("etapa", foreground=CORES["purple_hover"], font=("Consolas", 9, "bold"))
        caixa.tag_configure("erro", foreground=CORES["red"])
        caixa.tag_configure("aviso", foreground=CORES["amber"])
        return caixa

    def _escrever_log(self, caixa, linhas, limpar=False):
        if not caixa or not caixa.winfo_exists():
            return
        caixa.configure(state="normal")
        if limpar:
            caixa.delete("1.0", "end")
        for linha in linhas:
            tag = ()
            if RE_ETAPA.match(linha) or linha.startswith(("INÍCIO DA COLETA", "FIM DA COLETA", "RESUMO")):
                tag = ("etapa",)
            elif "ERRO" in linha or "FALHA" in linha or "Traceback" in linha:
                tag = ("erro",)
            elif "⚠" in linha or "AVISO" in linha:
                tag = ("aviso",)
            caixa.insert("end", linha + "\n", tag)
        linhas_totais = int(caixa.index("end-1c").split(".")[0])
        if linhas_totais > 1500:
            caixa.delete("1.0", f"{linhas_totais - 1500}.0")
        caixa.see("end")
        caixa.configure(state="disabled")

    # ------------------------------------------------------------ navegação

    def mostrar(self, nome):
        self.pagina_atual = nome
        for pagina, botao in self.botoes_nav.items():
            botao.configure(style="NavAtivo.TButton" if pagina == nome else "Nav.TButton")
        for filho in self.principal.winfo_children():
            filho.destroy()
        self.widgets = {}
        {
            "Painel": self._pagina_painel,
            "Executar": self._pagina_executar,
            "Histórico": self._pagina_historico,
            "Agendamento": self._pagina_agendamento,
            "Infraestrutura": self._pagina_infra,
            "Configurações": self._pagina_config,
        }[nome]()
        self._atualizar_estado_execucao(forcar=True)

    # --------------------------------------------------------------- painel

    def _pagina_painel(self):
        self._cabecalho("Painel", "Situação da coleta diária de preços. A coleta roda neste computador e grava no banco da AWS.")
        cartoes = ttk.Frame(self.principal)
        cartoes.pack(fill="x")
        for i in range(4):
            cartoes.columnconfigure(i, weight=1, uniform="cartoes")
        self._cartao(cartoes, 0, "Última coleta", "ultima", "purple")
        self._cartao(cartoes, 1, "Steam na última coleta", "steam", "blue")
        self._cartao(cartoes, 2, "Epic na última coleta", "epic", "green")
        self._cartao(cartoes, 3, "Próxima coleta agendada", "proxima", "amber")
        self._preencher_cartoes()

        painel = self._painel(self.principal, "Coleta agora")
        painel.pack(fill="both", expand=True, pady=(16, 0))
        linha = tk.Frame(painel, bg=CORES["panel"])
        linha.pack(fill="x", pady=(10, 0))
        self.widgets["etapa"] = tk.Label(linha, text="", bg=CORES["panel"], fg=CORES["text"],
                                         font=("Segoe UI Semibold", 11), anchor="w")
        self.widgets["etapa"].pack(side="left")
        ttk.Button(linha, text="■  Parar", style="Perigo.TButton", command=self.parar).pack(side="right")
        ttk.Button(linha, text="▶  Rodar coleta completa", style="Accent.TButton",
                   command=lambda: self.rodar(None)).pack(side="right", padx=(0, 8))
        self.widgets["barra"] = ttk.Progressbar(painel, style="Coleta.Horizontal.TProgressbar",
                                                mode="determinate", maximum=1000)
        self.widgets["barra"].pack(fill="x", pady=(12, 0))
        self.widgets["detalhe_execucao"] = tk.Label(painel, text="", bg=CORES["panel"], fg=CORES["muted"],
                                                    font=("Segoe UI", 9), anchor="w")
        self.widgets["detalhe_execucao"].pack(fill="x", pady=(6, 0))
        self.widgets["log"] = self._caixa_log(painel, 16)
        self._carregar_log_inicial()

    def _preencher_cartoes(self):
        execucoes = infra.historico(1)
        if execucoes:
            ultima = execucoes[0]
            texto, cor = STATUS.get(ultima.get("status"), (ultima.get("status") or "—", "muted"))
            self._definir("ultima", texto, f"{formatar_data(ultima.get('inicio'))} · "
                          f"{formatar_duracao(ultima.get('duracao_segundos'))}", CORES[cor])
            for loja in ("steam", "epic"):
                dados = dados_loja(ultima, loja)
                if dados:
                    self._definir(loja, dados[0], f"dos jogos com preço · {dados[1]} preços novos")
                else:
                    self._definir(loja, "—", "não rodou na última coleta")
        else:
            self._definir("ultima", "Nenhuma", "Ainda não há coleta registrada.")
        self._preencher_proxima()

    def _preencher_proxima(self):
        estado = self.agendamento
        if estado is None:
            self._definir("proxima", "Verificando...", "")
        elif not estado.get("existe"):
            self._definir("proxima", "Não agendada", "Ative em Agendamento.", CORES["amber"])
        elif not estado.get("ativa"):
            self._definir("proxima", "Desativada", f"Horário salvo: {estado.get('horario')}", CORES["amber"])
        else:
            self._definir("proxima", estado.get("proxima") or "—", f"Todo dia às {estado.get('horario')}")

    def _definir(self, chave, valor, detalhe, cor=None):
        rotulo = self.widgets.get(f"{chave}_valor")
        if rotulo and rotulo.winfo_exists():
            rotulo.configure(text=valor, fg=cor or CORES["text"])
            self.widgets[f"{chave}_detalhe"].configure(text=detalhe)

    # ------------------------------------------------------------- executar

    def _pagina_executar(self):
        self._cabecalho("Executar", "Rode a coleta inteira ou só algumas etapas. As etapas sempre seguem a ordem abaixo.")
        painel = self._painel(self.principal, "Etapas", "Útil para refazer só a Epic, ou só atualizar os preços do catálogo depois de uma correção.")
        painel.pack(fill="x")
        descricoes = {
            "steam": "preços de ~91 mil jogos via GetItems em lote (≈5 min de consulta)",
            "epic": "preços de ~6,5 mil ofertas via ITAD, com conferência na EGDATA (≈2 min)",
            "alertas": "avalia os alertas de preço dos usuários e envia e-mails",
            "limpeza": "tira da vitrine e das recomendações promoções que acabaram",
            "precos_atuais": "recalcula o preço atual de cada jogo mostrado no catálogo",
        }
        self.vars_etapas = {}
        for chave, nome in infra.ETAPAS:
            var = tk.BooleanVar(value=True)
            self.vars_etapas[chave] = var
            linha = tk.Frame(painel, bg=CORES["panel"])
            linha.pack(fill="x", pady=(8, 0))
            ttk.Checkbutton(linha, text=nome, variable=var).pack(side="left")
            tk.Label(linha, text=f"— {descricoes[chave]}", bg=CORES["panel"], fg=CORES["muted"],
                     font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))
        botoes = tk.Frame(painel, bg=CORES["panel"])
        botoes.pack(fill="x", pady=(14, 0))
        ttk.Button(botoes, text="▶  Rodar etapas marcadas", style="Accent.TButton",
                   command=self._rodar_marcadas).pack(side="left")
        ttk.Button(botoes, text="■  Parar", style="Perigo.TButton", command=self.parar).pack(side="left", padx=8)

        acompanhamento = self._painel(self.principal, "Acompanhamento")
        acompanhamento.pack(fill="both", expand=True, pady=(16, 0))
        self.widgets["etapa"] = tk.Label(acompanhamento, text="", bg=CORES["panel"], fg=CORES["text"],
                                         font=("Segoe UI Semibold", 11), anchor="w")
        self.widgets["etapa"].pack(fill="x", pady=(8, 0))
        self.widgets["barra"] = ttk.Progressbar(acompanhamento, style="Coleta.Horizontal.TProgressbar",
                                                mode="determinate", maximum=1000)
        self.widgets["barra"].pack(fill="x", pady=(10, 0))
        self.widgets["detalhe_execucao"] = tk.Label(acompanhamento, text="", bg=CORES["panel"],
                                                    fg=CORES["muted"], font=("Segoe UI", 9), anchor="w")
        self.widgets["detalhe_execucao"].pack(fill="x", pady=(6, 0))
        self.widgets["log"] = self._caixa_log(acompanhamento, 12)
        self._carregar_log_inicial()

    def _rodar_marcadas(self):
        etapas = [chave for chave, var in self.vars_etapas.items() if var.get()]
        if not etapas:
            messagebox.showinfo("Nenhuma etapa", "Marque pelo menos uma etapa.")
            return
        self.rodar(None if len(etapas) == len(infra.ETAPAS) else etapas)

    def rodar(self, etapas):
        if infra.execucao_atual():
            messagebox.showwarning("Coleta em andamento", "Já existe uma coleta rodando. Aguarde ou pare a atual.")
            return
        nomes = dict(infra.ETAPAS)
        descricao = "a coleta completa" if not etapas else "as etapas: " + ", ".join(nomes[e] for e in etapas)
        if not messagebox.askyesno("Rodar coleta", f"Rodar {descricao}?\n\nOs preços serão gravados no banco "
                                   "de produção (AWS). A coleta continua mesmo se o Manager for fechado."):
            return
        try:
            infra.iniciar_coleta(etapas, origem="manual")
        except Exception as erro:
            messagebox.showerror("Não foi possível iniciar", str(erro))
            infra.registrar_manager(f"[ERRO] Início da coleta: {erro}")
            return
        infra.registrar_manager(f"[INFO] Coleta manual iniciada ({descricao}).")
        self.after(1500, lambda: self._atualizar_estado_execucao(forcar=True))

    def parar(self):
        atual = infra.execucao_atual()
        if not atual:
            messagebox.showinfo("Nada para parar", "Não há coleta em andamento.")
            return
        if not messagebox.askyesno("Parar coleta", "Parar a coleta agora?\n\nO que já foi gravado fica no banco; "
                                   "a etapa atual fica incompleta."):
            return
        infra.parar_coleta()
        infra.registrar_manager(f"[INFO] Coleta interrompida pelo usuário (PID {atual['pid']}).")
        self._atualizar_estado_execucao(forcar=True)

    # ---------------------------------------------------- acompanhamento

    def _tick(self):
        try:
            self._atualizar_estado_execucao()
        finally:
            self.after(1000, self._tick)

    def _atualizar_estado_execucao(self, forcar=False):
        atual = infra.execucao_atual()
        mudou = (atual or {}).get("pid") != (self.execucao or {}).get("pid")
        terminou = self.execucao is not None and atual is None
        self.execucao = atual

        if atual:
            if mudou or forcar or self.log_aberto != atual.get("log"):
                self._acompanhar(atual.get("log"))
            else:
                self._ler_novas_linhas()
        elif terminou:
            self._ler_novas_linhas()
            infra.registrar_manager("[INFO] Coleta finalizada.")
            if self.pagina_atual == "Painel":
                self._preencher_cartoes()
            elif self.pagina_atual == "Histórico":
                self._preencher_historico()

        self._mostrar_progresso()

    def _acompanhar(self, arquivo):
        self.log_aberto = arquivo
        self.log_posicao = 0
        self.log_linhas = []
        self.progresso = {"etapa": 0, "total": 0, "titulo": "", "fracao": 0.0}
        self._escrever_log(self.widgets.get("log"), [], limpar=True)
        self._ler_novas_linhas()

    def _carregar_log_inicial(self):
        """Ao abrir a página: coleta em andamento ou o log da última."""
        atual = infra.execucao_atual()
        if atual:
            self._acompanhar(atual.get("log"))
            return
        execucoes = infra.historico(1)
        arquivo = execucoes[0].get("log") if execucoes else None
        if arquivo and os.path.isfile(arquivo):
            self.log_aberto = None
            linhas = infra.ultimas_linhas(arquivo, 400)
            self._escrever_log(self.widgets.get("log"), [f"(log da última coleta: {os.path.basename(arquivo)})", ""] + linhas, limpar=True)
        else:
            self._escrever_log(self.widgets.get("log"), ["Nenhuma coleta em andamento."], limpar=True)

    def _ler_novas_linhas(self):
        if not self.log_aberto:
            return
        try:
            with open(self.log_aberto, "rb") as f:
                f.seek(self.log_posicao)
                bruto = f.read()
        except OSError:
            return
        if not bruto:
            return
        corte = bruto.rfind(b"\n") + 1
        if corte == 0:
            return
        self.log_posicao += corte
        linhas = bruto[:corte].decode("utf-8", "replace").splitlines()
        for linha in linhas:
            self._interpretar(linha)
        self._escrever_log(self.widgets.get("log"), linhas)

    def _interpretar(self, linha):
        etapa = RE_ETAPA.match(linha.strip())
        if etapa:
            self.progresso.update(etapa=int(etapa.group(1)), total=int(etapa.group(2)),
                                  titulo=etapa.group(3), fracao=0.0)
            return
        andamento = RE_PROGRESSO.search(linha)
        if andamento and int(andamento.group(3)):
            self.progresso["fracao"] = min(0.95, int(andamento.group(2)) / int(andamento.group(3)) * 0.6)

    def _mostrar_progresso(self):
        atual = self.execucao
        rotulo_etapa = self.widgets.get("etapa")
        barra = self.widgets.get("barra")
        detalhe = self.widgets.get("detalhe_execucao")
        if atual:
            p = self.progresso
            inicio = datetime.fromisoformat(atual["inicio"])
            decorrido = formatar_duracao((datetime.now() - inicio).total_seconds())
            texto = (f"Etapa {p['etapa']} de {p['total']}: {p['titulo']}" if p["total"]
                     else "Preparando (abrindo túnel e carregando dados)...")
            info = f"Origem: {atual.get('origem')} · iniciada às {inicio:%H:%M} · {decorrido} decorridos · PID {atual['pid']}"
            if atual.get("ambiente") == "dev":
                info += " · banco DEV (teste)"
            total = p["total"] or 1
            valor = ((max(p["etapa"], 1) - 1) + p["fracao"]) / total * 1000 if p["total"] else 0
            self.lbl_estado.configure(text=f"●  Coleta rodando · {decorrido}", fg=CORES["green"])
        else:
            texto = "Nenhuma coleta em andamento."
            info = ""
            valor = 0
            self.lbl_estado.configure(text="○  Nenhuma coleta rodando", fg=CORES["muted"])
        if rotulo_etapa and rotulo_etapa.winfo_exists():
            rotulo_etapa.configure(text=texto)
        if barra and barra.winfo_exists():
            barra.configure(value=valor)
        if detalhe and detalhe.winfo_exists():
            detalhe.configure(text=info)

    # ------------------------------------------------------------ histórico

    def _pagina_historico(self):
        self._cabecalho("Histórico", "Coletas no banco de produção, da mais recente para a mais antiga. Clique duas vezes para abrir o log.")
        painel = self._painel(self.principal, "Execuções")
        painel.pack(fill="both", expand=True)
        botoes = tk.Frame(painel, bg=CORES["panel"])
        botoes.pack(fill="x", pady=(8, 0))
        ttk.Button(botoes, text="Atualizar", command=self._preencher_historico).pack(side="left")
        ttk.Button(botoes, text="Abrir log selecionado", command=self._abrir_log_selecionado).pack(side="left", padx=8)
        ttk.Button(botoes, text="Abrir pasta de logs",
                   command=lambda: self._abrir(infra.PASTA_LOGS_COLETA)).pack(side="left")
        colunas = (("inicio", "Início", 140), ("origem", "Origem", 80), ("etapas", "Etapas", 110),
                   ("status", "Status", 175), ("duracao", "Duração", 95), ("steam", "Steam", 160),
                   ("epic", "Epic", 160))
        frame = tk.Frame(painel, bg=CORES["panel"])
        frame.pack(fill="both", expand=True, pady=(12, 0))
        arvore = ttk.Treeview(frame, columns=[c[0] for c in colunas], show="headings")
        for chave, titulo, largura in colunas:
            arvore.heading(chave, text=titulo, anchor="w")
            arvore.column(chave, width=largura, minwidth=largura, anchor="w",
                          stretch=chave in {"etapas", "steam", "epic"})
        for status, (_, cor) in STATUS.items():
            arvore.tag_configure(status, foreground=CORES[cor])
        barra = ttk.Scrollbar(frame, orient="vertical", command=arvore.yview)
        arvore.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y")
        arvore.pack(fill="both", expand=True)
        arvore.bind("<Double-1>", lambda _e: self._abrir_log_selecionado())
        self.widgets["arvore"] = arvore
        self._preencher_historico()

    def _preencher_historico(self):
        arvore = self.widgets.get("arvore")
        if not arvore or not arvore.winfo_exists():
            return
        arvore.delete(*arvore.get_children())
        self.logs_historico = {}
        nomes = dict(infra.ETAPAS)
        for indice, registro in enumerate(infra.historico(200)):
            solicitadas = registro.get("etapas_solicitadas")
            etapas = "Todas" if not solicitadas or len(solicitadas) == len(infra.ETAPAS) else \
                ", ".join(nomes.get(e, e) for e in solicitadas)
            status = registro.get("status")
            iid = arvore.insert("", "end", values=(
                formatar_data(registro.get("inicio")),
                registro.get("origem") or "—",
                etapas,
                STATUS.get(status, (status or "—",))[0],
                formatar_duracao(registro.get("duracao_segundos")),
                resumo_loja(registro, "steam"),
                resumo_loja(registro, "epic"),
            ), tags=(status,) if status in STATUS else ())
            self.logs_historico[iid] = registro.get("log")

    def _abrir_log_selecionado(self):
        arvore = self.widgets.get("arvore")
        selecionado = arvore.selection() if arvore else ()
        if not selecionado:
            messagebox.showinfo("Selecione uma coleta", "Selecione uma linha do histórico.")
            return
        arquivo = self.logs_historico.get(selecionado[0])
        if not arquivo or not os.path.isfile(arquivo):
            messagebox.showinfo("Sem log", "Esta coleta não tem log separado (é anterior ao novo Manager) "
                                "ou o arquivo já foi apagado. São mantidos os 60 logs mais recentes.")
            return
        self._abrir(arquivo)

    def _abrir(self, caminho):
        try:
            if caminho == infra.PASTA_LOGS_COLETA:
                os.makedirs(caminho, exist_ok=True)
            os.startfile(str(caminho))
        except Exception as erro:
            messagebox.showerror("Não foi possível abrir", str(erro))

    # ---------------------------------------------------------- agendamento

    def _pagina_agendamento(self):
        self._cabecalho("Agendamento", "A coleta diária é uma tarefa do Agendador de Tarefas do Windows. "
                        "Ela roda mesmo com o Manager fechado.")
        painel = self._painel(self.principal, "Coleta diária")
        painel.pack(fill="x")
        self.widgets["agenda_estado"] = tk.Label(painel, text="Verificando...", bg=CORES["panel"],
                                                 fg=CORES["text"], font=("Segoe UI Semibold", 13), anchor="w")
        self.widgets["agenda_estado"].pack(fill="x", pady=(10, 0))
        self.widgets["agenda_detalhe"] = tk.Label(painel, text="", bg=CORES["panel"], fg=CORES["muted"],
                                                  font=("Segoe UI", 10), anchor="w", justify="left")
        self.widgets["agenda_detalhe"].pack(fill="x", pady=(4, 0))

        linha = tk.Frame(painel, bg=CORES["panel"])
        linha.pack(fill="x", pady=(16, 0))
        tk.Label(linha, text="Rodar todo dia às", bg=CORES["panel"], fg=CORES["text"]).pack(side="left")
        self.var_horario = tk.StringVar(value=self.config_manager.get("horario", infra.HORARIO_PADRAO))
        ttk.Entry(linha, textvariable=self.var_horario, width=7).pack(side="left", padx=8)
        ttk.Button(linha, text="Ativar / atualizar horário", style="Accent.TButton",
                   command=self._ativar_agendamento).pack(side="left")
        ttk.Button(linha, text="Desativar", style="Perigo.TButton",
                   command=self._desativar_agendamento).pack(side="left", padx=8)

        info = self._painel(self.principal, "Como funciona")
        info.pack(fill="x", pady=(16, 0))
        for texto in (
            "• O PC precisa estar ligado e com a sua sessão do Windows aberta (pode estar bloqueado).",
            "• Se o PC estiver desligado no horário, a coleta roda assim que ele for ligado.",
            "• A coleta abre o túnel SSH sozinha, roda as 5 etapas, fecha o túnel e guarda o log em logs/coleta.",
            "• Se já houver uma coleta rodando (por exemplo, uma manual), a agendada não começa outra.",
            "• O serviço de coleta da EC2 continua desligado: só este PC coleta, para não gravar em dobro.",
        ):
            tk.Label(info, text=texto, bg=CORES["panel"], fg=CORES["muted"], anchor="w", justify="left",
                     wraplength=880).pack(fill="x", pady=(6, 0))
        self._mostrar_agendamento()
        self._atualizar_agendamento_async()

    def _mostrar_agendamento(self):
        estado = self.agendamento
        if estado is None:
            texto_lateral = "◷  Agendamento: verificando..."
        elif not estado.get("existe"):
            texto_lateral = "◷  Coleta diária não agendada"
        elif not estado.get("ativa"):
            texto_lateral = "◷  Agendamento desativado"
        else:
            texto_lateral = f"◷  Próxima: {estado.get('proxima') or '—'}"
        self.lbl_proxima.configure(text=texto_lateral)
        if self.pagina_atual == "Painel":
            self._preencher_proxima()

        rotulo = self.widgets.get("agenda_estado")
        if not rotulo or not rotulo.winfo_exists() or estado is None:
            return
        detalhe = self.widgets["agenda_detalhe"]
        if estado.get("erro"):
            rotulo.configure(text="Não consegui consultar o agendamento", fg=CORES["red"])
            detalhe.configure(text=estado["erro"])
        elif not estado.get("existe"):
            rotulo.configure(text="Coleta diária não agendada", fg=CORES["amber"])
            detalhe.configure(text="Escolha o horário e clique em Ativar.")
        else:
            ativa = estado.get("ativa")
            rotulo.configure(text=f"{'Ativa' if ativa else 'Desativada'}: todo dia às {estado.get('horario')}",
                             fg=CORES["green"] if ativa else CORES["amber"])
            resultado = estado.get("ultimo_resultado")
            ultima = estado.get("ultima") or "nunca"
            texto_resultado = RESULTADO_TAREFA.get(resultado, f"código {resultado}")
            detalhe.configure(text=f"Próxima execução: {estado.get('proxima') or '—'}\n"
                              f"Última execução agendada: {ultima}"
                              + (f" ({texto_resultado})" if estado.get("ultima") else ""))

    def _atualizar_agendamento_async(self):
        def trabalho():
            try:
                estado = infra.estado_agendamento()
            except Exception as erro:
                estado = {"existe": False, "erro": str(erro)}
            self.after(0, lambda: self._receber_agendamento(estado))
        threading.Thread(target=trabalho, daemon=True).start()

    def _receber_agendamento(self, estado):
        self.agendamento = estado
        self._mostrar_agendamento()

    def _ciclo_agendamento(self):
        """Reconsulta a tarefa do Windows a cada minuto (próxima execução muda)."""
        self._atualizar_agendamento_async()
        self.after(60000, self._ciclo_agendamento)

    def _ativar_agendamento(self):
        horario = self.var_horario.get().strip()
        try:
            datetime.strptime(horario, "%H:%M")
        except ValueError:
            messagebox.showerror("Horário inválido", "Use o formato HH:MM, por exemplo 14:05.")
            return
        if not messagebox.askyesno("Ativar coleta diária", f"Agendar a coleta completa para todo dia às {horario}?\n\n"
                                   "Ela grava no banco de produção (AWS)."):
            return
        try:
            infra.agendar_coleta_diaria(horario)
        except Exception as erro:
            messagebox.showerror("Não foi possível agendar", str(erro))
            infra.registrar_manager(f"[ERRO] Agendamento: {erro}")
            return
        self.config_manager["horario"] = horario
        infra.salvar_config(self.config_manager)
        infra.registrar_manager(f"[INFO] Coleta diária agendada para {horario}.")
        self.agendamento = None
        self._mostrar_agendamento()
        self._atualizar_agendamento_async()

    def _desativar_agendamento(self):
        if not (self.agendamento or {}).get("existe"):
            messagebox.showinfo("Nada a desativar", "A coleta diária não está agendada.")
            return
        if not messagebox.askyesno("Desativar", "Remover o agendamento da coleta diária?"):
            return
        try:
            infra.remover_agendamento()
        except Exception as erro:
            messagebox.showerror("Não foi possível desativar", str(erro))
            return
        infra.registrar_manager("[INFO] Agendamento da coleta diária removido.")
        self._atualizar_agendamento_async()

    # ------------------------------------------------------- infraestrutura

    def _pagina_infra(self):
        self._cabecalho("Infraestrutura", "Conexão com o banco e situação do servidor na AWS. As verificações só leem, não alteram nada.")
        cartoes = ttk.Frame(self.principal)
        cartoes.pack(fill="x")
        for i in range(4):
            cartoes.columnconfigure(i, weight=1, uniform="cartoes")
        self._cartao(cartoes, 0, "Túnel até o banco", "tunel", "purple")
        self._cartao(cartoes, 1, "API pública", "api", "blue")
        self._cartao(cartoes, 2, "Servidor (EC2)", "ec2", "green")
        self._cartao(cartoes, 3, "Disco e memória", "recursos", "amber")
        try:
            host, porta, banco = infra.destino_banco()
            aberto = infra.porta_aberta("127.0.0.1", porta)
            self._definir("tunel", "Aberto" if aberto else "Fechado",
                          f"127.0.0.1:{porta} → {banco}. A coleta abre e fecha sozinha.",
                          CORES["green"] if aberto else CORES["muted"])
        except Exception as erro:
            self._definir("tunel", "Erro", str(erro), CORES["red"])

        botoes = tk.Frame(self.principal, bg=CORES["bg"])
        botoes.pack(fill="x", pady=(16, 0))
        self.widgets["btn_banco"] = ttk.Button(botoes, text="Testar conexão com o banco", style="Accent.TButton",
                                               command=self._testar_banco)
        self.widgets["btn_banco"].pack(side="left")
        self.widgets["btn_diag"] = ttk.Button(botoes, text="Verificar servidor e API", command=self._diagnostico)
        self.widgets["btn_diag"].pack(side="left", padx=8)
        painel = self._painel(self.principal, "Resultado")
        painel.pack(fill="both", expand=True, pady=(16, 0))
        self.widgets["diag"] = self._caixa_log(painel, 12)
        self._escrever_log(self.widgets["diag"], ["Clique em um dos botões acima."], limpar=True)

    def _testar_banco(self):
        self.widgets["btn_banco"].configure(state="disabled", text="Testando...")

        def trabalho():
            try:
                ok, mensagem = infra.testar_banco()
            except Exception as erro:
                ok, mensagem = False, f"{type(erro).__name__}: {erro}"

            def fim():
                if self.widgets.get("btn_banco") and self.widgets["btn_banco"].winfo_exists():
                    self.widgets["btn_banco"].configure(state="normal", text="Testar conexão com o banco")
                    self._escrever_log(self.widgets["diag"], [f"{datetime.now():%H:%M:%S} {'[OK]' if ok else '[ERRO]'} {mensagem}"])
                infra.registrar_manager(f"[{'OK' if ok else 'ERRO'}] Teste do banco: {mensagem}")
            self.after(0, fim)
        threading.Thread(target=trabalho, daemon=True).start()

    def _diagnostico(self):
        self.widgets["btn_diag"].configure(state="disabled", text="Verificando...")
        config = dict(self.config_manager)
        threading.Thread(target=self._diagnostico_trabalho, args=(config,), daemon=True).start()

    def _diagnostico_trabalho(self, config):
        linhas, valores = [], {}
        try:
            req = urllib.request.Request(config["api_url"], headers={"User-Agent": "DESCTRL-Manager/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resposta:
                dados = json.loads(resposta.read(65536).decode("utf-8", "replace"))
            if dados.get("status") == "online":
                valores["api"] = ("Online", "HTTP 200", "green")
                linhas.append("[OK] API pública respondeu: online")
            else:
                valores["api"] = ("Resposta estranha", str(dados)[:80], "amber")
                linhas.append(f"[AVISO] API pública: {str(dados)[:200]}")
        except Exception as erro:
            valores["api"] = ("Fora do ar", type(erro).__name__, "red")
            linhas.append(f"[ERRO] API pública: {type(erro).__name__}: {erro}")

        script = r"""
echo "HOST=$(hostname)"
echo "API=$(systemctl is-active desctrl-api.service 2>/dev/null)"
echo "COLETA=$(systemctl is-active desctrl-coleta.service 2>/dev/null)/$(systemctl is-enabled desctrl-coleta.service 2>/dev/null)"
free -m | awk '/^Mem:/ {print "RAM=" $2 " " $7}'
df -BG / | awk 'NR==2 {print "DISCO=" $2 " " $4 " " $5}'
"""
        try:
            processo = subprocess.run(
                ["ssh", "-i", config["ssh_chave"], "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
                 config["ssh_host"], script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
                creationflags=infra.SEM_JANELA,
            )
            if processo.returncode:
                raise RuntimeError(processo.stderr.strip()[-300:] or f"código {processo.returncode}")
            info = dict(l.split("=", 1) for l in processo.stdout.splitlines() if "=" in l)
            api = info.get("API", "?")
            coleta = info.get("COLETA", "?")
            valores["ec2"] = ("API ativa" if api == "active" else f"API: {api}",
                              f"Coleta na EC2: {coleta} (deve ficar inactive/disabled)",
                              "green" if api == "active" else "red")
            linhas.append(f"[{'OK' if api == 'active' else 'ERRO'}] Serviço da API na EC2: {api}")
            linhas.append(f"[{'OK' if coleta.startswith('inactive') else 'AVISO'}] Serviço de coleta na EC2: {coleta}"
                          + ("" if coleta.startswith("inactive") else " — está ligado e pode gravar em dobro"))
            ram = info.get("RAM", "").split()
            disco = info.get("DISCO", "").split()
            if len(ram) == 2 and len(disco) == 3:
                valores["recursos"] = (f"{disco[1]} livres", f"Disco {disco[2]} usado · RAM livre {ram[1]} de {ram[0]} MB",
                                       "green" if int(disco[2].rstrip('%')) < 85 else "amber")
                linhas.append(f"[INFO] Disco: {disco[2]} usado, {disco[1]} livres de {disco[0]}")
                linhas.append(f"[INFO] RAM disponível: {ram[1]} MB de {ram[0]} MB")
        except Exception as erro:
            valores["ec2"] = ("Sem conexão", "SSH falhou", "red")
            linhas.append(f"[ERRO] SSH: {type(erro).__name__}: {erro}")

        def fim():
            if not self.widgets.get("btn_diag") or not self.widgets["btn_diag"].winfo_exists():
                return
            self.widgets["btn_diag"].configure(state="normal", text="Verificar servidor e API")
            for chave, (valor, detalhe, cor) in valores.items():
                self._definir(chave, valor, detalhe, CORES[cor])
            self._escrever_log(self.widgets["diag"], [f"{datetime.now():%H:%M:%S} {l}" for l in linhas])
        self.after(0, fim)

    # -------------------------------------------------------- configurações

    def _pagina_config(self):
        self._cabecalho("Configurações", "Acesso ao servidor. Fica salvo em backend/desctrl_manager/logs/config.json (fora do Git).")
        painel = self._painel(self.principal, "Servidor")
        painel.pack(fill="x")
        self.vars_config = {}
        for chave, rotulo in (("ssh_host", "Usuário e host SSH"), ("ssh_chave", "Chave SSH (.pem)"),
                              ("api_url", "Endereço de saúde da API")):
            linha = tk.Frame(painel, bg=CORES["panel"])
            linha.pack(fill="x", pady=(10, 0))
            tk.Label(linha, text=rotulo, bg=CORES["panel"], fg=CORES["muted"], width=24, anchor="w").pack(side="left")
            var = tk.StringVar(value=self.config_manager.get(chave, ""))
            ttk.Entry(linha, textvariable=var).pack(side="left", fill="x", expand=True)
            self.vars_config[chave] = var
        ttk.Button(painel, text="Salvar", style="Accent.TButton", command=self._salvar_config).pack(anchor="w", pady=(14, 0))

        sobre = self._painel(self.principal, "Ambiente local")
        sobre.pack(fill="x", pady=(16, 0))
        try:
            python = infra.python_do_projeto()
        except Exception as erro:
            python = f"não encontrado ({erro})"
        try:
            host, porta, banco = infra.destino_banco()
            destino = f"{banco} em {host}:{porta} (túnel até a EC2)"
        except Exception as erro:
            destino = str(erro)
        for rotulo, valor in (("Projeto", infra.RAIZ), ("Python da coleta", python), ("Banco", destino),
                              ("Logs das coletas", infra.PASTA_LOGS_COLETA), ("Histórico", infra.ARQUIVO_HISTORICO)):
            tk.Label(sobre, text=f"{rotulo}: {valor}", bg=CORES["panel"], fg=CORES["text"], anchor="w",
                     justify="left", wraplength=880).pack(fill="x", pady=(6, 0))
        tk.Label(sobre, text="A senha do banco fica só no .env; o Manager nunca a mostra nem grava.",
                 bg=CORES["panel"], fg=CORES["muted"], anchor="w").pack(fill="x", pady=(10, 0))

    def _salvar_config(self):
        for chave, var in self.vars_config.items():
            self.config_manager[chave] = var.get().strip()
        if not os.path.isfile(self.config_manager["ssh_chave"]):
            if not messagebox.askyesno("Chave não encontrada", "O arquivo da chave SSH não existe. Salvar mesmo assim?"):
                return
        infra.salvar_config(self.config_manager)
        infra.registrar_manager("[INFO] Configurações salvas.")
        messagebox.showinfo("Salvo", "Configurações salvas.")

    # --------------------------------------------------------------- saída

    def _fechar(self):
        if infra.execucao_atual():
            messagebox.showinfo("Coleta continua", "A coleta em andamento continua rodando em segundo plano. "
                                "Abra o Manager de novo para acompanhar.")
        self.destroy()


def main():
    infra.registrar_manager("[INFO] Manager aberto.")
    Manager().mainloop()


if __name__ == "__main__":
    main()
