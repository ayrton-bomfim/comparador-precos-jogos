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
      ? 'Clique no botão abaixo para confirmar o novo endereço de e-mail.'
      : 'Este link não contém um token de confirmação. Solicite uma nova alteração de e-mail pelo seu perfil.'
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
      setMensagem(dados.mensagem || 'E-mail alterado e confirmado com sucesso.')
    } catch (error) {
      setEstado('erro')
      setMensagem(error.message || 'Não foi possível conectar ao servidor. Tente novamente.')
    }
  }

  return (
    <main className="pagina-seguranca">
      <section className="seguranca-card">
        <div className="seguranca-marca">DES<span>CTRL</span></div>
        <h1>{estado === 'sucesso' ? 'E-mail confirmado' : estado === 'erro' ? 'Não foi possível confirmar' : 'Confirmar novo e-mail'}</h1>
        <p className="seguranca-descricao">
          {estado === 'sucesso'
            ? 'O novo endereço foi confirmado e agora está associado à sua conta.'
            : estado === 'erro'
              ? 'O endereço de e-mail atual permanece ativo. Você pode voltar ao perfil e solicitar uma nova confirmação.'
              : 'Confirme que deseja associar o novo endereço à sua conta DESCTRL. O endereço atual permanece ativo até a confirmação.'}
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
              {estado === 'carregando' ? 'Confirmando…' : 'Confirmar novo e-mail'}
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
