import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import './Ofertas.css'
import { API_JOGOS_URL } from '../servicos/api'

const API = API_JOGOS_URL

function formatarPreco(valor) {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) {
    return '—'
  }

  if (Number(valor) === 0) {
    return 'Grátis'
  }

  return `R$ ${Number(valor).toFixed(2).replace('.', ',')}`
}

function imagemDoJogo(jogo) {
  return (
    jogo.url_imagem_steam ||
    jogo.url_imagem_epic ||
    (jogo.steam_id
      ? `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/header.jpg`
      : '')
  )
}

function diasEntre(a, b) {
  const inicio = new Date(a).getTime()
  const fim = new Date(b).getTime()
  return Math.max(0, (fim - inicio) / 86400000)
}

function analisarHistorico(historico) {
  const registros = [...historico]
    .filter((registro) => registro.data_coleta && registro.preco_atual !== null)
    .sort((a, b) => new Date(a.data_coleta) - new Date(b.data_coleta))

  if (registros.length === 0) {
    return {
      registros: [],
      promocoes: [],
      precoMinimo: null,
      precoMedio: null,
      maiorDesconto: 0,
      descontoMedio: 0,
      intervalos: [],
      intervaloMedio: null,
      diasDesdePromocao: null,
      tendencia: 'Dados insuficientes',
      nivel: 'insuficiente',
      faixaPreco: null,
      faixaDesconto: null,
      episodios: [],
      pontuacao: 0,
    }
  }

  const promocoes = registros.filter((registro) => Number(registro.desconto || 0) > 0)

  const precoMinimo = Math.min(...registros.map((registro) => Number(registro.preco_atual)))
  const precoMedio =
    registros.reduce((total, registro) => total + Number(registro.preco_atual), 0) /
    registros.length

  const maiorDesconto = promocoes.length
    ? Math.max(...promocoes.map((registro) => Number(registro.desconto || 0)))
    : 0

  const descontoMedio = promocoes.length
    ? promocoes.reduce((total, registro) => total + Number(registro.desconto || 0), 0) /
      promocoes.length
    : 0

  const episodios = []

  for (const registro of promocoes) {
    const ultimo = episodios[episodios.length - 1]

    if (
      !ultimo ||
      diasEntre(ultimo[ultimo.length - 1].data_coleta, registro.data_coleta) > 14
    ) {
      episodios.push([registro])
    } else {
      ultimo.push(registro)
    }
  }

  const intervalos = []

  for (let i = 1; i < episodios.length; i += 1) {
    intervalos.push(
      diasEntre(episodios[i - 1][0].data_coleta, episodios[i][0].data_coleta)
    )
  }

  const intervaloMedio = intervalos.length
    ? intervalos.reduce((total, valor) => total + valor, 0) / intervalos.length
    : null

  const ultimaPromocao = promocoes.length
    ? promocoes[promocoes.length - 1].data_coleta
    : null

  const diasDesdePromocao = ultimaPromocao
    ? diasEntre(ultimaPromocao, new Date())
    : null

  let pontuacao = 0

  if (promocoes.length >= 2) pontuacao += 20
  if (promocoes.length >= 4) pontuacao += 10

  if (intervaloMedio !== null && diasDesdePromocao !== null) {
    const razao = diasDesdePromocao / Math.max(intervaloMedio, 1)

    if (razao >= 1.15) pontuacao += 35
    else if (razao >= 0.75) pontuacao += 20
    else if (razao >= 0.45) pontuacao += 10
  }

  const ultimoPreco = Number(registros[registros.length - 1].preco_atual)

  if (ultimoPreco > precoMinimo * 1.4) pontuacao += 20
  else if (ultimoPreco > precoMinimo * 1.15) pontuacao += 10

  if (descontoMedio >= 50) pontuacao += 15
  else if (descontoMedio >= 30) pontuacao += 8

  let tendencia = 'Baixa'
  let nivel = 'baixa'

  if (registros.length < 3 || promocoes.length < 2) {
    tendencia = 'Dados insuficientes'
    nivel = 'insuficiente'
  } else if (pontuacao >= 65) {
    tendencia = 'Alta'
    nivel = 'alta'
  } else if (pontuacao >= 35) {
    tendencia = 'Média'
    nivel = 'media'
  }

  const descontoInferior = Math.max(0, Math.round(descontoMedio * 0.8))
  const descontoSuperior = Math.min(
    100,
    Math.round(Math.max(maiorDesconto, descontoMedio * 1.15))
  )

  const precosPromocao = promocoes
    .map((registro) => Number(registro.preco_atual))
    .filter(Number.isFinite)
    .sort((a, b) => a - b)

  const percentil = (valores, proporcao) => {
    if (!valores.length) return null

    const indice = (valores.length - 1) * proporcao
    const inferior = Math.floor(indice)
    const superior = Math.ceil(indice)

    if (inferior === superior) return valores[inferior]

    return (
      valores[inferior] +
      (valores[superior] - valores[inferior]) * (indice - inferior)
    )
  }

  const precoInferior = percentil(precosPromocao, 0.25)
  const precoSuperior = percentil(precosPromocao, 0.75)

  return {
    registros,
    promocoes,
    precoMinimo,
    precoMedio,
    maiorDesconto,
    descontoMedio,
    intervalos,
    intervaloMedio,
    diasDesdePromocao,
    tendencia,
    nivel,
    faixaPreco:
      precoInferior !== null && precoSuperior !== null
        ? [precoInferior, precoSuperior]
        : null,
    faixaDesconto:
      descontoSuperior > 0
        ? [descontoInferior, descontoSuperior]
        : null,
    episodios,
    pontuacao,
  }
}

