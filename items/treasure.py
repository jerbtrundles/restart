# items/treasure.py
from items.item import Item


class Treasure(Item):
    def __init__(self, obj_id: str = None, name: str = "Unknown Treasure",
                 description: str = "No description", weight: float = 0.5,
                 value: int = 100):
        # Call super without stackable
        super().__init__(obj_id, name, description, weight, value, treasure_type="generic")
        # Set stackable after super init
        self.stackable = False
        self.update_property("stackable", self.stackable)
    
    def use(self, user) -> str:
        """Use the treasure (admire it)."""
        return f"You admire the {self.name}. It looks quite valuable."