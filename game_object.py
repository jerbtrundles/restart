# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Added logic to `process_active_effects` to handle a new effect type: "hot" (Heal Over Time).
# - This new logic mirrors the "dot" handler but calls `self.heal()` instead of `self.take_damage()`.

import random
from typing import Dict, Any, List, Optional, Tuple
import uuid
from core.config import EFFECT_DEFAULT_TICK_INTERVAL, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, NPC_DOT_FLAVOR_MESSAGES

class GameObject:
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown",
        description: str = "No description"):
        self.obj_id = obj_id if obj_id else f"{self.__class__.__name__.lower()}_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.properties: Dict[str, Any] = {}
        self.active_effects: List[Dict[str, Any]] = []
        self.is_alive: bool = True

    def get_description(self) -> str:
        return f"{self.name}\n\n{self.description}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "id": self.obj_id,
            "name": self.name,
            "description": self.description,
            "properties": self.properties,
            "is_alive": self.is_alive 
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameObject':
        obj = cls(
            obj_id=data.get("obj_id") or data.get("id"),
            name=data.get("name", "Unknown"),
            description=data.get("description", "No description")
        )
        obj.properties = data.get("properties", {})
        obj.is_alive = data.get("is_alive", True) 
        return obj

    def update_property(self, key: str, value: Any) -> None:
        self.properties[key] = value

    def get_property(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)

    def take_damage(self, amount: int, damage_type: str) -> int:
        return 0
        
    def heal(self, amount: int) -> int:
        return 0

    def apply_effect(self, effect_data: Dict[str, Any], current_time: float) -> Tuple[bool, str]:
        if not self.is_alive: return False, f"{self.name} cannot be affected."
        effect_name = effect_data.get("name", "Unknown Effect")
        # Overwrite existing effect of the same name to refresh it
        self.active_effects = [eff for eff in self.active_effects if eff.get("name") != effect_name]
        
        new_effect_instance = effect_data.copy()
        new_effect_instance["id"] = f"effect_{uuid.uuid4().hex[:8]}"
        new_effect_instance["last_tick_time"] = current_time 
        
        # Effects from gear shouldn't have a duration; they last as long as the item is equipped
        if "base_duration" in new_effect_instance:
            new_effect_instance["duration_remaining"] = new_effect_instance.get("base_duration", 10.0)

        self.active_effects.append(new_effect_instance)
        return True, ""

    def remove_effect(self, effect_name: str) -> bool:
        original_count = len(self.active_effects)
        self.active_effects = [eff for eff in self.active_effects if eff.get("name") != effect_name]
        return len(self.active_effects) < original_count

    def process_active_effects(self, current_time: float, time_delta: float) -> List[str]:
        if not self.is_alive:
            if self.active_effects: self.active_effects.clear()
            return []

        expired_effects = []
        tick_messages = []

        for effect in self.active_effects:
            # Handle duration-based effects
            if "duration_remaining" in effect:
                effect["duration_remaining"] -= time_delta
                if effect["duration_remaining"] <= 0:
                    expired_effects.append(effect)
                    tick_messages.append(f"The {FORMAT_HIGHLIGHT}{effect.get('name', 'effect')}{FORMAT_RESET} on you wears off.")
                    continue

            # Handle Damage Over Time (DoT)
            if effect.get("type") == "dot":
                tick_interval = effect.get("tick_interval", EFFECT_DEFAULT_TICK_INTERVAL)
                if current_time - effect.get("last_tick_time", 0) >= tick_interval:
                    effect["last_tick_time"] = current_time
                    damage = effect.get("damage_per_tick", 0)
                    dmg_type = effect.get("damage_type", "unknown")
                    damage_taken = self.take_damage(damage, dmg_type)
                    if damage_taken > 0:
                        effect_name_fmt = f"{FORMAT_HIGHLIGHT}{effect.get('name', 'effect')}{FORMAT_RESET}"
                        message = f"You take {FORMAT_ERROR}{damage_taken}{FORMAT_RESET} {dmg_type} damage from the {effect_name_fmt}."
                        tick_messages.append(message)
            
            # Handle Heal Over Time (HoT)
            elif effect.get("type") == "hot":
                tick_interval = effect.get("tick_interval", EFFECT_DEFAULT_TICK_INTERVAL)
                if current_time - effect.get("last_tick_time", 0) >= tick_interval:
                    effect["last_tick_time"] = current_time
                    heal_amount = effect.get("heal_per_tick", 0)
                    healed_for = self.heal(heal_amount)
                    if healed_for > 0:
                        effect_name_fmt = f"{FORMAT_HIGHLIGHT}{effect.get('name', 'effect')}{FORMAT_RESET}"
                        message = f"The {effect_name_fmt} heals you for {FORMAT_SUCCESS}{healed_for}{FORMAT_RESET} health."
                        tick_messages.append(message)

            if not self.is_alive:
                tick_messages.append(f"You succumb to the effects of {effect.get('name', 'the affliction')}!")
                break
        
        if expired_effects:
            self.active_effects = [eff for eff in self.active_effects if eff not in expired_effects]
        
        if not self.is_alive and self.active_effects:
            self.active_effects.clear()

        return tick_messages