function obterResumoPromocoesPorPlataforma(historico) {
  return ['Steam', 'Epic'].map((plataforma) => {
    const registros = historico.filter(
      (registro) => registro.plataforma === plataforma
    )

    const analise = analisarHistorico(registros)

    return {
      plataforma,
      disponivel: registros.length > 0,
      promocoesRegistradas: analise.episodios.length,
      maiorDesconto: analise.maiorDesconto,
    }
  })
}

function calcularComportamentoDesenvolvedora(jogo, jogos, historicos) {
  const nome = (jogo?.desenvolvedor || '').trim().toLowerCase()

  if (!nome) {
    return {
      nome: 'Desenvolvedora não informada',
      jogosAnalisados: 0,
      promocoes: 0,
      descontoMedio: 0,
      intervaloMedio: null,
      nivel: 'Dados insuficientes',
    }
  }

  const jogosDoDesenvolvedor = jogos.filter(
    (item) => (item.desenvolvedor || '').trim().toLowerCase() === nome
  )

  const analises = jogosDoDesenvolvedor
    .map((item) => analisarHistorico(historicos[item.id] || []))
    .filter((analise) => analise.registros.length > 0)

  const descontos = analises.filter((analise) => analise.promocoes.length > 0)

  const intervalos = analises
    .map((analise) => analise.intervaloMedio)
    .filter((valor) => valor !== null)

  const descontoMedio = descontos.length
    ? descontos.reduce((total, analise) => total + analise.descontoMedio, 0) /
      descontos.length
    : 0

  const intervaloMedio = intervalos.length
    ? intervalos.reduce((total, valor) => total + valor, 0) / intervalos.length
    : null

  let nivel = 'Baixa'

  if (descontos.length >= 3 && descontoMedio >= 40) nivel = 'Alta'
  else if (descontos.length >= 2 || descontoMedio >= 25) nivel = 'Média'

  return {
    nome: jogo.desenvolvedor,
    jogosAnalisados: analises.length,
    promocoes: descontos.length,
    descontoMedio,
    intervaloMedio,
    nivel,
  }
}


function formatarDataGrafico(data) {
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(data))
}

function formatarMesGrafico(data) {
  return new Intl.DateTimeFormat('pt-BR', {
    month: 'short',
    year: '2-digit',
  })
    .format(new Date(data))
    .replace('.', '')
}

function obterHistoricoPorPlataforma(historico, plataforma) {
  return historico
    .filter((registro) => {
      if (plataforma === 'ambas') {
        return registro.plataforma === 'Steam' || registro.plataforma === 'Epic'
      }

      return registro.plataforma === plataforma
    })
    .filter(
      (registro) =>
        registro.data_coleta && Number.isFinite(Number(registro.preco_atual))
    )
    .sort(
      (a, b) =>
        new Date(a.data_coleta).getTime() -
        new Date(b.data_coleta).getTime()
    )
}

function obterDiasPeriodoGrafico(periodo) {
  const periodos = {
    '30d': 30,
    '3m': 90,
    '6m': 180,
    '1a': 365,
    tudo: null,
  }

  return periodos[periodo]
}

function filtrarHistoricoPorPeriodo(historico, periodo) {
  if (historico.length === 0) {
    return historico
  }

  const dias = obterDiasPeriodoGrafico(periodo)

  if (dias === null) {
    return historico
  }

  const maiorData = Math.max(
    ...historico.map((registro) => new Date(registro.data_coleta).getTime())
  )

  const dataInicial = maiorData - dias * 86400000

  const registroAnterior = [...historico]
    .reverse()
    .find(
      (registro) =>
        new Date(registro.data_coleta).getTime() < dataInicial
    )

  const dadosPeriodo = historico.filter(
    (registro) =>
      new Date(registro.data_coleta).getTime() >= dataInicial
  )

  if (registroAnterior && dadosPeriodo.length > 0) {
    dadosPeriodo.unshift({
      ...registroAnterior,
      id: `ancora-ofertas-${registroAnterior.id}-${periodo}`,
      data_coleta: new Date(dataInicial).toISOString(),
      _ancoraPeriodo: true,
    })
  }

  return dadosPeriodo
}

