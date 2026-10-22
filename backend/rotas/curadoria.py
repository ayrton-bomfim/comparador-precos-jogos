"""Rotas administrativas para curadoria e auditoria editorial do catálogo."""

from datetime import datetime, timezone, timedelta
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
    now_brasilia,
)
from ..seguranca.autenticacao import obter_admin_atual


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


def _vitrine_status_promocao(db: Session, jogo_id: int, agora=None) -> str:
    """Retorna ativa/inativa/desconhecida sem tratar dados antigos como confirmação.

    Um registro com promoção futura confirma atividade. Para registros sem data
    final ou sem desconto, exige coleta recente; dados antigos ficam como
    desconhecidos para evitar exclusões causadas por falhas temporárias.
    """
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

    if desconhecida:
        return "desconhecida"
    return "inativa"


@router.get("/buscar", response_model=list[dict])
def buscar_jogos_para_curadoria(
    _: AdminDep,
    termo: str = Query(min_length=2, max_length=100),
    db: Session = Depends(get_db),
):
    """Busca jogos por nome, desenvolvedora, publicadora ou identificador."""
    termo_limpo = termo.strip()
    termo_like = f"%{termo_limpo}%"

    jogos = (
        db.query(Jogo)
        .filter(
            or_(
                Jogo.nome.ilike(termo_like),
                Jogo.epic_id.ilike(termo_like),
                cast(Jogo.steam_id, String).ilike(termo_like),
                Jogo.desenvolvedor.ilike(termo_like),
                Jogo.publicadora.ilike(termo_like),
            )
        )
        .order_by(Jogo.nome.asc())
        .limit(30)
        .all()
    )

    resultados = []
    for jogo in jogos:
        resultados.append({
            "id": jogo.id,
            "nome": jogo.nome,
            "epic_id": jogo.epic_id,
            "steam_id": jogo.steam_id,
            "url_epic": jogo.url_epic,
            "imagem_epic": jogo.url_imagem_epic or jogo.url_imagem_steam,
            "desenvolvedor": jogo.desenvolvedor,
            "publicadora": jogo.publicadora,
            "eh_brasileiro": bool(getattr(jogo, "eh_brasileiro", False)),
            "promocao_ativa": _vitrine_status_promocao(db, jogo.id) == "ativa",
        })
    return resultados



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

    termo = (q or "").strip()
    if termo:
        padrao = f"%{termo}%"
        consulta = consulta.filter(
            or_(
                Jogo.nome.ilike(padrao),
                cast(Jogo.epic_id, String).ilike(padrao),
                cast(Jogo.steam_id, String).ilike(padrao),
                AuditoriaConteudo.observacao.ilike(padrao),
            )
        )

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


