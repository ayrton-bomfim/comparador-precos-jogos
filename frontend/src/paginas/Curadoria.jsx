import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import { API_BASE, useAuth } from '../contextos/AuthContext'
import './Curadoria.css'

const MOTIVOS_APROVACAO = [
  'Dentro do escopo do catálogo',
  'Informações validadas',
  'Conteúdo considerado adequado',
  'Teste e validação',
  'Outros',
]

const MOTIVOS_AUDITORIA = [
  'Conteúdo sensível',
  'Fora do catálogo',
  'Duplicado ou redundante',
  'Indisponível ou removido',
  'Problemas de qualidade ou integridade',
  'Outros',
]

const ITENS_POR_PAGINA_SENSIVEL = 50
const ITENS_POR_PAGINA_LISTAS = 50
const ITENS_POR_PAGINA_VITRINE = 50
const ITENS_POR_PAGINA_FEEDBACK = 50

function extrairPrioridade(observacao) {
  const texto = String(observacao || '')
  const correspondencia = texto.match(/Prioridade de revisão:\s*(P[1-5])\s*-\s*([^\r\n]+)/i)
  if (!correspondencia) return null

  const codigo = correspondencia[1].toUpperCase()
  const descricao = correspondencia[2].trim()
  return { codigo, rotulo: `${codigo} - ${descricao}` }
}

function BadgePrioridade({ observacao }) {
  const prioridade = extrairPrioridade(observacao)
  if (!prioridade) return null

  return (
    <span className={`curadoria-prioridade curadoria-prioridade-${prioridade.codigo.toLowerCase()}`}>
      {prioridade.rotulo}
    </span>
  )
}

function PaginacaoCuradoria({ total, pagina, tamanhoPagina, onMudarPagina, rotulo }) {
  const totalPaginas = Math.max(1, Math.ceil(total / tamanhoPagina))
  if (total <= tamanhoPagina) return null

  const inicio = (pagina - 1) * tamanhoPagina + 1
  const fim = Math.min(pagina * tamanhoPagina, total)

  return (
    <nav className="curadoria-paginacao-sensivel" aria-label={rotulo}>
      <span>
        Exibindo {inicio.toLocaleString('pt-BR')} a {fim.toLocaleString('pt-BR')} de {total.toLocaleString('pt-BR')}
      </span>
      <div>
        <button type="button" onClick={() => onMudarPagina(pagina - 1)} disabled={pagina <= 1}>
          Anterior
        </button>
        <strong>Página {pagina} de {totalPaginas}</strong>
        <button type="button" onClick={() => onMudarPagina(pagina + 1)} disabled={pagina >= totalPaginas}>
          Próxima
        </button>
      </div>
    </nav>
  )
}

function normalizarImagens(item, incluirGaleria = true) {
  const imagens = incluirGaleria && Array.isArray(item.imagens) ? item.imagens : []
  const resultado = []
  const vistos = new Set()

  for (const imagem of imagens) {
    const url = typeof imagem === 'string' ? imagem : imagem?.url
    if (!url || vistos.has(url)) continue

    vistos.add(url)
    resultado.push({
      url,
      tipo: typeof imagem === 'object' ? imagem?.tipo : null,
    })
  }

  // Antes do clique, mantém somente as capas que já vieram do catálogo.
  // As imagens extras salvas na galeria só são exibidas após consulta explícita.
  const capas = [
    { url: item.imagem_steam, tipo: 'Capa Steam' },
    { url: item.imagem_epic, tipo: 'Capa Epic' },
  ]

  for (const capa of capas) {
    if (capa.url && !vistos.has(capa.url)) {
      vistos.add(capa.url)
      resultado.unshift(capa)
    }
  }

  return resultado
}

function obterUrlSteam(item) {
  const url = String(item?.url_steam || '').trim()

  // Prioriza a URL direta já cadastrada. URLs de busca não contam como link direto.
  if (url && !/\/search(?:\/|\?)/i.test(url)) {
    return url
  }

  const steamId = String(item?.steam_id || '').trim()
  if (/^\d+$/.test(steamId)) {
    return `https://store.steampowered.com/app/${steamId}/`
  }

  return ''
}

function obterUrlEpic(item) {
  const url = String(item?.url_epic || '').trim()
  if (url) return url

  const epicId = String(item?.epic_id || '').trim()
  if (epicId) {
    return `https://store.epicgames.com/pt-BR/p/${epicId}`
  }

  return ''
}

