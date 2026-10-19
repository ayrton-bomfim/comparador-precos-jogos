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

## Autenticação e administrador

A Etapa 1 adiciona a base de autenticação da aplicação:

- usuário com papel (`user` ou `admin`);
- senha armazenada somente como hash;
- login com JWT Bearer;
- endpoint `/api/auth/me`;
- dependência de autorização para endpoints exclusivos de administrador;
- script de criação/atualização do primeiro administrador.

### 1. Instalar as novas dependências

```bash
pip install -r requirements.txt
```

### 2. Criar a tabela de usuários

A tabela `usuarios` deve existir no PostgreSQL do projeto com as colunas `id`, `username`, `email`, `senha_hash`, `role`, `ativo` e `criado_em`.

### 3. Configurar o `.env`

Defina uma `JWT_SECRET_KEY` forte e as credenciais iniciais do administrador.
Não versione o arquivo `.env`.

### 4. Criar o administrador

```bash
python -m backend.scripts.usuarios.criar_admin
```

### 5. Testar a autenticação

```bash
python backend/tests/testar_autenticacao_etapa1.py
```

O teste valida hash de senha, verificação, geração de JWT e a estrutura das rotas sem alterar o banco.
