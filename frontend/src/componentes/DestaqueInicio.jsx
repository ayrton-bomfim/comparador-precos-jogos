import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { API_JOGOS_URL } from '../servicos/api'
import './DestaqueInicio.css'

const INTERVALO_ROTACAO = 6000
const MAXIMO_DESTAQUES = 5
const MINIMO_BUSCA = 3

function formatarPreco(preco) {
  if (preco === null || preco === undefined || Number.isNaN(Number(preco))) return 'Indisponível'
  if (Number(preco) === 0) return 'Grátis'
  return `R$ ${Number(preco).toFixed(2).replace('.', ',')}`
}

function formatarNumero(valor) {
  return Number(valor || 0).toLocaleString('pt-BR')
}

function precoValido(preco) {
  return preco !== null && preco !== undefined && !Number.isNaN(Number(preco))
}

// Deixa no mesmo formato os jogos vindos da vitrine e da busca do catálogo.
function normalizarJogo(jogo) {
  return {
    id: jogo.id,
    nome: jogo.nome,
    imagem:
      jogo.imagem ||
      jogo.url_imagem_steam ||
      jogo.url_imagem_epic ||
      (jogo.steam_id ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg` : ''),
    precoSteam: jogo.preco_steam ?? jogo.preco_atual_steam ?? jogo.preco_base_steam ?? null,
    precoEpic: jogo.preco_epic ?? jogo.preco_atual_epic ?? jogo.preco_base_epic ?? null,
    descontoSteam: Number(jogo.desconto_steam || 0),
    descontoEpic: Number(jogo.desconto_epic || 0),
    promocaoFim: jogo.promocao_fim || null,
  }
}

function tempoRestante(fim) {
  if (!fim) return null
  const horas = (new Date(fim).getTime() - Date.now()) / 3_600_000
  if (!(horas > 0)) return null
  if (horas < 24) return 'Termina hoje'
  const dias = Math.ceil(horas / 24)
  return dias === 1 ? 'Termina amanhã' : `Termina em ${dias} dias`
}

function compararLojas(jogo) {
  const steam = precoValido(jogo.precoSteam) ? Number(jogo.precoSteam) : null
  const epic = precoValido(jogo.precoEpic) ? Number(jogo.precoEpic) : null
  if (steam === null || epic === null || steam === epic) {
    return { melhor: null, mensagem: null }
  }
  const melhor = steam < epic ? 'steam' : 'epic'
  const menor = Math.min(steam, epic)
  const maior = Math.max(steam, epic)
  const loja = melhor === 'steam' ? 'Steam' : 'Epic'
  const economia = maior > 0 ? Math.round(((maior - menor) / maior) * 100) : 0
  return {
    melhor,
    mensagem: menor === 0 ? `Grátis na ${loja}` : `${economia}% mais barato na ${loja}`,
  }
}

function LinhaLoja({ nome, classe, preco, desconto, melhor }) {
  return (
    <div className={`destaque-loja${melhor ? ' destaque-loja--melhor' : ''}`}>
      <span className={`plataforma ${classe}`}>{nome}</span>
      {desconto > 0 && <small>−{desconto}%</small>}
      <strong>{formatarPreco(preco)}</strong>
    </div>
  )
}

// Topo da página inicial: proposta do site, busca e uma comparação que nunca
// começa vazia (gira entre as ofertas da vitrine até o visitante escolher um jogo).
function DestaqueInicio({ ofertas = [], resumo = null, carregando = false }) {
  const navigate = useNavigate()
  const destaques = useMemo(
    () => ofertas.slice(0, MAXIMO_DESTAQUES).map(normalizarJogo),
    [ofertas]
  )
  const [indice, setIndice] = useState(0)
  const [pausado, setPausado] = useState(false)
  const [selecionado, setSelecionado] = useState(null)
  const [busca, setBusca] = useState('')
  const [resultado, setResultado] = useState({ termo: '', jogos: [] })
  const [buscaAberta, setBuscaAberta] = useState(false)

  const termo = busca.trim()
  const [carregandoJogo, setCarregandoJogo] = useState(false)
  const buscaValida = termo.length >= MINIMO_BUSCA
  const sugestoes = buscaValida && resultado.termo === termo ? resultado.jogos : []
  const buscando = buscaValida && resultado.termo !== termo

  // Mesma busca do cabeçalho: nomes que começam com o termo aparecem primeiro.
  useEffect(() => {
    if (termo.length < MINIMO_BUSCA) return undefined
    let ativo = true
    const espera = setTimeout(async () => {
      try {
        const resposta = await fetch(`${API_JOGOS_URL}/sugestoes?busca=${encodeURIComponent(termo)}`)
        if (!resposta.ok) throw new Error('Falha na busca')
        const lista = await resposta.json()
        if (ativo) setResultado({ termo, jogos: (Array.isArray(lista) ? lista : []).map(normalizarJogo) })
      } catch {
        if (ativo) setResultado({ termo, jogos: [] })
      }
    }, 300)
    return () => {
      ativo = false
      clearTimeout(espera)
    }
  }, [termo])

  const reduzirMovimento =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    if (selecionado || pausado || reduzirMovimento || destaques.length < 2) return undefined
    const relogio = setInterval(() => setIndice((atual) => (atual + 1) % destaques.length), INTERVALO_ROTACAO)
    return () => clearInterval(relogio)
  }, [selecionado, pausado, reduzirMovimento, destaques.length])

  const jogo = selecionado || destaques[indice % Math.max(destaques.length, 1)] || null
  const { melhor, mensagem } = jogo ? compararLojas(jogo) : { melhor: null, mensagem: null }
  const prazo = jogo && !selecionado ? tempoRestante(jogo.promocaoFim) : null
  const maiorDesconto = jogo ? Math.max(jogo.descontoSteam, jogo.descontoEpic) : 0

  // As sugestões não trazem preço; a listagem do catálogo traz o preço atual das duas lojas.
  const escolher = async (item) => {
    setBusca('')
    setBuscaAberta(false)
    if (item.precoSteam !== null || item.precoEpic !== null) {
      setSelecionado(item)
      return
    }
    setSelecionado(item)
    setCarregandoJogo(true)
    try {
      const resposta = await fetch(
        `${API_JOGOS_URL}/?pagina=1&por_pagina=20&busca=${encodeURIComponent(item.nome)}&ordenacao=nome`
      )
      const dados = resposta.ok ? await resposta.json() : []
      const lista = Array.isArray(dados) ? dados : dados.jogos || []
      const completo = lista.find((jogo) => jogo.id === item.id)
      if (completo) setSelecionado((atual) => (atual?.id === item.id ? normalizarJogo(completo) : atual))
    } catch (erro) {
      console.error('Erro ao carregar os preços do jogo:', erro)
    } finally {
      setCarregandoJogo(false)
    }
  }

  const enviarBusca = (evento) => {
    evento.preventDefault()
    if (sugestoes[0]) escolher(sugestoes[0])
    else if (termo) navigate(`/jogos?busca=${encodeURIComponent(termo)}`)
  }

  const atalhos = destaques.slice(0, 3)

  return (
    <section className="destaque-inicio" aria-labelledby="destaque-titulo">
      <div className="destaque-texto">
        <span className="destaque-eyebrow">Steam e Epic lado a lado</span>
        <h1 id="destaque-titulo">Pague menos no seu próximo jogo</h1>
        <p>Compare o preço nas duas lojas, acompanhe o histórico e descubra se vale esperar uma promoção.</p>

        <form className="destaque-busca" onSubmit={enviarBusca} autoComplete="off" role="search">
          <svg className="destaque-busca-icone" viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
          <input
            type="search"
            value={busca}
            onChange={(evento) => {
              setBusca(evento.target.value)
              setBuscaAberta(true)
            }}
            onFocus={() => setBuscaAberta(true)}
            onBlur={() => setTimeout(() => setBuscaAberta(false), 150)}
            onKeyDown={(evento) => evento.key === 'Escape' && setBuscaAberta(false)}
            placeholder="Busque um jogo..."
            aria-label="Pesquisar jogo para comparar preços"
            aria-controls="destaque-sugestoes"
            aria-expanded={buscaAberta && buscaValida}
          />
          <button type="submit">Comparar</button>

          {buscaAberta && buscaValida && (
            <div id="destaque-sugestoes" className="destaque-sugestoes" role="listbox">
              {buscando ? (
                <div className="destaque-sugestoes-vazio">Buscando...</div>
              ) : sugestoes.length > 0 ? (
                sugestoes.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="option"
                    aria-selected="false"
                    className="destaque-sugestao"
                    onMouseDown={(evento) => evento.preventDefault()}
                    onClick={() => escolher(item)}
                  >
                    {item.imagem ? <img src={item.imagem} alt="" loading="lazy" /> : <span className="destaque-sugestao-vazia" />}
                    <span>{item.nome}</span>
                  </button>
                ))
              ) : (
                <div className="destaque-sugestoes-vazio">Nenhum jogo encontrado.</div>
              )}
            </div>
          )}
        </form>

        {atalhos.length > 0 && (
          <p className="destaque-atalhos">
            <span>Experimente:</span>
            {atalhos.map((item) => (
              <button key={item.id} type="button" onClick={() => escolher(item)}>{item.nome}</button>
            ))}
          </p>
        )}

        <dl className="destaque-numeros">
          <div>
            <dt>Jogos no catálogo</dt>
            <dd>{resumo ? formatarNumero(resumo.jogos_catalogo) : '—'}</dd>
          </div>
          <div>
            <dt>Em promoção agora</dt>
            <dd>{resumo ? formatarNumero(resumo.jogos_em_promocao) : '—'}</dd>
          </div>
          <div>
            <dt>Lojas comparadas</dt>
            <dd>Steam e Epic</dd>
          </div>
        </dl>
      </div>

      <div
        className="destaque-cartao"
        onMouseEnter={() => setPausado(true)}
        onMouseLeave={() => setPausado(false)}
        onFocus={() => setPausado(true)}
        onBlur={() => setPausado(false)}
        aria-live={selecionado ? 'polite' : 'off'}
      >
        {jogo ? (
          <>
            <div className="destaque-cartao-topo">
              <span>{selecionado ? 'Sua comparação' : 'Oferta em destaque'}</span>
              {prazo && <span className="destaque-prazo">{prazo}</span>}
            </div>

            <div className="destaque-capa" key={jogo.id}>
              {jogo.imagem && <img src={jogo.imagem} alt="" />}
              {maiorDesconto > 0 && <span className="destaque-capa-desconto">−{maiorDesconto}%</span>}
            </div>

            <h2 className="destaque-nome">{jogo.nome}</h2>

            <div className="destaque-lojas">
              <LinhaLoja nome="Steam" classe="steam" preco={jogo.precoSteam} desconto={jogo.descontoSteam} melhor={melhor === 'steam'} />
              <LinhaLoja nome="Epic Games Store" classe="epic" preco={jogo.precoEpic} desconto={jogo.descontoEpic} melhor={melhor === 'epic'} />
            </div>

            <p className="destaque-veredito">
              {carregandoJogo ? 'Consultando os preços...' : mensagem || (precoValido(jogo.precoSteam) && precoValido(jogo.precoEpic)
                ? 'Mesmo preço nas duas lojas'
                : 'Disponível em apenas uma das lojas')}
            </p>

            <div className="destaque-acoes">
              <button type="button" className="destaque-acao-principal" onClick={() => navigate(`/jogos/${jogo.id}`)}>
                Ver detalhes
              </button>
              <button type="button" onClick={() => navigate(`/ofertas?jogo=${encodeURIComponent(jogo.id)}`)}>
                Previsão de preço
              </button>
            </div>

            {selecionado ? (
              <button type="button" className="destaque-voltar" onClick={() => setSelecionado(null)}>
                Voltar às ofertas em destaque
              </button>
            ) : destaques.length > 1 && (
              <div className="destaque-pontos" role="tablist" aria-label="Ofertas em destaque">
                {destaques.map((item, posicao) => (
                  <button
                    key={item.id}
                    type="button"
                    role="tab"
                    aria-selected={posicao === indice % destaques.length}
                    aria-label={`Mostrar ${item.nome}`}
                    onClick={() => setIndice(posicao)}
                  />
                ))}
              </div>
            )}
          </>
        ) : (
          <div className="destaque-cartao-carregando" aria-busy={carregando}>
            <span />
            <span />
            <span />
          </div>
        )}
      </div>
    </section>
  )
}

export default DestaqueInicio
