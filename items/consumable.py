from items.item import Item


class Consumable(Item):
    """A consumable item like food or potion."""
    
    def __init__(self, obj_id: str = None, name: str = "Unknown Consumable", 
                 description: str = "No description", weight: float = 0.5,
                 value: int = 5, uses: int = 1, effect_value: int = 10, 
                 effect_type: str = "heal"):
        """
        Initialize a consumable.
        """
        super().__init__(
            obj_id=obj_id, 
            name=name, 
            description=description, 
            weight=weight, 
            value=value, 
            stackable=(uses == 1),
            uses=uses,
            max_uses=uses,
            effect_value=effect_value,
            effect_type=effect_type
        )
    
    def use(self, user) -> str:
        """Use the consumable item."""
        uses = self.get_property("uses")
        if uses <= 0:
            return f"The {self.name} has been completely used up."
        
        # Decrement uses
        self.update_property("uses", uses - 1)
        
        effect_type = self.get_property("effect_type")
        effect_value = self.get_property("effect_value")
        
        if effect_type == "heal" and hasattr(user, "health") and hasattr(user, "max_health"):
            old_health = user.health
            user.health = min(user.health + effect_value, user.max_health)
            gained = user.health - old_health
            return f"You consume the {self.name} and regain {gained} health."
        
        return f"You consume the {self.name}."
    
    def examine(self) -> str:
        """Get a detailed description of the consumable."""
        base_desc = super().examine()
        if self.properties["max_uses"] > 1:
            return f"{base_desc}\n\nUses remaining: {self.properties['uses']}/{self.properties['max_uses']}"
        return base_desc