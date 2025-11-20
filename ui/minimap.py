# ui/minimap.py
import pygame
from typing import Dict, Tuple, Set, Optional, TYPE_CHECKING

from config import FORMAT_RESET, TEXT_COLOR, FORMAT_HIGHLIGHT
# Standard directions map to grid vectors (dx, dy)
# (0,0) is top-left in Pygame, so -y is Up/North.
DIRECTION_VECTORS = {
    "north": (0, -1), "n": (0, -1),
    "south": (0, 1),  "s": (0, 1),
    "east": (1, 0),   "e": (1, 0),
    "west": (-1, 0),  "w": (-1, 0),
    "northeast": (1, -1), "ne": (1, -1),
    "northwest": (-1, -1), "nw": (-1, -1),
    "southeast": (1, 1), "se": (1, 1),
    "southwest": (-1, 1), "sw": (-1, 1)
}

# Colors
MAP_BG_COLOR = (30, 30, 40)
MAP_ROOM_COLOR = (100, 100, 120)
MAP_CURRENT_ROOM_COLOR = (200, 200, 100)
MAP_CONNECTION_COLOR = (80, 80, 80)
MAP_BORDER_COLOR = (150, 150, 150)

# Settings
ROOM_SIZE = 20
CONNECTION_LENGTH = 20
MAP_RADIUS = 3 # How many rooms deep to scan

if TYPE_CHECKING:
    from world.world import World

def draw_minimap(surface: pygame.Surface, rect: pygame.Rect, world: 'World'):
    """
    Draws a visual representation of the local area within the given rect.
    """
    # 1. Background
    pygame.draw.rect(surface, MAP_BG_COLOR, rect)
    pygame.draw.rect(surface, MAP_BORDER_COLOR, rect, 1)

    if not world.player or not world.current_region_id or not world.current_room_id:
        return

    current_region = world.get_current_region()
    if not current_region: return

    # 2. BFS to gather rooms relative to player (0,0)
    # Map: (x, y) -> room_id
    grid_map: Dict[Tuple[int, int], str] = {}
    visited_coords: Set[Tuple[int, int]] = set()
    
    # Queue: (room_id, x, y, depth)
    queue = [(world.current_room_id, 0, 0, 0)]
    grid_map[(0, 0)] = world.current_room_id
    
    rooms_to_draw = [] # List of (x, y, room_obj, is_current)
    connections_to_draw = [] # List of (start_x, start_y, end_x, end_y)

    processed_ids = {world.current_room_id}

    while queue:
        curr_id, cx, cy, depth = queue.pop(0)
        
        curr_room = current_region.get_room(curr_id)
        if not curr_room: continue

        # Determine if we should draw this room
        # Logic: Always draw current room. For others, check 'visited' property.
        # If you want full map always, remove the 'visited' check.
        is_current = (curr_id == world.current_room_id)
        
        # Add to drawing list
        rooms_to_draw.append((cx, cy, curr_room, is_current))
        
        if depth >= MAP_RADIUS:
            continue

        # Process Exits
        for direction, dest_str in curr_room.exits.items():
            # Clean direction (n, s, east, etc)
            d_key = direction.lower()
            if d_key not in DIRECTION_VECTORS:
                continue # Skip vertical (up/down) or weird exits for the 2D map

            vec = DIRECTION_VECTORS[d_key]
            
            # Parse destination
            # If dest is "region:room", ensure it's the same region for the minimap
            if ":" in dest_str:
                dest_region_id, dest_room_id = dest_str.split(":")
                if dest_region_id != world.current_region_id:
                    continue # Don't map across regions (it gets messy)
            else:
                dest_room_id = dest_str

            nx, ny = cx + vec[0], cy + vec[1]

            # Add connection line request
            connections_to_draw.append((cx, cy, nx, ny))

            # Add neighbor to queue if new
            if dest_room_id not in processed_ids:
                processed_ids.add(dest_room_id)
                # Only explore neighbor if the current room was visited (Fog of War logic)
                # Or if you want to see 1 room into the dark, check logic here.
                if curr_room.visited:
                    queue.append((dest_room_id, nx, ny, depth + 1))
                    grid_map[(nx, ny)] = dest_room_id

    # 3. Calculate Center Offset to center the (0,0) room in the Rect
    center_x = rect.centerx
    center_y = rect.centery
    
    # Scaling factor (Grid Unit Size)
    # Room box + Connection length
    grid_unit = ROOM_SIZE + CONNECTION_LENGTH

    # 4. Draw Connections (Lines) first so they are behind rooms
    for (sx, sy, ex, ey) in connections_to_draw:
        start_pos = (center_x + sx * grid_unit, center_y + sy * grid_unit)
        end_pos = (center_x + ex * grid_unit, center_y + ey * grid_unit)
        
        # Clip to rect (simple check)
        if rect.collidepoint(start_pos) and rect.collidepoint(end_pos):
            pygame.draw.line(surface, MAP_CONNECTION_COLOR, start_pos, end_pos, 2)

    # 5. Draw Rooms
    font = pygame.font.SysFont("arial", 10)
    
    for (rx, ry, room_obj, is_current) in rooms_to_draw:
        screen_x = center_x + rx * grid_unit
        screen_y = center_y + ry * grid_unit
        
        # Calculate room box rect
        room_rect = pygame.Rect(0, 0, ROOM_SIZE, ROOM_SIZE)
        room_rect.center = (screen_x, screen_y)
        
        # Visibility check against panel bounds
        if not rect.contains(room_rect):
            continue

        color = MAP_CURRENT_ROOM_COLOR if is_current else MAP_ROOM_COLOR
        if not room_obj.visited and not is_current:
            color = (50, 50, 60) # Darker for unvisited "seen" neighbors

        pygame.draw.rect(surface, color, room_rect)
        pygame.draw.rect(surface, (0,0,0), room_rect, 1) # Border

        # Optional: Draw icons or indicators
        # Check for items/npcs to draw a small dot?
        if room_obj.items:
            # Draw small yellow dot
            pygame.draw.circle(surface, (255, 215, 0), room_rect.center, 2)