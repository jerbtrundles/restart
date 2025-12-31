# engine/items/treasure.py
from typing import Optional
from engine.items.item import Item

class Treasure(Item):
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Treasure",
                 description: str = "No description", weight: float = 0.5,
                 value: int = 100, **kwargs):
        
        # Use value from template if exists, otherwise default to False (unique treasures)
        # Note: Coins usually define "stackable": true in JSON to override this default.
        is_stackable = kwargs.pop('stackable', False)
        
        super().__init__(
            obj_id=obj_id, 
            name=name, 
            description=description, 
            weight=weight, 
            value=value, 
            stackable=is_stackable, 
            treasure_type="generic",
            **kwargs
        )
    
    def use(self, user) -> str:
        """Use the treasure (admire it)."""
        return f"You admire the {self.name}. It looks quite valuable."