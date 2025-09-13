# world/save_manager.py
"""
Handles saving and loading of the game world state to and from files.
"""
import json
import os
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from core.config import *
from items.item_factory import ItemFactory
from npcs.npc_factory import NPCFactory
from npcs.npc_schedules import initialize_npc_schedules
from player import Player
from utils.utils import _serialize_item_reference

if TYPE_CHECKING:
    from world.world import World


class SaveManager:
    def __init__(self, world: 'World'):
        self.world = world

    def save(self, filename: str = DEFAULT_SAVE_FILE) -> bool:
        """Saves the current world state to a JSON file."""
        save_path = self._resolve_save_path(filename, SAVE_GAME_DIR)
        if not save_path: return False
        print(f"Saving game to {save_path}...")
        try:
            if not self.world.player or not self.world.game: return False

            self.world.player.current_region_id = self.world.current_region_id
            self.world.player.current_room_id = self.world.current_room_id

            player_data = self.world.player.to_dict(self.world)
            npc_states = {
                instance_id: npc.to_dict() for instance_id, npc in self.world.npcs.items()
                if npc and not npc.properties.get("is_summoned", False)
            }
            
            dynamic_items = {}
            for region_id, region in self.world.regions.items():
                if not region: continue
                for room_id, room in region.rooms.items():
                    if room and hasattr(room, 'items') and room.items:
                        dynamic_items[f"{region_id}:{room_id}"] = [
                            _serialize_item_reference(item, 1, self.world) for item in room.items if item
                        ]

            save_data = {
                "save_format_version": 3,
                "save_name": filename.replace(".json", ""),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "player": player_data,
                "npc_states": npc_states,
                "room_items_state": dynamic_items,
                "quest_board": self.world.quest_board,
                "time_state": self.world.game.time_manager.get_time_state_for_save(),
                "weather_state": self.world.game.weather_manager.get_weather_state_for_save(),
                # --- FIX: Get respawn_queue from the manager ---
                "respawn_queue": self.world.respawn_manager.respawn_queue,
            }
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'w') as f: json.dump(save_data, f, indent=2, default=str)
            print(f"Game saved successfully to {save_path}.")
            return True
        except Exception as e:
            print(f"{FORMAT_ERROR}Error saving game: {e}{FORMAT_RESET}")
            return False

    def load(self, filename: str = DEFAULT_SAVE_FILE) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Loads a world state from a file.
        Returns: (success_flag, time_data, weather_data)
        """
        save_path = self._resolve_load_path(filename, SAVE_GAME_DIR)
        if not save_path or not os.path.exists(save_path):
            print(f"Save file not found: {filename}. Starting new game.")
            self.world.initialize_new_world()
            return True, None, None

        print(f"Loading save game from {save_path}...")
        try:
            with open(save_path, 'r') as f: save_data = json.load(f)

            self.world.quest_board = save_data.get("quest_board", [])
            # --- FIX: Set respawn_queue on the manager ---
            self.world.respawn_manager.respawn_queue = save_data.get("respawn_queue", [])

            time_state = save_data.get("time_state")
            weather_state = save_data.get("weather_state")

            if "player" in save_data:
                player = Player.from_dict(save_data["player"], self.world)
                if not player: raise ValueError("Player.from_dict returned None")
                self.world.player = player
                self.world.player.world = self.world
                self.world.current_region_id = self.world.player.current_region_id
                self.world.current_room_id = self.world.player.current_room_id
                if not self.world.get_current_room():
                    print(f"Warning: Loaded location invalid. Resetting to respawn point.")
                    self.world.current_region_id = self.world.player.respawn_region_id
                    self.world.current_room_id = self.world.player.respawn_room_id
                    self.world.player.current_region_id = self.world.current_region_id
                    self.world.player.current_room_id = self.world.current_room_id
            else:
                self.world.initialize_new_world()
                return True, None, None

            self.world.npcs = {}
            for region in self.world.regions.values():
                if region:
                    for room in region.rooms.values():
                        if room: room.items = []

            for instance_id, npc_state in save_data.get("npc_states", {}).items():
                template_id = npc_state.get("template_id")
                if template_id:
                    state_overrides = npc_state.copy()
                    state_overrides.pop("template_id", None)
                    npc = NPCFactory.create_npc_from_template(template_id, self.world, instance_id, **state_overrides)
                    if npc: self.world.add_npc(npc)

            initialize_npc_schedules(self.world)
            self.world._load_room_items_from_save(save_data.get("room_items_state", {}))
            
            self.world.quest_manager.ensure_initial_quests()
            # --- FIX: Remove obsolete start_time assignment ---
            return True, time_state, weather_state
        except Exception as e:
            print(f"{FORMAT_ERROR}Critical Error loading save game '{filename}': {e}{FORMAT_RESET}")
            self.world.initialize_new_world()
            return False, None, None

    def _resolve_save_path(self, filename: str, base_dir: str) -> Optional[str]:
        try:
            os.makedirs(base_dir, exist_ok=True)
            safe_filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))
            if not safe_filename.endswith(".json"): safe_filename += ".json"
            return os.path.abspath(os.path.join(base_dir, safe_filename))
        except Exception as e:
            print(f"Error resolving save path '{filename}': {e}")
            return None

    def _resolve_load_path(self, filename: str, base_dir: str) -> Optional[str]:
        try:
            safe_filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))
            if not safe_filename.endswith(".json"): safe_filename += ".json"
            
            path = os.path.abspath(os.path.join(base_dir, safe_filename))
            if os.path.exists(path): return path

            cwd_path = os.path.abspath(safe_filename)
            if os.path.exists(cwd_path): return cwd_path
            
            return None
        except Exception as e:
            print(f"Error resolving load path '{filename}': {e}")
            return None