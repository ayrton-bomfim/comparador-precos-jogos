import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import './Ofertas.css'
import { API_JOGOS_URL } from '../servicos/api'
import { API_BASE, useAuth } from '../contextos/AuthContext'

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
  // Para Steam, usa diretamente a arte da loja/CDN em resolução maior,
  // evitando depender da imagem eventualmente salva no banco.
  if (jogo.steam_id) {
    return `https://cdn.akamai.steamstatic.com/steam/apps/${jogo.steam_id}/library_hero.jpg`
  }

  // Epic continua usando a URL fornecida pela origem quando disponível.
  return jogo.url_imagem_epic || jogo.url_imagem_steam || ''
}

function diasEntre(a, b) {
  const inicio = new Date(a).getTime()
  const fim = new Date(b).getTime()
  return Math.max(0, (fim - inicio) / 86400000)
}

function limitarNumero(valor, minimo, maximo) {
  return Math.min(maximo, Math.max(minimo, valor))
}

function calcularTendenciaLinear(registros, campo = 'preco_atual') {
  const pontos = registros
    .map((registro) => {
      const x = new Date(registro.data_coleta).getTime() / 86400000
      const y = Number(registro[campo])
      return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null
    })
    .filter(Boolean)

  if (pontos.length < 3) return null

  const mediaX = pontos.reduce((total, ponto) => total + ponto.x, 0) / pontos.length
  const mediaY = pontos.reduce((total, ponto) => total + ponto.y, 0) / pontos.length

  let numerador = 0
  let denominador = 0

  for (const ponto of pontos) {
    const dx = ponto.x - mediaX
    numerador += dx * (ponto.y - mediaY)
    denominador += dx * dx
  }

  if (!denominador) return null

  return numerador / denominador
}

function calcularDataMesmoPeriodo(dataHistorica, referencia) {
  if (!dataHistorica || !referencia) return null

  const origem = new Date(dataHistorica)
  const alvo = new Date(referencia)

  if (Number.isNaN(origem.getTime()) || Number.isNaN(alvo.getTime())) {
    return null
  }

  const candidato = new Date(alvo)
  candidato.setMonth(origem.getMonth(), origem.getDate())
  candidato.setHours(origem.getHours(), origem.getMinutes(), origem.getSeconds(), origem.getMilliseconds())

  if (candidato.getTime() <= alvo.getTime()) {
    candidato.setFullYear(candidato.getFullYear() + 1)
  }

  return candidato
}

function obterDataBlackFriday(ano, referencia = null) {
  const primeiroDia = new Date(ano, 10, 1)
  const diaSemana = primeiroDia.getDay()
  const primeiraSexta = 1 + ((5 - diaSemana + 7) % 7)
  const data = new Date(ano, 10, primeiraSexta + 21)

  if (referencia) {
    const base = new Date(referencia)
    data.setHours(
      base.getHours(),
      base.getMinutes(),
      base.getSeconds(),
      base.getMilliseconds()
    )
  }

  return data
}

function obterIntervalosRobustos(valores) {
  const ordenados = [...valores].filter(Number.isFinite).sort((a, b) => a - b)
  if (ordenados.length < 4) return ordenados

  const percentilLocal = (lista, proporcao) => {
    const indice = (lista.length - 1) * proporcao
    const inferior = Math.floor(indice)
    const superior = Math.ceil(indice)
    if (inferior === superior) return lista[inferior]
    return lista[inferior] + (lista[superior] - lista[inferior]) * (indice - inferior)
  }

  const q1 = percentilLocal(ordenados, 0.25)
  const q3 = percentilLocal(ordenados, 0.75)
  const iqr = q3 - q1
  const limiteInferior = q1 - 1.5 * iqr
  const limiteSuperior = q3 + 1.5 * iqr

  const filtrados = ordenados.filter(
    (valor) => valor >= limiteInferior && valor <= limiteSuperior
  )

  return filtrados.length >= 2 ? filtrados : ordenados
}

const diagnosticoAnaliseHistorico = {
  chamadas: 0,
  tempoTotal: 0,
  tempoMaximo: 0,
  registrosProcessados: 0,
}

const diagnosticoPerformance = {
  carregar: { chamadas: 0, tempoTotal: 0, etapas: {} },
  comportamentoDesenvolvedora: { chamadas: 0, tempoTotal: 0, tempoMaximo: 0 },
  resumoPromocoes: { chamadas: 0, tempoTotal: 0, tempoMaximo: 0 },
  melhoresTendencias: { chamadas: 0, tempoTotal: 0, tempoMaximo: 0 },
}

if (typeof window !== 'undefined') {
  window.__diagnosticoAnaliseHistorico = diagnosticoAnaliseHistorico
  window.__diagnosticoPerformance = diagnosticoPerformance
}

