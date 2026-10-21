import { useEffect, useMemo, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import CarrosselJogos from '../componentes/CarrosselJogos'
import { API_JOGOS_URL } from '../servicos/api'
import { useTema } from '../contextos/TemaContext'

function Inicio() {
  const navigate = useNavigate()
  const { tema } = useTema()

  const [secoesVitrine, setSecoesVitrine] = useState({ brasileiros: [], comunidade: [], em_alta: [], oportunidades: [] })
  const [jogosBusca, setJogosBusca] = useState([])
  const [jogosBuscaComparacao, setJogosBuscaComparacao] = useState([])
  const [busca, setBusca] = useState('')
  const [buscaComparacao, setBuscaComparacao] = useState('')
  const [jogoComparacao, setJogoComparacao] = useState(null)

  const sugestoesBusca = useMemo(() => {
    const termo = busca.trim().toLowerCase()

    if (!termo) return []

    return [...jogosBusca]
      .filter((jogo) => jogo.nome.toLowerCase().includes(termo))
      .sort((a, b) => {
        const nomeA = a.nome.toLowerCase()
        const nomeB = b.nome.toLowerCase()

        const comecaA = nomeA.startsWith(termo)
        const comecaB = nomeB.startsWith(termo)

        if (comecaA !== comecaB) {
          return comecaA ? -1 : 1
        }

        return nomeA.localeCompare(nomeB, 'pt-BR')
      })
      .slice(0, 6)
  }, [busca, jogosBusca])

  const sugestoesComparacao = useMemo(() => {
    const termo = buscaComparacao.trim().toLowerCase()

    if (!termo) return []

    return [...jogosBuscaComparacao]
      .filter((jogo) => jogo.nome.toLowerCase().includes(termo))
      .sort((a, b) => {
        const nomeA = a.nome.toLowerCase()
        const nomeB = b.nome.toLowerCase()

        const comecaA = nomeA.startsWith(termo)
        const comecaB = nomeB.startsWith(termo)

        if (comecaA !== comecaB) {
          return comecaA ? -1 : 1
        }

        return nomeA.localeCompare(nomeB, 'pt-BR')
      })
      .slice(0, 6)
  }, [buscaComparacao, jogosBuscaComparacao])

  const selecionarJogoComparacao = (jogo) => {
    setJogoComparacao(jogo)
    setBuscaComparacao('')
  }

  const trocarJogoComparacao = () => {
    setJogoComparacao(null)
    setBuscaComparacao('')
  }

  const pesquisarComparacao = (evento) => {
    evento.preventDefault()

    const termo = buscaComparacao.trim().toLowerCase()

    if (!termo) {
      setJogoComparacao(null)
      return
    }

    const jogoExato = jogosBuscaComparacao.find(
      (jogo) => jogo.nome.toLowerCase() === termo
    )

    const jogoEncontrado = jogoExato || sugestoesComparacao[0]

    if (jogoEncontrado) {
      selecionarJogoComparacao(jogoEncontrado)
    } else {
      setJogoComparacao(null)
    }
  }

  const formatarPreco = (preco) => {
    if (preco === null || preco === undefined || Number.isNaN(Number(preco))) {
      return 'Não disponível'
    }

    if (Number(preco) === 0) {
      return 'Grátis'
    }

    return `R$ ${Number(preco).toFixed(2).replace('.', ',')}`
  }

  const precoSteamComparacao = jogoComparacao
    ? jogoComparacao.preco_atual_steam ?? jogoComparacao.preco_base_steam
    : null

  const precoEpicComparacao = jogoComparacao
    ? jogoComparacao.preco_atual_epic ?? jogoComparacao.preco_base_epic
    : null

  const descontoSteamComparacao = Number(jogoComparacao?.desconto_steam || 0)
  const descontoEpicComparacao = Number(jogoComparacao?.desconto_epic || 0)

  const precoNumericoSteam = Number(precoSteamComparacao)
  const precoNumericoEpic = Number(precoEpicComparacao)

  const steamDisponivel =
    precoSteamComparacao !== null &&
    precoSteamComparacao !== undefined &&
    !Number.isNaN(precoNumericoSteam)

  const epicDisponivel =
    precoEpicComparacao !== null &&
    precoEpicComparacao !== undefined &&
    !Number.isNaN(precoNumericoEpic)

  const melhorLojaComparacao =
    steamDisponivel &&
    epicDisponivel &&
    precoNumericoSteam !== precoNumericoEpic
      ? precoNumericoSteam < precoNumericoEpic
        ? 'steam'
        : 'epic'
      : null

  const pesquisar = (evento) => {
    evento.preventDefault()

    const termo = busca.trim()

    if (!termo) {
      navigate('/jogos')
      return
    }

    navigate(`/jogos?busca=${encodeURIComponent(termo)}`)
  }

  const abrirJogo = (id) => {
    navigate(`/jogos/${id}`)
  }




  useEffect(() => {
    let ativo = true

    async function carregarVitrine() {
      try {
        const resposta = await fetch(`${API_JOGOS_URL}/vitrine/secoes`)
        if (!resposta.ok) throw new Error('Não foi possível carregar a vitrine.')
        const dados = await resposta.json()
        if (ativo) setSecoesVitrine({
          brasileiros: dados.brasileiros || [],
          comunidade: dados.comunidade || [],
          em_alta: dados.em_alta || [],
          oportunidades: dados.oportunidades || [],
        })
      } catch (erro) {
        console.error('Erro ao carregar as seções da vitrine:', erro)
      }
    }

    carregarVitrine()
    return () => { ativo = false }
  }, [])

  useEffect(() => {
    async function carregarJogosBusca(termo, setResultado) {
      const texto = termo.trim()

      if (!texto) {
        setResultado([])
        return
      }

      try {
        const resposta = await fetch(
          `${API_JOGOS_URL}/?pagina=1&por_pagina=20&busca=${encodeURIComponent(texto)}&ordenacao=nome`
        )

        if (!resposta.ok) {
          throw new Error('Não foi possível carregar os jogos para a pesquisa.')
        }

        const dados = await resposta.json()
        const lista = Array.isArray(dados) ? dados : dados.jogos || []

        setResultado(
          lista.map((jogo) => ({
            id: jogo.id,
            nome: jogo.nome,
            imagem:
              jogo.url_imagem_steam ||
              jogo.url_imagem_epic ||
              (jogo.steam_id
                ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
                : ''),
            preco_atual_steam: jogo.preco_atual_steam,
            preco_atual_epic: jogo.preco_atual_epic,
            preco_base_steam: jogo.preco_base_steam,
            preco_base_epic: jogo.preco_base_epic,
            desconto_steam: jogo.desconto_steam,
            desconto_epic: jogo.desconto_epic,
          }))
        )
      } catch (erro) {
        console.error('Erro ao carregar jogos para a pesquisa:', erro)
        setResultado([])
      }
    }

    carregarJogosBusca(busca, setJogosBusca)
  }, [busca])

  useEffect(() => {
    async function carregarJogosBuscaComparacao() {
      const termo = buscaComparacao.trim()

      if (!termo) {
        setJogosBuscaComparacao([])
        return
      }

      try {
        const resposta = await fetch(
          `${API_JOGOS_URL}/?pagina=1&por_pagina=20&busca=${encodeURIComponent(termo)}&ordenacao=nome`
        )

        if (!resposta.ok) {
          throw new Error('Não foi possível carregar os jogos para a comparação.')
        }

        const dados = await resposta.json()
        const lista = Array.isArray(dados) ? dados : dados.jogos || []

        setJogosBuscaComparacao(
          lista.map((jogo) => ({
            id: jogo.id,
            nome: jogo.nome,
            imagem:
              jogo.url_imagem_steam ||
              jogo.url_imagem_epic ||
              (jogo.steam_id
                ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
                : ''),
            preco_atual_steam: jogo.preco_atual_steam,
            preco_atual_epic: jogo.preco_atual_epic,
            preco_base_steam: jogo.preco_base_steam,
            preco_base_epic: jogo.preco_base_epic,
            desconto_steam: jogo.desconto_steam,
            desconto_epic: jogo.desconto_epic,
          }))
        )
      } catch (erro) {
        console.error('Erro ao carregar jogos para a comparação:', erro)
        setJogosBuscaComparacao([])
      }
    }

    carregarJogosBuscaComparacao()
  }, [buscaComparacao])

  return (
    <>
      <Cabecalho />

      <main>
        <section className="hero">
          <div className="hero-conteudo">
            <div className="hero-layout">
              <div className="hero-texto">
                <span className="hero-tag">DESCUBRA SEU PRÓXIMO JOGO</span>

                <h1>
                  Jogos incríveis.{' '}
                  <span className="hero-destaque">Preços inteligentes.</span>
                </h1>

                <p>
                  Encontre seus próximos jogos, compare lojas e descubra o melhor momento para comprar.
                </p>

                <form
                  className="barra-pesquisa"
                  onSubmit={pesquisar}
                  autoComplete="off"
                >
                  <span className="icone-pesquisa">⌕</span>

                  <input
                    type="text"
                    value={busca}
                    onChange={(evento) => setBusca(evento.target.value)}
                    placeholder="Pesquise por nome do jogo..."
                    aria-label="Pesquisar jogo"
                    aria-autocomplete="list"
                    aria-controls="sugestoes-pesquisa"
                  />

                  <button type="submit">Pesquisar</button>

                  {busca.trim() && (
                    <div
                      id="sugestoes-pesquisa"
                      className="sugestoes-pesquisa"
                    >
                      {sugestoesBusca.length > 0 ? (
                        sugestoesBusca.map((jogo) => (
                          <button
                            key={jogo.id}
                            type="button"
                            className="sugestao-jogo"
                            onClick={() => abrirJogo(jogo.id)}
                          >
                            {jogo.imagem ? (
                              <img
                                src={jogo.imagem}
                                alt=""
                                className="sugestao-jogo-imagem"
                              />
                            ) : (
                              <div className="sugestao-jogo-imagem sugestao-jogo-imagem-vazia" />
                            )}

                            <span className="sugestao-jogo-nome">
                              {jogo.nome}
                            </span>
                          </button>
                        ))
                      ) : (
                        <div className="sugestao-sem-resultados">
                          Nenhum jogo encontrado.
                        </div>
                      )}
                    </div>
                  )}
                </form>

                <div className="hero-beneficios" aria-label="Recursos do DESCTRL">
                  <span className="hero-beneficio">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M4 19V9" />
                      <path d="M10 19V5" />
                      <path d="M16 19v-7" />
                      <path d="M22 19V3" />
                    </svg>
                    <span>Histórico de preços</span>
                  </span>

                  <span className="hero-beneficio">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="m20.5 13.5-7 7a2 2 0 0 1-2.8 0l-7.2-7.2a2 2 0 0 1-.6-1.4V5a2 2 0 0 1 2-2h6.9a2 2 0 0 1 1.4.6l7.3 7.1a2 2 0 0 1 0 2.8Z" />
                      <circle cx="7.5" cy="7.5" r="1.5" />
                    </svg>
                    <span>Acompanhe promoções</span>
                  </span>

                  <span className="hero-beneficio">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <rect x="3" y="5" width="18" height="14" rx="2" />
                      <path d="M3 10h18" />
                      <path d="M8 15h3" />
                      <path d="M14 15h3" />
                    </svg>
                    <span>Compare as lojas</span>
                  </span>
                </div>
              </div>

            </div>
          </div>
        </section>



        <VitrineBrasileira
          jogos={secoesVitrine.brasileiros}
          destino="/jogos"
        />

        <SecaoJogos
          eyebrow="A COMUNIDADE ESCOLHE"
          titulo="Recomendados pela comunidade"
          jogos={secoesVitrine.comunidade}
          destino="/jogos?filtro=desconto"
        />

        <SecaoJogos
          eyebrow="EM ALTA"
          titulo="Em alta no DESCTRL"
          jogos={secoesVitrine.em_alta}
          destino="/jogos"
        />

        <SecaoJogos
          eyebrow="CURADORIA DESCTRL"
          titulo="Oportunidades de preço"
          jogos={secoesVitrine.oportunidades}
          mostrarDesconto
          destino="/jogos?filtro=desconto"
        />

        <section className="secao secao-comparacao">
          <div className="secao-cabecalho">
            <div>
              <span className="eyebrow">COMPARAÇÃO DE PREÇOS</span>
              <h2>Compare preços antes de decidir</h2>
            </div>
          </div>

          <div className="bloco-explicativo">
            <div className="explicacao">
              <h3>Steam × Epic Games Store</h3>
              <p>
                Pesquise o jogo que você está procurando, compare o preço atual
                nas duas lojas e consulte a tendência de promoções antes de
                comprar.
              </p>

              {jogoComparacao?.imagem && (
                <div className="comparador-imagem-jogo">
                  <img
                    src={jogoComparacao.imagem}
                    alt={jogoComparacao.nome}
                  />
                </div>
              )}

              {!jogoComparacao && (
              <form
                className="comparador-busca"
                onSubmit={pesquisarComparacao}
                autoComplete="off"
              >
                <span className="comparador-busca-icone">⌕</span>

                <input
                  type="text"
                  value={buscaComparacao}
                  onChange={(evento) => setBuscaComparacao(evento.target.value)}
                  placeholder="Pesquise um jogo para comparar..."
                  aria-label="Pesquisar jogo para comparação"
                  aria-autocomplete="list"
                  aria-controls="sugestoes-comparacao"
                />

                <button type="submit">Comparar</button>

                {buscaComparacao.trim() && (
                  <div
                    id="sugestoes-comparacao"
                    className="comparador-sugestoes"
                  >
                    {sugestoesComparacao.length > 0 ? (
                      sugestoesComparacao.map((jogo) => (
                        <button
                          key={jogo.id}
                          type="button"
                          className="comparador-sugestao"
                          onClick={() => selecionarJogoComparacao(jogo)}
                        >
                          {jogo.imagem ? (
                            <img src={jogo.imagem} alt="" />
                          ) : (
                            <span className="comparador-sugestao-imagem-vazia" />
                          )}
                          <span>{jogo.nome}</span>
                        </button>
                      ))
                    ) : (
                      <div className="comparador-sem-resultados">
                        Nenhum jogo encontrado.
                      </div>
                    )}
                  </div>
                )}
              </form>
              )}
            </div>

            <div className="mini-comparacao">
              {jogoComparacao ? (
                <>
                  <div className="comparador-jogo-selecionado">
                    <span>JOGO SELECIONADO</span>
                    <strong>{jogoComparacao.nome}</strong>
                  </div>

                  <div
                    className={`linha-preco ${
                      melhorLojaComparacao === 'steam'
                        ? 'melhor-preco'
                        : ''
                    }`}
                  >
                    <div className="comparador-loja">
                      <span className="plataforma steam">Steam</span>
                      {descontoSteamComparacao > 0 && (
                        <small>{descontoSteamComparacao}% OFF</small>
                      )}
                    </div>
                    <strong>{formatarPreco(precoSteamComparacao)}</strong>
                  </div>

                  <div
                    className={`linha-preco ${
                      melhorLojaComparacao === 'epic'
                        ? 'melhor-preco'
                        : ''
                    }`}
                  >
                    <div className="comparador-loja">
                      <span className="plataforma epic">Epic Games Store</span>
                      {descontoEpicComparacao > 0 && (
                        <small>{descontoEpicComparacao}% OFF</small>
                      )}
                    </div>
                    <strong>{formatarPreco(precoEpicComparacao)}</strong>
                  </div>

                  {melhorLojaComparacao && (
                    <span className="comparador-melhor-preco">
                      Menor preço entre as lojas
                    </span>
                  )}

                  <button
                    type="button"
                    className="comparador-detalhes"
                    onClick={() => navigate(`/jogos/${jogoComparacao.id}`)}
                  >
                    Ver detalhes do jogo →
                  </button>

                  <button
                    type="button"
                    className="comparador-previsao"
                    onClick={() => navigate(`/ofertas?jogo=${encodeURIComponent(jogoComparacao.id)}`)}
                  >
                    Ver previsão de preço →
                  </button>

                  <button
                    type="button"
                    className="comparador-trocar"
                    onClick={trocarJogoComparacao}
                  >
                    Trocar jogo
                  </button>
                </>
              ) : (
                <div className="comparador-vazio">
                  <span>ESCOLHA UM JOGO</span>
                  <strong>Pesquise pelo nome do jogo para comparar as lojas.</strong>
                </div>
              )}
            </div>
          </div>
        </section>


      </main>
    </>
  )
}

function VitrineBrasileira({ jogos = [], destino = '/jogos' }) {
  const [indicePrincipal, setIndicePrincipal] = useState(0)
  const lista = Array.isArray(jogos) ? jogos : []
  const total = lista.length
  const obterJogo = (deslocamento) => total ? lista[(indicePrincipal + deslocamento + total) % total] : null
  const principal = obterJogo(0)
  const secundarios = [obterJogo(1), obterJogo(2)].filter(Boolean)
  const avancar = (direcao) => {
    if (total > 1) setIndicePrincipal((atual) => (atual + direcao + total) % total)
  }

  return (
    <section className="vitrine-brasil" aria-labelledby="titulo-vitrine-brasil">
      <div className="vitrine-brasil-cabecalho">
        <div className="vitrine-brasil-identidade">
          <span className="vitrine-brasil-simbolo" aria-hidden="true">🇧🇷</span>
          <span className="vitrine-brasil-eyebrow">VITRINE ESPECIAL · DESENVOLVIMENTO NACIONAL</span>
        </div>
        <h2 id="titulo-vitrine-brasil">Brasil <span>em jogo</span></h2>
        <p>Histórias, ideias e mundos criados por estúdios brasileiros.</p>
      </div>

      {principal ? (
        <>
          <div className="vitrine-brasil-painel">
            <NavLink to={`/jogos/${principal.id}`} className="vitrine-brasil-principal" aria-label={`Conhecer ${principal.nome}`}>
              {principal.imagem && <img className="vitrine-brasil-imagem" src={principal.imagem} alt="" loading="lazy" decoding="async" />}
              <span className="vitrine-brasil-selo">BRASIL EM JOGO</span>
              <span className="vitrine-brasil-conteudo">
                <span className="vitrine-brasil-chamada">DESTAQUE NACIONAL</span>
                <strong>{principal.nome}</strong>
                <span className="vitrine-brasil-acao">Conhecer jogo <span aria-hidden="true">↗</span></span>
              </span>
            </NavLink>

            <div className="vitrine-brasil-secundarios">
              {secundarios.map((jogo, indice) => (
                <NavLink to={`/jogos/${jogo.id}`} className={`vitrine-brasil-secundario vitrine-brasil-secundario-${indice + 1}`} key={jogo.id} aria-label={`Conhecer ${jogo.nome}`}>
                  {jogo.imagem && <img className="vitrine-brasil-imagem" src={jogo.imagem} alt="" loading="lazy" decoding="async" />}
                  <span className="vitrine-brasil-selo">🇧🇷 NACIONAL</span>
                  <strong>{jogo.nome}</strong>
                  <span className="vitrine-brasil-link">Ver jogo ↗</span>
                </NavLink>
              ))}
            </div>
          </div>

          <div className="vitrine-brasil-rodape">
            <NavLink className="vitrine-brasil-ver-todos" to={destino}>Explorar jogos brasileiros <span aria-hidden="true">→</span></NavLink>
            <div className="vitrine-brasil-navegacao" aria-label="Navegação da vitrine">
              <button type="button" onClick={() => avancar(-1)} disabled={total < 2} aria-label="Jogo brasileiro anterior">‹</button>
              <div className="vitrine-brasil-indicadores" aria-label={`Jogo ${indicePrincipal + 1} de ${total}`}>
                {lista.slice(0, Math.min(total, 8)).map((jogo, indice) => (
                  <button key={jogo.id} type="button" className={indice === indicePrincipal % Math.min(total, 8) ? 'ativo' : ''} onClick={() => setIndicePrincipal(indice)} aria-label={`Mostrar ${jogo.nome}`} aria-current={indice === indicePrincipal ? 'true' : undefined} />
                ))}
              </div>
              <button type="button" onClick={() => avancar(1)} disabled={total < 2} aria-label="Próximo jogo brasileiro">›</button>
            </div>
          </div>
        </>
      ) : (
        <div className="vitrine-brasil-vazia">A seleção de jogos brasileiros estará disponível aqui em breve.</div>
      )}
    </section>
  )
}

function SecaoJogos({
  eyebrow,
  titulo,
  jogos,
  mostrarDesconto = false,
  destino = '/jogos',
  classeExtra = '',
}) {
  return (
    <section className={`secao secao-catalogo ${classeExtra}`.trim()}>
      <div className="secao-cabecalho">
        <div className="secao-titulo">
          <span className="eyebrow">{eyebrow}</span>
          <h2>{titulo}</h2>
        </div>

        <NavLink className="link-secao" to={destino}>
          Ver todos
        </NavLink>
      </div>

      <CarrosselJogos
        jogos={jogos}
        mostrarDesconto={mostrarDesconto}
      />
    </section>
  )
}

export default Inicio