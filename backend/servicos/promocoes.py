"""
Regra única para decidir se um jogo está em promoção.

Antes havia quatro cópias desta regra (vitrine da página inicial, curadoria,
recomendações da comunidade e rotina de expiração), cada uma com um critério.

Como a coleta grava no histórico apenas quando o preço muda, o registro mais
recente de cada loja representa o estado atual do jogo enquanto a coleta
daquela loja estiver em dia. Por isso a "idade" do registro não importa; o
que importa é se a loja foi coletada recentemente.

Estados:
- "ativa": ao menos uma loja tem desconto e a promoção não terminou.
- "inativa": nenhuma loja tem desconto vigente (fim confirmado ou preço cheio).
- "desconhecida": há desconto sem data de fim numa loja cuja coleta está
  atrasada, ou o jogo não tem histórico. Nesse caso nada é removido.
"""

from datetime import datetime, timedelta, timezone
import time

from sqlalchemy import bindparam, text

HORAS_COLETA_EM_DIA = 72
_CACHE_SEGUNDOS = 600
_cache_frescor = {"momento": 0.0, "valor": {}}

_PLATAFORMA = """
    CASE
        WHEN lower(trim(plataforma)) IN ('epic', 'epic games', 'epic games store') THEN 'epic'
        WHEN lower(trim(plataforma)) = 'steam' THEN 'steam'
    END
"""

_SQL_ULTIMOS = text(f"""
    SELECT DISTINCT ON (jogo_id, plataforma_norm)
        jogo_id, plataforma_norm, desconto, promocao_fim, data_coleta
    FROM (
        SELECT jogo_id, {_PLATAFORMA} AS plataforma_norm,
               desconto, promocao_fim, data_coleta, id
        FROM historico_precos
        WHERE jogo_id IN :ids
    ) h
    WHERE plataforma_norm IS NOT NULL
    ORDER BY jogo_id, plataforma_norm, data_coleta DESC, id DESC
""").bindparams(bindparam("ids", expanding=True))


def _utc(valor):
    if valor is None:
        return None
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


def lojas_em_dia(db, agora=None):
    """Indica, por loja, se a última coleta aconteceu nas últimas 72 horas."""
    agora = agora or datetime.now(timezone.utc)
    if time.monotonic() - _cache_frescor["momento"] > _CACHE_SEGUNDOS:
        linhas = db.execute(text(f"""
            SELECT {_PLATAFORMA} AS plataforma_norm, max(data_coleta)
            FROM historico_precos
            GROUP BY 1
        """)).all()
        _cache_frescor["valor"] = {plataforma: _utc(ultima) for plataforma, ultima in linhas if plataforma}
        _cache_frescor["momento"] = time.monotonic()

    limite = agora - timedelta(hours=HORAS_COLETA_EM_DIA)
    return {plataforma: bool(ultima and ultima >= limite) for plataforma, ultima in _cache_frescor["valor"].items()}


def detalhes_promocao(db, jogo_ids, agora=None):
    """Retorna {jogo_id: {"estado": ..., "desconto": maior desconto vigente}}."""
    agora = agora or datetime.now(timezone.utc)
    ids = sorted({int(jogo_id) for jogo_id in jogo_ids if jogo_id is not None})
    if not ids:
        return {}

    em_dia = lojas_em_dia(db, agora)
    registros = {}
    for linha in db.execute(_SQL_ULTIMOS, {"ids": ids}).mappings():
        registros.setdefault(int(linha["jogo_id"]), []).append(linha)

    resultado = {}
    for jogo_id in ids:
        linhas = registros.get(jogo_id)
        if not linhas:
            resultado[jogo_id] = {"estado": "desconhecida", "desconto": 0}
            continue

        estado, desconto_vigente = "inativa", 0
        for linha in linhas:
            desconto = int(linha["desconto"] or 0)
            if desconto <= 0:
                continue
            fim = _utc(linha["promocao_fim"])
            if fim is not None and fim <= agora:
                continue  # promoção com fim confirmado no passado
            if fim is not None or em_dia.get(linha["plataforma_norm"], False):
                estado = "ativa"
                desconto_vigente = max(desconto_vigente, desconto)
            elif estado != "ativa":
                estado = "desconhecida"
        resultado[jogo_id] = {"estado": estado, "desconto": desconto_vigente}
    return resultado


def estados_promocao(db, jogo_ids, agora=None):
    """Retorna {jogo_id: estado} para vários jogos com uma única consulta."""
    return {jogo_id: dados["estado"] for jogo_id, dados in detalhes_promocao(db, jogo_ids, agora).items()}


_cache_ativos = {"momento": 0.0, "valor": {}}


def jogos_em_promocao(db, agora=None):
    """{jogo_id: desconto} de todos os jogos com promoção ativa agora.

    Parte dos registros com desconto ainda sem fim confirmado e aplica a regra
    única. Leva cerca de 2 s, por isso o resultado fica 10 minutos em cache.
    """
    if time.monotonic() - _cache_ativos["momento"] > _CACHE_SEGUNDOS:
        candidatos = db.execute(text("""
            SELECT DISTINCT jogo_id FROM historico_precos
            WHERE desconto > 0
              AND (promocao_fim > now()
                   OR (promocao_fim IS NULL AND data_coleta > now() - interval '45 days'))
        """)).scalars().all()
        detalhes = detalhes_promocao(db, candidatos, agora)
        _cache_ativos["valor"] = {
            jogo_id: dados["desconto"] for jogo_id, dados in detalhes.items() if dados["estado"] == "ativa"
        }
        _cache_ativos["momento"] = time.monotonic()
    return dict(_cache_ativos["valor"])


def estado_promocao(db, jogo_id, agora=None):
    return estados_promocao(db, [jogo_id], agora).get(int(jogo_id), "desconhecida")


def em_promocao(db, jogo_id, agora=None):
    return estado_promocao(db, jogo_id, agora) == "ativa"


# Tipos da vitrine que dependem de promoção ativa para aparecer.
TIPOS_VITRINE_PROMOCAO = ("oportunidade", "curadoria_comunidade")


def limpar_vitrine_encerrada(db, agora=None):
    """Remove da vitrine os itens cuja promoção terminou comprovadamente.

    Itens em estado "desconhecido" são preservados até a próxima coleta.
    Não faz commit: quem chama decide.
    """
    itens = db.execute(text("""
        SELECT id, jogo_id FROM vitrine_itens
        WHERE tipo IN :tipos AND jogo_id IS NOT NULL
    """).bindparams(bindparam("tipos", expanding=True)), {"tipos": list(TIPOS_VITRINE_PROMOCAO)}).all()
    if not itens:
        return 0

    estados = estados_promocao(db, [jogo_id for _, jogo_id in itens], agora)
    encerrados = [item_id for item_id, jogo_id in itens if estados.get(int(jogo_id)) == "inativa"]
    if encerrados:
        db.execute(
            text("DELETE FROM vitrine_itens WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)),
            {"ids": encerrados},
        )
    return len(encerrados)
