"""
plugins/debug_plugin/commands.py
Command module for the Debug plugin.
"""
import uuid
from commands.commands import command
from core.config import FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS
from items.item_factory import ItemFactory
from npcs.npc_factory import NPCFactory
from utils.text_formatter import format_target_name

def register_commands(plugin):
    @command("debug", ["dbg"], "system", "Control debug mode and list available debug commands.\n\nUsage: debug [on|off|status]")
    def debug_command_handler(args, context):
        available_commands = plugin.config["debug_commands"] + ["debuggear"]
        if not args:
            return "Debug plugin commands:\n" + "\n".join([
                 f"- {cmd}" for cmd in available_commands
            ])
        subcommand = args[0].lower()
        subargs = args[1:]
        if subcommand == "on":
            return plugin.enable_debug_mode()
        elif subcommand == "off":
            return plugin.disable_debug_mode()
        elif subcommand == "status":
            services = plugin.service_locator.get_service_names() if plugin.service_locator else []
            return f"Debug status:\n- Debug mode: {plugin.debug_mode_enabled}\n- Available services: {', '.join(services)}"
        else:
            return f"Unknown debug subcommand: {subcommand}"
    
    @command("time", ["clock"], "world", "Display the current time and date information.")
    def time_command_handler(args, context):
        time_plugin = plugin.get_service("plugin:time_plugin")
        if not time_plugin:
            return "Time plugin not found"
        hour = time_plugin.hour
        minute = time_plugin.minute
        day = time_plugin.day
        month = time_plugin.month
        year = time_plugin.year
        period = time_plugin.current_time_period
        day_idx = (day - 1) % len(time_plugin.config["day_names"])
        day_name = time_plugin.config["day_names"][day_idx]
        month_name = time_plugin.config["month_names"][month - 1]
        response = f"Current Time: {hour:02d}:{minute:02d} ({period.capitalize()})\n"
        response += f"Current Date: {day_name}, {day} {month_name}, Year {year}\n\n"
        response += "Time Periods:\n"
        response += f"- Dawn: {time_plugin.config['dawn_hour']:02d}:00\n"
        response += f"- Day: {time_plugin.config['day_hour']:02d}:00\n"
        response += f"- Dusk: {time_plugin.config['dusk_hour']:02d}:00\n"
        response += f"- Night: {time_plugin.config['night_hour']:02d}:00\n"
        if hasattr(time_plugin, "update_count"):
            response += f"\nTime updates: {time_plugin.update_count}"
        return response
    
    @command("settime", [], "debug", "Set game time.\n\nUsage: settime <hour> [minute] or settime <period> (dawn/day/dusk/night)")
    def settime_command_handler(args, context):
        time_plugin = plugin.get_service("plugin:time_plugin")
        if not time_plugin:
            return f"{FORMAT_ERROR}Time plugin not found{FORMAT_RESET}" # Use format codes
        if not args:
            return f"{FORMAT_ERROR}Usage: settime <hour> [minute] or settime <period> (dawn/day/dusk/night){FORMAT_RESET}"

        new_hour = -1
        new_minute = 0

        if args[0].lower() in plugin.config["available_time_periods"]:
            period = args[0].lower()
            period_hours = {
                "dawn": time_plugin.config.get("dawn_hour", 6), # Use .get()
                "day": time_plugin.config.get("day_hour", 8),
                "dusk": time_plugin.config.get("dusk_hour", 18),
                "night": time_plugin.config.get("night_hour", 20)
            }
            if period not in period_hours: # Should not happen with check above, but safety
                return f"{FORMAT_ERROR}Invalid period '{period}'.{FORMAT_RESET}"
            new_hour = period_hours[period]
            new_minute = 0
        else:
            try:
                new_hour = int(args[0])
                if not (0 <= new_hour <= 23):
                    return f"{FORMAT_ERROR}Hour must be between 0 and 23.{FORMAT_RESET}"
                if len(args) > 1:
                    new_minute = int(args[1])
                    if not (0 <= new_minute <= 59):
                        return f"{FORMAT_ERROR}Minute must be between 0 and 59.{FORMAT_RESET}"
            except ValueError:
                return f"{FORMAT_ERROR}Invalid time format. Use: settime <hour> [minute] or settime <period>{FORMAT_RESET}"

        if new_hour == -1: # If parsing failed somehow
            return f"{FORMAT_ERROR}Could not determine time to set.{FORMAT_RESET}"

        # --- Set Time Directly in Plugin ---
        # Calculate target game_time in seconds based on current day/month/year and new H:M
        days_per_month = time_plugin.config.get("days_per_month", 30)
        months_per_year = time_plugin.config.get("months_per_year", 12)
        days_per_month = max(1, days_per_month)
        months_per_year = max(1, months_per_year)

        minutes_since_midnight = new_hour * 60 + new_minute
        days_since_epoch = (time_plugin.year - 1) * months_per_year * days_per_month + \
                           (time_plugin.month - 1) * days_per_month + \
                           (time_plugin.day - 1)
        total_minutes_since_epoch = days_since_epoch * 24 * 60 + minutes_since_midnight

        time_plugin.game_time = float(total_minutes_since_epoch * 60) # Set game_time as float

        # Directly update hour/minute for immediate consistency before full recalc
        time_plugin.hour = new_hour
        time_plugin.minute = new_minute

        # --- Force Updates ---
        time_plugin._recalculate_date_from_game_time() # Ensure day/month/year consistent
        time_plugin._update_time_period()           # Update period based on new hour
        time_plugin._update_world_time_data()       # Publish the new state

        # --- Optional: Force UI Redraw ---
        # plugin.force_draw_game_ui() # Call the helper in DebugPlugin

        return f"{FORMAT_SUCCESS}Time set to {time_plugin.hour:02d}:{time_plugin.minute:02d} ({time_plugin.current_time_period}){FORMAT_RESET}"
    
    @command("setweather", ["weather"], "debug", "Set game weather.\n\nUsage: setweather <type> [intensity]")
    def setweather_command_handler(args, context):
        weather_plugin = plugin.get_service("plugin:weather_plugin")
        if not weather_plugin:
            return "Weather plugin not found"
        if not args:
            available = ", ".join(plugin.config["available_weather_types"])
            return f"Usage: setweather <type> [intensity]\nAvailable types: {available}\nIntensities: mild, moderate, strong, severe"
        weather_type = args[0].lower()
        if weather_type not in plugin.config["available_weather_types"]:
            available = ", ".join(plugin.config["available_weather_types"])
            return f"Invalid weather type. Available types: {available}"
        intensity = "moderate"
        if len(args) > 1 and args[1] in ["mild", "moderate", "strong", "severe"]:
            intensity = args[1]
        old_weather = weather_plugin.current_weather
        old_intensity = weather_plugin.current_intensity
        weather_plugin.current_weather = weather_type
        weather_plugin.current_intensity = intensity
        if weather_plugin.world:
            weather_plugin.world.set_plugin_data(weather_plugin.plugin_id, "current_weather", weather_type)
            weather_plugin.world.set_plugin_data(weather_plugin.plugin_id, "current_intensity", intensity)
        if weather_plugin.event_system:
            description = weather_plugin.config["weather_descriptions"].get(
                weather_type, 
                "The weather is changing."
            )
            weather_plugin.event_system.publish("weather_changed", {
                "weather": weather_type,
                "intensity": intensity,
                "description": description,
                "old_weather": old_weather,
                "old_intensity": old_intensity
            })
            if weather_plugin.data_provider and weather_plugin.data_provider.is_outdoors_or_has_windows():
                message = f"The weather changes to {weather_type} ({intensity})."
                weather_plugin.event_system.publish("display_message", message)
        plugin.force_draw_game_ui()
        return f"Weather set to {weather_type} ({intensity})"
    
    @command("teleport", ["tp"], "debug", "Teleport to any room.\n\nUsage: teleport <region_id> <room_id> or teleport <room_id> (same region)")
    def teleport_command_handler(args, context):
        if not plugin.world:
            return "World not available"
        if not args:
            return "Usage: teleport <region_id> <room_id> or teleport <room_id> (same region)"
        old_region_id = plugin.world.current_region_id
        old_room_id = plugin.world.current_room_id
        if len(args) == 1:
            room_id = args[0]
            region_id = plugin.world.current_region_id
        else:
            region_id = args[0]
            room_id = args[1]
        region = plugin.world.get_region(region_id)
        if not region:
            return f"Region '{region_id}' not found"
        room = region.get_room(room_id)
        if not room:
            return f"Room '{room_id}' not found in region '{region_id}'"
        plugin.world.current_region_id = region_id
        plugin.world.current_room_id = room_id
        if hasattr(plugin.world, "game") and hasattr(plugin.world.game, "plugin_manager"):
            plugin.world.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
            plugin.world.game.plugin_manager.on_room_enter(region_id, room_id)
        return f"Teleported to {region_id}:{room_id}\n\n{plugin.world.look()}"
    
    @command("spawn", ["create"], "debug", "Spawn an item or NPC.\n\nUsage:\n  spawn item <item_id> [quantity]\n  spawn npc <template_id> [level] [name...]")
    def spawn_command_handler(args, context):
        world = plugin.world
        player = world.player if world else None # Get player for context if needed

        if not world:
            return f"{FORMAT_ERROR}World not available{FORMAT_RESET}"
        if not args or args[0].lower() not in ["item", "npc"]:
            return f"{FORMAT_ERROR}Usage: spawn item <item_id> [qty] | spawn npc <template_id> [level] [name...]{FORMAT_RESET}"

        spawn_type = args[0].lower()

        # --- Item Spawning (Unchanged, but added quantity) ---
        if spawn_type == "item":
            if len(args) < 2:
                # List available item templates
                available_items = sorted(world.item_templates.keys()) if hasattr(world, 'item_templates') else ["None"]
                return f"{FORMAT_ERROR}Usage: spawn item <item_id> [quantity]\nAvailable IDs (partial): {', '.join(available_items[:20])}...{FORMAT_RESET}"
            item_id = args[1]
            quantity = 1
            if len(args) > 2:
                try:
                    quantity = int(args[2])
                    if quantity <= 0: return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
                except ValueError:
                    return f"{FORMAT_ERROR}Invalid quantity '{args[2]}'.{FORMAT_RESET}"

            try:
                spawned_count = 0
                item_name = ""
                for _ in range(quantity):
                    item = ItemFactory.create_item_from_template(item_id, world) # Use template creation
                    if item:
                        item_name = item.name # Store name from first successful creation
                        world.add_item_to_room(
                            world.current_region_id,
                            world.current_room_id,
                            item
                        )
                        spawned_count += 1
                    else:
                        return f"{FORMAT_ERROR}Failed to create item from template ID: {item_id}{FORMAT_RESET}"

                plural_s = "s" if spawned_count > 1 else ""
                return f"{FORMAT_SUCCESS}Spawned {spawned_count} {item_name}{plural_s} ({item_id}) in current room.{FORMAT_RESET}"

            except Exception as e:
                return f"{FORMAT_ERROR}Error spawning item: {e}{FORMAT_RESET}"

        # --- NPC Spawning (REVISED) ---
        elif spawn_type == "npc":
            if not hasattr(world, 'npc_templates'):
                return f"{FORMAT_ERROR}NPC templates not loaded in world.{FORMAT_RESET}"
            if len(args) < 2:
                # List available NPC templates
                available_npcs = sorted(world.npc_templates.keys()) if world.npc_templates else ["None"]
                return f"{FORMAT_ERROR}Usage: spawn npc <template_id> [level] [name...]\nAvailable IDs (partial): {', '.join(available_npcs[:20])}...{FORMAT_RESET}"

            template_id = args[1]

            # Validate template ID
            if template_id not in world.npc_templates:
                available_npcs = sorted(world.npc_templates.keys())
                return f"{FORMAT_ERROR}Unknown NPC template ID: '{template_id}'.\nAvailable: {', '.join(available_npcs)}{FORMAT_RESET}"

            # Parse optional level and name
            level_override = None
            name_override = None
            remaining_args = args[2:]

            if remaining_args:
                # Check if the first remaining arg is a number (level)
                if remaining_args[0].isdigit():
                    try:
                        level_override = int(remaining_args[0])
                        if level_override <= 0:
                             return f"{FORMAT_ERROR}Level override must be positive.{FORMAT_RESET}"
                        # The rest is the name
                        if len(remaining_args) > 1:
                            name_override = " ".join(remaining_args[1:])
                    except ValueError: # Should not happen due to isdigit, but safety
                         return f"{FORMAT_ERROR}Invalid level value '{remaining_args[0]}'.{FORMAT_RESET}"
                else:
                    # If not a number, the whole remaining part is the name
                    name_override = " ".join(remaining_args)

            try:
                # Prepare overrides for the factory
                overrides = {
                    "current_region_id": world.current_region_id,
                    "current_room_id": world.current_room_id,
                    "home_region_id": world.current_region_id, # Spawned NPCs consider current location home
                    "home_room_id": world.current_room_id
                }
                if level_override is not None:
                    overrides["level"] = level_override
                if name_override is not None:
                    overrides["name"] = name_override # Pass name override

                # Generate a unique instance ID for the spawned NPC
                instance_id = f"debug_spawn_{template_id}_{uuid.uuid4().hex[:6]}"

                # Use the correct factory method
                npc = NPCFactory.create_npc_from_template(template_id, world, instance_id, **overrides)

                if not npc:
                    # Factory method already prints errors, but add context
                    return f"{FORMAT_ERROR}Failed to create NPC instance from template '{template_id}'. Check logs.{FORMAT_RESET}"

                # Add the NPC to the world
                world.add_npc(npc)

                # Format the success message using the NPC's *actual* final name and level
                final_name = npc.name
                final_level = npc.level
                # Use the text formatter helper for consistent display
                formatted_name = format_target_name(player, npc) if player else final_name
                return f"{FORMAT_SUCCESS}Spawned {formatted_name} (Lvl {final_level}, ID: {instance_id}) in current room.{FORMAT_RESET}"

            except Exception as e:
                import traceback
                traceback.print_exc()
                return f"{FORMAT_ERROR}Error spawning NPC: {e}{FORMAT_RESET}"

        return f"{FORMAT_ERROR}Invalid spawn type '{spawn_type}'.{FORMAT_RESET}" # Should not be reached
    
    @command("heal", ["restore"], "debug", "Heal the player.\n\nUsage: heal [amount]")
    def heal_command_handler(args, context):
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        amount = 0
        if not args:
            old_health = plugin.world.player.health
            plugin.world.player.health = plugin.world.player.max_health
            amount = plugin.world.player.health - old_health
        else:
            try:
                amount = int(args[0])
                old_health = plugin.world.player.health
                plugin.world.player.health = min(plugin.world.player.health + amount, plugin.world.player.max_health)
                amount = plugin.world.player.health - old_health
            except ValueError:
                return "Invalid amount. Usage: heal [amount]"
        return f"Healed player for {amount} health. Current health: {plugin.world.player.health}/{plugin.world.player.max_health}"
    
    @command("damage", ["hurt"], "debug", "Damage the player.\n\nUsage: damage <amount>")
    def damage_command_handler(args, context):
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        if not args:
            return "Usage: damage <amount>"
        try:
            amount = int(args[0])
            if amount <= 0:
                return "Damage amount must be positive"
            old_health = plugin.world.player.health
            plugin.world.player.health = max(plugin.world.player.health - amount, 0)
            actual_damage = old_health - plugin.world.player.health
            status = f"Player took {int(actual_damage)} damage. Current health: {plugin.world.player.health}/{plugin.world.player.max_health}"
            if plugin.world.player.health <= 0:
                status += "\nPlayer would be dead in a real game."
            return status
        except ValueError:
            return "Invalid amount. Usage: damage <amount>"
    
    @command("level", ["levelup"], "debug", "Level up the player.\n\nUsage: level [count]")
    def level_command_handler(args, context):
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        levels = 1
        if args:
            try:
                levels = int(args[0])
                if levels <= 0:
                    return "Number of levels must be positive"
            except ValueError:
                return "Invalid number. Usage: level [count]"
        old_level = plugin.world.player.level
        old_max_health = plugin.world.player.max_health
        old_stats = plugin.world.player.stats.copy()
        for _ in range(levels):
            plugin.world.player.level_up()
        result = f"Leveled up player from {old_level} to {plugin.world.player.level}\n"
        result += f"Health increased: {old_max_health} -> {plugin.world.player.max_health}\n"
        result += "Stats increased:\n"
        for stat_name, old_value in old_stats.items():
            new_value = plugin.world.player.stats[stat_name]
            result += f"- {stat_name}: {old_value} -> {new_value}\n"
        return result
    
    @command("debuggive", [], "debug", "Give an item to the player.\n\nUsage: give <item_type> <n> [quantity]")
    def debuggive_command_handler(args, context):
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        if not args or len(args) < 2:
            return "Usage: give <item_type> <n> [quantity]"
        from items.item import ItemFactory
        item_type = args[0]
        name = args[1]
        quantity = 1
        if len(args) > 2:
            try:
                quantity = int(args[2])
                if quantity <= 0:
                    return "Quantity must be positive"
            except ValueError:
                return "Invalid quantity. Usage: give <item_type> <n> [quantity]"
        try:
            item = ItemFactory.create_item(item_type, name=name, description=f"A debug {item_type.lower()} item.")
            success, message = plugin.world.player.inventory.add_item(item, quantity)
            if success:
                return f"Added {quantity} {item.name} to player inventory"
            else:
                return f"Failed to add item: {message}"
        except Exception as e:
            return f"Error creating item: {str(e)}"
    
    @command("setstats", ["stats"], "debug", "Set player stats.\n\nUsage: setstats <stat_name> <value> [<stat_name> <value> ...]")
    def setstats_command_handler(args, context):
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        if not args or len(args) % 2 != 0:
            return "Usage: setstats <stat_name> <value> [<stat_name> <value> ...]"
        stats_updated = []
        for i in range(0, len(args), 2):
            stat_name = args[i].lower()
            try:
                value = int(args[i + 1])
                if value < 0:
                    return f"Stat value must be non-negative: {stat_name}"
                if stat_name in plugin.world.player.stats:
                    old_value = plugin.world.player.stats[stat_name]
                    plugin.world.player.stats[stat_name] = value
                    stats_updated.append(f"{stat_name}: {old_value} -> {value}")
                else:
                    return f"Unknown stat: {stat_name}"
            except ValueError:
                return f"Invalid value for {stat_name}. Must be a number."
        if stats_updated:
            return "Stats updated:\n" + "\n".join(stats_updated)
        else:
            return "No stats were updated"
    
    @command("listregions", ["regions"], "debug", "List all regions in the world.\n\nUsage: listregions")
    def listregions_command_handler(args, context):
        if not plugin.world:
            return "World not available"
        if not plugin.world.regions:
            return "No regions found in the world"
        result = "Regions in the world:\n"
        for region_id, region in plugin.world.regions.items():
            room_count = len(region.rooms)
            result += f"- {region_id}: {region.name} ({room_count} rooms)\n"
        return result
    
    @command("listrooms", ["rooms"], "debug", "List rooms in a region.\n\nUsage: listrooms [region_id]")
    def listrooms_command_handler(args, context):
        if not plugin.world:
            return "World not available"
        region_id = None
        if args:
            region_id = args[0]
        else:
            region_id = plugin.world.current_region_id
        region = plugin.world.get_region(region_id)
        if not region:
            return f"Region '{region_id}' not found"
        if not region.rooms:
            return f"No rooms found in region '{region_id}'"
        result = f"Rooms in region '{region_id}' ({region.name}):\n"
        for room_id, room in region.rooms.items():
            exits = ", ".join(room.exits.keys()) if room.exits else "none"
            current = " (current)" if plugin.world.current_region_id == region_id and plugin.world.current_room_id == room_id else ""
            result += f"- {room_id}: {room.name}{current} (Exits: {exits})\n"
        return result
    
    @command("listnpcs", ["npcs"], "debug", "List NPCs in the world.\n\nUsage: listnpcs [region_id [room_id]]")
    def listnpcs_command_handler(args, context):
        if not plugin.world:
            return "World not available"
        if not plugin.world.npcs:
            return "No NPCs found in the world"
        if args:
            if len(args) == 1:
                region_id = args[0]
                npcs = [npc for npc in plugin.world.npcs.values() if npc.current_region_id == region_id]
                if not npcs:
                    return f"No NPCs found in region '{region_id}'"
                result = f"NPCs in region '{region_id}':\n"
                for npc in npcs:
                    result += f"- {npc.obj_id}: {npc.name} (Room: {npc.current_room_id})\n"
                return result
            elif len(args) == 2:
                region_id, room_id = args
                npcs = plugin.world.get_npcs_in_room(region_id, room_id)
                if not npcs:
                    return f"No NPCs found in room '{room_id}' of region '{region_id}'"
                result = f"NPCs in room '{room_id}' of region '{region_id}':\n"
                for npc in npcs:
                    result += f"- {npc.obj_id}: {npc.name} (Health: {npc.health}/{npc.max_health})\n"
                return result
        result = "All NPCs in the world:\n"
        for obj_id, npc in plugin.world.npcs.items():
            result += f"- {obj_id}: {npc.name} (Location: {npc.current_region_id}:{npc.current_room_id})\n"
        return result
    
    @command("listitems", ["items"], "debug", "List items in a location.\n\nUsage: listitems [player|<region_id> <room_id>]")
    def listitems_command_handler(args, context):
        if not plugin.world:
            return "World not available"
        if not args:
            items = plugin.world.get_items_in_current_room()
            if not items:
                return "No items in current room"
            result = "Items in current room:\n"
            for item in items:
                result += f"- {item.obj_id}: {item.name}\n"
            return result
        if args[0] == "player":
            if not plugin.world.player.inventory:
                return "Player has no inventory"
            return plugin.world.player.inventory.list_items()
        if len(args) == 2:
            region_id, room_id = args
            items = plugin.world.get_items_in_room(region_id, room_id)
            if not items:
                return f"No items in room '{room_id}' of region '{region_id}'"
            result = f"Items in room '{room_id}' of region '{region_id}':\n"
            for item in items:
                result += f"- {item.obj_id}: {item.name}\n"
            return result
        return "Usage: listitems [player|<region_id> <room_id>]"
    
    @command("forcenpcupdate", ["forcenpcs"], "debug", "Force NPCs to update their positions based on the current time period.")
    def force_npc_update_command(args, context):
        npc_plugin = plugin.get_service("plugin:npc_schedule_plugin")
        if npc_plugin and hasattr(npc_plugin, "_update_npcs"):
            npc_plugin._update_npcs(force=True)
            in_tavern = 0
            in_social = 0
            wandering = 0
            for npc in plugin.world.npcs.values():
                location = f"{npc.current_region_id}:{npc.current_room_id}"
                if hasattr(npc_plugin, "taverns") and any(location == f"{t['region_id']}:{t['room_id']}" for t in npc_plugin.taverns):
                    in_tavern += 1
                elif hasattr(npc_plugin, "social_areas") and any(location == f"{s['region_id']}:{s['room_id']}" for s in npc_plugin.social_areas):
                    in_social += 1
                else:
                    wandering += 1
            return f"Forced NPC update. NPCs in taverns: {in_tavern}, in social areas: {in_social}, wandering: {wandering}"
        else:
            updates = 0
            for npc in plugin.world.npcs.values():
                npc.last_moved = 0
                updates += 1
            return f"Forced update for {updates} NPCs."

    @command("debuggear", ["dbggear"], "debug", "Toggle powerful debug gear.\n\nUsage: debuggear <on|off>")
    def debuggear_command_handler(args, context):
        world = plugin.world
        player = world.player if world else None

        if not player:
            return f"{FORMAT_ERROR}Player not found.{FORMAT_RESET}"
        if not args or args[0].lower() not in ["on", "off"]:
            return f"{FORMAT_ERROR}Usage: debuggear <on|off>{FORMAT_RESET}"

        action = args[0].lower()
        debug_sword_id = "debug_sword"
        debug_armor_id = "debug_armor"
        messages = []

        if action == "on":
            messages.append(f"{FORMAT_HIGHLIGHT}Equipping debug gear...{FORMAT_RESET}")

            # --- Equip Sword ---
            # Check if already has debug sword
            existing_sword = player.inventory.find_item_by_name(debug_sword_id) or \
                             player.equipment.get("main_hand") or \
                             player.equipment.get("off_hand")
            if existing_sword and existing_sword.obj_id == debug_sword_id:
                 messages.append(f"- Debug Sword already present.")
            else:
                 sword = ItemFactory.create_item_from_template(debug_sword_id, world)
                 if sword:
                      added, msg = player.inventory.add_item(sword)
                      if added:
                           equipped, msg_equip = player.equip_item(sword)
                           if equipped:
                                messages.append(f"- {FORMAT_SUCCESS}Debug Sword equipped.{FORMAT_RESET}")
                           else:
                                messages.append(f"- {FORMAT_ERROR}Added Debug Sword to inventory, but failed to equip: {msg_equip}{FORMAT_RESET}")
                      else:
                           messages.append(f"- {FORMAT_ERROR}Failed to add Debug Sword to inventory: {msg}{FORMAT_RESET}")
                 else:
                      messages.append(f"- {FORMAT_ERROR}Failed to create Debug Sword.{FORMAT_RESET}")

            # --- Equip Armor ---
             # Check if already has debug armor
            existing_armor = player.inventory.find_item_by_name(debug_armor_id) or \
                              player.equipment.get("body")
            if existing_armor and existing_armor.obj_id == debug_armor_id:
                  messages.append(f"- Debug Armor already present.")
            else:
                  armor = ItemFactory.create_item_from_template(debug_armor_id, world)
                  if armor:
                       added, msg = player.inventory.add_item(armor)
                       if added:
                            equipped, msg_equip = player.equip_item(armor) # Equip to default slot (body)
                            if equipped:
                                 messages.append(f"- {FORMAT_SUCCESS}Debug Armor equipped.{FORMAT_RESET}")
                            else:
                                 messages.append(f"- {FORMAT_ERROR}Added Debug Armor to inventory, but failed to equip: {msg_equip}{FORMAT_RESET}")
                       else:
                            messages.append(f"- {FORMAT_ERROR}Failed to add Debug Armor to inventory: {msg}{FORMAT_RESET}")
                  else:
                       messages.append(f"- {FORMAT_ERROR}Failed to create Debug Armor.{FORMAT_RESET}")

            return "\n".join(messages)

        elif action == "off":
            messages.append(f"{FORMAT_HIGHLIGHT}Removing debug gear...{FORMAT_RESET}")
            items_removed = False

            # --- Remove from Equipment ---
            for slot, item in list(player.equipment.items()): # Iterate over a copy
                if item and item.obj_id in [debug_sword_id, debug_armor_id]:
                    # Unequip WITHOUT adding back to inventory
                    player.equipment[slot] = None # Just remove reference directly
                    messages.append(f"- Unequipped and removed {item.name} from {slot}.")
                    items_removed = True
                    # We don't need player.unequip_item because we don't want it back in inventory

            # --- Remove from Inventory ---
            sword_in_inv = player.inventory.find_item_by_name(debug_sword_id)
            if sword_in_inv:
                 # Remove all instances
                 while sword_in_inv:
                      removed_item, count, msg = player.inventory.remove_item(debug_sword_id, 999) # Remove all
                      if removed_item:
                           messages.append(f"- Removed {count}x {removed_item.name} from inventory.")
                           items_removed = True
                      sword_in_inv = player.inventory.find_item_by_name(debug_sword_id) # Check again

            armor_in_inv = player.inventory.find_item_by_name(debug_armor_id)
            if armor_in_inv:
                 while armor_in_inv:
                      removed_item, count, msg = player.inventory.remove_item(debug_armor_id, 999) # Remove all
                      if removed_item:
                           messages.append(f"- Removed {count}x {removed_item.name} from inventory.")
                           items_removed = True
                      armor_in_inv = player.inventory.find_item_by_name(debug_armor_id) # Check again

            if not items_removed:
                messages.append("- No debug gear found to remove.")

            return "\n".join(messages)
    # --- END ADD THE NEW COMMAND ---
