import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import { buscarHistoricoJogo, buscarJogo } from '../servicos/jogos'
import { API_JOGOS_URL } from '../servicos/api'
import { API_BASE, useAuth } from '../contextos/AuthContext'
import { useTema } from '../contextos/TemaContext'

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


function sanitizarDescricaoHTML(html) {
  if (!html || typeof window === 'undefined') {
    return ''
  }

  const parser = new DOMParser()
  const documento = parser.parseFromString(html, 'text/html')

  const tagsPermitidas = new Set([
    'H1',
    'H2',
    'H3',
    'P',
    'STRONG',
    'EM',
    'U',
    'BR',
    'UL',
    'OL',
    'LI',
    'IMG',
    'VIDEO',
    'SOURCE',
    'A',
  ])

  const atributosPermitidos = {
    IMG: new Set(['src', 'alt']),
    VIDEO: new Set(['poster', 'controls', 'muted', 'loop', 'playsinline']),
    SOURCE: new Set(['src', 'type']),
    A: new Set(['href', 'target', 'rel']),
  }

  const urlSegura = (valor) => {
    if (!valor) {
      return false
    }

    try {
      const url = new URL(valor, window.location.origin)
      return url.protocol === 'http:' || url.protocol === 'https:'
    } catch {
      return false
    }
  }

  const substituirPorFilhos = (elemento) => {
    const pai = elemento.parentNode

    if (!pai) {
      return
    }

    const filhos = Array.from(elemento.childNodes)

    filhos.forEach((filho) => {
      pai.insertBefore(filho, elemento)
      if (filho.nodeType === Node.ELEMENT_NODE) {
        limparNo(filho)
      }
    })

    elemento.remove()
  }

  const limparNo = (no) => {
    if (no.nodeType !== Node.ELEMENT_NODE) {
      return
    }

    const elemento = no

    if (!tagsPermitidas.has(elemento.tagName)) {
      substituirPorFilhos(elemento)
      return
    }

    const permitidos = atributosPermitidos[elemento.tagName] || new Set()

    Array.from(elemento.attributes).forEach((atributo) => {
      if (!permitidos.has(atributo.name.toLowerCase())) {
        elemento.removeAttribute(atributo.name)
      }
    })

    if (elemento.tagName === 'A') {
      const href = elemento.getAttribute('href')

      if (!urlSegura(href)) {
        substituirPorFilhos(elemento)
        return
      }

      elemento.setAttribute('target', '_blank')
      elemento.setAttribute('rel', 'noreferrer')
    }

    if (elemento.tagName === 'IMG') {
      const src = elemento.getAttribute('src')

      if (!urlSegura(src)) {
        elemento.remove()
        return
      }
    }

    if (elemento.tagName === 'VIDEO') {
      const poster = elemento.getAttribute('poster')

      if (poster && !urlSegura(poster)) {
        elemento.removeAttribute('poster')
      }
    }

    if (elemento.tagName === 'SOURCE') {
      const src = elemento.getAttribute('src')

      if (!urlSegura(src)) {
        elemento.remove()
        return
      }
    }

    Array.from(elemento.children).forEach(limparNo)
  }

  Array.from(documento.body.children).forEach(limparNo)

  return documento.body.innerHTML
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

function GraficoHistorico({ historico, plataforma, periodo, expandido = false }) {
  const [pontoSelecionado, setPontoSelecionado] = useState(null)
  const [posicaoTooltip, setPosicaoTooltip] = useState(null)
  const [pontoFixado, setPontoFixado] = useState(null)
  const tooltipTimerRef = useRef(null)

  // Mantém uma referência temporal consistente durante o cálculo de uma janela.
  const [agoraGrafico] = useState(() => Date.now())

  const dadosFiltrados = useMemo(() => {
    const dias = obterPeriodoEmDias(periodo)
    const historicoValido = historico
      .filter((registro) => {
        const timestamp = new Date(registro.data_coleta).getTime()
        const preco = Number(registro.preco_atual)
        return (
          (registro.plataforma === 'Steam' || registro.plataforma === 'Epic') &&
          Number.isFinite(timestamp) &&
          timestamp <= agoraGrafico &&
          registro.preco_atual !== null &&
          registro.preco_atual !== undefined &&
          Number.isFinite(preco)
        )
      })
      .sort(
        (a, b) =>
          new Date(a.data_coleta).getTime() -
          new Date(b.data_coleta).getTime()
      )

    if (historicoValido.length === 0) {
      return []
    }

    const primeiraDataJogo = Math.min(
      ...historicoValido.map((registro) =>
        new Date(registro.data_coleta).getTime()
      )
    )
    const dataInicial =
      dias === null
        ? primeiraDataJogo
        : agoraGrafico - dias * 24 * 60 * 60 * 1000

    const plataformas =
      plataforma === 'ambas' ? ['Steam', 'Epic'] : [plataforma]
    const resultado = []

    plataformas.forEach((plataformaAtual) => {
      const historicoPlataforma = historicoValido.filter(
        (registro) => registro.plataforma === plataformaAtual
      )

      if (historicoPlataforma.length === 0) {
        return
      }

      // Última cotação anterior ao início da janela: representa o preço
      // válido no primeiro dia, mesmo se não houve coleta dentro do período.
      const anteriores = historicoPlataforma.filter(
        (registro) =>
          new Date(registro.data_coleta).getTime() < dataInicial
      )
      const registroAnterior = anteriores[anteriores.length - 1]
      const registrosDoPeriodo = historicoPlataforma.filter((registro) => {
        const timestamp = new Date(registro.data_coleta).getTime()
        return timestamp >= dataInicial && timestamp <= agoraGrafico
      })

      const serie = []
      if (registroAnterior) {
        serie.push({
          ...registroAnterior,
          id: `ancora-${plataformaAtual}-${registroAnterior.id}-${periodo}`,
          data_coleta: new Date(dataInicial).toISOString(),
          _ancoraPeriodo: true,
        })
      }
      serie.push(...registrosDoPeriodo)

      // A última cotação conhecida continua válida até hoje. Este ponto é
      // apenas geométrico: não representa uma nova coleta nem gera marcador.
      if (serie.length > 0) {
        const ultimoRegistro = serie[serie.length - 1]
        const ultimaDataPlataforma = new Date(
          ultimoRegistro.data_coleta
        ).getTime()

        if (ultimaDataPlataforma < agoraGrafico) {
          serie.push({
            ...ultimoRegistro,
            id: `fim-periodo-${plataformaAtual}-${ultimoRegistro.id}-${periodo}`,
            data_coleta: new Date(agoraGrafico).toISOString(),
            _fimPeriodo: true,
          })
        }
      }

      resultado.push(...serie)
    })

    return resultado.sort(
      (a, b) =>
        new Date(a.data_coleta).getTime() -
        new Date(b.data_coleta).getTime()
    )
  }, [historico, plataforma, periodo, agoraGrafico])

  // Todos os Hooks devem ser executados antes de qualquer retorno condicional.
  useEffect(() => {
    return () => {
      if (tooltipTimerRef.current) {
        clearTimeout(tooltipTimerRef.current)
      }
    }
  }, [])

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
  const datasHistoricoJogo = historico
    .filter((registro) => {
      const timestamp = new Date(registro.data_coleta).getTime()
      return (
        (registro.plataforma === 'Steam' || registro.plataforma === 'Epic') &&
        Number.isFinite(timestamp) &&
        timestamp <= agoraGrafico
      )
    })
    .map((registro) => new Date(registro.data_coleta).getTime())

  const primeiraDataJogo =
    datasHistoricoJogo.length > 0
      ? Math.min(...datasHistoricoJogo)
      : agoraGrafico

  const diasPeriodo = obterPeriodoEmDias(periodo)
  const fimPeriodo = agoraGrafico

  const inicioPeriodo =
    diasPeriodo === null
      ? primeiraDataJogo
      : fimPeriodo - diasPeriodo * 24 * 60 * 60 * 1000

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

    if (timestamp < new Date(dados[0].data_coleta).getTime()) {
      return null
    }

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
    if (pontoFixado) {
      return
    }

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
      setPontoSelecionado(null)
      setPosicaoTooltip(null)
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

  const obterPontosComMudanca = (dados) => {
    const pontos = []
    let ultimoPreco = null

    dados.forEach((registro) => {
      const precoAtual = Math.round(Number(registro.preco_atual) * 100)

      if (!Number.isFinite(precoAtual)) {
        return
      }

      if (ultimoPreco === null || precoAtual !== ultimoPreco) {
        if (!registro._ancoraPeriodo && !registro._fimPeriodo) {
          pontos.push(registro)
        }
        ultimoPreco = precoAtual
      }
    })

    return pontos
  }

  const pontosSteam = obterPontosComMudanca(dadosSteam)
  const pontosEpic = obterPontosComMudanca(dadosEpic)

  const fixarPonto = (registro, plataformaRegistro) => {
    if (tooltipTimerRef.current) {
      clearTimeout(tooltipTimerRef.current)
      tooltipTimerRef.current = null
    }

    const x = calcularX(registro)
    const y = calcularY(registro)

    const ponto = {
      ...registro,
      plataforma: plataformaRegistro,
    }

    setPontoFixado(ponto)
    setPontoSelecionado(ponto)
    setPosicaoTooltip({
      x: (x / largura) * 100,
      y: (y / altura) * 100,
    })

    tooltipTimerRef.current = setTimeout(() => {
      setPontoFixado(null)
      setPontoSelecionado(null)
      setPosicaoTooltip(null)
      tooltipTimerRef.current = null
    }, 5000)
  }

  const limparTooltip = () => {
    if (pontoFixado) {
      return
    }

    setPontoSelecionado(null)
    setPosicaoTooltip(null)
  }

  return (
    <div className={`grafico-container${expandido ? " grafico-expandido" : ""}`}>
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

          {pontosSteam.map((registro) => {
            const x = calcularX(registro)
            const y = calcularY(registro)

            return (
              <circle
                key={`steam-${registro.id}`}
                cx={x}
                cy={y}
                r="5"
                className="ponto-historico ponto-steam"
                onMouseEnter={() => {
                  if (pontoFixado) return
                  setPontoSelecionado(registro)
                  setPosicaoTooltip({
                    x: (x / largura) * 100,
                    y: (y / altura) * 100,
                  })
                }}
                onMouseLeave={limparTooltip}
                onClick={() => fixarPonto(registro, 'Steam')}
              />
            )
          })}

          {pontosEpic.map((registro) => {
            const x = calcularX(registro)
            const y = calcularY(registro)

            return (
              <circle
                key={`epic-${registro.id}`}
                cx={x}
                cy={y}
                r="5"
                className="ponto-historico ponto-epic"
                onMouseEnter={() => {
                  if (pontoFixado) return
                  setPontoSelecionado(registro)
                  setPosicaoTooltip({
                    x: (x / largura) * 100,
                    y: (y / altura) * 100,
                  })
                }}
                onMouseLeave={limparTooltip}
                onClick={() => fixarPonto(registro, 'Epic')}
              />
            )
          })}

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

  const { tema, setTema } = useTema()
  const { token, autenticado } = useAuth()

  useEffect(() => {
    if (!token || !autenticado || !id) return
    fetch(`${API_BASE}/api/conquistas/evento`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ evento: 'detalhes_jogo', jogo_id: Number(id) }),
    }).catch((erro) => {
      console.warn('Não foi possível registrar a visita aos detalhes para conquistas.', erro)
    })
  }, [id, token, autenticado])

  const [jogo, setJogo] = useState(null)
  const [historico, setHistorico] = useState([])
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState(null)
  const [descricaoAtual, setDescricaoAtual] = useState(null)
  const [midiaJogo, setMidiaJogo] = useState({
    screenshots: [],
    videos: [],
    epic_images: [],
  })
  const [imagemSelecionada, setImagemSelecionada] = useState(null)
  const [imagemGaleriaSelecionada, setImagemGaleriaSelecionada] = useState(null)
  const [pausarCarrossel, setPausarCarrossel] = useState(false)
  const [modalRecomendacaoAberto, setModalRecomendacaoAberto] = useState(false)
  const [salvandoRecomendacao, setSalvandoRecomendacao] = useState(false)
  const [mensagemRecomendacao, setMensagemRecomendacao] = useState(null)
  const [recomendacaoAtual, setRecomendacaoAtual] = useState(null)
  const [carregandoRecomendacao, setCarregandoRecomendacao] = useState(false)
  const [modalDenunciaAberto, setModalDenunciaAberto] = useState(false)
  const [motivoDenuncia, setMotivoDenuncia] = useState('Fora do catálogo')
  const [observacaoDenuncia, setObservacaoDenuncia] = useState('')
  const [enviandoDenuncia, setEnviandoDenuncia] = useState(false)
  const [erroDenuncia, setErroDenuncia] = useState('')

  const enviarDenuncia = async () => {
    if (!jogo?.id || enviandoDenuncia) return
    setEnviandoDenuncia(true)
    setErroDenuncia('')
    try {
      const resposta = await fetch(`${API_BASE}/api/comunidade/denuncias-jogos`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jogo_id: Number(jogo.id), motivo: motivoDenuncia, observacao: observacaoDenuncia }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível enviar a denúncia.')
      setModalDenunciaAberto(false)
      navigate('/jogos', { replace: true, state: { aviso: dados.mensagem } })
    } catch (erro) {
      setErroDenuncia(erro.message || 'Falha ao enviar denúncia.')
    } finally { setEnviandoDenuncia(false) }
  }

  const [plataforma, setPlataforma] =
    useState('ambas')

  const [periodo, setPeriodo] =
    useState('3m')
  const [graficoExpandido, setGraficoExpandido] = useState(false)
  const graficoSecaoRef = useRef(null)

  const alternarGraficoExpandido = async () => {
    const secao = graficoSecaoRef.current
    const estaExpandido = graficoExpandido

    const liberarOrientacao = () => {
      try {
        if (typeof screen !== 'undefined' && screen.orientation?.unlock) {
          screen.orientation.unlock()
        }
      } catch {
        // A liberação é opcional e não deve impedir o fechamento do gráfico.
      }
    }

    if (estaExpandido) {
      // Fecha primeiro a camada visual para que o botão X sempre responda.
      setGraficoExpandido(false)

      if (document.fullscreenElement === secao) {
        try {
          await document.exitFullscreen()
        } catch {
          // A camada CSS também permite fechar quando fullscreen não está disponível.
        }
      }

      liberarOrientacao()
      return
    }

    // A visualização expandida funciona mesmo sem suporte a fullscreen/orientação.
    setGraficoExpandido(true)

    if (!window.matchMedia('(max-width: 760px)').matches || !secao) {
      return
    }

    let fullscreenAtivado = false

    try {
      if (typeof secao.requestFullscreen === 'function') {
        await secao.requestFullscreen()
        fullscreenAtivado = document.fullscreenElement === secao
      }
    } catch {
      // Alguns navegadores recusam fullscreen. Mantemos o modo expandido em CSS.
    }

    // Só tenta bloquear a orientação depois que fullscreen foi confirmado.
    // Muitos navegadores desktop/emulados expõem lock(), mas não o suportam.
    // Nesse caso, a exceção é opcional e não afeta o gráfico.
    if (fullscreenAtivado) {
      try {
        if (
          typeof screen !== 'undefined' &&
          screen.orientation &&
          typeof screen.orientation.lock === 'function'
        ) {
          await screen.orientation.lock('landscape')
        }
      } catch (erroOrientacao) {
        // NotSupportedError e SecurityError são resultados esperados em alguns
        // navegadores. Não relançar: o modo expandido continua utilizável.
      }
    }
  }

  useEffect(() => {
    if (!graficoExpandido) return undefined

    const sincronizarFullscreen = () => {
      if (document.fullscreenElement !== graficoSecaoRef.current) {
        // Se o usuário sair do fullscreen pelo controle do navegador,
        // recolhe também a camada alternativa.
        setGraficoExpandido(false)
        try {
          if (screen.orientation?.unlock) screen.orientation.unlock()
        } catch {
          // Compatibilidade com navegadores sem Orientation API.
        }
      }
    }

    const fecharComEscape = (evento) => {
      if (evento.key === 'Escape' && !document.fullscreenElement) {
        setGraficoExpandido(false)
        try {
          if (typeof screen !== 'undefined' && screen.orientation?.unlock) {
            screen.orientation.unlock()
          }
        } catch {
          // O fechamento não depende do suporte à Orientation API.
        }
      }
    }

    document.addEventListener('fullscreenchange', sincronizarFullscreen)
    document.addEventListener('keydown', fecharComEscape)

    return () => {
      document.removeEventListener('fullscreenchange', sincronizarFullscreen)
      document.removeEventListener('keydown', fecharComEscape)
    }
  }, [graficoExpandido])

  useEffect(() => {
    const imagensGaleria = [
      ...midiaJogo.screenshots,
      ...midiaJogo.epic_images,
    ]

    if (imagensGaleria.length <= 1 || pausarCarrossel) {
      return undefined
    }

    const intervalo = setInterval(() => {
      setImagemGaleriaSelecionada((imagemAtual) => {
        if (imagensGaleria.length === 0) {
          return null
        }

        const indiceAtual = imagensGaleria.findIndex(
          (imagem) => imagem.url === imagemAtual
        )

        const proximoIndice =
          indiceAtual >= 0
            ? (indiceAtual + 1) % imagensGaleria.length
            : 0

        return imagensGaleria[proximoIndice].url
      })
    }, 10000)

    return () => clearInterval(intervalo)
  }, [midiaJogo.screenshots, midiaJogo.epic_images, pausarCarrossel])

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
    let cancelado = false

    async function carregarRecomendacaoAtual() {
      if (!token || !autenticado) {
        setRecomendacaoAtual(null)
        return
      }

      setCarregandoRecomendacao(true)
      try {
        const resposta = await fetch(`${API_BASE}/api/jogos/vitrine/minha-recomendacao`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!resposta.ok) return
        const dados = await resposta.json()
        if (!cancelado) setRecomendacaoAtual(dados.recomendacao || null)
      } catch (erro) {
        console.warn('Não foi possível consultar sua recomendação atual.', erro)
      } finally {
        if (!cancelado) setCarregandoRecomendacao(false)
      }
    }

    carregarRecomendacaoAtual()
    return () => { cancelado = true }
  }, [token, autenticado, id])

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

            const epicImages = Array.isArray(dadosMidia.epic_images)
              ? dadosMidia.epic_images
              : []

            setMidiaJogo({
              screenshots,
              videos: Array.isArray(dadosMidia.videos)
                ? dadosMidia.videos
                : [],
              epic_images: epicImages,
            })

            setImagemGaleriaSelecionada(
              screenshots[0]?.url ||
                epicImages[0]?.url ||
                null
            )
          }
        } catch (erroMidia) {
          console.warn(
            'Não foi possível obter imagens e vídeos do jogo.',
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

  const temPromocaoValida = [precoSteam, precoEpic].some((preco) =>
    Number(preco?.desconto || 0) > 0 &&
    preco?.precoAtual !== null && preco?.precoAtual !== undefined &&
    Number(preco.precoAtual) >= 0 &&
    preco.precoSemDesconto !== null && preco.precoSemDesconto !== undefined &&
    Number(preco.precoSemDesconto) > Number(preco.precoAtual)
  )

  const registrarRecomendacao = async () => {
    if (!token || !autenticado || !jogo?.id || salvandoRecomendacao) return
    setSalvandoRecomendacao(true)
    setMensagemRecomendacao(null)
    try {
      const resposta = await fetch(`${API_BASE}/api/jogos/vitrine/recomendacao`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ jogo_id: Number(jogo.id) }),
      })
      const dados = await resposta.json().catch(() => ({}))
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível registrar sua recomendação.')
      setModalRecomendacaoAberto(false)
      setRecomendacaoAtual({ jogo_id: Number(jogo.id), nome: jogo.nome, total_recomendacoes: dados.total_recomendacoes })
      setMensagemRecomendacao({ tipo: 'sucesso', texto: dados.mensagem || 'Recomendação registrada!' })
    } catch (erro) {
      setMensagemRecomendacao({ tipo: 'erro', texto: erro.message || 'Falha ao registrar recomendação.' })
    } finally {
      setSalvandoRecomendacao(false)
    }
  }

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho
        tema={tema}
        setTema={setTema}
      />

      <main className="pagina-detalhes">
        <div className="conteudo-detalhes">
          <div className="detalhes-acoes-topo">
            <button
              className="botao-voltar-detalhes"
              onClick={() => navigate(-1)}
            >
              <span className="icone-voltar-detalhes" aria-hidden="true">‹</span>
              Voltar
            </button>

            <button
              type="button"
              className="botao-reportar-detalhes"
              onClick={() => setModalDenunciaAberto(true)}
            >
              ⚑ Reportar problema com este jogo
            </button>
          </div>

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

              <h1>{jogo.nome}</h1>

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

            <button
              type="button"
              onClick={() => navigate(`/ofertas?jogo=${jogo.id}`)}
              className="ofertas-link-detalhes"
              style={{
                position: 'absolute',
                right: '40px',
                bottom: '40px',
                zIndex: 2,
                padding: 0,
                border: 'none',
                background: 'transparent',
                fontSize: '16px',
                cursor: 'pointer',
              }}
            >
              Analisar ofertas →
            </button>
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
                overflow: 'hidden',
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
                      className="botao-loja botao-loja-steam"
                    >
                      <svg className="botao-loja-icone botao-loja-icone-steam" aria-hidden="true" viewBox="0 0 24 24" fill="none"><circle cx="15.7" cy="7.1" r="4.2" stroke="currentColor" strokeWidth="1.8"/><circle cx="7.1" cy="16.7" r="3.1" stroke="currentColor" strokeWidth="1.8"/><circle cx="15.7" cy="7.1" r="1.5" stroke="currentColor" strokeWidth="1.5"/><path d="m9.8 15.1 3.3-2.2M9.3 18.4l3.5 1.4a4.2 4.2 0 0 0 5.4-2.6l1.1-3.1" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                      Ver na Steam
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
                      className="botao-loja botao-loja-epic"
                    >
                      <svg className="botao-loja-icone botao-loja-icone-epic" aria-hidden="true" viewBox="0 0 24 24"><path d="M5 3.5h14v17H5z" fill="currentColor"/><path d="M8 7h8v2H10v2h5.5v2H10v2h6v2H8z" fill="var(--fundo-card)"/></svg>
                      Ver na Epic
                    </a>
                  )}
                </article>
              </div>
            </div>
          </section>

          {temPromocaoValida && (
            <section className="recomendacao-comunidade-detalhes" style={{ margin: '24px 0', padding: '22px', border: '1px solid var(--borda-tema, rgba(128,128,128,.28))', borderRadius: '16px', background: 'var(--fundo-card, rgba(128,128,128,.06))' }}>
              {autenticado && recomendacaoAtual ? (
                <div role="status" style={{ display: 'flex', alignItems: 'flex-start', gap: '14px' }}>
                  <span aria-hidden="true" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, width: '40px', height: '40px', borderRadius: '50%', background: 'rgba(139,92,246,.16)', color: 'var(--cor-destaque, #8b5cf6)', fontSize: '21px' }}>✓</span>
                  <div>
                    <span className="eyebrow">ESCOLHA DA COMUNIDADE</span>
                    <h2 style={{ margin: '6px 0' }}>{Number(recomendacaoAtual.jogo_id) === Number(jogo.id) ? 'Você já recomendou este jogo!' : 'Você já recomendou um jogo para a comunidade!'}</h2>
                    <p style={{ margin: 0, color: 'var(--texto-secundario, inherit)', lineHeight: 1.55 }}>
                      Sua recomendação atual é <strong>{recomendacaoAtual.nome}</strong>. Ela está contando para o ranking da comunidade.
                    </p>
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '18px', flexWrap: 'wrap' }}>
                  <div>
                    <span className="eyebrow">ESCOLHA DA COMUNIDADE</span>
                    <h2 style={{ margin: '6px 0' }}>Recomende este jogo</h2>
                    <p style={{ margin: 0, color: 'var(--texto-secundario, inherit)' }}>Achou uma boa oportunidade? Indique para outras pessoas enquanto houver promoção ativa.</p>
                  </div>
                  <button type="button" onClick={() => autenticado ? setModalRecomendacaoAberto(true) : navigate('/login')} disabled={salvandoRecomendacao || carregandoRecomendacao} style={{ border: 0, borderRadius: '10px', padding: '12px 18px', fontWeight: 700, cursor: 'pointer', background: 'var(--cor-destaque, #8b5cf6)', color: '#fff' }}>
                    ♡ Recomendar jogo
                  </button>
                </div>
              )}
              {mensagemRecomendacao && <p role="status" style={{ marginBottom: 0, color: mensagemRecomendacao.tipo === 'erro' ? '#e05252' : 'var(--texto-secundario, inherit)' }}>{mensagemRecomendacao.texto}</p>}
            </section>
          )}

          {modalRecomendacaoAberto && (
            <div role="presentation" onClick={() => !salvandoRecomendacao && setModalRecomendacaoAberto(false)} style={{ position: 'fixed', inset: 0, zIndex: 1200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px', background: 'rgba(0,0,0,.68)' }}>
              <section role="dialog" aria-modal="true" aria-labelledby="confirmar-recomendacao-titulo" onClick={(evento) => evento.stopPropagation()} style={{ width: 'min(100%, 660px)', padding: 'clamp(22px, 4vw, 34px)', borderRadius: '24px', background: (tema === 'escuro' || tema === 'dark') ? '#19191f' : '#ffffff', color: (tema === 'escuro' || tema === 'dark') ? '#f4f1fb' : '#24212b', boxShadow: '0 18px 60px rgba(0,0,0,.38)', border: (tema === 'escuro' || tema === 'dark') ? '1px solid rgba(255,255,255,.08)' : '1px solid rgba(30,20,50,.10)' }}>
                <span className="eyebrow">RECOMENDAÇÃO DA COMUNIDADE</span>
                <h2 id="confirmar-recomendacao-titulo" style={{ color: 'inherit', margin: '22px 0 12px', fontSize: 'clamp(24px, 3vw, 36px)', lineHeight: 1.2 }}>Recomendar {jogo.nome}?</h2>
                <p style={{ color: (tema === 'escuro' || tema === 'dark') ? '#d0cbd9' : '#5e5968', fontSize: '17px', lineHeight: 1.55, margin: 0 }}>Você terá uma recomendação ativa por vez. Ao confirmar, ela substituirá qualquer recomendação anterior e ficará válida enquanto houver uma promoção ativa confirmada para este jogo.</p>
                {mensagemRecomendacao?.tipo === 'erro' && <p role="alert" style={{ color: '#e05252' }}>{mensagemRecomendacao.texto}</p>}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '22px', flexWrap: 'wrap' }}>
                  <button type="button" onClick={() => setModalRecomendacaoAberto(false)} disabled={salvandoRecomendacao} style={{ padding: '12px 20px', borderRadius: '11px', cursor: 'pointer', border: (tema === 'escuro' || tema === 'dark') ? '1px solid #55515e' : '1px solid #d4d0dc', background: (tema === 'escuro' || tema === 'dark') ? '#292830' : '#f2f0f5', color: (tema === 'escuro' || tema === 'dark') ? '#f4f1fb' : '#292531', fontSize: '16px' }}>Cancelar</button>
                  <button type="button" onClick={registrarRecomendacao} disabled={salvandoRecomendacao} style={{ padding: '12px 22px', border: 0, borderRadius: '11px', background: 'var(--cor-destaque, #8b5cf6)', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: '16px' }}>{salvandoRecomendacao ? 'Registrando…' : 'Confirmar recomendação'}</button>
                </div>
              </section>
            </div>
          )}

          <section ref={graficoSecaoRef} className={`historico-detalhes${graficoExpandido ? " grafico-tela-cheia" : ""}`} aria-label="Histórico de preços">
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
              <button
                type="button"
                className="botao-expandir-grafico"
                onClick={alternarGraficoExpandido}
                aria-expanded={graficoExpandido}
                aria-label={graficoExpandido ? 'Fechar visualização ampliada' : 'Abrir gráfico em tela cheia'}
              >
                {graficoExpandido ? <span aria-hidden="true">×</span> : '⛶ Tela cheia'}
              </button>
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
              expandido={graficoExpandido}
            />
          </section>

          {(() => {
            const imagensGaleria = [
              ...midiaJogo.screenshots,
              ...midiaJogo.epic_images,
            ]

            const possuiVideo = midiaJogo.videos.some(
              (video) =>
                video?.webm?.max ||
                video?.webm?.['480'] ||
                video?.mp4?.max ||
                video?.mp4?.['480']
            )

            if (imagensGaleria.length === 0 && !possuiVideo) {
              return null
            }

            const imagemPrincipal =
              imagensGaleria.find(
                (imagem) => imagem.url === imagemGaleriaSelecionada
              ) || imagensGaleria[0]

            return (
              <section className="midia-detalhes">
                {imagensGaleria.length > 0 && (
                  <div className="galeria-steam-detalhes">
                    <div className="titulo-secao-detalhes">
                      <h2>Imagens do jogo</h2>
                      <p className="dica-galeria-detalhes">Deslize as miniaturas para explorar as imagens.</p>
                    </div>

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
                        alt={`Imagem selecionada de ${jogo.nome}`}
                        loading="eager"
                        decoding="async"
                        style={{
                          display: 'block',
                          width: '100%',
                          aspectRatio: '16 / 9',
                          objectFit: 'cover',
                          borderRadius: '16px',
                          transform: 'scale(1.34)',
                        }}
                      />
                    </button>

                    <div
                      className="miniaturas-galeria-detalhes"
                      aria-label="Galeria de imagens, deslize horizontalmente para ver mais"
                      style={{
                        display: 'flex',
                        justifyContent:
                          imagensGaleria.length * 104 +
                            Math.max(imagensGaleria.length - 1, 0) * 12 +
                            8 <=
                          900
                            ? 'center'
                            : 'flex-start',
                        gap: '12px',
                        marginTop: '18px',
                        overflowX: 'auto',
                        padding: '2px 4px 8px',
                      }}
                    >
                      {imagensGaleria.map((imagem, indice) => {
                        const selecionada =
                          imagem.url === imagemPrincipal.url

                        return (
                          <button
                            key={imagem.id || `${imagem.url}-${indice}`}
                            type="button"
                            onClick={() => {
                              setImagemGaleriaSelecionada(imagem.url)
                              setPausarCarrossel(true)
                            }}
                            aria-label={`Selecionar imagem ${indice + 1}`}
                            aria-current={
                              selecionada ? 'true' : undefined
                            }
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
                              src={imagem.thumbnail || imagem.url}
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
                  </div>
                )}

                {possuiVideo && (
                  <div className="video-steam-detalhes">
                    <div className="titulo-secao-detalhes">
                      <span className="eyebrow">VÍDEO</span>
                      <h2>Trailer</h2>
                    </div>

                    {(() => {
                      const video =
                        midiaJogo.videos.find((item) => item.destaque) ||
                        midiaJogo.videos[0]

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
            )
          })()}

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

                  <div
                    className="descricao-conteudo"
                    dangerouslySetInnerHTML={{
                      __html: sanitizarDescricaoHTML(descricao.texto),
                    }}
                  />
                </article>
              </div>
            </section>
          )}

          {modalDenunciaAberto && (
            <div role="presentation" onClick={(e) => { if (e.target === e.currentTarget) setModalDenunciaAberto(false) }} style={{ position: 'fixed', inset: 0, zIndex: 2000, background: 'rgba(0,0,0,.62)', backdropFilter: 'blur(6px)', WebkitBackdropFilter: 'blur(6px)', display: 'grid', placeItems: 'center', padding: 16 }}>
              <section role="dialog" aria-modal="true" aria-labelledby="titulo-denuncia-jogo" style={{ width: 'min(100%, 480px)', background: 'var(--fundo-card, #19191d)', color: 'var(--texto-principal, #f5f5f5)', border: '1px solid var(--borda, #38383e)', borderRadius: 16, padding: 24, boxShadow: '0 20px 70px #0008' }}>
                <button type="button" onClick={() => setModalDenunciaAberto(false)} aria-label="Fechar" style={{ float: 'right', background: 'transparent', color: 'inherit', border: 0, fontSize: 22, cursor: 'pointer' }}>×</button>
                <h2 id="titulo-denuncia-jogo" style={{ marginTop: 0 }}>Reportar jogo</h2>
                <p>Informe por que <strong>{jogo?.nome}</strong> deve ser retirado do catálogo. A retirada acontece assim que a denúncia for enviada.</p>
                <label htmlFor="motivo-denuncia" style={{ display: 'block', margin: '16px 0 6px', fontWeight: 600 }}>Motivo</label>
                <select id="motivo-denuncia" value={motivoDenuncia} onChange={(e) => setMotivoDenuncia(e.target.value)} style={{ width: '100%', padding: 12, borderRadius: 8, color: 'inherit', background: 'var(--fundo-input, #202024)', border: '1px solid var(--borda, #555)' }}>
                  <option>Conteúdo sensível</option><option>Fora do catálogo</option><option>Duplicado ou redundante</option><option>Indisponível ou removido</option><option>Problemas de qualidade ou integridade</option><option>Outros</option>
                </select>
                <label htmlFor="observacao-denuncia" style={{ display: 'block', margin: '16px 0 6px', fontWeight: 600 }}>Detalhes adicionais (opcional)</label>
                <textarea id="observacao-denuncia" value={observacaoDenuncia} onChange={(e) => setObservacaoDenuncia(e.target.value)} maxLength={2000} rows={3} placeholder="Explique o problema, se quiser..." style={{ width: '100%', boxSizing: 'border-box', resize: 'vertical', padding: 12, borderRadius: 8, color: 'inherit', background: 'var(--fundo-input, #202024)', border: '1px solid var(--borda, #555)' }} />
                {erroDenuncia && <p role="alert" style={{ color: '#ff7777' }}>{erroDenuncia}</p>}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18 }}>
                  <button type="button" onClick={() => setModalDenunciaAberto(false)} style={{ padding: '10px 14px', borderRadius: 8, cursor: 'pointer' }}>Cancelar</button>
                  <button type="button" onClick={enviarDenuncia} disabled={enviandoDenuncia} style={{ padding: '10px 14px', borderRadius: 8, cursor: 'pointer' }}>{enviandoDenuncia ? 'Enviando...' : 'Denunciar e retirar jogo'}</button>
                </div>
              </section>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default DetalhesJogo