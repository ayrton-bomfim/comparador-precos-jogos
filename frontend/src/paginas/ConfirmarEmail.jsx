import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { API_BASE } from '../contextos/AuthContext'
import './FluxosSeguranca.css'

function ConfirmarEmail() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const [estado, setEstado] = useState(token ? 'aguardando' : 'erro')
  const [mensagem, setMensagem] = useState(
    token
      ? 'Clique no botão abaixo para confirmar o endereço de e-mail associado à sua conta.'
      : 'Este link não contém um token de confirmação. Solicite uma nova confirmação ou alteração de e-mail pelo seu perfil.'
  )

  async function confirmar() {
    if (!token) return
    setEstado('carregando')
    setMensagem('Estamos validando o link de confirmação.')

    try {
      const resposta = await fetch(`${API_BASE}/api/auth/email/confirmar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) {
        throw new Error(dados.detail || 'Não foi possível confirmar o novo e-mail. O link pode ter expirado.')
      }
      setEstado('sucesso')
      setMensagem(dados.mensagem || 'E-mail confirmado com sucesso.')
    } catch (error) {
      setEstado('erro')
      setMensagem(error.message || 'Não foi possível conectar ao servidor. Tente novamente.')
    }
  }

  return (
    <main className="pagina-seguranca">
      <section className="seguranca-card">
        <div className="seguranca-marca">DES<span>CTRL</span></div>
        <h1>{estado === 'sucesso' ? 'E-mail confirmado' : estado === 'erro' ? 'Não foi possível confirmar' : 'Confirmar e-mail'}</h1>
        <p className="seguranca-descricao">
          {estado === 'sucesso'
            ? 'Seu endereço de e-mail foi confirmado com sucesso.'
            : estado === 'erro'
              ? 'O endereço de e-mail não foi alterado. Volte ao perfil para solicitar um novo link de confirmação.'
              : 'Confirme o endereço de e-mail associado à sua conta DESCTRL. Se você solicitou uma alteração de endereço, o novo e-mail só será aplicado após a confirmação.'}
        </p>

        {estado === 'sucesso' ? (
          <div className="seguranca-mensagem" role="status">{mensagem}</div>
        ) : estado === 'erro' ? (
          <div className="seguranca-erro" role="alert">{mensagem}</div>
        ) : (
          <>
            {estado === 'carregando' && <p className="seguranca-status" role="status">{mensagem}</p>}
            {estado === 'aguardando' && <p className="seguranca-status">{mensagem}</p>}
            <button className="seguranca-botao" type="button" onClick={confirmar} disabled={estado === 'carregando'}>
              {estado === 'carregando' ? 'Confirmando…' : 'Confirmar e-mail'}
            </button>
          </>
        )}

        <Link className="seguranca-botao" style={{ marginTop: 18 }} to={estado === 'sucesso' ? '/perfil' : '/login'}>
          {estado === 'sucesso' ? 'Voltar ao perfil' : 'Voltar'}
        </Link>
      </section>
    </main>
  )
}

export default ConfirmarEmail
