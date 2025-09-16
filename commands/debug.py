# commands/debug.py
"""
Contains all core debug and administrative commands for the game.
"""
from commands.command_system import command, registered_commands, command_groups
from config import (FORMAT_ERROR, FORMAT_RESET, FORMAT_SUCCESS,
                         FORMAT_TITLE, FORMAT_HIGHLIGHT, FORMAT_CATEGORY)
from items.item_factory import ItemFactory
from npcs.npc_factory import NPCFactory
from utils.utils import format_name_for_display


@command("spawn", ["create"], "debug",
         "Spawn an item or NPC.\n"
         "Usage:\n"
         "  spawn <template_id> [quantity_or_level]\n"
         "  spawn item <item_id> [quantity]\n"
         "  spawn npc <template_id> [level]")
def spawn_handler(args, context):
    world = context["world"]
    player = world.player
    if not args:
        return f"{FORMAT_ERROR}Usage: spawn <template_id> [quantity_or_level]{FORMAT_RESET}"

    # Helper functions to avoid code duplication
    def _spawn_item(item_id, quantity):
        item = ItemFactory.create_item_from_template(item_id, world)
        if not item: return f"{FORMAT_ERROR}Failed to create item from template ID: {item_id}{FORMAT_RESET}"
        for _ in range(quantity):
            new_instance = ItemFactory.create_item_from_template(item_id, world)
            if new_instance:
                world.add_item_to_room(world.current_region_id, world.current_room_id, new_instance)
        return f"{FORMAT_SUCCESS}Spawned {quantity} {item.name}{'s' if quantity > 1 else ''}.{FORMAT_RESET}"

    def _spawn_npc(template_id, level):
        overrides = {"current_region_id": world.current_region_id, "current_room_id": world.current_room_id}
        if level: overrides["level"] = level
        
        npc = NPCFactory.create_npc_from_template(template_id, world, **overrides)
        if not npc: return f"{FORMAT_ERROR}Failed to create NPC from template '{template_id}'.{FORMAT_RESET}"
        
        world.add_npc(npc)
        formatted_name = format_name_for_display(player, npc, start_of_sentence=True)
        return f"{formatted_name} appears!{FORMAT_RESET}"

    # Handle explicit "item" or "npc" subcommands
    if args[0].lower() in ["item", "npc"]:
        spawn_type = args[0].lower()
        sub_args = args[1:]
        if not sub_args: return f"{FORMAT_ERROR}You must specify an ID to spawn.{FORMAT_RESET}"

        entity_id_parts = list(sub_args)
        num_suffix = 1
        is_numeric_suffix = False
        if sub_args[-1].isdigit():
            num_suffix = int(sub_args[-1])
            entity_id_parts.pop()
            is_numeric_suffix = True
        
        entity_id = " ".join(entity_id_parts)

        if spawn_type == "item":
            return _spawn_item(entity_id, num_suffix)
        elif spawn_type == "npc":
            level = num_suffix if is_numeric_suffix else None
            return _spawn_npc(entity_id, level)
    
    # Handle implicit spawning
    template_id_parts = list(args)
    quantity_or_level = 1
    is_numeric_suffix = False
    if args[-1].isdigit():
        quantity_or_level = int(args[-1])
        template_id_parts.pop()
        is_numeric_suffix = True

    if not template_id_parts: return f"{FORMAT_ERROR}You must specify an ID to spawn.{FORMAT_RESET}"
    template_id = " ".join(template_id_parts)

    npc_template_found = world.npc_templates.get(template_id)
    item_template_found = world.item_templates.get(template_id)

    if npc_template_found and item_template_found:
        return (f"{FORMAT_ERROR}Ambiguous ID: '{template_id}' exists as both an item and an NPC.\n"
                f"Please specify: 'spawn npc {template_id}' or 'spawn item {template_id}'.{FORMAT_RESET}")
    elif npc_template_found:
        level = quantity_or_level if is_numeric_suffix else None
        return _spawn_npc(template_id, level)
    elif item_template_found:
        return _spawn_item(template_id, quantity_or_level)
    else:
        return f"{FORMAT_ERROR}Could not find an item or NPC template with ID '{template_id}'.{FORMAT_RESET}"

