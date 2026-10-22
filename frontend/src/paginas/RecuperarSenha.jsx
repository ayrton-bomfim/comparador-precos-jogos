import { useState } from 'react'
import { Link } from 'react-router-dom'
import { API_BASE } from '../contextos/AuthContext'
import './FluxosSeguranca.css'

function RecuperarSenha() {
  const [email, setEmail] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [mensagem, setMensagem] = useState('')

  async function enviarSolicitacao(event) {
    event.preventDefault()
    setErro('')
    setMensagem('')
    setCarregando(true)

    try {
      const resposta = await fetch(`${API_BASE}/api/auth/senha/recuperar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível processar a solicitação. Tente novamente.')
      }
      setMensagem(dados.mensagem || 'Se houver uma conta com esse e-mail, enviaremos instruções para redefinir a senha.')
    } catch (error) {
      setErro(error.message || 'Não foi possível conectar ao servidor. Tente novamente.')
    } finally {
      setCarregando(false)
    }
  }

  return (
    <main className="pagina-seguranca">
      <section className="seguranca-card">
        <div className="seguranca-marca">DES<span>CTRL</span></div>
        <h1>Recuperar senha</h1>
        <p className="seguranca-descricao">
          Informe o e-mail associado à sua conta. Se encontrarmos uma conta com esse endereço, enviaremos um link seguro para criar uma nova senha.
        </p>

        {mensagem ? (
          <div className="seguranca-mensagem" role="status">{mensagem}</div>
        ) : (
          <form className="seguranca-form" onSubmit={enviarSolicitacao}>
            <label>
              E-mail cadastrado
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
                maxLength={255}
                required
              />
            </label>
            {erro && <div className="seguranca-erro" role="alert">{erro}</div>}
            <button type="submit" disabled={carregando}>
              {carregando ? 'Enviando solicitação…' : 'Enviar link de recuperação'}
            </button>
          </form>
        )}

        <Link className="seguranca-link-voltar" to="/login">← Voltar para entrar</Link>
      </section>
    </main>
  )
}

export default RecuperarSenha
