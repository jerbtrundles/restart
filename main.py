"""
main.py
Main entry point for the MUD game.
"""
import argparse
from core.game_manager import GameManager
from core.config import DEFAULT_WORLD_FILE


def main():
    """
    Main function to start the game.
    """
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Pygame MUD Game')
    parser.add_argument('--world', '-w', type=str, default=DEFAULT_WORLD_FILE,
                        help=f'Path to world JSON file (default: {DEFAULT_WORLD_FILE})')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create and run the game
    game = GameManager(args.world)
    game.run()


if __name__ == "__main__":
    main()