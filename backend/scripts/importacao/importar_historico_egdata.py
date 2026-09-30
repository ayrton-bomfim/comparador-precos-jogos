"""
Importa o histórico de preços da EGDATA para o histórico da aplicação.

Execução:
    A partir da raiz do projeto:

    python -m backend.scripts.importacao.importar_historico_egdata

O script:
    1. Busca todos os jogos que possuem uma oferta Epic ativa.
    2. Consulta o histórico de preços da oferta na EGDATA.
    3. Converte os valores de centavos para reais.
    4. Calcula o percentual efetivo de desconto.
    5. Insere os registros na tabela historico_precos.
    6. Ignora registros que já existem.
    7. Continua para o próximo jogo caso um jogo apresente erro.
"""

from datetime import datetime, timezone

import requests

from ...banco_dados import SessionLocal
from ...modelos import Jogo, EpicOferta, HistoricoPreco


EGDATA_URL = "https://api.egdata.app/offers/{offer_id}/price-history"


def calcular_desconto(original, atual):
    """Calcula o percentual efetivo de desconto."""
    if original is None or atual is None or original <= 0:
        return 0

    desconto = round(((original - atual) / original) * 100)

    return max(0, min(100, desconto))


def converter_preco(valor):
    """Converte centavos da EGDATA para reais."""
    if valor is None:
        return None

    return round(valor / 100, 2)


def converter_data(data_iso):
    """
    Converte a data ISO da EGDATA para datetime.

    O banco utiliza DateTime sem timezone, portanto
    a informação de timezone é removida após a conversão.
    """
    if not data_iso:
        return None

    try:
        data = datetime.fromisoformat(
            data_iso.replace("Z", "+00:00")
        )

        if data.tzinfo is not None:
            data = data.astimezone(timezone.utc).replace(
                tzinfo=None
            )

        return data

    except (ValueError, TypeError):
        return None


def buscar_historico_egdata(offer_id):
    """Consulta o histórico de preços de uma oferta na EGDATA."""
    url = EGDATA_URL.format(offer_id=offer_id)

    resposta = requests.get(
        url,
        params={"country": "BR"},
        timeout=30,
    )

    resposta.raise_for_status()

    dados = resposta.json()

    if not isinstance(dados, list):
        raise ValueError(
            "A resposta da EGDATA não veio como lista."
        )

    return dados


def registro_ja_existe(
    db,
    jogo_id,
    data_coleta,
    preco_atual,
):
    """
    Verifica se o mesmo registro histórico já existe.

    A combinação considerada é:
        jogo + plataforma + data + preço atual
    """
    if data_coleta is None:
        return False

    existente = (
        db.query(HistoricoPreco)
        .filter(
            HistoricoPreco.jogo_id == jogo_id,
            HistoricoPreco.plataforma == "Epic",
            HistoricoPreco.data_coleta == data_coleta,
            HistoricoPreco.preco_atual == preco_atual,
        )
        .first()
    )

    return existente is not None


