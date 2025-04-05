"""
utils/text_formatter.py
Fixed text formatter with simpler rendering approach.
"""
import textwrap
from typing import TYPE_CHECKING, Dict, Tuple, List, Optional, Any
import pygame
import math

from core.config import (
    DEFAULT_COLORS, COLOR_DEFAULT, FORMAT_GRAY, FORMAT_PURPLE, # Import base colors if needed
    FORMAT_RED, FORMAT_ORANGE, FORMAT_YELLOW, FORMAT_GREEN, FORMAT_BLUE,
    FORMAT_CYAN, FORMAT_WHITE, FORMAT_RESET,
    SEMANTIC_FORMAT # Import the semantic mapping too
)

if TYPE_CHECKING:
    from player import Player
    from npcs.npc import NPC

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
        self._calculate_usable_width() # Renamed calculation method

    def _calculate_usable_width(self):
        """Calculate usable pixel width based on screen width and margin."""
        self.usable_width = self.screen_width - (self.margin * 2)
        self.line_height = self.font.get_linesize() + self.line_spacing

    def update_screen_width(self, new_width: int):
        self.screen_width = new_width
        self._calculate_usable_width()

    def render(self, surface: pygame.Surface, text: str, position: Tuple[int, int],
            max_height: Optional[int] = None) -> int:
        """
        Render text to a pygame surface with format codes and manual word wrapping.
        Returns the Y coordinate *below* the last rendered line.
        """
        if not text:
            return position[1]

        x_start, y = position
        current_color = self.default_color
        x = x_start

        # Split by explicit newlines first to handle paragraphs/manual breaks
        lines_from_input = text.split('\n')

        for line_index, current_line_text in enumerate(lines_from_input):
            # Check height limit before starting processing a new line from input
            if max_height and y + self.line_height > max_height:
                # print(f"Render height limit reached before line {line_index}") # Debug
                break # Stop processing further lines

            # Handle explicitly empty lines (single \n in input) -> just advance Y
            if not current_line_text.strip():
                # Check height limit before adding blank line space
                if not max_height or y + self.line_height <= max_height:
                    y += self.line_height
                continue # Move to the next line from input

            # Process words within the current line text
            words = current_line_text.split(' ')
            current_word_index = 0

            while current_word_index < len(words):
                word = words[current_word_index]

                # Check height limit *before potentially wrapping* to a new line
                if max_height and y + self.line_height > max_height:
                    # print(f"Render height limit reached mid-line wrap check") # Debug
                    return y # Return current Y, don't process more words

                # --- Segment Calculation (unchanged) ---
                segments = self._split_by_format_codes(word)
                word_render_width = 0
                temp_color_for_word = current_color
                segments_for_word = []
                for segment_text, format_code in segments:
                    if format_code:
                        temp_color_for_word = self.colors.get(format_code, temp_color_for_word)
                    elif segment_text:
                        segment_width = self.font.size(segment_text)[0]
                        word_render_width += segment_width
                        segments_for_word.append((segment_text, temp_color_for_word))
                # --- End Segment Calculation ---

                space_width = self.font.size(' ')[0] if x > x_start else 0

                # --- Word Wrapping Logic ---
                # Does the word fit on the *current* line?
                if x + space_width + word_render_width <= x_start + self.usable_width:
                    # Fits: Render space (if needed) and word segments
                    if x > x_start: x += space_width
                    for segment_text, segment_color in segments_for_word:
                        if segment_text:
                            text_surface = self.font.render(segment_text, True, segment_color)
                            surface.blit(text_surface, (x, y))
                            x += text_surface.get_width()
                    current_color = temp_color_for_word
                    current_word_index += 1 # Move to next word
                else:
                    # Word does NOT fit on current line
                    # Handle word longer than line width (render and force wrap)
                    if x == x_start:
                         temp_x = x
                         for segment_text, segment_color in segments_for_word:
                              if segment_text:
                                   text_surface = self.font.render(segment_text, True, segment_color)
                                   surface.blit(text_surface, (temp_x, y))
                                   temp_x += text_surface.get_width()
                         current_color = temp_color_for_word
                         current_word_index += 1 # Processed the long word
                         # Since we rendered something, advance Y for the *next* potential line
                         y += self.line_height
                         x = x_start
                    else:
                        # Normal wrap: move to next line, reset X, process *same* word again
                        y += self.line_height
                        x = x_start
                        # --- Do NOT increment current_word_index here ---

            # --- After processing all words for 'current_line_text' ---
            # If the line wasn't empty and we actually rendered something
            # that didn't end by forcing a wrap (i.e., x > x_start),
            # we need to advance Y to prepare for the next potential line from input.
            # If x == x_start, it means the last word either fit perfectly and filled
            # the line (rare) or caused a wrap, which already advanced Y.
            if x > x_start:
                 y += self.line_height
                 x = x_start # Reset x for the next line regardless

        # Ensure final Y is returned correctly
        # If the last action advanced Y, it's already correct (pointing below last line)
        # If the last action just rendered without advancing Y (e.g., fit perfectly),
        # the current Y is the top of the rendered line, but we need the position *below* it.
        # However, the loop structure seems to handle this by advancing Y after rendering
        # or after wrapping. Let's trust the final 'y' value.

        return y
    
    def remove_format_codes(self, text: str) -> str:
        if not text: return ""
        result = text
        for code in self.colors.keys():
            result = result.replace(code, "")
        return result

    def _split_by_format_codes(self, text: str) -> List[Tuple[str, Optional[str]]]:
        """Splits text, yielding (text_segment, format_code_or_None)."""
        result = []
        current_text = text
        while current_text:
            earliest_pos = len(current_text)
            earliest_code = None
            for code in self.colors.keys():
                try: # Protect against invalid code searches if needed
                    pos = current_text.find(code)
                    if pos != -1 and pos < earliest_pos:
                        earliest_pos = pos
                        earliest_code = code
                except TypeError: # Handle potential issues if code isn't a string
                     print(f"Warning: Invalid format code type encountered: {code}")
                     continue

            if earliest_code is None:
                result.append((current_text, None)) # Text segment
                break
            if earliest_pos > 0:
                result.append((current_text[:earliest_pos], None)) # Text segment
            result.append((earliest_code, earliest_code)) # Format code segment
            current_text = current_text[earliest_pos + len(earliest_code):]
        return result

