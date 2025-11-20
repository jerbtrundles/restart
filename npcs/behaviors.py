# npcs/behaviors.py

from typing import TYPE_CHECKING, Optional
import random
import time
from config import NPC_HEALER_HEAL_THRESHOLD
from magic.spell_registry import get_spell
from utils.utils import format_npc_arrival_message, format_npc_departure_message, format_name_for_display

if TYPE_CHECKING:
    from .npc import NPC
    from player import Player
    from . import combat as npc_combat_typing # For type hints only


def handle_ai(npc: 'NPC', world, current_time: float, player: 'Player') -> Optional[str]:
    """Main AI handler that delegates to specific behaviors."""
    if npc.has_effect("Stun"):
        return None # The NPC cannot perform any action

    # Local import of combat module to be used by AI functions
    from . import combat as npc_combat

    if npc.is_trading: return None # Don't act while trading

    # --- 1. High-priority specialized actions ---
    if npc.behavior_type == "healer":
        heal_msg = _healer_behavior(npc, world, current_time, player)
        if heal_msg: return heal_msg
    if npc.behavior_type == "retreating_for_mana":
        return _retreat_behavior(npc, world, current_time, player)

    # --- 2. Combat Action (if already in combat) ---
    if npc.in_combat:
        if npc.is_alive and npc.health < npc.max_health * npc.flee_threshold:
            flee_msg = _try_flee(npc, world, player)
            if flee_msg: return flee_msg
        
        # If not fleeing, try to attack
        return npc_combat.try_attack(npc, world, current_time)

    # --- 3. Combat Initiation (if NOT in combat) ---
    
    # Logic for HOSTILE NPCs to find targets
    if npc.faction == "hostile" and npc.aggression > 0:
        potential_targets = []
        
        # Check for player (if player exists, is alive, in room, and not ignored by debug)
        ignore_player = world.game and world.game.debug_ignore_player
        if player and player.is_alive and player.current_room_id == npc.current_room_id and not ignore_player:
            potential_targets.append(player)

        # Check for other NPCs in the room it is hostile to (friendly, neutral, player_minion)
        room_npcs = world.get_npcs_in_room(npc.current_region_id, npc.current_room_id)
        for other_npc in room_npcs:
            if other_npc != npc and other_npc.is_alive and npc_combat.is_hostile_to(npc, other_npc):
                potential_targets.append(other_npc)

        # If any targets found, pick one and attack
        if potential_targets and random.random() < npc.aggression:
            target_to_attack = random.choice(potential_targets)
            npc_combat.enter_combat(npc, target_to_attack)
            
            # Try an immediate attack, and return its message if the player can see it
            immediate_attack_msg = npc_combat.try_attack(npc, world, current_time)
            if immediate_attack_msg:
                return immediate_attack_msg
            
            # Fallback message if player is present but try_attack had no message (e.g. on CD)
            if player and player.current_room_id == npc.current_room_id:
                return f"{format_name_for_display(player, npc, True)} moves to attack {format_name_for_display(player, target_to_attack, False)}!"

    # --- THIS IS THE MISSING BLOCK ---
    # Logic for FRIENDLY/NEUTRAL NPCs to engage hostiles
    elif npc.faction != "hostile":
        room_npcs = world.get_npcs_in_room(npc.current_region_id, npc.current_room_id)
        hostiles_in_room = [other_npc for other_npc in room_npcs if other_npc.is_alive and other_npc.faction == "hostile"]
        
        if hostiles_in_room:
            # This NPC will engage the hostile to defend the area
            target_hostile = random.choice(hostiles_in_room)
            npc_combat.enter_combat(npc, target_hostile)
            
            engage_message = ""
            # Only generate a message if the player is in the same room to see it
            if player and player.is_alive and player.current_room_id == npc.current_room_id:
                attacker_name_fmt = format_name_for_display(player, npc, start_of_sentence=True)
                target_name_fmt = format_name_for_display(player, target_hostile, start_of_sentence=False)
                engage_message = f"{attacker_name_fmt} moves to attack {target_name_fmt}!"

            # Perform an immediate attack to be responsive
            immediate_attack_msg = npc_combat.try_attack(npc, world, current_time)
            if immediate_attack_msg:
                return (engage_message + "\n" + immediate_attack_msg).strip()
            else:
                return engage_message if engage_message else None # Return the engage message even if attack is on CD
    # --- END MISSING BLOCK ---

    # --- 4. Idle Movement (if not in combat and no new targets) ---
    if current_time - npc.last_moved < npc.move_cooldown: return None
    
    behavior = npc.behavior_type
    if behavior == "healer": behavior = "wanderer" # Wander when not healing
    
    move_message = None
    if behavior == "wanderer" or behavior == "aggressive": move_message = _wander_behavior(npc, world, player)
    elif behavior == "patrol": move_message = _patrol_behavior(npc, world, player)
    elif behavior == "follower": move_message = _follower_behavior(npc, world, player)
    elif behavior == "scheduled": move_message = _schedule_behavior(npc, world, player)
    elif behavior == "minion": move_message = _minion_behavior(npc, world, current_time, player) # Minion idle logic
    
    if move_message: npc.last_moved = current_time
    return move_message


