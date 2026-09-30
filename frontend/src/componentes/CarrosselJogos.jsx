import { useEffect, useRef, useState } from 'react'
import CardJogo from './CardJogo'

function CarrosselJogos({ jogos, mostrarDesconto = false }) {
  const listaRef = useRef(null)
  const [indiceAtual, setIndiceAtual] = useState(0)
  const [itensVisiveis, setItensVisiveis] = useState(4)
  const [passo, setPasso] = useState(0)

  useEffect(() => {
    const atualizarItensVisiveis = () => {
      if (window.innerWidth <= 620) {
        setItensVisiveis(1)
      } else if (window.innerWidth <= 900) {
        setItensVisiveis(2)
      } else {
        setItensVisiveis(4)
      }
    }

    atualizarItensVisiveis()
    window.addEventListener('resize', atualizarItensVisiveis)

    return () => {
      window.removeEventListener('resize', atualizarItensVisiveis)
    }
  }, [])

  useEffect(() => {
    const atualizarPasso = () => {
      const lista = listaRef.current
      const item = lista?.querySelector('.item-carrossel')

      if (!item) {
        setPasso(0)
        return
      }

      const largura = item.getBoundingClientRect().width
      const gap = parseFloat(getComputedStyle(lista).gap) || 20

      setPasso(largura + gap)
    }

    atualizarPasso()

    const lista = listaRef.current
    let observer

    if (lista && typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(atualizarPasso)
      observer.observe(lista)
    } else {
      window.addEventListener('resize', atualizarPasso)
    }

    return () => {
      observer?.disconnect()
      window.removeEventListener('resize', atualizarPasso)
    }
  }, [jogos, itensVisiveis])

  const maximo = Math.max(0, jogos.length - itensVisiveis)
  const indiceExibicao = Math.min(indiceAtual, maximo)
  const podeVoltar = indiceExibicao > 0
  const podeAvancar = indiceExibicao < maximo

  const rolar = (direcao) => {
    setIndiceAtual((atual) => {
      const novoIndice = atual + direcao * itensVisiveis
      return Math.max(0, Math.min(novoIndice, maximo))
    })
  }

  const deslocamento = (() => {
    if (indiceExibicao === 0) {
      return 0
    }

    if (indiceExibicao === maximo) {
      return -(indiceAtual * passo)
    }

    /*
      Mantém aproximadamente metade do card anterior visível
      e a mesma quantidade do próximo card.

      Se:
        passo = largura do card + gap
        gap   = espaço entre os cards

      então o deslocamento lateral ideal é:
        metade da largura do card + gap
      que equivale a:
        (passo + gap) / 2
    */
    const espacoLateral = passo * 0.20

    return -(indiceExibicao * passo) + espacoLateral
  })()

  return (
    <div className="carrossel">
      <button
        className={`seta-carrossel esquerda ${
          podeVoltar ? 'visivel' : ''
        }`}
        onClick={() => rolar(-1)}
        disabled={!podeVoltar}
        aria-label="Mostrar jogos anteriores"
      >
        ‹
      </button>

      <div
        className={`viewport-carrossel ${
          podeVoltar ? 'tem-esquerda' : ''
        } ${podeAvancar ? 'tem-direita' : ''}`}
      >
        <div
          className="lista-carrossel"
          ref={listaRef}
          style={{
            transform: `translate3d(${deslocamento}px, 0, 0)`,
          }}
        >
          {jogos.map((jogo) => (
            <div className="item-carrossel" key={jogo.id}>
              <CardJogo
                jogo={jogo}
                mostrarDesconto={mostrarDesconto}
              />
            </div>
          ))}
        </div>
      </div>

      <button
        className={`seta-carrossel direita ${
          podeAvancar ? 'visivel' : ''
        }`}
        onClick={() => rolar(1)}
        disabled={!podeAvancar}
        aria-label="Mostrar próximos jogos"
      >
        ›
      </button>
    </div>
  )
}

export default CarrosselJogos
