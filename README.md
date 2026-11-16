# 🎮 DESCTRL | Comparador de Preços de Jogos Digitais

O **DESCTRL** é uma aplicação web desenvolvida como Trabalho de Curso II (TC II) do curso de Ciência da Computação da Universidade Paulista (UNIP). Seu objetivo é ajudar jogadores a comparar preços de jogos digitais, acompanhar mudanças de preço e identificar oportunidades promocionais na **Steam** e na **Epic Games Store**.

O sistema reúne informações de catálogo, preços atuais e histórico promocional em uma interface com comparação, acompanhamento de jogos e recursos personalizados para usuários cadastrados.

> **Status:** versão beta em desenvolvimento. O código-fonte está disponível nesse repositório do GitHub.

## ✨ Funcionalidades

### Comparação e acompanhamento de preços

- Comparação de preços e descontos entre Steam e Epic Games Store.
- Exibição de preço atual, preço original, desconto e link para a loja, conforme os dados disponíveis.
- Consulta ao histórico de preços e promoções.
- Página de ofertas com análise heurística de tendências, faixas de preço e descontos.
- Estimativas de possíveis janelas promocionais baseadas no histórico disponível. Essas estimativas não garantem promoções futuras.
- Rotinas específicas para coleta de dados atuais e históricos de cada loja.

### Conta e segurança

- Cadastro e autenticação com usuário e senha.
- Integração de login com Google.
- Fluxos de confirmação e alteração de e-mail.
- Recursos de gerenciamento de senha e segurança da conta.
- Controle de sessões, incluindo invalidação de tokens após alterações relevantes de credenciais.
- Limitação de requisições em rotas da API por meio de *rate limiting*.

A disponibilidade e o comportamento de cada fluxo dependem da configuração do ambiente e dos serviços externos utilizados.

### Recursos personalizados

- Lista de jogos favoritos.
- Perfil do usuário e preferências de interface, incluindo tema claro ou escuro.
- Sistema de conquistas, experiência e níveis.
- Notificações relacionadas a conquistas.
- Alertas de preços por e-mail, conforme as configurações da conta e do serviço de envio.

### Curadoria e participação da comunidade

- Ferramentas administrativas para curadoria do catálogo.
- Recebimento de relatos sobre jogos e informações do catálogo.
- Encaminhamento de relatos para análise, evitando que um relato público provoque automaticamente a exclusão de um jogo.
- Rotas administrativas destinadas a usuários autorizados.

## 🏗️ Arquitetura

```text
Steam / Epic Games Store / EGDATA
          │
          ▼
Coletores + agendador diário
          │
          ▼
PostgreSQL
(catálogo, preços e histórico)
          │
          ▼
API REST com FastAPI
          │
          ▼
Interface React + Vite
```

O backend concentra as regras de negócio, autenticação, acesso aos dados, rotinas de coleta e serviços auxiliares. O frontend disponibiliza as páginas e os componentes com os quais o usuário interage.

## 🛠️ Tecnologias

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Requests
- Playwright, em rotinas que dependem de navegação automatizada
- Schedule
- python-dotenv
- Uvicorn
- SlowAPI para limitação de requisições

### Frontend

- React
- Vite
- React Router
- JavaScript
- CSS

### Integrações externas

- Steam
- Epic Games Store
- EGDATA, para dados relacionados à Epic Games Store
- Google Sign-In
- Resend, para envio de e-mails

As integrações dependem da disponibilidade, das credenciais e dos limites definidos por cada serviço externo.

## 📁 Estrutura do projeto

```text
comparador-precos-jogos/
├── backend/
│   ├── app.py                 # cria a API FastAPI e registra as rotas
│   ├── config.py              # lê o .env da raiz
│   ├── banco_dados.py         # conexão SQLAlchemy com o PostgreSQL
│   ├── modelos.py             # tabelas (ORM)
│   ├── rotas/                 # endpoints REST (jogos, comparador, auth, favoritos...)
│   ├── seguranca/             # JWT, permissões e rate limiting
│   ├── servicos/              # e-mail, EGDATA, alertas de preço, rotinas auxiliares
│   ├── coletores/             # coleta de preços
│   │   ├── agendador.py           # orquestra a coleta diária (Steam → Epic → alertas)
│   │   ├── coletar_historico.py   # histórico diário da Steam (GetItems em lote)
│   │   ├── coletar_historico_epic.py  # histórico diário da Epic (EGDATA)
│   │   ├── coletar_dados_steam.py # AppDetails + disponibilidade no Brasil
│   │   ├── steam_coletor.py / epic_coletor.py  # consulta sob demanda usada pela API
│   │   └── epic_catalogo.py       # descoberta do catálogo da Epic
│   ├── ferramentas/           # rotinas manuais e pontuais (ver backend/README.md)
│   ├── templates/             # layout HTML dos e-mails
│   ├── desctrl_manager/       # painel desktop de monitoramento (beta)
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── paginas/           # uma página por rota
│       ├── componentes/       # cabeçalho, rodapé, cards, carrossel...
│       ├── contextos/         # autenticação e tema
│       └── servicos/          # URL da API e chamadas comuns
├── logs/                      # logs da coleta (não versionado)
├── .env.example
├── iniciar_projeto.bat
├── parar_projeto.bat
└── executar_coleta_agora.bat
```

## ⚙️ Pré-requisitos

- Python 3.10 ou superior.
- Node.js e npm.
- PostgreSQL.
- Credenciais das integrações que forem usadas (Steam, Google Sign-In, Resend).

