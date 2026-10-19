"""
Módulo de coleta de dados da Steam.

Utiliza a API oficial da Steam como fonte principal,
com fallback para scraping direto quando necessário.
"""

import asyncio
import json
import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import quote

from .coletor_base import ColetorBase
from ..lista_jogos import JOGOS_STEAM


# Número de lotes GetItems processados simultaneamente.
# Valor inicial conservador para o teste de concorrência.
GETITEMS_WORKERS = 4


class SteamColetor(ColetorBase):

    def __init__(self):
        super().__init__()
        self.timeout = 30000
        self.url_base = "https://store.steampowered.com"
        self.api_base = "https://store.steampowered.com/api"
        self.store_browse_api = (
            "https://api.steampowered.com/"
            "IStoreBrowseService/GetItems/v1/"
        )
        self.contexto_store = {
            "language": "brazilian",
            "country_code": "BR",
            "steam_realm": 1,
        }
        self.data_request_store = {
            "include_basic_info": True,
            "include_release": True,
            "include_all_purchase_options": True,
        }
        self.batch_size_store = 50
        self._cache_precos = {}

    def _limpar_descricao(self, texto):
        """Remove tags HTML e limpa a descrição."""
        if not texto:
            return "N/A"

        texto = re.sub(r"<[^>]+>", "", texto)
        texto = re.sub(r"&[a-zA-Z]+;", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip()

        return texto if texto else "N/A"

    def _formatar_preco(self, valor):
        """Formata preços que já estão em REAIS ou vêm do scraping."""

        if valor is None:
            return "N/A"

        if isinstance(valor, (int, float)):
            if valor == 0:
                return "Grátis"
            return f"R$ {float(valor):.2f}".replace(".", ",")

        if isinstance(valor, str):
            valor = valor.strip()

            if not valor:
                return "N/A"

            if any(
                termo in valor.lower()
                for termo in ["grátis", "gratis", "free"]
            ):
                return "Grátis"

            match = re.search(r"[\d,.]+", valor)
            if match:
                numero = match.group()

                try:
                    if "," in numero:
                        # Ex.: 18,49 / 1.299,90
                        numero = numero.replace(".", "").replace(",", ".")
                    elif "." in numero:
                        # Ex.: 18.49 / 1299.90
                        numero = numero.replace(",", "")

                    return f"R$ {float(numero):.2f}".replace(".", ",")
                except ValueError:
                    pass

            return valor

        return "N/A"

    def _formatar_centavos(self, valor):
        """Converte um valor em centavos da Steam para reais formatados."""

        if valor is None or valor == "":
            return "N/A"

        try:
            centavos = int(str(valor))
        except (TypeError, ValueError):
            return "N/A"

        if centavos == 0:
            return "Grátis"

        return f"R$ {centavos / 100:.2f}".replace(".", ",")

    def _timestamp_para_datetime(self, valor):
        """Converte timestamp Unix para datetime com fuso UTC."""
        if valor is None:
            return None

        try:
            return datetime.fromtimestamp(
                int(valor),
                tz=timezone.utc,
            )
        except (TypeError, ValueError, OSError):
            return None

    def _extrair_dados_getitems(self, item):
        """
        Normaliza a resposta do IStoreBrowseService/GetItems.

        A Steam fornece:
        - preço atual;
        - preço original;
        - percentual de desconto;
        - active_discounts;
        - discount_description;
        - discount_end_date.

        O preço formatado retornado pela Steam é priorizado. Não usamos a
        primeira purchase_option quando best_purchase_option está ausente,
        pois ela pode representar DLC/expansão em jogos gratuitos.

        Não são preenchidos aqui ID/nome/início da campanha, pois o
        endpoint testado não os fornece de forma confiável.
        """
        best = item.get("best_purchase_option") or {}

        active_discounts = best.get("active_discounts") or []

        desconto_pct = best.get("discount_pct")
        preco_final = best.get("final_price_in_cents")
        preco_original = best.get("original_price_in_cents")
        preco_final_formatado = best.get("formatted_final_price")
        preco_original_formatado = best.get("formatted_original_price")
        package_id = best.get("packageid") or item.get("packageid")

        basic_info = item.get("basic_info") or {}
        is_free_getitems = bool(
            basic_info.get("is_free")
            or basic_info.get("is_free_to_play")
        )

        tipos_promocao = []
        finais_promocao = []

        for desconto in active_discounts:
            descricao = desconto.get("discount_description")
            if descricao and descricao not in tipos_promocao:
                tipos_promocao.append(descricao)

            fim = self._timestamp_para_datetime(
                desconto.get("discount_end_date")
            )
            if fim is not None:
                finais_promocao.append(fim)

        promocao_fim = min(finais_promocao) if finais_promocao else None
        promocao_tipo = " | ".join(tipos_promocao) if tipos_promocao else None

        # O teste mostrou que active_discounts vazio representa ausência
        # de promoção ativa; desconto_pct também funciona como confirmação.
        if desconto_pct is None:
            desconto_pct = 0

        try:
            desconto_pct = int(desconto_pct)
        except (TypeError, ValueError):
            desconto_pct = 0

        if is_free_getitems:
            preco_formatado = "Grátis"
            original_formatado = "Grátis"
            desconto_pct = 0
            promocao_tipo = None
            promocao_fim = None
        else:
            # O endpoint já entrega o preço formatado em BRL.
            # Priorizamos esse valor para não interpretar "1849" como R$ 1849,00.
            if preco_final_formatado:
                preco_formatado = str(preco_final_formatado).strip()
            else:
                preco_formatado = self._formatar_centavos(preco_final)

            if preco_original_formatado:
                original_formatado = str(preco_original_formatado).strip()
            else:
                original_formatado = self._formatar_centavos(preco_original)

        return {
            "plataforma": "Steam",
            "id": str(item.get("appid")) if item.get("appid") is not None else None,
            "nome": item.get("name") or "N/A",
            "preco": preco_formatado,
            "preco_sem_desconto": original_formatado,
            "desconto": f"{desconto_pct}%",
            "promocao_id": None,
            "promocao_nome": None,
            "promocao_inicio": None,
            "promocao_fim": promocao_fim,
            "promocao_tipo": promocao_tipo,
            "package_id": package_id,
        }

    def _consultar_getitems_lote(self, jogos_ids):
        """
        Consulta preços e promoções da Steam em lotes de até 50 IDs.

        Os lotes são enviados concorrentemente para reduzir o tempo total
        da coleta, mantendo o limite de 50 AppIDs por requisição da Steam.
        """
        ids_normalizados = []

        for jogo_id in jogos_ids or []:
            try:
                ids_normalizados.append(int(str(jogo_id)))
            except (TypeError, ValueError):
                print(f"AppID Steam inválido ignorado: {jogo_id}")

        ids_normalizados = list(dict.fromkeys(ids_normalizados))

        if not ids_normalizados:
            return {}

        lotes = [
            ids_normalizados[inicio:inicio + self.batch_size_store]
            for inicio in range(0, len(ids_normalizados), self.batch_size_store)
        ]

        def consultar_lote(lote):
            payload = {
                "ids": [{"appid": jogo_id} for jogo_id in lote],
                "context": self.contexto_store,
                "data_request": self.data_request_store,
            }

            url = (
                self.store_browse_api
                + "?input_json="
                + quote(
                    json.dumps(
                        payload,
                        separators=(",", ":"),
                    )
                )
            )

            try:
                response = requests.get(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Comparador-TCC/1.0",
                    },
                    timeout=15,
                )
                response.raise_for_status()

                dados = response.json()
                itens = dados.get("response", {}).get(
                    "store_items",
                    [],
                )

                return lote, itens, None

            except requests.exceptions.RequestException as erro:
                return lote, [], f"Erro na consulta em lote da Steam: {erro}"

            except ValueError as erro:
                return (
                    lote,
                    [],
                    "Erro ao interpretar JSON do GetItems da Steam: "
                    f"{erro}",
                )

        resultados = {}

        print(
            f"Steam GetItems concorrente: {len(lotes)} lotes de "
            f"até {self.batch_size_store} IDs, "
            f"{GETITEMS_WORKERS} requisições simultâneas."
        )

        with ThreadPoolExecutor(max_workers=GETITEMS_WORKERS) as executor:
            futuros = [
                executor.submit(consultar_lote, lote)
                for lote in lotes
            ]

            for futuro in as_completed(futuros):
                lote, itens, erro = futuro.result()

                if erro:
                    print(erro)
                    continue

                for item in itens:
                    dados_item = self._extrair_dados_getitems(item)
                    appid = dados_item.get("id")

                    if appid:
                        resultados[appid] = dados_item
                        self._cache_precos[appid] = dados_item

                print(
                    f"Steam GetItems: lote {len(lote)} IDs -> "
                    f"{len(itens)} itens retornados."
                )

        return resultados

    async def _scrape_preco_direto(self, jogo_id, ignorar_cache=False):
        if not ignorar_cache and jogo_id in self._cache_precos:
            return self._cache_precos[jogo_id]

        playwright = browser = page = None

        try:
            url = f"{self.url_base}/app/{jogo_id}/"
            playwright, browser, page = await self._abrir_pagina(url)

            if "/agecheck/" in page.url:
                print("\nPágina de verificação de idade detectada.")
                print("URL:", page.url)

                try:
                    await page.locator("select[name='ageDay']").select_option("1")
                    await page.locator("select[name='ageMonth']").select_option("January")
                    await page.locator("select[name='ageYear']").select_option("1990")

                    print("Data de nascimento preenchida.")

                    botao_view_page = page.locator(
                        "a.btnv6_blue_hoverfade.btn_medium",
                        has_text="View Page"
                    ).first

                    if await botao_view_page.count() == 0:
                        print("Botão 'View Page' não encontrado.")
                        return {
                            "preco": "N/A",
                            "preco_sem_desconto": "N/A",
                            "desconto": "0%"
                        }

                    await botao_view_page.click()

                    await page.wait_for_timeout(2000)

                    print("URL após verificação:", page.url)

                    if "/agecheck/" in page.url:
                        print("A página de verificação de idade continua ativa.")
                        return {
                            "preco": "N/A",
                            "preco_sem_desconto": "N/A",
                            "desconto": "0%"
                        }

                except Exception as erro:
                    print(f"Erro ao passar pela verificação de idade: {erro}")
                    return {
                        "preco": "N/A",
                        "preco_sem_desconto": "N/A",
                        "desconto": "0%"
                    }

            preco = None
            preco_original = None
            desconto = "0%"

            bloco_preco = page.locator(
                ".game_purchase_action .game_purchase_discount"
            ).first

            if await bloco_preco.count() > 0:
                elemento_final = bloco_preco.locator(
                    ".discount_final_price"
                ).first

                elemento_original = bloco_preco.locator(
                    ".discount_original_price"
                ).first

                elemento_desconto = bloco_preco.locator(
                    ".discount_pct"
                ).first

                if await elemento_final.count() > 0:
                    preco = await elemento_final.text_content()

                if await elemento_original.count() > 0:
                    preco_original = await elemento_original.text_content()

                if await elemento_desconto.count() > 0:
                    desconto = await elemento_desconto.text_content()

                preco = preco.strip() if preco else None
                preco_original = preco_original.strip() if preco_original else None
                desconto = desconto.strip() if desconto else "0%"
                desconto = desconto.replace("-", "")

            if not preco:
                # A página pode conter várias opções de compra, como
                # assinaturas, bundles e o próprio jogo. O primeiro
                # .game_purchase_price não é necessariamente o jogo.
                titulo_principal = page.locator("#appHubAppName").first
                nome_jogo = ""

                if await titulo_principal.count() > 0:
                    nome_jogo = (
                        await titulo_principal.text_content() or ""
                    ).strip()

                blocos_compra = page.locator(
                    ".game_area_purchase_game"
                )
                quantidade_blocos = await blocos_compra.count()
                bloco_jogo = None

                if nome_jogo:
                    nome_normalizado = re.sub(
                        r"\s+",
                        " ",
                        nome_jogo.lower(),
                    ).strip()

                    for indice in range(quantidade_blocos):
                        bloco = blocos_compra.nth(indice)
                        titulo_bloco = bloco.locator("h2.title").first

                        if await titulo_bloco.count() == 0:
                            continue

                        texto_titulo = (
                            await titulo_bloco.text_content() or ""
                        ).strip()

                        titulo_normalizado = re.sub(
                            r"\s+",
                            " ",
                            texto_titulo.lower(),
                        ).strip()

                        # Ex.: "Buy Bully: Scholarship Edition"
                        # corresponde a "Bully: Scholarship Edition".
                        if nome_normalizado in titulo_normalizado:
                            bloco_jogo = bloco
                            break

                if bloco_jogo is not None:
                    elemento = bloco_jogo.locator(
                        ".game_purchase_action .game_purchase_price"
                    ).first

                    if await elemento.count() > 0:
                        preco = await elemento.text_content()
                        preco = preco.strip() if preco else None

                        if not preco:
                            preco_centavos = await elemento.get_attribute(
                                "data-price-final"
                            )
                            if preco_centavos:
                                preco = self._formatar_centavos(
                                    preco_centavos
                                )

                # Último fallback para páginas sem título/bloco identificável.
                if not preco:
                    elemento = page.locator(
                        ".game_purchase_action .game_purchase_price"
                    ).first

                    if await elemento.count() > 0:
                        preco = await elemento.text_content()
                        preco = preco.strip() if preco else None

            if not preco:
                try:
                    botao = page.locator(
                        ".game_purchase_action .btn_addtocart"
                    ).first

                    if await botao.count() > 0:
                        texto = (await botao.text_content() or "").lower()

                        if any(
                            palavra in texto
                            for palavra in ["jogar", "play", "instalar"]
                        ):
                            preco = "Grátis"
                            preco_original = "Grátis"
                            desconto = "0%"
                except:
                    pass

            resultado = {
                "preco": self._formatar_preco(preco),
                "preco_sem_desconto": self._formatar_preco(preco_original),
                "desconto": desconto
            }

            if not ignorar_cache:
                self._cache_precos[jogo_id] = resultado

            return resultado

        except Exception as e:
            print(f"Erro no scraping direto da Steam ({jogo_id}): {e}")

            return {
                "preco": "N/A",
                "preco_sem_desconto": "N/A",
                "desconto": "0%"
            }

        finally:
            if browser:
                await browser.close()

            if playwright:
                await playwright.stop()
    async def coletar_fallback_preco(self, jogo_id):
        """
        Consulta uma fonte individual somente quando o GetItems em lote
        precisa de confirmação.

        Ordem:
        1. AppDetails, quando possui preço BRL;
        2. página individual da Steam via scraping, quando AppDetails
           não fornece preço utilizável.

        Retorna apenas dados de preço. Os dados de promoção do GetItems
        continuam sendo responsabilidade do coletor incremental.
        """
        jogo_id_str = str(jogo_id)

        try:
            url = (
                f"{self.api_base}/appdetails"
                f"?appids={jogo_id}&l=portuguese&cc=br"
            )

            response = requests.get(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Comparador-TCC/1.0",
                },
                timeout=15,
            )
            response.raise_for_status()

            payload = response.json()
            item = payload.get(jogo_id_str)

            if isinstance(item, dict) and item.get("success") is True:
                data = item.get("data") or {}
                price = data.get("price_overview") or {}

                if (
                    data.get("is_free") is True
                ):
                    return {
                        "preco": "Grátis",
                        "preco_sem_desconto": "Grátis",
                        "desconto": "0%",
                        "fonte": "APPDETAILS",
                    }

                if (
                    price.get("currency") == "BRL"
                    and price.get("final") is not None
                ):
                    return {
                        "preco": self._formatar_preco(price.get("final") / 100),
                        "preco_sem_desconto": self._formatar_preco(
                            price.get("initial", price.get("final")) / 100
                        ),
                        "desconto": (
                            f"{price.get('discount_percent', 0)}%"
                        ),
                        "fonte": "APPDETAILS",
                    }

            # AppDetails não resolveu o preço. Agora usamos a página real
            # da loja, ignorando deliberadamente o cache do GetItems.
            return await self._scrape_preco_direto(
                jogo_id,
                ignorar_cache=True,
            )

        except requests.exceptions.RequestException as erro:
            return {
                "preco": "N/A",
                "preco_sem_desconto": "N/A",
                "desconto": "0%",
                "fonte": "FALLBACK_ERRO_HTTP",
                "erro": str(erro)[:500],
            }

        except Exception as erro:
            return {
                "preco": "N/A",
                "preco_sem_desconto": "N/A",
                "desconto": "0%",
                "fonte": "FALLBACK_ERRO",
                "erro": repr(erro)[:500],
            }

    async def coletar_jogo(self, jogo_id):
        """Coleta os dados de um jogo específico da Steam.

        Preços e promoções usam o GetItems em lote/cache. O appdetails
        continua sendo usado para metadados e como fallback de preço.
        """
        jogo_id_str = str(jogo_id)
        print(f"Buscando jogo na Steam: {jogo_id}")

        try:
            # Garante que exista uma consulta GetItems para este AppID.
            if jogo_id_str not in self._cache_precos:
                self._consultar_getitems_lote([jogo_id])

            dados_store = self._cache_precos.get(jogo_id_str) or {}

            url = (
                f"{self.api_base}/appdetails"
                f"?appids={jogo_id}&l=portuguese&cc=br"
            )

            response = requests.get(url, timeout=15)
            response.raise_for_status()

            dados = response.json()
            dados_brutos = next(iter(dados.values()), None)

            if not dados_brutos or not dados_brutos.get("success", False):
                # Se o GetItems trouxe dados suficientes, devolve-os mesmo
                # sem os metadados completos do appdetails.
                if dados_store:
                    return {
                        **dados_store,
                        "id": jogo_id_str,
                        "url": f"{self.url_base}/app/{jogo_id}/",
                    }

                return {
                    "plataforma": "Steam",
                    "erro": "Jogo não encontrado",
                }

            dados_jogo = dados_brutos.get("data")

            if not dados_jogo:
                if dados_store:
                    return {
                        **dados_store,
                        "id": jogo_id_str,
                        "url": f"{self.url_base}/app/{jogo_id}/",
                    }

                return {
                    "plataforma": "Steam",
                    "erro": "Dados do jogo vazios",
                }

            preco_dados = dados_jogo.get("price_overview")
            is_free = dados_jogo.get("is_free", False)

            # Fonte principal: GetItems.
            preco_atual = dados_store.get("preco", "N/A")
            preco_original = dados_store.get("preco_sem_desconto", "N/A")
            desconto = dados_store.get("desconto", "0%")

            # Fallback/ajuste para jogos gratuitos ou respostas sem preço.
            if is_free:
                preco_atual = "Grátis"
                preco_original = "Grátis"
                desconto = "0%"

            elif preco_atual in ("N/A", None) and preco_dados:
                preco_atual = self._formatar_preco(preco_dados.get("final"))
                preco_original = self._formatar_preco(preco_dados.get("initial"))
                desconto = f"{preco_dados.get('discount_percent', 0)}%"

            elif preco_atual in ("N/A", None):
                print(
                    f"GetItems/appdetails não retornaram preço para {jogo_id}. "
                    "Tentando scraping..."
                )
                preco_scraping = await self._scrape_preco_direto(jogo_id)
                preco_atual = preco_scraping.get("preco", "N/A")
                preco_original = preco_scraping.get("preco_sem_desconto", "N/A")
                desconto = preco_scraping.get("desconto", "0%")

            descricao = (
                dados_jogo.get("about_the_game")
                or dados_jogo.get("detailed_description")
                or dados_jogo.get("short_description")
                or "N/A"
            )
            descricao = self._limpar_descricao(descricao)

            desenvolvedores = dados_jogo.get("developers", [])
            publicadoras = dados_jogo.get("publishers", [])
            generos = dados_jogo.get("genres", [])

            desenvolvedor = desenvolvedores[0] if desenvolvedores else None
            publicadora = publicadoras[0] if publicadoras else None
            genero = (
                ", ".join(
                    item.get("description", "")
                    for item in generos
                    if item.get("description")
                )
                or None
            )

            release_data = dados_jogo.get("release_date", {})

            resultado = {
                "plataforma": "Steam",
                "id": jogo_id_str,
                "nome": dados_jogo.get("name") or dados_store.get("nome", "N/A"),
                "preco": preco_atual,
                "preco_sem_desconto": preco_original,
                "desconto": desconto,
                "descricao": descricao,
                "url": f"{self.url_base}/app/{jogo_id}/",
                "gratuito": is_free,
                "desenvolvedor": desenvolvedor,
                "publicadora": publicadora,
                "genero": genero,
                "data_lancamento": release_data.get("date"),
                "url_imagem": dados_jogo.get("header_image"),
                "promocao_id": dados_store.get("promocao_id"),
                "promocao_nome": dados_store.get("promocao_nome"),
                "promocao_inicio": dados_store.get("promocao_inicio"),
                "promocao_fim": dados_store.get("promocao_fim"),
                "promocao_tipo": dados_store.get("promocao_tipo"),
                "package_id": dados_store.get("package_id"),
            }

            metacritic = dados_jogo.get("metacritic")
            resultado["avaliacao"] = (
                f"{metacritic.get('score', 'N/A')}/100"
                if metacritic
                else "N/A"
            )

            return resultado

        except requests.exceptions.Timeout:
            return {
                "plataforma": "Steam",
                "erro": "Timeout",
            }

        except requests.exceptions.RequestException as erro:
            return {
                "plataforma": "Steam",
                "erro": f"Erro de conexão: {erro}",
            }

        except Exception as erro:
            return {
                "plataforma": "Steam",
                "erro": f"Erro inesperado: {erro}",
            }

    async def coletar_precos_lote(self, jogos_ids):
        """Consulta preços e promoções em lote e retorna por AppID."""
        return await asyncio.to_thread(
            self._consultar_getitems_lote,
            jogos_ids,
        )

    async def coletar_precos(self):
        """Coleta os preços dos jogos definidos na lista."""

        print("Coletando dados da Steam...")

        try:
            resultados = []

            # Consulta preços/promocões em lote antes dos metadados individuais.
            self._consultar_getitems_lote(JOGOS_STEAM)

            for jogo_id in JOGOS_STEAM:
                dados_jogo = await self.coletar_jogo(jogo_id)

                if (
                    "erro" not in dados_jogo
                    and dados_jogo.get("nome") != "N/A"
                ):
                    resultados.append(dados_jogo)

                await asyncio.sleep(1.5)

            return {
                "plataforma": "Steam",
                "jogos": resultados
            }

        except Exception as erro:
            return {
                "plataforma": "Steam",
                "erro": str(erro)
            }

    async def coletar_promocoes(self):
        """Coleta jogos em promoção na Steam."""

        print("Coletando promoções da Steam...")

        try:
            url = (
                f"{self.api_base}/featuredcategories"
                "?l=portuguese&cc=br"
            )

            response = requests.get(
                url,
                timeout=15
            )

            response.raise_for_status()

            dados = response.json()
            promocoes = []

            featured = dados.get(
                "featured",
                {}
            ).get(
                "items",
                []
            )

            if not featured:
                featured = dados.get(
                    "specials",
                    {}
                ).get(
                    "items",
                    []
                )

            for jogo in featured[:10]:
                jogo_id = jogo.get("id")

                if not jogo_id:
                    continue

                detalhes = await self.coletar_jogo(jogo_id)

                if "erro" in detalhes:
                    continue

                promocoes.append({
                    "nome": detalhes.get("nome", "N/A"),
                    "preco_promocional": detalhes.get(
                        "preco",
                        "N/A"
                    ),
                    "desconto": detalhes.get(
                        "desconto",
                        "0%"
                    ),
                    "url": f"{self.url_base}/app/{jogo_id}/"
                })

            return {
                "plataforma": "Steam",
                "promocoes": promocoes,
                "total": len(promocoes)
            }

        except Exception as erro:
            return {
                "plataforma": "Steam",
                "erro": str(erro)
            }


async def testar_steam():
    """Executa um teste simples do coletor."""

    coletor = SteamColetor()

    print("=" * 50)
    print("TESTANDO COLETOR DA STEAM")
    print("=" * 50)

    resultado = await coletor.coletar_precos()
    jogos = resultado.get("jogos", [])

    print(f"\n{len(jogos)} jogos coletados.")

    for jogo in jogos:
        gratuito = (
            " (GRÁTIS)"
            if jogo.get("gratuito")
            else ""
        )

        print(
            f"- {jogo.get('nome')}: "
            f"{jogo.get('preco')}"
            f"{gratuito} "
            f"({jogo.get('desconto')})"
        )

    print("=" * 50)

    return resultado


if __name__ == "__main__":
    asyncio.run(testar_steam())