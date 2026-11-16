import { useMemo, useState } from 'react'
import { IconeImagens, IconeOlho } from './Icones'
import { normalizarImagens } from './utilidades'

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
            <IconeOlho riscado />
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
          className="cur-btn cur-btn--discreto cur-btn--p cur-galeria-carregar"
          onClick={onCarregarMidias}
          disabled={midiasCarregando}
        >
          <IconeImagens />
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
