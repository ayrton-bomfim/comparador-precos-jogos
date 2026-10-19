import { useEffect, useRef, useState } from 'react'
import './BotaoLoginGoogle.css'

const GOOGLE_SCRIPT = 'https://accounts.google.com/gsi/client'
let carregamentoScript

function carregarGoogleIdentity() {
  if (window.google?.accounts?.id) return Promise.resolve()
  if (!carregamentoScript) {
    carregamentoScript = new Promise((resolve, reject) => {
      const existente = document.querySelector(`script[src="${GOOGLE_SCRIPT}"]`)
      if (existente) {
        existente.addEventListener('load', resolve, { once: true })
        existente.addEventListener('error', reject, { once: true })
        return
      }
      const script = document.createElement('script')
      script.src = GOOGLE_SCRIPT
      script.async = true
      script.defer = true
      script.onload = resolve
      script.onerror = () => reject(new Error('Não foi possível carregar o serviço de login do Google.'))
      document.head.appendChild(script)
    }).catch((error) => {
      carregamentoScript = null
      throw error
    })
  }
  return carregamentoScript
}

function LogoGoogle() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true" focusable="false">
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </svg>
  )
}

export default function BotaoLoginGoogle({ onCredential, disabled = false }) {
  const containerRef = useRef(null)
  const callbackRef = useRef(onCredential)
  const [erro, setErro] = useState('')
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim()

  useEffect(() => { callbackRef.current = onCredential }, [onCredential])

  useEffect(() => {
    let ativo = true
    const container = containerRef.current
    if (!clientId || !container) return undefined

    let larguraRenderizada = 0
    let observador

    // O botão oficial precisa ter a mesma largura da camada visível para cobrir o clique.
    // O Google aceita de 200px a 400px.
    const renderizar = () => {
      if (!ativo || !window.google?.accounts?.id) return
      const largura = Math.round(Math.min(Math.max(container.clientWidth || 320, 200), 400))
      if (largura === larguraRenderizada) return
      larguraRenderizada = largura
      container.innerHTML = ''
      window.google.accounts.id.renderButton(container, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        text: 'continue_with',
        shape: 'rectangular',
        width: largura,
        logo_alignment: 'center',
        locale: 'pt_BR',
      })
    }

    carregarGoogleIdentity()
      .then(() => {
        if (!ativo || !window.google?.accounts?.id) return
        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (resposta) => {
            if (resposta?.credential) callbackRef.current?.(resposta.credential)
            else setErro('O Google não retornou uma credencial válida. Tente novamente.')
          },
        })
        renderizar()
        if (typeof ResizeObserver !== 'undefined') {
          observador = new ResizeObserver(renderizar)
          observador.observe(container)
        }
      })
      .catch(() => {
        if (ativo) setErro('Não foi possível carregar o botão do Google. Confira sua conexão e tente novamente.')
      })

    return () => {
      ativo = false
      observador?.disconnect()
    }
  }, [clientId])

  if (!clientId) {
    return <div className="google-login-indisponivel" role="status">Configure VITE_GOOGLE_CLIENT_ID para ativar o Google.</div>
  }

  return (
    <div className={`google-login-wrapper ${disabled ? 'google-login-desabilitado' : ''}`}>
      <div className="google-login-area">
        {/* Camada visível: imita o botão principal do formulário. */}
        <div className="google-login-visual" aria-hidden="true">
          <LogoGoogle />
          <span>Continuar com o Google</span>
        </div>
        {/* Camada clicável: botão oficial do Google, quase transparente, por cima. */}
        <div ref={containerRef} className="google-login-botao" aria-label="Continuar com o Google" />
        {disabled && <div className="google-login-bloqueio" aria-hidden="true" />}
      </div>
      {erro && <small className="google-login-erro" role="alert">{erro}</small>}
    </div>
  )
}
