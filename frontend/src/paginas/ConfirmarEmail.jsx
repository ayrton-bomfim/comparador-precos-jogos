import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { API_BASE } from '../contextos/AuthContext'

export default function ConfirmarEmail() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const [estado, setEstado] = useState({ carregando: true, texto: 'Confirmando seu novo e-mail…', sucesso: false })
  useEffect(() => {
    let ativo = true
    if (!token) return () => { ativo = false }
    fetch(`${API_BASE}/api/auth/email/confirmar`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }) })
      .then(async r => { const data = await r.json().catch(() => ({})); if (!r.ok) throw new Error(data.detail || 'Não foi possível confirmar o e-mail.'); return data })
      .then(data => { if (ativo) setEstado({ carregando: false, texto: data.mensagem || 'E-mail confirmado com sucesso.', sucesso: true }) })
      .catch(e => { if (ativo) setEstado({ carregando: false, texto: e.message, sucesso: false }) })
    return () => { ativo = false }
  }, [token])
  return <main className="perfil-modal-conta" style={{ maxWidth: 560, margin: '12vh auto', padding: 32 }}><h1>Confirmação de e-mail</h1><p role="status">{token ? estado.texto : 'O link não contém um token válido.'}</p>{(!token || !estado.carregando) && <Link to="/perfil">Voltar ao perfil</Link>}</main>
}
