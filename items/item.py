"""
items/item.py
Item system for the MUD game.
Base classes for all items in the game.
"""
from typing import Dict, Any, List, Optional # Added List, Optional
from game_object import GameObject

class Item(GameObject):
    """Base class for all items in the game."""

    def __init__(self, obj_id: str = None, name: str = "Unknown Item",
                 description: str = "No description", weight: float = 1.0,
                 value: int = 0, stackable: bool = False,
                 equip_slot: Optional[List[str]] = None, # <-- NEW: Optional list of valid slots
                 **kwargs):
        super().__init__(obj_id, name, description)
        self.weight = weight
        self.value = value
        self.stackable = stackable

        # Store basic properties
        self.update_property("weight", weight)
        self.update_property("value", value)
        self.update_property("stackable", stackable)
        # --- NEW: Store equip_slot ---
        if equip_slot:
            self.update_property("equip_slot", equip_slot)
        # --- END NEW ---

        # Store any additional properties from subclasses
        for key, value in kwargs.items():
             # Avoid overwriting core attributes handled above
             if key not in ["weight", "value", "stackable", "equip_slot", "name", "description", "obj_id", "id"]:
                  self.update_property(key, value)

    def examine(self) -> str:
        """
        Get a detailed description of the item.
        """
        base_desc = f"{self.name}\n\n{self.description}\n\nWeight: {self.weight}, Value: {self.value}"

        # Add equip slot info if present
        equip_slots = self.get_property("equip_slot")
        if equip_slots:
            slots_str = ", ".join([s.replace('_', ' ') for s in equip_slots])
            base_desc += f"\nEquip Slot(s): {slots_str}"

        # Add any specialized properties (unchanged)
        extra_props = []
        skip_keys = {"weight", "value", "stackable", "equip_slot", "name", "description", "id", "obj_id", "type"}
        for key, value in self.properties.items():
            if key not in skip_keys:
                if isinstance(value, (int, float, str, bool)):
                    formatted_name = key.replace('_', ' ').title()
                    extra_props.append(f"{formatted_name}: {value}")

        if extra_props:
            base_desc += "\n\n" + "\n".join(extra_props)

        return base_desc

    def use(self, user, **kwargs) -> str: # Allow flexible kwargs for targets etc.
        """
        Use this item (default behavior, to be overridden).
        """
        return f"You don't know how to use the {self.name}."

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the item to a dictionary for serialization.
        """
        data = super().to_dict()
        # Ensure core properties are present at top level for compatibility
        data["weight"] = self.weight
        data["value"] = self.value
        data["stackable"] = self.stackable
        # Equip slot is already in properties, which is included by super().to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """
        Create an item from a dictionary.
        """
        obj_id = data.get("obj_id") or data.get("id")

        # Extract properties that might be passed as kwargs
        # We get equip_slot from properties later if it exists
        item_kwargs = {
            "weight": data.get("weight", 1.0),
            "value": data.get("value", 0),
            "stackable": data.get("stackable", False),
        }

        # Create item using base init
        item = cls(
            obj_id=obj_id,
            name=data.get("name", "Unknown Item"),
            description=data.get("description", "No description"),
            **item_kwargs # Pass extracted properties
        )

        # Load all properties from the dict, overwriting defaults if necessary
        if "properties" in data:
            item.properties = data["properties"].copy() # Use copy

        # Ensure core attributes reflect loaded properties
        item.weight = item.properties.get("weight", item.weight)
        item.value = item.properties.get("value", item.value)
        item.stackable = item.properties.get("stackable", item.stackable)
        # Ensure equip_slot from properties is loaded if needed (already handled by loading properties)

        return item
