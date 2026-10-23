import { useEffect, useState } from 'react'
import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import './App.css'
import './mobile-touch.css'

import Inicio from './paginas/Inicio'
import Jogos from './paginas/Jogos'
import DetalhesJogo from './paginas/DetalhesJogo'
import Ofertas from './paginas/Ofertas'
import Sobre from './paginas/Sobre'
import Arquitetura from './paginas/Arquitetura'
import Login from './paginas/Login'
import Cadastro from './paginas/Cadastro'
import Curadoria from './paginas/Curadoria'
import Perfil from './paginas/Perfil'
import Favoritos from './paginas/Favoritos'
import RecuperarSenha from './paginas/RecuperarSenha'
import RedefinirSenha from './paginas/RedefinirSenha'
import ConfirmarEmail from './paginas/ConfirmarEmail'

import { useAuth } from './contextos/AuthContext'
import { useTema } from './contextos/TemaContext'
import Rodape from './componentes/Rodape'
import NotificacoesConquistas from './componentes/NotificacoesConquistas'

function RedirecionarSessaoExpirada() {
  const {
    sessaoExpirada,
    limparAvisoSessaoExpirada,
    redirecionarInicioAposLogout,
    limparRedirecionamentoLogout,
  } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!redirecionarInicioAposLogout) return
    navigate('/', { replace: true })
    limparRedirecionamentoLogout()
  }, [redirecionarInicioAposLogout, limparRedirecionamentoLogout, navigate])

  useEffect(() => {
    if (!sessaoExpirada) return
    limparAvisoSessaoExpirada()
    navigate('/login', {
      replace: true,
      state: { mensagem: 'Sua sessão expirou. Entre novamente para continuar.' },
    })
  }, [sessaoExpirada, limparAvisoSessaoExpirada, navigate])

  return null
}

const REVISAO_AVISO_BETA = 'beta-aviso-3'
const CHAVE_AVISO_BETA = `desctrl:${REVISAO_AVISO_BETA}:dispensado-em`
const DURACAO_AVISO_BETA = 7 * 24 * 60 * 60 * 1000

function AvisoBeta() {
  const [aberto, setAberto] = useState(() => {
    try {
      const dispensadoEm = Number(
        localStorage.getItem(CHAVE_AVISO_BETA)
      )

      if (!Number.isFinite(dispensadoEm) || dispensadoEm <= 0) {
        return true
      }

      return Date.now() - dispensadoEm >= DURACAO_AVISO_BETA
    } catch {
      return true
    }
  })

  function continuar() {
    try {
      localStorage.setItem(CHAVE_AVISO_BETA, String(Date.now()))
    } catch {
      // Se o navegador bloquear o armazenamento, o aviso ainda pode ser fechado normalmente.
    }

    setAberto(false)
  }

  if (!aberto) return null

  return (
    <div className="aviso-beta-overlay" role="presentation">
      <section className="aviso-beta-modal" role="dialog" aria-modal="true" aria-labelledby="aviso-beta-titulo" aria-describedby="aviso-beta-introducao">
        <div className="aviso-beta-cabecalho">
          <span className="aviso-beta-selo"><span aria-hidden="true">●</span> BETA PÚBLICO</span>
          <span className="aviso-beta-simbolo" aria-hidden="true">!</span>
        </div>
        <h2 id="aviso-beta-titulo">Você está entrando no beta do DESCTRL!</h2>
        <p id="aviso-beta-introducao" className="aviso-beta-introducao">
          O DESCTRL é um projeto acadêmico e esta versão está em testes. Explore à vontade e nos ajude a encontrar o que ainda não está certo.
        </p>
        <div className="aviso-beta-conteudo">
          <h3>Inconsistências que podem ocorrer nesta versão</h3>
          <ul>
            <li><strong>Os dados ainda estão sendo refinados.</strong> Os preços podem ser diferentes dos da loja no momento da consulta, e um mesmo jogo pode aparecer em cards separados, um para cada plataforma.</li>
            <li><strong>As estimativas são experimentais.</strong> A data estimada da próxima promoção usa o histórico já coletado, mas a fórmula ainda está sendo ajustada e pode ser imprecisa.</li>
            <li><strong>Alguns recursos estão incompletos.</strong> Você pode ver suas conquistas, mas as recompensas ainda não podem ser aplicadas, porque as artes estão em produção. Também pode ocorrer lentidão e erros pontuais.</li>
          </ul>
          <div className="aviso-beta-atencao">
            <span className="aviso-beta-atencao-icone" aria-hidden="true">ⓘ</span>
            <p>Antes de comprar, confirme o preço, a edição do jogo e as condições da oferta diretamente na loja. O DESCTRL ajuda na comparação, mas não garante dados em tempo real nem que a oferta continue disponível.</p>
          </div>
          <p className="aviso-beta-feedback">Achou algo estranho? Use o feedback no rodapé de qualquer página ou a opção de reportar na página do jogo. Testar a fundo e avisar o que encontrar é a melhor ajuda que você pode dar.</p>
        </div>
        <div className="aviso-beta-rodape">
          <button className="aviso-beta-continuar" type="button" onClick={continuar}>
            Entendi, continuar <span aria-hidden="true"></span>
          </button>
        </div>
      </section>
    </div>
  )
}

const MODO_MANUTENCAO = false

