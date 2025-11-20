# utils/text_formatter.py
"""
Handles text rendering with format codes, word wrapping, and interactive links.
Also provides utilities for level-based color coding.
"""
import re
import pygame
from typing import Dict, Tuple, List, Optional, Any, Union, TYPE_CHECKING

from config import (
    DEFAULT_COLORS, FORMAT_RESET, FORMAT_PURPLE, FORMAT_RED, 
    FORMAT_ORANGE, FORMAT_YELLOW, FORMAT_CYAN, FORMAT_GREEN, FORMAT_GRAY
)

if TYPE_CHECKING:
    from player import Player
    from npcs.npc import NPC

# --- Constants for Level Coloring ---
LEVEL_DIFF_COLORS = {
    "purple": FORMAT_PURPLE,
    "red": FORMAT_RED,
    "orange": FORMAT_ORANGE,
    "yellow": FORMAT_YELLOW,
    "blue": FORMAT_CYAN,
    "green": FORMAT_GREEN,
    "gray": FORMAT_GRAY,
}

# --- Interactive Classes ---

class ClickableZone:
    def __init__(self, rect: pygame.Rect, command: str):
        self.rect = rect
        self.command = command

class TextFormatter:
    def __init__(self, font: pygame.font.Font, screen_width: int,
                 colors: Optional[Dict[str, Tuple[int, int, int]]] = None,
                 margin: int = 10, line_spacing: int = 5):
        self.font = font
        self.screen_width = screen_width
        self.margin = margin
        self.line_spacing = line_spacing
        self.colors = DEFAULT_COLORS.copy()
        if colors: self.colors.update(colors)
        self.default_color = self.colors.get(FORMAT_RESET, (255, 255, 255))
        
        self._calculate_usable_width()
        self.blank_line_height = self.line_spacing
        
        # List to store hotspots generated during the last render pass
        self.last_hotspots: List[ClickableZone] = []
        
        # Regex to split by tags: matches [[...]]
        self.tag_pattern = re.compile(r'(\[\[.*?\]\])')

    def _calculate_usable_width(self):
        """Calculate usable pixel width based on screen width and margin."""
        self.usable_width = self.screen_width - (self.margin * 2)
        self.line_height_with_text = self.font.get_linesize() + self.line_spacing

    def update_screen_width(self, new_width: int):
        self.screen_width = new_width
        self._calculate_usable_width()

    def render(self, surface: pygame.Surface, text: str, position: Tuple[int, int],
               max_height: Optional[int] = None) -> int:
        """
        Render text with format codes, word wrapping, and clickable zones.
        Populates self.last_hotspots with the interactive areas relative to the surface.
        Returns the Y coordinate *below* the last rendered element.
        """
        self.last_hotspots = [] # Clear previous hotspots
        
        if not text:
            return position[1]

        x_start, y_start = position
        y = y_start 
        effective_max_y = (y_start + max_height) if max_height is not None else float('inf')

        # State for the parser
        current_color = self.default_color
        current_command: Optional[str] = None
        
        space_width = self.font.size(' ')[0]

        lines_from_input = text.split('\n')

        for line_text in lines_from_input:
            # --- Handle Blank Lines ---
            if not line_text: 
                y += self.blank_line_height
                if y >= effective_max_y: break
                continue 
            
            # 1. Parse all tags in the line first to separate Format from Text
            segments = self._parse_segments(line_text)
            
            x = x_start
            
            for seg_type, content in segments:
                if seg_type == 'format':
                    # --- Handle State Changes ---
                    if content in self.colors:
                        current_color = self.colors[content]
                    elif content.startswith('[[CMD:'):
                        # Extract command inside [[CMD:look X]]
                        current_command = content[6:-2]
                    elif content == '[[/CMD]]':
                        current_command = None
                    elif content == '[[/]]':
                        current_color = self.default_color
                
                elif seg_type == 'text':
                    # --- Handle Text Rendering and Wrapping ---
                    # Split by space to manage wrapping
                    words = content.split(' ')
                    
                    for i, word in enumerate(words):
                        # Handle explicit spaces from split
                        if not word:
                            # An empty string implies a space existed here in the original split
                            if i < len(words) - 1:
                                x += space_width
                            continue
                            
                        word_surface = self.font.render(word, True, current_color)
                        word_w = word_surface.get_width()
                        word_h = word_surface.get_height()
                        
                        # Check wrapping
                        if x + word_w > x_start + self.usable_width:
                            if x > x_start: # Move to next line
                                y += self.line_height_with_text
                                x = x_start
                        
                        if y + self.line_height_with_text > effective_max_y:
                            return y

                        # Render Word
                        surface.blit(word_surface, (x, y))
                        
                        # Create Hitbox if clickable
                        if current_command:
                            # Note: Rect relative to the surface being drawn on
                            hotspot_rect = pygame.Rect(x, y, word_w, word_h)
                            self.last_hotspots.append(ClickableZone(hotspot_rect, current_command))
                        
                        x += word_w
                        
                        # Add space after word if it's not the last part of this text segment
                        if i < len(words) - 1:
                            x += space_width

            # Explicit Newline at end of input string line
            y += self.line_height_with_text
            if y >= effective_max_y:
                break

        return y 

    def _parse_segments(self, text: str) -> List[Tuple[str, str]]:
        """
        Parses a string into a list of ('text', 'hello') or ('format', '[[RED]]').
        """
        parts = self.tag_pattern.split(text)
        segments = []
        for part in parts:
            if not part: continue
            if part.startswith('[[') and part.endswith(']]'):
                segments.append(('format', part))
            else:
                segments.append(('text', part))
        return segments

    def remove_format_codes(self, text: str) -> str:
        """Removes all [[...]] tags."""
        return self.tag_pattern.sub('', text)

