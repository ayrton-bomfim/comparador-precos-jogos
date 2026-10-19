import { createContext, useContext, useEffect, useRef, useState } from 'react'

export const API_BASE = 'http://127.0.0.1:8000'

const TOKEN_KEY = 'desctrl_token'
const AuthContext = createContext(null)

// O prazo efetivo vem do campo "exp" do JWT emitido pelo backend.
// Assim, não duplicamos aqui os 60 minutos configurados no .env.
// Futuramente, a política de aviso de expiração pode ser implementada neste contexto.
export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY))
  const [usuario, setUsuario] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [sessaoExpirada, setSessaoExpirada] = useState(false)
  const [redirecionarInicioAposLogout, setRedirecionarInicioAposLogout] = useState(false)
  const tokenAtualRef = useRef(token)

  useEffect(() => {
    tokenAtualRef.current = token
  }, [token])

  const encerrarSessao = (expirada = false) => {
    tokenAtualRef.current = null
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUsuario(null)
    setCarregando(false)
    setSessaoExpirada(expirada)
  }

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

    async function carregarUsuario() {
      if (!tokenVerificado) {
        if (ativo) {
          setUsuario(null)
          setCarregando(false)
        }
        return
      }

      setCarregando(true)

      try {
        const resposta = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${tokenVerificado}` },
        })

        if (!resposta.ok) throw new Error('Sessão inválida.')
        const dados = await resposta.json()

        if (ativo && tokenAtualRef.current === tokenVerificado) {
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
