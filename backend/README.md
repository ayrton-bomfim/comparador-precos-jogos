# Backend — DESCTRL

API REST (FastAPI + SQLAlchemy + PostgreSQL) e rotinas de coleta de preços da Steam e da Epic Games Store.

A instalação e a execução estão descritas no [README principal](../README.md). Todos os comandos abaixo são executados **a partir da raiz do projeto**, com o `venv` ativo.

## Estrutura

| Pasta / arquivo | Papel |
| --- | --- |
| `app.py` | Cria a aplicação FastAPI, configura CORS, GZip e rate limiting e registra as rotas. |
| `config.py` | Lê o `.env` da raiz e centraliza as configurações. |
| `banco_dados.py` | Engine e sessões do SQLAlchemy. |
| `modelos.py` | Modelos ORM das tabelas. |
| `lista_jogos.py` | Lista inicial de jogos e mapeamento Steam → slug da Epic, usada pelos coletores sob demanda. |
| `rotas/` | Endpoints REST: jogos, comparador, autenticação, segurança da conta, favoritos, conquistas, alertas, notificações, comunidade e curadoria. |
| `seguranca/` | Hash de senha, JWT, dependências de usuário/admin e rate limiting. |
| `servicos/` | Integração EGDATA, envio de e-mails (Resend), avaliação de alertas de preço e expiração de recomendações. |
| `coletores/` | Coleta diária (`agendador.py`) e coletores usados pela API. |
| `ferramentas/` | Rotinas manuais e pontuais (tabela abaixo). |
| `templates/` | Layout HTML do e-mail de alerta de preço. |
| `desctrl_manager/` | Painel desktop de monitoramento do servidor (versão beta). |

## Coleta diária

```bash
python -m backend.coletores.agendador --agora   # executa uma vez
python -m backend.coletores.agendador           # residente, no horário de COLETA_HORARIO
```

Etapas: (1) histórico da Steam via `GetItems` em lote → (2) histórico da Epic via EGDATA → (3) avaliação dos alertas de preço e envio de e-mails → (4) expiração das recomendações da comunidade cujas promoções terminaram.

Também é possível rodar cada loja isoladamente:

```bash
python -m backend.coletores.coletar_historico
python -m backend.coletores.coletar_historico_epic
```

## Ferramentas (`ferramentas/`)

Rotinas que não fazem parte do fluxo diário. Foram usadas na montagem inicial do banco ou servem para manutenção. Algumas gravam no banco assim que são executadas; quando houver modo de teste, use-o antes:

- só simulam, a menos que se passe a flag: `importar_historico_itad` (`--executar`) e `importar_estudios_idj` (`--apply`);
- aceitam teste sem gravar: `cadastrar_catalogo_epic` (`--dry-run`) e `coletar_metadados_steam` (`--simular`);
- gravam direto: `sincronizar_catalogo_steam`, `importar_historico_egdata` e `importar_historico_steamdb`.

| Comando | O que faz |
| --- | --- |
| `python -m backend.ferramentas.criar_tabelas` | Cria as tabelas que ainda não existem (instalação nova). Não altera dados. |
| `python -m backend.ferramentas.atualizar_banco_dev` | Recria o banco local (`.env.dev`) como cópia da produção, sem dados pessoais. Só lê a produção. |
| `python -m backend.ferramentas.criar_admin` | Cria ou atualiza o administrador inicial a partir de `ADMIN_*` no `.env`. |
| `python -m backend.ferramentas.sincronizar_catalogo_steam` | Baixa o catálogo de jogos da Steam (`IStoreService/GetAppList`) para `steam_catalogo` e `jogos`. |
| `python -m backend.ferramentas.cadastrar_catalogo_epic` | Descobre, deduplica e cadastra o catálogo de jogos base da Epic (via EGDATA). |
| `python -m backend.ferramentas.coletar_metadados_steam` | Enriquece metadados (gêneros, desenvolvedora, requisitos...) dos jogos disponíveis na Steam. |
| `python -m backend.ferramentas.importar_historico_itad` | Backfill do histórico antigo de preços da Steam/BR a partir da IsThereAnyDeal. |
| `python -m backend.ferramentas.importar_historico_egdata` | Importa o histórico de preços da Epic a partir da EGDATA. |
| `python -m backend.ferramentas.importar_historico_steamdb` | Importa um backup JSON de histórico capturado do SteamDB. |
| `python -m backend.ferramentas.importar_estudios_idj` | Coleta a lista pública de estúdios brasileiros da Indústria de Jogos (vitrine "brasileiros"). |

Arquivos auxiliares gerados (checkpoints, CSVs de diagnóstico) ficam em `logs/` ou na pasta onde o comando foi executado e não são versionados.

## Autenticação

- Senhas armazenadas apenas como hash; login por usuário/senha ou Google.
- JWT Bearer com expiração configurável (`ACCESS_TOKEN_EXPIRE_MINUTES`) e invalidação após troca de credenciais.
- Rotas administrativas protegidas por papel (`admin`).
- Rate limiting com SlowAPI.
