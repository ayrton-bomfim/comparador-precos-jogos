import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import CardJogo from '../componentes/CardJogo'
import { API_JOGOS_URL } from '../servicos/api'

function formatarPreco(preco, gratuito = false, plataformaDisponivel = false) {
  if (preco === null || preco === undefined) {
    return gratuito && plataformaDisponivel ? 'Grátis' : '—'
  }

  if (Number(preco) === 0) return 'Grátis'

  return Number(preco).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
}

function adaptarJogo(jogo) {
  const gratuito =
    typeof jogo.genero === 'string' &&
    jogo.genero.toLowerCase().includes('grátis para jogar')

  const steamDisponivel = Boolean(jogo.steam_id)

  const epicDisponivel =
    jogo.epic_id !== null &&
    jogo.epic_id !== undefined &&
    jogo.epic_id !== 'EXCLUSIVO_STEAM'

  const descontoSteam = Number(jogo.desconto_steam || 0)
  const descontoEpic = Number(jogo.desconto_epic || 0)

  return {
    id: jogo.id,
    nome: jogo.nome,
    genero: jogo.genero,
    imagem:
      jogo.url_imagem_steam ||
      jogo.url_imagem_epic ||
      (jogo.steam_id
        ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
        : null),
    precoSteam:
      jogo.preco_atual_steam ?? jogo.preco_base_steam ?? (gratuito && steamDisponivel ? 0 : null),
    precoEpic:
      jogo.preco_atual_epic ?? jogo.preco_base_epic ?? (gratuito && epicDisponivel ? 0 : null),
    steam: formatarPreco(
      jogo.preco_atual_steam ?? jogo.preco_base_steam,
      gratuito,
      steamDisponivel
    ),
    epic: formatarPreco(
      jogo.preco_atual_epic ?? jogo.preco_base_epic,
      gratuito,
      epicDisponivel
    ),
    desconto: Math.max(descontoSteam, descontoEpic),
  }
}

