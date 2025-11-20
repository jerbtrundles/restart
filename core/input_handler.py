# core/input_handler.py
"""
Handles all raw user input from Pygame and translates it into game actions.
Updated to handle mouse clicks for clickable text.
"""
import pygame
from typing import TYPE_CHECKING, List

from commands.command_system import CommandProcessor
from config import COMMAND_HISTORY_SIZE, SCROLL_SPEED

if TYPE_CHECKING:
    from core.game_manager import GameManager


class InputHandler:
    def __init__(self, game: 'GameManager', command_processor: CommandProcessor):
        self.game = game
        self.command_processor = command_processor

        self.input_text = ""
        self.command_history: List[str] = []
        self.history_index = -1
        self.tab_completion_buffer = ""
        self.tab_suggestions: List[str] = []
        self.tab_index = -1

    def handle_event(self, event: pygame.event.Event):
        """Main event handling router based on the current game state."""
        state_handler_map = {
            "title_screen": self._handle_title_input,
            "load_game_menu": self._handle_load_input,
            "playing": self._handle_playing_input,
            "game_over": self._handle_game_over_input,
        }
        handler = state_handler_map.get(self.game.game_state)
        if handler:
            handler(event)

    def _handle_title_input(self, event):
        if event.type != pygame.KEYDOWN: return
        if event.key == pygame.K_UP: self.game.selected_title_option = (self.game.selected_title_option - 1) % len(self.game.title_options)
        elif event.key == pygame.K_DOWN: self.game.selected_title_option = (self.game.selected_title_option + 1) % len(self.game.title_options)
        elif event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:
            self.game.select_title_option()

    def _handle_load_input(self, event):
        if event.type != pygame.KEYDOWN: return
        num_options = len(self.game.available_saves) + 1
        if event.key == pygame.K_UP: self.game.selected_load_option = (self.game.selected_load_option - 1 + num_options) % num_options
        elif event.key == pygame.K_DOWN: self.game.selected_load_option = (self.game.selected_load_option + 1) % num_options
        elif event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:
            self.game.select_load_option()
        elif event.key == pygame.K_ESCAPE:
            self.game.game_state = "title_screen"

    def _handle_playing_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in [pygame.K_RETURN, pygame.K_KP_ENTER]:                
                if self.input_text:
                    self.game.process_command(self.input_text)
                    self.command_history.append(self.input_text)
                    if len(self.command_history) > COMMAND_HISTORY_SIZE:
                        self.command_history.pop(0)
                    self.history_index = -1
                    self.input_text = ""
                    self.tab_completion_buffer = ""
            elif event.key == pygame.K_BACKSPACE:
                self.input_text = self.input_text[:-1]
                self.tab_completion_buffer = ""
            elif event.key == pygame.K_UP:
                self._navigate_history(1)
            elif event.key == pygame.K_DOWN:
                self._navigate_history(-1)
            elif event.key == pygame.K_TAB:
                self._handle_tab_completion()
            elif event.key == pygame.K_PAGEUP:
                self.game.renderer.scroll(self.game.renderer.layout["text_area"]["height"] // 2)
            elif event.key == pygame.K_PAGEDOWN:
                self.game.renderer.scroll(-self.game.renderer.layout["text_area"]["height"] // 2)
            elif event.key == pygame.K_F1:
                self.game.toggle_debug_mode()
            else:
                if event.unicode.isprintable():
                    self.input_text += event.unicode
                    self.tab_completion_buffer = ""
        
        elif event.type == pygame.MOUSEWHEEL:
            scroll_amount_pixels = SCROLL_SPEED * self.game.renderer.text_formatter.line_height_with_text * event.y
            self.game.renderer.scroll(scroll_amount_pixels)

        # --- MOUSE HANDLING ---
        if event.type in [pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP, pygame.MOUSEMOTION]:
            # 1. UI Panels Priority (Draggable windows)
            # If the UI manager consumes the event (click on panel), stop processing.
            if self.game.ui_manager.handle_event(event):
                return

            # 2. Text Links (Only on Mouse Up)
            if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                clicked_command = self.game.renderer.get_command_at_pos(event.pos)
                if clicked_command:
                    self.game.process_command(clicked_command)


    def _handle_game_over_input(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.game.handle_respawn()
            elif event.key == pygame.K_q:
                self.game.quit_to_title()

    def _navigate_history(self, direction: int):
        if not self.command_history: return
        if direction > 0: self.history_index = min(self.history_index + 1, len(self.command_history) - 1)
        else: self.history_index = max(self.history_index - 1, -1)
        self.input_text = self.command_history[-(self.history_index + 1)] if self.history_index >= 0 else ""
        self.tab_completion_buffer = ""

    def _handle_tab_completion(self):
        if not self.input_text.strip(): return
        if self.input_text.strip() != self.tab_completion_buffer or not self.tab_suggestions:
            self.tab_completion_buffer = self.input_text.strip()
            self.tab_suggestions = self.command_processor.get_command_suggestions(self.tab_completion_buffer)
            self.tab_index = -1
        if self.tab_suggestions:
            self.tab_index = (self.tab_index + 1) % len(self.tab_suggestions)
            self.input_text = self.tab_suggestions[self.tab_index]