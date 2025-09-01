# utils/utils.py
# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Renamed the inner 'ref' variable to 'contained_ref' during the recursive call
#   to avoid variable shadowing and resolve the Pylance type assignment error.

import random
import re
from core.config import DEBUG_SHOW_LEVEL, FORMAT_CATEGORY, FORMAT_FRIENDLY_NPC, FORMAT_RESET, LEVEL_DIFF_COMBAT_MODIFIERS, MIN_XP_GAIN, XP_GAIN_HEALTH_DIVISOR, XP_GAIN_LEVEL_MULTIPLIER
from items.item import Item
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING, Tuple

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
    from player import Player
    from npcs.npc import NPC

def _serialize_item_reference(item: 'Item', quantity: int, world: 'World') -> Optional[Dict[str, Any]]:
    """
    Creates a dictionary representing an item reference for saving.
    """
    if not item:
        return None
    if not hasattr(item, 'obj_id') or not item.obj_id:
         print(f"Warning: Item '{getattr(item, 'name', 'Unknown')}' missing obj_id during serialization.")
         return None

    from items.item_factory import ItemFactory

    template_id = item.obj_id
    template = ItemFactory.get_template(template_id, world)

    override_props: Dict[str, Any] = {}
    known_dynamic_props = {"durability", "uses", "is_open", "locked", "contains"}

    if template:
        template_props = template.get("properties", {})
        for key, current_value in item.properties.items():
            if key in known_dynamic_props:
                ContainerClass = ItemFactory._get_item_class("Container")
                if key == "contains" and ContainerClass and isinstance(item, ContainerClass):
                    contained_refs: List[Dict[str, Any]] = []
                    if isinstance(current_value, list):
                        for contained_item in current_value:
                            # <<< FIX: Use a different variable name to avoid shadowing >>>
                            contained_ref = _serialize_item_reference(contained_item, 1, world)
                            if contained_ref:
                                contained_refs.append(contained_ref)
                    if contained_refs:
                        override_props[key] = contained_refs
                else:
                    override_props[key] = current_value
            elif key not in template_props or template_props.get(key) != current_value:
                 if key not in ["weight", "value", "stackable", "name", "description", "equip_slot", "type", "max_durability", "max_uses", "effect_type", "effect_value", "damage", "defense", "target_id", "treasure_type"]:
                    override_props[key] = current_value
    else:
        print(f"Warning: Item template '{template_id}' not found during serialization of '{item.name}'. Saving only known dynamic state.")
        for key in known_dynamic_props:
            if key in item.properties:
                ContainerClass = ItemFactory._get_item_class("Container")
                if key == "contains" and ContainerClass and isinstance(item, ContainerClass):
                    contained_refs: List[Dict[str, Any]] = []
                    if isinstance(item.properties[key], list):
                        for contained_item in item.properties[key]:
                            # <<< FIX: Use a different variable name here as well >>>
                            contained_ref = _serialize_item_reference(contained_item, 1, world)
                            if contained_ref:
                                contained_refs.append(contained_ref)
                    if contained_refs: override_props[key] = contained_refs
                else:
                    override_props[key] = item.properties[key]

    if world and world.game and world.game.debug_mode and override_props:
         print(f"[Save DBG] Overrides for {item.name} ({template_id}): {override_props}")

    ref: Dict[str, Any] = {"item_id": template_id}

    if item.stackable and quantity > 1:
        ref["quantity"] = quantity

    if override_props:
        ref["properties_override"] = override_props

    return ref

def get_article(word: str) -> str:
    """Returns 'an' if word starts with a vowel sound, else 'a'."""
    if not word:
        return "a"
    return "an" if word[0].lower() in 'aeiou' else "a"

def simple_plural(word: str) -> str:
    """Adds a simple 's' for pluralization."""
    if not word:
        return ""
    return word + "" if word.endswith('s') else word + "s"

