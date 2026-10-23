import { useEffect, useRef, useState } from 'react'
import CardJogo from './CardJogo'

function CarrosselJogos({ jogos, mostrarDesconto = false }) {
  const listaRef = useRef(null)
  const viewportRef = useRef(null)
  const gestoRef = useRef(null)
  const arrastouRef = useRef(false)
  const deslocamentoRef = useRef(0)
  const [indiceAtual, setIndiceAtual] = useState(0)
  const [itensVisiveis, setItensVisiveis] = useState(4)
  const [passo, setPasso] = useState(0)

  useEffect(() => {
    const atualizarItensVisiveis = () => {
      if (window.innerWidth <= 620) {
        setItensVisiveis(2)
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

  /*
    Arraste que acompanha o dedo em tempo real.
    Durante o gesto, a lista é movida direto no DOM (sem renderizar o React a cada
    movimento, para ficar fluido) e a transição é desligada. Ao soltar, a transição
    volta e a lista encaixa na página seguinte, na anterior, ou retorna ao lugar.
  */
  const iniciarGesto = (evento) => {
    if (evento.pointerType === 'mouse') return
    gestoRef.current = {
      id: evento.pointerId,
      x: evento.clientX,
      y: evento.clientY,
      dx: 0,
      ativo: false,
      ultimoX: evento.clientX,
      ultimoT: performance.now(),
      velocidade: 0,
    }
    arrastouRef.current = false
  }

  const moverGesto = (evento) => {
    const gesto = gestoRef.current
    const lista = listaRef.current
    if (!gesto || !lista || evento.pointerId !== gesto.id) return

    const dx = evento.clientX - gesto.x
    const dy = evento.clientY - gesto.y

    if (!gesto.ativo) {
      // Só assume o gesto quando ele é predominantemente horizontal.
      const horizontal = Math.abs(dx) > 8 && Math.abs(dx) > Math.abs(dy) * 1.2
      if (!horizontal) return

      gesto.ativo = true
      lista.style.transition = 'none'
      try {
        evento.currentTarget.setPointerCapture(evento.pointerId)
      } catch {
        // Sem captura, o gesto ainda funciona enquanto o dedo estiver sobre o carrossel.
      }
    }

    // Velocidade suavizada (px/ms) para reconhecer um "flick" rápido.
    const agora = performance.now()
    const intervalo = agora - gesto.ultimoT
    if (intervalo > 0) {
      const instantanea = (evento.clientX - gesto.ultimoX) / intervalo
      gesto.velocidade = gesto.velocidade * 0.6 + instantanea * 0.4
    }
    gesto.ultimoX = evento.clientX
    gesto.ultimoT = agora
    gesto.dx = dx

    // Nas pontas, o carrossel "estica" com resistência em vez de seguir o dedo por inteiro.
    let movimento = dx
    if ((!podeVoltar && dx > 0) || (!podeAvancar && dx < 0)) movimento = dx * 0.35

    const limite = Math.max(passo * itensVisiveis, 1)
    movimento = Math.max(-limite, Math.min(limite, movimento))

    lista.style.transform = `translate3d(${deslocamentoRef.current + movimento}px, 0, 0)`
  }

  const encerrarGesto = (permitirTroca) => {
    const gesto = gestoRef.current
    gestoRef.current = null
    const lista = listaRef.current
    if (!gesto?.ativo || !lista) return

    try {
      viewportRef.current?.releasePointerCapture(gesto.id)
    } catch {
      // A captura já pode ter sido liberada pelo navegador.
    }

    // Devolve a transição do CSS para o encaixe ser animado.
    lista.style.transition = ''
    arrastouRef.current = permitirTroca

    const distancia = Math.abs(gesto.dx)
    const longe = distancia > 60
    const rapido = Math.abs(gesto.velocidade) > 0.5 && distancia > 20

    if (permitirTroca && (longe || rapido)) {
      const direcao = gesto.dx < 0 ? 1 : -1
      const alvo = Math.max(0, Math.min(indiceAtual + direcao * itensVisiveis, maximo))
      if (alvo !== indiceAtual) {
        rolar(direcao)
        return
      }
    }

    // Gesto curto, cancelado ou já na ponta: volta para a posição atual.
    lista.style.transform = `translate3d(${deslocamentoRef.current}px, 0, 0)`
  }

  const finalizarGesto = () => encerrarGesto(true)
  const cancelarGesto = () => encerrarGesto(false)

  const impedirCliqueAposArraste = (evento) => {
    if (arrastouRef.current) {
      evento.preventDefault()
      evento.stopPropagation()
      arrastouRef.current = false
    }
  }

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

  useEffect(() => {
    deslocamentoRef.current = deslocamento
  })

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
        ref={viewportRef}
        style={{ touchAction: 'pan-y' }}
        onPointerDown={iniciarGesto}
        onPointerMove={moverGesto}
        onPointerUp={finalizarGesto}
        onPointerCancel={cancelarGesto}
        onClickCapture={impedirCliqueAposArraste}
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
