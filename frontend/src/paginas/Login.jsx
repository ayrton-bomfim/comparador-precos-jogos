import { useState } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../contextos/AuthContext'
import BotaoLoginGoogle from '../componentes/BotaoLoginGoogle'
import './Login.css'

function Login() {
  const { login, loginGoogle, autenticado, carregando } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState(location.state?.username || '')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [entrando, setEntrando] = useState(false)
  const [entrandoGoogle, setEntrandoGoogle] = useState(false)

  if (carregando) {
    return <main className="pagina-login"><div className="login-card">Carregando...</div></main>
  }

  // Se já estiver autenticado, padroniza o destino para a página inicial.
  if (autenticado) {
    return <Navigate to="/" replace />
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setErro('')
    setEntrando(true)

    try {
      await login(username.trim(), senha)
      navigate('/', { replace: true })
    } catch (error) {
      setErro(error.message)
    } finally {
      setEntrando(false)
    }
  }

  const handleGoogleCredential = async (credential) => {
    setErro('')
    setEntrandoGoogle(true)
    try {
      const resultado = await loginGoogle(credential)
      if (resultado?.cadastroPendente) {
        navigate('/cadastro', {
          replace: true,
          state: { googleCredential: credential, googleEmail: resultado.email },
        })
        return
      }
      navigate('/', { replace: true })
    } catch (error) {
      setErro(error.message || 'Não foi possível entrar com o Google.')
    } finally {
      setEntrandoGoogle(false)
    }
  }

  return (
    <main className="pagina-login">
      <section className="login-card">
        <div className="login-marca">DES<span>CTRL</span></div>
        <h1>Entrar</h1>
        <p>Acesse sua conta para continuar.</p>

        {location.state?.mensagem && (
          <div className="login-erro" role="status">
            {location.state.mensagem}
          </div>
        )}

        <form onSubmit={handleSubmit} className="login-form">
          <label>
            Usuário
            <input
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              required
            />
          </label>

          <label>
            Senha
            <input
              type="password"
              value={senha}
              onChange={(event) => setSenha(event.target.value)}
              autoComplete="current-password"
              required
            />
          </label>

          <div className="login-esqueci-senha" aria-label="Recuperação de senha ainda não disponível">
            Esqueci minha senha
          </div>

          {erro && <div className="login-erro" role="alert">{erro}</div>}

          <button type="submit" disabled={entrando}>
            {entrando ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
        <div className="login-google-separador"><span>ou</span></div>
        <BotaoLoginGoogle onCredential={handleGoogleCredential} disabled={entrando || entrandoGoogle} />
        {entrandoGoogle && <p className="login-google-status" role="status">Conectando à sua conta Google…</p>}
        <div className="login-cadastro-link">Ainda não tem uma conta? <Link to="/cadastro">Criar conta</Link></div>
        <div className="login-voltar-inicio"><Link to="/">← Voltar para a página inicial</Link></div>
      </section>
    </main>
  )
}

export default Login
