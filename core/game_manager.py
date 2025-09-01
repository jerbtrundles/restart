# core/game_manager.py
# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Added defensive "guard clauses" in handle_input() and handle_respawn()
#   to safely handle cases where self.world.player might be None, preventing crashes.
# - Refined the logic in handle_input() to allow dead players to use a
#   whitelist of essential commands (look, status, help, quit, etc.).

import math
import time
import pygame
import sys
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from core.config import (
    BG_COLOR, DEBUG_COLOR, DEBUG_SHOW_LEVEL, DEFAULT_COLORS, FONT_FAMILY, FONT_SIZE, FORMAT_BLUE, FORMAT_CYAN, FORMAT_ERROR, FORMAT_GRAY,
    FORMAT_HIGHLIGHT, FORMAT_ORANGE, FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, FORMAT_YELLOW, GAME_OVER_MESSAGE_LINE1,
    GAME_OVER_MESSAGE_LINE2, INPUT_BG_COLOR, INPUT_HEIGHT, LINE_SPACING, MAX_BUFFER_LINES,
    PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD, PLAYER_STATUS_HEALTH_LOW_THRESHOLD, SAVE_GAME_DIR,
    SCREEN_HEIGHT, SCREEN_WIDTH, SCROLL_SPEED, SIDE_PANEL_WIDTH, STATUS_PANEL_PADDING, TARGET_FPS,
    TEXT_COLOR
)
from commands.command_system import CommandProcessor
from magic.spell_registry import get_spell
from plugins.plugin_system import PluginManager
from items.item import Item
from utils.text_formatter import TextFormatter, format_target_name
from world.world import World

if TYPE_CHECKING:
    from player import Player

