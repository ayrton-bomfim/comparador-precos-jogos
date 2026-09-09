"""
Lista de jogos da Steam para acompanhamento no Comparador de Preços.

Total: 60 jogos organizados por categoria.
IDs verificados e corrigidos em 07/09/2026.
"""

# =============================================================================
# JOGOS GRATUITOS (Free-to-Play)
# =============================================================================
JOGOS_GRATUITOS = [
    730,      # Counter-Strike 2
    570,      # Dota 2
    440,      # Team Fortress 2
    1085660,  # Destiny 2
    359550,   # Tom Clancy's Rainbow Six Siege
]

# =============================================================================
# JOGOS PLAYSTATION NO PC
# =============================================================================
JOGOS_PLAYSTATION = [
    1593500,  # God of War
    2322010,  # God of War Ragnarök
    1817070,  # Marvel's Spider-Man Remastered
    2651280,  # Marvel's Spider-Man 2
    1817190,  # Marvel's Spider-Man: Miles Morales
    2215430,  # Ghost of Tsushima: Director's Cut
    1659420,  # UNCHARTED: Legacy of Thieves Collection
    2420110,  # Horizon Forbidden West - Complete Edition
    3489700,  # Stellar Blade
    2561580,  # Horizon Zero Dawn Remastered
    2172010,  # Until Dawn
]

# =============================================================================
# JOGOS AAA MULTIPLATAFORMA
# =============================================================================
JOGOS_AAA = [
    3240220,  # Grand Theft Auto V Enhanced
    1174180,  # Red Dead Redemption 2
    1091500,  # Cyberpunk 2077
    252490,   # Rust
    1245620,  # Elden Ring
    990080,   # Hogwarts Legacy
    1086940,  # Baldur's Gate 3
    1716740,  # Starfield
    292030,   # The Witcher 3: Wild Hunt
    1774580,  # STAR WARS Jedi: Survivor
    2124490,  # SILENT HILL 2
]

# =============================================================================
# JOGOS INDIE
# =============================================================================
JOGOS_INDIE = [
    1868140,  # DAVE THE DIVER
    264710,   # Subnautica
    304430,   # INSIDE
    1145360,  # Hades
    367520,   # Hollow Knight
    413150,   # Stardew Valley
    504230,   # Celeste
    588650,   # Dead Cells
    1145350,  # Hades II
]

# =============================================================================
# JOGOS COOPERATIVOS
# =============================================================================
JOGOS_COOP = [
    728880,   # Overcooked! 2
    1426210,  # It Takes Two
    2001120,  # Split Fiction
    1222700,  # A Way Out
    996770,   # Moving Out
]

# =============================================================================
# JOGOS DE ACAO E AVENTURA
# =============================================================================
JOGOS_ACAO_AVENTURA = [
    203160,   # Tomb Raider GOTY Edition
    391220,   # Rise of the Tomb Raider
    750920,   # Shadow of the Tomb Raider
    1030840,  # Mafia: Definitive Edition
    238320,   # Outlast
    414700,   # Outlast 2
    447040,   # Watch Dogs 2
    239140,   # Dying Light
    1182900,  # A Plague Tale: Requiem
    536270,   # Ancestors: The Humankind Odyssey
]

# =============================================================================
# JOGOS DE ESTRATEGIA E SIMULACAO
# =============================================================================
JOGOS_ESTRATEGIA = [
    289070,   # Sid Meier's Civilization VI
    220200,   # Kerbal Space Program
    440900,   # Conan Exiles
    230290,   # Universe Sandbox
    1649240,  # Returnal
    1903340,  # Clair Obscur: Expedition 33
]

# =============================================================================
# JOGOS NOVOS (Lancamentos recentes)
# =============================================================================
JOGOS_NOVOS = [
    3768760,  # 007 First Light
    3764200,  # Resident Evil Requiem
    2129530,  # REANIMAL
]

# =============================================================================
# LISTA COMPLETA (60 JOGOS)
# =============================================================================
JOGOS_STEAM = (
    JOGOS_GRATUITOS +
    JOGOS_PLAYSTATION +
    JOGOS_AAA +
    JOGOS_INDIE +
    JOGOS_COOP +
    JOGOS_ACAO_AVENTURA +
    JOGOS_ESTRATEGIA +
    JOGOS_NOVOS
)

