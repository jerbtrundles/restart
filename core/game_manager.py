# core/game_manager.py
import math
import time
import pygame
import sys
import os # Needed for path joining
from typing import Any, List, Optional

from core.config import (
    BG_COLOR, DEBUG_COLOR, DEBUG_SHOW_LEVEL, DEFAULT_COLORS, FONT_FAMILY, FONT_SIZE, FORMAT_ERROR, FORMAT_HIGHLIGHT,
    FORMAT_RESET, FORMAT_TITLE, GAME_OVER_MESSAGE_LINE1, GAME_OVER_MESSAGE_LINE2, INPUT_BG_COLOR, INPUT_HEIGHT, LINE_SPACING, LOAD_SCREEN_COLUMN_WIDTH_FACTOR, LOAD_SCREEN_MAX_SAVES, MAX_BUFFER_LINES,
    SCREEN_HEIGHT, SCREEN_WIDTH, SCROLL_SPEED, TARGET_FPS, TEXT_COLOR, SAVE_GAME_DIR,
    DATA_DIR, COLOR_ORANGE, TITLE_FONT_SIZE_MULTIPLIER # <<< Added COLOR_ORANGE
)

from world.world import World
from commands.command_system import CommandProcessor
from utils.text_formatter import TextFormatter
from plugins.plugin_system import PluginManager
from commands.commands import register_movement_commands, save_handler, load_handler # Import specific handlers


