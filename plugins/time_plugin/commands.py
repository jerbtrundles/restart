# plugins/time_plugin/commands.py
from commands.command_system import command
from plugins.plugin_system import register_plugin_command

def register_commands(plugin):
    """Register plugin commands."""
    
    def time_command_handler(args, context):
        """Time command handler."""
        time_str = f"{plugin.hour:02d}:{plugin.minute:02d}"
        day_name = plugin.config["day_names"][plugin.day % len(plugin.config["day_names"]) - 1]
        month_name = plugin.config["month_names"][plugin.month - 1]
        
        response = f"Current Time: {time_str}\n"
        response += f"Current Date: {day_name}, {plugin.day} {month_name}, Year {plugin.year}\n"
        response += f"Time Period: {plugin.current_time_period.capitalize()}\n"
        
        return response
    
    def calendar_command_handler(args, context):
        """Calendar command handler."""
        day_name = plugin.config["day_names"][plugin.day % len(plugin.config["day_names"]) - 1]
        month_name = plugin.config["month_names"][plugin.month - 1]
        
        response = f"Current Date: {day_name}, {plugin.day} {month_name}, Year {plugin.year}\n\n"
        response += f"Days in a week: {plugin.config['days_per_week']}\n"
        response += f"Days in a month: {plugin.config['days_per_month']}\n"
        response += f"Months in a year: {plugin.config['months_per_year']}\n\n"
        
        response += "Day names: " + ", ".join(plugin.config["day_names"]) + "\n\n"
        response += "Month names: " + ", ".join(plugin.config["month_names"]) + "\n"
        
        return response
    
    # Register the commands
    register_plugin_command(
        plugin.plugin_id,
        "time", 
        time_command_handler,
        aliases=["clock"], 
        category="system", 
        help_text="Display the current in-game time and date."
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "calendar", 
        calendar_command_handler,
        aliases=["cal", "date"], 
        category="system", 
        help_text="Display the current in-game calendar."
    )
