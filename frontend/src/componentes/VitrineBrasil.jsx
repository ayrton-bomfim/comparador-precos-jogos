import { useEffect, useRef, useState } from 'react'
import { NavLink } from 'react-router-dom'
import './VitrineBrasil.css'

const INTERVALO_ROTACAO = 7000
const MAXIMO_SELECAO = 5

function formatarPreco(preco) {
  if (preco === null || preco === undefined || Number.isNaN(Number(preco))) return null
  if (Number(preco) === 0) return 'Grátis'
  return `R$ ${Number(preco).toFixed(2).replace('.', ',')}`
}

function formatarNumero(valor) {
  return Number(valor || 0).toLocaleString('pt-BR')
}

// Menor preço entre as lojas, com o desconto da loja escolhida.
function melhorOferta(jogo) {
  const opcoes = [
    { loja: 'Steam', preco: jogo.preco_steam, desconto: jogo.desconto_steam },
    { loja: 'Epic', preco: jogo.preco_epic, desconto: jogo.desconto_epic },
  ].filter((opcao) => opcao.preco !== null && opcao.preco !== undefined)
  if (!opcoes.length) return null
  return opcoes.reduce((melhor, opcao) => (Number(opcao.preco) < Number(melhor.preco) ? opcao : melhor))
}

function Preco({ jogo, compacto = false }) {
  const oferta = melhorOferta(jogo)
  if (!oferta) return <span className="brasil-preco brasil-preco--vazio">Preço indisponível</span>
  return (
    <span className={`brasil-preco${compacto ? ' brasil-preco--compacto' : ''}`}>
      {oferta.desconto > 0 && <span className="brasil-desconto">−{oferta.desconto}%</span>}
      <strong>{formatarPreco(oferta.preco)}</strong>
      {!compacto && <small>na {oferta.loja}</small>}
    </span>
  )
}

// Gesto de deslizar no toque; o mouse usa a lista lateral e os indicadores.
function useDeslizar(aoDeslizar) {
  const inicio = useRef(null)
  const deslizou = useRef(false)
  return {
    onPointerDown: (evento) => {
      if (evento.pointerType === 'mouse') return
      inicio.current = { x: evento.clientX, y: evento.clientY }
      deslizou.current = false
    },
    onPointerUp: (evento) => {
      const ponto = inicio.current
      inicio.current = null
      if (!ponto || evento.pointerType === 'mouse') return
      const dx = evento.clientX - ponto.x
      if (Math.abs(dx) < 45 || Math.abs(dx) < Math.abs(evento.clientY - ponto.y) * 1.2) return
      deslizou.current = true
      aoDeslizar(dx < 0 ? 1 : -1)
    },
    onPointerCancel: () => { inicio.current = null },
    onClickCapture: (evento) => {
      if (!deslizou.current) return
      evento.preventDefault()
      deslizou.current = false
    },
  }
}

