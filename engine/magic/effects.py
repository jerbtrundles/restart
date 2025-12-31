import random
import time
from typing import TYPE_CHECKING, Any, Optional, Tuple, Union
import uuid

from engine.items.container import Container
from engine.items.item import Item
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
# Target can be an entity OR an item (for utility spells like Knock/Curse removal)
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
    target_name_raw = getattr(target, 'name', 'target')

    # --- 1. Handle Item/Container Logic (Lock/Unlock/Curse) ---
    
    if spell.effect_type in ["unlock", "lock"]:
        if isinstance(target, Container):
            success, msg = target.magic_interact(spell.effect_type)
            return (1 if success else 0), msg
        else:
            return 0, f"The {spell.name} spell has no effect on {target_name_raw}."

    if spell.effect_type == "remove_curse":
        # Can target a specific Item directly
        if isinstance(target, Item):
            if target.get_property("cursed"):
                target.update_property("cursed", False)
                return 1, f"The dark aura surrounding the {target.name} dissipates."
            else:
                return 0, f"The {target.name} is not cursed."
        
        # Or target an Entity to cleanse all their equipped gear
        elif hasattr(target, 'equipment'):
            cleansed_count = 0
            # FIX: Use getattr to satisfy type checker, then .values() to get Items
            equip_dict = getattr(target, 'equipment', {})
            for item in equip_dict.values():
                if item and item.get_property("cursed"):
                    item.update_property("cursed", False)
                    cleansed_count += 1
            
            if cleansed_count > 0:
                return 1, f"A holy light washes over {target_name_raw}, cleansing {cleansed_count} cursed items."
            else:
                return 0, f"{target_name_raw} is not wearing any cursed items."

    # --- 2. Standard Combat/Healing Logic ---
    
    # Ensure target is an entity for combat logic if not handled above
    if not hasattr(target, 'health') and spell.effect_type in ["damage", "heal", "apply_dot", "apply_effect", "life_tap", "cleanse"]:
         return 0, f"{spell.name} has no effect on {target_name_raw}."

    # --- Calculation Phase ---
    base_value = spell.effect_value
    
    # 1. Stat Scaling (Intelligence/Spell Power)
    caster_int = getattr(caster, 'stats', {}).get('intelligence', 10) if hasattr(caster, 'stats') else 10
    caster_power = getattr(caster, 'stats', {}).get('spell_power', 0) if hasattr(caster, 'stats') else 0
    
    # Formula: Base + (Int-10)//5 + SpellPower
    stat_bonus = max(0, (caster_int - 10) // 5) + caster_power
    modified_value = base_value + stat_bonus
    
    # 2. Random Variance
    variation = random.uniform(-SPELL_DAMAGE_VARIATION_FACTOR, SPELL_DAMAGE_VARIATION_FACTOR)
    stat_based_final_value = max(MINIMUM_SPELL_EFFECT_VALUE, int(modified_value * (1 + variation)))

    # 3. Level Difference Scaling
    caster_level = getattr(caster, 'level', 1)
    target_level = getattr(target, 'level', 1)
    category = get_level_diff_category(caster_level, target_level)
    _, damage_heal_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))

    if spell.effect_type in ["damage", "life_tap"]:
         level_modified_value = int(stat_based_final_value * damage_heal_mod)
    elif spell.effect_type == "heal":
         level_modified_value = int(stat_based_final_value * damage_heal_mod)
    else:
         # Status effects usually rely on duration/ticks, value implies magnitude which doesn't scale with level diff usually
         level_modified_value = stat_based_final_value

    final_value = max(MINIMUM_SPELL_EFFECT_VALUE, level_modified_value)

    # --- Flavor Text Generation (Weakness/Resistance) ---
    if spell.effect_type in ["damage", "life_tap"] and spell.damage_type != "physical" and hasattr(target, 'get_resistance'):
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

    # --- Effect Application Phase ---
    
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

    elif spell.effect_type == "life_tap":
        if hasattr(target, 'take_damage'):
            # Deal Damage
            damage_dealt = getattr(target, 'take_damage')(final_value, damage_type=spell.damage_type)
            
            if damage_dealt > 0:
                # Heal Caster (50% Leech)
                heal_amount = int(damage_dealt * 0.5)
                if hasattr(caster, 'heal'):
                    caster.heal(heal_amount)
                
                # Custom message overriding default format
                message = f"{spell.name} drains {damage_dealt} life from {target_name_raw} and heals {formatted_caster_name} for {heal_amount}!"
                value = damage_dealt
            else:
                message = f"{spell.name} fails to drain {target_name_raw}."
                value = 0
        else:
            return 0, f"{spell.name} fizzles."

    elif spell.effect_type == "heal":
        if hasattr(target, 'heal'):
            effect_applied_value = getattr(target, 'heal')(final_value)
            value = effect_applied_value
        else:
            return 0, f"{spell.name} has no effect on {target_name_raw}."

    elif spell.effect_type == "cleanse":
        if hasattr(target, 'remove_effects_by_tag'):
            # Default to cleansing poison, disease, and curses if not specified in spell data
            tags_to_cleanse = spell.effect_data.get("tags", ["poison", "disease", "curse"]) if spell.effect_data else ["poison", "disease", "curse"]
            
            removed_count = 0
            for tag in tags_to_cleanse:
                removed_list = target.remove_effects_by_tag(tag)
                removed_count += len(removed_list)
            
            if removed_count > 0:
                value = 1
                message = f"{target_name_raw} is cleansed of {removed_count} afflictions."
            else:
                value = 0
                message = f"{spell.name} washes over {target_name_raw}, but finds nothing to cleanse."
        else:
            return 0, f"{spell.name} has no effect."

    elif spell.effect_type == "summon":
        if not isinstance(caster, Player): return 0, "Only players can summon creatures."
        template_id = spell.summon_template_id
        duration = spell.summon_duration
        if not template_id or not getattr(caster, 'world', None): return 0, "Summoning failed."
        
        instance_id = f"summon_{caster.obj_id[:5]}_{template_id[:5]}_{uuid.uuid4().hex[:6]}"
        # Summon level could scale, currently fixed or based on template
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
                "type": "dot", 
                "name": getattr(spell, 'dot_name', "Affliction"),
                "base_duration": getattr(spell, 'dot_duration', 10.0),
                "damage_per_tick": getattr(spell, 'dot_damage_per_tick', 1),
                "tick_interval": getattr(spell, 'dot_tick_interval', EFFECT_DEFAULT_TICK_INTERVAL),
                "damage_type": getattr(spell, 'dot_damage_type', "unknown"),
                "source_id": getattr(caster, 'obj_id', None)
            }
            # Copy tags if present in spell data
            if spell.effect_data and "tags" in spell.effect_data:
                dot_data["tags"] = spell.effect_data["tags"]

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
            # If duration is specified at top level of spell, override the data inside effect_data
            if spell.dot_duration > 0:
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

    # --- Message Construction (Fallback for standard effects) ---
    
    # If the specific handler (like life_tap) already set a message, skip default generation
    if not message:
         formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False) if viewer else target_name_raw
         
         if caster == target:
              if spell.effect_type == "heal":
                   message_template = getattr(spell, 'self_heal_message', f"{formatted_caster_name} heals themself for {{value}} health!")
              else:
                   message_template = f"{formatted_caster_name} uses {spell.name} on themself."
         else:
              damage_type_str = f" {spell.damage_type}" if spell.damage_type != SPELL_DEFAULT_DAMAGE_TYPE else ""
              
              if spell.effect_type == "damage": 
                   message_template = spell.hit_message.replace(" points!", f"{damage_type_str} points!")
              elif spell.effect_type == "heal": 
                   message_template = spell.heal_message
              else: 
                   message_template = f"{formatted_caster_name} uses {spell.name} on {formatted_target_name}."
         
         try:
              message = message_template.format(
                  caster_name=formatted_caster_name, 
                  target_name=formatted_target_name, 
                  spell_name=spell.name, 
                  value=effect_applied_value if 'effect_applied_value' in locals() else value
              )
         except (KeyError, AttributeError): 
              message = f"{formatted_caster_name} used {spell.name} on {formatted_target_name}."

    # Prepend flavor text if it was generated
    if flavor_message: 
        message = f"{FORMAT_HIGHLIGHT}{flavor_message}{FORMAT_RESET}\n{message}"

    return value, message