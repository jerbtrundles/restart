"""
core/config.py
Configuration settings for the game with enhanced text system support.
"""

# Display settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FONT_SIZE = 18
LINE_SPACING = 5
INPUT_HEIGHT = 30

# Colors
TEXT_COLOR = (255, 255, 255)  # White
BG_COLOR = (0, 0, 0)  # Black
INPUT_BG_COLOR = (50, 50, 50)  # Dark gray

# Text formatting codes
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