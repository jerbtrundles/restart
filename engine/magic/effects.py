# engine/magic/effects.py
import random
import time
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union
import uuid

from engine.items.container import Container
from engine.items.item import Item # Added Import
from engine.utils.text_formatter import get_level_diff_category, format_target_name
from engine.magic.spell import Spell
from engine.config import (
    DAMAGE_TYPE_FLAVOR_TEXT, EFFECT_DEFAULT_TICK_INTERVAL, FORMAT_HIGHLIGHT, FORMAT_RESET,
    LEVEL_DIFF_COMBAT_MODIFIERS, MINIMUM_SPELL_EFFECT_VALUE, SPELL_DAMAGE_VARIATION_FACTOR,
    SPELL_DEFAULT_DAMAGE_TYPE
)
from engine.utils.utils import format_name_for_display, get_article

if TYPE_CHECKING:
    from engine.player import Player
    from engine.npcs.npc import NPC

# Caster must be an entity
CasterType = Union['Player', 'NPC']
# Target can be an entity OR an item (for utility spells like Knock)
SpellTargetType = Union['Player', 'NPC', Item]
ViewerType = Union['Player'] 


def apply_spell_effect(caster: CasterType, target: SpellTargetType, spell: Spell, viewer: Optional[ViewerType]) -> Tuple[int, str]:
    from engine.npcs.npc_factory import NPCFactory
    from engine.player import Player
    value = 0
    message = ""
    flavor_message = ""

    # Pre-calculate names for message formatting
    formatted_caster_name = format_name_for_display(viewer, caster, start_of_sentence=True) if viewer else getattr(caster, 'name', 'Someone')
    # Target name might be reformatted later if needed, but we get a default here
    target_name_raw = getattr(target, 'name', 'target')

    # --- 1. Handle Item/Container Logic (Lock/Unlock) ---
    if spell.effect_type in ["unlock", "lock"]:
        if isinstance(target, Container):
            success, msg = target.magic_interact(spell.effect_type)
            return (1 if success else 0), msg
        else:
            return 0, f"The {spell.name} spell has no effect on {target_name_raw}."

    # --- 2. Standard Combat/Healing Logic ---
    # We must ensure target is an entity for combat logic
    if not hasattr(target, 'health') and spell.effect_type in ["damage", "heal", "apply_dot", "apply_effect"]:
         return 0, f"{spell.name} has no effect on {target_name_raw}."
    
    # ... (rest of the combat logic remains the same) ...
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

    if spell.effect_type == "damage":
         level_modified_value = int(stat_based_final_value * damage_heal_mod)
    elif spell.effect_type == "heal":
         level_modified_value = int(stat_based_final_value * damage_heal_mod)
    else:
         level_modified_value = stat_based_final_value

    final_value = max(MINIMUM_SPELL_EFFECT_VALUE, level_modified_value)

    if spell.effect_type == "damage" and spell.damage_type != "physical" and hasattr(target, 'get_resistance'):
        # target here is narrowed to entity by hasattr check above
        resistance_value = getattr(target, 'get_resistance')(spell.damage_type)
        flavor_key = None
        if resistance_value < 0: flavor_key = "weakness"
        elif resistance_value >= 50: flavor_key = "strong_resistance"
        elif resistance_value > 0: flavor_key = "resistance"

        if flavor_key:
            flavor_map = DAMAGE_TYPE_FLAVOR_TEXT.get(spell.damage_type, DAMAGE_TYPE_FLAVOR_TEXT["default"])
            message_template = flavor_map.get(flavor_key)
            if message_template:
                formatted_target_for_flavor = f"{FORMAT_HIGHLIGHT}{target_name_raw}{FORMAT_RESET}"
                flavor_message = message_template.format(target_name=formatted_target_for_flavor)

    # Apply Effect
    effect_applied_value = 0
    
    if spell.effect_type == "damage":
        if hasattr(target, 'take_damage'):
            effect_applied_value = getattr(target, 'take_damage')(final_value, damage_type=spell.damage_type)
            if effect_applied_value == 0 and final_value > 0:
                 message = f"{spell.name} seems to have no effect on {target_name_raw}."
                 value = 0
            else:
                 value = effect_applied_value
        else:
             return 0, f"{spell.name} fizzles against {target_name_raw}."

    elif spell.effect_type == "heal":
        if hasattr(target, 'heal'):
            effect_applied_value = getattr(target, 'heal')(final_value)
            value = effect_applied_value
        else:
            return 0, f"{spell.name} has no effect on {target_name_raw}."

    elif spell.effect_type == "summon":
        # ... (summon logic remains same) ...
        if not isinstance(caster, Player): return 0, "Only players can summon creatures."
        template_id = spell.summon_template_id
        duration = spell.summon_duration
        if not template_id or not getattr(caster, 'world', None): return 0, "Summoning failed."
        
        instance_id = f"summon_{caster.obj_id[:5]}_{template_id[:5]}_{uuid.uuid4().hex[:6]}"
        summon_level = 10 
        
        overrides = {
            "owner_id": caster.obj_id,
            "properties_override": { "owner_id": caster.obj_id, "summon_duration": duration, "creation_time": time.time(), "is_summoned": True },
            "level": summon_level,
            "current_region_id": caster.current_region_id, "current_room_id": caster.current_room_id,
            "faction": "player_minion",
        }
        
        if not caster.world: return 0, "Summoning failed."
        summoned_npc = NPCFactory.create_npc_from_template(template_id, caster.world, instance_id, **overrides)
        if summoned_npc:
            caster.world.add_npc(summoned_npc)
            if spell.spell_id not in caster.active_summons: caster.active_summons[spell.spell_id] = []
            caster.active_summons[spell.spell_id].append(summoned_npc.obj_id)
            summon_name_formatted = format_name_for_display(viewer, summoned_npc)
            return 1, f"{get_article(summon_name_formatted).capitalize()} {summon_name_formatted} rises to serve you!"
        return 0, "Summoning failed."

    elif spell.effect_type == "apply_dot":
        if hasattr(target, 'apply_effect'):
            dot_data = {
                "type": "dot", "name": getattr(spell, 'dot_name', "Affliction"),
                "base_duration": getattr(spell, 'dot_duration', 10.0),
                "damage_per_tick": getattr(spell, 'dot_damage_per_tick', 1),
                "tick_interval": getattr(spell, 'dot_tick_interval', EFFECT_DEFAULT_TICK_INTERVAL),
                "damage_type": getattr(spell, 'dot_damage_type', "unknown"),
                "source_id": getattr(caster, 'obj_id', None)
            }
            success, _ = getattr(target, 'apply_effect')(dot_data, time.time())
            if success:
                formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False) if viewer else target_name_raw
                try:
                    message = spell.hit_message.format(
                        caster_name=formatted_caster_name,
                        target_name=formatted_target_name,
                        spell_name=spell.name,
                        value=value
                    )
                except KeyError:
                    message = f"{formatted_target_name} is affected by {spell.name}."
                value = 1
            else:
                message = f"{spell.name} has no effect on {target_name_raw}."
                value = 0
        else:
            return 0, f"{spell.name} fizzles against {target_name_raw}."

    elif spell.effect_type == "apply_effect":
        if hasattr(target, 'apply_effect') and spell.effect_data:
            effect_to_apply = spell.effect_data.copy()
            effect_to_apply["base_duration"] = spell.dot_duration 
            effect_to_apply["source_id"] = getattr(caster, 'obj_id', None)
            
            success, _ = getattr(target, 'apply_effect')(effect_to_apply, time.time())
            
            if success:
                formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False) if viewer else target_name_raw
                try:
                    message = spell.hit_message.format(
                        caster_name=formatted_caster_name,
                        target_name=formatted_target_name,
                        spell_name=spell.name,
                        value=value
                    )
                except KeyError:
                    message = f"{formatted_target_name} is affected by {spell.name}."
                value = 1
            else:
                message = f"{spell.name} has no effect on {target_name_raw}."
                value = 0
        else:
            return 0, f"{spell.name} fizzles against {target_name_raw}."

    # Format Final Message (Fallback)
    formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False) if viewer else target_name_raw

    if not message:
         if caster == target:
              message_template = getattr(spell, 'self_heal_message', f"{formatted_caster_name} heals themself for {{value}} health!") if spell.effect_type == "heal" else f"{formatted_caster_name} uses {spell.name} on themself."
         else:
              damage_type_str = f" {spell.damage_type}" if spell.damage_type != SPELL_DEFAULT_DAMAGE_TYPE else ""
              if spell.effect_type == "damage": message_template = spell.hit_message.replace(" points!", f"{damage_type_str} points!")
              elif spell.effect_type == "heal": message_template = spell.heal_message
              else: message_template = f"{formatted_caster_name} uses {spell.name} on {formatted_target_name}."
         try:
              message = message_template.format(caster_name=formatted_caster_name, target_name=formatted_target_name, spell_name=spell.name, value=effect_applied_value)
         except (KeyError, AttributeError): message = f"{formatted_caster_name} used {spell.name} on {formatted_target_name}."

    if flavor_message: message = f"{FORMAT_HIGHLIGHT}{flavor_message}{FORMAT_RESET}\n{message}"

    return value, message