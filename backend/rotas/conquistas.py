"""Rotas de conquistas, progresso, XP e notificações do DESCTRL."""
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..banco_dados import get_db
from ..modelos import Conquista, Jogo, Usuario, NotificacaoUsuario
from ..seguranca.autenticacao import obter_usuario_atual

router = APIRouter(prefix="/api/conquistas", tags=["conquistas"])

CATALOGO = [
    {"codigo": "boas_vindas", "grupo": 1, "nome": "Boas-vindas ao DESCTRL", "descricao": "Visite seu perfil pela primeira vez.", "dica": "Dê uma passada no seu perfil.", "xp": 15, "meta": 1, "tipo_recompensa": "moldura", "ordem": 1},
    {"codigo": "identidade_confirmada", "grupo": 1, "nome": "Identidade confirmada", "descricao": "Confirme o endereço de e-mail da sua conta.", "dica": "Confira as opções relacionadas à sua conta.", "xp": 35, "meta": 1, "tipo_recompensa": "avatar", "ordem": 2},
    {"codigo": "tudo_em_ordem", "grupo": 1, "nome": "Tudo em ordem", "descricao": "Conclua as duas etapas anteriores.", "dica": "Algumas conquistas dependem de outras.", "xp": 50, "meta": 2, "tipo_recompensa": "capa", "ordem": 3},
    {"codigo": "primeiro_da_colecao", "grupo": 2, "nome": "Primeiro da coleção", "descricao": "Adicione um jogo aos seus favoritos.", "dica": "Comece por um jogo que você gosta.", "xp": 15, "meta": 1, "tipo_recompensa": "moldura", "ordem": 1},
    {"codigo": "colecao_em_formacao", "grupo": 2, "nome": "Coleção em formação", "descricao": "Favorite cinco jogos diferentes ao longo do tempo.", "dica": "Sua coleção pode crescer aos poucos.", "xp": 35, "meta": 5, "tipo_recompensa": "avatar", "ordem": 2},
    {"codigo": "cofre_de_jogos", "grupo": 2, "nome": "Cofre de jogos", "descricao": "Favorite vinte jogos diferentes ao longo do tempo.", "dica": "Cada jogo diferente conta uma vez.", "xp": 50, "meta": 20, "tipo_recompensa": "capa", "ordem": 3},
    {"codigo": "conhecendo_o_terreno", "grupo": 3, "nome": "Conhecendo o terreno", "descricao": "Explore a página de detalhes de um jogo enquanto estiver conectado.", "dica": "Explore as páginas dos jogos.", "xp": 15, "meta": 1, "tipo_recompensa": "moldura", "ordem": 1},
    {"codigo": "de_olho_no_mercado", "grupo": 3, "nome": "De olho no mercado", "descricao": "Consulte a página de ofertas enquanto estiver conectado.", "dica": "Confira o que está acontecendo nas ofertas.", "xp": 35, "meta": 1, "tipo_recompensa": "avatar", "ordem": 2},
    {"codigo": "cacador_de_oportunidades", "grupo": 3, "nome": "Caçador de oportunidades", "descricao": "Consulte ofertas de dez jogos diferentes.", "dica": "Observe diferentes jogos na página de ofertas.", "xp": 50, "meta": 10, "tipo_recompensa": "capa", "ordem": 3},
]
NIVEIS = [(1, 0, "Recruta"), (2, 100, "Explorador"), (3, 250, "Veterano"), (4, 450, "Especialista"), (5, 700, "Lenda")]
GRUPOS = (1, 2, 3)


def agora_brasilia() -> datetime:
    return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)


def garantir_catalogo(db: Session, usuario_id: int) -> None:
    existentes = {c.codigo for c in db.query(Conquista.codigo).filter(Conquista.usuario_id == usuario_id).all()}
    for item in CATALOGO:
        if item["codigo"] not in existentes:
            dados = {"ativado_em": agora_brasilia().isoformat()} if item["grupo"] == 1 else {}
            db.add(Conquista(usuario_id=usuario_id, **item, progresso=0, desbloqueada_em=None, dados=dados))
    db.flush()
    # Para usuários que já tinham as conquistas do grupo 1 concluídas antes desta versão.
    ativar_grupos_se_necessario(db, usuario_id)


def conquista_usuario(db: Session, usuario_id: int, codigo: str, bloquear: bool = False):
    consulta = db.query(Conquista).filter(Conquista.usuario_id == usuario_id, Conquista.codigo == codigo)
    if bloquear:
        consulta = consulta.with_for_update()
    return consulta.first()


