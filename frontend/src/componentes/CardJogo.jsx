import { useState } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contextos/AuthContext'
import { API_URL } from '../servicos/api'
import '../paginas/Curadoria.css'

const MOTIVOS_AUDITORIA = [
  'Conteúdo sensível',
  'Fora do catálogo',
  'Duplicado ou redundante',
  'Indisponível ou removido',
  'Problemas de qualidade ou integridade',
  'Outros',
]

function CardJogo({
  jogo,
  mostrarDesconto = false,
  modoSelecao = false,
  selecionado = false,
  onAlternarSelecao,
  statusAuditoriaExterno = null,
  favorito = false,
  onAlternarFavorito,
}) {
  const navigate = useNavigate()
  const { isAdmin, token } = useAuth()
  const [enviandoAuditoria, setEnviandoAuditoria] = useState(false)
  const [statusAuditoria, setStatusAuditoria] = useState(null)
  const [auditoriaPendente, setAuditoriaPendente] = useState(false)
  const [motivoAuditoria, setMotivoAuditoria] = useState('')
  const [observacaoAuditoria, setObservacaoAuditoria] = useState('')

  const obterAlvoModal = () =>
    document.querySelector('.pagina-jogos')?.closest('.app') ||
    document.querySelector('.app') ||
    document.body

  const imagens = [
    jogo.imagem,
    jogo.imagemEpic,
    jogo.imagemSteamFallback,
  ].filter(Boolean)

  const assinaturaImagens = imagens.join('|')
  const [estadoImagem, setEstadoImagem] = useState({ assinatura: assinaturaImagens, indice: 0 })
  const indiceImagem = estadoImagem.assinatura === assinaturaImagens ? estadoImagem.indice : 0
  const statusAuditoriaAtual = statusAuditoriaExterno || statusAuditoria
  const imagemAtual = imagens[indiceImagem] || null

  const tratarErroImagem = () => {
    setEstadoImagem((atual) => {
      const indiceAtual = atual.assinatura === assinaturaImagens ? atual.indice : 0
      return {
        assinatura: assinaturaImagens,
        indice: indiceAtual + 1 < imagens.length ? indiceAtual + 1 : imagens.length,
      }
    })
  }

  const abrirDetalhes = () => {
    navigate(`/jogos/${jogo.id}`)
  }

  const abrirAuditoria = (evento) => {
    evento.preventDefault()
    evento.stopPropagation()

    if (!isAdmin || !token || enviandoAuditoria || statusAuditoriaAtual === 'enviado') {
      return
    }

    setMotivoAuditoria('')
    setObservacaoAuditoria('')
    setAuditoriaPendente(true)
  }

  const fecharAuditoria = () => {
    if (enviandoAuditoria) return

    setAuditoriaPendente(false)
    setMotivoAuditoria('')
    setObservacaoAuditoria('')
  }

  const confirmarAuditoria = async () => {
    if (!motivoAuditoria) {
      return
    }

    if (motivoAuditoria === 'Outros' && !observacaoAuditoria.trim()) {
      return
    }

    try {
      setEnviandoAuditoria(true)
      setStatusAuditoria(null)

      const resposta = await fetch(`${API_URL}/api/admin/curadoria/`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          jogo_id: jogo.id,
          motivo: motivoAuditoria,
          observacao:
            motivoAuditoria === 'Outros'
              ? observacaoAuditoria.trim()
              : '',
        }),
      })

      const dados = await resposta.json().catch(() => ({}))

      if (resposta.status === 201) {
        setStatusAuditoria('enviado')
        setAuditoriaPendente(false)
        setMotivoAuditoria('')
        setObservacaoAuditoria('')
        return
      }

      if (resposta.status === 409) {
        const detalhe = String(dados.detail || '').toLowerCase()

        if (detalhe.includes('excluído')) {
          setStatusAuditoria('excluido')
        } else {
          setStatusAuditoria('existente')
        }

        setAuditoriaPendente(false)
        setMotivoAuditoria('')
        setObservacaoAuditoria('')
        return
      }

      throw new Error(
        dados.detail || `Erro ao enviar para auditoria: ${resposta.status}`
      )
    } catch (erro) {
      console.error('Erro ao enviar jogo para auditoria:', erro)
      setStatusAuditoria('erro')
    } finally {
      setEnviandoAuditoria(false)
    }
  }

  const converterPreco = (valor) => {
    if (valor === null || valor === undefined || valor === '—') return null
    if (typeof valor === 'number') return valor
    if (valor === 'Grátis') return 0

    return Number(
      String(valor)
        .replace('R$ ', '')
        .replace(/\./g, '')
        .replace(',', '.')
        .trim()
    )
  }

  const precoSteam = converterPreco(
    jogo.precoSteam ?? jogo.steam
  )

  const precoEpic = converterPreco(
    jogo.precoEpic ?? jogo.epic
  )

  const steamDisponivel = precoSteam !== null
  const epicDisponivel = precoEpic !== null

  const mesmoPreco =
    steamDisponivel &&
    epicDisponivel &&
    precoSteam === precoEpic

  const menorPreco =
    !steamDisponivel && epicDisponivel
      ? 'Epic Games'
      : steamDisponivel && !epicDisponivel
        ? 'Steam'
        : precoSteam < precoEpic
          ? 'Steam'
          : 'Epic Games'

  return (
    <article
      className={`card-jogo card-jogo-clicavel${modoSelecao ? ' card-jogo-com-selecao' : ''}${selecionado ? ' card-jogo-selecionado' : ''}`}
      onClick={abrirDetalhes}
      role="link"
      tabIndex={0}
      onKeyDown={(evento) => {
        if (evento.key === 'Enter' || evento.key === ' ') {
          evento.preventDefault()
          abrirDetalhes()
        }
      }}
    >
      <div className="imagem-jogo">
        {token && (
          <button
            type="button"
            className={`botao-favorito-card${favorito ? ' marcado' : ''}`}
            aria-label={favorito ? `Remover ${jogo.nome} dos favoritos` : `Adicionar ${jogo.nome} aos favoritos`}
            title={favorito ? 'Remover dos favoritos' : 'Adicionar aos favoritos'}
            onClick={(evento) => { evento.preventDefault(); evento.stopPropagation(); onAlternarFavorito?.(jogo.id) }}
            onKeyDown={(evento) => evento.stopPropagation()}
          >{favorito ? '♥' : '♡'}</button>
        )}
        {modoSelecao && isAdmin && (
          <label
            className="seletor-card-jogo"
            title={selecionado ? 'Desmarcar jogo' : 'Selecionar jogo'}
            onClick={(evento) => evento.stopPropagation()}
          >
            <input
              type="checkbox"
              checked={selecionado}
              onChange={() => onAlternarSelecao?.(jogo.id)}
              onClick={(evento) => evento.stopPropagation()}
              onKeyDown={(evento) => evento.stopPropagation()}
              aria-label={`${selecionado ? 'Desmarcar' : 'Selecionar'} ${jogo.nome}`}
            />
          </label>
        )}

        {imagemAtual ? (
          <img
            src={imagemAtual}
            alt={`Capa de ${jogo.nome}`}
            loading="lazy"
            decoding="async"
            onError={tratarErroImagem}
          />
        ) : (
          <div className="imagem-jogo-indisponivel" aria-label="Imagem indisponível">
            Imagem indisponível
          </div>
        )}

        {mostrarDesconto && jogo.desconto > 0 && (
          <span className="selo-desconto">
            -{jogo.desconto}%
          </span>
        )}

        {isAdmin && (
          <button
            type="button"
            onClick={abrirAuditoria}
            disabled={
              enviandoAuditoria ||
              statusAuditoriaAtual === 'enviado' ||
              statusAuditoriaAtual === 'excluido'
            }
            title={
              statusAuditoriaAtual === 'enviado'
                ? 'Jogo enviado para auditoria'
                : statusAuditoriaAtual === 'existente'
                  ? 'Jogo já está na curadoria'
                  : statusAuditoriaAtual === 'excluido'
                    ? 'Jogo já foi excluído pela curadoria'
                    : 'Enviar jogo para auditoria'
            }
            style={{
              position: 'absolute',
              top: '10px',
              right: '58px',
              zIndex: 3,
              border: '1px solid rgba(255, 255, 255, 0.22)',
              borderRadius: '7px',
              padding: '6px 9px',
              background:
                statusAuditoriaAtual === 'enviado'
                  ? '#1d7a4c'
                  : statusAuditoriaAtual === 'erro'
                    ? '#a33a3a'
                    : 'rgba(20, 20, 27, 0.92)',
              color: '#fff',
              fontSize: '11px',
              fontWeight: 700,
              cursor:
                enviandoAuditoria ||
                statusAuditoriaAtual === 'enviado' ||
                statusAuditoriaAtual === 'excluido'
                  ? 'default'
                  : 'pointer',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.28)',
              opacity: enviandoAuditoria ? 0.75 : 1,
            }}
          >
            {enviandoAuditoria
              ? 'Enviando...'
              : statusAuditoriaAtual === 'enviado'
                ? '✓ Enviado'
                : statusAuditoriaAtual === 'existente'
                  ? '✓ Em auditoria'
                  : statusAuditoriaAtual === 'excluido'
                    ? 'Excluído'
                    : statusAuditoriaAtual === 'erro'
                      ? 'Tentar novamente'
                      : '⚑ Auditar'}
          </button>
        )}
      </div>

      <div className="conteudo-card">
        <h3>{jogo.nome}</h3>

        <div className="precos">
          <div>
            <span className="rotulo-plataforma steam">
              Steam
            </span>

            <strong>{jogo.steam}</strong>
          </div>

          <div>
            <span className="rotulo-plataforma epic">
              Epic Games
            </span>

            <strong className={jogo.epic === '—' ? 'preco-indisponivel' : ''}>
              {jogo.epic === '—' ? 'Não disponível' : jogo.epic}
            </strong>
          </div>
        </div>

        <span className="menor-preco">
          {!steamDisponivel && !epicDisponivel
            ? 'Preço indisponível'
            : jogo.steam === 'Grátis' && jogo.epic === 'Grátis'
              ? 'Grátis nas duas lojas'
              : !steamDisponivel
                ? 'Exclusivo Epic Games'
                : !epicDisponivel
                  ? 'Exclusivo Steam'
                  : mesmoPreco
                ? 'Mesmo preço nas lojas'
                : `Menor preço: ${menorPreco}`}
        </span>
      </div>

      {auditoriaPendente && createPortal(
        <div
          className="curadoria-modal-overlay"
          role="presentation"
          onMouseDown={(evento) => {
            if (evento.target === evento.currentTarget) {
              fecharAuditoria()
            }
          }}
        >
          <div
            className="curadoria-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`auditoria-modal-titulo-${jogo.id}`}
            onClick={(evento) => evento.stopPropagation()}
          >
            <div className="curadoria-modal-cabecalho">
              <div>
                <span className="curadoria-status">AUDITORIA</span>
                <h2 id={`auditoria-modal-titulo-${jogo.id}`}>
                  Enviar jogo para auditoria
                </h2>
              </div>

              <button
                type="button"
                className="curadoria-modal-fechar"
                onClick={fecharAuditoria}
                disabled={enviandoAuditoria}
                aria-label="Fechar"
              >
                ×
              </button>
            </div>

            <p>
              Selecione o motivo pelo qual <strong>{jogo.nome}</strong> deve
              ser enviado para análise.
            </p>

            <label
              className="curadoria-modal-label"
              htmlFor={`motivo-auditoria-${jogo.id}`}
            >
              Motivo da auditoria
            </label>

            <select
              id={`motivo-auditoria-${jogo.id}`}
              value={motivoAuditoria}
              onChange={(evento) => {
                const valor = evento.target.value
                setMotivoAuditoria(valor)

                if (valor !== 'Outros') {
                  setObservacaoAuditoria('')
                }
              }}
              className="curadoria-modal-select"
              autoFocus
            >
              <option value="" disabled hidden>
                Selecione um motivo...
              </option>

              {MOTIVOS_AUDITORIA.map((motivo) => (
                <option key={motivo} value={motivo}>
                  {motivo}
                </option>
              ))}
            </select>

            {motivoAuditoria === 'Outros' && (
              <div className="curadoria-modal-outros">
                <label
                  className="curadoria-modal-label"
                  htmlFor={`observacao-auditoria-${jogo.id}`}
                >
                  Explique o motivo
                </label>

                <textarea
                  id={`observacao-auditoria-${jogo.id}`}
                  value={observacaoAuditoria}
                  onChange={(evento) =>
                    setObservacaoAuditoria(evento.target.value)
                  }
                  className="curadoria-modal-textarea"
                  rows={4}
                  maxLength={1000}
                  placeholder="Descreva por que o jogo deve ser auditado..."
                />

                <small className="curadoria-modal-contador">
                  {observacaoAuditoria.length}/1000
                </small>
              </div>
            )}

            <div className="curadoria-modal-acoes">
              <button
                type="button"
                className="botao-modal-cancelar"
                onClick={fecharAuditoria}
                disabled={enviandoAuditoria}
              >
                Cancelar
              </button>

              <button
                type="button"
                className="botao-modal-confirmar botao-modal-aprovar"
                onClick={confirmarAuditoria}
                disabled={
                  !motivoAuditoria ||
                  (motivoAuditoria === 'Outros' &&
                    !observacaoAuditoria.trim()) ||
                  enviandoAuditoria
                }
              >
                {enviandoAuditoria
                  ? 'Enviando...'
                  : 'Confirmar auditoria'}
              </button>
            </div>
          </div>
        </div>,
        obterAlvoModal()
      )}
    </article>
  )
}

export default CardJogo