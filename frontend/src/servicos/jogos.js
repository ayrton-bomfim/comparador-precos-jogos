import { API_URL } from './api'


export async function buscarJogo(id) {
  const resposta = await fetch(`${API_URL}/api/jogos/${id}`)

  if (!resposta.ok) {
    throw new Error('Não foi possível carregar os dados do jogo.')
  }

  return resposta.json()
}

export async function buscarHistoricoJogo(id) {
  const resposta = await fetch(`${API_URL}/api/jogos/${id}/historico`)

  if (!resposta.ok) {
    throw new Error('Não foi possível carregar o histórico de preços.')
  }

  return resposta.json()
}