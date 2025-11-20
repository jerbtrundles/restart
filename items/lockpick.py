# items/lockpick.py
import random
from typing import Optional
from items.item import Item
from config import FORMAT_ERROR, FORMAT_SUCCESS, FORMAT_HIGHLIGHT, FORMAT_RESET

class Lockpick(Item):
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Lockpick",
                 description: str = "No description", weight: float = 0.1,
                 value: int = 5, break_chance: float = 0.25, **kwargs):
        super().__init__(obj_id, name, description, weight, value, stackable=True, **kwargs)
        self.break_chance = break_chance
        self.update_property("break_chance", break_chance)

    def use(self, user, target: Optional[Item] = None, **kwargs) -> str:
        if not target:
            return f"What do you want to use the {self.name} on?"

        # Check Capability (Duck Typing) for lockpicking
        if hasattr(target, 'pick_lock') and callable(getattr(target, 'pick_lock', None)):
            # Attempt to pick the lock
            success, message = target.pick_lock(user) # type: ignore
            
            # Handle breakage mechanic
            if random.random() < self.break_chance:
                # Remove 1 from stack/inventory
                if hasattr(user, "inventory"):
                    user.inventory.remove_item(self.obj_id, 1)
                message += f"\n{FORMAT_ERROR}Your lockpick snaps in the mechanism!{FORMAT_RESET}"
            
            return message
        else:
            return f"You can't use a lockpick on the {target.name}."