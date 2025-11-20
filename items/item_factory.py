# items/item_factory.py
import inspect
import json
import os
import random
import copy # NEW: Import copy for deepcopy
from typing import TYPE_CHECKING, Any, Dict, Optional, Type

from config import FORMAT_ERROR, FORMAT_RESET
from items.gem import Gem
from items.item import Item
from items.weapon import Weapon
from items.armor import Armor
from items.consumable import Consumable
from items.container import Container
from items.key import Key
from items.treasure import Treasure
from items.junk import Junk
from items.lockpick import Lockpick
from magic.spell_registry import SPELL_REGISTRY

if TYPE_CHECKING:
    from world.world import World

# --- Define Class Mapping at Module Level ---
# Create the map *after* imports
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
print(f"[Item Factory Startup] Final ITEM_CLASS_MAP: {ITEM_CLASS_MAP}")
    
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
                if k in valid_params or k == 'obj_id': valid_kwargs[k] = v
                elif has_kwargs: valid_kwargs[k] = v
                elif k not in ['name', 'description', 'weight', 'value', 'stackable', 'type']: extra_properties[k] = v
            item = cls(**valid_kwargs)
            for key, value in extra_properties.items(): item.update_property(key, value)
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
        item_class = ITEM_CLASS_MAP.get(item_type_name)
        if not item_class:
             print(f"{FORMAT_ERROR}Error: Unknown item type '{item_type_name}' in from_dict. Using base Item.{FORMAT_RESET}")
             item_class = ITEM_CLASS_MAP.get("Item")
        if not item_class:
             print(f"{FORMAT_ERROR}Critical Error: Base Item class not found in map during from_dict.{FORMAT_RESET}")
             return None
        try:
            if issubclass(item_class, Container): return item_class.from_dict(data, world)
            else: return item_class.from_dict(data)
        except Exception as e:
             print(f"{FORMAT_ERROR}Error creating item type '{item_type_name}' directly from dict: {e}{FORMAT_RESET}")
             return None

    @staticmethod
    def get_template(item_id: str, world: Optional['World'] = None) -> Optional[Dict[str, Any]]:
         """Retrieves an item template definition."""
         if world and hasattr(world, 'item_templates'):
              return world.item_templates.get(item_id)
         print(f"Warning: Cannot get template for '{item_id}'. World or templates missing.")
         return None

    @staticmethod
    def create_item_from_template(item_id: str, world: 'World', **overrides) -> Optional['Item']:
        if not world or not hasattr(world, 'item_templates'): return None
        template = world.item_templates.get(item_id)
        if not template:
            print(f"{FORMAT_ERROR}Error: Item template '{item_id}' not found.{FORMAT_RESET}")
            return None

        # --- NEW: Procedural Item Transmutation Logic ---
        template_props = template.get("properties", {})
        if template_props.get("is_procedural", False):
            proc_type = template_props.get("procedural_type")
            
            # Create a deep copy to modify, preserving the original template
            new_template = copy.deepcopy(template)
            
            if proc_type == "random_spell_scroll":
                possible_spells = [s for s in SPELL_REGISTRY.values() if s.level_required > 0 and s.mana_cost > 0]
                if not possible_spells:
                    print(f"{FORMAT_ERROR}Cannot generate random scroll: no valid spells found.{FORMAT_RESET}")
                    return None
                
                chosen_spell = random.choice(possible_spells)
                
                # Generate new, concrete properties for this specific scroll type
                new_item_id = f"item_scroll_{chosen_spell.spell_id}"
                new_name = f"Scroll of {chosen_spell.name}"
                new_description = f"A scroll inscribed with the runes for the '{chosen_spell.name}' spell."
                new_value = chosen_spell.level_required * 50 + 50
                
                # Update the copied template with the new concrete data
                new_template['name'] = new_name
                new_template['description'] = new_description
                new_template['value'] = new_value
                new_template['properties']['spell_to_learn'] = chosen_spell.spell_id
                
                # CRITICAL: Remove the procedural flags to make it a normal item
                del new_template['properties']['is_procedural']
                if 'procedural_type' in new_template['properties']:
                    del new_template['properties']['procedural_type']
                
                # The rest of the function will now use this new, concrete template
                template = new_template
                item_id = new_item_id
        # --- END: Procedural Item Transmutation Logic ---

        item_type_name = template.get("type", "Item")
        item_class = ITEM_CLASS_MAP.get(item_type_name)

        if item_class is None:
            print(f"{FORMAT_ERROR}Critical Error: Class lookup failed for type '{item_type_name}' (from template '{item_id}').{FORMAT_RESET}")
            return None

        try:
            creation_args = template.copy()
            creation_args["obj_id"] = item_id
            
            template_properties = creation_args.pop("properties", {})
            prop_overrides = overrides.pop("properties_override", {})
            
            creation_args.update(overrides)
            
            sig = inspect.signature(item_class.__init__)
            valid_params = set(sig.parameters.keys())
            init_args = {k: v for k, v in creation_args.items() if k in valid_params or k == 'obj_id'}

            if 'equip_slot' in valid_params:
                slot_value = prop_overrides.get('equip_slot', template_properties.get('equip_slot'))
                if slot_value is not None:
                    init_args['equip_slot'] = slot_value
            
            item = item_class(**init_args)

            if not hasattr(item, 'properties'): item.properties = {}
            for key, value in template_properties.items():
                 if key == 'equip_slot' and 'equip_slot' in init_args:
                      continue
                 item.properties[key] = value

            for key, value in prop_overrides.items():
                if key == 'equip_slot' and 'equip_slot' in init_args:
                     continue
                item.properties[key] = value

            item.weight = item.properties.get("weight", getattr(item, 'weight', 0.0))
            item.value = item.properties.get("value", getattr(item, 'value', 0))
            item.stackable = item.properties.get("stackable", getattr(item, 'stackable', False))
            if 'name' in overrides: item.name = overrides['name']
            if 'description' in overrides: item.description = overrides['description']
            item.update_property("weight", item.weight)
            item.update_property("value", item.value)
            item.update_property("stackable", item.stackable)
            
            if 'equip_slot' in init_args:
                item.update_property("equip_slot", init_args['equip_slot'])

            return item

        except Exception as e:
            print(f"{FORMAT_ERROR}General Error instantiating item '{item_id}' from template: {e}{FORMAT_RESET}")
            import traceback; traceback.print_exc(); return None