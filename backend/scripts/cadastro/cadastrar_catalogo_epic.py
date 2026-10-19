"""
Cadastra o catálogo normalizado da Epic Games no banco.

Este script substitui o fluxo antigo baseado em Steam -> slug -> scraper
individual. A fonte aqui é o EpicCatalogo, que já faz descoberta,
canonização, deduplicação e classificação dos jogos.

Execução, a partir da raiz do projeto:

    python -m backend.scripts.cadastro.cadastrar_catalogo_epic

Teste sem gravar:

    python -m backend.scripts.cadastro.cadastrar_catalogo_epic --limite 10 --dry-run

Teste gravando somente 10 jogos:

    python -m backend.scripts.cadastro.cadastrar_catalogo_epic --limite 10

Cadastro completo:

    python -m backend.scripts.cadastro.cadastrar_catalogo_epic
"""

from __future__ import annotations

import argparse
import unicodedata
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy.orm import Session

from ...banco_dados import SessionLocal
from ...modelos import (
    EpicCatalogo as EpicCatalogoModel,
    EpicOferta,
    Jogo,
)

from ...coletores.epic_catalogo import (
    EpicCatalogo as EpicCatalogoColetor,
)


def _converter_data(data_valor: Any):
    """
    Converte a data de lançamento do catálogo para date.

    O catálogo normalmente fornece uma data ISO. Caso a fonte forneça
    somente uma data, ela também é aceita.
    """
    if not data_valor:
        return None

    if hasattr(data_valor, "date"):
        return data_valor.date()

    texto = str(data_valor).strip()

    if not texto:
        return None

    try:
        return datetime.fromisoformat(
            texto.replace("Z", "+00:00")
        ).date()
    except ValueError:
        try:
            return datetime.strptime(
                texto[:10],
                "%Y-%m-%d",
            ).date()
        except ValueError:
            return None


def _converter_datetime(data_valor: Any):
    """Converte uma data ISO do catálogo para datetime compatível com TIMESTAMPTZ."""
    if not data_valor:
        return None

    if isinstance(data_valor, datetime):
        return data_valor

    texto = str(data_valor).strip()
    if not texto:
        return None

    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(texto[:10], "%Y-%m-%d").replace(
                tzinfo=timezone(timedelta(hours=-3))
            )
        except ValueError:
            return None


def _extrair_seller(dados: dict[str, Any]) -> tuple[str | None, str | None]:
    seller = dados.get("seller") or {}
    if not isinstance(seller, dict):
        return None, None
    return seller.get("id"), seller.get("name")


def _extrair_imagem(jogo: dict[str, Any]) -> str | None:
    """
    Escolhe uma imagem do catálogo normalizado.

    Prioridade:
        1. OfferImageWide
        2. primeira imagem que possua URL
    """
    imagens = jogo.get("imagens") or []

    if not isinstance(imagens, list):
        return None

    for imagem in imagens:
        if not isinstance(imagem, dict):
            continue

        if (
            imagem.get("type") == "OfferImageWide"
            and imagem.get("url")
        ):
            return imagem["url"]

    for imagem in imagens:
        if not isinstance(imagem, dict):
            continue

        if imagem.get("url"):
            return imagem["url"]

    return None


