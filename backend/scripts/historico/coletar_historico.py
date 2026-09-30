# -*- coding: utf-8 -*-
"""
Script de coleta de histórico de preços da Steam.

Este script percorre todos os jogos cadastrados, consulta seus preços
atuais na Steam e registra as variações na tabela de histórico.
"""

import sys
import os
import asyncio
from datetime import datetime
from sqlalchemy import func, and_, cast, Date
from ...coletores.steam_coletor import SteamColetor
from ...banco_dados import SessionLocal
from ...modelos import Jogo, HistoricoPreco

# Adiciona o diretório pai ao path para importar os módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _formatar_moeda(valor):
    """Formata um valor numérico em reais no padrão brasileiro."""
    if valor is None:
        return "N/A"
    return f"R$ {float(valor):.2f}".replace(".", ",")


def _parse_preco(preco_str):
    """Converte preços formatados em reais para float, aceitando pt-BR e en-US."""
    if preco_str in (None, "N/A"):
        return None

    if isinstance(preco_str, (int, float)):
        return round(float(preco_str), 2)

    valor = str(preco_str).strip()
    if not valor:
        return None

    if valor.lower() in {"grátis", "gratis", "free"}:
        return 0.0

    valor = valor.replace("R$", "").replace("BRL", "").strip()

    # Normaliza formatos como 278,40 / 278.40 / 1.299,90 / 1,299.90.
    if "," in valor and "." in valor:
        if valor.rfind(",") > valor.rfind("."):
            valor = valor.replace(".", "").replace(",", ".")
        else:
            valor = valor.replace(",", "")
    elif "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    else:
        # Ponto isolado é tratado como separador decimal.
        valor = valor.replace(" ", "")

    try:
        return round(float(valor), 2)
    except (ValueError, TypeError):
        return None


