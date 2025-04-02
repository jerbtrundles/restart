from typing import Container, Optional

from items.item import Item


class Key(Item):
    """A key that can unlock containers or doors."""

    def __init__(self, obj_id: str = None, name: str = "Unknown Key",
                 description: str = "No description", weight: float = 0.1,
                 value: int = 15, target_id: Optional[str] = None): # Use Optional
        """
        Initialize a key.

        Args:
            target_id: The ID of the container or door this key unlocks.
                       Can be None if it's a generic key opened by obj_id.
        """
        super().__init__(obj_id, name, description, weight, value, stackable=False)
        self.properties["target_id"] = target_id

    # MODIFY use method for Key
    def use(self, user, target_item: Optional[Item] = None) -> str:
        """Use the key on a target item (e.g., a container)."""
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
