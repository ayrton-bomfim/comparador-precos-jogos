import { useState } from 'react'
import GaleriaCuradoria from './GaleriaCuradoria'
import { IconeAnterior, IconeExterno, IconeProximo, IconeRelacionados, IconeVoltar } from './Icones'
import {
  DESCRITORES_STEAM,
  MOTIVOS_APROVACAO,
  MOTIVOS_AUDITORIA,
  MOTIVOS_COM_RELACIONADOS,
  extrairPrioridade,
  formatarData,
  linksDaLoja,
  rotuloOrigem,
} from './utilidades'

const LIMITE_OBSERVACAO = 220

function GrupoDecisao({ titulo, decisao, motivos, ativo, processando, onEscolher }) {
  return (
    <div className={`cur-decisao-grupo cur-decisao-${decisao}${ativo ? ' atalho-ativo' : ''}`}>
      <span className="cur-decisao-titulo">{titulo}</span>
      <div className="cur-decisao-opcoes">
        {motivos.map((motivo, posicao) => (
          <button
            type="button"
            key={motivo}
            className={`cur-chip cur-chip--${decisao}`}
            onClick={() => onEscolher(motivo)}
            disabled={processando}
            title={
              decisao === 'excluir' && MOTIVOS_COM_RELACIONADOS.includes(motivo)
                ? 'Também encaminha jogos da mesma desenvolvedora/publicadora para revisão.'
                : undefined
            }
          >
            {ativo && <kbd>{posicao + 1}</kbd>}
            {motivo}
            {decisao === 'excluir' && MOTIVOS_COM_RELACIONADOS.includes(motivo) && (
              <IconeRelacionados titulo="Também encaminha jogos relacionados" />
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

// Painel com tudo o que é preciso para decidir sobre um jogo sem abrir a loja.
function PainelJogo({
  item,
  podeDecidir,
  imagemBorrada,
  galeria,
  posicao,
  onAnterior,
  onProximo,
  processando,
  modoAtalho,
  outros,
  onAbrirOutros,
  onAlterarOutros,
  onCancelarOutros,
  onDecidir,
  onReabrir,
  onFechar,
}) {
  const [observacaoAberta, setObservacaoAberta] = useState(false)
  const prioridade = extrairPrioridade(item.observacao)
  const descritores = Array.isArray(item.steam_content_descriptors?.ids)
    ? item.steam_content_descriptors.ids.map((id) => DESCRITORES_STEAM[id] || `Descritor ${id}`)
    : []
  const notasConteudo = item.steam_content_descriptors?.notes || item.steam_content_notes || ''
  const observacaoLonga = String(item.observacao || '').length > LIMITE_OBSERVACAO

  const ficha = [
    ['Desenvolvedora', item.desenvolvedor],
    ['Publicadora', item.publicadora && item.publicadora !== item.desenvolvedor ? item.publicadora : null],
    ['Gênero', item.genero],
    ['Lançamento', formatarData(item.data_lancamento)],
    ['Idade mínima', item.steam_required_age > 0 ? `${item.steam_required_age} anos` : null],
    ['Origem', rotuloOrigem(item.origem)],
    ['ID da loja', item.steam_id || item.epic_id],
  ].filter(([, valor]) => valor)

  const escolher = (decisao) => (motivo) => {
    if (motivo === 'Outros') onAbrirOutros(decisao)
    else onDecidir(decisao, motivo)
  }

  return (
    <aside className="cur-painel" aria-label={`Detalhes de ${item.nome}`}>
      <div className="cur-painel-navegacao">
        <button type="button" className="cur-btn cur-btn--discreto cur-btn--p cur-painel-fechar" onClick={onFechar} aria-label="Voltar para a lista">
          <IconeVoltar /> Lista
        </button>
        <span>{posicao.indice + 1} de {posicao.total}</span>
        <div>
          <button type="button" className="cur-btn cur-btn--icone cur-btn--p" onClick={onAnterior} disabled={posicao.indice <= 0} aria-label="Jogo anterior"><IconeAnterior /></button>
          <button type="button" className="cur-btn cur-btn--icone cur-btn--p" onClick={onProximo} disabled={posicao.indice >= posicao.total - 1} aria-label="Próximo jogo"><IconeProximo /></button>
        </div>
      </div>

      <div className="cur-painel-corpo">
        <GaleriaCuradoria item={item} imagemBorrada={imagemBorrada} {...galeria} />

        <header className="cur-painel-titulo">
          <div className="cur-painel-selos">
            <span className={`cur-selo cur-selo-${item.status}`}>
              {item.status === 'aprovado' ? 'Aprovado' : item.status === 'excluido' ? 'Excluído' : 'Pendente'}
            </span>
            {prioridade && (
              <span className={`cur-tag cur-prioridade-${prioridade.codigo.toLowerCase()}`}>{prioridade.rotulo}</span>
            )}
            {item.steam_conteudo_adulto && <span className="cur-tag cur-tag-alerta">Marcado como adulto na Steam</span>}
          </div>
          <h2>{item.nome}</h2>
          <span className="cur-painel-id">Registro #{item.id}</span>
        </header>

        {ficha.length > 0 && (
          <dl className="cur-ficha">
            {ficha.map(([rotulo, valor]) => (
              <div key={rotulo}>
                <dt>{rotulo}</dt>
                <dd>{valor}</dd>
              </div>
            ))}
          </dl>
        )}

        {(descritores.length > 0 || notasConteudo) && (
          <section className="cur-descritores">
            <h3>Descritores de conteúdo (Steam)</h3>
            {descritores.length > 0 && (
              <ul>
                {descritores.map((descricao) => <li key={descricao}>{descricao}</li>)}
              </ul>
            )}
            {notasConteudo && <p>“{notasConteudo}”</p>}
          </section>
        )}

        {item.status !== 'pendente' && (
          <section className="cur-decisao-registrada">
            <h3>Decisão registrada</h3>
            <p>
              <strong>{item.motivo || 'Sem motivo informado'}</strong>
              {item.decidido_em && <> · {formatarData(item.decidido_em, true)}</>}
            </p>
          </section>
        )}

        {item.status === 'pendente' && item.motivo && (
          <p className="cur-motivo-fila"><span>Motivo da fila:</span> {item.motivo}</p>
        )}

        {item.observacao && (
          <section className="cur-observacao">
            <h3>Observação</h3>
            <p className={observacaoLonga && !observacaoAberta ? 'recolhida' : ''}>{item.observacao}</p>
            {observacaoLonga && (
              <button type="button" className="cur-btn cur-btn--discreto cur-btn--p" onClick={() => setObservacaoAberta((aberta) => !aberta)}>
                {observacaoAberta ? 'Mostrar menos' : 'Mostrar tudo'}
              </button>
            )}
          </section>
        )}

        <div className="cur-lojas">
          {linksDaLoja(item).map((link) => (
            <a key={link.url} className="cur-btn cur-btn--secundario cur-btn--p" href={link.url} target="_blank" rel="noopener noreferrer">
              {link.rotulo} <IconeExterno />
            </a>
          ))}
        </div>
      </div>

      <footer className="cur-decisao">
        {podeDecidir ? (
          outros ? (
            <form
              className="cur-decisao-outros"
              onSubmit={(event) => {
                event.preventDefault()
                if (outros.texto.trim()) onDecidir(outros.decisao, 'Outros', outros.texto.trim())
              }}
            >
              <label htmlFor="cur-outros-texto">
                {outros.decisao === 'aprovar' ? 'Por que aprovar?' : 'Por que excluir?'} (motivo “Outros”)
              </label>
              <textarea
                id="cur-outros-texto"
                value={outros.texto}
                onChange={(event) => onAlterarOutros(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) event.currentTarget.form.requestSubmit()
                  if (event.key === 'Escape') onCancelarOutros()
                }}
                rows={3}
                maxLength={1000}
                autoFocus
                placeholder="Descreva o motivo da decisão..."
              />
              <div>
                <button type="button" className="cur-btn cur-btn--secundario" onClick={onCancelarOutros} disabled={processando}>Cancelar</button>
                <button
                  type="submit"
                  className={`cur-btn ${outros.decisao === 'aprovar' ? 'cur-btn--aprovar' : 'cur-btn--perigo'}`}
                  disabled={processando || !outros.texto.trim()}
                >
                  {outros.decisao === 'aprovar' ? 'Confirmar aprovação' : 'Confirmar exclusão'}
                </button>
              </div>
            </form>
          ) : (
            <>
              <GrupoDecisao
                titulo="Aprovar como"
                decisao="aprovar"
                motivos={MOTIVOS_APROVACAO}
                ativo={modoAtalho === 'aprovar'}
                processando={processando}
                onEscolher={escolher('aprovar')}
              />
              <GrupoDecisao
                titulo="Excluir por"
                decisao="excluir"
                motivos={MOTIVOS_AUDITORIA}
                ativo={modoAtalho === 'excluir'}
                processando={processando}
                onEscolher={escolher('excluir')}
              />
              <p className="cur-decisao-dica">
                {modoAtalho ? (
                  'Pressione o número do motivo · Esc cancela'
                ) : (
                  <>
                    <IconeRelacionados /> também encaminha jogos da mesma desenvolvedora/publicadora · Atalhos: A aprovar, E excluir
                  </>
                )}
              </p>
            </>
          )
        ) : (
          <button type="button" className="cur-btn cur-btn--secundario cur-btn--largo" onClick={onReabrir} disabled={processando}>
            {processando ? 'Reabrindo...' : 'Reabrir análise'}
          </button>
        )}
      </footer>
    </aside>
  )
}

export default PainelJogo
