"""Rotas administrativas para curadoria e auditoria editorial do catálogo."""

from datetime import date, datetime
from typing import Annotated

import requests

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, case, cast, func, or_, text
from sqlalchemy.orm import Session

from ..banco_dados import get_db
from ..modelos import (
    AuditoriaConteudo,
    AuditoriaConteudoHistorico,
    Jogo,
    EpicCatalogo,
    EpicOferta,
    Usuario,
    VitrineItem,
    now_brasilia,
)
from ..seguranca.autenticacao import obter_admin_atual
from ..servicos.promocoes import detalhes_promocao, estado_promocao, jogos_em_promocao, limpar_vitrine_encerrada
from .jogos import _jogo_visivel_catalogo


router = APIRouter(
    prefix="/api/admin/curadoria",
    tags=["curadoria-admin"],
)

AdminDep = Annotated[Usuario, Depends(obter_admin_atual)]


MOTIVOS_AUDITORIA = (
    "Conteúdo sensível",
    "Fora do catálogo",
    "Duplicado ou redundante",
    "Indisponível ou removido",
    "Problemas de qualidade ou integridade",
    "Outros",
)

MOTIVOS_APROVACAO = (
    "Dentro do escopo do catálogo",
    "Informações validadas",
    "Conteúdo considerado adequado",
    "Teste e validação",
    "Outros",
)

CONTEUDO_SENSIVEL_MOTIVO = MOTIVOS_AUDITORIA[0]
FORA_DO_CATALOGO_MOTIVO = MOTIVOS_AUDITORIA[1]


def _filtro_texto_jogo(termo: str, incluir_observacao: bool = False):
    """Condição de busca usada em todos os campos da Curadoria.

    Procura, sem diferenciar maiúsculas nem acentos, em: nome, IDs das lojas,
    desenvolvedora, publicadora e gênero (e na observação da auditoria, nas filas).
    Retorna None quando o termo está vazio.
    """
    termo_normalizado = (termo or "").strip()
    if not termo_normalizado:
        return None

    padrao = func.unaccent(f"%{termo_normalizado}%")
    campos = [
        Jogo.nome,
        Jogo.epic_id,
        cast(Jogo.steam_id, String),
        Jogo.desenvolvedor,
        Jogo.publicadora,
        Jogo.genero,
    ]
    if incluir_observacao:
        campos.append(AuditoriaConteudo.observacao)
    return or_(*[func.unaccent(func.coalesce(campo, "")).ilike(padrao) for campo in campos])


def _aplicar_busca_textual_auditoria(consulta, termo: str):
    """Aplica a mesma busca a todas as filas (pendentes, sensível e decididas)."""
    condicao = _filtro_texto_jogo(termo, incluir_observacao=True)
    return consulta if condicao is None else consulta.filter(condicao)


def validar_motivo_aprovacao(motivo: str | None) -> str | None:
    if motivo is None:
        return None

    motivo_normalizado = motivo.strip()
    if motivo_normalizado not in MOTIVOS_APROVACAO:
        raise HTTPException(
            status_code=422,
            detail=(
                "Selecione um motivo de aprovação válido: "
                + ", ".join(MOTIVOS_APROVACAO)
            ),
        )

    return motivo_normalizado


def validar_motivo_auditoria(motivo: str | None) -> str | None:
    if motivo is None:
        return None

    motivo_normalizado = motivo.strip()
    if motivo_normalizado not in MOTIVOS_AUDITORIA:
        raise HTTPException(
            status_code=422,
            detail=(
                "Motivo de auditoria inválido. Use uma das categorias: "
                + ", ".join(MOTIVOS_AUDITORIA)
            ),
        )

    return motivo_normalizado


class CuradoriaCriar(BaseModel):
    jogo_id: int
    motivo: str | None = Field(default=None, max_length=255)
    observacao: str | None = None


class CuradoriaDecisao(BaseModel):
    motivo: str | None = Field(default=None, max_length=255)
    observacao: str | None = None


class CuradoriaResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    jogo_id: int
    nome: str
    epic_id: str | None
    steam_id: str | None
    url_epic: str | None
    url_steam: str | None
    imagem_epic: str | None
    imagem_steam: str | None
    imagens: list
    status: str
    origem: str
    motivo: str | None
    observacao: str | None
    criado_em: datetime
    decidido_em: datetime | None

    # Sinais da auditoria de conteúdo sensível.
    steam_conteudo_adulto: bool
    status_auditoria: str

    # Metadados do jogo exibidos no painel de decisão, para evitar abrir a loja.
    desenvolvedor: str | None = None
    publicadora: str | None = None
    genero: str | None = None
    data_lancamento: date | None = None
    steam_required_age: int | None = None
    steam_content_descriptors: dict | None = None
    steam_content_notes: str | None = None

    # Resumo opcional do encaminhamento automático de jogos relacionados.
    jogos_relacionados_encontrados: int = 0
    jogos_relacionados_adicionados: int = 0
    jogos_relacionados_reabertos: int = 0
    jogos_relacionados_reclassificados: int = 0
    jogos_relacionados_ja_pendentes: int = 0
    jogos_relacionados_ja_excluidos: int = 0
    jogos_relacionados_ja_aprovados: int = 0


class CuradoriaPaginaResposta(BaseModel):
    """Envelope paginado das filas administrativas de curadoria."""

    items: list[CuradoriaResposta]
    total: int
    page: int
    page_size: int
    total_geral: int | None = None


class CuradoriaHistoricoResposta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    curadoria_id: int
    status_anterior: str | None
    status_novo: str
    motivo: str | None
    observacao: str | None
    usuario_id: int | None
    criado_em: datetime


def _serializar(
    curadoria: AuditoriaConteudo,
    resumo_relacionados: dict[str, int] | None = None,
) -> CuradoriaResposta:
    resumo_relacionados = resumo_relacionados or {}
    jogo = curadoria.jogo

    # Alguns registros antigos podem não ter a URL da Steam persistida,
    # mas todos os jogos do catálogo possuem steam_id. Nesse caso,
    # montamos a URL diretamente a partir do App ID para a curadoria.
    steam_id = str(jogo.steam_id).strip() if jogo.steam_id is not None else None
    url_steam = jogo.url_steam
    if not url_steam and steam_id and steam_id.isdigit():
        url_steam = f"https://store.steampowered.com/app/{steam_id}/"

    return CuradoriaResposta(
        id=curadoria.id,
        jogo_id=jogo.id,
        nome=jogo.nome,
        epic_id=jogo.epic_id,
        steam_id=steam_id,
        url_epic=jogo.url_epic,
        url_steam=url_steam,
        imagem_epic=jogo.url_imagem_epic,
        imagem_steam=jogo.url_imagem_steam,
        imagens=curadoria.imagens or [],
        status=curadoria.status,
        origem=curadoria.origem,
        motivo=curadoria.motivo,
        observacao=curadoria.observacao,
        criado_em=curadoria.criado_em,
        decidido_em=curadoria.decidido_em,
        steam_conteudo_adulto=bool(jogo.steam_conteudo_adulto),
        status_auditoria=jogo.status_auditoria,
        desenvolvedor=jogo.desenvolvedor,
        publicadora=jogo.publicadora,
        genero=jogo.genero,
        data_lancamento=jogo.data_lancamento,
        steam_required_age=jogo.steam_required_age,
        steam_content_descriptors=(
            jogo.steam_content_descriptors
            if isinstance(jogo.steam_content_descriptors, dict)
            else None
        ),
        steam_content_notes=jogo.steam_content_notes,
        jogos_relacionados_encontrados=resumo_relacionados.get("encontrados", 0),
        jogos_relacionados_adicionados=resumo_relacionados.get("adicionados", 0),
        jogos_relacionados_reabertos=resumo_relacionados.get("reabertos", 0),
        jogos_relacionados_reclassificados=resumo_relacionados.get("reclassificados", 0),
        jogos_relacionados_ja_pendentes=resumo_relacionados.get("ja_pendentes", 0),
        jogos_relacionados_ja_excluidos=resumo_relacionados.get("ja_excluidos", 0),
        jogos_relacionados_ja_aprovados=resumo_relacionados.get("ja_aprovados", 0),
    )