def importar_historico_jogo(db, jogo, oferta):
    """
    Importa o histórico de uma única oferta Epic.
    """

    print()
    print("=" * 70)
    print(f"JOGO: {jogo.nome}")
    print(f"JOGO ID: {jogo.id}")
    print(f"OFFER ID: {oferta.offer_id}")
    print("=" * 70)

    dados = buscar_historico_egdata(
        oferta.offer_id
    )

    # A EGDATA pode retornar os registros fora de ordem.
    dados = sorted(
        dados,
        key=lambda registro: registro.get("updatedAt") or ""
    )

    print(
        f"Registros recebidos da EGDATA: {len(dados)}"
    )

    importados = 0
    duplicados = 0
    ignorados = 0

    for registro in dados:
        preco = registro.get("price") or {}

        original_centavos = preco.get(
            "originalPrice"
        )

        atual_centavos = preco.get(
            "discountPrice"
        )

        # Sem preço original, não conseguimos
        # montar corretamente o registro.
        if original_centavos is None:
            ignorados += 1
            continue

        # Se não houver preço promocional,
        # significa que o jogo está pelo preço original.
        if atual_centavos is None:
            atual_centavos = original_centavos

        preco_original = converter_preco(
            original_centavos
        )

        preco_atual = converter_preco(
            atual_centavos
        )

        data_coleta = converter_data(
            registro.get("updatedAt")
        )

        if preco_atual is None or data_coleta is None:
            ignorados += 1
            continue

        desconto = calcular_desconto(
            preco_original,
            preco_atual,
        )

        # Evita inserir o mesmo registro novamente.
        if registro_ja_existe(
            db,
            jogo.id,
            data_coleta,
            preco_atual,
        ):
            duplicados += 1
            continue

        historico = HistoricoPreco(
            jogo_id=jogo.id,
            nome_jogo=jogo.nome,
            plataforma="Epic",
            preco_atual=preco_atual,
            preco_sem_desconto=preco_original,
            desconto=desconto,
            data_coleta=data_coleta,
        )

        db.add(historico)

        importados += 1

        print(
            f"  + {data_coleta.strftime('%d/%m/%Y %H:%M:%S')} | "
            f"R$ {preco_atual:.2f} | "
            f"original R$ {preco_original:.2f} | "
            f"{desconto}%"
        )

    db.commit()

    print()
    print("RESULTADO")
    print(f"  Importados: {importados}")
    print(f"  Já existentes: {duplicados}")
    print(f"  Ignorados: {ignorados}")

    return {
        "importados": importados,
        "duplicados": duplicados,
        "ignorados": ignorados,
    }


def buscar_jogos_com_oferta_epic(db):
    """
    Busca jogos que possuem uma oferta Epic ativa.

    O join é feito através de EpicOferta.jogo_id.
    """

    resultados = (
        db.query(Jogo, EpicOferta)
        .join(
            EpicOferta,
            EpicOferta.jogo_id == Jogo.id,
        )
        .filter(
            EpicOferta.ativo.is_(True),
            Jogo.epic_id.isnot(None),
        )
        .all()
    )

    return resultados


def main():
    db = SessionLocal()

    total_jogos = 0
    total_importados = 0
    total_duplicados = 0
    total_ignorados = 0
    total_erros = 0

    try:
        print("=" * 70)
        print("IMPORTADOR DE HISTÓRICO — EGDATA")
        print("=" * 70)
        print()

        jogos_ofertas = buscar_jogos_com_oferta_epic(
            db
        )

        if not jogos_ofertas:
            print(
                "Nenhum jogo com oferta Epic ativa foi encontrado."
            )
            return

        print(
            f"Jogos encontrados: {len(jogos_ofertas)}"
        )

        for jogo, oferta in jogos_ofertas:

            total_jogos += 1

            try:
                resultado = importar_historico_jogo(
                    db,
                    jogo,
                    oferta,
                )

                total_importados += resultado[
                    "importados"
                ]

                total_duplicados += resultado[
                    "duplicados"
                ]

                total_ignorados += resultado[
                    "ignorados"
                ]

            except requests.RequestException as erro:
                db.rollback()

                total_erros += 1

                print()
                print(
                    f"ERRO AO CONSULTAR EGDATA — "
                    f"{jogo.nome}"
                )
                print(erro)

            except Exception as erro:
                db.rollback()

                total_erros += 1

                print()
                print(
                    f"ERRO AO IMPORTAR — "
                    f"{jogo.nome}"
                )
                print(erro)

        print()
        print("=" * 70)
        print("RESUMO FINAL")
        print("=" * 70)
        print(
            f"Jogos processados: {total_jogos}"
        )
        print(
            f"Registros importados: {total_importados}"
        )
        print(
            f"Registros já existentes: {total_duplicados}"
        )
        print(
            f"Registros ignorados: {total_ignorados}"
        )
        print(
            f"Jogos com erro: {total_erros}"
        )
        print("=" * 70)

    except Exception as erro:
        db.rollback()

        print()
        print("=" * 70)
        print("ERRO GERAL")
        print("=" * 70)
        print(erro)

    finally:
        db.close()


if __name__ == "__main__":
    main()