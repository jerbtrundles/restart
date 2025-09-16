# ui/renderer.py
"""
Handles all rendering for the game, including UI panels, text, and game states.
"""
import pygame
from typing import TYPE_CHECKING, List, Dict, Any

from config import *
from ui import panels
from utils.text_formatter import TextFormatter

if TYPE_CHECKING:
    from core.game_manager import GameManager


class Renderer:
    def __init__(self, screen: pygame.Surface, game: 'GameManager'):
        self.screen = screen
        self.game = game
        self.font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE, bold=False)
        self.title_font = pygame.font.SysFont(FONT_FAMILY, int(FONT_SIZE * 1.5), bold=True)
        self.selected_font = pygame.font.SysFont(FONT_FAMILY, FONT_SIZE, bold=True)
        self.layout: Dict[str, Any] = {}
        self.scroll_offset = 0
        self.total_rendered_height = 0
        self.text_buffer: List[str] = []
        self.cursor_visible = True
        self.cursor_timer = 0

        self.text_formatter = TextFormatter(
            font=self.font,
            screen_width=SCREEN_WIDTH,
            colors=DEFAULT_COLORS,
            margin=10,
            line_spacing=LINE_SPACING
        )

    def calculate_layout(self):
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
        self.layout = {"screen_width": current_width, "screen_height": current_height, "time_bar": {"height": time_bar_height, "y": time_bar_y}, "input_area": {"height": input_area_height, "y": input_area_y}, "left_status_panel": {"x": left_panel_rect.x, "y": left_panel_rect.y, "width": left_panel_rect.width, "height": left_panel_rect.height}, "right_status_panel": {"x": right_panel_rect.x, "y": right_panel_rect.y, "width": right_panel_rect.width, "height": right_panel_rect.height}, "room_info_panel": {"x": room_panel_rect.x, "y": room_panel_rect.y, "width": room_panel_rect.width, "height": room_panel_rect.height}, "text_area": {"x": text_area_rect.x, "y": text_area_rect.y, "width": text_area_rect.width, "height": text_area_height}}

    def draw(self):
        """Main draw call that routes to the correct state-specific renderer."""
        self.calculate_layout()
        self.screen.fill(BG_COLOR)
        
        # Update cursor blink timer
        self.cursor_timer += self.game.clock.get_time()
        if self.cursor_timer >= 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

        state_renderer_map = {
            "title_screen": self._draw_title_screen,
            "load_game_menu": self._draw_load_screen,
            "playing": self._draw_playing_screen,
            "game_over": self._draw_game_over_screen,
        }
        renderer_func = state_renderer_map.get(self.game.game_state)
        if renderer_func:
            renderer_func()

        if self.game.debug_mode:
             debug_text = "DEBUG" + (" (Levels ON)" if DEBUG_SHOW_LEVEL else "")
             debug_surface = self.font.render(debug_text, True, DEBUG_COLOR)
             self.screen.blit(debug_surface, (self.layout["screen_width"] - debug_surface.get_width() - 10, 5))

        pygame.display.flip()

    def scroll(self, amount_pixels: int):
        content_height = self.total_rendered_height; visible_height = self.layout.get("text_area", {}).get("height", SCREEN_HEIGHT)
        max_scroll = max(0, content_height - visible_height)
        self.scroll_offset = max(0, min(max_scroll, self.scroll_offset + amount_pixels))

    def _draw_title_screen(self):
        self._draw_centered_text("Pygame MUD", self.title_font, (200, 200, 50), y_offset=-100)
        for i, option in enumerate(self.game.title_options):
            font = self.selected_font if i == self.game.selected_title_option else self.font
            color = (255, 255, 100) if i == self.game.selected_title_option else TEXT_COLOR
            prefix = "> " if i == self.game.selected_title_option else "  "
            self._draw_centered_text(f"{prefix}{option}", font, color, y_offset=-20 + i * 40)
    
    def _draw_load_screen(self):
        self._draw_centered_text("Load Game", self.title_font, (200, 200, 50), y_offset=-150)
        option_start_y = -100; option_spacing = 30; max_display = 10
        if not self.game.available_saves:
            self._draw_centered_text("No save files found.", self.font, (180, 180, 180))
        for i in range(max_display):
            display_index = i
            if display_index >= len(self.game.available_saves): break
            save_name = self.game.available_saves[display_index]
            is_selected = (display_index == self.game.selected_load_option)
            font = self.selected_font if is_selected else self.font
            color = (255, 255, 100) if is_selected else TEXT_COLOR
            prefix = "> " if is_selected else "  "
            self._draw_centered_text(f"{prefix}{save_name}", font, color, y_offset=option_start_y + i * option_spacing)
        
        back_selected = (self.game.selected_load_option == len(self.game.available_saves))
        back_font = self.selected_font if back_selected else self.font
        back_color = (255, 255, 100) if back_selected else TEXT_COLOR
        back_prefix = "> " if back_selected else "  "
        self._draw_centered_text(f"{back_prefix}[ Back ]", back_font, back_color, y_offset=option_start_y + max_display * option_spacing + 20)
    
    def _draw_playing_screen(self):
        panels.draw_time_bar(self, self.game.time_manager.time_data)
        if self.game.world and self.game.world.player:
            panels.draw_left_status_panel(self, self.game.world.player)
            panels.draw_right_status_panel(self, self.game.world.player, self.game.world)
            panels.draw_room_info_panel(self, self.game.world)
        self._draw_text_area()
        self._draw_input_area()

    def _draw_game_over_screen(self):
        self._draw_centered_text(GAME_OVER_MESSAGE_LINE1, self.title_font, DEFAULT_COLORS[FORMAT_ERROR], y_offset=-20)
        self._draw_centered_text(GAME_OVER_MESSAGE_LINE2, self.font, TEXT_COLOR, y_offset=20)
        
    def _draw_text_area(self):
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

    def _draw_input_area(self):
        pygame.draw.rect(self.screen, INPUT_BG_COLOR, (0, self.layout["input_area"]["y"], self.layout["screen_width"], self.layout["input_area"]["height"]))
        input_display = "> " + self.game.input_handler.input_text
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

    def _draw_centered_text(self, text, font, color, y_offset=0):
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(self.layout["screen_width"] // 2, self.layout["screen_height"] // 2 + y_offset))
        self.screen.blit(surface, rect)

    def add_message(self, message: str):
        """Adds a sanitized message to the renderer's text buffer."""
        clean_message = self._sanitize_text(message)
        self.text_buffer.append(clean_message)
        if len(self.text_buffer) > MAX_BUFFER_LINES:
            self.text_buffer.pop(0)

    def _sanitize_text(self, text: str) -> str:
        if not text: return ""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = ''.join(ch if ch == '\n' or ord(ch) >= 32 else ' ' for ch in text)
        while '\n\n\n' in text: text = text.replace('\n\n\n', '\n\n')
        return text