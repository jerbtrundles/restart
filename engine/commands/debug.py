# engine/commands/debug.py
"""
Contains all core debug and administrative commands for the game.
"""
import random
import time
from typing import Dict, List, Optional
from engine.commands.command_system import command, registered_commands, command_groups
from engine.config import (FORMAT_ERROR, FORMAT_RESET, FORMAT_SUCCESS,
                         FORMAT_TITLE, FORMAT_HIGHLIGHT, FORMAT_CATEGORY)
from engine.config.config_world import DYNAMIC_REGION_DEFAULT_NUM_ROOMS
from engine.items.item_factory import ITEM_CLASS_MAP, ItemFactory
from engine.magic.debug_effects import DEBUG_EFFECTS
from engine.npcs.npc import NPC
from engine.npcs.npc_factory import NPCFactory
from engine.utils.utils import format_name_for_display
from engine.world.region_generator import RegionGenerator
from engine.items.container import Container
from engine.items.key import Key
from engine.items.item import Item
from engine.items.lockpick import Lockpick
from engine.magic.spell_registry import load_spells_from_json, SPELL_REGISTRY, get_spell

def _find_npc_globally(world, npc_name: str) -> List[NPC]:
    """Helper function to find NPC(s) anywhere in the world by name."""
    npc_name_lower = npc_name.lower()
    exact_matches = []
    partial_matches = []
    for npc in world.npcs.values():
        if npc.name.lower() == npc_name_lower:
            exact_matches.append(npc)
        elif npc_name_lower in npc.name.lower():
            partial_matches.append(npc)
    return exact_matches or partial_matches

@command("spawn", ["create"], "debug",
         "Spawn an entity. Supports smart name resolution.\n"
         "Usage:\n"
         "  spawn <item_name> [quantity]\n"
         "  spawn <npc_name> [count] OR [count] [level]\n"
         "  spawn npc <npc_id> [count] [level]")
