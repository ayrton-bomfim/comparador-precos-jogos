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


Steam / Epic Games Store
          │
          ▼
Coletores e rotinas de atualização
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
│   ├── coletores/
│   ├── rotas/
│   ├── seguranca/
│   ├── scripts/
│   │   ├── cadastro/
│   │   ├── historico/
│   │   ├── importacao/
│   │   └── usuarios/
│   ├── servicos/
│   ├── templates/
│   ├── testes/
│   ├── tools/
│   ├── app.py
│   ├── banco_dados.py
│   ├── config.py
│   ├── modelos.py
│   └── requirements.txt
├── frontend/
│   ├── public/
│   └── src/
│       ├── componentes/
│       ├── contextos/
│       ├── paginas/
│       └── servicos/
├── Conceitos de Mascote/
├── executar_coleta_agora.bat
├── iniciar_projeto.bat
├── parar_projeto.bat
├── .gitignore
└── README.md
```

A estrutura acima resume as principais pastas. Os arquivos podem mudar conforme a evolução do projeto.

## ⚙️ Pré-requisitos

- Python compatível com as dependências do backend.
- Node.js e npm.
- Uma instância do PostgreSQL.
- Variáveis de ambiente para backend e frontend.
- Credenciais para integrações externas que forem utilizadas, como Google Sign-In e envio de e-mails.

## 🚀 Como executar localmente

### 1. Configurar o backend

Na raiz do repositório, crie e ative um ambiente virtual e instale as dependências:

```bat
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Configure as variáveis de ambiente usando `backend/.env.example` como referência. Preencha os dados de conexão com o PostgreSQL e as credenciais necessárias para as integrações desejadas. Não copie credenciais reais para o repositório.

Inicie a API a partir da raiz do projeto:

```bat
python -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8001
```

Com a configuração local usada durante o desenvolvimento, a API fica disponível em `http://127.0.0.1:8001`. A documentação interativa pode ser acessada em `http://127.0.0.1:8001/docs` quando os recursos externos necessários estiverem acessíveis. O esquema OpenAPI fica em `http://127.0.0.1:8001/openapi.json`.

Se o projeto for executado com outro host ou porta, ajuste os endereços de acordo.

### 2. Configurar o frontend

Em outro terminal:

```bat
cd frontend
npm install
npm run dev
```

O Vite exibirá no terminal o endereço local da interface. Configure `frontend/.env.example` conforme as instruções do arquivo e a URL em que a API estiver sendo executada.

### 3. Inicialização por script

O repositório também contém arquivos `.bat` para facilitar a inicialização, a parada do ambiente e a execução da coleta. Confira a configuração local desses arquivos antes de utilizá-los, especialmente em outra máquina.

## 🔄 Coleta de dados

A aplicação possui rotinas separadas para as lojas:

- **Steam:** coleta de informações de catálogo e preços usando os mecanismos implementados no projeto, incluindo consultas em lote e rotinas incrementais.
- **Epic Games Store:** coleta de informações de catálogo e preços, com integração à EGDATA em rotinas relacionadas a preços e histórico.

Existem scripts para cadastro de catálogo, atualização de metadados, coleta de preços e processamento de histórico. Alguns scripts podem ter pré-requisitos específicos; não os execute indiscriminadamente contra um banco de produção.

A coleta manual pode ser iniciada por `executar_coleta_agora.bat`, de acordo com a configuração local. A execução automática pode ser organizada pelo Agendador de Tarefas do Windows. Confira os parâmetros e o comportamento do script antes de programar execuções recorrentes.

Os dados coletados dependem das fontes externas, da disponibilidade delas e dos limites aplicados por cada serviço. O histórico disponível pode variar de jogo para jogo.

## 🔐 Configuração e segurança

- Use `backend/.env.example` e `frontend/.env.example` como referência.
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
