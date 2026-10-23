import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { API_BASE, useAuth } from '../contextos/AuthContext'
import BotaoLoginGoogle from '../componentes/BotaoLoginGoogle'
import './Cadastro.css'

const USERNAME_PATTERN = /^[A-Za-z0-9_.-]+$/

function validarUsernameLocal(valor) {
  if (!valor) return { tipo: '', mensagem: '' }
  if (valor.length < 3) return { tipo: 'erro', mensagem: 'Quase lá! Vamos dar mais um pouquinho de tamanho a esse nome?' }
  if (valor.length > 100) return { tipo: 'erro', mensagem: 'Gostamos de nomes criativos, mas esse ficou comprido demais!' }
  if (!USERNAME_PATTERN.test(valor)) return { tipo: 'erro', mensagem: 'Opa! Esse símbolo não é permitido por aqui.' }
  return { tipo: 'verificando', mensagem: 'Checando se esse nome já tem dono...' }
}

function validarEmailLocal(valor) {
  if (!valor.trim()) return { tipo: 'erro', mensagem: 'Ei, faltou informar seu e-mail!' }
  // Validação de formato para feedback imediato; o backend também valida.
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(valor.trim())) {
    return { tipo: 'erro', mensagem: 'Esse e-mail parece estar incompleto. Dá uma conferida?' }
  }
  return { tipo: 'valido', mensagem: '' }
}

function validarSenhaLocal(valor) {
  if (!valor) return { tipo: 'erro', mensagem: 'Ei, faltou criar sua senha!' }
  if (valor.length < 6) return { tipo: 'erro', mensagem: 'Sua senha ficou curtinha demais. Use pelo menos 6 caracteres.' }
  if (valor.length > 128) return { tipo: 'erro', mensagem: 'Sua senha ficou longa demais. Use até 128 caracteres.' }
  return { tipo: 'valido', mensagem: '' }
}

