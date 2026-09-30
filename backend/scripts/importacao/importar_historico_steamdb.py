"""
Importa o histórico de preços capturado do SteamDB
para a tabela historico_precos.

Arquivo esperado:
    steam_historico_backup_54_jogos.json

Execução:
    A partir da raiz do projeto:

    python -m backend.scripts.importacao.importar_historico_steamdb

Formato do backup do localStorage:

{
    "203160": [
        {
            "x": 1729531389000,
            "y": 49.90,
            "f": "R$ 49,90",
            "d": 75
        }
    ],
    "220200": [
        ...
    ]
}

Onde:

    x = timestamp em milissegundos
    y = preço atual
    f = preço formatado
    d = percentual de desconto
"""

import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from ...banco_dados import SessionLocal
from ...modelos import Jogo, HistoricoPreco


# ============================================================
# CONFIGURAÇÕES
# ============================================================

ARQUIVO_JSON = (
    Path(__file__).resolve().parent.parent.parent
    / "steam_historico_backup_54_jogos.json"
)

PLATAFORMA = "Steam"


# ============================================================
# CONVERSÃO DE DATA
# ============================================================

def converter_timestamp(timestamp):
    """
    Converte o timestamp do SteamDB, que vem em milissegundos,
    para datetime sem timezone.

    O modelo HistoricoPreco utiliza DateTime sem timezone.
    """

    if timestamp is None:
        return None

    try:

        data = datetime.fromtimestamp(
            float(timestamp) / 1000,
            tz=timezone.utc
        )

        # O banco utiliza DateTime sem timezone.
        data = data.replace(
            tzinfo=None
        )

        return data

    except (
        ValueError,
        TypeError,
        OverflowError
    ):

        return None


# ============================================================
# CONVERSÃO DE PREÇO
# ============================================================

def converter_preco(valor):
    """
    Converte o preço para Decimal com 2 casas decimais.
    """

    if valor is None:
        return None

    try:

        return Decimal(
            str(valor)
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    except (
        ValueError,
        TypeError
    ):

        return None


# ============================================================
# PREÇO ORIGINAL
# ============================================================

def calcular_preco_original(
    preco_atual,
    desconto
):
    """
    Calcula uma estimativa do preço original utilizando
    o preço atual e o percentual de desconto informado
    pelo SteamDB.

    Exemplo:

        R$ 74,97
        75% desconto

        -> aproximadamente R$ 299,88
    """

    if preco_atual is None:
        return None

    try:

        desconto = Decimal(
            str(desconto or 0)
        )

        if desconto <= 0:

            return preco_atual.quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP
            )

        if desconto >= 100:

            return None

        original = (
            preco_atual
            / (
                Decimal("1")
                - (
                    desconto
                    / Decimal("100")
                )
            )
        )

        return original.quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

    except (
        ValueError,
        TypeError,
        ArithmeticError
    ):

        return None


# ============================================================
# VERIFICA DUPLICIDADE
# ============================================================

def registro_ja_existe(
    db,
    jogo_id,
    data_coleta,
    preco_atual
):
    """
    Verifica se o registro já existe no banco.

    Critério:

        jogo_id
        plataforma
        data_coleta
        preco_atual
    """

    if data_coleta is None:
        return False

    existente = (
        db.query(HistoricoPreco)
        .filter(
            HistoricoPreco.jogo_id == jogo_id,

            HistoricoPreco.plataforma
            == PLATAFORMA,

            HistoricoPreco.data_coleta
            == data_coleta,

            HistoricoPreco.preco_atual
            == preco_atual,
        )
        .first()
    )

    return existente is not None


# ============================================================
# CARREGA JSON
# ============================================================