function GaleriaCuradoria({
  item,
  imagemBorrada = false,
  onCarregarMidias,
  midiasCarregando = false,
  midiasConsultadas = false,
  erroMidias = '',
}) {
  const imagens = useMemo(
    () => normalizarImagens(item, midiasConsultadas),
    [item, midiasConsultadas]
  )
  const [selecaoImagem, setSelecaoImagem] = useState({ itemId: item.id, indice: 0 })
  const indice = selecaoImagem.itemId === item.id ? selecaoImagem.indice : 0
  const selecionarImagem = (novoIndice) => setSelecaoImagem({ itemId: item.id, indice: novoIndice })

  const imagemPrincipal = imagens[indice]?.url || item.imagem_epic || item.imagem_steam

  return (
    <div className="curadoria-galeria">
      <div className="curadoria-imagem-principal">
        {imagemPrincipal ? (
          <img
            src={imagemPrincipal}
            alt={`Imagem de ${item.nome}`}
            className={imagemBorrada ? 'imagem-borrada' : ''}
          />
        ) : (
          <div className="curadoria-card-sem-imagem">LOJA</div>
        )}

        {imagemBorrada && imagemPrincipal && (
          <div className="curadoria-aviso-imagem-sensivel" aria-hidden="true">
            <div className="curadoria-aviso-imagem-icone">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M2.5 12C4.7 7.7 8.1 5.5 12 5.5C15.9 5.5 19.3 7.7 21.5 12C19.3 16.3 15.9 18.5 12 18.5C8.1 18.5 4.7 16.3 2.5 12Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.8"/>
                <path d="M4 4L20 20" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <strong>CONTEÚDO SENSÍVEL</strong>
            <span>Imagem ocultada por segurança</span>
          </div>
        )}

        {midiasConsultadas && imagens.length > 1 && (
          <span className="curadoria-contador-imagens">
            {indice + 1}/{imagens.length}
          </span>
        )}
      </div>

      {midiasConsultadas && imagens.length > 1 && (
        <div className="curadoria-miniaturas" aria-label={`Imagens de ${item.nome}`}>
          {imagens.map((imagem, index) => (
            <button
              type="button"
              key={`${imagem.url}-${index}`}
              className={index === indice ? 'ativa' : ''}
              onClick={() => selecionarImagem(index)}
              title={imagem.tipo || `Imagem ${index + 1}`}
              aria-label={`Mostrar imagem ${index + 1}`}
            >
              <img
                src={imagem.url}
                alt=""
                loading="lazy"
                className={imagemBorrada ? 'imagem-borrada' : ''}
              />
            </button>
          ))}
        </div>
      )}

      {typeof onCarregarMidias === 'function' && (
        <div className="curadoria-carregar-galeria">
          {erroMidias && <span className="curadoria-erro-galeria" role="alert">{erroMidias}</span>}
          {midiasConsultadas ? (
            <span className="curadoria-status-galeria">
              {imagens.length > 1 ? 'Galeria carregada' : 'Nenhuma imagem adicional encontrada'}
            </span>
          ) : (
            <button
              type="button"
              className="botao-carregar-galeria"
              onClick={onCarregarMidias}
              disabled={midiasCarregando}
            >
              {midiasCarregando ? 'Buscando imagens...' : erroMidias ? 'Tentar novamente' : 'Carregar galeria'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function Curadoria() {
  const { token, isAdmin, carregando } = useAuth()

  const [pendentes, setPendentes] = useState([])
  const [totalPendentes, setTotalPendentes] = useState(0)
  const [totalPendentesFiltrados, setTotalPendentesFiltrados] = useState(0)
  const [paginaPendentes, setPaginaPendentes] = useState(1)
  const [buscaPendentesTexto, setBuscaPendentesTexto] = useState('')
  const [buscaPendentes, setBuscaPendentes] = useState('')
  const [buscaAprovadosTexto, setBuscaAprovadosTexto] = useState('')
  const [buscaAprovados, setBuscaAprovados] = useState('')
  const [buscaExcluidosTexto, setBuscaExcluidosTexto] = useState('')
  const [buscaExcluidos, setBuscaExcluidos] = useState('')
  const [totalItensStatus, setTotalItensStatus] = useState(0)
  const [totalAprovados, setTotalAprovados] = useState(0)
  const [totalExcluidos, setTotalExcluidos] = useState(0)
  const [totalVitrine, setTotalVitrine] = useState(0)
  const [totalFeedbackPendentes, setTotalFeedbackPendentes] = useState(0)
  const [paginaStatus, setPaginaStatus] = useState(1)
  // A API entrega somente a página solicitada, em vez de enviar toda a fila ao navegador.
  const [conteudosSensiveis, setConteudosSensiveis] = useState([])
  const [totalConteudosSensiveis, setTotalConteudosSensiveis] = useState(0)
  const [paginaSensivel, setPaginaSensivel] = useState(1)
  const [filtroTextoSensivel, setFiltroTextoSensivel] = useState('')
  const [termoBuscaSensivel, setTermoBuscaSensivel] = useState('')
  const [itensStatus, setItensStatus] = useState([])
  const [busca, setBusca] = useState('')
  const [motivoFiltro, setMotivoFiltro] = useState('')
  const [resultados, setResultados] = useState([])
  const [resultadoSelecionado, setResultadoSelecionado] = useState(-1)
  const [aba, setAba] = useState('pendentes')
  const [feedbackItens, setFeedbackItens] = useState([])
  const [feedbackTotal, setFeedbackTotal] = useState(0)
  const [paginaFeedback, setPaginaFeedback] = useState(1)
  const [feedbackStatus, setFeedbackStatus] = useState('pendente')
  const [feedbackCarregando, setFeedbackCarregando] = useState(false)
  const [feedbackErro, setFeedbackErro] = useState('')
  const [feedbackAcaoId, setFeedbackAcaoId] = useState(null)
  const [itensVitrine, setItensVitrine] = useState([])
  const [paginaVitrine, setPaginaVitrine] = useState(1)
  const [filtroVitrine, setFiltroVitrine] = useState('')
  const [termoVitrine, setTermoVitrine] = useState('')
  const [carregandoVitrine, setCarregandoVitrine] = useState(false)
  const [erroVitrine, setErroVitrine] = useState('')
  const [carregandoLista, setCarregandoLista] = useState(false)
  const [carregandoStatus, setCarregandoStatus] = useState(false)
  const [carregandoBusca, setCarregandoBusca] = useState(false)
  const [acaoId, setAcaoId] = useState(null)
  const [mensagem, setMensagem] = useState('')
  const [erro, setErro] = useState('')
  const [exclusaoPendente, setExclusaoPendente] = useState(null)
  const [motivoExclusao, setMotivoExclusao] = useState('')
  const [observacaoExclusao, setObservacaoExclusao] = useState('')
  const [aprovacaoPendente, setAprovacaoPendente] = useState(null)
  const [motivoAprovacao, setMotivoAprovacao] = useState('')
  const [observacaoAprovacao, setObservacaoAprovacao] = useState('')
  const [itensSelecionados, setItensSelecionados] = useState(() => new Set())
  const [acaoLote, setAcaoLote] = useState(null)
  const [motivoLote, setMotivoLote] = useState('')
  const [observacaoLote, setObservacaoLote] = useState('')
  const [processandoLote, setProcessandoLote] = useState(false)
  const [progressoLote, setProgressoLote] = useState({ concluidos: 0, total: 0 })
  const [imagensSensiveisBorradas, setImagensSensiveisBorradas] = useState(true)
  // A galeria só é consultada após um clique explícito no cartão.
  const [midiasEmCarregamento, setMidiasEmCarregamento] = useState(() => new Set())
  const [midiasConsultadas, setMidiasConsultadas] = useState(() => new Set())
  const [errosMidias, setErrosMidias] = useState(() => new Map())
  const idsMidiaEmRequisicao = useRef(new Set())
  const sequenciaSessaoMidia = useRef(0)
  const sequenciaConteudoSensivel = useRef(0)
  const sequenciaPendentes = useRef(0)
  const sequenciaStatus = useRef(0)

  const getHeaders = useCallback(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token])

  // Atualiza os contadores de todas as abas ao entrar na Curadoria, sem exigir que cada aba seja aberta.
  const atualizarContadoresAbas = useCallback(async () => {
    if (!isAdmin || !token) return
    const headers = getHeaders()
    const buscarJson = async (url) => {
      const resposta = await fetch(url, { headers })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || `Falha ao consultar ${url}`)
      return dados
    }
    const paginaMinima = (rota) => `${API_BASE}${rota}?page=1&page_size=1`
    const consultas = await Promise.allSettled([
      buscarJson(paginaMinima('/api/admin/curadoria/pendentes')),
      buscarJson(paginaMinima('/api/admin/curadoria/conteudo-sensivel')),
      buscarJson(paginaMinima('/api/admin/curadoria/status/aprovado')),
      buscarJson(paginaMinima('/api/admin/curadoria/status/excluido')),
      buscarJson(`${API_BASE}/api/admin/curadoria/vitrine`),
      buscarJson(`${API_BASE}/api/admin/feedback?status=pendente&page=1&page_size=1`),
    ])
    const totalDaResposta = (resultado, fallback = 0) => {
      if (resultado.status !== 'fulfilled') return fallback
      const dados = resultado.value
      if (Array.isArray(dados)) return dados.length
      return Number(dados.total_geral ?? dados.total ?? fallback)
    }
    if (consultas[0].status === 'fulfilled') setTotalPendentes(totalDaResposta(consultas[0]))
    if (consultas[1].status === 'fulfilled') setTotalConteudosSensiveis(totalDaResposta(consultas[1]))
    if (consultas[2].status === 'fulfilled') setTotalAprovados(totalDaResposta(consultas[2]))
    if (consultas[3].status === 'fulfilled') setTotalExcluidos(totalDaResposta(consultas[3]))
    if (consultas[4].status === 'fulfilled') setTotalVitrine(totalDaResposta(consultas[4]))
    if (consultas[5].status === 'fulfilled') setTotalFeedbackPendentes(totalDaResposta(consultas[5]))
  }, [getHeaders, isAdmin, token])

  useEffect(() => {
    atualizarContadoresAbas()
  }, [atualizarContadoresAbas])

  const atualizarMidias = useCallback(async (item) => {
    const resposta = await fetch(`${API_BASE}/api/admin/curadoria/${item.id}/midias`, {
      method: 'POST',
      headers: getHeaders(),
    })
    const dados = await resposta.json().catch(() => ({}))

    if (!resposta.ok) {
      throw new Error(dados.detail || 'Não foi possível carregar a galeria deste jogo.')
    }

    return dados
  }, [getHeaders])

  const solicitarMidias = useCallback(async (item) => {
    const id = item.id
    if (idsMidiaEmRequisicao.current.has(id) || midiasConsultadas.has(id)) return

    const sessaoDaRequisicao = sequenciaSessaoMidia.current
    idsMidiaEmRequisicao.current.add(id)
    setMidiasEmCarregamento((atuais) => new Set(atuais).add(id))
    setErrosMidias((atuais) => {
      const proximo = new Map(atuais)
      proximo.delete(id)
      return proximo
    })

    try {
      const atualizado = await atualizarMidias(item)
      if (sessaoDaRequisicao !== sequenciaSessaoMidia.current) return

      if (atualizado && typeof atualizado === 'object') {
        const aplicarAtualizacao = (setter) => setter((atuais) =>
          atuais.map((registro) => registro.id === id ? { ...registro, ...atualizado } : registro)
        )
        aplicarAtualizacao(setPendentes)
        aplicarAtualizacao(setConteudosSensiveis)
        aplicarAtualizacao(setItensStatus)
      }
      setMidiasConsultadas((atuais) => new Set(atuais).add(id))
    } catch (error) {
      if (sessaoDaRequisicao === sequenciaSessaoMidia.current) {
        setErrosMidias((atuais) => new Map(atuais).set(id, error?.message || 'Falha ao carregar a galeria.'))
      }
    } finally {
      if (sessaoDaRequisicao === sequenciaSessaoMidia.current) {
        idsMidiaEmRequisicao.current.delete(id)
        setMidiasEmCarregamento((atuais) => {
          const proximo = new Set(atuais)
          proximo.delete(id)
          return proximo
        })
      }
    }
  }, [atualizarMidias, midiasConsultadas])

  const carregarPendentes = useCallback(async () => {
    const sequencia = ++sequenciaPendentes.current
    setCarregandoLista(true)
    setErro('')

    try {
      const parametros = new URLSearchParams({
        page: String(paginaPendentes),
        page_size: String(ITENS_POR_PAGINA_LISTAS),
      })
      if (motivoFiltro) parametros.set('motivo', motivoFiltro)
      if (buscaPendentes) parametros.set('q', buscaPendentes)

      const resposta = await fetch(
        `${API_BASE}/api/admin/curadoria/pendentes?${parametros.toString()}`,
        { headers: getHeaders() }
      )
      const dados = await resposta.json().catch(() => ({}))
      if (sequencia !== sequenciaPendentes.current) return

      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível carregar a fila.')
      }

      // Compatibilidade temporária com a resposta antiga em lista.
      let registros
      let total
      let totalGeral
      if (Array.isArray(dados)) {
        const filtrados = motivoFiltro ? dados.filter((item) => item.motivo === motivoFiltro) : dados
        total = filtrados.length
        totalGeral = dados.length
        const inicio = (paginaPendentes - 1) * ITENS_POR_PAGINA_LISTAS
        registros = filtrados.slice(inicio, inicio + ITENS_POR_PAGINA_LISTAS)
      } else {
        registros = Array.isArray(dados.items) ? dados.items : []
        total = Number(dados.total || 0)
        totalGeral = Number(dados.total_geral ?? total)
      }

      setTotalPendentes(totalGeral)
      setTotalPendentesFiltrados(total)
      const ultimaPagina = Math.max(1, Math.ceil(total / ITENS_POR_PAGINA_LISTAS))
      if (paginaPendentes > ultimaPagina) {
        setPendentes([])
        setPaginaPendentes(ultimaPagina)
        return
      }

      // Carrega apenas os registros e as imagens já persistidas.
      // A busca de novas imagens acontece exclusivamente pelo botão da galeria.
      if (sequencia !== sequenciaPendentes.current) return
      setPendentes(registros)
    } catch (error) {
      if (sequencia !== sequenciaPendentes.current) return
      setPendentes([])
      setTotalPendentes(0)
      setTotalPendentesFiltrados(0)
      setErro(error.message)
    } finally {
      if (sequencia === sequenciaPendentes.current) setCarregandoLista(false)
    }
  }, [getHeaders, paginaPendentes, motivoFiltro, buscaPendentes])

  const carregarStatus = useCallback(async (statusFiltro) => {
    const sequencia = ++sequenciaStatus.current
    setCarregandoStatus(true)
    setErro('')

    try {
      const parametros = new URLSearchParams({
        page: String(paginaStatus),
        page_size: String(ITENS_POR_PAGINA_LISTAS),
      })
      if (motivoFiltro) parametros.set('motivo', motivoFiltro)
      const termoBuscaStatus = statusFiltro === 'aprovado' ? buscaAprovados : buscaExcluidos
      if (termoBuscaStatus) parametros.set('q', termoBuscaStatus)

      const resposta = await fetch(
        `${API_BASE}/api/admin/curadoria/status/${statusFiltro}?${parametros.toString()}`,
        { headers: getHeaders() }
      )
      const dados = await resposta.json().catch(() => ({}))
      if (sequencia !== sequenciaStatus.current) return

      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível carregar os registros.')
      }

      // Compatibilidade temporária com a resposta antiga em lista.
      let registros
      let total
      if (Array.isArray(dados)) {
        const filtrados = motivoFiltro ? dados.filter((item) => item.motivo === motivoFiltro) : dados
        total = filtrados.length
        const inicio = (paginaStatus - 1) * ITENS_POR_PAGINA_LISTAS
        registros = filtrados.slice(inicio, inicio + ITENS_POR_PAGINA_LISTAS)
      } else {
        registros = Array.isArray(dados.items) ? dados.items : []
        total = Number(dados.total || 0)
      }

      setTotalItensStatus(total)
      const ultimaPagina = Math.max(1, Math.ceil(total / ITENS_POR_PAGINA_LISTAS))
      if (paginaStatus > ultimaPagina) {
        setItensStatus([])
        setPaginaStatus(ultimaPagina)
        return
      }
      setItensStatus(registros)
    } catch (error) {
      if (sequencia !== sequenciaStatus.current) return
      setItensStatus([])
      setTotalItensStatus(0)
      setErro(error.message)
    } finally {
      if (sequencia === sequenciaStatus.current) setCarregandoStatus(false)
    }
  }, [getHeaders, paginaStatus, motivoFiltro, buscaAprovados, buscaExcluidos])

  const carregarConteudosSensiveis = useCallback(async () => {
    const sequencia = ++sequenciaConteudoSensivel.current
    setCarregandoStatus(true)
    setErro('')

    try {
      const parametros = new URLSearchParams({
        page: String(paginaSensivel),
        page_size: String(ITENS_POR_PAGINA_SENSIVEL),
      })
      if (termoBuscaSensivel) parametros.set('q', termoBuscaSensivel)

      const resposta = await fetch(
        `${API_BASE}/api/admin/curadoria/conteudo-sensivel?${parametros.toString()}`,
        { headers: getHeaders() }
      )
      const dados = await resposta.json().catch(() => ({}))

      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível carregar os conteúdos sensíveis.')
      }
      // Aceita a resposta antiga em lista como fallback, mas a rota atualizada
      // deve responder com { items, total, page, page_size } e paginar no banco.
      const itens = Array.isArray(dados)
        ? dados.slice((paginaSensivel - 1) * ITENS_POR_PAGINA_SENSIVEL, paginaSensivel * ITENS_POR_PAGINA_SENSIVEL)
        : (Array.isArray(dados.items) ? dados.items : [])
      const total = Array.isArray(dados) ? dados.length : Number(dados.total || 0)
      if (sequencia !== sequenciaConteudoSensivel.current) return

      setTotalConteudosSensiveis(total)
      const ultimaPagina = Math.max(1, Math.ceil(total / ITENS_POR_PAGINA_SENSIVEL))
      if (paginaSensivel > ultimaPagina) {
        setConteudosSensiveis([])
        setPaginaSensivel(ultimaPagina)
        return
      }
      setConteudosSensiveis(itens)
    } catch (error) {
      if (sequencia !== sequenciaConteudoSensivel.current) return
      setConteudosSensiveis([])
      setTotalConteudosSensiveis(0)
      setErro(error.message)
    } finally {
      if (sequencia === sequenciaConteudoSensivel.current) {
        setCarregandoStatus(false)
      }
    }
  }, [getHeaders, paginaSensivel, termoBuscaSensivel])

  // A busca é aplicada no backend com debounce, evitando baixar a fila inteira
  // e evitando uma chamada à API a cada tecla digitada.
  useEffect(() => {
    const temporizador = window.setTimeout(() => {
      setTermoBuscaSensivel(filtroTextoSensivel.trim())
    }, 300)
    return () => window.clearTimeout(temporizador)
  }, [filtroTextoSensivel])

  // Ao trocar de sessão, invalida respostas da conta anterior e limpa dados
  // administrativos que não devem permanecer visíveis para outra conta.
  useEffect(() => {
    sequenciaPendentes.current += 1
    sequenciaStatus.current += 1
    sequenciaConteudoSensivel.current += 1
    sequenciaSessaoMidia.current += 1
    idsMidiaEmRequisicao.current.clear()
    setMidiasEmCarregamento(new Set())
    setMidiasConsultadas(new Set())
    setErrosMidias(new Map())

    setPendentes([])
    setTotalPendentes(0)
    setTotalPendentesFiltrados(0)
    setConteudosSensiveis([])
    setTotalConteudosSensiveis(0)
    setItensStatus([])
    setTotalItensStatus(0)
    setResultados([])
    setResultadoSelecionado(-1)
    setItensSelecionados(new Set())
    setMensagem('')
    setErro('')
    setCarregandoLista(false)
    setCarregandoStatus(false)
    setCarregandoBusca(false)
    setAcaoId(null)
    setExclusaoPendente(null)
    setAprovacaoPendente(null)
    setAcaoLote(null)
    setProcessandoLote(false)
  }, [token, isAdmin])

  const carregarFeedback = useCallback(async () => {
    if (!isAdmin || !token) return
    setFeedbackCarregando(true)
    setFeedbackErro('')
    try {
      const parametros = new URLSearchParams({ status: feedbackStatus, page: String(paginaFeedback), page_size: String(ITENS_POR_PAGINA_FEEDBACK) })
      const resposta = await fetch(`${API_BASE}/api/admin/feedback?${parametros.toString()}`, { headers: getHeaders() })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar os feedbacks.')
      setFeedbackItens(Array.isArray(dados.items) ? dados.items : [])
      setFeedbackTotal(Number(dados.total || 0))
    } catch (error) {
      setFeedbackItens([])
      setFeedbackTotal(0)
      setFeedbackErro(error.message || 'Falha ao carregar feedbacks.')
    } finally {
      setFeedbackCarregando(false)
    }
  }, [getHeaders, isAdmin, token, feedbackStatus, paginaFeedback])

  const atualizarStatusFeedback = async (item) => {
    setFeedbackAcaoId(item.id)
    setFeedbackErro('')
    try {
      const concluido = item.status !== 'concluido'
      const resposta = await fetch(`${API_BASE}/api/admin/feedback/${item.id}/concluir`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify({ concluido }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível atualizar o feedback.')
      await carregarFeedback()
      await atualizarContadoresAbas()
    } catch (error) {
      setFeedbackErro(error.message || 'Falha ao atualizar feedback.')
    } finally {
      setFeedbackAcaoId(null)
    }
  }

  useEffect(() => {
    if (!isAdmin || !token) return

    if (aba === 'pendentes') {
      sequenciaStatus.current += 1
      sequenciaConteudoSensivel.current += 1
      carregarPendentes()
      return
    }

    if (aba === 'feedback') {
      sequenciaPendentes.current += 1
      sequenciaStatus.current += 1
      sequenciaConteudoSensivel.current += 1
      carregarFeedback()
      return
    }

    if (aba === 'sensivel') {
      sequenciaPendentes.current += 1
      sequenciaStatus.current += 1
      carregarConteudosSensiveis()
      return
    }

    sequenciaPendentes.current += 1
    sequenciaConteudoSensivel.current += 1
    if (aba === 'vitrine') return
    const statusBackend = aba === 'aprovados' ? 'aprovado' : 'excluido'
    carregarStatus(statusBackend)
  }, [isAdmin, token, aba, carregarPendentes, carregarConteudosSensiveis, carregarStatus, carregarFeedback])

  const carregarVitrine = useCallback(async () => {
    if (!isAdmin || !token) return
    setCarregandoVitrine(true)
    setErroVitrine('')
    try {
      const parametros = new URLSearchParams({ page: String(paginaVitrine), page_size: String(ITENS_POR_PAGINA_VITRINE) })
      if (termoVitrine) parametros.set('q', termoVitrine)
      const resposta = await fetch(`${API_BASE}/api/admin/curadoria/vitrine?${parametros.toString()}`, { headers: getHeaders() })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar a vitrine.')
      const itens = Array.isArray(dados) ? dados.filter(item => ['jogo_brasileiro', 'oportunidade'].includes(item.tipo)) : (Array.isArray(dados.items) ? dados.items : [])
      setItensVitrine(itens)
      setTotalVitrine(Number(dados.total ?? itens.length))
      const ultimaPagina = Math.max(1, Math.ceil(Number(dados.total ?? itens.length) / ITENS_POR_PAGINA_VITRINE))
      if (paginaVitrine > ultimaPagina) setPaginaVitrine(ultimaPagina)
    } catch (error) {
      setErroVitrine(error.message || 'Falha ao carregar a vitrine.')
    } finally {
      setCarregandoVitrine(false)
    }
  }, [getHeaders, isAdmin, token, paginaVitrine, termoVitrine])

  useEffect(() => {
    if (aba === 'vitrine' && isAdmin && token) carregarVitrine()
  }, [aba, isAdmin, token, carregarVitrine])

  const atualizarItemVitrine = async (item, alteracoes) => {
    setAcaoId(item.id)
    setMensagem('')
    setErroVitrine('')
    try {
      const resposta = await fetch(`${API_BASE}/api/admin/curadoria/vitrine/${item.id}`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify(alteracoes),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível atualizar o item.')
      await carregarVitrine()
    } catch (error) {
      setErroVitrine(error.message || 'Falha ao atualizar item.')
    } finally {
      setAcaoId(null)
    }
  }

  const removerItemVitrine = async (item) => {
    if (!window.confirm(`Remover ${item.jogo_nome || item.nome || 'este item'} da vitrine?`)) return
    setAcaoId(item.id)
    setErroVitrine('')
    try {
      const resposta = await fetch(`${API_BASE}/api/admin/curadoria/vitrine/${item.id}`, {
        method: 'DELETE',
        headers: getHeaders(),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível remover o item.')
      setItensVitrine(atuais => atuais.filter(registro => registro.id !== item.id))
    } catch (error) {
      setErroVitrine(error.message || 'Falha ao remover item.')
    } finally {
      setAcaoId(null)
    }
  }

  const adicionarJogoVitrine = async (jogo, tipo) => {
    setAcaoId(`${tipo}-${jogo.id}`)
    setMensagem('')
    setErroVitrine('')
    try {
      const resposta = await fetch(`${API_BASE}/api/admin/curadoria/vitrine/lote`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({ tipo, jogo_ids: [jogo.id] }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível adicionar o jogo à vitrine.')
      if (dados.adicionados?.length) {
        setMensagem(`${jogo.nome} adicionado a ${tipo === 'jogo_brasileiro' ? 'Brasil em jogo' : 'Oportunidades de preço'}.`)
        await carregarVitrine()
      } else {
        const motivo = dados.ignorados?.[0]?.motivo || 'O jogo não pôde ser adicionado.'
        setErroVitrine(`${jogo.nome}: ${motivo}`)
      }
    } catch (error) {
      setErroVitrine(error.message || 'Falha ao adicionar jogo à vitrine.')
    } finally {
      setAcaoId(null)
    }
  }

  const pesquisar = async (event) => {
    event.preventDefault()
    setMensagem('')
    setErro('')

    if (busca.trim().length < 2) {
      setErro('Digite pelo menos 2 caracteres para pesquisar.')
      return
    }

    setCarregandoBusca(true)

    try {
      const resposta = await fetch(
        `${API_BASE}/api/admin/curadoria/buscar?termo=${encodeURIComponent(busca.trim())}`,
        { headers: getHeaders() }
      )
      const dados = await resposta.json().catch(() => ({}))

      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível realizar a busca.')
      }

      const lista = Array.isArray(dados) ? dados : []
      setResultados(lista)
      setResultadoSelecionado(lista.length > 0 ? 0 : -1)
    } catch (error) {
      setErro(error.message)
    } finally {
      setCarregandoBusca(false)
    }
  }

  const adicionar = async (jogo) => {
    setAcaoId(jogo.id)
    setMensagem('')
    setErro('')

    try {
      const ehSensivel = aba === 'sensivel'

      const endpoint = ehSensivel
        ? `${API_BASE}/api/admin/curadoria/conteudo-sensivel`
        : `${API_BASE}/api/admin/curadoria/`

      const resposta = await fetch(endpoint, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(
          ehSensivel
            ? {
                jogo_id: jogo.id,
                observacao: 'Inclusão manual na fila de conteúdo sensível',
              }
            : { jogo_id: jogo.id }
        ),
      })
      const dados = await resposta.json().catch(() => ({}))

      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível adicionar o jogo.')
      }

      setMensagem(
        ehSensivel
          ? `${jogo.nome} foi enviado para a fila de conteúdo sensível.`
          : `${jogo.nome} foi enviado para análise.`
      )
      setResultados([])
      setResultadoSelecionado(-1)
      setBusca('')

      if (ehSensivel) {
        await carregarConteudosSensiveis()
        setAba('sensivel')
      } else {
        await carregarPendentes()
        setAba('pendentes')
      }
    } catch (error) {
      setErro(error.message)
    } finally {
      setAcaoId(null)
    }
  }

  const reabrir = async (item) => {
    setAcaoId(item.id)
    setMensagem('')
    setErro('')

    try {
      const resposta = await fetch(
        `${API_BASE}/api/admin/curadoria/${item.id}/reabrir`,
        {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify({}),
        }
      )
      const dados = await resposta.json().catch(() => ({}))

      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível reabrir a auditoria.')
      }

      setMensagem(`${item.nome} voltou para a fila de análise.`)
      await carregarPendentes()
      await carregarStatus(item.status)
    } catch (error) {
      setErro(error.message)
    } finally {
      setAcaoId(null)
    }
  }

  const abrirAprovacao = (item) => {
    setMensagem('')
    setErro('')
    setMotivoAprovacao('')
    setObservacaoAprovacao('')
    setAprovacaoPendente(item)
  }

  const fecharAprovacao = () => {
    if (acaoId !== null) return
    setAprovacaoPendente(null)
    setMotivoAprovacao('')
    setObservacaoAprovacao('')
  }

  const confirmarAprovacao = async () => {
    if (!aprovacaoPendente || !motivoAprovacao) {
      setErro('Selecione um motivo para aprovar o jogo.')
      return
    }

    if (motivoAprovacao === 'Outros' && !observacaoAprovacao.trim()) {
      setErro('Explique o motivo da aprovação quando a categoria for "Outros".')
      return
    }

    await decidir(
      aprovacaoPendente,
      'aprovar',
      motivoAprovacao,
      motivoAprovacao === 'Outros' ? observacaoAprovacao.trim() : '',
    )
    setAprovacaoPendente(null)
    setMotivoAprovacao('')
    setObservacaoAprovacao('')
  }

  const alternarBorradoSensivel = () => {
    setImagensSensiveisBorradas((atual) => !atual)
  }

  const alternarSelecao = (item) => {
    setItensSelecionados((atual) => {
      const proximo = new Set(atual)
      if (proximo.has(item.id)) {
        proximo.delete(item.id)
      } else {
        proximo.add(item.id)
      }
      return proximo
    })
  }

  // A seleção em lote fica limitada aos cartões da página atual (até 50).
  // Ao mudar página, filtro ou aba, a seleção é limpa para evitar decisões
  // acidentais em itens que deixaram de estar visíveis.
  const selecionarPaginaSensivel = () => {
    const itensPagina = aba === 'pendentes' ? itensPendentesFiltrados : conteudosSensiveisPaginados
    const idsPagina = itensPagina.map((item) => item.id)
    setItensSelecionados((atual) => {
      const proximo = new Set(atual)
      const todosSelecionados = idsPagina.length > 0 && idsPagina.every((id) => proximo.has(id))

      if (todosSelecionados) {
        idsPagina.forEach((id) => proximo.delete(id))
      } else {
        idsPagina.forEach((id) => proximo.add(id))
      }
      return proximo
    })
  }

  const limparSelecao = () => setItensSelecionados(new Set())

  const abrirAcaoLote = (decisao) => {
    if (!itensSelecionados.size || processandoLote) return
    setMensagem('')
    setErro('')
    setMotivoLote('')
    setObservacaoLote('')
    setAcaoLote(decisao)
  }

  const fecharAcaoLote = () => {
    if (processandoLote) return
    setAcaoLote(null)
    setMotivoLote('')
    setObservacaoLote('')
  }

  const confirmarAcaoLote = async () => {
    if (!acaoLote || !itensSelecionados.size || processandoLote) return

    if (!motivoLote) {
      setErro(acaoLote === 'aprovar'
        ? 'Selecione um motivo para aprovar os jogos.'
        : 'Selecione um motivo para excluir os jogos.')
      return
    }

    if (motivoLote === 'Outros' && !observacaoLote.trim()) {
      setErro(acaoLote === 'aprovar'
        ? 'Explique o motivo da aprovação quando a categoria for "Outros".'
        : 'Explique o motivo da exclusão quando a categoria for "Outros".')
      return
    }

    // Só processa registros visíveis e selecionados da página atual.
    const itensDisponiveis = aba === 'pendentes' ? itensPendentesFiltrados : conteudosSensiveisPaginados
    const itens = itensDisponiveis.filter((item) => itensSelecionados.has(item.id))
    if (!itens.length) {
      setErro('Nenhum jogo selecionado está mais disponível na página atual.')
      return
    }

    setProcessandoLote(true)
    setProgressoLote({ concluidos: 0, total: itens.length })
    setMensagem('')
    setErro('')

    const corpo = { motivo: motivoLote }
    if (motivoLote === 'Outros') corpo.observacao = observacaoLote.trim()

    try {
      const resultadosLote = Array(itens.length)
      let proximoIndice = 0

      const trabalhadorLote = async () => {
        while (true) {
          const indice = proximoIndice++
          if (indice >= itens.length) return
          const item = itens[indice]

          try {
            const resposta = await fetch(
              `${API_BASE}/api/admin/curadoria/${item.id}/${acaoLote}`,
              {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(corpo),
              }
            )
            const dados = await resposta.json().catch(() => ({}))
            if (!resposta.ok) {
              throw new Error(dados.detail || `Não foi possível processar ${item.nome}.`)
            }
            resultadosLote[indice] = { status: 'fulfilled', item, dados }
          } catch (error) {
            resultadosLote[indice] = { status: 'rejected', item, erro: error }
          } finally {
            setProgressoLote((atual) => ({
              ...atual,
              concluidos: Math.min(atual.concluidos + 1, atual.total),
            }))
          }
        }
      }

      // Exclusões por Conteúdo sensível também acionam a busca de relacionados.
      // Nesse caso, executamos uma requisição de cada vez para reduzir conflitos
      // quando vários jogos selecionados compartilham desenvolvedora/publicadora.
      const buscaRelacionados = acaoLote === 'excluir' &&
        ['Conteúdo sensível', 'Fora do catálogo'].includes(motivoLote)
      const concorrencia = buscaRelacionados ? 1 : Math.min(3, itens.length)
      await Promise.all(Array.from({ length: concorrencia }, () => trabalhadorLote()))

      const concluidos = resultadosLote.filter((r) => r?.status === 'fulfilled')
      const falhas = resultadosLote.filter((r) => r?.status === 'rejected')
      const idsConcluidos = new Set(concluidos.map((r) => r.item.id))

      if (idsConcluidos.size) {
        setConteudosSensiveis((atuais) => atuais.filter((item) => !idsConcluidos.has(item.id)))
        setPendentes((atuais) => atuais.filter((item) => !idsConcluidos.has(item.id)))
        setItensSelecionados((atuais) => {
          const proximo = new Set(atuais)
          idsConcluidos.forEach((id) => proximo.delete(id))
          return proximo
        })
      }

      if (acaoLote === 'excluir' && ['Conteúdo sensível', 'Fora do catálogo'].includes(motivoLote) && concluidos.length) {
        const somaCampo = (campo) => concluidos.reduce(
          (total, resultado) => total + Number(resultado.dados?.[campo] || 0), 0
        )
        const novos = somaCampo('jogos_relacionados_adicionados')
        const reabertos = somaCampo('jogos_relacionados_reabertos')
        const reclassificados = somaCampo('jogos_relacionados_reclassificados')
        const encaminhados = novos + reabertos + reclassificados
        const destino = motivoLote === 'Conteúdo sensível'
          ? 'avaliação de conteúdo sensível'
          : 'fila normal com o motivo Fora do catálogo'
        setMensagem(
          `${concluidos.length} jogo(s) excluído(s). A busca de relacionados foi executada para cada item` +
          (encaminhados
            ? ` e encaminhou ${encaminhados} jogo(s) relacionado(s) para ${destino} (${novos} novo(s), ${reabertos} reaberto(s), ${reclassificados} reclassificado(s)).`
            : ', sem novos encaminhamentos de jogos relacionados.')
        )
      } else if (concluidos.length) {
        setMensagem(
          acaoLote === 'aprovar'
            ? `${concluidos.length} jogo(s) aprovado(s) com o mesmo motivo.`
            : `${concluidos.length} jogo(s) excluído(s) com o mesmo motivo.`
        )
      }

      if (concluidos.length) {
        if (aba === 'pendentes') await carregarPendentes()
        else await carregarConteudosSensiveis()
      }

      if (falhas.length) {
        const nomesFalha = falhas.slice(0, 3).map((r) => r.item.nome).join(', ')
        const sufixo = falhas.length > 3 ? ` e mais ${falhas.length - 3}` : ''
        setErro(
          `${concluidos.length} processado(s), ${falhas.length} falhou(aram). ` +
          `Falha em: ${nomesFalha}${sufixo}. Os itens com falha permaneceram selecionados.`
        )
      }

      setAcaoLote(null)
      setMotivoLote('')
      setObservacaoLote('')
    } catch (error) {
      setErro(error.message || 'Não foi possível concluir a ação em lote.')
    } finally {
      setProcessandoLote(false)
    }
  }

  const abrirExclusao = (item) => {
    setMensagem('')
    setErro('')
    setMotivoExclusao('')
    setObservacaoExclusao('')
    setExclusaoPendente(item)
  }

  const fecharExclusao = () => {
    if (acaoId !== null) return
    setExclusaoPendente(null)
    setMotivoExclusao('')
    setObservacaoExclusao('')
  }

  const confirmarExclusao = async () => {
    if (!exclusaoPendente || !motivoExclusao) {
      setErro('Selecione um motivo para excluir o jogo.')
      return
    }

    if (motivoExclusao === 'Outros' && !observacaoExclusao.trim()) {
      setErro('Explique o motivo da exclusão quando a categoria for "Outros".')
      return
    }

    await decidir(
      exclusaoPendente,
      'excluir',
      motivoExclusao,
      motivoExclusao === 'Outros' ? observacaoExclusao.trim() : '',
    )
    setExclusaoPendente(null)
    setMotivoExclusao('')
    setObservacaoExclusao('')
  }

  const decidir = async (item, decisao, motivoDecisao = null, observacaoDecisao = '') => {
    setAcaoId(item.id)
    setMensagem('')
    setErro('')

    try {
      const corpo = {}

      if (motivoDecisao) {
        corpo.motivo = motivoDecisao
      }

      if (observacaoDecisao) {
        corpo.observacao = observacaoDecisao
      }

      const resposta = await fetch(
        `${API_BASE}/api/admin/curadoria/${item.id}/${decisao}`,
        {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify(corpo),
        }
      )
      const dados = await resposta.json().catch(() => ({}))

      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível registrar a decisão.')
      }

      const ehExclusaoSensivel =
        decisao === 'excluir' && motivoDecisao === 'Conteúdo sensível'
      const relacionadosAdicionados = Number(dados.jogos_relacionados_adicionados || 0)
      const relacionadosReabertos = Number(dados.jogos_relacionados_reabertos || 0)
      const relacionadosReclassificados = Number(dados.jogos_relacionados_reclassificados || 0)
      const relacionadosJaPendentes = Number(dados.jogos_relacionados_ja_pendentes || 0)
      const relacionadosJaExcluidos = Number(dados.jogos_relacionados_ja_excluidos || 0)
      const relacionadosEncontrados = Number(dados.jogos_relacionados_encontrados || 0)

      let mensagem = decisao === 'aprovar'
        ? `${item.nome} foi aprovado.`
        : `${item.nome} foi excluído.`

      if (ehExclusaoSensivel) {
        const encaminhados = relacionadosAdicionados + relacionadosReabertos + relacionadosReclassificados
        if (encaminhados > 0) {
          mensagem += ` ${encaminhados} jogo(s) relacionado(s) foram encaminhados para avaliação de conteúdo sensível (${relacionadosAdicionados} novo(s), ${relacionadosReabertos} reaberto(s), ${relacionadosReclassificados} reclassificado(s)).`
        } else if (relacionadosEncontrados === 0) {
          mensagem += ' Nenhum outro jogo foi encontrado pela mesma desenvolvedora/publicadora.'
        }

        if (relacionadosJaPendentes > 0 || relacionadosJaExcluidos > 0) {
          mensagem += ` ${relacionadosJaPendentes} já estava(m) pendente(s) por conteúdo sensível e ${relacionadosJaExcluidos} já estava(m) excluído(s) pelo mesmo motivo.`
        }
      }
      setMensagem(mensagem)

      // Mantém a remoção local para não recarregar todas as mídias após cada
      // decisão. Quando a exclusão sensível cria/reabre relacionados e a
      // aba atual é a fila sensível, atualizamos apenas a lista. O efeito de
      // mídias continua limitado à página atual e respeita seu cache local.
      if (aba === 'sensivel') {
        setConteudosSensiveis((atual) => atual.filter((registro) => registro.id !== item.id))
        setItensSelecionados((atual) => {
          const proximo = new Set(atual)
          proximo.delete(item.id)
          return proximo
        })
        // A lista é paginada no servidor; recarregue para preencher a vaga e
        // manter o total correto, mesmo quando não houver relacionados.
        await carregarConteudosSensiveis()
      } else {
        await carregarPendentes()
      }
    } catch (error) {
      setErro(error.message)
    } finally {
      setAcaoId(null)
    }
  }

  if (carregando) {
    return <div className="curadoria-carregando">Carregando...</div>
  }

  if (!isAdmin || !token) {
    return <Navigate to="/" replace />
  }

  const opcoesFiltro = aba === 'aprovados'
    ? MOTIVOS_APROVACAO
    : aba === 'pendentes'
      ? MOTIVOS_AUDITORIA.filter((motivo) => motivo !== 'Conteúdo sensível')
      : MOTIVOS_AUDITORIA

  // Motivo e paginação já são aplicados no backend; estes arrays contêm apenas a página atual.
  const itensPendentesFiltrados = pendentes
  const itensStatusFiltrados = itensStatus

  const termoSensivel = filtroTextoSensivel.trim().toLocaleLowerCase('pt-BR')
  // A API retorna somente os itens da página atual, já filtrados e ordenados.
  const totalPaginasSensivel = Math.max(1, Math.ceil(totalConteudosSensiveis / ITENS_POR_PAGINA_SENSIVEL))
  const paginaSensivelAtual = Math.min(paginaSensivel, totalPaginasSensivel)
  const conteudosSensiveisPaginados = conteudosSensiveis

  return (
    <div className="curadoria-pagina">
      <Cabecalho />

      <main className="curadoria-conteudo">
        <header className="curadoria-topo">
          <div>
            <span className="curadoria-kicker">ADMINISTRAÇÃO</span>
            <h1>Curadoria do catálogo</h1>
            <p>Analise os jogos antes que eles façam parte do catálogo público.</p>
          </div>

          <div className="curadoria-contador">
            <strong>{totalPendentes}</strong>
            <span>Jogos aguardando decisão</span>
          </div>
        </header>

        <details className="curadoria-orientacao" aria-labelledby="curadoria-orientacao-titulo">
          <summary className="curadoria-orientacao-cabecalho">
            <span className="curadoria-orientacao-cabecalho-texto">
              <strong id="curadoria-orientacao-titulo">Como funciona a curadoria?</strong>
              <span>Use as abas para revisar o catálogo, registrar decisões e escolher o que aparece na página inicial.</span>
            </span>
            <span className="curadoria-orientacao-seta-principal" aria-hidden="true" />
          </summary>
          <div className="curadoria-orientacao-conteudo">
          <div className="curadoria-orientacao-lista">
            <details className="curadoria-orientacao-item">
              <summary>
                <span>Aguardando análise</span>
                <span className="curadoria-orientacao-seta" aria-hidden="true" />
              </summary>
              <p>Reúne jogos pendentes de avaliação. É possível revisar informações, aprovar ou excluir registros, individualmente ou em lote.</p>
            </details>
            <details className="curadoria-orientacao-item">
              <summary>
                <span>Conteúdo sensível</span>
                <span className="curadoria-orientacao-seta" aria-hidden="true" />
              </summary>
              <p>Centraliza jogos sinalizados para uma análise específica de conteúdo sensível, ajudando a manter o catálogo adequado ao escopo do projeto.</p>
            </details>
            <details className="curadoria-orientacao-item">
              <summary>
                <span>Aprovados</span>
                <span className="curadoria-orientacao-seta" aria-hidden="true" />
              </summary>
              <p>Permite consultar os jogos aprovados e acompanhar as decisões registradas durante a curadoria.</p>
            </details>
            <details className="curadoria-orientacao-item">
              <summary>
                <span>Excluídos</span>
                <span className="curadoria-orientacao-seta" aria-hidden="true" />
              </summary>
              <p>Guarda os registros retirados do catálogo, com seus motivos, e permite consultar o histórico ou reabrir uma análise quando disponível.</p>
            </details>
            <details className="curadoria-orientacao-item">
              <summary>
                <span>Vitrine</span>
                <span className="curadoria-orientacao-seta" aria-hidden="true" />
              </summary>
              <p>Define quais jogos aparecem nas seções “Brasil em jogo” e “Oportunidades de preço” da página inicial. Cada seção possui critérios próprios.</p>
            </details>
            <details className="curadoria-orientacao-item">
              <summary>
                <span>Feedback</span>
                <span className="curadoria-orientacao-seta" aria-hidden="true" />
              </summary>
              <p>Reúne sugestões enviadas pela comunidade. Abra a página de origem e marque como feito quando a melhoria for concluída; os registros ficam no histórico.</p>
            </details>
          </div>
          </div>
        </details>

        {aba !== 'feedback' && <section className="curadoria-busca">
          <h2>{aba === 'feedback' ? 'Feedback da comunidade' : aba === 'vitrine' ? 'Pesquisar jogos para a Vitrine' : aba === 'sensivel' ? 'Adicionar conteúdo sensível' : 'Adicionar jogo para análise'}</h2>
          <p>{aba === 'feedback' ? 'Use a nova aba abaixo para acompanhar as sugestões recebidas.' : aba === 'vitrine' ? 'Pesquise por jogo, desenvolvedora ou publicadora e escolha em qual seção deseja incluí-lo. Cada seção tem validações próprias.' : aba === 'sensivel' ? 'Pesquise um jogo e inclua-o manualmente na fila de auditoria de conteúdo sensível.' : 'Pesquise um jogo existente no catálogo e envie-o para a fila.'}</p>

          <form onSubmit={pesquisar} className="curadoria-form-busca">
            <input
              value={busca}
              onChange={(event) => {
                const valor = event.target.value
                setBusca(valor)
                if (!valor.trim()) {
                  setResultados([])
                  setResultadoSelecionado(-1)
                }
              }}
              onKeyDown={(event) => {
                if (!resultados.length) return

                if (event.key === 'ArrowDown') {
                  event.preventDefault()
                  setResultadoSelecionado((indice) =>
                    indice < resultados.length - 1 ? indice + 1 : 0
                  )
                  return
                }

                if (event.key === 'ArrowUp') {
                  event.preventDefault()
                  setResultadoSelecionado((indice) =>
                    indice > 0 ? indice - 1 : resultados.length - 1
                  )
                  return
                }

                if (event.key === 'Escape') {
                  event.preventDefault()
                  setResultados([])
                  setResultadoSelecionado(-1)
                  return
                }

                if (event.key === 'Enter') {
                  // Com resultados abertos, Enter navega até o resultado selecionado.
                  // Sem resultados, o formulário executa o submit e realiza a busca.
                  if (resultadoSelecionado >= 0) {
                    event.preventDefault()
                    document
                      .getElementById(`curadoria-resultado-${resultados[resultadoSelecionado].id}`)
                      ?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
                  }
                }
              }}
              placeholder={aba === 'vitrine' ? "Ex.: nome do jogo, estúdio ou publicadora..." : "Ex.: Cyberpunk, Hogwarts..."}
              aria-label="Pesquisar jogo, desenvolvedora ou publicadora"
              aria-controls="curadoria-resultados"
              aria-activedescendant={
                resultadoSelecionado >= 0 && resultados[resultadoSelecionado]
                  ? `curadoria-resultado-${resultados[resultadoSelecionado].id}`
                  : undefined
              }
            />
            <button type="submit" disabled={carregandoBusca}>
              {carregandoBusca ? 'Buscando...' : 'Pesquisar'}
            </button>
          </form>

          {resultados.length > 0 && (
            <div
              id="curadoria-resultados"
              className="curadoria-resultados"
              role="listbox"
              aria-label="Resultados da pesquisa"
              style={{
                maxHeight: '430px',
                overflowY: resultados.length > 5 ? 'auto' : 'visible',
                paddingRight: resultados.length > 5 ? '6px' : undefined,
              }}
            >
              {resultados.map((jogo, index) => (
                <article
                  id={`curadoria-resultado-${jogo.id}`}
                  className={`curadoria-resultado ${
                    index === resultadoSelecionado ? 'selecionado' : ''
                  }`}
                  key={jogo.id}
                  role="option"
                  aria-selected={index === resultadoSelecionado}
                  onMouseEnter={() => setResultadoSelecionado(index)}
                >
                  {jogo.imagem_epic
                    ? <img src={jogo.imagem_epic} alt="" />
                    : <div className="curadoria-sem-imagem">LOJA</div>}

                  <div className="curadoria-resultado-info">
                    <strong>{jogo.nome}</strong>
                    <span>{jogo.epic_id || jogo.steam_id || 'Sem ID da loja'}</span>
                    {jogo.desenvolvedor && <small>{jogo.desenvolvedor}</small>}
                  </div>

                  {aba === 'vitrine' ? (
                    <div className="curadoria-vitrine-busca-acoes">
                      <small>{jogo.eh_brasileiro ? 'Classificado como brasileiro' : 'Não classificado como brasileiro'}</small>
                      <small>{jogo.promocao_ativa ? 'Promoção ativa confirmada' : 'Sem promoção ativa confirmada'}</small>
                      <button type="button" disabled={!jogo.eh_brasileiro || Boolean(acaoId)} onClick={() => adicionarJogoVitrine(jogo, 'jogo_brasileiro')}>
                        {acaoId === `jogo_brasileiro-${jogo.id}` ? 'Adicionando...' : 'Brasil em jogo'}
                      </button>
                      <button type="button" disabled={!jogo.promocao_ativa || Boolean(acaoId)} onClick={() => adicionarJogoVitrine(jogo, 'oportunidade')}>
                        {acaoId === `oportunidade-${jogo.id}` ? 'Adicionando...' : 'Oportunidades de preço'}
                      </button>
                    </div>
                  ) : (
                    <button type="button" onClick={() => adicionar(jogo)} disabled={acaoId === jogo.id}>
                      {acaoId === jogo.id ? 'Adicionando...' : (aba === 'sensivel' ? 'Sinalizar conteúdo sensível' : 'Enviar para análise')}
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
        </section>}

        <div className="curadoria-abas">
          <button
            type="button"
            className={aba === 'pendentes' ? 'ativa' : ''}
            onClick={() => {
              setAba('pendentes')
              setPaginaPendentes(1)
              setPaginaStatus(1)
              setResultados([])
              setItensSelecionados(new Set())
              setResultadoSelecionado(-1)
               setMotivoFiltro('')
              setImagensSensiveisBorradas(true)
            }}
          >
            Aguardando análise <span>{totalPendentes}</span>
          </button>
          <button
            type="button"
            className={aba === 'sensivel' ? 'ativa' : ''}
            onClick={() => {
              setAba('sensivel')
              setPaginaPendentes(1)
              setPaginaStatus(1)
              setResultados([])
              setItensSelecionados(new Set())
              setResultadoSelecionado(-1)
              setMotivoFiltro('')
              setPaginaSensivel(1)
              setFiltroTextoSensivel('')
              setTermoBuscaSensivel('')
              setItensSelecionados(new Set())
              setImagensSensiveisBorradas(true)
            }}
          >
            Conteúdo sensível <span>{totalConteudosSensiveis}</span>
          </button>
          <button
            type="button"
            className={aba === 'aprovados' ? 'ativa' : ''}
            onClick={() => {
              setAba('aprovados')
              setPaginaPendentes(1)
              setPaginaStatus(1)
              setResultados([])
              setItensSelecionados(new Set())
              setResultadoSelecionado(-1)
               setMotivoFiltro('')
              setImagensSensiveisBorradas(true)
            }}
          >
            Aprovados <span>{totalAprovados}</span>
          </button>
          <button
            type="button"
            className={aba === 'excluidos' ? 'ativa' : ''}
            onClick={() => {
              setAba('excluidos')
              setPaginaPendentes(1)
              setPaginaStatus(1)
              setResultados([])
              setItensSelecionados(new Set())
              setResultadoSelecionado(-1)
               setMotivoFiltro('')
              setImagensSensiveisBorradas(true)
            }}
          >
            Excluídos <span>{totalExcluidos}</span>
          </button>
          <button
            type="button"
            className={aba === 'vitrine' ? 'ativa' : ''}
            onClick={() => {
              setAba('vitrine')
              setResultados([])
              setItensSelecionados(new Set())
              setResultadoSelecionado(-1)
              setMensagem('')
              setErro('')
            }}
          >
            Vitrine <span>{totalVitrine}</span>
          </button>
          <button
            type="button"
            className={aba === 'feedback' ? 'ativa' : ''}
            onClick={() => {
              setAba('feedback')
              setResultados([])
              setItensSelecionados(new Set())
              setResultadoSelecionado(-1)
              setMensagem('')
              setErro('')
            }}
          >
            Feedback <span>{totalFeedbackPendentes}</span>
          </button>
        </div>

        {aba === 'feedback' ? (
          <section className="curadoria-feedback">
            <div className="curadoria-feedback-topo">
              <div>
                <h2>Sugestões da comunidade</h2>
                <p>Consulte os relatos recebidos, abra a página de origem e marque como feito quando a melhoria for concluída. Os registros permanecem no histórico.</p>
              </div>
              <label className="curadoria-feedback-filtro">
                <span>Status</span>
                <select value={feedbackStatus} onChange={(event) => { setFeedbackStatus(event.target.value); setPaginaFeedback(1) }}>
                  <option value="pendente">Pendentes</option>
                  <option value="concluido">Concluídos</option>
                  <option value="todos">Todos</option>
                </select>
              </label>
            </div>
            {feedbackErro && <div className="curadoria-erro" role="alert">{feedbackErro}</div>}
            {feedbackCarregando ? (
              <div className="curadoria-vazio"><span>…</span><strong>Carregando feedbacks</strong></div>
            ) : feedbackItens.length === 0 ? (
              <div className="curadoria-vazio"><span>✓</span><strong>Nenhum feedback nesta categoria</strong><p>Quando houver sugestões recebidas, elas aparecerão aqui.</p></div>
            ) : (
              <>
                <p className="curadoria-feedback-contagem">{feedbackTotal.toLocaleString('pt-BR')} registro(s)</p>
                <div className="curadoria-feedback-lista">
                  {feedbackItens.map((item) => {
                    const origem = String(item.pagina_origem || '').trim()
                    const urlOrigem = origem.startsWith('/') ? origem : ''
                    const nomePagina = origem.replace(/^https?:\/\/[^/]+/i, '').split(/[?#]/)[0] || '/'
                    return (
                      <article className={`curadoria-feedback-card ${item.status === 'concluido' ? 'concluido' : ''}`} key={item.id}>
                        <div className="curadoria-feedback-corpo">
                          <div className="curadoria-feedback-card-topo">
                            <div><span className="curadoria-feedback-tipo">{item.tipo || 'outro'}</span><h3>{nomePagina}</h3></div>
                            <span className={`curadoria-feedback-status ${item.status === 'concluido' ? 'feito' : 'aberto'}`}>{item.status === 'concluido' ? 'Concluído' : 'Pendente'}</span>
                          </div>
                          <p className="curadoria-feedback-descricao">{item.descricao}</p>
                          <div className="curadoria-feedback-meta">
                            <span>Recebido: {item.criada_em ? new Date(item.criada_em).toLocaleString('pt-BR') : 'Data indisponível'}</span>
                            {item.usuario_nome && <span>Usuário: {item.usuario_nome}</span>}
                            {item.concluida_em && <span>Concluído: {new Date(item.concluida_em).toLocaleString('pt-BR')}</span>}
                          </div>
                          <div className="curadoria-feedback-acoes">
                            {urlOrigem ? <a href={urlOrigem} className="botao-loja" target="_blank" rel="noreferrer">Abrir página de origem ↗</a> : <span className="curadoria-feedback-origem">Origem registrada: {origem || 'não informada'}</span>}
                            <button type="button" className={item.status === 'concluido' ? 'botao-reabrir' : 'botao-aprovar'} onClick={() => atualizarStatusFeedback(item)} disabled={feedbackAcaoId === item.id}>
                              {feedbackAcaoId === item.id ? 'Salvando...' : item.status === 'concluido' ? 'Reabrir' : 'Marcar como feito'}
                            </button>
                          </div>
                        </div>
                      </article>
                    )
                  })}
                </div>
                <PaginacaoCuradoria
                  total={feedbackTotal}
                  pagina={paginaFeedback}
                  tamanhoPagina={ITENS_POR_PAGINA_FEEDBACK}
                  onMudarPagina={setPaginaFeedback}
                  rotulo="Paginação dos feedbacks"
                />
              </>
            )}
          </section>
        ) : aba === 'vitrine' ? (
          <section className="curadoria-vitrine">
            <div className="curadoria-vitrine-topo">
              <div>
                <h2>Vitrine da página inicial</h2>
                <p>Gerencie exclusivamente os jogos exibidos em “Brasil em jogo” e “Oportunidades de preço”. Use a busca acima para adicionar jogos individualmente; cada seção valida seus próprios critérios.</p>
              </div>
              <button type="button" onClick={carregarVitrine} disabled={carregandoVitrine}>
                {carregandoVitrine ? 'Atualizando...' : 'Atualizar lista'}
              </button>
            </div>
            <div className="curadoria-vitrine-busca">
              <label htmlFor="busca-vitrine-curadoria">Buscar na vitrine</label>
              <input
                id="busca-vitrine-curadoria"
                type="search"
                value={filtroVitrine}
                placeholder="Nome do jogo ou desenvolvedor"
                onChange={(event) => setFiltroVitrine(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') { setPaginaVitrine(1); setTermoVitrine(filtroVitrine.trim()) }
                }}
              />
              <button type="button" onClick={() => { setPaginaVitrine(1); setTermoVitrine(filtroVitrine.trim()) }}>Buscar</button>
              {termoVitrine && <button type="button" onClick={() => { setFiltroVitrine(''); setTermoVitrine(''); setPaginaVitrine(1) }}>Limpar</button>}
            </div>
            {erroVitrine && <div className="curadoria-erro" role="alert">{erroVitrine}</div>}
            {mensagem && <div className="curadoria-mensagem" role="status">{mensagem}</div>}
            {carregandoVitrine ? (
              <p>Carregando itens da vitrine...</p>
            ) : itensVitrine.length === 0 ? (
              <div className="curadoria-vitrine-vazia">
                <strong>A vitrine ainda não possui itens.</strong>
                <p>Pesquise um jogo acima e escolha “Brasil em jogo” ou “Oportunidades de preço”.</p>
              </div>
            ) : (
              <div className="curadoria-vitrine-lista">
                {itensVitrine.map(item => (
                  <article className="curadoria-vitrine-item" key={item.id}>
                    {item.imagem ? <img src={item.imagem} alt="" loading="lazy" /> : <div className="curadoria-sem-imagem">JOGO</div>}
                    <div className="curadoria-vitrine-item-info">
                      <strong>{item.jogo_nome || item.nome || `Item #${item.id}`}</strong>
                      <span>{item.tipo === 'jogo_brasileiro' ? 'Brasil em jogo' : item.tipo === 'oportunidade' ? 'Oportunidades de preço' : 'Registro antigo de estúdio (não usado para seleção automática)'}</span>
                      {item.desenvolvedor && <small>Desenvolvedor: {item.desenvolvedor}</small>}
                      <label>Prioridade
                        <input type="number" min="0" max="100000" value={item.prioridade} disabled={acaoId === item.id}
                          onChange={event => {
                            const valor = event.target.value
                            setItensVitrine(atuais => atuais.map(registro => registro.id === item.id ? { ...registro, prioridade: valor } : registro))
                          }}
                          onBlur={event => {
                            const prioridade = Number(event.target.value)
                            if (Number.isInteger(prioridade) && prioridade >= 0 && prioridade !== Number(item.prioridade)) atualizarItemVitrine(item, { prioridade })
                          }}
                        />
                      </label>
                    </div>
                    <div className="curadoria-vitrine-item-acoes">
                      <button type="button" disabled={acaoId === item.id} onClick={() => atualizarItemVitrine(item, { ativo: !item.ativo })}>
                        {item.ativo ? 'Desativar' : 'Ativar'}
                      </button>
                      <button type="button" className="botao-excluir" disabled={acaoId === item.id} onClick={() => removerItemVitrine(item)}>
                        {acaoId === item.id ? 'Processando...' : 'Remover'}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
            {!carregandoVitrine && itensVitrine.length > 0 && (
              <PaginacaoCuradoria
                total={totalVitrine}
                pagina={paginaVitrine}
                tamanhoPagina={ITENS_POR_PAGINA_VITRINE}
                onMudarPagina={setPaginaVitrine}
                rotulo="Paginação da vitrine"
              />
            )}
          </section>
        ) : (
        <>
        {aba === 'sensivel' ? (
          <div className="curadoria-filtro-aba curadoria-filtro-sensivel">
            <span className="curadoria-filtro-sensivel-label">Proteção de imagens</span>
            <button
              type="button"
              className={`botao-borrar-imagens-sensivel ${imagensSensiveisBorradas ? 'ativo' : ''}`}
              onClick={alternarBorradoSensivel}
              aria-pressed={imagensSensiveisBorradas}
            >
              <span className="botao-ocultar-imagens-icone" aria-hidden="true">
                {imagensSensiveisBorradas ? (
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M2.5 12C4.7 7.7 8.1 5.5 12 5.5C15.9 5.5 19.3 7.7 21.5 12C19.3 16.3 15.9 18.5 12 18.5C8.1 18.5 4.7 16.3 2.5 12Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.8"/>
                    <path d="M4 4L20 20" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M2.5 12C4.7 7.7 8.1 5.5 12 5.5C15.9 5.5 19.3 7.7 21.5 12C19.3 16.3 15.9 18.5 12 18.5C8.1 18.5 4.7 16.3 2.5 12Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                    <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.8"/>
                  </svg>
                )}
              </span>
              <span>{imagensSensiveisBorradas ? 'Imagens ocultas' : 'Mostrar imagens'}</span>
            </button>
          </div>
        ) : (
          <div className={`curadoria-filtro-aba ${aba === 'excluidos' ? 'curadoria-filtro-excluidos' : ''}`}>
            {aba === 'pendentes' && (
              <form className="curadoria-busca-lista" onSubmit={(event) => { event.preventDefault(); setPaginaPendentes(1); setItensSelecionados(new Set()); setBuscaPendentes(buscaPendentesTexto.trim()) }}>
                <label htmlFor="curadoria-busca-pendentes">Pesquisar na fila</label>
                <div className="curadoria-busca-lista-controles">
                  <input id="curadoria-busca-pendentes" value={buscaPendentesTexto} onChange={(event) => setBuscaPendentesTexto(event.target.value)} placeholder="Nome, ID da loja, estúdio..." maxLength={255} />
                  <button type="submit">Pesquisar</button>
                  {(buscaPendentes || buscaPendentesTexto) && <button type="button" className="curadoria-busca-limpar" onClick={() => { setBuscaPendentesTexto(''); setBuscaPendentes(''); setPaginaPendentes(1); setItensSelecionados(new Set()) }}>Limpar</button>}
                </div>
              </form>
            )}
            {aba === 'aprovados' && (
              <form className="curadoria-busca-lista" onSubmit={(event) => { event.preventDefault(); setPaginaStatus(1); setBuscaAprovados(buscaAprovadosTexto.trim()) }}>
                <label htmlFor="curadoria-busca-aprovados">Pesquisar aprovados</label>
                <div className="curadoria-busca-lista-controles">
                  <input id="curadoria-busca-aprovados" value={buscaAprovadosTexto} onChange={(event) => setBuscaAprovadosTexto(event.target.value)} placeholder="Nome, ID da loja, estúdio..." maxLength={255} />
                  <button type="submit">Pesquisar</button>
                  {(buscaAprovados || buscaAprovadosTexto) && <button type="button" className="curadoria-busca-limpar" onClick={() => { setBuscaAprovadosTexto(''); setBuscaAprovados(''); setPaginaStatus(1) }}>Limpar</button>}
                </div>
              </form>
            )}
            {aba === 'excluidos' && (
              <form className="curadoria-busca-lista" onSubmit={(event) => { event.preventDefault(); setPaginaStatus(1); setBuscaExcluidos(buscaExcluidosTexto.trim()) }}>
                <label htmlFor="curadoria-busca-excluidos">Pesquisar excluídos</label>
                <div className="curadoria-busca-lista-controles">
                  <input id="curadoria-busca-excluidos" value={buscaExcluidosTexto} onChange={(event) => setBuscaExcluidosTexto(event.target.value)} placeholder="Nome, ID da loja, estúdio..." maxLength={255} />
                  <button type="submit">Pesquisar</button>
                  {(buscaExcluidos || buscaExcluidosTexto) && <button type="button" className="curadoria-busca-limpar" onClick={() => { setBuscaExcluidosTexto(''); setBuscaExcluidos(''); setPaginaStatus(1) }}>Limpar</button>}
                </div>
              </form>
            )}
            <div className="curadoria-filtro-motivo-grupo">
              <label htmlFor="curadoria-filtro-motivo">Filtrar por motivo</label>
              <select
                id="curadoria-filtro-motivo"
                value={motivoFiltro}
                onChange={(event) => {
                  setMotivoFiltro(event.target.value)
                  setItensSelecionados(new Set())
                  setPaginaPendentes(1)
                  setPaginaStatus(1)
                }}
                className="curadoria-select-motivo"
              >
                <option value="">Todos os motivos</option>
                {opcoesFiltro.map((motivo) => (
                  <option key={motivo} value={motivo}>
                    {motivo}
                  </option>
                ))}
              </select>
            </div>

            {aba === 'excluidos' && (
              <div className="curadoria-filtro-protecao">
                <span className="curadoria-filtro-sensivel-label">Proteção de imagens</span>
                <button
                  type="button"
                  className={`botao-borrar-imagens-sensivel ${imagensSensiveisBorradas ? 'ativo' : ''}`}
                  onClick={alternarBorradoSensivel}
                  aria-pressed={imagensSensiveisBorradas}
                >
                  <span className="botao-ocultar-imagens-icone" aria-hidden="true">
                    {imagensSensiveisBorradas ? (
                      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M2.5 12C4.7 7.7 8.1 5.5 12 5.5C15.9 5.5 19.3 7.7 21.5 12C19.3 16.3 15.9 18.5 12 18.5C8.1 18.5 4.7 16.3 2.5 12Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                        <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.8"/>
                        <path d="M4 4L20 20" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                      </svg>
                    ) : (
                      <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M2.5 12C4.7 7.7 8.1 5.5 12 5.5C15.9 5.5 19.3 7.7 21.5 12C19.3 16.3 15.9 18.5 12 18.5C8.1 18.5 4.7 16.3 2.5 12Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                        <circle cx="12" cy="12" r="3.2" stroke="currentColor" strokeWidth="1.8"/>
                      </svg>
                    )}
                  </span>
                  <span>{imagensSensiveisBorradas ? 'Imagens ocultas' : 'Mostrar imagens'}</span>
                </button>
              </div>
            )}
          </div>
        )}

        {mensagem && <div className="curadoria-mensagem">{mensagem}</div>}
        {erro && <div className="curadoria-erro" role="alert">{erro}</div>}

        {aba === 'pendentes' ? (
          <section className="curadoria-lista">
            {!carregandoLista && itensPendentesFiltrados.length > 0 && (
              <div className="curadoria-selecao-barra">
                <div className="curadoria-selecao-resumo">
                  <strong>{itensSelecionados.size}</strong>
                  <span>{itensSelecionados.size === 1 ? 'jogo selecionado' : 'jogos selecionados'}</span>
                  <small>Seleção limitada à página atual ({itensPendentesFiltrados.length} itens no máximo).</small>
                </div>
                <div className="curadoria-selecao-acoes">
                  <button
                    type="button"
                    className="botao-selecao-secundario"
                    onClick={selecionarPaginaSensivel}
                    disabled={processandoLote || !itensPendentesFiltrados.length}
                  >
                    {itensPendentesFiltrados.length > 0 && itensPendentesFiltrados.every((item) => itensSelecionados.has(item.id))
                      ? 'Desmarcar página'
                      : 'Selecionar página'}
                  </button>
                  {itensSelecionados.size > 0 && (
                    <>
                      <button type="button" className="botao-selecao-lote botao-selecao-aprovar" onClick={() => abrirAcaoLote('aprovar')} disabled={processandoLote}>Aprovar selecionados</button>
                      <button type="button" className="botao-selecao-lote botao-selecao-excluir" onClick={() => abrirAcaoLote('excluir')} disabled={processandoLote}>Excluir selecionados</button>
                      <button type="button" className="botao-selecao-secundario" onClick={limparSelecao} disabled={processandoLote}>Limpar seleção</button>
                    </>
                  )}
                </div>
              </div>
            )}
            {carregandoLista ? (
              <div className="curadoria-vazio">Carregando fila...</div>
            ) : itensPendentesFiltrados.length === 0 ? (
              <div className="curadoria-vazio">
                <span>✓</span>
                <strong>{(motivoFiltro || buscaPendentes) ? 'Nenhum jogo encontrado com os filtros atuais' : 'Nenhum jogo aguardando análise'}</strong>
                <p>{(motivoFiltro || buscaPendentes) ? 'Ajuste a pesquisa ou selecione outro motivo.' : 'A fila está limpa por enquanto.'}</p>
              </div>
            ) : (
              <>
              <PaginacaoCuradoria
                total={totalPendentesFiltrados}
                pagina={paginaPendentes}
                tamanhoPagina={ITENS_POR_PAGINA_LISTAS}
                onMudarPagina={(pagina) => { setPaginaPendentes(pagina); setItensSelecionados(new Set()) }}
                rotulo="Paginação da fila de análise, início"
              />
              {itensPendentesFiltrados.map((item) => (
                <article className="curadoria-card" key={item.id}>
                  <GaleriaCuradoria
                    item={item}
                    onCarregarMidias={() => solicitarMidias(item)}
                    midiasCarregando={midiasEmCarregamento.has(item.id)}
                    midiasConsultadas={midiasConsultadas.has(item.id)}
                    erroMidias={errosMidias.get(item.id) || ''}
                    imagemBorrada={
                      imagensSensiveisBorradas && (
                        aba === 'sensivel' ||
                        (aba === 'excluidos' && item.motivo === 'Conteúdo sensível')
                      )
                    }
                  />

                  <div className="curadoria-card-corpo">
                    <label className="curadoria-selecao-item">
                      <input
                        type="checkbox"
                        checked={itensSelecionados.has(item.id)}
                        onChange={() => alternarSelecao(item)}
                        disabled={processandoLote}
                      />
                      <span>Selecionar jogo</span>
                    </label>
                    <div className="curadoria-card-titulo">
                      <div>
                        <span className="curadoria-status">PENDENTE</span>
                        <h2>{item.nome}</h2>
                      </div>
                      <span className="curadoria-id">#{item.id}</span>
                    </div>

                    <div className="curadoria-meta">
                      <span>ID da loja: {item.epic_id || item.steam_id || 'não informado'}</span>
                      <span>Origem: {item.origem}</span>
                      {item.steam_conteudo_adulto && <span>Conteúdo sensível: sinalizado</span>}
                    </div>

                    {item.motivo && <p><strong>Motivo:</strong> {item.motivo}</p>}
                    {item.observacao && <p><strong>Observação:</strong> {item.observacao}</p>}

                    <div className="curadoria-acoes">
                      {obterUrlSteam(item) && (
                        <a
                          className="botao-loja"
                          href={obterUrlSteam(item)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🛒 Ver na Steam ↗
                        </a>
                      )}
                      {obterUrlEpic(item) && (
                        <a
                          className="botao-loja"
                          href={obterUrlEpic(item)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🛒 Ver na Epic Games ↗
                        </a>
                      )}
                      {!obterUrlSteam(item) && !obterUrlEpic(item) && (
                        <a
                          className="botao-loja"
                          href={`https://store.steampowered.com/search/?term=${encodeURIComponent(item.nome || '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🔎 Buscar na Steam ↗
                        </a>
                      )}

                      <button
                        type="button"
                        className="botao-aprovar"
                        disabled={acaoId === item.id}
                        onClick={() => abrirAprovacao(item)}
                      >
                        Aprovar
                      </button>
                      <button
                        type="button"
                        className="botao-excluir"
                        disabled={acaoId === item.id}
                        onClick={() => abrirExclusao(item)}
                      >
                        Excluir
                      </button>
                    </div>
                  </div>
                </article>
              ))}
              <PaginacaoCuradoria
                total={totalPendentesFiltrados}
                pagina={paginaPendentes}
                tamanhoPagina={ITENS_POR_PAGINA_LISTAS}
                onMudarPagina={(pagina) => { setPaginaPendentes(pagina); setItensSelecionados(new Set()) }}
                rotulo="Paginação da fila de análise, fim"
              />
              </>
            )}
          </section>
        ) : aba === 'sensivel' ? (
          <section className="curadoria-lista">
            <div className="curadoria-aviso-triagem">
              <strong>Fila de revisão, não confirmação final.</strong>
              <p>Os sinais e a prioridade ajudam a ordenar a análise, mas não comprovam sozinhos conteúdo explícito. Os jogos ficam pendentes até serem aprovados ou excluídos.</p>
            </div>

            <div className="curadoria-pesquisa-sensivel">
              <label htmlFor="curadoria-busca-sensivel">Filtrar esta fila</label>
              <input
                id="curadoria-busca-sensivel"
                type="search"
                value={filtroTextoSensivel}
                onChange={(event) => {
                  setFiltroTextoSensivel(event.target.value)
                  setPaginaSensivel(1)
                  setItensSelecionados(new Set())
                }}
                placeholder="Nome do jogo, ID da loja ou evidência..."
              />
              <span>{totalConteudosSensiveis.toLocaleString('pt-BR')} jogos</span>
            </div>

            {totalConteudosSensiveis > 0 && !carregandoStatus && (
              <div className="curadoria-selecao-barra">
                <div className="curadoria-selecao-resumo">
                  <strong>{itensSelecionados.size}</strong>
                  <span>{itensSelecionados.size === 1 ? 'jogo selecionado' : 'jogos selecionados'}</span>
                  <small>Seleção limitada à página atual ({conteudosSensiveisPaginados.length} itens no máximo).</small>
                </div>
                <div className="curadoria-selecao-acoes">
                  <button
                    type="button"
                    className="botao-selecao-secundario"
                    onClick={selecionarPaginaSensivel}
                    disabled={processandoLote || !conteudosSensiveisPaginados.length}
                  >
                    {conteudosSensiveisPaginados.length > 0 &&
                    conteudosSensiveisPaginados.every((item) => itensSelecionados.has(item.id))
                      ? 'Desmarcar página'
                      : 'Selecionar página'}
                  </button>
                  {itensSelecionados.size > 0 && (
                    <>
                      <button
                        type="button"
                        className="botao-selecao-lote botao-selecao-aprovar"
                        onClick={() => abrirAcaoLote('aprovar')}
                        disabled={processandoLote}
                      >
                        Aprovar selecionados
                      </button>
                      <button
                        type="button"
                        className="botao-selecao-lote botao-selecao-excluir"
                        onClick={() => abrirAcaoLote('excluir')}
                        disabled={processandoLote}
                      >
                        Excluir selecionados
                      </button>
                      <button
                        type="button"
                        className="botao-selecao-secundario"
                        onClick={limparSelecao}
                        disabled={processandoLote}
                      >
                        Limpar seleção
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}

            {carregandoStatus ? (
              <div className="curadoria-vazio">Carregando conteúdos sensíveis...</div>
            ) : totalConteudosSensiveis === 0 ? (
              <div className="curadoria-vazio">
                <span>✓</span>
                <strong>{termoSensivel ? 'Nenhum jogo corresponde ao filtro' : 'Nenhum conteúdo sensível pendente'}</strong>
                <p>{termoSensivel ? 'Experimente outro nome, ID ou termo de evidência.' : 'Use a busca acima para inserir manualmente um jogo.'}</p>
              </div>
            ) : (
              <>
              <PaginacaoCuradoria
                total={totalConteudosSensiveis}
                pagina={paginaSensivelAtual}
                tamanhoPagina={ITENS_POR_PAGINA_SENSIVEL}
                onMudarPagina={(pagina) => {
                  setPaginaSensivel(pagina)
                  setItensSelecionados(new Set())
                }}
                rotulo="Paginação de conteúdo sensível, início"
              />
              {conteudosSensiveisPaginados.map((item) => (
                <article className="curadoria-card" key={item.id}>
                  <GaleriaCuradoria
                    item={item}
                    onCarregarMidias={() => solicitarMidias(item)}
                    midiasCarregando={midiasEmCarregamento.has(item.id)}
                    midiasConsultadas={midiasConsultadas.has(item.id)}
                    erroMidias={errosMidias.get(item.id) || ''}
                    imagemBorrada={imagensSensiveisBorradas}
                  />

                  <div className="curadoria-card-corpo">
                    <label className="curadoria-selecao-item">
                      <input
                        type="checkbox"
                        checked={itensSelecionados.has(item.id)}
                        onChange={() => alternarSelecao(item)}
                        disabled={processandoLote}
                      />
                      <span>Selecionar jogo</span>
                    </label>
                    <div className="curadoria-card-titulo">
                      <div>
                        <span className="curadoria-status">PENDENTE DE REVISÃO</span>
                        <BadgePrioridade observacao={item.observacao} />
                        <h2>{item.nome}</h2>
                      </div>
                      <span className="curadoria-id">#{item.id}</span>
                    </div>

                    <div className="curadoria-meta">
                      <span>ID da loja: {item.epic_id || item.steam_id || 'não informado'}</span>
                      <span>Origem: {item.origem === 'triagem_adulto' ? 'Triagem automática' : (item.origem || 'manual')}</span>
                    </div>

                    {item.observacao && <p className="curadoria-observacao-triagem"><strong>Observação:</strong> {item.observacao}</p>}

                    <div className="curadoria-acoes">
                      {obterUrlSteam(item) && (
                        <a
                          className="botao-loja"
                          href={obterUrlSteam(item)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🛒 Ver na Steam ↗
                        </a>
                      )}
                      {obterUrlEpic(item) && (
                        <a
                          className="botao-loja"
                          href={obterUrlEpic(item)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🛒 Ver na Epic Games ↗
                        </a>
                      )}
                      {!obterUrlSteam(item) && !obterUrlEpic(item) && (
                        <a
                          className="botao-loja"
                          href={`https://store.steampowered.com/search/?term=${encodeURIComponent(item.nome || '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🔎 Buscar na Steam ↗
                        </a>
                      )}

                      <button
                        type="button"
                        className="botao-aprovar"
                        disabled={acaoId === item.id}
                        onClick={() => abrirAprovacao(item)}
                      >
                        Aprovar
                      </button>
                      <button
                        type="button"
                        className="botao-excluir"
                        disabled={acaoId === item.id}
                        onClick={() => abrirExclusao(item)}
                      >
                        Excluir
                      </button>
                    </div>
                  </div>
                </article>
              ))}
              <PaginacaoCuradoria
                total={totalConteudosSensiveis}
                pagina={paginaSensivelAtual}
                tamanhoPagina={ITENS_POR_PAGINA_SENSIVEL}
                onMudarPagina={(pagina) => {
                  setPaginaSensivel(pagina)
                  setItensSelecionados(new Set())
                }}
                rotulo="Paginação de conteúdo sensível, fim"
              />
              </>
            )}
          </section>
        ) : (
          <section className="curadoria-lista">
            {carregandoStatus ? (
              <div className="curadoria-vazio">Carregando registros...</div>
            ) : itensStatusFiltrados.length === 0 ? (
              <div className="curadoria-vazio">
                <span>✓</span>
                <strong>{(motivoFiltro || (aba === 'aprovados' ? buscaAprovados : buscaExcluidos)) ? 'Nenhum jogo encontrado com os filtros atuais' : 'Nenhum jogo nesta lista'}</strong>
                <p>{(motivoFiltro || (aba === 'aprovados' ? buscaAprovados : buscaExcluidos)) ? 'Ajuste a pesquisa ou selecione outro motivo.' : `Não há registros com status "${aba}" no momento.`}</p>
              </div>
            ) : (
              <>
              <PaginacaoCuradoria
                total={totalItensStatus}
                pagina={paginaStatus}
                tamanhoPagina={ITENS_POR_PAGINA_LISTAS}
                onMudarPagina={setPaginaStatus}
                rotulo={`Paginação da aba ${aba}, início`}
              />
              {itensStatusFiltrados.map((item) => (
                <article className="curadoria-card" key={item.id}>
                  <GaleriaCuradoria
                    item={item}
                    onCarregarMidias={() => solicitarMidias(item)}
                    midiasCarregando={midiasEmCarregamento.has(item.id)}
                    midiasConsultadas={midiasConsultadas.has(item.id)}
                    erroMidias={errosMidias.get(item.id) || ''}
                    imagemBorrada={
                      imagensSensiveisBorradas && (
                        aba === 'sensivel' ||
                        (aba === 'excluidos' && item.motivo === 'Conteúdo sensível')
                      )
                    }
                  />

                  <div className="curadoria-card-corpo">
                    <div className="curadoria-card-titulo">
                      <div>
                        <span className="curadoria-status">
                          {item.status === 'aprovado' ? 'APROVADO' : 'EXCLUÍDO'}
                        </span>
                        <h2>{item.nome}</h2>
                      </div>
                      <span className="curadoria-id">#{item.id}</span>
                    </div>

                    <div className="curadoria-meta">
                      <span>ID da loja: {item.epic_id || item.steam_id || 'não informado'}</span>
                      <span>Origem: {item.origem}</span>
                    </div>

                    {item.motivo && <p><strong>Motivo:</strong> {item.motivo}</p>}
                    {item.observacao && <p><strong>Observação:</strong> {item.observacao}</p>}
                    {item.decidido_em && (
                      <p><strong>Decidido em:</strong> {new Date(item.decidido_em).toLocaleString('pt-BR')}</p>
                    )}

                    <div className="curadoria-acoes">
                      {obterUrlSteam(item) && (
                        <a
                          className="botao-loja"
                          href={obterUrlSteam(item)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🛒 Ver na Steam ↗
                        </a>
                      )}
                      {obterUrlEpic(item) && (
                        <a
                          className="botao-loja"
                          href={obterUrlEpic(item)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🛒 Ver na Epic Games ↗
                        </a>
                      )}
                      {!obterUrlSteam(item) && !obterUrlEpic(item) && (
                        <a
                          className="botao-loja"
                          href={`https://store.steampowered.com/search/?term=${encodeURIComponent(item.nome || '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          🔎 Buscar na Steam ↗
                        </a>
                      )}

                      <button
                        type="button"
                        className="botao-reabrir"
                        disabled={acaoId === item.id}
                        onClick={() => reabrir(item)}
                      >
                        {acaoId === item.id ? 'Reabrindo...' : 'Reabrir análise'}
                      </button>
                    </div>
                  </div>
                </article>
              ))}
              <PaginacaoCuradoria
                total={totalItensStatus}
                pagina={paginaStatus}
                tamanhoPagina={ITENS_POR_PAGINA_LISTAS}
                onMudarPagina={setPaginaStatus}
                rotulo={`Paginação da aba ${aba}, fim`}
              />
              </>
            )}
          </section>
        )}
        </>
        )}

        {acaoLote && (
          <div
            className="curadoria-modal-overlay"
            role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) fecharAcaoLote()
            }}
          >
            <div
              className="curadoria-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="curadoria-modal-lote-titulo"
            >
              <div className="curadoria-modal-cabecalho">
                <div>
                  <span className="curadoria-status">
                    {acaoLote === 'aprovar' ? 'APROVAÇÃO EM LOTE' : 'EXCLUSÃO EM LOTE'}
                  </span>
                  <h2 id="curadoria-modal-lote-titulo">
                    {acaoLote === 'aprovar' ? 'Aprovar jogos selecionados' : 'Excluir jogos selecionados'}
                  </h2>
                </div>
                <button
                  type="button"
                  className="curadoria-modal-fechar"
                  onClick={fecharAcaoLote}
                  aria-label="Fechar"
                  disabled={processandoLote}
                >
                  ×
                </button>
              </div>

              <p>
                Você está aplicando a mesma decisão a <strong>{itensSelecionados.size} jogo(s)</strong>.
                Selecione a justificativa para todos os itens.
              </p>

              <div className="curadoria-modal-lista-selecao">
                {(aba === 'pendentes' ? itensPendentesFiltrados : conteudosSensiveisPaginados)
                  .filter((item) => itensSelecionados.has(item.id))
                  .slice(0, 8)
                  .map((item) => <span key={item.id}>{item.nome}</span>)}
                {itensSelecionados.size > 8 && (
                  <small>+ {itensSelecionados.size - 8} outro(s)</small>
                )}
              </div>

              <label className="curadoria-modal-label" htmlFor="motivo-lote">
                {acaoLote === 'aprovar' ? 'Motivo da aprovação' : 'Motivo da exclusão'}
              </label>
              <select
                id="motivo-lote"
                value={motivoLote}
                onChange={(event) => {
                  const valor = event.target.value
                  setMotivoLote(valor)
                  if (valor !== 'Outros') setObservacaoLote('')
                }}
                className="curadoria-modal-select"
                autoFocus
                disabled={processandoLote}
              >
                <option value="" disabled hidden>Selecione um motivo...</option>
                {(acaoLote === 'aprovar' ? MOTIVOS_APROVACAO : MOTIVOS_AUDITORIA).map((motivo) => (
                  <option key={motivo} value={motivo}>{motivo}</option>
                ))}
              </select>

              {acaoLote === 'excluir' && motivoLote === 'Conteúdo sensível' && (
                <div className="curadoria-aviso-lote curadoria-aviso-lote-sensivel">
                  <strong>Busca automática de relacionados</strong>
                  <p>Essa justificativa aciona a busca por jogos da mesma desenvolvedora ou publicadora para encaminhá-los à avaliação de conteúdo sensível, quando aplicável. A operação será executada um jogo por vez.</p>
                </div>
              )}

              {acaoLote === 'excluir' && motivoLote === 'Fora do catálogo' && (
                <div className="curadoria-aviso-lote curadoria-aviso-lote-fora-catalogo">
                  <strong>Busca automática de relacionados</strong>
                  <p>Essa justificativa aciona a busca por jogos da mesma desenvolvedora ou publicadora para encaminhá-los à fila normal de avaliação com o motivo "Fora do catálogo", quando aplicável. Jogos já aprovados, já excluídos ou pendentes por outro motivo terão suas decisões e filas preservadas. A operação será executada um jogo por vez.</p>
                </div>
              )}

              {motivoLote === 'Outros' && (
                <div className="curadoria-modal-outros">
                  <label className="curadoria-modal-label" htmlFor="observacao-lote">
                    Explique o motivo
                  </label>
                  <textarea
                    id="observacao-lote"
                    value={observacaoLote}
                    onChange={(event) => setObservacaoLote(event.target.value)}
                    className="curadoria-modal-textarea"
                    rows={4}
                    maxLength={1000}
                    placeholder={acaoLote === 'aprovar'
                      ? 'Descreva por que os jogos devem ser aprovados...'
                      : 'Descreva por que os jogos devem ser excluídos...'}
                    disabled={processandoLote}
                  />
                  <small className="curadoria-modal-contador">{observacaoLote.length}/1000</small>
                </div>
              )}

              <div className="curadoria-modal-acoes">
                <button
                  type="button"
                  className="botao-modal-cancelar"
                  onClick={fecharAcaoLote}
                  disabled={processandoLote}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className={`botao-modal-confirmar ${acaoLote === 'aprovar' ? 'botao-modal-aprovar' : ''}`}
                  onClick={confirmarAcaoLote}
                  disabled={
                    !motivoLote ||
                    (motivoLote === 'Outros' && !observacaoLote.trim()) ||
                    processandoLote ||
                    !itensSelecionados.size
                  }
                >
                  {processandoLote
                    ? `${acaoLote === 'aprovar' ? 'Aprovando' : 'Excluindo'} ${progressoLote.concluidos}/${progressoLote.total}...`
                    : (acaoLote === 'aprovar' ? 'Confirmar aprovações' : 'Confirmar exclusões')}
                </button>
              </div>
            </div>
          </div>
        )}

        {aprovacaoPendente && (
          <div
            className="curadoria-modal-overlay"
            role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) fecharAprovacao()
            }}
          >
            <div
              className="curadoria-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="curadoria-modal-aprovacao-titulo"
            >
              <div className="curadoria-modal-cabecalho">
                <div>
                  <span className="curadoria-status">APROVAÇÃO</span>
                  <h2 id="curadoria-modal-aprovacao-titulo">Aprovar jogo</h2>
                </div>
                <button
                  type="button"
                  className="curadoria-modal-fechar"
                  onClick={fecharAprovacao}
                  aria-label="Fechar"
                >
                  ×
                </button>
              </div>

              <p>
                Selecione a justificativa para aprovar <strong>{aprovacaoPendente.nome}</strong>.
              </p>

              <label className="curadoria-modal-label" htmlFor="motivo-aprovacao">
                Motivo da aprovação
              </label>
              <select
                id="motivo-aprovacao"
                value={motivoAprovacao}
                onChange={(event) => {
                  const valor = event.target.value
                  setMotivoAprovacao(valor)
                  if (valor !== 'Outros') setObservacaoAprovacao('')
                }}
                className="curadoria-modal-select"
                autoFocus
              >
                <option value="" disabled hidden>Selecione um motivo...</option>
                {MOTIVOS_APROVACAO.map((motivo) => (
                  <option key={motivo} value={motivo}>
                    {motivo}
                  </option>
                ))}
              </select>

              {motivoAprovacao === 'Outros' && (
                <div className="curadoria-modal-outros">
                  <label className="curadoria-modal-label" htmlFor="observacao-aprovacao">
                    Explique o motivo
                  </label>
                  <textarea
                    id="observacao-aprovacao"
                    value={observacaoAprovacao}
                    onChange={(event) => setObservacaoAprovacao(event.target.value)}
                    className="curadoria-modal-textarea"
                    rows={4}
                    maxLength={1000}
                    placeholder="Descreva por que o jogo deve ser aprovado..."
                  />
                  <small className="curadoria-modal-contador">
                    {observacaoAprovacao.length}/1000
                  </small>
                </div>
              )}

              <div className="curadoria-modal-acoes">
                <button
                  type="button"
                  className="botao-modal-cancelar"
                  onClick={fecharAprovacao}
                  disabled={acaoId === aprovacaoPendente.id}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className="botao-modal-confirmar botao-modal-aprovar"
                  onClick={confirmarAprovacao}
                  disabled={
                    !motivoAprovacao ||
                    (motivoAprovacao === 'Outros' && !observacaoAprovacao.trim()) ||
                    acaoId === aprovacaoPendente.id
                  }
                >
                  {acaoId === aprovacaoPendente.id ? 'Aprovando...' : 'Confirmar aprovação'}
                </button>
              </div>
            </div>
          </div>
        )}

        {exclusaoPendente && (
          <div
            className="curadoria-modal-overlay"
            role="presentation"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) fecharExclusao()
            }}
          >
            <div
              className="curadoria-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="curadoria-modal-titulo"
            >
              <div className="curadoria-modal-cabecalho">
                <div>
                  <span className="curadoria-status">EXCLUSÃO</span>
                  <h2 id="curadoria-modal-titulo">Excluir jogo da curadoria</h2>
                </div>
                <button
                  type="button"
                  className="curadoria-modal-fechar"
                  onClick={fecharExclusao}
                  aria-label="Fechar"
                >
                  ×
                </button>
              </div>

              <p>
                Selecione o motivo pelo qual <strong>{exclusaoPendente.nome}</strong>
                {' '}deve ser excluído.
              </p>

              <label className="curadoria-modal-label" htmlFor="motivo-exclusao">
                Motivo da exclusão
              </label>
              <select
                id="motivo-exclusao"
                value={motivoExclusao}
                onChange={(event) => {
                  const valor = event.target.value
                  setMotivoExclusao(valor)
                  if (valor !== 'Outros') {
                    setObservacaoExclusao('')
                  }
                }}
                className="curadoria-modal-select"
                autoFocus
              >
                <option value="" disabled hidden>Selecione um motivo...</option>
                {MOTIVOS_AUDITORIA.map((motivo) => (
                  <option key={motivo} value={motivo}>
                    {motivo}
                  </option>
                ))}
              </select>

              {motivoExclusao === 'Conteúdo sensível' && (
                <div className="curadoria-aviso-lote curadoria-aviso-lote-sensivel">
                  <strong>Busca automática de relacionados</strong>
                  <p>Essa justificativa aciona a busca por jogos da mesma desenvolvedora ou publicadora para encaminhá-los à avaliação de conteúdo sensível, quando aplicável.</p>
                </div>
              )}

              {motivoExclusao === 'Fora do catálogo' && (
                <div className="curadoria-aviso-lote curadoria-aviso-lote-fora-catalogo">
                  <strong>Busca automática de relacionados</strong>
                  <p>Essa justificativa aciona a busca por jogos da mesma desenvolvedora ou publicadora para encaminhá-los à fila normal de avaliação com o motivo &quot;Fora do catálogo&quot;, quando aplicável. Jogos já aprovados, já excluídos ou pendentes por outro motivo terão suas decisões e filas preservadas.</p>
                </div>
              )}

              {motivoExclusao === 'Outros' && (
                <div className="curadoria-modal-outros">
                  <label className="curadoria-modal-label" htmlFor="observacao-exclusao">
                    Explique o motivo
                  </label>
                  <textarea
                    id="observacao-exclusao"
                    value={observacaoExclusao}
                    onChange={(event) => setObservacaoExclusao(event.target.value)}
                    className="curadoria-modal-textarea"
                    rows={4}
                    maxLength={1000}
                    placeholder="Descreva por que o jogo deve ser excluído..."
                  />
                  <small className="curadoria-modal-contador">
                    {observacaoExclusao.length}/1000
                  </small>
                </div>
              )}

              <div className="curadoria-modal-acoes">
                <button
                  type="button"
                  className="botao-modal-cancelar"
                  onClick={fecharExclusao}
                  disabled={acaoId === exclusaoPendente.id}
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  className="botao-modal-confirmar"
                  onClick={confirmarExclusao}
                  disabled={
                    !motivoExclusao ||
                    (motivoExclusao === 'Outros' && !observacaoExclusao.trim()) ||
                    acaoId === exclusaoPendente.id
                  }
                >
                  {acaoId === exclusaoPendente.id ? 'Excluindo...' : 'Confirmar exclusão'}
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default Curadoria
