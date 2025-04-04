# items/item_factory.py
import inspect
import json # For loading templates
import os   # For path manipulation
from typing import TYPE_CHECKING, Any, Dict, Optional, Type # Added Type
from core.config import FORMAT_ERROR, FORMAT_RESET
from items.container import Container

if TYPE_CHECKING:
    from items.item import Item
    from world.world import World # Needed for context
    
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
    def create_item(item_type: str, **kwargs) -> Optional['Item']:
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

    # This method might be less used now, but keep for potential dynamic creation
    @staticmethod
    def from_dict(data: Dict[str, Any], world: Optional['World'] = None) -> Optional['Item']:
        """Create an item from a dictionary (potentially without a template)."""
        if not data: return None
        item_id = data.get("obj_id", data.get("id")) # Get ID

        # If ID exists, try creating from template first
        if item_id and world:
             overrides = data.get("properties_override", data.get("properties", {}))
             # Include top-level overrides if present
             for key in ["name", "description", "weight", "value", "stackable"]:
                  if key in data: overrides[key] = data[key]

             item = ItemFactory.create_item_from_template(item_id, world, **overrides)
             if item: return item
             # If template creation failed, fall through to direct creation

        # Fallback: Direct creation from dict (treat dict as a pseudo-template)
        print(f"Warning: Creating item '{data.get('name', 'Unknown')}' directly from dict, template lookup failed or ID missing.")
        item_type_name = data.get("type", "Item")
        item_class = ItemFactory._get_item_class(item_type_name)
        if not item_class:
             print(f"{FORMAT_ERROR}Error: Unknown item type '{item_type_name}'. Using base Item.{FORMAT_RESET}")
             item_class = ItemFactory._get_item_class("Item")

        try:
             # Use the class's standard from_dict (which now handles properties better)
             # Pass world context if needed by Container.from_dict
             if issubclass(item_class, Container):
                  return item_class.from_dict(data, world)
             else:
                  return item_class.from_dict(data)
        except Exception as e:
             print(f"{FORMAT_ERROR}Error creating item type '{item_type_name}' directly from dict: {e}{FORMAT_RESET}")
             return None
   
    @staticmethod
    def _get_item_class(item_type_name: str) -> Optional[Type['Item']]:
        """Helper to get the actual class object."""
        from items.item import Item
        from items.consumable import Consumable
        from items.key import Key
        from items.treasure import Treasure
        from items.weapon import Weapon
        from items.container import Container
        from items.junk import Junk

        item_classes = {
             "Item": Item, "Weapon": Weapon, "Consumable": Consumable,
             "Container": Container, "Key": Key, "Treasure": Treasure,
             "Junk": Junk
             # Add Armor, Shield etc. when created
        }
        return item_classes.get(item_type_name)

    @staticmethod
    def get_template(item_id: str, world: Optional['World'] = None) -> Optional[Dict[str, Any]]:
         """Retrieves an item template definition."""
         if world and hasattr(world, 'item_templates'):
              return world.item_templates.get(item_id)
         # Fallback or error if world/templates missing?
         print(f"Warning: Cannot get template for '{item_id}'. World or templates missing.")
         return None

    @staticmethod
    def create_item_from_template(item_id: str, world: 'World', **overrides) -> Optional['Item']:
         """Creates an item instance from a template ID and applies overrides."""
         if not world or not hasattr(world, 'item_templates'):
              print(f"{FORMAT_ERROR}Error: World context with item_templates required.{FORMAT_RESET}")
              return None

         template = world.item_templates.get(item_id)
         if not template:
              print(f"{FORMAT_ERROR}Error: Item template '{item_id}' not found.{FORMAT_RESET}")
              return None

         item_type_name = template.get("type", "Item")
         item_class = ItemFactory._get_item_class(item_type_name)

         if not item_class:
              print(f"{FORMAT_ERROR}Error: Unknown item type '{item_type_name}' for template '{item_id}'. Using base Item.{FORMAT_RESET}")
              item_class = ItemFactory._get_item_class("Item") # Fallback to base

         try:
              # 1. Prepare arguments from template
              creation_args = template.copy()
              creation_args["obj_id"] = item_id # Use template ID as base obj_id

              # Separate properties dict
              template_properties = creation_args.pop("properties", {})

              # 2. Apply overrides to the creation args (top-level first)
              prop_overrides = overrides.pop("properties_override", {}) # Get property overrides separately
              creation_args.update(overrides) # Apply top-level overrides first

              # 3. Create the base item instance using modified template args
              # Ensure only valid __init__ args are passed
              sig = inspect.signature(item_class.__init__)
              valid_params = set(sig.parameters.keys())
              init_args = {k: v for k, v in creation_args.items() if k in valid_params or k=='obj_id'}

              item = item_class(**init_args)

              # 4. Apply template properties
              if not hasattr(item, 'properties'): item.properties = {}
              item.properties.update(template_properties)

              # 5. Apply property overrides
              item.properties.update(prop_overrides)

              # 6. Ensure core instance attributes reflect final property values
              item.weight = item.properties.get("weight", item.weight)
              item.value = item.properties.get("value", item.value)
              item.stackable = item.properties.get("stackable", item.stackable)
              # Re-sync properties dict just in case core attributes were overridden at top level
              item.update_property("weight", item.weight)
              item.update_property("value", item.value)
              item.update_property("stackable", item.stackable)

              return item

         except Exception as e:
              print(f"{FORMAT_ERROR}Error instantiating item '{item_id}' from template: {e}{FORMAT_RESET}")
              import traceback
              traceback.print_exc()
              return None
