# config/config_game.py
"""
Configuration for core game systems, file paths, and debug settings.
"""
import os

# --- Directories and Files ---
DATA_DIR = "data"
SAVE_GAME_DIR = os.path.join(DATA_DIR, "saves")
REGION_DIR = os.path.join(DATA_DIR, "regions")
ITEM_TEMPLATE_DIR = os.path.join(DATA_DIR, "items")
NPC_TEMPLATE_DIR = os.path.join(DATA_DIR, "npcs")
DEFAULT_WORLD_FILE = "world.json"
DEFAULT_SAVE_FILE = "default_save.json"

# --- System Settings ---
SCROLL_SPEED = 3
MAX_SCROLL_HISTORY = 1000
COMMAND_HISTORY_SIZE = 50
MAX_BUFFER_LINES = 50

# --- Debug Settings ---
DEBUG_IGNORE_PLAYER_COMBAT = False
DEBUG_SHOW_LEVEL = True

# --- Core Time System Settings ---
TIME_REAL_SECONDS_PER_GAME_DAY = 1200  # 20 minutes
TIME_DAYS_PER_WEEK = 7
TIME_DAYS_PER_MONTH = 30
TIME_MONTHS_PER_YEAR = 12
TIME_DAY_NAMES = [
    "Moonday", "Tideday", "Windday", "Thunderday",
    "Fireday", "Starday", "Sunday"
]
TIME_MONTH_NAMES = [
    "Deepwinter", "Icemelt", "Springbloom", "Rainshower",
    "Meadowgrow", "Highsun", "Fireheat", "Goldenfield",
    "Harvestide", "Leaffall", "Frostwind", "Darknight"
]
TIME_DAWN_HOUR = 6
TIME_DAY_HOUR = 8
TIME_DUSK_HOUR = 18
TIME_NIGHT_HOUR = 20
TIME_UPDATE_THRESHOLD = 0.001
TIME_MAX_CATCHUP_SECONDS = 5.0

# --- Weather System Settings ---
WEATHER_PERSISTENCE_CHANCE = 0.3
WEATHER_TRANSITION_CHANGE_CHANCE = 0.5
WEATHER_INTENSITY_WEIGHTS = [0.4, 0.3, 0.2, 0.1] # mild, moderate, strong, severe