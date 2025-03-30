"""
items/item.py
Item system for the MUD game.
Base classes for all items in the game.
"""
from typing import Dict, List, Optional, Any
import uuid
import json


class Item:
    """Base class for all items in the game."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Item", 
                 description: str = "No description", weight: float = 1.0,
                 value: int = 0, stackable: bool = False):
        """
        Initialize an item.
        
        Args:
            item_id: Unique ID for the item. If None, one will be generated.
            name: The display name of the item.
            description: A textual description of the item.
            weight: The weight of the item in arbitrary units.
            value: The monetary value of the item.
            stackable: Whether multiple instances of this item can be stacked in inventory.
        """
        self.item_id = item_id if item_id else f"item_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.weight = weight
        self.value = value
        self.stackable = stackable
        self.properties: Dict[str, Any] = {}  # Additional properties for derived item types
    
    def examine(self) -> str:
        """
        Get a detailed description of the item.
        
        Returns:
            A formatted description of the item.
        """
        return f"{self.name}\n\n{self.description}\n\nWeight: {self.weight}, Value: {self.value}"
    
    def use(self, user) -> str:
        """
        Use this item (default behavior, to be overridden).
        
        Args:
            user: The entity using the item.
            
        Returns:
            A string describing what happened.
        """
        return f"You don't know how to use the {self.name}."
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the item to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the item.
        """
        return {
            "type": self.__class__.__name__,
            "item_id": self.item_id,
            "name": self.name,
            "description": self.description,
            "weight": self.weight,
            "value": self.value,
            "stackable": self.stackable,
            "properties": self.properties
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """
        Create an item from a dictionary.
        
        Args:
            data: Dictionary data to convert into an item.
            
        Returns:
            An item instance.
        """
        item = cls(
            item_id=data["item_id"],
            name=data["name"],
            description=data["description"],
            weight=data["weight"],
            value=data["value"],
            stackable=data["stackable"]
        )
        item.properties = data.get("properties", {})
        return item


class Weapon(Item):
    """A weapon item that can be used in combat."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Weapon", 
                 description: str = "No description", weight: float = 2.0,
                 value: int = 10, damage: int = 5, durability: int = 100):
        """
        Initialize a weapon.
        
        Args:
            damage: The base damage value of the weapon.
            durability: The durability/condition of the weapon.
        """
        super().__init__(item_id, name, description, weight, value, stackable=False)
        self.properties["damage"] = damage
        self.properties["durability"] = durability
        self.properties["max_durability"] = durability
    
    def examine(self) -> str:
        """Get a detailed description of the weapon."""
        base_desc = super().examine()
        return f"{base_desc}\n\nDamage: {self.properties['damage']}\nDurability: {self.properties['durability']}/{self.properties['max_durability']}"
    
    def use(self, user) -> str:
        """Use the weapon (practice attack)."""
        return f"You practice swinging the {self.name}. It feels {'sturdy' if self.properties['durability'] > 50 else 'fragile'}."


class Consumable(Item):
    """A consumable item like food or potion."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Consumable", 
                 description: str = "No description", weight: float = 0.5,
                 value: int = 5, uses: int = 1, effect_value: int = 10, 
                 effect_type: str = "heal"):
        """
        Initialize a consumable.
        
        Args:
            uses: The number of uses before the item is consumed.
            effect_value: How strong the effect is.
            effect_type: What type of effect (heal, damage, etc.).
        """
        super().__init__(item_id, name, description, weight, value, stackable=(uses == 1))
        self.properties["uses"] = uses
        self.properties["max_uses"] = uses
        self.properties["effect_value"] = effect_value
        self.properties["effect_type"] = effect_type
    
    def examine(self) -> str:
        """Get a detailed description of the consumable."""
        base_desc = super().examine()
        if self.properties["max_uses"] > 1:
            return f"{base_desc}\n\nUses remaining: {self.properties['uses']}/{self.properties['max_uses']}"
        return base_desc
    
    def use(self, user) -> str:
        """Use the consumable item."""
        if self.properties["uses"] <= 0:
            return f"The {self.name} has been completely used up."
        
        self.properties["uses"] -= 1
        
        effect_type = self.properties["effect_type"]
        effect_value = self.properties["effect_value"]
        
        if effect_type == "heal":
            # Attempt to heal the user if it has health
            if hasattr(user, "health") and hasattr(user, "max_health"):
                old_health = user.health
                user.health = min(user.health + effect_value, user.max_health)
                gained = user.health - old_health
                return f"You consume the {self.name} and regain {gained} health."
            
            return f"You consume the {self.name}, but it has no effect on you."
        
        # Other effect types can be added here
        return f"You consume the {self.name}."


class Container(Item):
    """A container that can hold other items."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Container", 
                 description: str = "No description", weight: float = 2.0,
                 value: int = 20, capacity: float = 50.0):
        """
        Initialize a container.
        
        Args:
            capacity: The maximum weight the container can hold.
        """
        super().__init__(item_id, name, description, weight, value, stackable=False)
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
    
    def __init__(self, item_id: str = None, name: str = "Unknown Key", 
                 description: str = "No description", weight: float = 0.1,
                 value: int = 15, target_id: str = None):
        """
        Initialize a key.
        
        Args:
            target_id: The ID of the container or door this key unlocks.
        """
        super().__init__(item_id, name, description, weight, value, stackable=False)
        self.properties["target_id"] = target_id
    
    def use(self, user) -> str:
        """Use the key (attempt to unlock something)."""
        return f"You need to specify what to use the {self.name} on."


class Treasure(Item):
    """A valuable item that exists primarily for its value."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Treasure", 
                 description: str = "No description", weight: float = 0.5,
                 value: int = 100):
        """Initialize a treasure item."""
        super().__init__(item_id, name, description, weight, value, stackable=False)
        self.properties["treasure_type"] = "generic"  # Can be 'coin', 'gem', 'jewelry', etc.
    
    def use(self, user) -> str:
        """Use the treasure (admire it)."""
        return f"You admire the {self.name}. It looks quite valuable."


class ItemFactory:
    """Factory class for creating items from templates or data."""
    
    @staticmethod
    def create_item(item_type: str, **kwargs) -> Item:
        """
        Create an item of the specified type.
        
        Args:
            item_type: The type of item to create.
            **kwargs: Additional arguments to pass to the item constructor.
            
        Returns:
            An instance of the requested item type.
        """
        item_classes = {
            "Item": Item,
            "Weapon": Weapon,
            "Consumable": Consumable,
            "Container": Container,
            "Key": Key,
            "Treasure": Treasure
        }
        
        if item_type not in item_classes:
            raise ValueError(f"Unknown item type: {item_type}")
        
        return item_classes[item_type](**kwargs)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Item:
        """
        Create an item from a dictionary.
        
        Args:
            data: Dictionary containing item data.
            
        Returns:
            An item instance of the appropriate type.
        """
        item_type = data.get("type", "Item")
        
        # Create a base item first
        item = ItemFactory.create_item(item_type, 
                                      item_id=data.get("item_id"),
                                      name=data.get("name", "Unknown Item"),
                                      description=data.get("description", "No description"),
                                      weight=data.get("weight", 1.0),
                                      value=data.get("value", 0))
        
        # Set additional properties
        if "properties" in data:
            item.properties.update(data["properties"])
            
        return item