def _extrair_imagens_egdata(offer_id: str) -> list[str]:
    """Busca as imagens do offer diretamente na EGDATA."""
    url = f"https://api.egdata.app/offers/{offer_id}"
    resposta = requests.get(
        url,
        params={"locale": "pt-BR"},
        timeout=20,
    )
    resposta.raise_for_status()
    dados = resposta.json()

    imagens = []
    vistos = set()
    for imagem in dados.get("keyImages") or []:
        if not isinstance(imagem, dict):
            continue
        imagem_url = imagem.get("url")
        if not imagem_url or not isinstance(imagem_url, str):
            continue
        if not imagem_url.startswith(("http://", "https://")):
            continue
        if imagem_url in vistos:
            continue
        vistos.add(imagem_url)
        imagens.append(imagem_url)

    return imagens[:8]


def _extrair_imagens_steam(steam_id: str | None) -> list[str]:
    """Busca screenshots da Steam para complementar a galeria de auditoria."""
    app_id = str(steam_id or '').strip()
    if not app_id.isdigit():
        return []

    url = "https://store.steampowered.com/api/appdetails"
    try:
        resposta = requests.get(
            url,
            params={"appids": app_id, "l": "portuguese", "cc": "br"},
            timeout=12,
        )
        resposta.raise_for_status()
        payload = resposta.json().get(app_id) or {}
        if not payload.get("success"):
            return []

        dados = payload.get("data") or {}
        resultado = []
        vistos = set()
        for screenshot in dados.get("screenshots") or []:
            imagem_url = screenshot.get("path_full") if isinstance(screenshot, dict) else None
            if (
                isinstance(imagem_url, str)
                and imagem_url.startswith(("http://", "https://"))
                and imagem_url not in vistos
            ):
                vistos.add(imagem_url)
                resultado.append(imagem_url)
            if len(resultado) >= 8:
                break
        return resultado
    except (requests.RequestException, ValueError) as exc:
        # A galeria é complementar; falha na Steam não bloqueia a auditoria.
        print(f"Não foi possível obter screenshots da Steam para AppID {app_id}: {exc}")
        return []


def _buscar_offer_id(curadoria: AuditoriaConteudo, db: Session) -> str | None:
    """Resolve o offer_id usando o catálogo persistido e, depois, EpicOferta."""
    catalogo = (
        db.query(EpicCatalogo)
        .filter(EpicCatalogo.jogo_id == curadoria.jogo_id)
        .order_by(EpicCatalogo.id.desc())
        .first()
    )
    if catalogo and catalogo.epic_offer_id:
        return catalogo.epic_offer_id

    oferta = (
        db.query(EpicOferta)
        .filter(EpicOferta.jogo_id == curadoria.jogo_id)
        .order_by(EpicOferta.ativo.desc(), EpicOferta.id.asc())
        .first()
    )
    return oferta.offer_id if oferta else None


@router.post("/{curadoria_id}/midias", response_model=CuradoriaResposta)
def atualizar_midias(
    _: AdminDep,
    curadoria_id: int,
    db: Session = Depends(get_db),
):
    """Atualiza a galeria usando EGDATA e screenshots Steam, sem bloquear a auditoria se uma loja falhar."""
    curadoria = (
        db.query(AuditoriaConteudo)
        .filter(AuditoriaConteudo.id == curadoria_id)
        .first()
    )
    if not curadoria:
        raise HTTPException(
            status_code=404,
            detail="Registro de curadoria não encontrado.",
        )

    jogo = curadoria.jogo
    offer_id = _buscar_offer_id(curadoria, db)
    imagens_epic = []
    if offer_id:
        try:
            imagens_epic = _extrair_imagens_egdata(offer_id)
        except (requests.RequestException, ValueError) as exc:
            print(f"Não foi possível obter imagens EGDATA para o jogo {jogo.id}: {exc}")

    imagens_steam = _extrair_imagens_steam(jogo.steam_id)

    # Mantém a capa no início e deduplica as fontes antes de persistir.
    imagens_combinadas = []
    vistos = set()
    fontes = [
        jogo.url_imagem_epic,
        jogo.url_imagem_steam,
        *(curadoria.imagens or []),
        *imagens_epic,
        *imagens_steam,
    ]
    for imagem in fontes:
        if isinstance(imagem, dict):
            imagem = imagem.get("url")
        if (
            isinstance(imagem, str)
            and imagem.startswith(("http://", "https://"))
            and imagem not in vistos
        ):
            vistos.add(imagem)
            imagens_combinadas.append(imagem)
        if len(imagens_combinadas) >= 8:
            break

    if imagens_combinadas and imagens_combinadas != (curadoria.imagens or []):
        curadoria.imagens = imagens_combinadas
        db.commit()
        db.refresh(curadoria)

    return _serializar(curadoria)


LIMITE_BUSCA_CATALOGO = 40


