# engine/npcs/ai/combat_logic.py
import random
from typing import TYPE_CHECKING, Optional
from engine.utils.utils import format_name_for_display
from .movement import execute_move
from engine.npcs import combat as npc_combat

if TYPE_CHECKING:
    from engine.npcs.npc import NPC
    from engine.player import Player
    from engine.world.world import World

def try_flee(npc: 'NPC', world: 'World', player: 'Player') -> Optional[str]:
    """Attempts to move the NPC to an adjacent room during combat."""
    if not npc.current_region_id or not npc.current_room_id: return None
    region = world.get_region(npc.current_region_id)
    if not region: return None
    room_before_flee = region.get_room(npc.current_room_id)
    
    if not room_before_flee or not room_before_flee.exits:
        return None # Cannot flee if there are no exits.

    # Determine if the player can see the NPC flee from its starting room.
    player_can_see_flee = (player and player.is_alive and player.current_room_id == room_before_flee.obj_id)

    # Logic to find a valid direction to flee to
    valid_exits = {}
    if npc.faction == 'hostile':
        for direction, dest_id in room_before_flee.exits.items():
            r_id, room_id = (dest_id.split(':') if ':' in dest_id else (npc.current_region_id, dest_id))
            if not world.is_location_safe(r_id, room_id):
                valid_exits[direction] = dest_id
        if not valid_exits: valid_exits = room_before_flee.exits # If all exits are safe, just pick one
    else:
        valid_exits = room_before_flee.exits

    direction = random.choice(list(valid_exits.keys()))
    
    # Exit combat *before* moving.
    npc_combat.exit_combat(npc)
    
    execute_move(npc, world, player, direction)
    
    # Generate and return the specific "flee" message ONLY if the player was in the starting room.
    if player_can_see_flee:
        return f"{format_name_for_display(player, npc, True)} flees to the {direction}!"

    return None

def start_retreat(npc: 'NPC', world: 'World', current_time: float, player: 'Player') -> Optional[str]:
    """Calculates a path to a safe zone and sets the AI state to retreating."""
    if not npc.current_region_id or not npc.current_room_id: return None

    if not npc.retreat_destination and npc.current_region_id and npc.current_room_id:
        npc.retreat_destination = world.find_nearest_safe_room(npc.current_region_id, npc.current_room_id)
        
    if npc.retreat_destination:
        # Find the full path to the destination
        path = world.find_path(
            npc.current_region_id, 
            npc.current_room_id, 
            npc.retreat_destination[0], 
            npc.retreat_destination[1]
        )
        
        # If a path exists, we can announce the first step
        if path:
            first_direction = path[0]
            # Store the complete path for the retreat behavior to use
            npc.current_path = path 
            
            # Set up the NPC state for retreating
            npc.original_behavior = npc.behavior_type
            npc.behavior_type = "retreating_for_mana"
            npc_combat.exit_combat(npc)
            
            # Generate the improved message if the player can see the NPC
            if player and player.current_room_id == npc.current_room_id:
                return f"{format_name_for_display(player, npc, True)} looks exhausted and retreats from battle, heading {first_direction}!"
        else:
            npc.retreat_destination = None # Clear destination
            return None 

    return None

def perform_retreat(npc: 'NPC', world: 'World', current_time: float, player: 'Player') -> Optional[str]:
    """Logic for handling the 'retreating_for_mana' state."""
    # 1. Check if retreat condition is over
    if npc.mana >= npc.max_mana:
        npc.behavior_type = npc.original_behavior or "wanderer"
        npc.retreat_destination = None
        npc.current_path = []
        if player and player.current_room_id == npc.current_room_id:
            return f"{format_name_for_display(player, npc, True)} looks recovered."
        return None

    # 2. If at destination, do nothing (path should be empty)
    if npc.retreat_destination and (npc.current_region_id, npc.current_room_id) == npc.retreat_destination:
        npc.current_path = [] 
        return None 

    # 3. If we have a path, move along it.
    if npc.current_path:
        next_direction = npc.current_path.pop(0)
        return execute_move(npc, world, player, next_direction)

    # 4. Fallback if something went wrong
    npc.behavior_type = npc.original_behavior or "wanderer"
    npc.retreat_destination = None
    if player and player.current_room_id == npc.current_room_id:
        return f"{format_name_for_display(player, npc, True)} seems to have lost their way and stops retreating."
    return None

def scan_for_targets(npc: 'NPC', world: 'World', player: 'Player') -> Optional[str]:
    """
    Checks for enemies in the current room and initiates combat if found.
    Returns an interaction message string if combat starts and is visible.
    """
    if not npc.current_region_id or not npc.current_room_id: return None

    # 1. Logic for HOSTILE NPCs
    if npc.faction == "hostile" and npc.aggression > 0:
        potential_targets = []
        
        ignore_player = world.game and world.game.debug_ignore_player
        if player and player.is_alive and player.current_room_id == npc.current_room_id and not ignore_player:
            potential_targets.append(player)

        room_npcs = world.get_npcs_in_room(npc.current_region_id, npc.current_room_id)
        for other_npc in room_npcs:
            if other_npc != npc and other_npc.is_alive and npc_combat.is_hostile_to(npc, other_npc):
                potential_targets.append(other_npc)

        if potential_targets and random.random() < npc.aggression:
            target_to_attack = random.choice(potential_targets)
            npc_combat.enter_combat(npc, target_to_attack)
            
            # Try attack immediately
            return _execute_immediate_attack_msg(npc, world, target_to_attack, player)

    # 2. Logic for FRIENDLY/NEUTRAL NPCs defending against hostiles
    elif npc.faction != "hostile":
        room_npcs = world.get_npcs_in_room(npc.current_region_id, npc.current_room_id)
        hostiles_in_room = [other_npc for other_npc in room_npcs if other_npc.is_alive and other_npc.faction == "hostile"]
        
        if hostiles_in_room:
            target_hostile = random.choice(hostiles_in_room)
            npc_combat.enter_combat(npc, target_hostile)
            
            return _execute_immediate_attack_msg(npc, world, target_hostile, player)
            
    return None

def _execute_immediate_attack_msg(npc: 'NPC', world: 'World', target, player: 'Player') -> Optional[str]:
    """Helper to try an attack immediately and format the engage message."""
    # Current time is needed for CD check inside try_attack, pass 0 to force check if needed? 
    # No, we need actual time. We'll access time via the npc's last action for approximation or pass it down.
    # ideally scan_for_targets should accept current_time. 
    # For now, let's assume try_attack handles the check.
    
    import time
    current_time = time.time() # Best effort since we don't have it passed in this helper
    
    immediate_msg = npc_combat.try_attack(npc, world, current_time)
    
    # Construct "Moves to attack" message if player is watching
    engage_message = ""
    if player and player.is_alive and player.current_room_id == npc.current_room_id:
        att_name = format_name_for_display(player, npc, start_of_sentence=True)
        def_name = format_name_for_display(player, target, start_of_sentence=False)
        engage_message = f"{att_name} moves to attack {def_name}!"

    if immediate_msg:
        return (engage_message + "\n" + immediate_msg).strip()
    return engage_message if engage_message else None