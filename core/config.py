"""
core/config.py
Configuration settings for the game with enhanced text system support.
"""

# Display settings
import os


SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 720
FONT_SIZE = 18
LINE_SPACING = 5
INPUT_HEIGHT = 30

# Colors
TEXT_COLOR = (255, 255, 255)  # White
BG_COLOR = (0, 0, 0)  # Black
INPUT_BG_COLOR = (50, 50, 50)  # Dark gray

COLOR_PURPLE = (255, 0, 255)
COLOR_RED = (255, 0, 0)
COLOR_ORANGE = (255, 165, 0)
COLOR_YELLOW = (255, 255, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_CYAN = (0, 255, 255)
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (128, 128, 128)
COLOR_DEFAULT = COLOR_WHITE # Explicit default

FORMAT_PURPLE = "[[PURPLE]]"
FORMAT_RED = "[[RED]]"
FORMAT_ORANGE = "[[ORANGE]]"
FORMAT_YELLOW = "[[YELLOW]]"
FORMAT_GREEN = "[[GREEN]]"
FORMAT_BLUE = "[[BLUE]]"
FORMAT_GRAY = "[[GRAY]]"
FORMAT_CYAN = "[[CYAN]]"
FORMAT_WHITE = "[[WHITE]]"
# Keep FORMAT_RESET for resetting to default, makes semantic sense
FORMAT_RESET = "[[/]]"

FORMAT_ERROR = FORMAT_RED
FORMAT_TITLE = FORMAT_YELLOW
FORMAT_HIGHLIGHT = FORMAT_GREEN
FORMAT_SUCCESS = FORMAT_GREEN
FORMAT_CATEGORY = FORMAT_CYAN

# Default color values for format codes (RGB)
DEFAULT_COLORS = {
    FORMAT_RESET: (255, 255, 255),     # White (default)
    FORMAT_PURPLE: COLOR_PURPLE,
    FORMAT_RED: COLOR_RED,
    FORMAT_ORANGE: COLOR_ORANGE,
    FORMAT_YELLOW: COLOR_YELLOW,
    FORMAT_GREEN: COLOR_GREEN,
    FORMAT_BLUE: COLOR_CYAN,
    FORMAT_GRAY: COLOR_GRAY,
    FORMAT_CYAN: COLOR_CYAN,
    FORMAT_WHITE: COLOR_WHITE,
    FORMAT_RESET: COLOR_DEFAULT, # Reset goes to the default color
}

SEMANTIC_FORMAT = {
    "TITLE": FORMAT_ORANGE,     # Titles will be Orange
    "CATEGORY": FORMAT_BLUE,      # Category labels will be Blue
    "HIGHLIGHT": FORMAT_CYAN,     # Highlights will be Cyan
    "SUCCESS": FORMAT_GREEN,      # Success messages will be Green
    "ERROR": FORMAT_RED,        # Error messages will be Red
    "NEUTRAL": FORMAT_YELLOW,     # Neutral/near-level mobs will be Yellow
    "DEFAULT": FORMAT_RESET       # Default text reset
}

# Scrolling settings
SCROLL_SPEED = 3  # Lines to scroll per mouse wheel movement
MAX_SCROLL_HISTORY = 1000  # Maximum number of lines to keep in scroll history

# Game settings
DEFAULT_WORLD_FILE = "world.json"

# Text display settings
MAX_PARAGRAPH_WIDTH = 80  # Maximum width for wrapped text
TEXT_MARGIN = 10  # Margin from edge of screen
PARAGRAPH_SPACING = 10  # Space between paragraphs

# History settings
COMMAND_HISTORY_SIZE = 50  # Number of commands to keep in history

# Debug settings
DEBUG_COLOR = (255, 0, 0)  # Red for debug text

DEFAULT_SAVE_FILE = "default_save.json"
DATA_DIR = "data"
SAVE_GAME_DIR = os.path.join(DATA_DIR, "saves")
REGION_DIR = os.path.join(DATA_DIR, "regions")
ITEM_TEMPLATE_DIR = os.path.join(DATA_DIR, "items")
NPC_TEMPLATE_DIR = os.path.join(DATA_DIR, "npcs")

# --- Player Health Calculation ---
PLAYER_BASE_HEALTH = 80
PLAYER_CON_HEALTH_MULTIPLIER = 2.0 # HP gained per point of CON at level 1
PLAYER_LEVEL_HEALTH_BASE_INCREASE = 5 # Base HP gain per level (before CON)
PLAYER_LEVEL_CON_HEALTH_MULTIPLIER = 0.5 # Extra HP gain per level per point of CON

# --- NPC Health Calculation ---
NPC_BASE_HEALTH = 30 # Lower base for NPCs?
NPC_CON_HEALTH_MULTIPLIER = 1.5
NPC_LEVEL_HEALTH_BASE_INCREASE = 3
NPC_LEVEL_CON_HEALTH_MULTIPLIER = 0.3

# Multipliers applied based on Attacker's level relative to Target's level
# Example: If Player attacks a RED target, player's hit chance is multiplied by 0.85, damage by 0.75.
# Example: If Player defeats a GREEN target, XP gained is multiplied by 0.5.
LEVEL_DIFF_COMBAT_MODIFIERS = {
    # Tier:   (Hit Chance Multiplier, Damage Dealt Multiplier, XP Multiplier)
    "purple": (0.70, 0.60, 2.50), # Hardest to hit, deal much less dmg, gain most XP
    "red":    (0.85, 0.75, 1.75),
    "orange": (0.95, 0.90, 1.25),
    "yellow": (1.00, 1.00, 1.00), # Baseline
    "blue":   (1.05, 1.10, 0.80),
    "green":  (1.15, 1.25, 0.50),
    "gray":   (1.25, 1.40, 0.20), # Easiest to hit, deal much more dmg, gain least XP
}

# Define Min/Max values for clamping
MIN_HIT_CHANCE = 0.05 # 5% minimum chance to hit
MAX_HIT_CHANCE = 0.95 # 95% maximum chance to hit
MIN_XP_GAIN = 1       # Always gain at least 1 XP
MIN_ATTACK_COOLDOWN = 0.5 # Prevent excessively fast attacks

MAX_BUFFER_LINES = 50 # keep this much history

# --- Trading Settings ---
DEFAULT_VENDOR_SELL_MULTIPLIER = 2.0  # Player Buys: Item Value * 2.0 (default)
DEFAULT_VENDOR_BUY_MULTIPLIER = 0.4   # Player Sells: Item Value * 0.4 (default)
VENDOR_CAN_BUY_JUNK = True
VENDOR_CAN_BUY_ALL_ITEMS = False # Should vendors only buy certain types?

REPAIR_COST_PER_VALUE_POINT = 0.1 # e.g., 10% of item value to repair fully
REPAIR_MINIMUM_COST = 1