def _move_npc(npc: 'NPC', world, player: 'Player', direction: str) -> Optional[str]:
    """Helper function to execute NPC movement and generate messages."""
    old_room_id = npc.current_room_id
    room = world.get_region(npc.current_region_id).get_room(old_room_id)
    if not room: return None # Safety check
    destination = room.exits.get(direction)
    if not destination: return None

    new_region_id, new_room_id = (destination.split(':') if ':' in destination else (npc.current_region_id, destination))
    
    message = None
    if player and player.current_room_id == old_room_id and player.is_alive:
        message = format_npc_departure_message(npc, direction, player)
    
    npc.current_region_id = new_region_id
    npc.current_room_id = new_room_id
    
    if player and player.current_room_id == new_room_id and player.is_alive:
        # If a departure message was already created, append arrival. Otherwise, just create arrival.
        arrival_msg = format_npc_arrival_message(npc, direction, player)
        message = (message + "\n" + arrival_msg) if message else arrival_msg
        
    return message


def _wander_behavior(npc: 'NPC', world, player: 'Player') -> Optional[str]:
    if random.random() > npc.wander_chance: return None
    room = world.get_region(npc.current_region_id).get_room(npc.current_room_id)
    if not room or not room.exits: return None
    
    valid_exits = {}
    is_in_instance = npc.current_region_id and npc.current_region_id.startswith("instance_")

    for direction, dest_id in room.exits.items():
        dest_region_id, dest_room_id = (dest_id.split(':') if ':' in dest_id else (npc.current_region_id, dest_id))

        if not dest_region_id: continue

        # no npcs should enter instances
        if not is_in_instance and dest_region_id.startswith("instance_"):
            continue

        # all npcs can move within the same region
        # no npcs can leave instances
        if is_in_instance:
            if dest_region_id == npc.current_region_id:
                valid_exits[direction] = dest_id
            continue

        # hostiles shouldn't wander into safe zones
        if npc.faction == 'hostile':
            if not world.is_location_safe(dest_region_id, dest_room_id):
                valid_exits[direction] = dest_id
        else:
            # friendly npcs can enter safe zones
            valid_exits[direction] = dest_id

    if not valid_exits: return None
    
    direction_to_go = random.choice(list(valid_exits.keys()))
    return _move_npc(npc, world, player, direction_to_go)

def _patrol_behavior(npc: 'NPC', world, player: 'Player') -> Optional[str]:
    if not npc.patrol_points: return None
    target_room_id = npc.patrol_points[npc.patrol_index]
    
    if npc.current_room_id == target_room_id:
        npc.patrol_index = (npc.patrol_index + 1) % len(npc.patrol_points)
        return None # Arrived at patrol point, wait for next cooldown

    # Find path to the *next* patrol point
    path = world.find_path(npc.current_region_id, npc.current_room_id, npc.home_region_id, target_room_id) # Assume patrol points are in home region
    if path: 
        return _move_npc(npc, world, player, path[0])
    else:
        # Cannot find path to patrol point, just wander
        return _wander_behavior(npc, world, player)

