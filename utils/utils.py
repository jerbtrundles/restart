# utils/utils.py
import random
import re
from core.config import DEBUG_SHOW_LEVEL, FORMAT_CATEGORY, FORMAT_FRIENDLY_NPC, FORMAT_RESET, LEVEL_DIFF_COMBAT_MODIFIERS, MIN_XP_GAIN, XP_GAIN_HEALTH_DIVISOR, XP_GAIN_LEVEL_MULTIPLIER
from items.item import Item
from typing import Dict, Any, List, Optional, Union

from typing import TYPE_CHECKING

from utils.text_formatter import LEVEL_DIFF_COLORS, get_level_diff_category

DEPARTURE_VERBS = [
    "leaves", "heads", "departs", "goes", "wanders",
    "proceeds", "ventures", "ambles", "strolls", "moves", "sets off"
]
ARRIVAL_VERBS = [
    "arrives", "enters", "appears", "comes", "walks in",
    "emerges", "shows up", "ambles in", "strolls in"
]

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
def format_name_for_display(
    viewer: Optional[Union['Player', 'NPC']],
    target: Optional[Union['Player', 'NPC', Item]],
    start_of_sentence: bool = False
) -> str:
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

    base_name = target.name # <<< ASSUME target.name is CLEAN BASE NAME
    target_level = getattr(target, 'level', None) # Get level if it exists
    is_npc = isinstance(target, NPC)
    is_item = isinstance(target, Item)
    is_hostile = is_npc and getattr(target, 'faction', 'neutral') == 'hostile'
    is_generic = not base_name[0].isupper() if base_name else True

    color_code = FORMAT_RESET # Default color

    # --- Determine Level Suffix ---
    level_suffix = ""
    if is_npc and target_level is not None and DEBUG_SHOW_LEVEL:
        # Add level suffix for ALL NPCs for consistency during display
        level_suffix = f" (Level {target_level})"

    # --- UPDATED Color Determination Logic ---
    if is_npc:
        is_friendly = getattr(target, 'friendly', False) # Check the friendly attribute
        faction = getattr(target, 'faction', 'neutral')

        if is_friendly:
            color_code = FORMAT_FRIENDLY_NPC # <<< USE FRIENDLY COLOR
        elif faction == 'hostile' and viewer and target_level is not None:
            # Hostile: Use level-based coloring (existing logic)
            viewer_level = getattr(viewer, 'level', 1)
            color_category = get_level_diff_category(viewer_level, target_level)
            color_code = LEVEL_DIFF_COLORS.get(color_category, FORMAT_RESET)
        # Else (Neutral NPC): color remains FORMAT_RESET (default white)

    elif is_item:
        color_code = FORMAT_CATEGORY # Items use category color
    # --- END UPDATED Color Logic ---


    # Construct the name part including level suffix *before* color
    name_with_level = f"{base_name}{level_suffix}"
    formatted_name_part = f"{color_code}{name_with_level}{FORMAT_RESET}"

    # Prepend article if generic
    result = ""
    if is_generic: # Add article if name seems generic (lowercase start)
        article = get_article(base_name) # Article based on base name
        result = f"{article} {formatted_name_part}"
    else:
        result = formatted_name_part

    # Capitalize if start of sentence (same logic as before)
    if start_of_sentence and result:
        first_letter_index = -1; in_code = False
        for i, char in enumerate(result):
             if char == '[': in_code = True
             elif char == ']': in_code = False
             elif not in_code and char.isalpha(): first_letter_index = i; break
        if first_letter_index != -1:
             result = result[:first_letter_index] + result[first_letter_index].upper() + result[first_letter_index+1:]
        elif result: result = result[0].upper() + result[1:]

    return result

def _reverse_direction(direction: str) -> str:
    """Gets the opposite cardinal/relative direction."""
    opposites = {
        "north": "south", "south": "north",
        "east": "west", "west": "east",
        "northeast": "southwest", "southwest": "northeast",
        "northwest": "southeast", "southeast": "northwest",
        "up": "down", "down": "up",
        "in": "out", "out": "in",
        # Add other potential directions if needed
        "enter": "exit", "exit": "enter",
        "inside": "outside", "outside": "inside",
        "surface": "dive", "dive": "surface", # For water
        "climb": "descend", "descend": "climb" # For climbing
    }
    # fallback, needs work; we have "downstream, upstream" exits that need special attention, for example
    return opposites.get(direction.lower(), "somewhere opposite")


def get_departure_phrase(direction: str) -> str:
    """Gets a natural language phrase for leaving in a direction."""
    direction = direction.lower()
    phrases = {
        "up": "upwards",
        "down": "downwards",
        "in": "inside",
        "enter": "inside",
        "inside": "inside",
        "out": "outside",
        "exit": "outside",
        "outside": "outside",
        "dive": "diving down",
        "climb": "climbing up",
        # Add more special cases as needed
    }
    # Default for cardinal directions
    if direction in ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]:
        return f"to the {direction}"

    return phrases.get(direction, f"towards the {direction}") # Use specific phrase or default

