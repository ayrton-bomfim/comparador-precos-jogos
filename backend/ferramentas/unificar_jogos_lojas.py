"""
Reconhece o mesmo jogo na Steam e na Epic e une as linhas duplicadas.

Problema: o cadastro da Epic criava um jogo novo sempre que não encontrava o
epic_id, sem tentar casar com o jogo já cadastrado pela Steam. Assim, o mesmo
jogo podia aparecer duas vezes (uma linha só-Steam e outra só-Epic), cada uma
com metade dos preços.

Como o par é encontrado:
1. Cada oferta Epic é convertida no ID de jogo do IsThereAnyDeal (ITAD).
2. O ITAD devolve os AppIDs Steam desse mesmo jogo (só "app/", não pacotes).
3. Se existe um jogo só-Steam com esse AppID e o nome bate (similaridade
   >= LIMIAR_NOME), o par é unido automaticamente. O nome é conferido porque
   o ITAD erra em títulos genéricos (ex.: ofertas chamadas só "Deluxe
   Edition" associadas à Deluxe de outro jogo).
4. Pares com nome divergente, conflitos e coincidências só de nome vão para
   um CSV de revisão manual; nada é unido sem as duas evidências.

Na união, o jogo da Steam é mantido e recebe os dados, ofertas, histórico
Epic, favoritos, alertas, auditorias e itens de vitrine do jogo da Epic, que
é removido. Cada união é registrada em mesclagens_jogos.

Também grava jogos.itad_id em todos os jogos com Epic resolvidos.

SEGURANÇA: por padrão apenas SIMULA. Para gravar, use --executar.

    python -m backend.ferramentas.unificar_jogos_lojas
    python -m backend.ferramentas.unificar_jogos_lojas --executar

Requer a migração de 2026-11-23 (python -m backend.ferramentas.migrar_banco).
"""

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from ..banco_dados import engine
from ..servicos.identidade_jogos import LIMIAR_NOME, chave_nome, similaridade
from ..servicos.itad import SHOP_EPIC, SHOP_STEAM, ids_loja_por_itad, mapear_ids_loja

ARQUIVO_REVISAO = Path(__file__).resolve().parents[2] / "logs" / "unificacao_jogos_revisar.csv"


def _carregar(conexao):
    jogos_epic = conexao.execute(text("""
        SELECT j.id, j.nome, j.epic_id, j.steam_id, o.offer_id
        FROM jogos j
        JOIN epic_ofertas o ON o.jogo_id = j.id
        WHERE j.epic_id IS NOT NULL
        ORDER BY j.id, o.id
    """)).all()
    return jogos_epic


