# world/world.py
from typing import Dict, List, Optional, Any, Tuple
import time
import json
import os

from core.config import FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET
from player import Player
from world.region import Region
from world.room import Room
from items.item import Item # Import base Item
from items.inventory import Inventory
from npcs.npc import NPC
from utils.text_formatter import format_target_name


class World:
    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.player = Player("Adventurer")
        if not hasattr(self.player, "inventory"): self.player.inventory = Inventory(max_slots=20, max_weight=100.0)
        # --- Initialize equipment properly ---
        if not hasattr(self.player, "equipment"):
             self.player.equipment = { "main_hand": None, "off_hand": None, "body": None, "head": None, "feet": None, "hands": None, "neck": None }
        # --- End Init ---
        self.npcs: Dict[str, NPC] = {}
        self.start_time = time.time()
        self.last_update_time = 0
        self.plugin_data = {}
        self.game = None # To link back to game manager if needed

    def add_region(self, region_id: str, region: Region) -> None: self.regions[region_id] = region
    def get_region(self, region_id: str) -> Optional[Region]: return self.regions.get(region_id)
    def get_current_region(self) -> Optional[Region]: return self.regions.get(self.current_region_id) if self.current_region_id else None
    def get_current_room(self) -> Optional[Room]:
        region = self.get_current_region()
        return region.get_room(self.current_room_id) if region and self.current_room_id else None


    # ... (add_npc, get_npc, get_npcs_in_room, get_current_room_npcs - unchanged) ...
    def add_npc(self, npc: NPC) -> None:
        npc.last_moved = time.time() - self.start_time # Initialize last_moved
        self.npcs[npc.obj_id] = npc
    def get_npc(self, obj_id: str) -> Optional[NPC]: return self.npcs.get(obj_id)
    def get_npcs_in_room(self, region_id: str, room_id: str) -> List[NPC]:
        return [npc for npc in self.npcs.values() if npc.current_region_id == region_id and npc.current_room_id == room_id and npc.is_alive] # Check is_alive
    def get_current_room_npcs(self) -> List[NPC]:
        if not self.current_region_id or not self.current_room_id: return []
        return self.get_npcs_in_room(self.current_region_id, self.current_room_id)

    # ... (update - unchanged) ...
    def update(self) -> List[str]:
        current_time = time.time() - self.start_time
        messages = []
        # Limit updates to prevent excessive processing if tick rate is high
        if current_time - self.last_update_time < 0.5: # e.g., update NPCs max twice per second
            return messages
        self.last_update_time = current_time

        # Update NPCs
        # Iterate over a copy of values in case NPCs are removed during update (e.g., dying)
        for npc in list(self.npcs.values()):
            # Only update living NPCs (respawn logic might be handled elsewhere or here)
            if npc.is_alive:
                npc_message = npc.update(self, current_time)
                if npc_message: messages.append(npc_message)
            # Add respawn logic here if needed based on npc.spawn_time etc.
            # elif npc.should_respawn(current_time): npc.respawn(self); messages.append(...)

        return messages

    # ... (change_room - unchanged) ...
    def change_room(self, direction: str) -> str:
        old_region_id = self.current_region_id; old_room_id = self.current_room_id
        current_room = self.get_current_room()
        if not current_room: return f"{FORMAT_ERROR}You are lost in the void.{FORMAT_RESET}"
        destination_id = current_room.get_exit(direction)
        if not destination_id: return f"{FORMAT_ERROR}You cannot go {direction}.{FORMAT_RESET}"

        new_region_id = self.current_region_id
        new_room_id = destination_id

        # Check for complex exit (e.g., requires key, condition) - Placeholder
        # if isinstance(exit_info, ExitObject) and not exit_info.can_pass(self.player):
        #     return f"{FORMAT_ERROR}{exit_info.fail_message}{FORMAT_RESET}"

        # Handle region transition
        if ":" in destination_id:
             new_region_id, new_room_id = destination_id.split(":")

        target_region = self.get_region(new_region_id)
        if not target_region or not target_region.get_room(new_room_id):
             return f"{FORMAT_ERROR}That path leads to an unknown place.{FORMAT_RESET}"

        # Successfully moving
        self.current_region_id = new_region_id
        self.current_room_id = new_room_id
        new_room = target_region.get_room(new_room_id)
        new_room.visited = True # Mark as visited

        # Trigger hooks/events
        if self.game and hasattr(self.game, "plugin_manager"):
             self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
             self.game.plugin_manager.on_room_enter(new_region_id, new_room_id)

        # Announce region change
        region_change_msg = ""
        if new_region_id != old_region_id:
             region_change_msg = f"{FORMAT_HIGHLIGHT}You have entered {target_region.name}.{FORMAT_RESET}\n\n"

        return region_change_msg + self.look() # Return description of new location


    # ... (look - use get_room_description_for_display) ...
    def look(self) -> str:
        """Get a description of the player's current surroundings."""
        # Delegate to the more comprehensive method
        return self.get_room_description_for_display()

    # ... (get_player_status - unchanged, relies on Player.get_status) ...
    def get_player_status(self) -> str:
        # Player.get_status() now includes inventory and equipment details
        return self.player.get_status()


    # ... (get_items_in_room, get_items_in_current_room - unchanged) ...
    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        region = self.get_region(region_id)
        if region: room = region.get_room(room_id)
        return room.items if region and room and hasattr(room, "items") else []
    def get_items_in_current_room(self) -> List[Item]:
        if not self.current_region_id or not self.current_room_id: return []
        return self.get_items_in_room(self.current_region_id, self.current_room_id)

    # ... (add_item_to_room, remove_item_from_room - unchanged) ...
    def add_item_to_room(self, region_id: str, room_id: str, item: Item) -> bool:
        region = self.get_region(region_id); room = region.get_room(room_id) if region else None
        if not room: return False
        if not hasattr(room, "items"): room.items = []
        room.items.append(item); return True
    def remove_item_from_room(self, region_id: str, room_id: str, obj_id: str) -> Optional[Item]:
        items = self.get_items_in_room(region_id, room_id)
        for i, item in enumerate(items):
            if item.obj_id == obj_id: return items.pop(i)
        return None

    # --- NEW: Helper methods for finding things ---
    def find_item_in_room(self, name: str) -> Optional[Item]:
         """Finds an item in the current room by name/id."""
         items = self.get_items_in_current_room()
         name_lower = name.lower()
         for item in items:
              if name_lower == item.name.lower() or name_lower == item.obj_id:
                   return item
         # Fallback partial match
         for item in items:
              if name_lower in item.name.lower():
                   return item
         return None

    def find_npc_in_room(self, name: str) -> Optional[NPC]:
         """Finds an NPC in the current room by name/id."""
         npcs = self.get_current_room_npcs()
         name_lower = name.lower()
         for npc in npcs:
              if name_lower == npc.name.lower() or name_lower == npc.obj_id:
                   return npc
         # Fallback partial match
         for npc in npcs:
              if name_lower in npc.name.lower():
                   return npc
         return None
    # --- END NEW ---


    # ... (save_to_json, load_from_json - Updated to use Player.to/from_dict which includes equipment) ...
    def save_to_json(self, filename: str) -> bool:
        save_path = self._resolve_save_path(filename)
        if not save_path: return False
        try:
            world_data = {
                "current_region_id": self.current_region_id,
                "current_room_id": self.current_room_id,
                "player": self.player.to_dict(), # Player dict now includes equipment
                "regions": {}, "npcs": {},
                "plugin_data": self.plugin_data
            }
            for region_id, region in self.regions.items():
                region_data = {"name": region.name, "description": region.description, "rooms": {}}
                for room_id, room in region.rooms.items():
                     room_dict = room.to_dict()
                     # Explicitly ensure items list is serialized correctly
                     room_dict["items"] = [item.to_dict() for item in getattr(room, 'items', [])]
                     region_data["rooms"][room_id] = room_dict
                world_data["regions"][region_id] = region_data
            for npc_id, npc in self.npcs.items():
                world_data["npcs"][npc_id] = npc.to_dict()

            with open(save_path, 'w') as f:
                json.dump(world_data, f, indent=2, default=lambda o: '<not serializable>') # Handle non-serializable gently
            print(f"World saved to {save_path}")
            return True
        except Exception as e:
            print(f"Error saving world: {e}"); import traceback; traceback.print_exc(); return False

    def load_from_json(self, filename: str) -> bool:
        file_path = self._resolve_load_path(filename)
        if not file_path: return False
        try:
            with open(file_path, 'r') as f: world_data = json.load(f)

            self.regions = {}; self.npcs = {}; self.start_time = time.time()
            self.plugin_data = world_data.get("plugin_data", {})

            if "player" in world_data:
                self.player = Player.from_dict(world_data["player"])
            else: self.player = Player("Adventurer")

            if not hasattr(self.player, "inventory") or self.player.inventory is None:
                 self.player.inventory = Inventory()
            if not hasattr(self.player, "equipment") or self.player.equipment is None:
                 self.player.equipment = { "main_hand": None, "off_hand": None, "body": None, "head": None, "feet": None, "hands": None, "neck": None }

            # *** Use Region.from_dict ***
            for region_id, region_data in world_data.get("regions", {}).items():
                try:
                    # Pass region_id as obj_id hint for Region.from_dict
                    region_data['obj_id'] = region_data.get('obj_id', region_id)
                    region = Region.from_dict(region_data)
                    self.add_region(region_id, region) # Use the original key for the world dict
                except Exception as region_load_error:
                    print(f"Warning: Failed to load region '{region_data.get('name', region_id)}': {region_load_error}")
                    import traceback
                    traceback.print_exc() # Print traceback for region loading errors
            # *** End Change ***

            current_time = time.time() - self.start_time
            for npc_id, npc_data in world_data.get("npcs", {}).items():
                 try:
                      # Pass npc_id as obj_id hint
                      npc_data['obj_id'] = npc_data.get('obj_id', npc_id)
                      npc = NPC.from_dict(npc_data)
                      npc.last_moved = current_time
                      if not hasattr(npc, "inventory") or npc.inventory is None:
                           npc.inventory = Inventory(max_slots=10, max_weight=50.0)
                      self.npcs[npc.obj_id] = npc # Use npc.obj_id as key now
                 except Exception as npc_load_error:
                      print(f"Warning: Failed to load NPC '{npc_data.get('name', npc_id)}': {npc_load_error}")
                      import traceback
                      traceback.print_exc() # Print traceback for NPC loading errors

            self.current_region_id = world_data.get("current_region_id")
            self.current_room_id = world_data.get("current_room_id")

            if not self.get_current_room():
                 print(f"Warning: Loaded location {self.current_region_id}:{self.current_room_id} is invalid. Resetting.")
                 if self.regions:
                      first_region_id = next(iter(self.regions))
                      first_region = self.regions[first_region_id]
                      if first_region.rooms:
                           self.current_region_id = first_region_id
                           self.current_room_id = next(iter(first_region.rooms))
                           print(f"Reset location to {self.current_region_id}:{self.current_room_id}")
                      else: self.current_region_id = self.current_room_id = None
                 else: self.current_region_id = self.current_room_id = None

            print(f"World loaded from {file_path}. Location: {self.current_region_id}:{self.current_room_id}")
            return True
        except json.JSONDecodeError as json_err:
             print(f"FATAL: Error decoding JSON from {file_path}: {json_err}")
             return False
        except Exception as e:
            print(f"Error loading world: {e}"); import traceback; traceback.print_exc(); return False

    # Helper for resolving save/load paths (internal)
    def _resolve_save_path(self, filename):
         paths = [filename, os.path.join(os.getcwd(), filename)]
         # Add parent dir path if relevant
         parent_dir = os.path.dirname(os.getcwd())
         if parent_dir != os.getcwd(): paths.append(os.path.join(parent_dir, filename))
         # Try to use existing file path first
         for path in paths:
              if os.path.exists(path): return path
         # Fallback: use path with writable directory
         for path in paths:
             try:
                 dir_path = os.path.dirname(path) or os.getcwd()
                 if os.path.exists(dir_path) and os.access(dir_path, os.W_OK): return path
             except: continue
         # Default to current dir if all else fails
         return os.path.join(os.getcwd(), filename)

    def _resolve_load_path(self, filename):
        paths = [filename, os.path.join(os.getcwd(), filename)]
        parent_dir = os.path.dirname(os.getcwd())
        if parent_dir != os.getcwd(): paths.append(os.path.join(parent_dir, filename))
        # Maybe add script's dir path too?
        script_dir = os.path.dirname(os.path.abspath(__file__)) # world dir
        paths.append(os.path.join(script_dir, "..", filename)) # Game root?

        for path in paths:
            if os.path.exists(path):
                print(f"Found load file at: {path}")
                return path
        print(f"Error: Cannot find load file '{filename}'")
        print(f"Searched: {paths}")
        return None


    # ... (set_plugin_data, get_plugin_data - unchanged) ...
    def set_plugin_data(self, plugin_id: str, key: str, value: Any) -> None:
        if plugin_id not in self.plugin_data: self.plugin_data[plugin_id] = {}
        self.plugin_data[plugin_id][key] = value
    def get_plugin_data(self, plugin_id: str, key: str, default: Any = None) -> Any:
        return self.plugin_data.get(plugin_id, {}).get(key, default)


    # ... (find_path - unchanged) ...
    def find_path(self, source_region_id: str, source_room_id: str,
                 target_region_id: str, target_room_id: str) -> Optional[List[str]]:
        start_node = (source_region_id, source_room_id)
        goal_node = (target_region_id, target_room_id)
        if start_node == goal_node: return []

        queue = [(0, start_node, [])] # (cost, node, path)
        visited = {start_node}
        cheapest_path_to = {start_node: []} # Store the actual path directions

        import heapq
        pq = [(0, start_node)] # (priority, node) for A*
        g_score = {start_node: 0} # Cost from start

        while pq:
            current_priority, current_node = heapq.heappop(pq)

            if current_node == goal_node:
                return cheapest_path_to[goal_node]

            current_region_id, current_room_id = current_node
            region = self.get_region(current_region_id)
            if not region: continue
            room = region.get_room(current_room_id)
            if not room: continue

            for direction, exit_id in room.exits.items():
                next_region_id, next_room_id = current_region_id, exit_id
                if ":" in exit_id: next_region_id, next_room_id = exit_id.split(":")

                next_node = (next_region_id, next_room_id)

                # Basic validation if next room/region exists
                next_region = self.get_region(next_region_id)
                if not next_region or not next_region.get_room(next_room_id): continue # Skip invalid exits

                new_cost = g_score[current_node] + 1 # Simple cost = 1 per step

                if next_node not in g_score or new_cost < g_score[next_node]:
                    g_score[next_node] = new_cost
                    # Heuristic: 0 if same region, 1 if different (very basic)
                    heuristic = 0 if next_region_id == target_region_id else 1
                    priority = new_cost + heuristic
                    heapq.heappush(pq, (priority, next_node))
                    # Update path
                    cheapest_path_to[next_node] = cheapest_path_to[current_node] + [direction]

        return None # No path found


    # ... (get_room_description_for_display - unchanged) ...
    def get_room_description_for_display(self) -> str:
        current_room = self.get_current_room()
        if not current_room: return f"{FORMAT_ERROR}You are nowhere.{FORMAT_RESET}"
        time_period = self.get_plugin_data("time_plugin", "time_period")
        weather = self.get_plugin_data("weather_plugin", "current_weather")
        room_desc = current_room.get_full_description(time_period, weather)
        npcs_in_room = self.get_current_room_npcs()
        npcs_text = []
        if npcs_in_room:
            for npc in npcs_in_room:
                formatted_name = format_target_name(self.player, npc) # <<< USE FORMATTER
                activity = f" ({npc.ai_state['current_activity']})" if hasattr(npc, "ai_state") and "current_activity" in npc.ai_state else ""
                combat_status = f" {FORMAT_ERROR}(Fighting!){FORMAT_RESET}" if npc.in_combat else ""
                # Use formatted_name in the message
                npcs_text.append(f"{formatted_name} is here{activity}{combat_status}.")

        items_in_room = self.get_items_in_current_room()
        # *** Optional: Color items based on rarity/value? For now, keep as is ***
        items_text = [f"There is {FORMAT_CATEGORY}{item.name}{FORMAT_RESET} here." for item in items_in_room]

        full_description = room_desc
        if npcs_text: full_description += "\n\n" + "\n".join(npcs_text)
        if items_text: full_description += "\n\n" + "\n".join(items_text)
        return full_description

    def is_location_safe(self, region_id: str, room_id: Optional[str] = None) -> bool:
        """
        Check if a given region (and optionally room) is considered safe
        from hostile monster spawns and entry.
        """
        region = self.get_region(region_id)
        if not region:
            return False # Unknown regions are not considered safe

        # Check the region's safe_zone property
        if region.get_property("safe_zone", False):
            return True

        # Optional: Add specific room checks here if needed later
        # e.g., if room_id in config.SAFE_ROOMS_EVEN_IN_DANGEROUS_REGIONS: return True

        return False # Default to not safe if region isn't marked
