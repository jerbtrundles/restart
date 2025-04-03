# magic/effects.py
# *** NEW: Central Spell Effect Application Logic ***
# Place this function outside the Player class, maybe in a new magic/effects.py file or keep here for now
import random
import time
from typing import TYPE_CHECKING, Any, Tuple, Union

from utils.text_formatter import format_target_name
from magic.spell import Spell # Ensure time is imported if not already

if TYPE_CHECKING:
    from player import Player
    from npcs.npc import NPC

# Define a type hint for caster/target if needed
CasterTargetType = Union['Player', 'NPC']

def apply_spell_effect(caster: CasterTargetType, target: CasterTargetType, spell: Spell) -> Tuple[int, str]:
    """Applies the spell's effect to the target and returns the value and message."""
    value = 0
    message = ""

    # --- Calculate Effect Value ---
    base_value = spell.effect_value
    caster_int = getattr(caster, 'stats', {}).get('intelligence', 10)
    caster_power = getattr(caster, 'stats', {}).get('spell_power', 0)
    stat_bonus = max(0, (caster_int - 10) // 5) + caster_power
    modified_value = base_value + stat_bonus
    variation = random.uniform(-0.1, 0.1)
    final_value = max(1, int(modified_value * (1 + variation)))

    # --- Apply Effect and Store Intermediate Value ---
    effect_applied_value = 0 # Store the actual damage/heal amount
    if spell.effect_type == "damage":
        if hasattr(target, 'take_damage'):
            effect_applied_value = target.take_damage(final_value)
            value = effect_applied_value # Set return value
        else:
             # Handle fizzle case - create message here
             target_name = getattr(target, 'name', 'target')
             message = f"{spell.name} fizzles against {target_name}."
             return 0, message # Return early if fizzled

    elif spell.effect_type == "heal":
        if hasattr(target, 'heal'):
            effect_applied_value = target.heal(final_value)
            value = effect_applied_value # Set return value
        else:
            # Handle no effect case - create message here
            target_name = getattr(target, 'name', 'target')
            message = f"{spell.name} has no effect on {target_name}."
            return 0, message # Return early if no effect

    # --- TODO: Add Buff/Debuff application logic ---
    # Remember to set 'value' appropriately (e.g., duration, stat bonus amount)
    # And create the message here if applicable.
    # ...

    # --- Format the final message ---
    # Use format_target_name here, requires viewer (caster) and target
    formatted_target_name = format_target_name(caster, target)
    caster_name = getattr(caster, 'name', 'Someone')

    # Choose the correct template based on self-target and effect type
    if caster == target:
        if spell.effect_type == "heal":
            message_template = getattr(spell, 'self_heal_message', "You heal yourself for {value} health!") # Use specific template
        # Add self-damage, self-buff templates if needed
        # elif spell.effect_type == "damage":
        #    message_template = getattr(spell, 'self_hit_message', "You hit yourself with {spell_name} for {value} damage!")
        else:
            # Fallback for other self-targeted effects
            message_template = f"You use {spell.name} on yourself."
            # Format this fallback template - might not need value/names
            message = message_template # Already formatted enough
    else:
        # Target is someone else
        if spell.effect_type == "damage":
            message_template = spell.hit_message
        elif spell.effect_type == "heal":
            message_template = spell.heal_message
        # Add other effect types
        else:
            # Generic fallback for other effects on others
            message_template = f"{caster_name} uses {spell.name} on {formatted_target_name}."
            # Format this fallback template
            message = message_template # Already formatted enough

    # Format the chosen template if it's not one of the simple fallbacks
    if not message: # Only format if message wasn't set by a fallback case above
        try:
             # Ensure all placeholders are handled, provide defaults if necessary
             message = message_template.format(
                 caster_name=caster_name,
                 target_name=formatted_target_name,
                 spell_name=spell.name,
                 value=effect_applied_value # Use the actual applied value in the message
            )
        except KeyError as e:
             # Handle cases where a template is missing a required key
             print(f"Warning: Formatting error for spell '{spell.name}'. Missing key: {e}. Template: '{message_template}'")
             # Provide a very basic fallback message
             message = f"{caster_name} used {spell.name} on {formatted_target_name}."


    # Handle cases where the effect didn't apply (already handled by early returns for fizzle/no effect)
    if value == 0 and not message and spell.effect_type in ["damage", "heal"]:
         # If damage/heal was 0, but wasn't a fizzle/no effect case, generate a minimal message
         message = f"{caster_name}'s {spell.name} has minimal effect on {formatted_target_name}."


    # If message is still empty after all this, create a generic one
    if not message:
         message = f"{caster_name} used {spell.name} on {formatted_target_name}."


    return value, message # Return calculated value and formatted message