def spawn_handler(args, context):
    world = context["world"]
    player = world.player
    if not args:
        known_types = ", ".join(sorted([t.lower() for t in ITEM_CLASS_MAP.keys()]))
        return (f"{FORMAT_ERROR}Usage examples:\n"
                f"  spawn potion 5        (5 Potions)\n"
                f"  spawn goblin 5        (5 Default Level Goblins)\n"
                f"  spawn goblin 5 3      (5 Level 3 Goblins)\n"
                f"Item Types: {known_types}{FORMAT_RESET}")

    # --- HELPER FUNCTIONS ---
    def _resolve_item_id(user_input: str) -> Optional[str]:
        user_input_lower = user_input.lower()
        if user_input_lower in world.item_templates: return user_input_lower
        prefixes_to_try = ["item_", "scroll_"]
        for prefix in prefixes_to_try:
            potential_id = f"{prefix}{user_input_lower}"
            if potential_id in world.item_templates: return potential_id
        return None

    def _spawn_item(item_id: str, quantity: int) -> str:
        from engine.utils.utils import get_article, simple_plural
        resolved_id = _resolve_item_id(item_id)
        if not resolved_id: 
            return f"{FORMAT_ERROR}Could not find an item template matching '{item_id}'.{FORMAT_RESET}"
        
        spawned_items = []
        for _ in range(quantity):
            new_instance = ItemFactory.create_item_from_template(resolved_id, world)
            if new_instance:
                world.add_item_to_room(world.current_region_id, world.current_room_id, new_instance)
                spawned_items.append(new_instance)
            else:
                break 
        
        if not spawned_items:
            return f"{FORMAT_ERROR}Failed to spawn any items from template ID: {resolved_id}{FORMAT_RESET}"

        item_counts: Dict[str, int] = {}
        for item in spawned_items:
            item_counts[item.name] = item_counts.get(item.name, 0) + 1
        
        message_parts = []
        for name, count in item_counts.items():
            if count > 1:
                message_parts.append(f"{count} {simple_plural(name)}")
            else:
                message_parts.append(f"{get_article(name)} {name}")
        
        return f"{FORMAT_SUCCESS}Spawned {', '.join(message_parts)}.{FORMAT_RESET}"

    def _spawn_npc(template_id: str, count: int, level: Optional[int]) -> str:
        from engine.utils.utils import simple_plural, get_article
        
        spawned_names = []
        
        for _ in range(count):
            overrides = {"current_region_id": world.current_region_id, "current_room_id": world.current_room_id}
            if level: overrides["level"] = level
            
            npc = NPCFactory.create_npc_from_template(template_id, world, **overrides)
            if not npc:
                if not spawned_names:
                    return f"{FORMAT_ERROR}Failed to create NPC from template '{template_id}'.{FORMAT_RESET}"
                break # Stop if we fail partway
            
            world.add_npc(npc)
            spawned_names.append(npc.name)
            
        # Formatting the output message
        if len(spawned_names) == 1:
            formatted_name = format_name_for_display(player, world.get_npc(list(world.npcs.keys())[-1]), start_of_sentence=True) # Get last added
            return f"{formatted_name} appears!{FORMAT_RESET}"
        else:
             # Simple pluralization for the summary
             name = spawned_names[0]
             lvl_str = f" (Level {level})" if level else " (Default Level)"
             return f"{FORMAT_SUCCESS}Spawned {count} {simple_plural(name)}{lvl_str}.{FORMAT_RESET}"

    # --- MAIN COMMAND LOGIC ---
    
    # 1. Explicit "spawn npc <id> [count] [level]"
    if args[0].lower() == 'npc':
        if len(args) < 2: return f"{FORMAT_ERROR}Usage: spawn npc <npc_id> [count] [level]{FORMAT_RESET}"
        npc_id = args[1]
        
        count = 1
        level = None
        
        if len(args) > 2 and args[2].isdigit():
            count = int(args[2])
        
        if len(args) > 3 and args[3].isdigit():
            level = int(args[3])
            
        return _spawn_npc(npc_id, count, level)

    # 2. Random Item by Type "spawn <type> [quantity]"
    item_type_to_spawn = args[0].lower()
    known_item_types = [t.lower() for t in ITEM_CLASS_MAP.keys()]
    if item_type_to_spawn in known_item_types:
        matching_ids = [
            item_id for item_id, template in world.item_templates.items()
            if template.get("type", "").lower() == item_type_to_spawn
        ]
        if not matching_ids: return f"{FORMAT_ERROR}No items of type '{item_type_to_spawn}' are defined.{FORMAT_RESET}"
        
        random_item_id = random.choice(matching_ids)
        quantity = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1
        return _spawn_item(random_item_id, quantity)

    # 3. Smart Match "spawn <name> ..."
    #    Logic:
    #    - If 2 numbers at end: Name, Count, Level
    #    - If 1 number at end: 
    #         - If NPC: Name, Count (Default Level)  <-- CHANGED
    #         - If Item: Name, Quantity
    
    name_parts = list(args)
    val1 = None
    val2 = None
    
    # Check last arg
    if name_parts[-1].isdigit():
        val1 = int(name_parts.pop())
        # Check second to last arg
        if name_parts and name_parts[-1].isdigit():
            val2 = val1 # Shift: last was Level
            val1 = int(name_parts.pop()) # second-last was Count
    
    name = " ".join(name_parts)
    if not name: return f"{FORMAT_ERROR}You must specify something to spawn.{FORMAT_RESET}"
    
    # Check Item First
    resolved_item_id = _resolve_item_id(name)
    if resolved_item_id:
        quantity = val1 if val1 is not None else 1
        return _spawn_item(resolved_item_id, quantity)

    # Check NPC
    if name.lower() in world.npc_templates:
        if val2 is not None and val1 is not None:
            # "spawn goblin 5 3" -> Count 5, Level 3
            return _spawn_npc(name.lower(), count=val1, level=val2)
        elif val1 is not None:
            # "spawn goblin 5" -> Count 5, Default Level (CHANGED BEHAVIOR)
            return _spawn_npc(name.lower(), count=val1, level=None)
        else:
            # "spawn goblin" -> Count 1, Default Level
            return _spawn_npc(name.lower(), count=1, level=None)
    
    return f"{FORMAT_ERROR}Could not find an item or NPC template matching '{name}'.{FORMAT_RESET}"

