# engine/items/key.py
from typing import Optional
from engine.items.item import Item

class Key(Item):
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Key",
                 description: str = "No description", weight: float = 0.1,
                 value: int = 15, target_id: Optional[str] = None):
        # Call super without stackable
        super().__init__(obj_id, name, description, weight, value, target_id=target_id)
        # Set stackable after super init
        self.stackable = False
        self.update_property("stackable", self.stackable)

    def use(self, user, target: Optional[Item] = None, **kwargs) -> str:
        """Use the key on a target item (e.g., a container)."""
        if not target:
            return f"What do you want to use the {self.name} on?"

        # Check Capability (Duck Typing)
        # We check if the target acts like a lockable container by checking for toggle_lock
        if hasattr(target, 'toggle_lock') and callable(getattr(target, 'toggle_lock', None)):
            # We pass 'self' (the Key instance) to the container's toggle_lock
            success = getattr(target, 'toggle_lock')(self)
            
            if success:
                # Check result state to craft the message
                is_locked = target.get_property("locked")
                if is_locked:
                    return f"You lock the {target.name} with the {self.name}."
                else:
                    return f"You unlock the {target.name} with the {self.name}."
            else:
                return f"The {self.name} doesn't fit the lock on the {target.name}."
        else:
            return f"You can't use the {self.name} on the {target.name}."