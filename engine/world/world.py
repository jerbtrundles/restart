# engine/world/world.py
import heapq
import time
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING

from engine.config import FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, DEFAULT_SAVE_FILE, WORLD_UPDATE_INTERVAL
from engine.core.quest_manager import QuestManager
from engine.items.item_factory import ItemFactory
from engine.npcs.npc_factory import NPCFactory
from engine.player import Player
from engine.world.region import Region
from engine.world.room import Room
from engine.items.item import Item
from engine.npcs.npc import NPC
from engine.world.spawner import Spawner
from engine.world.save_manager import SaveManager
from engine.world.definition_loader import load_all_definitions, initialize_new_world
from engine.world.respawn_manager import RespawnManager
from engine.world.instance_manager import InstanceManager
from engine.utils.pathfinding import find_path
from engine.utils.utils import _serialize_item_reference

# New Import
from engine.world.description_generator import generate_room_description

if TYPE_CHECKING:
    from engine.core.game_manager import GameManager

class World:
    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.item_templates: Dict[str, Dict[str, Any]] = {}
        self.npc_templates: Dict[str, Dict[str, Any]] = {}
        self.player: Optional['Player'] = None
        self.npcs: Dict[str, NPC] = {}
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.quest_board: List[Dict[str, Any]] = []
        
        self.quest_manager = QuestManager(self)
        self.spawner = Spawner(self)
        self.save_manager = SaveManager(self)
        self.respawn_manager = RespawnManager(self)
        self.instance_manager = InstanceManager(self)

        self.last_update_time = 0.0
        if TYPE_CHECKING:
            self.game: Optional['GameManager'] = None

        load_all_definitions(self)

    def initialize_new_world(self, start_region="town", start_room="town_square"):
        initialize_new_world(self, start_region, start_room)

    def load_save_game(self, filename: str = DEFAULT_SAVE_FILE) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        return self.save_manager.load(filename)

    def save_game(self, filename: str = DEFAULT_SAVE_FILE) -> bool:
        return self.save_manager.save(filename)

    def update(self) -> List[str]:
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

        if self.player and self.quest_manager:
            self.quest_manager.check_quest_completion()

        npcs_to_remove = [npc_id for npc_id, npc in self.npcs.items() if not npc.is_alive]
        for npc_id in npcs_to_remove: self.npcs.pop(npc_id, None)

        self.instance_manager.check_and_cleanup_completed_instances()
        
        return messages

    def find_path(self, source_region_id: str, source_room_id: str, target_region_id: str, target_room_id: str) -> Optional[List[str]]:
        return find_path(self, source_region_id, source_room_id, target_region_id, target_room_id)

    def add_to_respawn_queue(self, npc: NPC):
        self.respawn_manager.add_to_queue(npc)

    def look(self, minimal: bool = False) -> str:
        """Delegate room description generation to the dedicated module."""
        return generate_room_description(self, minimal)

    def change_room(self, direction: str) -> str:
        if not self.player or not self.player.is_alive:
             return f"{FORMAT_ERROR}You cannot move while dead.{FORMAT_RESET}"
        
        # Local narrowing for type safety
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        
        current_room = self.get_current_room()
        if not old_region_id or not old_room_id or not current_room:
            return f"{FORMAT_ERROR}You are lost in an unknown place and cannot move.{FORMAT_RESET}"
        
        destination_id = current_room.get_exit(direction)
        if not destination_id: return f"{FORMAT_ERROR}You cannot go {direction}.{FORMAT_RESET}"
        
        new_region_id, new_room_id = (destination_id.split(":") if ":" in destination_id else (old_region_id, destination_id))
        
        if not new_region_id:
            return f"{FORMAT_ERROR}You are lost and cannot determine your region.{FORMAT_RESET}"
        
        target_region = self.get_region(new_region_id)
        if not target_region:
             return f"{FORMAT_ERROR}That path leads to an unknown region.{FORMAT_RESET}"
             
        target_room = target_region.get_room(new_room_id)
        if not target_room:
            return f"{FORMAT_ERROR}That path leads to an unknown place.{FORMAT_RESET}"

        # --- LOCK CHECK ON DESTINATION ---
        target_lock_key = target_room.get_property("locked_by")
        if target_lock_key:
             has_key = any(slot.item and slot.item.obj_id == target_lock_key for slot in self.player.inventory.slots)
             if not has_key:
                  return f"{FORMAT_ERROR}The door to {target_room.name} is locked.{FORMAT_RESET}"
        # ---------------------------------

        self.current_region_id = new_region_id
        self.current_room_id = new_room_id
        target_room.visited = True
        self.player.current_region_id = new_region_id
        self.player.current_room_id = new_room_id

        if new_region_id.startswith("instance_"):
            for quest in self.player.quest_log.values():
                if quest.get("instance_region_id") == new_region_id:
                    quest["completion_check_enabled"] = True
                    break

        region_change_msg = f"{FORMAT_HIGHLIGHT}You have entered {target_region.name}.{FORMAT_RESET}\n\n" if new_region_id != old_region_id else ""
        return region_change_msg + self.look(minimal=True)

    def _load_room_items_from_save(self, room_items_data: Dict[str, Any]):
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
    
    def get_current_region(self) -> Optional[Region]: 
        return self.regions.get(self.current_region_id) if self.current_region_id else None
    
    def get_current_room(self) -> Optional[Room]:
        region = self.get_current_region()
        if region and self.current_room_id:
            return region.get_room(self.current_room_id)
        return None

    def add_region(self, region_id: str, region: Region) -> None: self.regions[region_id] = region
    
    def add_npc(self, npc: NPC) -> None:
        npc.last_moved = time.time()
        npc.world = self
        self.npcs[npc.obj_id] = npc
    
    def get_npc(self, instance_id: str) -> Optional[NPC]: return self.npcs.get(instance_id)
    
    def get_npcs_in_room(self, region_id: str, room_id: str) -> List[NPC]:
        return [npc for npc in self.npcs.values() if npc.current_region_id == region_id and npc.current_room_id == room_id and npc.is_alive]
    
    def get_current_room_npcs(self) -> List[NPC]:
        # Narrowing for type safety
        rid, rmid = self.current_region_id, self.current_room_id
        if not rid or not rmid: return []
        return self.get_npcs_in_room(rid, rmid)
    
    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        region = self.get_region(region_id)
        if not region: return []
        room = region.get_room(room_id)
        return getattr(room, 'items', []) if room else []
    
    def get_items_in_current_room(self) -> List[Item]:
        # Narrowing for type safety
        rid, rmid = self.current_region_id, self.current_room_id
        if not rid or not rmid: return []
        return self.get_items_in_room(rid, rmid)
    
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
    
    def is_location_outdoors(self, region_id: str, room_id: str) -> bool:
        region = self.get_region(region_id)
        if not region: return True
        room = region.get_room(room_id)
        if room:
            room_setting = room.get_property("outdoors")
            if room_setting is not None:
                return room_setting
        
        region_setting = region.get_property("outdoors")
        if region_setting is not None:
            return region_setting
        return True
    
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
    
    def get_room_description_for_display(self, minimal: bool = False) -> str:
        return generate_room_description(self, minimal)
    
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
    
    def dispatch_event(self, event_type: str, data: Dict[str, Any]) -> Optional[str]:
        if event_type == "npc_killed":
            return self.quest_manager.handle_npc_killed(event_type, data)
        return None
    
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

    def instantiate_quest_region(self, quest_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        return self.instance_manager.instantiate_quest_region(quest_data)

    def cleanup_quest_region(self, quest_id: str):
        self.instance_manager.cleanup_quest_region(quest_id)