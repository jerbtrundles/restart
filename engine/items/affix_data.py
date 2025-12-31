"""
Definitions for procedural item affixes (Prefixes and Suffixes).
"""

# Allowed Types: "Weapon", "Armor", "Jewelry" (Neck/Ring implied by slot), "All"

PREFIXES = {
    "Sharp": {
        "allowed_types": ["Weapon"],
        "level_min": 1,
        "modifiers": {"damage": 2}, # Flat increase to item stat
        "value_mult": 1.2
    },
    "Jagged": {
        "allowed_types": ["Weapon"],
        "level_min": 3,
        "modifiers": {"damage": 5},
        "value_mult": 1.5
    },
    "Masterwork": {
        "allowed_types": ["Weapon", "Armor"],
        "level_min": 5,
        "modifiers": {"damage": 3, "defense": 3},
        "value_mult": 2.0
    },
    "Heavy": {
        "allowed_types": ["Armor"],
        "level_min": 1,
        "modifiers": {"defense": 2, "weight": 2.0},
        "value_mult": 1.1
    },
    "Reinforced": {
        "allowed_types": ["Armor"],
        "level_min": 3,
        "modifiers": {"defense": 5, "durability": 20},
        "value_mult": 1.4
    },
    "Lightweight": {
        "allowed_types": ["Armor", "Weapon"],
        "level_min": 1,
        "modifiers": {"weight": -1.0}, # Negative reduces weight
        "value_mult": 1.1
    }
}

SUFFIXES = {
    "of the Bear": {
        "allowed_types": ["Armor", "Weapon"],
        "level_min": 1,
        "equip_stats": {"strength": 2, "constitution": 2}, # Player stats when equipped
        "value_mult": 1.3
    },
    "of the Owl": {
        "allowed_types": ["Armor", "Weapon"],
        "level_min": 1,
        "equip_stats": {"wisdom": 2, "intelligence": 2},
        "value_mult": 1.3
    },
    "of the Tiger": {
        "allowed_types": ["Weapon"],
        "level_min": 3,
        "equip_stats": {"strength": 3, "agility": 3},
        "value_mult": 1.5
    },
    "of Thorns": {
        "allowed_types": ["Armor"],
        "level_min": 5,
        "equip_stats": {"defense": 2}, 
        "value_mult": 1.4
    },
    "of Vampirism": {
        "allowed_types": ["Weapon"],
        "level_min": 10,
        "equip_buff": "Vampirism",
        "value_mult": 3.0
    },
    "of the Void": {
        "allowed_types": ["Weapon"],
        "level_min": 5,
        "equip_stats": {"spell_power": 5},
        "value_mult": 2.0
    }
}