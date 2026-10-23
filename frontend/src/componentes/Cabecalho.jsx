import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { API_JOGOS_URL } from '../servicos/api'
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
  const [menuMobileAberto, setMenuMobileAberto] = useState(false)
  const [dadosConquistasMenu, setDadosConquistasMenu] = useState(null)
  const [erroConquistasMenu, setErroConquistasMenu] = useState(false)
  const [animacaoTema, setAnimacaoTema] = useState('')
  const perfilRef = useRef(null)
  const timeoutTemaRef = useRef(null)
  const botaoMenuRef = useRef(null)
  const botaoFecharMenuRef = useRef(null)
  const painelMenuRef = useRef(null)
  const arrasteMenuRef = useRef(null)
  const arrastouMenuRef = useRef(false)
  const { pathname } = useLocation()
  const navigate = useNavigate()
  const [buscaAberta, setBuscaAberta] = useState(false)
  const [termoBusca, setTermoBusca] = useState('')
  const [jogosBusca, setJogosBusca] = useState([])
  const buscaRef = useRef(null)
  const botaoBuscaRef = useRef(null)

  // Garante que o menu feche ao mudar de página (inclusive pelo botão "voltar").
  useEffect(() => {
    setMenuMobileAberto(false)
    setBuscaAberta(false)
    setTermoBusca('')
  }, [pathname])

  useEffect(() => {
    if (!menuMobileAberto) return undefined

    const fecharComEscape = (event) => {
      if (event.key === 'Escape') setMenuMobileAberto(false)
    }

    // Se a janela crescer (ex.: girar o celular), o menu mobile deixa de existir.
    const larguraDesktop = window.matchMedia('(min-width: 621px)')
    const fecharSeDesktop = (event) => {
      if (event.matches) setMenuMobileAberto(false)
    }

    // Trava a rolagem da página de fundo enquanto o menu está aberto.
    const overflowAnterior = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // Foco inicial no botão de fechar (acessibilidade).
    botaoFecharMenuRef.current?.focus()

    document.addEventListener('keydown', fecharComEscape)
    larguraDesktop.addEventListener('change', fecharSeDesktop)

    return () => {
      document.removeEventListener('keydown', fecharComEscape)
      larguraDesktop.removeEventListener('change', fecharSeDesktop)
      document.body.style.overflow = overflowAnterior
      botaoMenuRef.current?.focus()
    }
  }, [menuMobileAberto])

  // Arrastar o menu para a direita fecha (gesto de toque). O mouse não participa.
  const iniciarArrasteMenu = (evento) => {
    if (evento.pointerType === 'mouse') return
    arrasteMenuRef.current = { x: evento.clientX, y: evento.clientY, dx: 0, ativo: false }
    arrastouMenuRef.current = false
  }

  const moverArrasteMenu = (evento) => {
    const arraste = arrasteMenuRef.current
    if (!arraste) return

    const dx = evento.clientX - arraste.x
    const dy = evento.clientY - arraste.y

    if (!arraste.ativo) {
      const horizontal = Math.abs(dx) > 10 && Math.abs(dx) > Math.abs(dy) * 1.5
      if (!horizontal || dx <= 0) return
      arraste.ativo = true
    }

    arraste.dx = Math.max(0, dx)
    const painel = painelMenuRef.current
    if (painel) {
      painel.style.transition = 'none'
      painel.style.transform = `translateX(${arraste.dx}px)`
    }
  }

  const finalizarArrasteMenu = () => {
    const arraste = arrasteMenuRef.current
    arrasteMenuRef.current = null
    const painel = painelMenuRef.current
    if (!arraste?.ativo || !painel) return

    arrastouMenuRef.current = true
    painel.style.transition = 'transform .2s ease'

    if (arraste.dx > 90) {
      painel.style.transform = 'translateX(100%)'
      setTimeout(() => setMenuMobileAberto(false), 180)
    } else {
      painel.style.transform = ''
    }
  }

  const bloquearCliqueAposArraste = (evento) => {
    if (!arrastouMenuRef.current) return
    evento.preventDefault()
    evento.stopPropagation()
    arrastouMenuRef.current = false
  }

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


  const sugestoesBusca = useMemo(() => {
    const termo = termoBusca.trim().toLocaleLowerCase('pt-BR')
    if (!termo) return []

    return [...jogosBusca]
      .filter((jogo) => jogo.nome.toLocaleLowerCase('pt-BR').includes(termo))
      .sort((a, b) => {
        const nomeA = a.nome.toLocaleLowerCase('pt-BR')
        const nomeB = b.nome.toLocaleLowerCase('pt-BR')
        const comecaA = nomeA.startsWith(termo)
        const comecaB = nomeB.startsWith(termo)
        if (comecaA !== comecaB) return comecaA ? -1 : 1
        return nomeA.localeCompare(nomeB, 'pt-BR')
      })
      .slice(0, 6)
  }, [termoBusca, jogosBusca])

  useEffect(() => {
    if (!buscaAberta) return undefined
    const foco = window.setTimeout(() => buscaRef.current?.focus(), 30)
    const fecharEscape = (evento) => {
      if (evento.key === 'Escape') {
        setBuscaAberta(false)
        setTermoBusca('')
      }
    }
    const fecharCliqueFora = (evento) => {
      if (!evento.target.closest('.cabecalho-busca') && !evento.target.closest('.botao-busca-cabecalho')) {
        setBuscaAberta(false)
      }
    }
    document.addEventListener('keydown', fecharEscape)
    document.addEventListener('pointerdown', fecharCliqueFora)
    return () => {
      window.clearTimeout(foco)
      document.removeEventListener('keydown', fecharEscape)
      document.removeEventListener('pointerdown', fecharCliqueFora)
    }
  }, [buscaAberta])

  useEffect(() => {
    const termo = termoBusca.trim()
    if (!buscaAberta || termo.length < 2) {
      setJogosBusca([])
      return undefined
    }

    const controller = new AbortController()
    const timeout = window.setTimeout(async () => {
      try {
        const resposta = await fetch(
          `${API_JOGOS_URL}/?pagina=1&por_pagina=20&busca=${encodeURIComponent(termo)}&ordenacao=nome`,
          { signal: controller.signal }
        )
        if (!resposta.ok) throw new Error('Não foi possível carregar os jogos para a pesquisa.')
        const dados = await resposta.json()
        const lista = Array.isArray(dados) ? dados : dados.jogos || []
        setJogosBusca(lista.map((jogo) => ({
          id: jogo.id,
          nome: jogo.nome,
          imagem: jogo.url_imagem_steam || jogo.url_imagem_epic ||
            (jogo.steam_id ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg` : ''),
        })))
      } catch (erro) {
        if (erro.name !== 'AbortError') {
          console.error('Erro ao carregar jogos para a pesquisa do cabeçalho:', erro)
          setJogosBusca([])
        }
      }
    }, 220)

    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [buscaAberta, termoBusca])

  const enviarBuscaCabecalho = (evento) => {
    evento.preventDefault()
    const termo = termoBusca.trim()
    setBuscaAberta(false)
    setTermoBusca('')
    navigate(termo ? `/jogos?busca=${encodeURIComponent(termo)}` : '/jogos')
  }

  const abrirJogoBuscaCabecalho = (id) => {
    setBuscaAberta(false)
    setTermoBusca('')
    navigate(`/jogos/${id}`)
  }

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
          ref={botaoBuscaRef}
          className={`botao-busca-cabecalho ${buscaAberta ? 'ativo' : ''}`}
          type="button"
          onClick={() => setBuscaAberta((aberta) => !aberta)}
          aria-label={buscaAberta ? 'Fechar pesquisa' : 'Pesquisar jogos'}
          aria-expanded={buscaAberta}
          aria-controls="painel-busca-cabecalho"
          title="Pesquisar jogos"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="10.8" cy="10.8" r="6.8" />
            <path d="m16 16 4.2 4.2" />
          </svg>
        </button>
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

        <button
          className="botao-menu-mobile"
          type="button"
          ref={botaoMenuRef}
          onClick={() => setMenuMobileAberto((aberto) => !aberto)}
          aria-label={menuMobileAberto ? 'Fechar menu de navegação' : 'Abrir menu de navegação'}
          aria-expanded={menuMobileAberto}
          aria-controls="menu-navegacao-mobile"
        >
          <span aria-hidden="true" className={menuMobileAberto ? 'menu-mobile-icone aberto' : 'menu-mobile-icone'}>
            <i></i><i></i><i></i>
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

      {buscaAberta && (
        <div
          className="cabecalho-busca-camada"
          aria-hidden="true"
          onClick={() => {
            setBuscaAberta(false)
            setTermoBusca('')
          }}
        />
      )}

      {buscaAberta && (
        <div id="painel-busca-cabecalho" className="cabecalho-busca">
          <form className="cabecalho-busca-formulario" onSubmit={enviarBuscaCabecalho} autoComplete="off">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="10.8" cy="10.8" r="6.8" />
              <path d="m16 16 4.2 4.2" />
            </svg>
            <input
              ref={buscaRef}
              type="search"
              value={termoBusca}
              onChange={(evento) => setTermoBusca(evento.target.value)}
              placeholder="Pesquisar jogos..."
              aria-label="Pesquisar jogos"
              aria-autocomplete="list"
              aria-controls="sugestoes-busca-cabecalho"
            />
            <button type="submit" aria-label="Ver resultados da pesquisa">
              <span>Buscar</span>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" /></svg>
            </button>
          </form>
          {termoBusca.trim().length >= 2 && (
            <div id="sugestoes-busca-cabecalho" className="cabecalho-busca-sugestoes">
              {sugestoesBusca.length ? sugestoesBusca.map((jogo) => (
                <button
                  key={jogo.id}
                  type="button"
                  className="cabecalho-busca-sugestao"
                  onClick={() => abrirJogoBuscaCabecalho(jogo.id)}
                >
                  {jogo.imagem
                    ? <img src={jogo.imagem} alt="" />
                    : <span className="cabecalho-busca-imagem-vazia"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4zM4 15l4-4 4 4 3-3 5 5" /></svg></span>}
                  <span>{jogo.nome}</span>
                  <svg className="cabecalho-busca-seta" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 18 6-6-6-6" /></svg>
                </button>
              )) : (
                <div className="cabecalho-busca-sem-resultados">
                  {termoBusca.trim().length < 2 ? 'Digite pelo menos 2 caracteres.' : 'Nenhum jogo encontrado.'}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {menuMobileAberto && (
        <div className="menu-mobile-camada" onClick={(event) => {
          if (event.target === event.currentTarget) setMenuMobileAberto(false)
        }}>
          <div
            id="menu-navegacao-mobile"
            className="menu-mobile-painel"
            role="dialog"
            aria-modal="true"
            aria-label="Navegação principal"
            ref={painelMenuRef}
            onPointerDown={iniciarArrasteMenu}
            onPointerMove={moverArrasteMenu}
            onPointerUp={finalizarArrasteMenu}
            onPointerCancel={finalizarArrasteMenu}
            onClickCapture={bloquearCliqueAposArraste}
          >
            <div className="menu-mobile-topo">
              <div className="menu-mobile-identidade">
                      <NavLink
        className="marca menu-mobile-marca"
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
              </div>
              <button type="button" className="menu-mobile-fechar" ref={botaoFecharMenuRef} onClick={() => setMenuMobileAberto(false)} aria-label="Fechar menu">×</button>
            </div>
            <nav className="menu-mobile-links" aria-label="Links do menu">
              <NavLink to="/" end onClick={() => setMenuMobileAberto(false)}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m3 10 9-7 9 7"/><path d="M5.5 9v12h5v-7h3v7h5V9"/></svg><span>Início</span>
              </NavLink>
              <NavLink to="/jogos" onClick={() => setMenuMobileAberto(false)}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 8h10a4 4 0 0 1 3.8 3l1 4a2.5 2.5 0 0 1-4.2 2.3L15 15H9l-2.6 2.3A2.5 2.5 0 0 1 2.2 15l1-4A4 4 0 0 1 7 8Z"/><path d="M7 10.5v4M5 12.5h4M16.5 11.5h.01M18.5 14h.01"/></svg><span>Jogos</span>
              </NavLink>
              <NavLink to="/ofertas" onClick={() => setMenuMobileAberto(false)}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.5 13 13 20.5 3.5 11V3.5H11Z"/><circle cx="7.5" cy="7.5" r="1"/></svg><span>Ofertas</span>
              </NavLink>
              <NavLink to="/sobre" onClick={() => setMenuMobileAberto(false)}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.6 2.6 0 1 1 4.4 1.9c-1.2 1-1.9 1.3-1.9 3M12 17.5h.01"/></svg><span>Sobre</span>
              </NavLink>
              {autenticado && (
                <>
                  <div className="menu-mobile-separador" aria-hidden="true"></div>
                  <NavLink to="/favoritos" onClick={() => setMenuMobileAberto(false)}>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20.8 8.8c0 5-8.8 10-8.8 10s-8.8-5-8.8-10A4.7 4.7 0 0 1 12 6.5a4.7 4.7 0 0 1 8.8 2.3Z"/></svg><span>Favoritos</span>
                  </NavLink>
                </>
              )}
              {isAdmin && (
                <>
                  <div className="menu-mobile-separador" aria-hidden="true"></div>
                  <NavLink to="/admin/curadoria" onClick={() => setMenuMobileAberto(false)}>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 10h18M7 15h4"/></svg><span>Curadoria</span><small>ADMIN</small>
                  </NavLink>
                </>
              )}
            </nav>
            <div className="menu-mobile-conta">
              <button
                type="button"
                className="menu-mobile-tema"
                role="switch"
                aria-checked={temaEscuro}
                onClick={alternarTema}
              >
                {temaEscuro ? (
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z"/></svg>
                ) : (
                  <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
                )}
                <span className="menu-mobile-tema-texto">Modo escuro</span>
                <span className="menu-mobile-tema-chave" aria-hidden="true"><i></i></span>
              </button>

              {autenticado ? (
                <div className="menu-mobile-cartao-usuario">
                  <NavLink to="/perfil" className="menu-mobile-resumo-usuario" onClick={() => setMenuMobileAberto(false)}>
                    <span className="menu-mobile-avatar" aria-hidden="true">♙</span>
                    <span className="menu-mobile-resumo-textos"><strong>{usuario?.username || 'Usuário'}</strong><small>Ver meu perfil</small></span>
                    <span className="menu-mobile-seta" aria-hidden="true">›</span>
                  </NavLink>
                  <button type="button" className="menu-mobile-sair" onClick={() => { setMenuMobileAberto(false); logout() }}>
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M10 17l5-5-5-5M15 12H3"/><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6"/></svg><span>Sair da conta</span>
                  </button>
                </div>
              ) : (
                <>
                  <NavLink className="menu-mobile-entrar" to="/login" onClick={() => setMenuMobileAberto(false)}>Entrar <span>›</span></NavLink>
                  <NavLink className="menu-mobile-cadastrar" to="/cadastro" onClick={() => setMenuMobileAberto(false)}>Criar conta <span>›</span></NavLink>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </header>
  )
}

export default Cabecalho