def _schedule_behavior(npc: 'NPC', world, player: 'Player') -> Optional[str]:
    game = world.game
    if not game: return None
    
    # Find the correct schedule entry for the current hour
    current_hour_str = str(game.time_manager.hour)
    target_entry = None
    if current_hour_str in npc.schedule:
        target_entry = npc.schedule[current_hour_str]
    else:
        # Find the most recent schedule entry before the current hour
        sorted_hours = sorted([int(h) for h in npc.schedule.keys()], reverse=True)
        for hour in sorted_hours:
            if game.time_manager.hour >= hour:
                target_entry = npc.schedule[str(hour)]
                break
        if not target_entry and sorted_hours: # Handle wrap-around (e.g., it's 3 AM, last entry was 10 PM)
            target_entry = npc.schedule[str(sorted_hours[0])] # Use latest entry from previous day
            
    if not target_entry: return None # No schedule defined for this NPC

    dest_region = target_entry.get("region_id")
    dest_room = target_entry.get("room_id")
    activity = target_entry.get("activity", "idle")

    new_destination = (dest_region, dest_room, activity)
    
    # Update AI state if destination is new
    if npc.schedule_destination != new_destination:
        npc.schedule_destination = new_destination
        npc.current_path = [] # Clear old path
        npc.ai_state["current_activity"] = activity

    # If at destination, do nothing
    if npc.current_region_id == dest_region and npc.current_room_id == dest_room:
        npc.current_path = [] # Clear path on arrival
        return None

    # Find path if we don't have one
    if not npc.current_path:
        path = world.find_path(npc.current_region_id, npc.current_room_id, dest_region, dest_room)
        if path:
            npc.current_path = path
        else:
            # Can't find path, stay put and clear destination to force recalculation next time
            npc.schedule_destination = None 
            return None
    
    # Move along the path
    direction = npc.current_path.pop(0)
    return _move_npc(npc, world, player, direction)


def _follower_behavior(npc: 'NPC', world, player: 'Player', path_override=None) -> Optional[str]:
    path = path_override
    if not path:
        target_id = npc.follow_target
        if not target_id: return None # No one to follow

        target = world.player if world.player and world.player.obj_id == target_id else world.get_npc(target_id)
        if not target or not target.is_alive: 
            npc.follow_target = None # Target is gone
            return None
        
        # Don't move if in the same room
        if npc.current_region_id == target.current_region_id and npc.current_room_id == target.current_room_id:
            return None 

        path = world.find_path(npc.current_region_id, npc.current_room_id, target.current_region_id, target.current_room_id)
    
    if path: 
        direction = path[0] # Just get the next direction
        if path_override: path.pop(0) # Only consume path if it's an override (like retreat path)
        return _move_npc(npc, world, player, direction)
    return None

def _minion_behavior(npc: 'NPC', world, current_time: float, player: 'Player') -> Optional[str]:
    """Handles logic for minions when they are IDLE (not in combat)."""
    from . import combat as npc_combat

    owner = player if player and player.obj_id == npc.properties.get("owner_id") else None

    # 1. Despawn if owner is missing or timer runs out
    if not owner:
        return npc.despawn(world, silent=True) # Despawn silently if owner doesn't exist
        
    duration = npc.properties.get("summon_duration", 0)
    created = npc.properties.get("creation_time", 0)
    if duration > 0 and current_time > (created + duration):
        return npc.despawn(world, silent=False) # Announce despawn from timeout

    owner_loc = (owner.current_region_id, owner.current_room_id)
    my_loc = (npc.current_region_id, npc.current_room_id)

    # 2. Follow owner if not in the same room
    if my_loc != owner_loc:
        npc.follow_target = owner.obj_id # Set target for follower logic
        return _follower_behavior(npc, world, player, path_override=None)

    # 3. If in the same room, check for things to attack
    if my_loc == owner_loc:
        # 3a. Assist owner if they are in combat
        if owner.in_combat and owner.combat_target:
            target = owner.combat_target
            if target and target.is_alive:
                npc_combat.enter_combat(npc, target)
                return f"{npc.name} moves to assist you against {format_name_for_display(player, target, False)}!"

        # 3b. Intercept anything attacking the owner
        room_npcs = world.get_npcs_in_room(npc.current_region_id, npc.current_room_id)
        attacker = next((other for other in room_npcs if other.is_alive and owner in other.combat_targets), None)
        if attacker:
            npc_combat.enter_combat(npc, attacker)
            return f"{npc.name} intercepts {format_name_for_display(player, attacker, False)}!"

        # 3c. Proactively attack any hostile in the room (aggressive minion stance)
        hostile = next((other for other in room_npcs if other.is_alive and other.faction == "hostile"), None)
        if hostile:
            npc_combat.enter_combat(npc, hostile)
            return f"{npc.name} moves to attack {format_name_for_display(player, hostile, False)}!"
            
    return None # Minion is idle and with its owner, no threats detected.