@command("sethealth", ["hp"], "debug", "Set your current health.\nUsage: sethealth <amount>")
def sethealth_handler(args, context):
    player = context["world"].player
    if not player:
        return f"{FORMAT_ERROR}Player not found.{FORMAT_RESET}"
    if not args:
        return f"{FORMAT_ERROR}Usage: sethealth <amount>{FORMAT_RESET}"

    try:
        amount = int(args[0])
        old_health = player.health
        player.health = max(0, min(amount, player.max_health))
        
        if player.health == 0:
            player.die(context["world"])
            return f"{FORMAT_HIGHLIGHT}Health set to 0. You have died.{FORMAT_RESET}"
        
        return f"{FORMAT_SUCCESS}Health set from {old_health:.0f} to {player.health:.0f}/{player.max_health:.0f}.{FORMAT_RESET}"
    except ValueError:
        return f"{FORMAT_ERROR}Invalid number: '{args[0]}'. Please provide an integer.{FORMAT_RESET}"

@command("level", ["levelup"], "debug", "Level up the player, preserving XP progress.\nUsage: level [count]")
def level_command_handler(args, context):
    player = context["world"].player
    if not player: return "Player not available"
    
    levels_to_gain = int(args[0]) if args and args[0].isdigit() else 1
    if levels_to_gain <= 0: return "Number of levels must be positive."

    current_xp_percentage = 0
    if player.experience_to_level > 0:
        current_xp_percentage = max(0, player.experience) / player.experience_to_level

    level_up_messages = []
    for _ in range(levels_to_gain):
        player.experience = player.experience_to_level
        level_up_messages.append(player.level_up())

    player.experience = int(player.experience_to_level * current_xp_percentage)
    return "\n\n".join(level_up_messages)

@command("settime", [], "debug", "Set game time.\nUsage: settime <hour> [minute] or settime <period>")
def settime_command_handler(args, context):
    game = context["game"]
    time_manager = game.time_manager
    if not args: return f"{FORMAT_ERROR}Usage: settime <hour> [minute] or settime <period> (dawn/day/dusk/night){FORMAT_RESET}"

    new_hour, new_minute = -1, 0
    period_map = {"dawn": 6, "day": 10, "dusk": 18, "night": 22}
    if args[0].lower() in period_map:
        new_hour = period_map[args[0].lower()]
    else:
        try:
            new_hour = int(args[0])
            if not (0 <= new_hour <= 23): return f"{FORMAT_ERROR}Hour must be 0-23.{FORMAT_RESET}"
            if len(args) > 1:
                new_minute = int(args[1])
                if not (0 <= new_minute <= 59): return f"{FORMAT_ERROR}Minute must be 0-59.{FORMAT_RESET}"
        except ValueError: return f"{FORMAT_ERROR}Invalid time format.{FORMAT_RESET}"
    
    if new_hour == -1: return f"{FORMAT_ERROR}Could not set time.{FORMAT_RESET}"

    days_since_epoch = (time_manager.year - 1) * 360 + (time_manager.month - 1) * 30 + (time_manager.day - 1)
    total_minutes_since_epoch = days_since_epoch * 1440 + new_hour * 60 + new_minute
    time_manager.initialize_time(float(total_minutes_since_epoch * 60))

    for npc in game.world.npcs.values():
        if npc.behavior_type == "scheduled":
            npc.schedule_destination = None
            npc.current_path = []

    return f"{FORMAT_SUCCESS}Time set to {new_hour:02d}:{new_minute:02d}. NPCs will update schedules.{FORMAT_RESET}"

