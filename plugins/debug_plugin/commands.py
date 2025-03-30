"""
plugins/debug_plugin/commands.py
Command module for the Debug plugin.
"""
from plugins.plugin_system import register_plugin_command
import random

def register_commands(plugin):
    """Register debug plugin commands."""
    
    def debug_command_handler(args, context):
        """Debug command handler."""
        if not args:
            return "Debug plugin commands:\n" + "\n".join([
                f"- {cmd}" for cmd in plugin.config["debug_commands"]
            ])
        
        subcommand = args[0].lower()
        subargs = args[1:]
        
        # Handle subcommands
        if subcommand == "on":
            return plugin.enable_debug_mode()
        elif subcommand == "off":
            return plugin.disable_debug_mode()
        elif subcommand == "status":
            services = plugin.service_locator.get_service_names() if plugin.service_locator else []
            return f"Debug status:\n- Debug mode: {plugin.debug_mode_enabled}\n- Available services: {', '.join(services)}"
        else:
            return f"Unknown debug subcommand: {subcommand}"
    
    def settime_command_handler(args, context):
        """Set time command handler."""
        # Get time plugin
        time_plugin = plugin.get_service("plugin:time_plugin")
        if not time_plugin:
            return "Time plugin not found"
        
        if not args:
            return "Usage: settime <hour> [minute] or settime <period> (dawn/day/dusk/night)"
        
        # Check if setting time period
        if args[0].lower() in plugin.config["available_time_periods"]:
            period = args[0].lower()
            
            # Map periods to hours
            period_hours = {
                "dawn": time_plugin.config["dawn_hour"],
                "day": time_plugin.config["day_hour"],
                "dusk": time_plugin.config["dusk_hour"],
                "night": time_plugin.config["night_hour"]
            }
            
            # Update the time by directly modifying the game_time
            # Calculate minutes since start of day
            minutes_since_day_start = period_hours[period] * 60
            
            # Calculate current day in minutes
            current_day_minutes = (time_plugin.day - 1) * 24 * 60
            current_month_minutes = (time_plugin.month - 1) * time_plugin.config["days_per_month"] * 24 * 60
            current_year_minutes = (time_plugin.year - 1) * time_plugin.config["months_per_year"] * time_plugin.config["days_per_month"] * 24 * 60
            
            # Set game_time to keep the current date but change the time
            time_plugin.game_time = (current_year_minutes + current_month_minutes + current_day_minutes + minutes_since_day_start) * 60
            
            # Update hour and minute
            time_plugin.hour = period_hours[period]
            time_plugin.minute = 0
            
            # Update time period and all data
            time_plugin._update_time_period()
            time_plugin._update_world_time_data()
            
            # Force an update
            time_plugin._on_tick("force_update", None)
            
            return f"Time set to {period} ({time_plugin.hour:02d}:00)"
        
        # Otherwise, set specific hour/minute
        try:
            hour = int(args[0])
            if hour < 0 or hour > 23:
                return "Hour must be between 0 and 23"
            
            minute = 0
            if len(args) > 1:
                minute = int(args[1])
                if minute < 0 or minute > 59:
                    return "Minute must be between 0 and 59"
            
            # Same process but with specified hours and minutes
            # Calculate minutes since start of day
            minutes_since_day_start = hour * 60 + minute
            
            # Calculate current day in minutes
            current_day_minutes = (time_plugin.day - 1) * 24 * 60
            current_month_minutes = (time_plugin.month - 1) * time_plugin.config["days_per_month"] * 24 * 60
            current_year_minutes = (time_plugin.year - 1) * time_plugin.config["months_per_year"] * time_plugin.config["days_per_month"] * 24 * 60
            
            # Set game_time to keep the current date but change the time
            time_plugin.game_time = (current_year_minutes + current_month_minutes + current_day_minutes + minutes_since_day_start) * 60
            
            # Update hour and minute directly
            time_plugin.hour = hour
            time_plugin.minute = minute
            
            # Update time period
            old_period = time_plugin.current_time_period
            time_plugin._update_time_period()
            time_plugin._update_world_time_data()
            
            # Force an update
            time_plugin._on_tick("force_update", None)
            
            return f"Time set to {hour:02d}:{minute:02d} ({time_plugin.current_time_period})"
        except ValueError:
            return "Invalid time format. Use: settime <hour> [minute] or settime <period>"
    
    def setweather_command_handler(args, context):
        """Set weather command handler."""
        # Get weather plugin
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
        
        # Update the weather
        old_weather = weather_plugin.current_weather
        old_intensity = weather_plugin.current_intensity
        
        weather_plugin.current_weather = weather_type
        weather_plugin.current_intensity = intensity
        
        # Make sure to update world state
        if weather_plugin.world:
            weather_plugin.world.set_plugin_data(weather_plugin.plugin_id, "current_weather", weather_type)
            weather_plugin.world.set_plugin_data(weather_plugin.plugin_id, "current_intensity", intensity)
        
        # Ensure notification event is triggered to update UI
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
            
            # Also send display message if player is outdoors
            if weather_plugin.data_provider and weather_plugin.data_provider.is_outdoors_or_has_windows():
                message = f"The weather changes to {weather_type} ({intensity})."
                weather_plugin.event_system.publish("display_message", message)
        
        # Force a UI redraw to ensure changes are shown immediately
        plugin.force_draw_game_ui()
        
        return f"Weather set to {weather_type} ({intensity})"
    
    def teleport_command_handler(args, context):
        """Teleport command handler."""
        if not plugin.world:
            return "World not available"
        
        if not args:
            return "Usage: teleport <region_id> <room_id> or teleport <room_id> (same region)"
        
        # Store old location
        old_region_id = plugin.world.current_region_id
        old_room_id = plugin.world.current_room_id
        
        # If only one arg, assume it's a room in the current region
        if len(args) == 1:
            room_id = args[0]
            region_id = plugin.world.current_region_id
        else:
            region_id = args[0]
            room_id = args[1]
        
        # Validate region
        region = plugin.world.get_region(region_id)
        if not region:
            return f"Region '{region_id}' not found"
        
        # Validate room
        room = region.get_room(room_id)
        if not room:
            return f"Room '{room_id}' not found in region '{region_id}'"
        
        # Perform teleport
        plugin.world.current_region_id = region_id
        plugin.world.current_room_id = room_id
        
        # Notify plugins about room change if game manager is available
        if hasattr(plugin.world, "game") and hasattr(plugin.world.game, "plugin_manager"):
            # Notify about room exit
            plugin.world.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
            
            # Notify about room enter
            plugin.world.game.plugin_manager.on_room_enter(region_id, room_id)
        
        # Get room description
        return f"Teleported to {region_id}:{room_id}\n\n{plugin.world.look()}"
    
    def spawn_command_handler(args, context):
        """Spawn item or NPC command handler."""
        if not plugin.world:
            return "World not available"
        
        if not args or args[0] not in ["item", "npc"]:
            return "Usage: spawn item <item_type> [<name>] or spawn npc <template_name> [<name>]"
        
        spawn_type = args[0]
        
        if spawn_type == "item" and len(args) > 1:
            from items.item import ItemFactory
            
            item_type = args[1]
            name = " ".join(args[2:]) if len(args) > 2 else f"Debug {item_type}"
            
            try:
                # Create the item
                item = ItemFactory.create_item(item_type, name=name, description=f"A debug {item_type.lower()} item.")
                
                # Add to current room
                plugin.world.add_item_to_room(
                    plugin.world.current_region_id,
                    plugin.world.current_room_id,
                    item
                )
                
                return f"Spawned {item.name} ({item_type}) in current room"
            except Exception as e:
                return f"Error spawning item: {str(e)}"
        
        elif spawn_type == "npc" and len(args) > 1:
            from npcs.npc_factory import NPCFactory
            
            template_name = args[1]
            name = " ".join(args[2:]) if len(args) > 2 else None
            
            try:
                # Create the NPC
                npc_args = {"name": name} if name else {}
                npc = NPCFactory.create_npc(template_name, **npc_args)
                
                if not npc:
                    return f"Unknown NPC template: {template_name}"
                
                # Set NPC location to current room
                npc.current_region_id = plugin.world.current_region_id
                npc.current_room_id = plugin.world.current_room_id
                
                # Add to world
                plugin.world.add_npc(npc)
                
                return f"Spawned {npc.name} ({template_name}) in current room"
            except Exception as e:
                return f"Error spawning NPC: {str(e)}"
        
        return "Invalid spawn command"
    
    def heal_command_handler(args, context):
        """Heal player command handler."""
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        
        amount = 0
        if not args:
            # Full heal
            old_health = plugin.world.player.health
            plugin.world.player.health = plugin.world.player.max_health
            amount = plugin.world.player.health - old_health
        else:
            try:
                # Heal specific amount
                amount = int(args[0])
                old_health = plugin.world.player.health
                plugin.world.player.health = min(plugin.world.player.health + amount, plugin.world.player.max_health)
                amount = plugin.world.player.health - old_health
            except ValueError:
                return "Invalid amount. Usage: heal [amount]"
        
        return f"Healed player for {amount} health. Current health: {plugin.world.player.health}/{plugin.world.player.max_health}"
    
    def damage_command_handler(args, context):
        """Damage player command handler."""
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
            
            status = f"Player took {actual_damage} damage. Current health: {plugin.world.player.health}/{plugin.world.player.max_health}"
            
            if plugin.world.player.health <= 0:
                status += "\nPlayer would be dead in a real game."
            
            return status
        except ValueError:
            return "Invalid amount. Usage: damage <amount>"
    
    def level_command_handler(args, context):
        """Level up player command handler."""
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
        
        # Store initial stats
        old_level = plugin.world.player.level
        old_max_health = plugin.world.player.max_health
        old_stats = plugin.world.player.stats.copy()
        
        # Level up the specified number of times
        for _ in range(levels):
            plugin.world.player.level_up()
        
        # Format the result
        result = f"Leveled up player from {old_level} to {plugin.world.player.level}\n"
        result += f"Health increased: {old_max_health} -> {plugin.world.player.max_health}\n"
        result += "Stats increased:\n"
        for stat_name, old_value in old_stats.items():
            new_value = plugin.world.player.stats[stat_name]
            result += f"- {stat_name}: {old_value} -> {new_value}\n"
        
        return result
    
    def give_command_handler(args, context):
        """Give item to player command handler."""
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        
        if not args or len(args) < 2:
            return "Usage: give <item_type> <name> [quantity]"
        
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
                return "Invalid quantity. Usage: give <item_type> <name> [quantity]"
        
        try:
            # Create the item
            item = ItemFactory.create_item(item_type, name=name, description=f"A debug {item_type.lower()} item.")
            
            # Add to player inventory
            success, message = plugin.world.player.inventory.add_item(item, quantity)
            
            if success:
                return f"Added {quantity} {item.name} to player inventory"
            else:
                return f"Failed to add item: {message}"
        except Exception as e:
            return f"Error creating item: {str(e)}"
    
    def setstats_command_handler(args, context):
        """Set player stats command handler."""
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        
        if not args or len(args) % 2 != 0:
            return "Usage: setstats <stat_name> <value> [<stat_name> <value> ...]"
        
        # Parse stat pairs
        stats_updated = []
        for i in range(0, len(args), 2):
            stat_name = args[i].lower()
            try:
                value = int(args[i + 1])
                if value < 0:
                    return f"Stat value must be non-negative: {stat_name}"
                
                # Update stat if it exists
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
    
    def listregions_command_handler(args, context):
        """List regions command handler."""
        if not plugin.world:
            return "World not available"
        
        if not plugin.world.regions:
            return "No regions found in the world"
        
        result = "Regions in the world:\n"
        for region_id, region in plugin.world.regions.items():
            room_count = len(region.rooms)
            result += f"- {region_id}: {region.name} ({room_count} rooms)\n"
        
        return result
    
    def listrooms_command_handler(args, context):
        """List rooms command handler."""
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
    
    def listnpcs_command_handler(args, context):
        """List NPCs command handler."""
        if not plugin.world:
            return "World not available"
        
        if not plugin.world.npcs:
            return "No NPCs found in the world"
        
        # Filter by region/room if args provided
        if args:
            if len(args) == 1:
                # Filter by region
                region_id = args[0]
                npcs = [npc for npc in plugin.world.npcs.values() if npc.current_region_id == region_id]
                
                if not npcs:
                    return f"No NPCs found in region '{region_id}'"
                
                result = f"NPCs in region '{region_id}':\n"
                for npc in npcs:
                    result += f"- {npc.npc_id}: {npc.name} (Room: {npc.current_room_id})\n"
                
                return result
            elif len(args) == 2:
                # Filter by region and room
                region_id, room_id = args
                npcs = plugin.world.get_npcs_in_room(region_id, room_id)
                
                if not npcs:
                    return f"No NPCs found in room '{room_id}' of region '{region_id}'"
                
                result = f"NPCs in room '{room_id}' of region '{region_id}':\n"
                for npc in npcs:
                    result += f"- {npc.npc_id}: {npc.name} (Health: {npc.health}/{npc.max_health})\n"
                
                return result
        
        # List all NPCs
        result = "All NPCs in the world:\n"
        for npc_id, npc in plugin.world.npcs.items():
            result += f"- {npc_id}: {npc.name} (Location: {npc.current_region_id}:{npc.current_room_id})\n"
        
        return result
    
    def listitems_command_handler(args, context):
        """List items command handler."""
        if not plugin.world:
            return "World not available"
        
        # If no args, show items in current room
        if not args:
            items = plugin.world.get_items_in_current_room()
            
            if not items:
                return "No items in current room"
            
            result = "Items in current room:\n"
            for item in items:
                result += f"- {item.item_id}: {item.name}\n"
            
            return result
        
        # If 'player' arg, show player inventory
        if args[0] == "player":
            if not plugin.world.player.inventory:
                return "Player has no inventory"
            
            return plugin.world.player.inventory.list_items()
        
        # If region/room args, show items in that room
        if len(args) == 2:
            region_id, room_id = args
            items = plugin.world.get_items_in_room(region_id, room_id)
            
            if not items:
                return f"No items in room '{room_id}' of region '{region_id}'"
            
            result = f"Items in room '{room_id}' of region '{region_id}':\n"
            for item in items:
                result += f"- {item.item_id}: {item.name}\n"
            
            return result
        
        return "Usage: listitems [player|<region_id> <room_id>]"
    
    def time_command_handler(args, context):
        """Time command handler to display current time."""
        # Get time plugin
        time_plugin = plugin.get_service("plugin:time_plugin")
        if not time_plugin:
            return "Time plugin not found"
        
        # Format time information
        hour = time_plugin.hour
        minute = time_plugin.minute
        day = time_plugin.day
        month = time_plugin.month
        year = time_plugin.year
        period = time_plugin.current_time_period
        
        # Get day and month names
        day_idx = (day - 1) % len(time_plugin.config["day_names"])
        day_name = time_plugin.config["day_names"][day_idx]
        month_name = time_plugin.config["month_names"][month - 1]
        
        # Build response
        response = f"Current Time: {hour:02d}:{minute:02d} ({period.capitalize()})\n"
        response += f"Current Date: {day_name}, {day} {month_name}, Year {year}\n\n"
        
        # Add time periods info
        response += "Time Periods:\n"
        response += f"- Dawn: {time_plugin.config['dawn_hour']:02d}:00\n"
        response += f"- Day: {time_plugin.config['day_hour']:02d}:00\n"
        response += f"- Dusk: {time_plugin.config['dusk_hour']:02d}:00\n"
        response += f"- Night: {time_plugin.config['night_hour']:02d}:00\n"
        
        # Add update count for debugging
        if hasattr(time_plugin, "update_count"):
            response += f"\nTime updates: {time_plugin.update_count}"
        
        return response
        
    # Register the debug commands
    register_plugin_command(
        plugin.plugin_id,
        "debug",
        debug_command_handler,
        aliases=["dbg"],
        category="system",
        help_text="Control debug mode and list available debug commands.\n\nUsage: debug [on|off|status]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "time",
        time_command_handler,
        aliases=["clock"],
        category="world",
        help_text="Display the current time and date information."
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "settime",
        settime_command_handler,
        aliases=[],
        category="debug",
        help_text="Set game time.\n\nUsage: settime <hour> [minute] or settime <period> (dawn/day/dusk/night)"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "setweather",
        setweather_command_handler,
        aliases=["weather"],
        category="debug",
        help_text="Set game weather.\n\nUsage: setweather <type> [intensity]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "teleport",
        teleport_command_handler,
        aliases=["tp"],
        category="debug",
        help_text="Teleport to any room.\n\nUsage: teleport <region_id> <room_id> or teleport <room_id> (same region)"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "spawn",
        spawn_command_handler,
        aliases=["create"],
        category="debug",
        help_text="Spawn an item or NPC.\n\nUsage: spawn item <item_type> [<name>] or spawn npc <template_name> [<name>]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "heal",
        heal_command_handler,
        aliases=["restore"],
        category="debug",
        help_text="Heal the player.\n\nUsage: heal [amount]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "damage",
        damage_command_handler,
        aliases=["hurt"],
        category="debug",
        help_text="Damage the player.\n\nUsage: damage <amount>"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "level",
        level_command_handler,
        aliases=["levelup"],
        category="debug",
        help_text="Level up the player.\n\nUsage: level [count]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "give",
        give_command_handler,
        aliases=["giveitem"],
        category="debug",
        help_text="Give an item to the player.\n\nUsage: give <item_type> <name> [quantity]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "setstats",
        setstats_command_handler,
        aliases=["stats"],
        category="debug",
        help_text="Set player stats.\n\nUsage: setstats <stat_name> <value> [<stat_name> <value> ...]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listregions",
        listregions_command_handler,
        aliases=["regions"],
        category="debug",
        help_text="List all regions in the world.\n\nUsage: listregions"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listrooms",
        listrooms_command_handler,
        aliases=["rooms"],
        category="debug",
        help_text="List rooms in a region.\n\nUsage: listrooms [region_id]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listnpcs",
        listnpcs_command_handler,
        aliases=["npcs"],
        category="debug",
        help_text="List NPCs in the world.\n\nUsage: listnpcs [region_id [room_id]]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listitems",
        listitems_command_handler,
        aliases=["items"],
        category="debug",
        help_text="List items in a location.\n\nUsage: listitems [player|<region_id> <room_id>]"
    )