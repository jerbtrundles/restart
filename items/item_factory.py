import inspect
from typing import Any, Container, Dict, Optional
from items.item import Item
from items.consumable import Consumable
from items.key import Key
from items.treasure import Treasure
from items.weapon import Weapon
from utils.text_formatter import TextFormatter


class ItemFactory:
    """Factory class for creating items from templates or data."""
    
    @staticmethod
    def create_item(item_type: str, **kwargs) -> Item:
         # ... (create_item method - no change needed here) ...
         item_classes = {
             "Item": Item, "Weapon": Weapon, "Consumable": Consumable,
             "Container": Container, "Key": Key, "Treasure": Treasure
         }
         if item_type not in item_classes:
             raise ValueError(f"Unknown item type: {item_type}")
         # Get the class constructor
         cls = item_classes[item_type]
         # Get expected parameters for the constructor
         sig = inspect.signature(cls.__init__)
         valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters or k == 'obj_id'} # Allow obj_id too
         # Pass only valid kwargs to constructor
         item = cls(**valid_kwargs)
         # Apply remaining kwargs as properties AFTER initialization
         for key, value in kwargs.items():
              if key not in valid_kwargs and key != 'type':
                   item.update_property(key, value)
         return item
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Optional[Item]: # Return Optional[Item]
        """Create an item from a dictionary."""
        if not data:
            return None

        item_type = data.get("type", "Item") # Default to "Item"

        item_classes = {
             "Item": Item, "Weapon": Weapon, "Consumable": Consumable,
             "Container": Container, "Key": Key, "Treasure": Treasure
        }

        cls = item_classes.get(item_type, Item) # Get the class, fallback to Item

        try:
            # Use the class's from_dict method
            item = cls.from_dict(data)

            # Post-creation property loading/validation if needed
            # Example: Ensure essential properties exist
            if isinstance(item, Weapon):
                 item.properties.setdefault("damage", 0)
                 item.properties.setdefault("durability", 100)
                 item.properties.setdefault("max_durability", 100)
            elif isinstance(item, Consumable):
                 item.properties.setdefault("uses", 1)
                 item.properties.setdefault("max_uses", 1)
                 item.properties.setdefault("effect_type", "heal")
                 item.properties.setdefault("effect_value", 10)
            # ... add for other types if necessary

            return item

        except Exception as e:
            print(f"{TextFormatter.FORMAT_ERROR}Error creating item type '{item_type}' from dict: {e}{TextFormatter.FORMAT_RESET}")
            # Attempt fallback to base Item if specific type failed
            if cls != Item:
                 try:
                     print(f"Attempting fallback to base Item for {data.get('name', 'unknown item')}")
                     return Item.from_dict(data)
                 except Exception as fallback_e:
                     print(f"{TextFormatter.FORMAT_ERROR}Fallback to base Item failed: {fallback_e}{TextFormatter.FORMAT_RESET}")
                     return None
            else:
                 return None # Failed even with base Item