# --- Helper Functions ---

def get_level_diff_category(viewer_level: int, target_level: int) -> str:
    """Calculates the difficulty category string based on level difference."""
    level_diff = target_level - viewer_level
    color_category = "gray" # Default

    if viewer_level <= 5:
        if level_diff >= 3: color_category = "purple"
        elif level_diff == 2: color_category = "red"
        elif level_diff == 1: color_category = "orange"
        elif level_diff == 0: color_category = "yellow"
        elif level_diff == -1: color_category = "blue"
        elif level_diff == -2: color_category = "green"
        else: color_category = "gray"
    else:
        purple_threshold = 3 + ((viewer_level - 5) // 12)
        red_threshold = 2 + ((viewer_level - 5) // 9)
        orange_threshold = 1
        yellow_lower_bound = 0 - ((viewer_level - 5) // 7)
        blue_lower_bound = yellow_lower_bound - (1 + ((viewer_level - 5) // 8))
        green_lower_bound = blue_lower_bound - (1 + ((viewer_level - 5) // 9))

        if level_diff >= purple_threshold: color_category = "purple"
        elif level_diff >= red_threshold: color_category = "red"
        elif level_diff >= orange_threshold: color_category = "orange"
        elif level_diff >= yellow_lower_bound: color_category = "yellow"
        elif level_diff >= blue_lower_bound: color_category = "blue"
        elif level_diff >= green_lower_bound: color_category = "green"
        else: color_category = "gray"

    return color_category

def format_target_name(viewer, target) -> str:
    """
    Applies level-based color formatting. 
    Does NOT apply click tags (used by side panels usually).
    """
    if not hasattr(target, 'name'): return "something"

    full_name = target.name 
    target_level = getattr(target, 'level', 1)
    format_code = FORMAT_RESET 

    if hasattr(target, 'faction'):
        faction = target.faction
        if faction == "hostile" and viewer:
             viewer_level = getattr(viewer, 'level', 1)
             color_category = get_level_diff_category(viewer_level, target_level)
             format_code = LEVEL_DIFF_COLORS.get(color_category, FORMAT_RESET)

    return f"{format_code}{full_name}{FORMAT_RESET}"