# Mapa atual de gêneros/subgêneros.
# A chave é normalizada sem acentos e em minúsculas.
MAPA_GENEROS = {
    "ação": "Ação",
    "ação e aventura": "Ação, Aventura",
    "action": "Ação",
    "action-adventure": "Ação, Aventura",

    "aventura": "Aventura",
    "adventure": "Aventura",

    "rpg": "RPG",
    "rpg de ação": "RPG, Ação",
    "action rpg": "RPG, Ação",
    "rpg tático": "RPG, Estratégia por Turnos",

    "estratégia": "Estratégia",
    "strategy": "Estratégia",
    "estratégia por turnos": "Estratégia por Turnos",
    "turn-based": "Estratégia por Turnos",
    "táticas baseadas em turnos": "Estratégia por Turnos",
    "tactical": "Estratégia",
    "tático": "Estratégia",
    "rts": "Estratégia",
    "4x": "4X",

    "simulação": "Simulação",
    "simulation": "Simulação",
    "simulação espacial": "Simulação Espacial",
    "space simulation": "Simulação Espacial",
    "gestão": "Gestão",
    "management": "Gestão",
    "construção de cidades": "Construção de Cidades",
    "city builder": "Construção de Cidades",
    "construção de base": "Construção de Base",
    "base-building": "Construção de Base",

    "tiro": "Tiro",
    "shooter": "Tiro",
    "fps": "Tiro",
    "third-person shooter": "Tiro",
    "third person shooter": "Tiro",
    "atirador em terceira pessoa": "Tiro",

    "sobrevivência": "Sobrevivência",
    "survival": "Sobrevivência",
    "terror de sobrevivência": "Terror de Sobrevivência",

    "terror": "Terror",
    "horror": "Terror",

    "corrida": "Corrida",
    "racing": "Corrida",
    "racing": "Corrida",

    "esportes": "Esportes",
    "futebol": "Esportes",
    "tênis": "Esportes",
    "skate": "Esportes",
    "futebol": "Esportes",
    "tênis": "Esportes",
    "skate": "Esportes",

    "plataforma": "Plataforma",
    "platformer": "Plataforma",
    "metroidvania": "Metroidvania",

    "quebra-cabeça": "Quebra-Cabeça",
    "puzzle": "Quebra-Cabeça",
    "quebra-cabeças desafiadores": "Quebra-Cabeça",
    "plataforma de quebra-cabeças": "Quebra-Cabeça",

    "casual": "Casual",

    "luta": "Luta",
    "fighting": "Luta",
    "furtivos": "Furtivo",

    "roguelite": "Roguelite",
    "rogue-lite": "Roguelite",
    "roguelike": "Roguelike",

    "jogos de festa": "Festa",
    "jogos de turnos": "Estratégia por Turnos",
    "party": "Festa",

    "jogo de cartas": "Cartas",
    "card game": "Cartas",
    "ccg": "Cartas",
    "jcc": "Cartas",

    "defesa de torre": "Defesa de Torre",
    "tower defense": "Defesa de Torre",

    "moba": "MOBA",
    "mmo": "MMO",
    "mmorpg": "MMORPG",
    "battle royale": "Battle Royale",

    "arcade": "Arcade",
    "visual novel": "Visual Novel",
    "trivia": "Trivia",
    "ritmo": "Ritmo",
    "música": "Música",

    "sandbox": "Sandbox",
    "dungeon crawler": "Dungeon Crawler",
    "souls-like": "Souls-like",
}


def normalizar(texto):
    texto = str(texto or "").strip().lower()

    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texto)
        if unicodedata.category(caractere) != "Mn"
    )


MAPA_GENEROS_NORMALIZADO = {
    normalizar(chave): valor
    for chave, valor in MAPA_GENEROS.items()
}


def obter_nome_tag(tag):
    """
    A API retorna as tags como:
    {"id": "...", "name": "..."}
    """
    if isinstance(tag, dict):
        nome = tag.get("name")
        if nome:
            return str(nome).strip()

    return None


def extrair_generos(tags):
    encontrados = []

    for tag in tags or []:
        nome_tag = obter_nome_tag(tag)

        if not nome_tag:
            continue

        chave = normalizar(nome_tag)

        if chave in MAPA_GENEROS_NORMALIZADO:
            for genero in MAPA_GENEROS_NORMALIZADO[chave].split(", "):
                if genero not in encontrados:
                    encontrados.append(genero)

    return encontrados

