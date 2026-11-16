import { useCallback, useEffect, useState } from 'react'
import { API_BASE } from '../../contextos/AuthContext'
import BuscaCatalogo from './BuscaCatalogo'
import { IconeDescer, IconeLixeira, IconeMais, IconeSubir } from './Icones'
import { formatarNumero } from './utilidades'

const SECOES = [
  {
    tipo: 'oportunidade',
    rotulo: 'Oportunidades de preço',
    regra: 'Jogos em promoção ativa na Steam ou na Epic. Saem sozinhos quando a promoção termina.',
    sugestao: 'Promoções ativas entre os jogos mais vistos, com os maiores descontos primeiro.',
  },
  {
    tipo: 'curadoria_comunidade',
    rotulo: 'Indicações para a comunidade',
    regra: 'Completam “Recomendados pela comunidade” depois dos votos dos usuários, com o selo “Indicação da curadoria”. Saem sozinhas quando a promoção termina.',
    sugestao: 'Jogos em promoção ativa, dos mais vistos para os menos vistos.',
  },
  {
    tipo: 'jogo_brasileiro',
    rotulo: 'Brasil em jogo',
    regra: 'Jogos classificados como brasileiros no catálogo. Não dependem de promoção.',
    sugestao: 'Jogos brasileiros mais vistos que ainda não estão na seção.',
  },
]

const SITUACOES = {
  exibido: ['Na página inicial', 'ok'],
  fila: ['Aguardando vaga', 'neutro'],
  aguardando_coleta: ['Promoção sem confirmação recente', 'alerta'],
  oculto_catalogo: ['Fora do catálogo público', 'erro'],
  nao_brasileiro: ['Não classificado como brasileiro', 'erro'],
  pausado: ['Pausado', 'neutro'],
}

const POR_PAGINA = 50

