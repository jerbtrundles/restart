"""
utils/colored_text.py
Colored text rendering module for the MUD game.
"""
import pygame
from typing import List, Tuple, Dict, Optional


class ColoredText:
    """
    A utility class for rendering text with color formatting codes.
    """
    def __init__(self, font, format_colors: Dict[str, Tuple[int, int, int]]):
        """
        Initialize the ColoredText renderer.
        
        Args:
            font: The Pygame font to use for rendering.
            format_colors: A dictionary mapping format codes to RGB color tuples.
        """
        self.font = font
        self.format_colors = format_colors
        self.default_color = (255, 255, 255)

    def render(self, surface, text: str, position: Tuple[int, int], default_color=None) -> None:
        """
        Render text with color formatting codes to the given surface.
        Properly handles newlines in the text.
        
        Args:
            surface: The Pygame surface to render onto.
            text: The text to render, which may contain format codes.
            position: The (x, y) position to start rendering.
            default_color: The default text color to use. If None, uses the instance default.
        """
        if default_color is None:
            default_color = self.default_color
        
        x_orig, y = position  # Keep track of original x position for newlines
        x = x_orig
        
        # Split the text into lines first
        lines = text.split('\n')
        line_height = self.font.get_linesize()
        
        for line_idx, line in enumerate(lines):
            # Reset x position for each new line
            x = x_orig
            
            # For empty lines, just advance y
            if not line:
                y += line_height
                continue
                
            # Split the line into segments based on format codes
            segments = self._split_by_format_codes(line)
            
            # Render each segment with its color
            current_color = default_color
            for segment in segments:
                if segment in self.format_colors:
                    # This is a format code, update the current color
                    current_color = self.format_colors[segment]
                else:
                    # This is regular text, render it
                    # Skip any segments containing only control characters
                    if segment and any(ord(c) >= 32 for c in segment):
                        # Replace any control characters with spaces
                        cleaned_segment = ''.join(c if ord(c) >= 32 else ' ' for c in segment)
                        
                        if cleaned_segment:  # Only render non-empty segments
                            text_surface = self.font.render(cleaned_segment, True, current_color)
                            surface.blit(text_surface, (x, y))
                            x += text_surface.get_width()
            
            # Move to the next line
            y += line_height    
    
    def remove_format_codes(self, text: str) -> str:
        """
        Remove all format codes from the text and normalize newlines.
        
        Args:
            text: The text containing format codes.
            
        Returns:
            Text with all format codes removed.
        """
        if not text:
            return ""
            
        # First remove all format codes
        result = text
        for code in self.format_colors.keys():
            result = result.replace(code, "")
        
        # Normalize newlines
        result = result.replace('\r\n', '\n').replace('\r', '\n')
        
        # Replace control characters (except newlines) with spaces
        result = ''.join(c if c == '\n' or ord(c) >= 32 else ' ' for c in result)
        
        # Collapse multiple consecutive newlines into at most two
        while '\n\n\n' in result:
            result = result.replace('\n\n\n', '\n\n')
        
        return result
    
    def _split_by_format_codes(self, text: str) -> List[str]:
        """
        Split the text into segments, separating format codes from regular text.
        
        Args:
            text: The text to split.
            
        Returns:
            A list of segments, where format codes are separate items.
        """
        result = []
        
        # Start with the whole text
        current_text = text
        
        while current_text:
            # Find the earliest format code
            earliest_pos = len(current_text)
            earliest_code = None
            
            for code in self.format_colors.keys():
                pos = current_text.find(code)
                if pos != -1 and pos < earliest_pos:
                    earliest_pos = pos
                    earliest_code = code
            
            if earliest_code is None:
                # No more format codes, add the remaining text
                result.append(current_text)
                break
            
            # Add the text before the format code
            if earliest_pos > 0:
                result.append(current_text[:earliest_pos])
                
            # Add the format code itself
            result.append(earliest_code)
            
            # Continue with the rest of the text
            current_text = current_text[earliest_pos + len(earliest_code):]
        
        return result