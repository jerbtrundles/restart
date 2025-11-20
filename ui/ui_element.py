# ui/ui_element.py
import pygame
from typing import Callable, Tuple, Optional, Any, List
from utils.text_formatter import ClickableZone

# UI Colors
PANEL_BG_COLOR = (30, 30, 35)
PANEL_BORDER_COLOR = (80, 80, 90)
HEADER_BG_COLOR = (50, 50, 60)
HEADER_TEXT_COLOR = (200, 200, 200)
HEADER_HEIGHT = 24

# Renderer signature: (surface, context, hotspots_list) -> None
ContentRenderer = Callable[[pygame.Surface, Any, List[ClickableZone]], None]

class UIPanel:
    def __init__(self, 
                 height: int, 
                 title: str,
                 content_renderer: ContentRenderer):
        
        self.rect = pygame.Rect(0, 0, 100, height) 
        self.title = title
        self.content_renderer = content_renderer
        
        self.font = pygame.font.SysFont("arial", 14, bold=True)
        
        self.surface: Optional[pygame.Surface] = None
        self.content_surface: Optional[pygame.Surface] = None
        
        # Hotspots relative to the content surface (0,0 is top-left of content area)
        self.hotspots: List[ClickableZone] = []

    def resize(self, width: int, height: int):
        width = max(1, width)
        height = max(1, height)

        if self.surface and self.rect.width == width and self.rect.height == height:
            return
            
        self.rect.width = width
        self.rect.height = height
        self.surface = pygame.Surface((width, height))
        
        content_h = max(1, height - HEADER_HEIGHT)
        self.content_surface = pygame.Surface((width, content_h))

    def update(self, context_data: Any):
        if not self.surface or not self.content_surface: return

        # 1. Clear Content & Hotspots
        self.content_surface.fill(PANEL_BG_COLOR)
        self.hotspots = []
        
        # 2. Render Content (Populates self.hotspots)
        self.content_renderer(self.content_surface, context_data, self.hotspots)
        
        # 3. Draw Panel Frame
        self.surface.fill(PANEL_BORDER_COLOR) 
        pygame.draw.rect(self.surface, PANEL_BG_COLOR, (1, 1, self.rect.width - 2, self.rect.height - 2))
        
        # Header
        pygame.draw.rect(self.surface, HEADER_BG_COLOR, (1, 1, self.rect.width - 2, HEADER_HEIGHT - 1))
        title_surf = self.font.render(self.title, True, HEADER_TEXT_COLOR)
        self.surface.blit(title_surf, (5, 4))
        
        # Blit Content
        self.surface.blit(self.content_surface, (0, HEADER_HEIGHT))

    def draw(self, screen: pygame.Surface, x: int, y: int):
        self.rect.x = x
        self.rect.y = y
        if self.surface:
            screen.blit(self.surface, (x, y))