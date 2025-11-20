# ui/ui_manager.py
import pygame
from typing import List, Any, Optional, Tuple
from ui.ui_element import UIPanel, HEADER_HEIGHT
from utils.text_formatter import ClickableZone

GAP = 10
PREVIEW_BORDER_COLOR = (100, 200, 255)
PREVIEW_FILL_COLOR = (100, 200, 255, 40)
SHADOW_COLOR = (0, 0, 0, 128)
SHADOW_OFFSET = (8, 8)

class UIManager:
    def __init__(self):
        self.left_dock: List[UIPanel] = []
        self.right_dock: List[UIPanel] = []
        self.left_bounds = pygame.Rect(0, 0, 100, 100)
        self.right_bounds = pygame.Rect(0, 0, 100, 100)
        
        self.dragging_panel: Optional[UIPanel] = None
        self.drag_offset: Tuple[int, int] = (0, 0)
        self.drag_pos: Tuple[int, int] = (0, 0)

        # Collected absolute hotspots for the current frame
        self.active_hotspots: List[ClickableZone] = []

    def add_panel(self, panel: UIPanel, side: str = "left"):
        if side == "left": self.left_dock.append(panel)
        else: self.right_dock.append(panel)

    def update_bounds(self, left_rect: pygame.Rect, right_rect: pygame.Rect):
        self.left_bounds = left_rect
        self.right_bounds = right_rect

    def handle_event(self, event: pygame.event.Event) -> bool:
        # ... (Same dragging logic as before) ...
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                all_panels = self.left_dock + self.right_dock
                for panel in all_panels:
                    header_rect = pygame.Rect(panel.rect.x, panel.rect.y, panel.rect.width, HEADER_HEIGHT)
                    if header_rect.collidepoint(event.pos):
                        self.dragging_panel = panel
                        self.drag_offset = (event.pos[0] - panel.rect.x, event.pos[1] - panel.rect.y)
                        self.drag_pos = event.pos
                        if panel in self.left_dock: self.left_dock.remove(panel)
                        if panel in self.right_dock: self.right_dock.remove(panel)
                        return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and self.dragging_panel:
                self._drop_panel()
                self.dragging_panel = None
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.dragging_panel:
                self.drag_pos = event.pos
                return True

        return False

    def _get_drop_info(self) -> Tuple[List[UIPanel], int, pygame.Rect]:
        mx, my = self.drag_pos
        dist_to_left = abs(mx - self.left_bounds.centerx)
        dist_to_right = abs(mx - self.right_bounds.centerx)
        
        target_list = self.left_dock if dist_to_left < dist_to_right else self.right_dock
        target_rect = self.left_bounds if dist_to_left < dist_to_right else self.right_bounds
        
        panel_y = my - self.drag_offset[1]
        insert_index = len(target_list)
        for i, existing_panel in enumerate(target_list):
            if panel_y < existing_panel.rect.centery:
                insert_index = i
                break
        return target_list, insert_index, target_rect

    def _drop_panel(self):
        if not self.dragging_panel: return
        target_list, insert_index, _ = self._get_drop_info()
        target_list.insert(insert_index, self.dragging_panel)

    def update_and_draw(self, screen: pygame.Surface, context_data: Any):
        self.active_hotspots = [] # Clear previous frame

        target_dock_list: Optional[List[UIPanel]] = None
        insert_index: int = -1
        target_dock_bounds: Optional[pygame.Rect] = None
        
        if self.dragging_panel:
            target_dock_list, insert_index, target_dock_bounds = self._get_drop_info()

        def draw_dock(dock_list: List[UIPanel], bounds: pygame.Rect):
            y = bounds.y
            width = bounds.width
            
            for i, panel in enumerate(dock_list):
                if self.dragging_panel and dock_list is target_dock_list and i == insert_index:
                     if self.dragging_panel: 
                        y += self.dragging_panel.rect.height + GAP

                panel.resize(width, panel.rect.height)
                panel.update(context_data)
                panel.draw(screen, bounds.x, y)
                
                # --- TRANSLATE HOTSPOTS ---
                # Panel content starts at (x, y + HEADER_HEIGHT) relative to screen
                content_abs_x = bounds.x
                content_abs_y = y + HEADER_HEIGHT
                
                for zone in panel.hotspots:
                    # Create new Rect in screen space
                    abs_rect = pygame.Rect(
                        content_abs_x + zone.rect.x,
                        content_abs_y + zone.rect.y,
                        zone.rect.width,
                        zone.rect.height
                    )
                    # Only add if visible (simple clip check against panel content area)
                    # For now, assume content fits.
                    self.active_hotspots.append(ClickableZone(abs_rect, zone.command))

                y += panel.rect.height + GAP

        draw_dock(self.left_dock, self.left_bounds)
        draw_dock(self.right_dock, self.right_bounds)
        
        if self.dragging_panel and target_dock_bounds and target_dock_list is not None:
            draw_x = self.drag_pos[0] - self.drag_offset[0]
            draw_y = self.drag_pos[1] - self.drag_offset[1]
            
            # Preview
            preview_y = target_dock_bounds.y
            for i in range(insert_index):
                preview_y += target_dock_list[i].rect.height + GAP
            
            preview_rect = pygame.Rect(target_dock_bounds.x, preview_y, target_dock_bounds.width, self.dragging_panel.rect.height)
            
            preview_surf = pygame.Surface((preview_rect.width, preview_rect.height), pygame.SRCALPHA)
            preview_surf.fill(PREVIEW_FILL_COLOR)
            screen.blit(preview_surf, (preview_rect.x, preview_rect.y))
            pygame.draw.rect(screen, PREVIEW_BORDER_COLOR, preview_rect, 2)
            
            # Dragging Panel
            self.dragging_panel.resize(target_dock_bounds.width, self.dragging_panel.rect.height)
            self.dragging_panel.update(context_data)
            
            shadow_rect = pygame.Rect(draw_x + SHADOW_OFFSET[0], draw_y + SHADOW_OFFSET[1], self.dragging_panel.rect.width, self.dragging_panel.rect.height)
            shadow_surf = pygame.Surface((shadow_rect.width, shadow_rect.height), pygame.SRCALPHA)
            shadow_surf.fill(SHADOW_COLOR)
            screen.blit(shadow_surf, (shadow_rect.x, shadow_rect.y))

            self.dragging_panel.draw(screen, draw_x, draw_y)