import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useSearchParams } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import CardJogo from '../componentes/CardJogo'
import { useAuth } from '../contextos/AuthContext'
import { API_JOGOS_URL, API_URL } from '../servicos/api'

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
      jogo.url_imagem_epic ||
      jogo.url_imagem_steam ||
      (jogo.steam_id
        ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
        : null),

    imagemEpic: jogo.url_imagem_epic || null,

    imagemSteamFallback:
      jogo.url_imagem_steam ||
      (jogo.steam_id
        ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
        : null),

    precoSteam:
      jogo.preco_atual_steam ??
      jogo.preco_base_steam ??
      (gratuito && steamDisponivel ? 0 : null),

    precoEpic:
      jogo.preco_atual_epic ??
      jogo.preco_base_epic ??
      (gratuito && epicDisponivel ? 0 : null),

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

const MOTIVOS_AUDITORIA = [
  'Conteúdo sensível',
  'Fora do catálogo',
  'Duplicado ou redundante',
  'Indisponível ou removido',
  'Problemas de qualidade ou integridade',
  'Outros',
]

function Jogos() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { isAdmin, token } = useAuth()
  const tokenAtualRef = useRef(token)
  useEffect(() => { tokenAtualRef.current = token }, [token])
  const [idsFavoritos, setIdsFavoritos] = useState(() => new Set())
  const [favoritosEmAtualizacao, setFavoritosEmAtualizacao] = useState(() => new Set())

  const [tema, setTema] = useState(() => {
    const salvo = localStorage.getItem('tema-comparador')
    return salvo === 'escuro' ? 'escuro' : 'claro'
  })

  const [jogos, setJogos] = useState([])
  const [totalJogos, setTotalJogos] = useState(0)
  const [totalPaginasApi, setTotalPaginasApi] = useState(1)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState(null)
  const [jogosSelecionados, setJogosSelecionados] = useState(() => new Set())
  const [modalLoteAberto, setModalLoteAberto] = useState(false)
  const [motivoLote, setMotivoLote] = useState('')
  const [observacaoLote, setObservacaoLote] = useState('')
  const [processandoLote, setProcessandoLote] = useState(false)
  const [progressoLote, setProgressoLote] = useState({ concluidos: 0, total: 0 })
  const [resultadoLote, setResultadoLote] = useState(null)
  const [statusAuditoriaLote, setStatusAuditoriaLote] = useState({})
  const [modalVitrineAberto, setModalVitrineAberto] = useState(false)
  const [tipoVitrine, setTipoVitrine] = useState('oportunidade')
  const [processandoVitrine, setProcessandoVitrine] = useState(false)
  const [resultadoVitrine, setResultadoVitrine] = useState(null)
  const [filtrosAbertos, setFiltrosAbertos] = useState(false)

  const busca = searchParams.get('busca') || ''
  const [buscaDigitada, setBuscaDigitada] = useState(busca)

  // Mantém o campo alinhado com voltar/avançar do navegador e links externos.
  useEffect(() => {
    // Ao apagar até 2 caracteres, a URL é limpa, mas o texto digitado permanece.
    if (buscaDigitada.trim().length < 3 && !busca) return
    setBuscaDigitada(busca)
  }, [busca])

  // A busca dinâmica só começa com 3 caracteres, seguindo o padrão do cabeçalho.
  // 100 ms evita consultas a cada tecla; termos menores limpam o filtro anterior.
  useEffect(() => {
    const termo = buscaDigitada.trim()
    const parametros = new URLSearchParams(window.location.search)

    if (termo.length < 3) {
      if (parametros.has('busca')) {
        parametros.delete('busca')
        parametros.delete('pagina')
        setSearchParams(parametros, { replace: true })
      }
      return undefined
    }

    const timeout = window.setTimeout(() => {
      const atuais = new URLSearchParams(window.location.search)
      if (atuais.get('busca') === termo && !atuais.has('pagina')) return
      atuais.set('busca', termo)
      atuais.delete('pagina')
      setSearchParams(atuais, { replace: true })
    }, 100)

    return () => window.clearTimeout(timeout)
  }, [buscaDigitada, setSearchParams])

  const filtrosValidos = [
    'brasileiros',
    'todos',
    'steam',
    'epic',
    'desconto',
    'gratis',
  ]

  const ordenacoesValidas = [
    'nome',
    'menor-preco',
    'maior-preco',
    'desconto',
    'mais-vistos',
  ]

  // Os filtros escolhidos ficam guardados apenas durante a sessão do navegador.
  // Ao encerrar a sessão, o catálogo volta aos padrões do DESCTRL.
  const [filtroInicialSessao] = useState(() => {
    try {
      const salvo = sessionStorage.getItem('desctrl-catalogo-filtro')
      return filtrosValidos.includes(salvo) ? salvo : 'brasileiros'
    } catch {
      return 'brasileiros'
    }
  })

  const [ordenacaoInicialSessao] = useState(() => {
    try {
      const salva = sessionStorage.getItem('desctrl-catalogo-ordenacao')
      return ordenacoesValidas.includes(salva) ? salva : 'mais-vistos'
    } catch {
      return 'mais-vistos'
    }
  })

  const filtroParam = searchParams.get('filtro')

  const filtro = filtrosValidos.includes(filtroParam)
    ? filtroParam
    : filtroInicialSessao

  const ordenacaoParam = searchParams.get('ordenacao')

  const ordenacao = ordenacoesValidas.includes(ordenacaoParam)
    ? ordenacaoParam
    : ordenacaoInicialSessao

  const paginaParam = Number(searchParams.get('pagina'))

  const pagina =
    Number.isInteger(paginaParam) && paginaParam > 0
      ? paginaParam
      : 1

  const porPagina = 20

  useEffect(() => {
    localStorage.setItem('tema-comparador', tema)
  }, [tema])

  useEffect(() => {
    try {
      sessionStorage.setItem('desctrl-catalogo-filtro', filtro)
      sessionStorage.setItem('desctrl-catalogo-ordenacao', ordenacao)
    } catch (erro) {
      console.warn('Não foi possível guardar os filtros desta sessão.', erro)
    }
  }, [filtro, ordenacao])

  useEffect(() => {
    let ativo = true
    const tokenDaSessao = token
    // Limpa estado vinculado à sessão anterior antes de consultar a nova.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setIdsFavoritos(new Set())
    setFavoritosEmAtualizacao(new Set())
    async function carregarIdsFavoritos() {
      if (!tokenDaSessao) return
      try {
        const resposta = await fetch(`${API_URL}/api/favoritos/ids`, {
          headers: { Authorization: `Bearer ${tokenDaSessao}` },
        })
        if (!resposta.ok) return
        const dados = await resposta.json()
        if (ativo && tokenAtualRef.current === tokenDaSessao) setIdsFavoritos(new Set(dados.ids || []))
      } catch (erro) {
        if (ativo) console.warn('Não foi possível carregar os favoritos.', erro)
      }
    }
    carregarIdsFavoritos()
    return () => { ativo = false }
  }, [token])

  useEffect(() => {
    // Limpa seleções e dados de curadoria ao trocar de conta/permissão.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setJogosSelecionados(new Set())
    setModalLoteAberto(false)
    setMotivoLote('')
    setObservacaoLote('')
    setResultadoLote(null)
    setProgressoLote({ concluidos: 0, total: 0 })
    setStatusAuditoriaLote({})
  }, [token, isAdmin])

  const alternarFavorito = async (jogoId) => {
    const tokenDaSessao = token
    if (!tokenDaSessao || favoritosEmAtualizacao.has(jogoId)) return
    const eraFavorito = idsFavoritos.has(jogoId)
    setFavoritosEmAtualizacao(atual => new Set(atual).add(jogoId))
    try {
      const resposta = await fetch(`${API_URL}/api/favoritos/${jogoId}`, {
        method: eraFavorito ? 'DELETE' : 'POST',
        headers: { Authorization: `Bearer ${tokenDaSessao}` },
      })
      if (!resposta.ok) throw new Error('Falha ao atualizar favorito')
      if (tokenAtualRef.current === tokenDaSessao) {
        setIdsFavoritos(atual => {
          const novo = new Set(atual)
          if (eraFavorito) novo.delete(jogoId)
          else novo.add(jogoId)
          return novo
        })
      }
    } catch (erro) {
      if (tokenAtualRef.current === tokenDaSessao) {
        console.error(erro)
        window.alert('Não foi possível atualizar seus favoritos. Tente novamente.')
      }
    } finally {
      if (tokenAtualRef.current === tokenDaSessao) {
        setFavoritosEmAtualizacao(atual => {
          const novo = new Set(atual)
          novo.delete(jogoId)
          return novo
        })
      }
    }
  }

  useEffect(() => {
    // Uma seleção nunca deve sobreviver à mudança da lista visível.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setJogosSelecionados(new Set())
  }, [pagina, busca, filtro, ordenacao])

  useEffect(() => {
    let ativo = true
    const controller = new AbortController()
    async function carregarJogos() {
      try {
        setCarregando(true)
        setErro(null)

        const parametros = new URLSearchParams({
          pagina: String(pagina),
          por_pagina: String(porPagina),
          busca,
          filtro,
          ordenacao,
        })

        const resposta = await fetch(
          `${API_JOGOS_URL}/?${parametros.toString()}`,
          { signal: controller.signal }
        )

        if (!resposta.ok) {
          throw new Error(
            `Erro ao carregar jogos: ${resposta.status}`
          )
        }

        const dados = await resposta.json()

        const lista = Array.isArray(dados)
          ? dados
          : dados.jogos || []

        if (!ativo) return
        setJogos(lista.map(adaptarJogo))

        setTotalJogos(
          Array.isArray(dados)
            ? lista.length
            : dados.total || 0
        )

        setTotalPaginasApi(
          Array.isArray(dados)
            ? 1
            : dados.total_paginas || 1
        )
      } catch (erroCarregamento) {
        if (!ativo || erroCarregamento.name === 'AbortError') return
        console.error(erroCarregamento)

        setErro(
          'Não foi possível carregar os jogos do banco de dados.'
        )
      } finally {
        if (ativo) setCarregando(false)
      }
    }

    carregarJogos()
    return () => {
      ativo = false
      controller.abort()
    }
  }, [pagina, porPagina, busca, filtro, ordenacao])

  /*
   * A filtragem e a ordenação agora são feitas pelo backend.
   * Portanto, o React recebe somente os 20 jogos da página atual.
   */
  const totalPaginas = totalPaginasApi

  const paginaAtual = Math.min(
    Math.max(1, pagina),
    totalPaginas
  )

  const jogosPagina = jogos

  const paginasVisiveis = useMemo(() => {
    if (totalPaginas <= 7) {
      return Array.from(
        { length: totalPaginas },
        (_, indice) => indice + 1
      )
    }

    const primeiraPaginaVisivel = Math.min(
      Math.max(1, paginaAtual - 3),
      totalPaginas - 6
    )

    return Array.from(
      { length: 7 },
      (_, indice) => primeiraPaginaVisivel + indice
    )
  }, [paginaAtual, totalPaginas])

  const atualizarParametros = (alteracoes) => {
    const parametros = new URLSearchParams(
      window.location.search
    )

    Object.entries(alteracoes).forEach(
      ([chave, valor]) => {
        if (
          valor === null ||
          valor === undefined ||
          valor === '' ||
          (chave === 'pagina' && Number(valor) === 1)
        ) {
          parametros.delete(chave)
        } else {
          parametros.set(chave, String(valor))
        }
      }
    )

    setSearchParams(parametros, {
      replace: true,
    })
  }

  const alterarFiltro = (novoFiltro) => {
    atualizarParametros({
      filtro: novoFiltro,
      pagina: 1,
    })
  }

  const pesquisar = (evento) => {
    evento.preventDefault()
    const termo = buscaDigitada.trim()
    atualizarParametros({
      busca: termo || null,
      pagina: 1,
    })
  }

  const todosJogosPaginaSelecionados =
    jogosPagina.length > 0 &&
    jogosPagina.every((jogo) => jogosSelecionados.has(jogo.id))

  const alternarSelecaoJogo = (jogoId) => {
    setJogosSelecionados((selecionadosAtuais) => {
      const novosSelecionados = new Set(selecionadosAtuais)
      if (novosSelecionados.has(jogoId)) {
        novosSelecionados.delete(jogoId)
      } else {
        novosSelecionados.add(jogoId)
      }
      return novosSelecionados
    })
  }

  const alternarSelecaoPagina = () => {
    if (todosJogosPaginaSelecionados) {
      setJogosSelecionados(new Set())
      return
    }
    setJogosSelecionados(new Set(jogosPagina.map((jogo) => jogo.id)))
  }

  const abrirModalLote = () => {
    if (!isAdmin || !token || jogosSelecionados.size === 0) return
    setMotivoLote('')
    setObservacaoLote('')
    setResultadoLote(null)
    setProgressoLote({ concluidos: 0, total: jogosSelecionados.size })
    setModalLoteAberto(true)
  }

  const fecharModalLote = () => {
    if (processandoLote) return
    setModalLoteAberto(false)
    setMotivoLote('')
    setObservacaoLote('')
    setResultadoLote(null)
  }

  const confirmarAuditoriaLote = async () => {
    if (!isAdmin || !token || !motivoLote || processandoLote) return
    if (motivoLote === 'Outros' && !observacaoLote.trim()) return

    const alvos = jogosPagina.filter((jogo) => jogosSelecionados.has(jogo.id))
    if (alvos.length === 0) {
      setResultadoLote({ total: 0, enviados: 0, jaNaFila: 0, falhas: [] })
      return
    }

    setProcessandoLote(true)
    setResultadoLote(null)
    setProgressoLote({ concluidos: 0, total: alvos.length })

    const resultados = new Array(alvos.length)
    let proximoIndice = 0
    let concluidos = 0

    const trabalhador = async () => {
      while (true) {
        const indice = proximoIndice
        proximoIndice += 1
        if (indice >= alvos.length) return

        const jogo = alvos[indice]
        try {
          const resposta = await fetch(`${API_URL}/api/admin/curadoria/`, {
            method: 'POST',
            headers: {
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              jogo_id: jogo.id,
              motivo: motivoLote,
              observacao: motivoLote === 'Outros' ? observacaoLote.trim() : '',
            }),
          })

          const dados = await resposta.json().catch(() => ({}))
          const detalhe = String(dados.detail || '').trim()

          if (resposta.status === 201) {
            resultados[indice] = { id: jogo.id, nome: jogo.nome, tipo: 'enviado' }
          } else if (
            resposta.status === 409 &&
            detalhe.toLowerCase().includes('já está aguardando análise')
          ) {
            resultados[indice] = {
              id: jogo.id,
              nome: jogo.nome,
              tipo: 'jaNaFila',
              detalhe,
            }
          } else {
            resultados[indice] = {
              id: jogo.id,
              nome: jogo.nome,
              tipo: 'falha',
              detalhe: detalhe || `Erro HTTP ${resposta.status}`,
            }
          }
        } catch (erroEnvio) {
          resultados[indice] = {
            id: jogo.id,
            nome: jogo.nome,
            tipo: 'falha',
            detalhe: erroEnvio instanceof Error ? erroEnvio.message : 'Falha de comunicação',
          }
        } finally {
          concluidos += 1
          setProgressoLote({ concluidos, total: alvos.length })
        }
      }
    }

    try {
      const quantidadeTrabalhadores = Math.min(5, alvos.length)
      await Promise.all(
        Array.from({ length: quantidadeTrabalhadores }, () => trabalhador())
      )

      const enviados = resultados.filter((item) => item?.tipo === 'enviado')
      const jaNaFila = resultados.filter((item) => item?.tipo === 'jaNaFila')
      const falhas = resultados.filter((item) => item?.tipo === 'falha')
      const finalizadosIds = new Set([...enviados, ...jaNaFila].map((item) => item.id))

      setStatusAuditoriaLote((anteriores) => {
        const atualizados = { ...anteriores }
        enviados.forEach((item) => { atualizados[item.id] = 'enviado' })
        jaNaFila.forEach((item) => { atualizados[item.id] = 'existente' })
        return atualizados
      })

      setJogosSelecionados((selecionadosAtuais) => {
        const restantes = new Set(selecionadosAtuais)
        finalizadosIds.forEach((id) => restantes.delete(id))
        return restantes
      })

      setResultadoLote({
        total: alvos.length,
        enviados: enviados.length,
        jaNaFila: jaNaFila.length,
        falhas,
      })
    } finally {
      setProcessandoLote(false)
    }
  }

  const abrirModalVitrine = () => {
    if (!isAdmin || !token || jogosSelecionados.size === 0) return
    setResultadoVitrine(null)
    setTipoVitrine('oportunidade')
    setModalVitrineAberto(true)
  }

  const fecharModalVitrine = () => {
    if (processandoVitrine) return
    setModalVitrineAberto(false)
    setResultadoVitrine(null)
  }

  const confirmarVitrine = async () => {
    if (!isAdmin || !token || jogosSelecionados.size === 0 || processandoVitrine) return
    setProcessandoVitrine(true)
    setResultadoVitrine(null)
    try {
      const resposta = await fetch(`${API_URL}/api/admin/curadoria/vitrine/lote`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          tipo: tipoVitrine,
          jogo_ids: Array.from(jogosSelecionados),
        }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || `Erro HTTP ${resposta.status}`)
      setResultadoVitrine(dados)
      const idsAdicionados = new Set((dados.adicionados || []).map(item => item.jogo_id))
      setJogosSelecionados(atuais => new Set([...atuais].filter(id => !idsAdicionados.has(id))))
    } catch (erro) {
      setResultadoVitrine({ erro: erro.message })
    } finally {
      setProcessandoVitrine(false)
    }
  }

  const alvoModalLote =
    typeof document !== 'undefined'
      ? document.querySelector('.pagina-jogos')?.closest('.app') || document.body
      : null

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho
        tema={tema}
        setTema={setTema}
      />

      <main className="pagina-jogos">

        <section className="cabecalho-jogos">
          <div>
            <span className="eyebrow">
              CATÁLOGO
            </span>

            <h1>Jogos</h1>

            <p>
              Explore os jogos disponíveis e compare os
              preços entre Steam e Epic Games Store.
            </p>
          </div>
        </section>

        <section className="controles-jogos">
          <form
            className="pesquisa-jogos"
            onSubmit={pesquisar}
          >
            <span className="icone-pesquisa">⌕</span>
            <input
              type="text"
              value={buscaDigitada}
              onChange={(evento) => setBuscaDigitada(evento.target.value)}
              placeholder="Pesquisar por nome do jogo..."
              aria-label="Pesquisar jogo"
            />
            <button type="submit">Pesquisar</button>
          </form>

          <div className="atalho-filtros-jogos">
            <div className="resumo-filtros-ativos" aria-live="polite">
              <div className="titulo-resumo-filtros">
                <span className="icone-resumo-filtros" aria-hidden="true">☷</span>
                <strong>Filtros ativos</strong>
              </div>
              <div className="etiquetas-resumo-filtros">
                {filtro !== 'todos' && (
                  <span className="etiqueta-filtro-ativo">
                    <span aria-hidden="true">✓</span>
                    {filtro === 'brasileiros' ? 'Estúdios brasileiros' :
                      filtro === 'steam' ? 'Steam' :
                      filtro === 'epic' ? 'Epic Games' :
                      filtro === 'desconto' ? 'Com desconto' : 'Grátis'}
                  </span>
                )}
                <span className="etiqueta-ordenacao-ativa">
                  <span aria-hidden="true">↕</span>
                  {ordenacao === 'mais-vistos' ? 'Mais vistos' :
                    ordenacao === 'nome' ? 'Nome' :
                    ordenacao === 'menor-preco' ? 'Menor preço' :
                    ordenacao === 'maior-preco' ? 'Maior preço' : 'Maior desconto'}
                </span>
                {filtro === 'todos' && (
                  <span className="texto-sem-restricao">Sem filtro de loja ou origem</span>
                )}
              </div>
              <p className="descricao-resumo-filtros">
                {filtro === 'brasileiros'
                  ? 'Exibindo jogos de estúdios brasileiros.'
                  : filtro === 'todos'
                    ? 'Exibindo jogos de todas as origens disponíveis no catálogo.'
                    : filtro === 'steam'
                      ? 'Exibindo jogos disponíveis na Steam.'
                      : filtro === 'epic'
                        ? 'Exibindo jogos disponíveis na Epic Games Store.'
                        : filtro === 'desconto'
                          ? 'Exibindo jogos que estão com desconto.'
                          : 'Exibindo jogos gratuitos.'}
              </p>
            </div>
            <button
              type="button"
              className="botao-abrir-filtros"
              onClick={() => setFiltrosAbertos(true)}
              aria-haspopup="dialog"
              aria-expanded={filtrosAbertos}
            >
              ⚙ Filtros e ordenação
            </button>
          </div>
        </section>

        {filtrosAbertos && (
          <div
            className="camada-filtros-jogos"
            onMouseDown={(evento) => {
              if (evento.target === evento.currentTarget) setFiltrosAbertos(false)
            }}
          >
            <section
              className="painel-filtros-jogos"
              role="dialog"
              aria-modal="true"
              aria-labelledby="titulo-filtros-jogos"
            >
              <header className="topo-filtros-jogos">
                <div>
                  <span className="eyebrow">PERSONALIZE SUA BUSCA</span>
                  <h2 id="titulo-filtros-jogos">Filtros e ordenação</h2>
                </div>
                <button
                  type="button"
                  className="fechar-filtros-jogos"
                  onClick={() => setFiltrosAbertos(false)}
                  aria-label="Fechar filtros"
                >×</button>
              </header>

              <div className="conteudo-filtros-jogos">
                <div className="grupo-filtros grupo-filtros-modal">
                  <span>Filtrar jogos</span>
                  {[
                    ['brasileiros', 'Estúdios brasileiros'],
                    ['todos', 'Todos os jogos'],
                    ['steam', 'Steam'],
                    ['epic', 'Epic Games'],
                    ['desconto', 'Com desconto'],
                    ['gratis', 'Grátis'],
                  ].map(([valor, texto]) => (
                    <button
                      key={valor}
                      type="button"
                      className={filtro === valor ? 'filtro-ativo' : ''}
                      aria-pressed={filtro === valor}
                      onClick={() => alterarFiltro(valor)}
                    >{texto}</button>
                  ))}
                </div>

                <label className="ordenacao-jogos ordenacao-modal">
                  <span>Ordenar por</span>
                  <select
                    value={ordenacao}
                    onChange={(evento) => atualizarParametros({
                      ordenacao: evento.target.value,
                      pagina: 1,
                    })}
                  >
                    <option value="mais-vistos">Mais vistos</option>
                    <option value="nome">Nome</option>
                    <option value="menor-preco">Menor preço</option>
                    <option value="maior-preco">Maior preço</option>
                    <option value="desconto">Maior desconto</option>
                  </select>
                </label>
              </div>

              <footer className="rodape-filtros-jogos">
                <button
                  type="button"
                  className="limpar-filtros-jogos"
                  onClick={() => atualizarParametros({ filtro: 'brasileiros', ordenacao: 'mais-vistos', pagina: 1 })}
                >Restaurar padrão</button>
                <button
                  type="button"
                  className="aplicar-filtros-jogos"
                  onClick={() => setFiltrosAbertos(false)}
                >Ver resultados</button>
              </footer>
            </section>
          </div>
        )}

        <section className="resultado-jogos">

          <div className="resultado-cabecalho">
            <span>
              {carregando
                ? 'Carregando jogos...'
                : `${totalJogos} ${
                    totalJogos === 1
                      ? 'jogo encontrado'
                      : 'jogos encontrados'
                  }`}
            </span>
          </div>

          {isAdmin && token && !erro && jogosPagina.length > 0 && (
            <div className="barra-selecao-jogos">
              <label className="selecao-pagina-jogos">
                <input
                  type="checkbox"
                  checked={todosJogosPaginaSelecionados}
                  onChange={alternarSelecaoPagina}
                  aria-label="Selecionar todos os jogos desta página"
                />
                <span>Selecionar página ({jogosPagina.length})</span>
              </label>

              <div className="acoes-selecao-jogos">
                <span className="contador-selecao-jogos">
                  {jogosSelecionados.size} selecionado(s)
                </span>
                {jogosSelecionados.size > 0 && (
                  <button
                    type="button"
                    className="botao-limpar-selecao-jogos"
                    onClick={() => setJogosSelecionados(new Set())}
                  >
                    Limpar
                  </button>
                )}
                <button
                  type="button"
                  className="botao-auditoria-lote"
                  onClick={abrirModalLote}
                  disabled={jogosSelecionados.size === 0}
                >
                  Auditar selecionados
                </button>
                <button
                  type="button"
                  className="botao-auditoria-lote botao-vitrine-lote"
                  onClick={abrirModalVitrine}
                  disabled={jogosSelecionados.size === 0}
                >
                  Adicionar à vitrine
                </button>
              </div>
            </div>
          )}

          {erro ? (

            <div className="sem-resultados">

              <strong>
                Não foi possível carregar os jogos
              </strong>

              <span>
                {erro}
              </span>

            </div>

          ) : jogosPagina.length > 0 ? (

            <div className="grade-jogos pagina-grade-jogos">

              {jogosPagina.map((jogo) => (
                <CardJogo
                  key={jogo.id}
                  jogo={jogo}
                  mostrarDesconto
                  modoSelecao={isAdmin && Boolean(token)}
                  selecionado={jogosSelecionados.has(jogo.id)}
                  onAlternarSelecao={alternarSelecaoJogo}
                  statusAuditoriaExterno={statusAuditoriaLote[jogo.id] || null}
                  favorito={idsFavoritos.has(jogo.id)}
                  onAlternarFavorito={alternarFavorito}
                />
              ))}

            </div>

          ) : !carregando ? (

            <div className="sem-resultados">

              <strong>
                Nenhum jogo encontrado
              </strong>

              <span>
                Tente alterar a busca ou remover algum filtro.
              </span>

            </div>

          ) : null}

          {totalPaginas > 1 && (

            <div
              className="paginacao-jogos"
              aria-label="Paginação do catálogo"
            >

              <button
                type="button"
                className="paginacao-extremo"
                onClick={() =>
                  atualizarParametros({
                    pagina: 1,
                  })
                }
                disabled={paginaAtual === 1}
                aria-label="Ir para a primeira página"
                title="Primeira página"
              >
                «
              </button>

              <button
                type="button"
                className="paginacao-adjacente"
                onClick={() =>
                  atualizarParametros({
                    pagina: Math.max(
                      1,
                      paginaAtual - 1
                    ),
                  })
                }
                disabled={paginaAtual === 1}
                aria-label="Ir para a página anterior"
                title="Página anterior"
              >
                ‹
              </button>

              {paginasVisiveis.map((numero) => (
                <button
                  key={numero}
                  type="button"
                  className={
                    paginaAtual === numero
                      ? 'pagina-ativa'
                      : ''
                  }
                  onClick={() =>
                    atualizarParametros({
                      pagina: numero,
                    })
                  }
                  aria-current={
                    paginaAtual === numero
                      ? 'page'
                      : undefined
                  }
                  aria-label={`Ir para a página ${numero}`}
                >
                  {numero}
                </button>
              ))}

              <button
                type="button"
                className="paginacao-adjacente"
                onClick={() =>
                  atualizarParametros({
                    pagina: Math.min(
                      totalPaginas,
                      paginaAtual + 1
                    ),
                  })
                }
                disabled={
                  paginaAtual === totalPaginas
                }
                aria-label="Ir para a próxima página"
                title="Próxima página"
              >
                ›
              </button>

              <button
                type="button"
                className="paginacao-extremo"
                onClick={() =>
                  atualizarParametros({
                    pagina: totalPaginas,
                  })
                }
                disabled={
                  paginaAtual === totalPaginas
                }
                aria-label="Ir para a última página"
                title="Última página"
              >
                »
              </button>

            </div>

          )}

        </section>

      </main>
      {modalVitrineAberto && alvoModalLote && createPortal(
        <div
          className="curadoria-modal-overlay"
          role="presentation"
          onMouseDown={(evento) => {
            if (evento.target === evento.currentTarget) fecharModalVitrine()
          }}
        >
          <div className="curadoria-modal modal-auditoria-lote" role="dialog" aria-modal="true" aria-labelledby="vitrine-lote-titulo">
            <div className="curadoria-modal-cabecalho">
              <div>
                <span className="curadoria-status">GERENCIAMENTO DA VITRINE</span>
                <h2 id="vitrine-lote-titulo">Adicionar jogos à página inicial</h2>
              </div>
              <button type="button" className="curadoria-modal-fechar" onClick={fecharModalVitrine} disabled={processandoVitrine} aria-label="Fechar">×</button>
            </div>
            {!resultadoVitrine ? (
              <>
                <p>Você selecionou <strong>{jogosSelecionados.size} jogo(s)</strong>. Escolha a seção de destino.</p>
                <label className="curadoria-modal-label" htmlFor="tipo-vitrine-lote">Seção da vitrine</label>
                <select id="tipo-vitrine-lote" className="curadoria-modal-select" value={tipoVitrine} onChange={e => setTipoVitrine(e.target.value)} disabled={processandoVitrine}>
                  <option value="oportunidade">Oportunidades de preço</option>
                  <option value="jogo_brasileiro">Brasil em jogo</option>
                </select>
                {tipoVitrine === 'jogo_brasileiro' && <p>Somente jogos cujo desenvolvedor já esteja cadastrado como estúdio brasileiro serão adicionados.</p>}
                {tipoVitrine === 'oportunidade' && <p>Somente jogos com desconto válido registrado no histórico serão adicionados.</p>}
                {processandoVitrine && <p role="status">Salvando seleções...</p>}
                <div className="curadoria-modal-acoes">
                  <button type="button" className="botao-modal-cancelar" onClick={fecharModalVitrine} disabled={processandoVitrine}>Cancelar</button>
                  <button type="button" className="botao-modal-confirmar botao-modal-aprovar" onClick={confirmarVitrine} disabled={processandoVitrine}>
                    {processandoVitrine ? 'Salvando...' : 'Confirmar seleção'}
                  </button>
                </div>
              </>
            ) : (
              <>
                {resultadoVitrine.erro ? (
                  <p role="alert">{resultadoVitrine.erro}</p>
                ) : (
                  <>
                    <p><strong>{(resultadoVitrine.adicionados || []).length}</strong> jogo(s) adicionado(s) à vitrine.</p>
                    {(resultadoVitrine.ignorados || []).length > 0 && (
                      <div className="resultado-auditoria-lote">
                        <strong>{resultadoVitrine.ignorados.length} jogo(s) não foram adicionados</strong>
                        <ul>{resultadoVitrine.ignorados.map(item => <li key={item.jogo_id}>Jogo #{item.jogo_id}: {item.motivo}</li>)}</ul>
                      </div>
                    )}
                  </>
                )}
                <div className="curadoria-modal-acoes">
                  <button type="button" className="botao-modal-confirmar botao-modal-aprovar" onClick={fecharModalVitrine}>Fechar</button>
                </div>
              </>
            )}
          </div>
        </div>,
        alvoModalLote
      )}
      {modalLoteAberto && alvoModalLote && createPortal(
        <div
          className="curadoria-modal-overlay"
          role="presentation"
          onMouseDown={(evento) => {
            if (evento.target === evento.currentTarget) fecharModalLote()
          }}
        >
          <div
            className="curadoria-modal modal-auditoria-lote"
            role="dialog"
            aria-modal="true"
            aria-labelledby="auditoria-lote-titulo"
            onClick={(evento) => evento.stopPropagation()}
          >
            <div className="curadoria-modal-cabecalho">
              <div>
                <span className="curadoria-status">AUDITORIA EM LOTE</span>
                <h2 id="auditoria-lote-titulo">Enviar jogos para auditoria</h2>
              </div>
              <button
                type="button"
                className="curadoria-modal-fechar"
                onClick={fecharModalLote}
                disabled={processandoLote}
                aria-label="Fechar"
              >
                ×
              </button>
            </div>

            {!resultadoLote ? (
              <>
                <p>
                  Você selecionou <strong>{jogosSelecionados.size} jogo(s)</strong>.
                  Todos receberão o mesmo motivo de auditoria.
                </p>

                <label className="curadoria-modal-label" htmlFor="motivo-auditoria-lote">
                  Motivo da auditoria
                </label>
                <select
                  id="motivo-auditoria-lote"
                  className="curadoria-modal-select"
                  value={motivoLote}
                  onChange={(evento) => {
                    setMotivoLote(evento.target.value)
                    if (evento.target.value !== 'Outros') setObservacaoLote('')
                  }}
                  disabled={processandoLote}
                >
                  <option value="" disabled>Selecione um motivo...</option>
                  {MOTIVOS_AUDITORIA.map((motivo) => (
                    <option key={motivo} value={motivo}>{motivo}</option>
                  ))}
                </select>

                {motivoLote === 'Outros' && (
                  <div className="curadoria-modal-outros">
                    <label className="curadoria-modal-label" htmlFor="observacao-auditoria-lote">
                      Explique o motivo
                    </label>
                    <textarea
                      id="observacao-auditoria-lote"
                      className="curadoria-modal-textarea"
                      value={observacaoLote}
                      onChange={(evento) => setObservacaoLote(evento.target.value)}
                      rows={4}
                      maxLength={1000}
                      placeholder="Descreva por que esses jogos devem ser auditados..."
                      disabled={processandoLote}
                    />
                    <small className="curadoria-modal-contador">
                      {observacaoLote.length}/1000
                    </small>
                  </div>
                )}

                {processandoLote && (
                  <div className="progresso-auditoria-lote" role="status" aria-live="polite">
                    <span>Processando {progressoLote.concluidos} de {progressoLote.total}...</span>
                    <div className="trilho-progresso-auditoria-lote">
                      <div
                        className="preenchimento-progresso-auditoria-lote"
                        style={{ width: `${progressoLote.total ? (progressoLote.concluidos / progressoLote.total) * 100 : 0}%` }}
                      />
                    </div>
                    <small>São enviadas até 5 requisições simultaneamente.</small>
                  </div>
                )}

                <div className="curadoria-modal-acoes">
                  <button
                    type="button"
                    className="botao-modal-cancelar"
                    onClick={fecharModalLote}
                    disabled={processandoLote}
                  >
                    Cancelar
                  </button>
                  <button
                    type="button"
                    className="botao-modal-confirmar botao-modal-aprovar"
                    onClick={confirmarAuditoriaLote}
                    disabled={
                      !motivoLote ||
                      processandoLote ||
                      (motivoLote === 'Outros' && !observacaoLote.trim())
                    }
                  >
                    {processandoLote ? 'Enviando...' : `Confirmar ${jogosSelecionados.size} jogo(s)`}
                  </button>
                </div>
              </>
            ) : (
              <>
                <div className="resultado-auditoria-lote" role="status" aria-live="polite">
                  <strong>Processamento concluído</strong>
                  <p>
                    {resultadoLote.enviados} enviado(s), {resultadoLote.jaNaFila} já aguardavam análise e {resultadoLote.falhas.length} falharam.
                  </p>
                  {resultadoLote.falhas.length > 0 && (
                    <div className="falhas-auditoria-lote">
                      <span>Os jogos abaixo permanecem selecionados para nova tentativa:</span>
                      <ul>
                        {resultadoLote.falhas.map((falha) => (
                          <li key={falha.id}>
                            <strong>{falha.nome}:</strong> {falha.detalhe}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
                <div className="curadoria-modal-acoes">
                  <button
                    type="button"
                    className="botao-modal-confirmar botao-modal-aprovar"
                    onClick={fecharModalLote}
                  >
                    Fechar
                  </button>
                </div>
              </>
            )}
          </div>
        </div>,
        alvoModalLote
      )}
    </div>
  )
}

export default Jogos