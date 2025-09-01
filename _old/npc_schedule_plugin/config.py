"""
plugins/npc_schedule_plugin/config.py
Default configuration for the Improved NPC plugin.
"""

DEFAULT_CONFIG = {
    # Day/night settings
    "day_start_hour": 6,    # 6 AM
    "night_start_hour": 20,  # 8 PM
    
    # Movement probabilities
    "day_wander_chance": 0.3,   # 30% chance to move each update during day
    "night_wander_chance": 0.1,  # 10% chance during night
    
    # Activity descriptions
    "day_activities": [
        "wandering", "exploring", "looking around", "browsing", "working",
        "shopping", "searching", "inspecting", "studying", "observing"
    ],
    "night_activities": [
        "relaxing", "chatting", "drinking", "resting", "socializing",
        "dining", "telling stories", "listening to music", "playing games", "sleeping"
    ],
    
    # Update interval (in seconds)
    "update_interval": 30,
    
    # Room type identification keywords
    "tavern_keywords": ["tavern", "inn", "pub", "bar", "drink", "beer", "ale"],
    "social_keywords": ["hall", "square", "garden", "plaza", "center", "meeting", "gather"],
    
    # Debug mode
    "debug": False
}