function Cadastro() {
  const navigate = useNavigate()
  const location = useLocation()
  const { loginGoogle, concluirCadastroGoogle } = useAuth()
  const [googleCredential, setGoogleCredential] = useState(location.state?.googleCredential || '')
  const [googleEmail, setGoogleEmail] = useState(location.state?.googleEmail || '')
  const googleCadastroAtivo = Boolean(googleCredential && googleEmail)
  const [entrandoGoogle, setEntrandoGoogle] = useState(false)
  const [username, setUsername] = useState('')
  const [usernameStatus, setUsernameStatus] = useState({ tipo: '', mensagem: '' })
  const [email, setEmail] = useState(location.state?.googleEmail || '')
  const [emailTocado, setEmailTocado] = useState(false)
  const [emailTentouEnviar, setEmailTentouEnviar] = useState(false)
  const [senha, setSenha] = useState('')
  const [mostrarSenha, setMostrarSenha] = useState(false)
  const [senhaTocada, setSenhaTocada] = useState(false)
  const [senhaTentouEnviar, setSenhaTentouEnviar] = useState(false)
  const [confirmarSenha, setConfirmarSenha] = useState('')
  const [mostrarConfirmacao, setMostrarConfirmacao] = useState(false)
  const [confirmacaoTocada, setConfirmacaoTocada] = useState(false)
  const [confirmacaoTentouEnviar, setConfirmacaoTentouEnviar] = useState(false)
  const [erro, setErro] = useState('')
  const [sucesso, setSucesso] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    const valor = username.trim()
    const local = validarUsernameLocal(valor)
    if (!valor || local.tipo === 'erro') return undefined
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const resposta = await fetch(`${API_BASE}/api/auth/username-disponivel?username=${encodeURIComponent(valor)}`, { signal: controller.signal })
        if (!resposta.ok) throw new Error('Falha na consulta')
        const dados = await resposta.json()
        setUsernameStatus({ tipo: dados.disponivel ? 'disponivel' : 'erro', mensagem: dados.disponivel ? 'Tudo certo! Esse nome pode ser seu.' : 'Boa escolha, mas esse nome já está em uso. Que tal variar um pouquinho?' })
      } catch (error) {
        if (error.name !== 'AbortError') setUsernameStatus({ tipo: 'aviso', mensagem: 'Estamos com dificuldade para consultar os nomes. Tente de novo daqui a pouco.' })
      }
    }, 450)
    return () => { clearTimeout(timer); controller.abort() }
  }, [username])

  async function handleGoogleCredential(credential) {
    setErro('')
    setSucesso('')
    setEntrandoGoogle(true)
    try {
      const resultado = await loginGoogle(credential)
      if (resultado?.cadastroPendente) {
        setGoogleCredential(credential)
        setGoogleEmail(resultado.email)
        setEmail(resultado.email)
        setSucesso('Conta Google validada. Agora escolha seu nome de usuário e crie uma senha para concluir o cadastro.')
        return
      }
      navigate('/', { replace: true })
    } catch (error) {
      setErro(error.message || 'Não foi possível criar ou acessar sua conta Google.')
    } finally {
      setEntrandoGoogle(false)
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setErro('')
    setSucesso('')
    setEmailTentouEnviar(true)
    setSenhaTentouEnviar(true)
    setConfirmacaoTentouEnviar(true)
    const nome = username.trim()
    const local = validarUsernameLocal(nome)
    if (!nome || local.tipo === 'erro') {
      setUsernameStatus(!nome ? { tipo: 'erro', mensagem: 'Ei, faltou escolher seu nome de usuário!' } : local)
      setErro(!nome ? 'Ei, faltou escolher seu nome de usuário!' : local.mensagem)
      return
    }
    const validacaoEmail = validarEmailLocal(email)
    if (validacaoEmail.tipo === 'erro') { setErro(validacaoEmail.mensagem); return }
    const validacaoSenha = validarSenhaLocal(senha)
    if (validacaoSenha.tipo === 'erro') { setErro(validacaoSenha.mensagem); return }
    if (!confirmarSenha) { setErro('Ei, faltou confirmar sua senha!'); return }
    if (usernameStatus.tipo !== 'disponivel') {
      setErro(usernameStatus.tipo === 'erro' ? usernameStatus.mensagem : 'Só um instante: precisamos confirmar se esse nome está livre.')
      return
    }
    if (senha !== confirmarSenha) { setErro('As senhas não estão iguais. Dá uma conferida!'); return }
    setEnviando(true)
    try {
      if (googleCadastroAtivo) {
        await concluirCadastroGoogle(googleCredential, {
          username: nome,
          senha,
          confirmarSenha,
        })
        navigate('/', { replace: true })
        return
      }

      const resposta = await fetch(`${API_BASE}/api/auth/cadastro`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: nome, email: email.trim(), senha, confirmar_senha: confirmarSenha }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não conseguimos criar sua conta agora. Tente novamente.')
      setSucesso(dados.mensagem || 'Conta criada! Enviamos um link de confirmação para seu e-mail.')
      setTimeout(() => navigate('/login', { state: { username: nome } }), 3500)
    } catch (error) {
      setErro(error.message || 'Não consegui falar com o servidor. Tente novamente em instantes.')
    } finally { setEnviando(false) }
  }

  return (
    <main className="pagina-cadastro">
      <section className="cadastro-card">
        <Link className="cadastro-marca" to="/">DES<span>CTRL</span></Link>
        <h1>{googleCadastroAtivo ? 'Finalize seu cadastro' : 'Criar conta'}</h1>
        <p>{googleCadastroAtivo
          ? 'Sua conta Google foi validada. Escolha o nome de usuário e a senha que deseja utilizar no DESCTRL.'
          : 'Crie sua conta para acompanhar os preços dos seus jogos favoritos.'}</p>
        <form onSubmit={handleSubmit} className="cadastro-form" noValidate>
          <label className="cadastro-campo-username">
            Nome de usuário
            <div className={`cadastro-username-wrap ${usernameStatus.tipo === 'erro' ? 'tem-erro' : ''} ${usernameStatus.tipo === 'disponivel' ? 'tem-sucesso' : ''}`}>
              <input type="text" value={username} onChange={(event) => { const valor = event.target.value; setUsername(valor); setUsernameStatus(validarUsernameLocal(valor.trim())); setErro('') }} autoComplete="username" maxLength={101} placeholder="Ex.: jogador_123" required aria-invalid={usernameStatus.tipo === 'erro'} aria-describedby="username-feedback" />
              {usernameStatus.tipo === 'disponivel' && <span className="username-indicador username-ok" aria-label="Nome disponível" title="Nome disponível">✓</span>}
              {usernameStatus.tipo === 'verificando' && <span className="username-indicador username-loading" aria-label="Verificando" title="Verificando">…</span>}
              {usernameStatus.tipo === 'erro' && <span className="username-indicador username-falha" aria-label="Nome indisponível" title="Nome indisponível">!</span>}
            </div>
            {usernameStatus.mensagem && <small id="username-feedback" className={`username-feedback username-${usernameStatus.tipo}`} role={usernameStatus.tipo === 'erro' ? 'alert' : 'status'}>{usernameStatus.mensagem}</small>}
          </label>
          <label>E-mail
            <input
              type="email"
              value={googleCadastroAtivo ? googleEmail : email}
              onChange={(event) => { if (!googleCadastroAtivo) setEmail(event.target.value); setErro('') }}
              onBlur={() => setEmailTocado(true)}
              autoComplete="email"
              maxLength={255}
              placeholder="voce@exemplo.com"
              required
              readOnly={googleCadastroAtivo}
              aria-invalid={!googleCadastroAtivo && (emailTocado || emailTentouEnviar) && validarEmailLocal(email).tipo === 'erro'}
              aria-describedby="email-feedback"
            />
            {!googleCadastroAtivo && (emailTentouEnviar || (emailTocado && email.trim())) && validarEmailLocal(email).tipo === 'erro' && <small id="email-feedback" className="campo-feedback campo-erro" role="alert">{validarEmailLocal(email).mensagem}</small>}
            <small>{googleCadastroAtivo
              ? 'Este endereço foi confirmado pelo Google e será usado na sua conta.'
              : 'Esse endereço poderá receber alertas de preços se você ativar as notificações por e-mail.'}</small>
          </label>
          <label>Senha
            <div className="cadastro-senha-wrap">
              <input type={mostrarSenha ? 'text' : 'password'} value={senha} onChange={(event) => { setSenha(event.target.value); setErro('') }} onBlur={() => setSenhaTocada(true)} autoComplete="new-password" minLength={6} maxLength={128} placeholder="Pelo menos 6 caracteres" required aria-invalid={(senhaTocada || senhaTentouEnviar) && validarSenhaLocal(senha).tipo === 'erro'} aria-describedby="senha-feedback" />
              <button type="button" className="cadastro-toggle-senha" onClick={() => setMostrarSenha((visivel) => !visivel)} aria-label={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'} aria-pressed={mostrarSenha} title={mostrarSenha ? 'Ocultar senha' : 'Mostrar senha'}>
                {mostrarSenha ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 5.2A10.7 10.7 0 0112 5c5 0 8.5 4.2 9.5 6.2a1.8 1.8 0 010 1.6 13 13 0 01-3.1 3.8M6.2 6.2a13 13 0 00-3.7 5 1.8 1.8 0 000 1.6A10.7 10.7 0 0012 19c1 0 2-.2 2.9-.5" /></svg> : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12z" /><circle cx="12" cy="12" r="2.7" /></svg>}
              </button>
            </div>
            {(senhaTentouEnviar || (senhaTocada && senha)) && validarSenhaLocal(senha).tipo === 'erro' && <small id="senha-feedback" className="campo-feedback campo-erro" role="alert">{validarSenhaLocal(senha).mensagem}</small>}
          </label>
          <label>Confirmar senha
            <div className="cadastro-senha-wrap">
              <input type={mostrarConfirmacao ? 'text' : 'password'} value={confirmarSenha} onChange={(event) => { setConfirmarSenha(event.target.value); setErro('') }} onBlur={() => setConfirmacaoTocada(true)} autoComplete="new-password" minLength={6} maxLength={128} required aria-invalid={(confirmacaoTocada || confirmacaoTentouEnviar) && Boolean(confirmarSenha) && senha !== confirmarSenha} aria-describedby="confirmar-senha-feedback" />
              <button type="button" className="cadastro-toggle-senha" onClick={() => setMostrarConfirmacao((visivel) => !visivel)} aria-label={mostrarConfirmacao ? 'Ocultar confirmação da senha' : 'Mostrar confirmação da senha'} aria-pressed={mostrarConfirmacao} title={mostrarConfirmacao ? 'Ocultar senha' : 'Mostrar senha'}>
                {mostrarConfirmacao ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18M10.6 10.6a2 2 0 002.8 2.8M9.9 5.2A10.7 10.7 0 0112 5c5 0 8.5 4.2 9.5 6.2a1.8 1.8 0 010 1.6 13 13 0 01-3.1 3.8M6.2 6.2a13 13 0 00-3.7 5 1.8 1.8 0 000 1.6A10.7 10.7 0 0012 19c1 0 2-.2 2.9-.5" /></svg> : <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 12s3.5-6.5 9.5-6.5 9.5 6.5 9.5 6.5-3.5 6.5-9.5 6.5S2.5 12 2.5 12z" /><circle cx="12" cy="12" r="2.7" /></svg>}
              </button>
            </div>
            {confirmacaoTentouEnviar && !confirmarSenha && <small id="confirmar-senha-feedback" className="campo-feedback campo-erro" role="alert">Ei, faltou confirmar sua senha!</small>}
            {(confirmacaoTocada || confirmacaoTentouEnviar) && Boolean(confirmarSenha) && senha !== confirmarSenha && <small id="confirmar-senha-feedback" className="campo-feedback campo-erro" role="alert">As senhas não estão iguais. Dá uma conferida!</small>}
          </label>
          {erro && <div className="cadastro-mensagem cadastro-erro" role="alert">{erro}</div>}
          {sucesso && <div className="cadastro-mensagem cadastro-sucesso" role="status">{sucesso}</div>}
          <button type="submit" disabled={enviando}>{enviando ? 'Preparando sua conta…' : googleCadastroAtivo ? 'Concluir cadastro' : 'Criar conta'}</button>
        </form>
        {googleCadastroAtivo && (
          <button
            type="button"
            className="cadastro-google"
            onClick={() => {
              setGoogleCredential('')
              setGoogleEmail('')
              setEmail('')
              setSucesso('')
              setErro('')
            }}
          >
            Usar outra conta Google ou cadastro tradicional
          </button>
        )}
        {!googleCadastroAtivo && (
          <>
            <div className="cadastro-ou"><span>ou</span></div>
            <BotaoLoginGoogle onCredential={handleGoogleCredential} disabled={enviando || entrandoGoogle} />
            {entrandoGoogle && <div className="cadastro-mensagem" role="status">Conectando à sua conta Google…</div>}
          </>
        )}
        <div className="cadastro-rodape">Já tem uma conta? <Link to="/login">Entrar</Link></div>
        <div className="cadastro-voltar-inicio"><Link to="/"><span className="cadastro-voltar-chevron" aria-hidden="true" />Voltar para a página inicial</Link></div>
      </section>
    </main>
  )
}

export default Cadastro
