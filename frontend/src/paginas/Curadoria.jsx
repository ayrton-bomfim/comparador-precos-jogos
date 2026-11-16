import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import { API_BASE, useAuth } from '../contextos/AuthContext'
import AjudaCuradoria from './curadoria/AjudaCuradoria'
import AvisoFlutuante from './curadoria/AvisoFlutuante'
import BuscaCatalogo from './curadoria/BuscaCatalogo'
import ListaFila from './curadoria/ListaFila'
import PainelJogo from './curadoria/PainelJogo'
import SecaoVitrine from './curadoria/SecaoVitrine'
import { IconeAjuda, IconeAnterior, IconeCheck, IconeExterno, IconeFechar, IconeMais, IconeOlho, IconeProximo } from './curadoria/Icones'
import {
  ABAS,
  ABAS_DECISAO,
  ABAS_FILA,
  ITENS_POR_PAGINA,
  MOTIVOS_APROVACAO,
  MOTIVOS_AUDITORIA,
  MOTIVOS_COM_RELACIONADOS,
  campoDeTextoEmFoco,
  deveBorrar,
  formatarData,
  formatarNumero,
  motivosDoFiltro,
  rotaDaFila,
} from './curadoria/utilidades'
import './Curadoria.css'

const CONTADORES_INICIAIS = { pendentes: 0, sensivel: 0, aprovados: 0, excluidos: 0, vitrine: 0, feedback: 0 }

function PaginacaoCompacta({ total, pagina, onMudar, rotulo = 'Paginação' }) {
  if (!total) return null
  const totalPaginas = Math.max(1, Math.ceil(total / ITENS_POR_PAGINA))
  const inicio = (pagina - 1) * ITENS_POR_PAGINA + 1
  const fim = Math.min(pagina * ITENS_POR_PAGINA, total)

  return (
    <nav className="cur-paginacao" aria-label={rotulo}>
      <span>{formatarNumero(inicio)}–{formatarNumero(fim)} de {formatarNumero(total)}</span>
      <button type="button" className="cur-btn cur-btn--icone cur-btn--p" onClick={() => onMudar(pagina - 1)} disabled={pagina <= 1} aria-label="Página anterior"><IconeAnterior /></button>
      <button type="button" className="cur-btn cur-btn--icone cur-btn--p" onClick={() => onMudar(pagina + 1)} disabled={pagina >= totalPaginas} aria-label="Próxima página"><IconeProximo /></button>
    </nav>
  )
}

function somarRelacionados(dados) {
  return ['jogos_relacionados_adicionados', 'jogos_relacionados_reabertos', 'jogos_relacionados_reclassificados']
    .reduce((total, campo) => total + Number(dados?.[campo] || 0), 0)
}

