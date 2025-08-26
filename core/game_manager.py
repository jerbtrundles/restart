# core/game_manager.py
import math
import time
import pygame
import sys
import os # Needed for path joining
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from utils.utils import format_name_for_display, get_article, simple_plural
from items.item import Item

from core.config import (
    BG_COLOR, DEBUG_COLOR, DEBUG_SHOW_LEVEL, DEFAULT_COLORS, EFFECT_DEFAULT_TICK_INTERVAL, FONT_FAMILY, FONT_SIZE, FORMAT_BLUE, FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_GRAY, FORMAT_HIGHLIGHT, FORMAT_ORANGE,
    FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, FORMAT_YELLOW, GAME_OVER_MESSAGE_LINE1, GAME_OVER_MESSAGE_LINE2, INPUT_BG_COLOR, INPUT_HEIGHT, ITEM_DURABILITY_LOW_THRESHOLD, LINE_SPACING, LOAD_SCREEN_COLUMN_WIDTH_FACTOR, LOAD_SCREEN_MAX_SAVES, MAX_BUFFER_LINES, PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD, PLAYER_STATUS_HEALTH_LOW_THRESHOLD,
    SCREEN_HEIGHT, SCREEN_WIDTH, SCROLL_SPEED, SIDE_PANEL_WIDTH, STATUS_PANEL_PADDING, STATUS_PANEL_WIDTH, TARGET_FPS, TEXT_COLOR, SAVE_GAME_DIR,
    DATA_DIR, COLOR_ORANGE, TITLE_FONT_SIZE_MULTIPLIER # <<< Added COLOR_ORANGE
)

from magic.spell_registry import get_spell
from world.world import World
from commands.command_system import CommandProcessor
from utils.text_formatter import TextFormatter, format_target_name
from plugins.plugin_system import PluginManager
from commands.commands import register_movement_commands, save_handler, load_handler # Import specific handlers


