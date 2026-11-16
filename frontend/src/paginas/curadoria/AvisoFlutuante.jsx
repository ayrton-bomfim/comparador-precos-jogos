import { useEffect } from 'react'

const DURACAO_MS = 10000

// Aviso fixo no canto da tela: o resultado de cada ação fica visível mesmo
// quando a pessoa está no meio da lista. Erros só somem quando fechados.
function AvisoFlutuante({ aviso, onFechar }) {
  useEffect(() => {
    if (!aviso || aviso.tipo === 'erro') return undefined
    const temporizador = window.setTimeout(onFechar, DURACAO_MS)
    return () => window.clearTimeout(temporizador)
  }, [aviso, onFechar])

  if (!aviso) return null

  return (
    <div
      className={`cur-aviso cur-aviso-${aviso.tipo || 'sucesso'}`}
      role={aviso.tipo === 'erro' ? 'alert' : 'status'}
      key={aviso.id}
    >
      <p>{aviso.texto}</p>
      {aviso.acao && (
        <button
          type="button"
          className="cur-aviso-acao"
          onClick={() => {
            aviso.acao.onClick()
            onFechar()
          }}
        >
          {aviso.acao.rotulo}
        </button>
      )}
      <button type="button" className="cur-aviso-fechar" onClick={onFechar} aria-label="Fechar aviso">×</button>
    </div>
  )
}

export default AvisoFlutuante