# Map thresholds to format codes
LEVEL_DIFF_COLORS = {
    "purple": FORMAT_PURPLE,
    "red": FORMAT_RED,        # Very hard -> Red
    "orange": FORMAT_ORANGE,    # Hard -> Orange
    "yellow": FORMAT_YELLOW,    # Even/Slightly hard -> Yellow
    "blue": FORMAT_BLUE,      # Easy -> Blue
    "green": FORMAT_GREEN,      # Very easy -> Green
    "gray": FORMAT_GRAY,
}

def format_target_name(viewer, target) -> str:
    """
    Formats the target's name based on dynamic level difference relative to the viewer (7 Tiers).
    Only colors hostile NPCs based on level.
    """
    # Local import for runtime if needed
    from npcs.npc import NPC # Assuming NPC is defined relative to this file's usage

    if not hasattr(target, 'name'):
        return "something" # Fallback

    base_name = target.name

    # Only color hostile NPCs based on level
    if not isinstance(target, NPC) or target.friendly or target.faction != "hostile":
        return base_name

    viewer_level = getattr(viewer, 'level', 1)
    target_level = getattr(target, 'level', 1)

    # --- Use the new function to get the category ---
    color_category = get_level_diff_category(viewer_level, target_level)
    # --- End Use ---

    format_code = LEVEL_DIFF_COLORS.get(color_category, FORMAT_RESET)

    level_str = f" (Level {target_level})"
    if f"(Level {target_level})" in base_name:
         level_str = ""

    return f"{format_code}{base_name}{level_str}{FORMAT_RESET}"

# --- NEW Function to Calculate Category ---
def get_level_diff_category(viewer_level: int, target_level: int) -> str:
    """Calculates the difficulty category string based on level difference."""
    level_diff = target_level - viewer_level
    color_category = "gray" # Default

    if viewer_level <= 5:
        # Strict Thresholds for Levels 1-5
        if level_diff >= 3: color_category = "purple"
        elif level_diff == 2: color_category = "red"
        elif level_diff == 1: color_category = "orange"
        elif level_diff == 0: color_category = "yellow"
        elif level_diff == -1: color_category = "blue"
        elif level_diff == -2: color_category = "green"
        else: color_category = "gray" # <= -3
    else:
        # Scaling Logic for Levels 6+
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
# --- END NEW Function ---

