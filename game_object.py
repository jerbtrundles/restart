"""
game_object.py
Base class for all game objects with common functionality.
"""
from typing import Dict, Any, List, Optional, Tuple
import uuid


class GameObject:
    def __init__(self, obj_id: str = None, name: str = "Unknown", 
                 description: str = "No description"):
        self.obj_id = obj_id if obj_id else f"{self.__class__.__name__.lower()}_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.properties: Dict[str, Any] = {}  # Additional properties for derived classes
        self.active_effects: List[Dict[str, Any]] = [] # <<< ADD active effects list

    def get_description(self) -> str:
        return f"{self.name}\n\n{self.description}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "id": self.obj_id,
            "name": self.name,
            "description": self.description,
            "properties": self.properties
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameObject':
        obj = cls(
            obj_id=data.get("obj_id") or data.get("id"),
            name=data.get("name", "Unknown"),
            description=data.get("description", "No description")
        )
        obj.properties = data.get("properties", {})
        return obj
    
    def update_property(self, key: str, value: Any) -> None:
        self.properties[key] = value
    
    def get_property(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)

    def apply_effect(self, effect_data: Dict[str, Any], current_time: float) -> Tuple[bool, str]:
        """
        Applies a status effect to this game object.

        Args:
            effect_data: A dictionary containing the base definition of the effect
                         (type, name, base_duration, damage_per_tick, etc.).
            current_time: The current absolute time (time.time()).

        Returns:
            Tuple (success: bool, message: str)
        """
        if not self.is_alive: return False, f"{self.name} cannot be affected." # Assuming is_alive exists

        effect_name = effect_data.get("name", "Unknown Effect")
        effect_type = effect_data.get("type", "unknown")

        # --- Check for existing effect of the same name ---
        # Simple rule: New application refreshes duration (overwrites old one)
        existing_effect_index = -1
        for i, existing in enumerate(self.active_effects):
            if existing.get("name") == effect_name:
                existing_effect_index = i
                break

        # Prepare the new effect instance
        new_effect_instance = effect_data.copy() # Copy base data
        new_effect_instance["id"] = f"effect_{uuid.uuid4().hex[:8]}" # Unique instance ID
        new_effect_instance["duration_remaining"] = new_effect_instance.get("base_duration", 10.0) # Set remaining from base
        new_effect_instance["last_tick_time"] = current_time # Initialize tick timer

        # --- Apply or Replace ---
        if existing_effect_index != -1:
            # Replace existing effect
            self.active_effects[existing_effect_index] = new_effect_instance
            # Message depends on viewer (implemented where apply_effect is called)
            # Base message could be: f"The {effect_name} on {self.name} is renewed."
        else:
            # Add new effect
            self.active_effects.append(new_effect_instance)
            # Base message could be: f"{self.name} is afflicted with {effect_name}."

        # Success - actual message formatting happens in the calling function (attack/cast)
        # This just confirms the effect was added/refreshed internally.
        return True, "" # Return success, message handled by caller

    # --- NEW: Method to remove effects ---
    def remove_effect(self, effect_name: str) -> bool:
        """Removes the first found effect instance with the matching name."""
        original_count = len(self.active_effects)
        self.active_effects = [eff for eff in self.active_effects if eff.get("name") != effect_name]
        return len(self.active_effects) < original_count # Return True if an effect was removed
