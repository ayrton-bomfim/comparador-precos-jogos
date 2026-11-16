"""Limpa recomendações e itens da vitrine cuja promoção terminou.

Usa a regra única de promoção (backend/servicos/promocoes.py): só remove o
que tem fim confirmado; estados desconhecidos são preservados.

Executada diariamente pelo agendador da coleta (etapa 4). Também pode ser
rodada manualmente, a partir da raiz do projeto:
    python -m backend.servicos.expirar_recomendacoes_comunidade
"""
from datetime import datetime, timezone
import logging

from backend.banco_dados import SessionLocal
from backend.modelos import Usuario, Jogo, NotificacaoUsuario
from backend.servicos.promocoes import estados_promocao, limpar_vitrine_encerrada

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("desctrl.recomendacoes")


def expirar_recomendacoes(db=None):
    propria_sessao = db is None
    db = db or SessionLocal()
    agora = datetime.now(timezone.utc)
    total_usuarios_limpos = 0
    total_jogos_expirados = 0

    try:
        jogo_ids = [
            int(jogo_id)
            for (jogo_id,) in (
                db.query(Usuario.jogo_recomendado_id)
                .filter(Usuario.jogo_recomendado_id.isnot(None))
                .distinct()
                .all()
            )
        ]

        estados = estados_promocao(db, jogo_ids, agora)
        for jogo_id in jogo_ids:
            estado = estados.get(jogo_id, "desconhecida")
            if estado != "inativa":
                if estado == "desconhecida":
                    logger.info("Jogo %s: estado desconhecido; recomendação preservada", jogo_id)
                continue

            jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()
            nome_jogo = jogo.nome if jogo else f"jogo #{jogo_id}"
            usuarios = (
                db.query(Usuario)
                .filter(Usuario.jogo_recomendado_id == jogo_id)
                .with_for_update()
                .all()
            )
            if not usuarios:
                continue

            # A limpeza e as notificações são gravadas na mesma transação.
            for usuario in usuarios:
                usuario.jogo_recomendado_id = None
                db.add(NotificacaoUsuario(
                    usuario_id=usuario.id,
                    tipo="recomendacao",
                    titulo="Promoção encerrada",
                    mensagem=(
                        f"A recomendação de {nome_jogo} foi encerrada porque "
                        "não há mais promoção ativa confirmada nas lojas acompanhadas."
                    ),
                    link=f"/jogos/{jogo_id}",
                    jogo_id=jogo_id,
                    dados={"acao": "promocao_encerrada", "origem": "rotina_automatica"},
                ))
            total_usuarios_limpos += len(usuarios)
            total_jogos_expirados += 1
            logger.info(
                "Jogo %s (%s): encerradas %s recomendação(ões)",
                jogo_id, nome_jogo, len(usuarios),
            )

        itens_vitrine_removidos = limpar_vitrine_encerrada(db, agora)

        db.commit()
        logger.info(
            "Rotina concluída: %s jogo(s) expirado(s), %s usuário(s) liberado(s), %s item(ns) da vitrine removido(s)",
            total_jogos_expirados, total_usuarios_limpos, itens_vitrine_removidos,
        )
        return {
            "jogos_expirados": total_jogos_expirados,
            "usuarios_liberados": total_usuarios_limpos,
            "itens_vitrine_removidos": itens_vitrine_removidos,
        }
    except Exception:
        db.rollback()
        logger.exception("Rotina de expiração falhou; alterações desta execução revertidas")
        raise
    finally:
        if propria_sessao:
            db.close()


if __name__ == "__main__":
    resultado = expirar_recomendacoes()
    print(
        "Concluído: {jogos_expirados} jogo(s) expirado(s), "
        "{usuarios_liberados} usuário(s) liberado(s), "
        "{itens_vitrine_removidos} item(ns) da vitrine removido(s).".format(**resultado)
    )
