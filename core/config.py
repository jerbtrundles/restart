"""
core/config.py
Configuration settings for the game with enhanced text system support.
"""

# Display settings
import os


SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FONT_SIZE = 18
LINE_SPACING = 5
INPUT_HEIGHT = 30

# Colors
TEXT_COLOR = (255, 255, 255)  # White
BG_COLOR = (0, 0, 0)  # Black
INPUT_BG_COLOR = (50, 50, 50)  # Dark gray

COLOR_RED = (255, 0, 0)
COLOR_ORANGE = (255, 165, 0)
COLOR_YELLOW = (255, 255, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_CYAN = (0, 255, 255)
COLOR_WHITE = (255, 255, 255)
COLOR_DEFAULT = COLOR_WHITE # Explicit default

FORMAT_RED = "[[RED]]"
FORMAT_ORANGE = "[[ORANGE]]"
FORMAT_YELLOW = "[[YELLOW]]"
FORMAT_GREEN = "[[GREEN]]"
FORMAT_BLUE = "[[BLUE]]"
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
    FORMAT_RED: COLOR_RED,
    FORMAT_ORANGE: COLOR_ORANGE,
    FORMAT_YELLOW: COLOR_YELLOW,
    FORMAT_GREEN: COLOR_GREEN,
    FORMAT_BLUE: COLOR_CYAN,
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