def encontrar_pares(conexao):
    """Retorna (pares_automaticos, revisao, itad_por_jogo)."""
    linhas = _carregar(conexao)
    offers = [linha.offer_id for linha in linhas]
    print(f"Ofertas Epic: {len(offers)}")

    offer_para_itad = mapear_ids_loja(offers, SHOP_EPIC)
    itad_por_jogo = {}
    for linha in linhas:
        itad_id = offer_para_itad.get(linha.offer_id)
        if itad_id and linha.id not in itad_por_jogo:
            itad_por_jogo[linha.id] = itad_id
    print(f"Jogos com Epic resolvidos no ITAD: {len(itad_por_jogo)}")

    # Só jogos sem Steam são candidatos a duplicata.
    so_epic = {}
    for linha in linhas:
        if linha.steam_id is None and linha.id in itad_por_jogo and linha.id not in so_epic:
            so_epic[linha.id] = linha
    print(f"Jogos só-Epic resolvidos: {len(so_epic)}")

    itad_ids = sorted({itad_por_jogo[jogo_id] for jogo_id in so_epic})
    steam_por_itad = ids_loja_por_itad(itad_ids, SHOP_STEAM)
    appids = {
        item.split("/", 1)[1]
        for lista in steam_por_itad.values()
        for item in lista
        if item.startswith("app/")
    }
    jogos_steam = {
        linha.steam_id: linha
        for linha in conexao.execute(
            text("SELECT id, nome, steam_id, epic_id FROM jogos WHERE steam_id = ANY(:ids)"),
            {"ids": sorted(appids)},
        ).all()
    }

    pares, revisao = [], []
    steam_ja_usado = set()
    for jogo_id, epic in so_epic.items():
        itad_id = itad_por_jogo[jogo_id]
        apps = [i.split("/", 1)[1] for i in steam_por_itad.get(itad_id, []) if i.startswith("app/")]
        candidatos = [jogos_steam[a] for a in apps if a in jogos_steam]
        if not candidatos:
            continue

        base = {
            "itad_id": itad_id,
            "epic_jogo_id": epic.id,
            "epic_nome": epic.nome,
            "epic_id": epic.epic_id,
        }
        if len(candidatos) > 1:
            revisao.append({**base, "motivo": "ITAD aponta mais de um AppID Steam",
                            "steam_jogo_id": ";".join(str(c.id) for c in candidatos),
                            "steam_nome": " | ".join(c.nome for c in candidatos), "similaridade": ""})
            continue

        steam = candidatos[0]
        nota = similaridade(epic.nome, steam.nome)
        item = {**base, "steam_jogo_id": steam.id, "steam_nome": steam.nome,
                "steam_id": steam.steam_id, "similaridade": round(nota, 3)}

        if steam.epic_id:
            revisao.append({**item, "motivo": f"Jogo Steam já tem outra Epic ({steam.epic_id})"})
        elif steam.id in steam_ja_usado:
            revisao.append({**item, "motivo": "Outra linha Epic já foi unida a este jogo Steam"})
        elif nota < LIMIAR_NOME:
            revisao.append({**item, "motivo": "Nome diverge (possível edição ou mapeamento errado do ITAD)"})
        else:
            steam_ja_usado.add(steam.id)
            pares.append(item)

    return pares, revisao, itad_por_jogo


def coincidencias_so_de_nome(conexao, ja_tratados):
    """Pares com o mesmo nome normalizado que o ITAD não confirmou (só revisão)."""
    linhas = conexao.execute(text("""
        SELECT id, nome, steam_id, epic_id FROM jogos
        WHERE (steam_id IS NULL) <> (epic_id IS NULL)
    """)).all()
    so_steam = {}
    for linha in linhas:
        if linha.steam_id:
            so_steam.setdefault(chave_nome(linha.nome), []).append(linha)
    revisao = []
    for linha in linhas:
        if linha.epic_id and linha.id not in ja_tratados:
            iguais = so_steam.get(chave_nome(linha.nome), [])
            if iguais:
                revisao.append({
                    "itad_id": "", "epic_jogo_id": linha.id, "epic_nome": linha.nome, "epic_id": linha.epic_id,
                    "steam_jogo_id": ";".join(str(s.id) for s in iguais),
                    "steam_nome": " | ".join(s.nome for s in iguais), "steam_id": ";".join(s.steam_id for s in iguais),
                    "similaridade": 1.0,
                    "motivo": "Mesmo nome, sem confirmação do ITAD" + (" (homônimos)" if len(iguais) > 1 else ""),
                })
    return revisao


# Tabelas com chave única (usuario_id, jogo_id): move o que não conflita e
# descarta o restante (o usuário já tem o item no jogo mantido).
TABELAS_USUARIO_JOGO = ("favoritos", "historico_favoritos", "alertas_preco")