def get_arrival_phrase(direction: str) -> str:
    """Gets a natural language phrase for arriving from a direction."""
    # Note: This function expects the direction the NPC *came from*
    direction = direction.lower()
    phrases = {
        "up": "from above",
        "down": "from below",
        "in": "from inside",
        "enter": "from inside",
        "inside": "from inside",
        "out": "from outside",
        "exit": "from outside",
        "outside": "from outside",
        "dive": "surfacing", # Arriving from diving
        "surface": "diving down", # Arriving from surfacing (unlikely arrival dir?)
        "climb": "climbing down", # Arrived from climbing up
        "descend": "climbing up", # Arrived from descending
        # Add more special cases
    }
     # Default for cardinal directions
    if direction in ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]:
        return f"from the {direction}"

    return phrases.get(direction, f"from {direction}") # Use specific phrase or default

def format_npc_departure_message(npc: 'NPC', direction: str, viewer: Optional['Player']) -> str:
    """Creates a varied departure message."""
    # Pass viewer to format_name_for_display
    formatted_name = format_name_for_display(viewer, npc, start_of_sentence=True)
    verb = random.choice(DEPARTURE_VERBS)
    directional_phrase = get_departure_phrase(direction)
    return f"{formatted_name} {verb} {directional_phrase}."

def format_npc_arrival_message(npc: 'NPC', direction_exited_from: str, viewer: Optional['Player']) -> str:
    """Creates a varied arrival message."""
    # Pass viewer to format_name_for_display
    formatted_name = format_name_for_display(viewer, npc, start_of_sentence=True)
    verb = random.choice(ARRIVAL_VERBS)
    arrival_direction = _reverse_direction(direction_exited_from)
    directional_phrase = get_arrival_phrase(arrival_direction)
    return f"{formatted_name} {verb} {directional_phrase}."

def calculate_xp_gain(killer_level: int, target_level: int, target_max_health: int) -> int:
    """
    Calculates the experience points gained for defeating a target.

    Args:
        killer_level: The level of the entity that performed the kill (or owner's level for minions).
        target_level: The level of the defeated target.
        target_max_health: The maximum health of the defeated target.

    Returns:
        The calculated XP amount, clamped by MIN_XP_GAIN.
    """
    # Base XP calculation
    base_xp_gained = max(1, target_max_health // XP_GAIN_HEALTH_DIVISOR) + target_level * XP_GAIN_LEVEL_MULTIPLIER

    # Apply level difference modifier
    category = get_level_diff_category(killer_level, target_level)
    _, _, xp_mod = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
    final_xp_gained = int(base_xp_gained * xp_mod)

    # Ensure minimum XP
    final_xp_gained = max(MIN_XP_GAIN, final_xp_gained)

    return final_xp_gained
# --- END NEW ---

# --- NEW: Loot Message Formatting Utility ---
def format_loot_drop_message(viewer: Optional[Union['Player', 'NPC']], target: Union['Player', 'NPC'], dropped_items: List[Item]) -> str:
    """
    Formats the message indicating what loot a target dropped.

    Args:
        viewer: The entity viewing the event (usually the player).
        target: The entity that dropped the loot.
        dropped_items: A list of Item instances that were dropped.

    Returns:
        A formatted string describing the loot drop, or an empty string if no items.
    """
    if not dropped_items:
        return ""

    # Aggregate loot counts
    loot_counts: Dict[str, Dict[str, Any]] = {} # item_id -> {"name": str, "count": int}
    for item in dropped_items:
        item_id = item.obj_id # Use obj_id which should be the template ID
        if item_id not in loot_counts:
            loot_counts[item_id] = {"name": item.name, "count": 0}
        loot_counts[item_id]["count"] += 1

    # Format message parts
    loot_message_parts = []
    for item_id, data in loot_counts.items():
        name = data["name"]
        count = data["count"]
        if count == 1:
            article = get_article(name)
            loot_message_parts.append(f"{article} {name}")
        else:
            plural_name = simple_plural(name)
            loot_message_parts.append(f"{count} {plural_name}")

    # Construct the sentence
    loot_str = ""
    # Use format_name_for_display relative to the viewer
    formatted_target_name_start = format_name_for_display(viewer, target, start_of_sentence=True)

    if not loot_message_parts:
        return "" # Should not happen if dropped_items was not empty, but safety check
    elif len(loot_message_parts) == 1:
        loot_str = f"{formatted_target_name_start} dropped {loot_message_parts[0]}."
    elif len(loot_message_parts) == 2:
        loot_str = f"{formatted_target_name_start} dropped {loot_message_parts[0]} and {loot_message_parts[1]}."
    else: # More than 2 items
        all_but_last = ", ".join(loot_message_parts[:-1])
        last_item = loot_message_parts[-1]
        loot_str = f"{formatted_target_name_start} dropped {all_but_last}, and {last_item}."

    return loot_str
# --- END NEW ---