def grupo_ativo(db: Session, usuario_id: int, grupo: int) -> bool:
    if grupo == 1:
        return True
    registro = db.query(Conquista).filter(Conquista.usuario_id == usuario_id, Conquista.grupo == grupo).first()
    return bool(registro and (registro.dados or {}).get("ativado_em"))


def enfileirar_notificacao(db: Session, usuario_id: int, conquista: Conquista) -> None:
    # O toast e o histórico permanente são canais diferentes, ambos respeitando a preferência do site.
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario or not usuario.notificacao_site:
        return
    central = conquista_usuario(db, usuario_id, "boas_vindas", bloquear=True)
    if central:
        dados = dict(central.dados or {})
        fila = list(dados.get("notificacoes_pendentes", []))
        fila.append({
            "id": str(uuid4()), "tipo": "conquista_desbloqueada",
            "codigo": conquista.codigo, "nome": conquista.nome,
            "descricao": conquista.descricao, "xp": conquista.xp,
            "criada_em": agora_brasilia().isoformat(),
        })
        dados["notificacoes_pendentes"] = fila
        central.dados = dados
    db.add(NotificacaoUsuario(
        usuario_id=usuario_id, tipo="conquista", titulo=f"Conquista desbloqueada: {conquista.nome}",
        mensagem=f"{conquista.descricao} Você recebeu {conquista.xp} XP.",
        link="/perfil?aba=conquistas", dados={"codigo": conquista.codigo, "xp": conquista.xp},
    ))


def desbloquear(db: Session, usuario_id: int, codigo: str) -> bool:
    conquista = conquista_usuario(db, usuario_id, codigo, bloquear=True)
    if not conquista or conquista.desbloqueada_em is not None:
        return False
    if not grupo_ativo(db, usuario_id, conquista.grupo):
        return False
    conquista.progresso = conquista.meta
    conquista.desbloqueada_em = agora_brasilia()
    db.flush()
    enfileirar_notificacao(db, usuario_id, conquista)
    return True


def ativar_grupos_se_necessario(db: Session, usuario_id: int) -> None:
    grupo1 = db.query(Conquista).filter(Conquista.usuario_id == usuario_id, Conquista.grupo == 1).all()
    if not grupo1 or not all(c.desbloqueada_em is not None for c in grupo1):
        return
    agora = agora_brasilia().isoformat()
    for grupo in (2, 3):
        registros = db.query(Conquista).filter(Conquista.usuario_id == usuario_id, Conquista.grupo == grupo).all()
        for registro in registros:
            dados = dict(registro.dados or {})
            if not dados.get("ativado_em"):
                # O progresso começa do zero no instante em que o grupo é liberado.
                registro.progresso = 0
                if registro.codigo == "cacador_de_oportunidades":
                    dados["jogos_consultados"] = []
                dados["ativado_em"] = agora
                registro.dados = dados


def atualizar_conquistas_conta(db: Session, usuario: Usuario) -> None:
    identidade = conquista_usuario(db, usuario.id, "identidade_confirmada")
    if usuario.email_verificado and identidade:
        desbloquear(db, usuario.id, "identidade_confirmada")
    primeira = conquista_usuario(db, usuario.id, "boas_vindas")
    identidade = conquista_usuario(db, usuario.id, "identidade_confirmada")
    if primeira and identidade and primeira.desbloqueada_em and identidade.desbloqueada_em:
        desbloquear(db, usuario.id, "tudo_em_ordem")
    ativar_grupos_se_necessario(db, usuario.id)


def serializar(db: Session, usuario: Usuario) -> dict:
    registros = db.query(Conquista).filter(Conquista.usuario_id == usuario.id).order_by(Conquista.grupo, Conquista.ordem).all()
    xp_total = sum(c.xp for c in registros if c.desbloqueada_em is not None)
    nivel_atual = NIVEIS[0]
    proximo_nivel = None
    for nivel in NIVEIS:
        if xp_total >= nivel[1]:
            nivel_atual = nivel
        elif proximo_nivel is None:
            proximo_nivel = nivel
    return {
        "xp_total": xp_total,
        "nivel": {"numero": nivel_atual[0], "titulo": nivel_atual[2], "xp_minimo": nivel_atual[1]},
        "proximo_nivel": ({"numero": proximo_nivel[0], "titulo": proximo_nivel[2], "xp_necessario": proximo_nivel[1]} if proximo_nivel else None),
        "conquistas": [
            {"codigo": c.codigo, "grupo": c.grupo, "nome": c.nome, "descricao": c.descricao, "dica": c.dica,
             "xp": c.xp, "progresso": c.progresso, "meta": c.meta, "tipo_recompensa": c.tipo_recompensa,
             "ordem": c.ordem, "desbloqueada": c.desbloqueada_em is not None,
             "grupo_ativo": grupo_ativo(db, usuario.id, c.grupo),
             "desbloqueada_em": c.desbloqueada_em.isoformat() if c.desbloqueada_em else None,
             "dados": {k: v for k, v in (c.dados or {}).items() if k not in ("notificacoes_pendentes",)} }
            for c in registros
        ]
    }