@command("setweather", [], "debug", "Set the current weather.\nUsage: setweather <type> [intensity]")
def setweather_command_handler(args, context):
    game = context["game"]
    weather_manager = game.weather_manager
    if not args:
        return f"{FORMAT_ERROR}Usage: setweather <type> [intensity].\nTypes: clear, cloudy, rain, storm, snow.{FORMAT_RESET}"

    weather_type = args[0].lower()
    if weather_type not in weather_manager.weather_chances["summer"]:
        return f"{FORMAT_ERROR}Invalid weather type '{weather_type}'.{FORMAT_RESET}"

    weather_manager.current_weather = weather_type
    
    if len(args) > 1:
        intensity = args[1].lower()
        if intensity in ["mild", "moderate", "strong", "severe"]:
            weather_manager.current_intensity = intensity
        else:
            return f"{FORMAT_ERROR}Invalid intensity '{intensity}'. Use mild, moderate, strong, or severe.{FORMAT_RESET}"
    
    return f"{FORMAT_SUCCESS}Weather set to {weather_manager.current_weather} ({weather_manager.current_intensity}).{FORMAT_RESET}"

@command("teleport", ["tp"], "debug", "Teleport to a room or an NPC.\nUsage:\n  teleport <region_id> <room_id>\n  teleport <npc_name>")
def teleport_command_handler(args, context):
    world = context["world"]
    if not args: return f"{FORMAT_ERROR}Usage: teleport <region_id> <room_id> OR teleport <npc_name>{FORMAT_RESET}"
    
    if len(args) == 2:
        region_id, room_id = args[0], args[1]
        region = world.get_region(region_id)
        if region and region.get_room(room_id):
            world.current_region_id = region_id
            world.current_room_id = room_id
            world.player.current_region_id = region_id
            world.player.current_room_id = room_id
            return f"{FORMAT_SUCCESS}Teleported to {region_id}:{room_id}{FORMAT_RESET}\n\n{world.look(minimal=True)}"

    npc_name = " ".join(args)
    matches = _find_npc_globally(world, npc_name)

    if not matches:
        return f"{FORMAT_ERROR}Could not find location or NPC named '{npc_name}'.{FORMAT_RESET}"
    if len(matches) > 1:
        match_names = [f"{npc.name} ({npc.obj_id})" for npc in matches]
        return f"{FORMAT_ERROR}Ambiguous target. Found: {', '.join(match_names)}.{FORMAT_RESET}"

    target_npc = matches[0]
    if not target_npc.current_region_id or not target_npc.current_room_id:
        return f"{FORMAT_ERROR}{target_npc.name} is in an unknown location and cannot be teleported to.{FORMAT_RESET}"

    world.current_region_id = target_npc.current_region_id
    world.current_room_id = target_npc.current_room_id
    world.player.current_region_id = target_npc.current_region_id
    world.player.current_room_id = target_npc.current_room_id
    
    return f"{FORMAT_SUCCESS}Teleported to {target_npc.name}'s location ({target_npc.current_region_id}:{target_npc.current_room_id}){FORMAT_RESET}\n\n{world.look(minimal=True)}"

@command("whereis", ["find"], "debug", "Find the location of an NPC.\nUsage: whereis <npc_name>")
def whereis_handler(args, context):
    world = context["world"]
    if not args:
        return f"{FORMAT_ERROR}Usage: whereis <npc_name>{FORMAT_RESET}"

    npc_name = " ".join(args)
    matches = _find_npc_globally(world, npc_name)

    if not matches:
        return f"{FORMAT_ERROR}Could not find any NPC named '{npc_name}'.{FORMAT_RESET}"
    if len(matches) > 1:
        match_names = [f"{npc.name} ({npc.obj_id})" for npc in matches]
        return f"{FORMAT_ERROR}Ambiguous target. Found: {', '.join(match_names)}.{FORMAT_RESET}"

    npc = matches[0]
    region = world.get_region(npc.current_region_id)
    room = region.get_room(npc.current_room_id) if region else None

    if region and room:
        return f"{FORMAT_HIGHLIGHT}{npc.name}{FORMAT_RESET} is at: {region.name} ({room.name}) [{npc.current_region_id}:{npc.current_room_id}]"
    else:
        return f"{FORMAT_ERROR}{npc.name} is in an invalid location: {npc.current_region_id}:{npc.current_room_id}{FORMAT_RESET}"

