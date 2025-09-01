# items/weapon.py
from items.item import Item
from typing import List, Optional # Import List, Optional

class Weapon(Item):
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Weapon",
                 description: str = "No description", weight: float = 2.0,
                 value: int = 10, damage: int = 5, durability: int = 100,
                 equip_slot: Optional[List[str]] = None,
                 **kwargs):
        if equip_slot is None:
             equip_slot = ["main_hand", "off_hand"]

        # Call super without stackable, but include other kwargs
        super().__init__(
            obj_id=obj_id, name=name, description=description, weight=weight,
            value=value, equip_slot=equip_slot,
            damage=damage, durability=durability, max_durability=durability,
            **kwargs
        )
        # Set stackable after super init
        self.stackable = False
        self.update_property("stackable", self.stackable)

    def use(self, user, **kwargs) -> str:
        """Use the weapon (e.g., to equip it if not equipped)."""
        # Check if already equipped
        is_equipped = False
        for slot, equipped_item in user.equipment.items():
             if equipped_item and equipped_item.obj_id == self.obj_id:
                  is_equipped = True
                  break

        if is_equipped:
             durability = self.get_property("durability")
             if durability <= 0: return f"The {self.name} is broken and cannot be used."
             condition = "sturdy" if durability > self.get_property("max_durability", 1) / 2 else "worn"
             return f"You practice swinging the equipped {self.name}. It feels {condition}."
        else:
             # Attempt to equip it
             success, message = user.equip_item(self)
             return message

    def examine(self) -> str:
        """Get a detailed description of the weapon."""
        base_desc = super().examine() # Includes equip slot now
        # Damage and Durability are added by base examine if they are in properties
        return base_desc # Base examine should be sufficient now
