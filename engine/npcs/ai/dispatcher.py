# engine/npcs/ai/dispatcher.py
from typing import TYPE_CHECKING, Optional
from engine.npcs import combat as npc_combat
from .movement import perform_wander, perform_patrol, perform_follow, perform_schedule
from .combat_logic import try_flee, scan_for_targets, perform_retreat
from .specialized import perform_healer_logic, perform_minion_logic

if TYPE_CHECKING:
    from engine.npcs.npc import NPC
    from engine.player import Player
    from engine.world.world import World

def handle_ai(npc: 'NPC', world: 'World', current_time: float, player: 'Player') -> Optional[str]:
    """Main AI handler that delegates to specific behaviors."""
    
    if npc.has_effect("Stun"):
        return None 

    if npc.is_trading: return None 

    # --- 1. Minion Expiry (High Priority, bypasses movement cooldown) ---
    if npc.behavior_type == "minion":
        duration = npc.properties.get("summon_duration", 0)
        created = npc.properties.get("creation_time", 0)
        if duration > 0 and current_time > (created + duration):
            return npc.despawn(world, silent=False)

    # --- 2. High-priority specialized actions ---
    if npc.behavior_type == "healer":
        heal_msg = perform_healer_logic(npc, world, current_time, player)
        if heal_msg: return heal_msg
        
    if npc.behavior_type == "retreating_for_mana":
        return perform_retreat(npc, world, current_time, player)

    # --- 3. Combat Action (if already in combat) ---
    if npc.in_combat:
        if npc.is_alive and npc.health < npc.max_health * npc.flee_threshold:
            flee_msg = try_flee(npc, world, player)
            if flee_msg: return flee_msg
        return npc_combat.try_attack(npc, world, current_time)

    # --- 4. Combat Initiation (if NOT in combat) ---
    initiate_msg = scan_for_targets(npc, world, player)
    if initiate_msg:
        return initiate_msg

    # --- 5. Idle Movement (Cooldown check) ---
    if current_time - npc.last_moved < npc.move_cooldown: return None
    
    behavior = npc.behavior_type
    if behavior == "healer": behavior = "wanderer" 
    
    move_message = None
    if behavior == "wanderer" or behavior == "aggressive": 
        move_message = perform_wander(npc, world, player)
    elif behavior == "patrol": 
        move_message = perform_patrol(npc, world, player)
    elif behavior == "follower": 
        move_message = perform_follow(npc, world, player)
    elif behavior == "scheduled": 
        move_message = perform_schedule(npc, world, player)
    elif behavior == "minion": 
        move_message = perform_minion_logic(npc, world, current_time, player)
    
    if move_message: npc.last_moved = current_time
    return move_message