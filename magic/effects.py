# magic/effects.py
import random
import time
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

from utils.text_formatter import get_level_diff_category, format_target_name
from magic.spell import Spell
from core.config import LEVEL_DIFF_COMBAT_MODIFIERS # Import modifiers

if TYPE_CHECKING:
    from player import Player
    from npcs.npc import NPC

CasterTargetType = Union['Player', 'NPC']
ViewerType = Union['Player'] # Viewer is assumed to be the player

def apply_spell_effect(caster: CasterTargetType, target: CasterTargetType, spell: Spell, viewer: Optional[ViewerType]) -> Tuple[int, str]:
    """
    Applies the spell's effect to the target and returns the value and message.
    Names are formatted relative to the viewer.
    """
    value = 0
    message = ""

    # --- Calculate Effect Value ---
    base_value = spell.effect_value
    caster_int = getattr(caster, 'stats', {}).get('intelligence', 10) if hasattr(caster, 'stats') else 10
    caster_power = getattr(caster, 'stats', {}).get('spell_power', 0) if hasattr(caster, 'stats') else 0
    stat_bonus = max(0, (caster_int - 10) // 5) + caster_power
    modified_value = base_value + stat_bonus
    variation = random.uniform(-0.1, 0.1)
    stat_based_final_value = max(1, int(modified_value * (1 + variation)))

    caster_level = getattr(caster, 'level', 1)
    target_level = getattr(target, 'level', 1)
    category = get_level_diff_category(caster_level, target_level)
    _, damage_heal_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))

    # Apply modifier differently for damage vs heal
    if spell.effect_type == "damage":
         level_modified_value = int(stat_based_final_value * damage_heal_mod)
    elif spell.effect_type == "heal":
         # Healing effectiveness might *increase* when healing lower levels? Or stay same?
         # Let's assume modifier applies similarly to healing for now.
         level_modified_value = int(stat_based_final_value * damage_heal_mod)
         # Alternative: Don't modify healing based on target level diff
         # level_modified_value = stat_based_final_value
    else:
         # Buff/Debuff durations or values could also be modified here
         level_modified_value = stat_based_final_value # No change for other types yet

    final_value = max(1, level_modified_value) # Ensure at least 1

    # --- Apply Effect and Store Intermediate Value ---
    effect_applied_value = 0
    target_name_raw = getattr(target, 'name', 'target')
    damage_type = "magical" # Default for spells unless specified otherwise

    if spell.effect_type == "damage":
        if hasattr(target, 'take_damage'):
            effect_applied_value = target.take_damage(final_value, damage_type=damage_type)
            if effect_applied_value == 0 and final_value > 0: # Damage was likely fully resisted/negated
                 message = f"{spell.name} seems to have no effect on {target_name_raw}."
                 value = 0
            else:
                 value = effect_applied_value # Set return value
        else:
             message = f"{spell.name} fizzles against {target_name_raw}."
             return 0, message # Return early if fizzled

    elif spell.effect_type == "heal":
        if hasattr(target, 'heal'):
            effect_applied_value = target.heal(final_value)
            value = effect_applied_value # Set return value
        else:
            message = f"{spell.name} has no effect on {target_name_raw}."
            return 0, message # Return early if no effect

    # --- TODO: Add Buff/Debuff ---
    # ...

    # --- Format the final message ---
    # Use format_target_name, passing the viewer if available
    formatted_caster_name = format_target_name(viewer, caster) if viewer else getattr(caster, 'name', 'Someone')
    formatted_target_name = format_target_name(viewer, target) if viewer else getattr(target, 'name', 'target')

    # Only generate message if not already set (e.g., by fizzle/no effect/resisted)
    if not message:
         # Select template based on caster == target, effect type etc.
         if caster == target:
              # ... (self-cast message logic) ...
              message_template = f"{formatted_caster_name} uses {spell.name} on themself." # Default self-cast
              if spell.effect_type == "heal": message_template = getattr(spell, 'self_heal_message', f"{formatted_caster_name} heals themself for {{value}} health!")

         else:
              # ... (other-target message logic) ...
              message_template = f"{formatted_caster_name} uses {spell.name} on {formatted_target_name}." # Default other-cast
              if spell.effect_type == "damage": message_template = spell.hit_message
              elif spell.effect_type == "heal": message_template = spell.heal_message

         try:
              message = message_template.format(
                  caster_name=formatted_caster_name,
                  target_name=formatted_target_name,
                  spell_name=spell.name,
                  value=effect_applied_value # Use actual applied value
              )
         except KeyError as e:
              print(f"Warning: Formatting error for spell '{spell.name}'. Missing key: {e}. Template: '{message_template}'")
              message = f"{formatted_caster_name} used {spell.name} on {formatted_target_name}."

    return value, message
