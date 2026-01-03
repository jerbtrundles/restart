# engine/magic/spell.py
"""
Defines the structure for spells in the game.
"""
from typing import Optional, Dict, Any, List

from engine.config import EFFECT_DEFAULT_TICK_INTERVAL, EFFECT_POISON_DAMAGE_TYPE

class Spell:
    def __init__(self,
                 spell_id: str,
                 name: str,
                 description: str,
                 mana_cost: int = 10,
                 cooldown: float = 5.0,
                 # Legacy Single Effect Fields
                 effect_type: Optional[str] = None,
                 effect_value: int = 0,
                 damage_type: str = "magical",
                 # New Multi-Effect Support
                 effects: Optional[List[Dict[str, Any]]] = None,
                 
                 target_type: str = "enemy",
                 cast_message: str = "You cast {spell_name}!",
                 hit_message: str = "{caster_name} hits {target_name} with {spell_name} for {value} points!",
                 heal_message: str = "{caster_name} heals {target_name} with {spell_name} for {value} points!",
                 self_heal_message="You heal yourself for {value} health!",
                 level_required: int = 1,
                 
                 summon_template_id: Optional[str] = None,
                 summon_duration: float = 0.0,
                 max_summons: int = 0,
                 
                 # Legacy Dot fields
                 dot_name: Optional[str] = None,
                 dot_duration: float = 0.0,
                 dot_damage_per_tick: int = 0,
                 dot_tick_interval: float = EFFECT_DEFAULT_TICK_INTERVAL,
                 dot_damage_type: str = EFFECT_POISON_DAMAGE_TYPE,
                 
                 effect_data: Optional[Dict[str, Any]] = None,
                 **kwargs
    ):
        self.spell_id = spell_id
        self.name = name
        self.description = description
        self.mana_cost = mana_cost
        self.cooldown = cooldown
        self.target_type = target_type
        self.cast_message = cast_message
        self.hit_message = hit_message
        self.heal_message = heal_message
        self.self_heal_message = self_heal_message
        self.level_required = level_required
        self.summon_template_id = summon_template_id
        self.summon_duration = summon_duration
        
        # --- Normalize Effects List ---
        if effects:
            self.effects = effects
        else:
            # Construct a legacy effect payload
            legacy_effect = {
                "type": effect_type or "damage",
                "value": effect_value,
                "damage_type": damage_type,
                "summon_template_id": summon_template_id,
                "summon_duration": summon_duration,
                "max_summons": max_summons,
                "dot_name": dot_name,
                "dot_duration": dot_duration,
                "dot_damage_per_tick": dot_damage_per_tick,
                "dot_tick_interval": dot_tick_interval,
                "dot_damage_type": dot_damage_type,
                "effect_data": effect_data
            }
            self.effects = [legacy_effect]

        # --- Backward Compatibility Attributes ---
        # Many AI/Systems check these directly on the spell object
        primary_effect = self.effects[0]
        self.effect_type = primary_effect["type"]
        self.effect_value = primary_effect.get("value", 0)
        self.damage_type = primary_effect.get("damage_type", damage_type)
        
        # Also expose these if they were set in the primary effect
        self.dot_duration = primary_effect.get("dot_duration", dot_duration)
        self.effect_data = primary_effect.get("effect_data", effect_data)

    @classmethod
    def from_dict(cls, spell_id: str, data: Dict[str, Any]) -> 'Spell':
        return cls(spell_id=spell_id, **data)

    def can_cast(self, caster) -> bool:
        caster_level = getattr(caster, 'level', 1)
        return caster_level >= self.level_required

    def format_cast_message(self, caster) -> str:
        return self.cast_message.format(caster_name=getattr(caster, 'name', 'Someone'), spell_name=self.name)
    
    def has_effect_type(self, type_name: str) -> bool:
        """Helper to check if any effect in the list matches the type."""
        for effect in self.effects:
            if effect.get("type") == type_name:
                return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "spell_id": self.spell_id,
            "name": self.name,
            "description": self.description,
            "mana_cost": self.mana_cost,
            "cooldown": self.cooldown,
            "target_type": self.target_type,
            "effects": self.effects, 
            "level_required": self.level_required,
            "cast_message": self.cast_message,
            "hit_message": self.hit_message
        }