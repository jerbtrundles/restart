# items/item_factory.py
import inspect
from typing import Any, Dict, Optional # Removed Container import if not used elsewhere here
from core.config import FORMAT_ERROR, FORMAT_RESET
from items.item import Item

class ItemFactory:
    """Factory class for creating items from templates or data."""

    # *** NEW: Helper method to delay imports ***
    @staticmethod
    def _get_item_classes() -> Dict[str, type]:
        """Imports item classes locally and returns the class mapping."""
        # Import necessary item types here, inside the method
        from items.item import Item # Base item
        from items.consumable import Consumable
        from items.key import Key
        from items.treasure import Treasure
        from items.weapon import Weapon
        from items.container import Container # Import Container locally
        from items.junk import Junk # Import Junk locally

        return {
             "Item": Item, "Weapon": Weapon, "Consumable": Consumable,
             "Container": Container, "Key": Key, "Treasure": Treasure,
             "Junk": Junk
        }
    # *** END NEW ***
    
    @staticmethod
    def create_item(item_type: str, **kwargs) -> Optional[Item]:
        # *** Use the helper method ***
        from utils.text_formatter import TextFormatter # <<< IMPORT INSIDE METHOD
        item_classes = ItemFactory._get_item_classes()
        cls = item_classes.get(item_type)
        if not cls:
            # Maybe try to create a base 'Item' as fallback? Or raise error?
            print(f"{FORMAT_ERROR}Warning: Unknown item type '{item_type}' requested in create_item. Trying base Item.{FORMAT_RESET}")
            cls = Item # Fallback to base Item if type unknown
            # Alternatively: raise ValueError(f"Unknown item type: {item_type}")

        try:
            # Get expected parameters for the constructor
            sig = inspect.signature(cls.__init__)
            # Allow obj_id, allow **kwargs catch-all
            valid_params = set(sig.parameters.keys())
            has_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())

            valid_kwargs = {}
            extra_properties = {}

            for k, v in kwargs.items():
                if k in valid_params:
                    valid_kwargs[k] = v
                elif k == 'obj_id': # Allow obj_id explicitly if not in signature (like for base GameObject)
                    valid_kwargs[k] = v
                elif has_kwargs: # If class accepts **kwargs, pass them along
                    valid_kwargs[k] = v
                else: # Otherwise, store as potential extra property
                    # Only store if it's not a standard Item/GameObject attribute we handle separately
                    if k not in ['name', 'description', 'weight', 'value', 'stackable', 'type']:
                        extra_properties[k] = v

            # Create the item instance
            item = cls(**valid_kwargs)

            # Apply any remaining kwargs as properties AFTER initialization
            for key, value in extra_properties.items():
                item.update_property(key, value)

            # Ensure core properties reflect kwargs if they weren't constructor args
            # (This might be redundant if Item.__init__ already handles **kwargs well)
            if 'weight' in kwargs and not isinstance(item, Item): item.weight = kwargs['weight'] # Safety check
            if 'value' in kwargs and not isinstance(item, Item): item.value = kwargs['value']
            if 'stackable' in kwargs and not isinstance(item, Item): item.stackable = kwargs['stackable']

            return item
        except Exception as e:
            print(f"{FORMAT_ERROR}Error creating item type '{item_type}' with args {kwargs}: {e}{FORMAT_RESET}")
            import traceback
            traceback.print_exc()
            return None
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Optional[Item]:
        """Create an item from a dictionary."""
        if not data: return None
        item_type = data.get("type", "Item")
        item_classes = ItemFactory._get_item_classes()
        cls = item_classes.get(item_type, Item) # Fallback to Item

        from utils.text_formatter import TextFormatter # <<< IMPORT INSIDE METHOD

        try:
            # Use the class's from_dict method (inherited from GameObject -> Item)
            item = cls.from_dict(data)
            if not item: # If from_dict somehow returned None
                 raise ValueError("Item.from_dict returned None")

            return item
        except Exception as e:
            print(f"{FORMAT_ERROR}Error creating item type '{item_type}' from dict: {e}{FORMAT_RESET}")
            # Attempt fallback to base Item if specific type failed
            if cls != Item:
                 try:
                     print(f"Attempting fallback to base Item for {data.get('name', 'unknown item')}")
                     return Item.from_dict(data)
                 except Exception as fallback_e:
                     print(f"{FORMAT_ERROR}Fallback to base Item failed: {fallback_e}{FORMAT_RESET}")
                     return None
            else:
                 return None # Failed even with base Item