@command("ignoreplayer", [], "debug", "Make hostile NPCs ignore the player.\nUsage: ignoreplayer <on|off>")
def ignoreplayer_handler(args, context):
    game = context["game"]
    if not args or args[0].lower() not in ["on", "off"]:
        current_status = "ON" if game.debug_ignore_player else "OFF"
        return f"Usage: ignoreplayer <on|off>\nCurrently: {current_status}"

    action = args[0].lower()
    game.debug_ignore_player = (action == "on")
    status_msg = "will now ignore you" if action == "on" else "will now engage you normally"
    return f"{FORMAT_SUCCESS}Hostiles {status_msg}.{FORMAT_RESET}"

@command("debuggear", ["dbggear"], "debug", "Toggle a full set of powerful debug gear.\nUsage: debuggear <on|off>")
def debuggear_command_handler(args, context):
    world = context["world"]
    player = world.player if world else None

    if not player: return f"{FORMAT_ERROR}Player not found.{FORMAT_RESET}"
    if not args or args[0].lower() not in ["on", "off"]: return f"{FORMAT_ERROR}Usage: debuggear <on|off>{FORMAT_RESET}"

    action = args[0].lower()
    debug_item_ids = [
        "debug_sword", "debug_shield", "debug_armor", "debug_helmet",
        "debug_gauntlets", "debug_boots", "debug_amulet"
    ]
    messages = []

    if action == "on":
        messages.append(f"{FORMAT_HIGHLIGHT}Equipping full debug gear...{FORMAT_RESET}")
        for item_id in debug_item_ids:
            is_present = any(item.obj_id == item_id for item in player.equipment.values() if item) or player.inventory.find_item_by_id(item_id)
            if is_present:
                messages.append(f"- {item_id}: Already present.")
                continue
            
            item = ItemFactory.create_item_from_template(item_id, world)
            if item:
                added, msg = player.inventory.add_item(item)
                if added:
                    equipped, msg_equip = player.equip_item(item)
                    if equipped: messages.append(f"- {FORMAT_SUCCESS}Equipped {item.name}.{FORMAT_RESET}")
                    else: messages.append(f"- {FORMAT_ERROR}Failed to equip {item.name}: {msg_equip}{FORMAT_RESET}")
                else: messages.append(f"- {FORMAT_ERROR}Failed to add {item.name} to inventory: {msg}{FORMAT_RESET}")
            else: messages.append(f"- {FORMAT_ERROR}Failed to create item '{item_id}'.{FORMAT_RESET}")
        
        return "\n".join(messages)

    elif action == "off":
        messages.append(f"{FORMAT_HIGHLIGHT}Removing all debug gear...{FORMAT_RESET}")
        items_removed = False
        
        for slot, item in list(player.equipment.items()):
            if item and item.obj_id in debug_item_ids:
                player.unequip_item(slot)
        
        for item_id in debug_item_ids:
            removed_item, count, msg = player.inventory.remove_item(item_id, 999)
            if removed_item and count > 0:
                messages.append(f"- Removed {count}x {removed_item.name} from inventory.")
                items_removed = True

        if not items_removed:
            messages.append("- No debug gear found to remove.")
        
        return "\n".join(messages)

@command("debug_commands", ["dbgcmd"], "debug", "Show all registered commands and their state.")
def debug_commands_handler(args, context):
    total_commands = len(registered_commands)
    unique_commands = len(set(cmd['handler'] for cmd in registered_commands.values()))
    
    response = f"{FORMAT_TITLE}===== Command Registry State ====={FORMAT_RESET}\n"
    response += f"Total Registered Names/Aliases: {FORMAT_HIGHLIGHT}{total_commands}{FORMAT_RESET}\n"
    response += f"Unique Command Functions: {FORMAT_HIGHLIGHT}{unique_commands}{FORMAT_RESET}\n\n"

    if not registered_commands:
        response += f"{FORMAT_ERROR}No commands are registered!{FORMAT_RESET}\n"
        return response

    response += f"{FORMAT_TITLE}Commands by Category:{FORMAT_RESET}\n"
    for category, commands_list in sorted(command_groups.items()):
        if not commands_list: continue
        unique_cmds_in_cat = sorted(list({cmd['name'] for cmd in commands_list}))
        response += f"  - {FORMAT_CATEGORY}{category.capitalize()}{FORMAT_RESET} ({len(unique_cmds_in_cat)} unique):\n"
        for cmd_name in unique_cmds_in_cat:
            response += f"    - {cmd_name}\n"
    
    return response

