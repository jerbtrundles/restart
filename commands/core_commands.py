"""
commands/core_commands.py
Core commands for the MUD game using the unified command system.
This combines commands from system, inventory, and help modules.
"""
from typing import List, Dict, Any
from commands.command_system import command
from core.config import FORMAT_TITLE, FORMAT_HIGHLIGHT, FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, DEFAULT_WORLD_FILE

# System commands
@command("help", aliases=["h", "?"], category="system", 
         help_text="Display help information about available commands.\n\nUsage: help [command]\n\nIf no command is specified, shows a list of all commands.")
def help_handler(args, context):
    """Handle the help command."""
    command_processor = context["command_processor"]
    
    if args:
        return command_processor.get_command_help(args[0])
    else:
        return command_processor.get_help_text()

@command("quit", aliases=["q", "exit"], category="system", 
         help_text="Exit the game. Your progress will not be automatically saved.")
def quit_handler(args, context):
    """Handle the quit command."""
    if "game" in context:
        context["game"].quit_game()
    return f"{FORMAT_HIGHLIGHT}Goodbye!{FORMAT_RESET}"

@command("save", aliases=[], category="system", 
         help_text="Save the current game state to a file.\n\nUsage: save [filename]\n\nIf no filename is provided, saves to the default world file.")
def save_handler(args, context):
    """Handle the save command."""
    world = context["world"]
    
    if args:
        filename = args[0] + ".json" if not args[0].endswith(".json") else args[0]
        if world.save_to_json(filename):
            return f"{FORMAT_SUCCESS}World saved to {filename}{FORMAT_RESET}"
        else:
            return f"{FORMAT_ERROR}Error saving world to {filename}{FORMAT_RESET}"
    else:
        if world.save_to_json(DEFAULT_WORLD_FILE):
            return f"{FORMAT_SUCCESS}World saved to {DEFAULT_WORLD_FILE}{FORMAT_RESET}"
        else:
            return f"{FORMAT_ERROR}Error saving world{FORMAT_RESET}"

@command("load", aliases=[], category="system", 
         help_text="Load a game state from a file.\n\nUsage: load [filename]\n\nIf no filename is provided, loads from the default world file.")
def load_handler(args, context):
    """Handle the load command."""
    world = context["world"]
    
    if args:
        filename = args[0] + ".json" if not args[0].endswith(".json") else args[0]
        if world.load_from_json(filename):
            return f"{FORMAT_SUCCESS}World loaded from {filename}{FORMAT_RESET}\n\n{world.look()}"
        else:
            return f"{FORMAT_ERROR}Error loading world from {filename}{FORMAT_RESET}"
    else:
        if world.load_from_json(DEFAULT_WORLD_FILE):
            return f"{FORMAT_SUCCESS}World loaded from {DEFAULT_WORLD_FILE}{FORMAT_RESET}\n\n{world.look()}"
        else:
            return f"{FORMAT_ERROR}Error loading world or file not found{FORMAT_RESET}"

# Inventory and status commands
@command("inventory", aliases=["i", "inv"], category="inventory", 
         help_text="Show the items you are carrying.")
def inventory_handler(args, context):
    """Handle the inventory command."""
    world = context["world"]
    
    inventory_text = f"{FORMAT_TITLE}INVENTORY{FORMAT_RESET}\n\n"
    inventory_text += world.player.inventory.list_items()
    
    return inventory_text

@command("status", aliases=["stat", "st"], category="inventory", 
         help_text="Display your character's health, stats, and other information.")
def status_handler(args, context):
    """Handle the status command."""
    world = context["world"]
    
    status = world.get_player_status()
    return f"{FORMAT_TITLE}CHARACTER STATUS{FORMAT_RESET}\n\n{status}"