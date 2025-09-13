# world/world.py
import heapq
import time
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING

from core.config import *
from core.quest_manager import QuestManager
from items.item_factory import ItemFactory
from player import Player
from world.region import Region
from world.room import Room
from items.item import Item
from npcs.npc import NPC
from world.spawner import Spawner
from world.save_manager import SaveManager
from world.definition_loader import load_all_definitions, initialize_new_world
from world.respawn_manager import RespawnManager
from utils.pathfinding import find_path
from utils.utils import format_name_for_display, get_article, simple_plural

if TYPE_CHECKING:
    from core.game_manager import GameManager

class World:
    def __init__(self):
        # State
        self.regions: Dict[str, Region] = {}
        self.item_templates: Dict[str, Dict[str, Any]] = {}
        self.npc_templates: Dict[str, Dict[str, Any]] = {}
        self.player: Optional['Player'] = None
        self.npcs: Dict[str, NPC] = {}
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.quest_board: List[Dict[str, Any]] = []
        
        # Managers
        self.quest_manager = QuestManager(self)
        self.spawner = Spawner(self)
        self.save_manager = SaveManager(self)
        self.respawn_manager = RespawnManager(self)

        self.last_update_time = 0
        if TYPE_CHECKING:
            self.game: Optional['GameManager'] = None

        load_all_definitions(self)

    def initialize_new_world(self, start_region="town", start_room="town_square"):
        """Delegates new world initialization."""
        initialize_new_world(self, start_region, start_room)

    def load_save_game(self, filename: str = DEFAULT_SAVE_FILE) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Delegates loading to the SaveManager."""
        return self.save_manager.load(filename)

    def save_game(self, filename: str = DEFAULT_SAVE_FILE) -> bool:
        """Delegates saving to the SaveManager."""
        return self.save_manager.save(filename)

    def update(self) -> List[str]:
        """Main world update tick."""
        current_time_abs = time.time()
        messages = []
        if current_time_abs - self.last_update_time < WORLD_UPDATE_INTERVAL:
             return messages
        self.last_update_time = current_time_abs
        
        messages.extend(self.respawn_manager.update(current_time_abs))
        self.spawner.update(current_time_abs)

        npcs_to_update = [npc for npc in self.npcs.values() if npc.is_alive]
        for npc in npcs_to_update:
            npc_message = npc.update(self, current_time_abs)
            if npc_message: messages.append(npc_message)

        npcs_to_remove = [npc_id for npc_id, npc in self.npcs.items() if not npc.is_alive]
        for npc_id in npcs_to_remove: self.npcs.pop(npc_id, None)
        
        return messages

    def find_path(self, source_region_id: str, source_room_id: str, target_region_id: str, target_room_id: str) -> Optional[List[str]]:
        """Delegates pathfinding to the utility function."""
        return find_path(self, source_region_id, source_room_id, target_region_id, target_room_id)

    def add_to_respawn_queue(self, npc: NPC):
        """Delegates adding to the respawn queue to its manager."""
        self.respawn_manager.add_to_queue(npc)

    def get_room_description_for_display(self, minimal: bool = False) -> str:
        if not self.player or not self.game: return "You are not yet in the world."
        current_room = self.get_current_room()
        current_region = self.get_current_region()
        if not current_room or not current_region: return f"{FORMAT_ERROR}You are nowhere.{FORMAT_RESET}"
        
        title = f"{FORMAT_TITLE}[{current_region.name.upper()} - {current_room.name.upper()}]{FORMAT_RESET}\n\n"
        
        # --- BUG FIX & REFACTOR ---
        # Get time and weather from their respective core managers via the game object
        time_period = self.game.time_manager.current_time_period
        weather = self.game.weather_manager.current_weather
        # --- END FIX ---
        
        room_desc = current_room.get_full_description(time_period, weather)

        all_npcs_in_room = self.get_current_room_npcs()
        friendly_npcs = [npc for npc in all_npcs_in_room if npc.faction != "hostile"]
        hostile_npcs = [npc for npc in all_npcs_in_room if npc.faction == "hostile"]
        items_in_room = self.get_items_in_current_room()
        
        full_description = title + room_desc

        # --- FRIENDLY NPCs ---
        if friendly_npcs or not minimal:
            friendly_content_str = f"{FORMAT_GRAY}(None){FORMAT_RESET}"
            if friendly_npcs:
                friendly_npc_list = []
                for npc in friendly_npcs:
                    formatted_name = format_name_for_display(self.player, npc, start_of_sentence=False)
                    status_suffix = f" {FORMAT_ERROR}(Fighting!){FORMAT_RESET}" if npc.in_combat else ""
                    if hasattr(npc, "ai_state") and "current_activity" in npc.ai_state: status_suffix = f" ({npc.ai_state['current_activity']})"
                    friendly_npc_list.append(f"{formatted_name}{status_suffix}")
                friendly_content_str = ", ".join(friendly_npc_list)
            full_description += f"\n\n{FORMAT_CATEGORY}People here:{FORMAT_RESET} {friendly_content_str}"

        # --- HOSTILE NPCs ---
        if hostile_npcs or not minimal:
            hostile_content_str = f"{FORMAT_GRAY}(None){FORMAT_RESET}"
            if hostile_npcs:
                hostile_npc_list = [f"{format_name_for_display(self.player, npc)}" for npc in hostile_npcs]
                hostile_content_str = ", ".join(hostile_npc_list)
            full_description += f"\n{FORMAT_CATEGORY}Hostiles:{FORMAT_RESET} {hostile_content_str}"

        # --- ITEMS ---
        if items_in_room or not minimal:
            item_content_str = f"{FORMAT_GRAY}(None){FORMAT_RESET}"
            if items_in_room:
                item_counts: Dict[str, Dict[str, Any]] = {}
                for item in items_in_room:
                    if item.obj_id not in item_counts: item_counts[item.obj_id] = {"name": item.name, "count": 0}
                    item_counts[item.obj_id]["count"] += 1
                item_message_parts = []
                for data in item_counts.values():
                    if data["count"] == 1: item_message_parts.append(f"{get_article(data['name'])} {FORMAT_CATEGORY}{data['name']}{FORMAT_RESET}")
                    else: item_message_parts.append(f"{data['count']} {FORMAT_CATEGORY}{simple_plural(data['name'])}{FORMAT_RESET}")
                item_content_str = ", ".join(item_message_parts)
            full_description += f"\n{FORMAT_CATEGORY}Items:{FORMAT_RESET} {item_content_str}"
        
        return full_description    
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
        region_change_msg = f"{FORMAT_HIGHLIGHT}You have entered {target_region.name}.{FORMAT_RESET}\n\n" if new_region_id != old_region_id else ""
        return region_change_msg + self.look(minimal=True)

    def _load_room_items_from_save(self, room_items_data: Dict[str, Any]):
        """Populates rooms with items from a save data dictionary."""
        for location_key, item_refs in room_items_data.items():
            try:
                region_id, room_id = location_key.split(":")
                region = self.get_region(region_id)
                room = region.get_room(room_id) if region else None
                if room:
                    for item_ref in item_refs:
                        if item_ref and "item_id" in item_ref:
                            item = ItemFactory.create_item_from_template(item_ref["item_id"], self, **item_ref.get("properties_override", {}))
                            if item: room.add_item(item)
            except ValueError:
                print(f"Warning: Could not parse room location key '{location_key}' from save file.")

    # --- Accessors, Mutators, and other helpers ---
    def get_region(self, region_id: str) -> Optional[Region]: return self.regions.get(region_id)
    def get_current_region(self) -> Optional[Region]: return self.regions.get(self.current_region_id) if self.current_region_id else None
    def get_current_room(self) -> Optional[Room]:
        region = self.get_current_region()
        return region.get_room(self.current_room_id) if region and self.current_room_id else None
    def add_region(self, region_id: str, region: Region) -> None: self.regions[region_id] = region
    def add_npc(self, npc: NPC) -> None:
        npc.last_moved = time.time()
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
    def is_location_safe(self, region_id: str, room_id: Optional[str] = None) -> bool:
        region = self.get_region(region_id)
        if not region: return False
        return region.get_property("safe_zone", False)
    def find_item_in_room(self, name: str) -> Optional[Item]:
         items = self.get_items_in_current_room()
         name_lower = name.lower()
         for item in items:
              if name_lower == item.name.lower() or name_lower == item.obj_id: return item
         for item in items:
              if name_lower in item.name.lower(): return item
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
    def look(self, minimal: bool = False) -> str:
        return self.get_room_description_for_display(minimal=minimal)
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
    def dispatch_event(self, event_type: str, data: Dict[str, Any]):
        if event_type == "npc_killed":
            self.quest_manager.handle_npc_killed(event_type, data)
    def find_nearest_safe_room(self, source_region_id: str, source_room_id: str) -> Optional[Tuple[str, str]]:
        if self.is_location_safe(source_region_id, source_room_id):
            return (source_region_id, source_room_id)
        candidate_paths = []
        for region_id, region in self.regions.items():
            if region.get_property("safe_zone", False):
                for room_id in region.rooms.keys():
                    path = self.find_path(source_region_id, source_room_id, region_id, room_id)
                    if path is not None:
                        heapq.heappush(candidate_paths, (len(path), (region_id, room_id)))
        if candidate_paths:
            return heapq.heappop(candidate_paths)[1]
        return None
