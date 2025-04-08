# magic/spell_registry.py
"""
Registry of all available spells in the game.
"""
from typing import Dict, Optional
from magic.spell import Spell

SPELL_REGISTRY: Dict[str, Spell] = {}

def register_spell(spell: Spell):
    """Adds a spell to the registry."""
    if spell.spell_id in SPELL_REGISTRY:
        print(f"Warning: Overwriting spell with ID {spell.spell_id}")
    SPELL_REGISTRY[spell.spell_id] = spell

def get_spell(spell_id: str) -> Optional[Spell]:
    """Retrieves a spell definition from the registry."""
    return SPELL_REGISTRY.get(spell_id)

def get_spell_by_name(spell_name: str) -> Optional[Spell]:
    """Finds a spell by its name (case-insensitive)."""
    search_name = spell_name.lower()
    for spell in SPELL_REGISTRY.values():
        if spell.name.lower() == search_name:
            return spell
    return None

# --- Define Initial Spells ---

register_spell(Spell(
    spell_id="magic_missile",
    name="Magic Missile",
    description="A bolt of pure arcane energy strikes your target.",
    mana_cost=5,
    cooldown=3.0,
    effect_type="damage",
    effect_value=8,
    target_type="enemy",
    cast_message="{caster_name} launches a shimmering bolt!",
    hit_message="{caster_name}'s missile hits {target_name} for {value} arcane damage!",
    level_required=1
))

register_spell(Spell(
    spell_id="minor_heal",
    name="Minor Heal",
    description="Soothes minor wounds with gentle restorative magic.",
    mana_cost=8,
    cooldown=6.0,
    effect_type="heal",
    effect_value=15,
    target_type="friendly", # Can target self or others
    cast_message="{caster_name} channels soothing energy.",
    heal_message="{caster_name} heals {target_name} for {value} health!",
    self_heal_message="A soothing warmth spreads through you, restoring {value} health!", # <<< Example custom self-heal message
    level_required=1
))

register_spell(Spell(
    spell_id="fireball",
    name="Fireball",
    description="Hurls a ball of roaring flame at the target.",
    mana_cost=15,
    cooldown=8.0,
    effect_type="damage",
    effect_value=20,
    target_type="enemy",
    cast_message="{caster_name} summons a sphere of fire!",
    hit_message="A fireball engulfs {target_name}, dealing {value} fire damage!",
    level_required=3
))

register_spell(Spell(
    spell_id="zap", # Simple monster spell
    name="Zap",
    description="A weak jolt of electricity.",
    mana_cost=0, # Monsters might not use mana
    cooldown=5.0,
    effect_type="damage",
    effect_value=5,
    target_type="enemy",
    cast_message="{caster_name} crackles with energy!",
    hit_message="{caster_name} zaps {target_name} for {value} damage!",
    level_required=1
))

register_spell(Spell(
    spell_id="raise_skeleton",
    name="Raise Skeleton",
    description="Animates inert bones into a temporary skeletal servant.",
    mana_cost=1,       # Higher cost for summoning
    cooldown=1.0,      # Longer cooldown
    effect_type="summon", # *** NEW Effect Type ***
    target_type="self", # Typically cast by the player on themselves/area
    cast_message="{caster_name} chants words of necromancy...",
    level_required=5,   # Example level requirement
    # --- NEW Properties for Summoning ---
    summon_template_id="skeleton_minion", # ID of the NPC template to summon
    summon_duration=500.0,               # How long it lasts in seconds
    max_summons=10                       # How many of *this specific* summon can be active
))


# Add more spells here...