def _healer_behavior(npc: 'NPC', world, current_time, player: 'Player') -> Optional[str]:
    from . import combat as npc_combat # Local import
    
    heal_spell = next((s for s_id in npc.usable_spells if (s := get_spell(s_id)) and s.effect_type == "heal" and current_time >= npc.spell_cooldowns.get(s_id, 0) and npc.mana >= s.mana_cost), None)
    if not heal_spell: return None
    
    targets = world.get_npcs_in_room(npc.current_region_id, npc.current_room_id)
    if player and player.current_room_id == npc.current_room_id and player.is_alive: 
        targets.append(player)
    
    wounded = [t for t in targets if t.is_alive and not npc_combat.is_hostile_to(npc, t) and (t.health / t.max_health) < NPC_HEALER_HEAL_THRESHOLD]
    if not wounded: return None
    
    target_to_heal = min(wounded, key=lambda t: t.health / t.max_health)
    npc.last_combat_action = current_time # Using a spell counts as an action
    result = npc_combat.cast_spell(npc, heal_spell, target_to_heal, current_time)
    
    if player and player.current_room_id == npc.current_room_id:
        return result.get("message")
    return None

def start_retreat(npc: 'NPC', world, current_time: float, player: 'Player') -> Optional[str]:
    # No changes to this part - it finds the destination coordinates
    if not npc.retreat_destination and npc.current_region_id and npc.current_room_id:
        npc.retreat_destination = world.find_nearest_safe_room(npc.current_region_id, npc.current_room_id)
        
    if npc.retreat_destination:
        if world.game and world.game.debug_mode:
            print(f"[AI DEBUG] NPC '{npc.name}' ({npc.obj_id}) starting retreat to {npc.retreat_destination}")
        
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
            from . import combat as npc_combat
            npc_combat.exit_combat(npc)
            
            # Generate the improved message if the player can see the NPC
            if player and player.current_room_id == npc.current_room_id:
                return f"{format_name_for_display(player, npc, True)} looks exhausted and retreats from battle, heading {first_direction}!"
        else:
            # If no path is found, the retreat fails. Don't change state.
            npc.retreat_destination = None # Clear destination
            if world.game and world.game.debug_mode:
                print(f"[AI DEBUG] NPC '{npc.name}' failed to find a retreat path.")
            # Do not return a message, allowing the combat logic to fall back to a physical attack.
            return None 

    # This is reached if no retreat destination was found in the first place
    return None

def _retreat_behavior(npc: 'NPC', world, current_time: float, player: 'Player') -> Optional[str]:
    # 1. Check if retreat condition is over
    if npc.mana >= npc.max_mana:
        if world.game and world.game.debug_mode:
             print(f"[AI DEBUG] NPC '{npc.name}' recovered mana, resuming '{npc.original_behavior}'")
        npc.behavior_type = npc.original_behavior or "wanderer"
        npc.retreat_destination = None
        npc.current_path = []
        if player and player.current_room_id == npc.current_room_id:
            return f"{format_name_for_display(player, npc, True)} looks recovered."
        return None

    # 2. If at destination, do nothing (path should be empty)
    if npc.retreat_destination and (npc.current_region_id, npc.current_room_id) == npc.retreat_destination:
        npc.current_path = [] # Clear path on arrival
        return None 

    # 3. If we have a path, move along it.
    if npc.current_path:
        # The path was already calculated by start_retreat. We just follow it.
        next_direction = npc.current_path.pop(0)
        return _move_npc(npc, world, player, next_direction)

    # 4. Fallback if something went wrong (e.g., path is empty but not at destination)
    # This might happen if the world changes mid-retreat.
    npc.behavior_type = npc.original_behavior or "wanderer"
    npc.retreat_destination = None
    if player and player.current_room_id == npc.current_room_id:
        return f"{format_name_for_display(player, npc, True)} seems to have lost their way and stops retreating."
    return None

def _try_flee(npc: 'NPC', world, player: 'Player') -> Optional[str]:
    # Get the room the NPC is currently in, *before* moving.
    room_before_flee = world.get_region(npc.current_region_id).get_room(npc.current_room_id)
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
    from . import combat as npc_combat
    npc_combat.exit_combat(npc)
    
    # The NPC always moves, regardless of whether the player sees it.
    # The _move_npc function correctly handles any arrival message if the player is in the destination room.
    _move_npc(npc, world, player, direction)
    
    # Generate and return the specific "flee" message ONLY if the player was in the starting room.
    if player_can_see_flee:
        flee_msg = f"{format_name_for_display(player, npc, True)} flees to the {direction}!"
        return flee_msg

    # If the player wasn't in the same room, they see nothing.
    return None
