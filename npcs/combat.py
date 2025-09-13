# npcs/combat.py
# --- MODIFIED WITH SMARTER SPELL SELECTION AND FAILSAFES ---

from typing import TYPE_CHECKING, Any, Dict, Optional, Union
import random
import time
from magic.effects import apply_spell_effect
from magic.spell_registry import get_spell
from utils.text_formatter import format_target_name, get_level_diff_category
from utils.utils import calculate_xp_gain, format_loot_drop_message, format_name_for_display
from core.config import (
    FACTION_RELATIONSHIP_MATRIX,
    FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, HIT_CHANCE_AGILITY_FACTOR,
    LEVEL_DIFF_COMBAT_MODIFIERS, MAX_HIT_CHANCE, MIN_HIT_CHANCE,
    MINIMUM_DAMAGE_TAKEN, NPC_ATTACK_DAMAGE_VARIATION_RANGE, NPC_BASE_HIT_CHANCE,
    NPC_LOW_MANA_RETREAT_THRESHOLD
)

if TYPE_CHECKING:
    from .npc import NPC
    from player import Player


def get_relation_to(viewer: Union['NPC', 'Player'], target: Union['NPC', 'Player']) -> int:
    # ... (this function is unchanged) ...
    if not hasattr(viewer, 'faction') or not hasattr(target, 'faction'): return 0
    viewer_faction, target_faction = viewer.faction, target.faction
    relation_map = FACTION_RELATIONSHIP_MATRIX.get(viewer_faction)
    if not relation_map: return 0
    return relation_map.get(target_faction, 0)

def is_hostile_to(npc: 'NPC', other) -> bool:
    return get_relation_to(npc, other) < 0

def enter_combat(npc: 'NPC', target):
    # ... (this function is unchanged) ...
    if not npc.is_alive or not target or not getattr(target, 'is_alive', False): return
    npc.in_combat = True
    npc.combat_targets.add(target)
    if hasattr(target, 'enter_combat') and not (hasattr(target, 'combat_targets') and npc in target.combat_targets):
        target.enter_combat(npc)

def exit_combat(npc: 'NPC', target=None):
    # ... (this function is unchanged) ...
    targets_to_remove = [target] if target else list(npc.combat_targets)
    for t in targets_to_remove:
        if t in npc.combat_targets:
            npc.combat_targets.remove(t)
            if hasattr(t, "exit_combat"): t.exit_combat(npc)
    if not npc.combat_targets: npc.in_combat = False

def attack(npc: 'NPC', target) -> Dict[str, Any]:
    # ... (this function is unchanged) ...
    viewer = npc.world.player if npc.world and hasattr(npc.world, 'player') else None
    category = get_level_diff_category(npc.level, getattr(target, 'level', 1))
    hit_chance_mod, damage_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
    agi_mod = (npc.stats.get("agility", 8) - getattr(target, "stats", {}).get("agility", 10)) * HIT_CHANCE_AGILITY_FACTOR
    final_hit_chance = max(MIN_HIT_CHANCE, min((NPC_BASE_HIT_CHANCE + agi_mod) * hit_chance_mod, MAX_HIT_CHANCE))
    formatted_caster = format_name_for_display(viewer, npc, True)
    formatted_target = format_name_for_display(viewer, target, False)
    if random.random() > final_hit_chance:
        return {"message": f"{formatted_caster} attacks {formatted_target} but misses!", "target_defeated": False}
    damage_var = random.randint(*NPC_ATTACK_DAMAGE_VARIATION_RANGE)
    base_damage = max(1, npc.attack_power + damage_var)
    modified_damage = max(MINIMUM_DAMAGE_TAKEN, int(base_damage * damage_mod))
    actual_damage = target.take_damage(modified_damage, "physical")
    hit_message = f"{formatted_caster} attacks {formatted_target} for {int(actual_damage)} damage!"
    return {"message": hit_message, "target_defeated": not target.is_alive}