function PaginaManutencao() {
  return (
    <main className="pagina-manutencao">
      <div className="manutencao-grade" aria-hidden="true" />
      <header className="manutencao-cabecalho">
        <a className="manutencao-marca" href="/" aria-label="DESCTRL">
          <span className="manutencao-marca-des">DES</span>
          <span className="manutencao-marca-ctrl">CTRL</span>
        </a>
        <span className="manutencao-status"><span className="manutencao-status-ponto" /><span>Em manutenção</span></span>
      </header>
      <section className="manutencao-conteudo" aria-labelledby="manutencao-titulo">
        <div className="manutencao-ilustracao" aria-hidden="true">
          <div className="manutencao-orbita manutencao-orbita-externa" />
          <div className="manutencao-orbita manutencao-orbita-interna" />
          <div className="manutencao-brilho" />
          <div className="manutencao-icone-robo">
            <div className="robo-antena" /><div className="robo-orelha robo-orelha-esquerda" /><div className="robo-orelha robo-orelha-direita" />
            <div className="robo-cabeca"><span className="robo-olho robo-olho-esquerdo" /><span className="robo-olho robo-olho-direito" /><span className="robo-sorriso" /></div>
            <div className="robo-corpo" /><div className="robo-pata robo-pata-esquerda" /><div className="robo-pata robo-pata-direita" /><div className="robo-cauda" />
          </div>
          <div className="manutencao-ferramenta manutencao-ferramenta-esquerda">⚙</div><div className="manutencao-ferramenta manutencao-ferramenta-direita">⌁</div>
          <span className="manutencao-particula part-1" /><span className="manutencao-particula part-2" /><span className="manutencao-particula part-3" /><span className="manutencao-particula part-4" />
        </div>
        <p className="manutencao-etiqueta">EM BREVE</p>
        <h1 id="manutencao-titulo">O DESCTRL chega<span>em breve!</span></h1>
        <p className="manutencao-descricao">Estamos finalizando os últimos ajustes para lançar o DESCTRL e ajudar você a encontrar os melhores preços de jogos.</p>
        <div className="manutencao-beneficios">
          <article className="manutencao-card"><span className="manutencao-card-icone roxo" aria-hidden="true">✦</span><h2>Novas funcionalidades</h2><p>Estamos preparando melhorias e novos recursos.</p></article>
          <article className="manutencao-card"><span className="manutencao-card-icone ciano" aria-hidden="true">▥</span><h2>Dados mais precisos</h2><p>Aprimorando a coleta e a qualidade das informações.</p></article>
          <article className="manutencao-card"><span className="manutencao-card-icone rosa" aria-hidden="true">◇</span><h2>Mais estabilidade</h2><p>Trabalhando para uma navegação mais confiável.</p></article>
          <article className="manutencao-card"><span className="manutencao-card-icone ciano" aria-hidden="true">⌘</span><h2>Feito para quem joga</h2><p>Para continuar ajudando você a encontrar bons preços.</p></article>
        </div>
        <div className="manutencao-agradecimento"><span aria-hidden="true">♥</span><div><strong>Obrigado pela paciência e pelo apoio!</strong><p>Voltaremos em breve.</p></div></div>
      </section>
      <footer className="manutencao-rodape"><span>DESCTRL</span></footer>
    </main>
  )
}

function App() {
  const { tema } = useTema()
  const location = useLocation()
  const mostrarAvisoBeta = location.pathname === '/'

  // Ao navegar para outra rota, começa sempre no topo da página.
  // Centralizado aqui para funcionar também nos links do rodapé e menus.
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
  }, [location.pathname])

  // Mantém o navegador e as áreas externas ao app alinhados ao tema ativo.
  useEffect(() => {
    const mediaEscuro = window.matchMedia('(prefers-color-scheme: dark)')

    const atualizarCores = () => {
      const escuro = tema === 'escuro' || (tema === 'sistema' && mediaEscuro.matches)
      const cor = escuro ? '#101014' : '#DCDCE5'

      let metaTema = document.querySelector('meta[name="theme-color"]')
      if (!metaTema) {
        metaTema = document.createElement('meta')
        metaTema.name = 'theme-color'
        document.head.appendChild(metaTema)
      }
      metaTema.setAttribute('content', cor)

      document.documentElement.style.backgroundColor = cor
      document.body.style.backgroundColor = cor
      document.documentElement.style.colorScheme = escuro ? 'dark' : 'light'
    }

    atualizarCores()
    mediaEscuro.addEventListener('change', atualizarCores)

    return () => mediaEscuro.removeEventListener('change', atualizarCores)
  }, [tema])

  if (MODO_MANUTENCAO) return <PaginaManutencao />

  return (
    <div className={`app tema-${tema}`}>
      <RedirecionarSessaoExpirada />
      <NotificacoesConquistas />
      {mostrarAvisoBeta && <AvisoBeta />}
      <Routes>
        <Route path="/" element={<Inicio />} />
        <Route path="/jogos" element={<Jogos />} />
        <Route path="/jogos/:id" element={<DetalhesJogo />} />
        <Route path="/ofertas" element={<Ofertas />} />
        <Route path="/sobre" element={<Sobre />} />
        <Route path="/arquitetura" element={<Arquitetura />} />
        <Route path="/login" element={<Login />} />
        <Route path="/cadastro" element={<Cadastro />} />
        <Route path="/recuperar-senha" element={<RecuperarSenha />} />
        <Route path="/redefinir-senha" element={<RedefinirSenha />} />
        <Route path="/confirmar-email" element={<ConfirmarEmail />} />
        <Route path="/admin/curadoria" element={<Curadoria />} />
        <Route path="/perfil" element={<Perfil />} />
        <Route path="/favoritos" element={<Favoritos />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Rodape />
    </div>
  )
}

export default App
