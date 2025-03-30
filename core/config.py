"""
core/config.py
Configuration settings for the game.
"""

# Display settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FONT_SIZE = 18
LINE_SPACING = 5
INPUT_HEIGHT = 30

# Colors
TEXT_COLOR = (255, 255, 255)
BG_COLOR = (0, 0, 0)
INPUT_BG_COLOR = (50, 50, 50)

# Text formatting codes
# These will be replaced with appropriate color codes when rendering text
FORMAT_TITLE = "[[TITLE]]"       # Yellow, for headings
FORMAT_CATEGORY = "[[CAT]]"      # Cyan, for categories and labels
FORMAT_HIGHLIGHT = "[[HI]]"      # Green, for important information
FORMAT_SUCCESS = "[[OK]]"        # Green, for success messages
FORMAT_ERROR = "[[ERR]]"         # Red, for error messages
FORMAT_RESET = "[[/]]"           # Reset to default text color

# Color values for formatting codes
FORMAT_COLORS = {
    FORMAT_TITLE: (255, 255, 0),      # Yellow
    FORMAT_CATEGORY: (0, 255, 255),   # Cyan
    FORMAT_HIGHLIGHT: (0, 255, 0),    # Green
    FORMAT_SUCCESS: (0, 255, 0),      # Green
    FORMAT_ERROR: (255, 0, 0),        # Red
    FORMAT_RESET: TEXT_COLOR          # Default text color
}

# Scrolling
SCROLL_SPEED = 3  # Lines to scroll per mouse wheel movement

# Game settings
DEFAULT_WORLD_FILE = "world.json"