function VitrineBrasil({ selecao = [], panorama = null }) {
  // Seleção editorial da curadoria; sem ela, os jogos nacionais em promoção.
  const destaques = (selecao.length ? selecao : panorama?.em_promocao || []).slice(0, MAXIMO_SELECAO)
  const idsDestaque = new Set(destaques.map((jogo) => jogo.id))
  const promocoes = (panorama?.em_promocao || []).filter((jogo) => !idsDestaque.has(jogo.id)).slice(0, 4)
  const estudios = panorama?.estudios || []

  const [indice, setIndice] = useState(0)
  const [pausado, setPausado] = useState(false)
  const total = destaques.length
  const atual = total ? destaques[indice % total] : null

  const reduzirMovimento =
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    if (pausado || reduzirMovimento || total < 2) return undefined
    const relogio = setInterval(() => setIndice((valor) => (valor + 1) % total), INTERVALO_ROTACAO)
    return () => clearInterval(relogio)
  }, [pausado, reduzirMovimento, total])

  const gestos = useDeslizar((direcao) => setIndice((valor) => (valor + direcao + total) % total))

  return (
    <section className="brasil" aria-labelledby="brasil-titulo">
      <header className="brasil-cabecalho">
        <div>
          <span className="brasil-eyebrow">
            <span className="brasil-faixa" aria-hidden="true" />
            Destaques do desenvolvimento nacional
          </span>
          <h2 id="brasil-titulo">Brasil <span>em jogo</span></h2>
          <p>Histórias, ideias e mundos criados por estúdios brasileiros, com o melhor preço entre as lojas.</p>
        </div>

        {panorama && (
          <dl className="brasil-numeros">
            <div>
              <dd>{formatarNumero(panorama.jogos_catalogo)}</dd>
              <dt>jogos nacionais no catálogo</dt>
            </div>
            <div>
              <dd>{formatarNumero(panorama.estudios_total)}</dd>
              <dt>estúdios brasileiros</dt>
            </div>
            <div>
              <dd>{formatarNumero(panorama.jogos_em_promocao)}</dd>
              <dt>em promoção agora</dt>
            </div>
          </dl>
        )}
      </header>

      {atual ? (
        <div
          className="brasil-painel"
          onMouseEnter={() => setPausado(true)}
          onMouseLeave={() => setPausado(false)}
          onFocus={() => setPausado(true)}
          onBlur={() => setPausado(false)}
        >
          <NavLink
            to={`/jogos/${atual.id}`}
            className="brasil-principal"
            aria-label={`Conhecer ${atual.nome}`}
            {...gestos}
          >
            {atual.imagem && <img key={atual.id} src={atual.imagem} alt="" decoding="async" />}
            <span className="brasil-principal-conteudo">
              <span className="brasil-etiquetas">
                <span className="brasil-etiqueta brasil-etiqueta--destaque">Feito no Brasil</span>
                {atual.genero && <span className="brasil-etiqueta">{atual.genero}</span>}
                {atual.metacritic && <span className="brasil-etiqueta">Metacritic {atual.metacritic}</span>}
              </span>
              <strong className="brasil-principal-nome">{atual.nome}</strong>
              {atual.desenvolvedor && <span className="brasil-estudio">por {atual.desenvolvedor}</span>}
              <span className="brasil-principal-rodape">
                <Preco jogo={atual} />
                <span className="brasil-cta">Conhecer jogo</span>
              </span>
            </span>
          </NavLink>

          {total > 1 && (
            <ol className="brasil-lista" aria-label="Seleção nacional">
              {destaques.map((jogo, posicao) => {
                const ativo = posicao === indice % total
                return (
                  <li key={jogo.id}>
                    <button
                      type="button"
                      className={`brasil-item${ativo ? ' ativo' : ''}`}
                      aria-current={ativo ? 'true' : undefined}
                      onClick={() => setIndice(posicao)}
                    >
                      {jogo.imagem ? <img src={jogo.imagem} alt="" loading="lazy" /> : <span className="brasil-item-vazio" />}
                      <span className="brasil-item-texto">
                        <strong>{jogo.nome}</strong>
                        <span>{jogo.desenvolvedor || jogo.genero || 'Estúdio brasileiro'}</span>
                      </span>
                      <Preco jogo={jogo} compacto />
                      {ativo && !pausado && !reduzirMovimento && (
                        <span className="brasil-item-progresso" key={`${jogo.id}-${indice}`} aria-hidden="true" />
                      )}
                    </button>
                  </li>
                )
              })}
            </ol>
          )}
        </div>
      ) : (
        <div className="brasil-vazio">A seleção de jogos brasileiros estará disponível aqui em breve.</div>
      )}

      {promocoes.length > 0 && (
        <div className="brasil-bloco">
          <h3>Nacionais em promoção agora</h3>
          <div className="brasil-promocoes">
            {promocoes.map((jogo) => (
              <NavLink key={jogo.id} to={`/jogos/${jogo.id}`} className="brasil-promocao">
                <span className="brasil-promocao-capa">
                  {jogo.imagem && <img src={jogo.imagem} alt="" loading="lazy" />}
                </span>
                <strong>{jogo.nome}</strong>
                <Preco jogo={jogo} compacto />
              </NavLink>
            ))}
          </div>
        </div>
      )}

      <footer className="brasil-rodape">
        {estudios.length > 0 && (
          <div className="brasil-estudios">
            <span>Estúdios em destaque:</span>
            {estudios.slice(0, 6).map((estudio) => (
              <NavLink
                key={estudio.nome}
                to={`/jogos?filtro=brasileiros&busca=${encodeURIComponent(estudio.nome)}`}
              >
                {estudio.nome}
              </NavLink>
            ))}
          </div>
        )}
        <NavLink className="brasil-ver-todos" to="/jogos?filtro=brasileiros">
          Explorar {panorama ? `os ${formatarNumero(panorama.jogos_catalogo)} ` : ''}jogos brasileiros
          <span aria-hidden="true"> →</span>
        </NavLink>
      </footer>
    </section>
  )
}

export default VitrineBrasil
