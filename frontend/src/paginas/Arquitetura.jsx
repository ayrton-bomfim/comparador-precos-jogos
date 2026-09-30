import { useEffect, useState } from 'react'
import Cabecalho from '../componentes/Cabecalho'
import './Arquitetura.css'

const etapasGerais = [
  {
    numero: '01',
    titulo: 'Lojas digitais',
    texto: 'Steam e Epic Games Store.',
  },
  {
    numero: '02',
    titulo: 'Coleta de dados',
    texto: 'Obtenção de preços, descontos e metadados.',
  },
  {
    numero: '03',
    titulo: 'Armazenamento',
    texto: 'Dados persistidos e histórico organizado.',
  },
  {
    numero: '04',
    titulo: 'Análise',
    texto: 'Tratamento do histórico e identificação de padrões.',
  },
  {
    numero: '05',
    titulo: 'Visualização',
    texto: 'Informações apresentadas na aplicação web.',
  },
]

const camadas = [
  {
    numero: '01',
    titulo: 'Fontes de dados',
    subtitulo: 'Steam + Epic Games Store',
    detalhes: 'As lojas fornecem os dados públicos utilizados pela solução.',
  },
  {
    numero: '02',
    titulo: 'Coletores',
    subtitulo: 'Requests + Playwright + fallback',
    detalhes: 'Módulos específicos obtêm e normalizam os dados de cada plataforma.',
  },
  {
    numero: '03',
    titulo: 'Persistência',
    subtitulo: 'PostgreSQL',
    detalhes: 'Jogos e registros de histórico são armazenados para consultas posteriores.',
  },
  {
    numero: '04',
    titulo: 'Serviços',
    subtitulo: 'FastAPI',
    detalhes: 'A API organiza e disponibiliza os dados para o frontend.',
  },
  {
    numero: '05',
    titulo: 'Apresentação',
    subtitulo: 'React',
    detalhes: 'A interface permite pesquisa, comparação, histórico e análise.',
  },
]

function SteamIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <circle cx="24" cy="24" r="21" fill="#1b5aa0" />
      <circle cx="30.5" cy="17.5" r="6.2" fill="none" stroke="#fff" strokeWidth="3.2" />
      <circle cx="30.5" cy="17.5" r="2.1" fill="#fff" />
      <circle cx="16.2" cy="29.8" r="4.2" fill="#fff" />
      <path
        d="M19.6 27.7 27 22.7"
        stroke="#fff"
        strokeWidth="3.2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function ApiIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <rect x="9" y="8" width="30" height="32" rx="7" fill="#6c55d9" />
      <path
        d="M17 19.5 13.5 24 17 28.5M31 19.5l3.5 4.5-3.5 4.5M27.5 17 20.5 31"
        fill="none"
        stroke="#fff"
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <text x="24" y="37" fill="#fff" fontSize="5.5" fontWeight="800" textAnchor="middle">
        API
      </text>
    </svg>
  )
}

function EpicIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <path
        d="M24 7 38 15v18L24 41 10 33V15L24 7Z"
        fill="#2f2b3f"
        stroke="#8c67ef"
        strokeWidth="1.8"
      />
      <path
        d="m24 13 8 4.6v9.8L24 32l-8-4.6v-9.8L24 13Z"
        fill="#8c67ef"
      />
      <path
        d="M21 19h6M21 23h6M21 27h4"
        stroke="#fff"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  )
}

function GraphqlIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <circle cx="24" cy="24" r="13" fill="none" stroke="#8f67f3" strokeWidth="2.5" />
      <circle cx="24" cy="10" r="2.6" fill="#8f67f3" />
      <circle cx="36.2" cy="31" r="2.6" fill="#8f67f3" />
      <circle cx="11.8" cy="31" r="2.6" fill="#8f67f3" />
      <path
        d="M24 12.6 35.1 29.3M24 12.6 12.9 29.3M14.1 31h19.8"
        stroke="#b9a9ff"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M18 21.5 22 19l4 2.5v5L22 29l-4-2.5v-5Z"
        fill="#8f67f3"
        opacity=".92"
      />
    </svg>
  )
}

function ValidacaoIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <circle cx="21" cy="21" r="10" fill="none" stroke="#b8a7ff" strokeWidth="4" />
      <path
        d="M29 29 37 37"
        stroke="#b8a7ff"
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  )
}

function BrowserIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <rect x="8" y="10" width="32" height="28" rx="6" fill="#8c67ef" />
      <rect x="11" y="14" width="26" height="21" rx="3" fill="#19141f" />
      <circle cx="14.5" cy="12.8" r="1.3" fill="#fff" />
      <circle cx="18.5" cy="12.8" r="1.3" fill="#fff" />
      <circle cx="22.5" cy="12.8" r="1.3" fill="#fff" />
    </svg>
  )
}

function DatabaseIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <ellipse cx="24" cy="12" rx="12" ry="6" fill="#35d07f" />
      <path d="M12 12v9c0 3.3 5.4 6 12 6s12-2.7 12-6v-9" fill="#28b66c" />
      <path d="M12 21v9c0 3.3 5.4 6 12 6s12-2.7 12-6v-9" fill="#1f9e60" />
      <ellipse cx="24" cy="12" rx="12" ry="6" fill="none" stroke="#0c6a3e" strokeWidth="1.2" />
    </svg>
  )
}

function CogIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <circle cx="24" cy="24" r="8" fill="#8f67f3" />
      <path
        d="M24 7v5M24 36v5M7 24h5M36 24h5M12 12l3.5 3.5M32.5 32.5 36 36M36 12l-3.5 3.5M15.5 32.5 12 36"
        stroke="#8f67f3"
        strokeWidth="5"
        strokeLinecap="round"
      />
    </svg>
  )
}

function PostgresIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" className="fluxo-icon-svg">
      <path
        d="M12 16c0-4 5-7 12-7s12 3 12 7v10c0 7-4 13-12 13S12 33 12 26V16Z"
        fill="#4f8ccf"
      />
      <path
        d="M14 17c2.5 2 5.9 3 10 3s7.5-1 10-3M14 24c2.5 2 5.9 3 10 3s7.5-1 10-3"
        fill="none"
        stroke="#dcecff"
        strokeWidth="1.4"
        opacity=".75"
      />
      <circle cx="28.5" cy="15.5" r="2.4" fill="#fff" opacity=".9" />
    </svg>
  )
}

