# engine/items/gem.py
"""
Represents gems and precious stones, a category of valuable treasure.
"""
from typing import Optional
from engine.items.item import Item

class Gem(Item):
    """A gem item, primarily for selling or future crafting."""

    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Gem",
                 description: str = "A precious, cut gemstone.",
                 weight: float = 0.1, # Gems are light
                 value: int = 50, # Gems are valuable
                 **kwargs):
        """Initialize a gem item."""
        super().__init__(
            obj_id=obj_id,
            name=name,
            description=description,
            weight=weight,
            value=value,
            stackable=True, # Gems should be stackable
            **kwargs
        )
        # Ensure stackable is correctly set in properties
        self.update_property("stackable", True)

    def use(self, user, **kwargs) -> str:
        """Using a gem just examines its quality."""
        return f"You hold the {self.name} up to the light. It sparkles brilliantly."
