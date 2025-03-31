"""
items/item.py
Item system for the MUD game.
Base classes for all items in the game.
"""
from typing import Dict, Any
from game_object import GameObject

class Item(GameObject):
    """Base class for all items in the game."""
    
    def __init__(self, obj_id: str = None, name: str = "Unknown Item", 
                 description: str = "No description", weight: float = 1.0,
                 value: int = 0, stackable: bool = False, **kwargs):
        super().__init__(obj_id, name, description)
        self.weight = weight
        self.value = value
        self.stackable = stackable
        
        # Store basic properties
        self.update_property("weight", weight)
        self.update_property("value", value)
        self.update_property("stackable", stackable)
        
        # Store any additional properties from subclasses
        for key, value in kwargs.items():
            self.update_property(key, value)
    
    def examine(self) -> str:
        """
        Get a detailed description of the item.
        """
        base_desc = f"{self.name}\n\n{self.description}\n\nWeight: {self.weight}, Value: {self.value}"
        
        # Add any specialized properties
        extra_props = []
        for key, value in self.properties.items():
            if key not in {"weight", "value", "stackable"}:  # Skip the basic ones we already showed
                if isinstance(value, (int, float, str, bool)):  # Only show simple properties
                    # Format the property name to be title case and replace underscores with spaces
                    formatted_name = key.replace('_', ' ').title()
                    extra_props.append(f"{formatted_name}: {value}")
        
        if extra_props:
            base_desc += "\n\n" + "\n".join(extra_props)
            
        return base_desc

    def use(self, user) -> str:
        """
        Use this item (default behavior, to be overridden).
        """
        return f"You don't know how to use the {self.name}."
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the item to a dictionary for serialization.
        """
        # Start with the base implementation
        data = super().to_dict()
        
        # Make sure item-specific fields are at the top level for backwards compatibility
        data["obj_id"] = self.obj_id  # Backward compatibility
        data["weight"] = self.weight
        data["value"] = self.value
        data["stackable"] = self.stackable
        
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """
        Create an item from a dictionary.
        """
        # Handle obj_id for backward compatibility
        obj_id = data.get("obj_id") or data.get("id")
        
        # Extract basic properties
        item = cls(
            obj_id=obj_id,
            name=data.get("name", "Unknown Item"),
            description=data.get("description", "No description"),
            weight=data.get("weight", 1.0),
            value=data.get("value", 0),
            stackable=data.get("stackable", False)
        )
        
        # Load properties
        if "properties" in data:
            item.properties = data["properties"]
            
        return item
    
class Weapon(Item):
    """A weapon item that can be used in combat."""
    
    def __init__(self, obj_id: str = None, name: str = "Unknown Weapon", 
                 description: str = "No description", weight: float = 2.0,
                 value: int = 10, damage: int = 5, durability: int = 100):
        """
        Initialize a weapon.
        """
        super().__init__(
            obj_id=obj_id, 
            name=name, 
            description=description, 
            weight=weight, 
            value=value, 
            stackable=False,
            damage=damage,
            durability=durability,
            max_durability=durability
        )
    
    def use(self, user) -> str:
        """Use the weapon (practice attack)."""
        durability = self.get_property("durability")
        if durability <= 0:
            return f"The {self.name} is broken and cannot be used."
            
        condition = "sturdy" if durability > self.get_property("max_durability") / 2 else "fragile"
        return f"You practice swinging the {self.name}. It feels {condition}."
    
    def examine(self) -> str:
        """Get a detailed description of the weapon."""
        base_desc = super().examine()
        return f"{base_desc}\n\nDamage: {self.properties['damage']}\nDurability: {self.properties['durability']}/{self.properties['max_durability']}"

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

class Container(Item):
    """A container that can hold other items."""
    
    def __init__(self, obj_id: str = None, name: str = "Unknown Container", 
                 description: str = "No description", weight: float = 2.0,
                 value: int = 20, capacity: float = 50.0):
        """
        Initialize a container.
        
        Args:
            capacity: The maximum weight the container can hold.
        """
        super().__init__(obj_id, name, description, weight, value, stackable=False)
        self.properties["capacity"] = capacity
        self.properties["contains"] = []  # List of item IDs
        self.properties["locked"] = False
        self.properties["key_id"] = None  # ID of key that can open this container
    
    def examine(self) -> str:
        """Get a detailed description of the container."""
        base_desc = super().examine()
        if self.properties["locked"]:
            return f"{base_desc}\n\nThe {self.name} is locked."
        
        # We'll need inventory management to show contents
        return f"{base_desc}\n\nCapacity: {self.properties['capacity']} weight units."
    
    def use(self, user) -> str:
        """Use the container (open it)."""
        if self.properties["locked"]:
            return f"The {self.name} is locked."
        
        # We'll need inventory management to handle this properly
        return f"You open the {self.name}."


class Key(Item):
    """A key that can unlock containers or doors."""
    
    def __init__(self, obj_id: str = None, name: str = "Unknown Key", 
                 description: str = "No description", weight: float = 0.1,
                 value: int = 15, target_id: str = None):
        """
        Initialize a key.
        
        Args:
            target_id: The ID of the container or door this key unlocks.
        """
        super().__init__(obj_id, name, description, weight, value, stackable=False)
        self.properties["target_id"] = target_id
    
    def use(self, user) -> str:
        """Use the key (attempt to unlock something)."""
        return f"You need to specify what to use the {self.name} on."


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
