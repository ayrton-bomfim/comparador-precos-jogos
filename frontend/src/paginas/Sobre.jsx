import { useEffect, useState } from 'react'
import Cabecalho from '../componentes/Cabecalho'
import fotoAutor from '../assets/foto-autor.jpg'
import './Sobre.css'

function Sobre() {
  const [tema, setTema] = useState(() => {
    const temaCompartilhado = localStorage.getItem('tema-comparador')

    if (temaCompartilhado === 'escuro' || temaCompartilhado === 'claro') {
      return temaCompartilhado
    }

    const temaLegado = localStorage.getItem('tema')
    return temaLegado === 'escuro' ? 'escuro' : 'claro'
  })

  useEffect(() => {
    localStorage.setItem('tema-comparador', tema)
  }, [tema])

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho tema={tema} setTema={setTema} />

      <main className="pagina-sobre">
        <section className="sobre-intro">
          <h1>O que é o DESCTRL?</h1>

          <p className="sobre-intro-destaque">
            Este projeto é o meu trabalho de conclusão do curso de Ciência da Computação na Universidade Paulista.
          </p>

          <div className="sobre-intro-texto">
            <p>
              Jogos fazem parte da minha vida desde criança. Quando precisei escolher um tema, queria algo que
              me mantivesse engajado durante todo o projeto e que me permitisse aplicar na prática o que aprendi em sala.
            </p>
            <p>
              Juntar essas duas coisas resultou em uma aplicação que compara os preços de jogos entre as principais
              lojas digitais e registra como eles mudam ao longo do tempo. A proposta é investigar se esse histórico
              ajuda a perceber quando vale mais a pena comprar.
            </p>

            <figure className="sobre-autor sobre-autor-grande">
              <img src={fotoAutor} alt="Foto de Ayrton, autor do projeto" width="168" height="168" />
              <figcaption>
                <strong>Ayrton Bomfim</strong>
                <span>Autor do projeto</span>
              </figcaption>
            </figure>
          </div>

          <p className="sobre-intro-status">
            <span className="sobre-ponto-status" aria-hidden="true" />
            Essa é uma versão beta e o projeto continua em desenvolvimento.
          </p>
        </section>

        <section className="sobre-fluxo-secao" aria-labelledby="sobre-fluxo-titulo">
          <h2 id="sobre-fluxo-titulo">Como os preços chegam até você</h2>

          <ol className="sobre-fluxo">
            <li className="sobre-etapa">
              <div className="sobre-etapa-visual visual-lojas" aria-hidden="true">
                <span className="sobre-loja steam-selo"><b>S</b>Steam</span>
                <span className="sobre-loja epic-selo"><b>E</b>Epic Games</span>
              </div>
              <div className="sobre-etapa-texto">
                <h3><span className="sobre-etapa-numero" aria-hidden="true">1</span>Lojas</h3>
                <p>Steam e Epic Games Store publicam o preço de cada jogo.</p>
              </div>
            </li>

            <li className="sobre-etapa">
              <div className="sobre-etapa-visual visual-coleta" aria-hidden="true">
                <span><i /><b /></span>
                <span><i /><b /></span>
                <span><i /><b /></span>
              </div>
              <div className="sobre-etapa-texto">
                <h3><span className="sobre-etapa-numero" aria-hidden="true">2</span>Coleta</h3>
                <p>O DESCTRL lê os preços e descontos publicados.</p>
              </div>
            </li>

            <li className="sobre-etapa">
              <div className="sobre-etapa-visual visual-historico" aria-hidden="true">
                <svg viewBox="0 0 160 80" role="presentation">
                  <path className="historico-base" d="M6 70H154" />
                  <polyline className="historico-linha" points="8,26 34,30 58,28 84,54 110,50 134,58 152,30" />
                  <circle className="historico-ponto" cx="152" cy="30" r="4.5" />
                </svg>
              </div>
              <div className="sobre-etapa-texto">
                <h3><span className="sobre-etapa-numero" aria-hidden="true">3</span>Histórico</h3>
                <p>Cada coleta fica guardada e forma a linha do tempo do preço.</p>
              </div>
            </li>

            <li className="sobre-etapa etapa-final">
              <div className="sobre-etapa-visual visual-voce" aria-hidden="true">
                <div><span>Steam</span><strong>R$ 59,99</strong></div>
                <div><span>Epic Games</span><strong>R$ 64,99</strong></div>
                <small>valores de exemplo</small>
              </div>
              <div className="sobre-etapa-texto">
                <h3><span className="sobre-etapa-numero" aria-hidden="true">4</span>Para você</h3>
                <p>Você compara as lojas, vê o histórico e cria alertas.</p>
              </div>
            </li>
          </ol>
        </section>

        <section className="sobre-limites" aria-labelledby="sobre-limites-titulo">
          <h2 id="sobre-limites-titulo">O que o DESCTRL não faz</h2>

          <ul className="sobre-limites-lista">
            <li>
              <span className="sobre-limite-marca" aria-hidden="true">✕</span>
              <strong>Não vende jogos</strong>
              <p>A compra acontece na loja.</p>
            </li>
            <li>
              <span className="sobre-limite-marca" aria-hidden="true">✕</span>
              <strong>Não promete descontos futuros</strong>
              <p>As estimativas usam só o histórico coletado.</p>
            </li>
            <li>
              <span className="sobre-limite-marca" aria-hidden="true">✕</span>
              <strong>Não garante o preço de agora</strong>
              <p>Confira o valor final na loja antes de comprar.</p>
            </li>
          </ul>
        </section>

        {/* A visão exclusiva do administrador logado entra aqui, depois desta seção. */}
      </main>
    </div>
  )
}

export default Sobre
