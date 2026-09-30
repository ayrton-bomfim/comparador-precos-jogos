# 🎮 Comparador de Preços de Jogos Digitais

Aplicação web desenvolvida como Trabalho de Curso II (TC II) para comparação de preços de jogos digitais nas plataformas **Steam** e **Epic Games Store**.

O projeto coleta preços, descontos e informações promocionais, mantém histórico de alterações no PostgreSQL e disponibiliza uma interface web para comparação, consulta de histórico e análise de comportamento promocional.

## 🚧 Status do Projeto

Em desenvolvimento.

A versão atual já possui:

- Backend REST com FastAPI.
- Frontend em React + Vite.
- Persistência em PostgreSQL.
- Comparação de preços entre Steam e Epic Games Store.
- Histórico de preços baseado em mudanças relevantes.
- Identificação de promoções e período de término quando fornecido pela fonte.
- Coleta automática diária.
- Página de detalhes com histórico de preços.
- Página de ofertas com análise heurística de tendências promocionais.
- Página de arquitetura da solução.
- Rotinas de testes e ferramentas de diagnóstico.

## ✨ Principais Funcionalidades

### Comparação de preços

A aplicação apresenta os preços atuais dos jogos nas duas plataformas e permite visualizar:

- Preço atual.
- Preço original.
- Percentual de desconto.
- Menor preço disponível.
- Link para a loja.
- Informações básicas do jogo.

### Histórico de preços

O sistema registra alterações relevantes de preço e promoção, evitando criar registros repetidos apenas pela passagem do tempo.

O histórico pode armazenar, quando disponível:

- Preço atual.
- Preço original.
- Desconto.
- Identificador da promoção.
- Nome da promoção.
- Tipo da promoção.
- Início da promoção.
- Fim da promoção.
- Data da coleta.

### Análise de promoções

A página de ofertas utiliza dados históricos para apresentar uma análise heurística do comportamento promocional dos jogos, incluindo tendências, faixas de desconto, faixas de preço e estimativas de próximas janelas promocionais.

A previsão é baseada no histórico coletado e não representa garantia de comportamento futuro.

### Coleta automatizada

A coleta diária é organizada em duas rotinas independentes:

- **Steam:** consulta em lote utilizando `IStoreBrowseService/GetItems`, reduzindo a necessidade de acesso individual às páginas dos jogos.
- **Epic Games Store:** consulta de preço atual e histórico por meio da EGDATA.

O projeto também possui um agendador e um arquivo `.bat` para execução manual ou automática pelo Agendador de Tarefas do Windows.

## 🏗️ Arquitetura

```text
┌─────────────────────┐
│ Steam / Epic        │
│ Fontes de dados     │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ Coleta / Ingestão   │
│ Steam GetItems      │
│ Epic / EGDATA       │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ PostgreSQL          │
│ Jogos               │
│ Ofertas             │
│ Histórico           │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ FastAPI             │
│ API da aplicação    │
└──────────┬──────────┘
           │
           ↓
┌─────────────────────┐
│ React + Vite        │
│ Interface web       │
└─────────────────────┘
```

O projeto mantém componentes legados baseados em Playwright, mas a coleta diária atual foi estruturada prioritariamente em consultas HTTP/JSON para reduzir dependência de navegação de páginas.

## 🛠️ Tecnologias

### Backend

- Python 3.10+
- FastAPI
- SQLAlchemy
- PostgreSQL
- Requests
- Playwright
- Schedule
- python-dotenv
- Uvicorn

### Frontend

- React
- Vite
- React Router
- JavaScript
- CSS

## 📁 Estrutura do Projeto

```text
comparador-precos-jogos/
│
├── backend/
│   ├── coletores/
│   ├── rotas/
│   ├── scripts/
│   │   ├── cadastro/
│   │   ├── historico/
│   │   └── importacao/
│   ├── servicos/
│   ├── tests/
│   ├── tools/
│   ├── app.py
│   ├── banco_dados.py
│   ├── config.py
│   ├── modelos.py
│   └── requirements.txt
│
├── frontend/
│   ├── public/
│   └── src/
│       ├── componentes/
│       ├── paginas/
│       └── servicos/
│
├── executar_coleta_agora.bat
├── iniciar_projeto.bat
├── parar_projeto.bat
├── .gitignore
└── README.md
```

## 🚀 Como Executar

### Backend

No Windows:

```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

### Frontend

Em outro terminal:

```bat
cd frontend
npm install
npm run dev
```

Por padrão, o frontend é executado pelo Vite e o backend pela API FastAPI.

## ⚙️ Configuração

Utilize os arquivos `.env.example` como referência:

```text
backend/.env.example
frontend/.env.example
```

Não versione arquivos `.env` reais, chaves de API ou outras credenciais.

## 🔄 Coleta Manual

A coleta histórica completa pode ser iniciada pelo arquivo:

```text
executar_coleta_agora.bat
```

O processo executa:

```text
Steam → histórico via GetItems
Epic  → histórico via EGDATA
```

Os logs da execução são armazenados localmente e não fazem parte do repositório.

## ⏰ Coleta Automática

A mesma rotina pode ser executada diariamente pelo **Agendador de Tarefas do Windows**.

O agendamento utiliza o mesmo arquivo `.bat` da execução manual, evitando manter implementações diferentes para coleta manual e automática.

## 🧪 Testes e Ferramentas

O projeto possui testes manuais e ferramentas de diagnóstico organizados em:

```text
backend/tests/manual/
backend/tools/
```

Também foram utilizados scripts exploratórios locais durante a implementação. Esses arquivos não fazem parte do repositório principal e são mantidos no `.gitignore`.

## 🔮 Próximos Passos

Entre os próximos aprimoramentos planejados estão:

- Ampliar o catálogo de jogos monitorados.
- Migrar o cadastro de catálogo para fontes baseadas em API/JSON.
- Melhorar a identificação e relacionamento entre jogos, edições e DLCs.
- Expandir os dados coletados de cada produto.
- Aprimorar a análise histórica e as estimativas de comportamento promocional.
- Evoluir a estrutura do banco para suportar melhor versões, edições e conteúdos adicionais.

## 👨‍💻 Autor

**Ayrton Bomfim**

Projeto desenvolvido para o curso de Ciência da Computação — UNIP.