def unir(conexao, manter_id, remover_id, criterio, detalhes):
    """Une o jogo `remover_id` (só-Epic) ao `manter_id` (só-Steam)."""
    p = {"manter": manter_id, "remover": remover_id}
    removido = conexao.execute(text("SELECT * FROM jogos WHERE id = :remover FOR UPDATE"), p).mappings().one()
    mantido = conexao.execute(text("SELECT * FROM jogos WHERE id = :manter FOR UPDATE"), p).mappings().one()
    if mantido["epic_id"] or removido["steam_id"]:
        raise RuntimeError("Par deixou de ser só-Steam + só-Epic; nada foi alterado.")

    # epic_id é único: libera no removido antes de gravar no mantido.
    conexao.execute(text("UPDATE jogos SET epic_id = NULL WHERE id = :remover"), p)
    conexao.execute(text("""
        UPDATE jogos m SET
            epic_id = r.epic_id_original,
            url_epic = COALESCE(m.url_epic, r.url_epic),
            descricao_epic = COALESCE(m.descricao_epic, r.descricao_epic),
            url_imagem_epic = COALESCE(m.url_imagem_epic, r.url_imagem_epic),
            preco_base_epic = COALESCE(m.preco_base_epic, r.preco_base_epic),
            itad_id = COALESCE(m.itad_id, :itad_id),
            visualizacoes = m.visualizacoes + r.visualizacoes,
            eh_brasileiro = m.eh_brasileiro OR r.eh_brasileiro,
            status_auditoria = CASE WHEN m.status_auditoria = 'nao_avaliado'
                                    THEN r.status_auditoria ELSE m.status_auditoria END,
            updated_at = now()
        FROM (SELECT j.*, CAST(:epic_id AS VARCHAR) AS epic_id_original FROM jogos j WHERE j.id = :remover) r
        WHERE m.id = :manter
    """), {**p, "epic_id": removido["epic_id"], "itad_id": detalhes.get("itad_id")})

    movidos = {}
    for tabela in ("epic_ofertas", "historico_precos", "auditorias_conteudo_historico",
                   "notificacoes_usuario", "vitrine_itens"):
        movidos[tabela] = conexao.execute(
            text(f"UPDATE {tabela} SET jogo_id = :manter WHERE jogo_id = :remover"), p
        ).rowcount
    movidos["edicoes"] = conexao.execute(
        text("UPDATE jogos SET jogo_base_id = :manter WHERE jogo_base_id = :remover"), p).rowcount
    movidos["usuarios_recomendacao"] = conexao.execute(
        text("UPDATE usuarios SET jogo_recomendado_id = :manter WHERE jogo_recomendado_id = :remover"), p).rowcount

    # Tabelas com um registro por jogo: o mantido prevalece se já tiver.
    for tabela in ("epic_catalogo", "auditorias_conteudo"):
        movidos[tabela] = conexao.execute(text(f"""
            UPDATE {tabela} SET jogo_id = :manter
            WHERE jogo_id = :remover
              AND NOT EXISTS (SELECT 1 FROM {tabela} WHERE jogo_id = :manter)
        """), p).rowcount

    # Se a auditoria do removido ficou para trás (o mantido já tinha uma), o
    # histórico dela passa para a do mantido; senão o ON DELETE CASCADE da
    # auditoria removida apagaria esse histórico.
    movidos["auditorias_historico_religadas"] = conexao.execute(text("""
        UPDATE auditorias_conteudo_historico h SET auditoria_id = m.id
        FROM auditorias_conteudo r, auditorias_conteudo m
        WHERE r.jogo_id = :remover AND m.jogo_id = :manter AND h.auditoria_id = r.id
    """), p).rowcount

    for tabela in TABELAS_USUARIO_JOGO:
        movidos[tabela] = conexao.execute(text(f"""
            UPDATE {tabela} t SET jogo_id = :manter
            WHERE t.jogo_id = :remover
              AND NOT EXISTS (SELECT 1 FROM {tabela} o WHERE o.jogo_id = :manter AND o.usuario_id = t.usuario_id)
        """), p).rowcount

    # O que sobrou (duplicado no mantido) cai pelo ON DELETE CASCADE.
    conexao.execute(text("DELETE FROM jogos WHERE id = :remover"), p)

    conexao.execute(text("""
        INSERT INTO mesclagens_jogos
            (jogo_mantido_id, jogo_removido_id, nome_mantido, nome_removido,
             steam_id, epic_id, itad_id, criterio, detalhes)
        VALUES (:manter, :remover, :nome_mantido, :nome_removido,
                :steam_id, :epic_id, :itad_id, :criterio, CAST(:detalhes AS JSONB))
    """), {
        **p,
        "nome_mantido": mantido["nome"], "nome_removido": removido["nome"],
        "steam_id": mantido["steam_id"], "epic_id": removido["epic_id"],
        "itad_id": detalhes.get("itad_id"), "criterio": criterio,
        "detalhes": json.dumps({**detalhes, "movidos": movidos}, ensure_ascii=False, default=str),
    })
    return movidos


