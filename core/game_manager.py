# core/game_manager.py
"""
The central coordinator of the game, managing game states, the main loop,
and delegating tasks to other core systems.
"""
import pygame
import sys
import os
import time
from typing import List, Optional

from commands.command_system import CommandProcessor
from core.config import *
from core.time_manager import TimeManager
from core.weather_manager import WeatherManager
from core.input_handler import InputHandler
from ui.renderer import Renderer
from world.world import World


class GameManager:
    def __init__(self, save_file: str = DEFAULT_SAVE_FILE):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Pygame MUD")
        self.clock = pygame.time.Clock()

        self.world = World()
        self.world.game = self
        self.command_processor = CommandProcessor()
        self.time_manager = TimeManager()
        self.weather_manager = WeatherManager()
        self.renderer = Renderer(self.screen, self)
        self.input_handler = InputHandler(self, self.command_processor)

        self.current_save_file = save_file
        self.game_state = "title_screen"
        self.debug_mode = False
        # --- FIX: Re-add the missing debug attribute ---
        self.debug_ignore_player = DEBUG_IGNORE_PLAYER_COMBAT

        # State for menus
        self.title_options = ["New Game", "Load Game", "Quit"]
        self.selected_title_option = 0
        self.available_saves: List[str] = []
        self.selected_load_option = 0

    def run(self):
        running = True
        while running:
            # Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                if event.type == pygame.VIDEORESIZE:
                    self._handle_resize(event)
                self.input_handler.handle_event(event)

            # Update Game State
            if self.game_state == "playing":
                self.update()

            # Render
            self.renderer.draw()
            self.clock.tick(TARGET_FPS)
        
        pygame.quit()
        sys.exit()

    def update(self):
        """Main update loop for the 'playing' game state."""
        current_time_abs = time.time()
        
        time_change = self.time_manager.update(current_time_abs)
        if time_change:
            old_period, new_period = time_change
            season = self.time_manager.time_data.get("season", "summer")
            self.weather_manager.update_on_time_period_change(season)
            
            msg = self.time_manager.get_time_transition_message(old_period, new_period)
            if msg: self.renderer.add_message(msg)

        world_messages = self.world.update()
        for msg in world_messages: self.renderer.add_message(msg)

        if self.world.player and self.world.player.is_alive:
            player_messages = self.world.player.update(current_time_abs, self.clock.get_time() / 1000.0)
            for msg in player_messages: self.renderer.add_message(msg)

        if self.world.player and not self.world.player.is_alive:
            self.game_state = "game_over"

    def process_command(self, text: str):
        """Processes a command string and adds the result to the text buffer."""
        self.renderer.add_message(f"> {text}")
        
        context = {"game": self, "world": self.world, "command_processor": self.command_processor}
        
        player = self.world.player
        if not player:
            command_result = f"{FORMAT_ERROR}CRITICAL ERROR: Player is missing.{FORMAT_RESET}"
        elif not player.is_alive:
            cmd_word = text.strip().lower().split()[0]
            allowed_dead_commands = {"look", "l", "status", "st", "inventory", "i", "inv", "help", "h", "?", "quit", "q", "exit", "load"}
            if cmd_word in allowed_dead_commands:
                command_result = self.command_processor.process_input(text, context)
            else:
                command_result = f"{FORMAT_ERROR}You are dead. You cannot do that.{FORMAT_RESET}"
        else:
            command_result = self.command_processor.process_input(text, context)

        if command_result:
            self.renderer.add_message(command_result)
        
        self.renderer.scroll_offset = 0

    def start_new_game(self):
        self.world.initialize_new_world()
        self.time_manager.initialize_time()
        self.weather_manager = WeatherManager()
        if self.world.player:
            self.game_state = "playing"
            self.renderer.text_buffer = []
            welcome_message = f"{FORMAT_TITLE}Welcome to Pygame MUD!{FORMAT_RESET}\nType 'help' to see available commands.\n\n{'='*40}\n\n{self.world.look()}"
            self.renderer.add_message(welcome_message)
            self.renderer.scroll_offset = 0
        else:
            print(f"{FORMAT_ERROR}Failed to initialize new world properly! Returning to title.{FORMAT_RESET}")
            self.game_state = "title_screen"

    def load_selected_game(self):
        if self.selected_load_option < 0 or self.selected_load_option >= len(self.available_saves): return
        save_to_load = self.available_saves[self.selected_load_option]
        
        load_success, loaded_time_data, loaded_weather_data = self.world.load_save_game(save_to_load)
        
        if load_success and self.world.player and loaded_weather_data:
            self.time_manager.apply_loaded_time_state(loaded_time_data)
            self.weather_manager.apply_loaded_weather_state(loaded_weather_data)
            self.current_save_file = save_to_load
            self.game_state = "playing"
            self.renderer.text_buffer = []
            welcome_message = f"{FORMAT_TITLE}Welcome back!{FORMAT_RESET}\n(Loaded game: {self.current_save_file})\n\n{'='*40}\n\n{self.world.look()}"
            self.renderer.add_message(welcome_message)
            self.renderer.scroll_offset = 0
        else:
            print(f"{FORMAT_ERROR}Failed to load '{save_to_load}'. Returning to title.{FORMAT_RESET}")
            self.world = World(); self.world.game = self
            self.game_state = "title_screen"

    def handle_respawn(self):
        if self.game_state != "game_over" or not self.world.player: return
        self.world.player.respawn()
        self.world.current_region_id = self.world.player.respawn_region_id
        self.world.current_room_id = self.world.player.respawn_room_id
        self.renderer.text_buffer = [f"{FORMAT_HIGHLIGHT}You feel your spirit return to your body...{FORMAT_RESET}\n"]
        self.renderer.add_message(self.world.look())
        self.game_state = "playing"
        self.input_handler.input_text = ""

    def quit_to_title(self):
        self.renderer.text_buffer = []
        self.renderer.scroll_offset = 0
        self.input_handler.input_text = ""
        self.input_handler.command_history = []
        self.input_handler.history_index = -1
        self.game_state = "title_screen"

    def select_title_option(self):
        selected = self.title_options[self.selected_title_option]
        if selected == "New Game": self.start_new_game()
        elif selected == "Load Game": self._update_available_saves(); self.game_state = "load_game_menu"; self.selected_load_option = 0
        elif selected == "Quit": pygame.event.post(pygame.event.Event(pygame.QUIT))

    def select_load_option(self):
        if self.selected_load_option == len(self.available_saves):
            self.game_state = "title_screen"
        elif self.available_saves and 0 <= self.selected_load_option < len(self.available_saves):
            self.load_selected_game()

    def _update_available_saves(self):
        self.available_saves = []
        if not os.path.isdir(SAVE_GAME_DIR): return
        try:
            self.available_saves = sorted([fname for fname in os.listdir(SAVE_GAME_DIR) if fname.lower().endswith(".json")])
        except Exception as e:
            print(f"Error scanning save directory '{SAVE_GAME_DIR}': {e}")
            
    def toggle_debug_mode(self):
        self.debug_mode = not self.debug_mode
        if self.game_state == "playing":
            msg = f"{FORMAT_HIGHLIGHT}Debug mode {'enabled' if self.debug_mode else 'disabled'}.{FORMAT_RESET}"
            self.renderer.add_message(msg)

    def _handle_resize(self, event):
        new_width, new_height = max(800, event.w), max(600, event.h)
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        self.renderer.screen = self.screen