def _carregar_indices(db: Session) -> dict[str, dict[Any, Any]]:
    """
    Carrega previamente os registros necessários para o cadastro.

    A versão anterior consultava o PostgreSQL várias vezes para cada jogo.
    Aqui fazemos poucas consultas iniciais e depois as buscas são feitas
    em memória.
    """
    jogos = db.query(Jogo).all()
    catalogos = db.query(EpicCatalogoModel).all()
    ofertas = db.query(EpicOferta).all()

    return {
        "jogos_por_id": {
            jogo.id: jogo
            for jogo in jogos
            if jogo.id is not None
        },
        "jogos_por_epic_id": {
            jogo.epic_id: jogo
            for jogo in jogos
            if jogo.epic_id
        },
        "jogos_por_url_epic": {
            jogo.url_epic: jogo
            for jogo in jogos
            if jogo.url_epic
        },
        "catalogos_por_epic_id": {
            catalogo.epic_id: catalogo
            for catalogo in catalogos
            if catalogo.epic_id
        },
        "catalogos_por_jogo_id": {
            catalogo.jogo_id: catalogo
            for catalogo in catalogos
            if catalogo.jogo_id is not None
        },
        "ofertas_por_offer_id": {
            oferta.offer_id: oferta
            for oferta in ofertas
            if oferta.offer_id
        },
    }


def _buscar_jogo_existente_indices(
    indices: dict[str, dict[Any, Any]],
    jogo_catalogo: dict[str, Any],
) -> tuple[Jogo | None, str | None]:
    """Procura um jogo usando o epic_id baseado em pageSlug."""
    epic_id = jogo_catalogo.get("epic_id")
    url_epic = jogo_catalogo.get("url")

    if epic_id:
        catalogo = indices["catalogos_por_epic_id"].get(epic_id)
        if catalogo:
            jogo = indices["jogos_por_id"].get(catalogo.jogo_id)
            if jogo:
                return jogo, "epic_catalogo.epic_id"

        jogo = indices["jogos_por_epic_id"].get(epic_id)
        if jogo:
            return jogo, "jogos.epic_id"

    if url_epic:
        jogo = indices["jogos_por_url_epic"].get(url_epic)
        if jogo:
            return jogo, "jogos.url_epic"

    # Fallback importante: o registro da oferta continua identificando a
    # relação existente mesmo quando a identidade pública do produto muda.
    offer_id = jogo_catalogo.get("epic_offer_id")

    if offer_id:
        oferta = indices["ofertas_por_offer_id"].get(offer_id)
        if oferta:
            jogo = indices["jogos_por_id"].get(oferta.jogo_id)
            if jogo:
                return jogo, "epic_oferta.offer_id"

    return None, None


def _verificar_conflito_epic_id_indice(
    indices: dict[str, dict[Any, Any]],
    jogo: Jogo,
    epic_id: str | None,
) -> None:
    """Verifica conflito de epic_id usando o índice em memória."""
    if not epic_id:
        return

    outro = indices["jogos_por_epic_id"].get(epic_id)

    if outro and outro.id != jogo.id:
        raise RuntimeError(
            "Conflito de epic_id: "
            f"'{epic_id}' já pertence ao Jogo id={outro.id} "
            f"('{outro.nome}'), enquanto o catálogo aponta para "
            f"Jogo id={jogo.id} ('{jogo.nome}')."
        )


def _atualizar_jogo(
    jogo: Jogo,
    dados: dict[str, Any],
) -> None:
    """
    Atualiza somente os dados pertencentes à fonte Epic.

    steam_id, descricao_steam, url_steam, preco_base_steam e demais
    dados específicos da Steam não são alterados aqui.
    """
    epic_id = dados.get("epic_id")
    nome = dados.get("nome")
    url_epic = dados.get("url")

    if epic_id:
        jogo.epic_id = epic_id

    if nome:
        jogo.nome = nome

    jogo.descricao_epic = (
        dados.get("descricao_longa")
        or dados.get("descricao")
        or jogo.descricao_epic
    )

    imagem = _extrair_imagem(dados)
    if imagem:
        jogo.url_imagem_epic = imagem

    if url_epic:
        jogo.url_epic = url_epic

    if dados.get("desenvolvedor"):
        jogo.desenvolvedor = dados["desenvolvedor"]

    if dados.get("publicadora"):
        jogo.publicadora = dados["publicadora"]

    generos = extrair_generos(dados.get("tags"))
    if generos:
        jogo.genero = ", ".join(generos)

    data_lancamento = _converter_data(
        dados.get("data_lancamento")
        or dados.get("data_lancamento_pc")
    )

    if data_lancamento:
        jogo.data_lancamento = data_lancamento

    # O preço atual e o histórico serão tratados pela etapa de histórico
    # via EGDATA. Não gravamos aqui valores cuja unidade/formato da fonte
    # de catálogo não tenha sido validado para o modelo financeiro.
    jogo.updated_at = datetime.now()


