import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'

function Cabecalho({ tema, setTema }) {
  const [perfilAberto, setPerfilAberto] = useState(false)
  const perfilRef = useRef(null)

  useEffect(() => {
    const fecharAoClicarFora = (event) => {
      if (perfilRef.current && !perfilRef.current.contains(event.target)) {
        setPerfilAberto(false)
      }
    }

    document.addEventListener('mousedown', fecharAoClicarFora)
    return () => document.removeEventListener('mousedown', fecharAoClicarFora)
  }, [])

  const alternarTema = () => {
    setTema(tema === 'escuro' ? 'claro' : 'escuro')
  }

  const temaEscuro = tema === 'escuro'

  return (
    <header className="cabecalho">
      <NavLink className="marca" to="/">
        <span className="marca-icone">◆</span>
        <span>Comparador</span>
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
      </nav>

      <div className="acoes-cabecalho">
        <button
          className={`botao-tema-animado ${temaEscuro ? 'escuro' : 'claro'}`}
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
            <div className="dropdown-perfil" role="menu">
              <div className="dropdown-perfil-cabecalho">
                <strong>Minha conta</strong>
                <span>Área de usuário</span>
              </div>

              <button type="button" role="menuitem" className="item-perfil">
                <span>Perfil</span>
                <small>Em desenvolvimento</small>
              </button>
              <button type="button" role="menuitem" className="item-perfil">
                <span>Configurações</span>
                <small>Em desenvolvimento</small>
              </button>
              <button type="button" role="menuitem" className="item-perfil">
                <span>Notificações</span>
                <small>Em desenvolvimento</small>
              </button>
              <button type="button" role="menuitem" className="item-perfil">
                <span>Jogos favoritos</span>
                <small>Em desenvolvimento</small>
              </button>
              <button type="button" role="menuitem" className="item-perfil">
                <span>Histórico</span>
                <small>Em desenvolvimento</small>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export default Cabecalho