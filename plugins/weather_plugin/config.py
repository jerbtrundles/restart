"""
plugins/weather_plugin/config.py
Default configuration for the Weather plugin.
"""

DEFAULT_CONFIG = {
    # Weather change settings
    "hourly_change_chance": 0.2,  # 20% chance per hour
    
    # Weather type probabilities by season
    "weather_chances": {
        "spring": {"clear": 0.4, "cloudy": 0.3, "rain": 0.3, "storm": 0.1},
        "summer": {"clear": 0.6, "cloudy": 0.2, "rain": 0.1, "storm": 0.1},
        "fall": {"clear": 0.3, "cloudy": 0.4, "rain": 0.2, "storm": 0.1},
        "winter": {"clear": 0.5, "cloudy": 0.3, "snow": 0.2}
    },
    
    # Weather descriptions
    "weather_descriptions": {
        "clear": "The sky is clear and blue.",
        "cloudy": "Clouds fill the sky.",
        "rain": "Rain falls steadily.",
        "storm": "Thunder rumbles as a storm rages.",
        "snow": "Snowflakes drift down from the sky."
    },
    
    # Weather intensity descriptions
    "intensity_descriptions": {
        "mild": "mild",
        "moderate": "moderate",
        "strong": "strong",
        "severe": "severe"
    }
}