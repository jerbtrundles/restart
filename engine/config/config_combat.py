# engine/config/config_combat.py
"""
Configuration for shared combat mechanics, damage calculations, and status effects.
Loads dynamic elemental data from JSON.
"""
import json
import os
from engine.config.config_game import DATA_DIR

# --- Shared Combat Mechanics ---
MIN_HIT_CHANCE = 0.05
MAX_HIT_CHANCE = 0.95
MIN_XP_GAIN = 1
MIN_ATTACK_COOLDOWN = 0.5
HIT_CHANCE_AGILITY_FACTOR = 0.02
MINIMUM_DAMAGE_TAKEN = 1

# --- Level Difference Modifiers ---
LEVEL_DIFF_COMBAT_MODIFIERS = {
    "purple": (0.70, 0.60, 2.50),
    "red":    (0.85, 0.75, 1.75),
    "orange": (0.95, 0.90, 1.25),
    "yellow": (1.00, 1.00, 1.00),
    "blue":   (1.05, 1.10, 0.80),
    "green":  (1.15, 1.25, 0.50),
    "gray":   (1.25, 1.40, 0.20),
}

# --- Experience Point Calculation ---
XP_GAIN_HEALTH_DIVISOR = 5
XP_GAIN_LEVEL_MULTIPLIER = 5
SPELL_XP_GAIN_HEALTH_DIVISOR = 4
SPELL_XP_GAIN_LEVEL_MULTIPLIER = 6

# --- Magic & Spell Effects ---
SPELL_DAMAGE_VARIATION_FACTOR = 0.1
MINIMUM_SPELL_EFFECT_VALUE = 1
SPELL_EFFECT_TYPES = ["damage", "heal", "buff", "debuff", "summon", "cleanse", "remove_curse", "life_tap"]

# --- Status Effect Settings ---
EFFECT_DEFAULT_TICK_INTERVAL = 3.0
EFFECT_POISON_DAMAGE_TYPE = "poison"

# --- DYNAMIC ELEMENTAL LOADING ---
def _load_elemental_config():
    path = os.path.join(DATA_DIR, "combat", "elements.json")
    defaults = {
        "valid_damage_types": ["physical", "magical"],
        "default_damage_type": "magical",
        "elemental_opposites": {},
        "flavor_text": {"default": {"weakness": "Hits weak!", "resistance": "Resisted.", "strong_resistance": "Strongly resisted."}},
        "hazards": {"mapping": {}, "flavor": {}}
    }
    
    if not os.path.exists(path):
        print(f"Warning: Combat config not found at {path}. Using defaults.")
        return defaults

    try:
        with open(path, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"Error loading combat config: {e}")
        return defaults

_elemental_data = _load_elemental_config()

# Exported Constants
VALID_DAMAGE_TYPES = _elemental_data.get("valid_damage_types", ["physical"])
SPELL_DEFAULT_DAMAGE_TYPE = _elemental_data.get("default_damage_type", "magical")
ELEMENTAL_OPPOSITES = _elemental_data.get("elemental_opposites", {})
DAMAGE_TYPE_FLAVOR_TEXT = _elemental_data.get("flavor_text", {})

# Hazard Configuration
HAZARD_TYPE_MAP = _elemental_data.get("hazards", {}).get("mapping", {})
HAZARD_FLAVOR_TEXT = _elemental_data.get("hazards", {}).get("flavor", {})