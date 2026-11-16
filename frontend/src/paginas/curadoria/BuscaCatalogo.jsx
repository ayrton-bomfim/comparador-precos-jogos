import { useEffect, useRef, useState } from 'react'
import { API_BASE } from '../../contextos/AuthContext'

const ROTULO_AUDITORIA = {
  pendente: 'Na fila de análise',
  aprovado: 'Aprovado',
  excluido: 'Excluído',
}

const ROTULO_VITRINE = {
  oportunidade: 'Oportunidades',
  curadoria_comunidade: 'Indicação',
  jogo_brasileiro: 'Brasil em jogo',
}

// Busca no catálogo completo (mesmos campos e regras dos filtros da Curadoria:
// nome, ID, estúdio, publicadora ou gênero, sem diferenciar acentos).
// Pesquisa enquanto se digita, a partir de 2 caracteres.
function BuscaCatalogo({ getHeaders, renderAcoes, placeholder, autoFocus = false }) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState([])
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [pesquisado, setPesquisado] = useState('')
  const sequencia = useRef(0)

  useEffect(() => {
    const texto = termo.trim()
    if (texto.length < 2) return undefined

    const temporizador = window.setTimeout(async () => {
      const atual = ++sequencia.current
      setCarregando(true)
      setErro('')
      try {
        const resposta = await fetch(
          `${API_BASE}/api/admin/curadoria/buscar?termo=${encodeURIComponent(texto)}`,
          { headers: getHeaders() }
        )
        const dados = await resposta.json().catch(() => [])
        if (atual !== sequencia.current) return
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível realizar a busca.')
        setResultados(Array.isArray(dados) ? dados : [])
        setPesquisado(texto)
      } catch (error) {
        if (atual === sequencia.current) setErro(error.message)
      } finally {
        if (atual === sequencia.current) setCarregando(false)
      }
    }, 350)
    return () => window.clearTimeout(temporizador)
  }, [termo, getHeaders])

  const textoAtual = termo.trim()
  const visiveis = textoAtual.length >= 2 ? resultados : []

  return (
    <div className="cur-busca-catalogo">
      <div className="cur-busca-campo" role="search">
        <input
          type="search"
          value={termo}
          onChange={(event) => setTermo(event.target.value)}
          placeholder={placeholder}
          aria-label="Pesquisar jogo no catálogo"
          autoFocus={autoFocus}
        />
        {carregando && <span className="cur-busca-carregando" aria-live="polite">Buscando...</span>}
      </div>

      {erro && <p className="cur-busca-erro" role="alert">{erro}</p>}
      {textoAtual.length === 1 && <p className="cur-busca-vazia">Digite pelo menos 2 caracteres.</p>}
      {!carregando && pesquisado && pesquisado === textoAtual && !visiveis.length && !erro && (
        <p className="cur-busca-vazia">Nenhum jogo encontrado para “{pesquisado}”.</p>
      )}

      {visiveis.length > 0 && (
        <>
          <p className="cur-busca-contagem">
            {visiveis.length >= 40 ? 'Mostrando os 40 primeiros resultados. Refine a busca para ver outros.' : `${visiveis.length} resultado(s)`}
          </p>
          <ul className="cur-busca-resultados" aria-label="Resultados da pesquisa">
            {visiveis.map((jogo) => {
              const capa = jogo.imagem_steam || jogo.imagem_epic
              return (
                <li key={jogo.id}>
                  {capa ? <img src={capa} alt="" loading="lazy" /> : <span className="cur-sem-imagem">LOJA</span>}
                  <div className="cur-busca-info">
                    <strong>{jogo.nome}</strong>
                    <span>{[jogo.desenvolvedor, jogo.steam_id || jogo.epic_id].filter(Boolean).join(' · ')}</span>
                    <span className="cur-busca-situacao">
                      {jogo.auditoria_status && (
                        <span className="cur-tag" title={jogo.auditoria_motivo || ''}>{ROTULO_AUDITORIA[jogo.auditoria_status] || jogo.auditoria_status}</span>
                      )}
                      {(jogo.vitrine || []).map((tipo) => (
                        <span className="cur-tag cur-tag-roxo" key={tipo}>Vitrine: {ROTULO_VITRINE[tipo] || tipo}</span>
                      ))}
                      {jogo.promocao_ativa && <span className="cur-tag cur-tag-desconto">Promoção -{jogo.desconto}%</span>}
                      {jogo.eh_brasileiro && <span className="cur-tag">Brasileiro</span>}
                    </span>
                  </div>
                  <div className="cur-busca-acoes">{renderAcoes(jogo)}</div>
                </li>
              )
            })}
          </ul>
        </>
      )}
    </div>
  )
}

export default BuscaCatalogo
