# items/item_factory.py
import inspect
import json
import os
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from core.config import FORMAT_ERROR, FORMAT_RESET
from items.item import Item
from items.weapon import Weapon
from items.armor import Armor
from items.consumable import Consumable
from items.container import Container
from items.key import Key
from items.treasure import Treasure
from items.junk import Junk

if TYPE_CHECKING:
    from world.world import World

# --- Define the Class Mapping at Module Level ---
# Create the map *after* imports. Use getattr to handle potential None from failed imports.
ITEM_CLASS_MAP: Dict[str, Type[Item]] = {
     "Item": Item,
     "Weapon": Weapon,       # Use imported class directly
     "Armor": Armor,         # Use imported class directly
     "Consumable": Consumable,
     "Container": Container,
     "Key": Key,
     "Treasure": Treasure,
     "Junk": Junk
     # Add other mappings directly
}
print(f"[Factory Startup] Final ITEM_CLASS_MAP: {ITEM_CLASS_MAP}")
    
class ItemFactory:
    """Factory class for creating items from templates or data."""

    @staticmethod
    def create_item(item_type: str, **kwargs) -> Optional['Item']:
        """Creates a basic item instance. Less used now, prefers templates."""
        # Use the module-level map
        cls = ITEM_CLASS_MAP.get(item_type)
        if not cls:
            print(f"{FORMAT_ERROR}Warning: Unknown item type '{item_type}' requested in create_item. Trying base Item.{FORMAT_RESET}")
            cls = ITEM_CLASS_MAP.get("Item")

        if not cls:
             print(f"{FORMAT_ERROR}Critical Error: Base Item class not found in map.{FORMAT_RESET}")
             return None
        try:
            # ... (rest of create_item logic - unchanged, uses cls) ...
            sig = inspect.signature(cls.__init__)
            valid_params = set(sig.parameters.keys())
            has_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
            valid_kwargs = {}
            extra_properties = {}
            for k, v in kwargs.items():
                if k in valid_params or k == 'obj_id': valid_kwargs[k] = v
                elif has_kwargs: valid_kwargs[k] = v
                elif k not in ['name', 'description', 'weight', 'value', 'stackable', 'type']: extra_properties[k] = v
            item = cls(**valid_kwargs)
            for key, value in extra_properties.items(): item.update_property(key, value)
            # Optional safety checks for core attrs if needed
            # if 'weight' in kwargs: item.weight = kwargs['weight'] # etc.
            return item
        except Exception as e:
            print(f"{FORMAT_ERROR}Error creating item type '{item_type}' with args {kwargs}: {e}{FORMAT_RESET}")
            import traceback; traceback.print_exc(); return None

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
    def from_dict(data: Dict[str, Any], world: Optional['World'] = None) -> Optional['Item']:
        """DEPRECATED? Create an item from dict. Prefers create_item_from_template."""
        item_id = data.get("obj_id", data.get("id"))
        if item_id and world:
             overrides = data.get("properties_override", data.get("properties", {}))
             for key in ["name", "description", "weight", "value", "stackable"]:
                  if key in data: overrides[key] = data[key]
             item = ItemFactory.create_item_from_template(item_id, world, **overrides)
             if item: return item

        print(f"Warning: Creating item '{data.get('name', 'Unknown')}' directly from dict (template lookup failed or ID missing).")
        item_type_name = data.get("type", "Item")
        # Use the module-level map
        item_class = ITEM_CLASS_MAP.get(item_type_name)
        if not item_class:
             print(f"{FORMAT_ERROR}Error: Unknown item type '{item_type_name}' in from_dict. Using base Item.{FORMAT_RESET}")
             item_class = ITEM_CLASS_MAP.get("Item")
        if not item_class:
             print(f"{FORMAT_ERROR}Critical Error: Base Item class not found in map during from_dict.{FORMAT_RESET}")
             return None
        try:
            # Use the class's standard from_dict
            if issubclass(item_class, Container): return item_class.from_dict(data, world)
            else: return item_class.from_dict(data)
        except Exception as e:
             print(f"{FORMAT_ERROR}Error creating item type '{item_type_name}' directly from dict: {e}{FORMAT_RESET}")
             return None

    @staticmethod
    def get_template(item_id: str, world: Optional['World'] = None) -> Optional[Dict[str, Any]]:
         """Retrieves an item template definition."""
         # ... (unchanged) ...
         if world and hasattr(world, 'item_templates'):
              return world.item_templates.get(item_id)
         print(f"Warning: Cannot get template for '{item_id}'. World or templates missing.")
         return None

    @staticmethod
    def create_item_from_template(item_id: str, world: 'World', **overrides) -> Optional['Item']:
        # ... (template loading logic) ...
        if not world or not hasattr(world, 'item_templates'): return None
        template = world.item_templates.get(item_id)
        if not template: print(f"{FORMAT_ERROR}Error: Item template '{item_id}' not found.{FORMAT_RESET}"); return None

        item_type_name = template.get("type", "Item") # Should be "Weapon" or "Armor"

        # --- Direct Lookup ---
        item_class = ITEM_CLASS_MAP.get(item_type_name) # Look up using the string from JSON

        # --- Explicit Check for None ---
        if item_class is None:
            # Print detailed error if lookup failed
            print(f"{FORMAT_ERROR}Critical Error: Class lookup failed for type '{item_type_name}' (from template '{item_id}'). Check ITEM_CLASS_MAP and imports.{FORMAT_RESET}")
            # Fallback to base Item *if possible*
            item_class = ITEM_CLASS_MAP.get("Item")
            if item_class is None: # Base Item missing too? Major problem.
                print(f"{FORMAT_ERROR}Critical Error: Base 'Item' class not found in ITEM_CLASS_MAP! Cannot create item.{FORMAT_RESET}")
                return None # Cannot proceed
            else:
                print(f"{FORMAT_ERROR}Attempting to create base 'Item' instead.{FORMAT_RESET}")

        try:
            # 1. Prepare arguments from template
            creation_args = template.copy()
            creation_args["obj_id"] = item_id

            # Separate properties dicts
            template_properties = creation_args.pop("properties", {})
            prop_overrides = overrides.pop("properties_override", {}) # Get property overrides separately

            # 2. Apply top-level overrides to creation args
            creation_args.update(overrides) # Apply top-level overrides first

            # 3. Prepare init_args based on signature, BUT ADD equip_slot logic
            sig = inspect.signature(item_class.__init__)
            valid_params = set(sig.parameters.keys())
            init_args = {k: v for k, v in creation_args.items() if k in valid_params or k == 'obj_id'}

            # --- *** NEW: Add equip_slot handling *** ---
            # Check if equip_slot is a required parameter for this class
            if 'equip_slot' in valid_params:
                # Prioritize override, then template properties
                slot_value = prop_overrides.get('equip_slot', template_properties.get('equip_slot'))
                if slot_value is not None:
                    init_args['equip_slot'] = slot_value # Add to args passed to __init__
            # --- *** END NEW *** ---

            # 4. Create the base item instance
            print(f"[Factory Debug] Attempting to instantiate '{item_id}' using class '{item_class.__name__ if item_class else 'None'}' with init_args: {init_args}")
            item = item_class(**init_args)

            # 5. Apply template properties (excluding equip_slot if already handled)
            if not hasattr(item, 'properties'): item.properties = {}
            # Add template properties, potentially overwriting defaults set by __init__
            for key, value in template_properties.items():
                 # Don't overwrite equip_slot if it was passed via init_args
                 if key == 'equip_slot' and 'equip_slot' in init_args:
                      continue
                 item.properties[key] = value # Apply other template props

            # 6. Apply property overrides (excluding equip_slot if handled)
            for key, value in prop_overrides.items():
                if key == 'equip_slot' and 'equip_slot' in init_args:
                     continue
                item.properties[key] = value # Apply overrides

            # 7. Ensure core instance attributes reflect final property values
            item.weight = item.properties.get("weight", getattr(item, 'weight', 0.0))
            item.value = item.properties.get("value", getattr(item, 'value', 0))
            item.stackable = item.properties.get("stackable", getattr(item, 'stackable', False))
            if 'name' in overrides: item.name = overrides['name']
            if 'description' in overrides: item.description = overrides['description']
            item.update_property("weight", item.weight)
            item.update_property("value", item.value)
            item.update_property("stackable", item.stackable)
            # Ensure equip_slot is also in properties if it came from init_args
            if 'equip_slot' in init_args:
                item.update_property("equip_slot", init_args['equip_slot'])

            # ... (Container handling) ...
            return item

        except TypeError as te: # Catch the specific error
             print(f"{FORMAT_ERROR}TypeError during instantiation of '{item_id}' (Class: {item_class}): {te}{FORMAT_RESET}")
             print(f"{FORMAT_ERROR}Args passed to constructor: {init_args}{FORMAT_RESET}")
             import traceback; traceback.print_exc(); return None # Print traceback
        except Exception as e:
             print(f"{FORMAT_ERROR}General Error instantiating item '{item_id}' from template: {e}{FORMAT_RESET}")
             import traceback; traceback.print_exc(); return None
