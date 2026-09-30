import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import { buscarHistoricoJogo, buscarJogo } from '../servicos/jogos'
import { API_JOGOS_URL } from '../servicos/api'

function formatarPreco(preco) {
  if (preco === null || preco === undefined) {
    return 'Não disponível'
  }

  if (Number(preco) === 0) {
    return 'Grátis'
  }

  return Number(preco).toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  })
}

function formatarData(data) {
  if (!data) {
    return 'Não informado'
  }

  const dataFormatada = new Date(data)

  return dataFormatada.toLocaleDateString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    timeZone: 'UTC',
  })
}

function obterImagem(jogo) {
  return jogo.url_imagem_steam || jogo.url_imagem_epic || null
}

function obterImagemHero(jogo) {
  if (jogo.steam_id) {
    return `https://cdn.cloudflare.steamstatic.com/steam/apps/${jogo.steam_id}/library_hero.jpg`
  }

  return jogo.url_imagem_epic || jogo.url_imagem_steam || null
}

function obterLogoSteam(jogo) {
  if (!jogo.steam_id) {
    return null
  }

  return `https://cdn.cloudflare.steamstatic.com/steam/apps/${jogo.steam_id}/library_logo.png`
}

function descricaoValida(descricao) {
  if (!descricao) {
    return false
  }

  const valor = descricao.trim()

  return (
    valor !== '' &&
    valor.toUpperCase() !== 'N/A' &&
    valor.toUpperCase() !== 'NÃO INFORMADO'
  )
}

function obterDescricao(jogo) {
  if (descricaoValida(jogo.descricao_steam)) {
    return {
      fonte: 'Steam',
      texto: jogo.descricao_steam,
    }
  }

  if (descricaoValida(jogo.descricao_epic)) {
    return {
      fonte: 'Epic Games Store',
      texto: jogo.descricao_epic,
    }
  }

  return null
}

function obterPrecosAtuais(jogo, historico) {
  const precos = {
    Steam: jogo.preco_base_steam,
    Epic: jogo.preco_base_epic,
  }

  const ultimosRegistros = {}

  historico.forEach((registro) => {
    if (registro.plataforma !== 'Steam' && registro.plataforma !== 'Epic') {
      return
    }

    const registroAnterior = ultimosRegistros[registro.plataforma]

    if (
      !registroAnterior ||
      new Date(registro.data_coleta).getTime() >
        new Date(registroAnterior.data_coleta).getTime()
    ) {
      ultimosRegistros[registro.plataforma] = registro
    }
  })

  if (ultimosRegistros.Steam) {
    precos.Steam = ultimosRegistros.Steam.preco_atual
  }

  if (ultimosRegistros.Epic) {
    precos.Epic = ultimosRegistros.Epic.preco_atual
  }

  return precos
}

function obterMenorPreco(jogo, historico) {
  const precosAtuais = obterPrecosAtuais(jogo, historico)

  const precos = [
    precosAtuais.Steam,
    precosAtuais.Epic,
  ].filter((preco) => preco !== null && preco !== undefined)

  if (precos.length === 0) {
    return null
  }

  return Math.min(...precos)
}

function registroMaisRecente(historico, plataforma) {
  return historico
    .filter((registro) => registro.plataforma === plataforma)
    .sort(
      (a, b) =>
        new Date(b.data_coleta).getTime() -
        new Date(a.data_coleta).getTime()
    )[0] || null
}

function obterDadosPreco(jogo, historico, plataforma) {
  const registro = registroMaisRecente(historico, plataforma)
  const precoBase =
    plataforma === 'Steam'
      ? jogo.preco_base_steam
      : jogo.preco_base_epic

  const precoAtual =
    registro?.preco_atual ?? precoBase

  const desconto = Number(registro?.desconto ?? 0)

  const precoSemDesconto =
    registro?.preco_sem_desconto ?? precoAtual

  return {
    registro,
    precoAtual,
    desconto: Number.isFinite(desconto) ? desconto : 0,
    precoSemDesconto,
  }
}

function obterPeriodoEmDias(periodo) {
  const periodos = {
    '30d': 30,
    '3m': 90,
    '6m': 180,
    '1a': 365,
    tudo: null,
  }

  return periodos[periodo]
}