class EventoConquista(BaseModel):
    evento: str = Field(min_length=1, max_length=50)
    jogo_id: int | None = Field(default=None, gt=0)


@router.get("")
def listar_conquistas(usuario: Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    garantir_catalogo(db, usuario.id)
    atualizar_conquistas_conta(db, usuario)
    db.commit()
    return serializar(db, usuario)


@router.get("/notificacoes")
def listar_notificacoes(usuario: Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    """Lista notificações pendentes sem removê-las antes de o frontend recebê-las."""
    garantir_catalogo(db, usuario.id)
    atualizar_conquistas_conta(db, usuario)
    central = conquista_usuario(db, usuario.id, "boas_vindas", bloquear=True)
    dados = dict(central.dados or {}) if central else {}
    fila = list(dados.get("notificacoes_pendentes", []))
    db.commit()
    # Mantém a fila persistida até o frontend confirmar que exibiu cada item.
    fila.sort(key=lambda item: item.get("criada_em", ""), reverse=True)
    return {"notificacoes": fila}


@router.post("/notificacoes/{notificacao_id}/confirmar")
def confirmar_notificacao(
    notificacao_id: str,
    usuario: Usuario = Depends(obter_usuario_atual),
    db: Session = Depends(get_db),
):
    """Remove da fila somente a notificação que o frontend confirmou como exibida."""
    central = conquista_usuario(db, usuario.id, "boas_vindas", bloquear=True)
    if not central:
        db.commit()
        return {"ok": True, "removida": False}

    dados = dict(central.dados or {})
    fila = list(dados.get("notificacoes_pendentes", []))
    nova_fila = [item for item in fila if str(item.get("id")) != notificacao_id]
    removida = len(nova_fila) != len(fila)
    if removida:
        dados["notificacoes_pendentes"] = nova_fila
        central.dados = dados
    db.commit()
    return {"ok": True, "removida": removida}


@router.post("/evento")
def registrar_evento(dados: EventoConquista, usuario: Usuario = Depends(obter_usuario_atual), db: Session = Depends(get_db)):
    garantir_catalogo(db, usuario.id)
    atualizar_conquistas_conta(db, usuario)
    evento = dados.evento.strip().lower()

    if evento == "visita_perfil":
        desbloquear(db, usuario.id, "boas_vindas")
    elif evento == "detalhes_jogo":
        if dados.jogo_id is None or not db.query(Jogo.id).filter(Jogo.id == dados.jogo_id).first():
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
        desbloquear(db, usuario.id, "conhecendo_o_terreno")
    elif evento == "visita_ofertas":
        desbloquear(db, usuario.id, "de_olho_no_mercado")
    elif evento == "consulta_jogo_ofertas":
        if dados.jogo_id is None or not db.query(Jogo.id).filter(Jogo.id == dados.jogo_id).first():
            raise HTTPException(status_code=404, detail="Jogo não encontrado.")
        desbloquear(db, usuario.id, "de_olho_no_mercado")
        conquista = conquista_usuario(db, usuario.id, "cacador_de_oportunidades", bloquear=True)
        if conquista and grupo_ativo(db, usuario.id, 3) and conquista.desbloqueada_em is None:
            ids = list((conquista.dados or {}).get("jogos_consultados", []))
            if dados.jogo_id not in ids:
                ids.append(dados.jogo_id)
                conquista.dados = {**(conquista.dados or {}), "jogos_consultados": ids}
                conquista.progresso = min(len(ids), conquista.meta)
            if len(ids) >= conquista.meta:
                desbloquear(db, usuario.id, "cacador_de_oportunidades")
    else:
        raise HTTPException(status_code=400, detail="Evento de conquista desconhecido.")

    atualizar_conquistas_conta(db, usuario)
    db.commit()
    return serializar(db, usuario)
