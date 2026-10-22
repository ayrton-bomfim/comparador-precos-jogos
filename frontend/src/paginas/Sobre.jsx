import { useEffect, useState } from 'react'
import Cabecalho from '../componentes/Cabecalho'
import './Sobre.css'

const recursos = [
  {
    numero: '01',
    icone: '⇄',
    titulo: 'Compare preços',
    descricao: 'Veja os preços disponíveis nas lojas analisadas e compare antes de comprar.',
    classe: 'comparar',
  },
  {
    numero: '02',
    icone: '↗',
    titulo: 'Explore o histórico',
    descricao: 'Entenda como o preço de um jogo mudou ao longo do tempo.',
    classe: 'historico',
  },
  {
    numero: '03',
    icone: '%',
    titulo: 'Observe promoções',
    descricao: 'Consulte descontos e acompanhe o comportamento dos preços promocionais.',
    classe: 'promocoes',
  },
  {
    numero: '04',
    icone: '⌁',
    titulo: 'Consulte estimativas',
    descricao: 'Use os padrões do histórico disponível como apoio para suas decisões.',
    classe: 'estimativas',
  },
]

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
        <section className="sobre-hero-visual">
          <div className="sobre-hero-conteudo">
            <span className="sobre-eyebrow"><span className="sobre-ponto-vivo" /> SOBRE O DESCTRL</span>
            <h1>Seu próximo jogo<br /><span>pode custar menos.</span></h1>
            <p>
              Um jeito mais claro de acompanhar preços, comparar lojas e entender
              o histórico de promoções antes de decidir onde comprar seu próximo jogo.
            </p>
            <div className="sobre-lojas-mini" aria-label="Lojas analisadas">
              <span className="sobre-loja-selo steam-selo">S</span>
              <span className="sobre-loja-selo epic-selo">E</span>
              <span className="sobre-lojas-texto">Steam <i /> Epic Games Store</span>
            </div>
          </div>

          <div className="sobre-hero-arte" aria-label="Ilustração conceitual de comparação de preços">
            <div className="sobre-orbita orbita-externa" />
            <div className="sobre-orbita orbita-interna" />
            <div className="sobre-placa-jogo placa-jogo-fundo">
              <span className="placa-etiqueta">HISTÓRICO</span>
              <div className="placa-grafico"><i /><i /><i /><i /><i /><i /><i /></div>
              <div className="placa-linhas"><i /><i /></div>
            </div>
            <div className="sobre-placa-jogo placa-jogo-frente">
              <div className="placa-capa"><span>GAME<br />ON</span><b>✦</b></div>
              <div className="placa-detalhes">
                <span>PREÇO ATUAL</span>
                <strong>Compare.</strong>
                <small>Escolha com informação.</small>
              </div>
              <div className="placa-tag">% OFF</div>
            </div>
            <div className="sobre-brilho brilho-um" />
            <div className="sobre-brilho brilho-dois" />
          </div>
        </section>

        <section className="sobre-recursos-secao" aria-labelledby="sobre-recursos-titulo">
          <div className="sobre-secao-cabecalho">
            <div>
              <span className="sobre-eyebrow">MENOS PROCURA, MAIS CLAREZA</span>
              <h2 id="sobre-recursos-titulo">O que você encontra por aqui</h2>
            </div>
            <p>Informações para comprar com mais contexto, não no escuro.</p>
          </div>

          <div className="sobre-recursos-grid">
            {recursos.map((recurso) => (
              <article className={`sobre-recurso-card recurso-${recurso.classe}`} key={recurso.numero}>
                <div className="sobre-recurso-topo">
                  <span className="sobre-recurso-icone" aria-hidden="true">{recurso.icone}</span>
                  <span className="sobre-recurso-numero">{recurso.numero}</span>
                </div>
                <h3>{recurso.titulo}</h3>
                <p>{recurso.descricao}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="sobre-fluxo-secao" aria-labelledby="sobre-fluxo-titulo">
          <div className="sobre-fluxo-intro">
            <span className="sobre-eyebrow">POR TRÁS DA TELA</span>
            <h2 id="sobre-fluxo-titulo">Da loja até você.</h2>
            <p>O projeto organiza informações de lojas digitais e transforma esses dados em uma visão mais fácil de consultar.</p>
          </div>

          <div className="sobre-fluxo-passos">
            <article className="sobre-fluxo-passo">
              <span className="sobre-fluxo-icone" aria-hidden="true">▦</span>
              <span className="sobre-fluxo-numero">ETAPA 01</span>
              <strong>Lojas digitais</strong>
              <small>Steam e Epic Games Store</small>
            </article>
            <span className="sobre-fluxo-conector" aria-hidden="true">→</span>
            <article className="sobre-fluxo-passo">
              <span className="sobre-fluxo-icone" aria-hidden="true">↓</span>
              <span className="sobre-fluxo-numero">ETAPA 02</span>
              <strong>Coleta e organização</strong>
              <small>Preços e descontos disponíveis</small>
            </article>
            <span className="sobre-fluxo-conector" aria-hidden="true">→</span>
            <article className="sobre-fluxo-passo">
              <span className="sobre-fluxo-icone" aria-hidden="true">⌁</span>
              <span className="sobre-fluxo-numero">ETAPA 03</span>
              <strong>Análise do histórico</strong>
              <small>Registros e padrões observados</small>
            </article>
            <span className="sobre-fluxo-conector" aria-hidden="true">→</span>
            <article className="sobre-fluxo-passo passo-destaque">
              <span className="sobre-fluxo-icone" aria-hidden="true">◎</span>
              <span className="sobre-fluxo-numero">ETAPA 04</span>
              <strong>Informação para você</strong>
              <small>Comparações e visualizações</small>
            </article>
          </div>
        </section>

        <section className="sobre-transparencia">
          <div className="sobre-transparencia-icone" aria-hidden="true">i</div>
          <div>
            <strong>Uma estimativa é uma referência, não uma promessa.</strong>
            <p>Preços e promoções podem mudar nas lojas. As análises dependem do histórico disponível e não garantem a data nem o valor de um desconto futuro. Confira sempre o preço final na loja antes de comprar.</p>
          </div>
        </section>

        <footer className="sobre-rodape">
          <div className="sobre-rodape-marca"><span className="sobre-marca-simbolo">D</span><strong>DESCTRL</strong></div>
          <p>Projeto acadêmico desenvolvido no curso de Ciência da Computação da UNIP.</p>
          <span className="sobre-rodape-ano">2026</span>
        </footer>
      </main>
    </div>
  )
}

export default Sobre
