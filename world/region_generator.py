# world/region_generator.py
"""
Handles the procedural generation of new, dynamic game regions based on themes.
"""
import json
import os
import random
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from config import DATA_DIR, FORMAT_ERROR, FORMAT_RESET
from world.region import Region
from world.room import Room

if TYPE_CHECKING:
    from world.world import World


class RegionGenerator:
    def __init__(self, world: "World"):
        self.world = world
        self.themes: Dict[str, Any] = {}
        self.placeholders: Dict[str, List[str]] = {}
        self.load_themes()

    def load_themes(self):
        """Loads region generation themes and placeholders from a JSON file."""
        theme_path = os.path.join(DATA_DIR, "regions", "dynamic_themes.json")
        try:
            with open(theme_path, 'r') as f:
                data = json.load(f)
                self.themes = data.get("themes", {})
                self.placeholders = data.get("placeholders", {})
        except FileNotFoundError:
            print(f"{FORMAT_ERROR}Error: Dynamic theme file not found at '{theme_path}'.{FORMAT_RESET}")
        except json.JSONDecodeError:
            print(f"{FORMAT_ERROR}Error: Could not decode JSON from '{theme_path}'.{FORMAT_RESET}")

    def _format_with_placeholders(self, text: str) -> str:
        """Replaces placeholders like {Adjective} with random words from the theme file."""
        for key, words in self.placeholders.items():
            # Handle {Noun} (capitalized) and {noun} (lowercase)
            if f"{{{key.capitalize()}}}" in text:
                text = text.replace(f"{{{key.capitalize()}}}", random.choice(words).capitalize())
            if f"{{{key.lower()}}}" in text:
                text = text.replace(f"{{{key.lower()}}}", random.choice(words).lower())
        return text

    def generate_region(self, theme_name: str, num_rooms: int) -> Optional[Tuple[Region, str]]:
        """
        Generates a new Region object based on a theme, returning the Region and its entry room ID.
        This uses the 3D geometric generation algorithm.
        """
        theme = self.themes.get(theme_name)
        if not theme:
            print(f"{FORMAT_ERROR}RegionGenerator: Theme '{theme_name}' not found.{FORMAT_RESET}")
            return None

        # --- Start of 3D Geometric Generation Algorithm ---
        direction_vectors = {
            "north": (0, -1, 0), "south": (0, 1, 0), "east": (1, 0, 0), "west": (-1, 0, 0),
            "northeast": (1, -1, 0), "northwest": (-1, -1, 0), "southeast": (1, 1, 0), "southwest": (-1, 1, 0),
            "up": (0, 0, 1), "down": (0, 0, -1)
        }
        opposite_direction = {
            "north": "south", "south": "north", "east": "west", "west": "east",
            "northeast": "southwest", "southwest": "northeast", "northwest": "southeast", "southeast": "northwest",
            "up": "down", "down": "up"
        }
        planar_directions = ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"]
        vertical_directions = ["up", "down"]

        coords_to_id: Dict[Tuple[int, int, int], str] = {}
        id_to_coords: Dict[str, Tuple[int, int, int]] = {}
        rooms_data: Dict[str, Any] = {}
        
        # 1. Create the Region object and its entry room
        region_id = f"dynamic_{theme_name}_{uuid.uuid4().hex[:6]}"
        region_name = self._format_with_placeholders(random.choice(theme.get("name_templates", ["A Mysterious Place"])))
        new_region = Region(name=region_name, description=theme.get("description", ""), obj_id=region_id)
        new_region.spawner_config = theme.get("spawner", {})

        entry_room_id = f"room_entry"
        coords_to_id[(0, 0, 0)] = entry_room_id
        id_to_coords[entry_room_id] = (0, 0, 0)
        rooms_data[entry_room_id] = { "name": "Entrance", "exits": {} }
        frontier = [entry_room_id]

        # 2. Grow the region
        for i in range(1, num_rooms):
            new_room_id = f"room_{i}"
            connection_made = False
            random.shuffle(frontier)
            for current_room_id in frontier:
                cx, cy, cz = id_to_coords[current_room_id]
                
                direction_pool = planar_directions + vertical_directions if random.random() < 0.2 else vertical_directions + planar_directions
                random.shuffle(direction_pool)
                
                for direction in direction_pool:
                    dx, dy, dz = direction_vectors[direction]
                    next_coords = (cx + dx, cy + dy, cz + dz)
                    if next_coords not in coords_to_id:
                        coords_to_id[next_coords] = new_room_id
                        id_to_coords[new_room_id] = next_coords
                        rooms_data[new_room_id] = { "name": random.choice(theme.get("room_names", ["A Room"])), "exits": {} }
                        rooms_data[current_room_id]["exits"][direction] = new_room_id
                        rooms_data[new_room_id]["exits"][opposite_direction[direction]] = current_room_id
                        frontier.append(new_room_id)
                        connection_made = True
                        break
                if connection_made: break
            if not connection_made: break

        # 3. Add extra connections
        num_extra_connections = random.randint(num_rooms // 2, num_rooms)
        for _ in range(num_extra_connections):
            room_id = random.choice(list(id_to_coords.keys()))
            cx, cy, cz = id_to_coords[room_id]
            possible_connections = [d for d, (dx, dy, dz) in direction_vectors.items() if (cx + dx, cy + dy, cz + dz) in coords_to_id and d not in rooms_data[room_id]["exits"]]
            if possible_connections:
                chosen_direction = random.choice(possible_connections)
                nx, ny, nz = (cx + direction_vectors[chosen_direction][0], cy + direction_vectors[chosen_direction][1], cz + direction_vectors[chosen_direction][2])
                neighbor_id = coords_to_id[(nx, ny, nz)]
                rooms_data[room_id]["exits"][chosen_direction] = neighbor_id
                rooms_data[neighbor_id]["exits"][opposite_direction[chosen_direction]] = room_id
        
        # 4. Finalize Room objects with descriptions and add to Region
        for room_id, data in rooms_data.items():
            desc = self._format_with_placeholders(random.choice(theme.get("room_descriptions", ["An empty space."])))
            room = Room(name=data["name"], description=desc, exits=data["exits"], obj_id=room_id)
            new_region.add_room(room_id, room)

        return new_region, entry_room_id