"""
plugins/monster_spawner_plugin/config.py
Default configuration for the Monster Spawner plugin.
"""

DEFAULT_CONFIG = {
    # How often to attempt spawns (in seconds)
    "spawn_interval": 120,
    
    # Maximum monsters per region
    "max_monsters_per_region": 10,
    
    # Chance to spawn a monster on each attempt (0.0-1.0)
    "spawn_chance": 0.3,
    
    # Specific rooms that shouldn't have monsters spawn, even in unsafe regions
    "no_spawn_rooms": [
        "town_square", "tavern", "inn", "shop", "temple", "shrine", "home",
        "general_store", "blacksmith", # Added town shops explicitly
        "farmhouse_yard", "shepherds_hut" # Added specific safe spots
    ],
    
    # *** UPDATED: Weighted monster types by region ***
    "region_monsters": {
        "default": { # Fallback for unlisted regions
            "giant_rat": 5,
            "goblin": 3
        },
        "town": { # Should not spawn due to safe_zone, but define anyway
             "giant_rat": 1 # Maybe a rat occasionally?
        },
        "forest": {
            "wolf": 5,
            "goblin": 3,
            "giant_rat": 2,
            "bandit": 1 # Bandits might hide in forests
        },
        "caves": {
            "giant_rat": 4,
            "goblin": 3,
            "skeleton": 2,
            "troll": 1 # Deeper caves might have trolls
        },
        "ruins": {
            "skeleton": 6,
            "goblin": 2,
            "bandit": 2 # Ruins attract scavengers/bandits
        },
        "mountains": {
            "wolf": 4, # Mountain wolves
            "goblin": 2, # Hardy goblins
            "skeleton": 1 # Perhaps from failed expeditions
            # Add mountain-specific monsters later if created (e.g., "yeti")
        },
        "swamp": {
            "giant_rat": 3, # Swamp rats
            "goblin": 2, # Mire Goblins?
            # Add swamp monsters later (e.g., "giant_leech", "bog_creeper")
            "skeleton": 1 # Lost souls
        },
        "farmland": { # Should be safe if marked, but maybe occasional pests?
            "giant_rat": 2,
            "wolf": 1 # Wolves preying on livestock?
        },
        "foothills": {
            "wolf": 3,
            "goblin": 2,
            "bandit": 1
        },
        "coastal_path": {
            "giant_rat": 2,
             "bandit": 1 # Coastal bandits/pirates nearby
            # Add crab monsters?
        },
        "portbridge": { # If not safe, could have dock rats, smugglers, bandits
             "giant_rat": 4,
             "bandit": 3
             # Add "smuggler" or "pirate" NPC type if distinct from bandit
        }
    },

    # *** UPDATED: Level ranges by region ***
    "region_levels": {
        "default": [1, 2],
        "town": [1, 1], # Low level even if something spawns
        "forest": [1, 4],
        "caves": [2, 6],
        "ruins": [3, 7],
        "mountains": [4, 8],
        "swamp": [2, 5],
        "farmland": [1, 2], # Keep levels low even if unsafe
        "foothills": [2, 4],
        "coastal_path": [1, 3],
        "portbridge": [1, 5] # Wider range for a port town
    },
    
    # Debug mode
    "debug": False
}