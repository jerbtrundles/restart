# utils/utils.py
from items.item import Item
from typing import Dict, Any, Optional

from typing import TYPE_CHECKING

def debug_string(s):
    print("String content:")
    for i, ch in enumerate(s):
        print(f"Position {i}: '{ch}' (ord: {ord(ch)})")
    print("End of string")

if(TYPE_CHECKING):
    from world.world import World
def _serialize_item_reference(item: Item, quantity: int, world: 'World') -> Optional[Dict[str, Any]]:
    """
    Creates a dictionary representing an item reference for saving.
    Includes item_id, quantity (if >1 or stackable), and property overrides.
    """
    if not item:
        return None

    from items.item_factory import ItemFactory # If needed
    override_props = {}
    # Get the template to compare against
    template = ItemFactory.get_template(item.obj_id, world) # Pass world context

    if template:
        template_props = template.get("properties", {})
        # Iterate through the *item's* current properties
        for key, current_value in item.properties.items():
            # Save property if it's known to change (like durability/uses)
            # OR if it differs from the template's value
            # OR if it's not present in the template at all (custom property)
            if key in ["durability", "uses"] or \
               key not in template_props or \
               template_props.get(key) != current_value:
                 # Exclude non-state core attributes that come from template
                 if key not in ["weight", "value", "stackable", "name", "description", "equip_slot", "type"]:
                      override_props[key] = current_value
    else:
        # If no template, save all properties except core ones? Risky.
        # Or save only known stateful properties. Let's stick to known stateful.
        print(f"Warning: No template for item {item.obj_id} during save ref check. Saving only known state.")
        if "durability" in item.properties:
             override_props["durability"] = item.properties["durability"]
        if "uses" in item.properties:
             override_props["uses"] = item.properties["uses"]
        # Add other known stateful properties here if needed

    ref = {"item_id": item.obj_id}
    # Only include quantity if stackable and > 1
    if item.stackable and quantity > 1:
        ref["quantity"] = quantity
    # Include overrides if any exist
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
