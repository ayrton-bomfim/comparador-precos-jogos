import { useNavigate } from 'react-router-dom'

function CardJogo({ jogo, mostrarDesconto = false }) {
  const navigate = useNavigate()

  const abrirDetalhes = () => {
    navigate(`/jogos/${jogo.id}`)
  }

  const converterPreco = (valor) => {
    if (valor === null || valor === undefined || valor === '—') return null
    if (typeof valor === 'number') return valor
    if (valor === 'Grátis') return 0

    return Number(
      String(valor)
        .replace('R$ ', '')
        .replace(/\./g, '')
        .replace(',', '.')
        .trim()
    )
  }

  const precoSteam = converterPreco(
    jogo.precoSteam ?? jogo.steam
  )

  const precoEpic = converterPreco(
    jogo.precoEpic ?? jogo.epic
  )

  const steamDisponivel = precoSteam !== null
  const epicDisponivel = precoEpic !== null

  const mesmoPreco =
    steamDisponivel &&
    epicDisponivel &&
    precoSteam === precoEpic

  const menorPreco =
    !steamDisponivel && epicDisponivel
      ? 'Epic Games'
      : steamDisponivel && !epicDisponivel
        ? 'Steam'
        : precoSteam < precoEpic
          ? 'Steam'
          : 'Epic Games'

  return (
    <article
      className="card-jogo card-jogo-clicavel"
      onClick={abrirDetalhes}
      role="link"
      tabIndex={0}
      onKeyDown={(evento) => {
        if (evento.key === 'Enter' || evento.key === ' ') {
          evento.preventDefault()
          abrirDetalhes()
        }
      }}
    >
      <div className="imagem-jogo">
        <img
          src={jogo.imagem}
          alt={`Capa de ${jogo.nome}`}
        />

        {mostrarDesconto && jogo.desconto > 0 && (
          <span className="selo-desconto">
            -{jogo.desconto}%
          </span>
        )}
      </div>

      <div className="conteudo-card">
        <h3>{jogo.nome}</h3>

        <div className="precos">
          <div>
            <span className="rotulo-plataforma steam">
              Steam
            </span>

            <strong>{jogo.steam}</strong>
          </div>

          <div>
            <span className="rotulo-plataforma epic">
              Epic Games
            </span>

            <strong className={jogo.epic === '—' ? 'preco-indisponivel' : ''}>
              {jogo.epic === '—' ? 'Não disponível' : jogo.epic}
            </strong>
          </div>
        </div>

        <span className="menor-preco">
          {!steamDisponivel && !epicDisponivel
            ? 'Preço indisponível'
            : jogo.steam === 'Grátis' && jogo.epic === 'Grátis'
              ? 'Grátis nas duas lojas'
              : !steamDisponivel
                ? 'Exclusivo Epic Games'
                : !epicDisponivel
                  ? 'Exclusivo Steam'
                  : mesmoPreco
                ? 'Mesmo preço nas lojas'
                : `Menor preço: ${menorPreco}`}
        </span>
      </div>
    </article>
  )
}

export default CardJogo