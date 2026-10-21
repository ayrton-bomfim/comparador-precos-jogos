import { createContext, useContext, useEffect, useState } from 'react'

const TemaContext = createContext(null)

export function TemaProvider({ children }) {
  const [tema, setTema] = useState(() => {
    return localStorage.getItem('tema-comparador') || 'escuro'
  })

  useEffect(() => {
    localStorage.setItem('tema-comparador', tema)
  }, [tema])

  return (
    <TemaContext.Provider value={{ tema, setTema }}>
      {children}
    </TemaContext.Provider>
  )
}

// Este hook é exportado junto do Provider intencionalmente; ambos pertencem ao contexto.
// eslint-disable-next-line react-refresh/only-export-components
export function useTema() {
  const contexto = useContext(TemaContext)

  if (!contexto) {
    throw new Error('useTema deve ser usado dentro de TemaProvider.')
  }

  return contexto
}
