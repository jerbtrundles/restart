from typing import Any, Container, Dict
from items.item import Consumable, Item, Key, Treasure, Weapon


class ItemFactory:
    """Factory class for creating items from templates or data."""
    
    @staticmethod
    def create_item(item_type: str, **kwargs) -> Item:
        """
        Create an item of the specified type.
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
        """
        if not data:
            return None
            
        item_type = data.get("type", "Item")
        
        # Try to create the appropriate item type
        try:
            if item_type in ["Weapon", "Consumable", "Container", "Key", "Treasure"]:
                return globals()[item_type].from_dict(data)
            else:
                # Default to base Item
                return Item.from_dict(data)
                
        except Exception as e:
            print(f"Error creating item of type {item_type}: {e}")
            # Fallback to base Item in case of errors
            return Item.from_dict(data)