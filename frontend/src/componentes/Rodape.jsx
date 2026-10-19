import { useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { API_BASE } from '../contextos/AuthContext'

function Rodape() {
  const location = useLocation()
  const [aberto, setAberto] = useState(false)
  const [tipo, setTipo] = useState('melhoria')
  const [pagina, setPagina] = useState(() => `${window.location.pathname}${window.location.search}`)
  const [descricao, setDescricao] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [mensagem, setMensagem] = useState('')

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
          <NavLink className="footer-logo" to="/" aria-label="DESCTRL">
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
          <NavLink to="/">Início</NavLink>
          <NavLink to="/jogos">Jogos</NavLink>
          <NavLink to="/ofertas">Ofertas</NavLink>
        </div>

        <div className="footer-coluna">
          <h3>Sobre</h3>
          <NavLink to="/sobre">Sobre o DESCTRL</NavLink>
        </div>

        <div className="footer-coluna">
          <h3>Participar</h3>
          <button type="button" onClick={abrirSugestao} style={{ background: 'none', border: 0, padding: 0, color: 'inherit', textAlign: 'left', cursor: 'pointer', font: 'inherit' }}>Enviar sugestão</button>
        </div>

        <div className="footer-coluna footer-lojas">
          <h3>Lojas monitoradas</h3>

          <a
            className="footer-loja"
            href="https://store.steampowered.com/"
            target="_blank"
            rel="noreferrer"
          >
            <span
              className="footer-loja-icone footer-loja-icone-steam"
              aria-hidden="true"
            >
              <span className="steam-no-principal">
                <span className="steam-nucleo"></span>
              </span>
              <span className="steam-no-secundario"></span>
              <span className="steam-ligacao"></span>
            </span>
            <span>Steam</span>
          </a>

          <a
            className="footer-loja"
            href="https://store.epicgames.com/?lang=pt-BR"
            target="_blank"
            rel="noreferrer"
          >
            <span
              className="footer-loja-icone footer-loja-icone-epic"
              aria-hidden="true"
            >
              <span className="epic-emblema">
                <span className="epic-titulo">EPIC</span>
                <span className="epic-subtitulo">GAMES</span>
                <span className="epic-ponta"></span>
              </span>
            </span>
            <span>Epic Games Store</span>
          </a>
        </div>
      </div>

      {aberto && (
        <div role="presentation" onClick={(e) => { if (e.target === e.currentTarget) setAberto(false) }} style={{ position: 'fixed', inset: 0, zIndex: 3000, background: 'rgba(0,0,0,.72)', display: 'grid', placeItems: 'center', padding: 16 }}>
          <form role="dialog" aria-modal="true" aria-labelledby="titulo-sugestao" onSubmit={enviarSugestao} style={{ width: 'min(100%, 520px)', maxHeight: '90vh', overflowY: 'auto', boxSizing: 'border-box', background: 'var(--fundo-card, #19191d)', color: 'var(--texto-principal, #f5f5f5)', border: '1px solid var(--borda, #38383e)', borderRadius: 16, padding: 24, boxShadow: '0 20px 70px #0008' }}>
            <button type="button" onClick={() => setAberto(false)} aria-label="Fechar" style={{ float: 'right', background: 'transparent', color: 'inherit', border: 0, fontSize: 22, cursor: 'pointer' }}>×</button>
            <h2 id="titulo-sugestao" style={{ marginTop: 0 }}>Enviar sugestão</h2>
            <p>Conte o que podemos melhorar no DESCTRL.</p>
            <label htmlFor="tipo-sugestao" style={{ display: 'block', margin: '14px 0 6px', fontWeight: 600 }}>Tipo</label>
            <select id="tipo-sugestao" value={tipo} onChange={(e) => setTipo(e.target.value)} style={{ width: '100%', padding: 12, borderRadius: 8, color: 'inherit', background: 'var(--fundo-input, #202024)', border: '1px solid var(--borda, #555)' }}>
              <option value="melhoria">Melhoria em algo existente</option><option value="funcionalidade">Nova funcionalidade</option><option value="interface">Interface e usabilidade</option><option value="outro">Outro</option>
            </select>
            <label htmlFor="pagina-sugestao" style={{ display: 'block', margin: '14px 0 6px', fontWeight: 600 }}>Página de origem (editável)</label>
            <input id="pagina-sugestao" value={pagina} onChange={(e) => setPagina(e.target.value)} maxLength={500} required style={{ width: '100%', boxSizing: 'border-box', padding: 12, borderRadius: 8, color: 'inherit', background: 'var(--fundo-input, #202024)', border: '1px solid var(--borda, #555)' }} />
            <label htmlFor="descricao-sugestao" style={{ display: 'block', margin: '14px 0 6px', fontWeight: 600 }}>Sua sugestão</label>
            <textarea id="descricao-sugestao" value={descricao} onChange={(e) => setDescricao(e.target.value)} minLength={5} maxLength={5000} required rows={5} placeholder="Descreva sua ideia..." style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', padding: 12, borderRadius: 8, color: 'inherit', background: 'var(--fundo-input, #202024)', border: '1px solid var(--borda, #555)' }} />
            {mensagem && <p role="status">{mensagem}</p>}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18 }}><button type="button" onClick={() => setAberto(false)} style={{ padding: '10px 14px', borderRadius: 8, cursor: 'pointer' }}>Fechar</button><button type="submit" disabled={enviando} style={{ padding: '10px 14px', borderRadius: 8, cursor: 'pointer' }}>{enviando ? 'Enviando...' : 'Enviar sugestão'}</button></div>
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
