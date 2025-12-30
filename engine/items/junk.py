# engine/items/junk.py
"""
Represents generic junk items, often dropped by monsters or found as clutter.
These items primarily exist to be sold.
"""
from typing import Optional
from engine.items.item import Item

class Junk(Item):
    """A junk item, usually for selling."""

    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Junk",
                 description: str = "An item of little apparent use, but maybe someone will buy it.",
                 weight: float = 0.2, value: int = 1, # Junk typically has low value
                 **kwargs):
        """Initialize a junk item."""
        super().__init__(
            obj_id=obj_id,
            name=name,
            description=description,
            weight=weight,
            value=value, # Junk has a base value for selling
            stackable=True, # Let junk items stack (like pelts, fangs)
            **kwargs # Pass extra properties if needed (e.g., material)
        )
        # Ensure stackable is correctly set in properties as well
        self.update_property("stackable", True)

    def use(self, user, **kwargs) -> str:
        """Using junk doesn't do much."""
        return f"You examine the {self.name}, but can't find any immediate use for it."

    # examine() is inherited from Item and should be sufficient.
    # to_dict() and from_dict() are inherited from Item.