function GraficoHistoricoOfertas({ historico, plataforma, onPlataformaChange }) {
  const [pontoSelecionado, setPontoSelecionado] = useState(null)
  const [agoraAtual] = useState(() => Date.now())
  const [previsaoSelecionada, setPrevisaoSelecionada] = useState(false)
  const [periodo, setPeriodo] = useState('1a')

  const plataformasDisponiveis = useMemo(
    () =>
      new Set(
        historico
          .map((registro) => registro.plataforma)
          .filter((nome) => nome === 'Steam' || nome === 'Epic')
      ),
    [historico]
  )

  const plataformaAtiva =
    plataforma !== 'ambas' && !plataformasDisponiveis.has(plataforma)
      ? 'ambas'
      : plataforma

  const dadosPlataforma = useMemo(
    () => obterHistoricoPorPlataforma(historico, plataformaAtiva),
    [historico, plataformaAtiva]
  )

  const dados = useMemo(
    () => filtrarHistoricoPorPeriodo(dadosPlataforma, periodo),
    [dadosPlataforma, periodo]
  )

  const analiseGrafico = useMemo(
    () => analisarHistorico(dados),
    [dados]
  )

  const grafico = useMemo(() => {
    if (dados.length < 2) return null

    const largura = 1000
    const altura = 440
    const margem = {
      topo: 28,
      direita: 30,
      baixo: 58,
      esquerda: 78,
    }

    const areaLargura = largura - margem.esquerda - margem.direita
    const areaAltura = altura - margem.topo - margem.baixo

    const historicoInicio = new Date(dados[0].data_coleta).getTime()
    const historicoFim = new Date(dados[dados.length - 1].data_coleta).getTime()
    const agora = agoraAtual

    const intervaloMedio = analiseGrafico.intervaloMedio
    const diasDesdePromocao = analiseGrafico.diasDesdePromocao
    const restante =
      intervaloMedio !== null && diasDesdePromocao !== null
        ? intervaloMedio - diasDesdePromocao
        : null

    let previsaoInicio = null
    let previsaoFim = null
    let previsaoData = null

    if (
      intervaloMedio !== null &&
      analiseGrafico.faixaPreco &&
      analiseGrafico.faixaDesconto
    ) {
      const baseDias = Math.max(restante ?? 0, 0)
      const janelaMinima = Math.max(1, Math.round(baseDias * 0.5))
      const janelaMaxima = Math.max(
        janelaMinima + 7,
        Math.round(baseDias * 1.25)
      )

      if (restante !== null && restante <= 0) {
        previsaoInicio = agora
        previsaoFim = agora + Math.max(7, Math.round(intervaloMedio * 0.25)) * 86400000
      } else {
        previsaoInicio = agora + janelaMinima * 86400000
        previsaoFim = agora + janelaMaxima * 86400000
      }

      previsaoData = previsaoInicio + (previsaoFim - previsaoInicio) / 2
    }

    const limiteFim = Math.max(
      historicoFim,
      previsaoFim || historicoFim,
      agora
    )

    const inicio = Math.min(historicoInicio, agora)
    const fim = limiteFim === inicio ? inicio + 86400000 : limiteFim

    const todosPrecos = dados.map((registro) => Number(registro.preco_atual))
    const precosPrevisao = analiseGrafico.faixaPreco || []
    const valores = [...todosPrecos, ...precosPrevisao].filter(Number.isFinite)

    let minimo = Math.min(...valores)
    let maximo = Math.max(...valores)

    if (minimo === maximo) {
      minimo = Math.max(0, minimo - Math.max(minimo * 0.15, 10))
      maximo += Math.max(maximo * 0.15, 10)
    } else {
      const folga = (maximo - minimo) * 0.12
      minimo = Math.max(0, minimo - folga)
      maximo += folga
    }

    const calcularX = (data) =>
      margem.esquerda +
      ((new Date(data).getTime() - inicio) / (fim - inicio)) * areaLargura

    const calcularY = (preco) =>
      margem.topo +
      (1 - (preco - minimo) / Math.max(maximo - minimo, 1)) * areaAltura

    const series = ['Steam', 'Epic']
      .filter((nome) => plataformaAtiva === 'ambas' || plataformaAtiva === nome)
      .map((nome) => ({
        nome,
        dados: dados.filter((registro) => registro.plataforma === nome),
      }))
      .filter((serie) => serie.dados.length > 0)

    const pontosSeries = series.map((serie) => ({
      ...serie,
      pontos: serie.dados.map((registro) => ({
        ...registro,
        x: calcularX(registro.data_coleta),
        y: calcularY(Number(registro.preco_atual)),
      })),
    }))

    const quantidadeTicks = 5
    const ticksY = Array.from({ length: quantidadeTicks }, (_, indice) => {
      const proporcao = indice / (quantidadeTicks - 1)
      const preco = maximo - (maximo - minimo) * proporcao
      return {
        preco,
        y: margem.topo + proporcao * areaAltura,
      }
    })

    const inicioTicks = inicio
    const fimTicks = fim
    const ticksX = Array.from({ length: 5 }, (_, indice) => {
      const proporcao = indice / 4
      const timestamp = inicioTicks + (fimTicks - inicioTicks) * proporcao
      return {
        data: new Date(timestamp),
        x: margem.esquerda + proporcao * areaLargura,
      }
    })

    const previsao =
      previsaoData && previsaoInicio && previsaoFim
        ? {
            inicio: calcularX(previsaoInicio),
            fim: calcularX(previsaoFim),
            xAtual: calcularX(agora),
            data: calcularX(previsaoData),
            yAtual: calcularY(
              Number(dados[dados.length - 1].preco_atual)
            ),
            yPrevisto: calcularY(
              analiseGrafico.faixaPreco
                ? (analiseGrafico.faixaPreco[0] + analiseGrafico.faixaPreco[1]) / 2
                : Number(dados[dados.length - 1].preco_atual)
            ),
            dataPrevisao: new Date(previsaoData),
            dataInicio: new Date(previsaoInicio),
            dataFim: new Date(previsaoFim),
            precoPrevisto: analiseGrafico.faixaPreco
              ? (analiseGrafico.faixaPreco[0] + analiseGrafico.faixaPreco[1]) / 2
              : null,
            descontoPrevisto: analiseGrafico.faixaDesconto
              ? (analiseGrafico.faixaDesconto[0] + analiseGrafico.faixaDesconto[1]) / 2
              : null,
          }
        : null

    return {
      largura,
      altura,
      margem,
      areaLargura,
      areaAltura,
      pontosSeries,
      ticksY,
      ticksX,
      previsao,
      calcularX,
      calcularY,
    }
  }, [dados, plataformaAtiva, analiseGrafico, agoraAtual])

  const pontoTooltip = pontoSelecionado && grafico
    ? {
        left: `${(pontoSelecionado.x / grafico.largura) * 100}%`,
        top: `${(pontoSelecionado.y / grafico.altura) * 100}%`,
      }
    : null

  const filtrosPlataforma = ['ambas', 'Steam', 'Epic']

  const renderControles = () => (
    <div className="grafico-controles">
      <div className="grafico-grupo-controle">
        <span>Plataforma</span>
        <div className="grafico-filtros">
          {filtrosPlataforma.map((opcao) => {
            const disponivel =
              opcao === 'ambas' || plataformasDisponiveis.has(opcao)

            return (
              <button
                type="button"
                key={opcao}
                className={plataformaAtiva === opcao ? 'ativo' : ''}
                disabled={!disponivel}
                title={
                  disponivel
                    ? undefined
                    : `Sem histórico disponível para ${opcao}`
                }
                onClick={() => {
                  if (!disponivel) return
                  setPontoSelecionado(null)
                  setPrevisaoSelecionada(false)
                  onPlataformaChange(opcao)
                }}
              >
                {opcao === 'ambas' ? 'Ambas' : opcao}
              </button>
            )
          })}
        </div>
      </div>

      <div className="grafico-grupo-controle">
        <span>Período</span>
        <div className="grafico-filtros">
          {[
            ['30d', '30 dias'],
            ['3m', '3 meses'],
            ['6m', '6 meses'],
            ['1a', '1 ano'],
            ['tudo', 'Tudo'],
          ].map(([valor, rotulo]) => (
            <button
              type="button"
              key={valor}
              className={periodo === valor ? 'ativo' : ''}
              onClick={() => {
                setPeriodo(valor)
                setPontoSelecionado(null)
                setPrevisaoSelecionada(false)
              }}
            >
              {rotulo}
            </button>
          ))}
        </div>
      </div>
    </div>
  )

  if (!grafico) {
    return (
      <div className="grafico-interativo">
        {renderControles()}
        <div className="grafico-legenda">
          {plataformasDisponiveis.has('Steam') && (
            <span>
              <i className="legenda-ponto legenda-steam" />
              Steam
            </span>
          )}
          {plataformasDisponiveis.has('Epic') && (
            <span>
              <i className="legenda-ponto legenda-epic" />
              Epic
            </span>
          )}
        </div>
        <div className="ofertas-sem-dados">
          Histórico insuficiente para montar o gráfico neste filtro.
        </div>
      </div>
    )
  }

  return (
    <div className="grafico-interativo">
      {renderControles()}

      <div className="grafico-legenda">
        {grafico.pontosSeries.map((serie) => (
          <span key={serie.nome}>
            <i className={`legenda-ponto legenda-${serie.nome.toLowerCase()}`} />
            {serie.nome}
          </span>
        ))}
        {grafico.previsao && (
          <span>
            <i className="legenda-pontilhada" />
            Previsão
          </span>
        )}
      </div>

      <div className="grafico-area">
        <svg
          className="ofertas-grafico"
          viewBox={`0 0 ${grafico.largura} ${grafico.altura}`}
          role="img"
          aria-label={`Histórico de preços de ${historico.length ? 'jogo selecionado' : ''}`}
        >
          {grafico.ticksY.map((tick) => (
            <g key={`y-${tick.y}`}>
              <line
                x1={grafico.margem.esquerda}
                y1={tick.y}
                x2={grafico.largura - grafico.margem.direita}
                y2={tick.y}
                className="grafico-grade"
              />
              <text
                x={grafico.margem.esquerda - 12}
                y={tick.y + 4}
                className="grafico-label-eixo"
                textAnchor="end"
              >
                {formatarPreco(tick.preco)}
              </text>
            </g>
          ))}

          {grafico.ticksX.map((tick) => (
            <text
              key={`x-${tick.x}`}
              x={tick.x}
              y={grafico.altura - 20}
              className="grafico-label-eixo"
              textAnchor="middle"
            >
              {formatarMesGrafico(tick.data)}
            </text>
          ))}

          <line
            x1={grafico.margem.esquerda}
            y1={grafico.margem.topo + grafico.areaAltura}
            x2={grafico.largura - grafico.margem.direita}
            y2={grafico.margem.topo + grafico.areaAltura}
            className="grafico-eixo"
          />

          {grafico.previsao && (
            <>
              <rect
                x={grafico.previsao.inicio}
                y={grafico.margem.topo}
                width={Math.max(0, grafico.previsao.fim - grafico.previsao.inicio)}
                height={grafico.areaAltura}
                className="grafico-faixa-previsao"
              />

              <line
                x1={grafico.previsao.xAtual}
                y1={grafico.previsao.yAtual}
                x2={grafico.previsao.data}
                y2={grafico.previsao.yPrevisto}
                className="grafico-linha-previsao"
              />

              <line
                x1={grafico.previsao.data}
                y1={grafico.previsao.yPrevisto}
                x2={grafico.previsao.fim}
                y2={grafico.previsao.yPrevisto}
                className="grafico-linha-previsao"
              />

              <circle
                cx={grafico.previsao.data}
                cy={grafico.previsao.yPrevisto}
                r="7"
                className="grafico-ponto-previsao"
                onMouseEnter={() => setPrevisaoSelecionada(true)}
                onMouseLeave={() => setPrevisaoSelecionada(false)}
              />

              <line
                x1={grafico.previsao.inicio}
                y1={grafico.margem.topo}
                x2={grafico.previsao.inicio}
                y2={grafico.margem.topo + grafico.areaAltura}
                className="grafico-divisor-previsao"
              />
            </>
          )}

          {grafico.pontosSeries.map((serie) => (
            <g key={serie.nome}>
              <polyline
                points={serie.pontos.map((ponto) => `${ponto.x},${ponto.y}`).join(' ')}
                className={`grafico-linha grafico-linha-${serie.nome.toLowerCase()}`}
              />

              {serie.pontos
                .filter((ponto) => !ponto._ancoraPeriodo)
                .map((ponto) => (
                <circle
                  key={`${serie.nome}-${ponto.id}-${ponto.data_coleta}`}
                  cx={ponto.x}
                  cy={ponto.y}
                  r="5"
                  className={`grafico-ponto grafico-ponto-${serie.nome.toLowerCase()}`}
                  onMouseEnter={() => setPontoSelecionado(ponto)}
                  onMouseLeave={() => setPontoSelecionado(null)}
                />
              ))}
            </g>
          ))}
        </svg>

        {pontoSelecionado && pontoTooltip && (
          <div
            className="grafico-tooltip"
            style={pontoTooltip}
          >
            <strong>{pontoSelecionado.plataforma}</strong>
            <span>{formatarDataGrafico(pontoSelecionado.data_coleta)}</span>
            <strong>{formatarPreco(pontoSelecionado.preco_atual)}</strong>
            <span>
              {Number(pontoSelecionado.desconto || 0) > 0
                ? `${pontoSelecionado.desconto}% de desconto`
                : 'Sem promoção'}
            </span>
          </div>
        )}

        {grafico.previsao && previsaoSelecionada && (
          <div
            className="grafico-tooltip grafico-tooltip-previsao"
            style={{
              left: `${(grafico.previsao.data / grafico.largura) * 100}%`,
              top: `${(grafico.previsao.yPrevisto / grafico.altura) * 100}%`,
            }}
          >
            <strong>PREVISÃO</strong>
            <span>
              Janela: {formatarDataGrafico(grafico.previsao.dataInicio)} – {formatarDataGrafico(grafico.previsao.dataFim)}
            </span>
            <span>
              Ponto central: {formatarDataGrafico(grafico.previsao.dataPrevisao)}
            </span>
            <strong>
              {grafico.previsao.precoPrevisto !== null
                ? formatarPreco(grafico.previsao.precoPrevisto)
                : '—'}
            </strong>
            <span>
              {grafico.previsao.descontoPrevisto !== null
                ? `${Math.round(grafico.previsao.descontoPrevisto)}% de desconto provável`
                : 'Desconto não estimado'}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}

function Ofertas() {
  const [tema, setTema] = useState(() => {
    const salvo = localStorage.getItem('tema-comparador')
    return salvo === 'escuro' ? 'escuro' : 'claro'
  })

  const [jogos, setJogos] = useState([])
  const [historicos, setHistoricos] = useState({})
  const [busca, setBusca] = useState('')
  const [plataformaGrafico, setPlataformaGrafico] = useState('ambas')
  const [jogoSelecionado, setJogoSelecionado] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    localStorage.setItem('tema-comparador', tema)
  }, [tema])

  useEffect(() => {
    async function carregar() {
      try {
        setCarregando(true)
        setErro('')

        const resposta = await fetch(`${API}/`)

        if (!resposta.ok) {
          throw new Error('Não foi possível carregar os jogos.')
        }

        const dados = await resposta.json()
        setJogos(dados)

        const resultados = await Promise.all(
          dados.map(async (jogo) => {
            try {
              const respostaHistorico = await fetch(`${API}/${jogo.id}/historico`)

              if (!respostaHistorico.ok) return [jogo.id, []]

              return [jogo.id, await respostaHistorico.json()]
            } catch {
              return [jogo.id, []]
            }
          })
        )

        const mapa = Object.fromEntries(resultados)
        setHistoricos(mapa)

        const jogoIdParametro = new URLSearchParams(window.location.search).get('jogo')
        const jogoParametro = jogoIdParametro
          ? dados.find((jogo) => String(jogo.id) === String(jogoIdParametro))
          : null

        const ordenados = dados
          .map((jogo) => ({
            jogo,
            analise: analisarHistorico(mapa[jogo.id] || []),
          }))
          .filter(({ analise }) => analise.registros.length > 0)
          .sort((a, b) => b.analise.pontuacao - a.analise.pontuacao)

        if (jogoParametro) {
          setJogoSelecionado(jogoParametro)
        } else if (ordenados.length > 0) {
          setJogoSelecionado(ordenados[0].jogo)
        } else if (dados.length > 0) {
          setJogoSelecionado(dados[0])
        }
      } catch (error) {
        console.error('Erro ao carregar previsão:', error)
        setErro(error.message || 'Não foi possível carregar os dados.')
      } finally {
        setCarregando(false)
      }
    }

    carregar()
  }, [])

  const sugestoes = useMemo(() => {
    const termo = busca.trim().toLowerCase()

    if (!termo) return []

    return jogos
      .filter((jogo) => jogo.nome.toLowerCase().includes(termo))
      .slice(0, 6)
  }, [busca, jogos])

  const analise = useMemo(
    () =>
      analisarHistorico(
        jogoSelecionado ? historicos[jogoSelecionado.id] || [] : []
      ),
    [jogoSelecionado, historicos]
  )

  const comportamento = useMemo(
    () =>
      jogoSelecionado
        ? calcularComportamentoDesenvolvedora(
            jogoSelecionado,
            jogos,
            historicos
          )
        : null,
    [jogoSelecionado, jogos, historicos]
  )

  const resumoPromocoesPlataforma = useMemo(
    () => obterResumoPromocoesPorPlataforma(analise.registros),
    [analise.registros]
  )

  const melhoresTendencias = useMemo(
    () =>
      jogos
        .map((jogo) => ({
          jogo,
          analise: analisarHistorico(historicos[jogo.id] || []),
        }))
        .filter(({ analise }) => analise.nivel !== 'insuficiente')
        .sort((a, b) => b.analise.pontuacao - a.analise.pontuacao)
        .slice(0, 6),
    [jogos, historicos]
  )

  const selecionarJogo = (jogo) => {
    setJogoSelecionado(jogo)
    setBusca('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const ultimoRegistroPorPlataforma = useMemo(() => {
    const mapa = {}

    for (const registro of analise.registros) {
      const chave = (registro.plataforma || '').toLowerCase()

      if (
        !mapa[chave] ||
        new Date(registro.data_coleta) >
          new Date(mapa[chave].data_coleta)
      ) {
        mapa[chave] = registro
      }
    }

    return mapa
  }, [analise.registros])

  const precoAtual = Object.values(ultimoRegistroPorPlataforma)
    .map((registro) => Number(registro.preco_atual))
    .filter(Number.isFinite)

  const precoAtualMinimo = precoAtual.length ? Math.min(...precoAtual) : null

  const proximaJanela = (() => {
    if (!analise.intervaloMedio || analise.diasDesdePromocao === null) {
      return 'Sem estimativa suficiente'
    }

    const restante =
      analise.intervaloMedio - analise.diasDesdePromocao

    if (restante <= 0) {
      return 'Janela de promoção potencialmente próxima'
    }

    const minimo = Math.max(1, Math.round(restante * 0.5))
    const maximo = Math.max(minimo + 7, Math.round(restante * 1.25))

    return `Entre ${minimo} e ${maximo} dias`
  })()

  const previsaoTexto =
    analise.nivel === 'alta'
      ? 'O histórico indica uma tendência relevante de nova promoção.'
      : analise.nivel === 'media'
        ? 'O histórico apresenta sinais moderados de uma nova promoção.'
        : analise.nivel === 'baixa'
          ? 'O histórico apresenta poucos sinais de uma nova promoção no momento.'
          : 'Ainda não há histórico suficiente para estimar uma tendência.'

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho tema={tema} setTema={setTema} />

      <main className="pagina-ofertas">
        <section className="ofertas-hero">
          <div className="ofertas-hero-conteudo">
            <span className="hero-tag">PREVISÃO DE PREÇOS</span>

            <h1>Descubra quando pode valer a pena esperar.</h1>

            <p>
              Analise o histórico de preços e o comportamento promocional para
              acompanhar tendências de futuras ofertas.
            </p>

            <div className="ofertas-pesquisa">
              <span className="icone-pesquisa">⌕</span>

              <input
                type="text"
                value={busca}
                onChange={(evento) => setBusca(evento.target.value)}
                placeholder="Pesquise um jogo para analisar..."
                aria-label="Pesquisar jogo para análise"
              />

              {busca.trim() && sugestoes.length > 0 && (
                <div className="ofertas-sugestoes">
                  {sugestoes.map((jogo) => (
                    <button
                      type="button"
                      key={jogo.id}
                      onClick={() => selecionarJogo(jogo)}
                    >
                      <img src={imagemDoJogo(jogo)} alt="" />
                      <span>{jogo.nome}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>

        {erro ? (
          <div className="ofertas-erro">
            <strong>Não foi possível carregar a análise</strong>
            <span>{erro}</span>
          </div>
        ) : carregando ? (
          <div className="ofertas-carregando">
            Carregando histórico e tendências...
          </div>
        ) : jogoSelecionado ? (
          <>
            <section className="ofertas-secao">
              <div className="ofertas-titulo-secao">
                <span className="eyebrow">JOGO SELECIONADO</span>
                <h2>Previsão para {jogoSelecionado.nome}</h2>
              </div>

              <div className="jogo-selecionado-card">
                <img src={imagemDoJogo(jogoSelecionado)} alt="" />

                <div className="jogo-selecionado-info">
                  <span className="jogo-desenvolvedor">
                    {jogoSelecionado.desenvolvedor ||
                      'Desenvolvedora não informada'}
                  </span>

                  <h3>{jogoSelecionado.nome}</h3>

                  <div className="jogo-precos">
                    <div>
                      <span>Preço atual</span>
                      <strong>{formatarPreco(precoAtualMinimo)}</strong>
                    </div>

                    <div>
                      <span>Menor preço histórico</span>
                      <strong>{formatarPreco(analise.precoMinimo)}</strong>
                    </div>
                  </div>

                  <Link
                    to={`/jogos/${jogoSelecionado.id}`}
                    className="ofertas-link-detalhes"
                  >
                    Ver detalhes do jogo →
                  </Link>

                  <div className="jogo-promocoes-plataformas">
                    {resumoPromocoesPlataforma.map((item) => (
                      <div
                        key={item.plataforma}
                        className={`jogo-promocao-plataforma ${
                          !item.disponivel ? 'indisponivel' : ''
                        }`}
                      >
                        <span>{item.plataforma}</span>
                        {item.disponivel ? (
                          <>
                            <strong>
                              {item.promocoesRegistradas}{' '}
                              {item.promocoesRegistradas === 1
                                ? 'promoção registrada'
                                : 'promoções registradas'}
                            </strong>
                            <small>
                              Maior desconto: {item.maiorDesconto}%
                            </small>
                          </>
                        ) : (
                          <strong>Não disponível</strong>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </section>

            <section className="ofertas-secao">
              <div className="previsao-card">
                <div className="previsao-principal">
                  <span className="eyebrow">PREVISÃO</span>
                  <h2>Tendência de promoção</h2>

                  <strong className={`tendencia-${analise.nivel}`}>
                    {analise.tendencia}
                  </strong>

                  <p>{previsaoTexto}</p>
                </div>

                <div className="previsao-indicadores">
                  <div>
                    <span>Próxima janela estimada</span>
                    <strong>{proximaJanela}</strong>
                  </div>

                  <div>
                    <span>Desconto estimado</span>
                    <strong>
                      {analise.faixaDesconto
                        ? `${analise.faixaDesconto[0]}% – ${analise.faixaDesconto[1]}%`
                        : '—'}
                    </strong>
                  </div>

                  <div>
                    <span>Faixa de preço estimada</span>
                    <strong>
                      {analise.faixaPreco
                        ? analise.faixaPreco[0] === analise.faixaPreco[1]
                          ? formatarPreco(analise.faixaPreco[0])
                          : `${formatarPreco(
                              analise.faixaPreco[0]
                            )} – ${formatarPreco(analise.faixaPreco[1])}`
                        : '—'}
                    </strong>
                  </div>
                </div>
              </div>
            </section>

            <section className="ofertas-secao">
              <div className="ofertas-titulo-secao">
                <span className="eyebrow">HISTÓRICO</span>
                <h2>Histórico de preços</h2>
              </div>

              <div className="ofertas-grafico-card">
                <GraficoHistoricoOfertas
                  historico={analise.registros}
                  plataforma={plataformaGrafico}
                  onPlataformaChange={setPlataformaGrafico}
                />
              </div>

              <div className="ofertas-indicadores">
                <div>
                  <span>Menor preço</span>
                  <strong>{formatarPreco(analise.precoMinimo)}</strong>
                </div>

                <div>
                  <span>Maior desconto</span>
                  <strong>{analise.maiorDesconto}%</strong>
                </div>

                <div>
                  <span>Preço médio</span>
                  <strong>{formatarPreco(analise.precoMedio)}</strong>
                </div>

                <div>
                  <span>Registros</span>
                  <strong>{analise.registros.length}</strong>
                </div>
              </div>
            </section>

            <section className="ofertas-secao">
              <div className="ofertas-titulo-secao">
                <span className="eyebrow">DESENVOLVEDORA</span>
                <h2>Comportamento promocional</h2>
              </div>

              <div className="desenvolvedora-card">
                <div>
                  <span>Jogos analisados</span>
                  <strong>{comportamento?.jogosAnalisados || 0}</strong>
                </div>

                <div>
                  <span>Jogos que já tiveram promoções</span>
                  <strong>{comportamento?.promocoes || 0}</strong>
                </div>

                <div>
                  <span>Desconto médio</span>
                  <strong>
                    {comportamento?.descontoMedio
                      ? `${Math.round(comportamento.descontoMedio)}%`
                      : '—'}
                  </strong>
                </div>

                <div>
                  <span>Intervalo médio</span>
                  <strong>
                    {comportamento?.intervaloMedio
                      ? `${Math.round(comportamento.intervaloMedio)} dias`
                      : '—'}
                  </strong>
                </div>

                <div>
                  <span>Tempo desde a última</span>
                  <strong>
                    {analise.diasDesdePromocao !== null
                      ? `${Math.round(analise.diasDesdePromocao)} dias`
                      : '—'}
                  </strong>
                </div>
              </div>

              <p className="ofertas-explicacao">
                A análise considera o histórico do jogo e, quando existem
                dados suficientes, o comportamento promocional de outros jogos
                da mesma desenvolvedora.
              </p>
            </section>
          </>
        ) : null}

        {!carregando && melhoresTendencias.length > 0 && (
          <section className="ofertas-secao">
            <div className="ofertas-titulo-secao">
              <span className="eyebrow">EXPLORE</span>
              <h2>Melhores tendências</h2>
              <p>
                Selecione um jogo para atualizar toda a análise acima.
              </p>
            </div>

            <div className="tendencias-grade">
              {melhoresTendencias.map(({ jogo, analise: analiseCard }) => (
                <button
                  type="button"
                  key={jogo.id}
                  className={`tendencia-card ${
                    jogoSelecionado?.id === jogo.id ? 'selecionado' : ''
                  }`}
                  onClick={() => selecionarJogo(jogo)}
                >
                  <img src={imagemDoJogo(jogo)} alt="" />

                  <div>
                    <strong>{jogo.nome}</strong>
                    <span>
                      {jogo.desenvolvedor ||
                        'Desenvolvedora não informada'}
                    </span>

                    <em className={`tendencia-${analiseCard.nivel}`}>
                      Tendência {analiseCard.tendencia}
                    </em>
                  </div>
                </button>
              ))}
            </div>
          </section>
        )}
      </main>

      <footer>
        <strong>Comparador de Preços</strong>
        <span>Steam × Epic Games Store</span>
      </footer>
    </div>
  )
}

export default Ofertas
