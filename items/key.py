# items/key.py

from typing import Optional

from items.item import Item

class Key(Item):
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Key",
                 description: str = "No description", weight: float = 0.1,
                 value: int = 15, target_id: Optional[str] = None):
        # Call super without stackable
        super().__init__(obj_id, name, description, weight, value, target_id=target_id)
        # Set stackable after super init
        self.stackable = False
        self.update_property("stackable", self.stackable)

    # MODIFY use method for Key
    def use(self, user, target_item: Optional[Item] = None) -> str:
        """Use the key on a target item (e.g., a container)."""
        # --- FIX: Import Container locally, only when this method is called ---
        from items.container import Container

        if not target_item:
            return f"What do you want to use the {self.name} on?"

        if isinstance(target_item, Container):
            success = target_item.toggle_lock(self)
            if success:
                if target_item.properties["locked"]:
                    return f"You lock the {target_item.name} with the {self.name}."
                else:
                    return f"You unlock the {target_item.name} with the {self.name}."
            else:
                return f"The {self.name} doesn't fit the lock on the {target_item.name}."
        else:
            return f"You can't use the {self.name} on the {target_item.name}."