# =============================================================================
# MAPEAMENTO STEAM ID -> EPIC SLUG
# =============================================================================
STEAM_TO_EPIC = {
    # Jogos Gratuitos
    730: None,   # Counter-Strike 2 - Exclusivo Steam
    570: None,   # Dota 2 - Exclusivo Steam
    440: None,   # Team Fortress 2 - Exclusivo Steam
    1085660: "destiny-2",
    359550: "rainbow-six-siege-x",

    # Jogos PlayStation
    1593500: "god-of-war",
    2322010: "god-of-war-ragnarok-3ca641",
    1817070: "marvels-spider-man-remastered",
    2651280: "marvels-spider-man-2",
    1817190: "marvels-spider-man-miles-morales",
    2215430: "ghost-of-tsushima",
    1659420: "uncharted-legacy-of-thieves-collection",
    2420110: "horizon-forbidden-west-complete-edition",
    3489700: "stellar-blade-fa21c3",
    2561580: "horizon-zero-dawn-remastered",
    2172010: "until-dawn",

    # Jogos AAA
    3240220: "grand-theft-auto-v",
    1174180: "red-dead-redemption-2",
    1091500: "cyberpunk-2077",
    252490: None,   # Rust - Exclusivo Steam
    1245620: None,  # Elden Ring - Exclusivo Steam
    990080: "hogwarts-legacy",
    1086940: None,  # Baldur's Gate 3 - Exclusivo Steam
    1716740: None,  # Starfield - Exclusivo Steam
    292030: "the-witcher-3-wild-hunt",
    1774580: "star-wars-jedi-survivor",
    2124490: "silent-hill-2-4542c7",

    # Jogos Indie
    1868140: "dave-the-diver-ed092a",
    264710: "subnautica",
    304430: "inside",
    1145360: "hades",
    367520: None,   # Hollow Knight - Exclusivo Steam
    413150: None,   # Stardew Valley - Exclusivo Steam
    504230: "celeste",
    588650: "dead-cells",
    1145350: "hades-ii",

    # Jogos Cooperativos
    728880: "overcooked-2",
    1426210: "it-takes-two",
    2001120: "split-fiction",
    1222700: "a-way-out-635680",
    996770: "moving-out",

    # Jogos de Acao e Aventura
    203160: "tomb-raider",
    391220: "rise-of-the-tomb-raider",
    750920: "shadow-of-the-tomb-raider",
    1030840: "mafia-definitive-edition",
    238320: "outlast",
    414700: "outlast-2",
    447040: "watch-dogs-2",
    239140: "dying-light",
    1182900: "a-plague-tale-requiem",
    536270: "ancestors",

    # Jogos de Estrategia e Simulacao
    289070: "sid-meiers-civilization-vi",
    220200: "kerbal-space-program",
    440900: "conan-exiles",
    230290: "universe-sandbox",
    1649240: "returnal",
    1903340: "expedition-33-b3240d",

    # Jogos Novos
    3768760: "007-first-light-182cea",
    3764200: "resident-evil-requiem-4ead6d",
    2129530: "reanimal",
}

# =============================================================================
# FUNCOES AUXILIARES
# =============================================================================

def get_jogos_por_categoria(categoria):
    """
    Retorna os jogos de uma categoria especifica.

    Args:
        categoria (str): Nome da categoria.

    Returns:
        list: Lista de IDs dos jogos da categoria.
    """
    categorias = {
        "gratuitos": JOGOS_GRATUITOS,
        "playstation": JOGOS_PLAYSTATION,
        "aaa": JOGOS_AAA,
        "indie": JOGOS_INDIE,
        "coop": JOGOS_COOP,
        "acao_aventura": JOGOS_ACAO_AVENTURA,
        "estrategia": JOGOS_ESTRATEGIA,
        "novos": JOGOS_NOVOS,
        "todos": JOGOS_STEAM,
        "demo": JOGOS_STEAM,
    }
    return categorias.get(categoria.lower(), [])


def total_jogos():
    """
    Retorna o total de jogos na lista.

    Returns:
        int: Quantidade total de jogos.
    """
    return len(JOGOS_STEAM)


def get_epic_slug(steam_id):
    """
    Retorna o slug da Epic para um dado Steam ID.

    Args:
        steam_id (int): Identificador do jogo na Steam.

    Returns:
        str or None: Slug da Epic, ou None se nao disponivel.
    """
    return STEAM_TO_EPIC.get(steam_id)