# --- MODIFIED: Added a failsafe check ---
def cast_spell(npc: 'NPC', spell, target, current_time: float) -> Dict[str, Any]:
    """Casts a spell, but now includes validation to prevent miscasting."""
    # Failsafe: Prevent friendly spells on enemies and vice-versa
    if spell.target_type == 'friendly' and is_hostile_to(npc, target):
        # This is the bug we are fixing! The AI chose a friendly spell for an enemy.
        # Instead of healing the enemy, we will fall back to a physical attack.
        return attack(npc, target)

    if spell.target_type == 'enemy' and not is_hostile_to(npc, target):
        # This prevents an AI from damaging an ally by mistake.
        return attack(npc, target)
        
    if npc.mana < spell.mana_cost: return {"message": f"{npc.name} lacks mana."}
    npc.mana -= spell.mana_cost
    npc.spell_cooldowns[spell.spell_id] = current_time + spell.cooldown
    viewer = npc.world.player if npc.world and hasattr(npc.world, 'player') else None
    _, effect_message = apply_spell_effect(npc, target, spell, viewer)
    
    full_message = f"{spell.format_cast_message(npc)}\n{effect_message}"
    
    return {"message": full_message, "target_defeated": not getattr(target, 'is_alive', True)}


# --- MODIFIED: This function now correctly filters spells ---
def try_attack(npc: 'NPC', world, current_time: float) -> Optional[str]:
    from . import behaviors as npc_behaviors 
    player = getattr(world, 'player', None)
    if not player: return None
    if current_time - npc.last_combat_action < npc.combat_cooldown: return None
    
    target = npc.combat_target
    if not (target and target.is_alive and target.current_room_id == npc.current_room_id):
        valid_targets = [t for t in npc.combat_targets if t and t.is_alive and t.current_room_id == npc.current_room_id]
        if not valid_targets: exit_combat(npc); return None
        target = random.choice(valid_targets); npc.combat_target = target

    chosen_spell = None
    if npc.max_mana > 0 and npc.usable_spells and random.random() < npc.spell_cast_chance:
        if npc.mana / npc.max_mana < NPC_LOW_MANA_RETREAT_THRESHOLD:
            return npc_behaviors.start_retreat(npc, world, current_time, player)
        
        available_spells = [s for s_id in npc.usable_spells if (s := get_spell(s_id)) 
                            and current_time >= npc.spell_cooldowns.get(s_id, 0) 
                            and npc.mana >= s.mana_cost]
        
        # --- KEY FIX: Filter for spells that are appropriate for an ENEMY target ---
        offensive_spells = [s for s in available_spells if s.target_type == 'enemy']

        if offensive_spells:
            chosen_spell = random.choice(offensive_spells)

    action_result = None
    if chosen_spell:
        # The target for an offensive spell is always the current combat target
        action_result = cast_spell(npc, chosen_spell, target, current_time)
        npc.last_combat_action = current_time
    elif current_time - npc.last_attack_time >= npc.attack_cooldown:
        # ATTACK HERE IF SPELL CASTING DOESN'T WORK OUT
        action_result = attack(npc, target)
        npc.last_attack_time = npc.last_combat_action = current_time
    
    if action_result:
        messages = [action_result.get("message")]
        if action_result.get("target_defeated", False):
            exit_combat(npc, target)
            messages.append(f"{format_name_for_display(player, npc, True)} has defeated {format_name_for_display(player, target, False)}!")
            
            if player and npc.properties.get("owner_id") == getattr(player, "obj_id", None):
                xp_gainer = player
            else:
                xp_gainer = npc

            xp = calculate_xp_gain(xp_gainer.level, target.level, target.max_health)
            if xp > 0:
                leveled, level_msg = xp_gainer.gain_experience(xp)
                messages.append(f"{FORMAT_SUCCESS}{xp_gainer.name} gained {xp} XP!{FORMAT_RESET}")
                if leveled: messages.append(level_msg)
            if hasattr(target, 'die'):
                # The 'die' method might return loot (for NPCs) or None (for Players)
                possible_loot = target.die(world)
                if possible_loot: messages.append(format_loot_drop_message(player, target, possible_loot))
        final_message = "\n".join(filter(None, messages))
        if player and player.is_alive and player.current_room_id == npc.current_room_id: return final_message
    return None