async def coletar_historico_precos():
    """
    Coleta preços/promoções da Steam em lote e salva somente mudanças reais.

    Um novo registro é criado quando muda pelo menos um dos campos de estado:
    - preço atual;
    - preço original;
    - desconto;
    - promoção (ID, nome, tipo, início ou fim).

    A simples mudança de dia/data_coleta não cria um novo registro.
    """
    print("=" * 60)
    print("COLETANDO HISTÓRICO DE PREÇOS (STEAM)")
    print("Consulta principal: IStoreBrowseService/GetItems em lote")
    print("Novo registro: mudança de estado do preço/promoção")
    print("=" * 60)
    print(f"Início: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

    db = SessionLocal()
    coletor = SteamColetor()

    try:
        jogos = (
            db.query(Jogo)
            .filter(Jogo.steam_id.isnot(None))
            .all()
        )

        print(f"\n{len(jogos)} jogos encontrados no banco")

        if not jogos:
            print(
                "Nenhum jogo encontrado. "
                "Execute o cadastro dos jogos da Steam primeiro."
            )
            return

        ids = [jogo.steam_id for jogo in jogos]
        dados_lote = await coletor.coletar_precos_lote(ids)

        alterados = 0
        erros = 0
        ignorados = 0

        for i, jogo in enumerate(jogos, 1):
            print(
                f"\n[{i}/{len(jogos)}] "
                f"Processando: {jogo.nome} "
                f"(Steam ID: {jogo.steam_id})"
            )

            try:
                dados = dados_lote.get(str(jogo.steam_id))

                # Fallback para o fluxo completo do coletor apenas quando
                # GetItems não trouxe preço, como ocorre com alguns F2P.
                if not dados or dados.get("preco") in ("N/A", None):
                    print(
                        "  GetItems não trouxe preço. "
                        "Usando fallback HTTP do coletor."
                    )
                    dados = await coletor.coletar_jogo(jogo.steam_id)

                if not dados or "erro" in dados:
                    erro = (
                        dados.get("erro", "Dados não disponíveis")
                        if dados
                        else "Dados não disponíveis"
                    )
                    print(f"  Erro: {erro}")
                    erros += 1
                    continue

                # Conversão de preço atual
                preco_str = dados.get("preco", "N/A")

                preco_num = _parse_preco(preco_str)

                if preco_num is None:
                    print(
                        "  Preço indisponível. "
                        "O histórico não será atualizado."
                    )
                    ignorados += 1
                    continue

                # Conversão de preço original
                preco_original_str = dados.get(
                    "preco_sem_desconto",
                    "N/A",
                )

                preco_original_num = _parse_preco(preco_original_str)

                if preco_original_num is None:
                    preco_original_num = preco_num

                desconto_str = dados.get("desconto", "0%")
                try:
                    desconto = (
                        int(desconto_str.replace("%", ""))
                        if desconto_str
                        else 0
                    )
                except (ValueError, AttributeError):
                    desconto = 0

                # Dados da promoção retornados pelo GetItems.
                promocao_id = dados.get("promocao_id")
                promocao_nome = dados.get("promocao_nome")
                promocao_tipo = dados.get("promocao_tipo")
                promocao_inicio = dados.get("promocao_inicio")
                promocao_fim = dados.get("promocao_fim")

                ultimo_registro = (
                    db.query(HistoricoPreco)
                    .filter(
                        and_(
                            HistoricoPreco.jogo_id == jogo.id,
                            HistoricoPreco.plataforma == "Steam",
                        )
                    )
                    .order_by(
                        HistoricoPreco.data_coleta.desc()
                    )
                    .first()
                )

                deve_criar = False
                motivos = []

                if ultimo_registro is None:
                    deve_criar = True
                    motivos.append("Primeiro registro")
                else:
                    preco_atual_float = round(float(preco_num), 2)
                    preco_anterior_float = round(
                        float(ultimo_registro.preco_atual),
                        2,
                    )

                    if abs(
                        preco_atual_float - preco_anterior_float
                    ) > 0.01:
                        deve_criar = True
                        motivos.append(
                            "Preço alterado "
                            f"(R$ {preco_anterior_float:.2f} -> "
                            f"R$ {preco_atual_float:.2f})"
                        )

                    preco_original_anterior = (
                        float(ultimo_registro.preco_sem_desconto)
                        if ultimo_registro.preco_sem_desconto is not None
                        else None
                    )

                    if (
                        preco_original_anterior is None
                        and preco_original_num is not None
                    ):
                        deve_criar = True
                        motivos.append(
                            "Preço original passou a ser informado"
                        )
                    elif (
                        preco_original_anterior is not None
                        and preco_original_num is not None
                        and abs(
                            round(preco_original_num, 2)
                            - round(preco_original_anterior, 2)
                        ) > 0.01
                    ):
                        deve_criar = True
                        motivos.append(
                            f"Preço original alterado "
                            f"({_formatar_moeda(preco_original_anterior)} -> "
                            f"{_formatar_moeda(preco_original_num)})"
                        )

                    if desconto != (ultimo_registro.desconto or 0):
                        deve_criar = True
                        motivos.append(
                            "Desconto alterado "
                            f"({ultimo_registro.desconto or 0}% -> {desconto}%)"
                        )

                    if promocao_id != ultimo_registro.promocao_id:
                        deve_criar = True
                        motivos.append("ID da promoção alterado")

                    if promocao_nome != ultimo_registro.promocao_nome:
                        deve_criar = True
                        motivos.append("Nome da promoção alterado")

                    if promocao_tipo != ultimo_registro.promocao_tipo:
                        deve_criar = True
                        motivos.append("Tipo da promoção alterado")

                    if (
                        promocao_inicio
                        != ultimo_registro.promocao_inicio
                    ):
                        deve_criar = True
                        motivos.append("Início da promoção alterado")

                    if promocao_fim != ultimo_registro.promocao_fim:
                        deve_criar = True
                        motivos.append("Fim da promoção alterado")

                if not deve_criar:
                    print(
                        f"  Nenhuma mudança de estado "
                        f"({_formatar_moeda(preco_num)}, {desconto}%, "
                        f"promoção={promocao_tipo or 'nenhuma'})"
                    )
                    ignorados += 1
                    continue

                historico = HistoricoPreco(
                    jogo_id=jogo.id,
                    nome_jogo=jogo.nome,
                    plataforma="Steam",
                    preco_atual=preco_num,
                    preco_sem_desconto=preco_original_num,
                    desconto=desconto,
                    data_coleta=datetime.now(),
                    promocao_id=promocao_id,
                    promocao_nome=promocao_nome,
                    promocao_tipo=promocao_tipo,
                    promocao_inicio=promocao_inicio,
                    promocao_fim=promocao_fim,
                )

                db.add(historico)

                print("  " + " | ".join(motivos))
                print(
                    f"  Novo registro: {_formatar_moeda(preco_num)} "
                    f"(original: {_formatar_moeda(preco_original_num)}, "
                    f"desconto de {desconto}%)"
                )

                if promocao_tipo:
                    print(
                        f"  Tipo de promoção Steam: {promocao_tipo}"
                    )

                if promocao_fim:
                    print(
                        "  Fim da promoção: "
                        f"{promocao_fim.strftime('%d/%m/%Y %H:%M UTC')}"
                    )

                alterados += 1

                if preco_original_num > 0:
                    jogo.preco_base_steam = preco_original_num
                    jogo.updated_at = datetime.now()

            except Exception as erro:
                print(f"  Erro: {erro}")
                erros += 1

        db.commit()

        print("\n" + "=" * 60)
        print("RESUMO DA COLETA")
        print("=" * 60)
        print(f"  Novos registros: {alterados}")
        print(f"  Ignorados (sem mudança): {ignorados}")
        print(f"  Erros: {erros}")
        print(f"  Total: {len(jogos)}")
        print(
            f"  Fim: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )

    except Exception as erro:
        db.rollback()
        print(f"\nErro geral: {erro}")
        import traceback
        traceback.print_exc()

    finally:
        db.close()


async def verificar_historico():
    """Verifica quantos registros de historico existem por dia."""
    db = SessionLocal()
    try:
        count = db.query(HistoricoPreco).count()
        ultimo = db.query(HistoricoPreco).order_by(HistoricoPreco.data_coleta.desc()).first()

        por_dia = db.query(
            cast(HistoricoPreco.data_coleta, Date).label("data"),
            func.count(HistoricoPreco.id).label("total")
        ).group_by("data").order_by("data").all()

        print(f"\nHISTORICO ATUAL:")
        print(f"  Total de registros: {count}")
        print(f"  Dias com registros: {len(por_dia)}")

        if ultimo:
            print(f"  Ultima coleta: {ultimo.data_coleta.strftime('%d/%m/%Y %H:%M')}")
            print(f"  Ultimo preco: R$ {ultimo.preco_atual:.2f} ({ultimo.plataforma})")

        if por_dia:
            print("\n  Registros por dia:")
            for item in por_dia[-5:]:
                print(f"    {item[0].strftime('%d/%m/%Y')}: {item[1]} registros")

    finally:
        db.close()


async def limpar_historico_duplicado():
    """
    Remove somente registros com o mesmo estado completo.

    Registros diferentes no mesmo dia são preservados, pois podem
    representar mudanças reais de preço ou promoção.
    """
    db = SessionLocal()

    try:
        print(
            "Procurando duplicatas exatas no histórico "
            "(sem apagar mudanças legítimas no mesmo dia)..."
        )

        campos_estado = [
            HistoricoPreco.jogo_id,
            HistoricoPreco.plataforma,
            HistoricoPreco.preco_atual,
            HistoricoPreco.preco_sem_desconto,
            HistoricoPreco.desconto,
            HistoricoPreco.promocao_id,
            HistoricoPreco.promocao_nome,
            HistoricoPreco.promocao_tipo,
            HistoricoPreco.promocao_inicio,
            HistoricoPreco.promocao_fim,
        ]

        duplicatas = (
            db.query(
                *campos_estado,
                func.count(HistoricoPreco.id).label("total"),
            )
            .group_by(*campos_estado)
            .having(func.count(HistoricoPreco.id) > 1)
            .all()
        )

        if not duplicatas:
            print("  Nenhuma duplicata exata encontrada.")
            return

        print(
            f"  Encontrados {len(duplicatas)} grupos de "
            "duplicatas exatas."
        )

        for dup in duplicatas:
            filtros = [
                HistoricoPreco.jogo_id == dup.jogo_id,
                HistoricoPreco.plataforma == dup.plataforma,
                HistoricoPreco.preco_atual == dup.preco_atual,
                HistoricoPreco.preco_sem_desconto == dup.preco_sem_desconto,
                HistoricoPreco.desconto == dup.desconto,
                HistoricoPreco.promocao_id == dup.promocao_id,
                HistoricoPreco.promocao_nome == dup.promocao_nome,
                HistoricoPreco.promocao_tipo == dup.promocao_tipo,
                HistoricoPreco.promocao_inicio == dup.promocao_inicio,
                HistoricoPreco.promocao_fim == dup.promocao_fim,
            ]

            registros = (
                db.query(HistoricoPreco)
                .filter(and_(*filtros))
                .order_by(HistoricoPreco.data_coleta.desc())
                .all()
            )

            for registro in registros[1:]:
                db.delete(registro)

        db.commit()
        print("  Duplicatas exatas removidas.")

    except Exception as erro:
        db.rollback()
        print(f"  Erro: {erro}")

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(coletar_historico_precos())