import { useEffect, useMemo, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import CarrosselJogos from '../componentes/CarrosselJogos'
import { API_JOGOS_URL } from '../servicos/api'

function Inicio() {
  const navigate = useNavigate()
  const [tema, setTema] = useState(() => {
    const salvo = localStorage.getItem('tema-comparador')
    return salvo === 'escuro' ? 'escuro' : 'claro'
  })

  const [jogosDestaque, setJogosDestaque] = useState([])
  const [jogosGratuitos, setJogosGratuitos] = useState([])
  const [ofertas, setOfertas] = useState([])
  const [jogosBusca, setJogosBusca] = useState([])
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
  }, [buscaComparacao, jogosBusca])

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

    const jogoExato = jogosBusca.find(
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
    async function carregarJogosDestaque() {
      try {
        const resposta = await fetch(`${API_JOGOS_URL}/`)

        if (!resposta.ok) {
          throw new Error('Não foi possível carregar os jogos em destaque.')
        }

        const dados = await resposta.json()

        const jogosOrdenados = [...dados]
          .sort(
            (a, b) =>
              Number(b.visualizacoes || 0) -
              Number(a.visualizacoes || 0) ||
              a.nome.localeCompare(b.nome)
          )
          .slice(0, 10)

        const jogosFormatados = jogosOrdenados.map((jogo) => {
          const precoSteam =
            jogo.preco_atual_steam ?? jogo.preco_base_steam
          const precoEpic =
            jogo.preco_atual_epic ?? jogo.preco_base_epic

          return {
            id: jogo.id,
            nome: jogo.nome,
            imagem:
              jogo.url_imagem_steam ||
              (jogo.steam_id
                ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
                : ''),
            steam:
              precoSteam === null || precoSteam === undefined
                ? '—'
                : Number(precoSteam) === 0
                  ? 'Grátis'
                  : `R$ ${Number(precoSteam).toFixed(2).replace('.', ',')}`,
            epic:
              precoEpic === null || precoEpic === undefined
                ? '—'
                : Number(precoEpic) === 0
                  ? 'Grátis'
                  : `R$ ${Number(precoEpic).toFixed(2).replace('.', ',')}`,
          }
        })

        setJogosDestaque(jogosFormatados)
      } catch (erro) {
        console.error('Erro ao carregar jogos em destaque:', erro)
        setJogosDestaque([])
      }
    }

    carregarJogosDestaque()
  }, [])

  useEffect(() => {
    async function carregarJogosGratuitos() {
      try {
        const resposta = await fetch(`${API_JOGOS_URL}/`)

        if (!resposta.ok) {
          throw new Error('Não foi possível carregar os jogos gratuitos.')
        }

        const dados = await resposta.json()

        const jogosFiltrados = dados
          .filter(
            (jogo) =>
              typeof jogo.genero === 'string' &&
              jogo.genero.toLowerCase().includes('grátis para jogar')
          )
          .map((jogo) => {
            const gratuito = typeof jogo.genero === 'string' &&
              jogo.genero.toLowerCase().includes('grátis para jogar')

            const precoSteam =
              jogo.preco_atual_steam ?? jogo.preco_base_steam
            const precoEpic =
              jogo.preco_atual_epic ?? jogo.preco_base_epic

            return {
              id: jogo.id,
              nome: jogo.nome,
              imagem:
                jogo.url_imagem_steam ||
                jogo.url_imagem_epic ||
                (jogo.steam_id
                  ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
                  : ''),
              steam:
                precoSteam === null || precoSteam === undefined
                  ? gratuito && jogo.steam_id
                    ? 'Grátis'
                    : 'Não disponível'
                  : Number(precoSteam) === 0
                    ? 'Grátis'
                    : `R$ ${Number(precoSteam).toFixed(2).replace('.', ',')}`,
              epic:
                precoEpic === null || precoEpic === undefined
                  ? gratuito && jogo.epic_id
                    ? 'Grátis'
                    : 'Não disponível'
                  : Number(precoEpic) === 0
                    ? 'Grátis'
                    : `R$ ${Number(precoEpic).toFixed(2).replace('.', ',')}`,
            }
          })

        setJogosGratuitos(jogosFiltrados)
      } catch (erro) {
        console.error('Erro ao carregar jogos gratuitos:', erro)
        setJogosGratuitos([])
      }
    }

    carregarJogosGratuitos()
  }, [])

  useEffect(() => {
    async function carregarOfertas() {
      try {
        const resposta = await fetch(`${API_JOGOS_URL}/`)

        if (!resposta.ok) {
          throw new Error('Não foi possível carregar as ofertas.')
        }

        const dados = await resposta.json()

        const jogosEmOferta = dados
          .map((jogo) => {
            const descontoSteam = Number(jogo.desconto_steam || 0)
            const descontoEpic = Number(jogo.desconto_epic || 0)
            const maiorDesconto = Math.max(descontoSteam, descontoEpic)

            const precoSteam =
              jogo.preco_atual_steam ?? jogo.preco_base_steam
            const precoEpic =
              jogo.preco_atual_epic ?? jogo.preco_base_epic

            const formatarPreco = (preco) => {
              if (preco === null || preco === undefined) return 'Não disponível'
              if (Number(preco) === 0) return 'Grátis'

              return `R$ ${Number(preco)
                .toFixed(2)
                .replace('.', ',')}`
            }

            return {
              id: jogo.id,
              nome: jogo.nome,
              imagem:
                jogo.url_imagem_steam ||
                jogo.url_imagem_epic ||
                (jogo.steam_id
                  ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
                  : ''),
              steam: formatarPreco(precoSteam),
              epic: formatarPreco(precoEpic),
              desconto: maiorDesconto,
            }
          })
          .filter((jogo) => jogo.desconto > 0)
          .sort((a, b) => b.desconto - a.desconto || a.nome.localeCompare(b.nome))
          .slice(0, 10)

        setOfertas(jogosEmOferta)
      } catch (erro) {
        console.error('Erro ao carregar ofertas:', erro)
        setOfertas([])
      }
    }

    carregarOfertas()
  }, [])

  useEffect(() => {
    async function carregarJogosBusca() {
      try {
        const resposta = await fetch(`${API_JOGOS_URL}/`)

        if (!resposta.ok) {
          throw new Error('Não foi possível carregar os jogos para a pesquisa.')
        }

        const dados = await resposta.json()

        setJogosBusca(
          dados.map((jogo) => ({
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
        setJogosBusca([])
      }
    }

    carregarJogosBusca()
  }, [])

  useEffect(() => {
    localStorage.setItem('tema-comparador', tema)
  }, [tema])

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho tema={tema} setTema={setTema} />

      <main>
        <section className="hero">
          <div className="hero-conteudo">
            <span className="hero-tag">COMPARADOR DE PREÇOS</span>
            <h1>Compare preços e acompanhe o melhor momento para comprar</h1>
            <p>
              Consulte o histórico
              de preços e acompanhe tendências de promoções para cada jogo
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
          </div>
        </section>

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

        <SecaoJogos
          eyebrow="EXPLORE"
          titulo="Jogos em destaque"
          jogos={jogosDestaque}
          destino="/jogos"
        />

        <SecaoJogos
          eyebrow="OPORTUNIDADES"
          titulo="Ofertas"
          jogos={ofertas}
          mostrarDesconto
          destino="/jogos?filtro=desconto"
        />

        <SecaoJogos
          eyebrow="SEM CUSTO"
          titulo="Jogos gratuitos"
          jogos={jogosGratuitos}
          destino="/jogos?filtro=gratis"
        />


      </main>

      <footer>
        <strong>Comparador de Preços</strong>
        <span>Steam × Epic Games Store</span>
      </footer>
    </div>
  )
}

function SecaoJogos({
  eyebrow,
  titulo,
  jogos,
  mostrarDesconto = false,
  destino = '/jogos',
}) {
  return (
    <section className="secao secao-catalogo">
      <div className="secao-cabecalho">
        <div>
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