## 🚀 Como executar localmente

### 1. Backend

Na raiz do repositório:

```bat
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
playwright install chromium
```

Copie `.env.example` para `.env` **na raiz do projeto** e preencha ao menos `DATABASE_URL` e `JWT_SECRET_KEY`.

Crie as tabelas (só cria o que não existe; não altera dados) e o administrador inicial:

```bat
python -m backend.ferramentas.criar_tabelas
python -m backend.ferramentas.criar_admin
```

Inicie a API:

```bat
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

A API fica em `http://127.0.0.1:8000`, com documentação interativa em `http://127.0.0.1:8000/docs`.

### 2. Frontend

Em outro terminal:

```bat
cd frontend
copy .env.example .env
npm install
npm run dev
```

A interface abre em `http://localhost:5173`.

### 3. Inicialização por script

`iniciar_projeto.bat` faz os passos acima automaticamente (detecta o `venv`, instala as dependências do frontend se faltarem, sobe API e Vite e abre o navegador). `parar_projeto.bat` encerra os dois processos.

### 4. Banco local x produção

O projeto trabalha com dois arquivos de configuração na raiz:

| Arquivo | Banco | Usado por |
| --- | --- | --- |
| `.env` | Produção (PostgreSQL na AWS, via túnel SSH na porta 5433) | Coleta diária (`executar_coleta_agora.bat`) |
| `.env.dev` | Cópia local de desenvolvimento (PostgreSQL local, porta 5432) | `iniciar_projeto.bat`, testes e demonstrações |

O `.env.dev` é ativado pela variável `DESCTRL_ENV=dev`; o que não estiver nele é lido do `.env`. O `iniciar_projeto.bat` usa o banco local sempre que o `.env.dev` existir; para abrir o site sobre a produção, use `iniciar_projeto.bat producao`.

Para atualizar a cópia local com os dados atuais da produção (com o túnel aberto):

```bat
python -m backend.ferramentas.atualizar_banco_dev
set DESCTRL_ENV=dev
python -m backend.ferramentas.criar_admin
```

A cópia traz catálogo, preços, histórico e auditorias, mas **não** traz dados pessoais (usuários, favoritos, alertas, notificações, conquistas).

## 🔄 Coleta de dados

A coleta diária é orquestrada por `backend/coletores/agendador.py`:

1. **Steam:** consulta os preços em lote pela API `IStoreBrowseService/GetItems` e grava no histórico apenas quando o preço muda. Casos sem conclusão passam pelo AppDetails para classificar a disponibilidade no Brasil.
2. **Epic Games Store:** consulta as ofertas pela EGDATA e grava as mudanças de preço e promoções.
3. **Pós-coleta:** avalia os alertas de preço dos usuários (envio por e-mail) e expira recomendações antigas da comunidade.

Formas de executar:

```bat
:: uma coleta imediata (também disponível em executar_coleta_agora.bat)
python -m backend.coletores.agendador --agora

:: processo residente que roda todo dia no horário de COLETA_HORARIO
python -m backend.coletores.agendador
```

Cada execução é registrada em `logs/execucoes_coleta.jsonl`, e o diagnóstico de disponibilidade da Steam em `logs/coleta_disponibilidade_br_diaria.csv`.

As cargas iniciais de catálogo e de histórico antigo (ITAD, EGDATA, SteamDB) foram feitas com as rotinas de `backend/ferramentas/`, descritas em `backend/README.md`.

## 🔐 Configuração e segurança

- Use `.env.example` (raiz) e `frontend/.env.example` como referência.
- **Nunca publique arquivos `.env` reais, senhas, tokens, chaves de API, certificados ou outras credenciais.**
- Não inclua cópias locais do banco de dados, dumps, backups ou arquivos com dados privados no Git.
- Use credenciais próprias para cada ambiente e mantenha as permissões administrativas restritas.
- Antes de disponibilizar a aplicação na internet, configure HTTPS, CORS, origens permitidas, segredos de produção, banco de dados, envio de e-mails e políticas de backup.
- Recursos que dependem de serviços externos só funcionarão quando as respectivas credenciais e configurações estiverem corretas.

## 🧪 Validação e desenvolvimento

O projeto foi desenvolvido de forma incremental, com verificações de sintaxe do backend e validações de lint e build do frontend durante a implementação. Isso não equivale a uma certificação completa nem garante que todos os fluxos tenham sido testados em produção.

Para validar o frontend:

```bat
cd frontend
npm run lint
npm run build
```

Para conferir a inicialização do backend, execute a API e acesse o endpoint de saúde configurado no projeto. Os testes de integração devem ser realizados com um banco de desenvolvimento e credenciais de teste.

## 🗺️ Próximos passos

- Preparar e validar a implantação da aplicação em um ambiente hospedado.
- Revisar a configuração de produção e o gerenciamento de segredos.
- Ampliar e qualificar os metadados e o catálogo de jogos.
- Melhorar o relacionamento entre jogos, edições, bundles e DLCs.
- Aprimorar a cobertura de testes automatizados e de integração.
- Monitorar a confiabilidade das coletas e a qualidade dos dados históricos.
- Evoluir a análise promocional com base nos dados efetivamente disponíveis.

## 👨‍💻 Autor

**Ayrton Bomfim**

Projeto desenvolvido para o curso de Ciência da Computação da Universidade Paulista (UNIP).
