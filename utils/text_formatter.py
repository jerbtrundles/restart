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

class TextFormatter:
    def __init__(self, font: pygame.font.Font, screen_width: int,
                 colors: Optional[Dict[str, Tuple[int, int, int]]] = None,
                 margin: int = 10, line_spacing: int = 5):
        self.font = font
        self.screen_width = screen_width
        self.margin = margin
        self.line_spacing = line_spacing # Spacing between lines of text
        self.colors = DEFAULT_COLORS.copy()
        if colors: self.colors.update(colors)
        self.default_color = self.colors.get(FORMAT_RESET, (255, 255, 255))
        self._calculate_usable_width()
        # --- Define spacing for blank lines (adjust as needed) ---
        # Option 1: Use only the line_spacing value
        self.blank_line_height = self.line_spacing

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
        Render text with format codes, word wrapping, and correct line spacing.
        Returns the Y coordinate *below* the last rendered element.
        """
        if not text:
            return position[1]

        x_start, y = position
        current_color = self.default_color

        lines_from_input = text.split('\n')

        for line_index, line_text in enumerate(lines_from_input):

            # --- Handle Blank Lines ---
            if not line_text.strip():
                if max_height and y + self.blank_line_height > max_height: break
                y += self.blank_line_height
                continue

            # --- Process Line with Content ---
            words = line_text.split(' ')
            current_word_index = 0
            x = x_start
            current_line_rendered_y = y # Track the Y where the current *physical* line started rendering
            content_rendered_on_this_physical_line = False

            while current_word_index < len(words):

                 # --- Height check before starting a new line implicitly or explicitly ---
                 # Check if rendering the *next* word would *require* a new line that exceeds max_height
                if max_height:
                    # Calculate potential next word width (approximate is fine here)
                    next_word_width = self.font.size(words[current_word_index])[0] if words[current_word_index] else 0
                    space_width = self.font.size(' ')[0] if x > x_start else 0

                    # If the word *won't* fit AND starting a new line would exceed max_height
                    if (x + space_width + next_word_width > x_start + self.usable_width) and \
                       (y + self.line_height_with_text > max_height):
                         # print(f"Stopping render: Next word wrap would exceed max_height {max_height}. Current Y={y}")
                         return y # Return current y, cannot render more

                    # Also check if simply advancing to the next line (e.g., for a long word) exceeds height
                    if (x == x_start and next_word_width > self.usable_width) and \
                       (y + self.line_height_with_text > max_height):
                         # print(f"Stopping render: Long word would exceed max_height {max_height}. Current Y={y}")
                         return y

                word = words[current_word_index]
                if not word: current_word_index += 1; continue

                # --- Calculate word width and segments ---
                segments = self._split_by_format_codes(word)
                word_render_width = 0
                temp_color_for_word = current_color
                segments_for_word = []
                for segment_text, format_code in segments:
                    if format_code: temp_color_for_word = self.colors.get(format_code, temp_color_for_word)
                    elif segment_text: word_render_width += self.font.size(segment_text)[0]; segments_for_word.append((segment_text, temp_color_for_word))

                space_width = self.font.size(' ')[0] if x > x_start else 0

                # --- Word Wrapping Logic ---
                if x + space_width + word_render_width <= x_start + self.usable_width:
                    # Word fits
                    if x > x_start: x += space_width
                    for segment_text, segment_color in segments_for_word:
                        if segment_text: text_surface = self.font.render(segment_text, True, segment_color); surface.blit(text_surface, (x, y)); x += text_surface.get_width()
                    current_color = temp_color_for_word
                    content_rendered_on_this_physical_line = True # Mark that we drew something
                    current_word_index += 1
                else:
                    # Word does NOT fit
                    if x == x_start:
                        # Word is longer than the line width - render it anyway
                        temp_x = x
                        for segment_text, segment_color in segments_for_word:
                            if segment_text: text_surface = self.font.render(segment_text, True, segment_color); surface.blit(text_surface, (temp_x, y)); temp_x += text_surface.get_width()
                        current_color = temp_color_for_word
                        content_rendered_on_this_physical_line = True
                        current_word_index += 1
                        # --- Advance Y *AFTER* rendering the long word ---
                        y += self.line_height_with_text
                        x = x_start
                        current_line_rendered_y = y # Update the starting Y for the new physical line
                        content_rendered_on_this_physical_line = False # Reset for the new line
                    else:
                        # Normal word wrap: Advance Y, reset X, re-process this word
                        y += self.line_height_with_text
                        x = x_start
                        current_line_rendered_y = y # Update the starting Y for the new physical line
                        content_rendered_on_this_physical_line = False # Reset for the new line
                        # --- DO NOT increment current_word_index ---

            # --- After processing all words for the logical line ---
            # If content was rendered on the last physical line used for this logical line,
            # we need to advance Y to prepare for the next logical line.
            if content_rendered_on_this_physical_line:
                y += self.line_height_with_text

            # --- Check max_height again after potentially advancing Y ---
            if max_height and y > max_height:
                # We might have slightly overdrawn, but return the Y where the next line *would* start
                # Or maybe return the previous line's start Y if strict cutoff needed?
                # Returning current `y` is generally safer for subsequent renders.
                break # Stop processing further logical lines from input

        return y # Return the final Y position
    
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

# --- SIMPLIFIED: Only apply color, no articles/capitalization ---
def format_target_name(viewer, target) -> str:
    """Applies level-based color formatting ONLY. No articles or capitalization."""
    from npcs.npc import NPC # <<< ADD THIS LINE
    
    if not hasattr(target, 'name'): return "something"

    full_name = target.name # Use the name directly from the object
    target_level = getattr(target, 'level', 1)
    format_code = FORMAT_RESET # Default

    # Only apply level-based coloring to hostile NPCs
    if isinstance(target, NPC) and target.faction == "hostile" and viewer:
         viewer_level = getattr(viewer, 'level', 1)
         color_category = get_level_diff_category(viewer_level, target_level)
         format_code = LEVEL_DIFF_COLORS.get(color_category, FORMAT_RESET)

    # Return the name with color codes applied
    return f"{format_code}{full_name}{FORMAT_RESET}"
# --- END SIMPLIFIED ---

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

