import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { API_BASE } from '../contextos/AuthContext'
import './FluxosSeguranca.css'

function RedefinirSenha() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') || ''
  const [novaSenha, setNovaSenha] = useState('')
  const [confirmarSenha, setConfirmarSenha] = useState('')
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')

  async function redefinir(event) {
    event.preventDefault()
    setErro('')
    setSucesso('')

    if (!token) {
      setErro('Este link não contém um token de recuperação. Solicite um novo link.')
      return
    }
    if (novaSenha.length < 8) {
      setErro('A nova senha deve ter pelo menos 8 caracteres.')
      return
    }
    if (novaSenha !== confirmarSenha) {
      setErro('A confirmação da nova senha não corresponde.')
      return
    }

    setCarregando(true)
    try {
      const resposta = await fetch(`${API_BASE}/api/auth/senha/redefinir`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          nova_senha: novaSenha,
          confirmar_senha: confirmarSenha,
        }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível redefinir a senha. Solicite um novo link.')
      }
      setSucesso(dados.mensagem || 'Senha redefinida com sucesso.')
      setNovaSenha('')
      setConfirmarSenha('')
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
        <h1>Crie uma nova senha</h1>
        <p className="seguranca-descricao">
          Escolha uma nova senha para sua conta. Por segurança, o link de recuperação expira após 30 minutos e só pode ser utilizado uma vez.
        </p>

        {sucesso ? (
          <>
            <div className="seguranca-mensagem" role="status">{sucesso}</div>
            <button className="seguranca-botao" type="button" onClick={() => navigate('/login', { replace: true, state: { mensagem: 'Senha redefinida. Entre com sua nova senha.' } })}>
              Ir para o login
            </button>
          </>
        ) : (
          <form className="seguranca-form" onSubmit={redefinir}>
            {!token && <div className="seguranca-erro" role="alert">Token de recuperação ausente. Solicite um novo link.</div>}
            <label>
              Nova senha
              <input
                type="password"
                value={novaSenha}
                onChange={(event) => setNovaSenha(event.target.value)}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
              />
            </label>
            <label>
              Confirmar nova senha
              <input
                type="password"
                value={confirmarSenha}
                onChange={(event) => setConfirmarSenha(event.target.value)}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
                required
              />
            </label>
            {erro && <div className="seguranca-erro" role="alert">{erro}</div>}
            <button type="submit" disabled={carregando || !token}>
              {carregando ? 'Salvando nova senha…' : 'Redefinir senha'}
            </button>
          </form>
        )}

        <Link className="seguranca-link-voltar" to="/login">← Voltar para entrar</Link>
      </section>
    </main>
  )
}

export default RedefinirSenha