def carregar_historico():

    print()
    print(
        f"📂 Lendo arquivo:"
    )

    print(
        f"   {ARQUIVO_JSON}"
    )

    if not ARQUIVO_JSON.exists():

        raise FileNotFoundError(
            f"Arquivo não encontrado: "
            f"{ARQUIVO_JSON}"
        )

    with open(
        ARQUIVO_JSON,
        "r",
        encoding="utf-8"
    ) as arquivo:

        dados = json.load(
            arquivo
        )

    # ========================================================
    # FORMATO 1
    #
    # Caso o arquivo já tenha:
    #
    # {
    #     "historico": [...]
    # }
    # ========================================================

    if (
        isinstance(dados, dict)
        and "historico" in dados
    ):

        historico = dados.get(
            "historico",
            []
        )

        print(
            "📄 Formato detectado:"
            " histórico normalizado"
        )

        return historico


    # ========================================================
    # FORMATO 2
    #
    # Formato original do localStorage:
    #
    # {
    #     "203160": [...],
    #     "220200": [...],
    #     ...
    # }
    # ========================================================

    if not isinstance(
        dados,
        dict
    ):

        raise ValueError(
            "O JSON não possui um formato válido."
        )

    print(
        "📄 Formato detectado:"
        " localStorage do SteamDB"
    )

    historico = []

    for appid, registros in dados.items():

        if not isinstance(
            registros,
            list
        ):

            continue

        for registro in registros:

            if not isinstance(
                registro,
                dict
            ):

                continue

            # Copia para não alterar
            # o objeto original.

            item = dict(
                registro
            )

            # Adiciona o AppID que está
            # na chave do JSON.

            item["appid"] = str(
                appid
            )

            historico.append(
                item
            )

    return historico


# ============================================================
# NORMALIZA REGISTROS
# ============================================================

def normalizar_historico(
    historico
):

    normalizados = []

    ignorados = 0

    for registro in historico:

        # ====================================================
        # FORMATO ORIGINAL STEAMDB
        #
        # {
        #   "appid": "1174180",
        #   "x": 1729531389000,
        #   "y": 139.96,
        #   "d": 65
        # }
        # ====================================================

        if "x" in registro:

            timestamp = registro.get(
                "x"
            )

            preco = registro.get(
                "y"
            )

            desconto = registro.get(
                "d",
                0
            )

            appid = registro.get(
                "appid"
            )

            if (
                appid is None
                or timestamp is None
                or preco is None
            ):

                ignorados += 1

                continue

            data_coleta = (
                converter_timestamp(
                    timestamp
                )
            )

            preco_atual = (
                converter_preco(
                    preco
                )
            )

            if (
                data_coleta is None
                or preco_atual is None
            ):

                ignorados += 1

                continue

            try:

                desconto = int(
                    desconto or 0
                )

            except (
                ValueError,
                TypeError
            ):

                desconto = 0

            desconto = max(
                0,
                min(
                    100,
                    desconto
                )
            )

            normalizados.append({

                "appid": str(
                    appid
                ),

                "data_coleta":
                    data_coleta,

                "preco_atual":
                    preco_atual,

                "desconto":
                    desconto,
            })

            continue


        # ====================================================
        # FORMATO JÁ NORMALIZADO
        # ====================================================

        if (
            "data_coleta" in registro
            and "preco_atual" in registro
        ):

            try:

                appid = str(
                    registro["appid"]
                )

                data_coleta = (
                    datetime.fromisoformat(
                        str(
                            registro[
                                "data_coleta"
                            ]
                        ).replace(
                            "Z",
                            "+00:00"
                        )
                    )
                )

                if data_coleta.tzinfo:

                    data_coleta = (
                        data_coleta
                        .astimezone(
                            timezone.utc
                        )
                        .replace(
                            tzinfo=None
                        )
                    )

                preco_atual = (
                    converter_preco(
                        registro[
                            "preco_atual"
                        ]
                    )
                )

                desconto = int(
                    registro.get(
                        "percentual_desconto",
                        registro.get(
                            "desconto",
                            0
                        )
                    )
                    or 0
                )

                normalizados.append({

                    "appid": appid,

                    "data_coleta":
                        data_coleta,

                    "preco_atual":
                        preco_atual,

                    "desconto":
                        max(
                            0,
                            min(
                                100,
                                desconto
                            )
                        ),
                })

            except Exception:

                ignorados += 1

            continue


        ignorados += 1


    return (
        normalizados,
        ignorados
    )


# ============================================================
# IMPORTAÇÃO
# ============================================================