def _criar_jogo(
    dados: dict[str, Any],
) -> Jogo:
    """
    Cria um novo Jogo exclusivamente a partir dos dados do catálogo Epic.
    """
    epic_id = dados.get("epic_id")
    nome = dados.get("nome")

    if not epic_id:
        raise ValueError(
            "Jogo do catálogo sem epic_id (pageSlug/productHome)."
        )

    if not nome:
        raise ValueError(
            f"Jogo '{epic_id}' sem nome."
        )

    return Jogo(
        epic_id=epic_id,
        nome=nome,
        descricao_epic=(
            dados.get("descricao_longa")
            or dados.get("descricao")
        ),
        url_imagem_epic=_extrair_imagem(dados),
        url_epic=dados.get("url"),
        desenvolvedor=dados.get("desenvolvedor"),
        publicadora=dados.get("publicadora"),
        genero=", ".join(extrair_generos(dados.get("tags"))) or None,
        data_lancamento=_converter_data(
            dados.get("data_lancamento")
            or dados.get("data_lancamento_pc")
        ),
    )


def _salvar_catalogo_epic(
    db: Session,
    jogo: Jogo,
    dados: dict[str, Any],
) -> tuple[EpicCatalogoModel, bool]:
    """Cria ou atualiza o registro específico do jogo no catálogo Epic."""
    epic_id = dados.get("epic_id")
    offer_id = dados.get("epic_offer_id")
    namespace = dados.get("epic_namespace")
    seller_id, seller_nome = _extrair_seller(dados)

    catalogo = (
        db.query(EpicCatalogoModel)
        .filter(EpicCatalogoModel.jogo_id == jogo.id)
        .first()
    )

    if catalogo is None and epic_id:
        catalogo = (
            db.query(EpicCatalogoModel)
            .filter(EpicCatalogoModel.epic_id == epic_id)
            .first()
        )
        if catalogo and catalogo.jogo_id != jogo.id:
            raise RuntimeError(
                f"Conflito de epic_id: '{epic_id}' já pertence ao "
                f"Jogo id={catalogo.jogo_id}."
            )

    criada = catalogo is None
    if criada:
        catalogo = EpicCatalogoModel(jogo_id=jogo.id)
        db.add(catalogo)

    catalogo.nome = dados.get("nome")
    catalogo.epic_id = epic_id
    catalogo.epic_offer_id = offer_id
    catalogo.epic_namespace = namespace
    catalogo.seller_id = seller_id
    catalogo.seller_nome = seller_nome
    catalogo.locale = dados.get("locale")
    catalogo.pre_purchase = bool(dados.get("pre_purchase"))
    catalogo.release_date = _converter_datetime(dados.get("data_lancamento"))
    catalogo.pc_release_date = _converter_datetime(dados.get("data_lancamento_pc") or dados.get("pc_release_date"))
    catalogo.creation_date = _converter_datetime(dados.get("creation_date"))
    catalogo.last_modified_date = _converter_datetime(dados.get("last_modified_date"))
    catalogo.categorias = dados.get("categorias") or []
    catalogo.tags = dados.get("tags") or []
    catalogo.ativo = True

    db.flush()
    return catalogo, criada


def _extrair_tipo_oferta(dados: dict[str, Any]) -> str:
    """Retorna o tipo da oferta preservando BASE_GAME, EDITION e EXPERIENCE."""
    tipo = str(dados.get("epic_offer_type") or "BASE_GAME").strip().upper()

    if tipo not in {"BASE_GAME", "EDITION", "EXPERIENCE"}:
        raise ValueError(
            f"Tipo de oferta Epic inválido: {tipo!r}. "
            """Esperado: BASE_GAME, EDITION ou EXPERIENCE."""
        )

    return tipo


