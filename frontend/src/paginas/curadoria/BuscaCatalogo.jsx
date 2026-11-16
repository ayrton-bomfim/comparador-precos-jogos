import { useState } from 'react'
import { API_BASE } from '../../contextos/AuthContext'

// Busca no catálogo completo, usada para enviar jogos à fila e para a vitrine.
// As ações de cada resultado são definidas por quem usa o componente.
function BuscaCatalogo({ getHeaders, renderAcoes, placeholder, autoFocus = false }) {
  const [termo, setTermo] = useState('')
  const [resultados, setResultados] = useState([])
  const [carregando, setCarregando] = useState(false)
  const [erro, setErro] = useState('')
  const [pesquisado, setPesquisado] = useState(false)

  const pesquisar = async (event) => {
    event.preventDefault()
    const texto = termo.trim()
    if (texto.length < 2) {
      setErro('Digite pelo menos 2 caracteres.')
      return
    }

    setCarregando(true)
    setErro('')
    try {
      const resposta = await fetch(
        `${API_BASE}/api/admin/curadoria/buscar?termo=${encodeURIComponent(texto)}`,
        { headers: getHeaders() }
      )
      const dados = await resposta.json().catch(() => [])
      if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível realizar a busca.')
      setResultados(Array.isArray(dados) ? dados : [])
      setPesquisado(true)
    } catch (error) {
      setErro(error.message)
    } finally {
      setCarregando(false)
    }
  }

  return (
    <div className="cur-busca-catalogo">
      <form onSubmit={pesquisar} role="search">
        <input
          type="search"
          value={termo}
          onChange={(event) => {
            setTermo(event.target.value)
            if (!event.target.value.trim()) {
              setResultados([])
              setPesquisado(false)
            }
          }}
          placeholder={placeholder}
          aria-label="Pesquisar jogo, desenvolvedora ou publicadora no catálogo"
          autoFocus={autoFocus}
        />
        <button type="submit" disabled={carregando}>{carregando ? 'Buscando...' : 'Pesquisar'}</button>
      </form>

      {erro && <p className="cur-busca-erro" role="alert">{erro}</p>}
      {pesquisado && !resultados.length && !erro && (
        <p className="cur-busca-vazia">Nenhum jogo encontrado para “{termo.trim()}”.</p>
      )}

      {resultados.length > 0 && (
        <ul className="cur-busca-resultados" aria-label="Resultados da pesquisa">
          {resultados.map((jogo) => {
            const capa = jogo.imagem_steam || jogo.imagem_epic
            return (
              <li key={jogo.id}>
                {capa ? <img src={capa} alt="" loading="lazy" /> : <span className="cur-sem-imagem">LOJA</span>}
                <div className="cur-busca-info">
                  <strong>{jogo.nome}</strong>
                  <span>{[jogo.desenvolvedor, jogo.steam_id || jogo.epic_id].filter(Boolean).join(' · ')}</span>
                </div>
                <div className="cur-busca-acoes">{renderAcoes(jogo)}</div>
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}

export default BuscaCatalogo
