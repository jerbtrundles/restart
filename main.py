"""main.py"""
import argparse
import os
from core.game_manager import GameManager
from core.config import DATA_DIR, DEFAULT_WORLD_FILE, SAVE_GAME_DIR
from commands.commands import register_movement_commands

def main():
    parser = argparse.ArgumentParser(description='Pygame MUD Game')
    # Change argument to specify save file, not world definition
    parser.add_argument('--save', '-s', type=str, default="default_save.json",
                        help='Save game file to load/save (default: default_save.json)')
    # Remove --world argument
    # parser.add_argument('--world', '-w', type=str, default=DEFAULT_WORLD_FILE,...)
    args = parser.parse_args()

    # Ensure save directory exists
    if not os.path.exists(SAVE_GAME_DIR):
        os.makedirs(SAVE_GAME_DIR)
    # Ensure data directory exists (World loading checks subdirs)
    if not os.path.exists(DATA_DIR):
         os.makedirs(DATA_DIR)
         # Maybe create empty subdirs too?
         for sub in ["regions", "items", "npcs"]:
              os.makedirs(os.path.join(DATA_DIR, sub), exist_ok=True)
         print(f"Created data directory structure at '{DATA_DIR}'")


    register_movement_commands()
    game = GameManager(args.save) # Pass save file name
    game.run()

if __name__ == "__main__":
    main()
