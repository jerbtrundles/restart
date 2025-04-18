"""main.py"""
import argparse
import os
from core.game_manager import GameManager
from core.config import DATA_DIR, DEFAULT_SAVE_FILE, SAVE_GAME_DIR
from commands.commands import register_movement_commands

def main():
    parser = argparse.ArgumentParser(description='Pygame MUD Game')
    # Change argument to specify save file, not world definition
    parser.add_argument('--save', '-s', type=str, default=DEFAULT_SAVE_FILE,
                        help='Save game file to load/save (default: default_save.json)')
    args = parser.parse_args()

    create_initial_directories()
    register_movement_commands()

    game = GameManager(args.save)
    game.run()

def create_initial_directories():
    if not os.path.exists(SAVE_GAME_DIR):
        os.makedirs(SAVE_GAME_DIR)
    if not os.path.exists(DATA_DIR):
         os.makedirs(DATA_DIR)
         for sub in ["regions", "items", "npcs"]:
              os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)
         print(f"Created data directory structure at '{DATA_DIR}'")

if __name__ == "__main__":
    main()
