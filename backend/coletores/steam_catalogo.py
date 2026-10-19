import os
import json
import requests
from dotenv import load_dotenv

from backend.banco_dados import SessionLocal
from backend.modelos import Jogo, SteamCatalogo


URL = "https://api.steampowered.com/IStoreService/GetAppList/v1/"

TAMANHO_LOTE_API = 100

# Início da sincronização.
# None = começa do início do catálogo.
# Se precisar retomar manualmente uma execução interrompida, informe um
# last_appid específico aqui.
RETOMAR_LAST_APPID = None


def carregar_chave():
    load_dotenv()

    chave = os.getenv("STEAM_API_KEY") or os.getenv("STEAM_KEY")

    if not chave:
        raise RuntimeError(
            "Chave Steam não encontrada. "
            "Verifique STEAM_API_KEY ou STEAM_KEY no .env."
        )

    return chave


def buscar_catalogo_steam(chave, last_appid=None):
    input_json = {
        "include_games": True,
        "include_dlc": False,
        "include_software": False,
        "include_videos": False,
        "include_hardware": False,
        "max_results": TAMANHO_LOTE_API,
    }

    if last_appid is not None:
        input_json["last_appid"] = last_appid

    params = {
        "key": chave,
        "input_json": json.dumps(input_json, ensure_ascii=False),
    }

    resposta = requests.get(URL, params=params, timeout=30)
    resposta.raise_for_status()

    dados = resposta.json()
    return dados.get("response", {})


def processar_lote(db, apps):
    existentes = 0
    novos = 0
    catalogos_novos = 0
    catalogos_atualizados = 0
    nomes_longos = 0

    for app in apps:
        steam_id = str(app["appid"])
        nome = app.get("name") or f"Steam App {steam_id}"

        last_modified = app.get("last_modified")
        price_change_number = app.get("price_change_number")

        if len(nome) > 255:
            nomes_longos += 1

        # jogos.nome continua limitado a 255 caracteres.
        # O nome completo fica em steam_catalogo.nome, que deve ser TEXT.
        nome_jogo = nome[:255]

        jogo = (
            db.query(Jogo)
            .filter(Jogo.steam_id == steam_id)
            .first()
        )

        if jogo:
            existentes += 1
        else:
            novos += 1

            jogo = Jogo(
                steam_id=steam_id,
                nome=nome_jogo,
            )

            db.add(jogo)
            db.flush()

        catalogo = (
            db.query(SteamCatalogo)
            .filter(SteamCatalogo.steam_id == steam_id)
            .first()
        )

        if catalogo:
            catalogos_atualizados += 1
        else:
            catalogo = SteamCatalogo(
                jogo_id=jogo.id,
                steam_id=steam_id,
            )

            db.add(catalogo)
            catalogos_novos += 1

        # Mantém o nome completo retornado pela Steam.
        catalogo.nome = nome
        catalogo.last_modified = last_modified
        catalogo.price_change_number = price_change_number
        catalogo.ativo = True

    return (
        existentes,
        novos,
        catalogos_novos,
        catalogos_atualizados,
        nomes_longos,
    )


def main():
    print("=" * 70)
    print("IMPORTAÇÃO DO CATÁLOGO STEAM")
    print("=" * 70)
    if RETOMAR_LAST_APPID is None:
        print("Iniciando catálogo Steam desde o início.")
    else:
        print(f"Retomando após last_appid={RETOMAR_LAST_APPID}")

    chave = carregar_chave()

    db = SessionLocal()

    total_apps = 0
    total_existentes = 0
    total_novos = 0
    total_catalogos_novos = 0
    total_catalogos_atualizados = 0
    total_nomes_longos = 0
    paginas = 0

    last_appid = RETOMAR_LAST_APPID

    try:
        while True:
            paginas += 1

            print()
            print("-" * 70)
            print(f"Página/lote: {paginas}")
            if last_appid is None:
                print("Consultando GetAppList desde o início...")
            else:
                print(
                    f"Consultando GetAppList após last_appid={last_appid}..."
                )

            resposta = buscar_catalogo_steam(
                chave,
                last_appid=last_appid,
            )

            apps = resposta.get("apps") or []
            proximo_last_appid = resposta.get("last_appid")

            if not apps:
                print("API não retornou mais aplicativos.")
                break

            print(f"Apps recebidos: {len(apps)}")
            print(f"last_appid recebido: {proximo_last_appid}")

            (
                existentes,
                novos,
                catalogos_novos,
                catalogos_atualizados,
                nomes_longos,
            ) = processar_lote(db, apps)

            db.commit()

            total_apps += len(apps)
            total_existentes += existentes
            total_novos += novos
            total_catalogos_novos += catalogos_novos
            total_catalogos_atualizados += catalogos_atualizados
            total_nomes_longos += nomes_longos

            print(f"Jogos já existentes  : {existentes}")
            print(f"Jogos novos          : {novos}")
            print(f"Catálogos novos      : {catalogos_novos}")
            print(f"Catálogos atualizados: {catalogos_atualizados}")

            if nomes_longos:
                print(
                    f"⚠ Nomes com mais de 255 caracteres: {nomes_longos}"
                )

            print("✓ Lote gravado no banco.")

            if proximo_last_appid is None:
                print("\nAPI não informou próximo last_appid.")
                break

            if proximo_last_appid == last_appid:
                print(
                    "\nATENÇÃO: last_appid não avançou. "
                    "Importação interrompida para evitar loop."
                )
                break

            last_appid = proximo_last_appid

        print()
        print("=" * 70)
        print("IMPORTAÇÃO CONCLUÍDA")
        print("=" * 70)
        print(f"Total de apps processados       : {total_apps}")
        print(f"Jogos que já existiam           : {total_existentes}")
        print(f"Jogos novos                     : {total_novos}")
        print(f"Catálogos novos                 : {total_catalogos_novos}")
        print(f"Catálogos atualizados           : {total_catalogos_atualizados}")
        print(f"Nomes > 255 caracteres          : {total_nomes_longos}")
        print(f"Lotes processados               : {paginas}")
        print("=" * 70)

    except Exception:
        db.rollback()

        print()
        print("=" * 70)
        print("ERRO DURANTE A IMPORTAÇÃO")
        print("=" * 70)
        print(
            "O lote em andamento foi revertido. "
            "Os lotes anteriores já confirmados permanecem gravados."
        )
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
