"""
plugins/npc_schedule_plugin/commands.py
Command module for the Improved NPC plugin.
"""
from plugins.plugin_system import register_plugin_command

def register_commands(plugin):
    """Register plugin commands."""
    
    def force_npc_update_command(args, context):
        """Force NPC update command handler."""
        # Force NPC update
        plugin._update_npcs(force=True)
        
        # Get counts
        in_tavern = 0
        in_social = 0
        wandering = 0
        
        for npc in plugin.world.npcs.values():
            location = f"{npc.current_region_id}:{npc.current_room_id}"
            if any(location == f"{t['region_id']}:{t['room_id']}" for t in plugin.taverns):
                in_tavern += 1
            elif any(location == f"{s['region_id']}:{s['room_id']}" for s in plugin.social_areas):
                in_social += 1
            else:
                wandering += 1
        
        return f"Forced NPC update. NPCs in taverns: {in_tavern}, in social areas: {in_social}, wandering: {wandering}"
    
    def list_locations_command(args, context):
        """List NPC gathering locations command."""
        response = "NPC Gathering Locations:\n\n"
        
        if plugin.taverns:
            response += "Taverns/Inns:\n"
            for t in plugin.taverns:
                response += f"- {t['name']} (in {t['region_id']})\n"
            response += "\n"
        else:
            response += "No taverns or inns found.\n\n"
            
        if plugin.social_areas:
            response += "Social Areas:\n"
            for s in plugin.social_areas:
                response += f"- {s['name']} (in {s['region_id']})\n"
        else:
            response += "No social areas found.\n"
            
        return response
    
    def npc_activity_command(args, context):
        """Check what NPCs are doing."""
        if not args:
            return "Please specify which NPC you want to check."
        
        npc_name = " ".join(args).lower()
        found_npc = None
        
        # First try to find NPC in current room
        for npc in plugin.world.get_current_room_npcs():
            if npc_name in npc.name.lower():
                found_npc = npc
                break
        
        # If not found in current room, search all NPCs
        if not found_npc:
            for npc in plugin.world.npcs.values():
                if npc_name in npc.name.lower():
                    found_npc = npc
                    break
        
        if not found_npc:
            return f"No NPC named '{npc_name}' found."
            
        # Build response with NPC details
        activity = found_npc.ai_state.get("current_activity", "unknown")
        location = f"{found_npc.current_region_id}:{found_npc.current_room_id}"
        
        # Get room name if possible
        room_name = location
        if (found_npc.current_region_id in plugin.world.regions and 
            found_npc.current_room_id in plugin.world.regions[found_npc.current_region_id].rooms):
            room = plugin.world.regions[found_npc.current_region_id].rooms[found_npc.current_room_id]
            room_name = room.name
        
        # Determine location type
        location_type = "somewhere"
        if any(location == f"{t['region_id']}:{t['room_id']}" for t in plugin.taverns):
            location_type = "at a tavern"
        elif any(location == f"{s['region_id']}:{s['room_id']}" for s in plugin.social_areas):
            location_type = "in a social area"
        
        response = f"{found_npc.name} is currently {activity} {location_type}.\n"
        response += f"Location: {room_name}\n"
        response += f"Behavior type: {found_npc.behavior_type}\n"
        
        # Add more details
        if hasattr(found_npc, "wander_chance"):
            response += f"Movement probability: {found_npc.wander_chance * 100:.1f}%\n"
        
        if hasattr(found_npc, "dialog") and found_npc.dialog:
            response += "\nThis NPC can talk about: "
            topics = list(found_npc.dialog.keys())[:5]  # Show up to 5 topics
            response += ", ".join(topics)
            if len(found_npc.dialog) > 5:
                response += f" and {len(found_npc.dialog) - 5} more topics"
        
        return response
    
    def set_period_command(args, context):
        """Set the current period for testing."""
        if not args:
            return "Usage: setperiod <day|night>"
        
        period = args[0].lower()
        if period not in ["day", "night"]:
            return "Period must be either 'day' or 'night'"
        
        # Set the period
        plugin.current_period = period
        
        # Force update
        plugin._update_npcs(force=True)
        
        return f"Period set to {period}. NPCs will behave accordingly."
    
    # Register the commands
    register_plugin_command(
        plugin.plugin_id,
        "forcenpcupdate",
        force_npc_update_command,
        aliases=["forcenpcs"],
        category="debug",
        help_text="Force NPCs to update their positions based on the current time period."
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listlocations",
        list_locations_command,
        aliases=["npclocs"],
        category="world",
        help_text="List all taverns and social areas where NPCs may gather."
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "npcactivity",
        npc_activity_command,
        aliases=["checkactivity"],
        category="world",
        help_text="Check what a specific NPC is currently doing.\n\nUsage: npcactivity <npc_name>"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "setperiod",
        set_period_command,
        aliases=[],
        category="debug",
        help_text="Set the current period (day/night) for testing NPC behavior.\n\nUsage: setperiod <day|night>"
    )