def main():

    print()
    print("=" * 70)
    print(
        "IMPORTAÇÃO DO HISTÓRICO STEAMDB"
    )
    print("=" * 70)

    # ========================================================
    # CARREGA JSON
    # ========================================================

    try:

        historico_bruto = (
            carregar_historico()
        )

    except Exception as erro:

        print()
        print(
            "❌ Erro ao carregar JSON:"
        )

        print(
            erro
        )

        return

    print()
    print(
        "📊 Registros encontrados no arquivo:"
        f" {len(historico_bruto)}"
    )

    # ========================================================
    # NORMALIZA
    # ========================================================

    (
        historico,
        ignorados_normalizacao
    ) = normalizar_historico(
        historico_bruto
    )

    print(
        "🔄 Registros válidos após conversão:"
        f" {len(historico)}"
    )

    print(
        "⚠️ Ignorados durante conversão:"
        f" {ignorados_normalizacao}"
    )

    # ========================================================
    # BANCO
    # ========================================================

    db = SessionLocal()

    importados = 0
    duplicados = 0
    ignorados = ignorados_normalizacao
    jogos_nao_encontrados = 0

    jogos_cache = {}

    jogos_nao_encontrados_ids = set()

    try:

        print()
        print(
            "🔎 Associando AppIDs aos jogos do banco..."
        )

        # ====================================================
        # PROCESSA CADA REGISTRO
        # ====================================================

        for indice, registro in enumerate(
            historico,
            1
        ):

            appid = str(
                registro["appid"]
            )

            data_coleta = (
                registro["data_coleta"]
            )

            preco_atual = (
                registro["preco_atual"]
            )

            desconto = (
                registro["desconto"]
            )

            # =================================================
            # PROCURA JOGO
            # =================================================

            if appid not in jogos_cache:

                jogo = (
                    db.query(Jogo)
                    .filter(
                        Jogo.steam_id
                        == appid
                    )
                    .first()
                )

                jogos_cache[
                    appid
                ] = jogo

            else:

                jogo = jogos_cache[
                    appid
                ]

            # =================================================
            # JOGO NÃO ENCONTRADO
            # =================================================

            if jogo is None:

                if (
                    appid
                    not in jogos_nao_encontrados_ids
                ):

                    print()
                    print(
                        "⚠️ Jogo não encontrado:"
                    )

                    print(
                        f"   Steam AppID: {appid}"
                    )

                    jogos_nao_encontrados_ids.add(
                        appid
                    )

                    jogos_nao_encontrados += 1

                continue

            # =================================================
            # PREÇO ORIGINAL
            # =================================================

            preco_sem_desconto = (
                calcular_preco_original(
                    preco_atual,
                    desconto
                )
            )

            # =================================================
            # VERIFICA DUPLICIDADE
            # =================================================

            if registro_ja_existe(
                db,
                jogo.id,
                data_coleta,
                preco_atual
            ):

                duplicados += 1

                continue

            # =================================================
            # CRIA HISTÓRICO
            # =================================================

            novo_historico = (
                HistoricoPreco(

                    jogo_id=jogo.id,

                    nome_jogo=jogo.nome,

                    plataforma=PLATAFORMA,

                    preco_atual=preco_atual,

                    preco_sem_desconto=
                        preco_sem_desconto,

                    desconto=desconto,

                    data_coleta=data_coleta,
                )
            )

            db.add(
                novo_historico
            )

            importados += 1

            # =================================================
            # PROGRESSO
            # =================================================

            if (
                importados % 100 == 0
            ):

                print(
                    f"  ➜ {importados} "
                    "registros preparados..."
                )

        # ====================================================
        # COMMIT
        # ====================================================

        print()
        print(
            "💾 Gravando no PostgreSQL..."
        )

        db.commit()

        print(
            "✅ Commit realizado!"
        )

    except Exception as erro:

        db.rollback()

        print()
        print(
            "❌ ERRO DURANTE A IMPORTAÇÃO"
        )

        print(
            f"   {type(erro).__name__}: {erro}"
        )

        print()
        print(
            "↩️ Rollback realizado."
        )

    finally:

        db.close()

    # ========================================================
    # RESULTADO
    # ========================================================

    print()
    print("=" * 70)
    print(
        "RESULTADO DA IMPORTAÇÃO"
    )
    print("=" * 70)

    print(
        f"📥 Importados:"
        f" {importados}"
    )

    print(
        f"⏭️ Já existentes:"
        f" {duplicados}"
    )

    print(
        f"⚠️ Ignorados:"
        f" {ignorados}"
    )

    print(
        f"❓ Jogos não encontrados:"
        f" {jogos_nao_encontrados}"
    )

    print(
        f"📊 Registros válidos no JSON:"
        f" {len(historico)}"
    )

    print(
        f"🎮 AppIDs encontrados no banco:"
        f" {len(jogos_cache) - len(jogos_nao_encontrados_ids)}"
    )

    print("=" * 70)


# ============================================================
# EXECUÇÃO
# ============================================================

if __name__ == "__main__":

    main()