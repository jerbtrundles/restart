# engine/npcs/ai/specialized.py
from typing import TYPE_CHECKING, Optional, List, Union
from engine.config import NPC_HEALER_HEAL_THRESHOLD
from engine.magic.spell_registry import get_spell
from engine.utils.utils import format_name_for_display
from engine.npcs import combat as npc_combat
from .movement import perform_follow

if TYPE_CHECKING:
    from engine.npcs.npc import NPC
    from engine.player import Player
    from engine.world.world import World

def perform_healer_logic(npc: 'NPC', world: 'World', current_time: float, player: 'Player') -> Optional[str]:
    """Behavior for healer NPCs to heal wounded allies."""
    
    # Safety Check: Ensure NPC has a valid location
    if not npc.current_region_id or not npc.current_room_id:
        return None

    # Find a heal spell
    heal_spell = next((s for s_id in npc.usable_spells 
                       if (s := get_spell(s_id)) 
                       and s.effect_type == "heal" 
                       and current_time >= npc.spell_cooldowns.get(s_id, 0) 
                       and npc.mana >= s.mana_cost), None)
    
    if not heal_spell: return None
    
    # Get NPCs in room and explicitly type the list to allow appending the Player
    targets: List[Union['NPC', 'Player']] = list(world.get_npcs_in_room(npc.current_region_id, npc.current_room_id))
    
    if player and player.current_room_id == npc.current_room_id and player.is_alive: 
        targets.append(player)
    
    # Filter for wounded friendly targets
    wounded = [t for t in targets 
               if t.is_alive 
               and not npc_combat.is_hostile_to(npc, t) 
               and (t.health / t.max_health) < NPC_HEALER_HEAL_THRESHOLD]
    
    if not wounded: return None
    
    target_to_heal = min(wounded, key=lambda t: t.health / t.max_health)
    npc.last_combat_action = current_time 
    
    result = npc_combat.cast_spell(npc, heal_spell, target_to_heal, current_time)
    
    if player and player.current_room_id == npc.current_room_id:
        return result.get("message")
    
    return None

def perform_minion_logic(npc: 'NPC', world: 'World', current_time: float, player: 'Player') -> Optional[str]:
    """Handles logic for minions when they are IDLE (not in combat)."""
    
    # Safety Check: Ensure NPC has a valid location
    if not npc.current_region_id or not npc.current_room_id:
        return None

    owner = player if player and player.obj_id == npc.properties.get("owner_id") else None

    # 1. Despawn if owner is missing or timer runs out
    if not owner:
        return npc.despawn(world, silent=True)
        
    duration = npc.properties.get("summon_duration", 0)
    created = npc.properties.get("creation_time", 0)
    if duration > 0 and current_time > (created + duration):
        return npc.despawn(world, silent=False) 

    owner_loc = (owner.current_region_id, owner.current_room_id)
    my_loc = (npc.current_region_id, npc.current_room_id)

    # 2. Follow owner if not in the same room
    if my_loc != owner_loc:
        npc.follow_target = owner.obj_id 
        return perform_follow(npc, world, player, path_override=None)

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

        # 3c. Proactively attack any hostile in the room
        hostile = next((other for other in room_npcs if other.is_alive and other.faction == "hostile"), None)
        if hostile:
            npc_combat.enter_combat(npc, hostile)
            return f"{npc.name} moves to attack {format_name_for_display(player, hostile, False)}!"
            
    return None