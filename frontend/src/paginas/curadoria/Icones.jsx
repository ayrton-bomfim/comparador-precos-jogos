// Ícones da Curadoria: mesmo traço (1.8), mesmo tamanho (1em) e cor herdada do texto.
// Substituem as setas em texto (↗ ↪ ← ‹ ›) que destoavam dos botões.

function Svg({ children, titulo }) {
  return (
    <svg
      className="cur-icone"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={titulo ? undefined : 'true'}
      role={titulo ? 'img' : undefined}
    >
      {titulo && <title>{titulo}</title>}
      {children}
    </svg>
  )
}

export function IconeExterno() {
  return <Svg><path d="M14 4h6v6" /><path d="M20 4l-9 9" /><path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></Svg>
}

export function IconeRelacionados({ titulo }) {
  return <Svg titulo={titulo}><circle cx="6" cy="6" r="2.2" /><circle cx="18" cy="6" r="2.2" /><circle cx="12" cy="18" r="2.2" /><path d="M7.5 7.7L11 16" /><path d="M16.5 7.7L13 16" /></Svg>
}

export function IconeVoltar() {
  return <Svg><path d="M15 6l-6 6 6 6" /></Svg>
}

export function IconeAnterior() {
  return <Svg><path d="M15 6l-6 6 6 6" /></Svg>
}

export function IconeProximo() {
  return <Svg><path d="M9 6l6 6-6 6" /></Svg>
}

export function IconeSubir() {
  return <Svg><path d="M6 15l6-6 6 6" /></Svg>
}

export function IconeDescer() {
  return <Svg><path d="M6 9l6 6 6-6" /></Svg>
}

export function IconeMais() {
  return <Svg><path d="M12 5v14" /><path d="M5 12h14" /></Svg>
}

export function IconeCheck() {
  return <Svg><path d="M5 12.5l4.5 4.5L19 7" /></Svg>
}

export function IconeFechar() {
  return <Svg><path d="M6 6l12 12" /><path d="M18 6L6 18" /></Svg>
}

export function IconeLixeira() {
  return <Svg><path d="M4 7h16" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M6 7l1 12a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-12" /><path d="M9 7V4h6v3" /></Svg>
}

export function IconeAjuda() {
  return <Svg><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 0 1 4.9.7c0 1.7-2.4 2.2-2.4 3.8" /><path d="M12 17h.01" /></Svg>
}

export function IconeOlho({ riscado = false }) {
  return (
    <Svg>
      <path d="M2.5 12C4.7 7.7 8.1 5.5 12 5.5s7.3 2.2 9.5 6.5c-2.2 4.3-5.6 6.5-9.5 6.5S4.7 16.3 2.5 12z" />
      <circle cx="12" cy="12" r="3.2" />
      {riscado && <path d="M4 4l16 16" />}
    </Svg>
  )
}

export function IconeImagens() {
  return <Svg><rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10" r="1.6" /><path d="M21 16l-5-5-8 8" /></Svg>
}