@router.get("/buscar", response_model=list[dict])
def buscar_jogos_para_curadoria(
    _: AdminDep,
    termo: str = Query(min_length=2, max_length=100),
    db: Session = Depends(get_db),
):
    """Busca jogos no catálogo e informa a situação de cada um na Curadoria."""
    termo_limpo = termo.strip()
    comeca_com = case((func.unaccent(Jogo.nome).ilike(func.unaccent(f"{termo_limpo}%")), 0), else_=1)
    jogos = (
        db.query(Jogo)
        .filter(_filtro_texto_jogo(termo_limpo))
        .order_by(comeca_com, Jogo.visualizacoes.desc().nullslast(), Jogo.nome.asc())
        .limit(LIMITE_BUSCA_CATALOGO)
        .all()
    )
    ids = [jogo.id for jogo in jogos]
    promocoes = detalhes_promocao(db, ids)

    auditorias = {}
    vitrine: dict[int, list[str]] = {}
    if ids:
        for jogo_id, status_auditoria, motivo in (
            db.query(AuditoriaConteudo.jogo_id, AuditoriaConteudo.status, AuditoriaConteudo.motivo)
            .filter(AuditoriaConteudo.jogo_id.in_(ids))
            .all()
        ):
            auditorias[jogo_id] = {"status": status_auditoria, "motivo": motivo}
        for jogo_id, tipo in db.query(VitrineItem.jogo_id, VitrineItem.tipo).filter(VitrineItem.jogo_id.in_(ids)).all():
            vitrine.setdefault(int(jogo_id), []).append(tipo)

    return [
        {
            "id": jogo.id,
            "nome": jogo.nome,
            "epic_id": jogo.epic_id,
            "steam_id": jogo.steam_id,
            "url_epic": jogo.url_epic,
            "imagem_steam": jogo.url_imagem_steam,
            "imagem_epic": jogo.url_imagem_epic or jogo.url_imagem_steam,
            "desenvolvedor": jogo.desenvolvedor,
            "publicadora": jogo.publicadora,
            "eh_brasileiro": bool(jogo.eh_brasileiro),
            "promocao_ativa": promocoes.get(jogo.id, {}).get("estado") == "ativa",
            "desconto": promocoes.get(jogo.id, {}).get("desconto", 0),
            "auditoria_status": auditorias.get(jogo.id, {}).get("status"),
            "auditoria_motivo": auditorias.get(jogo.id, {}).get("motivo"),
            "vitrine": vitrine.get(jogo.id, []),
        }
        for jogo in jogos
    ]


@router.post("/conteudo-sensivel", response_model=CuradoriaResposta, status_code=status.HTTP_201_CREATED)
def adicionar_conteudo_sensivel(
    admin: AdminDep,
    dados: CuradoriaCriar,
    db: Session = Depends(get_db),
):
    """Adiciona manualmente um jogo à fila específica de conteúdo sensível."""
    jogo = db.query(Jogo).filter(Jogo.id == dados.jogo_id).first()
    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")

    existente = (
        db.query(AuditoriaConteudo)
        .filter(AuditoriaConteudo.jogo_id == jogo.id)
        .first()
    )

    if existente:
        if existente.motivo == CONTEUDO_SENSIVEL_MOTIVO and existente.status == "excluido":
            raise HTTPException(
                status_code=409,
                detail="Este jogo já foi retirado desta auditoria de conteúdo sensível.",
            )
        raise HTTPException(
            status_code=409,
            detail=f"Este jogo já está na auditoria com status '{existente.status}'.",
        )

    if jogo.status_auditoria == "nao_avaliado":
        jogo.status_auditoria = "pendente"

    curadoria = AuditoriaConteudo(
        jogo_id=jogo.id,
        nome_jogo=jogo.nome,
        status="pendente",
        origem="manual",
        motivo=CONTEUDO_SENSIVEL_MOTIVO,
        observacao=dados.observacao,
        imagens=[jogo.url_imagem_epic] if jogo.url_imagem_epic else [],
        criado_por=admin.id,
    )

    db.add(curadoria)
    db.flush()

    db.add(
        AuditoriaConteudoHistorico(
            auditoria_id=curadoria.id,
            jogo_id=curadoria.jogo_id,
            nome_jogo=curadoria.jogo.nome,
            status_anterior=None,
            status_novo="pendente",
            motivo=CONTEUDO_SENSIVEL_MOTIVO,
            observacao=dados.observacao,
            usuario_id=admin.id,
        )
    )

    db.commit()
    db.refresh(curadoria)
    return _serializar(curadoria)


@router.get("/conteudo-sensivel", response_model=CuradoriaPaginaResposta)
def listar_conteudo_sensivel(
    _: AdminDep,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
):
    """Lista conteúdo sensível pendente usando paginação e filtro no banco."""
    consulta = (
        db.query(AuditoriaConteudo)
        .join(Jogo)
        .filter(
            AuditoriaConteudo.status == "pendente",
            AuditoriaConteudo.motivo == CONTEUDO_SENSIVEL_MOTIVO,
        )
    )

    consulta = _aplicar_busca_textual_auditoria(consulta, q or "")

    total = consulta.order_by(None).with_entities(func.count(AuditoriaConteudo.id)).scalar() or 0

    # Mantém a priorização visual que antes era calculada depois de baixar toda a fila.
    prioridade = case(
        (AuditoriaConteudo.observacao.ilike("Prioridade de revisão: P1%"), 1),
        (AuditoriaConteudo.observacao.ilike("Prioridade de revisão: P2%"), 2),
        (AuditoriaConteudo.observacao.ilike("Prioridade de revisão: P3%"), 3),
        (AuditoriaConteudo.observacao.ilike("Prioridade de revisão: P4%"), 4),
        (AuditoriaConteudo.observacao.ilike("Prioridade de revisão: P5%"), 5),
        else_=99,
    )
    registros = (
        consulta
        .order_by(prioridade.asc(), AuditoriaConteudo.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return CuradoriaPaginaResposta(
        items=[_serializar(item) for item in registros],
        total=int(total),
        page=page,
        page_size=page_size,
    )


@router.post("/", response_model=CuradoriaResposta, status_code=status.HTTP_201_CREATED)
def adicionar_para_avaliacao(
    admin: AdminDep,
    dados: CuradoriaCriar,
    db: Session = Depends(get_db),
):
    """
    Adiciona manualmente um jogo à fila de avaliação.

    Se o jogo já possui uma auditoria decidida (aprovado/excluído),
    a mesma auditoria é reaberta como pendente. Isso preserva o registro
    único por jogo e acrescenta uma nova entrada ao histórico, em vez de
    criar uma segunda auditoria para o mesmo jogo.
    """
    motivo = validar_motivo_auditoria(dados.motivo)
    if motivo is None:
        raise HTTPException(
            status_code=422,
            detail="Selecione uma categoria de motivo para a auditoria.",
        )

    # Conteúdo sensível usa a aba específica, mas pode ser enviado
    # normalmente pelo botão Auditar da página de Jogos. O registro será
    # listado em /conteudo-sensivel em vez de /pendentes.
    jogo = db.query(Jogo).filter(Jogo.id == dados.jogo_id).first()
    if not jogo:
        raise HTTPException(status_code=404, detail="Jogo não encontrado.")

    existente = (
        db.query(AuditoriaConteudo)
        .filter(AuditoriaConteudo.jogo_id == jogo.id)
        .first()
    )

    if existente:
        if existente.status == "pendente":
            raise HTTPException(
                status_code=409,
                detail="Este jogo já está aguardando análise.",
            )

        if existente.status not in {"aprovado", "excluido"}:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Este jogo possui uma auditoria com status "
                    f"'{existente.status}' e não pode ser reenviado agora."
                ),
            )

        # Reabre a auditoria existente. O jogo continua com uma única
        # linha em auditorias_conteudo, enquanto cada nova ação fica
        # registrada em auditorias_conteudo_historico.
        status_anterior = existente.status

        existente.status = "pendente"
        existente.origem = "manual"
        existente.motivo = motivo
        existente.observacao = dados.observacao
        existente.decidido_por = None
        existente.decidido_em = None

        jogo.status_auditoria = "pendente"

        db.add(
            AuditoriaConteudoHistorico(
                auditoria_id=existente.id,
                jogo_id=existente.jogo_id,
                nome_jogo=jogo.nome,
                status_anterior=status_anterior,
                status_novo="pendente",
                motivo=motivo,
                observacao=dados.observacao,
                usuario_id=admin.id,
            )
        )

        db.commit()
        db.refresh(existente)

        return _serializar(existente)

    if jogo.status_auditoria == "nao_avaliado":
        jogo.status_auditoria = "pendente"

    curadoria = AuditoriaConteudo(
        jogo_id=jogo.id,
        nome_jogo=jogo.nome,
        status="pendente",
        origem="manual",
        motivo=motivo,
        observacao=dados.observacao,
        imagens=[jogo.url_imagem_epic] if jogo.url_imagem_epic else [],
        criado_por=admin.id,
    )

    db.add(curadoria)
    db.flush()

    historico = AuditoriaConteudoHistorico(
        auditoria_id=curadoria.id,
        jogo_id=curadoria.jogo_id,
        nome_jogo=curadoria.jogo.nome,
        status_anterior=None,
        status_novo="pendente",
        motivo=motivo,
        observacao=dados.observacao,
        usuario_id=admin.id,
    )

    db.add(historico)
    db.commit()
    db.refresh(curadoria)

    return _serializar(curadoria)


