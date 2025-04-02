from items.item import Item


class Treasure(Item):
    """A valuable item that exists primarily for its value."""
    
    def __init__(self, obj_id: str = None, name: str = "Unknown Treasure", 
                 description: str = "No description", weight: float = 0.5,
                 value: int = 100):
        """Initialize a treasure item."""
        super().__init__(obj_id, name, description, weight, value, stackable=False)
        self.properties["treasure_type"] = "generic"  # Can be 'coin', 'gem', 'jewelry', etc.
    
    def use(self, user) -> str:
        """Use the treasure (admire it)."""
        return f"You admire the {self.name}. It looks quite valuable."