function analisarHistorico(historico, contexto = {}) {
  const inicioDiagnostico = performance.now()

  diagnosticoAnaliseHistorico.chamadas += 1
  diagnosticoAnaliseHistorico.registrosProcessados += historico.length

  const jogo = contexto.jogo || null
  const comportamentoDesenvolvedora = contexto.comportamentoDesenvolvedora || null
  const dataLancamento = jogo?.data_lancamento ? new Date(jogo.data_lancamento) : null
  const idadeJogoDias =
    dataLancamento && !Number.isNaN(dataLancamento.getTime())
      ? Math.max(0, diasEntre(dataLancamento, new Date()))
      : null

  const registros = [...historico]
    .filter(
      (registro) =>
        registro.data_coleta &&
        registro.preco_atual !== null &&
        Number.isFinite(Number(registro.preco_atual))
    )
    .sort(
      (a, b) =>
        new Date(a.data_coleta).getTime() -
        new Date(b.data_coleta).getTime()
    )

  const vazio = {
    registros: [],
    promocoes: [],
    episodios: [],
    movimentos: [],
    alteracoesPreco: [],
    aumentos: [],
    reducoes: [],
    estabilidade: true,
    estadoAtual: 'desconhecido',
    promocaoAtual: {
      ativa: false,
      inicio: null,
      fim: null,
      desconto: 0,
      nome: null,
      id: null,
    },
    precoMinimo: null,
    precoMedio: null,
    maiorDesconto: 0,
    descontoMedio: 0,
    intervalos: [],
    intervaloMedio: null,
    intervaloAlteracoes: [],
    intervaloAlteracoesMedio: null,
    diasDesdePromocao: null,
    diasDesdeAlteracao: null,
    diasEstabilidade: null,
    tendencia: 'Dados insuficientes',
    nivel: 'insuficiente',
    faixaPreco: null,
    faixaDesconto: null,
    pontuacao: 0,
    confianca: 0,
    previsao: {
      tipo: 'insuficiente',
      rotulo: 'Dados insuficientes',
      janelaInicio: null,
      janelaFim: null,
      dataEstimada: null,
      precoEstimado: null,
      descontoEstimado: null,
      explicacao: 'Ainda não há histórico suficiente para estimar o próximo comportamento.',
    },
  }

  if (registros.length === 0) {
    const tempoDiagnostico = performance.now() - inicioDiagnostico

    diagnosticoAnaliseHistorico.tempoTotal += tempoDiagnostico
    diagnosticoAnaliseHistorico.tempoMaximo = Math.max(
      diagnosticoAnaliseHistorico.tempoMaximo,
      tempoDiagnostico
    )

    return vazio
  }

  const agora = new Date()
  const promocoes = registros.filter(
    (registro) => Number(registro.desconto || 0) > 0
  )

  // As promoções mais recentes têm peso adicional na estimativa do desconto.
  // Mantemos isso no mesmo escopo de `promocoes` para evitar referências
  // inexistentes durante a execução da análise.
  const promocoesRecentes = promocoes.slice(-6)

  const precoMinimo = Math.min(
    ...registros.map((registro) => Number(registro.preco_atual))
  )

  const precoMedio =
    registros.reduce(
      (total, registro) => total + Number(registro.preco_atual),
      0
    ) / registros.length

  const maiorDesconto = promocoes.length
    ? Math.max(
        ...promocoes.map((registro) => Number(registro.desconto || 0))
      )
    : 0

  const descontoMedio = promocoes.length
    ? promocoes.reduce(
        (total, registro) => total + Number(registro.desconto || 0),
        0
      ) / promocoes.length
    : 0

  const episodios = []

  for (const registro of promocoes) {
    const ultimo = episodios[episodios.length - 1]

    if (
      !ultimo ||
      diasEntre(ultimo[ultimo.length - 1].data_coleta, registro.data_coleta) >
        14
    ) {
      episodios.push([registro])
    } else {
      ultimo.push(registro)
    }
  }

  const intervalos = []

  for (let i = 1; i < episodios.length; i += 1) {
    intervalos.push(
      diasEntre(
        episodios[i - 1][0].data_coleta,
        episodios[i][0].data_coleta
      )
    )
  }

  const intervaloMedio = intervalos.length
    ? intervalos.reduce((total, valor) => total + valor, 0) / intervalos.length
    : null

  /*
   * Período normal entre duas promoções:
   *
   *   fim da promoção A -> início da promoção B
   *
   * Quando a base possui promocao_fim/promocao_inicio, usamos essas datas.
   * Caso contrário, usamos a última observação promocional da primeira
   * ocorrência e a primeira observação da ocorrência seguinte. Isso permite
   * estimar quanto tempo o jogo costuma permanecer em preço normal.
   */
  const intervalosNormais = []

  for (let i = 1; i < episodios.length; i += 1) {
    const episodioAnterior = episodios[i - 1]
    const episodioSeguinte = episodios[i]

    const ultimaAnterior = episodioAnterior[episodioAnterior.length - 1]
    const primeiraSeguinte = episodioSeguinte[0]

    const fimAnterior = ultimaAnterior?.promocao_fim
      ? new Date(ultimaAnterior.promocao_fim)
      : null
    const inicioSeguinte = primeiraSeguinte?.promocao_inicio
      ? new Date(primeiraSeguinte.promocao_inicio)
      : null

    const dataInicioNormal =
      fimAnterior && !Number.isNaN(fimAnterior.getTime())
        ? fimAnterior
        : new Date(ultimaAnterior.data_coleta)

    const dataFimNormal =
      inicioSeguinte && !Number.isNaN(inicioSeguinte.getTime())
        ? inicioSeguinte
        : new Date(primeiraSeguinte.data_coleta)

    const intervaloNormal = diasEntre(dataInicioNormal, dataFimNormal)

    if (intervaloNormal > 0) {
      intervalosNormais.push(intervaloNormal)
    }
  }

  const intervaloNormalMedio = intervalosNormais.length
    ? intervalosNormais.reduce((total, valor) => total + valor, 0) /
      intervalosNormais.length
    : null

  // Estatísticas dos períodos normais observados:
  // fim da promoção anterior -> início da próxima promoção.
  const intervalosNormaisOrdenados = [...intervalosNormais].sort(
    (a, b) => a - b
  )

  const obterMediana = (valores) => {
    if (!valores.length) return null

    const meio = Math.floor(valores.length / 2)

    return valores.length % 2 === 0
      ? (valores[meio - 1] + valores[meio]) / 2
      : valores[meio]
  }

  const intervalosNormaisRobustos = obterIntervalosRobustos(intervalosNormaisOrdenados)
  const intervaloNormalMediano = obterMediana(intervalosNormaisRobustos)
  const intervaloNormalMinimo = intervalosNormaisRobustos.length
    ? intervalosNormaisRobustos[0]
    : null
  const intervaloNormalMaximo = intervalosNormaisRobustos.length
    ? intervalosNormaisRobustos[intervalosNormaisRobustos.length - 1]
    : null

  /*
   * Duração média das promoções. Ela serve apenas como fallback quando a
   * promoção atual não possui uma data de término informada pela loja.
   */
  const duracoesPromocoes = episodios
    .map((episodio) => {
      const primeiro = episodio[0]
      const ultimo = episodio[episodio.length - 1]

      const inicio = primeiro?.promocao_inicio
        ? new Date(primeiro.promocao_inicio)
        : new Date(primeiro?.data_coleta)
      const fim = ultimo?.promocao_fim
        ? new Date(ultimo.promocao_fim)
        : new Date(ultimo?.data_coleta)

      if (Number.isNaN(inicio.getTime()) || Number.isNaN(fim.getTime())) {
        return null
      }

      const duracao = diasEntre(inicio, fim)
      return duracao > 0 ? duracao : null
    })
    .filter((valor) => valor !== null)

  const duracaoPromocaoMedia = duracoesPromocoes.length
    ? duracoesPromocoes.reduce((total, valor) => total + valor, 0) /
      duracoesPromocoes.length
    : null

  const ultimaPromocao = promocoes.length
    ? promocoes[promocoes.length - 1]
    : null

  const diasDesdePromocao = ultimaPromocao
    ? diasEntre(ultimaPromocao.data_coleta, agora)
    : null

  const alteracoesPreco = []
  const movimentos = []
  const aumentos = []
  const reducoes = []

  for (let i = 1; i < registros.length; i += 1) {
    const anterior = registros[i - 1]
    const atual = registros[i]

    const precoAnterior = Number(anterior.preco_atual)
    const precoAtual = Number(atual.preco_atual)

    if (!Number.isFinite(precoAnterior) || !Number.isFinite(precoAtual)) {
      continue
    }

    const delta = Math.round((precoAtual - precoAnterior) * 100) / 100
    const dataAlteracao = atual.data_coleta

    if (delta === 0) continue

    const movimento = {
      anterior,
      atual,
      delta,
      data: dataAlteracao,
      direcao: delta > 0 ? 'aumento' : 'reducao',
    }

    movimentos.push(movimento)
    alteracoesPreco.push(atual)

    if (delta > 0) aumentos.push(movimento)
    else reducoes.push(movimento)
  }

  const intervaloAlteracoes = []

  for (let i = 1; i < alteracoesPreco.length; i += 1) {
    intervaloAlteracoes.push(
      diasEntre(
        alteracoesPreco[i - 1].data_coleta,
        alteracoesPreco[i].data_coleta
      )
    )
  }

  const intervaloAlteracoesMedio = intervaloAlteracoes.length
    ? intervaloAlteracoes.reduce((total, valor) => total + valor, 0) /
      intervaloAlteracoes.length
    : null

  const ultimaAlteracao = alteracoesPreco.length
    ? alteracoesPreco[alteracoesPreco.length - 1]
    : null

  const referenciaEstabilidade =
    ultimaAlteracao?.data_coleta || registros[0].data_coleta

  const diasDesdeAlteracao = referenciaEstabilidade
    ? diasEntre(referenciaEstabilidade, agora)
    : null

  const diasEstabilidade = diasDesdeAlteracao

  const ultimoRegistro = registros[registros.length - 1]
  const descontoAtual = Number(ultimoRegistro.desconto || 0)

  /*
   * A API pode trazer coletas posteriores sem promocao_fim, mesmo quando
   * outra coleta da mesma promoção já informou a data de término.
   *
   * Por isso, para determinar a promoção atual, não usamos somente o último
   * registro. Procuramos o término válido mais recente entre os registros
   * promocionais que ainda pertencem ao estado atual.
   */
  const episodioAtual = episodios[episodios.length - 1] || []

  const promocoesAtuaisCandidatas = episodioAtual
    .filter((registro) => {
      const fim = registro.promocao_fim
        ? new Date(registro.promocao_fim)
        : null

      return (
        Number(registro.desconto || 0) > 0 &&
        fim &&
        !Number.isNaN(fim.getTime()) &&
        fim.getTime() > agora.getTime()
      )
    })
    .sort(
      (a, b) =>
        new Date(a.promocao_fim).getTime() -
        new Date(b.promocao_fim).getTime()
    )

  const registroPromocaoAtual =
    promocoesAtuaisCandidatas[promocoesAtuaisCandidatas.length - 1] ||
    (descontoAtual > 0 ? ultimoRegistro : null)

  const fimPromocaoAtual = registroPromocaoAtual?.promocao_fim
    ? new Date(registroPromocaoAtual.promocao_fim)
    : null

  const fimPromocaoValido =
    Boolean(fimPromocaoAtual) &&
    !Number.isNaN(fimPromocaoAtual.getTime()) &&
    fimPromocaoAtual.getTime() > agora.getTime()

  const promocaoAtualAtiva = descontoAtual > 0

  const promocaoAtual =
    promocaoAtualAtiva
      ? {
          ativa: true,
          inicio:
            registroPromocaoAtual?.promocao_inicio ||
            ultimoRegistro.promocao_inicio ||
            ultimoRegistro.data_coleta,
          fim:
            fimPromocaoValido
              ? fimPromocaoAtual.toISOString()
              : null,
          desconto: descontoAtual,
          nome:
            registroPromocaoAtual?.promocao_nome ||
            ultimoRegistro.promocao_nome ||
            null,
          id:
            registroPromocaoAtual?.promocao_id ||
            ultimoRegistro.promocao_id ||
            null,
        }
      : {
          ativa: false,
          inicio: null,
          fim: null,
          desconto: 0,
          nome: null,
          id: null,
        }

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

  // Tendência de preço promocional: o próprio jogo é a principal fonte
  // de evidência para prever o próximo valor.
  const obterPrecoMedianoDeEpisodio = (episodio) => {
    const precos = episodio
      .map((registro) => Number(registro.preco_atual))
      .filter(Number.isFinite)
      .sort((a, b) => a - b)

    return precos.length ? percentil(precos, 0.5) : null
  }

  const representantesEpisodios = episodios
    .map((episodio) => {
      const preco = obterPrecoMedianoDeEpisodio(episodio)
      return preco !== null
        ? {
            data_coleta: episodio[0]?.data_coleta,
            preco_atual: preco,
          }
        : null
    })
    .filter(Boolean)

  const tendenciaPrecoPromocionalPorDia = calcularTendenciaLinear(
    representantesEpisodios,
    'preco_atual'
  )

  const representantesRecentes = representantesEpisodios.slice(-4)
  const precosPromocionaisPorEpisodio = representantesEpisodios
    .map((registro) => Number(registro.preco_atual))
    .filter(Number.isFinite)
    .sort((a, b) => a - b)

  const precoPromocionalMediano = percentil(
    precosPromocionaisPorEpisodio,
    0.5
  )
  const precoPromocionalRecente = representantesRecentes.length
    ? percentil(
        representantesRecentes
          .map((registro) => Number(registro.preco_atual))
          .filter(Number.isFinite)
          .sort((a, b) => a - b),
        0.5
      )
    : null

  // Sazonalidade: procura episódios anteriores que retornam em época
  // semelhante do ano e projeta a mesma época para o próximo ciclo anual.
  const referenciaSazonal =
    fimPromocaoAtual && fimPromocaoAtual.getTime() > agora.getTime()
      ? fimPromocaoAtual
      : agora
  const datasSazonais = []
  const episodiosHistoricos = promocaoAtual.ativa
    ? episodios.slice(0, Math.max(0, episodios.length - 1))
    : episodios

  for (const episodio of episodiosHistoricos) {
    const inicio = episodio?.[0]?.data_coleta
    const candidato = calcularDataMesmoPeriodo(inicio, referenciaSazonal)
    if (!candidato) continue

    const distanciaDias = diasEntre(referenciaSazonal, candidato)
    // Consideramos os próximos seis meses, permitindo que campanhas
    // sazonais se desloquem algumas semanas entre anos.
    if (distanciaDias >= 0 && distanciaDias <= 180) {
      datasSazonais.push(candidato)
    }
  }

  /*
   * Black Friday é tratada como um evento sazonal explícito, mas somente
   * quando o próprio histórico da plataforma mostra recorrência suficiente.
   *
   * Isso evita transformar a Black Friday em uma promoção obrigatória para
   * qualquer jogo. Para este jogo, por exemplo, a Steam possui ocorrências
   * promocionais próximas à Black Friday em 2024 e 2025, enquanto a Epic
   * não possui a mesma evidência no histórico fornecido.
   */
  const blackFridayAtual = obterDataBlackFriday(
    referenciaSazonal.getFullYear(),
    referenciaSazonal
  )

  const blackFridayOcorrencias = episodiosHistoricos.filter((episodio) => {
    const inicio = episodio?.[0]?.data_coleta
    if (!inicio) return false

    const dataInicio = new Date(inicio)
    if (Number.isNaN(dataInicio.getTime())) return false

    const blackFridayHistorica = obterDataBlackFriday(
      dataInicio.getFullYear(),
      dataInicio
    )

    return Math.abs(
      dataInicio.getTime() - blackFridayHistorica.getTime()
    ) <= 14 * 86400000
  }).length

  const blackFridayForte = blackFridayOcorrencias >= 2

  if (
    blackFridayForte &&
    blackFridayAtual.getTime() > referenciaSazonal.getTime() &&
    diasEntre(referenciaSazonal, blackFridayAtual) <= 180
  ) {
    datasSazonais.push(blackFridayAtual)
  }

  const datasSazonaisOrdenadas = datasSazonais.sort(
    (a, b) => a.getTime() - b.getTime()
  )
  const sazonalidadeForte = datasSazonaisOrdenadas.length >= 2
  const dataSazonalMediana = sazonalidadeForte
    ? new Date(
        obterMediana(datasSazonaisOrdenadas.map((data) => data.getTime()))
      )
    : datasSazonaisOrdenadas.length === 1
      ? datasSazonaisOrdenadas[0]
      : null

  const comportamentoDesenvolvedoraValido =
    comportamentoDesenvolvedora &&
    Number(comportamentoDesenvolvedora.jogosAnalisados) > 0

  const sinalDesenvolvedora = comportamentoDesenvolvedoraValido
    ? limitarNumero(Number(comportamentoDesenvolvedora.descontoMedio || 0), 0, 100)
    : null

  const descontoHistoricoJogo = promocoes.length
    ? promocoes.reduce((total, registro) => total + Number(registro.desconto || 0), 0) /
      promocoes.length
    : null

  const descontoRecente = promocoesRecentes.length
    ? promocoesRecentes.reduce(
        (total, registro) => total + Number(registro.desconto || 0),
        0
      ) / promocoesRecentes.length
    : null

  const idadeJogoAnos = idadeJogoDias !== null ? idadeJogoDias / 365.25 : null

  const descontoIdadeAjustado =
    descontoHistoricoJogo !== null &&
    idadeJogoAnos !== null &&
    promocoes.length >= 3
      ? limitarNumero(
          descontoHistoricoJogo +
            limitarNumero(idadeJogoAnos - 3, -3, 5) * 1.5,
          0,
          100
        )
      : null

  const descontoEstimativaBase =
    descontoHistoricoJogo !== null
      ? descontoHistoricoJogo * 0.65 +
        (descontoRecente ?? descontoHistoricoJogo) * 0.25 +
        (descontoIdadeAjustado ?? descontoHistoricoJogo) * 0.1
      : null

  const descontoEstimativaComContexto =
    descontoEstimativaBase !== null
      ? limitarNumero(
          descontoEstimativaBase * 0.8 +
            (sinalDesenvolvedora !== null ? sinalDesenvolvedora * 0.2 : descontoEstimativaBase * 0.2),
          0,
          100
        )
      : null

  const descontoInferiorBase =
    descontoEstimativaComContexto !== null
      ? Math.max(0, Math.round(descontoEstimativaComContexto * 0.85))
      : Math.max(0, Math.round(descontoMedio * 0.8))
  const descontoSuperiorBase =
    descontoEstimativaComContexto !== null
      ? Math.min(100, Math.round(descontoEstimativaComContexto * 1.15))
      : Math.min(100, Math.round(Math.max(maiorDesconto, descontoMedio * 1.15)))

  const descontoInferior = descontoInferiorBase
  const descontoSuperior = descontoSuperiorBase

  const totalMovimentos = movimentos.length
  const proporcaoAumentos = totalMovimentos
    ? aumentos.length / totalMovimentos
    : 0

  const periodoHistoricoDias = diasEntre(
    registros[0].data_coleta,
    registros[registros.length - 1].data_coleta
  )

  /*
   * Confiança baseada na quantidade de observações e na existência de
   * mudanças de preço/promoções. O valor serve apenas para ordenar os cards
   * iniciais da página; não representa probabilidade estatística.
   */
  let confianca = 0

  if (registros.length >= 3) confianca += 20
  if (registros.length >= 6) confianca += 15
  if (totalMovimentos >= 2) confianca += 20
  if (totalMovimentos >= 4) confianca += 10
  if (episodios.length >= 2) confianca += 15
  if (periodoHistoricoDias >= 60) confianca += 10
  if (totalMovimentos > 0 && (aumentos.length > 0 || reducoes.length > 0)) {
    confianca += 10
  }

  confianca = Math.min(100, confianca)

  const historicoSuficiente =
    registros.length >= 3 &&
    (totalMovimentos >= 2 || episodios.length >= 2 || periodoHistoricoDias >= 45)

  const aumentosConsistentes =
    aumentos.length >= 2 &&
    proporcaoAumentos >= 0.6

  const estadoAtual = promocaoAtual.ativa ? 'promocao' : 'normal'

  const ultimoPreco = Number(ultimoRegistro.preco_atual)

  let tipoPrevisao = 'insuficiente'
  let rotuloPrevisao = 'Dados insuficientes'
  let janelaInicio = null
  let janelaFim = null
  let dataEstimada = null
  let precoEstimado = null
  let descontoEstimado = null
  let explicacao =
    'Ainda não há histórico suficiente para estimar o próximo comportamento.'

  // Essas referências são usadas tanto quando a promoção está ativa quanto
  // quando projetamos uma próxima promoção. Por isso precisam ficar no
  // escopo da análise inteira, e não dentro de um único `if`.
  const precoBase = Number(ultimoRegistro.preco_sem_desconto)

  const registrosForaPromocao = registros
    .filter((registro) => Number(registro.desconto || 0) === 0)
    .map((registro) => Number(registro.preco_atual))
    .filter(Number.isFinite)

  const precoNormalHistorico = registrosForaPromocao.length
    ? percentil([...registrosForaPromocao].sort((a, b) => a - b), 0.5)
    : null

  /*
   * 1) Promoção ativa: a próxima transição de estado é NORMAL.
   *
   * Importante: a previsão de "próxima promoção" só deve ser calculada
   * depois que a promoção atual terminar. Caso contrário, a interface acaba
   * sugerindo uma transição Promoção -> Promoção, o que mistura duas etapas
   * diferentes do ciclo de preço.
   */
  if (promocaoAtual.ativa) {
    tipoPrevisao = 'fim_promocao'
    rotuloPrevisao = 'Preço normal'

    const dataFimConhecido = promocaoAtual.fim
      ? new Date(promocaoAtual.fim)
      : null

    const fimConhecido =
      Boolean(dataFimConhecido) &&
      !Number.isNaN(dataFimConhecido.getTime()) &&
      dataFimConhecido.getTime() > agora.getTime()

    const inicioPromocaoAtual = promocaoAtual.inicio
      ? new Date(promocaoAtual.inicio)
      : null

    const fimPromocaoEstimado =
      !fimConhecido &&
      inicioPromocaoAtual &&
      !Number.isNaN(inicioPromocaoAtual.getTime()) &&
      duracaoPromocaoMedia !== null
        ? new Date(
            inicioPromocaoAtual.getTime() +
              duracaoPromocaoMedia * 86400000
          )
        : null

    const fimParaPrevisao = fimConhecido
      ? dataFimConhecido
      : fimPromocaoEstimado && fimPromocaoEstimado.getTime() > agora.getTime()
        ? fimPromocaoEstimado
        : null

    if (fimParaPrevisao) {
      const inicioNormal = fimParaPrevisao

      if (
        intervaloNormalMediano !== null &&
        intervaloNormalMinimo !== null &&
        intervaloNormalMaximo !== null
      ) {
        /*
         * A janela não usa mais o maior intervalo bruto observado.
         * Intervalos extremos são filtrados por IQR e, quando existe
         * recorrência anual, a sazonalidade recebe peso relevante.
         */
        const minimoNormal = Math.max(7, Math.round(intervaloNormalMinimo))
        const maximoNormal = Math.max(
          minimoNormal + 7,
          Math.round(intervaloNormalMaximo)
        )
        const medianaNormal = Math.max(
          minimoNormal,
          Math.min(maximoNormal, Math.round(intervaloNormalMediano))
        )

        const dataPorIntervalo = new Date(
          inicioNormal.getTime() + medianaNormal * 86400000
        )

        if (blackFridayForte) {
          // Quando há recorrência da própria plataforma próxima à Black Friday,
          // o evento sazonal passa a ter prioridade sobre um intervalo médio
          // que poderia empurrar artificialmente a previsão para o fim do ano.
          const pesoBlackFriday = 0.75
          dataEstimada = new Date(
            dataPorIntervalo.getTime() * (1 - pesoBlackFriday) +
              blackFridayAtual.getTime() * pesoBlackFriday
          )
        } else if (dataSazonalMediana) {
          const pesoSazonal = sazonalidadeForte ? 0.65 : 0.4
          dataEstimada = new Date(
            dataPorIntervalo.getTime() * (1 - pesoSazonal) +
              dataSazonalMediana.getTime() * pesoSazonal
          )
        } else {
          dataEstimada = dataPorIntervalo
        }

        /*
         * A transição conhecida acontece no fim da promoção atual.
         * A janela visual, portanto, precisa começar exatamente nessa data.
         * A sazonalidade pode influenciar a data estimada da próxima promoção,
         * mas não pode deslocar o início da transição Promoção -> Preço normal.
         */
        const centroJanela = dataEstimada.getTime()
        const larguraJanela = sazonalidadeForte
          ? Math.max(14, Math.round(Math.max(7, maximoNormal - minimoNormal) * 0.75))
          : Math.max(14, Math.round((maximoNormal - minimoNormal) * 0.5))

        janelaInicio = inicioNormal
        janelaFim = new Date(
          Math.min(
            inicioNormal.getTime() + maximoNormal * 86400000,
            centroJanela + larguraJanela * 86400000
          )
        )
      } else {
        janelaInicio = inicioNormal
        janelaFim = inicioNormal
        dataEstimada = inicioNormal
      }
    }

    /*
     * A data acima representa o término da promoção atual e o início do
     * período de preço normal. Porém, o card da interface está mostrando
     * "Próxima promoção estimada". Portanto, o preço exibido junto dessa
     * data deve ser o preço PROMOCIONAL esperado, e não o preço normal.
     *
     * Usamos o histórico promocional do próprio jogo como principal referência.
     */
    const precoPromocionalBase =
      precoPromocionalMediano !== null
        ? precoPromocionalMediano * 0.7 +
          (precoPromocionalRecente ?? precoPromocionalMediano) * 0.3
        : null

    let precoPromocionalEstimado = precoPromocionalBase

    if (
      precoPromocionalEstimado !== null &&
      Number.isFinite(tendenciaPrecoPromocionalPorDia)
    ) {
      const diasParaProximaPromocao = Math.max(
        1,
        diasEntre(agora, dataEstimada || agora)
      )

      const ajusteTendencia = limitarNumero(
        tendenciaPrecoPromocionalPorDia * diasParaProximaPromocao,
        -precoPromocionalEstimado * 0.2,
        precoPromocionalEstimado * 0.2
      )

      precoPromocionalEstimado += ajusteTendencia
    }

    if (
      precoPromocionalEstimado !== null &&
      precoInferior !== null &&
      precoSuperior !== null
    ) {
      const piso = Math.min(precoInferior, precoPromocionalEstimado * 0.9)
      const teto = Math.max(precoSuperior, precoPromocionalEstimado * 1.1)

      precoPromocionalEstimado = limitarNumero(
        precoPromocionalEstimado,
        piso,
        teto
      )
    }

    // O preço normal continua disponível como referência, mas não é o valor
    // mostrado no card de "Próxima promoção estimada".
    // Em promoção ativa, priorizamos a mediana dos registros realmente
    // fora de promoção. Isso evita usar `preco_sem_desconto` de um registro
    // promocional como se ele fosse o preço normal.
    const precoNormalReferencia =
      Number.isFinite(precoNormalHistorico) && precoNormalHistorico > 0
        ? precoNormalHistorico
        : Number.isFinite(precoBase) && precoBase > 0
          ? precoBase
          : null

    const descontoProximaPromocao =
      descontoEstimativaComContexto !== null
        ? Math.round(descontoEstimativaComContexto)
        : null

    if (
      Number.isFinite(precoNormalReferencia) &&
      Number.isFinite(descontoProximaPromocao)
    ) {
      const precoPorDesconto =
        Math.round(
          precoNormalReferencia *
            (1 - descontoProximaPromocao / 100) *
            100
        ) / 100

      if (precoPromocionalEstimado === null) {
        precoPromocionalEstimado = precoPorDesconto
      } else {
        // O histórico do próprio jogo continua dominante; o desconto
        // previsto serve como conferência de consistência.
        precoPromocionalEstimado =
          Math.round(
            (precoPromocionalEstimado * 0.8 + precoPorDesconto * 0.2) * 100
          ) / 100
      }
    }

    precoEstimado = precoPromocionalEstimado

    // O percentual exibido deve ser calculado a partir do preço promocional
    // efetivamente previsto e do preço normal de referência. Isso mantém
    // preço e desconto coerentes no tooltip/card, mesmo quando o preço
    // promocional foi ajustado pela tendência ou pela sazonalidade.
    if (
      Number.isFinite(precoNormalReferencia) &&
      Number.isFinite(precoEstimado) &&
      precoNormalReferencia > 0
    ) {
      descontoEstimado = Math.max(
        0,
        Math.min(100, Math.round((1 - precoEstimado / precoNormalReferencia) * 100))
      )
    }

    explicacao = fimConhecido
      ? intervaloNormalMedio !== null
        ? 'A promoção atual ainda está ativa. A próxima alteração prevista é o retorno ao preço normal na data de término registrada; depois disso, a próxima promoção é estimada a partir dos períodos normais observados. O preço exibido corresponde ao valor promocional esperado para essa próxima promoção.'
        : 'A promoção atual ainda está ativa. A próxima alteração prevista é o retorno ao preço normal na data de término registrada. Não há histórico suficiente entre promoções para estimar com precisão a próxima data, mas o preço exibido usa o histórico de preços promocionais do próprio jogo.'
      : fimPromocaoEstimado
        ? intervaloNormalMedio !== null
          ? 'A data de término da promoção atual foi estimada a partir da duração histórica das promoções. Depois dela, a janela representa o período normal observado entre promoções anteriores e se encerra quando a próxima promoção começar.'
          : 'A data de término da promoção atual foi estimada a partir da duração histórica das promoções, mas não há histórico suficiente entre promoções para estimar o período normal.'
        : 'A promoção atual ainda está ativa. Não há uma data de término válida nem histórico suficiente para estimar sua duração; por isso, não foi inventada uma janela.'
  } else if (historicoSuficiente && aumentosConsistentes) {
    /*
     * 2) Aumento: exige ao menos duas altas e predominância de movimentos
     * ascendentes para evitar classificar um histórico oscilante como alta.
     */
    tipoPrevisao = 'aumento'
    rotuloPrevisao = 'Aumento'
    const baseIntervalo = intervaloAlteracoesMedio || 30
    const restante = Math.max(
      0,
      baseIntervalo - (diasDesdeAlteracao || 0)
    )
    const minimo = Math.max(1, Math.round(restante * 0.5))
    const maximo = Math.max(minimo + 7, Math.round(restante * 1.25))

    janelaInicio = new Date(agora.getTime() + minimo * 86400000)
    janelaFim = new Date(agora.getTime() + maximo * 86400000)
    dataEstimada = new Date(
      janelaInicio.getTime() + (janelaFim.getTime() - janelaInicio.getTime()) / 2
    )

    const aumentosRecentes = aumentos.slice(-3)
    const aumentoMedio = aumentosRecentes.length
      ? aumentosRecentes.reduce((total, item) => total + item.delta, 0) /
        aumentosRecentes.length
      : 0

    precoEstimado =
      Math.round((ultimoPreco + Math.max(0, aumentoMedio)) * 100) / 100

    explicacao =
      'Os últimos movimentos apresentam aumentos recorrentes e predominantes no histórico, por isso a próxima alteração foi classificada como possível aumento.'
  } else if (
    historicoSuficiente &&
    episodios.length >= 2 &&
    intervaloMedio !== null
  ) {
    /*
     * 3) Promoção recorrente: usa somente o comportamento entre episódios
     * promocionais, preservando a distinção em relação a intervalos de preço.
     */
    tipoPrevisao = 'promocao'
    rotuloPrevisao = 'Promoção'
    const baseIntervalo = intervaloNormalMediano || intervaloMedio || 30
    const restante = Math.max(7, baseIntervalo - (diasDesdePromocao || 0))
    const minimo = Math.max(7, Math.round(restante * 0.65))
    const maximo = Math.max(minimo + 14, Math.round(restante * 1.35))

    const dataPorIntervalo = new Date(agora.getTime() + restante * 86400000)
    if (dataSazonalMediana) {
      const pesoSazonal = sazonalidadeForte ? 0.65 : 0.4
      dataEstimada = new Date(
        dataPorIntervalo.getTime() * (1 - pesoSazonal) +
          dataSazonalMediana.getTime() * pesoSazonal
      )
    } else {
      dataEstimada = dataPorIntervalo
    }

    janelaInicio = new Date(
      Math.max(
        agora.getTime() + minimo * 86400000,
        dataEstimada.getTime() - 21 * 86400000
      )
    )
    janelaFim = new Date(
      Math.min(
        agora.getTime() + maximo * 86400000,
        dataEstimada.getTime() + 21 * 86400000
      )
    )

    // O próprio jogo domina a previsão de preço. A desenvolvedora só
    // complementa quando há contexto suficiente, e a tendência temporal
    // ajusta o centro quando existe sinal consistente de queda/alta.
    const precoHistoricoBase =
      precoPromocionalMediano !== null
        ? precoPromocionalMediano * 0.7 +
          (precoPromocionalRecente ?? precoPromocionalMediano) * 0.3
        : null

    let precoAjustado = precoHistoricoBase

    if (precoAjustado !== null && Number.isFinite(tendenciaPrecoPromocionalPorDia)) {
      const diasParaPrevisao = Math.max(1, diasEntre(agora, dataEstimada || agora))
      const ajusteTendencia = limitarNumero(
        tendenciaPrecoPromocionalPorDia * diasParaPrevisao,
        -precoAjustado * 0.2,
        precoAjustado * 0.2
      )
      precoAjustado += ajusteTendencia
    }

    if (precoAjustado !== null && precoInferior !== null && precoSuperior !== null) {
      // A faixa histórica funciona como âncora para impedir extrapolações
      // excessivas. Só permitimos uma pequena adaptação fora dela quando há
      // tendência temporal consistente.
      const piso = Math.min(precoInferior, precoAjustado * 0.9)
      const teto = Math.max(precoSuperior, precoAjustado * 1.1)
      precoEstimado = limitarNumero(precoAjustado, piso, teto)
    } else {
      precoEstimado = precoAjustado
    }

    descontoEstimado =
      descontoEstimativaComContexto !== null
        ? Math.round(descontoEstimativaComContexto)
        : descontoSuperior > 0
          ? Math.round((descontoInferior + descontoSuperior) / 2)
          : null

    // Se houver preço-base conhecido, o desconto previsto e o preço previsto
    // precisam permanecer coerentes entre si.
    const precoNormalReferencia =
      Number.isFinite(precoNormalHistorico) && precoNormalHistorico > 0
        ? precoNormalHistorico
        : Number.isFinite(precoBase) && precoBase > 0
          ? precoBase
          : null

    if (
      Number.isFinite(precoNormalReferencia) &&
      Number.isFinite(descontoEstimado)
    ) {
      const precoPorDesconto =
        Math.round(
          precoNormalReferencia * (1 - descontoEstimado / 100) * 100
        ) / 100

      if (precoEstimado === null) {
        precoEstimado = precoPorDesconto
      } else {
        // O histórico do próprio jogo continua dominante; o cálculo pelo
        // desconto serve apenas para conferir consistência.
        precoEstimado =
          Math.round((precoEstimado * 0.8 + precoPorDesconto * 0.2) * 100) / 100
      }
    }

    // Depois do ajuste final do preço, recalculamos o desconto para que o
    // percentual mostrado corresponda exatamente ao valor previsto.
    if (
      Number.isFinite(precoNormalReferencia) &&
      Number.isFinite(precoEstimado) &&
      precoNormalReferencia > 0
    ) {
      descontoEstimado = Math.max(
        0,
        Math.min(100, Math.round((1 - precoEstimado / precoNormalReferencia) * 100))
      )
    }

    explicacao =
      `O histórico do próprio jogo é a principal referência para o preço. A previsão combina o padrão promocional, o comportamento recente e uma eventual tendência temporal; sazonalidade, idade e desenvolvedora entram como fatores complementares.`
  } else if (
    historicoSuficiente &&
    totalMovimentos < 2 &&
    (diasEstabilidade || 0) >= 30
  ) {
    /*
     * 4) Estabilidade: poucas alterações e um período longo sem mudança de
     * preço. A previsão representa manutenção do preço, e não uma promessa
     * de ausência de mudança futura.
     */
    tipoPrevisao = 'estabilidade'
    rotuloPrevisao = 'Estabilidade'
    const minimo = 7
    const maximo = 30

    janelaInicio = new Date(agora.getTime() + minimo * 86400000)
    janelaFim = new Date(agora.getTime() + maximo * 86400000)
    dataEstimada = new Date(
      janelaInicio.getTime() + (janelaFim.getTime() - janelaInicio.getTime()) / 2
    )
    precoEstimado = ultimoPreco

    explicacao =
      'O histórico apresenta poucas alterações de preço e um período prolongado sem mudança. O comportamento esperado no curto prazo é de estabilidade.'
  } else if (historicoSuficiente && totalMovimentos >= 2) {
    /*
     * 5) Histórico com oscilações, mas sem padrão dominante: estabilidade é
     * a classificação neutra quando não há evidência suficiente para alta
     * ou promoção recorrente.
     */
    tipoPrevisao = 'estabilidade'
    rotuloPrevisao = 'Estabilidade'
    const baseIntervalo = intervaloAlteracoesMedio || 30
    const minimo = Math.max(7, Math.round(baseIntervalo * 0.25))
    const maximo = Math.max(minimo + 7, Math.round(baseIntervalo * 0.75))

    janelaInicio = new Date(agora.getTime() + minimo * 86400000)
    janelaFim = new Date(agora.getTime() + maximo * 86400000)
    dataEstimada = new Date(
      janelaInicio.getTime() + (janelaFim.getTime() - janelaInicio.getTime()) / 2
    )
    precoEstimado = ultimoPreco

    explicacao =
      'Há alterações no histórico, mas nenhum padrão dominante de promoção recorrente ou aumento consistente. A estimativa neutra é de estabilidade.'
  }

  const tendencia =
    tipoPrevisao === 'promocao' || tipoPrevisao === 'fim_promocao'
      ? 'Promoção'
      : tipoPrevisao === 'aumento'
        ? 'Aumento'
        : tipoPrevisao === 'estabilidade'
          ? 'Estabilidade'
          : 'Dados insuficientes'

  const nivel =
    tipoPrevisao === 'promocao' || tipoPrevisao === 'fim_promocao'
      ? 'promocao'
      : tipoPrevisao === 'aumento'
        ? 'aumento'
        : tipoPrevisao === 'estabilidade'
          ? 'estabilidade'
          : 'insuficiente'

  const precoNormalEstimado =
    Number.isFinite(precoBase) && precoBase > 0
      ? precoBase
      : precoNormalHistorico

  /*
   * Normalização final da janela de previsão.
   *
   * Todas as regras acima calculam a data estimada e a janela a partir de
   * referências diferentes (intervalo, sazonalidade, término da promoção,
   * etc.). Em alguns cenários, a data estimada pode cair fora dos limites
   * usados para montar a janela. Isso não pode chegar à interface, porque
   * produziria uma janela invertida (ex.: 03/11 -> 22/10).
   *
   * A regra final é simples: início <= data estimada <= fim. A janela nunca
   * começa no passado e, se houver conflito entre as restrições, ela é
   * ajustada para preservar a própria data estimada da previsão.
   */
  if (janelaInicio && janelaFim && dataEstimada) {
    const agoraMs = agora.getTime()
    let inicioMs = new Date(janelaInicio).getTime()
    let fimMs = new Date(janelaFim).getTime()
    let estimadaMs = new Date(dataEstimada).getTime()

    if (
      Number.isFinite(inicioMs) &&
      Number.isFinite(fimMs) &&
      Number.isFinite(estimadaMs)
    ) {
      // A estimativa precisa ser futura e a janela precisa contê-la.
      estimadaMs = Math.max(estimadaMs, agoraMs)
      inicioMs = Math.max(inicioMs, agoraMs)

      if (estimadaMs < inicioMs) {
        inicioMs = estimadaMs
      }

      if (estimadaMs > fimMs) {
        fimMs = estimadaMs
      }

      // Proteção final contra qualquer combinação que ainda resulte em
      // datas invertidas.
      if (fimMs < inicioMs) {
        fimMs = inicioMs
      }

      janelaInicio = new Date(inicioMs)
      janelaFim = new Date(fimMs)
      dataEstimada = new Date(estimadaMs)
    }
  }

  const previsao = {
    tipo: tipoPrevisao,
    rotulo: rotuloPrevisao,
    janelaInicio: janelaInicio ? janelaInicio.toISOString() : null,
    janelaFim: janelaFim ? janelaFim.toISOString() : null,
    dataEstimada: dataEstimada ? dataEstimada.toISOString() : null,
    precoEstimado,
    precoNormalEstimado,
    descontoEstimado,
    explicacao,
    sazonalidade: {
      ocorrencias: datasSazonaisOrdenadas.length,
      forte: sazonalidadeForte,
      dataEstimada: dataSazonalMediana
        ? dataSazonalMediana.toISOString()
        : null,
      blackFriday: {
        ocorrencias: blackFridayOcorrencias,
        forte: blackFridayForte,
        dataEstimada: blackFridayForte
          ? blackFridayAtual.toISOString()
          : null,
      },
    },
    idadeJogoAnos,
    tendenciaPrecoPromocionalPorDia,
    precoPromocionalMediano,
    precoPromocionalRecente,
    duracaoPromocaoMedia,
  }

  const tempoDiagnostico = performance.now() - inicioDiagnostico

  diagnosticoAnaliseHistorico.tempoTotal += tempoDiagnostico
  diagnosticoAnaliseHistorico.tempoMaximo = Math.max(
    diagnosticoAnaliseHistorico.tempoMaximo,
    tempoDiagnostico
  )

  return {
    registros,
    promocoes,
    episodios,
    movimentos,
    alteracoesPreco,
    aumentos,
    reducoes,
    estabilidade: totalMovimentos === 0,
    estadoAtual,
    promocaoAtual,
    precoMinimo,
    precoMedio,
    maiorDesconto,
    descontoMedio,
    intervalos,
    intervaloMedio,
    intervalosNormais,
    intervalosNormaisRobustos,
    intervaloNormalMedio,
    sazonalidade: {
      ocorrencias: datasSazonaisOrdenadas.length,
      forte: sazonalidadeForte,
      dataEstimada: dataSazonalMediana
        ? dataSazonalMediana.toISOString()
        : null,
      blackFriday: {
        ocorrencias: blackFridayOcorrencias,
        forte: blackFridayForte,
        dataEstimada: blackFridayForte
          ? blackFridayAtual.toISOString()
          : null,
      },
    },
    idadeJogoDias,
    idadeJogoAnos,
    periodoHistoricoDias,
    precoPromocionalMediano,
    precoPromocionalRecente,
    tendenciaPrecoPromocionalPorDia,
    intervaloAlteracoes,
    intervaloAlteracoesMedio,
    diasDesdePromocao,
    diasDesdeAlteracao,
    diasEstabilidade,
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
    pontuacao: confianca,
    confianca,
    previsao,
  }
}
function obterResumoPromocoesPorPlataforma(historico) {
  const inicioDiagnostico = performance.now()
  diagnosticoPerformance.resumoPromocoes.chamadas += 1

  const resultado = ['Steam', 'Epic'].map((plataforma) => {
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

  const tempoDiagnostico = performance.now() - inicioDiagnostico
  diagnosticoPerformance.resumoPromocoes.tempoTotal += tempoDiagnostico
  diagnosticoPerformance.resumoPromocoes.tempoMaximo = Math.max(
    diagnosticoPerformance.resumoPromocoes.tempoMaximo,
    tempoDiagnostico
  )

  return resultado
}

function calcularComportamentoDesenvolvedora(
  jogo,
  jogos,
  historicos,
  plataforma = 'ambas'
) {
  const inicioDiagnostico = performance.now()
  diagnosticoPerformance.comportamentoDesenvolvedora.chamadas += 1

  const nomeNormalizado = (jogo?.publicadora || '').trim().toLowerCase()

  if (!nomeNormalizado) {
    return {
      nome: 'Publicadora não informada',
      suficiente: false,
      caracteristicas: [],
      meses: Array(12).fill(0),
      jogosEmPromocao: [],
      jogosAcompanhar: [],
      mesesDestaque: [],
      totalJogos: 0,
      totalPromocoes: 0,
    }
  }

  const jogosDaPublicadora = jogos.filter(
    (item) =>
      (item.publicadora || '').trim().toLowerCase() === nomeNormalizado
  )

  const usarPlataforma = (registro) =>
    plataforma === 'ambas' || registro.plataforma === plataforma

  const dados = jogosDaPublicadora
    .map((item) => {
      const historico = (historicos[item.id] || []).filter(usarPlataforma)
      const analise = analisarHistorico(historico)
      return { jogo: item, historico, analise }
    })
    .filter(({ analise }) => analise.registros.length > 0)

  const meses = Array(12).fill(0)
  let totalPromocoes = 0
  let totalDesconto = 0
  let totalRegistrosPromocionais = 0
  const intervalos = []
  const jogosEmPromocao = []
  const jogosAcompanhar = []

  dados.forEach(({ jogo: item, historico, analise }) => {
    const promocoes = analise.promocoes || []
    totalPromocoes += promocoes.length
    totalDesconto += promocoes.reduce(
      (total, registro) => total + Number(registro.desconto || 0),
      0
    )
    totalRegistrosPromocionais += promocoes.length

    ;(analise.episodios || []).forEach((episodio) => {
      const inicio = episodio?.[0]?.data_coleta
      const data = inicio ? new Date(inicio) : null
      if (data && !Number.isNaN(data.getTime())) meses[data.getMonth()] += 1
    })

    ;(analise.intervalos || []).forEach((valor) => {
      if (Number.isFinite(Number(valor))) intervalos.push(Number(valor))
    })

    const descontoAtual = plataforma === 'Steam'
      ? Number(item.desconto_steam || 0)
      : plataforma === 'Epic'
        ? Number(item.desconto_epic || 0)
        : Math.max(
            Number(item.desconto_steam || 0),
            Number(item.desconto_epic || 0)
          )

    const plataformasAtivas =
      plataforma === 'Steam'
        ? Number(item.desconto_steam || 0) > 0
          ? ['Steam']
          : []
        : plataforma === 'Epic'
          ? Number(item.desconto_epic || 0) > 0
            ? ['Epic']
            : []
          : [
              Number(item.desconto_steam || 0) > 0 ? 'Steam' : null,
              Number(item.desconto_epic || 0) > 0 ? 'Epic' : null,
            ].filter(Boolean)

    const detalhesPromocao = plataformasAtivas.map((nomePlataforma) => {
      const registrosPlataforma = (historicos[item.id] || [])
        .filter((registro) => registro.plataforma === nomePlataforma)
        .sort(
          (a, b) =>
            new Date(b.data_coleta).getTime() -
            new Date(a.data_coleta).getTime()
        )

      const registroAtual = registrosPlataforma.find(
        (registro) => Number(registro.desconto || 0) > 0
      )

      const fimValido = registrosPlataforma
        .map((registro) =>
          registro.promocao_fim ? new Date(registro.promocao_fim) : null
        )
        .filter(
          (data) =>
            data &&
            !Number.isNaN(data.getTime()) &&
            data.getTime() > Date.now()
        )
        .sort((a, b) => a.getTime() - b.getTime())[0]

      const precoAtual =
        nomePlataforma === 'Steam'
          ? Number(item.preco_atual_steam)
          : Number(item.preco_atual_epic)

      return {
        plataforma: nomePlataforma,
        desconto:
          nomePlataforma === 'Steam'
            ? Number(item.desconto_steam || 0)
            : Number(item.desconto_epic || 0),
        precoAtual: Number.isFinite(precoAtual) ? precoAtual : null,
        promocaoNome:
          registroAtual?.promocao_nome || 'Promoção',
        fimPromocao: fimValido ? fimValido.toISOString() : null,
      }
    })

    const estaEmPromocaoAgora = detalhesPromocao.length > 0

    if (estaEmPromocaoAgora) {
      jogosEmPromocao.push({
        ...item,
        desconto: descontoAtual,
        plataformasEmPromocao: detalhesPromocao,
        promocaoNome:
          detalhesPromocao[0]?.promocaoNome || 'Promoção',
      })
    } else {
      // Só entra em "Jogos para acompanhar" quando a análise do próprio
      // jogo possui histórico suficiente para prever uma próxima promoção
      // e também produziu um desconto estimado.
      const previsaoPromocao =
        analise.previsao?.tipo === 'promocao' &&
        Number.isFinite(Number(analise.previsao?.descontoEstimado)) &&
        Number(analise.previsao.descontoEstimado) > 0

      if (previsaoPromocao) {
        jogosAcompanhar.push({
          ...item,
          descontoPrevisto: Number(analise.previsao.descontoEstimado),
          confiancaPrevisao: Number.isFinite(Number(analise.confianca))
            ? Number(analise.confianca)
            : 0,
          dataPrevista: analise.previsao?.dataEstimada || null,
          precoPrevisto: Number.isFinite(Number(analise.previsao?.precoEstimado))
            ? Number(analise.previsao.precoEstimado)
            : null,
          plataformasAnalisadas:
            plataforma === 'ambas'
              ? [
                  historico.some((registro) => registro.plataforma === 'Steam')
                    ? 'Steam'
                    : null,
                  historico.some((registro) => registro.plataforma === 'Epic')
                    ? 'Epic'
                    : null,
                ].filter(Boolean)
              : [plataforma],
          diasDesdePromocao: Number.isFinite(Number(analise.diasDesdePromocao))
            ? Number(analise.diasDesdePromocao)
            : null,
          intervaloMedio: Number.isFinite(Number(analise.intervaloMedio))
            ? Number(analise.intervaloMedio)
            : null,
        })
      }
    }
  })

  const descontoMedio = totalRegistrosPromocionais
    ? totalDesconto / totalRegistrosPromocionais
    : 0

  const intervaloMedio = intervalos.length
    ? intervalos.reduce((total, valor) => total + valor, 0) / intervalos.length
    : null

  const maiorMes = Math.max(...meses)
  const mesesDestaque = maiorMes > 0
    ? meses
        .map((quantidade, indice) => ({ quantidade, indice }))
        .filter((item) => item.quantidade === maiorMes)
        .map((item) =>
          [
            'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
            'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
          ][item.indice]
        )
    : []

  const caracteristicas = []
  const jogosComHistorico = dados.filter(({ analise }) => analise.promocoes?.length > 0).length

  if (descontoMedio >= 50) caracteristicas.push('Descontos elevados')
  else if (descontoMedio >= 30) caracteristicas.push('Descontos relevantes')

  if (jogosComHistorico >= 2 && totalPromocoes >= jogosComHistorico * 2) {
    caracteristicas.push('Promoções recorrentes')
  }

  if (maiorMes > 0 && mesesDestaque.length > 0) {
    caracteristicas.push(
      mesesDestaque.length === 1
        ? `Maior atividade em ${mesesDestaque[0]}`
        : `Maior atividade em ${mesesDestaque.slice(0, 2).join(' e ')}`
    )
  }

  const mesesAtivos = meses.filter((quantidade) => quantidade > 0).length
  if (mesesAtivos >= 8) caracteristicas.push('Promoções regulares')
  else if (mesesAtivos >= 4) caracteristicas.push('Promoções sazonais')

  const descontosPorRegistro = dados.flatMap(({ analise }) =>
    (analise.promocoes || []).map((registro) => Number(registro.desconto || 0))
  )
  if (descontosPorRegistro.length >= 3) {
    const menor = Math.min(...descontosPorRegistro)
    const maior = Math.max(...descontosPorRegistro)
    if (maior - menor >= 40) caracteristicas.push('Alta variação de desconto')
  }

  if (!caracteristicas.length && dados.length > 0) {
    caracteristicas.push('Histórico sem padrão dominante')
  }

  // Primeiro vem o maior desconto previsto. A confiança da previsão
  // funciona como desempate; depois usamos a proximidade relativa ao
  // intervalo histórico da última promoção.
  jogosAcompanhar.sort((a, b) => {
    const descontoA = Number(a.descontoPrevisto || 0)
    const descontoB = Number(b.descontoPrevisto || 0)

    if (descontoB !== descontoA) {
      return descontoB - descontoA
    }

    const confiancaA = Number(a.confiancaPrevisao || 0)
    const confiancaB = Number(b.confiancaPrevisao || 0)

    if (confiancaB !== confiancaA) {
      return confiancaB - confiancaA
    }

    const aScore = a.intervaloMedio && a.diasDesdePromocao
      ? a.diasDesdePromocao / a.intervaloMedio
      : -1
    const bScore = b.intervaloMedio && b.diasDesdePromocao
      ? b.diasDesdePromocao / b.intervaloMedio
      : -1

    return bScore - aScore
  })

  const tempoDiagnostico = performance.now() - inicioDiagnostico
  diagnosticoPerformance.comportamentoDesenvolvedora.tempoTotal += tempoDiagnostico
  diagnosticoPerformance.comportamentoDesenvolvedora.tempoMaximo = Math.max(
    diagnosticoPerformance.comportamentoDesenvolvedora.tempoMaximo,
    tempoDiagnostico
  )

  return {
    nome: jogo.publicadora,
    suficiente: dados.length > 0 && totalPromocoes > 0,
    caracteristicas,
    meses,
    mesesDestaque,
    jogosEmPromocao: jogosEmPromocao.slice(0, 2),
    jogosAcompanhar: jogosAcompanhar.slice(0, 3),
    totalJogos: dados.length,
    totalPromocoes,
    descontoMedio,
    intervaloMedio,
  }
}


function obterTextoPrevisao(analise) {
  if (!analise) return 'Selecione uma plataforma para visualizar a previsão.'

  if (analise.nivel === 'promocao') {
    if (analise.previsao?.tipo === 'fim_promocao') {
      if (analise.promocaoAtual?.fim) {
        const fim = new Date(analise.promocaoAtual.fim)
        const data = formatarDataGrafico(fim)
        const horario = new Intl.DateTimeFormat('pt-BR', {
          hour: '2-digit',
          minute: '2-digit',
        }).format(fim)

        return `A promoção atual está em andamento e termina em ${data}, às ${horario}. Após isso, o preço tende a retornar ao valor normal.`
      }

      if (analise.previsao?.janelaInicio) {
        const fimEstimado = new Date(analise.previsao.janelaInicio)
        const dias = Math.max(
          1,
          Math.round(diasEntre(new Date(), fimEstimado))
        )

        return `A promoção atual está em andamento e deve terminar em cerca de ${dias} dias. Após isso, o preço tende a retornar ao valor normal.`
      }

      return 'A promoção atual está em andamento, mas não há uma data de término válida nem histórico suficiente para estimar sua duração.'
    }

    return 'O histórico indica um padrão de promoções recorrentes. Esse comportamento é usado como principal referência para estimar a próxima promoção.'
  }

  if (analise.nivel === 'aumento') {
    return 'Os movimentos recentes apresentam aumentos recorrentes e predominantes, indicando uma possível continuidade desse comportamento.'
  }

  if (analise.nivel === 'estabilidade') {
    if (
      analise.registros?.length >= 3 &&
      analise.movimentos?.length < 2 &&
      (analise.diasEstabilidade || 0) >= 30
    ) {
      return 'O preço apresentou poucas alterações e permaneceu estável por um período prolongado.'
    }

    return 'O histórico apresenta alterações de preço, mas não há um padrão predominante de promoções ou aumentos. Por isso, a estimativa atual considera a estabilidade.'
  }

  return 'Ainda não há histórico suficiente para identificar um padrão de comportamento ou estimar a próxima alteração de preço.'
}

function obterTextoPrevisaoAmbas(resumo) {
  const disponiveis = (resumo || []).filter((item) => item.disponivel && item.analise)

  if (disponiveis.length === 0) {
    return 'Ainda não há histórico suficiente em nenhuma das plataformas para identificar um padrão de comportamento.'
  }

  if (disponiveis.length === 1) {
    const item = disponiveis[0]
    const outro = resumo.find((plataforma) => plataforma.plataforma !== item.plataforma)
    const tendencia = item.analise.tendencia

    if (outro && !outro.disponivel) {
      return `${item.plataforma} apresenta ${tendencia.toLowerCase()} como tendência, enquanto o histórico da ${outro.plataforma} ainda é insuficiente para uma estimativa.`
    }
  }

  const steam = resumo.find((item) => item.plataforma === 'Steam')
  const epic = resumo.find((item) => item.plataforma === 'Epic')

  if (!steam?.disponivel || !epic?.disponivel) {
    const disponivel = steam?.disponivel ? steam : epic
    const indisponivel = steam?.disponivel ? epic : steam

    return `${disponivel.plataforma} apresenta ${disponivel.analise.tendencia.toLowerCase()} como tendência, enquanto o histórico da ${indisponivel.plataforma} ainda é insuficiente para uma estimativa.`
  }

  const steamPromocao = steam.analise.promocaoAtual?.ativa
  const epicPromocao = epic.analise.promocaoAtual?.ativa

  if (steamPromocao && epicPromocao) {
    return 'O jogo está em promoção nas duas plataformas no momento.'
  }

  if (steamPromocao !== epicPromocao) {
    const promocao = steamPromocao ? steam : epic
    const normal = steamPromocao ? epic : steam
    const tendenciaNormal = normal.analise.tendencia

    if (tendenciaNormal === 'Promoção') {
      return `O jogo está em promoção na ${promocao.plataforma}, enquanto a ${normal.plataforma} mantém o preço normal e apresenta tendência de promoção.`
    }

    return `O jogo está em promoção na ${promocao.plataforma}, enquanto a ${normal.plataforma} mantém o preço normal. Os históricos indicam comportamentos diferentes entre as plataformas.`
  }

  const tendenciaSteam = steam.analise.tendencia
  const tendenciaEpic = epic.analise.tendencia

  if (tendenciaSteam === tendenciaEpic) {
    if (tendenciaSteam === 'Promoção') {
      return 'O jogo está em preço normal nas duas plataformas, e ambas apresentam tendência de promoção.'
    }

    if (tendenciaSteam === 'Aumento') {
      return 'As duas plataformas estão em preço normal e apresentam uma possível continuidade de aumentos.'
    }

    if (tendenciaSteam === 'Estabilidade') {
      return 'O preço está normal nas duas plataformas, sem indicação de um padrão dominante de promoção ou aumento no curto prazo.'
    }

    return 'O histórico das duas plataformas ainda é insuficiente para identificar um padrão de comportamento.'
  }

  if (tendenciaSteam === 'Dados insuficientes') {
    return `As plataformas apresentam comportamentos diferentes: a Steam ainda não possui histórico suficiente para uma estimativa, enquanto a Epic indica ${tendenciaEpic.toLowerCase()}.`
  }

  if (tendenciaEpic === 'Dados insuficientes') {
    return `As plataformas apresentam comportamentos diferentes: a Steam indica ${tendenciaSteam.toLowerCase()}, enquanto a Epic ainda não possui histórico suficiente para uma estimativa.`
  }

  return `As plataformas apresentam comportamentos diferentes: a Steam indica ${tendenciaSteam.toLowerCase()}, enquanto a Epic apresenta ${tendenciaEpic.toLowerCase()}.`
}

function formatarJanelaPrevisao(previsao) {
  if (!previsao?.janelaInicio || !previsao?.janelaFim) return 'Sem estimativa'

  const inicio = formatarDataGrafico(previsao.janelaInicio)
  const fim = formatarDataGrafico(previsao.janelaFim)

  if (inicio === fim) return inicio

  return `${inicio} – ${fim}`
}

function formatarDataGrafico(data) {
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  }).format(new Date(data))
}