def gravar_revisao(revisao):
    ARQUIVO_REVISAO.parent.mkdir(parents=True, exist_ok=True)
    campos = ["motivo", "similaridade", "epic_jogo_id", "epic_nome", "epic_id",
              "steam_jogo_id", "steam_nome", "steam_id", "itad_id"]
    with ARQUIVO_REVISAO.open("w", newline="", encoding="utf-8-sig") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=campos, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(revisao)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--executar", action="store_true", help="grava as uniões (sem isto, só simula)")
    parser.add_argument("--limite", type=int, default=None, help="une no máximo N pares")
    args = parser.parse_args()

    inicio = datetime.now()
    with engine.connect() as conexao:
        banco = conexao.execute(text("SELECT current_database()")).scalar()
        print(f"Banco: {banco} | modo: {'EXECUÇÃO' if args.executar else 'SIMULAÇÃO'}")
        pares, revisao, itad_por_jogo = encontrar_pares(conexao)
        tratados = {p["epic_jogo_id"] for p in pares} | {r["epic_jogo_id"] for r in revisao}
        revisao += coincidencias_so_de_nome(conexao, tratados)

    if args.limite is not None:
        pares = pares[:args.limite]

    print(f"\nPares confirmados (ITAD + nome): {len(pares)}")
    for par in pares[:20]:
        print(f"  [{par['similaridade']:.2f}] Epic {par['epic_jogo_id']} '{par['epic_nome']}' "
              f"-> Steam {par['steam_jogo_id']} '{par['steam_nome']}' ({par['steam_id']})")
    if len(pares) > 20:
        print(f"  ... e mais {len(pares) - 20}")

    gravar_revisao(revisao)
    motivos = {}
    for item in revisao:
        chave = item["motivo"].split(" (")[0]
        motivos[chave] = motivos.get(chave, 0) + 1
    print(f"\nPara revisão manual: {len(revisao)} -> {ARQUIVO_REVISAO}")
    for motivo, quantidade in sorted(motivos.items(), key=lambda x: -x[1]):
        print(f"  {motivo}: {quantidade}")

    if not args.executar:
        print("\nSIMULAÇÃO: nada foi gravado. Use --executar para aplicar.")
        return

    with engine.begin() as conexao:
        atualizados = 0
        for jogo_id, itad_id in itad_por_jogo.items():
            atualizados += conexao.execute(
                text("UPDATE jogos SET itad_id = :itad WHERE id = :id AND itad_id IS DISTINCT FROM :itad"),
                {"itad": itad_id, "id": jogo_id},
            ).rowcount
    print(f"\nitad_id gravado/atualizado em {atualizados} jogos.")

    unidos = falhas = 0
    for par in pares:
        try:
            with engine.begin() as conexao:
                unir(conexao, par["steam_jogo_id"], par["epic_jogo_id"], "itad+nome", par)
            unidos += 1
        except Exception as erro:
            falhas += 1
            print(f"  Falha ao unir Epic {par['epic_jogo_id']} -> Steam {par['steam_jogo_id']}: {erro}")

    with engine.begin() as conexao:
        conexao.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY precos_atuais"))

    print(f"\nUnidos: {unidos} | falhas: {falhas} | duração: {datetime.now() - inicio}")


if __name__ == "__main__":
    main()