def _salvar_oferta(
    db: Session,
    jogo: Jogo,
    dados: dict[str, Any],
) -> tuple[EpicOferta, bool]:
    """
    Cria ou atualiza a EpicOferta identificada por offer_id.
    Aceita BASE_GAME, EDITION e EXPERIENCE.

    sandbox_id usa o epic_namespace do catálogo, conforme validado
    anteriormente com mappings reais da Epic.
    """
    offer_id = dados.get("epic_offer_id")
    namespace = dados.get("epic_namespace")
    titulo = dados.get("nome")
    tipo = str(dados.get("epic_offer_type") or "BASE_GAME").strip().upper()

    if tipo not in {"BASE_GAME", "EDITION", "EXPERIENCE"}:
        raise ValueError(
            f"Tipo de oferta Epic inválido para '{jogo.nome}': '{tipo}'."
        )
    tipo_oferta = _extrair_tipo_oferta(dados)

    if not offer_id:
        raise ValueError(
            f"Jogo '{jogo.nome}' sem epic_offer_id."
        )

    if not namespace:
        raise ValueError(
            f"Jogo '{jogo.nome}' sem epic_namespace."
        )

    oferta = (
        db.query(EpicOferta)
        .filter(EpicOferta.offer_id == offer_id)
        .first()
    )

    criada = False

    if oferta is None:
        oferta = EpicOferta(
            jogo_id=jogo.id,
            offer_id=offer_id,
            sandbox_id=namespace,
            titulo=titulo or jogo.nome,
            tipo=tipo_oferta,
            ativo=True,
        )

        db.add(oferta)
        criada = True

    else:
        if oferta.jogo_id != jogo.id:
            raise RuntimeError(
                "Conflito de offer_id: "
                f"'{offer_id}' já pertence ao Jogo id={oferta.jogo_id}, "
                f"mas o catálogo aponta para Jogo id={jogo.id} "
                f"('{jogo.nome}')."
            )

        oferta.sandbox_id = namespace
        oferta.titulo = titulo or oferta.titulo or jogo.nome
        oferta.tipo = tipo_oferta
        oferta.ativo = True

    return oferta, criada