@router.get("/pendentes", response_model=list[CuradoriaResposta] | CuradoriaPaginaResposta)
def listar_pendentes(
    _: AdminDep,
    db: Session = Depends(get_db),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
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
    if termo:
        termo_like = f"%{termo}%"
        consulta = consulta.filter(or_(
            Jogo.nome.ilike(termo_like),
            Jogo.epic_id.ilike(termo_like),
            cast(Jogo.steam_id, String).ilike(termo_like),
            Jogo.desenvolvedor.ilike(termo_like),
            Jogo.publicadora.ilike(termo_like),
            AuditoriaConteudo.observacao.ilike(termo_like),
        ))

    paginacao_solicitada = page is not None or page_size is not None or bool(motivo) or bool(termo)
    if not paginacao_solicitada:
        registros = consulta.order_by(AuditoriaConteudo.criado_em.asc()).all()
        return [_serializar(item) for item in registros]

    pagina = page or 1
    tamanho = page_size or 50
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


@router.get("/status/{status_filtro}", response_model=list[CuradoriaResposta] | CuradoriaPaginaResposta)
def listar_por_status(
    _: AdminDep,
    status_filtro: str,
    db: Session = Depends(get_db),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
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
    if termo:
        termo_like = f"%{termo}%"
        consulta = consulta.filter(or_(
            Jogo.nome.ilike(termo_like),
            Jogo.epic_id.ilike(termo_like),
            cast(Jogo.steam_id, String).ilike(termo_like),
            Jogo.desenvolvedor.ilike(termo_like),
            Jogo.publicadora.ilike(termo_like),
            AuditoriaConteudo.observacao.ilike(termo_like),
        ))

    paginacao_solicitada = page is not None or page_size is not None or bool(motivo) or bool(termo)
    ordenacao = (AuditoriaConteudo.decidido_em.desc(), AuditoriaConteudo.id.desc())
    if not paginacao_solicitada:
        registros = consulta.order_by(*ordenacao).all()
        return [_serializar(item) for item in registros]

    pagina = page or 1
    tamanho = page_size or 50
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

class VitrineLoteEntrada(BaseModel):
    tipo: str = Field(pattern=r"^(jogo_brasileiro|oportunidade)$")
    jogo_ids: list[int] = Field(min_length=1, max_length=100)


class VitrineEstudioEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=255)


class VitrineAtualizarEntrada(BaseModel):
    ativo: bool | None = None
    prioridade: int | None = Field(default=None, ge=0, le=100000)


def _vitrine_item_dict(row):
    return {
        "id": int(row["id"]),
        "tipo": row["tipo"],
        "nome": row["nome"],
        "jogo_id": int(row["jogo_id"]) if row["jogo_id"] is not None else None,
        "jogo_nome": row["jogo_nome"],
        "desenvolvedor": row["desenvolvedor"],
        "imagem": row["imagem"],
        "prioridade": int(row["prioridade"] or 0),
        "ativo": bool(row["ativo"]),
        "inicio_em": row["inicio_em"].isoformat() if row["inicio_em"] else None,
        "fim_em": row["fim_em"].isoformat() if row["fim_em"] else None,
        "criado_em": row["criado_em"].isoformat() if row["criado_em"] else None,
    }


@router.get("/vitrine")
def listar_itens_vitrine(
    _: AdminDep,
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    q: str | None = Query(default=None, max_length=200),
):
    """Lista itens da vitrine com busca e paginação aplicadas no banco."""
    try:
        filtros = "WHERE vi.tipo IN ('jogo_brasileiro', 'oportunidade')"
        parametros: dict[str, object] = {}
        termo = (q or '').strip()
        if termo:
            filtros += " AND (vi.nome ILIKE :termo OR j.nome ILIKE :termo OR j.desenvolvedor ILIKE :termo)"
            parametros['termo'] = f"%{termo}%"

        total = db.execute(text(f"""
            SELECT COUNT(*)
            FROM vitrine_itens vi
            LEFT JOIN jogos j ON j.id = vi.jogo_id
            {filtros}
        """), parametros).scalar() or 0

        consulta_parametros = {**parametros, 'limite': page_size, 'offset': (page - 1) * page_size}
        rows = db.execute(text(f"""
            SELECT vi.id, vi.tipo, vi.nome, vi.jogo_id, j.nome AS jogo_nome,
                   j.desenvolvedor, COALESCE(j.url_imagem_epic, j.url_imagem_steam) AS imagem,
                   vi.prioridade, vi.ativo, vi.inicio_em, vi.fim_em, vi.criado_em
            FROM vitrine_itens vi
            LEFT JOIN jogos j ON j.id = vi.jogo_id
            {filtros}
            ORDER BY vi.tipo ASC, vi.prioridade DESC, vi.id DESC
            LIMIT :limite OFFSET :offset
        """), consulta_parametros).mappings().all()
        return {
            'items': [_vitrine_item_dict(row) for row in rows],
            'total': int(total),
            'page': page,
            'page_size': page_size,
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Não foi possível consultar a tabela vitrine_itens.") from exc


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
    """Adiciona jogos à seção selecionada, evitando duplicatas."""
    ids = list(dict.fromkeys(entrada.jogo_ids))
    agora = datetime.now().astimezone()
    adicionados = []
    ignorados = []

    try:
        for jogo_id in ids:
            jogo = db.execute(text("""
                SELECT id, nome, desenvolvedor, eh_brasileiro
                FROM jogos
                WHERE id = :jogo_id
            """), {"jogo_id": jogo_id}).mappings().first()
            if not jogo:
                ignorados.append({"jogo_id": jogo_id, "motivo": "Jogo não encontrado."})
                continue

            if entrada.tipo == "jogo_brasileiro" and not bool(jogo["eh_brasileiro"]):
                ignorados.append({"jogo_id": jogo_id, "motivo": "Este jogo não está classificado como brasileiro no catálogo."})
                continue

            if entrada.tipo == "oportunidade":
                estado_promocao = _vitrine_status_promocao(db, jogo_id)
                if estado_promocao != "ativa":
                    motivo = (
                        "Não há confirmação recente de promoção ativa para este jogo."
                        if estado_promocao == "desconhecida"
                        else "O jogo não possui promoção ativa na Steam ou na Epic."
                    )
                    ignorados.append({"jogo_id": jogo_id, "motivo": motivo})
                    continue

            existente = db.execute(text("""
                SELECT id
                FROM vitrine_itens
                WHERE tipo = :tipo AND jogo_id = :jogo_id
                LIMIT 1
            """), {"tipo": entrada.tipo, "jogo_id": jogo_id}).first()
            if existente:
                ignorados.append({"jogo_id": jogo_id, "motivo": "O jogo já está cadastrado nessa seção."})
                continue

            inserido = db.execute(text("""
                INSERT INTO vitrine_itens (tipo, jogo_id, prioridade, ativo)
                VALUES (:tipo, :jogo_id, 0, TRUE)
                RETURNING id
            """), {"tipo": entrada.tipo, "jogo_id": jogo_id}).scalar_one()
            adicionados.append({"id": int(inserido), "jogo_id": jogo_id, "nome": jogo["nome"]})

        db.commit()
        return {"adicionados": adicionados, "ignorados": ignorados}
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Falha ao atualizar os itens da vitrine.") from exc


@router.patch("/vitrine/{item_id}")
def atualizar_item_vitrine(
    item_id: int,
    entrada: VitrineAtualizarEntrada,
    _: AdminDep,
    db: Session = Depends(get_db),
):
    atualizacoes = entrada.model_dump(exclude_unset=True)
    if not atualizacoes:
        raise HTTPException(status_code=422, detail="Informe ativo ou prioridade para atualizar.")
    if "prioridade" in atualizacoes and atualizacoes["prioridade"] is None:
        atualizacoes.pop("prioridade")
    if "ativo" in atualizacoes and atualizacoes["ativo"] is None:
        atualizacoes.pop("ativo")
    if not atualizacoes:
        raise HTTPException(status_code=422, detail="Nenhum campo válido informado.")

    campos = []
    parametros = {"item_id": item_id}
    for campo, valor in atualizacoes.items():
        campos.append(f"{campo} = :{campo}")
        parametros[campo] = valor
    try:
        resultado = db.execute(text(
            f"UPDATE vitrine_itens SET {', '.join(campos)} WHERE id = :item_id"
        ), parametros)
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
        resultado = db.execute(
            text("DELETE FROM vitrine_itens WHERE id = :item_id"),
            {"item_id": item_id},
        )
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
