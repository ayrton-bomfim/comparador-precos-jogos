# Frontend — DESCTRL

Interface web em React + Vite + React Router.

## Configuração

```bash
cp .env.example .env    # informe VITE_API_URL e, se usar login Google, VITE_GOOGLE_CLIENT_ID
npm install
npm run dev             # http://localhost:5173
```

## Validação

```bash
npm run lint
npm run build
```

## Estrutura

```text
src/
├── paginas/       # uma página por rota (Início, Jogos, Detalhes, Ofertas, Perfil, Favoritos, Curadoria...)
├── componentes/   # cabeçalho, rodapé, card de jogo, carrossel, notificações
├── contextos/     # AuthContext (sessão/JWT) e TemaContext (claro/escuro)
├── servicos/      # URL base da API e chamadas reutilizadas
├── App.jsx        # rotas
└── main.jsx
```