def format_name_for_display(
    viewer: Optional[Union['Player', 'NPC']],
    target: Optional[Union['Player', 'NPC', Item]],
    start_of_sentence: bool = False
) -> str:
    """Formats an entity's name for display."""
    from npcs.npc import NPC

    if not target or not hasattr(target, 'name') or not target.name:
        return "something"

    base_name = target.name
    target_level = getattr(target, 'level', None)
    is_npc = isinstance(target, NPC)
    is_item = isinstance(target, Item)
    is_hostile = is_npc and getattr(target, 'faction', 'neutral') == 'hostile'
    is_generic = not base_name[0].isupper() if base_name else True

    color_code = FORMAT_RESET

    level_suffix = ""
    if is_npc and target_level is not None and DEBUG_SHOW_LEVEL:
        level_suffix = f" (Level {target_level})"

    if is_npc:
        is_friendly = getattr(target, 'friendly', False)
        faction = getattr(target, 'faction', 'neutral')

        if is_friendly:
            color_code = FORMAT_FRIENDLY_NPC
        elif faction == 'hostile' and viewer and target_level is not None:
            viewer_level = getattr(viewer, 'level', 1)
            color_category = get_level_diff_category(viewer_level, target_level)
            color_code = LEVEL_DIFF_COLORS.get(color_category, FORMAT_RESET)
    elif is_item:
        color_code = FORMAT_CATEGORY

    name_with_level = f"{base_name}{level_suffix}"
    formatted_name_part = f"{color_code}{name_with_level}{FORMAT_RESET}"

    result = ""
    if is_generic:
        article = get_article(base_name)
        result = f"{article} {formatted_name_part}"
    else:
        result = formatted_name_part

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
        "enter": "exit", "exit": "enter",
        "inside": "outside", "outside": "inside",
        "surface": "dive", "dive": "surface",
        "climb": "descend", "descend": "climb"
    }
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
    }
    if direction in ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]:
        return f"to the {direction}"

    return phrases.get(direction, f"towards the {direction}")

def get_arrival_phrase(direction: str) -> str:
    """Gets a natural language phrase for arriving from a direction."""
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
        "dive": "surfacing",
        "surface": "diving down",
        "climb": "climbing down",
        "descend": "climbing up",
    }
    if direction in ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]:
        return f"from the {direction}"

    return phrases.get(direction, f"from {direction}")

def format_npc_departure_message(npc: 'NPC', direction: str, viewer: Optional['Player']) -> str:
    """Creates a varied departure message."""
    formatted_name = format_name_for_display(viewer, npc, start_of_sentence=True)
    verb = random.choice(DEPARTURE_VERBS)
    directional_phrase = get_departure_phrase(direction)
    return f"{formatted_name} {verb} {directional_phrase}."

def format_npc_arrival_message(npc: 'NPC', direction_exited_from: str, viewer: Optional['Player']) -> str:
    """Creates a varied arrival message."""
    formatted_name = format_name_for_display(viewer, npc, start_of_sentence=True)
    verb = random.choice(ARRIVAL_VERBS)
    arrival_direction = _reverse_direction(direction_exited_from)
    directional_phrase = get_arrival_phrase(arrival_direction)
    return f"{formatted_name} {verb} {directional_phrase}."

def calculate_xp_gain(killer_level: int, target_level: int, target_max_health: int) -> int:
    """Calculates the experience points gained for defeating a target."""
    base_xp_gained = max(1, target_max_health // XP_GAIN_HEALTH_DIVISOR) + target_level * XP_GAIN_LEVEL_MULTIPLIER
    category = get_level_diff_category(killer_level, target_level)
    _, _, xp_mod = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
    final_xp_gained = int(base_xp_gained * xp_mod)
    final_xp_gained = max(MIN_XP_GAIN, final_xp_gained)
    return final_xp_gained

def format_loot_drop_message(viewer: Optional[Union['Player', 'NPC']], target: Union['Player', 'NPC'], dropped_items: List[Item]) -> str:
    """Formats the message indicating what loot a target dropped."""
    if not dropped_items:
        return ""

    loot_counts: Dict[str, Dict[str, Any]] = {}
    for item in dropped_items:
        item_id = item.obj_id
        if item_id not in loot_counts:
            loot_counts[item_id] = {"name": item.name, "count": 0}
        loot_counts[item_id]["count"] += 1

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

    loot_str = ""
    formatted_target_name_start = format_name_for_display(viewer, target, start_of_sentence=True)

    if not loot_message_parts:
        return ""
    elif len(loot_message_parts) == 1:
        loot_str = f"{formatted_target_name_start} dropped {loot_message_parts[0]}."
    elif len(loot_message_parts) == 2:
        loot_str = f"{formatted_target_name_start} dropped {loot_message_parts[0]} and {loot_message_parts[1]}."
    else:
        all_but_last = ", ".join(loot_message_parts[:-1])
        last_item = loot_message_parts[-1]
        loot_str = f"{formatted_target_name_start} dropped {all_but_last}, and {last_item}."

    return loot_str