@router.get("/pendentes", response_model=CuradoriaPaginaResposta)
def listar_pendentes(
    _: AdminDep,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    motivo: str | None = Query(default=None, max_length=255),
    q: str | None = Query(default=None, max_length=255),
):
    """Lista jogos aguardando decisão, com busca e paginação executadas no banco."""
    consulta = (
        db.query(AuditoriaConteudo)
        .join(Jogo)
        .filter(
            AuditoriaConteudo.status == "pendente",
            or_(
                AuditoriaConteudo.motivo.is_(None),
                AuditoriaConteudo.motivo != CONTEUDO_SENSIVEL_MOTIVO,
            ),
        )
    )
    total_geral = consulta.order_by(None).with_entities(func.count(AuditoriaConteudo.id)).scalar() or 0
    if motivo:
        consulta = consulta.filter(AuditoriaConteudo.motivo == motivo)
    termo = (q or "").strip()
    consulta = _aplicar_busca_textual_auditoria(consulta, termo)

    # A paginação é sempre aplicada: a fila completa pode ter milhares de itens.
    pagina, tamanho = page, page_size
    total = consulta.order_by(None).with_entities(func.count(AuditoriaConteudo.id)).scalar() or 0
    registros = (
        consulta
        .order_by(AuditoriaConteudo.criado_em.asc(), AuditoriaConteudo.id.asc())
        .offset((pagina - 1) * tamanho)
        .limit(tamanho)
        .all()
    )
    return CuradoriaPaginaResposta(
        items=[_serializar(item) for item in registros],
        total=int(total),
        page=pagina,
        page_size=tamanho,
        total_geral=int(total_geral),
    )


@router.get("/status/{status_filtro}", response_model=CuradoriaPaginaResposta)
def listar_por_status(
    _: AdminDep,
    status_filtro: str,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    motivo: str | None = Query(default=None, max_length=255),
    q: str | None = Query(default=None, max_length=255),
):
    """Lista auditorias decididas, com busca e paginação executadas no banco."""
    if status_filtro not in {"aprovado", "excluido"}:
        raise HTTPException(
            status_code=400,
            detail="Status inválido. Use 'aprovado' ou 'excluido'.",
        )

    consulta = (
        db.query(AuditoriaConteudo)
        .join(Jogo)
        .filter(AuditoriaConteudo.status == status_filtro)
    )
    if motivo:
        consulta = consulta.filter(AuditoriaConteudo.motivo == motivo)
    termo = (q or "").strip()
    consulta = _aplicar_busca_textual_auditoria(consulta, termo)

    # A paginação é sempre aplicada: a lista de excluídos passa de 28 mil itens.
    ordenacao = (AuditoriaConteudo.decidido_em.desc(), AuditoriaConteudo.id.desc())
    pagina, tamanho = page, page_size
    total = consulta.order_by(None).with_entities(func.count(AuditoriaConteudo.id)).scalar() or 0
    registros = (
        consulta
        .order_by(*ordenacao)
        .offset((pagina - 1) * tamanho)
        .limit(tamanho)
        .all()
    )
    return CuradoriaPaginaResposta(
        items=[_serializar(item) for item in registros],
        total=int(total),
        page=pagina,
        page_size=tamanho,
    )


@router.get("/motivos", response_model=list[str])
def listar_motivos(
    _: AdminDep,
):
    """Retorna as categorias oficiais de motivo da auditoria."""
    return list(MOTIVOS_AUDITORIA)


