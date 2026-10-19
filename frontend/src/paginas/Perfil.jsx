import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, NavLink, useSearchParams } from 'react-router-dom'
import { API_BASE, useAuth } from '../contextos/AuthContext'
import Cabecalho from '../componentes/Cabecalho'
import BotaoLoginGoogle from '../componentes/BotaoLoginGoogle'
import { useTema } from '../contextos/TemaContext'
import './Perfil.css'

function Perfil() {
  const { usuario, token, atualizarUsuario, autenticado, carregando: authCarregando } = useAuth()
  const { tema, setTema } = useTema()
  const [searchParams, setSearchParams] = useSearchParams()

  // Definir os dados derivados antes dos efeitos que os usam nas dependências.
  const nomeUsuario = usuario?.username || usuario?.nome || usuario?.name || 'Usuário'
  const emailUsuario = usuario?.email || 'Ainda não configurado'
  const emailVerificado = Boolean(usuario?.email_verificado ?? usuario?.email_verificado_em ?? usuario?.email_verified)
  const papelUsuario = usuario?.role === 'admin'
    ? 'Administrador'
    : usuario?.role
      ? 'Usuário'
      : 'Perfil não informado'
  const inicialAvatar = nomeUsuario.trim().charAt(0).toLocaleUpperCase('pt-BR') || 'U'
  const chavePreferenciaDestaques = `desctrl-perfil-jogos-destaque:${usuario?.id ?? String(usuario?.email || nomeUsuario).toLocaleLowerCase('pt-BR')}`

  const [abaAtiva, setAbaAtiva] = useState(() => {
    const abaInicial = searchParams.get('aba')
    return ['configuracoes', 'conquistas', 'notificacoes'].includes(abaInicial) ? abaInicial : 'visao-geral'
  })
  const [visitaPerfilRegistrada, setVisitaPerfilRegistrada] = useState(false)
  const [dadosConquistas, setDadosConquistas] = useState(null)
  const [carregandoConquistas, setCarregandoConquistas] = useState(false)
  const [erroConquistas, setErroConquistas] = useState('')
  const [googleVinculando, setGoogleVinculando] = useState(false)
  const [googleVinculoMensagem, setGoogleVinculoMensagem] = useState(null)
  const [modalContaAberto, setModalContaAberto] = useState('')
  const [novoEmail, setNovoEmail] = useState('')
  const [mensagemModalConta, setMensagemModalConta] = useState(null)
  const [emailAlteracaoCarregando, setEmailAlteracaoCarregando] = useState(false)
  const [dicasConquistasVisiveis, setDicasConquistasVisiveis] = useState(false)
  const [editandoUsername, setEditandoUsername] = useState(false)
  const [novoUsername, setNovoUsername] = useState('')
  const [usernameCarregando, setUsernameCarregando] = useState(false)
  const [usernameMensagem, setUsernameMensagem] = useState(null)
  const [usernameStatus, setUsernameStatus] = useState({ tipo: '', mensagem: '' })
  const [nomesRecuperaveis, setNomesRecuperaveis] = useState([])
  const [carregandoNomes, setCarregandoNomes] = useState(false)
  const [recuperandoId, setRecuperandoId] = useState(null)
  const [preferenciasNotificacao, setPreferenciasNotificacao] = useState(() => {
    try {
      const salvas = JSON.parse(localStorage.getItem('desctrl-preferencias-notificacao') || '{}')
      return {
        email: Boolean(salvas.email),
        site: Boolean(salvas.site),
      }
    } catch {
      return { email: false, site: false }
    }
  })
  const [preferenciasNotificacaoCarregadas, setPreferenciasNotificacaoCarregadas] = useState(false)
  const [erroPreferenciasNotificacao, setErroPreferenciasNotificacao] = useState('')
  const [notificacoes, setNotificacoes] = useState([])
  const [notificacoesNaoLidas, setNotificacoesNaoLidas] = useState(0)
  const [filtroNotificacoes, setFiltroNotificacoes] = useState('todas')
  const [carregandoNotificacoes, setCarregandoNotificacoes] = useState(false)
  const [erroNotificacoes, setErroNotificacoes] = useState('')
  const [versaoNotificacoes, setVersaoNotificacoes] = useState(0)

  // Dados exclusivos da Visão geral.
  const [favoritosPerfil, setFavoritosPerfil] = useState([])
  const [carregandoFavoritos, setCarregandoFavoritos] = useState(false)
  const [erroFavoritos, setErroFavoritos] = useState('')
  const [versaoFavoritosPerfil, setVersaoFavoritosPerfil] = useState(0)
  const [minhaRecomendacao, setMinhaRecomendacao] = useState(null)
  const [carregandoRecomendacao, setCarregandoRecomendacao] = useState(false)
  const [erroRecomendacao, setErroRecomendacao] = useState('')
  const [removendoRecomendacao, setRemovendoRecomendacao] = useState(false)
  const [historicosPorJogo, setHistoricosPorJogo] = useState({})
  const [historicosSolicitados, setHistoricosSolicitados] = useState({})
  const [errosHistoricoPerfil, setErrosHistoricoPerfil] = useState({})
  const [versaoHistoricos, setVersaoHistoricos] = useState(0)
  const [indiceFavoritoAutomatico, setIndiceFavoritoAutomatico] = useState(0)
  const [jogoFavoritoFixado, setJogoFavoritoFixado] = useState(null)
  const [fixacaoExpiraEm, setFixacaoExpiraEm] = useState(null)
  const [personalizacaoAberta, setPersonalizacaoAberta] = useState(false)
  const [tipoPersonalizacao, setTipoPersonalizacao] = useState('avatar')
  const [recompensaSelecionada, setRecompensaSelecionada] = useState(null)
  const [idsDestaqueSalvos, setIdsDestaqueSalvos] = useState(() => lerDestaquesSalvos(chavePreferenciaDestaques))
  const [modalDestaquesAberto, setModalDestaquesAberto] = useState(false)
  const [idsDestaqueRascunho, setIdsDestaqueRascunho] = useState([])
  const [buscaDestaques, setBuscaDestaques] = useState('')
  const [lojaGrafico, setLojaGrafico] = useState('ambas')
  const [periodoGrafico, setPeriodoGrafico] = useState('3m')
  const [tooltipGraficoHover, setTooltipGraficoHover] = useState(null)
  const [tooltipGraficoFixada, setTooltipGraficoFixada] = useState(null)

  const idsDestaqueValidos = idsDestaqueSalvos
    .filter(id => favoritosPerfil.some(jogo => String(jogo.id) === String(id)))
    .slice(0, 3)
  // Na primeira visita, sugerimos até três favoritos recentes. Depois de salvar,
  // a escolha do usuário é respeitada, inclusive quando ele seleciona só um ou dois.
  const idsDestaqueAtivos = idsDestaqueValidos.length
    ? idsDestaqueValidos
    : favoritosPerfil.slice(0, 3).map(jogo => jogo.id)
  const favoritosDestaque = idsDestaqueAtivos
    .map(id => favoritosPerfil.find(jogo => String(jogo.id) === String(id)))
    .filter(Boolean)
  const jogoSelecionadoGrafico = fixacaoExpiraEm && fixacaoExpiraEm > Date.now()
    ? favoritosDestaque.find(jogo => jogo.id === jogoFavoritoFixado) || favoritosDestaque[0] || null
    : favoritosDestaque.length
      ? favoritosDestaque[((indiceFavoritoAutomatico % favoritosDestaque.length) + favoritosDestaque.length) % favoritosDestaque.length]
      : null
  const jogoSelecionadoGraficoId = jogoSelecionadoGrafico?.id
  const historicoSelecionado = useMemo(
    () => jogoSelecionadoGraficoId ? historicosPorJogo[jogoSelecionadoGraficoId] || [] : [],
    [jogoSelecionadoGraficoId, historicosPorJogo]
  )
  // O período é calculado sobre as duas lojas. Assim, ao filtrar uma loja,
  // ainda conhecemos a data final comum e podemos manter o último preço
  // conhecido até a observação mais recente da outra loja.
  const historicoPeriodoCompleto = useMemo(
    () => filtrarHistoricoPorPeriodoPerfil(historicoSelecionado, periodoGrafico),
    [historicoSelecionado, periodoGrafico]
  )
  // O histórico filtrado por loja, mas sem restringir o período, continua
  // alimentando o menor preço histórico e o preço atual dos cartões.
  const historicoLojaGrafico = useMemo(
    () => filtrarHistoricoPorLojaPerfil(historicoSelecionado, lojaGrafico),
    [historicoSelecionado, lojaGrafico]
  )
  const historicoLojaPeriodoGrafico = useMemo(
    () => filtrarHistoricoPorLojaPerfil(historicoPeriodoCompleto, lojaGrafico),
    [historicoPeriodoCompleto, lojaGrafico]
  )
  const historicoParaGrafico = historicoLojaPeriodoGrafico
  const graficoPerfil = useMemo(
    // Usa o histórico completo para carregar o preço conhecido no início
    // da janela selecionada e prolongá-lo até hoje.
    () => prepararGraficoPerfil(historicoSelecionado, periodoGrafico, lojaGrafico),
    [historicoSelecionado, periodoGrafico, lojaGrafico]
  )
  const precoAtualGrafico = obterPrecoAtualFiltradoPerfil(historicoSelecionado, jogoSelecionadoGrafico, lojaGrafico)
  const menorHistoricoGrafico = obterMenorHistoricoPerfil(historicoLojaGrafico)
  const descontoAtualGrafico = obterDescontoAtualFiltradoPerfil(jogoSelecionadoGrafico, lojaGrafico)
  const conquistasDesbloqueadas = (dadosConquistas?.conquistas || []).filter(item => item.desbloqueada)
  const recompensaVisualSelecionada = conquistasDesbloqueadas.find(item => item.codigo === recompensaSelecionada && item.tipo_recompensa === tipoPersonalizacao)
  const conquistasRecentes = [...conquistasDesbloqueadas]
    .sort((a, b) => new Date(b.desbloqueada_em || 0).getTime() - new Date(a.desbloqueada_em || 0).getTime())
    .slice(0, 3)
  const nivelPerfil = dadosConquistas?.nivel || { numero: 1, titulo: 'Recruta', xp_minimo: 0 }
  const proximoNivelPerfil = dadosConquistas?.proximo_nivel || null
  const xpPerfil = Number(dadosConquistas?.xp_total || 0)
  const progressoNivelPerfil = proximoNivelPerfil
    ? Math.max(0, Math.min(100, ((xpPerfil - (nivelPerfil.xp_minimo || 0)) / Math.max(1, proximoNivelPerfil.xp_necessario - (nivelPerfil.xp_minimo || 0))) * 100))
    : 100
  const favoritosNoMenorHistorico = favoritosPerfil.filter(jogo => Boolean(
    jogo.no_menor_preco_historico_steam || jogo.no_menor_preco_historico_epic ||
    jogo.menor_preco_historico_steam === true || jogo.menor_preco_historico_epic === true
  )).length

  useEffect(() => {
    const abaSolicitada = searchParams.get('aba')
    setAbaAtiva(['configuracoes', 'conquistas', 'notificacoes'].includes(abaSolicitada) ? abaSolicitada : 'visao-geral')
  }, [searchParams])

  useEffect(() => {
    if (!token || authCarregando || !autenticado) {
      setVisitaPerfilRegistrada(false)
      return undefined
    }

    let cancelado = false
    const registrarVisita = async () => {
      try {
        const resposta = await fetch(`${API_BASE}/api/conquistas/evento`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify({ evento: 'visita_perfil' }),
        })
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível registrar a visita ao perfil.')
        if (!cancelado) setVisitaPerfilRegistrada(true)
      } catch (erro) {
        console.warn('Não foi possível registrar a visita ao perfil para conquistas.', erro)
        if (!cancelado) setErroConquistas(erro.message || 'Falha ao registrar a visita ao perfil.')
      }
    }

    registrarVisita()
    return () => { cancelado = true }
  }, [token, authCarregando, autenticado])

  useEffect(() => {
    if (!['visao-geral', 'conquistas'].includes(abaAtiva) || !token || !visitaPerfilRegistrada) return undefined
    let cancelado = false

    const carregarConquistas = async () => {
      setCarregandoConquistas(true)
      setErroConquistas('')
      try {
        const resposta = await fetch(`${API_BASE}/api/conquistas`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar suas conquistas.')
        if (!cancelado) setDadosConquistas(dados)
      } catch (erro) {
        if (!cancelado) setErroConquistas(erro.message || 'Falha ao carregar as conquistas.')
      } finally {
        if (!cancelado) setCarregandoConquistas(false)
      }
    }

    carregarConquistas()
    return () => { cancelado = true }
  }, [abaAtiva, token, visitaPerfilRegistrada])

  useEffect(() => {
    if (abaAtiva !== 'visao-geral' || !token || !visitaPerfilRegistrada) return undefined
    let cancelado = false
    setCarregandoFavoritos(true)
    setErroFavoritos('')

    const carregarFavoritosPerfil = async () => {
      try {
        const resposta = await fetch(`${API_BASE}/api/favoritos`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar seus favoritos.')
        if (!cancelado) setFavoritosPerfil(Array.isArray(dados.favoritos) ? dados.favoritos : [])
      } catch (erro) {
        if (!cancelado) setErroFavoritos(erro.message || 'Falha ao carregar favoritos.')
      } finally {
        if (!cancelado) setCarregandoFavoritos(false)
      }
    }

    carregarFavoritosPerfil()
    return () => { cancelado = true }
  }, [abaAtiva, token, visitaPerfilRegistrada, versaoFavoritosPerfil])

  useEffect(() => {
    if (abaAtiva !== 'visao-geral' || !jogoSelecionadoGrafico?.id) return undefined
    const jogoId = jogoSelecionadoGrafico.id
    if (historicosSolicitados[jogoId] || Object.prototype.hasOwnProperty.call(historicosPorJogo, jogoId)) return undefined
    setHistoricosSolicitados(atuais => ({ ...atuais, [jogoId]: true }))

    const carregarHistorico = async () => {
      try {
        const resposta = await fetch(`${API_BASE}/api/jogos/${jogoId}/historico`)
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar o histórico de preços.')
        setHistoricosPorJogo(atuais => ({ ...atuais, [jogoId]: Array.isArray(dados) ? dados : [] }))
        setErrosHistoricoPerfil(atuais => ({ ...atuais, [jogoId]: '' }))
      } catch (erro) {
        setErrosHistoricoPerfil(atuais => ({ ...atuais, [jogoId]: erro.message || 'Falha ao carregar o histórico.' }))
      }
    }

    carregarHistorico()
    // Não cancelar ao trocar de jogo: armazenar a resposta em cache deixa a rotação fluida.
    return undefined
  }, [abaAtiva, jogoSelecionadoGrafico?.id, versaoHistoricos, historicosPorJogo, historicosSolicitados])

  useEffect(() => {
    if (abaAtiva !== 'visao-geral' || fixacaoExpiraEm || favoritosDestaque.length < 2) return undefined
    const intervalo = setInterval(() => {
      setIndiceFavoritoAutomatico(indice => (indice + 1) % favoritosDestaque.length)
    }, 10000)
    return () => clearInterval(intervalo)
  }, [abaAtiva, fixacaoExpiraEm, favoritosDestaque.length])

  useEffect(() => {
    if (!fixacaoExpiraEm) return undefined
    const tempoRestante = Math.max(0, fixacaoExpiraEm - Date.now())
    const temporizador = setTimeout(() => {
      setFixacaoExpiraEm(null)
      setJogoFavoritoFixado(null)
    }, tempoRestante)
    return () => clearTimeout(temporizador)
  }, [fixacaoExpiraEm])

  // Trocar o jogo, loja ou período invalida tooltips ancoradas no gráfico anterior.
  useEffect(() => {
    setTooltipGraficoHover(null)
    setTooltipGraficoFixada(null)
  }, [jogoSelecionadoGrafico?.id, lojaGrafico, periodoGrafico])

  // A tooltip aberta ao clicar em um marcador fica visível por cinco segundos.
  useEffect(() => {
    if (!tooltipGraficoFixada) return undefined
    const temporizador = setTimeout(() => setTooltipGraficoFixada(null), 5000)
    return () => clearTimeout(temporizador)
  }, [tooltipGraficoFixada])

  useEffect(() => {
    setIdsDestaqueSalvos(lerDestaquesSalvos(chavePreferenciaDestaques))
  }, [chavePreferenciaDestaques])

  useEffect(() => {
    if (!token) return undefined
    let cancelado = false
    const carregarPreferenciasNotificacao = async () => {
      setErroPreferenciasNotificacao('')
      try {
        const resposta = await fetch(`${API_BASE}/api/alertas-preco/preferencias`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar as preferências de notificação.')

        if (!dados.configuradas) {
          // Migra uma única vez as preferências antigas deste navegador para a conta.
          let antigas = { email: false, site: false }
          try {
            const salvas = JSON.parse(localStorage.getItem('desctrl-preferencias-notificacao') || '{}')
            antigas = { email: Boolean(salvas.email), site: Boolean(salvas.site) }
          } catch { /* Mantém os valores padrão. */ }
          const migracao = await fetch(`${API_BASE}/api/alertas-preco/preferencias`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
            body: JSON.stringify({ email: antigas.email && emailVerificado, site: antigas.site }),
          })
          const resultadoMigracao = await migracao.json().catch(() => ({}))
          if (!migracao.ok) throw new Error(resultadoMigracao.detail || 'Não foi possível migrar as preferências antigas.')
          if (!cancelado) setPreferenciasNotificacao({ email: Boolean(resultadoMigracao.email), site: Boolean(resultadoMigracao.site) })
        } else if (!cancelado) {
          setPreferenciasNotificacao({ email: Boolean(dados.email), site: Boolean(dados.site) })
        }
      } catch (erro) {
        if (!cancelado) setErroPreferenciasNotificacao(erro.message || 'Falha ao carregar as preferências.')
      } finally {
        if (!cancelado) setPreferenciasNotificacaoCarregadas(true)
      }
    }
    carregarPreferenciasNotificacao()
    return () => { cancelado = true }
  }, [token, emailVerificado])

  const alterarNotificacao = async (chave, valor) => {
    if (chave === 'email' && valor && !emailVerificado) return
    const anteriores = preferenciasNotificacao
    const proximas = { ...anteriores, [chave]: valor }
    setPreferenciasNotificacao(proximas)
    setErroPreferenciasNotificacao('')
    try {
      const resposta = await fetch(`${API_BASE}/api/alertas-preco/preferencias`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify(proximas),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível salvar as preferências.')
      setPreferenciasNotificacao({ email: Boolean(dados.email), site: Boolean(dados.site) })
    } catch (erro) {
      setPreferenciasNotificacao(anteriores)
      setErroPreferenciasNotificacao(erro.message || 'Falha ao salvar as preferências.')
    }
  }

  const solicitarAlteracaoEmail = async (form) => {
    if (!form || emailAlteracaoCarregando) return
    if (!token) {
      setMensagemModalConta({ tipo: 'erro', texto: 'Sua sessão expirou. Entre novamente e tente outra vez.' })
      return
    }

    const dados = new FormData(form)
    const email = String(dados.get('novo_email') || '').trim().toLowerCase()
    const senhaAtual = String(dados.get('senha_atual') || '')
    if (!email || !senhaAtual) {
      setMensagemModalConta({ tipo: 'erro', texto: 'Preencha o novo e-mail e sua senha atual.' })
      return
    }

    setEmailAlteracaoCarregando(true)
    setMensagemModalConta(null)
    try {
      const resposta = await fetch(`${API_BASE}/api/auth/email/solicitar-alteracao`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ novo_email: email, senha_atual: senhaAtual }),
      })
      const resultado = await resposta.json().catch(() => ({}))
      if (!resposta.ok) {
        throw new Error(resultado.detail || `Não foi possível solicitar a alteração (HTTP ${resposta.status}).`)
      }
      setMensagemModalConta({
        tipo: 'sucesso',
        texto: resultado.mensagem || 'Enviamos o link de confirmação para o novo endereço.',
      })
      form.reset()
      setNovoEmail('')
    } catch (erro) {
      setMensagemModalConta({
        tipo: 'erro',
        texto: erro.message || 'Não foi possível conectar ao servidor. Verifique se o backend está ativo.',
      })
    } finally {
      setEmailAlteracaoCarregando(false)
    }
  }

  const abrirModalConta = (tipo) => {
    setMensagemModalConta(null)
    setNovoEmail('')
    setModalContaAberto(tipo)
  }

  const carregarNomesRecuperaveis = useCallback(async () => {
    if (!token) return
    setCarregandoNomes(true)
    try {
      const resposta = await fetch(`${API_BASE}/api/auth/username-recuperaveis`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const dados = await resposta.json().catch(() => [])
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar os nomes recuperáveis.')
      setNomesRecuperaveis(Array.isArray(dados) ? dados : [])
    } catch (erro) {
      setUsernameMensagem({ tipo: 'erro', texto: erro.message || 'Falha ao carregar os nomes recuperáveis.' })
    } finally {
      setCarregandoNomes(false)
    }
  }, [token])

  useEffect(() => {
    if (abaAtiva !== 'notificacoes' || !token) return undefined
    let cancelado = false
    const carregarNotificacoes = async () => {
      setCarregandoNotificacoes(true); setErroNotificacoes('')
      try {
        const resposta = await fetch(`${API_BASE}/api/notificacoes?tipo=${encodeURIComponent(filtroNotificacoes)}&limite=200`, { headers: { Authorization: `Bearer ${token}` } })
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar as notificações.')
        if (!cancelado) { setNotificacoes(Array.isArray(dados.notificacoes) ? dados.notificacoes : []); setNotificacoesNaoLidas(Number(dados.nao_lidas || 0)) }
      } catch (erro) { if (!cancelado) setErroNotificacoes(erro.message || 'Falha ao carregar notificações.') }
      finally { if (!cancelado) setCarregandoNotificacoes(false) }
    }
    carregarNotificacoes()
    return () => { cancelado = true }
  }, [abaAtiva, token, filtroNotificacoes, versaoNotificacoes])

  const marcarNotificacaoLida = async (id) => {
    try {
      const resposta = await fetch(`${API_BASE}/api/notificacoes/${id}/ler`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}` } })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível marcar como lida.')
      setNotificacoes(atuais => atuais.map(item => item.id === id ? { ...item, lida: true } : item))
      setNotificacoesNaoLidas(atual => Math.max(0, atual - 1))
    } catch (erro) { setErroNotificacoes(erro.message || 'Falha ao atualizar a notificação.') }
  }

  const marcarTodasNotificacoesLidas = async () => {
    try {
      const resposta = await fetch(`${API_BASE}/api/notificacoes/ler-todas`, { method: 'PATCH', headers: { Authorization: `Bearer ${token}` } })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível marcar as notificações como lidas.')
      setNotificacoes(atuais => atuais.map(item => ({ ...item, lida: true }))); setNotificacoesNaoLidas(0)
    } catch (erro) { setErroNotificacoes(erro.message || 'Falha ao atualizar as notificações.') }
  }

  useEffect(() => {
    if (abaAtiva === 'configuracoes' && token) carregarNomesRecuperaveis()
  }, [abaAtiva, token, carregarNomesRecuperaveis])

  const fixarGraficoNoJogo = (jogoId) => {
    setIndiceFavoritoAutomatico(Math.max(0, favoritosDestaque.findIndex(jogo => String(jogo.id) === String(jogoId))))
    // Com apenas um destaque, ele já permanece selecionado naturalmente.
    if (favoritosDestaque.length < 2) {
      setJogoFavoritoFixado(null)
      setFixacaoExpiraEm(null)
      return
    }
    setJogoFavoritoFixado(jogoId)
    setFixacaoExpiraEm(Date.now() + 120000)
  }

  const retomarRotacaoGrafico = () => {
    setJogoFavoritoFixado(null)
    setFixacaoExpiraEm(null)
  }

  const atualizarTooltipGrafico = (evento) => {
    if (tooltipGraficoFixada || !graficoPerfil?.inicioMs || !graficoPerfil?.fimMs) return
    const retangulo = evento.currentTarget.getBoundingClientRect()
    if (!retangulo.width) return
    const xSvgBruto = ((evento.clientX - retangulo.left) / retangulo.width) * 1000
    const x = Math.max(graficoPerfil.xInicial, Math.min(graficoPerfil.xFinal, xSvgBruto))
    const fracao = (x - graficoPerfil.xInicial) / Math.max(1, graficoPerfil.xFinal - graficoPerfil.xInicial)
    const instante = graficoPerfil.inicioMs + fracao * (graficoPerfil.fimMs - graficoPerfil.inicioMs)
    const seriesConfiguradas = [
      { plataforma: 'steam', pontos: graficoPerfil.steamSerie },
      { plataforma: 'epic', pontos: graficoPerfil.epicSerie },
    ].filter(serie => lojaGrafico === 'ambas' || lojaGrafico === serie.plataforma)
    const series = seriesConfiguradas.map(serie => {
      let pontoAtual = null
      for (const ponto of serie.pontos) {
        if (ponto.instante <= instante) pontoAtual = ponto
        else break
      }
      return {
        plataforma: serie.plataforma,
        precoNumerico: pontoAtual?.precoNumerico ?? null,
        desconto: pontoAtual?.desconto ?? null,
        y: pontoAtual?.y ?? null,
      }
    })
    const ys = series.map(serie => serie.y).filter(valor => Number.isFinite(valor))
    const y = ys.length ? ys.reduce((soma, valor) => soma + valor, 0) / ys.length : 90
    setTooltipGraficoHover({ tipo: 'hover', x, y, instante, data: new Date(instante), series })
  }

  const abrirTooltipGraficoFixada = (evento, ponto, plataforma) => {
    evento.preventDefault()
    evento.stopPropagation()
    setTooltipGraficoHover(null)
    setTooltipGraficoFixada({
      tipo: 'fixa',
      x: ponto.x,
      y: ponto.y,
      instante: ponto.instante,
      data: new Date(ponto.instante),
      series: [{ plataforma, precoNumerico: ponto.precoNumerico, desconto: Number(ponto.desconto || 0), y: ponto.y }],
    })
  }

  const abrirModalDestaques = () => {
    setIdsDestaqueRascunho(favoritosDestaque.map(jogo => jogo.id))
    setBuscaDestaques('')
    setModalDestaquesAberto(true)
  }

  const alternarDestaqueRascunho = (jogoId) => {
    setIdsDestaqueRascunho(atuais => {
      const existe = atuais.some(id => String(id) === String(jogoId))
      if (existe) return atuais.filter(id => String(id) !== String(jogoId))
      if (atuais.length >= 3) return atuais
      return [...atuais, jogoId]
    })
  }

  const salvarDestaques = () => {
    const ids = idsDestaqueRascunho
      .filter(id => favoritosPerfil.some(jogo => String(jogo.id) === String(id)))
      .slice(0, 3)
    // É permitido destacar um, dois ou três jogos, mas não salvar uma coleção vazia.
    if (ids.length < 1) return
    setIdsDestaqueSalvos(ids)
    try { localStorage.setItem(chavePreferenciaDestaques, JSON.stringify(ids)) } catch (erro) {
      console.warn('Não foi possível salvar a seleção dos favoritos em destaque neste navegador.', erro)
    }
    setIndiceFavoritoAutomatico(0)
    if (!ids.some(id => String(id) === String(jogoFavoritoFixado))) retomarRotacaoGrafico()
    setModalDestaquesAberto(false)
  }

  const tentarNovamenteHistoricoPerfil = (jogoId) => {
    setHistoricosPorJogo(atuais => {
      const novos = { ...atuais }
      delete novos[jogoId]
      return novos
    })
    setHistoricosSolicitados(atuais => {
      const novos = { ...atuais }
      delete novos[jogoId]
      return novos
    })
    setErrosHistoricoPerfil(atuais => ({ ...atuais, [jogoId]: '' }))
    setVersaoHistoricos(versao => versao + 1)
  }

  const validarUsernameLocal = (valor) => {
    if (!valor) return { tipo: '', mensagem: '' }
    if (valor.length < 3) return { tipo: 'erro', mensagem: 'Quase lá! Vamos dar mais um pouquinho de tamanho a esse nome?' }
    if (valor.length > 100) return { tipo: 'erro', mensagem: 'Gostamos de nomes criativos, mas esse ficou comprido demais!' }
    if (!/^[A-Za-z0-9_.-]+$/.test(valor)) return { tipo: 'erro', mensagem: 'Opa! Esse símbolo não é permitido por aqui.' }
    return { tipo: 'verificando', mensagem: 'Checando se esse nome já tem dono...' }
  }

  useEffect(() => {
    if (!editandoUsername) return undefined
    const valor = novoUsername.trim()
    if (valor.toLowerCase() === String(nomeUsuario).toLowerCase()) {
      setUsernameStatus({ tipo: 'atual', mensagem: 'Esse já é seu nome de usuário.' })
      return undefined
    }
    const local = validarUsernameLocal(valor)
    if (!valor || local.tipo === 'erro') {
      setUsernameStatus(local)
      return undefined
    }
    setUsernameStatus(local)
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const resposta = await fetch(`${API_BASE}/api/auth/username-disponivel?username=${encodeURIComponent(valor)}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        })
        if (!resposta.ok) throw new Error('Falha na consulta')
        const dados = await resposta.json()
        setUsernameStatus({
          tipo: dados.disponivel ? 'disponivel' : 'erro',
          mensagem: dados.disponivel ? 'Tudo certo! Esse nome pode ser seu.' : 'Boa escolha, mas esse nome já está em uso. Que tal variar um pouquinho?',
        })
      } catch (erro) {
        if (erro.name !== 'AbortError') setUsernameStatus({ tipo: 'aviso', mensagem: 'Estamos com dificuldade para consultar os nomes. Tente de novo daqui a pouco.' })
      }
    }, 450)
    return () => { clearTimeout(timer); controller.abort() }
  }, [novoUsername, editandoUsername, token, nomeUsuario])

  const salvarUsername = async (evento) => {
    evento.preventDefault()
    if (!token) return
    const nome = novoUsername.trim()
    const local = validarUsernameLocal(nome)
    if (!nome) {
      setUsernameStatus({ tipo: 'erro', mensagem: 'Ei, faltou escolher seu nome de usuário!' })
      return
    }
    if (local.tipo === 'erro') {
      setUsernameStatus(local)
      return
    }
    if (nome.toLowerCase() === String(nomeUsuario).toLowerCase()) {
      setUsernameStatus({ tipo: 'atual', mensagem: 'Esse já é seu nome de usuário.' })
      return
    }
    if (usernameStatus.tipo !== 'disponivel') {
      setUsernameMensagem({ tipo: 'erro', texto: usernameStatus.tipo === 'erro' ? usernameStatus.mensagem : 'Só um instante: precisamos confirmar se esse nome está livre.' })
      return
    }
    setUsernameCarregando(true)
    setUsernameMensagem(null)
    try {
      const resposta = await fetch(`${API_BASE}/api/auth/username`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ username: novoUsername }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível alterar o nome de usuário.')
      atualizarUsuario({ username: dados.username })
      setEditandoUsername(false)
      setNovoUsername('')
      setUsernameStatus({ tipo: '', mensagem: '' })
      setUsernameMensagem({ tipo: 'sucesso', texto: `${dados.mensagem} Prazo: ${new Date(dados.reservado_ate).toLocaleString('pt-BR')}.` })
      await carregarNomesRecuperaveis()
    } catch (erro) {
      setUsernameMensagem({ tipo: 'erro', texto: erro.message || 'Falha ao alterar o nome de usuário.' })
    } finally {
      setUsernameCarregando(false)
    }
  }

  const recuperarUsername = async (historicoId) => {
    if (!token) return
    setRecuperandoId(historicoId)
    setUsernameMensagem(null)
    try {
      const resposta = await fetch(`${API_BASE}/api/auth/username/recuperar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ historico_id: historicoId }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível recuperar esse nome.')
      atualizarUsuario({ username: dados.username })
      setUsernameMensagem({ tipo: 'sucesso', texto: dados.mensagem })
      await carregarNomesRecuperaveis()
    } catch (erro) {
      setUsernameMensagem({ tipo: 'erro', texto: erro.message || 'Falha ao recuperar o nome.' })
      await carregarNomesRecuperaveis()
    } finally {
      setRecuperandoId(null)
    }
  }

  const vincularContaGoogle = async (credential) => {
    if (!token || !credential) {
      setGoogleVinculoMensagem({ tipo: 'erro', texto: 'Sua sessão expirou. Entre novamente e tente vincular o Google.' })
      return
    }

    setGoogleVinculando(true)
    setGoogleVinculoMensagem(null)
    try {
      const resposta = await fetch(`${API_BASE}/api/auth/google/vincular`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ credential }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível vincular sua conta Google.')
      }
      // Recarrega o estado canônico da conta após a vinculação.
      const respostaUsuario = await fetch(`${API_BASE}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      const usuarioAtualizado = await respostaUsuario.json().catch(() => ({}))
      if (!respostaUsuario.ok) {
        throw new Error('Google foi vinculado, mas não conseguimos atualizar os dados da conta. Recarregue a página.')
      }
      atualizarUsuario(usuarioAtualizado)
      setGoogleVinculoMensagem({
        tipo: 'sucesso',
        texto: dados.mensagem || 'Conta Google vinculada com sucesso.',
      })
    } catch (erro) {
      setGoogleVinculoMensagem({
        tipo: 'erro',
        texto: erro.message || 'Não foi possível vincular sua conta Google.',
      })
    } finally {
      setGoogleVinculando(false)
    }
  }

  useEffect(() => {
    if (abaAtiva !== 'visao-geral' || !token || !visitaPerfilRegistrada) return undefined
    let cancelado = false
    const carregarMinhaRecomendacao = async () => {
      setCarregandoRecomendacao(true)
      setErroRecomendacao('')
      try {
        const resposta = await fetch(`${API_BASE}/api/jogos/vitrine/minha-recomendacao`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar sua recomendação.')
        if (!cancelado) setMinhaRecomendacao(dados.recomendacao || null)
      } catch (erro) {
        if (!cancelado) setErroRecomendacao(erro.message || 'Falha ao carregar recomendação.')
      } finally {
        if (!cancelado) setCarregandoRecomendacao(false)
      }
    }
    carregarMinhaRecomendacao()
    return () => { cancelado = true }
  }, [abaAtiva, token, visitaPerfilRegistrada])

  const removerMinhaRecomendacao = async () => {
    if (!token || removendoRecomendacao || !window.confirm('Deseja remover sua recomendação ativa?')) return
    setRemovendoRecomendacao(true)
    setErroRecomendacao('')
    try {
      const resposta = await fetch(`${API_BASE}/api/jogos/vitrine/recomendacao`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível remover a recomendação.')
      setMinhaRecomendacao(null)
    } catch (erro) {
      setErroRecomendacao(erro.message || 'Falha ao remover recomendação.')
    } finally {
      setRemovendoRecomendacao(false)
    }
  }

  const selecionarAba = (aba) => {
    setAbaAtiva(aba)
    setSearchParams((atuais) => {
      const proximos = new URLSearchParams(atuais)
      if (aba === 'visao-geral') proximos.delete('aba')
      else proximos.set('aba', aba)
      return proximos
    }, { replace: true })
  }

  if (authCarregando) {
    return <main className="pagina-perfil"><div className="perfil-container">Carregando perfil...</div></main>
  }

  if (!autenticado) {
    return <Navigate to="/login" replace />
  }

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho tema={tema} setTema={setTema} />
      <main className="pagina-perfil">
        <div className="perfil-container">
          <div className="perfil-cabecalho-pagina">
            <div>
              <span className="eyebrow">MINHA CONTA</span>
              <h1>{abaAtiva === 'configuracoes' ? 'Configurações' : abaAtiva === 'conquistas' ? 'Conquistas' : abaAtiva === 'notificacoes' ? 'Notificações' : 'Meu perfil'}</h1>
              <p>{abaAtiva === 'configuracoes' ? 'Personalize a aparência e escolha quais avisos gostaria de acompanhar.' : abaAtiva === 'conquistas' ? 'Complete objetivos, ganhe XP e personalize sua identidade no DESCTRL.' : abaAtiva === 'notificacoes' ? 'Acompanhe avisos de preços e conquistas, mesmo depois que os alertas temporários desaparecerem.' : 'Sua coleção, suas conquistas e a evolução dos preços em um só lugar.'}</p>
            </div>
            <NavLink className="perfil-voltar" to="/">← Voltar</NavLink>
          </div>

          <nav className="perfil-abas" aria-label="Seções do perfil">
            <button type="button" className={abaAtiva === 'visao-geral' ? 'ativa' : ''} onClick={() => selecionarAba('visao-geral')}><span aria-hidden="true">◉</span> Visão geral</button>
            <button type="button" className={abaAtiva === 'conquistas' ? 'ativa' : ''} onClick={() => selecionarAba('conquistas')}><span aria-hidden="true">✦</span> Conquistas</button>
            <button type="button" className={abaAtiva === 'notificacoes' ? 'ativa' : ''} onClick={() => selecionarAba('notificacoes')}><span aria-hidden="true">♧</span> Notificações{notificacoesNaoLidas > 0 && <span className="perfil-notificacoes-contador">{notificacoesNaoLidas > 99 ? '99+' : notificacoesNaoLidas}</span>}</button>
            <button type="button" className={abaAtiva === 'configuracoes' ? 'ativa' : ''} onClick={() => selecionarAba('configuracoes')}><span aria-hidden="true">⚙</span> Configurações</button>
          </nav>


          {abaAtiva === 'conquistas' ? (
            <ConquistasPanel dados={dadosConquistas} carregando={carregandoConquistas} erro={erroConquistas} dicasVisiveis={dicasConquistasVisiveis} alternarDicas={() => setDicasConquistasVisiveis(valor => !valor)} />
          ) : abaAtiva === 'notificacoes' ? (
            <section className="perfil-painel perfil-notificacoes-painel">
              <header className="perfil-painel-cabecalho">
                <div><span className="perfil-painel-eyebrow">CENTRAL DE AVISOS</span><h2>Seu histórico</h2><p>{notificacoesNaoLidas ? `${notificacoesNaoLidas} notificação(ões) não lida(s)` : 'Você está em dia com suas notificações.'}</p></div>
                <button type="button" className="perfil-link-discreto perfil-link-botao" onClick={marcarTodasNotificacoesLidas} disabled={!notificacoesNaoLidas || carregandoNotificacoes}>Marcar todas como lidas</button>
              </header>
              <div className="perfil-notificacoes-filtros" role="group" aria-label="Filtrar notificações">
                {[['todas', 'Todas'], ['preco', 'Preços'], ['conquista', 'Conquistas'], ['recomendacao', 'Recomendações']].map(([valor, rotulo]) => <button type="button" key={valor} className={filtroNotificacoes === valor ? 'ativo' : ''} onClick={() => setFiltroNotificacoes(valor)} aria-pressed={filtroNotificacoes === valor}>{rotulo}</button>)}
              </div>
              {erroNotificacoes && <p className="perfil-notificacoes-erro" role="alert">{erroNotificacoes}<button type="button" onClick={() => setVersaoNotificacoes(valor => valor + 1)}>Tentar novamente</button></p>}
              {carregandoNotificacoes ? <div className="perfil-notificacoes-vazio">Carregando seu histórico…</div> : notificacoes.length ? (
                <div className="perfil-notificacoes-lista">
                  {notificacoes.map(item => <article className={`perfil-notificacao-item ${item.lida ? 'lida' : 'nao-lida'}`} key={item.id}>
                    <span className={`perfil-notificacao-item-icone ${item.tipo === 'conquista' ? 'conquista' : 'preco'}`} aria-hidden="true">{item.tipo === 'conquista' ? '✦' : item.tipo === 'recomendacao' ? '♡' : '⌁'}</span>
                    <div className="perfil-notificacao-item-conteudo"><div className="perfil-notificacao-item-topo"><span>{item.tipo === 'conquista' ? 'CONQUISTA' : item.tipo === 'recomendacao' ? 'RECOMENDAÇÃO' : 'ALERTA DE PREÇO'}</span>{!item.lida && <b>Nova</b>}</div><strong>{item.titulo}</strong><p>{item.mensagem}</p><small>{item.criada_em ? new Date(item.criada_em).toLocaleString('pt-BR') : 'Data indisponível'}</small><div className="perfil-notificacao-item-acoes">{item.link && <Link to={item.link} onClick={() => !item.lida && marcarNotificacaoLida(item.id)}>{item.tipo === 'conquista' ? 'Ver conquistas' : item.tipo === 'recomendacao' ? 'Ver recomendação' : 'Ver jogo'} <span aria-hidden="true">↗</span></Link>}{!item.lida && <button type="button" onClick={() => marcarNotificacaoLida(item.id)}>Marcar como lida</button>}</div></div>
                  </article>)}
                </div>
              ) : <div className="perfil-notificacoes-vazio"><span aria-hidden="true">♧</span><strong>Nenhuma notificação por aqui</strong><p>Quando um jogo atingir sua condição de preço ou você desbloquear uma conquista, os avisos aparecerão neste histórico se as notificações no site estiverem ativadas.</p><button type="button" onClick={() => selecionarAba('configuracoes')}>Ver preferências</button></div>}
            </section>
          ) : abaAtiva === 'configuracoes' ? (
            <section className="perfil-configuracoes-pagina">
              <div className="perfil-configuracoes-intro">
                <span className="perfil-configuracoes-intro-icone" aria-hidden="true">⚙</span>
                <div><h2>Preferências da conta</h2><p>As opções abaixo já podem ser ajustadas. Algumas funcionalidades, como o envio de alertas por e-mail, serão conectadas ao backend em uma próxima etapa.</p></div>
              </div>

              <section className="perfil-configuracao-secao">
                <div className="perfil-configuracao-secao-titulo"><span aria-hidden="true">◐</span><div><h3>Aparência</h3><p>Escolha como você prefere visualizar o site. Essa será a aparência padrão ao entrar, mas você pode mudar de tema sempre que quiser.</p></div></div>
                <div className="perfil-tema-opcoes" role="group" aria-label="Escolher tema">
                  <button type="button" className={`perfil-tema-opcao ${tema === 'claro' ? 'selecionada' : ''}`} onClick={() => setTema('claro')} aria-pressed={tema === 'claro'}>
                    <span className="perfil-tema-amostra tema-amostra-claro" aria-hidden="true"><i /><i /><i /></span><span><strong>Claro</strong><small>Fundo claro e conteúdo escuro</small></span><span className="perfil-radio-indicador" aria-hidden="true" />
                  </button>
                  <button type="button" className={`perfil-tema-opcao ${tema === 'escuro' ? 'selecionada' : ''}`} onClick={() => setTema('escuro')} aria-pressed={tema === 'escuro'}>
                    <span className="perfil-tema-amostra tema-amostra-escuro" aria-hidden="true"><i /><i /><i /></span><span><strong>Escuro</strong><small>Fundo escuro e destaque roxo</small></span><span className="perfil-radio-indicador" aria-hidden="true" />
                  </button>
                </div>
              </section>

              <section className="perfil-configuracao-secao">
                <div className="perfil-configuracao-secao-titulo"><span aria-hidden="true">♧</span><div><h3>Notificações e alertas</h3><p>Escolha por quais canais você aceita receber avisos sobre os jogos que acompanha.</p></div></div>
                <div className="perfil-opcoes-notificacao">
                  <PreferenciaToggle titulo="Notificações por e-mail" descricao={emailVerificado ? 'Receba avisos na sua caixa de entrada quando um jogo atender às condições que você configurou.' : 'Confirme seu e-mail para liberar este canal de notificação.'} checked={emailVerificado && preferenciasNotificacao.email} disabled={!emailVerificado || !preferenciasNotificacaoCarregadas} onChange={valor => alterarNotificacao('email', valor)} />
                  {!emailVerificado && <div className="perfil-email-nao-verificado"><span aria-hidden="true">ⓘ</span><div><strong>Confirme seu e-mail para ativar</strong><small>O endereço precisa estar confirmado antes de habilitar alertas por e-mail.</small></div><button type="button" onClick={() => { document.getElementById('perfil-conta-email')?.scrollIntoView({ behavior: 'smooth', block: 'center' }); document.getElementById('perfil-conta-email-acao')?.focus() }}>Ir para confirmação</button></div>}
                  <PreferenciaToggle titulo="Notificações no site" descricao="Preferência da conta para avisos dentro do DESCTRL." checked={preferenciasNotificacao.site} disabled={!preferenciasNotificacaoCarregadas} onChange={valor => alterarNotificacao('site', valor)} />
                </div>
                  {erroPreferenciasNotificacao && <p className="perfil-aviso-local" role="alert"><span aria-hidden="true">ⓘ</span> {erroPreferenciasNotificacao}</p>}
                  <p className="perfil-aviso-local"><span aria-hidden="true">ⓘ</span> As preferências ficam salvas na sua conta. Use o sininho em cada jogo para definir as condições de preço. Os avisos do site ficam disponíveis no histórico da aba Notificações; os e-mails são avaliados após as coletas diárias.</p>
              </section>

              <section className="perfil-configuracao-secao">
                <div className="perfil-configuracao-secao-titulo"><span aria-hidden="true">♙</span><div><h3>Conta e segurança</h3><p>Gerencie seu nome de usuário e os dados de acesso da conta.</p></div></div>
                <div className="perfil-dados-conta perfil-dados-conta-grade">
                  <article className="perfil-dado-conta-card">
                    <div className="perfil-dado-conta-icone" aria-hidden="true">@</div>
                    <div className="perfil-dado-conta-conteudo"><span>Nome de usuário</span><strong>{nomeUsuario}</strong><small>Seu identificador público no DESCTRL.</small></div>
                    <button type="button" className="perfil-dado-conta-acao" onClick={() => { setNovoUsername(nomeUsuario); setEditandoUsername(valor => !valor); setUsernameMensagem(null); setUsernameStatus({ tipo: '', mensagem: '' }) }} aria-label="Editar nome de usuário" title="Editar nome de usuário">✎</button>
                  </article>
                  <article className="perfil-dado-conta-card" id="perfil-conta-email">
                    <div className="perfil-dado-conta-icone" aria-hidden="true">✉</div>
                    <div className="perfil-dado-conta-conteudo"><span>E-mail</span><strong>{emailUsuario}</strong><small>{emailVerificado ? 'Endereço confirmado.' : 'Confirmação do endereço ainda não identificada pela sessão.'}</small></div>
                    <button id="perfil-conta-email-acao" type="button" className="perfil-dado-conta-acao-texto" onClick={() => abrirModalConta('email')}>Alterar</button>
                  </article>
                  <article className="perfil-dado-conta-card">
                    <div className="perfil-dado-conta-icone" aria-hidden="true">♙</div>
                    <div className="perfil-dado-conta-conteudo"><span>Senha</span><strong>••••••••</strong><small>Altere sua senha de acesso.</small></div>
                    <button type="button" className="perfil-dado-conta-acao-texto" onClick={() => abrirModalConta('senha')}>Alterar</button>
                  </article>
                  <article className="perfil-dado-conta-card">
                    <div className="perfil-dado-conta-icone" aria-hidden="true">⌘</div>
                    <div className="perfil-dado-conta-conteudo"><span>Navegadores conectados</span><strong>Gerenciamento de sessões</strong><small>Consulte e encerre sessões conectadas.</small></div>
                    <span className="perfil-status-em-breve">Em breve</span>
                  </article>
                </div>
                {editandoUsername && (
                  <form className="perfil-editar-username" onSubmit={salvarUsername}>
                    <label htmlFor="perfil-novo-username">Novo nome de usuário</label>
                    <div className={`perfil-editar-username-campo ${usernameStatus.tipo === 'erro' ? 'tem-erro' : ''} ${usernameStatus.tipo === 'disponivel' ? 'tem-sucesso' : ''}`}>
                      <input id="perfil-novo-username" value={novoUsername} onChange={evento => { setNovoUsername(evento.target.value); setUsernameMensagem(null) }} minLength={3} maxLength={101} pattern="[A-Za-z0-9_.-]+" autoComplete="off" required aria-invalid={usernameStatus.tipo === 'erro'} aria-describedby="perfil-username-feedback" />
                      {usernameStatus.tipo === 'disponivel' && <span className="perfil-username-indicador disponivel" aria-label="Nome disponível" title="Nome disponível">✓</span>}
                      {usernameStatus.tipo === 'verificando' && <span className="perfil-username-indicador verificando" aria-label="Verificando" title="Verificando">…</span>}
                      {usernameStatus.tipo === 'erro' && <span className="perfil-username-indicador erro" aria-label="Nome indisponível" title="Nome indisponível">!</span>}
                      <button type="submit" disabled={usernameCarregando || usernameStatus.tipo !== 'disponivel'}>{usernameCarregando ? 'Salvando...' : 'Salvar alteração'}</button>
                    </div>
                    {usernameStatus.mensagem && <small id="perfil-username-feedback" className={`perfil-username-feedback ${usernameStatus.tipo}`} role={usernameStatus.tipo === 'erro' ? 'alert' : 'status'}>{usernameStatus.mensagem}</small>}
                    <p>Seu nome anterior ficará reservado para você por 14 dias corridos.</p>
                    <button type="button" className="perfil-cancelar-edicao" onClick={() => { setEditandoUsername(false); setUsernameMensagem(null); setUsernameStatus({ tipo: '', mensagem: '' }) }}>Cancelar</button>
                  </form>
                )}
                {usernameMensagem && <p className={`perfil-mensagem-username ${usernameMensagem.tipo}`} role="status">{usernameMensagem.texto}</p>}
                <div className="perfil-nomes-recuperaveis">
                  <div className="perfil-nomes-recuperaveis-cabecalho"><div><h4>Nomes anteriores</h4><p>Você pode recuperar um nome reservado enquanto o prazo de 14 dias estiver ativo.</p></div><button type="button" onClick={carregarNomesRecuperaveis} disabled={carregandoNomes}>{carregandoNomes ? 'Atualizando...' : 'Atualizar'}</button></div>
                  {carregandoNomes ? <p className="perfil-nomes-vazio">Consultando reservas...</p> : nomesRecuperaveis.length ? <div className="perfil-lista-nomes">{nomesRecuperaveis.map(nome => <article className="perfil-nome-recuperavel" key={nome.id}><div><strong>{nome.username_anterior}</strong><small>Reservado até {new Date(nome.reservado_ate).toLocaleString('pt-BR')}</small></div><button type="button" onClick={() => recuperarUsername(nome.id)} disabled={recuperandoId !== null}>{recuperandoId === nome.id ? 'Recuperando...' : 'Recuperar nome'}</button></article>)}</div> : <p className="perfil-nomes-vazio">Nenhum nome anterior disponível para recuperação no momento.</p>}
                </div>
                <p className="perfil-aviso-local"><span aria-hidden="true">ⓘ</span> A alteração do nome é registrada pelo backend. A interface de alteração de e-mail e senha está preparada, mas precisa ser conectada aos endpoints de segurança antes de efetivar mudanças.</p>
              </section>
              <section className="perfil-configuracao-secao">
                <div className="perfil-configuracao-secao-titulo"><span aria-hidden="true">⌘</span><div><h3>Contas vinculadas</h3><p>Gerencie formas adicionais de entrar no DESCTRL.</p></div></div>
                <div className="perfil-google-vinculo">
                  <div className="perfil-google-vinculo-texto">
                    <strong>Conta Google</strong>
                    <p>{usuario?.google_vinculado
                      ? 'Sua conta Google está vinculada e pode ser usada para entrar no DESCTRL.'
                      : 'Vincule sua conta Google atual para entrar futuramente sem digitar sua senha do DESCTRL.'}</p>
                  </div>
                  {usuario?.google_vinculado ? (
                    <p className="perfil-google-vinculo-status sucesso" role="status">
                      ✓ Conta Google vinculada e validada.
                    </p>
                  ) : (
                    <BotaoLoginGoogle
                      onCredential={vincularContaGoogle}
                      disabled={googleVinculando}
                    />
                  )}
                  {googleVinculando && <p className="perfil-google-vinculo-status" role="status">Vinculando conta Google...</p>}
                  {googleVinculoMensagem && (
                    <p className={`perfil-google-vinculo-status ${googleVinculoMensagem.tipo}`} role="status">
                      {googleVinculoMensagem.texto}
                    </p>
                  )}
                </div>
              </section>
              {modalContaAberto && (
                <div className="perfil-modal-overlay" onMouseDown={evento => { if (evento.target === evento.currentTarget) setModalContaAberto('') }}>
                  <section className="perfil-modal-conta" role="dialog" aria-modal="true" aria-labelledby="perfil-modal-conta-titulo">
                    <button type="button" className="perfil-modal-fechar" onClick={() => setModalContaAberto('')} aria-label="Fechar janela">×</button>
                    <span className="perfil-modal-conta-icone" aria-hidden="true">{modalContaAberto === 'email' ? '✉' : '♙'}</span>
                    <h3 id="perfil-modal-conta-titulo">{modalContaAberto === 'email' ? 'Alterar e-mail' : 'Alterar senha'}</h3>
                    <p>{modalContaAberto === 'email' ? 'Seu endereço atual continuará ativo até que o novo endereço seja confirmado.' : 'Use sua senha atual para definir uma nova senha de acesso.'}</p>
                    {modalContaAberto === 'email' ? (
                      <form onSubmit={evento => { evento.preventDefault(); solicitarAlteracaoEmail(evento.currentTarget) }}>
                        <label htmlFor="perfil-modal-novo-email">Novo endereço de e-mail</label>
                        <input name="novo_email" id="perfil-modal-novo-email" type="email" value={novoEmail} onChange={evento => { setNovoEmail(evento.target.value); setMensagemModalConta(null) }} placeholder="voce@exemplo.com" required autoComplete="email" />
                        <label htmlFor="perfil-modal-senha-atual-email">Senha atual do DESCTRL</label>
                        <input name="senha_atual" id="perfil-modal-senha-atual-email" type="password" placeholder="Digite sua senha atual" required autoComplete="current-password" />
                        {mensagemModalConta && <p className={`perfil-modal-feedback ${mensagemModalConta.tipo}`} role="status">{mensagemModalConta.texto}</p>}
                        <div className="perfil-modal-acoes"><button type="button" className="secundario" onClick={() => setModalContaAberto('')}>Cancelar</button><button type="button" disabled={emailAlteracaoCarregando} onClick={evento => { evento.preventDefault(); solicitarAlteracaoEmail(evento.currentTarget.form) }}>{emailAlteracaoCarregando ? 'Enviando...' : 'Enviar confirmação'}</button></div>
                      </form>
                    ) : (
                      <form onSubmit={async evento => { evento.preventDefault(); setMensagemModalConta(null); const form = evento.currentTarget; const dados = new FormData(form); const senhaAtual = String(dados.get('senha_atual') || ''); const novaSenha = String(dados.get('nova_senha') || ''); const confirmarSenha = String(dados.get('confirmar_senha') || ''); if (novaSenha !== confirmarSenha) { setMensagemModalConta({ tipo: 'erro', texto: 'A confirmação da nova senha não corresponde.' }); return; } try { const resposta = await fetch(`${API_BASE}/api/auth/senha/alterar`, { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ senha_atual: senhaAtual, nova_senha: novaSenha, confirmar_senha: confirmarSenha }) }); const resultado = await resposta.json().catch(() => ({})); if (!resposta.ok) throw new Error(resultado.detail || 'Não foi possível alterar a senha.'); form.reset(); setMensagemModalConta({ tipo: 'sucesso', texto: resultado.mensagem || 'Senha alterada com sucesso.' }); } catch (erro) { setMensagemModalConta({ tipo: 'erro', texto: erro.message || 'Falha ao alterar a senha.' }); } }}>
                        <label htmlFor="perfil-modal-senha-atual">Senha atual</label><input name="senha_atual" id="perfil-modal-senha-atual" type="password" required autoComplete="current-password" />
                        <label htmlFor="perfil-modal-nova-senha">Nova senha</label><input name="nova_senha" id="perfil-modal-nova-senha" type="password" minLength={8} required autoComplete="new-password" />
                        <label htmlFor="perfil-modal-confirmar-senha">Confirmar nova senha</label><input name="confirmar_senha" id="perfil-modal-confirmar-senha" type="password" minLength={8} required autoComplete="new-password" />
                        {mensagemModalConta && <p className={`perfil-modal-feedback ${mensagemModalConta.tipo}`} role="status">{mensagemModalConta.texto}</p>}
                        <div className="perfil-modal-acoes"><button type="button" className="secundario" onClick={() => setModalContaAberto('')}>Cancelar</button><button type="submit">Salvar nova senha</button></div>
                      </form>
                    )}
                  </section>
                </div>
              )}
            </section>
          ) : (
          <>
            <section className="perfil-identidade perfil-identidade-destaque">
              <div className="perfil-identidade-banner" aria-hidden="true" />
              <div className="perfil-identidade-conteudo">
                <div className="perfil-avatar-perfil" aria-hidden="true">
                  <span className="perfil-avatar perfil-avatar-emoldurado">{inicialAvatar}</span>
                </div>
                <div className="perfil-identidade-info">
                  <span className="perfil-identidade-sobretitulo">SEU ESPAÇO NO DESCTRL</span>
                  <div className="perfil-nome-linha">
                    <h2>{nomeUsuario}</h2>
                    <span className="perfil-badge">{nivelPerfil.titulo || papelUsuario}</span>
                  </div>
                  <p className="perfil-usuario">Nível {nivelPerfil.numero || 1} · {xpPerfil} XP</p>
                  <div className="perfil-xp-linha">
                    <div className="perfil-xp-trilho" role="progressbar" aria-label="Progresso para o próximo nível" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progressoNivelPerfil)}>
                      <span style={{ width: `${progressoNivelPerfil}%` }} />
                    </div>
                    <small>{proximoNivelPerfil ? `${Math.max(0, proximoNivelPerfil.xp_necessario - xpPerfil)} XP para nível ${proximoNivelPerfil.numero}` : 'Nível máximo'}</small>
                  </div>
                </div>
                <button className="perfil-personalizar-botao" type="button" onClick={() => { setTipoPersonalizacao('avatar'); setRecompensaSelecionada(null); setPersonalizacaoAberta(true) }}>
                  <span aria-hidden="true">✎</span> Personalizar perfil
                </button>
              </div>
            </section>

            <section className="perfil-estatisticas perfil-estatisticas-overview" aria-label="Resumo da conta">
              <article className="perfil-stat"><div className="perfil-stat-icone" aria-hidden="true">♥</div><div className="perfil-stat-conteudo"><span>Favoritos</span><strong>{carregandoFavoritos ? '…' : favoritosPerfil.length}</strong><p>Jogos guardados na sua coleção</p></div></article>
              <article className="perfil-stat"><div className="perfil-stat-icone" aria-hidden="true">✦</div><div className="perfil-stat-conteudo"><span>Conquistas</span><strong>{dadosConquistas ? `${conquistasDesbloqueadas.length}/${(dadosConquistas.conquistas || []).length}` : carregandoConquistas ? '…' : '—'}</strong><p>Objetivos já desbloqueados</p></div></article>
              <article className="perfil-stat"><div className="perfil-stat-icone" aria-hidden="true">⌁</div><div className="perfil-stat-conteudo"><span>No menor preço histórico</span><strong>{carregandoFavoritos ? '…' : favoritosNoMenorHistorico}</strong><p>Favoritos no menor preço registrado</p></div></article>
            </section>

            <div className="perfil-overview-grade">
              <section className="perfil-painel perfil-painel-favoritos">
                <header className="perfil-painel-cabecalho">
                  <div><span className="perfil-painel-eyebrow">SUA COLEÇÃO</span><h2>Jogos favoritos</h2><p>{favoritosDestaque.length > 1 ? 'Escolha de um a três jogos. Clique em um card para fixar seu histórico por 2 minutos.' : 'Escolha até três jogos para destacar. Seu jogo em destaque será mostrado no gráfico abaixo.'}</p></div>
                  <div className="perfil-painel-acoes"><button type="button" className="perfil-link-discreto perfil-link-botao" onClick={abrirModalDestaques} disabled={carregandoFavoritos || favoritosPerfil.length === 0}>Escolher destaques</button><Link to="/favoritos" className="perfil-link-discreto">Ver todos <span aria-hidden="true">↗</span></Link></div>
                </header>
                {erroFavoritos ? (
                  <div className="perfil-overview-vazio"><strong>Não foi possível carregar seus favoritos.</strong><p>{erroFavoritos}</p><button type="button" onClick={() => setVersaoFavoritosPerfil(versao => versao + 1)}>Tentar novamente</button></div>
                ) : carregandoFavoritos && favoritosPerfil.length === 0 ? (
                  <div className="perfil-overview-vazio"><span className="perfil-mini-spinner" aria-hidden="true" /><strong>Carregando sua coleção…</strong></div>
                ) : favoritosDestaque.length === 0 ? (
                  <div className="perfil-overview-vazio"><span className="perfil-estado-icone" aria-hidden="true">♥</span><strong>Sua coleção começa aqui</strong><p>Favorite jogos no catálogo e eles aparecerão neste espaço.</p><NavLink to="/jogos" className="perfil-link-acao">Explorar jogos</NavLink></div>
                ) : (
                  <div className={`perfil-favoritos-destaque quantidade-${favoritosDestaque.length}`}>
                    {favoritosDestaque.map((jogo, indice) => {
                      const selecionado = jogoSelecionadoGrafico?.id === jogo.id
                      const precoSteam = jogo.preco_steam
                      const precoEpic = jogo.preco_epic
                      const melhorPreco = [precoSteam, precoEpic].filter(valor => valor != null).map(Number).sort((a, b) => a - b)[0]
                      return (
                        <article className={`perfil-favorito-destaque ${selecionado ? 'selecionado-no-grafico' : ''}`} key={jogo.id}>
                          <button className="perfil-favorito-selecionar" type="button" onClick={() => fixarGraficoNoJogo(jogo.id)} aria-pressed={Boolean(selecionado)} title={`Mostrar histórico de ${jogo.nome}`}>
                            <span className={`perfil-favorito-capa ${jogo.imagem ? '' : 'sem-imagem'}`}>
                              {jogo.imagem && <img src={jogo.imagem} alt={`Capa de ${jogo.nome}`} loading="lazy" onError={evento => { evento.currentTarget.style.display = 'none'; evento.currentTarget.parentElement.classList.add('sem-imagem') }} />}
                              <span className="perfil-favorito-placeholder" aria-hidden="true">🎮</span>
                            </span>
                            <span className="perfil-favorito-texto"><strong>{jogo.nome}</strong><small>{jogo.desenvolvedor || jogo.publicadora || 'Jogo favorito'}</small></span>
                            <span className="perfil-favorito-preco">{melhorPreco == null ? 'Preço indisponível' : formatarDinheiroPerfil(melhorPreco)}</span>
                            <span className="perfil-favorito-estado">{selecionado ? 'No gráfico' : indice === 0 ? 'Favorito recente' : 'Ver histórico'}</span>
                          </button>
                          <Link to={`/jogos/${jogo.id}`} className="perfil-favorito-detalhes">Ver detalhes <span aria-hidden="true">↗</span></Link>
                        </article>
                      )
                    })}
                  </div>
                )}
              </section>

              <aside className="perfil-painel perfil-painel-conquistas">
                <header className="perfil-painel-cabecalho perfil-painel-cabecalho-lateral">
                  <div><span className="perfil-painel-eyebrow">PROGRESSO</span><h2>Conquistas recentes</h2></div>
                  <button type="button" className="perfil-link-discreto perfil-link-botao" onClick={() => selecionarAba('conquistas')}>Ver todas <span aria-hidden="true">↗</span></button>
                </header>
                {carregandoConquistas && !dadosConquistas ? <div className="perfil-overview-vazio perfil-overview-vazio-compacto">Carregando conquistas…</div> : conquistasRecentes.length ? (
                  <div className="perfil-conquistas-recentes">
                    {conquistasRecentes.map(conquista => (
                      <article className="perfil-conquista-recente" key={conquista.codigo}>
                        <span className={`perfil-conquista-recente-icone tipo-${conquista.tipo_recompensa || 'padrao'}`} aria-hidden="true">{conquista.tipo_recompensa === 'moldura' ? '◈' : conquista.tipo_recompensa === 'avatar' ? '♙' : conquista.tipo_recompensa === 'capa' ? '▧' : '✦'}</span>
                        <span className="perfil-conquista-recente-texto"><strong>{conquista.nome}</strong><small>{conquista.desbloqueada_em ? new Date(conquista.desbloqueada_em).toLocaleDateString('pt-BR') : 'Desbloqueada'} · +{conquista.xp} XP</small></span>
                      </article>
                    ))}
                  </div>
                ) : <div className="perfil-overview-vazio perfil-overview-vazio-compacto"><span className="perfil-estado-icone" aria-hidden="true">✦</span><strong>Suas conquistas aparecerão aqui</strong><p>Conclua objetivos para desbloquear recompensas e ganhar XP.</p><button type="button" onClick={() => selecionarAba('conquistas')}>Explorar conquistas</button></div>}
              </aside>
            </div>

            <section className="perfil-painel perfil-painel-grafico" aria-label="Histórico de preço dos favoritos">
              <header className="perfil-painel-cabecalho perfil-painel-grafico-cabecalho">
                <div><span className="perfil-painel-eyebrow">ACOMPANHE AS VARIAÇÕES</span><h2>Histórico de preços</h2><p>{jogoSelecionadoGrafico ? jogoSelecionadoGrafico.nome : 'Escolha um jogo favorito para visualizar os preços.'}</p></div>
                <div className="perfil-grafico-status">
                  {fixacaoExpiraEm ? <><span className="perfil-status-fixado">● Seleção fixa por 2 min</span><button type="button" onClick={retomarRotacaoGrafico}>Retomar rotação</button></> : favoritosDestaque.length > 1 ? <span className="perfil-status-automatico"><span aria-hidden="true">↻</span> Alterna a cada 10 segundos</span> : <span className="perfil-status-automatico">{favoritosDestaque.length === 1 ? 'Exibindo seu destaque' : 'Aguardando favoritos'}</span>}
                </div>
              </header>
              <div className="perfil-grafico-filtros" aria-label="Filtros do gráfico de preços">
                <div className="perfil-grafico-filtro-grupo">
                  <span className="perfil-grafico-filtro-rotulo">Loja</span>
                  <div className="perfil-grafico-opcoes" role="group" aria-label="Filtrar por loja">
                    {[{ valor: 'ambas', rotulo: 'Todas' }, { valor: 'steam', rotulo: 'Steam' }, { valor: 'epic', rotulo: 'Epic Games' }].map(opcao => (
                      <button type="button" key={opcao.valor} className={lojaGrafico === opcao.valor ? 'ativa' : ''} onClick={() => setLojaGrafico(opcao.valor)} aria-pressed={lojaGrafico === opcao.valor}>{opcao.rotulo}</button>
                    ))}
                  </div>
                </div>
                <div className="perfil-grafico-filtro-grupo">
                  <span className="perfil-grafico-filtro-rotulo">Período</span>
                  <div className="perfil-grafico-opcoes" role="group" aria-label="Filtrar por período">
                    {[{ valor: '1m', rotulo: '1 mês' }, { valor: '3m', rotulo: '3 meses' }, { valor: '6m', rotulo: '6 meses' }, { valor: '1a', rotulo: '1 ano' }, { valor: 'tudo', rotulo: 'Todo o período' }].map(opcao => (
                      <button type="button" key={opcao.valor} className={periodoGrafico === opcao.valor ? 'ativa' : ''} onClick={() => setPeriodoGrafico(opcao.valor)} aria-pressed={periodoGrafico === opcao.valor}>{opcao.rotulo}</button>
                    ))}
                  </div>
                </div>
              </div>
              {!jogoSelecionadoGrafico ? (
                <div className="perfil-overview-vazio"><span className="perfil-estado-icone" aria-hidden="true">⌁</span><strong>Nenhum favorito para analisar</strong><p>Adicione jogos aos favoritos para comparar suas variações de preço.</p><NavLink to="/jogos" className="perfil-link-acao">Encontrar jogos</NavLink></div>
              ) : (
                <>
                  <div className="perfil-grafico-resumo">
                    <div><span>Preço atual</span><strong>{formatarDinheiroPerfil(precoAtualGrafico)}</strong><small>{rotuloLojaResumoPerfil(lojaGrafico)}</small></div>
                    <div><span>Menor preço histórico</span><strong>{formatarDinheiroPerfil(menorHistoricoGrafico)}</strong><small>{lojaGrafico === 'ambas' ? 'Entre as lojas disponíveis' : `Na ${rotuloLojaResumoPerfil(lojaGrafico)}`}</small></div>
                    <div><span>Desconto atual</span><strong>{descontoAtualGrafico}%</strong><small>{lojaGrafico === 'ambas' ? 'Maior desconto entre as lojas' : `Na ${rotuloLojaResumoPerfil(lojaGrafico)}`}</small></div>
                  </div>
                  {errosHistoricoPerfil[jogoSelecionadoGrafico.id] ? (
                    <div className="perfil-grafico-sem-dados"><p>{errosHistoricoPerfil[jogoSelecionadoGrafico.id]}</p><button type="button" onClick={() => tentarNovamenteHistoricoPerfil(jogoSelecionadoGrafico.id)}>Tentar novamente</button></div>
                  ) : !Object.prototype.hasOwnProperty.call(historicosPorJogo, jogoSelecionadoGrafico.id) ? (
                    <div className="perfil-grafico-sem-dados"><span className="perfil-mini-spinner" aria-hidden="true" /><p>Carregando histórico de preços…</p></div>
                  ) : (!graficoPerfil.steamPath && !graficoPerfil.epicPath) ? (
                    <div className="perfil-grafico-sem-dados"><span aria-hidden="true">⌁</span><p>Não há registros para esta loja e este período. Experimente ampliar o intervalo ou trocar a loja.</p></div>
                  ) : (
                    <div className="perfil-grafico-area">
                      <div className="perfil-grafico-canvas">
                        <svg className="perfil-grafico-svg" viewBox="0 0 1000 180" width="100%" height="180" preserveAspectRatio="none" style={{ display: 'block', width: '100%', maxWidth: 'none', height: '180px' }} role="group" aria-label={`Histórico interativo de preços de ${jogoSelecionadoGrafico.nome} ${lojaGrafico === 'ambas' ? 'na Steam e Epic Games Store' : `na ${rotuloLojaResumoPerfil(lojaGrafico)}`}`} onMouseMove={atualizarTooltipGrafico} onMouseLeave={() => setTooltipGraficoHover(null)}>
                          <g className="perfil-grafico-eixo-preco" aria-hidden="true">
                            {graficoPerfil.ticksPreco.map((marcacao, i) => <text key={`preco-tick-${i}`} x="78" y={marcacao.y + 4} textAnchor="end">{formatarDinheiroPerfil(marcacao.valor)}</text>)}
                          </g>
                          {(tooltipGraficoFixada || tooltipGraficoHover) && <line className="perfil-grafico-cursor" x1={(tooltipGraficoFixada || tooltipGraficoHover).x} y1="26" x2={(tooltipGraficoFixada || tooltipGraficoHover).x} y2="150" aria-hidden="true" />}
                          {graficoPerfil.steamPath && <path className="perfil-grafico-linha steam" d={graficoPerfil.steamPath} fill="none" style={{ fill: 'none' }} />}
                          {graficoPerfil.epicPath && <path className="perfil-grafico-linha epic" d={graficoPerfil.epicPath} fill="none" style={{ fill: 'none' }} />}
                          {graficoPerfil.steamPontos.map((ponto, i) => <g key={`steam-${i}`}>
                            <circle className="perfil-grafico-ponto-alvo steam" cx={ponto.x} cy={ponto.y} r="9" tabIndex="0" role="button" aria-label={`Steam, ${formatarDinheiroPerfil(ponto.precoNumerico)}, ${formatarDataLongaPerfil(new Date(ponto.instante))}. Clique para fixar os detalhes por cinco segundos.`} onClick={evento => abrirTooltipGraficoFixada(evento, ponto, 'steam')} onKeyDown={evento => { if (evento.key === 'Enter' || evento.key === ' ') abrirTooltipGraficoFixada(evento, ponto, 'steam') }} />
                            <circle className="perfil-grafico-ponto steam" cx={ponto.x} cy={ponto.y} r="3" pointerEvents="none" />
                          </g>)}
                          {graficoPerfil.epicPontos.map((ponto, i) => <g key={`epic-${i}`}>
                            <circle className="perfil-grafico-ponto-alvo epic" cx={ponto.x} cy={ponto.y} r="9" tabIndex="0" role="button" aria-label={`Epic Games Store, ${formatarDinheiroPerfil(ponto.precoNumerico)}, ${formatarDataLongaPerfil(new Date(ponto.instante))}. Clique para fixar os detalhes por cinco segundos.`} onClick={evento => abrirTooltipGraficoFixada(evento, ponto, 'epic')} onKeyDown={evento => { if (evento.key === 'Enter' || evento.key === ' ') abrirTooltipGraficoFixada(evento, ponto, 'epic') }} />
                            <circle className="perfil-grafico-ponto epic" cx={ponto.x} cy={ponto.y} r="3" pointerEvents="none" />
                          </g>)}
                        </svg>
                        {(tooltipGraficoFixada || tooltipGraficoHover) && (() => {
                          const tooltip = tooltipGraficoFixada || tooltipGraficoHover
                          const pertoDoTopo = tooltip.y < 72
                          const classeLateral = tooltip.x < 190 ? 'lado-inicio' : tooltip.x > 835 ? 'lado-fim' : ''
                          return (
                            <div className={`perfil-grafico-tooltip ${pertoDoTopo ? 'abaixo' : ''} ${classeLateral} ${tooltip.tipo === 'fixa' ? 'fixada' : 'hover'}`} style={{ left: `${tooltip.x / 10}%`, top: `${pertoDoTopo ? tooltip.y + 11 : tooltip.y}px` }} role={tooltip.tipo === 'fixa' ? 'status' : 'tooltip'} aria-live={tooltip.tipo === 'fixa' ? 'polite' : undefined}>
                              <strong className="perfil-grafico-tooltip-data">{formatarDataLongaPerfil(tooltip.data)}</strong>
                              {tooltip.series.map((serie, indice) => <div className="perfil-grafico-tooltip-serie" key={`${serie.plataforma}-${indice}`}>
                                <span className={serie.plataforma}>{serie.plataforma === 'steam' ? 'Steam' : 'Epic Games Store'}</span>
                                <b>{serie.precoNumerico == null ? 'Sem cotação conhecida' : formatarDinheiroPerfil(serie.precoNumerico)}</b>
                                {serie.precoNumerico != null && <small>{Number(serie.desconto || 0) > 0 ? `-${Number(serie.desconto)}% de desconto` : 'Sem promoção'}</small>}
                              </div>)}
                              {tooltip.tipo === 'fixa' && <small className="perfil-grafico-tooltip-temporaria">Exibindo por 5 segundos</small>}
                            </div>
                          )
                        })()}
                      </div>
                      <div className="perfil-grafico-legenda">{(lojaGrafico === 'ambas' || lojaGrafico === 'steam') && <span className="steam">Steam</span>}{(lojaGrafico === 'ambas' || lojaGrafico === 'epic') && <span className="epic">Epic Games Store</span>}<small>{historicoParaGrafico.length} registros no período</small></div>
                      <div className="perfil-grafico-eixo"><span>{formatarDataCurtaPerfil(graficoPerfil.primeiraData)}</span><span>{formatarDataCurtaPerfil(graficoPerfil.ultimaData)}</span></div>
                    </div>
                  )}
                </>
              )}
            </section>
            <section className="perfil-painel perfil-minha-recomendacao" aria-labelledby="perfil-recomendacao-titulo">
              <header className="perfil-painel-cabecalho">
                <div><span className="perfil-painel-eyebrow">COMUNIDADE</span><h2 id="perfil-recomendacao-titulo">Minha recomendação</h2><p>Você pode manter uma recomendação ativa enquanto o jogo estiver em promoção.</p></div>
              </header>
              {carregandoRecomendacao ? <div className="perfil-recomendacao-vazio"><span className="perfil-mini-spinner" aria-hidden="true" /><p>Carregando sua recomendação…</p></div> : minhaRecomendacao ? (
                <div className="perfil-recomendacao-jogo">
                  <div className={`perfil-recomendacao-capa ${minhaRecomendacao.imagem ? '' : 'sem-imagem'}`}>
                    {minhaRecomendacao.imagem && <img src={minhaRecomendacao.imagem} alt={`Capa de ${minhaRecomendacao.nome}`} loading="lazy" onError={evento => { evento.currentTarget.style.display = 'none'; evento.currentTarget.parentElement.classList.add('sem-imagem') }} />}
                    <span aria-hidden="true">🎮</span>
                  </div>
                  <div className="perfil-recomendacao-conteudo">
                    <div className="perfil-recomendacao-titulo-linha"><h3>{minhaRecomendacao.nome}</h3><span className={`perfil-recomendacao-status ${minhaRecomendacao.promocao_status === 'ativa' ? 'ativa' : 'verificando'}`}><i aria-hidden="true" />{minhaRecomendacao.promocao_status === 'ativa' ? 'Em promoção' : 'Promoção sendo confirmada'}</span></div>
                    <p>{minhaRecomendacao.total_recomendacoes} {minhaRecomendacao.total_recomendacoes === 1 ? 'recomendação da comunidade' : 'recomendações da comunidade'}</p>
                    <div className="perfil-recomendacao-acoes"><Link to={minhaRecomendacao.link} className="perfil-recomendacao-ver-jogo">Ver jogo <span aria-hidden="true">↗</span></Link><button type="button" className="perfil-recomendacao-remover" onClick={removerMinhaRecomendacao} disabled={removendoRecomendacao}>{removendoRecomendacao ? 'Removendo…' : 'Remover recomendação'}</button></div>
                  </div>
                </div>
              ) : <div className="perfil-recomendacao-vazio"><span aria-hidden="true">✦</span><strong>Nenhuma recomendação ativa</strong><p>Abra a página de um jogo em promoção para indicá-lo à comunidade.</p><NavLink to="/jogos" className="perfil-recomendacao-ver-jogo">Explorar jogos <span aria-hidden="true">↗</span></NavLink></div>}
              {erroRecomendacao && <p className="perfil-recomendacao-erro" role="alert">{erroRecomendacao}</p>}
            </section>
          </>
          )}
          {modalDestaquesAberto && (
            <div className="perfil-modal-overlay" role="presentation" onMouseDown={evento => { if (evento.target === evento.currentTarget) setModalDestaquesAberto(false) }}>
              <section className="perfil-modal-destaques" role="dialog" aria-modal="true" aria-labelledby="perfil-modal-destaques-titulo">
                <header className="perfil-modal-cabecalho">
                  <div><span className="perfil-painel-eyebrow">SUA COLEÇÃO</span><h2 id="perfil-modal-destaques-titulo">Escolher jogos em destaque</h2><p>Selecione de um a três favoritos para mostrar na Visão geral. Você pode escolher menos de três; a ordem de seleção define a ordem dos cards.</p></div>
                  <button type="button" className="perfil-modal-fechar" onClick={() => setModalDestaquesAberto(false)} aria-label="Fechar seleção de destaques">×</button>
                </header>
                <div className="perfil-modal-destaques-corpo">
                  <div className="perfil-modal-destaques-toolbar">
                    <label className="perfil-modal-destaques-busca"><span aria-hidden="true">⌕</span><input value={buscaDestaques} onChange={evento => setBuscaDestaques(evento.target.value)} placeholder="Buscar nos favoritos…" aria-label="Buscar jogos favoritos" /></label>
                    <span className={`perfil-modal-destaques-contagem ${idsDestaqueRascunho.length === 3 ? 'completo' : ''}`}>{idsDestaqueRascunho.length}/3 selecionados</span>
                  </div>
                  {idsDestaqueRascunho.length > 0 && (
                    <div className="perfil-modal-destaques-selecionados" aria-label="Jogos selecionados para destaque">
                      <span>Selecionados</span>
                      {idsDestaqueRascunho.map(id => favoritosPerfil.find(jogo => String(jogo.id) === String(id))).filter(Boolean).map(jogo => (
                        <button type="button" key={jogo.id} onClick={() => alternarDestaqueRascunho(jogo.id)} title={`Remover ${jogo.nome} dos destaques`}>{jogo.nome}<span aria-hidden="true">×</span></button>
                      ))}
                    </div>
                  )}
                  <div className="perfil-modal-destaques-lista">
                    {favoritosPerfil.filter(jogo => String(jogo.nome || '').toLocaleLowerCase('pt-BR').includes(buscaDestaques.trim().toLocaleLowerCase('pt-BR'))).map(jogo => {
                      const selecionado = idsDestaqueRascunho.some(id => String(id) === String(jogo.id))
                      const desabilitado = !selecionado && idsDestaqueRascunho.length >= 3
                      return (
                        <button type="button" key={jogo.id} className={`perfil-modal-destaque-jogo ${selecionado ? 'selecionado' : ''}`} onClick={() => alternarDestaqueRascunho(jogo.id)} disabled={desabilitado} aria-pressed={selecionado}>
                          <span className={`perfil-modal-destaque-imagem ${jogo.imagem ? '' : 'sem-imagem'}`}>{jogo.imagem && <img src={jogo.imagem} alt="" loading="lazy" onError={evento => { evento.currentTarget.style.display = 'none'; evento.currentTarget.parentElement.classList.add('sem-imagem') }} />}<span aria-hidden="true">🎮</span></span>
                          <span className="perfil-modal-destaque-jogo-texto"><strong>{jogo.nome}</strong><small>{jogo.desenvolvedor || jogo.publicadora || 'Jogo favorito'}</small></span>
                          <span className="perfil-modal-destaque-check" aria-hidden="true">{selecionado ? '✓' : '+'}</span>
                        </button>
                      )
                    })}
                    {favoritosPerfil.filter(jogo => String(jogo.nome || '').toLocaleLowerCase('pt-BR').includes(buscaDestaques.trim().toLocaleLowerCase('pt-BR'))).length === 0 && <div className="perfil-modal-inventario-vazio"><strong>Nenhum jogo encontrado</strong><p>Tente outra busca.</p></div>}
                  </div>
                </div>
                <footer className="perfil-modal-destaques-rodape">
                  <p>Escolha pelo menos um favorito e no máximo três. A seleção fica salva neste navegador para sua conta.</p>
                  <div><button type="button" className="perfil-modal-cancelar" onClick={() => setModalDestaquesAberto(false)}>Cancelar</button><button type="button" className="perfil-personalizar-botao" onClick={salvarDestaques} disabled={idsDestaqueRascunho.length < 1}>Salvar destaques</button></div>
                </footer>
              </section>
            </div>
          )}

          {personalizacaoAberta && (
            <div className="perfil-modal-overlay" role="presentation" onMouseDown={evento => { if (evento.target === evento.currentTarget) setPersonalizacaoAberta(false) }}>
              <section className="perfil-modal-personalizacao" role="dialog" aria-modal="true" aria-labelledby="perfil-modal-personalizacao-titulo">
                <header className="perfil-modal-cabecalho">
                  <div><span className="perfil-painel-eyebrow">IDENTIDADE DO JOGADOR</span><h2 id="perfil-modal-personalizacao-titulo">Personalizar perfil</h2><p>Consulte as recompensas que você desbloqueou e prepare a aparência do seu perfil.</p></div>
                  <button type="button" className="perfil-modal-fechar" onClick={() => setPersonalizacaoAberta(false)} aria-label="Fechar personalização">×</button>
                </header>
                <nav className="perfil-modal-categorias" aria-label="Categorias de personalização">
                  <button type="button" className={tipoPersonalizacao === 'avatar' ? 'ativa' : ''} onClick={() => { setTipoPersonalizacao('avatar'); setRecompensaSelecionada(null) }}>Imagem de perfil</button>
                  <button type="button" className={tipoPersonalizacao === 'moldura' ? 'ativa' : ''} onClick={() => { setTipoPersonalizacao('moldura'); setRecompensaSelecionada(null) }}>Molduras</button>
                  <button type="button" className={tipoPersonalizacao === 'capa' ? 'ativa' : ''} onClick={() => { setTipoPersonalizacao('capa'); setRecompensaSelecionada(null) }}>Capas de perfil</button>
                </nav>
                <div className="perfil-modal-corpo">
                  <div className="perfil-modal-previa">
                    <span className="perfil-painel-eyebrow">PRÉVIA ATUAL</span>
                    {tipoPersonalizacao === 'capa' ? <div className="perfil-modal-previa-capa"><span>{nomeUsuario}</span></div> : tipoPersonalizacao === 'moldura' ? <div className="perfil-modal-previa-avatar moldura"><span>{inicialAvatar}</span></div> : <div className="perfil-modal-previa-avatar"><span>{inicialAvatar}</span></div>}
                    <strong>{recompensaVisualSelecionada ? recompensaVisualSelecionada.nome : tipoPersonalizacao === 'avatar' ? 'Imagem de perfil padrão' : tipoPersonalizacao === 'moldura' ? 'Moldura padrão' : 'Capa padrão'}</strong>
                    <small>A prévia usa o estilo padrão enquanto os arquivos visuais das recompensas não estiverem cadastrados.</small>
                  </div>
                  <div className="perfil-modal-inventario">
                    <div className="perfil-modal-inventario-cabecalho"><h3>Recompensas desbloqueadas</h3><span>{conquistasDesbloqueadas.filter(item => item.tipo_recompensa === tipoPersonalizacao).length}</span></div>
                    {conquistasDesbloqueadas.filter(item => item.tipo_recompensa === tipoPersonalizacao).length ? (
                      <div className="perfil-modal-itens">
                        {conquistasDesbloqueadas.filter(item => item.tipo_recompensa === tipoPersonalizacao).map(item => (
                          <button type="button" key={item.codigo} className={`perfil-modal-item ${recompensaSelecionada === item.codigo ? 'selecionado' : ''}`} onClick={() => setRecompensaSelecionada(item.codigo)} aria-pressed={recompensaSelecionada === item.codigo}>
                            <span className={`perfil-modal-item-amostra tipo-${tipoPersonalizacao}`} aria-hidden="true">{tipoPersonalizacao === 'avatar' ? '♙' : tipoPersonalizacao === 'moldura' ? '◈' : '▧'}</span>
                            <span><strong>{item.nome}</strong><small>Recompensa desbloqueada · {item.xp} XP</small></span>
                            {recompensaSelecionada === item.codigo && <span className="perfil-modal-item-check" aria-hidden="true">✓</span>}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <div className="perfil-modal-inventario-vazio"><span aria-hidden="true">▧</span><strong>Nenhuma recompensa nesta categoria ainda</strong><p>Continue avançando na aba Conquistas para desbloquear novos itens.</p><button type="button" onClick={() => { setPersonalizacaoAberta(false); selecionarAba('conquistas') }}>Ver conquistas</button></div>
                    )}
                  </div>
                </div>
                <footer className="perfil-modal-rodape"><p>O backend atual registra o tipo da recompensa, mas ainda não fornece o catálogo de imagens nem uma rota para equipar e salvar itens. Por isso, esta seleção é apenas uma prévia e não altera sua aparência de forma permanente.</p><button type="button" className="perfil-personalizar-botao" onClick={() => setPersonalizacaoAberta(false)}>Concluir</button></footer>
              </section>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}


function lerDestaquesSalvos(chave) {
  try {
    const valor = JSON.parse(localStorage.getItem(chave) || '[]')
    return Array.isArray(valor) ? valor.slice(0, 3) : []
  } catch {
    return []
  }
}

function filtrarHistoricoPorLojaPerfil(historico, loja) {
  return (Array.isArray(historico) ? historico : []).filter(registro => {
    const plataforma = normalizarPlataformaPerfil(registro.plataforma)
    return plataforma && (loja === 'ambas' || plataforma === loja)
  })
}

function filtrarHistoricoPorPeriodoPerfil(historico, periodo) {
  const diasPorPeriodo = { '1m': 30, '3m': 90, '6m': 180, '1a': 365, tudo: null }
  const dias = diasPorPeriodo[periodo] ?? null
  if (dias === null) return historico
  const limite = Date.now() - dias * 24 * 60 * 60 * 1000
  return historico.filter(registro => {
    const instante = registro.data_coleta ? new Date(registro.data_coleta).getTime() : NaN
    return Number.isFinite(instante) && instante >= limite
  })
}

function rotuloLojaResumoPerfil(loja) {
  if (loja === 'steam') return 'Steam'
  if (loja === 'epic') return 'Epic Games Store'
  return 'Steam e Epic Games Store'
}

function obterPrecoAtualFiltradoPerfil(historico, jogo, loja) {
  const obterPreco = plataforma => {
    const campo = plataforma === 'steam' ? 'preco_steam' : 'preco_epic'
    if (jogo?.[campo] != null && Number.isFinite(Number(jogo[campo]))) return Number(jogo[campo])
    const registros = (historico || []).filter(item => normalizarPlataformaPerfil(item.plataforma) === plataforma && item.preco_atual != null && Number.isFinite(Number(item.preco_atual)))
    if (!registros.length) return null
    return Number([...registros].sort((a, b) => new Date(a.data_coleta).getTime() - new Date(b.data_coleta).getTime()).at(-1).preco_atual)
  }
  if (loja === 'steam') return obterPreco('steam')
  if (loja === 'epic') return obterPreco('epic')
  const precos = [obterPreco('steam'), obterPreco('epic')].filter(valor => valor != null && Number.isFinite(Number(valor))).map(Number)
  return precos.length ? Math.min(...precos) : null
}

function obterDescontoAtualFiltradoPerfil(jogo, loja) {
  if (loja === 'steam') return Number(jogo?.desconto_steam || 0)
  if (loja === 'epic') return Number(jogo?.desconto_epic || 0)
  return Math.max(Number(jogo?.desconto_steam || 0), Number(jogo?.desconto_epic || 0))
}

const formatarDinheiroPerfil = valor => valor == null || !Number.isFinite(Number(valor))
  ? 'Indisponível'
  : Number(valor) === 0
    ? 'Grátis'
    : Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

function normalizarPlataformaPerfil(plataforma) {
  const valor = String(plataforma || '').toLowerCase()
  if (valor.includes('steam')) return 'steam'
  if (valor.includes('epic')) return 'epic'
  return null
}

function prepararGraficoPerfil(historicoCompleto, periodo = '3m', loja = 'ambas') {
  const normalizarRegistros = lista => (Array.isArray(lista) ? lista : [])
    .map(registro => ({
      ...registro,
      plataformaNormalizada: normalizarPlataformaPerfil(registro.plataforma),
      instante: registro.data_coleta ? new Date(registro.data_coleta).getTime() : NaN,
      precoNumerico: registro.preco_atual == null ? NaN : Number(registro.preco_atual),
    }))
    .filter(registro => registro.plataformaNormalizada && Number.isFinite(registro.instante) && Number.isFinite(registro.precoNumerico))
    .sort((a, b) => a.instante - b.instante)

  // O gráfico usa somente observações que já aconteceram. O eixo temporal,
  // porém, sempre termina no momento atual, e não na última coleta registrada.
  // Assim, um preço sem atualização continua válido até hoje sem criar uma
  // observação ou marcador fictício no histórico.
  const agora = Date.now()
  const todosRegistros = normalizarRegistros(historicoCompleto)
    .filter(registro => registro.instante <= agora)
  const vazio = { steamPath: '', epicPath: '', steamPontos: [], epicPontos: [], steamSerie: [], epicSerie: [], ticksPreco: [], primeiraData: null, ultimaData: null, inicioMs: null, fimMs: null, xInicial: 88, xFinal: 988 }
  if (!todosRegistros.length) return vazio

  const diasPorPeriodo = { '1m': 30, '3m': 90, '6m': 180, '1a': 365, tudo: null }
  const dias = diasPorPeriodo[periodo] ?? null
  const primeiroHistorico = todosRegistros[0].instante
  const limitePeriodo = dias === null ? primeiroHistorico : agora - dias * 24 * 60 * 60 * 1000

  // A janela cobre todo o período selecionado até hoje. Não exigimos uma
  // observação dentro da janela: se a loja só tiver uma cotação anterior,
  // esse último preço conhecido é carregado do início ao fim do intervalo.
  const inicio = limitePeriodo
  const fim = agora
  if (!Number.isFinite(inicio) || !Number.isFinite(fim) || fim < inicio) return vazio

  const xInicial = 88
  const xFinal = 988
  const topo = 26
  const base = 150
  const amplitudeTempo = Math.max(1, fim - inicio)
  const posicionarX = instante => xInicial + ((instante - inicio) / amplitudeTempo) * (xFinal - xInicial)

  const plataformasVisiveis = loja === 'ambas' ? ['steam', 'epic'] : [loja]
  const seriesBrutas = {}

  for (const plataforma of ['steam', 'epic']) {
    if (!plataformasVisiveis.includes(plataforma)) {
      seriesBrutas[plataforma] = { caminho: [], observacoes: [] }
      continue
    }

    const registrosLoja = todosRegistros.filter(registro => registro.plataformaNormalizada === plataforma && registro.instante <= fim)
    if (!registrosLoja.length) {
      seriesBrutas[plataforma] = { caminho: [], observacoes: [] }
      continue
    }

    const anterioresAoInicio = registrosLoja.filter(registro => registro.instante <= inicio)
    const primeiroConhecido = anterioresAoInicio.length ? anterioresAoInicio[anterioresAoInicio.length - 1] : null
    const observacoesNaJanela = registrosLoja.filter(registro => registro.instante > inicio && registro.instante <= fim)
    const observacaoExataInicio = registrosLoja.find(registro => registro.instante === inicio)
    const pontosCaminho = []

    if (observacaoExataInicio) {
      pontosCaminho.push({ ...observacaoExataInicio, instante: inicio, sintetico: false })
    } else if (primeiroConhecido) {
      pontosCaminho.push({ ...primeiroConhecido, instante: inicio, sintetico: true })
    }

    const ultimoInstanteIncluido = pontosCaminho.length ? inicio : -Infinity
    pontosCaminho.push(...observacoesNaJanela
      .filter(registro => registro.instante > ultimoInstanteIncluido)
      .map(registro => ({ ...registro, sintetico: false })))

    seriesBrutas[plataforma] = {
      caminho: pontosCaminho,
      // Marcadores aparecem somente para observações reais dentro do período.
      observacoes: pontosCaminho.filter(registro => !registro.sintetico && registro.instante >= inicio && registro.instante <= fim),
    }
  }

  const todosPontosBrutos = ['steam', 'epic'].flatMap(plataforma => seriesBrutas[plataforma].caminho)
  if (!todosPontosBrutos.length) return vazio

  const valores = todosPontosBrutos.map(registro => registro.precoNumerico)
  let menorPreco = Math.min(...valores)
  let maiorPreco = Math.max(...valores)
  if (Math.abs(maiorPreco - menorPreco) < 0.000001) {
    const margem = maiorPreco === 0 ? 1 : Math.max(0.5, Math.abs(maiorPreco) * 0.05)
    menorPreco = Math.max(0, menorPreco - margem)
    maiorPreco += margem
  }
  const amplitudePreco = Math.max(0.000001, maiorPreco - menorPreco)
  const posicionar = registro => ({
    ...registro,
    x: posicionarX(registro.instante),
    y: base - ((registro.precoNumerico - menorPreco) / amplitudePreco) * (base - topo),
    sintetico: Boolean(registro.sintetico),
  })

  // Caminhos em escada sem área preenchida. O último valor conhecido fica
  // horizontal até hoje; somente observações reais recebem marcadores.
  const caminho = pontos => {
    if (!pontos.length) return ''
    let d = `M ${pontos[0].x.toFixed(2)} ${pontos[0].y.toFixed(2)}`
    for (let indice = 1; indice < pontos.length; indice += 1) {
      const ponto = pontos[indice]
      d += ` H ${ponto.x.toFixed(2)} V ${ponto.y.toFixed(2)}`
    }
    if (pontos[pontos.length - 1].x < xFinal - 0.5) d += ` H ${xFinal.toFixed(2)}`
    return d
  }

  const steamCaminhoPontos = seriesBrutas.steam.caminho.map(posicionar)
  const epicCaminhoPontos = seriesBrutas.epic.caminho.map(posicionar)
  const steamPontos = seriesBrutas.steam.observacoes.map(posicionar)
  const epicPontos = seriesBrutas.epic.observacoes.map(posicionar)
  const ticksPreco = Array.from({ length: 5 }, (_, indice) => {
    const fracao = indice / 4
    return {
      valor: maiorPreco - fracao * amplitudePreco,
      y: topo + fracao * (base - topo),
    }
  })

  return {
    steamPath: caminho(steamCaminhoPontos),
    epicPath: caminho(epicCaminhoPontos),
    steamPontos,
    epicPontos,
    steamSerie: steamCaminhoPontos,
    epicSerie: epicCaminhoPontos,
    ticksPreco,
    primeiraData: new Date(inicio),
    ultimaData: new Date(fim),
    inicioMs: inicio,
    fimMs: fim,
    xInicial,
    xFinal,
  }
}

function formatarDataLongaPerfil(valor) {
  if (!valor || !Number.isFinite(new Date(valor).getTime())) return 'Data indisponível'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' }).format(new Date(valor))
}

function obterMenorHistoricoPerfil(historico) {
  const precos = (historico || []).filter(item => normalizarPlataformaPerfil(item.plataforma) && item.preco_atual != null && Number.isFinite(Number(item.preco_atual))).map(item => Number(item.preco_atual))
  return precos.length ? Math.min(...precos) : null
}

function formatarDataCurtaPerfil(valor) {
  if (!valor) return 'Sem data'
  return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', year: '2-digit' }).format(valor)
}


function ConquistasPanel({ dados, carregando, erro, dicasVisiveis, alternarDicas }) {
  const [grupoSelecionadoId, setGrupoSelecionadoId] = useState(1)
  const grupos = [
    { id: 1, titulo: 'Conta completa', descricao: 'Dê os primeiros passos e complete sua identidade.', codigos: ['boas_vindas', 'identidade_confirmada', 'tudo_em_ordem'] },
    { id: 2, titulo: 'Colecionador de jogos', descricao: 'Monte sua coleção de favoritos. O progresso é permanente, mesmo se remover jogos depois.', codigos: ['primeiro_da_colecao', 'colecao_em_formacao', 'cofre_de_jogos'] },
    { id: 3, titulo: 'Explorador de ofertas', descricao: 'Descubra jogos e acompanhe o que aparece na página de ofertas.', codigos: ['conhecendo_o_terreno', 'de_olho_nas_ofertas', 'cacador_de_oportunidades'] },
  ]
  const catalogoVisual = {
    boas_vindas: { dica: 'Basta visitar Meu perfil estando conectado à sua conta.', dificuldade: 'Fácil', recompensa: 'Moldura de avatar', icone: '✦' },
    identidade_confirmada: { dica: 'A conquista será liberada quando a validação de e-mail estiver disponível e for concluída.', dificuldade: 'Média', recompensa: 'Imagem de perfil', icone: '✉' },
    tudo_em_ordem: { dica: 'Esta conquista é automática após Boas-vindas ao DESCTRL e Identidade confirmada.', dificuldade: 'Difícil', recompensa: 'Capa de perfil', icone: '✓' },
    primeiro_da_colecao: { dica: 'Marque qualquer jogo como favorito. Cada jogo diferente conta apenas uma vez.', dificuldade: 'Fácil', recompensa: 'Moldura de avatar', icone: '★' },
    colecao_em_formacao: { dica: 'O histórico considera jogos diferentes que você já favoritou, mesmo que depois desfavoritados.', dificuldade: 'Média', recompensa: 'Imagem de perfil', icone: '▦' },
    cofre_de_jogos: { dica: 'Cada jogo conta uma única vez no histórico da sua coleção.', dificuldade: 'Difícil', recompensa: 'Capa de perfil', icone: '▣' },
    conhecendo_o_terreno: { dica: 'Entre nos detalhes de qualquer jogo enquanto estiver conectado.', dificuldade: 'Fácil', recompensa: 'Moldura de avatar', icone: '⌕' },
    de_olho_nas_ofertas: { dica: 'Consulte um jogo na página de ofertas.', dificuldade: 'Média', recompensa: 'Imagem de perfil', icone: '%' },
    cacador_de_oportunidades: { dica: 'Consulte dez jogos diferentes na página de ofertas.', dificuldade: 'Difícil', recompensa: 'Capa de perfil', icone: '⌖' },
  }
  const conquistas = dados?.conquistas || []
  const porCodigo = Object.fromEntries(conquistas.map(item => [item.codigo, item]))
  const xpTotal = dados?.xp_total ?? 0
  const xpDisponivel = conquistas.reduce((total, item) => total + (Number(item.xp) || 0), 0)
  const nivel = dados?.nivel || { numero: 1, titulo: 'Recruta', xp_minimo: 0 }
  const proximoNivel = dados?.proximo_nivel
  const xpNivelAtual = xpTotal - (nivel.xp_minimo || 0)
  const xpParaProximo = proximoNivel ? proximoNivel.xp_necessario - (nivel.xp_minimo || 0) : 0
  const percentualNivel = proximoNivel && xpParaProximo > 0 ? Math.min(100, Math.max(0, (xpNivelAtual / xpParaProximo) * 100)) : 100
  const totalDesbloqueadas = conquistas.filter(item => item.desbloqueada).length
  const grupoSelecionado = grupos.find(grupo => grupo.id === grupoSelecionadoId) || grupos[0]
  const conquistasGrupo = grupoSelecionado.codigos.map(codigo => {
    const item = porCodigo[codigo]
    return item ? { ...item, ...(catalogoVisual[codigo] || {}) } : null
  }).filter(Boolean)
  const grupoAnteriorConcluido = grupoSelecionadoId === 1 || grupos
    .filter(grupo => grupo.id < grupoSelecionadoId)
    .every(grupo => grupo.codigos.every(codigo => Boolean(porCodigo[codigo]?.desbloqueada)))
  const grupoBloqueado = !grupoAnteriorConcluido
  const desbloqueadasNoGrupo = conquistasGrupo.filter(item => item.desbloqueada).length

  return (
    <section className="conquistas-pagina" aria-label="Conquistas e recompensas">
      <div className="conquistas-resumo">
        <div className="conquistas-nivel-emblema" aria-hidden="true">{['Ⅰ', 'Ⅱ', 'Ⅲ', 'Ⅳ', 'Ⅴ'][Math.min(Math.max((nivel.numero || 1) - 1, 0), 4)]}</div>
        <div className="conquistas-nivel-info">
          <span className="conquistas-sobretitulo">SEU PROGRESSO</span>
          <div className="conquistas-nivel-titulo"><h2>Nível {nivel.numero}</h2><span>{nivel.titulo}</span></div>
          <p>Ganhe XP ao concluir conquistas. Seu título evolui automaticamente quando você sobe de nível.</p>
          <div className="conquistas-barra-progresso" role="progressbar" aria-label="Progresso até o próximo nível" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(percentualNivel)}><span style={{ width: `${percentualNivel}%` }} /></div>
          <small>{xpTotal} XP conquistado{proximoNivel ? ` · ${Math.max(0, proximoNivel.xp_necessario - xpTotal)} XP para o nível ${proximoNivel.numero}` : ' · Nível máximo alcançado'}</small>
        </div>
        <div className="conquistas-resumo-numeros">
          <div><strong>{totalDesbloqueadas}/{conquistas.length || 9}</strong><span>Conquistas</span></div>
          <div><strong>{xpTotal}/{xpDisponivel || 300}</strong><span>XP conquistado</span></div>
        </div>
      </div>

      {carregando && <p className="conquistas-aviso-integracao" role="status">Sincronizando suas conquistas...</p>}
      {erro && <p className="conquistas-aviso-integracao" role="alert">{erro}</p>}

      <div className="conquistas-cabecalho-lista">
        <div><h2>Jornada de conquistas</h2><p>Avance por cada etapa e desbloqueie recompensas permanentes para seu perfil.</p></div>
        <button type="button" className={`conquistas-botao-dicas ${dicasVisiveis ? 'ativo' : ''}`} onClick={alternarDicas} aria-pressed={dicasVisiveis} aria-label={dicasVisiveis ? 'Ocultar dicas das conquistas' : 'Mostrar dicas das conquistas'} title={dicasVisiveis ? 'Ocultar dicas' : 'Mostrar dicas'}>{dicasVisiveis ? '◉' : '◎'} <span>{dicasVisiveis ? 'Ocultar dicas' : 'Ver dicas'}</span></button>
      </div>

      <nav className="conquistas-trilha" aria-label="Grupos de conquistas">
        <div className="conquistas-trilha-linha" aria-hidden="true"><span style={{ width: `${((grupoSelecionadoId - 1) / (grupos.length - 1)) * 100}%` }} /></div>
        {grupos.map(grupo => {
          const bloqueado = grupo.id > 1 && !grupos.filter(anterior => anterior.id < grupo.id).every(anterior => anterior.codigos.every(codigo => Boolean(porCodigo[codigo]?.desbloqueada)))
          const selecionado = grupo.id === grupoSelecionadoId
          const totalGrupo = grupo.codigos.filter(codigo => Boolean(porCodigo[codigo]?.desbloqueada)).length
          return (
            <button type="button" key={grupo.id} className={`conquistas-trilha-etapa ${selecionado ? 'selecionada' : ''} ${bloqueado ? 'bloqueada' : ''}`} onClick={() => setGrupoSelecionadoId(grupo.id)} aria-current={selecionado ? 'step' : undefined} aria-label={`Ver ${bloqueado ? 'prévia do ' : ''}grupo ${grupo.id}: ${grupo.titulo}${bloqueado ? ', bloqueado' : ''}`}>
              <span className="conquistas-trilha-marco" aria-hidden="true">{bloqueado ? '🔒' : grupo.id}</span>
              <span className="conquistas-trilha-nome">{grupo.titulo}</span>
              <span className="conquistas-trilha-contagem">{totalGrupo}/3</span>
            </button>
          )
        })}
      </nav>

      <section className={`conquistas-grupo-detalhe ${grupoBloqueado ? 'bloqueado' : ''}`} aria-labelledby="conquistas-grupo-atual-titulo">
        <header className="conquistas-grupo-detalhe-cabecalho">
          <div><span>GRUPO {grupoSelecionado.id}{grupoBloqueado ? ' · PRÉVIA' : ''}</span><h3 id="conquistas-grupo-atual-titulo">{grupoSelecionado.titulo}</h3><p>{grupoSelecionado.descricao}</p></div>
          <strong>{desbloqueadasNoGrupo}/3</strong>
        </header>
        {grupoBloqueado && <p className="conquistas-grupo-aviso">Conclua o grupo anterior para liberar esta etapa. Você pode consultar as conquistas e recompensas previstas.</p>}
        <div className="conquistas-timeline">
          {conquistasGrupo.map((conquista, posicao) => {
            const desbloqueada = Boolean(conquista.desbloqueada)
            const bloqueada = grupoBloqueado || !dados
            const status = bloqueada ? 'Bloqueada' : desbloqueada ? 'Desbloqueada' : 'Não desbloqueada'
            const progresso = Number(conquista.progresso) || 0
            const meta = Number(conquista.meta) || 1
            return (
              <article className={`conquista-timeline-item ${bloqueada ? 'conquista-bloqueada' : ''} ${desbloqueada ? 'conquista-desbloqueada' : ''}`} key={conquista.codigo}>
                <div className="conquista-timeline-marcador" aria-hidden="true"><span /></div>
                <div className="conquista-icone" aria-hidden="true">{bloqueada ? '🔒' : conquista.icone}</div>
                <div className="conquista-conteudo">
                  <div className="conquista-titulo-linha"><h4>{conquista.nome}</h4><span className="conquista-status">{status}</span></div>
                  <p>{conquista.descricao}</p>
                  {dicasVisiveis && <div className="conquista-dica"><strong>Dica</strong><span>{conquista.dica}</span></div>}
                  <div className="conquista-metadados"><span>✦ {conquista.xp} XP</span><span>{conquista.dificuldade}</span>{!desbloqueada && !bloqueada && meta > 1 && <span>Progresso: {Math.min(progresso, meta)}/{meta}</span>}</div>
                  <div className="conquista-recompensa-compacta">
                    <span className="conquista-recompensa-icone" aria-hidden="true">{posicao === 0 ? '▱' : posicao === 1 ? '◉' : '▧'}</span>
                    <span><small>RECOMPENSA</small><strong>{conquista.recompensa}</strong></span>
                    <span className="conquista-recompensa-status">{bloqueada ? 'Bloqueada' : desbloqueada ? 'Desbloqueada' : 'A conquistar'}</span>
                  </div>
                  {desbloqueada && conquista.desbloqueada_em && <small className="conquista-data-desbloqueio">Conquistada em {new Date(conquista.desbloqueada_em).toLocaleDateString('pt-BR')}</small>}
                </div>
              </article>
            )
          })}
          {!carregando && !erro && dados && conquistasGrupo.length === 0 && <p>As conquistas deste grupo ainda não estão disponíveis no catálogo.</p>}
        </div>
      </section>
      <p className="conquistas-aviso-integracao"><span aria-hidden="true">ⓘ</span> Seu progresso é carregado do backend. As recompensas são permanentes e os desbloqueios são confirmados pelo sistema.</p>
    </section>
  )
}

function PreferenciaToggle({ titulo, descricao, checked, onChange, disabled = false }) {
  return (
    <label className="perfil-notificacao-linha">
      <span className="perfil-notificacao-texto"><strong>{titulo}</strong><small>{descricao}</small></span>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={evento => onChange(evento.target.checked)} />
      <span className="perfil-switch" aria-hidden="true"><i /></span>
    </label>
  )
}





export default Perfil