@command("genregion", ["dungeon"], "debug", "Generate a dynamic region.\nUsage: genregion <theme> [num_rooms]")
def genregion_handler(args, context):
    world = context["world"]
    player = world.player
    if not player or not world.current_room_id:
        return f"{FORMAT_ERROR}You must be in the world to generate a region.{FORMAT_RESET}"

    if not args:
        generator = RegionGenerator(world)
        themes = ", ".join(generator.themes.keys())
        return f"{FORMAT_ERROR}Usage: genregion <theme> [num_rooms]\nAvailable themes: {themes}{FORMAT_RESET}"

    theme = args[0].lower()
    num_rooms = DYNAMIC_REGION_DEFAULT_NUM_ROOMS
    if len(args) > 1:
        try:
            num_rooms = int(args[1])
            if not (3 <= num_rooms <= 50): return f"{FORMAT_ERROR}Number of rooms must be between 3 and 50.{FORMAT_RESET}"
        except ValueError: return f"{FORMAT_ERROR}Invalid number of rooms.{FORMAT_RESET}"
    
    current_room = world.get_current_room()
    if "portal" in current_room.exits: return f"{FORMAT_ERROR}There is already a portal in this room.{FORMAT_RESET}"
    
    generator = RegionGenerator(world)
    generation_result = generator.generate_region(theme, num_rooms)
    if not generation_result: return f"{FORMAT_ERROR}Failed to generate region.{FORMAT_RESET}"
    
    new_region, entry_room_id = generation_result
    world.add_region(new_region.obj_id, new_region)
    
    current_room.exits["portal"] = f"{new_region.obj_id}:{entry_room_id}"
    entry_room = new_region.get_room(entry_room_id)
    if entry_room: entry_room.exits["portal"] = f"{world.current_region_id}:{world.current_room_id}"
    
    return (f"{FORMAT_SUCCESS}A shimmering portal appears!{FORMAT_RESET}\n"
            f"It leads to a new region: {FORMAT_HIGHLIGHT}{new_region.name}{FORMAT_RESET} ({new_region.obj_id})")

@command("close portal", [], "debug", "Close a portal and destroy the linked region.")
def close_portal_handler(args, context):
    world = context["world"]
    player = world.player
    if not player or not world.current_room_id: return f"{FORMAT_ERROR}You must be in the world.{FORMAT_RESET}"
    
    current_room = world.get_current_room()
    portal_exit = current_room.exits.get("portal")
    if not portal_exit: return f"{FORMAT_ERROR}There is no portal here to close.{FORMAT_RESET}"

    try: region_id_to_delete, room_id_linked = portal_exit.split(":")
    except ValueError: return f"{FORMAT_ERROR}The portal is corrupted.{FORMAT_RESET}"

    if not region_id_to_delete.startswith("dynamic_"): return f"{FORMAT_ERROR}This portal leads to a permanent region.{FORMAT_RESET}"

    linked_region = world.get_region(region_id_to_delete)
    if linked_region:
        linked_room = linked_region.get_room(room_id_linked)
        if linked_room and "portal" in linked_room.exits: del linked_room.exits["portal"]
            
    npcs_to_remove = [npc.obj_id for npc in world.npcs.values() if npc.current_region_id == region_id_to_delete]
    for npc_id in npcs_to_remove: del world.npcs[npc_id]
    if region_id_to_delete in world.regions: del world.regions[region_id_to_delete]
    del current_room.exits["portal"]

    return f"{FORMAT_SUCCESS}You close the portal. The region {region_id_to_delete} collapses.{FORMAT_RESET}"