@router.get("/historico", response_model=list[CuradoriaHistoricoResposta])
def listar_historico(
    _: AdminDep,
    curadoria_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Lista o histórico das decisões de curadoria."""
    query = db.query(AuditoriaConteudoHistorico).order_by(
        AuditoriaConteudoHistorico.criado_em.desc()
    )
    if curadoria_id is not None:
        query = query.filter(AuditoriaConteudoHistorico.auditoria_id == curadoria_id)

    return [
        CuradoriaHistoricoResposta(
            id=item.id,
            curadoria_id=item.auditoria_id,
            status_anterior=item.status_anterior,
            status_novo=item.status_novo,
            motivo=item.motivo,
            observacao=item.observacao,
            usuario_id=item.usuario_id,
            criado_em=item.criado_em,
        )
        for item in query.limit(200).all()
    ]


def _normalizar_nome_empresa(valor: str | None) -> str | None:
    """Normaliza desenvolvedora/publicadora para comparação exata sem diferenças de caixa/espaço."""
    if not isinstance(valor, str):
        return None
    normalizado = valor.strip().lower()
    return normalizado or None


def _anexar_observacao(observacao_atual: str | None, nova_observacao: str) -> str:
    atual = (observacao_atual or "").strip()
    if not atual:
        return nova_observacao
    if nova_observacao in atual:
        return atual
    return f"{atual}\n\n{nova_observacao}"


def _encaminhar_jogos_relacionados_para_auditoria(
    jogo_origem: Jogo,
    db: Session,
    admin: Usuario,
    motivo_destino: str,
) -> dict[str, int]:
    """
    Encaminha jogos da mesma desenvolvedora e/ou publicadora para revisão.

    A correspondência é exata, ignorando caixa e espaços nas extremidades.
    O relacionamento é apenas um sinal para revisão, não uma decisão automática.
    Para "Fora do catálogo", auditorias pendentes por outro motivo são preservadas.
    """
    if motivo_destino not in {CONTEUDO_SENSIVEL_MOTIVO, FORA_DO_CATALOGO_MOTIVO}:
        raise ValueError(f"Motivo de encaminhamento não suportado: {motivo_destino}")

    desenvolvedora = _normalizar_nome_empresa(jogo_origem.desenvolvedor)
    publicadora = _normalizar_nome_empresa(jogo_origem.publicadora)

    resumo = {
        "encontrados": 0,
        "adicionados": 0,
        "reabertos": 0,
        "reclassificados": 0,
        "ja_pendentes": 0,
        "ja_excluidos": 0,
        "ja_aprovados": 0,
    }

    if not desenvolvedora and not publicadora:
        return resumo

    criterios = []
    if desenvolvedora:
        criterios.append(func.lower(func.trim(Jogo.desenvolvedor)) == desenvolvedora)
    if publicadora:
        criterios.append(func.lower(func.trim(Jogo.publicadora)) == publicadora)

    jogos_relacionados = (
        db.query(Jogo)
        .filter(Jogo.id != jogo_origem.id, or_(*criterios))
        .order_by(Jogo.id.asc())
        .all()
    )
    resumo["encontrados"] = len(jogos_relacionados)
    if not jogos_relacionados:
        return resumo

    ids_relacionados = [jogo.id for jogo in jogos_relacionados]
    auditorias_existentes = (
        db.query(AuditoriaConteudo)
        .filter(AuditoriaConteudo.jogo_id.in_(ids_relacionados))
        .all()
    )
    auditoria_por_jogo = {item.jogo_id: item for item in auditorias_existentes}

    novas_auditorias: list[tuple[Jogo, AuditoriaConteudo, str]] = []
    historicos: list[AuditoriaConteudoHistorico] = []

    for relacionado in jogos_relacionados:
        campos_correspondentes = []
        if desenvolvedora and _normalizar_nome_empresa(relacionado.desenvolvedor) == desenvolvedora:
            campos_correspondentes.append(
                f"desenvolvedora '{(jogo_origem.desenvolvedor or '').strip()}'"
            )
        if publicadora and _normalizar_nome_empresa(relacionado.publicadora) == publicadora:
            campos_correspondentes.append(
                f"publicadora '{(jogo_origem.publicadora or '').strip()}'"
            )

        relacao = " e ".join(campos_correspondentes) or "empresa relacionada"
        if motivo_destino == CONTEUDO_SENSIVEL_MOTIVO:
            observacao_automatica = (
                "Encaminhado automaticamente para avaliação de conteúdo sensível por "
                f"compartilhar {relacao} com '{jogo_origem.nome}' (jogo ID {jogo_origem.id}). "
                "A correspondência é apenas um sinal para revisão e não confirma, por si só, "
                "que este jogo contém conteúdo sensível."
            )
        else:
            observacao_automatica = (
                "Encaminhado automaticamente para avaliação de catálogo por "
                f"compartilhar {relacao} com '{jogo_origem.nome}' (jogo ID {jogo_origem.id}). "
                "A relação é apenas um sinal para revisão e não determina automaticamente "
                "que este jogo esteja fora do catálogo."
            )

        existente = auditoria_por_jogo.get(relacionado.id)
        if existente:
            if existente.status == "aprovado":
                relacionado.status_auditoria = "aprovado"
                resumo["ja_aprovados"] += 1
                continue

            if existente.status == "excluido":
                relacionado.status_auditoria = "excluido"
                resumo["ja_excluidos"] += 1
                continue

            if existente.status == "pendente":
                # Se já está na fila de destino, não duplica o histórico.
                if existente.motivo == motivo_destino:
                    relacionado.status_auditoria = "pendente"
                    resumo["ja_pendentes"] += 1
                    continue

                # No fluxo "Fora do catálogo", filas pendentes de outros motivos
                # são preservadas sem reclassificação.
                if motivo_destino == FORA_DO_CATALOGO_MOTIVO:
                    resumo["ja_pendentes"] += 1
                    continue

            # Mantém o comportamento anterior do fluxo de conteúdo sensível:
            # registros não decididos podem ser reclassificados para essa fila.
            relacionado.status_auditoria = "pendente"
            status_anterior = existente.status
            existente.status = "pendente"
            existente.origem = "automatico"
            existente.motivo = motivo_destino
            existente.observacao = _anexar_observacao(
                existente.observacao, observacao_automatica
            )
            existente.decidido_por = None
            existente.decidido_em = None

            historicos.append(
                AuditoriaConteudoHistorico(
                    auditoria_id=existente.id,
                    jogo_id=relacionado.id,
                    nome_jogo=relacionado.nome,
                    status_anterior=status_anterior,
                    status_novo="pendente",
                    motivo=motivo_destino,
                    observacao=observacao_automatica,
                    usuario_id=admin.id,
                )
            )
            if status_anterior == "pendente":
                resumo["reclassificados"] += 1
            else:
                resumo["reabertos"] += 1
            continue

        nova_auditoria = AuditoriaConteudo(
            jogo_id=relacionado.id,
            nome_jogo=relacionado.nome,
            status="pendente",
            origem="automatico",
            motivo=motivo_destino,
            observacao=observacao_automatica,
            imagens=[relacionado.url_imagem_epic] if relacionado.url_imagem_epic else [],
            criado_por=admin.id,
        )
        novas_auditorias.append((relacionado, nova_auditoria, observacao_automatica))
        resumo["adicionados"] += 1

    if novas_auditorias:
        db.add_all([item[1] for item in novas_auditorias])
        db.flush()
        for relacionado, nova_auditoria, observacao_automatica in novas_auditorias:
            historicos.append(
                AuditoriaConteudoHistorico(
                    auditoria_id=nova_auditoria.id,
                    jogo_id=relacionado.id,
                    nome_jogo=relacionado.nome,
                    status_anterior=None,
                    status_novo="pendente",
                    motivo=motivo_destino,
                    observacao=observacao_automatica,
                    usuario_id=admin.id,
                )
            )

    if historicos:
        db.add_all(historicos)

    return resumo


def _decidir(
    curadoria_id: int,
    novo_status: str,
    dados: CuradoriaDecisao,
    db: Session,
    admin: Usuario,
):
    curadoria = db.query(AuditoriaConteudo).filter(AuditoriaConteudo.id == curadoria_id).first()
    if not curadoria:
        raise HTTPException(status_code=404, detail="Registro de curadoria não encontrado.")

    if curadoria.status != "pendente":
        raise HTTPException(
            status_code=409,
            detail=f"Este registro já foi decidido como '{curadoria.status}'.",
        )

    status_anterior = curadoria.status
    curadoria.status = novo_status

    if novo_status == "aprovado":
        motivo_decisao = validar_motivo_aprovacao(dados.motivo)
        if not motivo_decisao:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Selecione um motivo de aprovação válido: "
                    + ", ".join(MOTIVOS_APROVACAO)
                ),
            )
        curadoria.jogo.status_auditoria = "aprovado"
    else:
        motivo_decisao = validar_motivo_auditoria(dados.motivo)
        if not motivo_decisao:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Selecione um motivo de exclusão válido: "
                    + ", ".join(MOTIVOS_AUDITORIA)
                ),
            )
        curadoria.jogo.status_auditoria = "excluido"

    curadoria.motivo = motivo_decisao
    curadoria.observacao = dados.observacao or curadoria.observacao
    curadoria.decidido_por = admin.id
    curadoria.decidido_em = now_brasilia()

    db.add(
        AuditoriaConteudoHistorico(
            auditoria_id=curadoria.id,
            jogo_id=curadoria.jogo_id,
            nome_jogo=curadoria.jogo.nome,
            status_anterior=status_anterior,
            status_novo=novo_status,
            motivo=motivo_decisao or curadoria.motivo,
            observacao=dados.observacao,
            usuario_id=admin.id,
        )
    )

    resumo_relacionados = {
        "encontrados": 0,
        "adicionados": 0,
        "reabertos": 0,
        "reclassificados": 0,
        "ja_pendentes": 0,
        "ja_excluidos": 0,
        "ja_aprovados": 0,
    }
    if novo_status == "excluido" and motivo_decisao in {
        CONTEUDO_SENSIVEL_MOTIVO,
        FORA_DO_CATALOGO_MOTIVO,
    }:
        resumo_relacionados = _encaminhar_jogos_relacionados_para_auditoria(
            curadoria.jogo, db, admin, motivo_decisao
        )

    db.commit()
    db.refresh(curadoria)
    print(
        "Auditoria decidida: "
        f"jogos relacionados encontrados={resumo_relacionados['encontrados']}, "
        f"adicionados={resumo_relacionados['adicionados']}, "
        f"reabertos={resumo_relacionados['reabertos']}, "
        f"reclassificados={resumo_relacionados['reclassificados']}, "
        f"já pendentes={resumo_relacionados['ja_pendentes']}, "
        f"já aprovados={resumo_relacionados['ja_aprovados']}, "
        f"já excluídos={resumo_relacionados['ja_excluidos']}"
    )
    return _serializar(curadoria, resumo_relacionados)


@router.post("/{curadoria_id}/reabrir", response_model=CuradoriaResposta)
def reabrir(
    admin: AdminDep,
    curadoria_id: int,
    dados: CuradoriaDecisao,
    db: Session = Depends(get_db),
):
    """Reabre uma auditoria decidida, retornando-a ao status pendente."""
    curadoria = (
        db.query(AuditoriaConteudo)
        .filter(AuditoriaConteudo.id == curadoria_id)
        .first()
    )

    if not curadoria:
        raise HTTPException(
            status_code=404,
            detail="Registro de curadoria não encontrado.",
        )

    if curadoria.status not in {"aprovado", "excluido"}:
        raise HTTPException(
            status_code=409,
            detail=(
                "Apenas registros 'aprovado' ou 'excluido' podem ser reabertos. "
                f"Status atual: '{curadoria.status}'."
            ),
        )

    status_anterior = curadoria.status
    curadoria.status = "pendente"
    curadoria.jogo.status_auditoria = "pendente"
    curadoria.decidido_por = None
    curadoria.decidido_em = None

    motivo_reabertura = validar_motivo_auditoria(dados.motivo)
    if not motivo_reabertura:
        # Sem motivo informado, volta com o motivo com que o jogo entrou na fila
        # (a decisão sobrescreve curadoria.motivo com o motivo da aprovação/exclusão).
        motivos_anteriores = (
            db.query(AuditoriaConteudoHistorico.motivo)
            .filter(
                AuditoriaConteudoHistorico.auditoria_id == curadoria.id,
                AuditoriaConteudoHistorico.status_novo == "pendente",
            )
            .order_by(AuditoriaConteudoHistorico.id.desc())
            .all()
        )
        motivo_reabertura = next(
            (motivo for (motivo,) in motivos_anteriores if validar_motivo_auditoria(motivo)),
            None,
        )
    if motivo_reabertura:
        curadoria.motivo = motivo_reabertura
    if dados.observacao:
        curadoria.observacao = dados.observacao

    db.add(
        AuditoriaConteudoHistorico(
            auditoria_id=curadoria.id,
            jogo_id=curadoria.jogo_id,
            nome_jogo=curadoria.jogo.nome,
            status_anterior=status_anterior,
            status_novo="pendente",
            motivo=motivo_reabertura or curadoria.motivo,
            observacao=dados.observacao,
            usuario_id=admin.id,
        )
    )

    db.commit()
    db.refresh(curadoria)

    return _serializar(curadoria)


@router.post("/{curadoria_id}/aprovar", response_model=CuradoriaResposta)
def aprovar(
    admin: AdminDep,
    curadoria_id: int,
    dados: CuradoriaDecisao,
    db: Session = Depends(get_db),
):
    """Marca um jogo como aprovado na curadoria."""
    return _decidir(curadoria_id, "aprovado", dados, db, admin)


@router.post("/{curadoria_id}/excluir", response_model=CuradoriaResposta)
def excluir(
    admin: AdminDep,
    curadoria_id: int,
    dados: CuradoriaDecisao,
    db: Session = Depends(get_db),
):
    """Marca um jogo como excluído na curadoria."""
    return _decidir(curadoria_id, "excluido", dados, db, admin)


# ---------------------------------------------------------------------------
# Gerenciamento administrativo da vitrine da página inicial
# A tabela vitrine_itens já existe no banco; estas rotas não criam nem alteram
# o esquema. Todas as operações são protegidas por AdminDep.
# ---------------------------------------------------------------------------

TIPOS_VITRINE = ("jogo_brasileiro", "oportunidade", "curadoria_comunidade")
TIPOS_VITRINE_PROMOCAO = ("oportunidade", "curadoria_comunidade")
# Quantos jogos de cada seção aparecem na página inicial (igual a LIMITE_SECAO_INICIAL).
LIMITE_SECAO_INICIAL = 12


class VitrineLoteEntrada(BaseModel):
    tipo: str = Field(pattern=r"^(jogo_brasileiro|oportunidade|curadoria_comunidade)$")
    jogo_ids: list[int] = Field(min_length=1, max_length=100)


class VitrineEstudioEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=255)


class VitrineAtualizarEntrada(BaseModel):
    ativo: bool | None = None
    prioridade: int | None = Field(default=None, ge=0, le=100000)


class VitrineMoverEntrada(BaseModel):
    direcao: str = Field(pattern=r"^(cima|baixo)$")


def _ids_ordenados_vitrine(db: Session, tipo: str) -> list[int]:
    """IDs dos itens de uma seção na ordem em que aparecem na página inicial."""
    return [
        int(item_id)
        for item_id in db.execute(text("""
            SELECT id FROM vitrine_itens
            WHERE tipo = :tipo
            ORDER BY prioridade DESC, id DESC
        """), {"tipo": tipo}).scalars()
    ]


def _renumerar_vitrine(db: Session, ids: list[int]) -> None:
    """Grava a ordem informada: o primeiro da lista recebe a maior prioridade."""
    total = len(ids)
    for posicao, item_id in enumerate(ids):
        db.execute(
            text("UPDATE vitrine_itens SET prioridade = :prioridade WHERE id = :id"),
            {"prioridade": (total - posicao) * 10, "id": item_id},
        )


def _ids_visiveis(db: Session, jogo_ids: list[int]) -> set[int]:
    """Jogos que podem aparecer no catálogo público (mesma regra da página inicial)."""
    if not jogo_ids:
        return set()
    return {
        jogo_id
        for (jogo_id,) in (
            db.query(Jogo.id)
            .outerjoin(AuditoriaConteudo, AuditoriaConteudo.jogo_id == Jogo.id)
            .filter(Jogo.id.in_(jogo_ids))
            .filter(
                (AuditoriaConteudo.id.is_(None))
                | (~AuditoriaConteudo.status.in_(["pendente", "excluido"]))
            )
            .filter(_jogo_visivel_catalogo())
            .all()
        )
    }


@router.get("/vitrine")
def listar_itens_vitrine(
    _: AdminDep,
    db: Session = Depends(get_db),
    tipo: str | None = Query(default=None, pattern=r"^(jogo_brasileiro|oportunidade|curadoria_comunidade)$"),
    q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    """Lista a vitrine com a situação de cada item na página inicial.

    Antes de listar, remove os itens cuja promoção terminou comprovadamente,
    para que a lista mostre somente o que ainda pode aparecer no site.
    """
    try:
        removidos = limpar_vitrine_encerrada(db)
        if removidos:
            db.commit()

        # Todas as seções são avaliadas para o resumo; o filtro de tipo vale só para a lista.
        todos = (
            db.query(VitrineItem, Jogo)
            .join(Jogo, Jogo.id == VitrineItem.jogo_id)
            .filter(VitrineItem.tipo.in_(TIPOS_VITRINE))
            .order_by(VitrineItem.tipo.asc(), VitrineItem.prioridade.desc(), VitrineItem.id.desc())
            .all()
        )

        jogo_ids = [jogo.id for _, jogo in todos]
        visiveis = _ids_visiveis(db, jogo_ids)
        promocoes = detalhes_promocao(db, [jogo.id for item, jogo in todos if item.tipo in TIPOS_VITRINE_PROMOCAO])

        # Calcula a situação de cada item seguindo as mesmas regras da página inicial.
        exibidos_por_tipo: dict[str, int] = {}
        resumo = {t: {"total": 0, "na_pagina_inicial": 0} for t in TIPOS_VITRINE}
        itens = []
        for item, jogo in todos:
            resumo[item.tipo]["total"] += 1
            if not item.ativo:
                situacao = "pausado"
            elif jogo.id not in visiveis:
                situacao = "oculto_catalogo"
            elif item.tipo == "jogo_brasileiro" and not jogo.eh_brasileiro:
                situacao = "nao_brasileiro"
            elif item.tipo in TIPOS_VITRINE_PROMOCAO and promocoes.get(jogo.id, {}).get("estado") != "ativa":
                situacao = "aguardando_coleta"
            else:
                situacao = "exibido"
                exibidos_por_tipo[item.tipo] = exibidos_por_tipo.get(item.tipo, 0) + 1
                if exibidos_por_tipo[item.tipo] > LIMITE_SECAO_INICIAL:
                    situacao = "fila"
            if situacao == "exibido":
                resumo[item.tipo]["na_pagina_inicial"] += 1
            itens.append({
                "id": item.id,
                "tipo": item.tipo,
                "jogo_id": jogo.id,
                "jogo_nome": jogo.nome,
                "desenvolvedor": jogo.desenvolvedor,
                "imagem": jogo.url_imagem_steam or jogo.url_imagem_epic,
                "prioridade": int(item.prioridade or 0),
                "ativo": bool(item.ativo),
                "desconto": promocoes.get(jogo.id, {}).get("desconto", 0),
                "situacao": situacao,
                "criado_em": item.criado_em.isoformat() if item.criado_em else None,
            })

        if tipo:
            itens = [item for item in itens if item["tipo"] == tipo]
        condicao = _filtro_texto_jogo(q or "")
        if condicao is not None:
            ids_filtrados = {jogo_id for (jogo_id,) in db.query(Jogo.id).filter(Jogo.id.in_(jogo_ids)).filter(condicao).all()}
            itens = [item for item in itens if item["jogo_id"] in ids_filtrados]

        total = len(itens)
        inicio = (page - 1) * page_size
        return {
            "items": itens[inicio:inicio + page_size],
            "total": total,
            "page": page,
            "page_size": page_size,
            "resumo": resumo,
            "limite_pagina_inicial": LIMITE_SECAO_INICIAL,
            "removidos_encerrados": removidos,
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Não foi possível consultar a vitrine.") from exc


@router.get("/vitrine/sugestoes")
def sugerir_itens_vitrine(
    _: AdminDep,
    tipo: str = Query(pattern=r"^(jogo_brasileiro|oportunidade|curadoria_comunidade)$"),
    db: Session = Depends(get_db),
):
    """Sugere jogos para uma seção da vitrine.

    - Brasil em jogo: jogos brasileiros mais vistos.
    - Oportunidades: promoções ativas entre os jogos mais vistos, maior desconto primeiro.
    - Indicações para a comunidade: promoções ativas entre os mais vistos.
    """
    ja_cadastrados = {
        int(jogo_id)
        for jogo_id in db.execute(
            text("SELECT jogo_id FROM vitrine_itens WHERE tipo = :tipo AND jogo_id IS NOT NULL"),
            {"tipo": tipo},
        ).scalars()
    }
    consulta = (
        db.query(Jogo)
        .outerjoin(AuditoriaConteudo, AuditoriaConteudo.jogo_id == Jogo.id)
        .filter(
            (AuditoriaConteudo.id.is_(None))
            | (~AuditoriaConteudo.status.in_(["pendente", "excluido"]))
        )
        .filter(_jogo_visivel_catalogo())
    )
    descontos = {}
    if tipo == "jogo_brasileiro":
        consulta = consulta.filter(Jogo.eh_brasileiro.is_(True))
    else:
        # Parte de todos os jogos em promoção ativa (não só dos mais vistos).
        descontos = jogos_em_promocao(db)
        consulta = consulta.filter(Jogo.id.in_(list(descontos) or [0]))

    candidatos = [
        jogo
        for jogo in consulta.order_by(Jogo.visualizacoes.desc().nullslast(), Jogo.id.asc()).limit(200).all()
        if jogo.id not in ja_cadastrados
    ]
    if tipo == "oportunidade":
        # Entre os mais vistos em promoção, os maiores descontos primeiro.
        candidatos.sort(key=lambda jogo: (-descontos.get(jogo.id, 0), -(jogo.visualizacoes or 0)))
    promocoes = {jogo_id: {"desconto": desconto} for jogo_id, desconto in descontos.items()}

    return [
        {
            "id": jogo.id,
            "nome": jogo.nome,
            "desenvolvedor": jogo.desenvolvedor,
            "imagem": jogo.url_imagem_steam or jogo.url_imagem_epic,
            "desconto": promocoes.get(jogo.id, {}).get("desconto", 0),
            "visualizacoes": jogo.visualizacoes or 0,
        }
        for jogo in candidatos[:24]
    ]


@router.post("/vitrine/estudios", status_code=status.HTTP_201_CREATED)
def adicionar_estudio_brasileiro(
    entrada: VitrineEstudioEntrada,
    _: AdminDep,
    db: Session = Depends(get_db),
):
    """Cadastra um nome de estúdio/desenvolvedor brasileiro validado editorialmente."""
    nome = entrada.nome.strip()
    if len(nome) < 2:
        raise HTTPException(status_code=422, detail="Informe um nome de estúdio válido.")
    try:
        existente = db.execute(text("""
            SELECT id FROM vitrine_itens
            WHERE tipo = 'estudio_brasileiro'
              AND lower(trim(nome)) = lower(trim(:nome))
            LIMIT 1
        """), {"nome": nome}).first()
        if existente:
            raise HTTPException(status_code=409, detail="Esse estúdio já está cadastrado.")
        item_id = db.execute(text("""
            INSERT INTO vitrine_itens (tipo, nome, prioridade, ativo)
            VALUES ('estudio_brasileiro', :nome, 0, TRUE)
            RETURNING id
        """), {"nome": nome}).scalar_one()
        db.commit()
        return {"id": int(item_id), "tipo": "estudio_brasileiro", "nome": nome, "ativo": True}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Não foi possível cadastrar o estúdio.") from exc


@router.post("/vitrine/lote", status_code=status.HTTP_201_CREATED)
def adicionar_jogos_vitrine(
    entrada: VitrineLoteEntrada,
    _: AdminDep,
    db: Session = Depends(get_db),
):
    """Adiciona jogos ao fim da seção escolhida, validando as regras de cada seção."""
    ids = list(dict.fromkeys(entrada.jogo_ids))
    adicionados = []
    ignorados = []
    visiveis = _ids_visiveis(db, ids)

    try:
        ordem = _ids_ordenados_vitrine(db, entrada.tipo)
        for jogo_id in ids:
            jogo = db.query(Jogo).filter(Jogo.id == jogo_id).first()
            if not jogo:
                ignorados.append({"jogo_id": jogo_id, "motivo": "Jogo não encontrado."})
                continue
            if jogo_id not in visiveis:
                ignorados.append({"jogo_id": jogo_id, "motivo": "O jogo não aparece no catálogo público (pendente, excluído ou sem preço)."})
                continue
            if entrada.tipo == "jogo_brasileiro" and not jogo.eh_brasileiro:
                ignorados.append({"jogo_id": jogo_id, "motivo": "O jogo não está classificado como brasileiro no catálogo."})
                continue
            if entrada.tipo in TIPOS_VITRINE_PROMOCAO:
                estado = estado_promocao(db, jogo_id)
                if estado != "ativa":
                    ignorados.append({
                        "jogo_id": jogo_id,
                        "motivo": (
                            "Ainda não há confirmação de promoção ativa para este jogo."
                            if estado == "desconhecida"
                            else "O jogo não está em promoção na Steam nem na Epic."
                        ),
                    })
                    continue

            existente = db.execute(
                text("SELECT id FROM vitrine_itens WHERE tipo = :tipo AND jogo_id = :jogo_id LIMIT 1"),
                {"tipo": entrada.tipo, "jogo_id": jogo_id},
            ).first()
            if existente:
                ignorados.append({"jogo_id": jogo_id, "motivo": "O jogo já está nesta seção."})
                continue

            item_id = db.execute(text("""
                INSERT INTO vitrine_itens (tipo, jogo_id, prioridade, ativo)
                VALUES (:tipo, :jogo_id, 0, TRUE)
                RETURNING id
            """), {"tipo": entrada.tipo, "jogo_id": jogo_id}).scalar_one()
            ordem.append(int(item_id))
            adicionados.append({"id": int(item_id), "jogo_id": jogo_id, "nome": jogo.nome})

        if adicionados:
            _renumerar_vitrine(db, ordem)
        db.commit()
        return {"adicionados": adicionados, "ignorados": ignorados}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Falha ao atualizar os itens da vitrine.") from exc


@router.post("/vitrine/{item_id}/mover")
def mover_item_vitrine(
    item_id: int,
    entrada: VitrineMoverEntrada,
    _: AdminDep,
    db: Session = Depends(get_db),
):
    """Sobe ou desce um item dentro da sua seção."""
    tipo = db.execute(text("SELECT tipo FROM vitrine_itens WHERE id = :id"), {"id": item_id}).scalar()
    if not tipo:
        raise HTTPException(status_code=404, detail="Item da vitrine não encontrado.")

    ordem = _ids_ordenados_vitrine(db, tipo)
    posicao = ordem.index(item_id)
    destino = posicao - 1 if entrada.direcao == "cima" else posicao + 1
    if 0 <= destino < len(ordem):
        ordem[posicao], ordem[destino] = ordem[destino], ordem[posicao]
        _renumerar_vitrine(db, ordem)
        db.commit()
    return {"ok": True, "id": item_id, "posicao": max(0, min(destino, len(ordem) - 1)) + 1}


@router.patch("/vitrine/{item_id}")
def atualizar_item_vitrine(
    item_id: int,
    entrada: VitrineAtualizarEntrada,
    _: AdminDep,
    db: Session = Depends(get_db),
):
    atualizacoes = {campo: valor for campo, valor in entrada.model_dump(exclude_unset=True).items() if valor is not None}
    if not atualizacoes:
        raise HTTPException(status_code=422, detail="Informe ativo ou prioridade para atualizar.")

    campos = ", ".join(f"{campo} = :{campo}" for campo in atualizacoes)
    try:
        resultado = db.execute(
            text(f"UPDATE vitrine_itens SET {campos} WHERE id = :item_id"),
            {**atualizacoes, "item_id": item_id},
        )
        if resultado.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=404, detail="Item da vitrine não encontrado.")
        db.commit()
        return {"ok": True, "id": item_id, **atualizacoes}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Não foi possível atualizar o item da vitrine.") from exc


@router.delete("/vitrine/{item_id}")
def remover_item_vitrine(
    item_id: int,
    _: AdminDep,
    db: Session = Depends(get_db),
):
    try:
        resultado = db.execute(text("DELETE FROM vitrine_itens WHERE id = :item_id"), {"item_id": item_id})
        if resultado.rowcount == 0:
            db.rollback()
            raise HTTPException(status_code=404, detail="Item da vitrine não encontrado.")
        db.commit()
        return {"ok": True, "id": item_id}
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Não foi possível remover o item da vitrine.") from exc
