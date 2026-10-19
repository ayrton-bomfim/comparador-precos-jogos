"""Limpa recomendações comunitárias somente quando o fim da promoção é confirmado.

Executar na raiz do projeto:
    python -m backend.scripts.expirar_recomendacoes_comunidade

Agende a execução periódica (por exemplo, a cada hora) no Agendador de Tarefas
 do Windows ou no scheduler utilizado pelo ambiente de produção.
"""
from datetime import datetime, timedelta, timezone
import logging

from sqlalchemy import text

from backend.banco_dados import SessionLocal
from backend.modelos import Usuario, Jogo, NotificacaoUsuario

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("desctrl.recomendacoes")

PLATAFORMAS_VALIDAS = ("steam", "epic", "epic games", "epic games store")
HORAS_MAX_DADOS_SEM_FIM = 72


def _normalizar_data(valor):
    if valor is None:
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


def _estado_promocao(db, jogo_id, agora):
    """Retorna ativa/inativa/desconhecida sem confundir falha ou dados antigos com fim.

    Uma promoção com fim explícito no passado é considerada encerrada naquela loja.
    Quando não há data de fim, só consideramos a promoção ativa se o registro for
    recente. Dados antigos/incompletos deixam o estado desconhecido e impedem limpeza.
    """
    jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()
    if not jogo:
        return "desconhecida"

    # Se o jogo possui identificador de uma loja, a ausência de histórico dessa
    # loja não prova que a promoção acabou. Evita limpar por coleta incompleta.
    lojas_esperadas = set()
    if jogo.steam_id:
        lojas_esperadas.add("steam")
    if jogo.epic_id and jogo.epic_id != "EXCLUSIVO_STEAM":
        lojas_esperadas.add("epic")
    if not lojas_esperadas:
        return "desconhecida"

    try:
        registros = db.execute(text("""
            SELECT plataforma_norm, desconto, promocao_fim, data_coleta
            FROM (
                SELECT DISTINCT ON (
                    CASE
                        WHEN lower(trim(plataforma)) IN ('epic', 'epic games', 'epic games store') THEN 'epic'
                        WHEN lower(trim(plataforma)) = 'steam' THEN 'steam'
                        ELSE lower(trim(plataforma))
                    END
                )
                    CASE
                        WHEN lower(trim(plataforma)) IN ('epic', 'epic games', 'epic games store') THEN 'epic'
                        WHEN lower(trim(plataforma)) = 'steam' THEN 'steam'
                        ELSE lower(trim(plataforma))
                    END AS plataforma_norm,
                    desconto, promocao_fim, data_coleta, id
                FROM historico_precos
                WHERE jogo_id = :jogo_id
                  AND lower(trim(plataforma)) IN ('steam', 'epic', 'epic games', 'epic games store')
                ORDER BY
                    CASE
                        WHEN lower(trim(plataforma)) IN ('epic', 'epic games', 'epic games store') THEN 'epic'
                        WHEN lower(trim(plataforma)) = 'steam' THEN 'steam'
                        ELSE lower(trim(plataforma))
                    END,
                    data_coleta DESC, id DESC
            ) ultimos
        """), {"jogo_id": jogo_id}).mappings().all()
    except Exception:
        logger.exception("Falha consultando histórico do jogo_id=%s; preservando recomendação", jogo_id)
        return "desconhecida"

    if not registros:
        return "desconhecida"
    lojas_com_dados = {registro["plataforma_norm"] for registro in registros}
    if not lojas_esperadas.issubset(lojas_com_dados):
        return "desconhecida"

    limite_recencia = agora - timedelta(hours=HORAS_MAX_DADOS_SEM_FIM)
    desconhecida = False
    for registro in registros:
        coleta = _normalizar_data(registro["data_coleta"])
        fim = _normalizar_data(registro["promocao_fim"])
        desconto = int(registro["desconto"] or 0)

        if desconto > 0:
            if fim is not None:
                if fim > agora:
                    return "ativa"
                # O fim explícito passou: esta loja não mantém a promoção.
                continue
            if coleta is not None and coleta >= limite_recencia:
                return "ativa"
            desconhecida = True
        elif coleta is None or coleta < limite_recencia:
            desconhecida = True

    return "desconhecida" if desconhecida else "inativa"


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

        for jogo_id in jogo_ids:
            estado = _estado_promocao(db, jogo_id, agora)
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

        db.commit()
        logger.info(
            "Rotina concluída: %s jogo(s) expirado(s), %s usuário(s) liberado(s)",
            total_jogos_expirados, total_usuarios_limpos,
        )
        return {
            "jogos_expirados": total_jogos_expirados,
            "usuarios_liberados": total_usuarios_limpos,
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
        "{usuarios_liberados} usuário(s) liberado(s).".format(**resultado)
    )
