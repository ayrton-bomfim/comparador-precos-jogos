import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { useTema } from '../contextos/TemaContext'
import { API_BASE, useAuth } from '../contextos/AuthContext'
import './CabecalhoAuth.css'

function Cabecalho({ tema: temaProp, setTema: setTemaProp }) {
  const { usuario, isAdmin, autenticado, logout, token } = useAuth()
  const { tema: temaGlobal, setTema: setTemaGlobal } = useTema()
  const tema = temaProp ?? temaGlobal

  const atualizarTema = (proximoTema) => {
    setTemaProp?.(proximoTema)
    setTemaGlobal(proximoTema)
  }

  const [perfilAberto, setPerfilAberto] = useState(false)
  const [dadosConquistasMenu, setDadosConquistasMenu] = useState(null)
  const [erroConquistasMenu, setErroConquistasMenu] = useState(false)
  const [animacaoTema, setAnimacaoTema] = useState('')
  const perfilRef = useRef(null)
  const timeoutTemaRef = useRef(null)

  useEffect(() => {
    const fecharAoClicarFora = (event) => {
      if (perfilRef.current && !perfilRef.current.contains(event.target)) {
        setPerfilAberto(false)
      }
    }

    document.addEventListener('mousedown', fecharAoClicarFora)
    return () => document.removeEventListener('mousedown', fecharAoClicarFora)
  }, [])

  useEffect(() => {
    return () => {
      if (timeoutTemaRef.current) {
        clearTimeout(timeoutTemaRef.current)
      }
    }
  }, [])

  // O menu usa a mesma fonte de dados de nível e XP exibida na página de perfil.
  // A consulta ocorre quando o menu é aberto para refletir a evolução mais recente.
  useEffect(() => {
    if (!perfilAberto || !autenticado || !token) return undefined

    const controller = new AbortController()

    const carregarConquistasMenu = async () => {
      // Evita exibir dados de uma sessão anterior enquanto os dados atuais carregam.
      setDadosConquistasMenu(null)
      setErroConquistasMenu(false)

      try {
        const resposta = await fetch(`${API_BASE}/api/conquistas`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        })
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) {
          throw new Error(dados.detail || 'Não foi possível carregar o progresso do perfil.')
        }
        setDadosConquistasMenu(dados)
      } catch (erro) {
        if (erro.name !== 'AbortError') {
          console.warn('Não foi possível carregar o nível e o XP no menu do perfil.', erro)
          setErroConquistasMenu(true)
        }
      }
    }

    carregarConquistasMenu()
    return () => controller.abort()
  }, [perfilAberto, autenticado, token])

  const alternarTema = () => {
    const indoParaEscuro = tema !== 'escuro'
    const proximoTema = indoParaEscuro ? 'escuro' : 'claro'

    if (timeoutTemaRef.current) {
      clearTimeout(timeoutTemaRef.current)
    }

    setAnimacaoTema(
      indoParaEscuro ? 'animando-para-escuro' : 'animando-para-claro'
    )

    atualizarTema(proximoTema)

    timeoutTemaRef.current = setTimeout(() => {
      setAnimacaoTema('')
    }, 800)
  }

  const temaEscuro = tema === 'escuro'
  const nivelConquistasMenu = dadosConquistasMenu?.nivel || null
  const proximoNivelMenu = dadosConquistasMenu?.proximo_nivel || null
  const xpTotalMenu = Number(dadosConquistasMenu?.xp_total || 0)
  const xpMinimoNivelMenu = Number(nivelConquistasMenu?.xp_minimo || 0)
  const xpProximoNivelMenu = Number(proximoNivelMenu?.xp_necessario || 0)
  const progressoNivelMenu = dadosConquistasMenu
    ? proximoNivelMenu
      ? Math.max(0, Math.min(100, ((xpTotalMenu - xpMinimoNivelMenu) / Math.max(1, xpProximoNivelMenu - xpMinimoNivelMenu)) * 100))
      : 100
    : null

  return (
    <header className="cabecalho">
      <NavLink
        className="marca"
        to="/"
        aria-label="DESCTRL"
      >
        <span className="marca-particulas" aria-hidden="true">
          <i className="particula p1"></i>
          <i className="particula p2"></i>
          <i className="particula p3"></i>
          <i className="particula p4"></i>
          <i className="particula p5"></i>
          <i className="particula p6"></i>
          <i className="particula p7"></i>
          <i className="particula p8"></i>
          <i className="particula p9"></i>
          <i className="particula p10"></i>
          <i className="particula p11"></i>
          <i className="particula p12"></i>
          <i className="particula p13"></i>
          <i className="particula p14"></i>
        </span>

        <span className="marca-des">DES</span>

        <span className="marca-ctrl">
          <span className="marca-ctrl-frame" aria-hidden="true"></span>
          <span className="marca-ctrl-frame-inner" aria-hidden="true"></span>
          <span className="marca-ctrl-canto canto-superior-esquerdo" aria-hidden="true"></span>
          <span className="marca-ctrl-canto canto-superior-direito" aria-hidden="true"></span>
          <span className="marca-ctrl-canto canto-inferior-esquerdo" aria-hidden="true"></span>
          <span className="marca-ctrl-canto canto-inferior-direito" aria-hidden="true"></span>
          <span className="marca-ctrl-texto">CTRL</span>
          <span className="marca-ctrl-brilho" aria-hidden="true"></span>
        </span>
      </NavLink>

      <nav className="navegacao">
        <NavLink
          to="/"
          end
          className={({ isActive }) => (isActive ? 'ativo' : '')}
        >
          Início
        </NavLink>

        <NavLink
          to="/jogos"
          className={({ isActive }) => (isActive ? 'ativo' : '')}
        >
          Jogos
        </NavLink>

        <NavLink
          to="/ofertas"
          className={({ isActive }) => (isActive ? 'ativo' : '')}
        >
          Ofertas
        </NavLink>

        <NavLink
          to="/sobre"
          className={({ isActive }) => (isActive ? 'ativo' : '')}
        >
          Sobre
        </NavLink>

        {isAdmin && (
          <NavLink
            to="/admin/curadoria"
            className={({ isActive }) => (isActive ? 'ativo' : '')}
            title="Painel de curadoria"
          >
            Curadoria
          </NavLink>
        )}
      </nav>

      <div className="acoes-cabecalho">
        <button
          className={`botao-tema-animado ${temaEscuro ? 'escuro' : 'claro'} ${animacaoTema}`}
          type="button"
          onClick={alternarTema}
          title={temaEscuro ? 'Ativar modo claro' : 'Ativar modo escuro'}
          aria-label={temaEscuro ? 'Ativar modo claro' : 'Ativar modo escuro'}
          aria-pressed={temaEscuro}
        >
          <span className="tema-cenario">
            <span className="tema-estrelas">
              <i>✦</i>
              <i>✦</i>
              <i>·</i>
              <i>✦</i>
            </span>

            <span className="tema-nuvens">
              <i></i>
              <i></i>
              <i></i>
            </span>

            <span className="tema-astro"></span>
          </span>
        </button>

        <div className="perfil-menu" ref={perfilRef}>
          <button
            className="botao-perfil"
            type="button"
            onClick={() => setPerfilAberto((aberto) => !aberto)}
            aria-label="Abrir menu do perfil"
            aria-expanded={perfilAberto}
            aria-haspopup="menu"
            title="Perfil"
          >
            <span className="icone-perfil" aria-hidden="true">
              <span className="icone-perfil-cabeca"></span>
              <span className="icone-perfil-corpo"></span>
            </span>
          </button>

          {perfilAberto && (
            <div className={`dropdown-perfil desctrl-menu-novo ${autenticado ? 'desctrl-menu-autenticado' : 'desctrl-menu-visitante'}`} role="menu">
              {autenticado ? (
                <>
              <div className="desctrl-conta-topo">
                <span className="desctrl-avatar" aria-hidden="true">♙</span>
                <div className="desctrl-conta-info">
                  <strong>{usuario?.username || 'Visitante'}</strong>
                  <div className="desctrl-nivel">
                    <span>{nivelConquistasMenu?.titulo || (erroConquistasMenu ? 'Indisponível' : 'Carregando…')}</span>
                    {' '}Nível {nivelConquistasMenu?.numero ?? (erroConquistasMenu ? '—' : '…')}
                  </div>
                  <small>
                    {dadosConquistasMenu
                      ? `✧ ${xpTotalMenu} XP · Jornada iniciada`
                      : erroConquistasMenu
                        ? 'Não foi possível carregar seu progresso'
                        : 'Carregando sua jornada…'}
                  </small>
                </div>
              </div>
              <div className="desctrl-progresso">
                <div>
                  <span>
                    {dadosConquistasMenu
                      ? proximoNivelMenu ? 'Progresso para o próximo nível' : 'Nível máximo'
                      : erroConquistasMenu ? 'Progresso indisponível' : 'Carregando progresso…'}
                  </span>
                  <span>{progressoNivelMenu == null ? '—' : `${Math.round(progressoNivelMenu)}%`}</span>
                </div>
                <div className="desctrl-barra"><span style={{ width: `${progressoNivelMenu ?? 0}%` }} /></div>
              </div>
              <div className="desctrl-links">
                <NavLink to={autenticado ? '/perfil' : '/login'} role="menuitem" className="desctrl-link" onClick={() => setPerfilAberto(false)}>
                  <span className="desctrl-link-icone"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.6-3.5 3.1-5.5 7-5.5s6.4 2 7 5.5"/></svg></span>
                  <span className="desctrl-link-texto"><strong>Meu perfil</strong><small>Sua conta, coleção e conquistas</small></span><span className="desctrl-seta">›</span>
                </NavLink>
                <NavLink to="/perfil?aba=configuracoes" role="menuitem" className="desctrl-link" onClick={() => setPerfilAberto(false)}>
                  <span className="desctrl-link-icone"><svg viewBox="0 0 24 24" fill="none"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2.5"/><circle cx="15" cy="17" r="2.5"/></svg></span>
                  <span className="desctrl-link-texto"><strong>Configurações</strong><small>Conta, notificações e preferências</small></span><span className="desctrl-seta">›</span>
                </NavLink>
                <NavLink to={autenticado ? '/favoritos' : '/login'} role="menuitem" className="desctrl-link" onClick={() => setPerfilAberto(false)}>
                  <span className="desctrl-link-icone"><svg viewBox="0 0 24 24" fill="none"><path d="M20.8 8.8c0 5-8.8 10-8.8 10s-8.8-5-8.8-10A4.7 4.7 0 0 1 12 6.5a4.7 4.7 0 0 1 8.8 2.3Z"/></svg></span>
                  <span className="desctrl-link-texto"><strong>Jogos favoritos</strong><small>Seus jogos guardados</small></span><span className="desctrl-seta">›</span>
                </NavLink>
              </div>
              <button type="button" role="menuitem" className="desctrl-sair" onClick={() => { logout(); setPerfilAberto(false) }} aria-label="Sair da conta">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></svg>
                <span>Sair da conta</span>
              </button>
                </>
              ) : (
                <div className="desctrl-visitante-conteudo">
                  <div className="desctrl-visitante-apresentacao">
                    <span className="desctrl-visitante-simbolo" aria-hidden="true">
                      <svg viewBox="0 0 24 24" fill="none"><path d="M6.5 8.5h11a4 4 0 0 1 3.9 3.2l.8 4.2a2.6 2.6 0 0 1-4.4 2.3l-2.2-2.1H8.4l-2.2 2.1a2.6 2.6 0 0 1-4.4-2.3l.8-4.2a4 4 0 0 1 3.9-3.2Z"/><path d="M7.5 11.5v4M5.5 13.5h4M16.5 12.5h.01M18.5 15h.01"/></svg>
                    </span>
                    <h2>Seu universo. Suas escolhas.</h2>
                    <p>Crie seu espaço no DESCTRL e reúna tudo o que importa na sua jornada gamer.</p>
                  </div>

                  <div className="desctrl-visitante-beneficios">
                    <div className="desctrl-visitante-beneficio">
                      <span className="desctrl-visitante-icone" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M20.8 8.8c0 5-8.8 10-8.8 10s-8.8-5-8.8-10A4.7 4.7 0 0 1 12 6.5a4.7 4.7 0 0 1 8.8 2.3Z"/></svg></span>
                      <span><strong>Sua coleção pessoal</strong><small>Reúna os jogos que estão na sua mira.</small></span>
                    </div>
                    <div className="desctrl-visitante-beneficio">
                      <span className="desctrl-visitante-icone" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="8" r="3.5"/><path d="M5 20c.6-3.5 3.1-5.5 7-5.5s6.4 2 7 5.5"/></svg></span>
                      <span><strong>Seu espaço, suas preferências</strong><small>Tenha seu perfil e personalize sua experiência.</small></span>
                    </div>
                    <div className="desctrl-visitante-beneficio">
                      <span className="desctrl-visitante-icone" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/><path d="M19 4l1.5-1.5M5 4 3.5 2.5"/></svg></span>
                      <span><strong>No horizonte: alertas personalizados</strong><small>Recurso planejado para acompanhar os jogos do seu interesse.</small></span>
                    </div>
                  </div>

                  <NavLink to="/cadastro" role="menuitem" className="desctrl-visitante-criar" onClick={() => setPerfilAberto(false)}>Criar minha conta</NavLink>
                  <p className="desctrl-visitante-entrar">Já tem uma conta? <NavLink to="/login" role="menuitem" onClick={() => setPerfilAberto(false)}>Entrar</NavLink></p>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export default Cabecalho