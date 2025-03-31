"""main.py"""
import argparse
from core.game_manager import GameManager
from core.config import DEFAULT_WORLD_FILE
from commands.commands import register_movement_commands

def main():
    parser = argparse.ArgumentParser(description='Pygame MUD Game')
    parser.add_argument('--world', '-w', type=str, default=DEFAULT_WORLD_FILE,
                        help=f'Path to world JSON file (default: {DEFAULT_WORLD_FILE})')
    args = parser.parse_args()
    register_movement_commands()
    game = GameManager(args.world)
    game.run()

if __name__ == "__main__":
    main()