function Arquitetura() {
  const [tema, setTema] = useState(() => {
    const salvo = localStorage.getItem('tema-comparador')
    return salvo === 'escuro' ? 'escuro' : 'claro'
  })

  useEffect(() => {
    localStorage.setItem('tema-comparador', tema)
  }, [tema])

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho tema={tema} setTema={setTema} />

      <main className="pagina-arquitetura">
        <section className="arquitetura-hero">
          <span className="eyebrow">ARQUITETURA</span>
          <h1>Como o Comparador funciona</h1>
          <p>
            Visões do sistema desenvolvidas com a mesma identidade visual da
            aplicação para apoiar a documentação técnica e a apresentação do TCC.
          </p>
        </section>

        <section className="visao-secao">
          <div className="visao-cabecalho">
            <span className="eyebrow">VISÃO GERAL</span>
            <h2>Do dado bruto à informação apresentada</h2>
            <p>
              Esta visão resume o fluxo funcional da solução em uma sequência
              única, destacando as principais etapas do processamento.
            </p>
          </div>

          <div className="fluxo-geral">
            {etapasGerais.map((etapa, index) => (
              <div className="fluxo-item" key={etapa.numero}>
                <article className="fluxo-card">
                  <span className="fluxo-numero">{etapa.numero}</span>
                  <h3>{etapa.titulo}</h3>
                  <p>{etapa.texto}</p>
                </article>

                {index < etapasGerais.length - 1 && (
                  <span className="fluxo-conector" aria-hidden="true">
                    →
                  </span>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="visao-secao">
          <div className="visao-cabecalho">
            <span className="eyebrow">ARQUITETURA TÉCNICA</span>
            <h2>Separação das responsabilidades</h2>
            <p>
              A arquitetura técnica separa as responsabilidades da solução para
              facilitar manutenção, testes e evolução do sistema.
            </p>
          </div>

          <div className="arquitetura-camadas">
            {camadas.map((camada, index) => (
              <div className="camada-item" key={camada.numero}>
                <article className="camada-card">
                  <span className="camada-numero">{camada.numero}</span>

                  <div>
                    <span className="camada-subtitulo">{camada.subtitulo}</span>
                    <h3>{camada.titulo}</h3>
                    <p>{camada.detalhes}</p>
                  </div>
                </article>

                {index < camadas.length - 1 && (
                  <div className="camada-conector" aria-hidden="true">
                    <span>↓</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>

        <section className="visao-secao">
          <div className="visao-cabecalho">
            <span className="eyebrow">FLUXO DE DADOS</span>
            <h2>Coleta de dados da Steam</h2>
            <p>
              Esta representação reproduz em código a visão gráfica utilizada
              para explicar o processo do coletor, incluindo o caminho principal
              e o fallback.
            </p>
          </div>

          <div className="fluxo-steam">
            <div className="fluxo-steam-intro">
              <span className="fluxo-steam-eyebrow">COLETA DE DADOS</span>
              <h3>Fluxo do coletor da Steam</h3>
              <p>
                O processo utiliza a fonte estruturada como caminho principal e
                recorre ao Playwright em situações nas quais o dado necessário
                não é obtido pela API.
              </p>
            </div>

            <div className="steam-stage steam-stage-top">
              <div className="steam-icon-wrap">
                <SteamIcon />
              </div>

              <div>
                <span className="steam-stage-number">1. Identificador do jogo</span>
                <p>Utiliza o Steam ID do jogo para realizar a consulta.</p>
              </div>
            </div>

            <div className="steam-arrow">↓</div>

            <div className="steam-stage steam-stage-api">
              <div className="steam-icon-wrap">
                <ApiIcon />
              </div>

              <div>
                <span className="steam-stage-number">2. API de detalhes da Steam</span>
                <p>
                  Realiza uma requisição ao endpoint de detalhes da plataforma,
                  considerando o contexto do mercado brasileiro.
                </p>
              </div>
            </div>

            <div className="steam-arrow">↓</div>

            <div className="steam-stage steam-stage-validation">
              <div className="steam-icon-wrap">
                <ValidacaoIcon />
              </div>

              <div>
                <span className="steam-stage-number">3. Validação da resposta</span>
                <p>
                  Verifica se a resposta foi obtida com sucesso e se contém as
                  informações necessárias.
                </p>
              </div>
            </div>

            <div className="steam-branches">
              <div className="steam-branch steam-branch-valid">
                <span>Resposta válida</span>
              </div>

              <div className="steam-branch-line steam-branch-line-left" />
              <div className="steam-branch-line steam-branch-line-right" />

              <div className="steam-branch steam-branch-fail">
                <span>Falha ou dado ausente</span>
              </div>
            </div>

            <div className="steam-results">
              <div className="steam-result-card steam-result-valid">
                <div className="steam-icon-wrap">
                  <DatabaseIcon />
                </div>

                <div>
                  <span className="steam-stage-number">4. Extração dos dados</span>
                  <p>
                    Obtém nome, preço, desconto, desenvolvedor, publicadora,
                    gênero, data de lançamento, imagem e descrição.
                  </p>
                </div>
              </div>

              <div className="steam-result-card steam-result-fallback">
                <div className="steam-icon-wrap">
                  <BrowserIcon />
                </div>

                <div>
                  <span className="steam-stage-number">5. Fallback com Playwright</span>
                  <p>
                    Abre a página do produto, identifica o preço nos elementos da
                    área de compra e trata casos específicos, como jogos gratuitos
                    e verificações de idade.
                  </p>
                </div>
              </div>
            </div>

            <div className="steam-merge-lines">
              <span className="merge-line merge-left" />
              <span className="merge-line merge-right" />
              <span className="merge-arrow">↓</span>
            </div>

            <div className="steam-stage steam-stage-normalize">
              <div className="steam-icon-wrap">
                <CogIcon />
              </div>

              <div>
                <span className="steam-stage-number">6. Normalização dos dados</span>
                <p>
                  Converte os valores, trata jogos gratuitos, remove marcações
                  HTML e padroniza as informações antes do armazenamento.
                </p>
              </div>
            </div>

            <div className="steam-arrow">↓</div>

            <div className="steam-stage steam-stage-db">
              <div className="steam-icon-wrap">
                <PostgresIcon />
              </div>

              <div>
                <span className="steam-stage-number">7. Armazenamento no PostgreSQL</span>
                <p>
                  Salva as informações cadastrais do jogo e registra o preço no
                  histórico conforme as regras de atualização do sistema.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="visao-secao">
          <div className="visao-cabecalho">
            <span className="eyebrow">FLUXO DE DADOS</span>
            <h2>Coleta de dados da Epic Games Store</h2>
            <p>
              Esta representação mostra o caminho principal baseado em GraphQL e o
              fallback utilizado quando a coleta estruturada não é concluída.
            </p>
          </div>

          <div className="fluxo-epic">
            <div className="fluxo-epic-intro">
              <span className="fluxo-epic-eyebrow">COLETA DE DADOS</span>
              <h3>Fluxo do coletor da Epic Games Store</h3>
              <p>
                O processo acessa a página do jogo, identifica a oferta e utiliza
                chamadas estruturadas para obter os dados de catálogo e preço,
                recorrendo ao navegador como caminho complementar em caso de falha.
              </p>
            </div>

            <div className="steam-stage epic-stage-top">
              <div className="steam-icon-wrap">
                <EpicIcon />
              </div>
              <div>
                <span className="steam-stage-number">1. Slug e página do jogo</span>
                <p>Utiliza o slug do título para acessar a página correspondente na Epic Games Store.</p>
              </div>
            </div>

            <div className="steam-arrow">↓</div>

            <div className="steam-stage epic-stage-api">
              <div className="steam-icon-wrap">
                <BrowserIcon />
              </div>
              <div>
                <span className="steam-stage-number">2. Carregamento no Playwright</span>
                <p>
                  Abre a página no navegador automatizado e acompanha as respostas
                  de rede emitidas pela própria aplicação.
                </p>
              </div>
            </div>

            <div className="steam-arrow">↓</div>

            <div className="steam-stage epic-stage-validation">
              <div className="steam-icon-wrap">
                <ValidacaoIcon />
              </div>
              <div>
                <span className="steam-stage-number">3. Identificação da oferta</span>
                <p>
                  Captura <code>offerId</code>, <code>sandboxId</code> e os identificadores
                  necessários para as consultas GraphQL.
                </p>
              </div>
            </div>

            <div className="steam-branches epic-branches">
              <div className="steam-branch steam-branch-valid">
                <span>Identificadores obtidos</span>
              </div>

              <div className="steam-branch-line steam-branch-line-left" />

              <div className="steam-branch steam-branch-fail">
                <span>Falha ou dado incompleto</span>
              </div>

              <div className="steam-branch-line steam-branch-line-right" />
            </div>

            <div className="steam-results epic-results">
              <div className="steam-result-card steam-result-valid">
                <div className="steam-icon-wrap">
                  <GraphqlIcon />
                </div>
                <div>
                  <span className="steam-stage-number">4. Consultas GraphQL</span>
                  <p>
                    Consulta os dados de catálogo e de preço da oferta identificada,
                    reunindo as informações necessárias para a coleta.
                  </p>
                </div>
              </div>

              <div className="steam-result-card steam-result-fallback">
                <div className="steam-icon-wrap">
                  <BrowserIcon />
                </div>
                <div>
                  <span className="steam-stage-number">5. Fallback com navegador</span>
                  <p>
                    Em falhas da etapa principal, extrai nome e preço diretamente
                    dos elementos visíveis da página e marca o resultado para revisão manual.
                  </p>
                </div>
              </div>
            </div>

            <div className="steam-merge-lines">
              <span className="merge-line merge-left" />
              <span className="merge-line merge-right" />
              <span className="merge-arrow">↓</span>
            </div>

            <div className="steam-stage steam-stage-normalize">
              <div className="steam-icon-wrap">
                <CogIcon />
              </div>
              <div>
                <span className="steam-stage-number">6. Normalização dos dados</span>
                <p>
                  Converte os preços para o padrão da aplicação, calcula o desconto
                  e organiza os metadados antes do armazenamento.
                </p>
              </div>
            </div>

            <div className="steam-arrow">↓</div>

            <div className="steam-stage steam-stage-db">
              <div className="steam-icon-wrap">
                <PostgresIcon />
              </div>
              <div>
                <span className="steam-stage-number">7. Armazenamento no PostgreSQL</span>
                <p>
                  Persiste os dados cadastrais e registra o preço no histórico conforme
                  as regras de atualização do sistema.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="visao-secao">
          <div className="visao-cabecalho">
            <span className="eyebrow">FIGURA PARA O TCC</span>
            <h2>Visão compacta para documentação</h2>
            <p>
              Uma versão enxuta da arquitetura, adequada para funcionar como
              figura introdutória antes das explicações detalhadas.
            </p>
          </div>

          <div className="figura-arquitetura">
            <div className="figura-linha">
              <div className="figura-no">Steam / Epic Games Store</div>
              <div className="figura-seta">→</div>
              <div className="figura-no">Coleta</div>
              <div className="figura-seta">→</div>
              <div className="figura-no">PostgreSQL</div>
              <div className="figura-seta">→</div>
              <div className="figura-no">FastAPI</div>
              <div className="figura-seta">→</div>
              <div className="figura-no">React</div>
            </div>
          </div>

          <div className="figura-legenda">
            Figura — Visão simplificada da arquitetura do Comparador.
            <strong>Fonte: Elaborado pelo autor (2026).</strong>
          </div>
        </section>
      </main>
    </div>
  )
}

export default Arquitetura
