# commands/combat.py
"""
Contains all commands related to player combat actions.
"""
import time
from commands.command_system import command
from core.config import FORMAT_ERROR, FORMAT_RESET

@command("attack", ["kill", "fight", "hit"], "combat", "Attack a target.\nUsage: attack <target_name>")
def attack_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot attack.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Attack whom?{FORMAT_RESET}"

    # If player is trading, attacking will stop the trade
    if player.trading_with:
        vendor = world.get_npc(player.trading_with)
        if vendor:
            vendor.is_trading = False
        player.trading_with = None

    target_name = " ".join(args).lower()
    target_npc = None
    # Prioritize exact match
    for npc in world.get_current_room_npcs():
        if target_name == npc.name.lower() or target_name == npc.obj_id:
            target_npc = npc
            break
    # Fallback to partial match
    if not target_npc:
        for npc in world.get_current_room_npcs():
            if target_name in npc.name.lower():
                target_npc = npc
                break

    if not target_npc:
        return f"{FORMAT_ERROR}No '{target_name}' here to attack.{FORMAT_RESET}"
    if not target_npc.is_alive:
        return f"{FORMAT_ERROR}{target_npc.name} is already defeated.{FORMAT_RESET}"

    current_time = time.time()
    
    if not player.can_attack(current_time):
        effective_cooldown = player.get_effective_attack_cooldown()
        time_left = effective_cooldown - (current_time - player.last_attack_time)
        return f"Not ready. Wait {max(0, time_left):.1f}s."

    attack_result = player.attack(target_npc, world)
    return attack_result["message"]

@command("combat", ["cstat", "fightstatus"], "combat", "Show combat status.")
def combat_status_handler(args, context):
    world = context.get("world")
    player = getattr(world, "player", None)
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.in_combat: return "You are not in combat."
    
    return player.get_combat_status()