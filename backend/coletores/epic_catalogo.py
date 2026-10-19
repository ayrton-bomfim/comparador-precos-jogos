"""Descoberta e normalizacao do catalogo BASE_GAME da Epic via EGData."""

from __future__ import annotations

import math
import re
import time
import unicodedata
from typing import Any

import requests


class EpicCatalogo:
    """Consulta BASE_GAME, EDITION e EXPERIENCE da EGData e devolve jogos normalizados, sem persistir no BD."""

    URL_BUSCA = "https://api.egdata.app/search/v2/search"
    PAIS = "BR"
    LOCALE = "pt-BR"
    LIMITE_PAGINA = 100
    TIMEOUT = 30

    def __init__(
        self,
        timeout: int | None = None,
        pausa_paginas: float = 0.15,
        max_tentativas: int = 4,
        pausa_retry: float = 2.0,
    ):
        self.timeout = timeout or self.TIMEOUT
        self.pausa_paginas = pausa_paginas
        self.max_tentativas = max(1, max_tentativas)
        self.pausa_retry = max(0.0, pausa_retry)
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    @staticmethod
    def _normalizar_texto(valor: Any) -> str:
        if valor is None:
            return ""
        texto = str(valor).strip().lower()
        texto = unicodedata.normalize("NFKD", texto)
        texto = "".join(c for c in texto if not unicodedata.combining(c))
        texto = re.sub(r"\s+", " ", texto)
        return texto

    @staticmethod
    def _tem_restricao_br(oferta: dict[str, Any]) -> bool:
        """Retorna True somente quando a oferta declara explicitamente exclusao do BR."""
        pais = EpicCatalogo.PAIS

        blacklist = {str(p).upper() for p in (oferta.get("countriesBlacklist") or [])}
        if pais in blacklist:
            return True

        whitelist = oferta.get("countriesWhitelist")
        if whitelist is not None and len(whitelist) > 0:
            permitidos = {str(p).upper() for p in whitelist}
            if pais not in permitidos:
                return True

        return False

    @classmethod
    def _page_type_publico(cls, oferta: dict[str, Any]) -> str:
        """Retorna o tipo de página pública esperado para a oferta."""
        offer_type = str(oferta.get("offerType") or "").upper()

        if offer_type == "BASE_GAME":
            return "productHome"

        if offer_type in {"EDITION", "EXPERIENCE"}:
            return "offer"

        return ""

    @classmethod
    def _is_product_home(cls, oferta: dict[str, Any]) -> bool:
        return any(
            isinstance(mapping, dict)
            and mapping.get("pageType") == "productHome"
            for mapping in oferta.get("offerMappings") or []
        )

    @classmethod
    def _extrair_page_slug(cls, oferta: dict[str, Any]) -> str | None:
        """Retorna o pageSlug da página pública correspondente ao tipo da oferta."""
        page_type_esperado = cls._page_type_publico(oferta)

        if not page_type_esperado:
            return None

        for mapping in oferta.get("offerMappings") or []:
            if not isinstance(mapping, dict):
                continue

            if mapping.get("pageType") != page_type_esperado:
                continue

            page_slug = cls._normalizar_texto(mapping.get("pageSlug"))
            if page_slug:
                return page_slug

        # EXPERIENCE pode existir na EGData sem offerMappings.
        # Nesses casos, o urlSlug pode ser usado como identidade pública.
        if str(oferta.get("offerType") or "").upper() == "EXPERIENCE":
            url_slug = cls._normalizar_texto(oferta.get("urlSlug"))
            if url_slug:
                return re.sub(r"-(?:ios|android)$", "", url_slug)

        return None

    @classmethod
    def _page_slug_experience(cls, oferta: dict[str, Any]) -> str | None:
        """Retorna a identidade pública canônica de uma EXPERIENCE.

        A EGData pode devolver a mesma experiência em variantes específicas
        de plataforma, como ``-ios`` e ``-android``. Essas variantes possuem
        offer_id diferentes, mas apontam para a mesma experiência comercial.

        Para EXPERIENCE, preferimos um pageSlug sem esses sufixos.
        Quando não existe mapping público, usamos urlSlug como fallback.
        """
        for mapping in oferta.get("offerMappings") or []:
            if not isinstance(mapping, dict):
                continue

            if mapping.get("pageType") != "offer":
                continue

            page_slug = cls._normalizar_texto(mapping.get("pageSlug"))
            if not page_slug:
                continue

            if not re.search(r"-(?:ios|android)$", page_slug):
                return page_slug

        # Se só houver variantes de plataforma, normaliza o sufixo.
        for mapping in oferta.get("offerMappings") or []:
            if not isinstance(mapping, dict):
                continue

            if mapping.get("pageType") != "offer":
                continue

            page_slug = cls._normalizar_texto(mapping.get("pageSlug"))
            if page_slug:
                return re.sub(r"-(?:ios|android)$", "", page_slug)

        # Algumas EXPERIENCE, como Fortnite Battle Royale, não possuem
        # offerMappings, mas possuem um urlSlug público utilizável.
        url_slug = cls._normalizar_texto(oferta.get("urlSlug"))
        if url_slug:
            return re.sub(r"-(?:ios|android)$", "", url_slug)

        return None

    @classmethod
    def _chave_deduplicacao(cls, oferta: dict[str, Any]) -> str | None:
        """Identidade comercial usada para canonização.

        BASE_GAME/EDITION continuam usando o pageSlug público.
        EXPERIENCE usa uma chave específica que unifica variantes
        iOS/Android da mesma experiência.
        """
        offer_type = str(oferta.get("offerType") or "").upper()

        if offer_type == "EXPERIENCE":
            page_slug = cls._page_slug_experience(oferta)
        else:
            page_slug = cls._extrair_page_slug(oferta)

        if not page_slug:
            return None

        return f"{offer_type}:{page_slug}"

    @classmethod
    def _pontuacao_canonica(
        cls, oferta: dict[str, Any]
    ) -> tuple[int, int, int, int, int, str]:
        """Maior tupla = oferta preferida quando existem duplicatas.

        A prioridade de categoria evita que variantes técnicas/staging
        (por exemplo, ``spthidden``) com ``productHome`` sejam escolhidas
        no lugar da oferta comercial classificada como ``games``.
        """
        categorias = oferta.get("categories") or []

        return (
            int("games" in categorias),
            int("games/edition/base" in categorias),
            int(not bool(oferta.get("prePurchase"))),
            int(cls._is_product_home(oferta)),
            int(bool(oferta.get("releaseDate"))),
            str(oferta.get("lastModifiedDate") or ""),
        )

    @classmethod
    def _escolher_canonica(cls, ofertas: list[dict[str, Any]]) -> dict[str, Any]:
        return max(ofertas, key=cls._pontuacao_canonica)

    EXCECOES_JOGOS_APPLICATION = {
        ("047ee5c9350245588f043061fb0279ab", "ghost-recon-future-soldier/home"),
        ("0bef9383794a4d779ba0628084b14cba", "rumbleverse"),
    }

    # Correcoes manuais de URLs confirmadas na loja Epic.
    # Chave: (namespace, productSlug) da oferta canonica.
    # Essas correcoes têm prioridade sobre URL direta e productHome,
    # porque representam excecoes já validadas manualmente.
    CORRECOES_URL_MANUAIS: dict[tuple[str, str], str] = {
        ("ark", "ark/ultimate-survivor-edition"): "https://store.epicgames.com/p/ark--ultimate-survivor-edition",
        ("a14a02aa3c8143729605eaf7c93d7501", "battlefield-6"): "https://store.epicgames.com/p/battlefield-6",
        ("26ad9cfe11574001b0022deee5b7c15b", "broken-roads"): "https://store.epicgames.com/p/broken-roads-c8f827",
        ("c42b08b655c04a64a0535331629d4b6d", "bugsnax"): "https://store.epicgames.com/p/bugsnax",
        ("bd46d4ce259349e5bd8b3ded20274737", "chivalry-2--special-edition"): "https://store.epicgames.com/p/chivalry-2--special-edition",
        ("611482b8586142cda48a0786eb8a127c", "dead-by-daylight"): "https://store.epicgames.com/p/dead-by-daylight",
        ("tulip", "thimbleweed-park/delores"): "https://store.epicgames.com/p/thimbleweed-park--delores",
        ("19d5458aa3c849a1b0fff69da4c9ed9d", "ea-sports-pga-tour"): "https://store.epicgames.com/p/ea-sports-pga-tour",
        ("50b6612049324d0faf8642014139b082", "wrc"): "https://store.epicgames.com/p/ea-sports-wrc-24--ea-play-edition",
        ("4193c9fd2f41405f813f828cce02d132", "endless-dungeon"): "https://store.epicgames.com/p/endless-dungeon",
        ("epic", "flower/home"): "https://store.epicgames.com/p/flower",
        ("sundrop", "for-honor/home"): "https://store.epicgames.com/p/for-honor",
        ("fn", "fortnite"): "https://store.epicgames.com/p/fortnite",
        ("epic", "genesis-alpha-one"): "https://store.epicgames.com/p/genesis-alpha-one",
        ("598bbf91c75b4ac9a676d82719acdbb1", "ghostbusters-spirits-unleashed"): "https://store.epicgames.com/p/ghostbusters-spirits-unleashed",
        ("0584d2013f0149a791e7b9bad0eec102", "grand-theft-auto-v"): "https://store.epicgames.com/p/grand-theft-auto-v",
        ("c315a84ec4714288b34f7ac94ee2515d", "hextech-mayhem-a-league-of-legends-story"): "https://store.epicgames.com/p/hextech-mayhem-a-league-of-legends-story",
        ("78de1f402ddf486ebcbf9ba3009d6198", "huntdown/home"): "https://store.epicgames.com/p/huntdown",
        ("bdb4adaa3874491bbafe9a16b2764200", "lego-horizon-adventures-pp"): "https://store.epicgames.com/p/lego-horizon-adventures",
        ("turtle", "maneater--apex-edition"): "https://store.epicgames.com/p/maneater--apex-edition",
        ("1be39e503e234386a7d4456d33b197fc", "no-longer-home--farewell-edition"): "https://store.epicgames.com/p/no-longer-home--farewell-edition",
        ("c6e54ebd92da4ee8819c1c0956cebdc4", "outriders/home"): "https://store.epicgames.com/p/outriders",
        ("3a5c77a536854024add2714cbd0fa865", "robocop-rogue-city"): "https://store.epicgames.com/p/robocop-rogue-city",
        ("cinnamon", "sherlock-holmes-the-devils-daughter/home"): "https://store.epicgames.com/p/sherlock-holmes-the-devils-daughter",
        ("24285307a56445f1bc5d546df7af3025", "sins-of-a-solar-empire-2"): "https://store.epicgames.com/p/sins-of-a-solar-empire-ii",
        ("fe5a2e3e842a4394938a81f3308df2ed7", "solar-ash/home"): "https://store.epicgames.com/p/solar-ash",
        ("1e1d639f7fa045f08a1378885ec7080c", "the-mageseeker-a-league-of-legends-story--deluxe-edition"): "https://store.epicgames.com/p/the-mageseeker-a-league-of-legends-story--deluxe-edition",
        ("2a14cf8a83b149919a2399504e5686a6", "the-sims-4/ea-play-edition"): "https://store.epicgames.com/p/the-sims-4--ea-play-edition",
        ("cf4ee4f4e6574b82896b636179d946ee", "wayfinder"): "https://store.epicgames.com/p/wyldheart-68afa1",
        ("epic", "world-war-z/home"): "https://store.epicgames.com/p/world-war-z--base-game",
        ("9cf250606722448887fa1447b1d9da06", "wrc-9/deluxe-edition"): "https://store.epicgames.com/p/wrc-9--deluxe-edition",
    }


    # Ofertas que devem ser retiradas do catálogo antes da canonização.
    #
    # A regra é aplicada à oferta original, portanto esses registros não
    # chegam ao cadastro do catálogo nem viram Jogo/EpicCatalogo/EpicOferta.
    # A comparação usa o título normalizado porque a planilha de auditoria
    # não contém o namespace de todos os casos.
    EXCLUSOES_MANUAIS_NOME = {
        ">observer_",
        "ambulance life: a paramedic simulator",
        "battlefieldTM 2042 gold edition",
        "battlefieldTM 2042 ultimate edition",
        "beyond good & evil",
        "blackolive general audience",
        "cerise general audience",
        "chimeraland",
        "concord",
        "courser general audience",
        "crayta",
        "crsed: cuisine royale",
        "dauntless",
        "dishonored & prey: the arkane collection",
        "divine knockout",
        "ea sports fcTM 24 standard edition",
        "ea sportsTM fifa 23 standard edition",
        "evil dead: the game",
        "f1® 22 standard edition",
        "f1® 23",
        "f1® manager 2023",
        "fae farm pre-purchase",
        "fault: elder orb",
        "football manager 2021 touch",
        "football manager 2022",
        "football manager 2023",
        "fuser",
        "ghost recon breakpoint - trial weekend",
        "ghost recon future soldier: ultimate edition",
        "good company press",
        "guild of dungeoneering",
        "heroes & generals wwii",
        "hitman",
        "hood: outlaws & legends",
        "hyper scapeTM",
        "john wick hex",
        "kansas generalaudience",
        "knockout cityTM",
        "knockout cityTM block party edition",
        "knockout cityTM deluxe block party edition",
        "knockout cityTM trial",
        "lego® 2k drive",
        "life by you",
        "lionstagingaudience",
        "madden nfl 23",
        "madden nfl 24",
        "magic: legends",
        "monopoly® plus",
        "multiversus",
        "nba 2k21",
        "nixgeneralaudience",
        "no straight roads (pre-purchase)",
        "out of the park baseball 22",
        "phoenix point",
        "prince of persia: warrior within standard edition",
        "r.b.i. baseball 21",
        "realm royale reforged",
        "redout: solar challenge edition",
        "roots of pacha",
        "rumbleverse",
        "rune ii - standard edition",
        "scavengers",
        "space punks",
        "spellbreak",
        "star stable online",
        "star trek: resurgence",
        "starsiege: deadzone",
        "stonefly",
        "stranger things 3: the game",
        "surviving the aftermath: founder's edition",
        "synced",
        "the cycle: frontier",
        "the outer worlds - relstable",
        "the tenants",
        "ticket to ride: classic edition",
        "total war: pharaoh",
        "tower of fantasy",
        "trover saves the universe",
        "video horror society",
        "vigil: the longest night",
        "warface: clutch",
        "where the heart leads",
        "wild card football",
        "wolfenstein: the new order - worldwide",
        "wolfenstein: the old blood - worldwide",
        "zorya: the celestial sisters",
        "zorya: the celestial sisters friend pass",
    }

    # Casos que não são identificados apenas pelo nome.
    # Fortnite Android não deve entrar no catálogo, mas o Fortnite de PC sim.
    EXCLUSOES_MANUAIS_SLUG = {
        "fortnite-android",
        "f1-23",
        "space-punks",
        "spellbreak",
        "thecycle/home",
    }

    # Casos em que o comentário da auditoria indica que a oferta representa
    # uma edição que não deve ser cadastrada com a URL encontrada.
    EXCLUSOES_MANUAIS_ESPECIAIS = {
        "prince of persia: the sands of time remake",
    }

    # Títulos que a Epic fornece somente como o nome da edição.
    TITULOS_EDICAO_GENERICOS = {
        "edicao american wilds",
        "edicao anthology",
        "edicao black tie",
        "edicao caotica e maneira",
        "edicao comemorativa de 4 anos de insurgency: sandstorm",
        "edicao completa",
        "edicao definitiva",
        "edicao deluxe",
        "edicao digital deluxe",
        "edicao gold",
        "edicao premium",
        "edicao super deluxe",
        "edicao ultimate",
    }

    # Correções de nome. A URL pode continuar sendo a mesma página pública,
    # mas o nome armazenado deve refletir a versão atualmente comercializada.
    CORRECOES_NOME_MANUAIS: dict[tuple[str, str], str] = {
        ("0584d2013f0149a791e7b9bad0eec102", "grand-theft-auto-v"):
            "Grand Theft Auto V Enhanced",
    }

    # Correções manuais das 31 ofertas cujo título retornado pela Epic/EGData
    # é genérico. O offer_id é a identidade da oferta.
    CORRECOES_NOME_MANUAIS_OFFER_ID: dict[str, str] = {
        "cd047d2137504474b35f236c56280022": "Assassin's Creed Rogue - Deluxe Edition",
        "b48f8f79e8ac49148a65d9121c38896b": "Neon Abyss - Deluxe Edition",
        "4e5362e02cb241f9ad4fa45a16d69afe": "STAR WARS Jedi: Fallen Order Deluxe Edition",
        "8eeca1431d1b4010a12e6b3c8c400c94": "Tony Hawk's™ Pro Skater™ 1 + 2 - Deluxe Edition",
        "dda85a2a51fc480bb643d178c47fa8ec": "art of rally - Deluxe Edition",
        "98576bf5f7cd47a994b05e0937f5c09e": "Assassin's Creed Odyssey - Deluxe Edition",
        "855b9b1f91b0439089395bbaab1b6e4b": "Assassin's Creed Origins Deluxe Edition",
        "f90fc9961b064b7eb52cddf24851fe67": "The Medium - Deluxe Edition",
        "dd9311e1860e4dd7b23398da971cd496": "Zombie Army 4: Dead War - Deluxe Edition",
        "646d888512944af1a995397650a5056b": "Observer: System Redux - Deluxe Edition",
        "c5ab3ce9055042149520779a2b353e21": "The Dungeon of Naheulbeuk: The Amulet of Chaos - Deluxe Edition",
        "d9cb056bc6e645499c66a97ebe8a2906": "Shenmue III - Deluxe Edition",
        "e4d0605f415c43ca95e858ca9a1b12dc": "Q.U.B.E. 2 Deluxe Edition",
        "5ed82391fa1d4d9ea8366b8cce79f177": "Deliver Us The Moon: Digital Deluxe",
        "ec247631278d4ccda3eebb9f0ffb3391": "Totally Reliable Delivery Service Deluxe Edition",
        "db198a92c7534d24babb9a44440d2379": "MudRunner - American Wilds Edition",
        "f301fd4611f240da87cdc7baf1b67f44": "Sid Meier's Civilization® VI Anthology",
        "2b028f45690a412daa0542bbdee05130": "Tiny Tina's Wonderlands Chaotic Great Edition",
        "f506d29d55bb4c72b8d57fd9857b2be4": "Insurgency: Sandstorm - 4th Anniversary Edition",
        "c3a4300ca5fb498b91008b7e5fe5778e": "Remnant: From the Ashes - Complete Edition",
        "72eeff27e5534f109f6a3438390ee38a": "Red Dead Redemption 2: Ultimate Edition",
        "aba6ec8b6cf745f8af6417f2bb5839b1": "Predator: Hunting Grounds Digital Deluxe Edition",
        "d0cdd483102d4502b1df0e066f249417": "The Crew 2 Gold Edition",
        "55c9c7864480492fa21f3699b7aa2cf4": "Assassin's Creed Syndicate Gold Edition",
        "7138add3ee2241f6a5f945baababbc0b": "Assassin's Creed Odyssey Gold Edition",
        "684622a0f2e342a38e0980c10394acc8": "Far Cry® 5 Gold Edition",
        "2f669ed2f0534df28b48c998f77be223": "Assassin's Creed Origins Gold Edition",
        "aa0da56bf1244f4484f10689714e8523": "South Park™: The Fractured But Whole™ Gold Edition",
        "6892597eb9bf40388fc17aef68b19889": "Farming Simulator 19 - Premium Edition",
        "74979939bb5a48979ba866ab88be7dca": "Borderlands 3 - Super Deluxe Edition",
        "932a8392787347218ebadfb430286a2e": "Assassin's Creed Odyssey Ultimate Edition",
    }

    # Correções de URL que não dependem de namespace, porque a regra é
    # explicitamente sobre o produto identificado pelo título.
    CORRECOES_URL_ESPECIAIS: dict[str, str] = {
        "doom (1993)": "https://store.epicgames.com/p/doom-and-doom-ii-f5e089",
        "doom ii": "https://store.epicgames.com/p/doom-and-doom-ii-f5e089",
    }

    @classmethod
    def _eh_jogo_catalogo(cls, oferta: dict[str, Any]) -> bool:
        """Retorna True quando a oferta canônica deve entrar no catálogo de jogos.

        A regra principal usa a categoria ``games`` da EGData.
        Algumas ofertas reais de jogos, porém, aparecem somente como
        ``applications`` e são mantidas explicitamente como exceções.
        """
        categorias = set(oferta.get("categories") or [])
        offer_type = str(oferta.get("offerType") or "").upper()

        # BASE_GAME e EDITION seguem a regra principal da categoria games.
        if offer_type in {"BASE_GAME", "EDITION"}:
            if "games" in categorias:
                return True

        # EXPERIENCE entra somente quando a EGData identifica
        # explicitamente a experiência como conteúdo de jogos.
        #
        # O teste realizado em 06/10/2026 encontrou 23 EXPERIENCE,
        # e todas as 23 possuíam simultaneamente:
        #   - games
        #   - games/experience
        #
        # Isso inclui Fortnite: Raiz, Reload, Festival,
        # Salve o Mundo e LEGO Fortnite: Odyssey.
        if offer_type == "EXPERIENCE":
            return (
                "games" in categorias
                and "games/experience" in categorias
            )

        chave = (
            oferta.get("namespace"),
            oferta.get("productSlug"),
        )

        # As exceções existentes são específicas de BASE_GAME.
        return offer_type == "BASE_GAME" and chave in cls.EXCECOES_JOGOS_APPLICATION

    @staticmethod
    def _extrair_preco(oferta: dict[str, Any]) -> dict[str, Any]:
        bloco = oferta.get("price") or {}
        preco = bloco.get("price") or {}
        return {
            "moeda": preco.get("currencyCode"),
            "preco_original": preco.get("originalPrice"),
            "preco_atual": preco.get("discountPrice"),
            "desconto": preco.get("discount"),
            "atualizado_em": bloco.get("updatedAt"),
        }

    @staticmethod
    def _extrair_nome_custom_attribute(
        oferta: dict[str, Any], nome: str
    ) -> str | None:
        """Extrai um valor textual de customAttributes da oferta."""
        custom_attributes = oferta.get("customAttributes") or {}
        atributo = custom_attributes.get(nome) or {}

        if isinstance(atributo, dict):
            valor = atributo.get("value")
        else:
            valor = atributo

        if valor is None:
            return None

        valor = str(valor).strip()
        return valor or None

    @classmethod
    def _extrair_desenvolvedor(cls, oferta: dict[str, Any]) -> str | None:
        """Usa o campo direto da EGData e cai para customAttributes."""
        valor = oferta.get("developerDisplayName")

        if valor is not None and str(valor).strip():
            return str(valor).strip()

        return cls._extrair_nome_custom_attribute(oferta, "developerName")

    @classmethod
    def _extrair_publicadora(cls, oferta: dict[str, Any]) -> str | None:
        """Usa o campo direto da EGData e cai para customAttributes."""
        valor = oferta.get("publisherDisplayName")

        if valor is not None and str(valor).strip():
            return str(valor).strip()

        return cls._extrair_nome_custom_attribute(oferta, "publisherName")

    @classmethod
    def _extrair_url(cls, oferta: dict[str, Any]) -> str | None:
        """
        Obtém a URL canônica da página do produto na Epic.

        Prioridade:
        1. Correções manuais confirmadas;
        2. URL fornecida diretamente pela API;
        3. pageSlug de offerMappings correspondente ao tipo da oferta;
        4. None quando a API não fornece uma página pública confiável.

        Não usa productSlug nem urlSlug como identidade pública.
        """
        namespace = cls._normalizar_texto(oferta.get("namespace"))
        product_slug = cls._normalizar_texto(oferta.get("productSlug"))
        page_slug = cls._extrair_page_slug(oferta)
        titulo = cls._normalizar_texto(oferta.get("title"))

        # 1. Correções manuais por caso especial.
        url_especial = cls.CORRECOES_URL_ESPECIAIS.get(titulo)
        if url_especial:
            return url_especial

        # 2. Correções manuais confirmadas por namespace + productSlug.
        url_manual = cls.CORRECOES_URL_MANUAIS.get((namespace, product_slug))
        if url_manual:
            return url_manual

        # 3. URL direta fornecida pela API.
        url = oferta.get("url")
        if url is not None and str(url).strip():
            return str(url).strip()

        # 4. productHome informado em offerMappings.
        if page_slug:
            return f"https://store.epicgames.com/p/{page_slug}"

        return None


    @classmethod
    def _nome_base_para_edicao(cls, oferta: dict[str, Any], nomes_base_por_page_slug: dict[str, str] | None) -> str | None:
        if not nomes_base_por_page_slug:
            return None
        page_slug = cls._extrair_page_slug(oferta)
        if not page_slug or "--" not in page_slug:
            return None
        return nomes_base_por_page_slug.get(page_slug.split("--", 1)[0])

    @classmethod
    def _normalizar_nome_edicao(cls, oferta: dict[str, Any], nomes_base_por_page_slug: dict[str, str] | None = None) -> str | None:
        nome_original = oferta.get("title")
        if nome_original is None:
            return None
        nome = str(nome_original).strip()
        if str(oferta.get("offerType") or "").upper() != "EDITION":
            return nome
        if cls._normalizar_texto(nome) not in cls.TITULOS_EDICAO_GENERICOS:
            return nome
        nome_base = cls._nome_base_para_edicao(oferta, nomes_base_por_page_slug)
        if not nome_base:
            return nome
        nome_base = re.sub(r"\s+(?:edição\s+standard|standard\s+edition)$", "", nome_base, flags=re.IGNORECASE).strip(" -")
        return f"{nome_base} - {nome}" if nome_base else nome

    @classmethod
    def _normalizar_oferta(cls, oferta: dict[str, Any], nomes_base_por_page_slug: dict[str, str] | None = None) -> dict[str, Any]:
        preco = cls._extrair_preco(oferta)
        namespace = cls._normalizar_texto(oferta.get("namespace"))
        product_slug = cls._normalizar_texto(oferta.get("productSlug"))
        page_slug = cls._extrair_page_slug(oferta)
        nome_original = oferta.get("title")
        offer_id = str(oferta.get("id") or "").strip()
        chave = (namespace, product_slug)

        if offer_id in cls.CORRECOES_NOME_MANUAIS_OFFER_ID:
            nome = cls.CORRECOES_NOME_MANUAIS_OFFER_ID[offer_id]
        else:
            nome = cls.CORRECOES_NOME_MANUAIS.get(
                chave,
                nome_original,
            )

        if (
            offer_id not in cls.CORRECOES_NOME_MANUAIS_OFFER_ID
            and chave not in cls.CORRECOES_NOME_MANUAIS
            and str(oferta.get("offerType") or "").upper() == "EDITION"
        ):
            nome = cls._normalizar_nome_edicao(oferta, nomes_base_por_page_slug)
        return {
            "plataforma": "Epic Games",
            "epic_offer_id": oferta.get("id"),
            "epic_namespace": oferta.get("namespace"),
            "epic_offer_type": oferta.get("offerType"),
            "nome": nome,
            # Identidade pública: BASE_GAME -> productHome;
            # EDITION/EXPERIENCE -> offer.
            "epic_id": page_slug,
            "page_slug": page_slug,
            # Mantido somente para regras legadas/exceções e diagnóstico.
            "product_slug": oferta.get("productSlug"),
            "url_slug": oferta.get("urlSlug"),
            "url": cls._extrair_url(oferta),
            "descricao": oferta.get("description"),
            "descricao_longa": oferta.get("longDescription"),
            "desenvolvedor": cls._extrair_desenvolvedor(oferta),
            "publicadora": cls._extrair_publicadora(oferta),
            "data_lancamento": oferta.get("releaseDate"),
            "data_lancamento_pc": oferta.get("pcReleaseDate"),
            "preco": preco["preco_atual"],
            "preco_sem_desconto": preco["preco_original"],
            "desconto": preco["desconto"],
            "moeda": preco["moeda"],
            "preco_atualizado_em": preco["atualizado_em"],
            "imagens": oferta.get("keyImages") or [],
            "tags": oferta.get("tags") or [],
            "categorias": oferta.get("categories") or [],
            "locale": oferta.get("locale"),
            "locale_status": oferta.get("localeStatus"),
            "canonical_locale": oferta.get("canonicalLocale"),
            "last_modified_date": oferta.get("lastModifiedDate"),
            "creation_date": oferta.get("creationDate"),
            "effective_date": oferta.get("effectiveDate"),
            "viewable_date": oferta.get("viewableDate"),
            "pc_release_date": oferta.get("pcReleaseDate"),
            "pre_purchase": oferta.get("prePurchase"),
            "seller": oferta.get("seller"),
            "countries_blacklist": oferta.get("countriesBlacklist") or [],
            "countries_whitelist": oferta.get("countriesWhitelist"),
        }

    @classmethod
    def _motivos_descarte(cls, oferta: dict[str, Any]) -> list[str]:
        motivos: list[str] = []

        titulo = cls._normalizar_texto(oferta.get("title"))
        product_slug = cls._normalizar_texto(oferta.get("productSlug"))

        if titulo in cls.EXCLUSOES_MANUAIS_NOME:
            motivos.append("exclusao_manual")

        if product_slug in cls.EXCLUSOES_MANUAIS_SLUG:
            motivos.append("exclusao_manual_slug")

        if titulo in cls.EXCLUSOES_MANUAIS_ESPECIAIS:
            motivos.append("exclusao_manual_especial")

        if not cls._extrair_page_slug(oferta):
            motivos.append("sem_page_slug")
        if not cls._normalizar_texto(oferta.get("namespace")):
            motivos.append("sem_namespace")
        if cls._tem_restricao_br(oferta):
            motivos.append("restricao_br")
        return motivos

    @classmethod
    def _resumo_descarte(
        cls,
oferta: dict[str, Any], motivos: list[str]) -> dict[str, Any]:
        return {
            "id": oferta.get("id"),
            "nome": oferta.get("title"),
            "namespace": oferta.get("namespace"),
            "page_slug": cls._extrair_page_slug(oferta),
            "product_slug": oferta.get("productSlug"),
            "motivos": motivos,
        }

    def buscar_pagina(
        self,
        pagina: int,
        offer_type: str = "BASE_GAME",
    ) -> dict[str, Any]:
        offer_type = str(offer_type).upper().strip()

        if offer_type not in {"BASE_GAME", "EDITION", "EXPERIENCE"}:
            raise ValueError(
                f"offer_type inválido: {offer_type!r}. "
                "Use BASE_GAME, EDITION ou EXPERIENCE."
            )

        payload = {
            "offerType": offer_type,
            "sortBy": "lastModifiedDate",
            "sortDir": "desc",
            "page": pagina,
            "limit": self.LIMITE_PAGINA,
        }

        ultima_excecao: Exception | None = None

        for tentativa in range(1, self.max_tentativas + 1):
            try:
                resposta = self.session.post(
                    self.URL_BUSCA,
                    params={"country": self.PAIS, "locale": self.LOCALE},
                    json=payload,
                    timeout=self.timeout,
                )

                # 500/502/503/504 podem ser falhas transitórias do serviço.
                # 429 também merece retry, respeitando Retry-After quando existir.
                if resposta.status_code in {429, 500, 502, 503, 504}:
                    if tentativa >= self.max_tentativas:
                        resposta.raise_for_status()

                    retry_after = resposta.headers.get("Retry-After")
                    try:
                        espera = float(retry_after) if retry_after else (
                            self.pausa_retry * (2 ** (tentativa - 1))
                        )
                    except ValueError:
                        espera = self.pausa_retry * (2 ** (tentativa - 1))

                    print(
                        f"  ⚠️ Página {pagina}: HTTP {resposta.status_code} "
                        f"(tentativa {tentativa}/{self.max_tentativas}). "
                        f"Nova tentativa em {espera:.1f}s..."
                    )
                    time.sleep(espera)
                    continue

                resposta.raise_for_status()
                return resposta.json()

            except requests.RequestException as erro:
                ultima_excecao = erro

                if tentativa >= self.max_tentativas:
                    raise

                espera = self.pausa_retry * (2 ** (tentativa - 1))
                print(
                    f"  ⚠️ Página {pagina}: {type(erro).__name__} "
                    f"(tentativa {tentativa}/{self.max_tentativas}). "
                    f"Nova tentativa em {espera:.1f}s..."
                )
                time.sleep(espera)

        if ultima_excecao:
            raise ultima_excecao

        raise RuntimeError(f"Falha ao consultar a página {pagina}.")


    def coletar(self, max_paginas: int | None = None) -> dict[str, Any]:
        """
        Coleta BASE_GAME, EDITION e EXPERIENCE paginados, registra
        descartes e deduplica pela identidade pública de cada tipo de oferta.

        max_paginas limita deliberadamente a quantidade de páginas
        consultadas por tipo para testes rápidos.
        Quando None, cada tipo segue até o fim do catálogo.
        """
        todas: list[dict[str, Any]] = []
        totais_por_tipo: dict[str, int | None] = {
            "BASE_GAME": None,
            "EDITION": None,
            "EXPERIENCE": None,
        }
        paginas_por_tipo: dict[str, int] = {
            "BASE_GAME": 0,
            "EDITION": 0,
            "EXPERIENCE": 0,
        }
        inicio_coleta = time.perf_counter()

        print("\nColeta do catálogo Epic:")

        for offer_type in ("BASE_GAME", "EDITION", "EXPERIENCE"):
            pagina = 1
            print(f"\n  Tipo: {offer_type}")

            while True:
                if (
                    max_paginas is not None
                    and paginas_por_tipo[offer_type] >= max_paginas
                ):
                    break

                inicio_pagina = time.perf_counter()
                print(
                    f"    Consultando página {pagina}"
                    + (f"/{max_paginas}" if max_paginas is not None else "")
                    + "...",
                    end="",
                    flush=True,
                )

                dados = self.buscar_pagina(pagina, offer_type=offer_type)
                paginas_por_tipo[offer_type] += 1
                ofertas = dados.get("offers") or []
                totais_por_tipo[offer_type] = dados.get(
                    "total", totais_por_tipo[offer_type]
                )
                todas.extend(ofertas)

                tempo_pagina = time.perf_counter() - inicio_pagina
                total_tipo = totais_por_tipo[offer_type]

                if total_tipo:
                    total_paginas_api = math.ceil(
                        total_tipo / self.LIMITE_PAGINA
                    )
                    percentual = min(
                        100.0,
                        paginas_por_tipo[offer_type] / total_paginas_api * 100,
                    )
                    progresso = (
                        f"{paginas_por_tipo[offer_type]}/{total_paginas_api} "
                        f"({percentual:5.1f}%)"
                    )
                else:
                    progresso = f"{paginas_por_tipo[offer_type]} páginas"

                print(
                    f" ✓ {len(ofertas)} ofertas | "
                    f"acumulado geral: {len(todas)} | "
                    f"{progresso} | {tempo_pagina:.2f}s"
                )

                if not ofertas:
                    break

                if total_tipo is not None:
                    coletadas_tipo = sum(
                        1
                        for oferta in todas
                        if str(oferta.get("offerType") or "").upper() == offer_type
                    )
                    if coletadas_tipo >= total_tipo:
                        break

                if len(ofertas) < self.LIMITE_PAGINA:
                    break

                pagina += 1
                if self.pausa_paginas > 0:
                    time.sleep(self.pausa_paginas)

        tempo_total = time.perf_counter() - inicio_coleta
        print(
            f"\n✓ Coleta concluída: {sum(paginas_por_tipo.values())} páginas, "
            f"{len(todas)} ofertas em {tempo_total:.2f}s"
        )

        descartes: list[dict[str, Any]] = []
        elegiveis: list[dict[str, Any]] = []

        for oferta in todas:
            motivos = self._motivos_descarte(oferta)
            if motivos:
                descartes.append(self._resumo_descarte(oferta, motivos))
            else:
                elegiveis.append(oferta)

        grupos: dict[str, list[dict[str, Any]]] = {}
        for oferta in elegiveis:
            chave = self._chave_deduplicacao(oferta)
            assert chave is not None
            grupos.setdefault(chave, []).append(oferta)

        canonicas = [
            self._escolher_canonica(grupo)
            for grupo in grupos.values()
        ]
        canonicas.sort(key=lambda o: str(o.get("title") or "").casefold())

        quantidade_canonicas = len(canonicas)

        canonicas = [
            oferta
            for oferta in canonicas
            if self._eh_jogo_catalogo(oferta)
        ]

        quantidade_nao_jogos = quantidade_canonicas - len(canonicas)
        duplicatas_removidas = len(elegiveis) - quantidade_canonicas

        sem_page_slug = [
            item for item in descartes if "sem_page_slug" in item["motivos"]
        ]
        sem_namespace = [
            item for item in descartes if "sem_namespace" in item["motivos"]
        ]
        restritos_br = [
            item for item in descartes if "restricao_br" in item["motivos"]
        ]
        exclusoes_manuais = [
            item
            for item in descartes
            if any(
                motivo.startswith("exclusao_manual")
                for motivo in item["motivos"]
            )
        ]

        nomes_base_por_page_slug: dict[str, str] = {}
        for oferta in canonicas:
            if str(oferta.get("offerType") or "").upper() != "BASE_GAME":
                continue
            page_slug = self._extrair_page_slug(oferta)
            nome_base = oferta.get("title")
            if page_slug and nome_base:
                nomes_base_por_page_slug[page_slug] = str(nome_base).strip()

        jogos_por_tipo: dict[str, int] = {}
        for oferta in canonicas:
            tipo = str(oferta.get("offerType") or "UNKNOWN").upper()
            jogos_por_tipo[tipo] = jogos_por_tipo.get(tipo, 0) + 1

        return {
            "total_api": sum(
                valor for valor in totais_por_tipo.values()
                if valor is not None
            ),
            "totais_por_tipo": totais_por_tipo,
            "paginas_consultadas": sum(paginas_por_tipo.values()),
            "paginas_por_tipo": paginas_por_tipo,
            "ofertas_recebidas": len(todas),
            "ofertas_elegiveis": len(elegiveis),
            "descartadas_sem_page_slug": len(sem_page_slug),
            "descartadas_sem_namespace": len(sem_namespace),
            "descartadas_restricao_br": len(restritos_br),
            "descartadas_correcao_manual": len(exclusoes_manuais),
            "duplicatas_removidas": duplicatas_removidas,
            "nao_jogos_removidos": quantidade_nao_jogos,
            "jogos_aproveitaveis": len(canonicas),
            "jogos_por_tipo": jogos_por_tipo,
            "descartados": descartes,
            "jogos": [
                self._normalizar_oferta(o, nomes_base_por_page_slug)
                for o in canonicas
            ],
        }

if __name__ == "__main__":
    resultado = EpicCatalogo().coletar()
    print(f"API total: {resultado['total_api']}")
    print(f"API por tipo: {resultado['totais_por_tipo']}")
    print(f"Páginas: {resultado['paginas_consultadas']}")
    print(f"Páginas por tipo: {resultado['paginas_por_tipo']}")
    print(f"Recebidas: {resultado['ofertas_recebidas']}")
    print(f"Elegíveis: {resultado['ofertas_elegiveis']}")
    print(f"Aproveitáveis: {resultado['jogos_aproveitaveis']}")
    print(f"Jogos por tipo: {resultado['jogos_por_tipo']}")
    print(f"Sem pageSlug: {resultado['descartadas_sem_page_slug']}")
    print(f"Sem namespace: {resultado['descartadas_sem_namespace']}")
    print(f"Restrição BR: {resultado['descartadas_restricao_br']}")
    print(f"Exclusões manuais: {resultado['descartadas_correcao_manual']}")
    print(f"Duplicatas removidas: {resultado['duplicatas_removidas']}")
    print(f"Não-jogos removidos: {resultado['nao_jogos_removidos']}")
