# DESCTRL Manager

Painel para rodar e acompanhar a coleta diária de preços neste computador.
A coleta grava no PostgreSQL da AWS por um túnel SSH que ela mesma abre e fecha.

- Abrir: `dist\DESCTRL-Manager\DESCTRL-Manager.exe` (ou `py app.py` nesta pasta)
- Gerar o EXE: `build.bat`

## Como as peças se encaixam

| Peça | O que faz |
|---|---|
| `executor.py` | Roda a coleta: trava contra execuções simultâneas, abre o túnel, executa as etapas do agendador e grava o log em `logs/coleta/`. Usado pelo Manager, pela tarefa agendada e pelo `executar_coleta_agora.bat`. |
| `infra.py` | Funções comuns (só biblioteca padrão): túnel, trava, histórico, Python do projeto e tarefa do Windows. |
| `app.py` | A interface. Só dispara e acompanha; a coleta roda em processo próprio e continua se o Manager for fechado. |

A coleta usa o Python do `venv` do projeto, não o do EXE.

## Telas

- **Painel**: última coleta, cobertura da Steam e da Epic, próxima execução e a coleta em andamento ao vivo.
- **Executar**: coleta completa ou só algumas etapas (Steam, Epic, alertas, limpeza, preços atuais).
- **Histórico**: todas as coletas de produção, com status, duração e cobertura. Clique duplo abre o log.
- **Agendamento**: cria, muda ou remove a tarefa "DESCTRL - Coleta diaria" do Agendador de Tarefas do Windows.
- **Infraestrutura**: teste de conexão com o banco e diagnóstico da EC2 e da API (somente leitura).
- **Configurações**: host e chave SSH, salvos em `logs/config.json` (fora do Git).

## Linha de comando

```
venv\Scripts\python.exe -m backend.desctrl_manager.executor                    # coleta completa
venv\Scripts\python.exe -m backend.desctrl_manager.executor --etapas epic,precos_atuais
venv\Scripts\python.exe -m backend.desctrl_manager.executor --testar-banco
venv\Scripts\python.exe -m backend.desctrl_manager.executor --ambiente dev     # banco local
```

Códigos de saída: 0 concluída (com ou sem avisos), 1 falha ou parcial, 2 já havia outra coleta rodando.

## Requisitos da tarefa agendada

- PC ligado e com a sessão do Windows aberta (pode estar bloqueado).
- Se o PC estiver desligado no horário, a coleta roda assim que ele ligar.
- O serviço `desctrl-coleta` da EC2 deve continuar desligado, para não coletar em dobro.