@command("applyeffect", ["ae", "addeffect"], "debug", "Apply a debug status effect.")
def applyeffect_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}Player not found.{FORMAT_RESET}"
    if len(args) < 2:
        available_effects = ", ".join(DEBUG_EFFECTS.keys())
        return f"{FORMAT_ERROR}Usage: applyeffect <target> <effect>\nAvailable effects: {available_effects}{FORMAT_RESET}"

    target_name = args[0].lower(); effect_name = args[1].lower()
    target = player if target_name in ["self", "me", player.name.lower()] else world.find_npc_in_room(target_name)
    if not target: return f"{FORMAT_ERROR}Target '{target_name}' not found.{FORMAT_RESET}"

    effect_data = DEBUG_EFFECTS.get(effect_name)
    if not effect_data: return f"{FORMAT_ERROR}Debug effect '{effect_name}' not found.{FORMAT_RESET}"

    success, _ = target.apply_effect(effect_data, time.time())
    return f"{FORMAT_SUCCESS}Applied '{effect_name}' to {target.name}.{FORMAT_RESET}" if success else f"{FORMAT_ERROR}Failed to apply effect.{FORMAT_RESET}"

@command("removeeffect", ["cleareffect"], "debug", "Remove a status effect.")
def removeeffect_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}Player not found.{FORMAT_RESET}"
    if len(args) < 2: return f"{FORMAT_ERROR}Usage: removeeffect <target> <effect_name>{FORMAT_RESET}"

    target_name = args[0].lower(); effect_name = args[1].lower()
    target = player if target_name in ["self", "me", player.name.lower()] else world.find_npc_in_room(target_name)
    if not target: return f"{FORMAT_ERROR}Target '{target_name}' not found.{FORMAT_RESET}"

    success = target.remove_effect(effect_name)
    return f"{FORMAT_SUCCESS}Removed '{effect_name}' from {target.name}.{FORMAT_RESET}" if success else f"{FORMAT_ERROR}Effect not found.{FORMAT_RESET}"

@command("testrefactor", ["testlock"], "debug", "Focused test for locking/unlocking mechanics.")
def test_refactor_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return "Player not found."

    # --- 0. FORCE RELOAD SPELLS ---
    # Explicitly check for the spells before trying to learn them
    print("[DEBUG] Force reloading spells for test...")
    load_spells_from_json()

    # --- 1. Setup Objects ---
    key_id = "debug_key_999"
    
    # Check if spells loaded correctly
    knock_exists = get_spell("knock") is not None
    al_exists = get_spell("arcane_lock") is not None
    print(f"[DEBUG] Spells Loaded? Knock: {knock_exists}, Arcane Lock: {al_exists}")

    # Loot
    loot = Item(name="Victory Token", description="You successfully unlocked it!", weight=0.1, value=1000)
    
    # Chest (Locked)
    chest = Container(
        obj_id="debug_chest_999",
        name="Refactor Chest",
        description="A chest created to test the decoupling of Keys and Containers.",
        locked=True, key_id=key_id, capacity=100, contents=[loot]
    )
    
    # Key
    key = Key(obj_id=key_id, name="Refactor Key", description="Opens the Refactor Chest.", weight=0.1)
    
    # Lockpick
    lockpick = Lockpick(obj_id="debug_lockpick_01", name="debug lockpick", description="A flimsy tool.", weight=0.1)

    # --- 2. Clean State & Placement ---
    # Remove old test items if they exist to prevent duplicates
    existing_chest = world.find_item_in_room("Refactor Chest")
    if existing_chest: world.remove_item_instance_from_room(world.current_region_id, world.current_room_id, existing_chest)
    
    # Place new objects
    world.add_item_to_room(world.current_region_id, world.current_room_id, chest)
    player.inventory.add_item(key)
    player.inventory.add_item(lockpick)

    # --- 3. Learn Spells ---
    k_success, k_msg = player.learn_spell("knock")
    al_success, al_msg = player.learn_spell("arcane_lock")
    player.mana = player.max_mana # Restore mana

    # --- 4. Feedback ---
    msgs = [
        f"{FORMAT_TITLE}--- LOCK/UNLOCK TEST INITIALIZED ---{FORMAT_RESET}",
        f"1. Placed {FORMAT_HIGHLIGHT}Refactor Chest{FORMAT_RESET} (Locked) in the room.",
        f"2. Added {FORMAT_HIGHLIGHT}Refactor Key{FORMAT_RESET} and {FORMAT_HIGHLIGHT}debug lockpick{FORMAT_RESET} to inventory.",
    ]

    if k_success: msgs.append(f"3. Learned 'Knock'.")
    else: msgs.append(f"3. {FORMAT_ERROR}Failed to learn 'Knock': {k_msg}{FORMAT_RESET}")

    if al_success: msgs.append(f"4. Learned 'Arcane Lock'.")
    else: msgs.append(f"4. {FORMAT_ERROR}Failed to learn 'Arcane Lock': {al_msg}{FORMAT_RESET}")

    msgs.append(f"{FORMAT_CATEGORY}Current Mana restored to {player.mana}/{player.max_mana}.{FORMAT_RESET}")
    msgs.append("\n" + "="*20)
    msgs.append("TESTING SCENARIOS:")
    msgs.append(f"1. {FORMAT_HIGHLIGHT}use refactor key on refactor chest{FORMAT_RESET} (Should unlock)")
    msgs.append(f"2. {FORMAT_HIGHLIGHT}cast arcane lock on refactor chest{FORMAT_RESET} (Should lock)")
    msgs.append(f"3. {FORMAT_HIGHLIGHT}cast knock on refactor chest{FORMAT_RESET} (Should unlock)")
    msgs.append(f"4. {FORMAT_HIGHLIGHT}use debug lockpick on refactor chest{FORMAT_RESET} (Chance to unlock/break)")
    msgs.append(f"5. {FORMAT_HIGHLIGHT}take token from refactor chest{FORMAT_RESET} (Loot)")

    return "\n".join(msgs)