function formatarDataEixoGrafico(data, periodo) {
  const opcoes =
    periodo === '30d' || periodo === '3m'
      ? { day: '2-digit', month: 'short' }
      : { month: 'short', year: '2-digit' }

  return new Intl.DateTimeFormat('pt-BR', opcoes)
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

function filtrarRegistrosReaisPorPeriodo(historico, periodo) {
  if (!historico.length) return historico

  const dias = obterDiasPeriodoGrafico(periodo)
  const agora = Date.now()

  return historico.filter((registro) => {
    const data = new Date(registro.data_coleta).getTime()

    if (!Number.isFinite(data) || data > agora) return false
    if (dias === null) return true

    return data >= agora - dias * 86400000
  })
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

  const agora = Date.now()
  const dataInicial = agora - dias * 86400000
  const plataformas = [
    ...new Set(
      historico
        .map((registro) => registro.plataforma)
        .filter((plataforma) => plataforma === 'Steam' || plataforma === 'Epic')
    ),
  ]

  const dadosPeriodo = []

  /*
   * O histórico é orientado a mudanças: enquanto o preço permanece igual,
   * não criamos um novo registro. Por isso, uma plataforma pode não ter
   * nenhum registro dentro do recorte e ainda assim ter permanecido com
   * aquele preço durante todo o período.
   *
   * Para representar esse comportamento corretamente, cada plataforma
   * recebe sua própria âncora: o último estado conhecido antes do início do
   * período é reposicionado exatamente na borda inicial do gráfico.
   */
  for (const plataforma of plataformas) {
    const registrosPlataforma = historico
      .filter((registro) => registro.plataforma === plataforma)
      .sort(
        (a, b) =>
          new Date(a.data_coleta).getTime() -
          new Date(b.data_coleta).getTime()
      )

    if (registrosPlataforma.length === 0) continue

    const registroAnterior = [...registrosPlataforma]
      .reverse()
      .find(
        (registro) =>
          new Date(registro.data_coleta).getTime() < dataInicial
      )

    if (registroAnterior) {
      dadosPeriodo.push({
        ...registroAnterior,
        id: `ancora-ofertas-${plataforma}-${registroAnterior.id}-${periodo}`,
        data_coleta: new Date(dataInicial).toISOString(),
        _ancoraPeriodo: true,
      })
    }

    dadosPeriodo.push(
      ...registrosPlataforma.filter(
        (registro) =>
          new Date(registro.data_coleta).getTime() >= dataInicial
      )
    )
  }

  return dadosPeriodo.sort(
    (a, b) =>
      new Date(a.data_coleta).getTime() -
      new Date(b.data_coleta).getTime()
  )
}


function calcularPrevisaoParaGrafico(analise, periodo, agora) {
  const previsao = analise?.previsao

  if (
    !previsao ||
    !previsao.janelaInicio ||
    !previsao.janelaFim ||
    previsao.tipo === 'insuficiente'
  ) {
    return null
  }

  const janelaInicioBruta = new Date(previsao.janelaInicio).getTime()
  const janelaFimBruta = new Date(previsao.janelaFim).getTime()
  if (
    !Number.isFinite(janelaInicioBruta) ||
    !Number.isFinite(janelaFimBruta) ||
    janelaFimBruta <= agora
  ) {
    return null
  }

  return {
    // O gráfico usa exclusivamente os limites da janela provável.
    // `dataEstimada` continua disponível para os cards, mas não participa
    // da geometria da previsão.
    inicio: Math.max(agora, janelaInicioBruta),
    fim: janelaFimBruta,
    data: Math.max(agora, janelaInicioBruta),
    dataEstimada: previsao.dataEstimada || null,
    dataFimPromocao: null,
    dataInicio: new Date(janelaInicioBruta),
    dataFim: new Date(janelaFimBruta),
    dataPrevisao: new Date(janelaInicioBruta),
    proximaPromocaoDentroDoFiltro: true,
  }
}

function GraficoHistoricoOfertas({
  historico,
  plataforma,
  onPlataformaChange,
  periodo,
  onPeriodoChange,
  jogo,
  comportamentoDesenvolvedora,
}) {
  const [pontoSelecionado, setPontoSelecionado] = useState(null)
  const [graficoExpandido, setGraficoExpandido] = useState(false)
  const [pontosFixados, setPontosFixados] = useState([])
  const tooltipTimersRef = useRef(new Map())
  const [agoraAtual] = useState(() => Date.now())
  const [previsaoSelecionada, setPrevisaoSelecionada] = useState(null)
  const [previsaoTooltipMouse, setPrevisaoTooltipMouse] = useState(null)
  const [previsaoFixada, setPrevisaoFixada] = useState(null)
  const previsaoTimerRef = useRef(null)

  useEffect(() => {
    const timers = tooltipTimersRef.current
    return () => {
      for (const timer of timers.values()) {
        clearTimeout(timer)
      }
      timers.clear()
      if (previsaoTimerRef.current) {
        clearTimeout(previsaoTimerRef.current)
        previsaoTimerRef.current = null
      }
    }
  }, [])

  useEffect(() => {
    if (!graficoExpandido) return undefined

    const fecharComEscape = (evento) => {
      if (evento.key === 'Escape') setGraficoExpandido(false)
    }

    document.addEventListener('keydown', fecharComEscape)
    document.body.classList.add('grafico-tela-cheia-ofertas')

    return () => {
      document.removeEventListener('keydown', fecharComEscape)
      document.body.classList.remove('grafico-tela-cheia-ofertas')
    }
  }, [graficoExpandido])

  const alternarGraficoExpandido = () => {
    if (!window.matchMedia('(max-width: 760px)').matches) return
    setGraficoExpandido((atual) => !atual)
  }


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

  /*
   * A previsão não depende do recorte visual selecionado.
   * Ela usa todo o histórico disponível da(s) plataforma(s) ativas,
   * evitando que 30 dias / 3 meses / 6 meses escondam a previsão
   * apenas porque o recorte possui poucos registros.
   */
  const analisesPrevisao = useMemo(
    () => ({
      Steam: analisarHistorico(
        obterHistoricoPorPlataforma(historico, 'Steam'),
        { jogo, comportamentoDesenvolvedora }
      ),
      Epic: analisarHistorico(
        obterHistoricoPorPlataforma(historico, 'Epic'),
        { jogo, comportamentoDesenvolvedora }
      ),
    }),
    [historico, jogo, comportamentoDesenvolvedora]
  )

  const grafico = useMemo(() => {
    if (dados.length < 1) return null

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

    const nomesPrevisao =
      plataformaAtiva === 'ambas'
        ? ['Steam', 'Epic']
        : [plataformaAtiva]

    const previsoesBase = nomesPrevisao
      .map((nome) => {
        const analisePlataforma = analisesPrevisao[nome]

        const previsaoBase = calcularPrevisaoParaGrafico(
          analisePlataforma,
          periodo,
          agora
        )

        if (!previsaoBase) return null

        const ultimoRegistro =
          analisePlataforma.registros[
            analisePlataforma.registros.length - 1
          ]

        const precoAtualGrafico = Number(ultimoRegistro?.preco_atual)

        const precoPrevisto =
          Number.isFinite(analisePlataforma.previsao.precoEstimado)
            ? analisePlataforma.previsao.precoEstimado
            : precoAtualGrafico

        const precoNormalGrafico =
          Number.isFinite(analisePlataforma.previsao.precoNormalEstimado)
            ? analisePlataforma.previsao.precoNormalEstimado
            : null

        // O desconto exibido na previsão precisa ser derivado do mesmo
        // preço normal e do mesmo preço promocional que o gráfico utiliza.
        // Assim evitamos mostrar, por exemplo, 0% para um preço de R$ 19,19.
        const descontoPrevistoGrafico =
          Number.isFinite(precoNormalGrafico) &&
          precoNormalGrafico > 0 &&
          Number.isFinite(precoPrevisto)
            ? Math.max(
                0,
                Math.min(
                  100,
                  Math.round((1 - precoPrevisto / precoNormalGrafico) * 100)
                )
              )
            : null

        return {
          plataforma: nome,
          ...previsaoBase,
          precoAtual: precoAtualGrafico,
          precoPrevisto: Number.isFinite(precoPrevisto)
            ? precoPrevisto
            : null,
          descontoPrevisto: descontoPrevistoGrafico,
          descontoAtual: Number.isFinite(analisePlataforma.descontoAtual)
            ? analisePlataforma.descontoAtual
            : 0,
          precoNormal: precoNormalGrafico,
          dataEstimada: analisePlataforma.previsao.dataEstimada || null,
          tipo: analisePlataforma.previsao.tipo,
          rotulo: analisePlataforma.previsao.rotulo,
          explicacao: analisePlataforma.previsao.explicacao,
        }
      })
      .filter(Boolean)

    const horizonteFiltroDias = obterDiasPeriodoGrafico(periodo)

    /*
     * O domínio do gráfico agora é temporal de verdade:
     *   início do filtro -> hoje -> fim do filtro.
     *
     * A previsão usa exatamente esse mesmo eixo. Assim, quando existe uma
     * alteração futura dentro do período, a linha chega até a data da
     * alteração, sobe/desce verticalmente e continua no novo preço.
     * Se não existe alteração dentro do período, aí sim ela permanece reta
     * até o final do horizonte.
     */
    const inicio =
      horizonteFiltroDias !== null
        ? agora - horizonteFiltroDias * 86400000
        : Math.min(historicoInicio, agora)

    const fimPrevisaoMaximo = previsoesBase.length
      ? Math.max(...previsoesBase.map((item) => item.fim))
      : agora

    const fimFiltro =
      horizonteFiltroDias !== null
        ? agora + horizonteFiltroDias * 86400000
        : Math.max(historicoFim, agora, fimPrevisaoMaximo)

    /*
     * Quando uma janela de previsão termina antes do limite do filtro, não
     * deixamos uma faixa vazia depois dela. O gráfico termina na última
     * previsão efetivamente desenhada. Isso preserva a janela temporal da
     * previsão e faz o eixo ocupar toda a largura disponível.
     *
     * Se a previsão ultrapassa o filtro, continuamos respeitando o filtro.
     */
    const finsPrevisaoNoFiltro = previsoesBase
      .map((item) => Number(item.fim))
      .filter(
        (valor) =>
          Number.isFinite(valor) &&
          valor > agora &&
          valor <= fimFiltro
      )

    const fim =
      finsPrevisaoNoFiltro.length > 0
        ? Math.max(agora, ...finsPrevisaoNoFiltro)
        : fimFiltro

    const todosPrecos = dados.map((registro) => Number(registro.preco_atual))
    const precosPrevisao = previsoesBase
      .map((item) => item.precoPrevisto)
      .filter(Number.isFinite)
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

    const calcularX = (data) => {
      const timestamp = new Date(data).getTime()
      const proporcao =
        (timestamp - inicio) / Math.max(fim - inicio, 1)

      return margem.esquerda +
        limitarNumero(proporcao, 0, 1) * areaLargura
    }

    const calcularY = (preco) =>
      margem.topo +
      (1 - (preco - minimo) / Math.max(maximo - minimo, 1)) * areaAltura

    const previsoesAtivas = previsoesBase.map((item) => {
      const dataTransicaoNormal =
        item.tipo === 'fim_promocao' && Number.isFinite(Number(item.inicio))
          ? Number(item.inicio)
          : null

      // A mudança visual acontece no INÍCIO da janela provável.
      // A data estimada central não é usada no gráfico.
      const dataProximaAlteracao = Number.isFinite(Number(item.inicio))
        ? Number(item.inicio)
        : null

      const dataFimPromocao = Number.isFinite(Number(item.fim))
        ? Number(item.fim)
        : null

      const dentroDoHorizonte = (timestamp) =>
        Number.isFinite(timestamp) && timestamp > agora && timestamp <= fim

      const xAtual = calcularX(agora)
      const xFim = calcularX(fim)

      // Cada previsão tem seu próprio fim de janela. O eixo global pode
      // continuar mais à frente por causa de outra plataforma, mas a linha
      // desta previsão nunca deve ultrapassar a própria janela calculada.
      const fimPrevisaoTimestamp = Number(item.fim)
      const fimPrevisaoVisual = Number.isFinite(fimPrevisaoTimestamp)
        ? Math.min(fimPrevisaoTimestamp, fim)
        : fim
      const xFimPrevisao = calcularX(fimPrevisaoVisual)

      const yAtual = Number.isFinite(item.precoAtual)
        ? calcularY(item.precoAtual)
        : null
      const yPrevisto = Number.isFinite(item.precoPrevisto)
        ? calcularY(item.precoPrevisto)
        : null
      const yNormal = Number.isFinite(item.precoNormal)
        ? calcularY(item.precoNormal)
        : null

      const segmentos = []
      const transicoes = []

      const adicionarHorizontal = (x1, x2, y, tipo, dataInicio, dataFim) => {
        if (!Number.isFinite(y) || x2 <= x1) return
        segmentos.push({
          tipo: 'horizontal',
          x1,
          x2,
          y1: y,
          y2: y,
          subtipo: tipo,
          dataInicio,
          dataFim,
        })
      }

      const adicionarVertical = (x, y1, y2, tipo, data) => {
        if (!Number.isFinite(y1) || !Number.isFinite(y2) || Math.abs(y2 - y1) < 0.5) {
          return
        }
        segmentos.push({
          tipo: 'vertical',
          x1: x,
          x2: x,
          y1,
          y2,
          subtipo: tipo,
          dataInicio: data,
          dataFim: data,
        })
      }

      if (item.tipo === 'fim_promocao' && yNormal !== null) {
        const fimPromocaoValido = dentroDoHorizonte(dataTransicaoNormal)
        const dataProximaPromocao = item.dataEstimada
          ? new Date(item.dataEstimada).getTime()
          : null
        const proximaPromocaoValida = dentroDoHorizonte(dataProximaPromocao)

        if (fimPromocaoValido && yAtual !== null) {
          const xFimPromocao = calcularX(dataTransicaoNormal)

          // 1) A promoção atual permanece válida até a data de término
          // informada pela loja.
          adicionarHorizontal(
            xAtual,
            xFimPromocao,
            yAtual,
            'estado-atual',
            agora,
            dataTransicaoNormal
          )

          // 2) No término da promoção atual, o preço volta ao preço normal.
          adicionarVertical(
            xFimPromocao,
            yAtual,
            yNormal,
            'fim-promocao-atual',
            dataTransicaoNormal
          )
          transicoes.push({
            x: xFimPromocao,
            yDe: yAtual,
            yPara: yNormal,
            data: dataTransicaoNormal,
            subtitulo: 'Fim da promoção atual',
          })

          // 3) O preço normal permanece até a próxima promoção estimada.
          if (proximaPromocaoValida && yPrevisto !== null) {
            const xProximaPromocao = calcularX(dataProximaPromocao)

            adicionarHorizontal(
              xFimPromocao,
              xProximaPromocao,
              yNormal,
              'preco-normal',
              dataTransicaoNormal,
              dataProximaPromocao
            )

            // 4) Na data estimada, começa a próxima promoção prevista.
            adicionarVertical(
              xProximaPromocao,
              yNormal,
              yPrevisto,
              'proxima-promocao',
              dataProximaPromocao
            )
            transicoes.push({
              x: xProximaPromocao,
              yDe: yNormal,
              yPara: yPrevisto,
              data: dataProximaPromocao,
              subtitulo: 'Próxima promoção estimada',
            })

            // 5) A janela de previsão continua a partir da próxima promoção
            // até seu limite. Ao terminar a janela, voltamos ao preço normal
            // e encerramos a previsão, sem criar uma linha artificial depois.
            if (fimPrevisaoVisual > dataProximaPromocao) {
              adicionarHorizontal(
                xProximaPromocao,
                xFimPrevisao,
                yPrevisto,
                'promocao-prevista',
                dataProximaPromocao,
                fimPrevisaoVisual
              )

              if (yNormal !== null) {
                adicionarVertical(
                  xFimPrevisao,
                  yPrevisto,
                  yNormal,
                  'fim-janela',
                  fimPrevisaoVisual
                )
                transicoes.push({
                  x: xFimPrevisao,
                  yDe: yPrevisto,
                  yPara: yNormal,
                  data: fimPrevisaoVisual,
                  subtitulo: 'Fim da janela de previsão',
                })
              }
            }
          } else {
            // A próxima promoção está fora do horizonte visual: mantemos
            // somente o preço normal até o limite do filtro.
            adicionarHorizontal(
              xFimPromocao,
              xFim,
              yNormal,
              'preco-normal',
              dataTransicaoNormal,
              fim
            )
          }
        } else if (yAtual !== null) {
          // O término da promoção atual está fora do filtro: não inventamos
          // uma alteração dentro do período selecionado.
          adicionarHorizontal(xAtual, xFim, yAtual, 'estado-atual', agora, fim)
        }
      } else {
        const alteracaoValida =
          dentroDoHorizonte(dataProximaAlteracao) && yPrevisto !== null

        if (alteracaoValida && yAtual !== null) {
          const xAlteracao = calcularX(dataProximaAlteracao)
          adicionarHorizontal(
            xAtual,
            xAlteracao,
            yAtual,
            'estado-atual',
            agora,
            dataProximaAlteracao
          )
          adicionarVertical(
            xAlteracao,
            yAtual,
            yPrevisto,
            'previsao',
            dataProximaAlteracao
          )
          transicoes.push({
            x: xAlteracao,
            yDe: yAtual,
            yPara: yPrevisto,
            data: dataProximaAlteracao,
            subtitulo:
              item.tipo === 'aumento'
                ? 'Aumento estimado'
                : item.tipo === 'estabilidade'
                  ? 'Estabilidade estimada'
                  : 'Próxima promoção estimada',
          })
          adicionarHorizontal(
            xAlteracao,
            xFimPrevisao,
            yPrevisto,
            'previsao',
            dataProximaAlteracao,
            fimPrevisaoVisual
          )
        } else if (yAtual !== null) {
          // Só usamos uma linha reta até o final quando não existe nenhuma
          // alteração prevista dentro do horizonte visual.
          adicionarHorizontal(xAtual, xFim, yAtual, 'estado-atual', agora, fim)
        }
      }

      return {
        ...item,
        inicio: xAtual,
        fim: xFimPrevisao,
        fimVisual: xFimPrevisao,
        xAtual,
        data: dentroDoHorizonte(dataProximaAlteracao)
          ? calcularX(dataProximaAlteracao)
          : null,
        dataFimPromocao: dentroDoHorizonte(dataFimPromocao)
          ? calcularX(dataFimPromocao)
          : null,
        dataProximaAlteracaoX: dentroDoHorizonte(dataProximaAlteracao)
          ? calcularX(dataProximaAlteracao)
          : null,
        dataTransicaoNormalX: dentroDoHorizonte(dataTransicaoNormal)
          ? calcularX(dataTransicaoNormal)
          : null,
        dataProximaPromocaoX:
          item.tipo === 'fim_promocao' &&
          Number.isFinite(new Date(item.dataEstimada).getTime()) &&
          dentroDoHorizonte(new Date(item.dataEstimada).getTime())
            ? calcularX(new Date(item.dataEstimada).getTime())
            : null,
        transicao:
          dentroDoHorizonte(dataTransicaoNormal)
            ? calcularX(dataTransicaoNormal)
            : xAtual,
        yAtual,
        yPrevisto,
        yNormal,
        segmentos,
        transicoes,
        dataAtual: agora,
        dataFimHorizonte: fim,
      }
    })

    const series = ['Steam', 'Epic']
      .filter((nome) => plataformaAtiva === 'ambas' || plataformaAtiva === nome)
      .map((nome) => ({
        nome,
        dados: dados.filter((registro) => registro.plataforma === nome),
      }))
      .filter((serie) => serie.dados.length > 0)

    /*
     * O histórico continua sendo desenhado em degraus reais. O último
     * estado histórico é estendido até HOJE; a previsão começa exatamente
     * nesse mesmo ponto, conectando as duas partes sem salto visual.
     */
    const pontosSeries = series.map((serie) => {
      const pontosBase = serie.dados.map((registro) => ({
        ...registro,
        x: calcularX(registro.data_coleta),
        y: calcularY(Number(registro.preco_atual)),
      }))

      const pontosEscada = []
      let ultimoPontoComPrecoDiferente = pontosBase[0] || null

      if (ultimoPontoComPrecoDiferente) {
        pontosEscada.push({
          ...ultimoPontoComPrecoDiferente,
          _pontoDestaque: !ultimoPontoComPrecoDiferente._ancoraPeriodo,
        })
      }

      for (let indice = 1; indice < pontosBase.length; indice += 1) {
        const ponto = pontosBase[indice]
        const precoAnterior = Math.round(
          Number(ultimoPontoComPrecoDiferente.preco_atual) * 100
        )
        const precoAtualRegistro = Math.round(
          Number(ponto.preco_atual) * 100
        )

        if (precoAtualRegistro === precoAnterior) continue

        pontosEscada.push({
          ...ultimoPontoComPrecoDiferente,
          id: `escada-horizontal-${serie.nome}-${ultimoPontoComPrecoDiferente.id}-${ponto.id}`,
          data_coleta: ponto.data_coleta,
          x: ponto.x,
          y: ultimoPontoComPrecoDiferente.y,
          _pontoEscada: true,
        })

        const pontoComDestaque = {
          ...ponto,
          _pontoDestaque: !ponto._ancoraPeriodo,
        }

        pontosEscada.push(pontoComDestaque)
        ultimoPontoComPrecoDiferente = pontoComDestaque
      }

      let pontoAtual = null

      if (ultimoPontoComPrecoDiferente) {
        const ultimoTimestamp = new Date(
          ultimoPontoComPrecoDiferente.data_coleta
        ).getTime()

        if (ultimoTimestamp < agora) {
          pontoAtual = {
            ...ultimoPontoComPrecoDiferente,
            id: `atual-${serie.nome}-${ultimoPontoComPrecoDiferente.id}`,
            data_coleta: new Date(agora).toISOString(),
            x: calcularX(agora),
            y: ultimoPontoComPrecoDiferente.y,
            _pontoEscada: true,
            _pontoAtual: true,
          }
          pontosEscada.push(pontoAtual)
        }
      }

      return {
        ...serie,
        registros: pontosBase,
        pontos: pontosEscada,
        pontoAtual,
      }
    })

    const quantidadeTicks = 5
    const ticksY = Array.from({ length: quantidadeTicks }, (_, indice) => {
      const proporcao = indice / (quantidadeTicks - 1)
      const preco = maximo - (maximo - minimo) * proporcao
      return {
        preco,
        y: margem.topo + proporcao * areaAltura,
      }
    })

    const quantidadeTicksX = 5
    const ticksX = Array.from({ length: quantidadeTicksX }, (_, indice) => {
      const proporcao = indice / (quantidadeTicksX - 1)
      const timestamp = inicio + (fim - inicio) * proporcao
      return {
        data: new Date(timestamp),
        x: margem.esquerda + areaLargura * proporcao,
      }
    })

    const previsaoTicks = previsoesBase
      .flatMap((item) => [item.data, item.inicio])
      .filter((valor) => Number.isFinite(Number(valor)))

    return {
      largura,
      altura,
      margem,
      areaLargura,
      areaAltura,
      inicio,
      fim,
      pontosSeries,
      ticksY,
      ticksX,
      previsoes: previsoesAtivas,
      previsaoTicks,
      calcularX,
      calcularY,
    }
  }, [dados, plataformaAtiva, analisesPrevisao, agoraAtual, periodo])


  const previsoesHistoricoDisponiveis = Object.values(analisesPrevisao)
    .some((item) => item?.previsao?.tipo !== 'insuficiente')

  const previsaoDisponivel =
    Boolean(grafico?.previsoes?.length)

  const previsaoStatus = !previsoesHistoricoDisponiveis
    ? 'Previsão indisponível: histórico insuficiente para estimar o próximo comportamento.'
    : !previsaoDisponivel && periodo !== 'tudo'
      ? `Há uma previsão registrada, mas ela está fora do horizonte de ${
          periodo === '30d'
            ? '30 dias'
            : periodo === '3m'
              ? '3 meses'
              : periodo === '6m'
                ? '6 meses'
                : '1 ano'
        }.`
      : null


  const obterChavePonto = (serie, ponto) =>
    `${serie.nome}|${ponto.id}|${ponto.data_coleta}`

  const limparPontosFixados = () => {
    for (const timer of tooltipTimersRef.current.values()) {
      clearTimeout(timer)
    }

    tooltipTimersRef.current.clear()
    setPontosFixados([])
  }

  const fixarPonto = (ponto, serie) => {
    if (!ponto || !serie) return

    const chave = obterChavePonto(serie, ponto)

    const timerExistente = tooltipTimersRef.current.get(chave)
    if (timerExistente) {
      clearTimeout(timerExistente)
    }

    const pontoFixadoNovo = {
      ...ponto,
      plataforma: serie.nome,
      x: ponto.x,
      y: ponto.y,
      _fixado: true,
      _chaveFixada: chave,
    }

    setPontosFixados((anteriores) => [
      ...anteriores.filter((item) => item._chaveFixada !== chave),
      pontoFixadoNovo,
    ])

    const novoTimer = setTimeout(() => {
      setPontosFixados((anteriores) =>
        anteriores.filter((item) => item._chaveFixada !== chave)
      )
      tooltipTimersRef.current.delete(chave)
    }, 5000)

    tooltipTimersRef.current.set(chave, novoTimer)
  }


  const atualizarTooltipPrevisao = (event, previsao) => {
    if (!grafico || previsaoFixada) return

    const svg =
      event.currentTarget.ownerSVGElement || event.currentTarget
    const area = svg.getBoundingClientRect()

    if (!area.width || !area.height) return

    const escalaX = grafico.largura / area.width
    const escalaY = grafico.altura / area.height
    const x = limitarNumero(
      (event.clientX - area.left) * escalaX,
      grafico.margem.esquerda,
      grafico.largura - grafico.margem.direita
    )
    const yMouse = limitarNumero(
      (event.clientY - area.top) * escalaY,
      grafico.margem.topo,
      grafico.margem.topo + grafico.areaAltura
    )

    const dados = obterEstadoTooltipPrevisao(previsao, x)

    setPontoSelecionado(null)
    setPrevisaoSelecionada(previsao.plataforma)
    setPrevisaoTooltipMouse({
      x,
      y: Number.isFinite(dados?.y) ? dados.y : yMouse,
    })
  }

  const obterEstadoTooltipPrevisao = (previsao, x) => {
    if (!grafico) return null

    let preco = previsao.precoPrevisto
    let subtitulo = 'Próxima promoção estimada'
    let desconto = previsao.descontoPrevisto
    let y = previsao.yPrevisto

    if (previsao.tipo === 'fim_promocao' && previsao.yNormal !== null) {
      if (x < (previsao.dataTransicaoNormalX ?? previsao.xAtual)) {
        preco = previsao.precoAtual
        subtitulo = 'Promoção atual'
        desconto = previsao.descontoAtual
        y = previsao.yAtual
      } else if (
        previsao.dataProximaPromocaoX !== null &&
        x < previsao.dataProximaPromocaoX
      ) {
        preco = previsao.precoNormal
        subtitulo = 'Período normal'
        desconto = 0
        y = previsao.yNormal
      } else {
        preco = previsao.precoPrevisto
        subtitulo = 'Próxima promoção estimada'
        desconto = previsao.descontoPrevisto
        y = previsao.yPrevisto
      }
    } else if (previsao.dataProximaAlteracaoX !== null && x < previsao.dataProximaAlteracaoX) {
      preco = previsao.precoAtual
      subtitulo = 'Preço atual'
      desconto = previsao.descontoAtual
      y = previsao.yAtual
    }

    const proporcao =
      (x - grafico.margem.esquerda) / Math.max(grafico.areaLargura, 1)
    const timestamp =
      grafico.inicio +
      limitarNumero(proporcao, 0, 1) * (grafico.fim - grafico.inicio)

    return {
      x,
      y: Number.isFinite(y) ? y : null,
      data: new Date(timestamp),
      preco: Number.isFinite(preco) ? preco : null,
      subtitulo,
      desconto: Number.isFinite(Number(desconto)) ? Number(desconto) : null,
    }
  }

  const obterDadosTooltipPrevisao = (previsao) => {
    if (!grafico) return null

    const x = limitarNumero(
      previsaoTooltipMouse?.x ?? previsao.data ?? previsao.transicao ?? previsao.xAtual,
      grafico.margem.esquerda,
      grafico.largura - grafico.margem.direita
    )

    return obterEstadoTooltipPrevisao(previsao, x)
  }

  const fixarPrevisao = (previsao, x = null, y = null) => {
    if (!grafico) return

    if (previsaoFixada === previsao.plataforma) {
      if (previsaoTimerRef.current) {
        clearTimeout(previsaoTimerRef.current)
        previsaoTimerRef.current = null
      }
      setPrevisaoFixada(null)
      setPrevisaoSelecionada(null)
      setPrevisaoTooltipMouse(null)
      return
    }

    if (previsaoTimerRef.current) {
      clearTimeout(previsaoTimerRef.current)
    }

    const pontoX = x ?? previsao.data ?? previsao.transicao ?? previsao.xAtual
    const estado = obterEstadoTooltipPrevisao(previsao, pontoX)
    const pontoY = y ?? estado?.y ?? previsao.yPrevisto ?? previsao.yNormal

    setPontoSelecionado(null)
    setPrevisaoFixada(previsao.plataforma)
    setPrevisaoSelecionada(previsao.plataforma)
    setPrevisaoTooltipMouse({ x: pontoX, y: pontoY })

    previsaoTimerRef.current = setTimeout(() => {
      setPrevisaoFixada(null)
      setPrevisaoSelecionada(null)
      setPrevisaoTooltipMouse(null)
      previsaoTimerRef.current = null
    }, 5000)
  }

  const limparTooltipPrevisao = () => {
    if (previsaoFixada) return
    setPrevisaoSelecionada(null)
    setPrevisaoTooltipMouse(null)
  }

  const atualizarTooltipPeloMouse = (event) => {
    if (!grafico) return

    // O evento agora vem diretamente do SVG, evitando diferenças de escala
    // causadas pelo container externo do gráfico.
    const svg = event.currentTarget
    const area = svg.getBoundingClientRect()

    if (!area.width || !area.height) return

    const escalaX = grafico.largura / area.width
    const escalaY = grafico.altura / area.height

    const mouseX = (event.clientX - area.left) * escalaX
    const mouseY = (event.clientY - area.top) * escalaY

    if (
      mouseX < grafico.margem.esquerda ||
      mouseX > grafico.largura - grafico.margem.direita ||
      mouseY < grafico.margem.topo ||
      mouseY > grafico.margem.topo + grafico.areaAltura
    ) {
      setPontoSelecionado(null)
      return
    }

    /*
     * Procura a linha mais próxima do cursor, considerando TODOS os
     * segmentos da escada, inclusive os segmentos verticais das mudanças.
     *
     * Assim o tooltip funciona:
     * - no trecho horizontal;
     * - exatamente sobre o ponto de alteração;
     * - durante a subida/descida vertical;
     * - mesmo quando o cursor não estiver sobre o círculo.
     */
    const candidatos = []

    for (const serie of grafico.pontosSeries) {
      const pontos = serie.pontos || []

      if (pontos.length === 0) continue

      for (let indice = 0; indice < pontos.length; indice += 1) {
        const pontoAtual = pontos[indice]

        // O primeiro ponto também pode ser destacado isoladamente.
        if (indice === 0) {
          const distancia = Math.hypot(
            mouseX - pontoAtual.x,
            mouseY - pontoAtual.y
          )

          candidatos.push({
            serie,
            ponto: pontoAtual,
            distancia,
          })
          continue
        }

        const pontoAnterior = pontos[indice - 1]

        const dx = pontoAtual.x - pontoAnterior.x
        const dy = pontoAtual.y - pontoAnterior.y
        const comprimentoQuadrado = dx * dx + dy * dy

        let proporcao = 0

        if (comprimentoQuadrado > 0) {
          proporcao =
            ((mouseX - pontoAnterior.x) * dx +
              (mouseY - pontoAnterior.y) * dy) /
            comprimentoQuadrado

          proporcao = Math.max(0, Math.min(1, proporcao))
        }

        const pontoProjetado = {
          x: pontoAnterior.x + dx * proporcao,
          y: pontoAnterior.y + dy * proporcao,
        }

        const distancia = Math.hypot(
          mouseX - pontoProjetado.x,
          mouseY - pontoProjetado.y
        )

        candidatos.push({
          serie,
          ponto: pontoAtual,
          distancia,
        })
      }
    }

    candidatos.sort((a, b) => a.distancia - b.distancia)

    const maisProximo = candidatos[0]

    // Tolerância um pouco maior para facilitar a seleção visual da linha.
    if (!maisProximo || maisProximo.distancia > 30) {
      setPontoSelecionado(null)
      return
    }

    /*
     * Converte a posição horizontal do mouse em data.
     * O registro ativo é o último estado conhecido naquela data.
     */
    const proporcaoTempo =
      (mouseX - grafico.margem.esquerda) / grafico.areaLargura

    const timestamp =
      grafico.inicio +
      proporcaoTempo * (grafico.fim - grafico.inicio)

    const registros = maisProximo.serie.registros || []
    let registroAtivo = registros[0] || maisProximo.ponto

    for (const registro of registros) {
      if (new Date(registro.data_coleta).getTime() <= timestamp) {
        registroAtivo = registro
      } else {
        break
      }
    }

    const yLinha = grafico.calcularY(Number(registroAtivo.preco_atual))

    setPontoSelecionado({
      ...registroAtivo,
      plataforma: maisProximo.serie.nome,
      data_coleta: new Date(timestamp).toISOString(),
      x: mouseX,
      // Mantém a janela visualmente próxima ao cursor, mas alinhada à linha.
      y: Math.abs(mouseY - yLinha) <= 30 ? mouseY : yLinha,
      _hoverLinha: true,
    })
  }

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
                  limparPontosFixados()
                  setPrevisaoSelecionada(null)
                  if (previsaoTimerRef.current) {
                    clearTimeout(previsaoTimerRef.current)
                    previsaoTimerRef.current = null
                  }
                  setPrevisaoFixada(null)
                  setPrevisaoTooltipMouse(null)
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
                onPeriodoChange(valor)
                setPontoSelecionado(null)
                limparPontosFixados()
                setPrevisaoSelecionada(null)
                  setPrevisaoFixada(null)
                  setPrevisaoTooltipMouse(null)
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
      <div className={`grafico-interativo${graficoExpandido ? " grafico-tela-cheia-ofertas" : ""}`}>
        <div className="cabecalho-grafico-ofertas">
          {renderControles()}
          <button
            type="button"
            className="botao-expandir-grafico-ofertas"
            onClick={alternarGraficoExpandido}
            aria-label={graficoExpandido ? 'Fechar gráfico ampliado' : 'Expandir gráfico'}
            aria-expanded={graficoExpandido}
          >
            {graficoExpandido ? <span aria-hidden="true">×</span> : '⛶ Tela cheia'}
          </button>
        </div>
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
    <div className={`grafico-interativo${graficoExpandido ? " grafico-tela-cheia-ofertas" : ""}`}>
      <div className="cabecalho-grafico-ofertas">
          {renderControles()}
          <button
            type="button"
            className="botao-expandir-grafico-ofertas"
            onClick={alternarGraficoExpandido}
            aria-label={graficoExpandido ? 'Fechar gráfico ampliado' : 'Expandir gráfico'}
            aria-expanded={graficoExpandido}
          >
            {graficoExpandido ? <span aria-hidden="true">×</span> : '⛶ Tela cheia'}
          </button>
        </div>

      <div className="grafico-legenda">
        {grafico.pontosSeries.map((serie) => (
          <span key={serie.nome}>
            <i className={`legenda-ponto legenda-${serie.nome.toLowerCase()}`} />
            {serie.nome}
          </span>
        ))}
        <span>
          <i className="legenda-dia-atual" />
          Hoje
        </span>
        {grafico.previsoes?.length ? (
          <span>
            <i className="legenda-pontilhada" />
            Previsão
          </span>
        ) : (
          previsaoStatus && (
            <span className="grafico-previsao-indisponivel">
              {previsaoStatus}
            </span>
          )
        )}
      </div>

      <div className="grafico-area">
        <svg
          className="ofertas-grafico"
          viewBox={`0 0 ${grafico.largura} ${grafico.altura}`}
          role="img"
          aria-label={`Histórico de preços de ${historico.length ? 'jogo selecionado' : ''}`}
          onMouseMove={atualizarTooltipPeloMouse}
          onMouseLeave={() => {
            setPontoSelecionado(null)
            limparTooltipPrevisao()
          }}
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
              {formatarDataEixoGrafico(tick.data, periodo)}
            </text>
          ))}

          <line
            x1={grafico.margem.esquerda}
            y1={grafico.margem.topo + grafico.areaAltura}
            x2={grafico.largura - grafico.margem.direita}
            y2={grafico.margem.topo + grafico.areaAltura}
            className="grafico-eixo"
          />

          {grafico.previsoes?.length > 1 && (
            <rect
              x={Math.min(...grafico.previsoes.map((item) => item.inicio))}
              y={grafico.margem.topo}
              width={
                Math.max(...grafico.previsoes.map((item) => item.fimVisual ?? item.fim)) -
                Math.min(...grafico.previsoes.map((item) => item.inicio))
              }
              height={grafico.areaAltura}
              className="grafico-faixa-previsao-comparacao"
            />
          )}

          {grafico.previsoes?.map((previsao) => {

            return (
              <g
                key={`previsao-${previsao.plataforma}`}
                onMouseMove={(event) => atualizarTooltipPrevisao(event, previsao)}
                onMouseLeave={limparTooltipPrevisao}
              >
                <rect
                  x={previsao.inicio}
                  y={grafico.margem.topo}
                  width={Math.max(0, (previsao.fimVisual ?? previsao.fim) - previsao.inicio)}
                  height={grafico.areaAltura}
                  className={[
                    'grafico-faixa-previsao',
                    `grafico-faixa-previsao-${previsao.plataforma.toLowerCase()}`,
                  ].join(' ')}
                />

                {previsao.segmentos?.map((segmento, indice) => (
                  <line
                    key={`previsao-${previsao.plataforma}-segmento-${indice}`}
                    x1={segmento.x1}
                    y1={segmento.y1}
                    x2={segmento.x2}
                    y2={segmento.y2}
                    className={[
                      'grafico-linha-previsao',
                      `grafico-linha-previsao-${previsao.plataforma.toLowerCase()}`,
                      segmento.tipo === 'vertical'
                        ? 'grafico-linha-previsao-vertical'
                        : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    style={{
                      stroke:
                        previsao.plataforma === 'Steam'
                          ? '#4b8db8'
                          : '#8b5cf6',
                    }}
                    onMouseMove={(event) =>
                      atualizarTooltipPrevisao(event, previsao)
                    }
                  />
                ))}

                {previsao.transicoes?.map((transicao, indice) => (
                  <circle
                    key={`previsao-${previsao.plataforma}-transicao-${indice}`}
                    cx={transicao.x}
                    cy={transicao.yPara}
                    r="5"
                    className={[
                      'grafico-ponto',
                      'grafico-ponto-previsao',
                      `grafico-ponto-previsao-${previsao.plataforma.toLowerCase()}`,
                      previsaoFixada === previsao.plataforma
                        ? 'grafico-ponto-fixado'
                        : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    style={{
                      fill:
                        previsao.plataforma === 'Steam'
                          ? '#4b8db8'
                          : '#8b5cf6',
                    }}
                    onMouseEnter={(event) =>
                      atualizarTooltipPrevisao(event, previsao)
                    }
                    onMouseLeave={limparTooltipPrevisao}
                    onClick={() =>
                      fixarPrevisao(previsao, transicao.x, transicao.yPara)
                    }
                  />
                ))}

                {previsao.yPrevisto !== null && (
                  <circle
                    cx={previsao.fim}
                    cy={previsao.yPrevisto}
                    r="5"
                    className={[
                      'grafico-ponto',
                      'grafico-ponto-previsao',
                      'grafico-ponto-previsao-final',
                      previsaoFixada === previsao.plataforma
                        ? 'grafico-ponto-fixado'
                        : '',
                      `grafico-ponto-previsao-${previsao.plataforma.toLowerCase()}`,
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    style={{
                      fill:
                        previsao.plataforma === 'Steam'
                          ? '#4b8db8'
                          : '#8b5cf6',
                    }}
                    onMouseEnter={(event) =>
                      atualizarTooltipPrevisao(event, previsao)
                    }
                    onMouseLeave={limparTooltipPrevisao}
                    onClick={() =>
                      fixarPrevisao(previsao, previsao.fim, previsao.yPrevisto)
                    }
                  />
                )}

                <line
                  x1={previsao.xAtual}
                  y1={grafico.margem.topo}
                  x2={previsao.xAtual}
                  y2={grafico.margem.topo + grafico.areaAltura}
                  className={[
                    'grafico-divisor-previsao',
                    `grafico-divisor-previsao-${previsao.plataforma.toLowerCase()}`,
                  ].join(' ')}
                />
              </g>
            )
          })}

          {grafico.pontosSeries.map((serie) => (
            <g key={serie.nome}>
              <polyline
                points={serie.pontos.map((ponto) => `${ponto.x},${ponto.y}`).join(' ')}
                className={`grafico-linha grafico-linha-${serie.nome.toLowerCase()}`}
              />

              {serie.pontos
                .filter(
                  (ponto) =>
                    !ponto._pontoAtual &&
                    (
                      ponto._pontoDestaque === true ||
                      (
                        !ponto._ancoraPeriodo &&
                        !ponto._pontoEscada
                      )
                    )
                )
                .map((ponto) => (
                  <circle
                    key={`${serie.nome}-${ponto.id}-${ponto.data_coleta}`}
                    cx={ponto.x}
                    cy={ponto.y}
                    r={ponto._pontoDestaque ? '6' : '5'}
                    className={[
                      'grafico-ponto',
                      `grafico-ponto-${serie.nome.toLowerCase()}`,
                      ponto._pontoDestaque ? 'grafico-ponto-destaque' : '',
                      pontosFixados.some(
                        (item) => item._chaveFixada === obterChavePonto(serie, ponto)
                      )
                        ? 'grafico-ponto-fixado'
                        : '',
                    ]
                      .filter(Boolean)
                      .join(' ')}
                    onClick={() => fixarPonto(ponto, serie)}
                  />
                ))}

              {serie.pontoAtual && (
                <>
                  <line
                    x1={serie.pontoAtual.x}
                    y1={grafico.margem.topo}
                    x2={serie.pontoAtual.x}
                    y2={grafico.margem.topo + grafico.areaAltura}
                    className="grafico-linha-dia-atual"
                  />

                  <polygon
                    points={`
                      ${serie.pontoAtual.x},${serie.pontoAtual.y - 9}
                      ${serie.pontoAtual.x + 8},${serie.pontoAtual.y}
                      ${serie.pontoAtual.x},${serie.pontoAtual.y + 9}
                      ${serie.pontoAtual.x - 8},${serie.pontoAtual.y}
                    `}
                    className={`grafico-marcador-dia-atual grafico-marcador-dia-atual-${serie.nome.toLowerCase()}`}
                    onClick={() => fixarPonto(serie.pontoAtual, serie)}
                  />
                </>
              )}
            </g>
          ))}

        </svg>

        {pontosFixados.map((ponto) => (
          <div
            key={ponto._chaveFixada}
            className="grafico-tooltip grafico-tooltip-fixado"
            style={{
              left: `${(ponto.x / grafico.largura) * 100}%`,
              top: `${(ponto.y / grafico.altura) * 100}%`,
            }}
          >
            <strong>{ponto.plataforma}</strong>
            <span>{formatarDataGrafico(ponto.data_coleta)}</span>
            <strong>{formatarPreco(ponto.preco_atual)}</strong>
            <span>
              {Number(ponto.desconto || 0) > 0
                ? `${ponto.desconto}% de desconto`
                : 'Sem promoção'}
            </span>
            <small>Exibindo por 5 segundos</small>
          </div>
        ))}

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

        {grafico.previsoes?.map(
          (previsao) =>
            previsao.plataforma === previsaoSelecionada && (
              <div
                key={`tooltip-previsao-${previsao.plataforma}`}
                className="grafico-tooltip grafico-tooltip-previsao"
                style={{
                  left: `${((previsaoTooltipMouse?.x ?? (previsao.data ?? previsao.transicao)) / grafico.largura) * 100}%`,
                  top: `${((previsaoTooltipMouse?.y ?? (previsao.data !== null ? previsao.yPrevisto : previsao.yNormal)) / grafico.altura) * 100}%`,
                  transform:
                    ((previsaoTooltipMouse?.x ?? (previsao.data ?? previsao.transicao)) / grafico.largura) >= 0.82
                      ? 'translate(-100%, calc(-100% - 12px))'
                      : ((previsaoTooltipMouse?.x ?? (previsao.data ?? previsao.transicao)) / grafico.largura) <= 0.18
                        ? 'translate(0, calc(-100% - 12px))'
                        : 'translate(-50%, calc(-100% - 12px))',
                }}
              >
                {(() => {
                  const dadosTooltip = obterDadosTooltipPrevisao(previsao)

                  if (!dadosTooltip) return null

                  return (
                    <>
                      <strong>PREVISÃO · {previsao.plataforma}</strong>
                      <span>{dadosTooltip.subtitulo}</span>
                      <strong>{formatarDataGrafico(dadosTooltip.data)}</strong>
                      <strong>
                        {dadosTooltip.preco !== null
                          ? formatarPreco(dadosTooltip.preco)
                          : '—'}
                      </strong>
                      <span>
                        {dadosTooltip.desconto !== null
                          ? dadosTooltip.subtitulo === 'Próxima promoção estimada'
                            ? `${Math.round(dadosTooltip.desconto)}% de desconto provável`
                            : `${Math.round(dadosTooltip.desconto)}% de desconto`
                          : 'Desconto não estimado'}
                      </span>
                      {previsaoFixada === previsao.plataforma && (
                        <small>Exibindo por 5 segundos</small>
                      )}
                    </>
                  )
                })()}
              </div>
            )
        )}
      </div>
    </div>
  )
}

function Ofertas() {
  const { token, autenticado } = useAuth()
  const consultasRegistradas = useRef(new Set())

  const registrarConsultaOferta = useCallback((jogoId) => {
    if (!token || !autenticado || !jogoId) return
    const chave = String(jogoId)
    if (consultasRegistradas.current.has(chave)) return
    consultasRegistradas.current.add(chave)
    fetch(`${API_BASE}/api/conquistas/evento`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ evento: 'consulta_jogo_ofertas', jogo_id: Number(jogoId) }),
    }).catch((erro) => {
      consultasRegistradas.current.delete(chave)
      console.warn('Não foi possível registrar a consulta de ofertas para conquistas.', erro)
    })
  }, [token, autenticado])
  const [tema, setTema] = useState(() => {
    const salvo = localStorage.getItem('tema-comparador')
    return salvo === 'escuro' ? 'escuro' : 'claro'
  })

  const [jogos, setJogos] = useState([])
  const [historicos, setHistoricos] = useState({})
  const [busca, setBusca] = useState('')
  const [plataformaAnalise, setPlataformaAnalise] = useState('ambas')
  const [periodoGrafico, setPeriodoGrafico] = useState('30d')
  const [jogoSelecionado, setJogoSelecionado] = useState(null)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')

  useEffect(() => {
    localStorage.setItem('tema-comparador', tema)
  }, [tema])

  const requisicaoHistoricoAtual = useRef(0)

  useEffect(() => {
    const inicioCarregar = performance.now()
    diagnosticoPerformance.carregar.chamadas += 1
    let cancelado = false

    async function carregarJogoInicial() {
      try {
        setCarregando(true)
        setErro('')

        const jogoIdParametro = new URLSearchParams(window.location.search).get('jogo')
        let jogoInicial = null

        if (jogoIdParametro) {
          // Acesso vindo da página de um jogo: busca apenas esse registro.
          const inicioJogo = performance.now()
          const resposta = await fetch(`${API}/${encodeURIComponent(jogoIdParametro)}`)
          if (!resposta.ok) {
            throw new Error('Não foi possível carregar o jogo selecionado.')
          }
          jogoInicial = await resposta.json()
          registrarConsultaOferta(jogoInicial.id)
          diagnosticoPerformance.carregar.etapas.jogos = performance.now() - inicioJogo
        } else {
          // Abertura direta: reutiliza o ranking da seção "Recomendados pela comunidade"
          // da página inicial. O endpoint já ordena por quantidade de recomendações
          // e aplica os filtros de visibilidade e promoção ativa.
          const inicioJogos = performance.now()
          const respostaVitrine = await fetch(`${API}/vitrine/secoes`)
          if (!respostaVitrine.ok) {
            throw new Error('Não foi possível carregar as recomendações da comunidade.')
          }

          const dadosVitrine = await respostaVitrine.json()
          const primeiroRecomendado = dadosVitrine.comunidade?.[0] || null

          if (primeiroRecomendado?.id != null) {
            // Busca os detalhes completos usados pelo comparador e pelo histórico.
            const respostaJogo = await fetch(`${API}/${encodeURIComponent(primeiroRecomendado.id)}`)
            if (!respostaJogo.ok) {
              throw new Error('Não foi possível carregar o jogo mais recomendado pela comunidade.')
            }
            jogoInicial = await respostaJogo.json()
            if (!cancelado) setJogos([jogoInicial])
          }

          diagnosticoPerformance.carregar.etapas.jogos = performance.now() - inicioJogos
        }

        if (cancelado) return

        if (jogoInicial) {
          // Em modo de jogo selecionado, mantemos um catálogo mínimo para
          // que os cálculos locais não percorram milhares de registros.
          setJogos((atuais) => {
            const encontrados = atuais.some((jogo) => String(jogo.id) === String(jogoInicial.id))
            return encontrados ? atuais : [jogoInicial, ...atuais]
          })
          setJogoSelecionado(jogoInicial)
        } else {
          setErro('Não foi possível encontrar um jogo para analisar.')
          setCarregando(false)
        }
      } catch (error) {
        if (cancelado) return
        console.error('Erro ao carregar jogo para análise:', error)
        setErro(error.message || 'Não foi possível carregar os dados.')
        setCarregando(false)
      } finally {
        const tempoTotal = performance.now() - inicioCarregar
        diagnosticoPerformance.carregar.tempoTotal += tempoTotal
        diagnosticoPerformance.carregar.etapas.total = tempoTotal
      }
    }

    carregarJogoInicial()
    return () => { cancelado = true }
  }, [registrarConsultaOferta])

  // Busca o histórico somente do jogo selecionado. O endpoint individual já
  // existe no backend e retorna o mesmo formato usado pela análise da página.
  useEffect(() => {
    if (!jogoSelecionado) return

    const idRequisicao = ++requisicaoHistoricoAtual.current
    const inicioHistorico = performance.now()

    async function carregarHistoricoSelecionado() {
      setCarregando(true)
      setErro('')

      try {
        const resposta = await fetch(`${API}/${jogoSelecionado.id}/historico`)
        if (!resposta.ok) {
          throw new Error('Não foi possível carregar o histórico deste jogo.')
        }

        const historico = await resposta.json()
        if (idRequisicao !== requisicaoHistoricoAtual.current) return

        setHistoricos((atuais) => ({
          ...atuais,
          [jogoSelecionado.id]: historico,
        }))
        diagnosticoPerformance.carregar.etapas.historicos = performance.now() - inicioHistorico
      } catch (error) {
        if (idRequisicao !== requisicaoHistoricoAtual.current) return
        console.error('Erro ao carregar histórico do jogo selecionado:', error)
        setErro(error.message || 'Não foi possível carregar os dados do jogo.')
      } finally {
        if (idRequisicao === requisicaoHistoricoAtual.current) {
          setCarregando(false)
        }
      }
    }

    carregarHistoricoSelecionado()

    return () => {
      requisicaoHistoricoAtual.current += 1
    }
  }, [jogoSelecionado])

  useEffect(() => {
    if (!jogoSelecionado) return

    const disponiveis = new Set(
      (historicos[jogoSelecionado.id] || [])
        .map((registro) => registro.plataforma)
        .filter((plataforma) => plataforma === 'Steam' || plataforma === 'Epic')
    )

    if (
      plataformaAnalise !== 'ambas' &&
      !disponiveis.has(plataformaAnalise)
    ) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setPlataformaAnalise('ambas')
    }
  }, [jogoSelecionado, historicos, plataformaAnalise])

  const sugestoes = useMemo(() => {
    const termo = busca.trim().toLowerCase()

    if (!termo) return []

    return jogos
      .filter((jogo) => jogo.nome.toLowerCase().includes(termo))
      .slice(0, 6)
  }, [busca, jogos])

  const historicoJogo = useMemo(
    () => (jogoSelecionado ? historicos[jogoSelecionado.id] || [] : []),
    [jogoSelecionado, historicos]
  )

  const plataformasDisponiveisJogo = useMemo(
    () =>
      new Set(
        historicoJogo
          .map((registro) => registro.plataforma)
          .filter((plataforma) => plataforma === 'Steam' || plataforma === 'Epic')
      ),
    [historicoJogo]
  )

  const plataformaPaginaAtiva =
    plataformaAnalise !== 'ambas' &&
    !plataformasDisponiveisJogo.has(plataformaAnalise)
      ? 'ambas'
      : plataformaAnalise

  const comportamento = useMemo(
    () =>
      jogoSelecionado
        ? calcularComportamentoDesenvolvedora(
            jogoSelecionado,
            jogos,
            historicos,
            plataformaPaginaAtiva
          )
        : null,
    [jogoSelecionado, jogos, historicos, plataformaPaginaAtiva]
  )

  const analisesPorPlataforma = useMemo(
    () => ({
      Steam: analisarHistorico(
        historicoJogo.filter((registro) => registro.plataforma === 'Steam'),
        {
          jogo: jogoSelecionado,
          comportamentoDesenvolvedora: comportamento,
        }
      ),
      Epic: analisarHistorico(
        historicoJogo.filter((registro) => registro.plataforma === 'Epic'),
        {
          jogo: jogoSelecionado,
          comportamentoDesenvolvedora: comportamento,
        }
      ),
    }),
    [historicoJogo, jogoSelecionado, comportamento]
  )

  const analise = useMemo(
    () =>
      plataformaPaginaAtiva === 'Steam'
        ? analisesPorPlataforma.Steam
        : plataformaPaginaAtiva === 'Epic'
          ? analisesPorPlataforma.Epic
          : null,
    [plataformaPaginaAtiva, analisesPorPlataforma]
  )

  const analisesIndicadoresPorPlataforma = useMemo(
    () => ({
      Steam: analisarHistorico(
        filtrarRegistrosReaisPorPeriodo(
          historicoJogo.filter((registro) => registro.plataforma === 'Steam'),
          periodoGrafico
        ),
        {
          jogo: jogoSelecionado,
          comportamentoDesenvolvedora: comportamento,
        }
      ),
      Epic: analisarHistorico(
        filtrarRegistrosReaisPorPeriodo(
          historicoJogo.filter((registro) => registro.plataforma === 'Epic'),
          periodoGrafico
        ),
        {
          jogo: jogoSelecionado,
          comportamentoDesenvolvedora: comportamento,
        }
      ),
    }),
    [historicoJogo, periodoGrafico, jogoSelecionado, comportamento]
  )

  const resumoPromocoesPlataforma = useMemo(
    () => obterResumoPromocoesPorPlataforma(historicoJogo),
    [historicoJogo]
  )

  const melhoresTendencias = useMemo(() => {

    const candidatos = jogos
      .filter((jogo) => jogo.id !== jogoSelecionado?.id)
      .map((jogo) => {
        const historico = historicos[jogo.id] || []
        const steam = analisarHistorico(
          historico.filter((registro) => registro.plataforma === 'Steam')
        )
        const epic = analisarHistorico(
          historico.filter((registro) => registro.plataforma === 'Epic')
        )
        const analise =
          steam.pontuacao >= epic.pontuacao
            ? { ...steam, plataformaAnalise: 'Steam' }
            : { ...epic, plataformaAnalise: 'Epic' }

        const previsao = analise.previsao || {}
        const descontoPrevisto = Number(previsao.descontoEstimado)
        const descontoNormalizado = Number.isFinite(descontoPrevisto)
          ? limitarNumero(descontoPrevisto, 0, 100)
          : 0

        const potencialPromocao =
          previsao.tipo === 'promocao'
            ? 100
            : previsao.tipo === 'fim_promocao'
              ? 95
              : previsao.tipo === 'estabilidade'
                ? 30
                : previsao.tipo === 'aumento'
                  ? 15
                  : 0

        const consistenciaHistorico = limitarNumero(
          (analise.registros.length >= 3 ? 35 : 0) +
            (analise.episodios.length >= 2 ? 35 : 0) +
            (analise.intervalos.length >= 1 ? 15 : 0) +
            (analise.periodoHistoricoDias >= 45 ? 15 : 0),
          0,
          100
        )

        const indiceDestaque =
          potencialPromocao * 0.4 +
          descontoNormalizado * 0.3 +
          limitarNumero(Number(analise.confianca || 0), 0, 100) * 0.2 +
          consistenciaHistorico * 0.1

        return {
          jogo,
          analise,
          descontoPrevisto: Number.isFinite(descontoPrevisto)
            ? descontoPrevisto
            : null,
          indiceDestaque,
          consistenciaHistorico,
        }
      })
      .filter(
        ({ analise }) =>
          analise.nivel !== 'insuficiente' &&
          analise.registros.length >= 3 &&
          (analise.episodios.length >= 2 ||
            analise.intervalos.length >= 1 ||
            (analise.periodoHistoricoDias >= 45))
      )
      .sort((a, b) => {
        if (b.indiceDestaque !== a.indiceDestaque) {
          return b.indiceDestaque - a.indiceDestaque
        }

        return (b.descontoPrevisto ?? -1) - (a.descontoPrevisto ?? -1)
      })

    // Evita que a seção fique dominada por uma única publicadora.
    // Mantemos no máximo dois jogos por publicadora.
    const selecionados = []
    const quantidadePorPublicadora = new Map()

    for (const candidato of candidatos) {
      const chave =
        (candidato.jogo.publicadora || 'Publicadora não informada')
          .trim()
          .toLowerCase()
      const quantidadeAtual = quantidadePorPublicadora.get(chave) || 0

      if (quantidadeAtual >= 2) continue

      selecionados.push(candidato)
      quantidadePorPublicadora.set(chave, quantidadeAtual + 1)

      if (selecionados.length === 6) break
    }

    return selecionados
  }, [jogos, historicos, jogoSelecionado])

  useEffect(() => {
    diagnosticoPerformance.melhoresTendencias.chamadas += 1
  }, [melhoresTendencias])

  const selecionarJogo = (jogo) => {
    registrarConsultaOferta(jogo?.id)
    setJogoSelecionado(jogo)
    setBusca('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const resumoPrecosPorPlataforma = useMemo(
    () =>
      ['Steam', 'Epic'].map((plataforma) => {
        const analisePlataforma = analisesPorPlataforma[plataforma]
        const registros = analisePlataforma.registros

        const ultimoRegistro = registros.length
          ? registros[registros.length - 1]
          : null

        return {
          plataforma,
          disponivel: registros.length > 0,
          analise: analisePlataforma,
          precoAtual: ultimoRegistro
            ? Number(ultimoRegistro.preco_atual)
            : null,
          menorPreco: analisePlataforma.precoMinimo,
          descontoAtual: ultimoRegistro
            ? Number(ultimoRegistro.desconto || 0)
            : 0,
        }
      }),
    [analisesPorPlataforma]
  )

  const precoAtualSelecionado =
    plataformaPaginaAtiva === 'ambas'
      ? null
      : analise?.registros.length
        ? Number(
            analise.registros[analise.registros.length - 1].preco_atual
          )
        : null

  const previsaoSelecionada = analise?.previsao || null

  const textoPrevisao =
    analise ? obterTextoPrevisao(analise) : null

  return (
    <div className={`app tema-${tema}`}>
      <Cabecalho tema={tema} setTema={setTema} />

      <main className="pagina-ofertas">
        <section className="ofertas-hero">
          <div className="ofertas-hero-conteudo">
            <span className="hero-tag">PREVISÃO DE PREÇOS</span>

            <h1>Descubra quando pode valer a pena esperar</h1>

            <p>
              Analise o histórico de preços e o comportamento promocional para
              acompanhar tendências de futuras ofertas
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
                <img
                  className="jogo-selecionado-imagem-fundo"
                  src={imagemDoJogo(jogoSelecionado)}
                  alt=""
                  aria-hidden="true"
                  loading="eager"
                  decoding="async"
                />

                <div className="jogo-selecionado-sobreposicao" />

                <div className="jogo-selecionado-info">
                  <div className="jogo-info-cabecalho">
                    <div>
                      <span className="jogo-desenvolvedor">
                        {jogoSelecionado.desenvolvedor ||
                          'Desenvolvedora não informada'}
                      </span>

                      <h3>{jogoSelecionado.nome}</h3>
                    </div>

                    <div className="jogo-filtro-plataforma" aria-label="Filtrar análise por plataforma">
                      {[
                        ['ambas', 'Comparar'],
                        ['Steam', 'Steam'],
                        ['Epic', 'Epic'],
                      ].map(([valor, rotulo]) => {
                        const disponivel =
                          valor === 'ambas' || plataformasDisponiveisJogo.has(valor)

                        return (
                          <button
                            key={valor}
                            type="button"
                            className={plataformaPaginaAtiva === valor ? 'ativo' : ''}
                            disabled={!disponivel}
                            title={
                              disponivel
                                ? `Analisar ${rotulo}`
                                : `Sem histórico disponível para ${rotulo}`
                            }
                            onClick={() => {
                              if (!disponivel) return
                              setPlataformaAnalise(valor)
                            }}
                          >
                            {rotulo}
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <div
                    className={`jogo-precos ${
                      plataformaPaginaAtiva === 'ambas'
                        ? 'jogo-precos-comparacao'
                        : ''
                    }`}
                  >
                    {plataformaPaginaAtiva === 'ambas' ? (
                      resumoPrecosPorPlataforma.map((item) => (
                        <div
                          className={`jogo-preco-plataforma ${
                            item.disponivel ? '' : 'indisponivel'
                          }`}
                          key={item.plataforma}
                        >
                          <div className="jogo-preco-plataforma-cabecalho">
                            <span
                              className={`jogo-preco-plataforma-badge ${
                                item.plataforma === 'Steam' ? 'steam' : 'epic'
                              }`}
                            >
                              {item.plataforma}
                            </span>
                          </div>

                          <div className="jogo-preco-item">
                            <span>Preço atual</span>
                            <strong>
                              {item.disponivel
                                ? formatarPreco(item.precoAtual)
                                : '—'}
                            </strong>
                          </div>

                          <div className="jogo-preco-item">
                            <span>Menor preço histórico</span>
                            <strong>
                              {item.disponivel
                                ? formatarPreco(item.menorPreco)
                                : '—'}
                            </strong>
                          </div>
                        </div>
                      ))
                    ) : (
                      <>
                        <div className="jogo-preco-plataforma jogo-preco-plataforma-unica">
                          <div className="jogo-preco-plataforma-cabecalho">
                            <span
                              className={`jogo-preco-plataforma-badge ${
                                plataformaPaginaAtiva === 'Steam' ? 'steam' : 'epic'
                              }`}
                            >
                              {plataformaPaginaAtiva}
                            </span>
                          </div>

                          <div className="jogo-preco-item">
                            <span>Preço atual</span>
                            <strong>{formatarPreco(precoAtualSelecionado)}</strong>
                          </div>

                          <div className="jogo-preco-item">
                            <span>Menor preço histórico</span>
                            <strong>
                              {formatarPreco(analise?.precoMinimo)}
                            </strong>
                          </div>
                        </div>
                      </>
                    )}
                  </div>

                  <Link
                    to={`/jogos/${jogoSelecionado.id}`}
                    className="ofertas-link-detalhes"
                  >
                    Ver detalhes do jogo
                  </Link>

                  <div className="jogo-promocoes-bloco">
                    <span className="jogo-promocoes-titulo">
                      Histórico promocional
                    </span>

                    <div className="jogo-promocoes-plataformas">
                      {resumoPromocoesPlataforma
                        .filter(
                          (item) =>
                            plataformaAnalise === 'ambas' ||
                            item.plataforma === plataformaAnalise
                        )
                        .map((item) => (
                        <div
                          key={item.plataforma}
                          className={`jogo-promocao-plataforma ${
                            !item.disponivel ? 'indisponivel' : ''
                          }`}
                        >
                          <span
                            className={`jogo-preco-plataforma-badge ${
                              item.plataforma === 'Steam' ? 'steam' : 'epic'
                            }`}
                          >
                            {item.plataforma}
                          </span>
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
              </div>
            </section>

            <section className="ofertas-secao">
              <div className="previsao-card">
                <div className="previsao-principal">
                  <span className="eyebrow">PREVISÃO</span>
                  <h2>Previsão de comportamento</h2>

                  {plataformaPaginaAtiva === 'ambas' ? (
                    <>
                      <strong className="previsao-comparacao-titulo">
                        Panorama das plataformas
                      </strong>
                      <p>{obterTextoPrevisaoAmbas(resumoPrecosPorPlataforma)}</p>
                    </>
                  ) : (
                    <>
                      <strong className={`tendencia-${analise?.nivel || 'insuficiente'}`}>
                        {analise?.tendencia || 'Dados insuficientes'}
                      </strong>

                      <p>{textoPrevisao}</p>
                    </>
                  )}
                </div>

                {plataformaPaginaAtiva === 'ambas' ? (
                  <>
                    <div className="previsoes-comparacao">
                    {resumoPrecosPorPlataforma.map((item) => (
                      <div
                        className={`previsao-plataforma ${
                          item.disponivel ? '' : 'indisponivel'
                        }`}
                        key={item.plataforma}
                      >
                        <div className="previsao-plataforma-cabecalho">
                          <span
                            className={`previsao-plataforma-badge ${
                              item.plataforma === 'Steam' ? 'steam' : 'epic'
                            }`}
                          >
                            {item.plataforma}
                          </span>

                        </div>

                        {item.disponivel ? (
                          <>
                            <div className="previsao-indicadores">
                              <div>
                                <span>Estado atual</span>
                                <strong>
                                  {item.analise.promocaoAtual.ativa
                                    ? 'Promoção'
                                    : 'Preço normal'}
                                </strong>
                              </div>

                              <div>
                                <span>
                                  {item.analise.previsao.tipo === 'fim_promocao'
                                    ? 'Retorno ao normal'
                                    : 'Tendência'}
                                </span>
                                <strong>
                                  {item.analise.previsao.tipo === 'fim_promocao' &&
                                  item.analise.promocaoAtual.fim
                                    ? formatarDataGrafico(item.analise.promocaoAtual.fim)
                                    : item.analise.previsao.rotulo}
                                </strong>
                              </div>

                              <div>
                                <span>
                                  {item.analise.previsao.tipo === 'fim_promocao'
                                    ? 'Próxima promoção'
                                    : 'Janela provável'}
                                </span>
                                <strong>
                                  {item.analise.previsao.tipo === 'fim_promocao' &&
                                  item.analise.previsao.dataEstimada
                                    ? formatarDataGrafico(item.analise.previsao.dataEstimada)
                                    : formatarJanelaPrevisao(item.analise.previsao)}
                                </strong>
                              </div>

                              <div>
                                <span>Preço estimado</span>
                                <strong>
                                  {item.analise.previsao.precoEstimado !== null
                                    ? formatarPreco(
                                        item.analise.previsao.precoEstimado
                                      )
                                    : '—'}
                                </strong>
                              </div>
                            </div>

                          </>
                        ) : (
                          <p className="ofertas-explicacao">
                            Não há histórico suficiente para esta plataforma.
                          </p>
                        )}
                      </div>
                    ))}
                  </div>

                  </>
                ) : (
                  <div className="previsao-indicadores">
                    <div>
                      <span>Estado atual</span>
                      <strong>
                        {analise?.promocaoAtual.ativa
                          ? 'Promoção'
                          : analise
                            ? 'Preço normal'
                            : '—'}
                      </strong>
                    </div>

                    <div>
                      <span>
                        {previsaoSelecionada?.tipo === 'fim_promocao'
                          ? 'Retorno ao normal'
                          : 'Tendência'}
                      </span>
                      <strong>
                        {previsaoSelecionada?.tipo === 'fim_promocao' &&
                        analise?.promocaoAtual?.fim
                          ? formatarDataGrafico(analise.promocaoAtual.fim)
                          : previsaoSelecionada?.rotulo || '—'}
                      </strong>
                    </div>

                    <div>
                      <span>
                        {previsaoSelecionada?.tipo === 'fim_promocao'
                          ? 'Próxima promoção'
                          : 'Janela provável'}
                      </span>
                      <strong>
                        {previsaoSelecionada?.tipo === 'fim_promocao' &&
                        previsaoSelecionada?.dataEstimada
                          ? formatarDataGrafico(previsaoSelecionada.dataEstimada)
                          : formatarJanelaPrevisao(previsaoSelecionada)}
                      </strong>
                    </div>

                    <div>
                      <span>Preço estimado</span>
                      <strong>
                        {previsaoSelecionada?.precoEstimado !== null &&
                        previsaoSelecionada?.precoEstimado !== undefined
                          ? formatarPreco(previsaoSelecionada.precoEstimado)
                          : '—'}
                      </strong>
                    </div>
                  </div>
                )}

              </div>
            </section>

            <section className="ofertas-secao">
              <div className="ofertas-titulo-secao">
                <span className="eyebrow">HISTÓRICO</span>
                <h2>Histórico de preços</h2>
              </div>

              <div className="ofertas-grafico-card">
                <GraficoHistoricoOfertas
                  historico={historicoJogo}
                  plataforma={plataformaPaginaAtiva}
                  onPlataformaChange={setPlataformaAnalise}
                  periodo={periodoGrafico}
                  onPeriodoChange={setPeriodoGrafico}
                  jogo={jogoSelecionado}
                  comportamentoDesenvolvedora={comportamento}
                />
              </div>

              {plataformaPaginaAtiva === 'ambas' ? (
                <div className="indicadores-plataformas">
                  {resumoPrecosPorPlataforma.map((item) => (
                    <div className="indicadores-plataforma" key={item.plataforma}>
                      <div className="indicadores-plataforma-cabecalho">
                        <span
                          className={`previsao-plataforma-badge ${
                            item.plataforma === 'Steam' ? 'steam' : 'epic'
                          }`}
                        >
                          {item.plataforma}
                        </span>
                      </div>

                      <div className="ofertas-indicadores">
                        <div>
                          <span>Menor preço</span>
                          <strong>
                            {formatarPreco(
                              analisesIndicadoresPorPlataforma[item.plataforma]
                                .precoMinimo
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>Maior desconto</span>
                          <strong>
                            {analisesIndicadoresPorPlataforma[item.plataforma]
                              .maiorDesconto}%
                          </strong>
                        </div>

                        <div>
                          <span>Preço médio</span>
                          <strong>
                            {formatarPreco(
                              analisesIndicadoresPorPlataforma[item.plataforma]
                                .precoMedio
                            )}
                          </strong>
                        </div>

                        <div>
                          <span>Promoções</span>
                          <strong>
                            {analisesIndicadoresPorPlataforma[item.plataforma]
                              .episodios.length}
                          </strong>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="ofertas-indicadores">
                  <div>
                    <span>Menor preço · {plataformaPaginaAtiva}</span>
                    <strong>
                      {formatarPreco(
                        analisesIndicadoresPorPlataforma[plataformaPaginaAtiva]
                          ?.precoMinimo
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>Maior desconto</span>
                    <strong>
                      {analisesIndicadoresPorPlataforma[plataformaPaginaAtiva]
                        ?.maiorDesconto ?? 0}%
                    </strong>
                  </div>

                  <div>
                    <span>Preço médio</span>
                    <strong>
                      {formatarPreco(
                        analisesIndicadoresPorPlataforma[plataformaPaginaAtiva]
                          ?.precoMedio
                      )}
                    </strong>
                  </div>

                  <div>
                    <span>Promoções</span>
                    <strong>
                      {analisesIndicadoresPorPlataforma[plataformaPaginaAtiva]
                        ?.episodios.length ?? 0}
                    </strong>
                  </div>
                </div>
              )}
            </section>

            <section className="ofertas-secao">
              <div className="ofertas-titulo-secao">
                <span className="eyebrow">DISTRIBUIDORA</span>
                <h2>Comportamento da distribuidora</h2>
                <p>
                  Como {comportamento?.nome || 'esta distribuidora'} costuma se comportar em promoções
                  {plataformaPaginaAtiva === 'ambas'
                    ? ' nas plataformas analisadas.'
                    : ` na ${plataformaPaginaAtiva}.`}
                </p>
              </div>

              <div className="desenvolvedora-comportamento-card">
                <div className="desenvolvedora-cabecalho">
                  <div>
                    <span className="desenvolvedora-nome">
                      {comportamento?.nome || 'Desenvolvedora não informada'}
                    </span>
                    <div className="desenvolvedora-plataformas">
                      {(plataformaPaginaAtiva === 'ambas'
                        ? ['Steam', 'Epic']
                        : [plataformaPaginaAtiva]
                      ).map((plataformaItem) => (
                        <span
                          className={`desenvolvedora-tag desenvolvedora-tag-${plataformaItem.toLowerCase()}`}
                          key={plataformaItem}
                        >
                          {plataformaItem}
                        </span>
                      ))}
                    </div>
                  </div>

                  <div className="desenvolvedora-filtro">
                    {[
                      ['ambas', 'Ambas'],
                      ['Steam', 'Steam'],
                      ['Epic', 'Epic'],
                    ].map(([valor, rotulo]) => {
                      const disponivel =
                        valor === 'ambas' || plataformasDisponiveisJogo.has(valor)

                      return (
                        <button
                          key={valor}
                          type="button"
                          className={plataformaPaginaAtiva === valor ? 'ativo' : ''}
                          disabled={!disponivel}
                          onClick={() => disponivel && setPlataformaAnalise(valor)}
                        >
                          {rotulo}
                        </button>
                      )
                    })}
                  </div>
                </div>

                {!comportamento?.suficiente ? (
                  <div className="desenvolvedora-sem-historico">
                    <strong>Histórico insuficiente</strong>
                    <span>
                      Ainda não há registros promocionais suficientes para identificar um padrão confiável dessa distribuidora nesta plataforma.
                    </span>
                  </div>
                ) : (
                  <>
                    <div className="desenvolvedora-caracteristicas">
                      {comportamento.caracteristicas.map((caracteristica) => (
                        <span key={caracteristica}>{caracteristica}</span>
                      ))}
                    </div>

                    <div className="desenvolvedora-sazonalidade">
                      <div className="desenvolvedora-subtitulo">
                        <span>ATIVIDADE PROMOCIONAL AO LONGO DO ANO</span>
                        {comportamento.mesesDestaque.length > 0 && (
                          <small>
                            Maior atividade: {comportamento.mesesDestaque.join(' e ')}
                          </small>
                        )}
                      </div>

                      <div className="desenvolvedora-meses">
                        {[
                          'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun',
                          'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez',
                        ].map((mes, indice) => {
                          const valor = comportamento.meses[indice]
                          const maximo = Math.max(...comportamento.meses, 1)
                          const intensidade = valor / maximo

                          return (
                            <div className="desenvolvedora-mes" key={mes}>
                              <div
                                className="desenvolvedora-mes-barra"
                                style={{ '--intensidade': intensidade }}
                                title={`${mes}: ${valor} episódio${valor === 1 ? '' : 's'} promocional(is)`}
                              >
                                <span />
                              </div>
                              <small>{mes}</small>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {comportamento.jogosEmPromocao.length > 0 ? (
                      <div className="desenvolvedora-contexto">
                        <div className="desenvolvedora-subtitulo">
                          <span>🔥 EM PROMOÇÃO</span>
                          <small>Agora</small>
                        </div>

                        <div className="desenvolvedora-jogos-grid">
                          {comportamento.jogosEmPromocao.map((item) => (
                            <button
                              type="button"
                              className="desenvolvedora-jogo"
                              onClick={() => selecionarJogo(item)}
                              key={item.id}
                            >
                              <img src={imagemDoJogo(item)} alt="" />
                              <div>
                                <strong>{item.nome}</strong>

                                <div className="desenvolvedora-tags">
                                  {(item.plataformasEmPromocao || []).map(
                                    (plataformaItem) => (
                                      <span
                                        className={`desenvolvedora-tag desenvolvedora-tag-${plataformaItem.plataforma.toLowerCase()}`}
                                        key={plataformaItem.plataforma}
                                      >
                                        {plataformaItem.plataforma}
                                      </span>
                                    )
                                  )}
                                </div>

                                <span>
                                  {item.plataformasEmPromocao?.length === 1
                                    ? `${item.plataformasEmPromocao[0].promocaoNome} · -${item.plataformasEmPromocao[0].desconto}%`
                                    : `Descontos de até -${item.desconto}%`}
                                </span>

                                <div className="desenvolvedora-jogo-detalhes">
                                  {item.plataformasEmPromocao?.map(
                                    (plataformaItem) => (
                                      <span key={`${item.id}-${plataformaItem.plataforma}`}>
                                        {plataformaItem.precoAtual !== null
                                          ? `${plataformaItem.plataforma}: ${formatarPreco(plataformaItem.precoAtual)}`
                                          : `${plataformaItem.plataforma}: preço indisponível`}
                                      </span>
                                    )
                                  )}
                                </div>

                                <div className="desenvolvedora-jogo-fim">
                                  {item.plataformasEmPromocao?.map(
                                    (plataformaItem) => (
                                      <span key={`${item.id}-fim-${plataformaItem.plataforma}`}>
                                        {plataformaItem.fimPromocao
                                          ? `${plataformaItem.plataforma} · até ${new Date(
                                              plataformaItem.fimPromocao
                                            ).toLocaleDateString('pt-BR')}`
                                          : `${plataformaItem.plataforma} · fim não informado`}
                                      </span>
                                    )
                                  )}
                                </div>
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="desenvolvedora-contexto">
                        <div className="desenvolvedora-subtitulo">
                          <span>👀 JOGOS PARA ACOMPANHAR</span>
                          <small>Ordenados pelo desconto previsto</small>
                        </div>

                        {comportamento.jogosAcompanhar.length > 0 ? (
                          <div className="desenvolvedora-jogos-grid">
                            {comportamento.jogosAcompanhar.map((item) => (
                              <button
                                type="button"
                                className="desenvolvedora-jogo"
                                onClick={() => selecionarJogo(item)}
                                key={item.id}
                              >
                                <img src={imagemDoJogo(item)} alt="" />
                                <div>
                                  <strong>{item.nome}</strong>

                                  <div className="desenvolvedora-tags">
                                    {(item.plataformasAnalisadas || []).map(
                                      (plataformaItem) => (
                                        <span
                                          className={`desenvolvedora-tag desenvolvedora-tag-${plataformaItem.toLowerCase()}`}
                                          key={plataformaItem}
                                        >
                                          {plataformaItem}
                                        </span>
                                      )
                                    )}
                                  </div>

                                  <span>
                                    {Number.isFinite(Number(item.descontoPrevisto))
                                      ? `Desconto previsto: ${Math.round(item.descontoPrevisto)}%`
                                      : 'Desconto previsto: sem estimativa'}
                                    {item.precoPrevisto !== null
                                      ? ` · Preço previsto: ${formatarPreco(item.precoPrevisto)}`
                                      : ''}
                                  </span>

                                  <span>
                                    {item.diasDesdePromocao !== null
                                      ? `Última promoção: ${Math.round(item.diasDesdePromocao)} dias atrás`
                                      : 'Última promoção: sem data disponível'}
                                    {item.intervaloMedio !== null
                                      ? ` · Intervalo histórico: ${Math.round(
                                          item.intervaloMedio
                                        )} dias`
                                      : ''}
                                  </span>
                                </div>
                              </button>
                            ))}
                          </div>
                        ) : (
                          <span className="desenvolvedora-vazio">
                            Não há outros jogos com histórico promocional suficiente para acompanhar.
                          </span>
                        )}
                      </div>
                    )}
                  </>
                )}
              </div>
            </section>
          </>
        ) : null}

        {!carregando && melhoresTendencias.length > 0 && (
          <section className="ofertas-secao">
            <div className="ofertas-titulo-secao">
              <span className="eyebrow">EXPLORE</span>
              <h2>Sugestões para análise</h2>
              <p>
                Jogos selecionados pelo histórico promocional, previsão e qualidade dos dados.
              </p>
            </div>

            <div className="tendencias-grade">
              {melhoresTendencias.map(({ jogo }) => (
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
                      {jogo.publicadora ||
                        'Publicadora não informada'}
                    </span>


                  </div>
                </button>
              ))}
            </div>
          </section>
        )}
      </main>

    </div>
  )
}

export default Ofertas
