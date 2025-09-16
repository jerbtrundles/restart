# config/config_combat.py
"""
Configuration for shared combat mechanics, damage calculations, and status effects.
"""

# --- Shared Combat Mechanics ---
MIN_HIT_CHANCE = 0.05
MAX_HIT_CHANCE = 0.95
MIN_XP_GAIN = 1
MIN_ATTACK_COOLDOWN = 0.5
HIT_CHANCE_AGILITY_FACTOR = 0.02
MINIMUM_DAMAGE_TAKEN = 1

# --- Level Difference Modifiers ---
LEVEL_DIFF_COMBAT_MODIFIERS = {
    # Tier:   (Hit Chance Multiplier, Damage Dealt Multiplier, XP Multiplier)
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
SPELL_DEFAULT_DAMAGE_TYPE = "magical"
SPELL_DAMAGE_VARIATION_FACTOR = 0.1
MINIMUM_SPELL_EFFECT_VALUE = 1
SPELL_EFFECT_TYPES = ["damage", "heal", "buff", "debuff", "summon"]

# --- Status Effect Settings ---
EFFECT_DEFAULT_TICK_INTERVAL = 3.0
EFFECT_POISON_DAMAGE_TYPE = "poison"
EFFECT_FIRE_DAMAGE_TYPE = "fire"
EFFECT_COLD_DAMAGE_TYPE = "cold"
EFFECT_ELECTRIC_DAMAGE_TYPE = "electric"
EFFECT_DISEASE_DAMAGE_TYPE = "disease"