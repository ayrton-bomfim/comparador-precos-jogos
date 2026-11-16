const SECOES = [
  ['Aguardando análise', 'Jogos que entraram na fila por um motivo (fora do catálogo, duplicado, indisponível...). Aprove para mantê-los no catálogo público ou exclua para retirá-los.'],
  ['Conteúdo sensível', 'Fila separada para possíveis conteúdos adultos. A prioridade (P1 a P5) e os descritores da Steam ajudam a ordenar, mas não confirmam sozinhos o conteúdo.'],
  ['Aprovados e Excluídos', 'Histórico das decisões. Qualquer registro pode voltar para análise com “Reabrir análise”.'],
  ['Vitrine', 'Define os jogos das seções “Brasil em jogo” e “Oportunidades de preço” da página inicial.'],
  ['Feedback', 'Sugestões enviadas pela comunidade. Marque como feito quando a melhoria for concluída.'],
]

const ATALHOS = [
  ['J', 'Próximo jogo'],
  ['K', 'Jogo anterior'],
  ['A, depois 1–5', 'Aprovar com o motivo escolhido'],
  ['E, depois 1–6', 'Excluir com o motivo escolhido'],
  ['X', 'Marcar o jogo para ação em lote'],
  ['Z', 'Desfazer a última decisão'],
  ['Esc', 'Cancelar o atalho ou fechar o painel'],
  ['?', 'Abrir esta ajuda'],
]

function AjudaCuradoria({ onFechar }) {
  return (
    <div
      className="curadoria-modal-overlay"
      role="presentation"
      onMouseDown={(event) => { if (event.target === event.currentTarget) onFechar() }}
    >
      <div className="curadoria-modal cur-modal-largo" role="dialog" aria-modal="true" aria-labelledby="cur-ajuda-titulo">
        <div className="curadoria-modal-cabecalho">
          <div>
            <span className="curadoria-status">AJUDA</span>
            <h2 id="cur-ajuda-titulo">Como funciona a curadoria</h2>
          </div>
          <button type="button" className="curadoria-modal-fechar" onClick={onFechar} aria-label="Fechar" autoFocus>×</button>
        </div>

        <dl className="cur-ajuda-secoes">
          {SECOES.map(([titulo, texto]) => (
            <div key={titulo}>
              <dt>{titulo}</dt>
              <dd>{texto}</dd>
            </div>
          ))}
        </dl>

        <h3 className="cur-ajuda-subtitulo">Atalhos de teclado</h3>
        <table className="cur-ajuda-atalhos">
          <tbody>
            {ATALHOS.map(([tecla, acao]) => (
              <tr key={tecla}>
                <td><kbd>{tecla}</kbd></td>
                <td>{acao}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="cur-ajuda-nota">
          Toda decisão pode ser desfeita pelo aviso que aparece logo depois dela. Exclusões por “Conteúdo sensível” ou
          “Fora do catálogo” também encaminham jogos da mesma desenvolvedora/publicadora para revisão; esse
          encaminhamento não é desfeito junto com a decisão.
        </p>
      </div>
    </div>
  )
}

export default AjudaCuradoria
