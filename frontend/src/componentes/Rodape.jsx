import { useState } from 'react'
import { createPortal } from 'react-dom'
import { NavLink, useLocation } from 'react-router-dom'
import { API_BASE } from '../contextos/AuthContext'

function Rodape() {
  const location = useLocation()
  const [aberto, setAberto] = useState(false)
  const [contatoAberto, setContatoAberto] = useState(false)
  const [emailCopiado, setEmailCopiado] = useState(false)
  const [tipo, setTipo] = useState('melhoria')
  const [pagina, setPagina] = useState(() => `${window.location.pathname}${window.location.search}`)
  const [descricao, setDescricao] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [mensagem, setMensagem] = useState('')

  const copiarEmailContato = async () => {
    const email = 'contato@desctrl.com.br'
    try {
      await navigator.clipboard.writeText(email)
      setEmailCopiado(true)
      window.setTimeout(() => setEmailCopiado(false), 1800)
    } catch {
      // Fallback para navegadores/contextos sem acesso à Clipboard API.
      const campo = document.createElement('textarea')
      campo.value = email
      campo.setAttribute('readonly', '')
      campo.style.position = 'fixed'
      campo.style.opacity = '0'
      document.body.appendChild(campo)
      campo.select()
      const copiou = document.execCommand('copy')
      document.body.removeChild(campo)
      setEmailCopiado(copiou)
      if (copiou) window.setTimeout(() => setEmailCopiado(false), 1800)
    }
  }

  const irParaTopo = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const abrirSugestao = () => {
    setPagina(`${location.pathname}${location.search}`)
    setDescricao('')
    setMensagem('')
    setAberto(true)
  }

  const enviarSugestao = async (evento) => {
    evento.preventDefault()
    if (enviando) return
    setEnviando(true)
    setMensagem('')
    try {
      const resposta = await fetch(`${API_BASE}/api/comunidade/sugestoes`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tipo, pagina_origem: pagina, descricao }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível enviar sua sugestão.')
      setMensagem(dados.mensagem || 'Sugestão enviada com sucesso!')
      setDescricao('')
    } catch (erro) { setMensagem(erro.message || 'Falha ao enviar sugestão.') }
    finally { setEnviando(false) }
  }

  return (
    <footer className="site-footer">
      <svg
        className="footer-circuitos"
        viewBox="0 0 1600 430"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <g className="circuito circuito-esquerdo">
          <path d="M0 76 H82 V48 H176 V78 H292 V48 H394" />
          <path d="M0 126 H48 V96 H122 V112 H206 V84 H318" />
          <path d="M0 282 H74 V318 H160 V294 H242 V330 H364" />
          <path d="M34 430 V352 H112 V326 H184" />
          <path d="M250 78 H286 V54 H344" />
          <path d="M250 94 H276 V112 H322" />
          <rect x="80" y="43" width="9" height="9" rx="1" />
          <rect x="171" y="73" width="9" height="9" rx="1" />
          <rect x="288" y="43" width="9" height="9" rx="1" />
          <rect x="204" y="107" width="7" height="7" rx="1" />
          <rect x="156" y="289" width="8" height="8" rx="1" />
          <rect x="355" y="325" width="8" height="8" rx="1" />
          <rect x="340" y="50" width="7" height="7" rx="1" />
          <rect x="319" y="109" width="7" height="7" rx="1" />
        </g>

        <g className="circuito circuito-direito">
          <path d="M1600 74 H1516 V44 H1434 V74 H1352 V48 H1270" />
          <path d="M1600 126 H1548 V98 H1482 V118 H1408 V88 H1324" />
          <path d="M1600 286 H1528 V322 H1442 V294 H1354 V332 H1240" />
          <path d="M1564 430 V356 H1490 V326 H1418" />
          <rect x="1511" y="39" width="9" height="9" rx="1" />
          <rect x="1429" y="69" width="9" height="9" rx="1" />
          <rect x="1350" y="43" width="9" height="9" rx="1" />
          <rect x="1405" y="113" width="7" height="7" rx="1" />
          <rect x="1438" y="290" width="8" height="8" rx="1" />
          <rect x="1236" y="328" width="8" height="8" rx="1" />
        </g>

        <g className="circuito-nos">
          <circle cx="344" cy="54" r="3" />
          <circle cx="322" cy="112" r="3" />
          <circle cx="1240" cy="332" r="3" />
          <circle cx="364" cy="330" r="3" />
        </g>
      </svg>

      <div className="footer-particulas" aria-hidden="true">
        <span></span><span></span><span></span><span></span><span></span><span></span>
        <span></span><span></span><span></span><span></span><span></span><span></span>
        <span></span><span></span><span></span><span></span><span></span><span></span>
      </div>

      <div className="footer-conteudo">
        <div className="footer-marca">
          <NavLink className="footer-logo" to="/" aria-label="DESCTRL" onClick={irParaTopo}>
            <span className="footer-logo-des">DES</span>
            <span className="footer-logo-ctrl">CTRL</span>
          </NavLink>

          <p className="footer-slogan">Você joga. A gente fica de olho.</p>

          <p className="footer-descricao">
            Encontre melhores preços, acompanhe ofertas e descubra novos jogos
            nas suas lojas favoritas.
          </p>
        </div>

        <div className="footer-coluna">
          <h3>Explorar</h3>
          <NavLink to="/" onClick={irParaTopo}>Início</NavLink>
          <NavLink to="/jogos" onClick={irParaTopo}>Jogos</NavLink>
          <NavLink to="/ofertas" onClick={irParaTopo}>Ofertas</NavLink>
        </div>

        <div className="footer-coluna">
          <h3>Sobre o projeto</h3>
          <NavLink to="/sobre" onClick={irParaTopo}>Sobre o DESCTRL</NavLink>
          <button
            type="button"
            className="footer-link-botao"
            onClick={abrirSugestao}
          >
            Enviar sugestão
          </button>
        </div>

        <div className="footer-coluna footer-lojas">
          <h3>Lojas monitoradas</h3>

          <a
            className="footer-loja footer-loja-steam"
            href="https://store.steampowered.com/"
            target="_blank"
            rel="noreferrer"
          >
            <span className="footer-loja-icone footer-loja-icone-steam" aria-hidden="true">
              <svg className="footer-loja-logo footer-loja-logo-steam" viewBox="0 0 24 24" fill="none">
                <circle cx="15.7" cy="7.1" r="4.2" stroke="currentColor" strokeWidth="1.8" />
                <circle cx="7.1" cy="16.7" r="3.1" stroke="currentColor" strokeWidth="1.8" />
                <circle cx="15.7" cy="7.1" r="1.5" stroke="currentColor" strokeWidth="1.5" />
                <path d="m9.8 15.1 3.3-2.2M9.3 18.4l3.5 1.4a4.2 4.2 0 0 0 5.4-2.6l1.1-3.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span>Steam</span>
          </a>

          <a
            className="footer-loja footer-loja-epic"
            href="https://store.epicgames.com/?lang=pt-BR"
            target="_blank"
            rel="noreferrer"
          >
            <span className="footer-loja-icone footer-loja-icone-epic" aria-hidden="true">
              <svg className="footer-loja-logo footer-loja-logo-epic" viewBox="0 0 24 24">
                <path d="M5 3.5h14v17H5z" fill="currentColor" />
                <path d="M8 7h8v2H10v2h5.5v2H10v2h6v2H8z" fill="var(--fundo-card, #ffffff)" />
              </svg>
            </span>
            <span>Epic Games Store</span>
          </a>
        </div>

        <div className="footer-coluna footer-coluna-contato">
          <h3>Contato</h3>
          <button
            type="button"
            className="footer-link-botao"
            onClick={() => setContatoAberto(true)}
          >
            Fale com a gente
          </button>
          <span className="footer-universidade-label">Projeto acadêmico</span>
          <a
            className="footer-universidade footer-universidade-assinatura"
            href="https://www.unip.br/"
            target="_blank"
            rel="noreferrer"
            aria-label="Universidade Paulista, Ciência da Computação"
          >
            <span className="footer-universidade-icone" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" focusable="false">
                <path d="m2 10 10-5 10 5-10 5-10-5Z" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                <path d="M6 12v5c3.5 2.7 8.5 2.7 12 0v-5M22 10v6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
            <span className="footer-universidade-textos">
              <span className="footer-universidade-nome">Universidade Paulista</span>
              <span className="footer-universidade-curso">Ciência da Computação</span>
            </span>
          </a>
        </div>
      </div>

      {contatoAberto && createPortal(
        <div
          className="footer-modal-overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) setContatoAberto(false)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') setContatoAberto(false)
          }}
        >
          <div
            className="footer-modal-contato"
            role="dialog"
            aria-modal="true"
            aria-labelledby="titulo-contato"
          >
            <button
              type="button"
              className="footer-modal-fechar"
              onClick={() => setContatoAberto(false)}
              aria-label="Fechar janela de contato"
            >
              ×
            </button>
            <h2 id="titulo-contato">Entre em contato</h2>
            <div className="footer-contato-email-linha">
              <span className="footer-email-contato">contato@desctrl.com.br</span>
              <button
                type="button"
                className="footer-copiar-email"
                onClick={copiarEmailContato}
                aria-label={emailCopiado ? 'E-mail copiado' : 'Copiar endereço de e-mail'}
                title={emailCopiado ? 'Copiado!' : 'Copiar e-mail'}
              >
                {emailCopiado ? (
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <path d="m5 12 4 4L19 6" />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <rect x="8" y="8" width="11" height="12" rx="2" />
                    <path d="M16 8V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h2" />
                  </svg>
                )}
              </button>
            </div>
            <span className={`footer-copiar-feedback${emailCopiado ? ' visivel' : ''}`} role="status">
              {emailCopiado ? 'E-mail copiado' : ''}
            </span>
          </div>
        </div>,
        document.body
      )}

      {aberto && (
        <div
          className="footer-sugestao-overlay"
          role="presentation"
          onClick={(e) => {
            if (e.target === e.currentTarget) setAberto(false)
          }}
        >
          <form
            className="footer-sugestao-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="titulo-sugestao"
            onSubmit={enviarSugestao}
          >
            <button
              type="button"
              className="footer-sugestao-fechar"
              onClick={() => setAberto(false)}
              aria-label="Fechar"
            >
              ×
            </button>
            <h2 id="titulo-sugestao">Enviar sugestão</h2>
            <p className="footer-sugestao-intro">Conte o que podemos melhorar no DESCTRL.</p>

            <label htmlFor="tipo-sugestao">Tipo</label>
            <select
              id="tipo-sugestao"
              className="footer-sugestao-campo"
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
            >
              <option value="melhoria">Melhoria em algo existente</option>
              <option value="funcionalidade">Nova funcionalidade</option>
              <option value="interface">Interface e usabilidade</option>
              <option value="outro">Outro</option>
            </select>

            <label htmlFor="pagina-sugestao">Página de origem (editável)</label>
            <input
              id="pagina-sugestao"
              className="footer-sugestao-campo"
              value={pagina}
              onChange={(e) => setPagina(e.target.value)}
              maxLength={500}
              required
            />

            <label htmlFor="descricao-sugestao">Sua sugestão</label>
            <textarea
              id="descricao-sugestao"
              className="footer-sugestao-campo footer-sugestao-descricao"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              minLength={5}
              maxLength={5000}
              required
              rows={5}
              placeholder="Descreva sua ideia..."
            />

            {mensagem && <p className="footer-sugestao-mensagem" role="status">{mensagem}</p>}

            <div className="footer-sugestao-acoes">
              <button
                type="button"
                className="footer-sugestao-botao footer-sugestao-botao-secundario"
                onClick={() => setAberto(false)}
              >
                Fechar
              </button>
              <button
                type="submit"
                className="footer-sugestao-botao footer-sugestao-botao-principal"
                disabled={enviando}
              >
                {enviando ? 'Enviando...' : 'Enviar sugestão'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="footer-base">
        <span>© 2026 DESCTRL. Todos os direitos reservados.</span>
        <span>FEITO POR JOGADORES • PARA JOGADORES</span>
      </div>
    </footer>
  )
}

export default Rodape
