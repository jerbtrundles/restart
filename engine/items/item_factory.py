# engine/items/item_factory.py
import inspect
import json
import os
import random
import copy
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from engine.config import FORMAT_ERROR, FORMAT_RESET
from engine.items.gem import Gem
from engine.items.item import Item
from engine.items.weapon import Weapon
from engine.items.armor import Armor
from engine.items.consumable import Consumable
from engine.items.container import Container
from engine.items.key import Key
from engine.items.treasure import Treasure
from engine.items.junk import Junk
from engine.items.lockpick import Lockpick
from engine.magic.spell_registry import SPELL_REGISTRY

if TYPE_CHECKING:
    from engine.world.world import World

# --- Define Class Mapping at Module Level ---
ITEM_CLASS_MAP: Dict[str, Type[Item]] = {
     "Item": Item,
     "Weapon": Weapon,
     "Armor": Armor,
     "Consumable": Consumable,
     "Container": Container,
     "Key": Key,
     "Treasure": Treasure,
     "Junk": Junk,
     "Gem": Gem,
     "Lockpick": Lockpick
}
    
class ItemFactory:
    """Factory class for creating items from templates or data."""

    @staticmethod
    def create_item(item_type: str, **kwargs) -> Optional['Item']:
        """Creates a basic item instance. Less used now, prefers templates."""
        cls = ITEM_CLASS_MAP.get(item_type)
        if not cls:
            print(f"{FORMAT_ERROR}Warning: Unknown item type '{item_type}' requested in create_item. Trying base Item.{FORMAT_RESET}")
            cls = ITEM_CLASS_MAP.get("Item")

        if not cls:
             print(f"{FORMAT_ERROR}Critical Error: Base Item class not found in map.{FORMAT_RESET}")
             return None
        try:
            sig = inspect.signature(cls.__init__)
            valid_params = set(sig.parameters.keys())
            has_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
            
            valid_kwargs = {}
            extra_properties = {}
            
            for k, v in kwargs.items():
                if k in valid_params or k == 'obj_id': 
                    valid_kwargs[k] = v
                elif has_kwargs: 
                    # If the constructor accepts **kwargs, pass it through
                    valid_kwargs[k] = v
                elif k not in ['name', 'description', 'weight', 'value', 'stackable', 'type']: 
                    # If not a constructor arg and no **kwargs, put in extra_properties
                    extra_properties[k] = v
            
            item = cls(**valid_kwargs)
            for key, value in extra_properties.items(): 
                item.update_property(key, value)
            return item
        except Exception as e:
            print(f"{FORMAT_ERROR}Error creating item type '{item_type}' with args {kwargs}: {e}{FORMAT_RESET}")
            import traceback; traceback.print_exc(); return None

    @staticmethod
    def _get_item_class(item_type_name: str) -> Optional[Type['Item']]:
        """Helper to get the actual class object."""
        return ITEM_CLASS_MAP.get(item_type_name)

    @staticmethod
    def from_dict(data: Dict[str, Any], world: Optional['World'] = None) -> Optional['Item']:
        """Create an item from dict."""
        item_id = data.get("obj_id", data.get("id"))
        if item_id and world:
             overrides = data.get("properties_override", data.get("properties", {}))
             # Extract core attributes if present in data
             for key in ["name", "description", "weight", "value", "stackable"]:
                  if key in data: overrides[key] = data[key]
             item = ItemFactory.create_item_from_template(item_id, world, **overrides)
             if item: return item

        # Fallback for direct creation without template
        item_type_name = data.get("type", "Item")
        item_class = ITEM_CLASS_MAP.get(item_type_name)
        if not item_class:
             item_class = ITEM_CLASS_MAP.get("Item")
        
        if not item_class: return None
        
        try:
            if issubclass(item_class, Container): return item_class.from_dict(data, world)
            else: return item_class.from_dict(data)
        except Exception as e:
             print(f"{FORMAT_ERROR}Error creating item type '{item_type_name}' from dict: {e}{FORMAT_RESET}")
             return None

    @staticmethod
    def get_template(item_id: str, world: Optional['World'] = None) -> Optional[Dict[str, Any]]:
         """Retrieves an item template definition."""
         if world and hasattr(world, 'item_templates'):
              return world.item_templates.get(item_id)
         return None

    @staticmethod
    def create_item_from_template(item_id: str, world: 'World', **overrides) -> Optional['Item']:
        if not world or not hasattr(world, 'item_templates'): return None
        template = world.item_templates.get(item_id)
        if not template:
            # Fallback check for procedural items generated at runtime (like specific scrolls)
            if item_id.startswith("item_scroll_") and "item_scroll_random" in world.item_templates:
                 # This handles the case where we load a save with a generated scroll ID
                 # We grab the base template to ensure creation succeeds, trusting overrides to fix details
                 template = world.item_templates.get("item_scroll_random")
                 
            if not template:
                print(f"{FORMAT_ERROR}Error: Item template '{item_id}' not found.{FORMAT_RESET}")
                return None

        # --- Procedural Logic ---
        template_props = template.get("properties", {})
        if template_props.get("is_procedural", False):
            proc_type = template_props.get("procedural_type")
            new_template = copy.deepcopy(template)
            
            if proc_type == "random_spell_scroll":
                # If we are loading an item that already has specific overrides (like from save),
                # we don't want to re-randomize.
                if overrides.get("spell_to_learn"):
                     # We are loading a specific scroll, just strip the procedural flag
                     pass
                else:
                    # New generation
                    possible_spells = [s for s in SPELL_REGISTRY.values() if s.level_required > 0 and s.mana_cost > 0]
                    if possible_spells:
                        chosen_spell = random.choice(possible_spells)
                        new_item_id = f"item_scroll_{chosen_spell.spell_id}"
                        new_template['name'] = f"Scroll of {chosen_spell.name}"
                        new_template['description'] = f"A scroll inscribed with the runes for the '{chosen_spell.name}' spell."
                        new_template['value'] = chosen_spell.level_required * 50 + 50
                        new_template['properties']['spell_to_learn'] = chosen_spell.spell_id
                        
                        # Use these generated values if not overridden
                        if 'name' not in overrides: overrides['name'] = new_template['name']
                        if 'description' not in overrides: overrides['description'] = new_template['description']
                        if 'value' not in overrides: overrides['value'] = new_template['value']
                        if 'spell_to_learn' not in overrides: overrides['spell_to_learn'] = chosen_spell.spell_id
                        
            # Strip procedural flags
            if 'is_procedural' in new_template['properties']:
                del new_template['properties']['is_procedural']
            if 'procedural_type' in new_template['properties']:
                del new_template['properties']['procedural_type']
                
            template = new_template
        # ------------------------

        item_type_name = template.get("type", "Item")
        item_class = ITEM_CLASS_MAP.get(item_type_name)

        if item_class is None:
            return None

        try:
            creation_args = template.copy()
            creation_args["obj_id"] = item_id
            
            # Extract properties dict from template
            template_properties = creation_args.pop("properties", {})
            # Remove any nested 'properties_override' if it exists in kwargs (cleanup)
            if "properties_override" in overrides:
                 # This shouldn't happen with correct calling, but safety first
                 overrides.update(overrides.pop("properties_override"))

            # Merge overrides into creation args
            creation_args.update(overrides)
            
            # Introspect constructor
            sig = inspect.signature(item_class.__init__)
            valid_params = set(sig.parameters.keys())
            has_kwargs = any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values())
            
            # Filter arguments
            if has_kwargs:
                # If class accepts **kwargs, pass everything
                init_args = creation_args
            else:
                # Strict filtering
                init_args = {k: v for k, v in creation_args.items() if k in valid_params or k == 'obj_id'}

            # Handle equip_slot specifically if in overrides
            if 'equip_slot' in valid_params and 'equip_slot' in overrides:
                init_args['equip_slot'] = overrides['equip_slot']
            
            # Instantiate
            item = item_class(**init_args)

            # Apply properties
            if not hasattr(item, 'properties'): item.properties = {}
            
            # 1. Apply Template Properties
            for key, value in template_properties.items():
                 # Skip if handled by init explicitly (to avoid overwriting if init did logic)
                 if key == 'equip_slot' and 'equip_slot' in init_args: continue
                 item.properties[key] = value

            # 2. Apply Overrides to Properties
            # If the class didn't have **kwargs, the overrides weren't passed to __init__.
            # We must manually ensure they end up in properties.
            if not has_kwargs:
                 for key, value in overrides.items():
                      # Skip items that were valid params (like name, weight) as they are attrs
                      if key not in valid_params and key != 'obj_id':
                           item.properties[key] = value
            
            # Ensure core attributes update properties dict for consistency
            item.weight = getattr(item, 'weight', 0.0)
            item.value = getattr(item, 'value', 0)
            item.stackable = getattr(item, 'stackable', False)
            
            item.update_property("weight", item.weight)
            item.update_property("value", item.value)
            item.update_property("stackable", item.stackable)
            
            return item

        except Exception as e:
            print(f"{FORMAT_ERROR}Error creating item '{item_id}': {e}{FORMAT_RESET}")
            return None