class GameManager:
    def __init__(self, save_file: str = "default_save.json"): # Use save file name
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE, bold=False)
        self.title_font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE * TITLE_FONT_SIZE_MULTIPLIER, bold=True)
        self.selected_font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE, bold=True)
        self.clock = pygame.time.Clock()
        self.current_save_file = save_file # Store the target save file

        self.text_formatter = TextFormatter(
            font=self.font, screen_width=SCREEN_WIDTH,
            colors=DEFAULT_COLORS, margin=10, line_spacing=LINE_SPACING
        )
        
        # --- Defer World Initialization ---
        self.world = World() # Create instance, but don't load/init yet
        self.world.game = self # Link back
        self.current_save_file = save_file # Store default/target

        self.command_processor = CommandProcessor()
        register_movement_commands()

        # --- Initialize Plugins AFTER world load/init ---
        self.plugin_manager: Optional[PluginManager] = None

        # --- Game State ---
        self.game_state = "title_screen" # START HERE

        # --- Title Screen State ---
        self.title_options = ["New Game", "Load Game", "Quit"]
        self.selected_title_option = 0

        # --- Load Game Screen State ---
        self.available_saves: List[str] = []
        self.selected_load_option = 0 # Index in available_saves, -1 for 'Back'
        self.load_scroll_offset = 0 # For scrolling save list

        # --- Gameplay State (Initialized later) ---
        self.text_buffer: List[str] = []
        self.input_text = ""
        self.cursor_visible = True; self.cursor_timer = 0
        self.command_history = []; self.history_index = -1
        self.tab_completion_buffer = ""; self.tab_suggestions = []; self.tab_index = -1
        self.scroll_offset = 0
        self.total_rendered_height = 0
        self.debug_mode = False

        # default time data
        self.time_data = {
            "hour": 12, "minute": 0, "day": 1, "month": 1, "year": 1,
            "day_name": "Moonday", "month_name": "Deepwinter", "season": "winter",
            "time_period": "day", "time_str": "12:00",
            "date_str": "Moonday, 1 Deepwinter, Year 1"
        }

        print("GameManager initialized. Starting on Title Screen.")

    def _initialize_gameplay_systems(self):
        """Initializes plugins and systems needed only during active gameplay."""
        print("Initializing gameplay systems (Plugins)...")
        self.plugin_manager = PluginManager(self.world, self.command_processor)
        self.plugin_manager.event_system.subscribe("display_message", self._on_display_message)
        self.plugin_manager.event_system.subscribe("time_data", self._on_time_data_event) # Subscribe to time updates
        self.plugin_manager.event_system.subscribe("time_period_changed", self._on_time_period_changed)
        self.plugin_manager.load_all_plugins()

        # Force initial state push
        time_plugin = self.plugin_manager.get_plugin("time_plugin")
        if time_plugin: time_plugin._update_world_time_data() # This will publish the initial event
        weather_plugin = self.plugin_manager.get_plugin("weather_plugin")
        if weather_plugin: weather_plugin._notify_weather_change()


    def _shutdown_gameplay_systems(self):
        """Unloads plugins and resets gameplay state when returning to title."""
        print("Shutting down gameplay systems (Plugins)...")
        if self.plugin_manager:
            # --- ADD UNSUBSCRIBE ---
            if self.plugin_manager.event_system:
                self.plugin_manager.event_system.unsubscribe("display_message", self._on_display_message)
                self.plugin_manager.event_system.unsubscribe("time_data", self._on_time_data_event)
                self.plugin_manager.event_system.unsubscribe("time_period_changed", self._on_time_period_changed)
            # --- END UNSUBSCRIBE ---
            self.plugin_manager.unload_all_plugins()
        self.plugin_manager = None
        # Reset gameplay UI state
        self.text_buffer = []
        self.scroll_offset = 0
        self.total_rendered_height = 0
        self.input_text = ""
        self.command_history = []
        self.history_index = -1
        # Keep debug_mode? Or reset it? Let's keep it for now.

    def _on_time_data_event(self, event_type: str, data: dict) -> None:
        """Update the GameManager's copy of time data when the event is published."""
        if isinstance(data, dict):
            self.time_data = data.copy() # Update the dictionary used for drawing
        else:
            print(f"Warning: Received invalid time_data event: {data}")

    def _start_new_game(self):
        """Initializes a new world and transitions to playing state."""
        print("Starting New Game...")
        self.world.initialize_new_world() # Setup default player, items, NPCs
        if self.world.player:
            self._initialize_gameplay_systems() # Load plugins AFTER world exists
            self.game_state = "playing"
            # Add welcome message AFTER plugins load (so time/weather might be active)
            welcome_message = f"{FORMAT_TITLE}Welcome to Pygame MUD!{FORMAT_RESET}\n"
            welcome_message += "(Started new game)\n"
            welcome_message += "Type 'help' to see available commands.\n\n"
            welcome_message += "=" * 40 + "\n\n"
            welcome_message += self.world.look()
            self.text_buffer.append(self._sanitize_text(welcome_message))
            self._trim_text_buffer()
            self.scroll_offset = 0 # Ensure view starts at bottom
        else:
            print(f"{FORMAT_ERROR}Failed to initialize new world properly! Returning to title.{FORMAT_RESET}")
            self.game_state = "title_screen" # Go back if init failed

    def _load_selected_game(self):
        """Loads the selected save file and transitions to playing state."""
        if self.selected_load_option < 0 or self.selected_load_option >= len(self.available_saves):
            print("Invalid load selection.")
            return # Should not happen with UI checks

        save_to_load = self.available_saves[self.selected_load_option]
        print(f"Loading game: {save_to_load}...")

        # Attempt to load
        load_success = self.world.load_save_game(save_to_load)

        if load_success and self.world.player:
            self.current_save_file = save_to_load # Update current save file name
            self._initialize_gameplay_systems() # Load plugins AFTER world state is loaded
            self.game_state = "playing"
            # Add welcome message AFTER plugins load
            welcome_message = f"{FORMAT_TITLE}Welcome back to Pygame MUD!{FORMAT_RESET}\n"
            welcome_message += f"(Loaded game: {self.current_save_file})\n\n"
            welcome_message += "=" * 40 + "\n\n"
            welcome_message += self.world.look()
            self.text_buffer.append(self._sanitize_text(welcome_message))
            self._trim_text_buffer()
            self.scroll_offset = 0
        else:
            print(f"{FORMAT_ERROR}Failed to load save game '{save_to_load}'. Returning to title screen.{FORMAT_RESET}")
            # World might be in an inconsistent state, maybe reset it?
            self.world = World() # Create a fresh world object
            self.world.game = self
            self.world._load_definitions() # Reload static defs
            self.game_state = "title_screen" # Go back to title

    def _update_available_saves(self):
        """Scans the save directory for .json files."""
        self.available_saves = []
        if not os.path.isdir(SAVE_GAME_DIR):
            return # No save directory
        try:
            for fname in os.listdir(SAVE_GAME_DIR):
                if fname.lower().endswith(".json"):
                    # Optionally, try to parse briefly to see if it's a valid save?
                    # For now, just list all json files.
                    self.available_saves.append(fname)
            self.available_saves.sort() # Sort alphabetically
        except Exception as e:
            print(f"Error scanning save directory '{SAVE_GAME_DIR}': {e}")

    # Ensure handle_input still resets scroll_offset = 0
    def handle_input(self, text: str) -> str:
        # ... (add input to buffer, trim) ...
        input_text_formatted = f"> {text}"
        self.text_buffer.append(input_text_formatted)
        self._trim_text_buffer()

        if text.strip():
            self.command_history.append(text)
            self.history_index = -1

            context = { "game": self, "world": self.world, "command_processor": self.command_processor, "current_save_file": self.current_save_file }
            command_result = ""
            if not self.world.player.is_alive:
                command_result = f"{FORMAT_ERROR}You are dead. You cannot do that.{FORMAT_RESET}"
            else:
                command_result = self.command_processor.process_input(text, context)

            if command_result:
                sanitized_result = self._sanitize_text(command_result)
                self.text_buffer.append(sanitized_result)
                self._trim_text_buffer()

            self.scroll_offset = 0 # Reset scroll on new input/output
            self.input_text = "" # Clear input AFTER processing
            return "" # No direct return needed for display anymore
        else:
            self.input_text = ""
            return ""

    # ... (rest of GameManager, ensure _draw_status_indicators uses layout correctly) ...
    def _draw_status_indicators(self):
        if not hasattr(self.world, 'player') or not self.world.player:
            # If no player, we can't draw status, so return early
            return
        player = self.world.player

        status_y_offset = 5
        bar_height = 10
        bar_width = 100
        text_padding = 10
        bar_padding = 25

        # --- Health Bar ---
        health_x = self.text_formatter.margin
        # <<< Use layout Y position for status area >>>
        health_y = self.layout["status_area"]["y"] + status_y_offset
        # ... (rest of health bar drawing logic) ...
        pygame.draw.rect(self.screen, (80, 0, 0), (health_x, health_y, bar_width, bar_height))
        # ... (calculate filled_health_width, health_color) ...
        health_percent = player.health / player.max_health if player.max_health > 0 else 0
        filled_health_width = int(bar_width * health_percent)
        if health_percent < 0.3: health_color = (200, 0, 0)
        elif health_percent < 0.7: health_color = (200, 200, 0)
        else: health_color = (0, 200, 0)
        pygame.draw.rect(self.screen, health_color, (health_x, health_y, filled_health_width, bar_height))
        # ... (Health Text drawing logic) ...
        health_text = f"HP: {player.health}/{player.max_health}"
        health_surface = self.font.render(health_text, True, TEXT_COLOR)
        hp_text_x = health_x + bar_width + text_padding
        hp_text_y = health_y + (bar_height // 2) - (health_surface.get_height() // 2)
        self.screen.blit(health_surface, (hp_text_x, hp_text_y))


        # --- Mana Bar ---
        mana_x = hp_text_x + health_surface.get_width() + bar_padding
        # <<< Use layout Y position >>>
        mana_y = self.layout["status_area"]["y"] + status_y_offset
        # ... (rest of mana bar drawing logic) ...
        mana_bg_color = (0, 0, 80); pygame.draw.rect(self.screen, mana_bg_color, (mana_x, mana_y, bar_width, bar_height))
        # ... (calculate filled_mana_width, mana_fill_color) ...
        mana_percent = player.mana / player.max_mana if player.max_mana > 0 else 0
        filled_mana_width = int(bar_width * mana_percent)
        mana_fill_color = (50, 100, 255)
        pygame.draw.rect(self.screen, mana_fill_color, (mana_x, mana_y, filled_mana_width, bar_height))
        # ... (Mana Text drawing logic) ...
        mana_text = f"MP: {player.mana}/{player.max_mana}"
        mana_surface = self.font.render(mana_text, True, TEXT_COLOR)
        mp_text_x = mana_x + bar_width + text_padding
        mp_text_y = mana_y + (bar_height // 2) - (mana_surface.get_height() // 2)
        self.screen.blit(mana_surface, (mp_text_x, mp_text_y))


        # --- XP Bar ---
        xp_x = mp_text_x + mana_surface.get_width() + bar_padding
        # <<< Use layout Y position >>>
        xp_y = self.layout["status_area"]["y"] + status_y_offset
        # ... (rest of XP bar drawing logic) ...
        xp_bg_color = (100, 60, 0); pygame.draw.rect(self.screen, xp_bg_color, (xp_x, xp_y, bar_width, bar_height))
        # ... (calculate xp_percent, filled_xp_width, xp_fill_color) ...
        xp = player.experience; xp_needed = player.experience_to_level
        xp_percent = xp / xp_needed if xp_needed > 0 else 0
        filled_xp_width = int(bar_width * min(1.0, xp_percent))
        xp_fill_color = COLOR_ORANGE
        pygame.draw.rect(self.screen, xp_fill_color, (xp_x, xp_y, filled_xp_width, bar_height))
        # ... (XP Text drawing logic) ...
        xp_text = f"XP: {xp}/{xp_needed} (Lvl {player.level})"
        xp_surface = self.font.render(xp_text, True, TEXT_COLOR)
        xp_text_x = xp_x + bar_width + text_padding
        xp_text_y = xp_y + (bar_height // 2) - (xp_surface.get_height() // 2)
        self.screen.blit(xp_surface, (xp_text_x, xp_text_y))

        # --- Separator Line (Above Status Area) ---
        line_y = self.layout["status_area"]["y"]
        # Draw line slightly above the status area Y
        pygame.draw.line(self.screen, (80, 80, 100), (0, line_y - 1), (self.layout["screen_width"], line_y - 1), 1)

    # ... (_sanitize_text - unchanged) ...
    def _sanitize_text(self, text: str) -> str:
        if not text: return ""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = ''.join(ch if ch == '\n' or ord(ch) >= 32 else ' ' for ch in text)
        while '\n\n\n' in text: text = text.replace('\n\n\n', '\n\n')
        return text

    def update(self):
        """Update game state."""
        if self.game_state == "game_over":
            # Only update cursor blink in game over
            self.cursor_timer += self.clock.get_time()
            if self.cursor_timer >= 500: self.cursor_visible = not self.cursor_visible; self.cursor_timer = 0
            return

        current_time = time.time() # Use absolute time

        # This might be managed by the TimePlugin now, access it if needed
        # For mana regen, using real time might be simpler unless tied to game speed
        if self.world and self.world.player:
             self.world.player.update(current_time) # Pass time for regen calc
        # Or get game time from TimePlugin if precise game time needed:
        # time_plugin = self.service_locator.get_service("plugin:time_plugin")
        # current_game_time = time_plugin.game_time if time_plugin else 0

        # Update Plugins
        if self.plugin_manager:
            self.plugin_manager.on_tick(current_time) # Publish tick event handled within PluginManager

        # Update NPCs
        if self.world:
            npc_updates = self.world.update() # world.update handles NPC logic and returns messages
            if npc_updates:
                for message in npc_updates:
                    if message:
                        self.text_buffer.append(self._sanitize_text(message))
                self._trim_text_buffer()

        # Check for player death
        if self.world and self.world.player and not self.world.player.is_alive:
             self.game_state = "game_over"

        # Update cursor blink
        self.cursor_timer += self.clock.get_time()
        if self.cursor_timer >= 500: self.cursor_visible = not self.cursor_visible; self.cursor_timer = 0


    def draw(self):
        """Render the game based on the current game_state."""
        self._calculate_layout() # Always calculate layout first

        self.screen.fill(BG_COLOR)

        if self.game_state == "title_screen":
            self._draw_title_screen()
        elif self.game_state == "load_game_menu":
            self._draw_load_screen()
        elif self.game_state == "playing":
            self._draw_playing_screen() # Encapsulate gameplay drawing
        elif self.game_state == "game_over":
            self._draw_game_over_screen() # Encapsulate game over drawing

        # Debug indicator (Draws in all states if active)
        if self.debug_mode:
             debug_text = "DEBUG"
             if DEBUG_SHOW_LEVEL: debug_text += " (Levels ON)" # Indicate level visibility
             debug_surface = self.font.render(debug_text, True, DEBUG_COLOR)
             self.screen.blit(debug_surface, (self.layout["screen_width"] - debug_surface.get_width() - 10, 5))

        pygame.display.flip()

    # --- New Drawing Methods ---
    def _draw_centered_text(self, text, font, color, y_offset=0, center_x=None, center_y=None):
        """Helper to draw centered text."""
        if center_x is None: center_x = self.layout["screen_width"] // 2
        if center_y is None: center_y = self.layout["screen_height"] // 2
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(center_x, center_y + y_offset))
        self.screen.blit(surface, rect)

    def _draw_title_screen(self):
        """Draws the main title screen."""
        title_y_offset = -100
        option_start_y = -20
        option_spacing = 40

        # Draw Title
        self._draw_centered_text("Pygame MUD", self.title_font, (200, 200, 50), y_offset=title_y_offset)

        # Draw Options
        for i, option in enumerate(self.title_options):
            y_pos = option_start_y + i * option_spacing
            font_to_use = self.selected_font if i == self.selected_title_option else self.font
            color = (255, 255, 100) if i == self.selected_title_option else TEXT_COLOR
            prefix = "> " if i == self.selected_title_option else "  "
            self._draw_centered_text(f"{prefix}{option}", font_to_use, color, y_offset=y_pos)

    def _draw_load_screen(self):
        """Draws the load game selection screen."""
        title_y_offset = - (self.layout["screen_height"] // 2) + 50 # Near top
        option_start_y = title_y_offset + 60
        option_spacing = 30
        max_display = LOAD_SCREEN_MAX_SAVES
        col_width = self.layout["screen_width"] * LOAD_SCREEN_COLUMN_WIDTH_FACTOR
        col_x = (self.layout["screen_width"] - col_width) // 2

        # Draw Title
        self._draw_centered_text("Load Game", self.title_font, (200, 200, 50), y_offset=title_y_offset)

        # Display Saves (Scrollable)
        if not self.available_saves:
            self._draw_centered_text("No save files found.", self.font, (180, 180, 180), y_offset=option_start_y)
        else:
            # Display saves within the visible range
            for i in range(max_display):
                display_index = self.load_scroll_offset + i
                if display_index >= len(self.available_saves): break # Stop if we run out of saves

                save_name = self.available_saves[display_index]
                is_selected = (display_index == self.selected_load_option)
                font_to_use = self.selected_font if is_selected else self.font
                color = (255, 255, 100) if is_selected else TEXT_COLOR
                prefix = "> " if is_selected else "  "

                y_pos = option_start_y + i * option_spacing
                text_surface = font_to_use.render(f"{prefix}{save_name}", True, color)
                # Align text left within the column
                self.screen.blit(text_surface, (col_x + 10, y_pos))

        # Draw "Back" option
        back_index_relative = len(self.available_saves) - self.load_scroll_offset # Index relative to scroll start
        back_y_pos = option_start_y + (back_index_relative + 1) * option_spacing # Position after last potential save
        num_options = len(self.available_saves) + 1 # Total options including back
        is_back_selected = (self.selected_load_option == num_options - 1)

        # Only draw back if it fits on screen or is selected
        if back_y_pos < self.layout["screen_height"] - 50 or is_back_selected:
            font_to_use = self.selected_font if is_back_selected else self.font
            color = (255, 255, 100) if is_back_selected else TEXT_COLOR
            prefix = "> " if is_back_selected else "  "
            back_surface = font_to_use.render(f"{prefix}[ Back ]", True, color)
             # Center the back button horizontally
            back_rect = back_surface.get_rect(centerx=self.layout["screen_width"] // 2, y=back_y_pos)
            self.screen.blit(back_surface, back_rect)

        # Draw scroll indicators for save list if needed
        if len(self.available_saves) > max_display:
            if self.load_scroll_offset > 0: # Up arrow
                 pygame.draw.polygon(self.screen, (200, 200, 200), [(col_x + col_width - 15, option_start_y - 15), (col_x + col_width - 5, option_start_y - 5), (col_x + col_width - 25, option_start_y - 5)])
            if self.load_scroll_offset + max_display < len(self.available_saves): # Down arrow
                 pygame.draw.polygon(self.screen, (200, 200, 200), [(col_x + col_width - 15, option_start_y + max_display*option_spacing + 5), (col_x + col_width - 5, option_start_y + max_display*option_spacing -5), (col_x + col_width - 25, option_start_y + max_display*option_spacing - 5)])


    def _draw_playing_screen(self):
        """Draws the main game screen (text buffer, input, status)."""
        self._draw_time_bar()
        self._draw_status_indicators() # Uses layout['status_area']['y']

        # --- Text buffer rendering ---
        visible_text_area_rect = pygame.Rect(
            self.layout["text_area"]["x"], self.layout["text_area"]["y"],
            self.layout["text_area"]["width"], self.layout["text_area"]["height"]
        )

        # --- Clear the text area explicitly before drawing (helps prevent artifacts) ---
        pygame.draw.rect(self.screen, BG_COLOR, visible_text_area_rect)
        # --- End Clear ---


        if self.text_buffer:
            # Estimate needed height (adjust buffer slightly if needed)
            estimated_lines = sum(entry.count('\n') + 3 for entry in self.text_buffer)
            buffer_surface_height = max(visible_text_area_rect.height + 200, estimated_lines * self.text_formatter.line_height) # Generous buffer

            buffer_surface = pygame.Surface((visible_text_area_rect.width, buffer_surface_height), pygame.SRCALPHA)
            buffer_surface.fill((0, 0, 0, 0)) # Transparent

            full_text_to_render = "\n\n".join(self.text_buffer)
            content_height = self.text_formatter.render(buffer_surface, full_text_to_render, (0, 0))

            # --- Crucial: Adjust content_height measurement ---
            # Ensure content_height reflects the *actual* pixel height used by render,
            # including the last line's height if render returns Y *below* last line.
            # If render returns Y of the *top* of the last line, add line_height.
            # Assuming render returns Y *below* the last line, this should be okay.
            content_height = max(visible_text_area_rect.height, content_height) # Ensure it's at least view height
            # --- End adjustment ---

            self.total_rendered_height = content_height # Store for scrollbar

            # Calculate max scroll offset
            max_scroll_offset = max(0, content_height - visible_text_area_rect.height)
            # Clamp current scroll offset
            self.scroll_offset = max(0, min(self.scroll_offset, max_scroll_offset))

            # --- Recalculate source_y ---
            # Y position on the buffer surface from which to start copying pixels
            source_y = content_height - visible_text_area_rect.height - self.scroll_offset
            source_y = max(0, source_y) # Cannot be negative

            # --- Recalculate source_rect height ---
            # The height of the section we copy from the buffer
            blit_height = min(visible_text_area_rect.height, content_height - source_y)
            # --- End recalculate ---

            source_rect = pygame.Rect(0, source_y, visible_text_area_rect.width, blit_height)
            dest_pos = (visible_text_area_rect.x, visible_text_area_rect.y)

            # Blit the calculated portion
            self.screen.blit(buffer_surface, dest_pos, source_rect)

        # Draw Scroll Indicator and Input Area
        self._draw_scroll_indicator()
        self._draw_input_area()

    def _draw_game_over_screen(self):
        """Draws the game over screen."""
        # Can optionally draw the dimmed playing screen behind it
        # self._draw_playing_screen() # Draw dimmed game behind?
        # dim_surface = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        # dim_surface.fill((0, 0, 0, 180)) # Semi-transparent black overlay
        # self.screen.blit(dim_surface, (0, 0))
        self._draw_centered_text(GAME_OVER_MESSAGE_LINE1, self.title_font, DEFAULT_COLORS[FORMAT_ERROR], y_offset=-20)
        self._draw_centered_text(GAME_OVER_MESSAGE_LINE2, self.font, TEXT_COLOR, y_offset=20)

    def _draw_time_bar(self):
        # <<< This method seems correct already, it reads from self.time_data >>>
        # Retrieve values safely using .get()
        time_str = self.time_data.get("time_str", "??:??")
        date_str = self.time_data.get("date_str", "Unknown Date")
        time_period = self.time_data.get("time_period", "unknown")

        # Draw the bar background
        pygame.draw.rect(self.screen, (40, 40, 60), (0, 0, self.layout["screen_width"], self.layout["time_bar"]["height"]))

        # Draw time string (left)
        time_color = self._get_time_period_color(time_period)
        time_surface = self.font.render(time_str, True, time_color)
        self.screen.blit(time_surface, (10, 5))

        # Draw date string (center)
        date_surface = self.font.render(date_str, True, TEXT_COLOR)
        date_x = (self.layout["screen_width"] - date_surface.get_width()) // 2
        self.screen.blit(date_surface, (date_x, 5))

        # Draw period string (right)
        period_surface = self.font.render(time_period.capitalize(), True, time_color)
        period_x = self.layout["screen_width"] - period_surface.get_width() - 10
        self.screen.blit(period_surface, (period_x, 5))

        # Draw separator line
        pygame.draw.line(self.screen, (80, 80, 100), (0, self.layout["time_bar"]["height"]), (self.layout["screen_width"], self.layout["time_bar"]["height"]), 1)

    def _get_time_period_color(self, time_period):
        # ... (implementation unchanged) ...
        period_colors = {"dawn": (255, 165, 0), "day": (255, 255, 150), "dusk": (255, 100, 100), "night": (100, 100, 255)}
        return period_colors.get(time_period, TEXT_COLOR)

    def navigate_history(self, direction: int):
        # ... (implementation unchanged) ...
        if not self.command_history: return
        if direction > 0: self.history_index = min(self.history_index + 1, len(self.command_history) - 1)
        else: self.history_index = max(self.history_index - 1, -1)
        if self.history_index >= 0: self.input_text = self.command_history[-(self.history_index + 1)]
        else: self.input_text = ""
        self.tab_completion_buffer = ""; self.tab_suggestions = []; self.tab_index = -1

    def handle_tab_completion(self):
        # ... (implementation unchanged) ...
        current_text = self.input_text.strip()
        if not current_text: return
        if current_text != self.tab_completion_buffer or not self.tab_suggestions:
            self.tab_completion_buffer = current_text
            self.tab_suggestions = self.command_processor.get_command_suggestions(current_text)
            self.tab_index = -1
        if self.tab_suggestions:
            self.tab_index = (self.tab_index + 1) % len(self.tab_suggestions)
            self.input_text = self.tab_suggestions[self.tab_index]

    def resize_screen(self, new_width, new_height):
        # ... (implementation unchanged) ...
        SCREEN_WIDTH = new_width; SCREEN_HEIGHT = new_height
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        self.text_formatter.update_screen_width(new_width)

    def quit_game(self):
        """Cleanup and exit the application."""
        print("Quitting application...")
        self._shutdown_gameplay_systems() # Ensure cleanup if quit happens unexpectedly
        pygame.quit()
        sys.exit()

    # --- NEW: Handle Respawn ---
    def handle_respawn(self):
        """Handles the player respawn logic."""
        if self.game_state != "game_over": return

        player = self.world.player
        player.respawn() # Reset player state

        # Move player to respawn location
        self.world.current_region_id = player.respawn_region_id
        self.world.current_room_id = player.respawn_room_id

        # Add respawn message
        self.text_buffer = [f"{FORMAT_HIGHLIGHT}You feel your spirit return to your body...{FORMAT_RESET}\n"]
        self.text_buffer.append(self.world.look()) # Show new location

        # Change game state back
        self.game_state = "playing"
        self.input_text = "" # Clear input
    # --- END NEW ---


    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    # Ask to save on exit? For now, just quit.
                    # if self.game_state == "playing": self._prompt_save_on_exit()
                if self.game_state == "title_screen":
                    self._handle_title_input(event)
                elif self.game_state == "load_game_menu":
                    self._handle_load_input(event)
                elif self.game_state == "playing":
                    self._handle_playing_input(event)
                elif self.game_state == "game_over":
                    self._handle_game_over_input(event)

                # Handle resize globally
                if event.type == pygame.VIDEORESIZE:
                    self._handle_resize(event)

            # --- State Updates ---
            if self.game_state == "playing" or self.game_state == "game_over":
                 self.update() # Update world, NPCs, cursor only in these states
            else:
                 # Update cursor blink for menus
                 self.cursor_timer += self.clock.get_time()
                 if self.cursor_timer >= 500:
                     self.cursor_visible = not self.cursor_visible
                     self.cursor_timer = 0

            self.draw()
            self.clock.tick(TARGET_FPS) # Keep FPS limit

        # --- Cleanup after loop exits ---
        self._shutdown_gameplay_systems() # Ensure plugins unload if quitting from playing state
        pygame.quit()
        sys.exit()

    def _on_display_message(self, event_type: str, data: Any) -> None:
        """Handles messages published by plugins/events."""
        if isinstance(data, str): message = data
        elif isinstance(data, dict) and "message" in data: message = data["message"]
        else:
            try: message = str(data)
            except: message = "Unprintable message"
        self.text_buffer.append(self._sanitize_text(message))
        self._trim_text_buffer()

    def _on_time_data_event(self, event_type: str, data: dict) -> None:
        """Update the GameManager's copy of time data when the event is published."""
        if isinstance(data, dict):
            # --- Add Debug Print (Optional) ---
            # old_time_str = self.time_data.get("time_str", "N/A")
            # new_time_str = data.get("time_str", "N/A")
            # if old_time_str != new_time_str:
            #      print(f"[GameManager Debug] Received time_data update: {new_time_str}")
            # --- End Debug Print ---
            self.time_data = data.copy() # Update the dictionary used for drawing
        else:
            print(f"{FORMAT_ERROR}[GameManager] Warning: Received invalid time_data event: {data}{FORMAT_RESET}")
    def _on_time_period_changed(self, event_type: str, data: dict) -> None: # Keep this handler
        # Update local period if needed, display message
        if "new_period" in data:
             # self.time_data["time_period"] = data["new_period"] # _on_time_data_event handles this now
             pass
        if "transition_message" in data and data["transition_message"]:
             # Only add transition message if currently playing
             if self.game_state == "playing":
                  self.text_buffer.append(self._sanitize_text(data['transition_message']))
                  self._trim_text_buffer()


    def _create_test_world(self):
        # ... (implementation unchanged) ...
        from world.region import Region; from world.room import Room
        test_region = Region("Test Region", "A small test area.")
        entrance = Room("Entrance", "The entrance to the test region.")
        hall = Room("Main Hall", "A large hall with high ceilings.")
        garden = Room("Garden", "A beautiful garden with many plants.")
        entrance.exits = {"north": "hall"}; hall.exits = {"south": "entrance", "east": "garden"}; garden.exits = {"west": "hall"}
        garden.env_properties["outdoors"] = True; hall.env_properties["has_windows"] = True
        test_region.add_room("entrance", entrance); test_region.add_room("hall", hall); test_region.add_room("garden", garden)
        self.world.add_region("test", test_region)
        self.world.current_region_id = "test"; self.world.current_room_id = "entrance"
        from items.item_factory import ItemFactory
        sword = ItemFactory.create_item("Weapon", name="Steel Sword", description="A sharp steel sword.", damage=10)
        potion = ItemFactory.create_item("Consumable", name="Healing Potion", description="A potion that restores health.", effect_value=20, effect_type="heal")
        key = ItemFactory.create_item("Key", name="Brass Key", description="A small brass key.")
        self.world.add_item_to_room("test", "hall", sword); self.world.add_item_to_room("test", "garden", potion)
        self.world.player.inventory.add_item(key)
        from npcs.npc_factory import NPCFactory
        guard = NPCFactory.create_npc("guard", name="Guard Bob"); guard.current_region_id = "test"; guard.current_room_id = "entrance"; guard.patrol_points = ["entrance", "hall"]
        merchant = NPCFactory.create_npc("shopkeeper", name="Merchant Alice"); merchant.current_region_id = "test"; merchant.current_room_id = "hall"
        villager = NPCFactory.create_npc("villager", name="Villager Charlie"); villager.current_region_id = "test"; villager.current_room_id = "garden"
        self.world.add_npc(guard); self.world.add_npc(merchant); self.world.add_npc(villager)

    def _draw_status_indicators(self):
        """Draws health, mana, XP, etc. in the status area."""
        if not hasattr(self.world, 'player') or not self.world.player: return
        player = self.world.player

        status_y_offset = 5 # How far down from the top of the status area the bars/text start
        bar_height = 10 # Standard height for bars
        bar_width = 100 # Standard width for bars
        text_padding = 10 # Space between bar and text
        bar_padding = 25 # Space between bar sections (e.g., HP text and Mana bar)

        # --- Health Bar ---
        health_x = self.text_formatter.margin # Start at margin
        # Use the calculated Y for the status area
        health_y = self.layout["status_area"]["y"] + status_y_offset

        # Background
        pygame.draw.rect(self.screen, (80, 0, 0), (health_x, health_y, bar_width, bar_height))

        # Foreground (Filled portion)
        health_percent = player.health / player.max_health if player.max_health > 0 else 0
        filled_health_width = int(bar_width * health_percent)
        if health_percent < 0.3: health_color = (200, 0, 0)      # Red
        elif health_percent < 0.7: health_color = (200, 200, 0)  # Yellow
        else: health_color = (0, 200, 0)                         # Green
        pygame.draw.rect(self.screen, health_color, (health_x, health_y, filled_health_width, bar_height))

        # Health Text
        health_text = f"HP: {player.health}/{player.max_health}"
        health_surface = self.font.render(health_text, True, TEXT_COLOR)
        hp_text_x = health_x + bar_width + text_padding
        # Center text vertically with the bar center
        hp_text_y = health_y + (bar_height // 2) - (health_surface.get_height() // 2)
        self.screen.blit(health_surface, (hp_text_x, hp_text_y))


        # --- Mana Bar ---
        # Position mana bar after HP text, with bar padding
        mana_x = hp_text_x + health_surface.get_width() + bar_padding
        mana_y = health_y # Same vertical position as HP bar

        # Mana Background
        mana_bg_color = (0, 0, 80) # Dark Blue
        pygame.draw.rect(self.screen, mana_bg_color, (mana_x, mana_y, bar_width, bar_height))

        # Mana Foreground (Filled portion)
        mana_percent = player.mana / player.max_mana if player.max_mana > 0 else 0
        filled_mana_width = int(bar_width * mana_percent)
        mana_fill_color = (50, 100, 255) # Bright Blue
        pygame.draw.rect(self.screen, mana_fill_color, (mana_x, mana_y, filled_mana_width, bar_height))

        # Mana Text
        mana_text = f"MP: {player.mana}/{player.max_mana}"
        mana_surface = self.font.render(mana_text, True, TEXT_COLOR)
        mp_text_x = mana_x + bar_width + text_padding
        # Center text vertically with the bar center
        mp_text_y = mana_y + (bar_height // 2) - (mana_surface.get_height() // 2)
        self.screen.blit(mana_surface, (mp_text_x, mp_text_y))


        # --- Experience (XP) Bar (NEW) ---
        xp_x = mp_text_x + mana_surface.get_width() + bar_padding
        xp_y = mana_y # Same vertical position

        # XP Background
        xp_bg_color = (100, 60, 0) # Dark Orange/Brown
        pygame.draw.rect(self.screen, xp_bg_color, (xp_x, xp_y, bar_width, bar_height))

        # XP Foreground
        xp = player.experience
        xp_needed = player.experience_to_level
        xp_percent = xp / xp_needed if xp_needed > 0 else 0
        # Ensure percent doesn't exceed 1 visually even if xp > xp_needed briefly
        filled_xp_width = int(bar_width * min(1.0, xp_percent))
        xp_fill_color = COLOR_ORANGE # Use orange from config
        pygame.draw.rect(self.screen, xp_fill_color, (xp_x, xp_y, filled_xp_width, bar_height))

        # XP Text
        xp_text = f"XP: {xp}/{xp_needed} (Lvl {player.level})"
        xp_surface = self.font.render(xp_text, True, TEXT_COLOR)
        xp_text_x = xp_x + bar_width + text_padding
        xp_text_y = xp_y + (bar_height // 2) - (xp_surface.get_height() // 2)
        self.screen.blit(xp_surface, (xp_text_x, xp_text_y))
        # --- End XP Bar ---

        # --- Separator Line ---
        line_y = self.layout["status_area"]["y"]
        pygame.draw.line(self.screen, (80, 80, 100), (0, line_y - 1), (self.layout["screen_width"], line_y - 1), 1)

    # --- Scroll Indicator uses max_scroll ---
    def _draw_scroll_indicator(self):
        """Draws arrows if scrolling is possible."""
        # Check if necessary attributes exist
        if not hasattr(self, 'layout') or not hasattr(self, 'total_rendered_height'):
            return

        # Check if text_area is defined in layout
        text_area = self.layout.get("text_area")
        if not text_area or not isinstance(text_area, dict):
            return

        visible_height = text_area.get("height", 0)
        # Use the stored total rendered height
        content_height = self.total_rendered_height
        max_scroll = max(0, content_height - visible_height)

        # Show up arrow if not at the very bottom (i.e., can scroll up to see older)
        # scroll_offset < max_scroll means there's more content above the current view
        if self.scroll_offset < max_scroll:
            arrow_points_up = [
                 (self.layout["screen_width"] - 25, text_area["y"] + 15),
                 (self.layout["screen_width"] - 15, text_area["y"] + 5),
                 (self.layout["screen_width"] - 5, text_area["y"] + 15)
            ]
            if len(arrow_points_up) >= 3: pygame.draw.polygon(self.screen, (200, 200, 200), arrow_points_up)

        # Show down arrow if not at the very top (i.e., can scroll down to see newer)
        # scroll_offset > 0 means the top of the content is scrolled off-screen upwards
        if self.scroll_offset > 0:
            input_area_y = self.layout.get("input_area", {}).get("y", self.layout["screen_height"]) # Get input area top Y
            arrow_points_down = [
                (self.layout["screen_width"] - 25, input_area_y - 15),
                (self.layout["screen_width"] - 15, input_area_y - 5),
                (self.layout["screen_width"] - 5, input_area_y - 15)
            ]
            if len(arrow_points_down) >= 3: pygame.draw.polygon(self.screen, (200, 200, 200), arrow_points_down)

    def _calculate_layout(self):
        """Recalculates UI element positions and sizes."""
        current_width, current_height = self.screen.get_size()

        time_bar_height = 30
        input_area_height = INPUT_HEIGHT
        status_area_height = 30 # Height for HP/MP/XP bars
        margin = self.text_formatter.margin # Use margin from formatter

        # --- Calculate Y positions ---
        time_bar_y = 0
        input_area_y = current_height - input_area_height
        status_area_y = input_area_y - status_area_height # Status is directly above input

        # --- Calculate Text Area based on remaining space ---
        text_area_top_y = time_bar_y + time_bar_height + margin # Start below time bar + margin
        text_area_bottom_y = status_area_y - margin # End above status bar - margin

        # The height is simply the difference between the bottom and top Y coordinates
        text_area_height = text_area_bottom_y - text_area_top_y
        text_area_height = max(10, text_area_height) # Ensure minimum positive height

        # Update TextFormatter's usable width
        self.text_formatter.update_screen_width(current_width)

        # Store Layout
        self.layout = {
            "screen_width": current_width,
            "screen_height": current_height,
            "time_bar": {"height": time_bar_height, "y": time_bar_y},
            "input_area": {"height": input_area_height, "y": input_area_y},
            "status_area": {"height": status_area_height, "y": status_area_y},
            "text_area": {
                "x": margin,
                "y": text_area_top_y,
                "width": self.text_formatter.usable_width,
                "height": text_area_height
            }
        }
        # print(f"[Layout] ScreenH={current_height}, TextY={text_area_top_y}, TextH={text_area_height}, StatusY={status_area_y}, InputY={input_area_y}") # Debug

    def _draw_input_area(self):
        pygame.draw.rect(self.screen, INPUT_BG_COLOR,
                         (0, self.layout["input_area"]["y"], self.layout["screen_width"], self.layout["input_area"]["height"]))
        input_display = "> " + self.input_text
        if self.cursor_visible: input_display += "|"
        input_surface = self.font.render(input_display, True, TEXT_COLOR)
        input_y_pos = self.layout["input_area"]["y"] + (self.layout["input_area"]["height"] - input_surface.get_height()) // 2
        self.screen.blit(input_surface, (self.text_formatter.margin, input_y_pos))

    def _trim_text_buffer(self):
        """Removes older entries from the text buffer if it exceeds the limit."""
        # print(f"[DEBUG TRIM] Check: Buffer size = {len(self.text_buffer)}, Limit = {MAX_BUFFER_LINES}")
        if len(self.text_buffer) > MAX_BUFFER_LINES:
            excess = len(self.text_buffer) - MAX_BUFFER_LINES
            self.text_buffer = self.text_buffer[excess:] # Keep the latest entries

            # # Add a notification only once, at the *new* top
            # trim_notice = f"{FORMAT_HIGHLIGHT}(Older messages removed to prevent slowdown){FORMAT_RESET}"
            # # Avoid adding duplicate trim notices consecutively
            # if not self.text_buffer or self.text_buffer[0] != trim_notice:
            #      # Insert at the beginning so it's visible when scrolling up
            #      self.text_buffer.append(trim_notice)

    # --- Input Handlers for Each State ---
    def _handle_title_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_title_option = (self.selected_title_option - 1) % len(self.title_options)
            elif event.key == pygame.K_DOWN:
                self.selected_title_option = (self.selected_title_option + 1) % len(self.title_options)
            elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                selected = self.title_options[self.selected_title_option]
                if selected == "New Game":
                    self._start_new_game()
                elif selected == "Load Game":
                    self._update_available_saves() # Refresh save list
                    self.game_state = "load_game_menu"
                    self.selected_load_option = 0 # Default to first save or 'Back'
                    self.load_scroll_offset = 0
                elif selected == "Quit":
                    pygame.event.post(pygame.event.Event(pygame.QUIT)) # Post quit event

    def _handle_load_input(self, event):
        num_options = len(self.available_saves) + 1 # Saves + Back button
        max_display = 10 # How many saves to show at once

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_load_option = (self.selected_load_option - 1 + num_options) % num_options # Wrap around including Back
            elif event.key == pygame.K_DOWN:
                self.selected_load_option = (self.selected_load_option + 1) % num_options
            elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                if self.selected_load_option == num_options - 1: # Selected "Back"
                    self.game_state = "title_screen"
                elif self.available_saves and 0 <= self.selected_load_option < len(self.available_saves): # Selected a valid save
                    self._load_selected_game()
            elif event.key == pygame.K_ESCAPE: # Escape also goes back
                 self.game_state = "title_screen"
            # Add PageUp/PageDown for scrolling saves if needed later

        # --- Adjust scroll offset based on selection ---
        # Ensure selected item is visible
        visible_start_index = self.load_scroll_offset
        visible_end_index = self.load_scroll_offset + max_display -1

        if self.selected_load_option < visible_start_index:
            self.load_scroll_offset = self.selected_load_option
        elif self.selected_load_option > visible_end_index:
            self.load_scroll_offset = self.selected_load_option - max_display + 1
        # Clamp scroll offset
        self.load_scroll_offset = max(0, min(self.load_scroll_offset, max(0, num_options - max_display)))


    def _handle_playing_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                self.handle_input(self.input_text) # Process command
                # Reset tab completion state after entering command
                self.tab_completion_buffer = ""
                self.tab_suggestions = []
                self.tab_index = -1
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
                # Reset tab completion state if backspacing
                self.tab_completion_buffer = ""
                self.tab_suggestions = []
                self.tab_index = -1
            elif event.key == pygame.K_UP: self.navigate_history(1)
            elif event.key == pygame.K_DOWN: self.navigate_history(-1)
            elif event.key == pygame.K_TAB: self.handle_tab_completion()
            elif event.key == pygame.K_PAGEUP: self._scroll_text_buffer(self.layout["text_area"]["height"] // 2)
            elif event.key == pygame.K_PAGEDOWN: self._scroll_text_buffer(-self.layout["text_area"]["height"] // 2)
            elif event.key == pygame.K_HOME: self._scroll_text_buffer(self.total_rendered_height) # Scroll to top
            elif event.key == pygame.K_END: self.scroll_offset = 0 # Scroll to bottom
            elif event.key == pygame.K_F1: self._toggle_debug_mode()
            else:
                if event.unicode.isprintable():
                    self.input_text += event.unicode
                    # Reset tab completion state if typing new chars
                    self.tab_completion_buffer = ""
                    self.tab_suggestions = []
                    self.tab_index = -1
        elif event.type == pygame.MOUSEWHEEL:
            scroll_amount_pixels = SCROLL_SPEED * self.text_formatter.line_height * event.y # y is -1 or 1
            self._scroll_text_buffer(scroll_amount_pixels)

    def _handle_game_over_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.handle_respawn() # Existing respawn logic
            elif event.key == pygame.K_q:
                # Quit to title screen instead of exiting app
                self._shutdown_gameplay_systems()
                self.game_state = "title_screen"
                # Optionally reset world object here if desired
                # self.world = World()
                # self.world.game = self
                # self.world._load_definitions()

    def _handle_resize(self, event):
        """Handles window resize event."""
        # Store new size and let _calculate_layout handle it next frame
        new_width, new_height = event.w, event.h
        min_width, min_height = 600, 400 # Set minimum size
        new_width = max(min_width, new_width)
        new_height = max(min_height, new_height)

        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        # No need to call _calculate_layout here, draw() does it.

    # Helper for scrolling text buffer
    def _scroll_text_buffer(self, amount_pixels: int):
        """Scrolls the main text buffer by a pixel amount, clamping."""
        content_height = self.total_rendered_height
        visible_height = self.layout.get("text_area", {}).get("height", SCREEN_HEIGHT) # Use layout if available
        max_scroll = max(0, content_height - visible_height)
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset + amount_pixels))

    # Helper for toggling debug
    def _toggle_debug_mode(self):
        self.debug_mode = not self.debug_mode
        if self.game_state == "playing": # Only show message if in game
            msg = f"{FORMAT_HIGHLIGHT}Debug mode {'enabled' if self.debug_mode else 'disabled'}.{FORMAT_RESET}"
            if self.debug_mode: msg += " NPC Levels Visible."
            self.text_buffer.append(msg)
            self._trim_text_buffer()
