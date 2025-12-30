# engine/items/armor.py
from engine.items.item import Item
from typing import List, Optional

class Armor(Item):
    """
    Represents a piece of armor that provides defense when equipped.
    """
    def __init__(self,
                 obj_id: Optional[str] = None,
                 name: str = "Unknown Armor",
                 description: str = "A piece of protective gear.",
                 weight: float = 5.0, # Armor tends to be heavier
                 value: int = 50,     # Base value
                 defense: int = 1,    # Armor-specific stat
                 durability: int = 100,# Armor has durability
                 equip_slot: Optional[List[str]] = None, # Crucial: head, body, hands, feet, etc.
                 **kwargs):

        # --- Validate/Default equip_slot ---
        # Armor MUST have an equip slot defined, usually in the JSON template.
        # If it's somehow missing, we can't really default reliably.
        if equip_slot is None:
            # Best practice: Raise an error or log a critical warning.
            # Defaulting is risky. JSON should define this.
            print(f"CRITICAL WARNING: Armor '{name}' (ID: {obj_id}) created without an 'equip_slot' property! Template requires it.")
            # Fallback to body as a guess, but this is bad data.
            equip_slot = ["body"]
        elif isinstance(equip_slot, str): # Allow single string in JSON
            equip_slot = [equip_slot]

        # --- Call Super Item __init__ ---
        # Pass armor-specific properties (defense, durability, etc.)
        # and the equip_slot to the Item.__init__ via kwargs.
        # Item.__init__ will store them in the `properties` dictionary.
        super().__init__(
            obj_id=obj_id,
            name=name,
            description=description,
            weight=weight,
            value=value,
            stackable=False, # Armor is never stackable
            # Pass specific properties for Item's handling
            defense=defense,
            durability=durability,
            max_durability=durability, # Max durability defaults to initial durability
            equip_slot=equip_slot,     # Pass the validated list
            **kwargs                   # Pass any other properties from template/overrides
        )
        # Ensure stackable is explicitly false in properties dict as well
        self.update_property("stackable", False)


    def use(self, user, **kwargs) -> str:
        """Using armor equips it."""
        # Check if already equipped (same logic as Weapon.use)
        is_equipped = False
        for slot, equipped_item in user.equipment.items():
            if equipped_item and equipped_item.obj_id == self.obj_id:
                is_equipped = True
                break

        if is_equipped:
            durability = self.get_property("durability", 0)
            max_durability = self.get_property("max_durability", 1)
            condition = "good"
            if max_durability > 0:
                ratio = durability / max_durability
                if ratio <= 0.1: condition = "almost broken"
                elif ratio <= 0.5: condition = "worn"
                elif ratio <= 0.9: condition = "slightly damaged"
            # Slightly different message for armor
            return f"You check your equipped {self.name}. It's in {condition} condition."
        else:
            # Attempt to equip it using the player's method
            success, message = user.equip_item(self)
            return message

    def examine(self) -> str:
        """
        Get a detailed description, ensuring defense/durability are shown.
        (Inherited examine should work as long as defense/durability are in properties).
        """
        # The base Item.examine() iterates through self.properties, so defense,
        # durability, max_durability, and equip_slot will be shown automatically
        # as long as they were added to the properties dict by __init__.
        return super().examine()

    # to_dict and from_dict are inherited from Item and should work correctly
    # as defense/durability/equip_slot are stored in the properties dictionary.