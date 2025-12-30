# engine/magic/debug_effects.py
"""
A registry of pre-defined status effects for easy application via debug commands.
"""

DEBUG_EFFECTS = {
    # --- Harmful ---
    "debug_poison": {
        "type": "dot",
        "name": "Debug Poison",
        "base_duration": 30.0,
        "damage_per_tick": 5,
        "tick_interval": 3.0,
        "damage_type": "poison"
    },
    "debug_weaken": {
        "type": "stat_mod",
        "name": "Weaken",
        "base_duration": 20.0,
        "modifiers": {"strength": -5}
    },
    "debug_stun": {
        "type": "control",
        "name": "Stun",
        "base_duration": 9.0,
        # No other properties needed, the name "Stun" is the key
    },

    # --- Beneficial ---
    "debug_regen": {
        "type": "hot",
        "name": "Regeneration",
        "base_duration": 30.0,
        "heal_per_tick": 5,
        "tick_interval": 3.0,
    },
    "debug_haste": {
        "type": "stat_mod",
        "name": "Haste",
        "base_duration": 20.0,
        "modifiers": {"agility": 10}
    }
}