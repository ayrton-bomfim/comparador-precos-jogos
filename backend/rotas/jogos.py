"""
Módulo de rotas para consulta de jogos.

Este módulo define os endpoints da API para listar jogos
e obter detalhes de um jogo específico.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta
import requests
import time
import json
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session
from ..banco_dados import get_db
from ..modelos import Jogo, HistoricoPreco, AuditoriaConteudo, Usuario, NotificacaoUsuario
from ..seguranca.autenticacao import obter_usuario_atual
from ..coletores.steam_coletor import SteamColetor

EGDATA_SEARCH_URL = "https://api.egdata.app/search/v2/search"
EGDATA_COUNTRY = "BR"
EGDATA_LOCALE = "pt-BR"


router = APIRouter(prefix="/api/jogos", tags=["jogos"])

# Diagnóstico temporário de performance. Não altera a lógica dos endpoints.
_diagnostico_rotas_jogos = {
    "listar_jogos": {"chamadas": 0, "etapas": {}},
    "historico_lote": {"chamadas": 0, "etapas": {}},
}



def _normalizar_plataforma(plataforma):
    """
    Normaliza os nomes das plataformas usados no histórico.

    O histórico da Epic pode estar gravado como "Epic",
    enquanto versões da API podem procurar "Epic Games".
    Todos esses formatos passam a ser tratados como a mesma plataforma.
    """
    valor = (plataforma or "").strip().lower()

    if valor == "steam":
        return "steam"

    if valor in {"epic", "epic games", "epic games store"}:
        return "epic"

    return valor


def _jogo_visivel_catalogo():
    """
    Define quais jogos podem aparecer nas rotas públicas do catálogo.

    Regra geral de preço:
    - O jogo precisa ter preco_base_steam OU preco_base_epic preenchido.
    - Zero é um valor válido (por exemplo, jogo gratuito); apenas NULL conta
      como ausência de valor-base.

    Para jogos exclusivamente Steam (sem Epic ou com o marcador
    EXCLUSIVO_STEAM), a disponibilidade regional da Steam também é respeitada:
    - NULL: ainda não processado, continua visível se houver valor-base;
    - DISPONIVEL / GRATUITO: visível se houver valor-base;
    - INDISPONIVEL / INDETERMINADO: oculto.

    Jogos com Epic não dependem do status regional da Steam, mas ainda precisam
    ter valor-base em pelo menos uma das lojas.
    """
    jogo_somente_steam = (
        Jogo.epic_id.is_(None)
        | (Jogo.epic_id == "EXCLUSIVO_STEAM")
    )

    steam_status_valido = (
        Jogo.steam_disponibilidade_br.is_(None)
        | Jogo.steam_disponibilidade_br.in_(["DISPONIVEL", "GRATUITO"])
    )

    tem_preco_base = (
        Jogo.preco_base_steam.isnot(None)
        | Jogo.preco_base_epic.isnot(None)
    )

    return ((~jogo_somente_steam) | steam_status_valido) & tem_preco_base


@router.get("/")
# Esta rota usa SQLAlchemy síncrono; deve ser função síncrona (def) para
# o FastAPI executá-la no thread pool, sem bloquear o event loop inteiro.
def listar_jogos(
    pagina: int = 1,
    por_pagina: int = 20,
    busca: str = "",
    filtro: str = "todos",
    ordenacao: str = "mais-vistos",
    legado: bool = False,
    db: Session = Depends(get_db),
):
    """
    Lista o catálogo de forma paginada.

    Importante: para ordenações simples (nome, Steam, Epic e grátis), não
    montamos as subconsultas de histórico de todo o catálogo. Os históricos
    são consultados somente depois que os 20 jogos da página foram definidos.
    Isso evita que uma página simples tenha de varrer ~190 mil jogos/históricos.
    """
    inicio = time.perf_counter()

    pagina = max(1, pagina)
    por_pagina = min(max(1, por_pagina), 100)
    busca = (busca or "").strip()
    filtro = filtro if filtro in {"brasileiros", "todos", "steam", "epic", "desconto", "gratis"} else "todos"
    ordenacao = ordenacao if ordenacao in {"nome", "menor-preco", "maior-preco", "desconto", "mais-vistos"} else "mais-vistos"

    # Regra de visibilidade atual da curadoria Epic.
    query_base = (
        db.query(Jogo)
        .outerjoin(AuditoriaConteudo, AuditoriaConteudo.jogo_id == Jogo.id)
        .filter(
            ~AuditoriaConteudo.status.in_(["pendente", "excluido"])
            | (AuditoriaConteudo.id.is_(None))
        )
        .filter(_jogo_visivel_catalogo())
    )

    if filtro == "brasileiros":
        # A classificação é pré-calculada e mantida no banco.
        # Isso evita recalcular a correspondência com estudios_brasileiros
        # tanto na contagem quanto na consulta paginada.
        query_base = query_base.filter(Jogo.eh_brasileiro.is_(True))

    if busca:
        termo_busca = f"%{busca}%"
        query_base = query_base.filter(
            or_(
                Jogo.nome.ilike(termo_busca),
                Jogo.desenvolvedor.ilike(termo_busca),
                Jogo.publicadora.ilike(termo_busca),
            )
        )

    if filtro == "steam":
        query_base = query_base.filter(Jogo.steam_id.isnot(None))
    elif filtro == "epic":
        query_base = query_base.filter(
            Jogo.epic_id.isnot(None),
            Jogo.epic_id != "EXCLUSIVO_STEAM",
        )
    elif filtro == "gratis":
        query_base = query_base.filter(
            func.lower(func.coalesce(Jogo.genero, "")).like("%grátis para jogar%")
        )

    # ------------------------------------------------------------------
    # Modo legado: somente páginas que realmente precisam do catálogo
    # inteiro (atualmente Ofertas). O endpoint paginado normal não passa
    # por este caminho.
    # ------------------------------------------------------------------
    if legado:
        jogos = query_base.order_by(Jogo.nome.asc()).all()
        jogo_ids = [jogo.id for jogo in jogos]

        ultimos_dados = {}
        if jogo_ids:
            ultima_data_legado = (
                db.query(
                    HistoricoPreco.jogo_id.label("jogo_id"),
                    HistoricoPreco.plataforma.label("plataforma"),
                    func.max(HistoricoPreco.data_coleta).label("ultima_data"),
                )
                .filter(HistoricoPreco.jogo_id.in_(jogo_ids))
                .group_by(HistoricoPreco.jogo_id, HistoricoPreco.plataforma)
                .subquery()
            )

            registros = (
                db.query(HistoricoPreco)
                .join(
                    ultima_data_legado,
                    (HistoricoPreco.jogo_id == ultima_data_legado.c.jogo_id)
                    & (HistoricoPreco.plataforma == ultima_data_legado.c.plataforma)
                    & (HistoricoPreco.data_coleta == ultima_data_legado.c.ultima_data),
                )
                .filter(HistoricoPreco.jogo_id.in_(jogo_ids))
                .all()
            )

            for registro in registros:
                chave = (registro.jogo_id, _normalizar_plataforma(registro.plataforma))
                ultimos_dados[chave] = {
                    "desconto": registro.desconto or 0,
                    "preco_atual": float(registro.preco_atual)
                    if registro.preco_atual is not None
                    else None,
                }

        return [
            {
                "id": jogo.id,
                "nome": jogo.nome,
                "jogo_base_id": jogo.jogo_base_id,
                "steam_id": jogo.steam_id,
                "epic_id": jogo.epic_id,
                "desenvolvedor": jogo.desenvolvedor,
                "publicadora": jogo.publicadora,
                "genero": jogo.genero,
                "preco_base_steam": float(jogo.preco_base_steam) if jogo.preco_base_steam is not None else None,
                "preco_base_epic": float(jogo.preco_base_epic) if jogo.preco_base_epic is not None else None,
                "url_steam": jogo.url_steam,
                "url_epic": jogo.url_epic,
                "url_imagem_steam": jogo.url_imagem_steam,
                "url_imagem_epic": jogo.url_imagem_epic,
                "preco_atual_steam": ultimos_dados.get((jogo.id, "steam"), {}).get("preco_atual"),
                "preco_atual_epic": ultimos_dados.get((jogo.id, "epic"), {}).get("preco_atual"),
                "desconto_steam": ultimos_dados.get((jogo.id, "steam"), {}).get("desconto", 0),
                "desconto_epic": ultimos_dados.get((jogo.id, "epic"), {}).get("desconto", 0),
                "visualizacoes": jogo.visualizacoes,
            }
            for jogo in jogos
        ]

    # ------------------------------------------------------------------
    # Paginação normal.
    # Só precisamos das subconsultas de preço quando o filtro/ordenação
    # realmente depende de preço/desconto.
    # ------------------------------------------------------------------
    precisa_preco = filtro == "desconto" or ordenacao in {
        "desconto",
        "menor-preco",
        "maior-preco",
    }

    steam_preco = None
    epic_preco = None

    if precisa_preco:
        ultima_data = (
            db.query(
                HistoricoPreco.jogo_id.label("jogo_id"),
                HistoricoPreco.plataforma.label("plataforma"),
                func.max(HistoricoPreco.data_coleta).label("ultima_data"),
            )
            .group_by(HistoricoPreco.jogo_id, HistoricoPreco.plataforma)
            .cte("ultima_data_historico")
        )

        steam_preco = (
            db.query(
                HistoricoPreco.jogo_id.label("jogo_id"),
                HistoricoPreco.preco_atual.label("preco"),
                HistoricoPreco.desconto.label("desconto"),
            )
            .join(
                ultima_data,
                (HistoricoPreco.jogo_id == ultima_data.c.jogo_id)
                & (HistoricoPreco.plataforma == ultima_data.c.plataforma)
                & (HistoricoPreco.data_coleta == ultima_data.c.ultima_data),
            )
            .filter(func.lower(HistoricoPreco.plataforma) == "steam")
            .subquery()
        )

        epic_preco = (
            db.query(
                HistoricoPreco.jogo_id.label("jogo_id"),
                HistoricoPreco.preco_atual.label("preco"),
                HistoricoPreco.desconto.label("desconto"),
            )
            .join(
                ultima_data,
                (HistoricoPreco.jogo_id == ultima_data.c.jogo_id)
                & (HistoricoPreco.plataforma == ultima_data.c.plataforma)
                & (HistoricoPreco.data_coleta == ultima_data.c.ultima_data),
            )
            .filter(
                func.lower(HistoricoPreco.plataforma).in_(
                    ["epic", "epic games", "epic games store"]
                )
            )
            .subquery()
        )

        query_base = query_base.outerjoin(
            steam_preco, steam_preco.c.jogo_id == Jogo.id
        )
        query_base = query_base.outerjoin(
            epic_preco, epic_preco.c.jogo_id == Jogo.id
        )

        desconto_steam = func.coalesce(steam_preco.c.desconto, 0)
        desconto_epic = func.coalesce(epic_preco.c.desconto, 0)
        maior_desconto = func.greatest(desconto_steam, desconto_epic)

        if filtro == "desconto":
            query_base = query_base.filter(maior_desconto > 0)

        if ordenacao == "desconto":
            query_base = query_base.order_by(
                maior_desconto.desc(), Jogo.nome.asc()
            )
        elif ordenacao == "menor-preco":
            menor_preco = func.least(
                func.coalesce(steam_preco.c.preco, 999999999),
                func.coalesce(epic_preco.c.preco, 999999999),
            )
            query_base = query_base.order_by(
                menor_preco.asc(), Jogo.nome.asc()
            )
        elif ordenacao == "maior-preco":
            maior_preco = func.greatest(
                func.coalesce(steam_preco.c.preco, -1),
                func.coalesce(epic_preco.c.preco, -1),
            )
            query_base = query_base.order_by(
                maior_preco.desc(), Jogo.nome.asc()
            )
        elif ordenacao == "mais-vistos":
            query_base = query_base.order_by(
                Jogo.visualizacoes.desc(), Jogo.id.asc()
            )
        else:
            query_base = query_base.order_by(Jogo.nome.asc())
    else:
        if ordenacao == "mais-vistos":
            query_base = query_base.order_by(
                Jogo.visualizacoes.desc(), Jogo.id.asc()
            )
        else:
            query_base = query_base.order_by(Jogo.nome.asc())

    total = query_base.count()
    total_paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = min(pagina, total_paginas)

    jogos = (
        query_base
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .all()
    )

    # Depois de escolher os 20 jogos, busca somente seus últimos históricos.
    jogo_ids = [jogo.id for jogo in jogos]
    ultimos_dados = {}

    if jogo_ids:
        ultima_data_pagina = (
            db.query(
                HistoricoPreco.jogo_id.label("jogo_id"),
                HistoricoPreco.plataforma.label("plataforma"),
                func.max(HistoricoPreco.data_coleta).label("ultima_data"),
            )
            .filter(HistoricoPreco.jogo_id.in_(jogo_ids))
            .group_by(HistoricoPreco.jogo_id, HistoricoPreco.plataforma)
            .subquery()
        )

        registros = (
            db.query(HistoricoPreco)
            .join(
                ultima_data_pagina,
                (HistoricoPreco.jogo_id == ultima_data_pagina.c.jogo_id)
                & (HistoricoPreco.plataforma == ultima_data_pagina.c.plataforma)
                & (HistoricoPreco.data_coleta == ultima_data_pagina.c.ultima_data),
            )
            .filter(HistoricoPreco.jogo_id.in_(jogo_ids))
            .all()
        )

        for registro in registros:
            chave = (registro.jogo_id, _normalizar_plataforma(registro.plataforma))
            ultimos_dados[chave] = {
                "desconto": registro.desconto or 0,
                "preco_atual": float(registro.preco_atual)
                if registro.preco_atual is not None
                else None,
            }

    resposta = [
        {
            "id": jogo.id,
            "nome": jogo.nome,
            "jogo_base_id": jogo.jogo_base_id,
            "steam_id": jogo.steam_id,
            "epic_id": jogo.epic_id,
            "desenvolvedor": jogo.desenvolvedor,
            "publicadora": jogo.publicadora,
            "genero": jogo.genero,
            "preco_base_steam": float(jogo.preco_base_steam) if jogo.preco_base_steam is not None else None,
            "preco_base_epic": float(jogo.preco_base_epic) if jogo.preco_base_epic is not None else None,
            "url_steam": jogo.url_steam,
            "url_epic": jogo.url_epic,
            "url_imagem_steam": jogo.url_imagem_steam,
            "url_imagem_epic": jogo.url_imagem_epic,
            "preco_atual_steam": ultimos_dados.get((jogo.id, "steam"), {}).get("preco_atual"),
            "preco_atual_epic": ultimos_dados.get((jogo.id, "epic"), {}).get("preco_atual"),
            "desconto_steam": ultimos_dados.get((jogo.id, "steam"), {}).get("desconto", 0),
            "desconto_epic": ultimos_dados.get((jogo.id, "epic"), {}).get("desconto", 0),
            "visualizacoes": jogo.visualizacoes,
        }
        for jogo in jogos
    ]

    _diagnostico_rotas_jogos["listar_jogos"]["chamadas"] += 1
    _diagnostico_rotas_jogos["listar_jogos"]["etapas"] = {
        "total": round((time.perf_counter() - inicio) * 1000, 2),
        "total_registros": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
    }

    return {
        "jogos": resposta,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "total_paginas": total_paginas,
    }


@router.get("/lote/historicos")
def obter_historico_lote(db: Session = Depends(get_db)):
    inicio_diagnostico = time.perf_counter()
    _diagnostico_rotas_jogos["historico_lote"]["chamadas"] += 1
    """
    Obtém o histórico de todos os jogos visíveis em uma única requisição.

    A rota mantém o mesmo formato de cada registro usado pelo frontend,
    mas elimina o N+1 de uma requisição HTTP por jogo.
    """
    # Mantém a mesma regra de visibilidade usada em /api/jogos/.
    jogos = (
        db.query(Jogo.id)
        .outerjoin(
            AuditoriaConteudo,
            AuditoriaConteudo.jogo_id == Jogo.id,
        )
        .filter(
            ~AuditoriaConteudo.status.in_(["pendente", "excluido"])
            | (AuditoriaConteudo.id.is_(None))
        )
        .filter(_jogo_visivel_catalogo())
        .all()
    )
    _diagnostico_rotas_jogos["historico_lote"]["etapas"]["consulta_jogos"] = round((time.perf_counter() - inicio_diagnostico) * 1000, 2)
    inicio_etapa = time.perf_counter()

    jogo_ids = [jogo.id for jogo in jogos]

    historicos_por_jogo = {jogo_id: [] for jogo_id in jogo_ids}

    if not jogo_ids:
        _diagnostico_rotas_jogos["historico_lote"]["etapas"]["total"] = round((time.perf_counter() - inicio_diagnostico) * 1000, 2)
        return historicos_por_jogo

    _diagnostico_rotas_jogos["historico_lote"]["etapas"]["montagem_ids"] = round((time.perf_counter() - inicio_etapa) * 1000, 2)
    inicio_etapa = time.perf_counter()

    # Busca somente as colunas que o frontend realmente utiliza no
    # analisarHistorico(), mantendo exatamente os mesmos nomes do endpoint
    # individual /{jogo_id}/historico.
    registros = (
        db.query(
            HistoricoPreco.id,
            HistoricoPreco.jogo_id,
            HistoricoPreco.nome_jogo,
            HistoricoPreco.plataforma,
            HistoricoPreco.preco_atual,
            HistoricoPreco.preco_sem_desconto,
            HistoricoPreco.desconto,
            HistoricoPreco.data_coleta,
            HistoricoPreco.promocao_id,
            HistoricoPreco.promocao_nome,
            HistoricoPreco.promocao_tipo,
            HistoricoPreco.promocao_inicio,
            HistoricoPreco.promocao_fim,
        )
        .filter(HistoricoPreco.jogo_id.in_(jogo_ids))
        .order_by(
            HistoricoPreco.jogo_id.asc(),
            HistoricoPreco.data_coleta.asc(),
        )
        .all()
    )
    _diagnostico_rotas_jogos["historico_lote"]["etapas"]["consulta_historicos"] = round((time.perf_counter() - inicio_etapa) * 1000, 2)
    _diagnostico_rotas_jogos["historico_lote"]["etapas"]["quantidade_registros"] = len(registros)
    inicio_etapa = time.perf_counter()

    for registro in registros:
        historicos_por_jogo[registro.jogo_id].append(
            {
                "id": registro.id,
                "jogo_id": registro.jogo_id,
                "nome_jogo": registro.nome_jogo,
                "plataforma": registro.plataforma,
                "preco_atual": (
                    float(registro.preco_atual)
                    if registro.preco_atual is not None
                    else None
                ),
                "preco_sem_desconto": (
                    float(registro.preco_sem_desconto)
                    if registro.preco_sem_desconto is not None
                    else None
                ),
                "desconto": registro.desconto or 0,
                "data_coleta": (
                    registro.data_coleta.isoformat()
                    if registro.data_coleta
                    else None
                ),
                "promocao_id": registro.promocao_id,
                "promocao_nome": registro.promocao_nome,
                "promocao_tipo": registro.promocao_tipo,
                "promocao_inicio": (
                    registro.promocao_inicio.isoformat()
                    if registro.promocao_inicio
                    else None
                ),
                "promocao_fim": (
                    registro.promocao_fim.isoformat()
                    if registro.promocao_fim
                    else None
                ),
            }
        )

    _diagnostico_rotas_jogos["historico_lote"]["etapas"]["processamento_registros"] = round((time.perf_counter() - inicio_etapa) * 1000, 2)
    _diagnostico_rotas_jogos["historico_lote"]["etapas"]["total"] = round((time.perf_counter() - inicio_diagnostico) * 1000, 2)
    _diagnostico_rotas_jogos["historico_lote"]["etapas"]["quantidade_jogos"] = len(jogo_ids)

    # Diagnóstico temporário: mede apenas a serialização JSON do payload.
    inicio_serializacao = time.perf_counter()
    json.dumps(historicos_por_jogo)
    _diagnostico_rotas_jogos["historico_lote"]["etapas"]["serializacao_json"] = round(
        (time.perf_counter() - inicio_serializacao) * 1000,
        2,
    )

    return historicos_por_jogo


@router.get("/diagnostico/performance")
async def diagnostico_performance():
    return _diagnostico_rotas_jogos


@router.get("/{jogo_id}/historico")
def obter_historico_jogo(jogo_id: int, db: Session = Depends(get_db)):
    """
    Obtém o histórico de preços de um jogo.
    """
    jogo = (
        db.query(Jogo)
        .filter(Jogo.id == jogo_id)
        .filter(_jogo_visivel_catalogo())
        .first()
    )

    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    historico = (
        db.query(HistoricoPreco)
        .filter(HistoricoPreco.jogo_id == jogo_id)
        .order_by(HistoricoPreco.data_coleta.asc())
        .all()
    )

    return [
        {
            "id": registro.id,
            "jogo_id": registro.jogo_id,
            "nome_jogo": registro.nome_jogo,
            "plataforma": registro.plataforma,
            "preco_atual": float(registro.preco_atual) if registro.preco_atual is not None else None,
            "preco_sem_desconto": float(registro.preco_sem_desconto) if registro.preco_sem_desconto is not None else None,
            "desconto": registro.desconto or 0,
            "data_coleta": registro.data_coleta.isoformat() if registro.data_coleta else None,

            # Dados da promoção
            "promocao_id": registro.promocao_id,
            "promocao_nome": registro.promocao_nome,
            "promocao_tipo": registro.promocao_tipo,
            "promocao_inicio": (
                registro.promocao_inicio.isoformat()
                if registro.promocao_inicio
                else None
            ),
            "promocao_fim": (
                registro.promocao_fim.isoformat()
                if registro.promocao_fim
                else None
            ),
        }
        for registro in historico
    ]


@router.get("/{jogo_id}/midia")
def obter_midia_jogo(jogo_id: int, db: Session = Depends(get_db)):
    """
    Obtém mídia das lojas diretamente, sem salvar imagens no banco.

    Quando o registro consultado não possui mídia própria, usa o
    jogo_base_id como fallback. Isso permite que edições como Deluxe,
    Gold etc. reutilizem a galeria do jogo-base quando a loja não
    disponibilizar uma galeria específica para a edição.
    """
    jogo = (
        db.query(Jogo)
        .filter(Jogo.id == jogo_id)
        .filter(_jogo_visivel_catalogo())
        .first()
    )

    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    jogo_base = None
    if jogo.jogo_base_id:
        jogo_base = db.query(Jogo).filter(Jogo.id == jogo.jogo_base_id).first()

    screenshots = []
    videos = []
    epic_imagens = []

    def buscar_midia_steam(steam_id, identificador):
        """Busca screenshots e vídeos da Steam para um App ID."""
        if not steam_id:
            return [], []

        url_steam = (
            "https://store.steampowered.com/api/appdetails"
            f"?appids={steam_id}&l=portuguese&cc=br"
        )

        try:
            resposta = requests.get(url_steam, timeout=15)
            resposta.raise_for_status()
            dados = resposta.json()

            dados_brutos = next(iter(dados.values()), None)

            if not dados_brutos or not dados_brutos.get("success", False):
                return [], []

            dados_jogo = dados_brutos.get("data") or {}

            screenshots = [
                {
                    "id": imagem.get("id"),
                    "thumbnail": imagem.get("path_thumbnail"),
                    "url": imagem.get("path_full"),
                }
                for imagem in dados_jogo.get("screenshots", [])
                if imagem.get("path_full")
            ]

            videos = [
                {
                    "id": video.get("id"),
                    "nome": video.get("name"),
                    "thumbnail": video.get("thumbnail"),
                    "webm": video.get("webm", {}),
                    "mp4": video.get("mp4", {}),
                    "destaque": video.get("highlight", False),
                }
                for video in dados_jogo.get("movies", [])
                if video.get("thumbnail")
            ]

            return screenshots, videos

        except requests.exceptions.Timeout:
            print(f"Timeout ao buscar mídia da Steam para o jogo {identificador}")
        except requests.exceptions.RequestException as erro:
            print(
                f"Erro de conexão ao buscar mídia da Steam para o jogo "
                f"{identificador}: {erro}"
            )
        except Exception as erro:
            print(
                f"Erro inesperado ao buscar mídia da Steam para o jogo "
                f"{identificador}: {erro}"
            )

        return [], []

    def normalizar(valor):
        return " ".join(str(valor or "").strip().lower().split())

    def corresponde_epic_id(oferta, epic_id_normalizado):
        if not epic_id_normalizado:
            return False

        candidatos = [
            oferta.get("productSlug"),
            oferta.get("urlSlug"),
            oferta.get("slug"),
            oferta.get("url"),
        ]

        return any(
            epic_id_normalizado == normalizar(candidato)
            or epic_id_normalizado in normalizar(candidato)
            for candidato in candidatos
            if candidato
        )

    def buscar_midia_epic(jogo_consulta):
        """Busca a galeria Epic de um registro específico."""
        if not jogo_consulta or not (jogo_consulta.epic_id or jogo_consulta.nome):
            return []

        titulo_jogo = normalizar(jogo_consulta.nome)
        epic_id_normalizado = normalizar(jogo_consulta.epic_id)
        ofertas_encontradas = []

        try:
            # Uma página da Epic pode representar um BASE_GAME ou uma EDITION.
            for tipo_oferta in ("BASE_GAME", "EDITION"):
                payload = {
                    "title": jogo_consulta.nome,
                    "offerType": tipo_oferta,
                    "page": 1,
                    "limit": 20,
                }

                resposta_epic = requests.post(
                    EGDATA_SEARCH_URL,
                    params={
                        "country": EGDATA_COUNTRY,
                        "locale": EGDATA_LOCALE,
                    },
                    json=payload,
                    timeout=15,
                )
                resposta_epic.raise_for_status()

                dados_epic = resposta_epic.json()
                ofertas_encontradas.extend(dados_epic.get("offers") or [])

            # Prioridade para o identificador persistido.
            oferta = next(
                (
                    item
                    for item in ofertas_encontradas
                    if corresponde_epic_id(item, epic_id_normalizado)
                ),
                None,
            )

            # Depois, título exato.
            if oferta is None:
                oferta = next(
                    (
                        item
                        for item in ofertas_encontradas
                        if normalizar(item.get("title")) == titulo_jogo
                    ),
                    None,
                )

            # Último recurso: título parcialmente correspondente.
            if oferta is None and titulo_jogo:
                oferta = next(
                    (
                        item
                        for item in ofertas_encontradas
                        if titulo_jogo in normalizar(item.get("title"))
                        or normalizar(item.get("title")) in titulo_jogo
                    ),
                    None,
                )

            if not oferta:
                return []

            imagens = oferta.get("keyImages") or []

            imagens_galeria = [
                imagem
                for imagem in imagens
                if isinstance(imagem, dict)
                and imagem.get("url")
                and imagem.get("type") == "featuredMedia"
            ]

            if not imagens_galeria:
                imagens_galeria = [
                    imagem
                    for imagem in imagens
                    if isinstance(imagem, dict)
                    and imagem.get("url")
                    and imagem.get("type") == "GalleryImage"
                ]

            resultado = [
                {
                    "id": f"epic-{indice}",
                    "thumbnail": imagem.get("url"),
                    "url": imagem.get("url"),
                    "type": imagem.get("type"),
                }
                for indice, imagem in enumerate(imagens_galeria)
            ]

            if resultado:
                print(
                    f"Mídia Epic encontrada para {jogo_consulta.nome}: "
                    f"{len(resultado)} imagens | "
                    f"tipo={oferta.get('offerType')} | "
                    f"oferta={oferta.get('title')}"
                )

            return resultado

        except requests.exceptions.Timeout:
            print(
                f"Timeout ao buscar mídia da Epic para o jogo "
                f"{jogo_consulta.id}"
            )
        except requests.exceptions.RequestException as erro:
            print(
                f"Erro de conexão ao buscar mídia da Epic para o jogo "
                f"{jogo_consulta.id}: {erro}"
            )
        except Exception as erro:
            print(
                f"Erro inesperado ao buscar mídia da Epic para o jogo "
                f"{jogo_consulta.id}: {erro}"
            )

        return []

    # ---------------------------------------------------------
    # STEAM
    # ---------------------------------------------------------
    screenshots, videos = buscar_midia_steam(
        jogo.steam_id,
        jogo_id,
    )

    # Fallback: se a edição não possui mídia Steam própria,
    # usa o jogo-base relacionado.
    if jogo_base and not screenshots and not videos:
        screenshots, videos = buscar_midia_steam(
            jogo_base.steam_id,
            jogo_base.id,
        )

        if screenshots or videos:
            print(
                f"Mídia Steam do jogo {jogo_id} obtida por fallback "
                f"do jogo-base {jogo_base.id}"
            )

    # ---------------------------------------------------------
    # EPIC / EGDATA
    # ---------------------------------------------------------
    epic_imagens = buscar_midia_epic(jogo)

    # Fallback: se a edição não possui galeria própria,
    # usa a galeria do jogo-base relacionado.
    if jogo_base and not epic_imagens:
        epic_imagens = buscar_midia_epic(jogo_base)

        if epic_imagens:
            print(
                f"Mídia Epic do jogo {jogo_id} obtida por fallback "
                f"do jogo-base {jogo_base.id}"
            )

    return {
        "screenshots": screenshots,
        "videos": videos,
        "epic_images": epic_imagens,
    }


# ---------------------------------------------------------------------------
# Vitrine inicial: uma única tabela de curadoria e uma escolha temporária
# por usuário. O ranking popular reaproveita Jogo.visualizacoes.
# ---------------------------------------------------------------------------
class RecomendacaoVitrinePayload(BaseModel):
    jogo_id: int


def _jogo_em_promocao(db: Session, jogo_id: int, agora=None) -> bool:
    """Confirma promoção ativa a partir do último registro por loja."""
    agora = agora or datetime.now(timezone.utc)
    ultima_data = (
        db.query(
            HistoricoPreco.plataforma.label("plataforma"),
            func.max(HistoricoPreco.data_coleta).label("ultima_data"),
        )
        .filter(HistoricoPreco.jogo_id == jogo_id)
        .group_by(HistoricoPreco.plataforma)
        .subquery()
    )
    registros = (
        db.query(HistoricoPreco)
        .join(
            ultima_data,
            (HistoricoPreco.plataforma == ultima_data.c.plataforma)
            & (HistoricoPreco.data_coleta == ultima_data.c.ultima_data),
        )
        .filter(HistoricoPreco.jogo_id == jogo_id)
        .filter(func.lower(HistoricoPreco.plataforma).in_(["steam", "epic", "epic games", "epic games store"]))
        .all()
    )
    for registro in registros:
        if (registro.desconto or 0) <= 0:
            continue
        fim = registro.promocao_fim
        if fim is None:
            return True
        if fim.tzinfo is None:
            fim = fim.replace(tzinfo=timezone.utc)
        if fim > agora:
            return True
    return False


def _vitrine_status_promocao(db: Session, jogo_id: int, agora=None) -> str:
    """Estado conservador da promoção: ativa, inativa ou desconhecida."""
    agora = agora or datetime.now(timezone.utc)
    try:
        registros = db.execute(text("""
            SELECT plataforma_norm, desconto, promocao_fim, data_coleta
            FROM (
                SELECT DISTINCT ON (
                    CASE WHEN lower(trim(plataforma)) IN
                        ('epic', 'epic games', 'epic games store') THEN 'epic'
                        ELSE lower(trim(plataforma)) END
                )
                    CASE WHEN lower(trim(plataforma)) IN
                        ('epic', 'epic games', 'epic games store') THEN 'epic'
                        ELSE lower(trim(plataforma)) END AS plataforma_norm,
                    desconto, promocao_fim, data_coleta, id
                FROM historico_precos
                WHERE jogo_id = :jogo_id
                  AND lower(trim(plataforma)) IN
                    ('steam', 'epic', 'epic games', 'epic games store')
                ORDER BY
                    CASE WHEN lower(trim(plataforma)) IN
                        ('epic', 'epic games', 'epic games store') THEN 'epic'
                        ELSE lower(trim(plataforma)) END,
                    data_coleta DESC, id DESC
            ) ultimos
        """), {"jogo_id": jogo_id}).mappings().all()
    except Exception:
        return "desconhecida"
    if not registros:
        return "desconhecida"

    desconhecida = False
    limite_recencia = agora - timedelta(hours=72)
    for registro in registros:
        coleta = registro["data_coleta"]
        if coleta and coleta.tzinfo is None:
            coleta = coleta.replace(tzinfo=timezone.utc)
        fim = registro["promocao_fim"]
        if fim and fim.tzinfo is None:
            fim = fim.replace(tzinfo=timezone.utc)
        if (registro["desconto"] or 0) > 0:
            if fim is not None and fim > agora:
                return "ativa"
            if fim is not None and fim <= agora:
                continue
            if coleta and coleta >= limite_recencia:
                return "ativa"
            desconhecida = True
        elif not coleta or coleta < limite_recencia:
            desconhecida = True
    return "desconhecida" if desconhecida else "inativa"


def _precos_atuais_vitrine(db: Session, jogos):
    """Busca em lote os preços mais recentes de cada loja para os jogos da vitrine."""
    jogo_ids = list({jogo.id for jogo in jogos})
    if not jogo_ids:
        return {}

    ultima_data = (
        db.query(
            HistoricoPreco.jogo_id.label("jogo_id"),
            HistoricoPreco.plataforma.label("plataforma"),
            func.max(HistoricoPreco.data_coleta).label("ultima_data"),
        )
        .filter(HistoricoPreco.jogo_id.in_(jogo_ids))
        .group_by(HistoricoPreco.jogo_id, HistoricoPreco.plataforma)
        .subquery()
    )
    registros = (
        db.query(HistoricoPreco)
        .join(
            ultima_data,
            (HistoricoPreco.jogo_id == ultima_data.c.jogo_id)
            & (HistoricoPreco.plataforma == ultima_data.c.plataforma)
            & (HistoricoPreco.data_coleta == ultima_data.c.ultima_data),
        )
        .filter(HistoricoPreco.jogo_id.in_(jogo_ids))
        .all()
    )

    resultado = {}
    for registro in registros:
        plataforma = _normalizar_plataforma(registro.plataforma)
        if plataforma not in {"steam", "epic"}:
            continue
        resultado.setdefault(registro.jogo_id, {})[plataforma] = {
            "preco_atual": float(registro.preco_atual)
            if registro.preco_atual is not None else None,
            "desconto": registro.desconto or 0,
        }
    return resultado


def _formatar_preco_vitrine(preco):
    if preco is None:
        return "—"
    if float(preco) == 0:
        return "Grátis"
    return f"R$ {float(preco):.2f}".replace(".", ",")


def _serializar_jogo_vitrine(jogo, precos_historico=None):
    precos_historico = precos_historico or {}
    steam = precos_historico.get("steam", {})
    epic = precos_historico.get("epic", {})
    preco_steam = steam.get("preco_atual")
    preco_epic = epic.get("preco_atual")

    # Se o histórico não tiver preço atual, mantém o preço-base como fallback.
    if preco_steam is None:
        preco_steam = float(jogo.preco_base_steam) if jogo.preco_base_steam is not None else None
    if preco_epic is None:
        preco_epic = float(jogo.preco_base_epic) if jogo.preco_base_epic is not None else None

    return {
        "id": jogo.id,
        "nome": jogo.nome,
        "imagem": jogo.url_imagem_steam or jogo.url_imagem_epic or (
            f"https://cdn.akamai.steamstatic.com/steam/apps/{jogo.steam_id}/header.jpg"
            if jogo.steam_id else ""
        ),
        "steam": _formatar_preco_vitrine(preco_steam),
        "epic": _formatar_preco_vitrine(preco_epic),
        "desconto": max(int(steam.get("desconto", 0) or 0), int(epic.get("desconto", 0) or 0)),
        "desconto_steam": int(steam.get("desconto", 0) or 0),
        "desconto_epic": int(epic.get("desconto", 0) or 0),
        "visualizacoes": jogo.visualizacoes or 0,
    }


@router.get("/vitrine/secoes")
def obter_vitrine_secoes(db: Session = Depends(get_db)):
    agora = datetime.now(timezone.utc)
    visiveis = (
        db.query(Jogo)
        .outerjoin(AuditoriaConteudo, AuditoriaConteudo.jogo_id == Jogo.id)
        .filter(
            (AuditoriaConteudo.id.is_(None))
            | (~AuditoriaConteudo.status.in_(["pendente", "excluido"]))
        )
        .filter(_jogo_visivel_catalogo())
    )

    em_alta = visiveis.order_by(Jogo.visualizacoes.desc(), Jogo.id.asc()).limit(12).all()

    # Uma tabela guarda estúdios, jogos brasileiros e oportunidades.
    # Tipos aceitos: estudio_brasileiro, jogo_brasileiro, oportunidade.
    try:
        # Brasil em jogo é estritamente manual e exige classificação brasileira.
        jogos_manuais = db.execute(text("""
            SELECT vi.jogo_id
            FROM vitrine_itens vi
            JOIN jogos j ON j.id = vi.jogo_id
            WHERE vi.tipo = 'jogo_brasileiro' AND vi.ativo = TRUE
              AND vi.jogo_id IS NOT NULL AND j.eh_brasileiro IS TRUE
              AND (vi.inicio_em IS NULL OR vi.inicio_em <= :agora)
              AND (vi.fim_em IS NULL OR vi.fim_em > :agora)
            ORDER BY vi.prioridade DESC, vi.id DESC LIMIT 40
        """), {"agora": agora}).scalars().all()
        por_id_br = {j.id: j for j in visiveis.filter(Jogo.id.in_(jogos_manuais)).all()} if jogos_manuais else {}
        brasileiros = [por_id_br[jogo_id] for jogo_id in jogos_manuais if jogo_id in por_id_br][:12]

        oportunidades_ids = db.execute(text("""
            SELECT vi.id AS item_id, vi.jogo_id
            FROM vitrine_itens vi
            WHERE vi.tipo = 'oportunidade' AND vi.ativo = TRUE AND vi.jogo_id IS NOT NULL
              AND (vi.inicio_em IS NULL OR vi.inicio_em <= :agora)
              AND (vi.fim_em IS NULL OR vi.fim_em > :agora)
            ORDER BY vi.prioridade DESC, vi.id DESC LIMIT 100
        """), {"agora": agora}).mappings().all()
        oportunidades = []
        houve_limpeza_oportunidades = False
        for registro in oportunidades_ids:
            jogo_id = int(registro["jogo_id"])
            estado = _vitrine_status_promocao(db, jogo_id, agora)
            if estado == "inativa":
                # Só desativa quando os dados disponíveis confirmam o fim; falhas
                # ou dados antigos mantêm o cadastro para a próxima coleta.
                db.execute(text("UPDATE vitrine_itens SET ativo = FALSE WHERE id = :id"), {"id": registro["item_id"]})
                houve_limpeza_oportunidades = True
                continue
            if estado != "ativa":
                continue
            jogo = visiveis.filter(Jogo.id == jogo_id).first()
            if jogo:
                oportunidades.append(jogo)
            if len(oportunidades) >= 12:
                break
        if houve_limpeza_oportunidades:
            db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="A migração simplificada da vitrine ainda não foi aplicada.") from exc

    # As recomendações são o campo atual de cada usuário, não um histórico.
    # Jogos fora de promoção não entram na contagem mesmo que a limpeza do campo
    # ainda não tenha ocorrido.
    recomendados_ids = (
        db.query(Usuario.jogo_recomendado_id, func.count(Usuario.id).label("total"))
        .filter(Usuario.jogo_recomendado_id.isnot(None))
        .group_by(Usuario.jogo_recomendado_id)
        .order_by(func.count(Usuario.id).desc(), Usuario.jogo_recomendado_id.asc())
        .limit(100)
        .all()
    )
    totais_recomendacoes = {int(jogo_id): int(total) for jogo_id, total in recomendados_ids}
    ids_validos = []
    for jogo_id, _total in recomendados_ids:
        if _jogo_em_promocao(db, jogo_id, agora):
            ids_validos.append(jogo_id)
    recomendados_visiveis = {
        jogo.id: jogo for jogo in visiveis.filter(Jogo.id.in_(ids_validos)).all()
    } if ids_validos else {}
    comunidade = [recomendados_visiveis[jogo_id] for jogo_id in ids_validos if jogo_id in recomendados_visiveis][:15]

    # Consulta os históricos uma única vez para todas as seções da página inicial.
    jogos_vitrine = brasileiros + comunidade + em_alta + oportunidades
    precos_por_jogo = _precos_atuais_vitrine(db, jogos_vitrine)

    def serializar(jogo):
        return _serializar_jogo_vitrine(jogo, precos_por_jogo.get(jogo.id))

    def serializar_recomendacao(jogo):
        item = serializar(jogo)
        item["total_recomendacoes"] = totais_recomendacoes.get(jogo.id, 0)
        return item

    return {
        "brasileiros": [serializar(jogo) for jogo in brasileiros],
        "comunidade": [serializar_recomendacao(jogo) for jogo in comunidade],
        "em_alta": [serializar(jogo) for jogo in em_alta],
        "oportunidades": [serializar(jogo) for jogo in oportunidades],
    }


@router.put("/vitrine/recomendacao")
def definir_recomendacao_vitrine(
    payload: RecomendacaoVitrinePayload,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    jogo = (
        db.query(Jogo)
        .filter(Jogo.id == payload.jogo_id)
        .filter(_jogo_visivel_catalogo())
        .first()
    )
    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado ou indisponível.")
    if not _jogo_em_promocao(db, jogo.id):
        raise HTTPException(status_code=400, detail="Você só pode recomendar um jogo que esteja em promoção.")

    recomendacao_anterior = usuario.jogo_recomendado_id
    usuario.jogo_recomendado_id = jogo.id
    db.flush()
    total = db.query(func.count(Usuario.id)).filter(Usuario.jogo_recomendado_id == jogo.id).scalar() or 0
    db.add(NotificacaoUsuario(
        usuario_id=usuario.id,
        tipo="recomendacao",
        titulo="Recomendação registrada",
        mensagem=f"Você recomendou {jogo.nome} para a comunidade.",
        link=f"/jogos/{jogo.id}",
        jogo_id=jogo.id,
        dados={"acao": "registrada", "recomendacoes": int(total)},
    ))
    db.commit()
    return {"mensagem": "Sua recomendação foi registrada.", "jogo_recomendado_id": jogo.id, "total_recomendacoes": int(total)}


@router.delete("/vitrine/recomendacao")
def limpar_recomendacao_vitrine(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    jogo_id_anterior = usuario.jogo_recomendado_id
    usuario.jogo_recomendado_id = None
    if jogo_id_anterior:
        jogo_anterior = db.query(Jogo).filter(Jogo.id == jogo_id_anterior).first()
        if jogo_anterior:
            db.add(NotificacaoUsuario(
                usuario_id=usuario.id,
                tipo="recomendacao",
                titulo="Recomendação removida",
                mensagem=f"Sua recomendação para {jogo_anterior.nome} foi removida.",
                link=f"/jogos/{jogo_anterior.id}",
                jogo_id=jogo_anterior.id,
                dados={"acao": "removida"},
            ))
    db.commit()
    return {"mensagem": "Sua recomendação foi removida."}


@router.get("/vitrine/minha-recomendacao")
def obter_minhas_recomendacoes(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(obter_usuario_atual),
):
    jogo_id = usuario.jogo_recomendado_id
    if not jogo_id:
        return {"recomendacao": None}
    jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()
    if not jogo:
        return {"recomendacao": None}
    estado = _vitrine_status_promocao(db, jogo.id)
    if estado == "inativa":
        usuario.jogo_recomendado_id = None
        db.add(NotificacaoUsuario(
            usuario_id=usuario.id,
            tipo="recomendacao",
            titulo="Promoção encerrada",
            mensagem=f"A recomendação de {jogo.nome} foi encerrada porque não há mais promoção ativa confirmada.",
            link=f"/jogos/{jogo.id}",
            jogo_id=jogo.id,
            dados={"acao": "promocao_encerrada"},
        ))
        db.commit()
        return {"recomendacao": None}
    total = db.query(func.count(Usuario.id)).filter(Usuario.jogo_recomendado_id == jogo.id).scalar() or 0
    return {"recomendacao": {
        "jogo_id": jogo.id,
        "nome": jogo.nome,
        # Segue o critério de imagem hero da página de detalhes.
        "imagem": (
            f"https://cdn.cloudflare.steamstatic.com/steam/apps/{jogo.steam_id}/library_hero.jpg"
            if jogo.steam_id
            else jogo.url_imagem_epic or jogo.url_imagem_steam or ""
        ),
        # Alternativa usada pelo frontend se a imagem principal falhar.
        "imagem_fallback": (
            jogo.url_imagem_steam or jogo.url_imagem_epic or (
                f"https://cdn.akamai.steamstatic.com/steam/apps/{jogo.steam_id}/header.jpg"
                if jogo.steam_id else ""
            )
        ),
        "total_recomendacoes": int(total),
        "promocao_status": estado,
        "link": f"/jogos/{jogo.id}",
    }}


@router.get("/{jogo_id}")
def obter_jogo(jogo_id: int, db: Session = Depends(get_db)):
    """
    Obtém detalhes completos de um jogo específico.

    Args:
        jogo_id (int): Identificador interno do jogo.
        db (Session): Sessão do banco de dados (injetada automaticamente).

    Returns:
        dict: Dados completos do jogo.

    Raises:
        HTTPException: Se o jogo não for encontrado (status 404).
    """
    jogo = (
        db.query(Jogo)
        .filter(Jogo.id == jogo_id)
        .filter(_jogo_visivel_catalogo())
        .first()
    )

    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    jogo.visualizacoes += 1
    db.commit()
    db.refresh(jogo)

    return {
        "id": jogo.id,
        "nome": jogo.nome,
        "jogo_base_id": jogo.jogo_base_id,
        "steam_id": jogo.steam_id,
        "epic_id": jogo.epic_id,
        "desenvolvedor": jogo.desenvolvedor,
        "publicadora": jogo.publicadora,
        "genero": jogo.genero,
        "data_lancamento": jogo.data_lancamento.isoformat() if jogo.data_lancamento else None,
        "descricao_steam": jogo.descricao_steam,
        "descricao_epic": jogo.descricao_epic,
        "url_imagem_steam": jogo.url_imagem_steam,
        "url_imagem_epic": jogo.url_imagem_epic,
        "url_steam": jogo.url_steam,
        "url_epic": jogo.url_epic,
        "preco_base_steam": float(jogo.preco_base_steam) if jogo.preco_base_steam is not None else None,
        "preco_base_epic": float(jogo.preco_base_epic) if jogo.preco_base_epic is not None else None,
        "visualizacoes": jogo.visualizacoes,
        "created_at": jogo.created_at.isoformat() if jogo.created_at else None,
        "updated_at": jogo.updated_at.isoformat() if jogo.updated_at else None,
    }


def _descricao_valida(descricao):
    if not descricao:
        return False

    valor = descricao.strip()
    return valor and valor.upper() not in {"N/A", "NÃO INFORMADO"}


@router.get("/{jogo_id}/descricao")
async def obter_descricao(jogo_id: int, db: Session = Depends(get_db)):
    """
    Obtém a descrição atual da Steam e usa o banco como fallback.
    """
    jogo = (
        db.query(Jogo)
        .filter(Jogo.id == jogo_id)
        .filter(_jogo_visivel_catalogo())
        .first()
    )

    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado")

    # Fallback: descrição já armazenada no banco.
    if _descricao_valida(jogo.descricao_steam):
        descricao_fallback = jogo.descricao_steam
        fonte_fallback = "Steam (banco de dados)"
    elif _descricao_valida(jogo.descricao_epic):
        descricao_fallback = jogo.descricao_epic
        fonte_fallback = "Epic Games Store (banco de dados)"
    else:
        descricao_fallback = None
        fonte_fallback = None

    # Fonte principal: Steam em tempo real.
    if jogo.steam_id:
        try:
            coletor = SteamColetor()
            dados_steam = await coletor.coletar_jogo(jogo.steam_id)
            descricao_steam = dados_steam.get("descricao")

            if _descricao_valida(descricao_steam):
                return {
                    "fonte": "Steam",
                    "descricao": descricao_steam,
                    "atualizada": True,
                }
        except Exception as erro:
            print(f"Não foi possível obter descrição atual da Steam para o jogo {jogo_id}: {erro}")

    # Se a Steam falhar, mantém a experiência usando o dado persistido.
    return {
        "fonte": fonte_fallback,
        "descricao": descricao_fallback,
        "atualizada": False,
    }


@router.get("/buscar/{termo}")
def buscar_jogos(termo: str, db: Session = Depends(get_db)):
    """
    Busca jogos pelo nome (busca parcial).

    Args:
        termo (str): Termo de busca.
        db (Session): Sessão do banco de dados (injetada automaticamente).

    Returns:
        list: Lista de jogos que correspondem ao termo.
    """
    jogos = (
        db.query(Jogo)
        .filter(
            or_(
                Jogo.nome.ilike(f"%{termo}%"),
                Jogo.desenvolvedor.ilike(f"%{termo}%"),
                Jogo.publicadora.ilike(f"%{termo}%"),
            )
        )
        .filter(_jogo_visivel_catalogo())
        .all()
    )

    return [
        {
            "id": jogo.id,
            "nome": jogo.nome,
            "jogo_base_id": jogo.jogo_base_id,
            "steam_id": jogo.steam_id,
            "epic_id": jogo.epic_id,
            "desenvolvedor": jogo.desenvolvedor,
            "publicadora": jogo.publicadora,
            "genero": jogo.genero,
            "preco_base_steam": float(jogo.preco_base_steam) if jogo.preco_base_steam is not None else None,
            "preco_base_epic": float(jogo.preco_base_epic) if jogo.preco_base_epic is not None else None,
            "url_imagem_steam": jogo.url_imagem_steam,
            "url_imagem_epic": jogo.url_imagem_epic,
        }
        for jogo in jogos
    ]
