# utils/utils.py
import re
from core.config import FORMAT_RESET
from items.item import Item
from typing import Dict, Any, Optional, Union

from typing import TYPE_CHECKING

from utils.text_formatter import LEVEL_DIFF_COLORS, get_level_diff_category

def debug_string(s):
    print("String content:")
    for i, ch in enumerate(s):
        print(f"Position {i}: '{ch}' (ord: {ord(ch)})")
    print("End of string")

if(TYPE_CHECKING):
    from world.world import World
def _serialize_item_reference(item: 'Item', quantity: int, world: 'World') -> Optional[Dict[str, Any]]:
    """
    Creates a dictionary representing an item reference for saving.
    Includes item_id (template ID), quantity (if stackable & >1), and property overrides
    that differ from the template or represent dynamic state.
    """
    if not item:
        return None
    # Ensure item has an obj_id, which we assume corresponds to its template ID for lookup
    if not hasattr(item, 'obj_id') or not item.obj_id:
         print(f"Warning: Item '{getattr(item, 'name', 'Unknown')}' missing obj_id during serialization.")
         return None

    # Import factory locally to avoid circular dependencies at module level
    from items.item_factory import ItemFactory

    template_id = item.obj_id # Assume obj_id IS the template_id for items
    template = ItemFactory.get_template(template_id, world)

    override_props = {}
    # Define properties that ALWAYS represent dynamic state and should be saved if present
    known_dynamic_props = {"durability", "uses", "is_open", "locked", "contains"} # 'contains' for Containers

    if template:
        # Compare current item properties against template properties
        template_props = template.get("properties", {})
        for key, current_value in item.properties.items():
            # Always save known dynamic properties if they exist on the item
            if key in known_dynamic_props:
                # Special handling for container contents
                if key == "contains" and isinstance(item, ItemFactory._get_item_class("Container")): # Check if it's a Container
                    # Serialize contained items recursively
                    contained_refs = []
                    for contained_item in current_value: # current_value is List[Item]
                         ref = _serialize_item_reference(contained_item, 1, world) # Quantity inside container is 1 per entry
                         if ref: contained_refs.append(ref)
                    # Only save 'contains' if it's different from template's initial items,
                    # or if it's simply not empty (safer)
                    # TODO: Refine comparison with template's initial_items if necessary
                    if contained_refs: # Save if container has items dynamically added
                         override_props[key] = contained_refs
                else:
                    # Save if dynamic prop exists
                    override_props[key] = current_value
            # Check other properties: save if not in template or value differs
            elif key not in template_props or template_props.get(key) != current_value:
                 # Exclude core attributes that should come from template unless explicitly overridden elsewhere
                 # (e.g., weight, value, stackable, name, description, equip_slot, type)
                 # This assumes these core attributes DON'T change dynamically relative to template.
                 # If they *can* (e.g., name change), they need different handling.
                 if key not in ["weight", "value", "stackable", "name", "description", "equip_slot", "type"]:
                    override_props[key] = current_value
    else:
        # No template found - this is problematic for reference saving.
        # Fallback: Save known dynamic state, but log a clear warning.
        print(f"Warning: Item template '{template_id}' not found during serialization of '{item.name}'. Saving limited dynamic state.")
        for key in known_dynamic_props:
            if key in item.properties:
                if key == "contains" and isinstance(item, ItemFactory._get_item_class("Container")):
                    contained_refs = []
                    for contained_item in item.properties[key]:
                         ref = _serialize_item_reference(contained_item, 1, world)
                         if ref: contained_refs.append(ref)
                    if contained_refs: override_props[key] = contained_refs
                else:
                    override_props[key] = item.properties[key]

    # --- Construct the final reference dictionary ---
    ref = {"item_id": template_id} # Use the template ID

    # Only include quantity if stackable and more than 1 is being referenced
    if item.stackable and quantity > 1:
        ref["quantity"] = quantity

    # Include overrides dictionary only if it's not empty
    if override_props:
        ref["properties_override"] = override_props

    return ref

def get_article(word: str) -> str:
    """Returns 'an' if word starts with a vowel sound, else 'a'."""
    if not word:
        return "a"
    # Simple check for common vowel sounds - might need refinement for edge cases
    return "an" if word[0].lower() in 'aeiou' else "a"

def simple_plural(word: str) -> str:
    """Adds a simple 's' for pluralization. Okay for most MUD items."""
    # More complex rules (like 'es' for words ending in s, x, z, ch, sh)
    # could be added, but 's' is often sufficient.
    if not word:
        return ""
    # Avoid double 's' if it already ends in 's'
    return word + "" if word.endswith('s') else word + "s"

if TYPE_CHECKING:
    from player import Player
    from npcs.npc import NPC
def format_name_for_display(viewer: Optional[Union['Player', 'NPC']], target: Optional[Union['Player', 'NPC', Item]], start_of_sentence: bool = False) -> str:
    """
    Formats an entity's name for display with level-based color (for hostiles),
    articles for generic names, and context-aware capitalization.

    Args:
        viewer: The entity viewing the target (usually the player). Needed for level diff.
        target: The entity whose name is being formatted (Player, NPC, Item).
        start_of_sentence: True if this name is the first word in a sentence.

    Returns:
        The formatted name string.
    """
    from npcs.npc import NPC # Local import to avoid potential circularity at module level

    if not target or not hasattr(target, 'name') or not target.name:
        return "something" # Fallback

    full_name = target.name # Name might include "(Level X)"
    base_name = re.sub(r'\s*\(level \d+\)$', '', full_name, flags=re.IGNORECASE).strip()
    if not base_name: base_name = full_name # Use full name if stripping failed

    is_hostile = isinstance(target, NPC) and getattr(target, 'faction', 'neutral') == 'hostile'
    is_generic = base_name == base_name.lower() # Check if base name is lowercase
    color_code = FORMAT_RESET # Default color

    if is_hostile and viewer:
        viewer_level = getattr(viewer, 'level', 1)
        target_level = getattr(target, 'level', 1)
        color_category = get_level_diff_category(viewer_level, target_level)
        color_code = LEVEL_DIFF_COLORS.get(color_category, FORMAT_RESET)

    # Construct the core name part with color
    formatted_name = f"{color_code}{full_name}{FORMAT_RESET}"

    # Prepend article if generic
    result = ""
    if is_generic:
        article = get_article(base_name) # Get article based on base name
        result = f"{article} {formatted_name}"
    else:
        result = formatted_name # Proper name, just use the colored version

    # Capitalize if start of sentence
    if start_of_sentence and result:
        # Find the first actual letter after potential article and color codes
        first_letter_index = -1
        in_code = False
        for i, char in enumerate(result):
             if char == '[': in_code = True
             elif char == ']': in_code = False
             elif not in_code and char.isalpha():
                  first_letter_index = i
                  break

        if first_letter_index != -1:
             # Capitalize the found letter and reconstruct
             result = result[:first_letter_index] + result[first_letter_index].upper() + result[first_letter_index+1:]
        elif result: # Fallback if no letter found (e.g., just symbols?), capitalize first char
             result = result[0].upper() + result[1:]


    return result