class GameManager:
    def __init__(self, save_file: str = "default_save.json"): # Use save file name
        pygame.init()
        # print(pygame.font.get_fonts())
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE, bold=False)
        self.title_font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE * TITLE_FONT_SIZE_MULTIPLIER, bold=True)
        self.selected_font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE, bold=True)
        self.clock = pygame.time.Clock()
        self.current_save_file = save_file # Store the target save file
        self.status_panel_width = STATUS_PANEL_WIDTH # <<< Define width for the new panel

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
            self.cursor_timer += self.clock.get_time()
            if self.cursor_timer >= 500: self.cursor_visible = not self.cursor_visible; self.cursor_timer = 0
            return

        current_time_abs = time.time() 
        # --- MODIFIED: Calculate elapsed_real_time for player effects ---
        # Use self.clock.get_time() for more accurate frame-delta for player
        # Convert milliseconds to seconds
        elapsed_real_time_frame = self.clock.get_time() / 1000.0 
        # --- END MODIFIED ---

        player_update_messages = [] 

        if self.plugin_manager:
            self.plugin_manager.on_tick(current_time_abs) # Pass absolute time to plugins

        if self.world and self.world.player and self.world.player.is_alive:
            # --- MODIFIED: Pass elapsed_real_time_frame to player.update ---
            player_effect_messages = self.world.player.update(current_time_abs, elapsed_real_time_frame)
            if player_effect_messages:
                 player_update_messages.extend(player_effect_messages)
            # --- END MODIFIED ---
        
        npc_updates = []
        if self.world:
            # --- MODIFIED: Ensure NPC updates use a consistent interval or calculated delta ---
            # World.update itself will pass appropriate delta to NPC.update if needed
            # For now, NPC.update uses WORLD_UPDATE_INTERVAL internally for its effect processing.
            npc_updates = self.world.update() 
            # --- END MODIFIED ---

        # --- Append Player Messages to Buffer ---
        # (This logic for adding messages to buffer remains the same)
        if player_update_messages:
            buffer_changed = False
            for msg in player_update_messages:
                if msg:
                    clean_msg = self._sanitize_text(msg)
                    if clean_msg not in self.text_buffer[-len(player_update_messages):]: 
                        self.text_buffer.append(clean_msg)
                        buffer_changed = True
            if buffer_changed:
                self._trim_text_buffer()
                self.scroll_offset = 0 
        # --- End Append Player Messages ---

        if npc_updates:
            buffer_changed = False
            for message in npc_updates:
                if message:
                    clean_msg = self._sanitize_text(message)
                    if clean_msg not in self.text_buffer[-len(npc_updates):]: 
                        self.text_buffer.append(clean_msg)
                        buffer_changed = True
            if buffer_changed:
                self._trim_text_buffer()
                self.scroll_offset = 0 

        if self.world and self.world.player and not self.world.player.is_alive:
             self.game_state = "game_over"

        self.cursor_timer += self.clock.get_time() # Use raw milliseconds for cursor
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
            self._draw_left_status_panel()
            self._draw_right_status_panel() # <<< ADD THIS CALL
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
        # --- Title ---
        title_text = "Load Game"
        title_surface = self.title_font.render(title_text, True, (200, 200, 50))
        # Center title horizontally, position 50px from the top
        title_rect = title_surface.get_rect(centerx=self.layout["screen_width"] // 2, y=50)
        self.screen.blit(title_surface, title_rect)

        # --- Save List Area Calculation ---
        option_start_y = title_rect.bottom + 40 # Start options below the title
        option_spacing = 30 # Vertical space per option
        max_display_items = 10 # Max saves to show at once (can be adjusted)
        # Calculate column width and position
        col_width = max(200, int(self.layout["screen_width"] * 0.6)) # 60% of screen, min 200px
        col_x = (self.layout["screen_width"] - col_width) // 2
        # Calculate available height for the list itself (excluding Back button area)
        list_area_bottom_margin = 80 # Space above the back button
        list_area_height = self.layout["screen_height"] - option_start_y - list_area_bottom_margin
        # Determine how many items can fit vertically
        displayable_count = max(1, list_area_height // option_spacing)
        displayable_count = min(displayable_count, max_display_items) # Don't exceed max display limit

        # --- Display Saves (Scrollable) ---
        if not self.available_saves:
            no_saves_text = "No save files found."
            no_saves_surface = self.font.render(no_saves_text, True, (180, 180, 180))
            # Center the "no saves" message
            no_saves_rect = no_saves_surface.get_rect(centerx=self.layout["screen_width"] // 2, y=option_start_y)
            self.screen.blit(no_saves_surface, no_saves_rect)
        else:
            # Loop through the number of displayable slots
            for i in range(displayable_count):
                current_y_pos = option_start_y + i * option_spacing
                # Calculate the actual index in available_saves based on scroll offset
                display_index = self.load_scroll_offset + i

                # Stop if we've gone past the end of the available saves
                if display_index >= len(self.available_saves):
                    break

                save_name = self.available_saves[display_index]
                is_selected = (display_index == self.selected_load_option)
                font_to_use = self.selected_font if is_selected else self.font
                color = (255, 255, 100) if is_selected else TEXT_COLOR
                prefix = "> " if is_selected else "  "

                # Render the save name text
                text_surface = font_to_use.render(f"{prefix}{save_name}", True, color)
                # Blit directly at calculated coordinates (left-aligned within the column)
                self.screen.blit(text_surface, (col_x + 10, current_y_pos)) # Add small X padding

        # --- Draw "Back" option ---
        num_saves = len(self.available_saves)
        # The index for "Back" is always after the last save file index
        back_option_index = num_saves
        is_back_selected = (self.selected_load_option == back_option_index)

        # Calculate Back button position (place it consistently near the bottom)
        back_y_pos = self.layout["screen_height"] - 50 # 50px from bottom

        font_to_use = self.selected_font if is_back_selected else self.font
        color = (255, 255, 100) if is_back_selected else TEXT_COLOR
        prefix = "> " if is_back_selected else "  "
        back_surface = font_to_use.render(f"{prefix}[ Back ]", True, color)
        # Center the back button horizontally using its rect
        back_rect = back_surface.get_rect(centerx=self.layout["screen_width"] // 2, y=back_y_pos)
        self.screen.blit(back_surface, back_rect)

        # --- Draw scroll indicators for save list if needed ---
        if len(self.available_saves) > displayable_count:
            # Calculate arrow positions relative to the actual list display area
            list_top_y = option_start_y
            list_bottom_y = option_start_y + displayable_count * option_spacing
            arrow_x = col_x + col_width - 15 # X position for arrows (right side of column)

            # Show Up Arrow if scrolled down
            if self.load_scroll_offset > 0:
                pygame.draw.polygon(self.screen, (200, 200, 200), [
                    (arrow_x, list_top_y - 15),        # Top point
                    (arrow_x + 10, list_top_y - 5),    # Bottom right
                    (arrow_x - 10, list_top_y - 5)     # Bottom left
                ])
            # Show Down Arrow if more items below
            if self.load_scroll_offset + displayable_count < len(self.available_saves):
                pygame.draw.polygon(self.screen, (200, 200, 200), [
                    (arrow_x, list_bottom_y + 5),      # Bottom point (adjusted slightly below list)
                    (arrow_x + 10, list_bottom_y - 5), # Top right
                    (arrow_x - 10, list_bottom_y - 5)  # Top left
                ])

    def _draw_playing_screen(self):
        """Draws the main game screen with stacked left panels."""
        self._draw_time_bar()
        self._draw_left_status_panel()
        self._draw_right_status_panel()        # Draw Status Panel (Right)
        self._draw_room_info_panel()     # Draw Room Info Panel (Top-Left)

        # --- Main Text Area Rendering (Uses updated layout['text_area']) ---
        text_area_layout = self.layout.get("text_area")
        if not text_area_layout: return # Safety check

        visible_text_area_rect = pygame.Rect(
            text_area_layout["x"], text_area_layout["y"],
            text_area_layout["width"], text_area_layout["height"]
        )
        # --- Clear the text area explicitly before drawing ---
        pygame.draw.rect(self.screen, BG_COLOR, visible_text_area_rect)

        if self.text_buffer:
            # Estimate needed height
            min_buffer_height = visible_text_area_rect.height + self.text_formatter.line_height_with_text * 5
            estimated_lines = sum(entry.count('\n') + 3 for entry in self.text_buffer)
            buffer_surface_height = max(min_buffer_height, estimated_lines * self.text_formatter.line_height_with_text)

            # Ensure TextFormatter has the correct width for the main area
            self.text_formatter.update_screen_width(visible_text_area_rect.width)

            buffer_surface = pygame.Surface((visible_text_area_rect.width, buffer_surface_height), pygame.SRCALPHA)
            buffer_surface.fill((0, 0, 0, 0)) # Transparent background

            full_text_to_render = "\n\n".join(self.text_buffer)
            # Render the text onto the (potentially very tall) buffer surface
            raw_content_height = self.text_formatter.render(buffer_surface, full_text_to_render, (0, 0))

            # Calculate content height and scroll parameters
            content_height = max(visible_text_area_rect.height, raw_content_height + (self.text_formatter.line_spacing // 2))
            self.total_rendered_height = content_height
            max_scroll_offset = max(0, content_height - visible_text_area_rect.height)
            self.scroll_offset = max(0, min(self.scroll_offset, max_scroll_offset))
            source_y = max(0, content_height - visible_text_area_rect.height - self.scroll_offset)
            blit_height = max(0, min(visible_text_area_rect.height, content_height - source_y))

            if blit_height > 0:
                source_rect = pygame.Rect(0, source_y, visible_text_area_rect.width, blit_height)
                # Destination is the top-left corner of the text area on the screen
                dest_pos = (visible_text_area_rect.x, visible_text_area_rect.y)
                self.screen.blit(buffer_surface, dest_pos, source_rect)

        # Pass the text area's rect to the scroll indicator
        self._draw_scroll_indicator(visible_text_area_rect)
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

    def _draw_scroll_indicator(self, text_area_rect: pygame.Rect):
        """Draws arrows indicating possible scroll directions, with correct shape placement."""
        if not hasattr(self, 'total_rendered_height'): return

        visible_height = text_area_rect.height
        content_height = self.total_rendered_height
        max_scroll = max(0, content_height - visible_height)

        # No indicators needed if all content fits
        if max_scroll <= 0:
            return

        # Arrow drawing parameters
        arrow_x = text_area_rect.right - 15
        arrow_width = 8
        arrow_height = 8
        arrow_color = (180, 180, 180)

        # --- Draw UP arrow at the TOP if scrolling UP is possible ---
        if self.scroll_offset < max_scroll:
            # --- Draw the UP-pointing shape here ---
            tip_y = text_area_rect.top + 5
            base_y = tip_y + arrow_height
            arrow_points_up = [
                (arrow_x, tip_y),       # Top point
                (arrow_x - arrow_width, base_y), # Bottom left base
                (arrow_x + arrow_width, base_y)  # Bottom right base
            ]
            pygame.draw.polygon(self.screen, arrow_color, arrow_points_up)

        # --- Draw DOWN arrow at the BOTTOM if scrolling DOWN is possible ---
        if self.scroll_offset > 0:        
            # --- Draw the DOWN-pointing shape here ---
            tip_y = text_area_rect.bottom - 5
            base_y = tip_y - arrow_height
            arrow_points_down = [
                 (arrow_x, tip_y),      # Bottom point (tip)
                 (arrow_x - arrow_width, base_y), # Top left base
                 (arrow_x + arrow_width, base_y)  # Top right base
            ]
            pygame.draw.polygon(self.screen, arrow_color, arrow_points_down)

    def _calculate_layout(self):
        """Recalculates UI element positions with left and right side panels."""
        current_width, current_height = self.screen.get_size()

        # --- Read Config / Defaults ---
        # Use the imported config value, provide a fallback default
        side_panel_width = SIDE_PANEL_WIDTH # Directly use imported value
        padding = STATUS_PANEL_PADDING # Use config padding

        time_bar_height = 30
        input_area_height = INPUT_HEIGHT
        margin = self.text_formatter.margin # Use formatter's margin

        # --- Vertical Boundaries ---
        time_bar_y = 0
        input_area_y = current_height - input_area_height
        panels_top_y = time_bar_y + time_bar_height + margin
        panels_bottom_y = input_area_y - margin
        panels_available_height = max(50, panels_bottom_y - panels_top_y) # Min height 50

        # --- Left Status Panel (NEW) ---
        left_panel_x = margin
        left_panel_rect = pygame.Rect(
            left_panel_x, panels_top_y,
            side_panel_width, panels_available_height
        )

        # --- Right Status Panel (Adjusted) ---
        right_panel_x = current_width - side_panel_width - margin
        right_panel_rect = pygame.Rect(
            right_panel_x, panels_top_y,
            side_panel_width, panels_available_height
        )

        # --- Center Area Calculation ---
        center_area_x_start = left_panel_rect.right + margin
        center_area_x_end = right_panel_rect.left - margin
        center_area_width = max(100, center_area_x_end - center_area_x_start) # Min width 100

        # --- Define Target Heights (Same as before) ---
        target_room_panel_height = 300
        min_text_area_height = 100

        # --- Calculate Actual Room Panel Height (Same as before) ---
        max_possible_room_height = panels_available_height - margin - min_text_area_height
        actual_room_panel_height = min(target_room_panel_height, max_possible_room_height)
        actual_room_panel_height = max(30, actual_room_panel_height)

        # --- Room Info Panel (Top Center) ---
        room_panel_x = center_area_x_start # Start after left panel + margin
        room_panel_rect = pygame.Rect(
            room_panel_x, panels_top_y, # Align top with side panels
            center_area_width, actual_room_panel_height
        )

        # --- Text Area (Bottom Center) ---
        text_area_x = center_area_x_start
        text_area_y = room_panel_rect.bottom + margin
        text_area_width = center_area_width
        # Calculate height to fill remaining space in center column
        text_area_height = panels_bottom_y - text_area_y
        text_area_height = max(min_text_area_height, text_area_height)
        text_area_rect = pygame.Rect(
            text_area_x, text_area_y,
            text_area_width, text_area_height
        )

        # Update TextFormatter's usable width for the main text area
        self.text_formatter.update_screen_width(text_area_width)

        # Store Layout
        self.layout = {
            "screen_width": current_width,
            "screen_height": current_height,
            "time_bar": {"height": time_bar_height, "y": time_bar_y},
            "input_area": {"height": input_area_height, "y": input_area_y},
            "left_status_panel": { # <<< NEW
                "x": left_panel_rect.x, "y": left_panel_rect.y,
                "width": left_panel_rect.width, "height": left_panel_rect.height
            },
            "right_status_panel": { # <<< RENAMED
                "x": right_panel_rect.x, "y": right_panel_rect.y,
                "width": right_panel_rect.width, "height": right_panel_rect.height
            },
            "room_info_panel": { # Positioned Top-Center
                "x": room_panel_rect.x, "y": room_panel_rect.y,
                "width": room_panel_rect.width, "height": room_panel_rect.height
            },
            "text_area": {      # Positioned Bottom-Center
                "x": text_area_rect.x, "y": text_area_rect.y,
                "width": text_area_rect.width, "height": text_area_rect.height
            }
        }

    def _draw_room_info_panel(self):
        """Draws the panel showing current room info, with inline, wrapping lists."""
        # --- Initial Checks ---
        if not self.world: print("Debug Draw Room Panel: World object missing!"); return
        if not self.layout: print("Debug Draw Room Panel: Layout not calculated!"); return

        room_panel_layout = self.layout.get("room_info_panel")
        if not room_panel_layout: print("Error: Room info panel layout missing."); return

        panel_rect = pygame.Rect(
            room_panel_layout["x"], room_panel_layout["y"],
            room_panel_layout["width"], room_panel_layout["height"]
        )

        # Draw background/border
        pygame.draw.rect(self.screen, (15, 15, 15), panel_rect) # Darker background
        pygame.draw.rect(self.screen, (70, 70, 70), panel_rect, 1)

        padding = 5
        start_y = panel_rect.y + padding
        current_y = start_y
        max_y = panel_rect.bottom - padding
        section_spacing = self.text_formatter.line_height_with_text // 2
        line_height_needed = self.text_formatter.line_height_with_text # Store once

        current_room = self.world.get_current_room()
        if not current_room: print("Debug Draw Room Panel: Current room not found!"); return

        # --- Store original formatter width ---
        original_formatter_width = self.text_formatter.usable_width
        panel_usable_width = panel_rect.width - padding * 2
        panel_usable_width = max(1, panel_usable_width) # Ensure width is at least 1

        # --- 1. Render Main Room Description ---
        time_period = self.time_data.get("time_period", "day")
        weather = self.world.get_plugin_data("weather_plugin", "current_weather", "clear")
        room_description_text = current_room.get_full_description(time_period, weather)
        render_position = (panel_rect.x + padding, current_y)
        render_max_height_desc = max_y - current_y

        y_after_desc = current_y
        if render_max_height_desc > 0:
            self.text_formatter.update_screen_width(panel_usable_width)
            y_after_desc = self.text_formatter.render(
                self.screen, room_description_text, render_position, max_height=render_max_height_desc
            )
        else:
            # Not enough space even for the description
            pass # Skip rendering description

        current_y = y_after_desc
        current_y += section_spacing

        # --- 2. Prepare Items Line ---
        items_in_room = self.world.get_items_in_current_room()
        full_items_line = ""
        if items_in_room:
            # --- Group Items (same logic as before) ---
            item_counts: Dict[str, Dict[str, Any]] = {}
            for item in items_in_room:
                item_id = item.obj_id
                item_counts.setdefault(item_id, {"name": item.name, "count": 0})["count"] += 1
            items_text_parts = []
            # Sort items alphabetically for consistent display
            for item_id, data in sorted(item_counts.items(), key=lambda item: item[1]['name']):
                base_name = data["name"]
                count = data["count"]
                # Apply category formatting to the item name
                formatted_name = f"{FORMAT_CATEGORY}{base_name}{FORMAT_RESET}"
                if count == 1:
                    items_text_parts.append(f"{get_article(base_name)} {formatted_name}")
                else:
                    plural_base_name = simple_plural(base_name)
                    formatted_plural_name = f"{FORMAT_CATEGORY}{plural_base_name}{FORMAT_RESET}"
                    items_text_parts.append(f"{count} {formatted_plural_name}")
            # --- End Grouping ---
            items_list_str = ", ".join(items_text_parts)
            # Add the label *inside* the string to be rendered/wrapped
            full_items_line = f"{FORMAT_CATEGORY}Items:{FORMAT_RESET} {items_list_str}"
        else:
            full_items_line = f"{FORMAT_CATEGORY}Items:{FORMAT_RESET} {FORMAT_GRAY}(None){FORMAT_RESET}"

        # --- Render Items Section (using TextFormatter) ---
        render_max_height_items = max_y - current_y
        y_after_items = current_y
        if render_max_height_items >= line_height_needed: # Check if there's space for at least one line
            render_position_items = (panel_rect.x + padding, current_y)
            self.text_formatter.update_screen_width(panel_usable_width)
            # Pass the full line (including label) to render
            y_after_items = self.text_formatter.render(
                self.screen, full_items_line, render_position_items, max_height=render_max_height_items
            )
        else:
            # Not enough space to render the items section
            pass

        current_y = y_after_items
        current_y += section_spacing

        # --- 3. Prepare NPCs Line ---
        npcs_in_room = self.world.get_current_room_npcs()
        full_npc_line = ""
        if npcs_in_room:
            # Format each NPC name individually using the helper
            npc_text_parts = [format_name_for_display(self.world.player, npc, False) for npc in npcs_in_room]
            npc_list_str = ", ".join(npc_text_parts)
            # Add the label *inside* the string to be rendered/wrapped
            full_npc_line = f"{FORMAT_CATEGORY}Also here:{FORMAT_RESET} {npc_list_str}"
        else:
            full_npc_line = f"{FORMAT_CATEGORY}Also here:{FORMAT_RESET} {FORMAT_GRAY}(None){FORMAT_RESET}"

        # --- Render NPCs Section (using TextFormatter) ---
        render_max_height_npcs = max_y - current_y
        y_after_npcs = current_y
        if render_max_height_npcs >= line_height_needed: # Check if there's space for at least one line
            render_position_npcs = (panel_rect.x + padding, current_y)
            self.text_formatter.update_screen_width(panel_usable_width)
            # Pass the full line (including label) to render
            y_after_npcs = self.text_formatter.render(
                self.screen, full_npc_line, render_position_npcs, max_height=render_max_height_npcs
            )
        else:
            # Not enough space to render the NPCs section
            pass

        # --- Restore Formatter Width AFTER ALL panel rendering ---
        self.text_formatter.update_screen_width(original_formatter_width)

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
        # --- MODIFIED: Update total number of options correctly ---
        num_saves = len(self.available_saves)
        num_options = num_saves + 1 # Saves + Back button
        max_display_items = 10 # Or use calculated displayable_count if needed here

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.selected_load_option = (self.selected_load_option - 1 + num_options) % num_options
            elif event.key == pygame.K_DOWN:
                self.selected_load_option = (self.selected_load_option + 1) % num_options
            elif event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                # Check if 'Back' was selected (index is num_saves)
                if self.selected_load_option == num_saves:
                    self.game_state = "title_screen"
                # Check if a valid save file index was selected
                elif self.available_saves and 0 <= self.selected_load_option < num_saves:
                    self._load_selected_game()
                # Else: No saves available, Enter does nothing
            elif event.key == pygame.K_ESCAPE: # Escape also goes back
                 self.game_state = "title_screen"
            # --- Add PageUp/PageDown scrolling ---
            elif event.key == pygame.K_PAGEUP:
                 self.load_scroll_offset = max(0, self.load_scroll_offset - max_display_items)
                 # Optional: Adjust selection to stay within view?
                 self.selected_load_option = max(self.load_scroll_offset, min(self.selected_load_option, self.load_scroll_offset + max_display_items - 1))
            elif event.key == pygame.K_PAGEDOWN:
                 self.load_scroll_offset = min(max(0, num_saves - max_display_items), self.load_scroll_offset + max_display_items)
                 # Optional: Adjust selection
                 self.selected_load_option = max(self.load_scroll_offset, min(self.selected_load_option, self.load_scroll_offset + max_display_items - 1))
            # --- End PageUp/PageDown ---


        # --- Adjust scroll offset based on selection ---
        # (Ensure selected item is visible - logic needs refinement based on displayable_count)
        list_area_height = self.layout["screen_height"] - (self.title_font.get_height() + 90) - 80 # Approximate list height
        option_spacing = 30
        displayable_count = max(1, list_area_height // option_spacing)
        displayable_count = min(displayable_count, max_display_items)

        visible_start_index = self.load_scroll_offset
        visible_end_index = self.load_scroll_offset + displayable_count - 1

        # If selection moved above the visible area, scroll up
        if self.selected_load_option < visible_start_index:
            self.load_scroll_offset = self.selected_load_option
        # If selection moved below the visible area, scroll down
        elif self.selected_load_option > visible_end_index and self.selected_load_option < num_saves: # Don't scroll down if Back is selected
            self.load_scroll_offset = self.selected_load_option - displayable_count + 1

        # Clamp scroll offset to valid range
        self.load_scroll_offset = max(0, min(self.load_scroll_offset, max(0, num_saves - displayable_count)))
        # Ensure selected option is valid after scrolling adjustment
        self.selected_load_option = max(0, min(self.selected_load_option, num_options - 1))

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
            scroll_amount_pixels = SCROLL_SPEED * self.text_formatter.line_height_with_text * event.y # y is -1 or 1
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

    def _draw_left_status_panel(self):
        """Draws the left panel showing player Stats, Skills, and Spells."""
        if not self.world or not self.world.player: return

        player = self.world.player
        panel_layout = self.layout.get("left_status_panel")
        if not panel_layout: print("Error: Left status panel layout missing."); return

        panel_rect = pygame.Rect(
            panel_layout["x"], panel_layout["y"],
            panel_layout["width"], panel_layout["height"]
        )

        # Draw background/border
        pygame.draw.rect(self.screen, (20, 20, 20), panel_rect)
        pygame.draw.rect(self.screen, (80, 80, 80), panel_rect, 1)

        padding = STATUS_PANEL_PADDING
        line_height = self.text_formatter.line_height_with_text
        current_y = panel_rect.y + padding
        max_y = panel_rect.bottom - padding
        section_spacing = line_height // 2 # Smaller spacing between sections
        col_spacing = 20
        text_color_tuple = DEFAULT_COLORS.get(FORMAT_RESET, TEXT_COLOR)
        title_color_tuple = DEFAULT_COLORS.get(FORMAT_TITLE, (255, 255, 0))
        gray_color_tuple = DEFAULT_COLORS.get(FORMAT_GRAY, (128, 128, 128))
        error_color_tuple = DEFAULT_COLORS.get(FORMAT_ERROR, (255, 0, 0)) # For cooldown

        # --- 1. Stats Section ---
        if current_y + line_height <= max_y:
            title_surface = self.font.render("STATS", True, title_color_tuple)
            self.screen.blit(title_surface, (panel_rect.x + padding, current_y))
            current_y += line_height
        # ... (Stats rendering code remains the same) ...
        # --- Arrange Stats in Columns ---
        stats_to_show = {
            "strength": "STR", "dexterity": "DEX", "constitution": "CON",
            "agility": "AGI", "intelligence": "INT", "wisdom": "WIS",
            "spell_power": "SP", "magic_resist": "MR"
        }
        num_stats = len(stats_to_show)
        stats_per_col = math.ceil(num_stats / 2)

        col1_x = panel_rect.x + padding + 5
        col2_x = col1_x + (panel_rect.width - padding*2 - col_spacing) // 2 # Adjusted calculation slightly

        stat_items = list(stats_to_show.items())
        col1_y = current_y
        col2_y = current_y

        for i, (stat_key, stat_abbr) in enumerate(stat_items):
            if max(col1_y, col2_y) >= max_y: break # Check combined height

            stat_value = player.stats.get(stat_key, 0)
            stat_text = f"{stat_abbr}: {stat_value}"
            stat_surface = self.font.render(stat_text, True, text_color_tuple)

            if i < stats_per_col:
                if col1_y + line_height <= max_y:
                    self.screen.blit(stat_surface, (col1_x, col1_y))
                    col1_y += line_height
            else:
                if col2_y + line_height <= max_y:
                    self.screen.blit(stat_surface, (col2_x, col2_y))
                    col2_y += line_height

        current_y = max(col1_y, col2_y) # Set Y below the stats
        current_y += section_spacing # Add space after stats

        # --- 2. Skills Section ---
        if current_y + line_height <= max_y: # Check space for title
            title_surface = self.font.render("SKILLS", True, title_color_tuple)
            self.screen.blit(title_surface, (panel_rect.x + padding, current_y))
            current_y += line_height

        if player.skills:
            sorted_skills = sorted(player.skills.items())
            skills_rendered = 0
            for skill_name, level in sorted_skills:
                if current_y + line_height > max_y: # Check space for skill line
                    if current_y <= max_y - line_height // 2 :
                        more_surf = self.font.render("...", True, gray_color_tuple)
                        self.screen.blit(more_surf, (panel_rect.x + padding + 5, current_y))
                        current_y += line_height
                    break
                skill_text = f"- {skill_name.capitalize()}: {level}"
                skill_surface = self.font.render(skill_text, True, text_color_tuple)
                self.screen.blit(skill_surface, (panel_rect.x + padding + 5, current_y))
                current_y += line_height
                skills_rendered += 1
        else:
             if current_y + line_height <= max_y: # Check space for "None"
                none_surface = self.font.render("(None known)", True, gray_color_tuple)
                self.screen.blit(none_surface, (panel_rect.x + padding + 5, current_y))
                current_y += line_height

        current_y += section_spacing # Space after skills

        # --- 3. Spells Known Section (NEW) ---
        if current_y + line_height <= max_y: # Check space for title
            title_surface = self.font.render("SPELLS", True, title_color_tuple)
            self.screen.blit(title_surface, (panel_rect.x + padding, current_y))
            current_y += line_height

        if player.known_spells:
            sorted_spells = sorted(list(player.known_spells), key=lambda sid: getattr(get_spell(sid), 'name', sid))
            spells_rendered = 0
            max_spells_to_show = 5 # Limit displayed spells if needed
            current_time_abs = time.time() # Get current time once

            for spell_id in sorted_spells:
                if spells_rendered >= max_spells_to_show or current_y + line_height > max_y:
                    if len(sorted_spells) > spells_rendered and current_y <= max_y - line_height // 2:
                        more_surf = self.font.render("...", True, gray_color_tuple)
                        self.screen.blit(more_surf, (panel_rect.x + padding + 5, current_y))
                        current_y += line_height
                    break # Stop rendering spells

                spell = get_spell(spell_id)
                if spell:
                    # Cooldown check
                    cooldown_end = player.spell_cooldowns.get(spell_id, 0)
                    cd_status = ""
                    cd_color = text_color_tuple # Default color
                    if current_time_abs < cooldown_end:
                        time_left = cooldown_end - current_time_abs
                        cd_status = f" (CD {time_left:.1f}s)"
                        cd_color = error_color_tuple # Use error color for cooldown text

                    # Format spell line
                    spell_text = f"- {spell.name} ({spell.mana_cost} MP)"
                    spell_surface = self.font.render(spell_text, True, text_color_tuple)
                    # Render cooldown status separately if present, using its specific color
                    if cd_status:
                        cd_surface = self.font.render(cd_status, True, cd_color)
                        # Blit spell name first
                        self.screen.blit(spell_surface, (panel_rect.x + padding + 5, current_y))
                        # Blit cooldown status immediately after
                        self.screen.blit(cd_surface, (panel_rect.x + padding + 5 + spell_surface.get_width(), current_y))
                    else:
                        # Blit only the spell name/cost if no cooldown
                        self.screen.blit(spell_surface, (panel_rect.x + padding + 5, current_y))

                    current_y += line_height
                    spells_rendered += 1
                else:
                    # Handle case where spell definition might be missing
                    missing_text = f"- {spell_id} (Error!)"
                    missing_surface = self.font.render(missing_text, True, error_color_tuple)
                    self.screen.blit(missing_surface, (panel_rect.x + padding + 5, current_y))
                    current_y += line_height
                    spells_rendered += 1
        else:
            if current_y + line_height <= max_y: # Check space for "None"
                none_surface = self.font.render("(None known)", True, gray_color_tuple)
                self.screen.blit(none_surface, (panel_rect.x + padding + 5, current_y))
                current_y += line_height
        # No extra spacing needed after the last section

    def _draw_right_status_panel(self):
        """Draws the panel showing prioritized player status information."""
        if not self.world or not self.world.player:
            return

        player = self.world.player
        panel_layout = self.layout.get("right_status_panel")
        if not panel_layout:
            print("Error: Right status panel layout missing.")
            return

        panel_rect = pygame.Rect(
            panel_layout["x"], panel_layout["y"],
            panel_layout["width"], panel_layout["height"]
        )

        # Draw background/border
        pygame.draw.rect(self.screen, (20, 20, 20), panel_rect)
        pygame.draw.rect(self.screen, (80, 80, 80), panel_rect, 1)

        padding = 5
        line_height = self.text_formatter.line_height_with_text
        current_y = panel_rect.y + padding
        max_y = panel_rect.bottom - padding # Maximum Y coordinate for rendering content
        section_spacing = line_height // 2 # Reduced spacing between sections
        bar_spacing = 3

        # --- Draw Bars and Text ---
        bar_height = 10
        # Estimate max label width based on HP as it's usually the longest
        bar_label_width = self.font.size("HP: 9999/9999")[0]
        max_bar_width = max(20, panel_layout["width"] - (padding * 3) - bar_label_width)
        bar_x = panel_rect.x + padding

        # --- Health Bar ---
        if current_y + bar_height <= max_y:
            hp_text = f"HP: {int(player.health)}/{int(player.max_health)}"
            hp_percent = player.health / player.max_health if player.max_health > 0 else 0
            hp_color_code = FORMAT_SUCCESS
            if hp_percent <= PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD / 100: hp_color_code = FORMAT_ERROR
            elif hp_percent <= PLAYER_STATUS_HEALTH_LOW_THRESHOLD / 100: hp_color_code = FORMAT_YELLOW
            bar_fill_color = DEFAULT_COLORS.get(hp_color_code, DEFAULT_COLORS[FORMAT_SUCCESS])
            pygame.draw.rect(self.screen, (80, 0, 0), (bar_x, current_y, max_bar_width, bar_height))
            filled_width = int(max_bar_width * hp_percent)
            pygame.draw.rect(self.screen, bar_fill_color, (bar_x, current_y, filled_width, bar_height))
            hp_surface = self.font.render(hp_text, True, bar_fill_color)
            self.screen.blit(hp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (hp_surface.get_height() // 2)))
            current_y += bar_height + bar_spacing

        # --- Mana Bar ---
        if current_y + bar_height <= max_y:
            mp_text = f"MP: {int(player.mana)}/{int(player.max_mana)}"
            mp_percent = player.mana / player.max_mana if player.max_mana > 0 else 0
            bar_fill_color = DEFAULT_COLORS[FORMAT_BLUE]
            pygame.draw.rect(self.screen, (0, 0, 80), (bar_x, current_y, max_bar_width, bar_height))
            filled_width = int(max_bar_width * mp_percent)
            pygame.draw.rect(self.screen, bar_fill_color, (bar_x, current_y, filled_width, bar_height))
            mp_surface = self.font.render(mp_text, True, bar_fill_color)
            self.screen.blit(mp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (mp_surface.get_height() // 2)))
            current_y += bar_height + bar_spacing # Keep bar spacing

        # --- Experience Bar --- (Optional, can be removed if space is very tight)
        if current_y + bar_height <= max_y:
            xp_text = f"XP: {int(player.experience)}/{int(player.experience_to_level)}"
            xp_percent = player.experience / player.experience_to_level if player.experience_to_level > 0 else 0
            bar_fill_color = DEFAULT_COLORS[FORMAT_ORANGE]
            pygame.draw.rect(self.screen, (80, 40, 0), (bar_x, current_y, max_bar_width, bar_height))
            filled_width = int(max_bar_width * min(1.0, xp_percent))
            pygame.draw.rect(self.screen, bar_fill_color, (bar_x, current_y, filled_width, bar_height))
            xp_surface = self.font.render(xp_text, True, bar_fill_color)
            self.screen.blit(xp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (xp_surface.get_height() // 2)))
            current_y += bar_height + padding # Standard padding after last bar

        # --- Basic Info Section ---
        if current_y < max_y:
            current_y = self.text_formatter.render(self.screen, f"{FORMAT_TITLE}{player.name}{FORMAT_RESET}", (panel_rect.x + padding, current_y), max_height=(max_y - current_y))
        if current_y < max_y:
            level_surface = self.font.render(f"Level: {player.level}", True, TEXT_COLOR)
            self.screen.blit(level_surface, (panel_rect.x + padding, current_y))
            current_y += line_height
        if current_y < max_y:
            current_y = self.text_formatter.render(self.screen, f"Gold: {FORMAT_YELLOW}{player.gold}{FORMAT_RESET}", (panel_rect.x + padding, current_y), max_height=(max_y - current_y))
        # Use slightly more spacing after basic info before equipment
        current_y += line_height # Changed from section_spacing

        # --- Equipment Section ---
        title_rendered_equipment = False
        if current_y + line_height <= max_y: # Check for title space
            title_surface = self.font.render("EQUIPPED", True, DEFAULT_COLORS[FORMAT_TITLE])
            self.screen.blit(title_surface, (panel_rect.x + padding, current_y))
            current_y += line_height
            title_rendered_equipment = True

        if title_rendered_equipment:
            # Helper function (essential for concise equipment display)
            def format_equip_slot(slot_abbr: str, item: Optional[Item]) -> str:
                if not item: return f"{slot_abbr}: {FORMAT_GRAY}(Empty){FORMAT_RESET}"
                durability_str = ""
                max_durability = item.get_property("max_durability", 0); current_durability = item.get_property("durability", max_durability)
                if max_durability > 0:
                    ratio = current_durability / max_durability if max_durability else 0; dura_color = FORMAT_SUCCESS
                    if ratio <= 0.1: dura_color = FORMAT_ERROR
                    elif ratio <= ITEM_DURABILITY_LOW_THRESHOLD: dura_color = FORMAT_YELLOW
                    durability_str = f" [{dura_color}{int(current_durability)}/{int(max_durability)}{FORMAT_RESET}]"

                est_char_width = self.font.size("A")[0] if self.font else 8
                # Slightly increase allowed chars as panel might be wider than half screen now
                max_name_chars = max(8, (panel_layout["width"] // est_char_width) - len(slot_abbr) - len(self.text_formatter.remove_format_codes(durability_str)) - 7)
                item_name_display = item.name
                if len(item_name_display) > max_name_chars: item_name_display = item_name_display[:max_name_chars-3] + "..."
                return f"{slot_abbr}: {item_name_display}{durability_str}"

            slot_abbrs = {"main_hand": "MH", "off_hand": "OH", "head": "Hd", "body": "Bd", "hands": "Hn", "feet": "Ft", "neck": "Nk"}
            # Display fewer slots if needed, prioritize main/off/body/head?
            slots_to_display = ["main_hand", "off_hand", "head", "body", "hands", "feet", "neck"]

            for slot_key in slots_to_display:
                if current_y >= max_y: break # Height check before render
                item = player.equipment.get(slot_key)
                abbr = slot_abbrs.get(slot_key, slot_key[:2].upper())
                line_part = format_equip_slot(abbr, item)
                combined_line = f"- {line_part}"
                # Render equipment line, handling format codes
                current_y = self.text_formatter.render(self.screen, combined_line, (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y)) # Indent content slightly

            current_y += section_spacing # Space after equipment

        # --- Effects Section ---
        title_rendered_effects = False
        if current_y + line_height <= max_y:
            title_surface = self.font.render("EFFECTS", True, DEFAULT_COLORS[FORMAT_TITLE])
            self.screen.blit(title_surface, (panel_rect.x + padding, current_y))
            current_y += line_height
            title_rendered_effects = True

        if title_rendered_effects:
            if player.active_effects:
                sorted_effects = sorted(player.active_effects, key=lambda e: e.get("name", "zzz"))
                effects_shown = 0
                max_effects_to_show = 3 # Limit number of effects shown
                for effect in sorted_effects:
                    if effects_shown >= max_effects_to_show or current_y + line_height > max_y:
                        # If more effects exist but aren't shown, add an indicator
                        if len(sorted_effects) > effects_shown and current_y + line_height <= max_y:
                            more_surface = self.font.render("  ...", True, DEFAULT_COLORS[FORMAT_GRAY])
                            self.screen.blit(more_surface, (panel_rect.x + padding + 5, current_y))
                            current_y += line_height
                        break

                    name = effect.get('name', 'Unknown'); duration = effect.get('duration_remaining', 0)
                    duration_str = f"{duration:.1f}s" if duration < 60 else f"{duration/60:.1f}m"
                    effect_line_text = f"- {name} ({duration_str})"
                    effect_surface = self.font.render(effect_line_text, True, TEXT_COLOR)
                    self.screen.blit(effect_surface, (panel_rect.x + padding + 5, current_y))
                    current_y += line_height
                    effects_shown += 1
            else:
                if current_y + line_height <= max_y:
                    none_surface = self.font.render("(None)", True, DEFAULT_COLORS[FORMAT_GRAY])
                    self.screen.blit(none_surface, (panel_rect.x + padding + 5, current_y))
                    current_y += line_height

            current_y += section_spacing

        # --- REMOVED SPELLS SECTION ---

        # --- REMOVED QUESTS SECTION ---

        # --- Combat Targets Section ---
        title_rendered_targets = False
        # Only show targets if actively in combat
        if player.in_combat and player.combat_targets:
            if current_y + line_height <= max_y:
                title_surface = self.font.render("TARGETS", True, DEFAULT_COLORS[FORMAT_TITLE])
                self.screen.blit(title_surface, (panel_rect.x + padding, current_y))
                current_y += line_height
                title_rendered_targets = True

            if title_rendered_targets:
                valid_targets = [t for t in player.combat_targets if hasattr(t, 'is_alive') and t.is_alive]
                if valid_targets:
                    from utils.text_formatter import format_target_name
                    targets_shown = 0
                    max_targets_to_show = 3 # Limit displayed targets
                    for target in valid_targets:
                        if targets_shown >= max_targets_to_show or current_y >= max_y:
                            if len(valid_targets) > targets_shown and current_y + line_height <= max_y:
                                    more_surface = self.font.render("  ...", True, DEFAULT_COLORS[FORMAT_GRAY])
                                    self.screen.blit(more_surface, (panel_rect.x + padding + 5, current_y))
                                    current_y += line_height
                            break

                        formatted_target_name = format_target_name(player, target)
                        hp_str = ""
                        if hasattr(target, 'health') and hasattr(target, 'max_health') and target.max_health > 0:
                                health_percent = (target.health / target.max_health) * 100
                                hp_color = FORMAT_SUCCESS
                                if health_percent <= 25: hp_color = FORMAT_ERROR
                                elif health_percent <= 50: hp_color = FORMAT_HIGHLIGHT
                                hp_str = f" ({hp_color}{int(target.health)}/{int(target.max_health)}{FORMAT_RESET})"

                        target_line_text = f"- {formatted_target_name}{hp_str}"
                        current_y = self.text_formatter.render(self.screen, target_line_text, (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y))
                        targets_shown += 1
                else: # No valid targets despite being in combat? Render (None).
                    if current_y + line_height <= max_y:
                        none_surface = self.font.render("(None)", True, DEFAULT_COLORS[FORMAT_GRAY])
                        self.screen.blit(none_surface, (panel_rect.x + padding + 5, current_y))
                        current_y += line_height
                # No extra spacing needed at the very end
