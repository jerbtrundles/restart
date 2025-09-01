# commands/system.py
"""
Contains all core system and meta-game commands.
"""
import os
from commands.command_system import command
from core.config import SAVE_GAME_DIR, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS

@command("help", ["h", "?"], "system", "Show help.\nUsage: help [command]")
def help_handler(args, context):
    cp = context["command_processor"]
    return cp.get_command_help(args[0]) if args else cp.get_help_text()

@command("quit", ["q", "exit"], "system", "Return to the main title screen.")
def quit_handler(args, context):
    game = context.get("game")
    if game:
        game._shutdown_gameplay_systems()
        game.game_state = "title_screen"
        return f"{FORMAT_HIGHLIGHT}Returning to title screen...{FORMAT_RESET}"

@command("save", [], "system", "Save game state.\nUsage: save [filename]")
def save_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    game = context["game"]
    fname = (args[0] if args else game.current_save_file)
    if not fname.endswith(".json"): fname += ".json"
    if world.save_game(fname):
        game.current_save_file = fname
        return f"{FORMAT_SUCCESS}World state saved to {fname}{FORMAT_RESET}"
    else:
        return f"{FORMAT_ERROR}Error saving world state to {fname}{FORMAT_RESET}"

@command("load", [], "system", "Load game state.\nUsage: load [filename]")
def load_handler(args, context):
    world = context["world"]
    game = context["game"]
    fname = (args[0] if args else game.current_save_file)
    if not fname.endswith(".json"): fname += ".json"
    save_path = os.path.join(SAVE_GAME_DIR, fname)
    if not os.path.exists(save_path):
         return f"{FORMAT_ERROR}Save file '{fname}' not found in '{SAVE_GAME_DIR}'.{FORMAT_RESET}"
    print(f"Attempting to load game state from {fname}...")
    if game.plugin_manager: game.plugin_manager.unload_all_plugins()
    success = world.load_save_game(fname)
    if success:
         game.current_save_file = fname
         game.text_buffer = []
         game.scroll_offset = 0
         game.input_text = ""
         game.command_history = []
         game.history_index = -1
         game.game_state = "playing"
         if game.plugin_manager:
             game.plugin_manager.service_locator.register_service("world", game.world)
             game.plugin_manager.load_all_plugins()
             time_plugin = game.plugin_manager.get_plugin("time_plugin")
             if time_plugin: time_plugin._update_world_time_data()
             weather_plugin = game.plugin_manager.get_plugin("weather_plugin")
             if weather_plugin: weather_plugin._notify_weather_change()
         return f"{FORMAT_SUCCESS}World state loaded from {fname}{FORMAT_RESET}\n\n{world.look()}"
    else:
         return f"{FORMAT_ERROR}Error loading world state from {fname}. Game state might be unstable.{FORMAT_RESET}"