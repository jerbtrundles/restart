"""
plugins/time_plugin/config.py
Default configuration for the Time plugin.
"""

DEFAULT_CONFIG = {
    # Time settings (in real seconds)
    "real_seconds_per_game_day": 600,  # 10 minutes = 1 day
    "days_per_week": 7,
    "days_per_month": 30,
    "months_per_year": 12,
    "day_names": [
        "Moonday", "Tideday", "Windday", "Thunderday", 
        "Fireday", "Starday", "Sunday"
    ],
    "month_names": [
        "Deepwinter", "Icemelt", "Springbloom", "Rainshower",
        "Meadowgrow", "Highsun", "Fireheat", "Goldenfield",
        "Harvestide", "Leaffall", "Frostwind", "Darknight"
    ],
    "dawn_hour": 6,
    "day_hour": 8,
    "dusk_hour": 18,
    "night_hour": 20
}