class GameManager:
    def __init__(self, save_file: str = "default_save.json"):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE, bold=False)
        self.title_font = pygame.font.SysFont(FONT_FAMILY, int(FONT_SIZE * 1.5), bold=True)
        self.selected_font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE, bold=True)
        self.clock = pygame.time.Clock()
        self.current_save_file = save_file
        self.status_panel_width = SIDE_PANEL_WIDTH

        self.text_formatter = TextFormatter(
            font=self.font, screen_width=SCREEN_WIDTH,
            colors=DEFAULT_COLORS, margin=10, line_spacing=LINE_SPACING
        )
        
        self.world = World()
        self.world.game = self
        self.command_processor = CommandProcessor()

        self.plugin_manager: Optional[PluginManager] = None
        self.game_state = "title_screen"

        self.title_options = ["New Game", "Load Game", "Quit"]
        self.selected_title_option = 0
        self.available_saves: List[str] = []
        self.selected_load_option = 0
        self.load_scroll_offset = 0

        self.text_buffer: List[str] = []
        self.input_text = ""
        self.cursor_visible = True; self.cursor_timer = 0
        self.command_history = []; self.history_index = -1
        self.tab_completion_buffer = ""; self.tab_suggestions = []; self.tab_index = -1
        self.scroll_offset = 0
        self.total_rendered_height = 0
        self.debug_mode = False
        self.layout: Dict[str, Any] = {}

        self.time_data = {
            "hour": 12, "minute": 0, "day": 1, "month": 1, "year": 1,
            "day_name": "Moonday", "month_name": "Deepwinter", "season": "winter",
            "time_period": "day", "time_str": "12:00",
            "date_str": "Moonday, 1 Deepwinter, Year 1"
        }

    def _initialize_gameplay_systems(self):
        """Initializes plugins and systems needed only during active gameplay."""
        self.plugin_manager = PluginManager(self.world, self.command_processor)
        self.plugin_manager.event_system.subscribe("display_message", self._on_display_message)
        self.plugin_manager.event_system.subscribe("time_data", self._on_time_data_event)
        self.plugin_manager.event_system.subscribe("time_period_changed", self._on_time_period_changed)
        self.plugin_manager.load_all_plugins()

        time_plugin = self.plugin_manager.get_plugin("time_plugin")
        if time_plugin: time_plugin._update_world_time_data()
        weather_plugin = self.plugin_manager.get_plugin("weather_plugin")
        if weather_plugin: weather_plugin._notify_weather_change()

    def _shutdown_gameplay_systems(self):
        """Unloads plugins and resets gameplay state when returning to title."""
        if self.plugin_manager:
            if self.plugin_manager.event_system:
                self.plugin_manager.event_system.unsubscribe("display_message", self._on_display_message)
                self.plugin_manager.event_system.unsubscribe("time_data", self._on_time_data_event)
                self.plugin_manager.event_system.unsubscribe("time_period_changed", self._on_time_period_changed)
            self.plugin_manager.unload_all_plugins()
        self.plugin_manager = None
        self.text_buffer = []; self.scroll_offset = 0; self.total_rendered_height = 0
        self.input_text = ""; self.command_history = []; self.history_index = -1

    def handle_input(self, text: str) -> str:
        """Process a command from the user, now with a safety check for the player object."""
        self.text_buffer.append(f"> {text}")
        self._trim_text_buffer()

        if text.strip():
            self.command_history.append(text)
            self.history_index = -1

            context = { "game": self, "world": self.world, "command_processor": self.command_processor, "current_save_file": self.current_save_file }
            command_result = ""
            
            player = self.world.player
            if not player:
                command_result = f"{FORMAT_ERROR}CRITICAL ERROR: Player is missing. Please load a game.{FORMAT_RESET}"
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
                self.text_buffer.append(self._sanitize_text(command_result))
                self._trim_text_buffer()

            self.scroll_offset = 0
            self.input_text = ""
        else:
            self.input_text = ""
        return ""

    def handle_respawn(self):
        """Handles the player respawn logic, now with a safety check."""
        if self.game_state != "game_over": return

        player = self.world.player
        if not player:
            print(f"{FORMAT_ERROR}CRITICAL: handle_respawn was called, but player object is None! Returning to title.{FORMAT_RESET}")
            self._shutdown_gameplay_systems()
            self.game_state = "title_screen"
            return

        player.respawn()
        self.world.current_region_id = player.respawn_region_id
        self.world.current_room_id = player.respawn_room_id

        self.text_buffer = [f"{FORMAT_HIGHLIGHT}You feel your spirit return to your body...{FORMAT_RESET}\n"]
        self.text_buffer.append(self.world.look())

        self.game_state = "playing"
        self.input_text = ""
        
    def _on_time_data_event(self, event_type: str, data: dict) -> None:
        if isinstance(data, dict): self.time_data = data.copy()
        else: print(f"Warning: Received invalid time_data event: {data}")

    def _start_new_game(self):
        self.world.initialize_new_world()
        if self.world.player:
            self._initialize_gameplay_systems()
            self.game_state = "playing"
            welcome_message = f"{FORMAT_TITLE}Welcome to Pygame MUD!{FORMAT_RESET}\n(Started new game)\nType 'help' to see available commands.\n\n{'='*40}\n\n{self.world.look()}"
            self.text_buffer.append(self._sanitize_text(welcome_message))
            self._trim_text_buffer()
            self.scroll_offset = 0
        else:
            print(f"{FORMAT_ERROR}Failed to initialize new world properly! Returning to title.{FORMAT_RESET}")
            self.game_state = "title_screen"

    def _load_selected_game(self):
        if self.selected_load_option < 0 or self.selected_load_option >= len(self.available_saves): return
        save_to_load = self.available_saves[self.selected_load_option]
        load_success = self.world.load_save_game(save_to_load)
        if load_success and self.world.player:
            self.current_save_file = save_to_load
            self._initialize_gameplay_systems()
            self.game_state = "playing"
            welcome_message = f"{FORMAT_TITLE}Welcome back to Pygame MUD!{FORMAT_RESET}\n(Loaded game: {self.current_save_file})\n\n{'='*40}\n\n{self.world.look()}"
            self.text_buffer.append(self._sanitize_text(welcome_message))
            self._trim_text_buffer()
            self.scroll_offset = 0
        else:
            print(f"{FORMAT_ERROR}Failed to load save game '{save_to_load}'. Returning to title screen.{FORMAT_RESET}")
            self.world = World(); self.world.game = self; self.world._load_definitions()
            self.game_state = "title_screen"

    def update(self):
        if self.game_state == "game_over":
            self.cursor_timer += self.clock.get_time()
            if self.cursor_timer >= 500: self.cursor_visible = not self.cursor_visible; self.cursor_timer = 0
            return

        current_time_abs = time.time()
        elapsed_real_time_frame = self.clock.get_time() / 1000.0

        player_update_messages = []
        if self.plugin_manager: self.plugin_manager.on_tick(current_time_abs)

        if self.world and self.world.player and self.world.player.is_alive:
            player_effect_messages = self.world.player.update(current_time_abs, elapsed_real_time_frame)
            if player_effect_messages: player_update_messages.extend(player_effect_messages)
        
        npc_updates = []
        if self.world:
            npc_updates = self.world.update()

        if player_update_messages:
            buffer_changed = False
            for msg in player_update_messages:
                if msg:
                    clean_msg = self._sanitize_text(msg)
                    if clean_msg not in self.text_buffer[-len(player_update_messages):]:
                        self.text_buffer.append(clean_msg); buffer_changed = True
            if buffer_changed: self._trim_text_buffer(); self.scroll_offset = 0
        
        if npc_updates:
            buffer_changed = False
            for message in npc_updates:
                if message:
                    clean_msg = self._sanitize_text(message)
                    if clean_msg not in self.text_buffer[-len(npc_updates):]:
                        self.text_buffer.append(clean_msg); buffer_changed = True
            if buffer_changed: self._trim_text_buffer(); self.scroll_offset = 0

        if self.world and self.world.player and not self.world.player.is_alive:
             self.game_state = "game_over"

        self.cursor_timer += self.clock.get_time()
        if self.cursor_timer >= 500: self.cursor_visible = not self.cursor_visible; self.cursor_timer = 0

    def draw(self):
        self._calculate_layout()
        self.screen.fill(BG_COLOR)

        if self.game_state == "title_screen": self._draw_title_screen()
        elif self.game_state == "load_game_menu": self._draw_load_screen()
        elif self.game_state == "playing": self._draw_playing_screen()
        elif self.game_state == "game_over": self._draw_game_over_screen()

        if self.debug_mode:
             debug_text = "DEBUG" + (" (Levels ON)" if DEBUG_SHOW_LEVEL else "")
             debug_surface = self.font.render(debug_text, True, DEBUG_COLOR)
             self.screen.blit(debug_surface, (self.layout["screen_width"] - debug_surface.get_width() - 10, 5))

        pygame.display.flip()
        
    def run(self):
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: running = False
                if self.game_state == "title_screen": self._handle_title_input(event)
                elif self.game_state == "load_game_menu": self._handle_load_input(event)
                elif self.game_state == "playing": self._handle_playing_input(event)
                elif self.game_state == "game_over": self._handle_game_over_input(event)
                if event.type == pygame.VIDEORESIZE: self._handle_resize(event)

            if self.game_state in ["playing", "game_over"]: self.update()
            else:
                 self.cursor_timer += self.clock.get_time()
                 if self.cursor_timer >= 500: self.cursor_visible = not self.cursor_visible; self.cursor_timer = 0

            self.draw()
            self.clock.tick(TARGET_FPS)
        
        self._shutdown_gameplay_systems()
        pygame.quit()
        sys.exit()

    def _on_display_message(self, event_type: str, data: Any) -> None:
        if isinstance(data, str): message = data
        elif isinstance(data, dict) and "message" in data: message = data["message"]
        else:
            try: message = str(data)
            except: message = "Unprintable message"
        self.text_buffer.append(self._sanitize_text(message))
        self._trim_text_buffer()

    def _on_time_period_changed(self, event_type: str, data: dict) -> None:
        if "transition_message" in data and data["transition_message"] and self.game_state == "playing":
             self.text_buffer.append(self._sanitize_text(data['transition_message']))
             self._trim_text_buffer()

    def _sanitize_text(self, text: str) -> str:
        if not text: return ""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = ''.join(ch if ch == '\n' or ord(ch) >= 32 else ' ' for ch in text)
        while '\n\n\n' in text: text = text.replace('\n\n\n', '\n\n')
        return text

    def _trim_text_buffer(self):
        if len(self.text_buffer) > MAX_BUFFER_LINES:
            self.text_buffer = self.text_buffer[len(self.text_buffer) - MAX_BUFFER_LINES:]

    def _calculate_layout(self):
        current_width, current_height = self.screen.get_size()
        side_panel_width = SIDE_PANEL_WIDTH; padding = STATUS_PANEL_PADDING
        time_bar_height = 30; input_area_height = INPUT_HEIGHT; margin = self.text_formatter.margin
        time_bar_y = 0; input_area_y = current_height - input_area_height
        panels_top_y = time_bar_y + time_bar_height + margin
        panels_bottom_y = input_area_y - margin
        panels_available_height = max(50, panels_bottom_y - panels_top_y)
        left_panel_rect = pygame.Rect(margin, panels_top_y, side_panel_width, panels_available_height)
        right_panel_rect = pygame.Rect(current_width - side_panel_width - margin, panels_top_y, side_panel_width, panels_available_height)
        center_area_x_start = left_panel_rect.right + margin; center_area_x_end = right_panel_rect.left - margin
        center_area_width = max(100, center_area_x_end - center_area_x_start)
        target_room_panel_height = 300; min_text_area_height = 100
        max_possible_room_height = panels_available_height - margin - min_text_area_height
        actual_room_panel_height = max(30, min(target_room_panel_height, max_possible_room_height))
        room_panel_rect = pygame.Rect(center_area_x_start, panels_top_y, center_area_width, actual_room_panel_height)
        text_area_y = room_panel_rect.bottom + margin
        text_area_height = max(min_text_area_height, panels_bottom_y - text_area_y)
        text_area_rect = pygame.Rect(center_area_x_start, text_area_y, center_area_width, text_area_height)
        self.layout = {"screen_width": current_width, "screen_height": current_height, "time_bar": {"height": time_bar_height, "y": time_bar_y}, "input_area": {"height": input_area_height, "y": input_area_y}, "left_status_panel": {"x": left_panel_rect.x, "y": left_panel_rect.y, "width": left_panel_rect.width, "height": left_panel_rect.height}, "right_status_panel": {"x": right_panel_rect.x, "y": right_panel_rect.y, "width": right_panel_rect.width, "height": right_panel_rect.height}, "room_info_panel": {"x": room_panel_rect.x, "y": room_panel_rect.y, "width": room_panel_rect.width, "height": room_panel_rect.height}, "text_area": {"x": text_area_rect.x, "y": text_area_rect.y, "width": text_area_rect.width, "height": text_area_rect.height}}

    def _draw_title_screen(self):
        self._draw_centered_text("Pygame MUD", self.title_font, (200, 200, 50), y_offset=-100)
        for i, option in enumerate(self.title_options):
            font = self.selected_font if i == self.selected_title_option else self.font
            color = (255, 255, 100) if i == self.selected_title_option else TEXT_COLOR
            prefix = "> " if i == self.selected_title_option else "  "
            self._draw_centered_text(f"{prefix}{option}", font, color, y_offset=-20 + i * 40)

    def _draw_load_screen(self):
        self._draw_centered_text("Load Game", self.title_font, (200, 200, 50), y_offset=-150)
        option_start_y = -100; option_spacing = 30; max_display = 10
        if not self.available_saves:
            self._draw_centered_text("No save files found.", self.font, (180, 180, 180))
        for i in range(max_display):
            display_index = self.load_scroll_offset + i
            if display_index >= len(self.available_saves): break
            save_name = self.available_saves[display_index]
            is_selected = (display_index == self.selected_load_option)
            font = self.selected_font if is_selected else self.font
            color = (255, 255, 100) if is_selected else TEXT_COLOR
            prefix = "> " if is_selected else "  "
            self._draw_centered_text(f"{prefix}{save_name}", font, color, y_offset=option_start_y + i * option_spacing)
        
        back_selected = (self.selected_load_option == len(self.available_saves))
        back_font = self.selected_font if back_selected else self.font
        back_color = (255, 255, 100) if back_selected else TEXT_COLOR
        back_prefix = "> " if back_selected else "  "
        self._draw_centered_text(f"{back_prefix}[ Back ]", back_font, back_color, y_offset=option_start_y + max_display * option_spacing + 20)
    
    def _draw_playing_screen(self):
        self._draw_time_bar()
        self._draw_left_status_panel()
        self._draw_right_status_panel()
        self._draw_room_info_panel()
        text_area_layout = self.layout.get("text_area")
        if not text_area_layout: return
        visible_text_area_rect = pygame.Rect(text_area_layout["x"], text_area_layout["y"], text_area_layout["width"], text_area_layout["height"])
        pygame.draw.rect(self.screen, BG_COLOR, visible_text_area_rect)
        if self.text_buffer:
            min_buffer_height = visible_text_area_rect.height + self.text_formatter.line_height_with_text * 5
            estimated_lines = sum(entry.count('\n') + 3 for entry in self.text_buffer)
            buffer_surface_height = max(min_buffer_height, estimated_lines * self.text_formatter.line_height_with_text)
            self.text_formatter.update_screen_width(visible_text_area_rect.width)
            buffer_surface = pygame.Surface((visible_text_area_rect.width, buffer_surface_height), pygame.SRCALPHA)
            buffer_surface.fill((0, 0, 0, 0))
            raw_content_height = self.text_formatter.render(buffer_surface, "\n\n".join(self.text_buffer), (0, 0))
            content_height = max(visible_text_area_rect.height, raw_content_height + (self.text_formatter.line_spacing // 2))
            self.total_rendered_height = content_height
            max_scroll_offset = max(0, content_height - visible_text_area_rect.height)
            self.scroll_offset = max(0, min(self.scroll_offset, max_scroll_offset))
            source_y = max(0, content_height - visible_text_area_rect.height - self.scroll_offset)
            blit_height = max(0, min(visible_text_area_rect.height, content_height - source_y))
            if blit_height > 0:
                self.screen.blit(buffer_surface, (visible_text_area_rect.x, visible_text_area_rect.y), pygame.Rect(0, source_y, visible_text_area_rect.width, blit_height))
        self._draw_scroll_indicator(visible_text_area_rect)
        self._draw_input_area()

    def _draw_game_over_screen(self):
        self._draw_centered_text(GAME_OVER_MESSAGE_LINE1, self.title_font, DEFAULT_COLORS[FORMAT_ERROR], y_offset=-20)
        self._draw_centered_text(GAME_OVER_MESSAGE_LINE2, self.font, TEXT_COLOR, y_offset=20)

    def _draw_centered_text(self, text, font, color, y_offset=0):
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(self.layout["screen_width"] // 2, self.layout["screen_height"] // 2 + y_offset))
        self.screen.blit(surface, rect)

    def _draw_time_bar(self):
        time_str = self.time_data.get("time_str", "??:??")
        date_str = self.time_data.get("date_str", "Unknown Date")
        time_period = self.time_data.get("time_period", "unknown")
        pygame.draw.rect(self.screen, (40, 40, 60), (0, 0, self.layout["screen_width"], self.layout["time_bar"]["height"]))
        time_color = {"dawn": (255, 165, 0), "day": (255, 255, 150), "dusk": (255, 100, 100), "night": (100, 100, 255)}.get(time_period, TEXT_COLOR)
        time_surface = self.font.render(time_str, True, time_color)
        self.screen.blit(time_surface, (10, 5))
        date_surface = self.font.render(date_str, True, TEXT_COLOR)
        date_x = (self.layout["screen_width"] - date_surface.get_width()) // 2
        self.screen.blit(date_surface, (date_x, 5))
        period_surface = self.font.render(time_period.capitalize(), True, time_color)
        period_x = self.layout["screen_width"] - period_surface.get_width() - 10
        self.screen.blit(period_surface, (period_x, 5))
        pygame.draw.line(self.screen, (80, 80, 100), (0, self.layout["time_bar"]["height"]), (self.layout["screen_width"], self.layout["time_bar"]["height"]), 1)

    def _draw_left_status_panel(self):
        if not self.world or not self.world.player: return
        player = self.world.player
        panel_layout = self.layout.get("left_status_panel")
        if not panel_layout: return
        panel_rect = pygame.Rect(panel_layout["x"], panel_layout["y"], panel_layout["width"], panel_layout["height"])
        pygame.draw.rect(self.screen, (20, 20, 20), panel_rect)
        pygame.draw.rect(self.screen, (80, 80, 80), panel_rect, 1)
        padding = STATUS_PANEL_PADDING; line_height = self.text_formatter.line_height_with_text
        current_y = panel_rect.y + padding; max_y = panel_rect.bottom - padding
        text_color = DEFAULT_COLORS.get(FORMAT_RESET, TEXT_COLOR)
        title_color = DEFAULT_COLORS.get(FORMAT_TITLE, (255, 255, 0))
        gray_color = DEFAULT_COLORS.get(FORMAT_RESET, (128, 128, 128))
        error_color = DEFAULT_COLORS.get(FORMAT_ERROR, (255,0,0))

        if current_y + line_height <= max_y:
            self.screen.blit(self.font.render("STATS", True, title_color), (panel_rect.x + padding, current_y)); current_y += line_height
        stats_to_show = {"strength": "STR", "dexterity": "DEX", "constitution": "CON", "agility": "AGI", "intelligence": "INT", "wisdom": "WIS", "spell_power": "SP", "magic_resist": "MR"}
        stats_per_col = math.ceil(len(stats_to_show) / 2)
        col1_x = panel_rect.x + padding + 5; col2_x = col1_x + (panel_rect.width - padding*2 - 20) // 2
        col1_y, col2_y = current_y, current_y
        for i, (stat_key, stat_abbr) in enumerate(stats_to_show.items()):
            if max(col1_y, col2_y) >= max_y: break
            stat_text = f"{stat_abbr}: {player.stats.get(stat_key, 0)}"; stat_surface = self.font.render(stat_text, True, text_color)
            if i < stats_per_col:
                if col1_y + line_height <= max_y: self.screen.blit(stat_surface, (col1_x, col1_y)); col1_y += line_height
            else:
                if col2_y + line_height <= max_y: self.screen.blit(stat_surface, (col2_x, col2_y)); col2_y += line_height
        current_y = max(col1_y, col2_y) + line_height // 2
        
        if current_y + line_height <= max_y: self.screen.blit(self.font.render("SKILLS", True, title_color), (panel_rect.x + padding, current_y)); current_y += line_height
        if player.skills:
            for skill_name, level in sorted(player.skills.items()):
                if current_y + line_height > max_y: break
                self.screen.blit(self.font.render(f"- {skill_name.capitalize()}: {level}", True, text_color), (panel_rect.x + padding + 5, current_y)); current_y += line_height
        else:
            if current_y + line_height <= max_y: self.screen.blit(self.font.render("(None known)", True, gray_color), (panel_rect.x + padding + 5, current_y)); current_y += line_height
        current_y += line_height // 2
        
        if current_y + line_height <= max_y: self.screen.blit(self.font.render("SPELLS", True, title_color), (panel_rect.x + padding, current_y)); current_y += line_height
        if player.known_spells:
            current_time = time.time()
            for spell_id in sorted(list(player.known_spells), key=lambda sid: getattr(get_spell(sid), 'name', sid)):
                if current_y + line_height > max_y: break
                spell = get_spell(spell_id)
                if spell:
                    cooldown_end = player.spell_cooldowns.get(spell_id, 0)
                    cd_status = f" (CD {max(0, cooldown_end - current_time):.1f}s)" if current_time < cooldown_end else ""
                    spell_text = f"- {spell.name} ({spell.mana_cost} MP)"
                    self.screen.blit(self.font.render(spell_text, True, text_color), (panel_rect.x + padding + 5, current_y))
                    if cd_status:
                         self.screen.blit(self.font.render(cd_status, True, error_color), (panel_rect.x + padding + 5 + self.font.size(spell_text)[0], current_y))
                    current_y += line_height
        else:
            if current_y + line_height <= max_y: self.screen.blit(self.font.render("(None known)", True, gray_color), (panel_rect.x + padding + 5, current_y)); current_y += line_height
    
    def _draw_right_status_panel(self):
        if not self.world or not self.world.player: return
        player = self.world.player
        panel_layout = self.layout.get("right_status_panel")
        if not panel_layout: return
        panel_rect = pygame.Rect(panel_layout["x"], panel_layout["y"], panel_layout["width"], panel_layout["height"])
        pygame.draw.rect(self.screen, (20, 20, 20), panel_rect); pygame.draw.rect(self.screen, (80, 80, 80), panel_rect, 1)
        
        # --- Define local constants for clarity ---
        padding = 5
        line_height = self.text_formatter.line_height_with_text
        current_y = panel_rect.y + padding
        max_y = panel_rect.bottom - padding
        bar_height = 10
        bar_x = panel_rect.x + padding
        bar_label_width = self.font.size("HP: 9999/9999")[0]
        max_bar_width = max(20, panel_layout["width"] - (padding * 3) - bar_label_width)
        gray_color = DEFAULT_COLORS.get(FORMAT_GRAY, (128, 128, 128))

        # --- HP, MP, XP BARS and PLAYER INFO (No changes here) ---
        # (This part of the code remains identical)
        # --- HP BAR ---
        hp_text = f"HP: {int(player.health)}/{int(player.max_health)}"; hp_percent = player.health / player.max_health if player.max_health > 0 else 0
        hp_color = DEFAULT_COLORS[FORMAT_SUCCESS]
        if hp_percent <= PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD / 100: hp_color = DEFAULT_COLORS[FORMAT_ERROR]
        elif hp_percent <= PLAYER_STATUS_HEALTH_LOW_THRESHOLD / 100: hp_color = DEFAULT_COLORS[FORMAT_YELLOW]
        pygame.draw.rect(self.screen, (80, 0, 0), (bar_x, current_y, max_bar_width, bar_height))
        pygame.draw.rect(self.screen, hp_color, (bar_x, current_y, int(max_bar_width * hp_percent), bar_height))
        hp_surface = self.font.render(hp_text, True, hp_color)
        self.screen.blit(hp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (hp_surface.get_height() // 2))); current_y += bar_height + 3

        # --- MP BAR ---
        mp_text = f"MP: {int(player.mana)}/{int(player.max_mana)}"; mp_percent = player.mana / player.max_mana if player.max_mana > 0 else 0
        mp_color = DEFAULT_COLORS[FORMAT_CYAN]
        pygame.draw.rect(self.screen, (0, 0, 80), (bar_x, current_y, max_bar_width, bar_height))
        pygame.draw.rect(self.screen, mp_color, (bar_x, current_y, int(max_bar_width * mp_percent), bar_height))
        mp_surface = self.font.render(mp_text, True, mp_color)
        self.screen.blit(mp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (mp_surface.get_height() // 2))); current_y += bar_height + 3

        # --- XP BAR ---
        xp_text = f"XP: {int(player.experience)}/{int(player.experience_to_level)}"; xp_percent = player.experience / player.experience_to_level if player.experience_to_level > 0 else 0
        xp_color = DEFAULT_COLORS[FORMAT_ORANGE]
        pygame.draw.rect(self.screen, (80, 50, 0), (bar_x, current_y, max_bar_width, bar_height))
        pygame.draw.rect(self.screen, xp_color, (bar_x, current_y, int(max_bar_width * xp_percent), bar_height))
        xp_surface = self.font.render(xp_text, True, xp_color)
        self.screen.blit(xp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (xp_surface.get_height() // 2))); current_y += bar_height + padding
        
        # --- PLAYER INFO ---
        current_y = self.text_formatter.render(self.screen, f"{FORMAT_TITLE}{player.name}{FORMAT_RESET}", (panel_rect.x + padding, current_y), max_height=(max_y - current_y))
        if current_y < max_y: self.screen.blit(self.font.render(f"Level: {player.level}", True, TEXT_COLOR), (panel_rect.x + padding, current_y)); current_y += line_height
        if current_y < max_y: current_y = self.text_formatter.render(self.screen, f"Gold: {FORMAT_YELLOW}{player.gold}{FORMAT_RESET}", (panel_rect.x + padding, current_y), max_height=(max_y - current_y))
        current_y += line_height

        # --- EQUIPMENT (No changes here) ---
        if current_y + line_height <= max_y: self.screen.blit(self.font.render("EQUIPPED", True, DEFAULT_COLORS[FORMAT_TITLE]), (panel_rect.x + padding, current_y)); current_y += line_height
        def format_equip_slot(slot_abbr: str, item: Optional[Item]) -> str:
            if not item: return f"{slot_abbr}: {FORMAT_RESET}(Empty){FORMAT_RESET}"
            durability_str = ""
            max_durability = item.get_property("max_durability", 0); current_durability = item.get_property("durability", max_durability)
            if max_durability > 0:
                ratio = current_durability / max_durability if max_durability else 0; dura_color = FORMAT_SUCCESS
                if ratio <= 0.1: dura_color = FORMAT_ERROR
                elif ratio <= 0.3: dura_color = FORMAT_YELLOW
                durability_str = f" [{dura_color}{int(current_durability)}/{int(max_durability)}{FORMAT_RESET}]"
            return f"{slot_abbr}: {item.name}{durability_str}"
        slot_abbrs = {"main_hand": "MH", "off_hand": "OH", "head": "Hd", "body": "Bd", "hands": "Hn", "feet": "Ft", "neck": "Nk"}
        for slot_key in ["main_hand", "off_hand", "head", "body", "hands", "feet", "neck"]:
            if current_y >= max_y: break
            current_y = self.text_formatter.render(self.screen, f"- {format_equip_slot(slot_abbrs[slot_key], player.equipment.get(slot_key))}", (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y))
        current_y += line_height // 2

        # --- ACTIVE EFFECTS (No changes here) ---
        if current_y + line_height <= max_y: self.screen.blit(self.font.render("EFFECTS", True, DEFAULT_COLORS[FORMAT_TITLE]), (panel_rect.x + padding, current_y)); current_y += line_height
        
        if player.active_effects:
            for effect in sorted(player.active_effects, key=lambda e: e.get("name", "zzz")):
                if current_y >= max_y: break
                name = effect.get('name', 'Unknown Effect'); duration = effect.get('duration_remaining', 0)
                duration_str = f"{duration / 60:.1f}m" if duration > 60 else f"{duration:.1f}s"
                details = ""
                if effect.get("type") == "dot":
                     details = f" ({FORMAT_ERROR}{effect.get('damage_per_tick', 0)}/tick{FORMAT_RESET})"
                current_y = self.text_formatter.render(self.screen, f"- {name}{details} ({duration_str})", (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y))
        else:
            if current_y + line_height <= max_y:
                self.screen.blit(self.font.render("- (None)", True, gray_color), (panel_rect.x + padding + 5, current_y))
                current_y += line_height
                
        current_y += line_height // 2
        
        # --- HOSTILES ---
        if current_y + line_height <= max_y: self.screen.blit(self.font.render("HOSTILES", True, DEFAULT_COLORS[FORMAT_TITLE]), (panel_rect.x + padding, current_y)); current_y += line_height
        
        # Get all NPCs in the room and filter for hostiles
        all_npcs_in_room = self.world.get_current_room_npcs()
        hostile_targets = [npc for npc in all_npcs_in_room if npc.is_alive and npc.faction == "hostile"]
        
        if hostile_targets:
            for target in hostile_targets:
                 if current_y >= max_y: break
                 formatted_target_name = format_target_name(player, target)
                 hp_str = f" ({FORMAT_SUCCESS}{int(target.health)}/{int(target.max_health)}{FORMAT_RESET})" if hasattr(target, 'health') else ""
                 current_y = self.text_formatter.render(self.screen, f"- {formatted_target_name}{hp_str}", (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y))
        else:
            if current_y + line_height <= max_y:
                self.screen.blit(self.font.render("- (None)", True, gray_color), (panel_rect.x + padding + 5, current_y))
                current_y += line_height

    def _draw_room_info_panel(self):
        if not self.world or not self.layout: return
        panel_layout = self.layout.get("room_info_panel");
        if not panel_layout: return
        panel_rect = pygame.Rect(panel_layout["x"], panel_layout["y"], panel_layout["width"], panel_layout["height"])
        pygame.draw.rect(self.screen, (15, 15, 15), panel_rect); pygame.draw.rect(self.screen, (70, 70, 70), panel_rect, 1)
        padding = 5; current_y = panel_rect.y + padding; max_y = panel_rect.bottom - padding
        current_room = self.world.get_current_room()
        if not current_room: return

        # live updates each frame        
        room_description_text = self.world.get_room_description_for_display()
        
        original_formatter_width = self.text_formatter.usable_width; panel_usable_width = max(1, panel_rect.width - padding * 2)
        
        self.text_formatter.update_screen_width(panel_usable_width)
        # The render call remains the same, it just gets the correct text now.
        self.text_formatter.render(self.screen, room_description_text, (panel_rect.x + padding, current_y), max_height=max_y - current_y)
        
        # Restore the formatter's width for other UI elements
        self.text_formatter.update_screen_width(original_formatter_width)
    
    def _draw_input_area(self):
        pygame.draw.rect(self.screen, INPUT_BG_COLOR, (0, self.layout["input_area"]["y"], self.layout["screen_width"], self.layout["input_area"]["height"]))
        input_display = "> " + self.input_text
        if self.cursor_visible: input_display += "|"
        input_surface = self.font.render(input_display, True, TEXT_COLOR)
        input_y_pos = self.layout["input_area"]["y"] + (self.layout["input_area"]["height"] - input_surface.get_height()) // 2
        self.screen.blit(input_surface, (self.text_formatter.margin, input_y_pos))

    def _draw_scroll_indicator(self, text_area_rect: pygame.Rect):
        if not hasattr(self, 'total_rendered_height') or self.total_rendered_height <= text_area_rect.height: return
        arrow_x = text_area_rect.right - 15; arrow_width = 8; arrow_height = 8; arrow_color = (180, 180, 180)
        max_scroll = max(0, self.total_rendered_height - text_area_rect.height)
        if self.scroll_offset < max_scroll:
            pygame.draw.polygon(self.screen, arrow_color, [(arrow_x, text_area_rect.top + 5), (arrow_x - arrow_width, text_area_rect.top + 5 + arrow_height), (arrow_x + arrow_width, text_area_rect.top + 5 + arrow_height)])
        if self.scroll_offset > 0:
            pygame.draw.polygon(self.screen, arrow_color, [(arrow_x, text_area_rect.bottom - 5), (arrow_x - arrow_width, text_area_rect.bottom - 5 - arrow_height), (arrow_x + arrow_width, text_area_rect.bottom - 5 - arrow_height)])

    def _handle_title_input(self, event):
        if event.type != pygame.KEYDOWN: return
        if event.key == pygame.K_UP: self.selected_title_option = (self.selected_title_option - 1 + len(self.title_options)) % len(self.title_options)
        elif event.key == pygame.K_DOWN: self.selected_title_option = (self.selected_title_option + 1) % len(self.title_options)
        elif event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:
            selected = self.title_options[self.selected_title_option]
            if selected == "New Game": self._start_new_game()
            elif selected == "Load Game": self._update_available_saves(); self.game_state = "load_game_menu"; self.selected_load_option = 0; self.load_scroll_offset = 0
            elif selected == "Quit": pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _handle_load_input(self, event):
        # ... (implementation is safe) ...
        if event.type != pygame.KEYDOWN: return
        num_options = len(self.available_saves) + 1
        if event.key == pygame.K_UP: self.selected_load_option = (self.selected_load_option - 1 + num_options) % num_options
        elif event.key == pygame.K_DOWN: self.selected_load_option = (self.selected_load_option + 1) % num_options
        elif event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:
            if self.selected_load_option == len(self.available_saves): self.game_state = "title_screen"
            elif self.available_saves and 0 <= self.selected_load_option < len(self.available_saves): self._load_selected_game()
        elif event.key == pygame.K_ESCAPE: self.game_state = "title_screen"

    def _handle_playing_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]: self.handle_input(self.input_text); self.tab_completion_buffer = ""
            elif event.key == pygame.K_BACKSPACE: self.input_text = self.input_text[:-1]; self.tab_completion_buffer = ""
            elif event.key == pygame.K_UP: self.navigate_history(1)
            elif event.key == pygame.K_DOWN: self.navigate_history(-1)
            elif event.key == pygame.K_TAB: self.handle_tab_completion()
            elif event.key == pygame.K_PAGEUP: self._scroll_text_buffer(self.layout["text_area"]["height"] // 2)
            elif event.key == pygame.K_PAGEDOWN: self._scroll_text_buffer(-self.layout["text_area"]["height"] // 2)
            elif event.key == pygame.K_F1: self._toggle_debug_mode()
            else:
                if event.unicode.isprintable(): self.input_text += event.unicode; self.tab_completion_buffer = ""
        elif event.type == pygame.MOUSEWHEEL: self._scroll_text_buffer(SCROLL_SPEED * self.text_formatter.line_height_with_text * event.y)

    def _handle_game_over_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r: self.handle_respawn()
            elif event.key == pygame.K_q: self._shutdown_gameplay_systems(); self.game_state = "title_screen"
    
    def _handle_resize(self, event):
        new_width, new_height = max(600, event.w), max(400, event.h)
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)

    def navigate_history(self, direction: int):
        if not self.command_history: return
        if direction > 0: self.history_index = min(self.history_index + 1, len(self.command_history) - 1)
        else: self.history_index = max(self.history_index - 1, -1)
        self.input_text = self.command_history[-(self.history_index + 1)] if self.history_index >= 0 else ""
        self.tab_completion_buffer = ""

    def handle_tab_completion(self):
        if not self.input_text.strip(): return
        if self.input_text.strip() != self.tab_completion_buffer or not self.tab_suggestions:
            self.tab_completion_buffer = self.input_text.strip()
            self.tab_suggestions = self.command_processor.get_command_suggestions(self.tab_completion_buffer)
            self.tab_index = -1
        if self.tab_suggestions:
            self.tab_index = (self.tab_index + 1) % len(self.tab_suggestions)
            self.input_text = self.tab_suggestions[self.tab_index]
    
    def _scroll_text_buffer(self, amount_pixels: int):
        content_height = self.total_rendered_height; visible_height = self.layout.get("text_area", {}).get("height", SCREEN_HEIGHT)
        max_scroll = max(0, content_height - visible_height)
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset + amount_pixels))

    def _toggle_debug_mode(self):
        self.debug_mode = not self.debug_mode
        if self.game_state == "playing":
            msg = f"{FORMAT_HIGHLIGHT}Debug mode {'enabled' if self.debug_mode else 'disabled'}.{FORMAT_RESET}"
            self.text_buffer.append(msg); self._trim_text_buffer()

    def _update_available_saves(self):
        self.available_saves = []
        if not os.path.isdir(SAVE_GAME_DIR): return
        try:
            self.available_saves = sorted([fname for fname in os.listdir(SAVE_GAME_DIR) if fname.lower().endswith(".json")])
        except Exception as e:
            print(f"Error scanning save directory '{SAVE_GAME_DIR}': {e}")