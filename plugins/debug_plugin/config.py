"""
plugins/debug_plugin/config.py
Default configuration for the Debug plugin.
"""

DEFAULT_CONFIG = {
    # General debug settings
    "debug_message_prefix": "[DEBUG] ",
    
    # Time manipulation settings
    "available_time_periods": ["dawn", "day", "dusk", "night"],
    
    # Weather manipulation settings
    "available_weather_types": ["clear", "cloudy", "rain", "storm", "snow"],
    
    # Default values for teleport when no args provided
    "default_teleport_region": "test",
    "default_teleport_room": "entrance",
    
    # Maximum values for game mechanics
    "max_items_to_spawn": 10,
    "max_npcs_to_spawn": 5,
    
    # Available debug commands
    "debug_commands": [
        "settime", "setweather", "teleport", "spawn", 
        "heal", "damage", "level", "give", "setstats",
        "listregions", "listrooms", "listnpcs", "listitems"
    ]
}