import os
import torch

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'data', 'characters.json')

# Screen
SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600
FPS = 30

# AOL / Win95 Palette
COLOR_BG = (192, 192, 192)
COLOR_WINDOW = (255, 255, 255)
COLOR_TEXT = (0, 0, 0)
COLOR_TITLE_BAR = (0, 0, 128)
COLOR_TITLE_TEXT = (255, 255, 255)
COLOR_BUTTON_LIGHT = (223, 223, 223)
COLOR_BUTTON_DARK = (128, 128, 128)
COLOR_ACCENT = (0, 128, 128)

# LLM Settings
# We use device_map="auto" to use GPU if available, otherwise CPU
LLM_MODEL_ID = "microsoft/Phi-4-mini-instruct"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
HISTORY_LIMIT = 5
MAX_NEW_TOKENS = 45 # Keep responses short for chat style