function PainelCuradoria() {
  const { token } = useAuth()

  // Mantém a função de cabeçalhos estável entre renovações do token.
  const tokenAtualRef = useRef(token)
  useEffect(() => { tokenAtualRef.current = token }, [token])
  const getHeaders = useCallback(() => ({
    Authorization: `Bearer ${tokenAtualRef.current}`,
    'Content-Type': 'application/json',
  }), [])

  const [aba, setAba] = useState('pendentes')
  const [contadores, setContadores] = useState(CONTADORES_INICIAIS)

  // Fila atual (pendentes, sensível, aprovados ou excluídos)
  const [itensFila, setItensFila] = useState([])
  const [totalFila, setTotalFila] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [carregandoFila, setCarregandoFila] = useState(false)
  const [erroFila, setErroFila] = useState('')
  const [filtroTexto, setFiltroTexto] = useState('')
  const [termoFiltro, setTermoFiltro] = useState('')
  const [motivoFiltro, setMotivoFiltro] = useState('')
  const [selecionadoId, setSelecionadoId] = useState(null)
  const [painelAberto, setPainelAberto] = useState(false)
  const [imagensBorradas, setImagensBorradas] = useState(true)
  const [acaoId, setAcaoId] = useState(null)
  const [modoAtalho, setModoAtalho] = useState(null)
  const [outros, setOutros] = useState(null)

  // Ações em lote
  const [itensSelecionados, setItensSelecionados] = useState(() => new Set())
  const [acaoLote, setAcaoLote] = useState(null)
  const [motivoLote, setMotivoLote] = useState('')
  const [observacaoLote, setObservacaoLote] = useState('')
  const [processandoLote, setProcessandoLote] = useState(false)
  const [progressoLote, setProgressoLote] = useState({ concluidos: 0, total: 0 })

  // Galeria: só é consultada após clique explícito.
  const [midiasEmCarregamento, setMidiasEmCarregamento] = useState(() => new Set())
  const [midiasConsultadas, setMidiasConsultadas] = useState(() => new Set())
  const [errosMidias, setErrosMidias] = useState(() => new Map())
  const idsMidiaEmRequisicao = useRef(new Set())

  // Avisos e diálogos
  const [aviso, setAviso] = useState(null)
  const [mostrarAjuda, setMostrarAjuda] = useState(false)
  const [mostrarAdicionar, setMostrarAdicionar] = useState(false)
  const [adicionadosIds, setAdicionadosIds] = useState(() => new Set())

  // Feedback
  const [feedbackItens, setFeedbackItens] = useState([])
  const [feedbackTotal, setFeedbackTotal] = useState(0)
  const [paginaFeedback, setPaginaFeedback] = useState(1)
  const [feedbackStatus, setFeedbackStatus] = useState('pendente')
  const [feedbackCarregando, setFeedbackCarregando] = useState(false)
  const [feedbackErro, setFeedbackErro] = useState('')
  const [feedbackAcaoId, setFeedbackAcaoId] = useState(null)

  const sequenciaFila = useRef(0)
  const ultimaDecisaoRef = useRef(null)
  const contadorAvisos = useRef(0)
  const paginaRef = useRef(null)
  const barraRef = useRef(null)

  const ehFila = ABAS_FILA.includes(aba)
  const podeDecidir = ABAS_DECISAO.includes(aba)

  const notificar = useCallback((texto, tipo = 'sucesso', acao = null) => {
    contadorAvisos.current += 1
    setAviso({ id: contadorAvisos.current, texto, tipo, acao })
  }, [])
  const fecharAviso = useCallback(() => setAviso(null), [])

  // A barra de abas fica fixa; o painel lateral usa a altura dela como deslocamento.
  useEffect(() => {
    const barra = barraRef.current
    const raiz = paginaRef.current
    if (!barra || !raiz || typeof ResizeObserver === 'undefined') return undefined
    const observador = new ResizeObserver(() => {
      raiz.style.setProperty('--cur-altura-barra', `${barra.offsetHeight}px`)
    })
    observador.observe(barra)
    return () => observador.disconnect()
  }, [])

  // ---------------------------------------------------------------------
  // Contadores das abas
  // ---------------------------------------------------------------------
  const atualizarContadores = useCallback(async () => {
    const headers = getHeaders()
    const buscarTotal = async (url) => {
      const resposta = await fetch(`${API_BASE}${url}`, { headers })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Falha ao consultar contador.')
      return Array.isArray(dados) ? dados.length : Number(dados.total_geral ?? dados.total ?? 0)
    }
    const consultas = {
      pendentes: '/api/admin/curadoria/pendentes?page=1&page_size=1',
      sensivel: '/api/admin/curadoria/conteudo-sensivel?page=1&page_size=1',
      aprovados: '/api/admin/curadoria/status/aprovado?page=1&page_size=1',
      excluidos: '/api/admin/curadoria/status/excluido?page=1&page_size=1',
      vitrine: '/api/admin/curadoria/vitrine?page=1&page_size=1',
      feedback: '/api/admin/feedback?status=pendente&page=1&page_size=1',
    }
    const chaves = Object.keys(consultas)
    const resultados = await Promise.allSettled(chaves.map((chave) => buscarTotal(consultas[chave])))
    setContadores((atuais) => {
      const proximos = { ...atuais }
      resultados.forEach((resultado, indice) => {
        if (resultado.status === 'fulfilled') proximos[chaves[indice]] = resultado.value
      })
      return proximos
    })
  }, [getHeaders])

  useEffect(() => {
    atualizarContadores()
  }, [atualizarContadores])

  // ---------------------------------------------------------------------
  // Fila
  // ---------------------------------------------------------------------
  const carregarFila = useCallback(async () => {
    if (!ABAS_FILA.includes(aba)) return
    const sequencia = ++sequenciaFila.current
    setCarregandoFila(true)
    setErroFila('')

    try {
      const parametros = new URLSearchParams({ page: String(pagina), page_size: String(ITENS_POR_PAGINA) })
      if (motivoFiltro && aba !== 'sensivel') parametros.set('motivo', motivoFiltro)
      if (termoFiltro) parametros.set('q', termoFiltro)

      const resposta = await fetch(`${API_BASE}${rotaDaFila(aba)}?${parametros}`, { headers: getHeaders() })
      const dados = await resposta.json().catch(() => ({}))
      if (sequencia !== sequenciaFila.current) return
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar a fila.')

      const total = Number(dados.total || 0)
      const ultimaPagina = Math.max(1, Math.ceil(total / ITENS_POR_PAGINA))
      if (pagina > ultimaPagina) {
        setPagina(ultimaPagina)
        return
      }
      setItensFila(Array.isArray(dados.items) ? dados.items : [])
      setTotalFila(total)
    } catch (error) {
      if (sequencia !== sequenciaFila.current) return
      setItensFila([])
      setTotalFila(0)
      setErroFila(error.message)
    } finally {
      if (sequencia === sequenciaFila.current) setCarregandoFila(false)
    }
  }, [aba, pagina, motivoFiltro, termoFiltro, getHeaders])

  // Ações disparadas por avisos antigos (ex.: "Desfazer") usam sempre a versão atual.
  const carregarFilaRef = useRef(carregarFila)
  useEffect(() => { carregarFilaRef.current = carregarFila }, [carregarFila])

  useEffect(() => {
    carregarFila()
  }, [carregarFila])

  // O filtro de texto é aplicado no servidor, 350 ms depois da última tecla.
  useEffect(() => {
    const termo = filtroTexto.trim()
    if (termo === termoFiltro) return undefined
    const temporizador = window.setTimeout(() => {
      setTermoFiltro(termo)
      setPagina(1)
      setItensSelecionados(new Set())
    }, 350)
    return () => window.clearTimeout(temporizador)
  }, [filtroTexto, termoFiltro])

  let indiceAtual = itensFila.findIndex((item) => item.id === selecionadoId)
  if (indiceAtual < 0) indiceAtual = 0
  const itemSelecionado = itensFila[indiceAtual] || null
  const totalPaginasFila = Math.max(1, Math.ceil(totalFila / ITENS_POR_PAGINA))

  const selecionar = (item, abrirPainel = true) => {
    setSelecionadoId(item.id)
    setModoAtalho(null)
    setOutros(null)
    if (abrirPainel) setPainelAberto(true)
  }

  const navegar = (deslocamento) => {
    const destino = itensFila[indiceAtual + deslocamento]
    if (!destino) return
    selecionar(destino, false)
    window.requestAnimationFrame(() => {
      document.getElementById(`cur-item-${destino.id}`)?.scrollIntoView({ block: 'nearest' })
    })
  }

  const mudarPagina = (novaPagina) => {
    setPagina(novaPagina)
    setSelecionadoId(null)
    setItensSelecionados(new Set())
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const trocarAba = (novaAba) => {
    if (novaAba === aba) return
    sequenciaFila.current += 1
    setAba(novaAba)
    setPagina(1)
    setItensFila([])
    setTotalFila(0)
    setErroFila('')
    setFiltroTexto('')
    setTermoFiltro('')
    setMotivoFiltro('')
    setSelecionadoId(null)
    setPainelAberto(false)
    setItensSelecionados(new Set())
    setModoAtalho(null)
    setOutros(null)
    setImagensBorradas(true)
  }

  const removerDaFila = (idsRemovidos) => {
    const posicao = itensFila.findIndex((item) => idsRemovidos.has(item.id))
    const restantes = itensFila.filter((item) => !idsRemovidos.has(item.id))
    const proximo = restantes[Math.min(Math.max(posicao, 0), restantes.length - 1)] || null
    setItensFila(restantes)
    setTotalFila((total) => Math.max(0, total - idsRemovidos.size))
    setSelecionadoId(proximo?.id ?? null)
    setItensSelecionados((atuais) => {
      const proximos = new Set(atuais)
      idsRemovidos.forEach((id) => proximos.delete(id))
      return proximos
    })
    if (!proximo) setPainelAberto(false)
  }

  // ---------------------------------------------------------------------
  // Galeria
  // ---------------------------------------------------------------------
  const solicitarMidias = async (item) => {
    const id = item.id
    if (idsMidiaEmRequisicao.current.has(id) || midiasConsultadas.has(id)) return
    idsMidiaEmRequisicao.current.add(id)
    setMidiasEmCarregamento((atuais) => new Set(atuais).add(id))
    setErrosMidias((atuais) => {
      const proximos = new Map(atuais)
      proximos.delete(id)
      return proximos
    })

    try {
      const resposta = await fetch(`${API_BASE}/api/admin/curadoria/${id}/midias`, {
        method: 'POST',
        headers: getHeaders(),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar a galeria deste jogo.')
      setItensFila((atuais) => atuais.map((registro) => (registro.id === id ? { ...registro, ...dados } : registro)))
      setMidiasConsultadas((atuais) => new Set(atuais).add(id))
    } catch (error) {
      setErrosMidias((atuais) => new Map(atuais).set(id, error.message || 'Falha ao carregar a galeria.'))
    } finally {
      idsMidiaEmRequisicao.current.delete(id)
      setMidiasEmCarregamento((atuais) => {
        const proximos = new Set(atuais)
        proximos.delete(id)
        return proximos
      })
    }
  }

  // ---------------------------------------------------------------------
  // Decisões
  // ---------------------------------------------------------------------
  const desfazer = async (item) => {
    ultimaDecisaoRef.current = null
    try {
      // Devolve o motivo e a observação originais para o jogo voltar à fila certa.
      const corpo = {}
      if (MOTIVOS_AUDITORIA.includes(item.motivo)) corpo.motivo = item.motivo
      if (item.observacao) corpo.observacao = item.observacao

      const resposta = await fetch(`${API_BASE}/api/admin/curadoria/${item.id}/reabrir`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(corpo),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível desfazer a decisão.')

      setSelecionadoId(item.id)
      notificar(`Decisão desfeita: ${item.nome} voltou para a fila.`, 'info')
      carregarFilaRef.current()
      atualizarContadores()
    } catch (error) {
      notificar(error.message, 'erro')
    }
  }

  const decidir = async (item, decisao, motivo, observacao = '') => {
    if (acaoId !== null) return
    setAcaoId(item.id)
    setModoAtalho(null)

    try {
      const corpo = { motivo }
      if (observacao) corpo.observacao = observacao
      const resposta = await fetch(`${API_BASE}/api/admin/curadoria/${item.id}/${decisao}`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify(corpo),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível registrar a decisão.')

      removerDaFila(new Set([item.id]))
      setOutros(null)

      const encaminhados = somarRelacionados(dados)
      let texto = `${item.nome} foi ${decisao === 'aprovar' ? 'aprovado' : 'excluído'} (${motivo}).`
      if (encaminhados > 0) {
        texto += ` ${encaminhados} jogo(s) da mesma desenvolvedora/publicadora foram para revisão.`
      }
      ultimaDecisaoRef.current = { item }
      notificar(texto, 'sucesso', { rotulo: 'Desfazer', onClick: () => desfazer(item) })

      carregarFila()
      atualizarContadores()
    } catch (error) {
      notificar(error.message, 'erro')
    } finally {
      setAcaoId(null)
    }
  }

  const reabrir = async (item) => {
    setAcaoId(item.id)
    try {
      const resposta = await fetch(`${API_BASE}/api/admin/curadoria/${item.id}/reabrir`, {
        method: 'POST',
        headers: getHeaders(),
        body: JSON.stringify({}),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível reabrir a análise.')

      removerDaFila(new Set([item.id]))
      notificar(`${item.nome} voltou para a fila de análise.`)
      carregarFila()
      atualizarContadores()
    } catch (error) {
      notificar(error.message, 'erro')
    } finally {
      setAcaoId(null)
    }
  }

  // ---------------------------------------------------------------------
  // Seleção e lote (limitados à página atual)
  // ---------------------------------------------------------------------
  const alternarSelecao = (item) => {
    setItensSelecionados((atuais) => {
      const proximos = new Set(atuais)
      if (proximos.has(item.id)) proximos.delete(item.id)
      else proximos.add(item.id)
      return proximos
    })
  }

  const todosSelecionados = itensFila.length > 0 && itensFila.every((item) => itensSelecionados.has(item.id))
  const selecionarPagina = () => {
    setItensSelecionados(todosSelecionados ? new Set() : new Set(itensFila.map((item) => item.id)))
  }

  const abrirAcaoLote = (decisao) => {
    if (!itensSelecionados.size || processandoLote) return
    setMotivoLote('')
    setObservacaoLote('')
    setAcaoLote(decisao)
  }

  const fecharAcaoLote = () => {
    if (processandoLote) return
    setAcaoLote(null)
  }

  const confirmarAcaoLote = async () => {
    if (!acaoLote || !motivoLote || processandoLote) return
    if (motivoLote === 'Outros' && !observacaoLote.trim()) return

    const itens = itensFila.filter((item) => itensSelecionados.has(item.id))
    if (!itens.length) {
      notificar('Nenhum jogo selecionado está mais na página atual.', 'erro')
      return
    }

    setProcessandoLote(true)
    setProgressoLote({ concluidos: 0, total: itens.length })
    const corpo = { motivo: motivoLote }
    if (motivoLote === 'Outros') corpo.observacao = observacaoLote.trim()

    const resultados = Array(itens.length)
    let proximoIndice = 0
    const trabalhador = async () => {
      while (proximoIndice < itens.length) {
        const indice = proximoIndice++
        const item = itens[indice]
        try {
          const resposta = await fetch(`${API_BASE}/api/admin/curadoria/${item.id}/${acaoLote}`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(corpo),
          })
          const dados = await resposta.json().catch(() => ({}))
          if (!resposta.ok) throw new Error(dados.detail || `Não foi possível processar ${item.nome}.`)
          resultados[indice] = { ok: true, item, dados }
        } catch (error) {
          resultados[indice] = { ok: false, item, erro: error }
        } finally {
          setProgressoLote((atual) => ({ ...atual, concluidos: Math.min(atual.concluidos + 1, atual.total) }))
        }
      }
    }

    // Exclusões que buscam jogos relacionados rodam uma por vez para evitar conflitos.
    const buscaRelacionados = acaoLote === 'excluir' && MOTIVOS_COM_RELACIONADOS.includes(motivoLote)
    await Promise.all(Array.from({ length: buscaRelacionados ? 1 : Math.min(3, itens.length) }, trabalhador))

    const concluidos = resultados.filter((resultado) => resultado?.ok)
    const falhas = resultados.filter((resultado) => resultado && !resultado.ok)

    if (concluidos.length) {
      removerDaFila(new Set(concluidos.map((resultado) => resultado.item.id)))
      const encaminhados = concluidos.reduce((total, resultado) => total + somarRelacionados(resultado.dados), 0)
      let texto = `${concluidos.length} jogo(s) ${acaoLote === 'aprovar' ? 'aprovado(s)' : 'excluído(s)'} (${motivoLote}).`
      if (encaminhados) texto += ` ${encaminhados} jogo(s) relacionado(s) foram para revisão.`
      notificar(texto)
      carregarFila()
      atualizarContadores()
    }
    if (falhas.length) {
      const nomes = falhas.slice(0, 3).map((resultado) => resultado.item.nome).join(', ')
      notificar(
        `${falhas.length} jogo(s) não foram processados: ${nomes}${falhas.length > 3 ? '...' : ''}. Eles continuam selecionados.`,
        'erro'
      )
    }

    setProcessandoLote(false)
    setAcaoLote(null)
  }

  // ---------------------------------------------------------------------
  // Adicionar jogo à fila
  // ---------------------------------------------------------------------
  const adicionar = async (jogo, destino) => {
    const chave = `${destino}-${jogo.id}`
    setAcaoId(chave)
    try {
      const sensivel = destino === 'sensivel'
      const resposta = await fetch(
        `${API_BASE}/api/admin/curadoria/${sensivel ? 'conteudo-sensivel' : ''}`,
        {
          method: 'POST',
          headers: getHeaders(),
          body: JSON.stringify(
            sensivel
              ? { jogo_id: jogo.id, observacao: 'Inclusão manual na fila de conteúdo sensível' }
              : { jogo_id: jogo.id }
          ),
        }
      )
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível adicionar o jogo.')

      setAdicionadosIds((atuais) => new Set(atuais).add(chave))
      notificar(`${jogo.nome} foi enviado para ${sensivel ? 'a fila de conteúdo sensível' : 'análise'}.`)
      atualizarContadores()
      if (aba === destino) carregarFila()
    } catch (error) {
      notificar(error.message, 'erro')
    } finally {
      setAcaoId(null)
    }
  }

  // ---------------------------------------------------------------------
  // Feedback
  // ---------------------------------------------------------------------
  const carregarFeedback = useCallback(async () => {
    setFeedbackCarregando(true)
    setFeedbackErro('')
    try {
      const parametros = new URLSearchParams({
        status: feedbackStatus,
        page: String(paginaFeedback),
        page_size: String(ITENS_POR_PAGINA),
      })
      const resposta = await fetch(`${API_BASE}/api/admin/feedback?${parametros}`, { headers: getHeaders() })
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
  }, [getHeaders, feedbackStatus, paginaFeedback])

  useEffect(() => {
    if (aba === 'feedback') carregarFeedback()
  }, [aba, carregarFeedback])

  const atualizarStatusFeedback = async (item) => {
    setFeedbackAcaoId(item.id)
    setFeedbackErro('')
    try {
      const resposta = await fetch(`${API_BASE}/api/admin/feedback/${item.id}/concluir`, {
        method: 'PATCH',
        headers: getHeaders(),
        body: JSON.stringify({ concluido: item.status !== 'concluido' }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível atualizar o feedback.')
      await carregarFeedback()
      atualizarContadores()
    } catch (error) {
      setFeedbackErro(error.message || 'Falha ao atualizar feedback.')
    } finally {
      setFeedbackAcaoId(null)
    }
  }

  // ---------------------------------------------------------------------
  // Atalhos de teclado
  // ---------------------------------------------------------------------
  useEffect(() => {
    const aoTeclar = (event) => {
      if (event.ctrlKey || event.metaKey || event.altKey) return

      // Esc fecha qualquer diálogo aberto, em todas as abas.
      if (mostrarAjuda || mostrarAdicionar || acaoLote) {
        if (event.key === 'Escape') {
          setMostrarAjuda(false)
          setMostrarAdicionar(false)
          fecharAcaoLote()
        }
        return
      }
      if (!ehFila || campoDeTextoEmFoco(document.activeElement)) return

      const tecla = event.key.length === 1 ? event.key.toLowerCase() : event.key
      if (tecla === '?') {
        event.preventDefault()
        setMostrarAjuda(true)
        return
      }
      if (tecla === 'Escape') {
        if (modoAtalho) setModoAtalho(null)
        else if (outros) setOutros(null)
        else setPainelAberto(false)
        return
      }
      if (tecla === 'j') { navegar(1); return }
      if (tecla === 'k') { navegar(-1); return }
      if (tecla === 'z' && ultimaDecisaoRef.current) {
        fecharAviso()
        desfazer(ultimaDecisaoRef.current.item)
        return
      }
      if (!podeDecidir || !itemSelecionado || acaoId !== null) return
      if (tecla === 'x') { alternarSelecao(itemSelecionado); return }
      if (tecla === 'a' || tecla === 'e') {
        setOutros(null)
        setModoAtalho(tecla === 'a' ? 'aprovar' : 'excluir')
        return
      }
      if (modoAtalho && /^[1-9]$/.test(tecla)) {
        const motivo = (modoAtalho === 'aprovar' ? MOTIVOS_APROVACAO : MOTIVOS_AUDITORIA)[Number(tecla) - 1]
        if (!motivo) return
        event.preventDefault()
        if (motivo === 'Outros') {
          setOutros({ decisao: modoAtalho, texto: '' })
          setModoAtalho(null)
        } else {
          decidir(itemSelecionado, modoAtalho, motivo)
        }
      }
    }

    window.addEventListener('keydown', aoTeclar)
    return () => window.removeEventListener('keydown', aoTeclar)
  })

  const motivosFiltro = motivosDoFiltro(aba)
  const filtrosAtivos = Boolean(termoFiltro || motivoFiltro)

  return (
    <div className="curadoria-pagina cur-pagina" ref={paginaRef}>
      <Cabecalho />

      <main className="cur-conteudo">
        <header className="cur-cabecalho">
          <div>
            <span className="cur-kicker">Administração</span>
            <h1>Curadoria do catálogo</h1>
          </div>
          <div className="cur-cabecalho-acoes">
            <button type="button" className="cur-btn cur-btn--primario" onClick={() => setMostrarAdicionar(true)}>
              <IconeMais /> Adicionar jogo
            </button>
            <button
              type="button"
              className="cur-btn cur-btn--icone"
              onClick={() => setMostrarAjuda(true)}
              aria-label="Como funciona e atalhos de teclado"
              title="Como funciona e atalhos (?)"
            >
              <IconeAjuda />
            </button>
          </div>
        </header>

        <div className="cur-barra" ref={barraRef}>
          <nav className="cur-abas" aria-label="Seções da curadoria">
            {ABAS.map((item) => (
              <button
                type="button"
                key={item.id}
                className={aba === item.id ? 'ativa' : ''}
                aria-current={aba === item.id ? 'page' : undefined}
                onClick={() => trocarAba(item.id)}
              >
                {item.rotulo}
                <span>{formatarNumero(contadores[item.id])}</span>
              </button>
            ))}
          </nav>

          {ehFila && (
            <div className="cur-ferramentas">
              {podeDecidir && itensFila.length > 0 && (
                <label className="cur-selecionar-pagina" title="Selecionar todos os jogos desta página">
                  <input
                    type="checkbox"
                    checked={todosSelecionados}
                    ref={(elemento) => {
                      if (elemento) elemento.indeterminate = itensSelecionados.size > 0 && !todosSelecionados
                    }}
                    onChange={selecionarPagina}
                    disabled={processandoLote}
                    aria-label="Selecionar todos os jogos desta página"
                  />
                </label>
              )}

              {itensSelecionados.size > 0 ? (
                <div className="cur-lote">
                  <strong>{itensSelecionados.size} selecionado(s)</strong>
                  <button type="button" className="cur-btn cur-btn--aprovar cur-btn--p" onClick={() => abrirAcaoLote('aprovar')}>Aprovar</button>
                  <button type="button" className="cur-btn cur-btn--perigo cur-btn--p" onClick={() => abrirAcaoLote('excluir')}>Excluir</button>
                  <button type="button" className="cur-btn cur-btn--discreto cur-btn--p" onClick={() => setItensSelecionados(new Set())}>Limpar seleção</button>
                </div>
              ) : (
                <>
                  <input
                    type="search"
                    className="cur-filtro-texto"
                    value={filtroTexto}
                    onChange={(event) => setFiltroTexto(event.target.value)}
                    placeholder="Filtrar por nome, ID, estúdio ou gênero..."
                    aria-label="Filtrar esta lista"
                  />
                  {motivosFiltro.length > 0 && (
                    <select
                      className="cur-filtro-motivo"
                      value={motivoFiltro}
                      onChange={(event) => {
                        setMotivoFiltro(event.target.value)
                        setPagina(1)
                        setItensSelecionados(new Set())
                      }}
                      aria-label="Filtrar por motivo"
                    >
                      <option value="">Todos os motivos</option>
                      {motivosFiltro.map((motivo) => <option key={motivo} value={motivo}>{motivo}</option>)}
                    </select>
                  )}
                  <button
                    type="button"
                    className={`cur-btn cur-btn--secundario cur-btn--alternar${imagensBorradas ? ' ativo' : ''}`}
                    onClick={() => setImagensBorradas((atual) => !atual)}
                    aria-pressed={imagensBorradas}
                    title="Ocultar imagens com possível conteúdo sensível"
                  >
                    <IconeOlho riscado={imagensBorradas} />
                    <span>{imagensBorradas ? 'Imagens sensíveis ocultas' : 'Imagens visíveis'}</span>
                  </button>
                </>
              )}

              <PaginacaoCompacta total={totalFila} pagina={pagina} onMudar={mudarPagina} />
            </div>
          )}
        </div>

        {ehFila ? (
          <div className={`cur-area${painelAberto ? ' painel-aberto' : ''}`}>
            <section className={`cur-coluna-lista${carregandoFila ? ' atualizando' : ''}`} aria-busy={carregandoFila}>
              {erroFila && (
                <div className="cur-erro-fila" role="alert">
                  {erroFila}
                  <button type="button" className="cur-btn cur-btn--discreto cur-btn--p" onClick={carregarFila}>Tentar de novo</button>
                </div>
              )}

              {carregandoFila && !itensFila.length ? (
                <div className="cur-vazio">Carregando a fila...</div>
              ) : !itensFila.length && !erroFila ? (
                <div className="cur-vazio">
                  <span className="cur-vazio-icone"><IconeCheck /></span>
                  <strong>{filtrosAtivos ? 'Nenhum jogo encontrado com esses filtros' : 'Nenhum jogo nesta lista'}</strong>
                  <p>{filtrosAtivos ? 'Ajuste o filtro de texto ou o motivo.' : podeDecidir ? 'A fila está limpa por enquanto.' : 'Ainda não há decisões registradas aqui.'}</p>
                </div>
              ) : (
                <>
                  <ListaFila
                    itens={itensFila}
                    selecionadoId={itemSelecionado?.id}
                    onSelecionar={(item) => selecionar(item)}
                    borrar={(item) => deveBorrar(item, aba, imagensBorradas)}
                    permitirSelecao={podeDecidir}
                    itensSelecionados={itensSelecionados}
                    onAlternarSelecao={alternarSelecao}
                    idEmProcessamento={acaoId}
                    desabilitarSelecao={processandoLote}
                    mostrarMotivo={aba !== 'sensivel'}
                  />
                  {pagina < totalPaginasFila && (
                    <button type="button" className="cur-btn cur-btn--secundario cur-proxima-pagina" onClick={() => mudarPagina(pagina + 1)}>
                      Próxima página <IconeProximo />
                    </button>
                  )}
                </>
              )}
            </section>

            {itemSelecionado ? (
              <PainelJogo
                key={itemSelecionado.id}
                item={itemSelecionado}
                podeDecidir={podeDecidir}
                imagemBorrada={deveBorrar(itemSelecionado, aba, imagensBorradas)}
                galeria={{
                  onCarregarMidias: () => solicitarMidias(itemSelecionado),
                  midiasCarregando: midiasEmCarregamento.has(itemSelecionado.id),
                  midiasConsultadas: midiasConsultadas.has(itemSelecionado.id),
                  erroMidias: errosMidias.get(itemSelecionado.id) || '',
                }}
                posicao={{ indice: indiceAtual, total: itensFila.length }}
                onAnterior={() => navegar(-1)}
                onProximo={() => navegar(1)}
                processando={acaoId === itemSelecionado.id}
                modoAtalho={modoAtalho}
                outros={outros}
                onAbrirOutros={(decisao) => { setModoAtalho(null); setOutros({ decisao, texto: '' }) }}
                onAlterarOutros={(texto) => setOutros((atual) => (atual ? { ...atual, texto } : atual))}
                onCancelarOutros={() => setOutros(null)}
                onDecidir={(decisao, motivo, observacao) => decidir(itemSelecionado, decisao, motivo, observacao)}
                onReabrir={() => reabrir(itemSelecionado)}
                onFechar={() => setPainelAberto(false)}
              />
            ) : (
              !carregandoFila && itensFila.length === 0 ? null : (
                <aside className="cur-painel cur-painel-vazio">Selecione um jogo na lista.</aside>
              )
            )}
          </div>
        ) : aba === 'vitrine' ? (
          <SecaoVitrine getHeaders={getHeaders} notificar={notificar} atualizarContadores={atualizarContadores} />
        ) : (
          <section className="cur-secao">
            <div className="cur-secao-topo">
              <div>
                <h2>Sugestões da comunidade</h2>
                <p>Abra a página de origem e marque como feito quando a melhoria for concluída.</p>
              </div>
              <select
                className="cur-filtro-motivo"
                value={feedbackStatus}
                onChange={(event) => { setFeedbackStatus(event.target.value); setPaginaFeedback(1) }}
                aria-label="Status do feedback"
              >
                <option value="pendente">Pendentes</option>
                <option value="concluido">Concluídos</option>
                <option value="todos">Todos</option>
              </select>
            </div>

            {feedbackErro && <div className="cur-erro-fila" role="alert">{feedbackErro}</div>}
            {feedbackCarregando ? (
              <div className="cur-vazio">Carregando feedbacks...</div>
            ) : feedbackItens.length === 0 ? (
              <div className="cur-vazio">
                <span className="cur-vazio-icone"><IconeCheck /></span>
                <strong>Nenhum feedback nesta categoria</strong>
              </div>
            ) : (
              <>
                <ul className="cur-feedback-lista">
                  {feedbackItens.map((item) => {
                    const origem = String(item.pagina_origem || '').trim()
                    const urlOrigem = origem.startsWith('/') ? origem : ''
                    const nomePagina = origem.replace(/^https?:\/\/[^/]+/i, '').split(/[?#]/)[0] || '/'
                    const concluido = item.status === 'concluido'
                    return (
                      <li key={item.id} className={concluido ? 'concluido' : ''}>
                        <div className="cur-feedback-topo">
                          <span className="cur-tag">{item.tipo || 'outro'}</span>
                          <strong>{nomePagina}</strong>
                          <span className={`cur-selo ${concluido ? 'cur-selo-aprovado' : 'cur-selo-pendente'}`}>{concluido ? 'Concluído' : 'Pendente'}</span>
                        </div>
                        <p>{item.descricao}</p>
                        <div className="cur-feedback-rodape">
                          <span>
                            {formatarData(item.criada_em, true)}
                            {item.usuario_nome && ` · ${item.usuario_nome}`}
                          </span>
                          {urlOrigem && (
                            <a className="cur-btn cur-btn--discreto cur-btn--p" href={urlOrigem} target="_blank" rel="noreferrer">
                              Abrir página <IconeExterno />
                            </a>
                          )}
                          <button
                            type="button"
                            className={`cur-btn cur-btn--p ${concluido ? 'cur-btn--secundario' : 'cur-btn--aprovar'}`}
                            onClick={() => atualizarStatusFeedback(item)}
                            disabled={feedbackAcaoId === item.id}
                          >
                            {feedbackAcaoId === item.id ? 'Salvando...' : concluido ? 'Reabrir' : 'Marcar como feito'}
                          </button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
                <PaginacaoCompacta total={feedbackTotal} pagina={paginaFeedback} onMudar={setPaginaFeedback} rotulo="Paginação dos feedbacks" />
              </>
            )}
          </section>
        )}
      </main>

      {mostrarAdicionar && (
        <div
          className="curadoria-modal-overlay"
          role="presentation"
          onMouseDown={(event) => { if (event.target === event.currentTarget) setMostrarAdicionar(false) }}
        >
          <div className="curadoria-modal cur-modal-largo" role="dialog" aria-modal="true" aria-labelledby="cur-adicionar-titulo">
            <div className="curadoria-modal-cabecalho">
              <div>
                <span className="curadoria-status">CATÁLOGO</span>
                <h2 id="cur-adicionar-titulo">Adicionar jogo para revisão</h2>
              </div>
              <button type="button" className="cur-btn cur-btn--icone" onClick={() => setMostrarAdicionar(false)} aria-label="Fechar"><IconeFechar /></button>
            </div>
            <p>Pesquise qualquer jogo do catálogo (nome, ID, estúdio ou gênero) e escolha para qual fila ele deve ir.</p>
            <BuscaCatalogo
              getHeaders={getHeaders}
              autoFocus
              placeholder="Ex.: Cyberpunk, Hogwarts, nome do estúdio..."
              renderAcoes={(jogo) => {
                // Um jogo só pode estar numa fila por vez: se já está pendente, não oferece envio.
                if (jogo.auditoria_status === 'pendente') {
                  return <span className="cur-busca-aviso">Já está numa fila</span>
                }
                return ['pendentes', 'sensivel'].map((destino) => {
                  const chave = `${destino}-${jogo.id}`
                  const enviado = adicionadosIds.has(chave)
                  return (
                    <button
                      type="button"
                      key={destino}
                      className="cur-btn cur-btn--secundario cur-btn--p"
                      onClick={() => adicionar(jogo, destino)}
                      disabled={enviado || acaoId !== null}
                    >
                      {acaoId === chave ? 'Enviando...' : enviado ? 'Enviado' : destino === 'sensivel' ? 'Fila sensível' : 'Fila de análise'}
                    </button>
                  )
                })
              }}
            />
          </div>
        </div>
      )}

      {acaoLote && (
        <div
          className="curadoria-modal-overlay"
          role="presentation"
          onMouseDown={(event) => { if (event.target === event.currentTarget) fecharAcaoLote() }}
        >
          <div className="curadoria-modal" role="dialog" aria-modal="true" aria-labelledby="cur-lote-titulo">
            <div className="curadoria-modal-cabecalho">
              <div>
                <span className="curadoria-status">{acaoLote === 'aprovar' ? 'APROVAÇÃO EM LOTE' : 'EXCLUSÃO EM LOTE'}</span>
                <h2 id="cur-lote-titulo">{acaoLote === 'aprovar' ? 'Aprovar' : 'Excluir'} {itensSelecionados.size} jogo(s)</h2>
              </div>
              <button type="button" className="cur-btn cur-btn--icone" onClick={fecharAcaoLote} aria-label="Fechar" disabled={processandoLote}><IconeFechar /></button>
            </div>

            <div className="curadoria-modal-lista-selecao">
              {itensFila.filter((item) => itensSelecionados.has(item.id)).slice(0, 8).map((item) => <span key={item.id}>{item.nome}</span>)}
              {itensSelecionados.size > 8 && <small>+ {itensSelecionados.size - 8} outro(s)</small>}
            </div>

            <span className="curadoria-modal-label">Motivo para todos</span>
            <div className="cur-lote-motivos">
              {(acaoLote === 'aprovar' ? MOTIVOS_APROVACAO : MOTIVOS_AUDITORIA).map((motivo) => (
                <button
                  type="button"
                  key={motivo}
                  className={motivoLote === motivo ? 'selecionado' : ''}
                  aria-pressed={motivoLote === motivo}
                  onClick={() => setMotivoLote(motivo)}
                  disabled={processandoLote}
                >
                  {motivo}
                </button>
              ))}
            </div>

            {acaoLote === 'excluir' && MOTIVOS_COM_RELACIONADOS.includes(motivoLote) && (
              <p className="cur-lote-aviso">
                Este motivo também encaminha jogos da mesma desenvolvedora/publicadora para revisão. A operação roda um jogo por vez.
              </p>
            )}

            {motivoLote === 'Outros' && (
              <textarea
                className="curadoria-modal-textarea"
                value={observacaoLote}
                onChange={(event) => setObservacaoLote(event.target.value)}
                rows={3}
                maxLength={1000}
                placeholder="Explique o motivo..."
                disabled={processandoLote}
              />
            )}

            <div className="curadoria-modal-acoes">
              <button type="button" className="cur-btn cur-btn--secundario" onClick={fecharAcaoLote} disabled={processandoLote}>Cancelar</button>
              <button
                type="button"
                className={`cur-btn ${acaoLote === 'aprovar' ? 'cur-btn--aprovar' : 'cur-btn--perigo'}`}
                onClick={confirmarAcaoLote}
                disabled={!motivoLote || (motivoLote === 'Outros' && !observacaoLote.trim()) || processandoLote}
              >
                {processandoLote
                  ? `Processando ${progressoLote.concluidos}/${progressoLote.total}...`
                  : acaoLote === 'aprovar' ? 'Confirmar aprovações' : 'Confirmar exclusões'}
              </button>
            </div>
          </div>
        </div>
      )}

      {mostrarAjuda && <AjudaCuradoria onFechar={() => setMostrarAjuda(false)} />}
      <AvisoFlutuante aviso={aviso} onFechar={fecharAviso} />
    </div>
  )
}

// A chave por usuário recria a página do zero quando a conta muda,
// sem deixar dados administrativos de outra sessão na tela.
function Curadoria() {
  const { token, usuario, isAdmin, carregando } = useAuth()

  if (carregando) return <div className="curadoria-carregando">Carregando...</div>
  if (!isAdmin || !token) return <Navigate to="/" replace />

  return <PainelCuradoria key={usuario?.id ?? 'admin'} />
}

export default Curadoria
