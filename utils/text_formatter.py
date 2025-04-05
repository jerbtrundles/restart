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
    """
    Handles text formatting, wrapping, and style management for game text.
    
    Features:
    - Consistent text wrapping based on screen width
    - Format codes for colors and styles
    - Paragraph formatting with proper spacing
    """

    def __init__(self, font: pygame.font.Font, screen_width: int, 
                 colors: Optional[Dict[str, Tuple[int, int, int]]] = None,
                 margin: int = 10, line_spacing: int = 5):
        """
        Initialize the text formatter.
        
        Args:
            font: The pygame font to use for text rendering
            screen_width: Width of the screen in pixels
            colors: Custom colors for format codes (defaults to DEFAULT_COLORS)
            margin: Margin from screen edge in pixels
            line_spacing: Space between lines in pixels
        """
        self.font = font
        self.screen_width = screen_width
        self.margin = margin
        self.line_spacing = line_spacing
        self.colors = DEFAULT_COLORS.copy()
        
        # Override with custom colors if provided
        if colors:
            self.colors.update(colors)
            
        # Calculate chars per line for wrapping
        self._calculate_wrap_width()
        
    def _calculate_wrap_width(self):
        """Calculate the number of characters that fit on one line."""
        # Use a conservative estimate for character width
        test_char = "m"  # Wide character
        char_width = self.font.size(test_char)[0]
        usable_width = self.screen_width - (self.margin * 2)
        self.chars_per_line = max(40, usable_width // char_width)
        
        # Create a textwrap wrapper with the calculated width
        self.wrapper = textwrap.TextWrapper(
            width=self.chars_per_line,
            expand_tabs=True,
            replace_whitespace=True,
            break_long_words=True,
            break_on_hyphens=True
        )
        
    def update_screen_width(self, new_width: int):
        """
        Update the screen width and recalculate wrapping.
        
        Args:
            new_width: The new screen width in pixels
        """
        self.screen_width = new_width
        self._calculate_wrap_width()
    
    def format_text(self, text: str) -> List[str]:
        """
        Format text with wrapping and proper paragraph spacing.
        Breaks the text into individual lines.
        
        Args:
            text: The text to format
            
        Returns:
            A list of formatted lines
        """
        # Handle empty or None text
        if not text:
            return []
            
        # Process paragraphs separately to maintain spacing
        paragraphs = text.split('\n\n')
        result_lines = []
        
        for i, paragraph in enumerate(paragraphs):
            # Skip empty paragraphs but preserve spacing
            if not paragraph.strip():
                result_lines.append('')
                continue
                
            # Handle each paragraph
            lines = paragraph.split('\n')
            for line in lines:
                # Wrap the line
                wrapped_lines = self.wrapper.wrap(line) if line.strip() else ['']
                result_lines.extend(wrapped_lines)
            
            # Add paragraph break except after the last paragraph
            if i < len(paragraphs) - 1:
                result_lines.append('')
        
        return result_lines

    def render(self, surface: pygame.Surface, text: str, position: Tuple[int, int], 
            max_height: Optional[int] = None) -> int:
        """
        Render text to a pygame surface with format codes.
        
        Args:
            surface: The pygame surface to render to
            text: The text to render (may include format codes)
            position: (x, y) position to start rendering
            max_height: Optional maximum height to render (to avoid overlapping UI elements)
            
        Returns:
            The final y position after rendering
        """
        if not text:
            return position[1]
            
        x_orig, y = position
        current_color = self.colors[FORMAT_RESET]  # Default color
        line_height = self.font.get_linesize() + self.line_spacing
        
        # Process the text line by line
        lines = text.split('\n')
        for line in lines:
            # Check if we've reached the maximum height
            if max_height and y + line_height > max_height:
                break
                
            x = x_orig  # Reset x position for each line
            
            # Skip empty lines but advance Y position
            if not line:
                y += line_height
                continue
                
            # Process format codes and text segments
            segments = []
            remaining_text = line
            
            # Find and extract all format codes
            while remaining_text:
                # Find the earliest format code
                earliest_pos = len(remaining_text)
                earliest_code = None
                
                for code in self.colors.keys():
                    pos = remaining_text.find(code)
                    if pos != -1 and pos < earliest_pos:
                        earliest_pos = pos
                        earliest_code = code
                
                # No more format codes found
                if earliest_code is None:
                    segments.append((remaining_text, current_color))
                    break
                    
                # Add text before the format code
                if earliest_pos > 0:
                    segments.append((remaining_text[:earliest_pos], current_color))
                    
                # Update color based on the format code
                current_color = self.colors[earliest_code]
                    
                # Continue with the text after the format code
                remaining_text = remaining_text[earliest_pos + len(earliest_code):]
                
            # Render all segments in this line
            for text_segment, color in segments:
                if text_segment:
                    text_surface = self.font.render(text_segment, True, color)
                    surface.blit(text_surface, (x, y))
                    x += text_surface.get_width()
            
            # Move to the next line
            y += line_height
            
        return y  # Return the final y position   
    
    def remove_format_codes(self, text: str) -> str:
        """
        Remove all format codes from text.
        
        Args:
            text: Text with format codes
            
        Returns:
            Clean text without format codes
        """
        if not text:
            return ""
            
        result = text
        for code in self.colors.keys():
            result = result.replace(code, "")
            
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