def get_steam_id_from_epic(slug):
    """
    Retorna o Steam ID a partir de um slug da Epic.

    Args:
        slug (str): Slug do jogo na Epic Games Store.

    Returns:
        int or None: Steam ID correspondente, ou None se nao encontrado.
    """
    for steam_id, epic_slug in STEAM_TO_EPIC.items():
        if epic_slug == slug:
            return steam_id
    return None


def listar_jogos_com_nomes():
    """
    Retorna uma lista com IDs e nomes dos jogos para referencia.

    Returns:
        list: Lista de dicionarios com 'id' e 'nome'.
    """
    nomes = {
        730: "Counter-Strike 2",
        570: "Dota 2",
        440: "Team Fortress 2",
        1085660: "Destiny 2",
        359550: "Rainbow Six Siege",
        1593500: "God of War",
        2322010: "God of War Ragnarök",
        1817070: "Marvel's Spider-Man Remastered",
        2651280: "Marvel's Spider-Man 2",
        1817190: "Marvel's Spider-Man: Miles Morales",
        2215430: "Ghost of Tsushima: Director's Cut",
        1659420: "UNCHARTED: Legacy of Thieves Collection",
        2420110: "Horizon Forbidden West - Complete Edition",
        3489700: "Stellar Blade",
        3240220: "Grand Theft Auto V Enhanced",
        1174180: "Red Dead Redemption 2",
        1091500: "Cyberpunk 2077",
        252490: "Rust",
        1245620: "Elden Ring",
        990080: "Hogwarts Legacy",
        1086940: "Baldur's Gate 3",
        1716740: "Starfield",
        292030: "The Witcher 3: Wild Hunt",
        1774580: "STAR WARS Jedi: Survivor",
        2124490: "SILENT HILL 2",
        1868140: "DAVE THE DIVER",
        264710: "Subnautica",
        304430: "INSIDE",
        1145360: "Hades",
        367520: "Hollow Knight",
        413150: "Stardew Valley",
        504230: "Celeste",
        588650: "Dead Cells",
        728880: "Overcooked! 2",
        1426210: "It Takes Two",
        2001120: "Split Fiction",
        1222700: "A Way Out",
        996770: "Moving Out",
        203160: "Tomb Raider GOTY Edition",
        391220: "Rise of the Tomb Raider",
        750920: "Shadow of the Tomb Raider",
        1030840: "Mafia: Definitive Edition",
        238320: "Outlast",
        414700: "Outlast 2",
        447040: "Watch Dogs 2",
        239140: "Dying Light",
        1182900: "A Plague Tale: Requiem",
        536270: "Ancestors: The Humankind Odyssey",
        289070: "Sid Meier's Civilization VI",
        220200: "Kerbal Space Program",
        440900: "Conan Exiles",
        230290: "Universe Sandbox",
        1649240: "Returnal",
        1903340: "Clair Obscur: Expedition 33",
        3768760: "007 First Light",
        3764200: "Resident Evil Requiem",
        2129530: "REANIMAL",
        2561580: "Horizon Zero Dawn Remastered",
        2172010: "Until Dawn",
        1145350: "Hades II",
    }
    return [{"id": id_, "nome": nomes.get(id_, "Desconhecido")} for id_ in JOGOS_STEAM]


if __name__ == "__main__":
    print(f"Total de jogos na lista: {total_jogos()}")
    print("\nCategorias:")
    for cat in [
        "gratuitos", "playstation", "aaa", "indie",
        "coop", "acao_aventura", "estrategia", "novos"
    ]:
        print(f"  - {cat}: {len(get_jogos_por_categoria(cat))} jogos")

    mapeados = sum(1 for slug in STEAM_TO_EPIC.values() if slug is not None)
    print(f"\nMapeamento Epic: {mapeados}/{total_jogos()} jogos")

    exclusivos = [id_ for id_, slug in STEAM_TO_EPIC.items() if slug is None]
    if exclusivos:
        print("\nJogos exclusivos Steam (nao disponiveis na Epic):")
        nomes = {
            730: "Counter-Strike 2",
            570: "Dota 2",
            440: "Team Fortress 2",
            252490: "Rust",
            1245620: "Elden Ring",
            1086940: "Baldur's Gate 3",
            1716740: "Starfield",
            367520: "Hollow Knight",
            413150: "Stardew Valley",
        }
        for id_ in exclusivos:
            print(f"  - {nomes.get(id_, 'Desconhecido')} (ID: {id_})")

    print("\nTodos os IDs verificados e corrigidos.")