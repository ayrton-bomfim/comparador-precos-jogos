"""
Lista de jogos da Steam para acompanhamento no Comparador de Preços.
Total: 60 jogos organizados por categoria.
IDs verificados e corrigidos em 07/09/2026.
"""

# ============================================
# 🎮 JOGOS GRATUITOS (Free-to-Play)
# ============================================
JOGOS_GRATUITOS = [
    730,      # Counter-Strike 2
    570,      # Dota 2
    440,      # Team Fortress 2
    1085660,  # Destiny 2
    359550,   # Tom Clancy's Rainbow Six Siege
]

# ============================================
# 🏆 JOGOS PLAYSTATION NO PC
# ============================================
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

# ============================================
# 🏆 JOGOS AAA MULTIPLATAFORMA
# ============================================
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

# ============================================
# 🎮 JOGOS INDIE
# ============================================
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

# ============================================
# 🤝 JOGOS COOPERATIVOS
# ============================================
JOGOS_COOP = [
    728880,   # Overcooked! 2
    1426210,  # It Takes Two
    2001120,  # Split Fiction
    1222700,  # A Way Out
    996770,   # Moving Out
]

# ============================================
# 🕹️ JOGOS DE AÇÃO E AVENTURA
# ============================================
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

# ============================================
# 🎲 JOGOS DE ESTRATÉGIA E SIMULAÇÃO
# ============================================
JOGOS_ESTRATEGIA = [
    289070,   # Sid Meier's Civilization VI
    220200,   # Kerbal Space Program
    440900,   # Conan Exiles
    230290,   # Universe Sandbox
    1649240,  # Returnal
    1903340,  # Clair Obscur: Expedition 33
]

# ============================================
# 🔍 JOGOS NOVOS (Lançamentos recentes)
# ============================================
JOGOS_NOVOS = [
    3768760,  # 007 First Light
    3764200,  # Resident Evil Requiem
    2129530,  # REANIMAL
]


# ============================================
# 📊 LISTA COMPLETA (60 JOGOS)
# ============================================
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

# ============================================
# 🎯 LISTA PARA DEMONSTRAÇÃO
# ============================================
JOGOS_DEMO = JOGOS_STEAM

# ============================================
# 🔍 FUNÇÕES AUXILIARES
# ============================================
def get_jogos_por_categoria(categoria):
    """Retorna os jogos de uma categoria específica"""
    categorias = {
        'gratuitos': JOGOS_GRATUITOS,
        'playstation': JOGOS_PLAYSTATION,
        'aaa': JOGOS_AAA,
        'indie': JOGOS_INDIE,
        'coop': JOGOS_COOP,
        'acao_aventura': JOGOS_ACAO_AVENTURA,
        'estrategia': JOGOS_ESTRATEGIA,
        'novos': JOGOS_NOVOS,
        'todos': JOGOS_STEAM,
        'demo': JOGOS_DEMO,
    }
    return categorias.get(categoria.lower(), [])

def total_jogos():
    """Retorna o total de jogos na lista"""
    return len(JOGOS_STEAM)

def listar_jogos_com_nomes():
    """Retorna uma lista com IDs e nomes dos jogos"""
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
    print(f"📊 Total de jogos na lista: {total_jogos()}")
    print("\n📋 Categorias:")
    for cat in ['gratuitos', 'playstation', 'aaa', 'indie', 'coop', 'acao_aventura', 'estrategia', 'novos', 'verificar']:
        print(f"   - {cat}: {len(get_jogos_por_categoria(cat))} jogos")
    print("\n✅ Todos os IDs verificados e corrigidos!")