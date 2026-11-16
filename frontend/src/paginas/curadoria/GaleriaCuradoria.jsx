import { useMemo, useState } from 'react'
import { normalizarImagens } from './utilidades'

function IconeOlhoRiscado() {
  return (
    <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path d="M2.5 12C4.7 7.7 8.1 5.5 12 5.5C15.9 5.5 19.3 7.7 21.5 12C19.3 16.3 15.9 18.5 12 18.5C8.1 18.5 4.7 16.3 2.5 12Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.8" />
      <path d="M4 4L20 20" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

// Galeria do jogo no painel de decisão. As imagens extras só são buscadas
// quando o administrador pede, para não sobrecarregar as lojas.
function GaleriaCuradoria({
  item,
  imagemBorrada = false,
  onCarregarMidias,
  midiasCarregando = false,
  midiasConsultadas = false,
  erroMidias = '',
}) {
  const imagens = useMemo(() => normalizarImagens(item, midiasConsultadas), [item, midiasConsultadas])
  const [indice, setIndice] = useState(0)
  const imagemPrincipal = imagens[indice]?.url || imagens[0]?.url || ''

  return (
    <div className="cur-galeria">
      <div className="cur-galeria-principal">
        {imagemPrincipal ? (
          <img
            src={imagemPrincipal}
            alt={`Imagem de ${item.nome}`}
            className={imagemBorrada ? 'imagem-borrada' : ''}
          />
        ) : (
          <div className="cur-sem-imagem">Sem imagem</div>
        )}

        {imagemBorrada && imagemPrincipal && (
          <div className="cur-galeria-aviso" aria-hidden="true">
            <IconeOlhoRiscado />
            <strong>Imagem oculta</strong>
            <span>Possível conteúdo sensível</span>
          </div>
        )}

        {midiasConsultadas && imagens.length > 1 && (
          <span className="cur-galeria-contador">{indice + 1}/{imagens.length}</span>
        )}
      </div>

      {midiasConsultadas && imagens.length > 1 && (
        <div className="cur-galeria-miniaturas" aria-label={`Imagens de ${item.nome}`}>
          {imagens.map((imagem, posicao) => (
            <button
              type="button"
              key={`${imagem.url}-${posicao}`}
              className={posicao === indice ? 'ativa' : ''}
              onClick={() => setIndice(posicao)}
              title={imagem.tipo || `Imagem ${posicao + 1}`}
              aria-label={`Mostrar imagem ${posicao + 1}`}
            >
              <img src={imagem.url} alt="" loading="lazy" className={imagemBorrada ? 'imagem-borrada' : ''} />
            </button>
          ))}
        </div>
      )}

      {typeof onCarregarMidias === 'function' && !midiasConsultadas && (
        <button
          type="button"
          className="cur-galeria-carregar"
          onClick={onCarregarMidias}
          disabled={midiasCarregando}
        >
          {midiasCarregando ? 'Buscando imagens...' : erroMidias ? 'Tentar carregar a galeria de novo' : 'Carregar galeria'}
        </button>
      )}
      {erroMidias && <span className="cur-galeria-erro" role="alert">{erroMidias}</span>}
      {midiasConsultadas && imagens.length <= 1 && (
        <span className="cur-galeria-status">Nenhuma imagem adicional encontrada.</span>
      )}
    </div>
  )
}

export default GaleriaCuradoria
