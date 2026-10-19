import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_BASE, useAuth } from '../contextos/AuthContext'
import './NotificacoesConquistas.css'

export default function NotificacoesConquistas() {
  const { token, usuario } = useAuth()
  const usuarioId = usuario?.id ?? usuario?.usuario_id ?? null

  if (!token || !usuario) return null

  // A key isolates the queue between accounts without resetting state in an effect.
  return <FilaNotificacoes key={`${usuarioId ?? 'usuario'}:${token}`} token={token} />
}

function FilaNotificacoes({ token }) {
  const navigate = useNavigate()
  const [fila, setFila] = useState([])
  const timerRef = useRef(null)
  const idsEmExibicaoRef = useRef(new Set())
  const notificacao = fila[0] ?? null

  useEffect(() => {
    let cancelado = false

    const consultar = async () => {
      try {
        const resposta = await fetch(`${API_BASE}/api/conquistas/notificacoes`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!resposta.ok) return
        const dados = await resposta.json()
        if (cancelado) return

        const itens = Array.isArray(dados.notificacoes) ? dados.notificacoes : []
        setFila(atual => {
          const idsConhecidos = new Set([
            ...atual.map(item => item.id),
            ...idsEmExibicaoRef.current,
          ])
          const novos = itens.filter(item => item?.id && !idsConhecidos.has(item.id))
          novos.forEach(item => idsEmExibicaoRef.current.add(item.id))
          return novos.length ? [...atual, ...novos] : atual
        })
      } catch (erro) {
        if (!cancelado) console.warn('Não foi possível carregar notificações de conquistas.', erro)
      }
    }

    consultar()
    const intervalo = window.setInterval(consultar, 12000)
    return () => {
      cancelado = true
      window.clearInterval(intervalo)
    }
  }, [token])

  // Confirma a entrega só depois que o aviso entrou no estado renderizado.
  useEffect(() => {
    if (!notificacao?.id || !token) return undefined
    let cancelado = false
    const confirmar = async () => {
      try {
        await fetch(`${API_BASE}/api/conquistas/notificacoes/${encodeURIComponent(notificacao.id)}/confirmar`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
      } catch (erro) {
        if (!cancelado) console.warn('Não foi possível confirmar a exibição da notificação.', erro)
      }
    }
    confirmar()
    return () => { cancelado = true }
  }, [notificacao?.id, token])

  useEffect(() => {
    if (!notificacao) return undefined
    timerRef.current = window.setTimeout(() => {
      idsEmExibicaoRef.current.delete(notificacao.id)
      setFila(atual => atual.filter(item => item.id !== notificacao.id))
    }, 5000)
    return () => window.clearTimeout(timerRef.current)
  }, [notificacao])

  if (!notificacao) return null

  const fechar = () => {
    idsEmExibicaoRef.current.delete(notificacao.id)
    setFila(atual => atual.filter(item => item.id !== notificacao.id))
  }

  const abrirConquistas = () => {
    fechar()
    navigate('/perfil?aba=conquistas')
  }

  return (
    <aside className="notificacao-conquista" role="status" aria-live="polite">
      <button className="notificacao-conquista-fechar" type="button" aria-label="Fechar notificação" onClick={fechar}>×</button>
      <div className="notificacao-conquista-icone" aria-hidden="true">✦</div>
      <div className="notificacao-conquista-texto">
        <span className="notificacao-conquista-etiqueta">Conquista desbloqueada</span>
        <strong>{notificacao.nome}</strong>
        <p>{notificacao.descricao}</p>
        <button type="button" className="notificacao-conquista-link" onClick={abrirConquistas}>Ver conquistas <span aria-hidden="true">↗</span></button>
      </div>
      <span className="notificacao-conquista-xp">+{notificacao.xp} XP</span>
    </aside>
  )
}
