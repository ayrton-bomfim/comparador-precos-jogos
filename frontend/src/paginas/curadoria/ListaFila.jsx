import { extrairPrioridade, imagemDeCapa } from './utilidades'

// Lista compacta da fila: cerca de 10 jogos por tela em vez de 2 ou 3 cards grandes.
function ListaFila({
  itens,
  selecionadoId,
  onSelecionar,
  borrar,
  permitirSelecao,
  itensSelecionados,
  onAlternarSelecao,
  idEmProcessamento,
  desabilitarSelecao,
  mostrarMotivo = true,
}) {
  return (
    <ul className="cur-lista" aria-label="Jogos da fila">
      {itens.map((item) => {
        const ativo = item.id === selecionadoId
        const capa = imagemDeCapa(item)
        const prioridade = extrairPrioridade(item.observacao)
        const detalhe = [item.desenvolvedor, String(item.genero || '').split(',')[0]]
          .map((parte) => String(parte || '').trim())
          .filter(Boolean)
          .join(' · ')

        return (
          <li
            key={item.id}
            id={`cur-item-${item.id}`}
            className={`cur-linha${ativo ? ' ativa' : ''}${idEmProcessamento === item.id ? ' processando' : ''}`}
          >
            {permitirSelecao && (
              <input
                type="checkbox"
                className="cur-linha-check"
                checked={itensSelecionados.has(item.id)}
                onChange={() => onAlternarSelecao(item)}
                disabled={desabilitarSelecao}
                aria-label={`Selecionar ${item.nome} para ação em lote`}
              />
            )}
            <button
              type="button"
              className="cur-linha-botao"
              onClick={() => onSelecionar(item)}
              aria-current={ativo ? 'true' : undefined}
            >
              <span className="cur-linha-capa">
                {capa ? (
                  <img src={capa} alt="" loading="lazy" className={borrar(item) ? 'imagem-borrada' : ''} />
                ) : (
                  <span>LOJA</span>
                )}
              </span>
              <span className="cur-linha-info">
                <strong>{item.nome}</strong>
                <span>{detalhe || `ID da loja: ${item.steam_id || item.epic_id || 'não informado'}`}</span>
              </span>
              <span className="cur-linha-tags">
                {prioridade && (
                  <span className={`cur-tag cur-prioridade-${prioridade.codigo.toLowerCase()}`} title={prioridade.rotulo}>
                    {prioridade.codigo}
                  </span>
                )}
                {mostrarMotivo && item.motivo && <span className="cur-tag">{item.motivo}</span>}
              </span>
            </button>
          </li>
        )
      })}
    </ul>
  )
}

export default ListaFila
