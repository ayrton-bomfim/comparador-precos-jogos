import { createContext, useContext, useEffect, useRef, useState } from 'react'

import { API_URL } from '../servicos/api'

export const API_BASE = API_URL

const TOKEN_KEY = 'desctrl_token'
const TEMPO_INATIVIDADE_MS = 6 * 60 * 60 * 1000
const INTERVALO_MINIMO_REFRESH_MS = 60 * 1000
const AuthContext = createContext(null)

// O JWT controla a validade máxima do token, e os eventos humanos controlam
// a renovação e o encerramento local após seis horas sem atividade.
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [usuario, setUsuario] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [sessaoExpirada, setSessaoExpirada] = useState(false)
  const [redirecionarInicioAposLogout, setRedirecionarInicioAposLogout] = useState(false)
  const tokenAtualRef = useRef(token)
  const ultimaAtividadeHumanaRef = useRef(Date.now())
  const ultimaRenovacaoRef = useRef(0)
  const renovacaoEmAndamentoRef = useRef(false)
  const temporizadorInatividadeRef = useRef(null)
  const tokenValidadoRef = useRef(null)

  useEffect(() => {
    tokenAtualRef.current = token
  }, [token])

  const encerrarSessao = (expirada = false) => {
    tokenAtualRef.current = null
    tokenValidadoRef.current = null
    if (temporizadorInatividadeRef.current !== null) {
      window.clearTimeout(temporizadorInatividadeRef.current)
      temporizadorInatividadeRef.current = null
    }
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUsuario(null)
    setCarregando(false)
    setSessaoExpirada(expirada)
  }

  // A inatividade é medida por eventos humanos, não por requisições automáticas.
  // A renovação é limitada a uma chamada por minuto durante o uso ativo.
  useEffect(() => {
    if (!token) {
      if (temporizadorInatividadeRef.current !== null) {
        window.clearTimeout(temporizadorInatividadeRef.current)
        temporizadorInatividadeRef.current = null
      }
      return undefined
    }

    let ativo = true
    ultimaAtividadeHumanaRef.current = Date.now()
    ultimaRenovacaoRef.current = Date.now()

    const agendarEncerramentoPorInatividade = () => {
      if (temporizadorInatividadeRef.current !== null) {
        window.clearTimeout(temporizadorInatividadeRef.current)
      }

      const tempoDecorrido = Date.now() - ultimaAtividadeHumanaRef.current
      const tempoRestante = Math.max(0, TEMPO_INATIVIDADE_MS - tempoDecorrido)

      temporizadorInatividadeRef.current = window.setTimeout(() => {
        if (!ativo) return

        const inatividadeAtual = Date.now() - ultimaAtividadeHumanaRef.current
        if (inatividadeAtual >= TEMPO_INATIVIDADE_MS) {
          encerrarSessao(true)
        } else {
          agendarEncerramentoPorInatividade()
        }
      }, tempoRestante)
    }

    const renovarSessaoPorAtividade = async () => {
      const tokenAtual = tokenAtualRef.current
      if (!ativo || !tokenAtual || renovacaoEmAndamentoRef.current) return

      const agora = Date.now()
      if (agora - ultimaRenovacaoRef.current < INTERVALO_MINIMO_REFRESH_MS) return

      renovacaoEmAndamentoRef.current = true
      ultimaRenovacaoRef.current = agora

      try {
        const resposta = await fetch(`${API_BASE}/api/auth/session/refresh`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${tokenAtual}` },
        })

        if (!ativo || tokenAtualRef.current !== tokenAtual) return

        if (resposta.status === 401) {
          encerrarSessao(true)
          return
        }

        if (!resposta.ok) {
          // Falhas transitórias não encerram a sessão imediatamente.
          // Uma interação posterior poderá tentar renovar novamente.
          ultimaRenovacaoRef.current = 0
          return
        }

        const dados = await resposta.json()
        if (!dados.access_token || !ativo || tokenAtualRef.current !== tokenAtual) {
          ultimaRenovacaoRef.current = 0
          return
        }

        localStorage.setItem(TOKEN_KEY, dados.access_token)
        tokenAtualRef.current = dados.access_token
        ultimaRenovacaoRef.current = Date.now()
        setToken(dados.access_token)
      } catch {
        // Se a rede falhar, uma próxima interação poderá tentar novamente.
        ultimaRenovacaoRef.current = 0
      } finally {
        renovacaoEmAndamentoRef.current = false
      }
    }

    const registrarAtividadeHumana = () => {
      if (!ativo || !tokenAtualRef.current) return

      ultimaAtividadeHumanaRef.current = Date.now()
      agendarEncerramentoPorInatividade()
      void renovarSessaoPorAtividade()
    }

    agendarEncerramentoPorInatividade()

    window.addEventListener('pointerdown', registrarAtividadeHumana, { passive: true })
    window.addEventListener('keydown', registrarAtividadeHumana)
    window.addEventListener('touchstart', registrarAtividadeHumana, { passive: true })
    window.addEventListener('mousemove', registrarAtividadeHumana, { passive: true })

    return () => {
      ativo = false
      window.removeEventListener('pointerdown', registrarAtividadeHumana)
      window.removeEventListener('keydown', registrarAtividadeHumana)
      window.removeEventListener('touchstart', registrarAtividadeHumana)
      window.removeEventListener('mousemove', registrarAtividadeHumana)
      if (temporizadorInatividadeRef.current !== null) {
        window.clearTimeout(temporizadorInatividadeRef.current)
        temporizadorInatividadeRef.current = null
      }
    }
  }, [token])

  // Agenda o encerramento usando a expiração real informada no JWT.
  useEffect(() => {
    if (!token) return undefined

    let expiraEmMs
    try {
      const partes = token.split('.')
      if (partes.length !== 3) return undefined
      const payloadBase64 = partes[1].replace(/-/g, '+').replace(/_/g, '/')
      const payload = JSON.parse(atob(payloadBase64.padEnd(Math.ceil(payloadBase64.length / 4) * 4, '=')))
      if (typeof payload.exp !== 'number') return undefined
      expiraEmMs = payload.exp * 1000
    } catch {
      // A API continua sendo a autoridade para validar tokens malformados.
      return undefined
    }

    const tokenAgendado = token
    const tempoRestante = expiraEmMs - Date.now()
    const temporizador = window.setTimeout(() => {
      if (tokenAtualRef.current === tokenAgendado) {
        encerrarSessao(true)
      }
    }, Math.max(0, tempoRestante))

    return () => window.clearTimeout(temporizador)
  }, [token])

  useEffect(() => {
    let ativo = true
    const tokenVerificado = token

    // Renovar o JWT não muda a identidade da sessão. Comparamos o `sub` do JWT
    // para não repetir /me a cada rotação do token.
    let identidadeToken = null
    if (tokenVerificado) {
      try {
        const parte = tokenVerificado.split('.')[1]?.replace(/-/g, '+').replace(/_/g, '/')
        const payload = JSON.parse(atob((parte || '').padEnd(Math.ceil((parte || '').length / 4) * 4, '=')))
        identidadeToken = String(payload.sub || '')
      } catch { identidadeToken = null }
    }
    if (tokenVerificado && identidadeToken && tokenValidadoRef.current === identidadeToken) {
      setCarregando(false)
      return () => { ativo = false }
    }

    async function carregarUsuario() {
      if (!tokenVerificado) {
        if (ativo) {
          setUsuario(null)
          setCarregando(false)
        }
        return
      }

      // A renovação do JWT também altera `token`, mas não deve fazer a
      // aplicação inteira voltar ao estado visual de carregamento.
      // O carregamento global é reservado à inicialização da sessão.
      try {
        const resposta = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${tokenVerificado}` },
        })

        if (!resposta.ok) throw new Error('Sessão inválida.')
        const dados = await resposta.json()

        if (ativo && tokenAtualRef.current === tokenVerificado) {
          tokenValidadoRef.current = identidadeToken
          setUsuario(dados)
        }
      } catch {
        // Uma resposta atrasada de uma sessão anterior não pode apagar a nova sessão.
        if (ativo && tokenAtualRef.current === tokenVerificado) {
          encerrarSessao(true)
        }
      } finally {
        if (ativo && tokenAtualRef.current === tokenVerificado) {
          setCarregando(false)
        }
      }
    }

    carregarUsuario()
    return () => { ativo = false }
  }, [token])

  const login = async (username, password) => {
    const corpo = new URLSearchParams()
    corpo.append('username', username)
    corpo.append('password', password)

    const resposta = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: corpo,
    })
    const dados = await resposta.json().catch(() => ({}))

    if (!resposta.ok) {
      throw new Error(dados.detail || 'Usuário ou senha inválidos.')
    }
    if (!dados.access_token) {
      throw new Error('A API não retornou um token de acesso válido.')
    }

    const novoToken = dados.access_token
    const respostaMe = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${novoToken}` },
    })

    if (!respostaMe.ok) {
      throw new Error('Login realizado, mas não foi possível carregar o usuário.')
    }

    const usuarioAtual = await respostaMe.json()
    localStorage.setItem(TOKEN_KEY, novoToken)
    tokenAtualRef.current = novoToken
    setSessaoExpirada(false)
    setCarregando(false)
    setUsuario(usuarioAtual)
    setToken(novoToken)
    return usuarioAtual
  }

  const loginGoogle = async (credential) => {
    const resposta = await fetch(`${API_BASE}/api/auth/google`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    })
    const dados = await resposta.json().catch(() => ({}))
    if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível entrar com o Google.')

    // Identidade Google nova: ainda não cria sessão nem conta; o usuário
    // precisa concluir o cadastro escolhendo username e senha.
    if (dados.cadastro_pendente) {
      return { cadastroPendente: true, email: dados.email }
    }
    if (!dados.access_token) throw new Error('A API não retornou um token de acesso válido.')

    const novoToken = dados.access_token
    const respostaMe = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${novoToken}` },
    })
    if (!respostaMe.ok) throw new Error('Login Google realizado, mas não foi possível carregar o usuário.')

    const usuarioAtual = await respostaMe.json()
    localStorage.setItem(TOKEN_KEY, novoToken)
    tokenAtualRef.current = novoToken
    setSessaoExpirada(false)
    setCarregando(false)
    setUsuario(usuarioAtual)
    setToken(novoToken)
    return usuarioAtual
  }

  const concluirCadastroGoogle = async (credential, { username, senha, confirmarSenha }) => {
    const resposta = await fetch(`${API_BASE}/api/auth/google/cadastro`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        credential,
        username,
        senha,
        confirmar_senha: confirmarSenha,
      }),
    })
    const dados = await resposta.json().catch(() => ({}))
    if (!resposta.ok) {
      throw new Error(dados.detail || 'Não foi possível concluir o cadastro com Google.')
    }
    if (!dados.access_token) {
      throw new Error('O servidor não retornou um token de acesso válido.')
    }

    const novoToken = dados.access_token
    const respostaMe = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${novoToken}` },
    })
    if (!respostaMe.ok) {
      throw new Error('Cadastro criado, mas não foi possível carregar os dados da conta.')
    }

    const usuarioAtual = await respostaMe.json()
    localStorage.setItem(TOKEN_KEY, novoToken)
    tokenAtualRef.current = novoToken
    setSessaoExpirada(false)
    setCarregando(false)
    setUsuario(usuarioAtual)
    setToken(novoToken)
    return usuarioAtual
  }

  const atualizarUsuario = (dadosAtualizados) => {
    setUsuario(atual => atual ? { ...atual, ...dadosAtualizados } : atual)
  }

  const logout = () => {
    encerrarSessao(false)
    setRedirecionarInicioAposLogout(true)
  }

  const limparAvisoSessaoExpirada = () => setSessaoExpirada(false)
  const limparRedirecionamentoLogout = () => setRedirecionarInicioAposLogout(false)

  return (
    <AuthContext.Provider
      value={{
        token,
        usuario,
        carregando,
        autenticado: Boolean(token && usuario),
        isAdmin: Boolean(token && usuario?.role === 'admin'),
        sessaoExpirada,
        limparAvisoSessaoExpirada,
        redirecionarInicioAposLogout,
        limparRedirecionamentoLogout,
        login,
        loginGoogle,
        concluirCadastroGoogle,
        atualizarUsuario,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

// Este hook é exportado junto do Provider intencionalmente; ambos pertencem ao contexto.
// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const contexto = useContext(AuthContext)
  if (!contexto) throw new Error('useAuth deve ser usado dentro de AuthProvider.')
  return contexto
}
