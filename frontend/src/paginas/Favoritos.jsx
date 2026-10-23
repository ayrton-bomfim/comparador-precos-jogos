import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import { useAuth } from '../contextos/AuthContext'
import { API_URL } from '../servicos/api'
import { useTema } from '../contextos/TemaContext'
import './Favoritos.css'

const dinheiro = (valor) => valor == null ? 'Indisponível' : Number(valor) === 0 ? 'Grátis' : Number(valor).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })

// Padroniza acentos, caixa, pontuação e espaços para a busca funcionar de forma previsível.
const normalizarTextoBusca = (valor) => String(valor || '')
  .normalize('NFD')
  .replace(/[\u0300-\u036f]/g, '')
  .toLocaleLowerCase('pt-BR')
  .replace(/[\p{P}\p{S}]/gu, '')
  .replace(/\s+/g, ' ')
  .trim()

export default function Favoritos() {
  const { token, usuario, autenticado, carregando: authCarregando } = useAuth()
  const { tema } = useTema()
  const navigate = useNavigate()

  const voltarPagina = () => {
    const indiceHistorico = window.history.state?.idx
    if (Number.isInteger(indiceHistorico) && indiceHistorico > 0) {
      navigate(-1)
    } else {
      navigate('/')
    }
  }
  const [favoritos, setFavoritos] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const [busca, setBusca] = useState('')
  const [loja, setLoja] = useState('todas')
  const [filtroPrecoHistorico, setFiltroPrecoHistorico] = useState('todos')
  const [ordenacao, setOrdenacao] = useState('recentes')
  const [visualizacao, setVisualizacao] = useState('grade')
  const [filtrosAbertos, setFiltrosAbertos] = useState(false)
  const [pagina, setPagina] = useState(1)
  const itensPorPagina = 12
  const [removendo, setRemovendo] = useState(null)
  const [jogoParaRemover, setJogoParaRemover] = useState(null)
  const [alertasPreco, setAlertasPreco] = useState({})
  const [jogoConfigurandoAlerta, setJogoConfigurandoAlerta] = useState(null)
  const [rascunhoAlerta, setRascunhoAlerta] = useState(null)
  const [salvandoAlerta, setSalvandoAlerta] = useState(false)
  const [erroAlerta, setErroAlerta] = useState('')
  const requisicaoAtual = useRef(0)
  const favoritosCarregadosRef = useRef(false)

  const carregar = useCallback(async () => {
    const idRequisicao = ++requisicaoAtual.current
    const tokenDaRequisicao = token
    if (!tokenDaRequisicao) {
      setFavoritos([]); setErro(''); setCarregando(false)
      return
    }
    // Não desmonta visualmente a coleção durante uma atualização em segundo plano.
    if (!favoritosCarregadosRef.current) setCarregando(true)
    setErro('')
    try {
      const resposta = await fetch(`${API_URL}/api/favoritos`, {
        headers: { Authorization: `Bearer ${tokenDaRequisicao}` },
      })
      if (!resposta.ok) throw new Error(resposta.status === 401 ? 'Sua sessão expirou. Entre novamente.' : 'Não foi possível carregar seus favoritos.')
      const dados = await resposta.json()
      if (idRequisicao === requisicaoAtual.current) {
        setFavoritos(dados.favoritos || [])
        favoritosCarregadosRef.current = true
      }
    } catch (e) {
      if (idRequisicao === requisicaoAtual.current) setErro(e.message || 'Falha de conexão com a API.')
    } finally {
      if (idRequisicao === requisicaoAtual.current) setCarregando(false)
    }
  }, [token])

  const usuarioId = usuario?.id

  useEffect(() => {
    requisicaoAtual.current += 1
    // Limpa os dados apenas ao encerrar a sessão, não quando o JWT é renovado.
    if (!authCarregando && !autenticado) {
      setFavoritos([]); favoritosCarregadosRef.current = false; setErro(''); setRemovendo(null); setCarregando(false)
    } else if (!authCarregando && autenticado) {
      carregar()
    }
    return () => { requisicaoAtual.current += 1 }
  }, [authCarregando, autenticado, usuarioId, carregar])

  useEffect(() => {
    if (!token || !autenticado || authCarregando) {
      // Limpa alertas ao sair da sessão.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAlertasPreco({}); return
    }
    let ativo = true
    fetch(`${API_URL}/api/alertas-preco`, { headers: { Authorization: `Bearer ${token}` } })
      .then(async r => { if (!r.ok) throw new Error('Falha ao carregar alertas'); return r.json() })
      .then(d => { if (ativo) { const mapa = {}; for (const a of (d.alertas || [])) mapa[a.jogo_id] = a; setAlertasPreco(mapa) } })
      .catch(() => {})
    return () => { ativo = false }
  }, [token, autenticado, authCarregando])

  const abrirConfiguracaoAlerta = (jogo) => {
    const salvo = alertasPreco[jogo.id]
    const lojasDisponiveis = [...(jogo.steam_id ? ['steam'] : []), ...(jogo.epic_id && jogo.epic_id !== 'EXCLUSIVO_STEAM' ? ['epic'] : [])]
    setJogoConfigurandoAlerta(jogo)
    setRascunhoAlerta({ ativo: salvo?.ativo ?? true, lojas: salvo?.lojas?.length ? [...salvo.lojas] : lojasDisponiveis, condicao: salvo?.condicao || 'preco_alvo', preco_alvo: salvo?.preco_alvo != null ? Number(salvo.preco_alvo) : 29.90 })
    setErroAlerta('')
  }
  const alternarLojaAlerta = (lojaSelecionada) => setRascunhoAlerta(atual => {
    if (!atual) return atual
    return { ...atual, lojas: atual.lojas.includes(lojaSelecionada) ? atual.lojas.filter(l => l !== lojaSelecionada) : [...atual.lojas, lojaSelecionada] }
  })
  const salvarAlertaPreco = async () => {
    if (!jogoConfigurandoAlerta || !rascunhoAlerta || salvandoAlerta) return
    if (!rascunhoAlerta.lojas.length) { setErroAlerta('Selecione pelo menos uma loja.'); return }
    if (rascunhoAlerta.condicao === 'preco_alvo' && (!Number.isFinite(Number(rascunhoAlerta.preco_alvo)) || Number(rascunhoAlerta.preco_alvo) < 0)) { setErroAlerta('Informe um preço válido.'); return }
    setSalvandoAlerta(true); setErroAlerta('')
    try {
      const resposta = await fetch(`${API_URL}/api/alertas-preco/${jogoConfigurandoAlerta.id}`, { method: 'PUT', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ ativo: Boolean(rascunhoAlerta.ativo), lojas: rascunhoAlerta.lojas, condicao: rascunhoAlerta.condicao, preco_alvo: rascunhoAlerta.condicao === 'preco_alvo' ? Number(rascunhoAlerta.preco_alvo) : null }) })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível salvar o alerta.')
      setAlertasPreco(atual => ({ ...atual, [jogoConfigurandoAlerta.id]: dados.alerta }))
      setJogoConfigurandoAlerta(null); setRascunhoAlerta(null)
    } catch (e) { setErroAlerta(e.message || 'Falha ao salvar o alerta.') }
    finally { setSalvandoAlerta(false) }
  }

  const remover = (jogo) => {
    if (!jogo || removendo !== null) return
    setJogoParaRemover(jogo)
  }

  const confirmarRemocao = async () => {
    if (!jogoParaRemover || !token || removendo !== null) return
    const jogo = jogoParaRemover
    const tokenDaRequisicao = token
    setRemovendo(jogo.id)
    setErro('')
    try {
      const resposta = await fetch(`${API_URL}/api/favoritos/${jogo.id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${tokenDaRequisicao}` },
      })
      if (!resposta.ok) throw new Error('Não foi possível remover este jogo dos favoritos.')
      if (tokenDaRequisicao === token) {
        setFavoritos(atual => atual.filter(item => item.id !== jogo.id))
        setJogoParaRemover(null)
      }
    } catch (e) {
      if (tokenDaRequisicao === token) setErro(e.message)
    } finally {
      if (tokenDaRequisicao === token) setRemovendo(null)
    }
  }

  // Pré-calcula o texto pesquisável apenas quando a coleção muda.
  // Assim, a cada tecla não precisamos normalizar novamente todos os favoritos.
  const favoritosIndexados = useMemo(() => favoritos.map(jogo => ({
    jogo,
    textoBusca: normalizarTextoBusca(
      `${jogo.nome} ${jogo.desenvolvedor || ''} ${jogo.publicadora || ''}`
    ),
  })), [favoritos])

  const filtrados = useMemo(() => {
    const termoDigitado = normalizarTextoBusca(busca)
    // Mantém a coleção completa até haver pelo menos 3 caracteres úteis.
    const termoBusca = termoDigitado.length >= 3 ? termoDigitado : ''

    let lista = favoritosIndexados
      .filter(item => !termoBusca || item.textoBusca.includes(termoBusca))
      .map(item => item.jogo)

    if (loja === 'steam') lista = lista.filter(j => j.steam_id)
    if (loja === 'epic') lista = lista.filter(j => j.epic_id && j.epic_id !== 'EXCLUSIVO_STEAM')
    if (filtroPrecoHistorico === 'menor-preco-historico') {
      lista = lista.filter(j => j.no_menor_preco_historico_steam || j.no_menor_preco_historico_epic)
    }
    lista = [...lista]
    if (ordenacao === 'nome') lista.sort((a,b) => a.nome.localeCompare(b.nome, 'pt-BR'))
    if (ordenacao === 'menor-preco') lista.sort((a,b) => Math.min(a.preco_steam ?? Infinity, a.preco_epic ?? Infinity) - Math.min(b.preco_steam ?? Infinity, b.preco_epic ?? Infinity))
    if (ordenacao === 'maior-desconto') lista.sort((a,b) => Math.max(b.desconto_steam || 0,b.desconto_epic || 0) - Math.max(a.desconto_steam || 0,a.desconto_epic || 0))
    return lista
  }, [favoritosIndexados, busca, loja, filtroPrecoHistorico, ordenacao])

  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / itensPorPagina))
  const paginaAtual = Math.min(pagina, totalPaginas)
  const jogosDaPagina = filtrados.slice((paginaAtual - 1) * itensPorPagina, paginaAtual * itensPorPagina)
  const totalEmPromocao = favoritos.filter(j =>
    (j.preco_steam != null && Number(j.desconto_steam) > 0) ||
    (j.preco_epic != null && Number(j.desconto_epic) > 0)
  ).length
  const totalMenorPrecoHistorico = favoritos.filter(j =>
    j.no_menor_preco_historico_steam || j.no_menor_preco_historico_epic
  ).length

  useEffect(() => {
    // A página volta ao início sempre que os critérios da lista mudam.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPagina(1)
  }, [busca, loja, filtroPrecoHistorico, ordenacao])

  useEffect(() => {
    if (pagina > totalPaginas) {
      // Mantém a página dentro do intervalo após remoções/filtros.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPagina(totalPaginas)
    }
  }, [pagina, totalPaginas])

  const renderPaginacao = (local) => totalPaginas > 1 ? (
    <nav className={`favoritos-paginacao favoritos-paginacao-${local}`} aria-label={`Paginação ${local} dos favoritos`}>
      <span className="favoritos-paginacao-resumo">
        {`Mostrando ${(paginaAtual - 1) * itensPorPagina + 1}–${Math.min(paginaAtual * itensPorPagina, filtrados.length)} de ${filtrados.length}`}
      </span>
      <div className="favoritos-paginacao-controles">
        <button type="button" onClick={() => setPagina(p => Math.max(1, p - 1))} disabled={paginaAtual === 1} aria-label="Página anterior">‹ <span>Anterior</span></button>
        {Array.from({ length: totalPaginas }, (_, i) => i + 1).map(n => (
          <button key={n} type="button" className={paginaAtual === n ? 'ativo' : ''} onClick={() => setPagina(n)} aria-current={paginaAtual === n ? 'page' : undefined} aria-label={`Página ${n}`}>{n}</button>
        ))}
        <button type="button" onClick={() => setPagina(p => Math.min(totalPaginas, p + 1))} disabled={paginaAtual === totalPaginas} aria-label="Próxima página"><span>Próxima</span> ›</button>
      </div>
    </nav>
  ) : null

  if (authCarregando || carregando) return <div className={`app pagina-favoritos tema-${tema}`}><Cabecalho /><main className="favoritos-main"><div className="favoritos-carregando">Carregando sua coleção…</div></main></div>
  if (!autenticado) return <div className={`app pagina-favoritos tema-${tema}`}><Cabecalho /><main className="favoritos-main"><section className="favoritos-intro"><div className="favoritos-intro-texto"><span className="favoritos-eyebrow">SUA COLEÇÃO</span><h1>Jogos favoritos</h1><p>Entre na sua conta para guardar jogos e acompanhar os preços em um só lugar.</p></div><div className="favoritos-intro-acoes"><button type="button" className="favoritos-voltar" onClick={voltarPagina}><span className="favoritos-voltar-chevron" aria-hidden="true">‹</span> Voltar</button><button className="favoritos-botao-principal" onClick={() => navigate('/login')}>Entrar na conta</button></div></section></main></div>

  return <div className={`app pagina-favoritos tema-${tema}`}><Cabecalho /><main className="favoritos-main">
    <section className="favoritos-intro"><div className="favoritos-intro-texto"><span className="favoritos-eyebrow">SUA COLEÇÃO</span><h1>Jogos favoritos <span>{favoritos.length}</span></h1><p>Deixe seus jogos por aqui. As oportunidades a gente acompanha.</p></div><div className="favoritos-intro-acoes"><button type="button" className="favoritos-voltar" onClick={voltarPagina}><span className="favoritos-voltar-chevron" aria-hidden="true">‹</span> Voltar</button><Link className="favoritos-explorar" to="/jogos">＋ Explorar jogos</Link></div></section>
    <section className="favoritos-resumo" aria-label="Resumo da coleção">
      <article className="favoritos-resumo-card resumo-total">
        <span className="favoritos-resumo-icone" aria-hidden="true">♥</span>
        <div><strong>{favoritos.length}</strong><span>Jogos favoritos</span></div>
      </article>
      <article className="favoritos-resumo-card resumo-promocao">
        <span className="favoritos-resumo-icone" aria-hidden="true">%</span>
        <div><strong>{totalEmPromocao}</strong><span>Em promoção</span></div>
      </article>
      <article className="favoritos-resumo-card resumo-historico">
        <span className="favoritos-resumo-icone" aria-hidden="true">↘</span>
        <div><strong>{totalMenorPrecoHistorico}</strong><span>No menor preço histórico</span></div>
      </article>
    </section>
    <section className="favoritos-ferramentas" aria-label="Busca e filtros dos favoritos">
       <label className="favoritos-busca">
         <span aria-hidden="true">⌕</span>
         <input value={busca} onChange={e => setBusca(e.target.value)} placeholder="Digite 3 caracteres para buscar…" aria-label="Buscar nos favoritos" />
       </label>
       <div className="favoritos-atalho-filtros">
         <div className="favoritos-resumo-filtros-ativos" aria-live="polite">
           <div className="favoritos-resumo-filtros-titulo"><span aria-hidden="true">☷</span><strong>Filtros ativos</strong></div>
           <div className="favoritos-etiquetas-filtros">
             {loja !== 'todas' && <button type="button" className="favoritos-etiqueta-filtro" onClick={() => setLoja('todas')} title="Remover filtro de loja">{loja === 'steam' ? 'Steam' : 'Epic Games Store'} <span aria-hidden="true">×</span></button>}
             {filtroPrecoHistorico === 'menor-preco-historico' && <button type="button" className="favoritos-etiqueta-filtro" onClick={() => setFiltroPrecoHistorico('todos')} title="Remover filtro de preço">Menor preço histórico <span aria-hidden="true">×</span></button>}
             <span className="favoritos-etiqueta-ordenacao"><span aria-hidden="true">↕</span>{ordenacao === 'recentes' ? 'Adicionados recentemente' : ordenacao === 'nome' ? 'Nome: A a Z' : ordenacao === 'menor-preco' ? 'Menor preço disponível' : 'Maior desconto'}</span>
             {loja === 'todas' && filtroPrecoHistorico === 'todos' && <span className="favoritos-sem-restricao">Sem filtros adicionais</span>}
           </div>
           <p>{loja === 'steam' ? 'Exibindo favoritos disponíveis na Steam.' : loja === 'epic' ? 'Exibindo favoritos disponíveis na Epic Games Store.' : 'A busca considera seus jogos favoritos.'}{filtroPrecoHistorico === 'menor-preco-historico' ? ' Apenas jogos no menor preço histórico.' : ''}</p>
         </div>
         <button type="button" className="favoritos-botao-filtros" onClick={() => setFiltrosAbertos(true)} aria-haspopup="dialog" aria-expanded={filtrosAbertos}><span aria-hidden="true">⚙</span> Filtros e ordenação</button>
       </div>
       <div className="favoritos-controles-visualizacao" aria-label="Modo de visualização">
         <span>Visualização</span>
         <div className="favoritos-visualizacao">
           <button type="button" className={visualizacao === 'grade' ? 'ativo' : ''} onClick={() => setVisualizacao('grade')} aria-label="Visualização em grade" aria-pressed={visualizacao === 'grade'} title="Grade">▦</button>
           <button type="button" className={visualizacao === 'lista' ? 'ativo' : ''} onClick={() => setVisualizacao('lista')} aria-label="Visualização em lista" aria-pressed={visualizacao === 'lista'} title="Lista">☷</button>
         </div>
       </div>
     </section>

     {filtrosAbertos && (
       <div className="favoritos-camada-filtros" onMouseDown={evento => { if (evento.target === evento.currentTarget) setFiltrosAbertos(false) }}>
         <section className="favoritos-painel-filtros" role="dialog" aria-modal="true" aria-labelledby="favoritos-titulo-filtros">
           <header className="favoritos-topo-filtros">
             <div><span className="favoritos-eyebrow">PERSONALIZE SUA COLEÇÃO</span><h2 id="favoritos-titulo-filtros">Filtros e ordenação</h2><p>Escolha quais jogos deseja acompanhar e como organizá-los.</p></div>
             <button type="button" onClick={() => setFiltrosAbertos(false)} aria-label="Fechar filtros">×</button>
           </header>
           <div className="favoritos-conteudo-filtros">
             <fieldset className="favoritos-grupo-filtros">
               <legend>Filtrar por loja</legend>
               { [['todas', 'Todas as lojas'], ['steam', 'Steam'], ['epic', 'Epic Games Store']].map(([valor, texto]) => <button key={valor} type="button" className={loja === valor ? 'selecionado' : ''} aria-pressed={loja === valor} onClick={() => setLoja(valor)}>{texto}</button>)}
             </fieldset>
             <fieldset className="favoritos-grupo-filtros">
               <legend>Condição de preço</legend>
               { [['todos', 'Todos os favoritos'], ['menor-preco-historico', 'Menor preço histórico']].map(([valor, texto]) => <button key={valor} type="button" className={filtroPrecoHistorico === valor ? 'selecionado' : ''} aria-pressed={filtroPrecoHistorico === valor} onClick={() => setFiltroPrecoHistorico(valor)}>{texto}</button>)}
             </fieldset>
             <label className="favoritos-ordenacao-modal"><span>Ordenar por</span>
               <select aria-label="Ordenar favoritos" value={ordenacao} onChange={e => setOrdenacao(e.target.value)}>
                 <option value="recentes">Adicionados recentemente</option><option value="nome">Nome: A a Z</option><option value="menor-preco">Menor preço disponível</option><option value="maior-desconto">Maior desconto</option>
               </select>
             </label>
           </div>
           <footer className="favoritos-rodape-filtros">
             <button type="button" className="favoritos-limpar-filtros" onClick={() => { setLoja('todas'); setFiltroPrecoHistorico('todos'); setOrdenacao('recentes') }}>Restaurar padrão</button>
             <button type="button" className="favoritos-aplicar-filtros" onClick={() => setFiltrosAbertos(false)}>Ver resultados</button>
           </footer>
         </section>
       </div>
     )}

     {erro && <div className="favoritos-erro" role="alert">{erro} <button onClick={carregar}>Tentar novamente</button></div>}
    {favoritos.length === 0 && !erro ? <section className="favoritos-vazio"><div className="favoritos-vazio-icone">♡</div><h2>Sua coleção começa aqui</h2><p>Encontre um jogo de que goste e toque no coração para guardá-lo aqui. Depois fica fácil comparar os preços das lojas.</p><Link to="/jogos" className="favoritos-botao-principal">Explorar catálogo</Link></section> : filtrados.length === 0 && !erro ? <section className="favoritos-vazio compacto"><h2>Nenhum jogo encontrado</h2><p>Tente mudar a busca ou os filtros.</p><button onClick={() => {setBusca('');setLoja('todas');setFiltroPrecoHistorico('todos')}}>Limpar filtros</button></section> : <>{renderPaginacao('topo')}<section className={`favoritos-resultados ${visualizacao === 'lista' ? 'modo-lista' : 'modo-grade'}`}>
      {jogosDaPagina.map(j => <article className="favorito-card" key={j.id}><button className="favorito-remover" onClick={() => remover(j)} disabled={removendo !== null} aria-label={`Remover ${j.nome} dos favoritos`} title="Remover dos favoritos">{removendo === j.id ? '…' : '♥'}</button><Link className="favorito-imagem" to={`/jogos/${j.id}`}><img src={j.imagem || ''} alt={`Capa de ${j.nome}`} loading="lazy" onError={e => {e.currentTarget.style.visibility='hidden'}} /></Link><div className="favorito-info"><Link to={`/jogos/${j.id}`} className="favorito-nome">{j.nome}</Link><div className="favorito-identificacao"><p className="favorito-meta">{j.publicadora || j.desenvolvedor || 'Publicadora não informada'}</p>{(j.no_menor_preco_historico_steam || j.no_menor_preco_historico_epic) && <div className="favorito-menor-preco"><strong>Menor preço histórico</strong>{j.no_menor_preco_historico_steam && <span className="selo-menor-preco selo-steam">Steam</span>}{j.no_menor_preco_historico_epic && <span className="selo-menor-preco selo-epic">Epic</span>}</div>}</div><div className="favorito-precos"><div><span>Steam</span><strong>{j.steam_id ? dinheiro(j.preco_steam) : 'Indisponível'}</strong>{j.desconto_steam > 0 && <small>-{j.desconto_steam}%</small>}</div><div><span>Epic Games</span><strong>{j.epic_id && j.epic_id !== 'EXCLUSIVO_STEAM' ? dinheiro(j.preco_epic) : 'Indisponível'}</strong>{j.desconto_epic > 0 && <small>-{j.desconto_epic}%</small>}</div></div><div className="favorito-acoes">
          <button type="button" className={`favorito-acao-alerta ${alertasPreco[j.id]?.ativo ? "alerta-ativo" : ""}`} onClick={() => abrirConfiguracaoAlerta(j)} aria-label={`Configurar alerta de preço para ${j.nome}`} title="Configurar alerta de preço">
            <svg className="favorito-acao-icone" aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/><path d="M10 21h4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
            {alertasPreco[j.id]?.ativo ? "Alerta ativo" : "Alerta de preço"}
          </button>
          <Link className="favorito-acao-detalhes" to={`/jogos/${j.id}`} aria-label={`Ver detalhes de ${j.nome}`} title="Ver detalhes">
            <svg className="favorito-acao-icone" aria-hidden="true" viewBox="0 0 24 24" fill="none"><path d="M10.5 18a7.5 7.5 0 1 1 5.3-2.2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/><path d="m16 16 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
            Ver detalhes
          </Link>
          {j.url_steam && <a className="favorito-acao-loja favorito-acao-steam" href={j.url_steam} target="_blank" rel="noreferrer" aria-label={`Abrir ${j.nome} na Steam`} title="Abrir na Steam">
            <svg className="favorito-acao-icone favorito-acao-logo-steam" aria-hidden="true" viewBox="0 0 24 24" fill="none"><circle cx="15.7" cy="7.1" r="4.2" stroke="currentColor" strokeWidth="1.8"/><circle cx="7.1" cy="16.7" r="3.1" stroke="currentColor" strokeWidth="1.8"/><circle cx="15.7" cy="7.1" r="1.5" stroke="currentColor" strokeWidth="1.5"/><path d="m9.8 15.1 3.3-2.2M9.3 18.4l3.5 1.4a4.2 4.2 0 0 0 5.4-2.6l1.1-3.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Steam
          </a>}
          {j.url_epic && <a className="favorito-acao-loja favorito-acao-epic" href={j.url_epic} target="_blank" rel="noreferrer" aria-label={`Abrir ${j.nome} na Epic Games Store`} title="Abrir na Epic Games Store">
            <svg className="favorito-acao-icone favorito-acao-logo-epic" aria-hidden="true" viewBox="0 0 24 24"><path d="M5 3.5h14v17H5z" fill="currentColor"/><path d="M8 7h8v2H10v2h5.5v2H10v2h6v2H8z" fill="var(--fav-card)"/></svg>
            Epic
          </a>}
        </div></div></article>)}
    </section>{renderPaginacao('baixo')}</>}
    <p className="favoritos-contagem">Mostrando {filtrados.length} de {favoritos.length} {favoritos.length === 1 ? 'jogo salvo' : 'jogos salvos'}</p>
    {jogoConfigurandoAlerta && rascunhoAlerta && (
      <div className="favoritos-modal-overlay" role="presentation" onMouseDown={e => { if (e.target === e.currentTarget && !salvandoAlerta) { setJogoConfigurandoAlerta(null); setRascunhoAlerta(null); setErroAlerta('') } }}>
        <section className="favoritos-modal favoritos-modal-alerta" role="dialog" aria-modal="true" aria-labelledby="alerta-preco-titulo">
          <div className="favoritos-modal-icone favoritos-modal-alerta-icone" aria-hidden="true">🔔</div>
          <h2 id="alerta-preco-titulo">Alerta de preço</h2>
          <p className="alerta-preco-jogo"><strong>{jogoConfigurandoAlerta.nome}</strong></p>
          <label className="alerta-preco-ativacao"><input type="checkbox" checked={rascunhoAlerta.ativo} onChange={e => setRascunhoAlerta(a => ({ ...a, ativo: e.target.checked }))} /><span><strong>Manter alerta ativado</strong><small>Você pode pausar sem perder as configurações.</small></span></label>
          <div className="alerta-preco-grupo"><span className="alerta-preco-rotulo">Lojas monitoradas</span><div className="alerta-preco-lojas">
            {jogoConfigurandoAlerta.steam_id && <label className={rascunhoAlerta.lojas.includes('steam') ? 'selecionada' : ''}><input type="checkbox" checked={rascunhoAlerta.lojas.includes('steam')} onChange={() => alternarLojaAlerta('steam')} /> Steam</label>}
            {jogoConfigurandoAlerta.epic_id && jogoConfigurandoAlerta.epic_id !== 'EXCLUSIVO_STEAM' && <label className={rascunhoAlerta.lojas.includes('epic') ? 'selecionada' : ''}><input type="checkbox" checked={rascunhoAlerta.lojas.includes('epic')} onChange={() => alternarLojaAlerta('epic')} /> Epic Games</label>}
          </div></div>
          <div className="alerta-preco-grupo"><span className="alerta-preco-rotulo">Quando avisar?</span>
            <label className="alerta-preco-opcao"><input type="radio" name="condicao-alerta-preco" checked={rascunhoAlerta.condicao === 'promocao'} onChange={() => setRascunhoAlerta(a => ({ ...a, condicao: 'promocao' }))} /><span><strong>Quando entrar em promoção</strong><small>Avisa quando houver desconto em uma das lojas selecionadas.</small></span></label>
            <label className="alerta-preco-opcao"><input type="radio" name="condicao-alerta-preco" checked={rascunhoAlerta.condicao === 'preco_alvo'} onChange={() => setRascunhoAlerta(a => ({ ...a, condicao: 'preco_alvo' }))} /><span><strong>Quando atingir meu preço</strong><small>Avisa quando chegar ao valor definido ou ficar abaixo dele.</small></span></label>
          </div>
          {rascunhoAlerta.condicao === 'preco_alvo' && <div className="alerta-preco-grupo alerta-preco-valor"><label className="alerta-preco-rotulo" htmlFor="alerta-preco-alvo">Preço máximo desejado</label><div className="alerta-preco-valor-cabecalho"><strong>{Number(rascunhoAlerta.preco_alvo || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })}</strong><span>BRL</span></div><input id="alerta-preco-slider" aria-label="Ajustar preço máximo" type="range" min="0" max="500" step="1" value={Math.min(500, Number(rascunhoAlerta.preco_alvo) || 0)} onChange={e => setRascunhoAlerta(a => ({ ...a, preco_alvo: Number(e.target.value) }))} /><input id="alerta-preco-alvo" className="alerta-preco-campo-valor" type="number" min="0" max="10000" step="0.50" value={rascunhoAlerta.preco_alvo} onChange={e => setRascunhoAlerta(a => ({ ...a, preco_alvo: e.target.value === '' ? '' : Number(e.target.value) }))} /><small>Use o controle deslizante ou digite o valor exato.</small></div>}
          {erroAlerta && <p className="alerta-preco-erro" role="alert">{erroAlerta}</p>}
          <div className="favoritos-modal-acoes"><button type="button" className="favoritos-modal-cancelar" onClick={() => { setJogoConfigurandoAlerta(null); setRascunhoAlerta(null); setErroAlerta('') }} disabled={salvandoAlerta}>Cancelar</button><button type="button" className="favoritos-modal-confirmar favoritos-modal-alerta-salvar" onClick={salvarAlertaPreco} disabled={salvandoAlerta}>{salvandoAlerta ? 'Salvando…' : 'Salvar alerta'}</button></div>
        </section>
      </div>
    )}
    {jogoParaRemover && (
      <div className="favoritos-modal-overlay" role="presentation" onMouseDown={(evento) => {
        if (evento.target === evento.currentTarget && removendo === null) setJogoParaRemover(null)
      }}>
        <section className="favoritos-modal" role="dialog" aria-modal="true" aria-labelledby="favoritos-modal-titulo" aria-describedby="favoritos-modal-descricao">
          <div className="favoritos-modal-icone" aria-hidden="true">♥</div>
          <h2 id="favoritos-modal-titulo">Remover dos favoritos?</h2>
          <p id="favoritos-modal-descricao">Quer mesmo retirar <strong>{jogoParaRemover.nome}</strong> da sua coleção?</p>
          <div className="favoritos-modal-acoes">
            <button type="button" className="favoritos-modal-cancelar" onClick={() => setJogoParaRemover(null)} disabled={removendo !== null}>Cancelar</button>
            <button type="button" className="favoritos-modal-confirmar" onClick={confirmarRemocao} disabled={removendo !== null}>
              {removendo === jogoParaRemover.id ? 'Removendo…' : 'Sim, remover'}
            </button>
          </div>
        </section>
      </div>
    )}
  </main></div>
}
