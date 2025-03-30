"""
plugins/weather_plugin/commands.py
Command module for the Weather plugin.
"""
from plugins.plugin_system import register_plugin_command

def register_commands(plugin):
    """Register plugin commands."""
    
    def weather_command_handler(args, context):
        """Weather command handler."""
        # Get description from config
        description = plugin.config["weather_descriptions"].get(
            plugin.current_weather, 
            "The weather is unremarkable."
        )
        
        # Check if player is indoors
        is_outdoors = True
        if plugin.data_provider:
            is_outdoors = plugin.data_provider.is_outdoors_or_has_windows()
        
        if not is_outdoors:
            return f"You can't see the weather from inside, but you can hear sounds indicating {plugin.current_weather} conditions outside."
        
        # Return formatted response
        return f"Current Weather: {plugin.current_weather.capitalize()} ({plugin.current_intensity})\n\n{description}"
    
    # Register the commands
    register_plugin_command(
        plugin.plugin_id,
        "weather",
        weather_command_handler,
        aliases=["forecast"],
        category="world",
        help_text="Check the current weather conditions."
    )