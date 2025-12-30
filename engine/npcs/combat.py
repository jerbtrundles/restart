# engine/npcs/combat.py

from typing import TYPE_CHECKING, Any, Dict, Optional, Union
import random
import time
from engine.config import (
    HIT_CHANCE_AGILITY_FACTOR, LEVEL_DIFF_COMBAT_MODIFIERS, MAX_HIT_CHANCE, MIN_HIT_CHANCE, MINIMUM_DAMAGE_TAKEN, FORMAT_RESET,
    FORMAT_SUCCESS, NPC_ATTACK_DAMAGE_VARIATION_RANGE, NPC_BASE_HIT_CHANCE, NPC_LOW_MANA_RETREAT_THRESHOLD, FACTION_RELATIONSHIP_MATRIX
)
from engine.core.combat_system import CombatSystem
from engine.magic.effects import apply_spell_effect
from engine.magic.spell_registry import get_spell
from engine.utils.text_formatter import format_target_name, get_level_diff_category
from engine.utils.utils import calculate_xp_gain, format_loot_drop_message, format_name_for_display

if TYPE_CHECKING:
    from .npc import NPC
    from engine.player import Player


def get_relation_to(viewer: Union['NPC', 'Player'], target: Union['NPC', 'Player']) -> int:
    if not hasattr(viewer, 'faction') or not hasattr(target, 'faction'): return 0
    viewer_faction, target_faction = viewer.faction, target.faction
    relation_map = FACTION_RELATIONSHIP_MATRIX.get(viewer_faction)
    if not relation_map: return 0
    return relation_map.get(target_faction, 0)

def is_hostile_to(npc: 'NPC', other) -> bool:
    return get_relation_to(npc, other) < 0

def enter_combat(npc: 'NPC', target):
    if not npc.is_alive or not target or not getattr(target, 'is_alive', False): return
    npc.in_combat = True
    npc.combat_targets.add(target)
    if hasattr(target, 'enter_combat') and not (hasattr(target, 'combat_targets') and npc in target.combat_targets):
        target.enter_combat(npc)

def exit_combat(npc: 'NPC', target: Optional[Any] = None):
    """
    Safely handles exiting combat for an NPC.
    """
    if target:
        if target in npc.combat_targets:
            npc.combat_targets.remove(target)
            if hasattr(target, "exit_combat"):
                target.exit_combat(npc)
    else:
        # Clear everything
        targets_to_remove = list(npc.combat_targets)
        for t in targets_to_remove:
            npc.combat_targets.discard(t)
            if hasattr(t, "exit_combat"):
                t.exit_combat(npc)
                
    if not npc.combat_targets:
        npc.in_combat = False
        npc.combat_target = None

def attack(npc: 'NPC', target) -> Dict[str, Any]:
    """
    Optimized to use shared CombatSystem logic.
    """
    viewer = npc.world.player if npc.world and hasattr(npc.world, 'player') else None
    
    # Use Core System for calculation
    combat_result = CombatSystem.execute_attack(
        attacker=npc,
        defender=target,
        attack_power=npc.attack_power,
        weapon_name="attack",
        viewer=viewer
    )

    return {"message": combat_result["message"], "target_defeated": combat_result["target_defeated"]}

def cast_spell(npc: 'NPC', spell, target, current_time: float) -> Dict[str, Any]:
    """Casts a spell, but now includes validation to prevent miscasting."""
    
    # --- Logic Update: Check dynamic combat state alongside static factions ---
    is_actively_hostile = target in npc.combat_targets or is_hostile_to(npc, target)

    # Failsafe: Prevent friendly spells on enemies and vice-versa
    if spell.target_type == 'friendly' and is_actively_hostile:
        return attack(npc, target)

    if spell.target_type == 'enemy' and not is_actively_hostile:
        return attack(npc, target)
        
    if npc.mana < spell.mana_cost: return {"message": f"{npc.name} lacks mana."}
    npc.mana -= spell.mana_cost
    npc.spell_cooldowns[spell.spell_id] = current_time + spell.cooldown
    viewer = npc.world.player if npc.world and hasattr(npc.world, 'player') else None
    _, effect_message = apply_spell_effect(npc, target, spell, viewer)
    
    full_message = f"{spell.format_cast_message(npc)}\n{effect_message}"
    
    return {"message": full_message, "target_defeated": not getattr(target, 'is_alive', True)}

def try_attack(npc: 'NPC', world, current_time: float) -> Optional[str]:
    # --- UPDATED IMPORT ---
    from . import ai as npc_ai 
    
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
            # Use the exposed function from the new package
            retreat_message = npc_ai.start_retreat(npc, world, current_time, player)
            if retreat_message:
                return retreat_message 
        
        available_spells = [s for s_id in npc.usable_spells if (s := get_spell(s_id)) 
                            and current_time >= npc.spell_cooldowns.get(s_id, 0) 
                            and npc.mana >= s.mana_cost]
        
        offensive_spells = [s for s in available_spells if s.target_type == 'enemy']

        if offensive_spells:
            chosen_spell = random.choice(offensive_spells)

    action_result = None
    if chosen_spell:
        action_result = cast_spell(npc, chosen_spell, target, current_time)
        npc.last_combat_action = current_time
    elif current_time - npc.last_attack_time >= npc.attack_cooldown:
        action_result = attack(npc, target)
        npc.last_attack_time = npc.last_combat_action = current_time
    
    if action_result:
        messages = [action_result.get("message")]
        if action_result.get("target_defeated", False):
            exit_combat(npc, target)
            
            if player and npc.properties.get("owner_id") == getattr(player, "obj_id", None):
                xp_gainer = player
            else:
                xp_gainer = npc

            xp = calculate_xp_gain(xp_gainer.level, target.level, target.max_health)
            if xp > 0:
                leveled, level_msg = xp_gainer.gain_experience(xp)
                if leveled: messages.append(level_msg)
            if hasattr(target, 'die'):
                possible_loot = target.die(world)
                if possible_loot: messages.append(format_loot_drop_message(player, target, possible_loot))
        final_message = "\n".join(filter(None, messages))
        if player and player.is_alive and player.current_room_id == npc.current_room_id: return final_message
    return None