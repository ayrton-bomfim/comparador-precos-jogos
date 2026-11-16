// Constantes e funções compartilhadas pela página de Curadoria.

export const MOTIVOS_APROVACAO = [
  'Dentro do escopo do catálogo',
  'Informações validadas',
  'Conteúdo considerado adequado',
  'Teste e validação',
  'Outros',
]

export const MOTIVOS_AUDITORIA = [
  'Conteúdo sensível',
  'Fora do catálogo',
  'Duplicado ou redundante',
  'Indisponível ou removido',
  'Problemas de qualidade ou integridade',
  'Outros',
]

// Exclusões com estes motivos também encaminham jogos da mesma
// desenvolvedora/publicadora para revisão (regra do backend).
export const MOTIVOS_COM_RELACIONADOS = ['Conteúdo sensível', 'Fora do catálogo']

export const ITENS_POR_PAGINA = 50

export const ABAS = [
  { id: 'pendentes', rotulo: 'Aguardando análise' },
  { id: 'sensivel', rotulo: 'Conteúdo sensível' },
  { id: 'aprovados', rotulo: 'Aprovados' },
  { id: 'excluidos', rotulo: 'Excluídos' },
  { id: 'vitrine', rotulo: 'Vitrine' },
  { id: 'feedback', rotulo: 'Feedback' },
]

// Abas que exibem uma fila de auditorias (lista + painel de decisão).
export const ABAS_FILA = ['pendentes', 'sensivel', 'aprovados', 'excluidos']
export const ABAS_DECISAO = ['pendentes', 'sensivel']

// Descritores de conteúdo da Steam (content_descriptors.ids).
export const DESCRITORES_STEAM = {
  1: 'Alguma nudez ou conteúdo sexual',
  2: 'Violência ou sangue frequentes',
  3: 'Conteúdo sexual somente para adultos',
  4: 'Nudez ou conteúdo sexual frequentes',
  5: 'Conteúdo adulto geral',
}

export function rotaDaFila(aba) {
  if (aba === 'pendentes') return '/api/admin/curadoria/pendentes'
  if (aba === 'sensivel') return '/api/admin/curadoria/conteudo-sensivel'
  if (aba === 'aprovados') return '/api/admin/curadoria/status/aprovado'
  return '/api/admin/curadoria/status/excluido'
}

export function motivosDoFiltro(aba) {
  if (aba === 'aprovados') return MOTIVOS_APROVACAO
  if (aba === 'pendentes') return MOTIVOS_AUDITORIA.filter((motivo) => motivo !== 'Conteúdo sensível')
  if (aba === 'excluidos') return MOTIVOS_AUDITORIA
  return []
}

export function extrairPrioridade(observacao) {
  const texto = String(observacao || '')
  const correspondencia = texto.match(/Prioridade de revisão:\s*(P[1-5])\s*-\s*([^\r\n]+)/i)
  if (!correspondencia) return null

  const codigo = correspondencia[1].toUpperCase()
  return { codigo, rotulo: `${codigo} - ${correspondencia[2].trim()}` }
}

export function normalizarImagens(item, incluirGaleria = true) {
  const imagens = incluirGaleria && Array.isArray(item.imagens) ? item.imagens : []
  const resultado = []
  const vistos = new Set()

  for (const imagem of imagens) {
    const url = typeof imagem === 'string' ? imagem : imagem?.url
    if (!url || vistos.has(url)) continue
    vistos.add(url)
    resultado.push({ url, tipo: typeof imagem === 'object' ? imagem?.tipo : null })
  }

  // Antes do clique em "Carregar galeria", mostra só as capas já cadastradas.
  const capas = [
    { url: item.imagem_steam, tipo: 'Capa Steam' },
    { url: item.imagem_epic, tipo: 'Capa Epic' },
  ]
  for (const capa of capas) {
    if (capa.url && !vistos.has(capa.url)) {
      vistos.add(capa.url)
      resultado.unshift(capa)
    }
  }

  return resultado
}

export function obterUrlSteam(item) {
  const url = String(item?.url_steam || '').trim()
  // URLs de busca não contam como link direto.
  if (url && !/\/search(?:\/|\?)/i.test(url)) return url

  const steamId = String(item?.steam_id || '').trim()
  return /^\d+$/.test(steamId) ? `https://store.steampowered.com/app/${steamId}/` : ''
}

export function obterUrlEpic(item) {
  const url = String(item?.url_epic || '').trim()
  if (url) return url
  const epicId = String(item?.epic_id || '').trim()
  return epicId ? `https://store.epicgames.com/pt-BR/p/${epicId}` : ''
}

export function linksDaLoja(item) {
  const links = []
  const steam = obterUrlSteam(item)
  const epic = obterUrlEpic(item)
  if (steam) links.push({ rotulo: 'Steam', url: steam })
  if (epic) links.push({ rotulo: 'Epic Games', url: epic })
  if (!links.length) {
    links.push({
      rotulo: 'Buscar na Steam',
      url: `https://store.steampowered.com/search/?term=${encodeURIComponent(item?.nome || '')}`,
    })
  }
  return links
}

export function imagemDeCapa(item) {
  return item?.imagem_steam || item?.imagem_epic || ''
}

export function deveBorrar(item, aba, imagensBorradas) {
  if (!imagensBorradas || !item) return false
  return (
    aba === 'sensivel' ||
    item.motivo === 'Conteúdo sensível' ||
    Boolean(item.steam_conteudo_adulto)
  )
}

export function rotuloOrigem(origem) {
  if (origem === 'triagem_adulto') return 'Triagem automática'
  if (origem === 'automatico') return 'Automática'
  if (origem === 'manual') return 'Manual'
  return origem || 'Manual'
}

export function formatarData(valor, comHora = false) {
  if (!valor) return ''
  // Datas sem horário (AAAA-MM-DD) são tratadas como data local.
  const data = /^\d{4}-\d{2}-\d{2}$/.test(valor) ? new Date(`${valor}T00:00:00`) : new Date(valor)
  if (Number.isNaN(data.getTime())) return ''
  return comHora ? data.toLocaleString('pt-BR') : data.toLocaleDateString('pt-BR')
}

export function formatarNumero(valor) {
  return Number(valor || 0).toLocaleString('pt-BR')
}

export function campoDeTextoEmFoco(elemento) {
  if (!elemento) return false
  const tag = elemento.tagName
  // Caixas de seleção não recebem texto: os atalhos continuam valendo nelas.
  if (tag === 'INPUT') return !['checkbox', 'radio', 'button', 'submit'].includes(elemento.type)
  return tag === 'TEXTAREA' || tag === 'SELECT' || elemento.isContentEditable
}