@command("level", ["levelup"], "debug", "Level up the player.\nUsage: level [count]")
def level_command_handler(args, context):
    player = context["world"].player
    if not player: return "Player not available"
    
    levels_to_gain = int(args[0]) if args and args[0].isdigit() else 1
    if levels_to_gain <= 0: return "Number of levels must be positive."

    level_up_messages = [player.level_up() for _ in range(levels_to_gain)]
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
    if weather_type not in weather_manager.weather_chances["summer"]: # Check against any season's list
        return f"{FORMAT_ERROR}Invalid weather type '{weather_type}'.{FORMAT_RESET}"

    weather_manager.current_weather = weather_type
    
    if len(args) > 1:
        intensity = args[1].lower()
        if intensity in ["mild", "moderate", "strong", "severe"]:
            weather_manager.current_intensity = intensity
        else:
            return f"{FORMAT_ERROR}Invalid intensity '{intensity}'. Use mild, moderate, strong, or severe.{FORMAT_RESET}"
    
    return f"{FORMAT_SUCCESS}Weather set to {weather_manager.current_weather} ({weather_manager.current_intensity}).{FORMAT_RESET}"

@command("teleport", ["tp"], "debug", "Teleport to any room.\nUsage: teleport <region_id> <room_id> or teleport <room_id>")
def teleport_command_handler(args, context):
    world = context["world"]
    if not args: return "Usage: teleport <region_id> <room_id> or teleport <room_id> (same region)"
    
    old_region_id, old_room_id = world.current_region_id, world.current_room_id
    region_id, room_id = (args[0], args[1]) if len(args) > 1 else (world.current_region_id, args[0])
    
    region = world.get_region(region_id)
    if not region: return f"Region '{region_id}' not found"
    if not region.get_room(room_id): return f"Room '{room_id}' not found in region '{region_id}'"
    
    world.current_region_id = region_id
    world.current_room_id = room_id
    world.player.current_region_id = region_id
    world.player.current_room_id = room_id
    
    return f"Teleported to {region_id}:{room_id}\n\n{world.look(minimal=True)}"

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
            # Check if already equipped or in inventory
            is_present = any(item.obj_id == item_id for item in player.equipment.values() if item) or player.inventory.find_item_by_id(item_id)
            if is_present:
                messages.append(f"- {item_id}: Already present.")
                continue
            
            item = ItemFactory.create_item_from_template(item_id, world)
            if item:
                # Add to inventory first, then equip from there
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
        
        # Unequip first
        for slot, item in list(player.equipment.items()):
            if item and item.obj_id in debug_item_ids:
                player.unequip_item(slot)
        
        # Then remove from inventory
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
    """
    A debug command to inspect the state of the command registration system.
    """
    total_commands = len(registered_commands)
    unique_commands = len(set(cmd['handler'] for cmd in registered_commands.values()))
    
    response = f"{FORMAT_TITLE}===== Command Registry State ====={FORMAT_RESET}\n"
    response += f"Total Registered Names/Aliases: {FORMAT_HIGHLIGHT}{total_commands}{FORMAT_RESET}\n"
    response += f"Unique Command Functions: {FORMAT_HIGHLIGHT}{unique_commands}{FORMAT_RESET}\n\n"

    if not registered_commands:
        response += f"{FORMAT_ERROR}No commands are registered! Check the console for import errors during startup.{FORMAT_RESET}\n"
        return response

    response += f"{FORMAT_TITLE}Commands by Category:{FORMAT_RESET}\n"
    for category, commands_list in sorted(command_groups.items()):
        if not commands_list:
            continue
        
        # Get unique commands for this category
        unique_cmds_in_cat = sorted(list({cmd['name'] for cmd in commands_list}))
        
        response += f"  - {FORMAT_CATEGORY}{category.capitalize()}{FORMAT_RESET} ({len(unique_cmds_in_cat)} unique):\n"
        for cmd_name in unique_cmds_in_cat:
            response += f"    - {cmd_name}\n"
    
    response += f"\n{FORMAT_TITLE}All Registered Names:{FORMAT_RESET}\n"
    response += ", ".join(sorted(registered_commands.keys()))
    
    return response