@command("census", ["pop", "population"], "debug", "Show active NPC counts per region.\nUsage: census")
def census_handler(args, context):
    world = context["world"]
    
    # Dictionary to hold counts: {region_id: count}
    counts = {}
    total_active = 0
    
    # Iterate through all NPCs in memory
    for npc in world.npcs.values():
        if not npc.is_alive: continue # Ignore dead NPCs waiting for cleanup
        
        rid = npc.current_region_id or "unknown"
        counts[rid] = counts.get(rid, 0) + 1
        total_active += 1
        
    current_region = world.current_region_id

    # Formatting
    msg = [
        f"{FORMAT_TITLE}WORLD CENSUS ({total_active} NPCs){FORMAT_RESET}",
        f"{FORMAT_CATEGORY}Current Region:{FORMAT_RESET} {current_region}"
    ]
    
    # Sort regions alphabetically
    for region_id in sorted(counts.keys()):
        count = counts[region_id]
        # Highlight the current region to show where spawning SHOULD be happening
        if region_id == current_region:
            line = f"{FORMAT_HIGHLIGHT}>> {region_id:<15}: {count}{FORMAT_RESET} (Active)"
        else:
            line = f"   {region_id:<15}: {count} (Dormant)"
        msg.append(line)
        
    return "\n".join(msg)

@command("setgold", ["gold", "money"], "debug", "Set your current gold amount.\nUsage: setgold <amount>")
def set_gold_handler(args, context):
    player = context["world"].player
    if not player: return f"{FORMAT_ERROR}Player not found.{FORMAT_RESET}"
    
    if not args: return f"{FORMAT_ERROR}Usage: setgold <amount>{FORMAT_RESET}"
    
    try:
        amount = int(args[0])
        if amount < 0: return f"{FORMAT_ERROR}Amount cannot be negative.{FORMAT_RESET}"
        
        old_gold = player.gold
        player.gold = amount
        return f"{FORMAT_SUCCESS}Gold updated from {old_gold} to {player.gold}.{FORMAT_RESET}"
    except ValueError:
        return f"{FORMAT_ERROR}Invalid amount.{FORMAT_RESET}"