function Jogos() {
  const [searchParams, setSearchParams] = useSearchParams()

  const [tema, setTema] = useState(() => {
    const salvo = localStorage.getItem('tema-comparador')
    return salvo === 'escuro' ? 'escuro' : 'claro'
  })

  const [jogos, setJogos] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState(null)
  const busca = searchParams.get('busca') || ''

  const filtrosValidos = ['todos', 'steam', 'epic', 'desconto', 'gratis']
  const ordenacoesValidas = [
    'nome',
    'menor-preco',
    'maior-preco',
    'desconto',
  ]

  const filtroParam = searchParams.get('filtro')
  const filtro = filtrosValidos.includes(filtroParam)
    ? filtroParam
    : 'todos'

  const ordenacaoParam = searchParams.get('ordenacao')
  const ordenacao = ordenacoesValidas.includes(ordenacaoParam)
    ? ordenacaoParam
    : 'nome'

  const paginaParam = Number(searchParams.get('pagina'))
  const pagina =
    Number.isInteger(paginaParam) && paginaParam > 0
      ? paginaParam
      : 1

  const porPagina = 12

  useEffect(() => {
    localStorage.setItem('tema-comparador', tema)
  }, [tema])

  useEffect(() => {
    async function carregarJogos() {
      try {
        setCarregando(true)
        setErro(null)

        const resposta = await fetch(`${API_JOGOS_URL}/`)

        if (!resposta.ok) {
          throw new Error(`Erro ao carregar jogos: ${resposta.status}`)
        }

        const dados = await resposta.json()
        setJogos(dados.map(adaptarJogo))
      } catch (erroCarregamento) {
        console.error(erroCarregamento)
        setErro('Não foi possível carregar os jogos do banco de dados.')
      } finally {
        setCarregando(false)
      }
    }

    carregarJogos()
  }, [])

  const jogosFiltrados = useMemo(() => {
    const termo = busca.trim().toLowerCase()

    const resultado = jogos.filter((jogo) => {
      const correspondeBusca =
        !termo || jogo.nome.toLowerCase().includes(termo)

      const correspondeFiltro =
        filtro === 'todos' ||
        (filtro === 'steam' && jogo.steam !== '—') ||
        (filtro === 'epic' && jogo.epic !== '—') ||
        (filtro === 'desconto' && jogo.desconto > 0) ||
        (filtro === 'gratis' &&
          typeof jogo.genero === 'string' &&
          jogo.genero.toLowerCase().includes('grátis para jogar'))

      return correspondeBusca && correspondeFiltro
    })

    const preco = (valor) => {
      if (!valor || valor === '—') return null
      if (valor === 'Grátis') return 0

      return Number(
        valor
          .replace('R$', '')
          .replace(/\./g, '')
          .replace(',', '.')
          .trim()
      )
    }

    const menorPreco = (jogo) => {
      const precos = [preco(jogo.steam), preco(jogo.epic)]
        .filter((valor) => valor !== null)

      return precos.length > 0 ? Math.min(...precos) : Infinity
    }

    const maiorPreco = (jogo) => {
      const precos = [preco(jogo.steam), preco(jogo.epic)]
        .filter((valor) => valor !== null)

      return precos.length > 0 ? Math.max(...precos) : -Infinity
    }

    return [...resultado].sort((a, b) => {
      if (ordenacao === 'nome') {
        return a.nome.localeCompare(b.nome, 'pt-BR')
      }

      if (ordenacao === 'menor-preco') {
        return menorPreco(a) - menorPreco(b)
      }

      if (ordenacao === 'maior-preco') {
        return maiorPreco(b) - maiorPreco(a)
      }

      if (ordenacao === 'desconto') {
        return (b.desconto || 0) - (a.desconto || 0)
      }

      return 0
    })
  }, [jogos, busca, filtro, ordenacao])

  const totalPaginas = Math.max(
    1,
    Math.ceil(jogosFiltrados.length / porPagina)
  )

  const paginaAtual = Math.min(Math.max(1, pagina), totalPaginas)

  const jogosPagina = jogosFiltrados.slice(
    (paginaAtual - 1) * porPagina,
    paginaAtual * porPagina
  )

  const atualizarParametros = (alteracoes) => {
    const parametros = new URLSearchParams(window.location.search)

    Object.entries(alteracoes).forEach(([chave, valor]) => {
      if (
        valor === null ||
        valor === undefined ||
        valor === '' ||
        (chave === 'filtro' && valor === 'todos') ||
        (chave === 'ordenacao' && valor === 'nome') ||
        (chave === 'pagina' && Number(valor) === 1)
      ) {
        parametros.delete(chave)
      } else {
        parametros.set(chave, String(valor))
      }
    })

    setSearchParams(parametros, { replace: true })
  }

  const alterarFiltro = (novoFiltro) => {
    atualizarParametros({
      filtro: novoFiltro,
      pagina: 1,
    })
  }

  const pesquisar = (evento) => {
    evento.preventDefault()
    atualizarParametros({ pagina: 1 })
  }

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho tema={tema} setTema={setTema} />

      <main className="pagina-jogos">
        <section className="cabecalho-jogos">
          <div>
            <span className="eyebrow">CATÁLOGO</span>
            <h1>Jogos</h1>
            <p>
              Explore os jogos disponíveis e compare os preços entre Steam e
              Epic Games Store.
            </p>
          </div>
        </section>

        <section className="controles-jogos">
          <form className="pesquisa-jogos" onSubmit={pesquisar}>
            <span className="icone-pesquisa">⌕</span>

            <input
              type="text"
              value={busca}
              onChange={(evento) => {
                atualizarParametros({
                  busca: evento.target.value,
                  pagina: 1,
                })
              }}
              placeholder="Pesquisar por nome do jogo..."
              aria-label="Pesquisar jogo"
            />

            <button type="submit">Pesquisar</button>
          </form>

          <div className="filtros-jogos">
            <div className="grupo-filtros">
              <span>Filtrar:</span>

              {[
                ['todos', 'Todos'],
                ['steam', 'Steam'],
                ['epic', 'Epic Games'],
                ['desconto', 'Com desconto'],
                ['gratis', 'Grátis'],
              ].map(([valor, texto]) => (
                <button
                  key={valor}
                  type="button"
                  className={filtro === valor ? 'filtro-ativo' : ''}
                  onClick={() => alterarFiltro(valor)}
                >
                  {texto}
                </button>
              ))}
            </div>

            <label className="ordenacao-jogos">
              <span>Ordenar:</span>

              <select
                value={ordenacao}
                onChange={(evento) => {
                  atualizarParametros({
                    ordenacao: evento.target.value,
                    pagina: 1,
                  })
                }}
              >
                <option value="nome">Nome</option>
                <option value="menor-preco">Menor preço</option>
                <option value="maior-preco">Maior preço</option>
                <option value="desconto">Maior desconto</option>
              </select>
            </label>
          </div>
        </section>

        <section className="resultado-jogos">
          <div className="resultado-cabecalho">
            <span>
              {carregando
                ? 'Carregando jogos...'
                : `${jogosFiltrados.length} ${
                    jogosFiltrados.length === 1
                      ? 'jogo encontrado'
                      : 'jogos encontrados'
                  }`}
            </span>
          </div>

          {erro ? (
            <div className="sem-resultados">
              <strong>Não foi possível carregar os jogos</strong>
              <span>{erro}</span>
            </div>
          ) : jogosPagina.length > 0 ? (
            <div className="grade-jogos pagina-grade-jogos">
              {jogosPagina.map((jogo) => (
                <CardJogo
                  key={jogo.id}
                  jogo={jogo}
                  mostrarDesconto
                />
              ))}
            </div>
          ) : !carregando ? (
            <div className="sem-resultados">
              <strong>Nenhum jogo encontrado</strong>
              <span>
                Tente alterar a busca ou remover algum filtro.
              </span>
            </div>
          ) : null}

          {totalPaginas > 1 && (
            <div className="paginacao-jogos">
              <button
                type="button"
                onClick={() =>
                  atualizarParametros({
                    pagina: Math.max(1, paginaAtual - 1),
                  })
                }
                disabled={paginaAtual === 1}
              >
                ‹
              </button>

              {Array.from(
                { length: totalPaginas },
                (_, indice) => indice + 1
              ).map((numero) => (
                <button
                  key={numero}
                  type="button"
                  className={paginaAtual === numero ? 'pagina-ativa' : ''}
                  onClick={() =>
                    atualizarParametros({ pagina: numero })
                  }
                >
                  {numero}
                </button>
              ))}

              <button
                type="button"
                onClick={() =>
                  atualizarParametros({
                    pagina: Math.min(totalPaginas, paginaAtual + 1),
                  })
                }
                disabled={paginaAtual === totalPaginas}
              >
                ›
              </button>
            </div>
          )}
        </section>
      </main>

      <footer>
        <strong>Comparador de Preços</strong>
        <span>Steam × Epic Games Store</span>
      </footer>
    </div>
  )
}

export default Jogos
