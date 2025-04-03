# magic/spell.py
"""
Defines the structure for spells in the game.
"""
from typing import Optional, Dict, Any

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
                 level_required: int = 1):

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
        return {
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
        }

    # No from_dict needed if spells are defined in code registry