// Gestão da vitrine da página inicial: uma seção por vez, com situação de cada
// item, ordem por setas e sugestões prontas para adicionar.
function SecaoVitrine({ getHeaders, notificar, atualizarContadores }) {
  const [tipo, setTipo] = useState('oportunidade')
  const [itens, setItens] = useState([])
  const [resumo, setResumo] = useState({})
  const [limite, setLimite] = useState(12)
  const [total, setTotal] = useState(0)
  const [pagina, setPagina] = useState(1)
  const [filtroTexto, setFiltroTexto] = useState('')
  const [termo, setTermo] = useState('')
  const [erro, setErro] = useState('')
  const [sugestoes, setSugestoes] = useState([])
  const [acaoId, setAcaoId] = useState(null)
  // "Versões" forçam um novo carregamento depois de uma ação; o estado de
  // carregamento é derivado comparando o pedido atual com o último recebido.
  const [versao, setVersao] = useState(0)
  const [versaoSugestoes, setVersaoSugestoes] = useState(0)
  const [chaveRecebida, setChaveRecebida] = useState('')
  const [chaveSugestoesRecebida, setChaveSugestoesRecebida] = useState('')

  const secao = SECOES.find((item) => item.tipo === tipo)
  const chaveLista = `${tipo}|${pagina}|${termo}|${versao}`
  const chaveSugestoes = `${tipo}|${versaoSugestoes}`
  const carregando = chaveRecebida !== chaveLista
  const carregandoSugestoes = chaveSugestoesRecebida !== chaveSugestoes

  const carregar = useCallback(() => setVersao((atual) => atual + 1), [])
  const carregarSugestoes = useCallback(() => setVersaoSugestoes((atual) => atual + 1), [])

  useEffect(() => {
    let ativo = true
    const parametros = new URLSearchParams({ tipo, page: String(pagina), page_size: String(POR_PAGINA) })
    if (termo) parametros.set('q', termo)

    fetch(`${API_BASE}/api/admin/curadoria/vitrine?${parametros}`, { headers: getHeaders() })
      .then(async (resposta) => {
        const dados = await resposta.json().catch(() => ({}))
        if (!resposta.ok) throw new Error(dados.detail || 'Não foi possível carregar a vitrine.')
        return dados
      })
      .then((dados) => {
        if (!ativo) return
        setItens(dados.items || [])
        setTotal(Number(dados.total || 0))
        setResumo(dados.resumo || {})
        setLimite(Number(dados.limite_pagina_inicial || 12))
        setErro('')
        if (dados.removidos_encerrados > 0) {
          notificar(`${dados.removidos_encerrados} item(ns) com promoção encerrada foram removidos automaticamente.`, 'info')
          atualizarContadores()
        }
      })
      .catch((error) => { if (ativo) setErro(error.message) })
      .finally(() => { if (ativo) setChaveRecebida(chaveLista) })

    return () => { ativo = false }
  }, [chaveLista, tipo, pagina, termo, getHeaders, notificar, atualizarContadores])

  useEffect(() => {
    let ativo = true
    fetch(`${API_BASE}/api/admin/curadoria/vitrine/sugestoes?tipo=${tipo}`, { headers: getHeaders() })
      .then(async (resposta) => {
        const dados = await resposta.json().catch(() => [])
        if (ativo) setSugestoes(resposta.ok && Array.isArray(dados) ? dados : [])
      })
      .catch(() => { if (ativo) setSugestoes([]) })
      .finally(() => { if (ativo) setChaveSugestoesRecebida(chaveSugestoes) })
    return () => { ativo = false }
  }, [chaveSugestoes, tipo, getHeaders])

  // O filtro é aplicado 350 ms depois da última tecla, como nas filas.
  useEffect(() => {
    const texto = filtroTexto.trim()
    if (texto === termo) return undefined
    const temporizador = window.setTimeout(() => {
      setTermo(texto)
      setPagina(1)
    }, 350)
    return () => window.clearTimeout(temporizador)
  }, [filtroTexto, termo])

  const trocarSecao = (novoTipo) => {
    if (novoTipo === tipo) return
    setTipo(novoTipo)
    setItens([])
    setSugestoes([])
    setPagina(1)
    setFiltroTexto('')
    setTermo('')
  }

  const chamar = async (url, opcoes, mensagemErro) => {
    const resposta = await fetch(url, { headers: getHeaders(), ...opcoes })
    const dados = await resposta.json().catch(() => ({}))
    if (!resposta.ok) throw new Error(dados.detail || mensagemErro)
    return dados
  }

  // tipoDestino é fixado no momento da ação (importante para o "Desfazer").
  const adicionar = async (jogo, tipoDestino = tipo) => {
    const secaoDestino = SECOES.find((item) => item.tipo === tipoDestino)
    setAcaoId(`add-${jogo.id}`)
    try {
      const dados = await chamar(
        `${API_BASE}/api/admin/curadoria/vitrine/lote`,
        { method: 'POST', body: JSON.stringify({ tipo: tipoDestino, jogo_ids: [jogo.id] }) },
        'Não foi possível adicionar o jogo.'
      )
      if (dados.adicionados?.length) {
        notificar(`${jogo.nome} entrou em “${secaoDestino.rotulo}”.`)
        setSugestoes((atuais) => atuais.filter((sugestao) => sugestao.id !== jogo.id))
        carregar()
        atualizarContadores()
      } else {
        notificar(`${jogo.nome}: ${dados.ignorados?.[0]?.motivo || 'não foi possível adicionar.'}`, 'erro')
      }
    } catch (error) {
      notificar(error.message, 'erro')
    } finally {
      setAcaoId(null)
    }
  }

  const mover = async (item, direcao) => {
    setAcaoId(`mover-${item.id}`)
    try {
      await chamar(
        `${API_BASE}/api/admin/curadoria/vitrine/${item.id}/mover`,
        { method: 'POST', body: JSON.stringify({ direcao }) },
        'Não foi possível mudar a ordem.'
      )
      carregar()
    } catch (error) {
      notificar(error.message, 'erro')
    } finally {
      setAcaoId(null)
    }
  }

  const remover = async (item) => {
    setAcaoId(`remover-${item.id}`)
    try {
      await chamar(`${API_BASE}/api/admin/curadoria/vitrine/${item.id}`, { method: 'DELETE' }, 'Não foi possível remover o item.')
      notificar(`${item.jogo_nome} saiu de “${secao.rotulo}”.`, 'sucesso', {
        rotulo: 'Desfazer',
        onClick: () => adicionar({ id: item.jogo_id, nome: item.jogo_nome }, tipo),
      })
      carregar()
      carregarSugestoes()
      atualizarContadores()
    } catch (error) {
      notificar(error.message, 'erro')
    } finally {
      setAcaoId(null)
    }
  }

  const reativar = async (item) => {
    setAcaoId(`reativar-${item.id}`)
    try {
      await chamar(
        `${API_BASE}/api/admin/curadoria/vitrine/${item.id}`,
        { method: 'PATCH', body: JSON.stringify({ ativo: true }) },
        'Não foi possível reativar o item.'
      )
      carregar()
    } catch (error) {
      notificar(error.message, 'erro')
    } finally {
      setAcaoId(null)
    }
  }

  const totalPaginas = Math.max(1, Math.ceil(total / POR_PAGINA))

  return (
    <section className="cur-secao">
      <div className="cur-secao-topo">
        <div>
          <h2>Vitrine da página inicial</h2>
          <p>Cada seção mostra até {limite} jogos na página inicial, na ordem desta lista. Seções vazias não aparecem no site.</p>
        </div>
      </div>

      <div className="cur-segmentos" role="tablist" aria-label="Seções da vitrine">
        {SECOES.map((item) => {
          const dadosResumo = resumo[item.tipo]
          return (
            <button
              type="button"
              role="tab"
              key={item.tipo}
              aria-selected={tipo === item.tipo}
              className={tipo === item.tipo ? 'ativo' : ''}
              onClick={() => trocarSecao(item.tipo)}
            >
              {item.rotulo}
              {dadosResumo && (
                <span title="Na página inicial / cadastrados">
                  {dadosResumo.na_pagina_inicial}/{dadosResumo.total}
                </span>
              )}
            </button>
          )
        })}
      </div>
      <p className="cur-vitrine-regra">{secao.regra}</p>

      <div className="cur-vitrine-grade">
        <div className="cur-vitrine-coluna">
          <div className="cur-vitrine-coluna-topo">
            <h3>Nesta seção · {formatarNumero(total)}</h3>
            <input
              type="search"
              value={filtroTexto}
              onChange={(event) => setFiltroTexto(event.target.value)}
              placeholder="Filtrar por nome, ID, estúdio ou gênero..."
              aria-label="Filtrar itens desta seção"
            />
          </div>

          {erro && <div className="cur-erro-fila" role="alert">{erro}<button type="button" onClick={carregar}>Tentar de novo</button></div>}
          {carregando && !itens.length ? (
            <div className="cur-vazio">Carregando...</div>
          ) : !itens.length ? (
            <div className="cur-vazio">
              <strong>{termo ? 'Nenhum item encontrado' : 'Nenhum jogo nesta seção'}</strong>
              <p>{termo ? 'Ajuste o filtro.' : 'Use as sugestões ao lado ou busque no catálogo. Enquanto estiver vazia, a seção não aparece no site.'}</p>
            </div>
          ) : (
            <ol className={`cur-vitrine-itens${carregando ? ' atualizando' : ''}`}>
              {itens.map((item, indice) => {
                const posicao = (pagina - 1) * POR_PAGINA + indice + 1
                const [rotuloSituacao, tom] = SITUACOES[item.situacao] || [item.situacao, 'neutro']
                const ocupado = acaoId !== null
                return (
                  <li key={item.id}>
                    <span className="cur-vitrine-posicao">{posicao}</span>
                    {item.imagem ? <img src={item.imagem} alt="" loading="lazy" /> : <span className="cur-sem-imagem">JOGO</span>}
                    <div className="cur-vitrine-info">
                      <strong>{item.jogo_nome}</strong>
                      <span>
                        {item.desconto > 0 && <span className="cur-tag cur-tag-desconto">-{item.desconto}%</span>}
                        {item.desenvolvedor}
                      </span>
                    </div>
                    <span className={`cur-situacao cur-situacao-${tom}`}>{rotuloSituacao}</span>
                    <div className="cur-vitrine-acoes">
                      {item.situacao === 'pausado' && (
                        <button type="button" className="cur-btn cur-btn--secundario cur-btn--p" disabled={ocupado} onClick={() => reativar(item)}>
                          Reativar
                        </button>
                      )}
                      <button type="button" className="cur-btn cur-btn--icone cur-btn--p" disabled={ocupado || posicao === 1} onClick={() => mover(item, 'cima')} aria-label={`Subir ${item.jogo_nome}`} title="Subir">
                        <IconeSubir />
                      </button>
                      <button type="button" className="cur-btn cur-btn--icone cur-btn--p" disabled={ocupado || posicao === total} onClick={() => mover(item, 'baixo')} aria-label={`Descer ${item.jogo_nome}`} title="Descer">
                        <IconeDescer />
                      </button>
                      <button type="button" className="cur-btn cur-btn--icone cur-btn--perigo cur-btn--p" disabled={ocupado} onClick={() => remover(item)} aria-label={`Remover ${item.jogo_nome}`} title="Remover da seção">
                        <IconeLixeira />
                      </button>
                    </div>
                  </li>
                )
              })}
            </ol>
          )}
          {totalPaginas > 1 && (
            <div className="cur-vitrine-paginas">
              <button type="button" className="cur-btn cur-btn--secundario cur-btn--p" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>Anterior</button>
              <span>Página {pagina} de {totalPaginas}</span>
              <button type="button" className="cur-btn cur-btn--secundario cur-btn--p" disabled={pagina >= totalPaginas} onClick={() => setPagina(pagina + 1)}>Próxima</button>
            </div>
          )}
        </div>

        <aside className="cur-vitrine-coluna">
          <h3>Sugestões</h3>
          <p className="cur-vitrine-ajuda">{secao.sugestao}</p>
          {carregandoSugestoes && !sugestoes.length ? (
            <div className="cur-vazio">Buscando sugestões...</div>
          ) : !sugestoes.length ? (
            <div className="cur-vazio"><p>Nenhuma sugestão no momento.</p></div>
          ) : (
            <ul className="cur-sugestoes">
              {sugestoes.map((jogo) => (
                <li key={jogo.id}>
                  {jogo.imagem ? <img src={jogo.imagem} alt="" loading="lazy" /> : <span className="cur-sem-imagem">JOGO</span>}
                  <div className="cur-vitrine-info">
                    <strong>{jogo.nome}</strong>
                    <span>
                      {jogo.desconto > 0 && <span className="cur-tag cur-tag-desconto">-{jogo.desconto}%</span>}
                      {formatarNumero(jogo.visualizacoes)} visualizações
                    </span>
                  </div>
                  <button
                    type="button"
                    className="cur-btn cur-btn--secundario cur-btn--p"
                    disabled={acaoId !== null}
                    onClick={() => adicionar(jogo)}
                  >
                    <IconeMais /> {acaoId === `add-${jogo.id}` ? 'Adicionando...' : 'Adicionar'}
                  </button>
                </li>
              ))}
            </ul>
          )}

          <h3 className="cur-vitrine-busca-titulo">Buscar no catálogo</h3>
          <BuscaCatalogo
            getHeaders={getHeaders}
            placeholder="Nome, ID, estúdio ou gênero..."
            renderAcoes={(jogo) => {
              const jaNaSecao = jogo.vitrine?.includes(tipo)
              return (
                <button
                  type="button"
                  className="cur-btn cur-btn--secundario cur-btn--p"
                  disabled={jaNaSecao || acaoId !== null}
                  onClick={() => adicionar(jogo)}
                >
                  {jaNaSecao ? 'Já na seção' : <><IconeMais /> Adicionar</>}
                </button>
              )
            }}
          />
        </aside>
      </div>
    </section>
  )
}

export default SecaoVitrine
