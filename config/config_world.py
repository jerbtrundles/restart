# config/config_world.py
"""
Configuration for the game world, including simulation, spawning, and factions.
"""

# --- World Settings ---
WORLD_UPDATE_INTERVAL = 0.5

# --- Monster Spawner Settings ---
SPAWN_INTERVAL_SECONDS = 100.0
SPAWN_CHANCE_PER_TICK = 0.1
SPAWN_ROOMS_PER_MONSTER = 5
SPAWN_MIN_MONSTERS_PER_REGION = 0
SPAWN_MAX_MONSTERS_PER_REGION_CAP = 10
SPAWN_NO_SPAWN_ROOM_KEYWORDS = [
    "town_square", "tavern", "inn", "shop", "temple", "shrine", "home",
    "general_store", "blacksmith", "farmhouse_yard", "shepherds_hut"
]
SPAWN_DEBUG = False

# --- Faction Settings ---
FACTIONS = ["player", "friendly", "neutral", "hostile", "player_minion"]
FACTION_RELATIONSHIP_MATRIX = {
    "player": {
        "player": 100, "player_minion": 100, "friendly": 100,
        "neutral": 0, "hostile": -100
    },
    "player_minion": {
        "player": 100, "player_minion": 100, "friendly": 100,
        "neutral": 0, "hostile": -100
    },
    "friendly": {
        "player": 100, "player_minion": 100, "friendly": 100,
        "neutral": 0, "hostile": -100
    },
    "neutral": {
        "player": 0, "player_minion": 0, "friendly": 0,
        "neutral": 0, "hostile": 0
    },
    "hostile": {
        "player": -100, "player_minion": -100, "friendly": -100,
        "neutral": -100, "hostile": 0
    }
}