function GraficoHistorico({ historico, plataforma, periodo }) {
  const [pontoSelecionado, setPontoSelecionado] = useState(null)
  const [posicaoTooltip, setPosicaoTooltip] = useState(null)

  const dadosFiltrados = useMemo(() => {
    let dados = historico
      .filter((registro) => {
        if (plataforma === 'ambas') {
          return (
            registro.plataforma === 'Steam' ||
            registro.plataforma === 'Epic'
          )
        }

        return registro.plataforma === plataforma
      })
      .sort(
        (a, b) =>
          new Date(a.data_coleta).getTime() -
          new Date(b.data_coleta).getTime()
      )

    const dias = obterPeriodoEmDias(periodo)

    if (dias !== null && dados.length > 0) {
      const maiorData = Math.max(
        ...dados.map((registro) =>
          new Date(registro.data_coleta).getTime()
        )
      )

      const dataInicial =
        maiorData - dias * 24 * 60 * 60 * 1000

      /*
       * Se não houver uma coleta exatamente no início do período,
       * recuperamos a última leitura anterior. Ela representa o
       * preço que permaneceu válido até a próxima coleta.
       */
      const registroAnterior = [...dados]
        .reverse()
        .find(
          (registro) =>
            new Date(registro.data_coleta).getTime() < dataInicial
        )

      dados = dados.filter(
        (registro) =>
          new Date(registro.data_coleta).getTime() >= dataInicial
      )

      if (registroAnterior && dados.length > 0) {
        dados.unshift({
          ...registroAnterior,
          id: `ancora-${registroAnterior.id}-${periodo}`,
          data_coleta: new Date(dataInicial).toISOString(),
          _ancoraPeriodo: true,
        })
      }
    }

    return dados
  }, [historico, plataforma, periodo])

  const dadosSteam = dadosFiltrados.filter(
    (registro) => registro.plataforma === 'Steam'
  )

  const dadosEpic = dadosFiltrados.filter(
    (registro) => registro.plataforma === 'Epic'
  )

  const todosPrecos = dadosFiltrados.map((registro) =>
    Number(registro.preco_atual)
  )

  if (dadosFiltrados.length === 0) {
    return (
      <div className="grafico-vazio">
        <span>
          Sem histórico de preços para o período selecionado.
        </span>
      </div>
    )
  }

  const somenteGratis = dadosFiltrados.every(
    (registro) => Number(registro.preco_atual) === 0
  )

  if (somenteGratis) {
    return (
      <div className="grafico-vazio">
        <strong>Esta versão é gratuita</strong>
        <span>
          Não há variação de preço para acompanhar nesta oferta.
          Selecione uma versão ou DLC paga para visualizar o histórico de preços.
        </span>
      </div>
    )
  }

  const largura = 900
  const altura = 400
  const margemEsquerda = 75
  const margemDireita = 25
  const margemSuperior = 30
  const margemInferior = 65

  const areaLargura =
    largura - margemEsquerda - margemDireita

  const areaAltura =
    altura - margemSuperior - margemInferior

  const maiorPreco = Math.max(...todosPrecos)
  const menorPreco = Math.min(...todosPrecos)

  /*
   * Mantém o eixo vertical com valores arredondados e consistentes.
   * O intervalo se adapta ao jogo, mas os passos usam números
   * agradáveis (1, 2, 5, 10, 20, 50, 100, ...).
   */
  const obterPassoEixo = (valor) => {
    if (valor <= 0) {
      return 1
    }

    const potencia = Math.pow(10, Math.floor(Math.log10(valor)))
    const normalizado = valor / potencia

    if (normalizado <= 1) {
      return potencia
    }

    if (normalizado <= 2) {
      return 2 * potencia
    }

    if (normalizado <= 2.5) {
      return 2.5 * potencia
    }

    if (normalizado <= 5) {
      return 5 * potencia
    }

    return 10 * potencia
  }

  const passoEixo = obterPassoEixo(maiorPreco / 7)

  const escalaMin = Math.max(
    0,
    Math.floor(menorPreco / passoEixo) * passoEixo
  )

  const escalaMax = Math.max(
    escalaMin + passoEixo * 5,
    Math.ceil(maiorPreco / passoEixo) * passoEixo
  )

  /*
   * O eixo X representa o período selecionado, e não apenas
   * as datas em que houve coleta.
   *
   * Assim, se houver uma leitura em 01/01 e outra em 15/01
   * com o mesmo preço, a linha permanece no mesmo nível
   * durante todo o intervalo.
   */
  const datasColeta = dadosFiltrados.map((registro) =>
    new Date(registro.data_coleta).getTime()
  )

  const ultimaData = Math.max(...datasColeta)

  const diasPeriodo = obterPeriodoEmDias(periodo)

  const inicioPeriodo =
    diasPeriodo === null
      ? Math.min(...datasColeta)
      : ultimaData - diasPeriodo * 24 * 60 * 60 * 1000

  const fimPeriodo = ultimaData

  const diferencaPeriodo = fimPeriodo - inicioPeriodo

  const calcularX = (registro) => {
    if (diferencaPeriodo === 0) {
      return margemEsquerda + areaLargura / 2
    }

    const proporcao =
      (new Date(registro.data_coleta).getTime() - inicioPeriodo) /
      diferencaPeriodo

    return margemEsquerda + proporcao * areaLargura
  }

  const calcularY = (registro) => {
    if (escalaMax === escalaMin) {
      return margemSuperior + areaAltura / 2
    }

    const proporcao =
      (Number(registro.preco_atual) - escalaMin) /
      (escalaMax - escalaMin)

    return (
      margemSuperior +
      areaAltura -
      proporcao * areaAltura
    )
  }

  /*
   * O histórico representa o preço válido até a próxima coleta.
   * Portanto, entre duas leituras não devemos desenhar uma subida
   * ou queda gradual: o preço permanece constante e só muda no
   * momento da próxima leitura.
   */
  const criarPontos = (dados) => {
    if (dados.length === 0) {
      return ''
    }

    const pontos = []

    dados.forEach((registro, indice) => {
      const x = calcularX(registro)
      const y = calcularY(registro)

      if (indice === 0) {
        pontos.push(`${x},${y}`)
        return
      }

      const registroAnterior = dados[indice - 1]
      const yAnterior = calcularY(registroAnterior)

      /* Mantém o preço anterior até a data da nova coleta. */
      pontos.push(`${x},${yAnterior}`)
      pontos.push(`${x},${y}`)
    })

    return pontos.join(' ')
  }

  const linhasGrade = 5

  /*
   * Define uma quantidade pequena e padronizada de datas
   * para cada período, evitando poluição visual.
   */
  const quantidadeMarcacoes = {
    '30d': 5,
    '3m': 6,
    '6m': 6,
    '1a': 7,
    tudo: 7,
  }

  const quantidadeDatas =
    quantidadeMarcacoes[periodo] || 7

  const datasEixo = Array.from(
    { length: quantidadeDatas },
    (_, indice) => {
      if (quantidadeDatas === 1 || diferencaPeriodo === 0) {
        return inicioPeriodo
      }

      return (
        inicioPeriodo +
        (diferencaPeriodo * indice) /
          (quantidadeDatas - 1)
      )
    }
  )

  const formatarDataEixo = (timestamp) => {
    const data = new Date(timestamp)

    if (periodo === '30d') {
      return data.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        timeZone: 'UTC',
      })
    }

    if (periodo === '3m' || periodo === '6m') {
      return data.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: '2-digit',
        timeZone: 'UTC',
      })
    }

    return data.toLocaleDateString('pt-BR', {
      month: 'short',
      year: 'numeric',
      timeZone: 'UTC',
    })
  }

  const calcularXEixo = (timestamp) => {
    if (diferencaPeriodo === 0) {
      return margemEsquerda + areaLargura / 2
    }

    return (
      margemEsquerda +
      ((timestamp - inicioPeriodo) / diferencaPeriodo) *
        areaLargura
    )
  }

  const obterValorNoMouse = (dados, x) => {
    if (dados.length === 0) {
      return null
    }

    const timestamp =
      inicioPeriodo +
      ((x - margemEsquerda) / areaLargura) *
        diferencaPeriodo

    let registroAtual = dados[0]

    for (let indice = 1; indice < dados.length; indice += 1) {
      const registro = dados[indice]

      if (new Date(registro.data_coleta).getTime() <= timestamp) {
        registroAtual = registro
      } else {
        break
      }
    }

    const y = calcularY(registroAtual)

    return {
      registro: registroAtual,
      timestamp,
      y,
    }
  }

  const lidarComMovimentoMouse = (evento, dados) => {
    const svg = evento.currentTarget.ownerSVGElement || evento.currentTarget
    const rect = svg.getBoundingClientRect()
    const x =
      ((evento.clientX - rect.left) / rect.width) * largura

    const xLimitado = Math.max(
      margemEsquerda,
      Math.min(largura - margemDireita, x)
    )

    const resultado = obterValorNoMouse(dados, xLimitado)

    if (!resultado) {
      return
    }

    const y = resultado.y
    const timestamp = resultado.timestamp

    setPontoSelecionado({
      ...resultado.registro,
      data_coleta: new Date(timestamp).toISOString(),
    })

    setPosicaoTooltip({
      x: (xLimitado / largura) * 100,
      y: (y / altura) * 100,
    })
  }

  const limparTooltip = () => {
    setPontoSelecionado(null)
    setPosicaoTooltip(null)
  }

  return (
    <div className="grafico-container">
      <div className="grafico-legenda">
        {(plataforma === 'ambas' ||
          plataforma === 'Steam') && (
          <span>
            <i className="legenda-ponto legenda-steam" />
            Steam
          </span>
        )}

        {(plataforma === 'ambas' ||
          plataforma === 'Epic') && (
          <span>
            <i className="legenda-ponto legenda-epic" />
            Epic
          </span>
        )}
      </div>

      <div className="grafico-area">
        <svg
          className="grafico-svg"
          viewBox={`0 0 ${largura} ${altura}`}
          preserveAspectRatio="none"
        >
          {Array.from({ length: linhasGrade }).map(
            (_, indice) => {
              const proporcao =
                indice / (linhasGrade - 1)

              const y =
                margemSuperior +
                proporcao * areaAltura

              const valor =
                escalaMax -
                proporcao *
                  (escalaMax - escalaMin)

              return (
                <g key={indice}>
                  <line
                    x1={margemEsquerda}
                    y1={y}
                    x2={largura - margemDireita}
                    y2={y}
                    className="grafico-grade"
                  />

                  <text
                    x={margemEsquerda - 10}
                    y={y + 4}
                    textAnchor="end"
                    className="grafico-eixo-texto"
                  >
                    {formatarPreco(valor)}
                  </text>
                </g>
              )
            }
          )}

          {datasEixo.map((timestamp, indice) => {
            const x = calcularXEixo(timestamp)

            return (
              <g key={`data-${indice}`}>
                <line
                  x1={x}
                  y1={margemSuperior}
                  x2={x}
                  y2={margemSuperior + areaAltura}
                  className="grafico-grade-vertical"
                />

                <text
                  x={x}
                  y={margemSuperior + areaAltura + 25}
                  textAnchor="middle"
                  className="grafico-eixo-texto grafico-data"
                >
                  {formatarDataEixo(timestamp)}
                </text>
              </g>
            )
          })}

          {dadosSteam.length > 1 && (
            <polyline
              points={criarPontos(dadosSteam)}
              className="linha-historico linha-steam"
            />
          )}

          {dadosEpic.length > 1 && (
            <polyline
              points={criarPontos(dadosEpic)}
              className="linha-historico linha-epic"
            />
          )}

          {dadosSteam.length > 0 && (
            <polyline
              points={criarPontos(dadosSteam)}
              className="linha-historico-hover linha-steam"
              onMouseMove={(evento) => lidarComMovimentoMouse(evento, dadosSteam)}
              onMouseLeave={limparTooltip}
            />
          )}

          {dadosEpic.length > 0 && (
            <polyline
              points={criarPontos(dadosEpic)}
              className="linha-historico-hover linha-epic"
              onMouseMove={(evento) => lidarComMovimentoMouse(evento, dadosEpic)}
              onMouseLeave={limparTooltip}
            />
          )}

          {dadosSteam
            .filter((registro) => !registro._ancoraPeriodo)
            .map((registro) => (
            <circle
              key={`steam-${registro.id}`}
              cx={calcularX(registro)}
              cy={calcularY(registro)}
              r="5"
              className="ponto-historico ponto-steam"
              onMouseEnter={() =>
                setPontoSelecionado(registro)
              }
              onMouseLeave={() =>
                setPontoSelecionado(null)
              }
            />
          ))}

          {dadosEpic
            .filter((registro) => !registro._ancoraPeriodo)
            .map((registro) => (
            <circle
              key={`epic-${registro.id}`}
              cx={calcularX(registro)}
              cy={calcularY(registro)}
              r="5"
              className="ponto-historico ponto-epic"
              onMouseEnter={() =>
                setPontoSelecionado(registro)
              }
              onMouseLeave={() =>
                setPontoSelecionado(null)
              }
            />
          ))}

          <line
            x1={margemEsquerda}
            y1={margemSuperior + areaAltura}
            x2={largura - margemDireita}
            y2={margemSuperior + areaAltura}
            className="grafico-eixo"
          />
        </svg>

        {pontoSelecionado && posicaoTooltip && (
          <div
            className="grafico-tooltip"
            style={{
              left: `${posicaoTooltip.x}%`,
              top: `${posicaoTooltip.y}%`,
            }}
          >
            <strong>
              {pontoSelecionado.plataforma}
            </strong>

            <span>
              {formatarData(
                pontoSelecionado.data_coleta
              )}
            </span>

            <strong>
              {formatarPreco(
                pontoSelecionado.preco_atual
              )}
            </strong>

            {pontoSelecionado.desconto > 0 && (
              <span>
                {pontoSelecionado.desconto}% de desconto
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

function DetalhesJogo() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [tema, setTema] = useState(() => {
    return localStorage.getItem('tema') || 'claro'
  })

  const [jogo, setJogo] = useState(null)
  const [historico, setHistorico] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState(null)
  const [descricaoAtual, setDescricaoAtual] = useState(null)
  const [midiaSteam, setMidiaSteam] = useState({
    screenshots: [],
    videos: [],
  })
  const [imagemSelecionada, setImagemSelecionada] = useState(null)
  const [imagemGaleriaSelecionada, setImagemGaleriaSelecionada] = useState(null)
  const [pausarCarrossel, setPausarCarrossel] = useState(false)

  const [plataforma, setPlataforma] =
    useState('ambas')

  const [periodo, setPeriodo] =
    useState('tudo')

  useEffect(() => {
    localStorage.setItem('tema', tema)
  }, [tema])

  useEffect(() => {
    if (midiaSteam.screenshots.length <= 1 || pausarCarrossel) {
      return undefined
    }

    const intervalo = setInterval(() => {
      setImagemGaleriaSelecionada((imagemAtual) => {
        const imagens = midiaSteam.screenshots

        if (imagens.length === 0) {
          return null
        }

        const indiceAtual = imagens.findIndex(
          (imagem) => imagem.url === imagemAtual
        )

        const proximoIndice =
          indiceAtual >= 0
            ? (indiceAtual + 1) % imagens.length
            : 0

        return imagens[proximoIndice].url
      })
    }, 10000)

    return () => clearInterval(intervalo)
  }, [midiaSteam.screenshots, pausarCarrossel])

  useEffect(() => {
    if (!pausarCarrossel) {
      return undefined
    }

    const retornoCarrossel = setTimeout(() => {
      setPausarCarrossel(false)
    }, 30000)

    return () => clearTimeout(retornoCarrossel)
  }, [pausarCarrossel])

  useEffect(() => {
    async function carregarDados() {
      try {
        setCarregando(true)
        setErro(null)

        const [dadosJogo, dadosHistorico] =
          await Promise.all([
            buscarJogo(id),
            buscarHistoricoJogo(id),
          ])

        setJogo(dadosJogo)
        setHistorico(dadosHistorico)

        try {
          const respostaDescricao = await fetch(
            `${API_JOGOS_URL}/${id}/descricao`
          )

          if (respostaDescricao.ok) {
            const dadosDescricao = await respostaDescricao.json()

            if (descricaoValida(dadosDescricao.descricao)) {
              setDescricaoAtual({
                fonte: dadosDescricao.fonte,
                texto: dadosDescricao.descricao,
              })
            }
          }
        } catch (erroDescricao) {
          console.warn(
            'Não foi possível obter a descrição atual da Steam.',
            erroDescricao
          )
        }

        try {
          const respostaMidia = await fetch(
            `${API_JOGOS_URL}/${id}/midia`
          )

          if (respostaMidia.ok) {
            const dadosMidia = await respostaMidia.json()

            const screenshots = Array.isArray(dadosMidia.screenshots)
              ? dadosMidia.screenshots
              : []

            setMidiaSteam({
              screenshots,
              videos: Array.isArray(dadosMidia.videos)
                ? dadosMidia.videos
                : [],
            })

            setImagemGaleriaSelecionada(
              screenshots[0]?.url || null
            )
          }
        } catch (erroMidia) {
          console.warn(
            'Não foi possível obter imagens e vídeos da Steam.',
            erroMidia
          )
        }
      } catch (erroCarregamento) {
        console.error(erroCarregamento)
        setErro(
          'Não foi possível carregar os dados deste jogo.'
        )
      } finally {
        setCarregando(false)
      }
    }

    carregarDados()
  }, [id])

  if (carregando) {
    return (
      <div className={`app tema-${tema}`}>
        <Cabecalho
          tema={tema}
          setTema={setTema}
        />

        <main className="pagina-detalhes estado-detalhes">
          <div className="carregando-detalhes">
            Carregando dados do jogo...
          </div>
        </main>
      </div>
    )
  }

  if (erro || !jogo) {
    return (
      <div className={`app tema-${tema}`}>
        <Cabecalho
          tema={tema}
          setTema={setTema}
        />

        <main className="pagina-detalhes estado-detalhes">
          <div className="erro-detalhes">
            <h1>Jogo não encontrado</h1>

            <p>
              {erro ||
                'Não foi possível encontrar este jogo.'}
            </p>

            <button
              className="botao-voltar-detalhes"
              onClick={() => navigate('/jogos')}
            >
              ← Voltar para jogos
            </button>
          </div>
        </main>
      </div>
    )
  }

  const menorPreco = obterMenorPreco(jogo, historico)
  const imagem = obterImagem(jogo)
  const imagemHero = obterImagemHero(jogo)
  const logoSteam = obterLogoSteam(jogo)

  const precoSteam = obterDadosPreco(jogo, historico, 'Steam')
  const precoEpic = obterDadosPreco(jogo, historico, 'Epic')
  const descricao = descricaoAtual || obterDescricao(jogo)

  const steamDisponivel =
    precoSteam.precoAtual !== null &&
    precoSteam.precoAtual !== undefined

  const epicDisponivel =
    precoEpic.precoAtual !== null &&
    precoEpic.precoAtual !== undefined

  const steamEhMenor =
    steamDisponivel &&
    epicDisponivel &&
    Number(precoSteam.precoAtual) < Number(precoEpic.precoAtual)

  const epicEhMenor =
    steamDisponivel &&
    epicDisponivel &&
    Number(precoEpic.precoAtual) < Number(precoSteam.precoAtual)

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho
        tema={tema}
        setTema={setTema}
      />

      <main className="pagina-detalhes">
        <div className="conteudo-detalhes">
          <button
            className="botao-voltar-detalhes"
            onClick={() => navigate(-1)}
          >
            ← Voltar
          </button>

          <section className="hero-detalhes">
            {imagemHero ? (
              <img
                className="imagem-fundo-detalhes"
                src={imagemHero}
                alt=""
                aria-hidden="true"
                loading="eager"
                decoding="async"
                onError={(evento) => {
                  if (imagem && evento.currentTarget.src !== imagem) {
                    evento.currentTarget.src = imagem
                  }
                }}
              />
            ) : (
              <div className="imagem-fundo-detalhes-vazia">
                Sem imagem
              </div>
            )}

            <div className="hero-sobreposicao-detalhes" />

            <div className="informacoes-principais">
              <span className="eyebrow">
                DETALHES DO JOGO
              </span>

              {logoSteam ? (
                <>
                  <img
                    className="logo-jogo-steam"
                    src={logoSteam}
                    alt={jogo.nome}
                    loading="eager"
                    decoding="async"
                    onError={(evento) => {
                      evento.currentTarget.style.display = 'none'
                      const fallback = evento.currentTarget.nextElementSibling
                      if (fallback) {
                        fallback.style.display = 'block'
                      }
                    }}
                  />
                  <h1 className="nome-jogo-fallback">{jogo.nome}</h1>
                </>
              ) : (
                <h1>{jogo.nome}</h1>
              )}

              {jogo.desenvolvedor && (
                <p className="desenvolvedor-detalhes">
                  Desenvolvido por{' '}
                  {jogo.desenvolvedor}
                </p>
              )}

              <div className="metadados-detalhes">
                {jogo.genero && (
                  <span>
                    <strong>Gênero:</strong>{' '}
                    {jogo.genero}
                  </span>
                )}

                {jogo.data_lancamento && (
                  <span>
                    <strong>Lançamento:</strong>{' '}
                    {formatarData(
                      jogo.data_lancamento
                    )}
                  </span>
                )}

                {jogo.publicadora && (
                  <span>
                    <strong>Publicadora:</strong>{' '}
                    {jogo.publicadora}
                  </span>
                )}
              </div>

              {menorPreco !== null && (
                <div className="menor-preco-detalhes">
                  <span>Menor preço atual</span>

                  <strong>
                    {formatarPreco(menorPreco)}
                  </strong>
                </div>
              )}
            </div>
          </section>



          {imagemSelecionada && (
            <div
              role="dialog"
              aria-modal="true"
              aria-label={`Visualização da imagem de ${jogo.nome}`}
              onClick={() => setImagemSelecionada(null)}
              style={{
                position: 'fixed',
                inset: 0,
                zIndex: 1000,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '24px',
                background: 'rgba(0, 0, 0, 0.88)',
                cursor: 'zoom-out',
              }}
            >
              <img
                src={imagemSelecionada}
                alt={`Screenshot ampliado de ${jogo.nome}`}
                style={{
                  maxWidth: '95vw',
                  maxHeight: '92vh',
                  objectFit: 'contain',
                  borderRadius: '10px',
                }}
              />
            </div>
          )}

          <section className="precos-detalhes">
            <div className="titulo-secao-detalhes">
              <div>
                <span className="eyebrow">
                  PREÇOS ATUAIS
                </span>

                <h2>Compare as lojas</h2>
              </div>
            </div>

            <div className="cards-precos">
              <div className="card-preco-wrapper">
                <div className="etiquetas-preco">
                  {steamEhMenor && (
                    <span className="marcador-menor-preco">
                      ✓ MELHOR PREÇO
                    </span>
                  )}

                  {precoSteam.desconto > 0 && (
                    <span className="marcador-desconto">
                      -{precoSteam.desconto}% OFF
                    </span>
                  )}
                </div>

                <article className="card-preco">
                  <div className="card-preco-topo">
                    <span className="nome-plataforma">
                      Steam
                    </span>
                  </div>

                  <strong className="preco-atual">
                    {formatarPreco(precoSteam.precoAtual)}
                  </strong>

                  {precoSteam.desconto > 0 &&
                    precoSteam.precoSemDesconto !== null &&
                    precoSteam.precoSemDesconto !== undefined && (
                      <span className="preco-sem-desconto">
                        {formatarPreco(precoSteam.precoSemDesconto)}
                      </span>
                    )}

                  {jogo.url_steam && (
                    <a
                      href={jogo.url_steam}
                      target="_blank"
                      rel="noreferrer"
                      className="botao-loja"
                    >
                      Ver na Steam ↗
                    </a>
                  )}
                </article>
              </div>

              <div className="card-preco-wrapper">
                <div className="etiquetas-preco">
                  {epicEhMenor && (
                    <span className="marcador-menor-preco">
                      ✓ MELHOR PREÇO
                    </span>
                  )}

                  {precoEpic.desconto > 0 && (
                    <span className="marcador-desconto">
                      -{precoEpic.desconto}% OFF
                    </span>
                  )}
                </div>

                <article className="card-preco">
                  <div className="card-preco-topo">
                    <span className="nome-plataforma">
                      Epic Games Store
                    </span>
                  </div>

                  <strong className="preco-atual">
                    {formatarPreco(precoEpic.precoAtual)}
                  </strong>

                  {precoEpic.desconto > 0 &&
                    precoEpic.precoSemDesconto !== null &&
                    precoEpic.precoSemDesconto !== undefined && (
                      <span className="preco-sem-desconto">
                        {formatarPreco(precoEpic.precoSemDesconto)}
                      </span>
                    )}

                  {jogo.url_epic && (
                    <a
                      href={jogo.url_epic}
                      target="_blank"
                      rel="noreferrer"
                      className="botao-loja"
                    >
                      Ver na Epic ↗
                    </a>
                  )}
                </article>
              </div>
            </div>
          </section>

          <section className="historico-detalhes">
            <div className="titulo-secao-detalhes">
              <div>
                <span className="eyebrow">
                  HISTÓRICO
                </span>

                <h2>Variação de preços</h2>

                <p>
                  Acompanhe como o preço do jogo
                  mudou ao longo do tempo.
                </p>
              </div>
            </div>

            <div className="controles-historico">
              <div className="grupo-controle">
                <span>Plataforma</span>

                <div className="botoes-filtro">
                  <button
                    className={
                      plataforma === 'ambas'
                        ? 'ativo'
                        : ''
                    }
                    onClick={() =>
                      setPlataforma('ambas')
                    }
                  >
                    Ambas
                  </button>

                  <button
                    className={
                      plataforma === 'Steam'
                        ? 'ativo'
                        : ''
                    }
                    onClick={() =>
                      setPlataforma('Steam')
                    }
                  >
                    Steam
                  </button>

                  <button
                    className={
                      plataforma === 'Epic'
                        ? 'ativo'
                        : ''
                    }
                    onClick={() =>
                      setPlataforma('Epic')
                    }
                  >
                    Epic
                  </button>
                </div>
              </div>

              <div className="grupo-controle">
                <span>Período</span>

                <div className="botoes-filtro">
                  <button
                    className={
                      periodo === '30d'
                        ? 'ativo'
                        : ''
                    }
                    onClick={() =>
                      setPeriodo('30d')
                    }
                  >
                    30 dias
                  </button>

                  <button
                    className={
                      periodo === '3m'
                        ? 'ativo'
                        : ''
                    }
                    onClick={() =>
                      setPeriodo('3m')
                    }
                  >
                    3 meses
                  </button>

                  <button
                    className={
                      periodo === '6m'
                        ? 'ativo'
                        : ''
                    }
                    onClick={() =>
                      setPeriodo('6m')
                    }
                  >
                    6 meses
                  </button>

                  <button
                    className={
                      periodo === '1a'
                        ? 'ativo'
                        : ''
                    }
                    onClick={() =>
                      setPeriodo('1a')
                    }
                  >
                    1 ano
                  </button>

                  <button
                    className={
                      periodo === 'tudo'
                        ? 'ativo'
                        : ''
                    }
                    onClick={() =>
                      setPeriodo('tudo')
                    }
                  >
                    Tudo
                  </button>
                </div>
              </div>
            </div>

            <GraficoHistorico
              historico={historico}
              plataforma={plataforma}
              periodo={periodo}
            />
          </section>

          {(midiaSteam.screenshots.length > 0 ||
            midiaSteam.videos.some(
              (video) =>
                video?.webm?.max ||
                video?.webm?.['480'] ||
                video?.mp4?.max ||
                video?.mp4?.['480']
            )) && (
            <section className="midia-detalhes">
              {midiaSteam.screenshots.length > 0 && (
                <div className="galeria-steam-detalhes">
                  <div className="titulo-secao-detalhes">
                    <h2>Imagens do jogo</h2>
                  </div>

                  {(() => {
                    const imagemPrincipal =
                      midiaSteam.screenshots.find(
                        (imagem) =>
                          imagem.url === imagemGaleriaSelecionada
                      ) || midiaSteam.screenshots[0]

                    return (
                      <>
                        <button
                          type="button"
                          onClick={() =>
                            setImagemSelecionada(imagemPrincipal.url)
                          }
                          aria-label="Ampliar imagem selecionada"
                          style={{
                            display: 'block',
                            width: '100%',
                            padding: 0,
                            border: '0',
                            background: 'none',
                            cursor: 'zoom-in',
                            borderRadius: '16px',
                            overflow: 'hidden',
                          }}
                        >
                          <img
                            src={imagemPrincipal.url}
                            alt={`Screenshot selecionado de ${jogo.nome}`}
                            loading="eager"
                            decoding="async"
                            style={{
                              display: 'block',
                              width: '100%',
                              aspectRatio: '16 / 9',
                              objectFit: 'cover',
                              borderRadius: '16px',
                            }}
                          />
                        </button>

                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'center',
                            gap: '12px',
                            marginTop: '18px',
                            overflowX: 'auto',
                            padding: '2px 4px 8px',
                          }}
                        >
                          {midiaSteam.screenshots.map((imagem, indice) => {
                            const selecionada =
                              imagem.url === imagemPrincipal.url

                            return (
                              <button
                                key={imagem.id || indice}
                                type="button"
                                onClick={() => {
                                  setImagemGaleriaSelecionada(imagem.url)
                                  setPausarCarrossel(true)
                                }}
                                aria-label={`Selecionar imagem ${indice + 1}`}
                                aria-current={selecionada ? 'true' : undefined}
                                style={{
                                  flex: '0 0 104px',
                                  width: '104px',
                                  height: '62px',
                                  padding: 0,
                                  border: selecionada
                                    ? '2px solid var(--roxo-tema)'
                                    : '2px solid transparent',
                                  borderRadius: '8px',
                                  overflow: 'hidden',
                                  background: 'none',
                                  cursor: 'pointer',
                                  opacity: selecionada ? 1 : 0.42,
                                  transition:
                                    'opacity 0.2s ease, border-color 0.2s ease, transform 0.2s ease',
                                }}
                              >
                                <img
                                  src={imagem.thumbnail}
                                  alt={`Miniatura ${indice + 1} de ${jogo.nome}`}
                                  loading="lazy"
                                  decoding="async"
                                  style={{
                                    display: 'block',
                                    width: '100%',
                                    height: '100%',
                                    objectFit: 'cover',
                                  }}
                                />
                              </button>
                            )
                          })}
                        </div>
                      </>
                    )
                  })()}
                </div>
              )}
              {midiaSteam.videos.some(
                (video) =>
                  video?.webm?.max ||
                  video?.webm?.['480'] ||
                  video?.mp4?.max ||
                  video?.mp4?.['480']
              ) && (
                <div className="video-steam-detalhes">
                  <div className="titulo-secao-detalhes">
                    <span className="eyebrow">VÍDEO</span>
                    <h2>Trailer</h2>
                  </div>

                  {(() => {
                    const video =
                      midiaSteam.videos.find((item) => item.destaque) ||
                      midiaSteam.videos[0]

                    const fonteVideo =
                      video?.webm?.max ||
                      video?.webm?.['480'] ||
                      video?.mp4?.max ||
                      video?.mp4?.['480']

                    if (!fonteVideo) {
                      return null
                    }

                    return (
                      <video
                        controls
                        preload="metadata"
                        poster={video.thumbnail}
                        style={{
                          display: 'block',
                          width: '100%',
                          maxHeight: '520px',
                          objectFit: 'contain',
                          borderRadius: '16px',
                          background: '#000',
                        }}
                      >
                        <source src={fonteVideo} />
                        Seu navegador não suporta reprodução de vídeo.
                      </video>
                    )
                  })()}
                </div>
              )}
            </section>
          )}

          {descricao && (
            <section className="descricoes-detalhes">
              <div className="titulo-secao-detalhes">
                <h2>Sobre o jogo</h2>
              </div>

              <div className="cards-descricao">
                <article className="card-descricao">
                  <h3>
                    {descricao.fonte.replace(' (banco de dados)', '')}
                  </h3>

                  <p>
                    {descricao.texto}
                  </p>
                </article>
              </div>
            </section>
          )}
        </div>
      </main>
    </div>
  )
}

export default DetalhesJogo