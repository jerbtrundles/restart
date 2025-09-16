# magic/spell.py
"""
Defines the structure for spells in the game.
"""
from typing import Optional, Dict, Any

from config import EFFECT_DEFAULT_TICK_INTERVAL, EFFECT_POISON_DAMAGE_TYPE

class Spell:
    def __init__(self,
                 spell_id: str,
                 name: str,
                 description: str,
                 mana_cost: int = 10,
                 cooldown: float = 5.0, # Cooldown in seconds
                 effect_type: str = "damage", # e.g., damage, heal, buff, debuff
                 effect_value: int = 10, # Amount of damage/healing, etc.
                 target_type: str = "enemy", # e.g., self, enemy, friendly, area_enemy
                 cast_message: str = "You cast {spell_name}!",
                 hit_message: str = "{caster_name} hits {target_name} with {spell_name} for {value} points!",
                 heal_message: str = "{caster_name} heals {target_name} with {spell_name} for {value} points!",
                 self_heal_message="You heal yourself for {value} health!",
                 level_required: int = 1,
                 damage_type: str = "nonelemental", # Added for damage type consistency
                 summon_template_id: Optional[str] = None,
                 summon_duration: float = 0.0,
                 max_summons: int = 0,
                 # --- NEW: Add DoT parameters ---
                 dot_name: Optional[str] = None,           # Name of the DoT effect (e.g., "Poison", "Burning")
                 dot_duration: float = 0.0,                # Base duration of the DoT
                 dot_damage_per_tick: int = 0,             # Damage applied each tick
                 dot_tick_interval: float = EFFECT_DEFAULT_TICK_INTERVAL, # Time between ticks
                 dot_damage_type: str = EFFECT_POISON_DAMAGE_TYPE       # Damage type of the DoT
                 # --- END NEW ---
    ):
        self.spell_id = spell_id
        self.name = name
        self.description = description
        self.mana_cost = mana_cost
        self.cooldown = cooldown
        self.effect_type = effect_type
        self.effect_value = effect_value
        self.target_type = target_type # 'self', 'enemy', 'friendly'
        self.cast_message = cast_message
        self.hit_message = hit_message
        self.heal_message = heal_message
        self.self_heal_message = self_heal_message
        self.level_required = level_required
        self.damage_type = damage_type

        # --- Store Summoning Attributes ---
        self.summon_template_id = summon_template_id
        self.summon_duration = summon_duration
        self.max_summons = max_summons

        # --- NEW: Store DoT Attributes ---
        self.dot_name = dot_name
        self.dot_duration = dot_duration
        self.dot_damage_per_tick = dot_damage_per_tick
        self.dot_tick_interval = dot_tick_interval
        self.dot_damage_type = dot_damage_type
        # --- END NEW ---


    def can_cast(self, caster) -> bool:
        """Check if the caster meets level requirements."""
        caster_level = getattr(caster, 'level', 1)
        return caster_level >= self.level_required

    def format_cast_message(self, caster) -> str:
        return self.cast_message.format(caster_name=getattr(caster, 'name', 'Someone'), spell_name=self.name)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize spell definition (useful for saving maybe, but mostly for registry)."""
        # Generally, spells are definitions, not saved state.
        # This might be useful if you load spells from JSON later.
        data = {
            "spell_id": self.spell_id,
            "name": self.name,
            "description": self.description,
            "mana_cost": self.mana_cost,
            "cooldown": self.cooldown,
            "effect_type": self.effect_type,
            "effect_value": self.effect_value,
            "target_type": self.target_type,
            "cast_message": self.cast_message,
            "hit_message": self.hit_message,
            "heal_message": self.heal_message,
            "self_heal_message": self.self_heal_message,
            "level_required": self.level_required,
            "damage_type": self.damage_type, # Save damage type
            "summon_template_id": self.summon_template_id,
            "summon_duration": self.summon_duration,
            "max_summons": self.max_summons,
            # --- NEW: Add DoT properties to serialization ---
            "dot_name": self.dot_name,
            "dot_duration": self.dot_duration,
            "dot_damage_per_tick": self.dot_damage_per_tick,
            "dot_tick_interval": self.dot_tick_interval,
            "dot_damage_type": self.dot_damage_type,
            # --- END NEW ---
        }
        return {k: v for k, v in data.items() if v is not None}

    # No from_dict needed if spells are defined in code registry
