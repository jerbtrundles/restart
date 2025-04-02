"""
Default configuration for the Monster Spawner plugin.
"""

DEFAULT_CONFIG = {
    # How often to attempt spawns (in seconds)
    "spawn_interval": 120,
    
    # Maximum monsters per region
    "max_monsters_per_region": 10,
    
    # Chance to spawn a monster on each attempt (0.0-1.0)
    "spawn_chance": 0.3,
    
    # Rooms that shouldn't have monsters spawn in them
    "no_spawn_rooms": ["town_square", "tavern", "inn", "shop", "temple", "shrine", "home"],
    
    # Weighted monster types by region (region_id -> monster types)
    "region_monsters": {
        "default": {
            "goblin": 3,
            "wolf": 3,
            "giant_rat": 2,
            "skeleton": 1
        },
        "forest": {
            "wolf": 5,
            "goblin": 2,
            "giant_rat": 1
        },
        "cave": {
            "giant_rat": 4,
            "goblin": 2,
            "skeleton": 3
        },
        "dungeon": {
            "skeleton": 5,
            "goblin": 2,
            "troll": 1
        }
    },
    
    # Level ranges by region (region_id -> [min, max])
    "region_levels": {
        "default": [1, 3],
        "forest": [1, 4],
        "cave": [2, 5],
        "dungeon": [4, 8]
    },
    
    # Debug mode
    "debug": False
}