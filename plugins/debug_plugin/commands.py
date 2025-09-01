# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - The `level` command now captures the detailed summary string from the player's `level_up` method.
# - It now displays a full breakdown of stat, health, and mana gains when used.

import uuid
from commands.command_system import command, command_groups
from core.config import FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS
from items.item_factory import ItemFactory
from npcs.npc_factory import NPCFactory
from utils.text_formatter import format_target_name

def register_commands(plugin):
    @command("debug", ["dbg"], "debug", "Control debug mode and list available debug commands.\n\nUsage: debug [on|off|status]")
    def debug_command_handler(args, context):
        available_commands = sorted(list(set(c['name'] for c in command_groups.get('debug', []))))
        
        if not args:
            return "Debug plugin commands:\n" + "\n".join([f"- {cmd}" for cmd in available_commands])
        
        subcommand = args[0].lower()
        if subcommand == "on":
            return plugin.enable_debug_mode()
        elif subcommand == "off":
            return plugin.disable_debug_mode()
        elif subcommand == "status":
            services = plugin.service_locator.get_service_names() if plugin.service_locator else []
            return f"Debug status:\n- Debug mode: {plugin.debug_mode_enabled}\n- Available services: {', '.join(services)}"
        else:
            return f"Unknown debug subcommand: {subcommand}"

    @command("level", ["levelup"], "debug", "Level up the player.\n\nUsage: level [count]")
    def level_command_handler(args, context):
        player = plugin.world.player
        if not player: return "Player not available"
        
        levels_to_gain = 1
        if args and args[0].isdigit():
            levels_to_gain = int(args[0])
            if levels_to_gain <= 0: return "Number of levels must be positive."

        level_up_messages = []
        for _ in range(levels_to_gain):
            level_up_messages.append(player.level_up())
            
        return "\n\n".join(level_up_messages)

    # ... all other debug commands remain unchanged ...
    @command("settime", [], "debug", "Set game time and force NPCs to update schedule.\n\nUsage: settime <hour> [minute] or settime <period>")
    def settime_command_handler(args, context):
        time_plugin = plugin.get_service("plugin:time_plugin")
        if not time_plugin: return f"{FORMAT_ERROR}Time plugin not found{FORMAT_RESET}"
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

        days_since_epoch = (time_plugin.year - 1) * 360 + (time_plugin.month - 1) * 30 + (time_plugin.day - 1)
        total_minutes_since_epoch = days_since_epoch * 1440 + new_hour * 60 + new_minute
        time_plugin.game_time = float(total_minutes_since_epoch * 60)
        time_plugin._recalculate_date_from_game_time()
        time_plugin._update_time_period()
        time_plugin._update_world_time_data()

        if plugin.world:
            for npc in plugin.world.npcs.values():
                if npc.behavior_type == "scheduled":
                    npc.schedule_destination = None
                    npc.current_path = []

        return f"{FORMAT_SUCCESS}Time set to {new_hour:02d}:{new_minute:02d}. NPCs will update their schedules.{FORMAT_RESET}"

    @command("npcactivity", [], "debug", "Check an NPC's current activity and schedule goal.\n\nUsage: npcactivity <npc_name>")
    def npc_activity_handler(args, context):
        if not plugin.world: return f"{FORMAT_ERROR}World not available.{FORMAT_RESET}"
        if not args: return f"{FORMAT_ERROR}Check activity for which NPC?{FORMAT_RESET}"
        npc_name = " ".join(args).lower()
        found_npc = None
        for npc in plugin.world.npcs.values():
            if npc_name in npc.name.lower():
                found_npc = npc
                break
        if not found_npc: return f"{FORMAT_ERROR}NPC '{npc_name}' not found.{FORMAT_RESET}"
        
        activity = found_npc.ai_state.get("current_activity", "idle")
        loc = f"{found_npc.current_region_id}:{found_npc.current_room_id}"
        path_len = len(found_npc.current_path) if hasattr(found_npc, 'current_path') else 0
        dest = found_npc.schedule_destination if hasattr(found_npc, 'schedule_destination') else None
        
        response = f"--- Status for {found_npc.name} ---\n"
        response += f"Activity: {activity}\n"
        response += f"Location: {loc}\n"
        response += f"Behavior: {found_npc.behavior_type}\n"
        if found_npc.behavior_type == "scheduled":
            if dest:
                response += f"Scheduled Goal: Go to {dest[0]}:{dest[1]} to '{dest[2]}'\n"
            else:
                response += "Scheduled Goal: None currently\n"
            response += f"Path Length: {path_len} steps remaining\n"
        return response

    @command("debuggear", ["dbggear"], "debug", "Toggle a full set of powerful debug gear.\n\nUsage: debuggear <on|off>")
    def debuggear_command_handler(args, context):
        world = plugin.world
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

    @command("teleport", ["tp"], "debug", "Teleport to any room.\n\nUsage: teleport <region_id> <room_id> or teleport <room_id>")
    def teleport_command_handler(args, context):
        if not plugin.world: return "World not available"
        if not args: return "Usage: teleport <region_id> <room_id> or teleport <room_id> (same region)"
        old_region_id, old_room_id = plugin.world.current_region_id, plugin.world.current_room_id
        region_id, room_id = (args[0], args[1]) if len(args) > 1 else (plugin.world.current_region_id, args[0])
        region = plugin.world.get_region(region_id)
        if not region: return f"Region '{region_id}' not found"
        if not region.get_room(room_id): return f"Room '{room_id}' not found in region '{region_id}'"
        plugin.world.current_region_id = region_id
        plugin.world.current_room_id = room_id
        plugin.world.player.current_region_id = region_id
        plugin.world.player.current_room_id = room_id
        if hasattr(plugin.world, "game") and plugin.world.game.plugin_manager:
            plugin.world.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
            plugin.world.game.plugin_manager.on_room_enter(region_id, room_id)
        return f"Teleported to {region_id}:{room_id}\n\n{plugin.world.look()}"