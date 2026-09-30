import { useEffect, useState } from 'react'
import Cabecalho from '../componentes/Cabecalho'
import './Sobre.css'

function Sobre() {
  const [tema, setTema] = useState(() => {
    return localStorage.getItem('tema') || 'claro'
  })

  useEffect(() => {
    localStorage.setItem('tema', tema)
  }, [tema])

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho tema={tema} setTema={setTema} />

      <main className="pagina-sobre">
        <section className="sobre-hero">
          <span className="eyebrow">SOBRE O PROJETO</span>

          <h1>Comparador de preços de jogos digitais</h1>

          <p>
            Uma aplicação web desenvolvida para acompanhar preços,
            promoções e histórico de jogos digitais, auxiliando na análise
            do comportamento dos preços em diferentes lojas.
          </p>

          <div className="sobre-resumo">
            <article>
              <strong>Steam</strong>
              <span>Comparação e histórico de preços</span>
            </article>

            <article>
              <strong>Epic Games Store</strong>
              <span>Comparação e histórico de preços</span>
            </article>
          </div>
        </section>

        <section className="sobre-secao">
          <div className="sobre-titulo">
            <span className="eyebrow">FUNCIONALIDADES</span>
            <h2>O que você pode fazer</h2>
          </div>

          <div className="sobre-grid quatro">
            <article className="sobre-card">
              <span className="sobre-numero">01</span>
              <h3>Comparar preços</h3>
              <p>
                Compare os preços atuais dos jogos entre as plataformas
                disponíveis.
              </p>
            </article>

            <article className="sobre-card">
              <span className="sobre-numero">02</span>
              <h3>Acompanhar histórico</h3>
              <p>
                Visualize como o preço de um jogo se comportou ao longo do
                tempo.
              </p>
            </article>

            <article className="sobre-card">
              <span className="sobre-numero">03</span>
              <h3>Analisar promoções</h3>
              <p>
                Observe descontos, frequência e intervalos entre episódios
                promocionais.
              </p>
            </article>

            <article className="sobre-card">
              <span className="sobre-numero">04</span>
              <h3>Estimar próximas promoções</h3>
              <p>
                Consulte estimativas baseadas no comportamento histórico das
                promoções registradas.
              </p>
            </article>
          </div>
        </section>

        <section className="sobre-secao">
          <div className="sobre-titulo">
            <span className="eyebrow">ARQUITETURA</span>
            <h2>Como o Comparador funciona</h2>
          </div>

          <div className="fluxo-sistema">
            <article>
              <span>01</span>
              <strong>Lojas digitais</strong>
              <p>Steam e Epic Games Store.</p>
            </article>

            <div className="fluxo-seta">→</div>

            <article>
              <span>02</span>
              <strong>Coleta de dados</strong>
              <p>Dados públicos de preços e descontos.</p>
            </article>

            <div className="fluxo-seta">→</div>

            <article>
              <span>03</span>
              <strong>Armazenamento</strong>
              <p>Histórico organizado em banco de dados.</p>
            </article>

            <div className="fluxo-seta">→</div>

            <article>
              <span>04</span>
              <strong>Análise</strong>
              <p>Identificação de padrões promocionais.</p>
            </article>

            <div className="fluxo-seta">→</div>

            <article>
              <span>05</span>
              <strong>Visualização</strong>
              <p>Informações apresentadas na aplicação.</p>
            </article>
          </div>
        </section>

        <section className="sobre-secao">
          <div className="sobre-titulo">
            <span className="eyebrow">TECNOLOGIAS</span>
            <h2>Tecnologias utilizadas</h2>
          </div>

          <div className="tecnologias-grid">
            <article className="tecnologia-card">
              <span>FRONTEND</span>
              <strong>React</strong>
              <p>Interface e visualização das informações.</p>
            </article>

            <article className="tecnologia-card">
              <span>BACKEND</span>
              <strong>Python + FastAPI</strong>
              <p>API responsável pela disponibilização dos dados.</p>
            </article>

            <article className="tecnologia-card">
              <span>COLETA</span>
              <strong>Playwright + Requests</strong>
              <p>Automação e consumo de fontes estruturadas.</p>
            </article>

            <article className="tecnologia-card">
              <span>DADOS</span>
              <strong>PostgreSQL</strong>
              <p>Armazenamento dos jogos e do histórico de preços.</p>
            </article>
          </div>
        </section>

        <section className="sobre-secao">
          <div className="sobre-titulo">
            <span className="eyebrow">PLATAFORMAS</span>
            <h2>Plataformas analisadas</h2>
          </div>

          <div className="plataformas-grid">
            <article className="plataforma-card">
              <div>
                <span className="plataforma-legenda">LOJA DIGITAL</span>
                <h3>Steam</h3>
              </div>

              <ul>
                <li>Preços</li>
                <li>Descontos</li>
                <li>Histórico</li>
                <li>Promoções</li>
              </ul>
            </article>

            <article className="plataforma-card">
              <div>
                <span className="plataforma-legenda">LOJA DIGITAL</span>
                <h3>Epic Games Store</h3>
              </div>

              <ul>
                <li>Preços</li>
                <li>Descontos</li>
                <li>Histórico</li>
                <li>Promoções</li>
              </ul>
            </article>
          </div>
        </section>

        <section className="sobre-secao">
          <div className="sobre-titulo">
            <span className="eyebrow">ANÁLISE</span>
            <h2>Como funciona a previsão?</h2>
          </div>

          <div className="previsao-sobre">
            <div className="previsao-fluxo">
              <span>Histórico de preços</span>
              <b>→</b>
              <span>Promoções identificadas</span>
              <b>→</b>
              <span>Intervalos e descontos</span>
              <b>→</b>
              <span>Estimativa</span>
            </div>

            <div className="previsao-texto">
              <p>
                A estimativa considera o comportamento histórico das
                promoções registradas para identificar padrões de frequência,
                intervalos entre promoções, descontos observados e preços
                promocionais.
              </p>

              <div className="aviso-sobre">
                <strong>Importante</strong>
                <span>
                  As estimativas são baseadas nos dados históricos disponíveis
                  e não representam garantia de uma futura promoção, data ou
                  percentual de desconto.
                </span>
              </div>
            </div>
          </div>
        </section>

        <section className="sobre-final">
          <article className="projeto-academico">
            <span className="eyebrow">PROJETO ACADÊMICO</span>

            <h2>Desenvolvimento de uma Aplicação Web</h2>

            <p>
              Um Comparador de Preços para o Mercado Brasileiro de Jogos
              Digitais.
            </p>

            <div className="dados-academicos">
              <div>
                <span>CURSO</span>
                <strong>Ciência da Computação</strong>
              </div>

              <div>
                <span>INSTITUIÇÃO</span>
                <strong>Universidade Paulista — UNIP</strong>
              </div>

              <div>
                <span>ANO</span>
                <strong>2026</strong>
              </div>

              <div>
                <span>AUTOR</span>
                <strong>Ayrton de Sousa Bomfim</strong>
              </div>
            </div>
          </article>

          <article className="limitacoes-card">
            <span className="eyebrow">LIMITAÇÕES</span>

            <h2>Sobre os dados e estimativas</h2>

            <p>
              Os dados apresentados dependem das informações disponíveis
              durante as coletas. Preços, descontos, disponibilidade e
              promoções podem sofrer alterações nas lojas digitais.
            </p>

            <p>
              As estimativas apresentadas pelo sistema são baseadas no
              histórico disponível e podem não refletir eventos promocionais
              futuros.
            </p>
          </article>
        </section>
      </main>
    </div>
  )
}

export default Sobre
