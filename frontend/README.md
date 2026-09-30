# Comparador de Preços de Jogos Digitais

Frontend da aplicação web desenvolvida para o Trabalho de Curso II em Ciência da Computação.

O projeto apresenta comparação de preços entre Steam e Epic Games Store, histórico de preços e análise de comportamento promocional.

## Tecnologias

- React
- Vite
- React Router
- JavaScript
- CSS

## Estrutura

```text
src/
├── componentes/
├── paginas/
├── servicos/
├── App.jsx
├── App.css
├── index.css
└── main.jsx
```

## Configuração

Crie um arquivo `.env` a partir de `.env.example` e informe a URL da API:

```env
VITE_API_URL=http://localhost:8000
```

## Execução

```bash
npm install
npm run dev
```

Para verificar o código:

```bash
npm run lint
```

Para gerar a versão de produção:

```bash
npm run build
```

## Rotas

- `/` — página inicial
- `/jogos` — catálogo de jogos
- `/jogos/:id` — detalhes e histórico
- `/ofertas` — análise de promoções
- `/sobre` — informações do projeto
- `/arquitetura` — visões da arquitetura da solução
