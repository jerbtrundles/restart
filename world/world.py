# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Updated `get_room_description_for_display` to show both friendly and hostile NPCs.
# - NPCs are now separated into "People here:" and "Hostiles:" categories for immediate clarity.
# - Hostile NPCs will now appear in the main text panel upon entering a room.

from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
import time
import json
import os
import uuid
import heapq

from core.config import *
from player import Player
from world.region import Region
from world.room import Room
from items.item import Item
from items.key import Key
from items.inventory import Inventory
from npcs.npc import NPC
from utils.text_formatter import format_target_name
from items.item_factory import ItemFactory
from npcs.npc_factory import NPCFactory
from npcs.npc_schedules import initialize_npc_schedules
from utils.utils import _serialize_item_reference, format_name_for_display, get_article, simple_plural

if TYPE_CHECKING:
    from core.game_manager import GameManager

class World:
    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.item_templates: Dict[str, Dict[str, Any]] = {}
        self.npc_templates: Dict[str, Dict[str, Any]] = {}
        self.player: Optional['Player'] = None
        self.npcs: Dict[str, NPC] = {}
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.start_time = time.time()
        self.last_update_time = 0
        self.plugin_data = {}

        if TYPE_CHECKING:
            self.game: Optional['GameManager'] = None

        self._load_definitions()

    def _load_definitions(self):
        print("Loading definitions...")
        self._load_item_templates()
        self._load_npc_templates()
        self._load_regions()
        print("Definitions loaded.")

    def _load_item_templates(self):
        self.item_templates = {}
        if not os.path.isdir(ITEM_TEMPLATE_DIR):
            print(f"Warning: Item template directory not found: {ITEM_TEMPLATE_DIR}")
            return
        for filename in os.listdir(ITEM_TEMPLATE_DIR):
            if filename.endswith(".json"):
                path = os.path.join(ITEM_TEMPLATE_DIR, filename)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        for item_id, template_data in data.items():
                            if item_id in self.item_templates:
                                print(f"Warning: Duplicate item template ID '{item_id}' found in {filename}.")
                            if "name" not in template_data or "type" not in template_data:
                                print(f"Warning: Item template '{item_id}' in {filename} is missing 'name' or 'type'. Skipping.")
                                continue
                            self.item_templates[item_id] = template_data
                except Exception as e:
                    print(f"Error loading item templates from {path}: {e}")

    def _load_npc_templates(self):
        self.npc_templates = {}
        if not os.path.isdir(NPC_TEMPLATE_DIR):
            print(f"Warning: NPC template directory not found: {NPC_TEMPLATE_DIR}")
            return
        for filename in os.listdir(NPC_TEMPLATE_DIR):
            if filename.endswith(".json"):
                path = os.path.join(NPC_TEMPLATE_DIR, filename)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        for template_id, template_data in data.items():
                            if template_id in self.npc_templates:
                                print(f"Warning: Duplicate NPC template ID '{template_id}' found in {filename}.")
                            if "name" not in template_data:
                                print(f"Warning: NPC template '{template_id}' in {filename} is missing 'name'. Skipping.")
                                continue
                            self.npc_templates[template_id] = template_data
                except Exception as e:
                    print(f"Error loading NPC templates from {path}: {e}")
        print(f"[NPC Templates] Loaded {len(self.npc_templates)} NPC templates.")

    def _load_regions(self):
        self.regions = {}
        if not os.path.isdir(REGION_DIR):
            print(f"Warning: Region directory not found: {REGION_DIR}")
            return
        for filename in os.listdir(REGION_DIR):
            if filename.endswith(".json"):
                path = os.path.join(REGION_DIR, filename)
                try:
                    with open(path, 'r') as f:
                        region_data = json.load(f)
                        region_id = filename[:-5]
                        region_data['obj_id'] = region_id
                        region = Region.from_dict(region_data)
                        self.add_region(region_id, region)
                except Exception as e:
                    print(f"Error loading region from {path}: {e}")

    def initialize_new_world(self, start_region="town", start_room="town_square"):
         print("Initializing new world state...")
         self.player = Player("Adventurer")
         self.player.world = self
         starter_dagger = ItemFactory.create_item_from_template("item_starter_dagger", self)
         potion = ItemFactory.create_item_from_template("item_healing_potion_small", self)
         if starter_dagger: self.player.inventory.add_item(starter_dagger)
         if potion: self.player.inventory.add_item(potion, 2)
         self.current_region_id = start_region
         self.current_room_id = start_room
         if self.player:
            self.player.current_region_id = start_region
            self.player.current_room_id = start_room
         self.npcs = {}
         for region in self.regions.values():
              for room in region.rooms.values():
                   room.items = []
         for region_id, region in self.regions.items():
              for room_id, room in region.rooms.items():
                   for item_ref in getattr(room, 'initial_item_refs', []):
                        item_id = item_ref.get("item_id")
                        qty = item_ref.get("quantity", 1)
                        overrides = item_ref.get("properties_override", {})
                        if item_id:
                             item = ItemFactory.create_item_from_template(item_id, self, **overrides)
                             if item:
                                  for _ in range(qty): room.add_item(item)
                             else: print(f"Warning: Failed to create initial item '{item_id}' in {region_id}:{room_id}")
                   for npc_ref in getattr(room, 'initial_npc_refs', []):
                        template_id = npc_ref.get("template_id")
                        instance_id = npc_ref.get("instance_id")
                        if not instance_id: instance_id = f"{template_id}_{uuid.uuid4().hex[:8]}"
                        if template_id and instance_id not in self.npcs:
                             overrides = npc_ref.get("overrides", {})
                             overrides.update({"current_region_id": region_id, "current_room_id": room_id, "home_region_id": region_id, "home_room_id": room_id})
                             npc = NPCFactory.create_npc_from_template(template_id, self, instance_id, **overrides)
                             if npc: self.add_npc(npc)
                             else: print(f"Warning: Failed to create initial NPC '{template_id}' in {region_id}:{room_id}")
         
         initialize_npc_schedules(self)
         
         self.start_time = time.time()
         self.last_update_time = 0
         self.plugin_data = {}
         print(f"New world initialized. Player at {start_region}:{start_room}")

    def load_save_game(self, filename: str = DEFAULT_SAVE_FILE) -> bool:
        save_path = self._resolve_load_path(filename, SAVE_GAME_DIR)
        if not save_path or not os.path.exists(save_path):
            print(f"Save file not found: {filename}. Starting new game.")
            self.initialize_new_world()
            return True
        print(f"Loading save game from {save_path}...")
        try:
            with open(save_path, 'r') as f: save_data = json.load(f)
            if "player" in save_data:
                self.player = Player.from_dict(save_data["player"], self)
                if not self.player: raise ValueError("Player.from_dict returned None")
                self.player.world = self
                self.current_region_id = self.player.current_region_id
                self.current_room_id = self.player.current_room_id
                if not self.get_current_room():
                    print(f"Warning: Loaded location invalid. Resetting to respawn.")
                    self.current_region_id = self.player.respawn_region_id
                    self.current_room_id = self.player.respawn_room_id
                    self.player.current_region_id = self.current_region_id
                    self.player.current_room_id = self.current_room_id
            else:
                self.initialize_new_world()
                return True
            self.npcs = {}
            for region in self.regions.values():
                if region:
                    for room in region.rooms.values():
                        if room: room.items = []
            for instance_id, npc_state in save_data.get("npc_states", {}).items():
                template_id = npc_state.get("template_id")
                if template_id:
                    state_overrides = npc_state.copy()
                    state_overrides.pop("template_id", None)
                    npc = NPCFactory.create_npc_from_template(template_id, self, instance_id, **state_overrides)
                    if npc: self.add_npc(npc)
            
            initialize_npc_schedules(self)

            for location_key, item_refs in save_data.get("room_items_state", {}).items():
                region_id, room_id = location_key.split(":")
                region = self.get_region(region_id)
                room = region.get_room(room_id) if region else None
                if room:
                    for item_ref in item_refs:
                        if item_ref and "item_id" in item_ref:
                            item = ItemFactory.create_item_from_template(item_ref["item_id"], self, **item_ref.get("properties_override", {}))
                            if item: room.add_item(item)
            self.plugin_data = save_data.get("plugin_data", {})
            self.start_time = time.time()
            return True
        except Exception as e:
            print(f"{FORMAT_ERROR}Critical Error loading save game '{filename}': {e}{FORMAT_RESET}")
            self.initialize_new_world()
            return False

    def save_game(self, filename: str = DEFAULT_SAVE_FILE) -> bool:
        save_path = self._resolve_save_path(filename, SAVE_GAME_DIR)
        if not save_path: return False
        print(f"Saving game to {save_path}...")
        try:
            if not self.player: return False
            self.player.current_region_id = self.current_region_id
            self.player.current_room_id = self.current_room_id
            player_data = self.player.to_dict(self)
            npc_states = {instance_id: npc.to_dict() for instance_id, npc in self.npcs.items() if npc and not npc.properties.get("is_summoned", False)}
            dynamic_items = {}
            for region_id, region in self.regions.items():
                if not region: continue
                for room_id, room in region.rooms.items():
                    if room and hasattr(room, 'items') and room.items:
                        dynamic_items[f"{region_id}:{room_id}"] = [_serialize_item_reference(item, 1, self) for item in room.items if item]
            save_data = {"save_format_version": 3, "save_name": filename.replace(".json", ""), "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "player": player_data, "npc_states": npc_states, "room_items_state": dynamic_items, "plugin_data": self.plugin_data}
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'w') as f: json.dump(save_data, f, indent=2, default=str)
            print(f"Game saved successfully to {save_path}.")
            return True
        except Exception as e:
            print(f"{FORMAT_ERROR}Error saving game: {e}{FORMAT_RESET}")
            return False

    def get_region(self, region_id: str) -> Optional[Region]: return self.regions.get(region_id)
    def get_current_region(self) -> Optional[Region]: return self.regions.get(self.current_region_id) if self.current_region_id else None
    def get_current_room(self) -> Optional[Room]:
        region = self.get_current_region()
        return region.get_room(self.current_room_id) if region and self.current_room_id else None
    def add_region(self, region_id: str, region: Region) -> None: self.regions[region_id] = region
    def add_npc(self, npc: NPC) -> None:
        npc.last_moved = time.time() - self.start_time
        npc.world = self
        self.npcs[npc.obj_id] = npc
    def get_npc(self, instance_id: str) -> Optional[NPC]: return self.npcs.get(instance_id)
    def get_npcs_in_room(self, region_id: str, room_id: str) -> List[NPC]:
        return [npc for npc in self.npcs.values() if npc.current_region_id == region_id and npc.current_room_id == room_id and npc.is_alive]
    def get_current_room_npcs(self) -> List[NPC]:
        if not self.current_region_id or not self.current_room_id: return []
        return self.get_npcs_in_room(self.current_region_id, self.current_room_id)
    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        region = self.get_region(region_id)
        if not region: return []
        room = region.get_room(room_id)
        return getattr(room, 'items', []) if room else []
    def get_items_in_current_room(self) -> List[Item]:
        if not self.current_region_id or not self.current_room_id: return []
        return self.get_items_in_room(self.current_region_id, self.current_room_id)
    def add_item_to_room(self, region_id: str, room_id: str, item: Item) -> bool:
        region = self.get_region(region_id)
        if not region: return False
        room = region.get_room(room_id)
        if room:
             room.add_item(item)
             return True
        return False
    def remove_item_from_room(self, region_id: str, room_id: str, obj_id: str) -> Optional[Item]:
         region = self.get_region(region_id)
         if not region: return None
         room = region.get_room(room_id)
         return room.remove_item(obj_id) if room else None

    def update(self) -> List[str]:
        current_time_abs = time.time()
        messages = []
        if current_time_abs - self.last_update_time < WORLD_UPDATE_INTERVAL:
             return messages
        self.last_update_time = current_time_abs
        npcs_to_remove = []
        for npc_id in list(self.npcs.keys()):
            npc = self.npcs.get(npc_id)
            if not npc: continue
            if npc.is_alive:
                npc_message = npc.update(self, current_time_abs)
                if npc_message: messages.append(npc_message)
            else:
                npcs_to_remove.append(npc_id)
        for npc_id in npcs_to_remove:
             removed_npc = self.npcs.pop(npc_id, None)
             if removed_npc and not removed_npc.properties.get("is_summoned", False) and self.player and self.player.is_alive and self.current_region_id == removed_npc.current_region_id and self.current_room_id == removed_npc.current_room_id:
                messages.append(f"{FORMAT_HIGHLIGHT}The corpse of the {removed_npc.name} fades away.{FORMAT_RESET}")
        return messages

    def find_item_in_room(self, name: str) -> Optional[Item]:
         items = self.get_items_in_current_room()
         name_lower = name.lower()
         for item in items:
              if name_lower == item.name.lower() or name_lower == item.obj_id: return item
         for item in items:
              if name_lower in item.name.lower(): return item
         return None

    def set_plugin_data(self, plugin_id: str, key: str, value: Any) -> None:
        if plugin_id not in self.plugin_data: self.plugin_data[plugin_id] = {}
        self.plugin_data[plugin_id][key] = value
        
    def get_plugin_data(self, plugin_id: str, key: str, default: Any = None) -> Any:
        return self.plugin_data.get(plugin_id, {}).get(key, default)

    def find_path(self, source_region_id: str, source_room_id: str, target_region_id: str, target_room_id: str) -> Optional[List[str]]:
        start_node = (source_region_id, source_room_id); goal_node = (target_region_id, target_room_id)
        if start_node == goal_node: return []
        pq = [(0, start_node)]; g_score = {start_node: 0}; cheapest_path_to = {start_node: []}
        while pq:
            _, current_node = heapq.heappop(pq)
            if current_node == goal_node: return cheapest_path_to[goal_node]
            current_region_id, current_room_id = current_node
            region = self.get_region(current_region_id)
            if not region: continue
            room = region.get_room(current_room_id)
            if not room: continue
            for direction, exit_id in room.exits.items():
                next_region_id, next_room_id = current_region_id, exit_id
                if ":" in exit_id: next_region_id, next_room_id = exit_id.split(":")
                next_node = (next_region_id, next_room_id)
                next_region = self.get_region(next_region_id)
                if not next_region or not next_region.get_room(next_room_id):
                    continue
                new_cost = g_score[current_node] + 1
                if next_node not in g_score or new_cost < g_score[next_node]:
                    g_score[next_node] = new_cost
                    priority = new_cost + (0 if next_region_id == target_region_id else 1)
                    heapq.heappush(pq, (priority, next_node))
                    cheapest_path_to[next_node] = cheapest_path_to[current_node] + [direction]
        return None

    def is_location_safe(self, region_id: str, room_id: Optional[str] = None) -> bool:
        region = self.get_region(region_id)
        if not region: return False
        return region.get_property("safe_zone", False)

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

    def find_npc_in_room(self, name: str) -> Optional[NPC]:
         npcs = self.get_current_room_npcs()
         name_lower = name.lower()
         for npc in npcs:
              if name_lower == npc.name.lower() or name_lower == npc.obj_id: return npc
         for npc in npcs:
              if name_lower in npc.name.lower(): return npc
         return None

    def get_player_status(self) -> str:
        if not self.player: return "Player not loaded."
        return self.player.get_status()

    def change_room(self, direction: str) -> str:
        if not self.player or not self.player.is_alive:
             return f"{FORMAT_ERROR}You cannot move while dead.{FORMAT_RESET}"
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        current_room = self.get_current_room()
        if not old_region_id or not old_room_id or not current_room:
            return f"{FORMAT_ERROR}You are lost in an unknown place and cannot move.{FORMAT_RESET}"
        destination_id = current_room.get_exit(direction)
        if not destination_id: return f"{FORMAT_ERROR}You cannot go {direction}.{FORMAT_RESET}"
        lock_key_id = current_room.get_property("locked_by")
        if lock_key_id:
            if not any(slot.item and slot.item.obj_id == lock_key_id for slot in self.player.inventory.slots):
                return f"{FORMAT_ERROR}The way is locked.{FORMAT_RESET}"
        new_region_id, new_room_id = (destination_id.split(":") if ":" in destination_id else (self.current_region_id, destination_id))
        if not new_region_id:
            return f"{FORMAT_ERROR}You are lost and cannot determine your region.{FORMAT_RESET}"
        target_region = self.get_region(new_region_id)
        if not target_region or not target_region.get_room(new_room_id):
            return f"{FORMAT_ERROR}That path leads to an unknown place.{FORMAT_RESET}"
        target_room = target_region.get_room(new_room_id)
        self.current_region_id = new_region_id
        self.current_room_id = new_room_id
        if target_room:
            target_room.visited = True
        self.player.current_region_id = new_region_id
        self.player.current_room_id = new_room_id
        if self.game and self.game.plugin_manager:
             self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
             self.game.plugin_manager.on_room_enter(new_region_id, new_room_id)
        region_change_msg = f"{FORMAT_HIGHLIGHT}You have entered {target_region.name}.{FORMAT_RESET}\n\n" if new_region_id != old_region_id else ""
        return region_change_msg + self.look()

    def look(self) -> str:
        return self.get_room_description_for_display()

    def get_room_description_for_display(self) -> str:
        if not self.player: return "You are not yet in the world."
        current_room = self.get_current_room()
        current_region = self.get_current_region()
        if not current_room or not current_region: return f"{FORMAT_ERROR}You are nowhere.{FORMAT_RESET}"
        
        title = f"{FORMAT_TITLE}[{current_region.name.upper()} - {current_room.name.upper()}]{FORMAT_RESET}\n\n"
        
        time_period = self.get_plugin_data("time_plugin", "time_period", "day")
        weather = self.get_plugin_data("weather_plugin", "current_weather", "clear")
        room_desc = current_room.get_full_description(time_period, weather)

        all_npcs_in_room = self.get_current_room_npcs()
        friendly_npcs = [npc for npc in all_npcs_in_room if npc.faction != "hostile"]
        hostile_npcs = [npc for npc in all_npcs_in_room if npc.faction == "hostile"]

        if friendly_npcs:
            friendly_npc_list = []
            for npc in friendly_npcs:
                formatted_name = format_name_for_display(self.player, npc, start_of_sentence=False)
                status_suffix = f" {FORMAT_ERROR}(Fighting!){FORMAT_RESET}" if npc.in_combat else ""
                if hasattr(npc, "ai_state") and "current_activity" in npc.ai_state: status_suffix = f" ({npc.ai_state['current_activity']})"
                friendly_npc_list.append(f"{formatted_name}{status_suffix}")
            
            friendly_content_str = ", ".join(friendly_npc_list)
        else:
            friendly_content_str = f"{FORMAT_GRAY}(None){FORMAT_RESET}"

        if hostile_npcs:
            hostile_npc_list = []
            for npc in hostile_npcs:
                formatted_name = format_name_for_display(self.player, npc, start_of_sentence=False)
                hp_str = f" ({FORMAT_SUCCESS}{int(npc.health)}/{int(npc.max_health)}{FORMAT_RESET})"
                hostile_npc_list.append(f"{formatted_name}{hp_str}")

            hostile_content_str = ", ".join(hostile_npc_list)
        else:
            hostile_content_str = f"{FORMAT_GRAY}(None){FORMAT_RESET}"

        items_in_room = self.get_items_in_current_room()
        
        if items_in_room:
            item_counts: Dict[str, Dict[str, Any]] = {}
            for item in items_in_room:
                if item.obj_id not in item_counts: item_counts[item.obj_id] = {"name": item.name, "count": 0}
                item_counts[item.obj_id]["count"] += 1
            
            item_message_parts = []
            for item_id, data in item_counts.items():
                if data["count"] == 1: item_message_parts.append(f"{get_article(data['name'])} {FORMAT_CATEGORY}{data['name']}{FORMAT_RESET}")
                else: item_message_parts.append(f"{data['count']} {FORMAT_CATEGORY}{simple_plural(data['name'])}{FORMAT_RESET}")

            item_content_str = ", ".join(item_message_parts)
        else:
            item_content_str = f"{FORMAT_GRAY}(None){FORMAT_RESET}"

        full_description = title + room_desc
        full_description += f"\n\n{FORMAT_CATEGORY}People here:{FORMAT_RESET} {friendly_content_str}"
        full_description += f"\n{FORMAT_CATEGORY}Hostiles:{FORMAT_RESET} {hostile_content_str}"
        full_description += f"\n{FORMAT_CATEGORY}Items:{FORMAT_RESET} {item_content_str}"
        
        return full_description

    def remove_item_instance_from_room(self, region_id: str, room_id: str, item_instance: Item) -> bool:
        region = self.get_region(region_id)
        if not region: return False
        room = region.get_room(room_id)
        if not room or not hasattr(room, 'items'): return False
        try:
            room.items.remove(item_instance)
            return True
        except ValueError:
            return False