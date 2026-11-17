import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import Cabecalho from '../componentes/Cabecalho'
import CarrosselJogos from '../componentes/CarrosselJogos'
import DestaqueInicio from '../componentes/DestaqueInicio'
import VitrineBrasil from '../componentes/VitrineBrasil'
import { API_JOGOS_URL } from '../servicos/api'

const PASSOS_COMO_FUNCIONA = [
  ['Coletamos', 'Os preços da Steam e da Epic Games Store são consultados periodicamente e guardados num histórico.'],
  ['Comparamos', 'Para cada jogo, mostramos o preço nas duas lojas e destacamos onde ele está mais barato.'],
  ['Prevemos', 'Com o histórico, estimamos a tendência de preço para você decidir entre comprar agora ou esperar.'],
]

function Inicio() {
  const [secoesVitrine, setSecoesVitrine] = useState({ brasileiros: [], comunidade: [], em_alta: [], oportunidades: [] })
  const [vitrineCarregada, setVitrineCarregada] = useState(false)
  const [resumo, setResumo] = useState(null)
  const [destaques, setDestaques] = useState([])
  const [panoramaBrasil, setPanoramaBrasil] = useState(null)

  useEffect(() => {
    let ativo = true

    async function carregarVitrine() {
      try {
        const resposta = await fetch(`${API_JOGOS_URL}/vitrine/secoes`)
        if (!resposta.ok) throw new Error('Não foi possível carregar a vitrine.')
        const dados = await resposta.json()
        if (ativo) setSecoesVitrine({
          brasileiros: dados.brasileiros || [],
          comunidade: dados.comunidade || [],
          em_alta: dados.em_alta || [],
          oportunidades: dados.oportunidades || [],
        })
      } catch (erro) {
        console.error('Erro ao carregar as seções da vitrine:', erro)
      } finally {
        if (ativo) setVitrineCarregada(true)
      }
    }

    // Dados complementares: se falharem, a página continua com as seções principais.
    async function carregar(caminho, aplicar) {
      try {
        const resposta = await fetch(`${API_JOGOS_URL}${caminho}`)
        if (resposta.ok) {
          const dados = await resposta.json()
          if (ativo) aplicar(dados)
        }
      } catch (erro) {
        console.error(`Erro ao carregar ${caminho}:`, erro)
      }
    }

    carregarVitrine()
    carregar('/vitrine/resumo', setResumo)
    carregar('/vitrine/destaques', (dados) => setDestaques(Array.isArray(dados) ? dados : []))
    carregar('/vitrine/brasil', setPanoramaBrasil)
    return () => { ativo = false }
  }, [])

  // Topo: ofertas relevantes escolhidas automaticamente; na falta delas,
  // as oportunidades da curadoria e, por último, os jogos em alta.
  const ofertasDestaque = [destaques, secoesVitrine.oportunidades, secoesVitrine.em_alta]
    .find((lista) => lista.length > 0) || []

  return (
    <>
      <Cabecalho />

      <main>
        <DestaqueInicio ofertas={ofertasDestaque} resumo={resumo} carregando={!vitrineCarregada} />

        <VitrineBrasil selecao={secoesVitrine.brasileiros} panorama={panoramaBrasil} />

        <SecaoJogos
          eyebrow="EM ALTA"
          titulo="Em alta no DESCTRL"
          jogos={secoesVitrine.em_alta}
          destino="/jogos"
          ocultarSeVazia={vitrineCarregada}
        />

        <SecaoJogos
          eyebrow="CURADORIA DESCTRL"
          titulo="Oportunidades de preço"
          jogos={secoesVitrine.oportunidades}
          mostrarDesconto
          destino="/jogos?filtro=desconto"
          ocultarSeVazia={vitrineCarregada}
        />

        <SecaoJogos
          eyebrow="A COMUNIDADE ESCOLHE"
          titulo="Recomendados pela comunidade"
          jogos={secoesVitrine.comunidade}
          destino="/jogos"
          ocultarSeVazia={vitrineCarregada}
          selo={(jogo) => (
            jogo.origem === 'curadoria'
              ? 'Indicação da curadoria'
              : jogo.total_recomendacoes > 0
                ? `${jogo.total_recomendacoes} ${jogo.total_recomendacoes === 1 ? 'recomendação' : 'recomendações'}`
                : null
          )}
        />

        <section className="secao secao-como-funciona" aria-labelledby="titulo-como-funciona">
          <div className="secao-cabecalho">
            <div>
              <span className="eyebrow">COMO FUNCIONA</span>
              <h2 id="titulo-como-funciona">Do preço de hoje à hora certa de comprar</h2>
            </div>
          </div>
          <ol className="como-funciona-passos">
            {PASSOS_COMO_FUNCIONA.map(([titulo, texto], posicao) => (
              <li key={titulo}>
                <span aria-hidden="true">{posicao + 1}</span>
                <h3>{titulo}</h3>
                <p>{texto}</p>
              </li>
            ))}
          </ol>
        </section>
      </main>
    </>
  )
}

function SecaoJogos({
  eyebrow,
  titulo,
  jogos,
  mostrarDesconto = false,
  destino = '/jogos',
  classeExtra = '',
  ocultarSeVazia = false,
  selo = null,
}) {
  // Depois do carregamento, uma seção sem jogos some em vez de mostrar um carrossel vazio.
  if (ocultarSeVazia && !jogos.length) return null

  return (
    <section className={`secao secao-catalogo ${classeExtra}`.trim()}>
      <div className="secao-cabecalho">
        <div className="secao-titulo">
          <span className="eyebrow">{eyebrow}</span>
          <h2>{titulo}</h2>
        </div>

        <NavLink className="link-secao" to={destino}>
          Ver todos
        </NavLink>
      </div>

      <CarrosselJogos
        jogos={jogos}
        mostrarDesconto={mostrarDesconto}
        selo={selo}
      />
    </section>
  )
}

export default Inicio