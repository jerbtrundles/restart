# main.py
import argparse
import os
import sys

# Ensure the current directory is in sys.path so 'engine' is found
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from engine.config import DATA_DIR, DEFAULT_SAVE_FILE, SAVE_GAME_DIR
from engine.core.game_manager import GameManager
# This triggers the engine/commands/__init__.py logic
import engine.commands 

def main():
    print(f"Save Directory: {SAVE_GAME_DIR}")

    parser = argparse.ArgumentParser(description='Pygame MUD Game')
    parser.add_argument('--save', '-s', type=str, default=DEFAULT_SAVE_FILE,
                        help='Save game file to load/save (default: default_save.json)')
    args = parser.parse_args()

    create_initial_directories()
    
    # Initialize Game
    game = GameManager(args.save)
    game.run()
#2
def create_initial_directories():
    if not os.path.exists(SAVE_GAME_DIR):
        os.makedirs(SAVE_GAME_DIR)
    
    # Logic to ensure data folders exist
    if not os.path.exists(DATA_DIR):
         os.makedirs(DATA_DIR)
         for sub in ["regions", "items", "npcs", "magic", "crafting", "player", "quests", "knowledge"]:
              os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)
         print(f"Created data directory structure at '{DATA_DIR}'")

if __name__ == "__main__":
    main()