def cadastrar_catalogo(
    db: Session,
    jogos: list[dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, int]:
    """
    Cadastra os jogos do catálogo usando índices em memória.

    A versão anterior fazia várias consultas SQL para cada jogo. Esta versão:
      1. carrega Jogo, EpicCatalogo e EpicOferta uma única vez;
      2. encontra registros existentes em memória;
      3. prepara os Jogo;
      4. faz um flush dos novos Jogo;
      5. cria/atualiza EpicCatalogo e EpicOferta usando os índices;
      6. deixa o commit/rollback para main().
    """
    novos = 0
    atualizados = 0
    ofertas_novas = 0
    ofertas_atualizadas = 0
    catalogos_novos = 0
    catalogos_atualizados = 0

    indices = _carregar_indices(db)

    print(
        "Índices carregados: "
        f"{len(indices['jogos_por_epic_id'])} jogos por epic_id, "
        f"{len(indices['catalogos_por_epic_id'])} catálogos por epic_id, "
        f"{len(indices['ofertas_por_offer_id'])} ofertas por offer_id."
    )

    # Primeira fase: encontrar/criar/atualizar os Jogo.
    itens_processados = []

    for indice, dados in enumerate(jogos, 1):
        nome = dados.get("nome") or dados.get("epic_id") or "N/A"

        jogo, origem = _buscar_jogo_existente_indices(indices, dados)

        if jogo is None:
            jogo = _criar_jogo(dados)
            db.add(jogo)

            novos += 1
            origem = "novo"
        else:
            _verificar_conflito_epic_id_indice(
                indices,
                jogo,
                dados.get("epic_id"),
            )
            _atualizar_jogo(jogo, dados)
            atualizados += 1

        itens_processados.append((jogo, dados, origem))

        # Mantém os índices atualizados para evitar duplicação entre itens
        # da própria carga.
        epic_id = dados.get("epic_id")
        url_epic = dados.get("url")

        if epic_id:
            indices["jogos_por_epic_id"][epic_id] = jogo

        if url_epic:
            indices["jogos_por_url_epic"][url_epic] = jogo

        if indice == 1 or indice % 100 == 0 or indice == len(jogos):
            print(f"  Jogos preparados: {indice}/{len(jogos)}")

    # Um único flush para atribuir IDs aos novos Jogo antes das relações
    # que usam jogo_id.
    print("\nAplicando jogos no banco...")
    db.flush()
    print("  ✓ Jogos aplicados")

    # Segunda fase: EpicCatalogo + EpicOferta.
    for indice, (jogo, dados, origem) in enumerate(itens_processados, 1):
        epic_id = dados.get("epic_id")
        offer_id = dados.get("epic_offer_id")

        catalogo = indices["catalogos_por_jogo_id"].get(jogo.id)

        if catalogo is None and epic_id:
            catalogo = indices["catalogos_por_epic_id"].get(epic_id)

            if catalogo and catalogo.jogo_id != jogo.id:
                raise RuntimeError(
                    f"Conflito de epic_id: '{epic_id}' já pertence ao "
                    f"Jogo id={catalogo.jogo_id}."
                )

        catalogo_criado = catalogo is None

        if catalogo_criado:
            catalogo = EpicCatalogoModel(jogo_id=jogo.id)
            db.add(catalogo)
            catalogos_novos += 1
        else:
            catalogos_atualizados += 1

        catalogo.nome = dados.get("nome")
        catalogo.epic_id = epic_id
        catalogo.epic_offer_id = offer_id

        namespace = dados.get("epic_namespace")
        seller_id, seller_nome = _extrair_seller(dados)

        catalogo.epic_namespace = namespace
        catalogo.seller_id = seller_id
        catalogo.seller_nome = seller_nome
        catalogo.locale = dados.get("locale")
        catalogo.pre_purchase = bool(dados.get("pre_purchase"))
        catalogo.release_date = _converter_datetime(
            dados.get("data_lancamento")
        )
        catalogo.pc_release_date = _converter_datetime(
            dados.get("data_lancamento_pc")
            or dados.get("pc_release_date")
        )
        catalogo.creation_date = _converter_datetime(
            dados.get("creation_date")
        )
        catalogo.last_modified_date = _converter_datetime(
            dados.get("last_modified_date")
        )
        catalogo.categorias = dados.get("categorias") or []
        catalogo.tags = dados.get("tags") or []
        catalogo.ativo = True

        if catalogo_criado:
            # O objeto ainda pode não possuir ID até o flush final.
            # Os índices por epic_id/jogo_id são atualizados depois do flush.
            pass

        if not offer_id:
            raise ValueError(
                f"Jogo '{jogo.nome}' sem epic_offer_id."
            )

        if not namespace:
            raise ValueError(
                f"Jogo '{jogo.nome}' sem epic_namespace."
            )

        tipo_oferta = _extrair_tipo_oferta(dados)

        oferta = indices["ofertas_por_offer_id"].get(offer_id)

        if oferta is None:
            oferta = EpicOferta(
                jogo_id=jogo.id,
                offer_id=offer_id,
                sandbox_id=namespace,
                titulo=dados.get("nome") or jogo.nome,
                tipo=tipo_oferta,
                ativo=True,
            )
            db.add(oferta)
            ofertas_novas += 1
        else:
            if oferta.jogo_id != jogo.id:
                raise RuntimeError(
                    "Conflito de offer_id: "
                    f"'{offer_id}' já pertence ao Jogo id={oferta.jogo_id}, "
                    f"mas o catálogo aponta para Jogo id={jogo.id} "
                    f"('{jogo.nome}')."
                )

            oferta.sandbox_id = namespace
            oferta.titulo = (
                dados.get("nome")
                or oferta.titulo
                or jogo.nome
            )
            oferta.tipo = tipo_oferta
            oferta.ativo = True
            ofertas_atualizadas += 1

        # Atualiza o índice da própria carga.
        if catalogo_criado:
            if epic_id:
                indices["catalogos_por_epic_id"][epic_id] = catalogo
            indices["catalogos_por_jogo_id"][jogo.id] = catalogo

        if offer_id:
            indices["ofertas_por_offer_id"][offer_id] = oferta

        if indice == 1 or indice % 100 == 0 or indice == len(itens_processados):
            print(
                f"  Catálogo/ofertas preparados: "
                f"{indice}/{len(itens_processados)}"
            )

    # Um único flush para validar constraints e materializar IDs.
    print("\nValidando EpicCatalogo + EpicOferta no banco...")
    db.flush()
    print("  ✓ Flush final concluído")

    resultado = {
        "jogos_novos": novos,
        "jogos_atualizados": atualizados,
        "catalogos_novos": catalogos_novos,
        "catalogos_atualizados": catalogos_atualizados,
        "ofertas_novas": ofertas_novas,
        "ofertas_atualizadas": ofertas_atualizadas,
        "total_processado": len(jogos),
    }

    if dry_run:
        print("\n⚠️ MODO DRY-RUN: nenhuma alteração será mantida.")

    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cadastra o catálogo normalizado da Epic no banco."
    )

    parser.add_argument(
        "--limite",
        type=int,
        default=None,
        help="Processa os primeiros N jogos de uma coleta de teste rápido (1 página).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executa tudo, mas finaliza com ROLLBACK.",
    )

    args = parser.parse_args()

    if args.limite is not None and args.limite <= 0:
        parser.error("--limite deve ser maior que zero.")

    print("=" * 70)
    print("CADASTRO DO CATÁLOGO EPIC")
    print("=" * 70)
    print("Fonte: EpicCatalogo")
    print("Persistência: Jogo + EpicCatalogo + EpicOferta")

    db = SessionLocal()

    try:
        print("\nBuscando catálogo normalizado da Epic...")

        # Com --limite, usamos uma única página para testes rápidos.
        # O cadastro completo (sem --limite) continua coletando o catálogo inteiro.
        max_paginas_coleta = 1 if args.limite is not None else None

        if max_paginas_coleta is not None:
            print(
                "Modo de teste rápido: coleta limitada a "
                f"{max_paginas_coleta} página."
            )

        resultado_catalogo = EpicCatalogoColetor().coletar(
            max_paginas=max_paginas_coleta
        )

        jogos = resultado_catalogo.get("jogos") or []

        print(
            f"Jogos encontrados na coleta: {len(jogos)}"
        )

        if args.limite is not None:
            jogos = jogos[:args.limite]
            print(
                f"Limite solicitado: {len(jogos)}"
            )

            if len(jogos) < args.limite:
                print(
                    "⚠️ A página de teste não produziu jogos suficientes "
                    "para atingir o limite solicitado."
                )

        if not jogos:
            raise RuntimeError(
                "O catálogo não retornou nenhum jogo."
            )

        print("\nPreparando persistência...")
        resultado = cadastrar_catalogo(
            db,
            jogos,
            dry_run=args.dry_run,
        )

        print("\n" + "=" * 70)
        print("RESUMO")
        print("=" * 70)
        print(
            f"  Jogos novos       : {resultado['jogos_novos']}"
        )
        print(
            f"  Jogos atualizados : {resultado['jogos_atualizados']}"
        )
        print(
            f"  Catálogos novos   : {resultado['catalogos_novos']}"
        )
        print(
            f"  Catálogos atualizados: "
            f"{resultado['catalogos_atualizados']}"
        )
        print(
            f"  Ofertas novas     : {resultado['ofertas_novas']}"
        )
        print(
            f"  Ofertas atualizadas: "
            f"{resultado['ofertas_atualizadas']}"
        )
        print(
            f"  Total processado  : {resultado['total_processado']}"
        )

        if args.dry_run:
            db.rollback()
            print("\n✓ ROLLBACK executado. Nenhuma alteração foi gravada.")
        else:
            db.commit()
            print("\n✓ COMMIT executado. Catálogo gravado no banco.")

    except Exception as erro:
        db.rollback()
        print("\n" + "=" * 70)
        print("ERRO")
        print("=" * 70)
        print(f"{type(erro).__name__}: {erro}")
        print("\n✓ ROLLBACK executado.")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
