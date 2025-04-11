# magic/effects.py
import random
import time
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union
import uuid

from npcs.npc_factory import NPCFactory
from utils.text_formatter import get_level_diff_category, format_target_name
from magic.spell import Spell
from core.config import EFFECT_DEFAULT_TICK_INTERVAL, LEVEL_DIFF_COMBAT_MODIFIERS, MINIMUM_SPELL_EFFECT_VALUE, SPELL_DAMAGE_VARIATION_FACTOR, SPELL_DEFAULT_DAMAGE_TYPE
from utils.utils import format_name_for_display, get_article # Import modifiers

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
    from player import Player
    value = 0
    message = ""

    # --- Calculate Effect Value ---
    base_value = spell.effect_value
    caster_int = getattr(caster, 'stats', {}).get('intelligence', 10) if hasattr(caster, 'stats') else 10
    caster_power = getattr(caster, 'stats', {}).get('spell_power', 0) if hasattr(caster, 'stats') else 0
    stat_bonus = max(0, (caster_int - 10) // 5) + caster_power
    modified_value = base_value + stat_bonus
    variation = random.uniform(-SPELL_DAMAGE_VARIATION_FACTOR, SPELL_DAMAGE_VARIATION_FACTOR)
    stat_based_final_value = max(MINIMUM_SPELL_EFFECT_VALUE, int(modified_value * (1 + variation)))

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

    final_value = max(MINIMUM_SPELL_EFFECT_VALUE, level_modified_value)

    # --- Apply Effect and Store Intermediate Value ---
    effect_applied_value = 0
    target_name_raw = getattr(target, 'name', 'target')
    message = "" # Initialize message

    if spell.effect_type == "damage":
        if hasattr(target, 'take_damage'):
            effect_applied_value = target.take_damage(final_value, damage_type=spell.damage_type)
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

    # --- ADD SUMMON EFFECT TYPE ---
    elif spell.effect_type == "summon":
        # Only players can summon for now
        if not isinstance(caster, Player): # Use isinstance to check type
            return 0, "Only players can summon creatures."

        template_id = spell.summon_template_id
        duration = spell.summon_duration
        max_allowed_by_spell = spell.max_summons
        max_total_allowed = getattr(caster, 'max_total_summons', 1)
        world = getattr(caster, 'world', None) # Get world from caster

        if not template_id or not world:
            return 0, "Summoning failed (invalid spell data or world context)."

        # Check Limits
        current_summons_for_spell = caster.active_summons.get(spell.spell_id, [])
        total_active_summons = sum(len(ids) for ids in caster.active_summons.values())

        if len(current_summons_for_spell) >= max_allowed_by_spell:
            return 0, f"You cannot control more {spell.name}s."
        if total_active_summons >= max_total_allowed:
            return 0, "You cannot control any more summons."

        # Prepare Overrides
        instance_id = f"summon_{caster.obj_id[:5]}_{template_id[:5]}_{uuid.uuid4().hex[:6]}"
        current_time_abs = time.time() # Use absolute time for creation timestamp

        # --- Example Scaling ---
        summon_level = 10 # max(1, caster.level // 3 + 1) # Minion level scales (adjust formula)

        overrides = {
            "owner_id": caster.obj_id,
            "properties_override": { # Put dynamic properties here
                "owner_id": caster.obj_id,
                "summon_duration": duration,
                "creation_time": current_time_abs,
                "is_summoned": True
            },
            "level": summon_level, # Override level based on caster
            "current_region_id": caster.current_region_id,
            "current_room_id": caster.current_room_id,
            "home_region_id": caster.current_region_id,
            "home_room_id": caster.current_room_id,
            "faction": "player_minion", # Ensure correct faction
        }

        # Create NPC Instance using the Factory
        summoned_npc = NPCFactory.create_npc_from_template(template_id, world, instance_id, **overrides)

        if summoned_npc:
            world.add_npc(summoned_npc) # Add to world

            # Update Player's summon list
            if spell.spell_id not in caster.active_summons:
                caster.active_summons[spell.spell_id] = []
            caster.active_summons[spell.spell_id].append(summoned_npc.obj_id)

            # Format name using viewer context
            summon_name_formatted = format_name_for_display(viewer, summoned_npc) # Use helper
            value = 1 # Indicate success count
            # Combine cast message and success info
            message = f"{get_article(summon_name_formatted).capitalize()} {summon_name_formatted} rises to serve you!"
            return value, message # Return success count and message
        else:
            return 0, "Summoning failed (creature could not be formed)."
    # --- END SUMMON ---

    # --- NEW: Handle apply_dot ---
    elif spell.effect_type == "apply_dot":
        if hasattr(target, 'apply_effect'):
            dot_data = {
                "type": "dot",
                "name": getattr(spell, 'dot_name', "Affliction"),
                "base_duration": getattr(spell, 'dot_duration', 10.0),
                "damage_per_tick": getattr(spell, 'dot_damage_per_tick', 1),
                "tick_interval": getattr(spell, 'dot_tick_interval', EFFECT_DEFAULT_TICK_INTERVAL),
                "damage_type": getattr(spell, 'dot_damage_type', "unknown"),
                "source_id": getattr(caster, 'obj_id', None) # Optional: track caster
            }
            # Call target's apply_effect method
            success, _ = target.apply_effect(dot_data, time.time())
            if success:
                # Use spell's hit_message for successful application
                # Format target name relative to viewer
                formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False)
                message = spell.hit_message.format(target_name=formatted_target_name)
                # 'value' for DoT application could be 1 for success, 0 for fail/resist?
                value = 1
            else:
                message = f"{spell.name} has no effect on {target_name_raw}."
                value = 0
        else:
            message = f"{spell.name} fizzles against {target_name_raw}."
            return 0, message

    # --- TODO: Add Buff/Debuff ---
    # ...

    # --- Format the final message ---
    # Use format_target_name, passing the viewer if available
    formatted_caster_name = format_name_for_display(viewer, caster, start_of_sentence=True) if viewer else getattr(caster, 'name', 'Someone')
    formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False) if viewer else target_name_raw

    # Only generate message if not already set (e.g., by fizzle/no effect/resisted)
    if not message:
         # Select template based on caster == target, effect type etc.
         if caster == target:
              # ... (self-cast message logic) ...
              message_template = f"{formatted_caster_name} uses {spell.name} on themself." # Default self-cast
              if spell.effect_type == "heal":
                   message_template = getattr(spell, 'self_heal_message', f"{formatted_caster_name} heals themself for {{value}} health!")

         else:
              # ... (other-target message logic) ...
              message_template = f"{formatted_caster_name} uses {spell.name} on {formatted_target_name}." # Default other-cast
              damage_type_str = f" {spell.damage_type}" if spell.damage_type != SPELL_DEFAULT_DAMAGE_TYPE else ""
              if spell.effect_type == "damage":
                   message_template = spell.hit_message.replace(" points!", f"{damage_type_str} points!") # Add type to default
              elif spell.effect_type == "heal":
                   message_template = spell.heal_message
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
