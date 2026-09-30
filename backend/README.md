# Backend — Comparador de Preços de Jogos

Backend da aplicação web de comparação de preços entre Steam e Epic Games Store.

## Stack

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Requests
- Playwright
- Uvicorn

## Estrutura

```text
backend/
├── app.py
├── banco_dados.py
├── config.py
├── lista_jogos.py
├── modelos.py
├── coletores/
│   ├── coletor_base.py
│   ├── steam_coletor.py
│   ├── epic_coletor.py
│   └── agendador.py
├── rotas/
│   ├── jogos.py
│   └── comparador.py
├── scripts/
│   ├── cadastro/
│   ├── historico/
│   └── importacao/
├── tests/manual/
└── tools/
```

## Configuração

1. Crie um ambiente virtual.
2. Instale as dependências:

```bash
pip install -r requirements.txt
```

3. Instale os navegadores do Playwright:

```bash
playwright install chromium
```

4. Copie `.env.example` para `.env` e ajuste a conexão do PostgreSQL.

## Executar a API

A partir da raiz do projeto, no diretório que contém a pasta `backend`:

```bash
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
```

A documentação fica disponível em:

- `http://localhost:8000/docs`
- `http://localhost:8000/redoc`

## Scripts principais

Cadastro inicial:

```bash
python -m backend.scripts.cadastro.salvar_jogos_steam
python -m backend.scripts.cadastro.salvar_jogos_epic
```

Atualização do histórico:

```bash
python -m backend.scripts.historico.coletar_historico
python -m backend.scripts.historico.coletar_historico_epic
```

Os scripts de importação em `scripts/importacao/` são auxiliares para cargas históricas específicas e não fazem parte do fluxo normal da API.

## Testes manuais

Os arquivos em `tests/manual/` são testes e diagnósticos manuais utilizados durante o desenvolvimento dos coletores e do banco. Eles não são executados automaticamente pela API.

## Ferramentas auxiliares

`tools/` reúne utilitários de diagnóstico e manutenção, como verificação de slugs da Epic e diagnóstico da tela de verificação de idade.

## Variáveis de ambiente

Nunca versionar `.env`. Use `.env.example` como referência para a configuração local.
