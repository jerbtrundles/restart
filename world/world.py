# world/world.py
import heapq
import time
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING

from config import (
    FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_GRAY, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_TITLE, DEFAULT_SAVE_FILE, WORLD_UPDATE_INTERVAL
)
from core.quest_manager import QuestManager
from items.item_factory import ItemFactory
from npcs.npc_factory import NPCFactory
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

        # --- START OF MODIFICATION ---
        # After NPC updates, check if any quest objectives have been met
        if self.player and self.quest_manager:
            self.quest_manager.check_quest_completion()
        # --- END OF MODIFICATION ---

        npcs_to_remove = [npc_id for npc_id, npc in self.npcs.items() if not npc.is_alive]
        for npc_id in npcs_to_remove: self.npcs.pop(npc_id, None)

        self._check_and_cleanup_completed_instances()
        
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
        
        time_period = self.game.time_manager.current_time_period
        weather = self.game.weather_manager.current_weather

        if not self.current_region_id or not self.current_room_id:
            return f"Error: get_room_description_for_display: no region id/room id."
        is_outdoors = self.is_location_outdoors(self.current_region_id, self.current_room_id)
        
        room_desc = current_room.get_full_description(time_period, weather, is_outdoors=is_outdoors)

        # --- START OF MODIFICATION ---
        # Check for active quests that modify this room's description
        for quest_id, quest_data in self.player.quest_log.items():
            entry_point = quest_data.get("entry_point")
            if (quest_data.get("state") == "active" and entry_point and 
                entry_point.get("region_id") == self.current_region_id and 
                entry_point.get("room_id") == self.current_room_id):
                
                # Check if the quest adds a special description
                extra_desc = entry_point.get("description_when_visible")
                if extra_desc:
                    # Append the special description to the main room description
                    room_desc += f"\n\n{FORMAT_HIGHLIGHT}{extra_desc}{FORMAT_RESET}"
        # --- END OF MODIFICATION ---

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
    def is_location_outdoors(self, region_id: str, room_id: str) -> bool:
        region = self.get_region(region_id)
        if not region:
            return True
        room = region.get_room(room_id) if self.get_region(region_id) else None
        if room:
            room_setting = room.get_property("outdoors")
            if room_setting is not None:
                return room_setting
        region = self.get_region(region_id)
        if region:
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

    def instantiate_quest_region(self, quest_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        """
        Dynamically creates a temporary region for a quest and spawns the giver.
        Returns: (success, message, giver_npc_instance_id)
        """
        if not self.player:
            return False, "Cannot instantiate region without a player.", None

        try:
            entry_point = quest_data['entry_point']
            instance_def = quest_data['instance_definition']
            quest_instance_id = quest_data['instance_id']

            # ... (Code for creating the region and rooms remains the same) ...
            unique_region_id = f"instance_{quest_instance_id}"
            quest_data['instance_region_id'] = unique_region_id
            new_region = Region( obj_id=unique_region_id, name=instance_def['region_name'], description=instance_def['region_description'] )
            new_region.properties = instance_def.get("properties", {})
            entry_room_id = ""
            for room_id, room_data in instance_def['rooms'].items():
                if not entry_room_id: entry_room_id = room_id
                for direction, exit_dest in list(room_data.get('exits', {}).items()):
                    if exit_dest == "dynamic_exit": room_data['exits'][direction] = f"{entry_point['region_id']}:{entry_point['room_id']}"
                    elif ":" not in exit_dest: room_data['exits'][direction] = f"{unique_region_id}:{exit_dest}"
                new_room = Room.from_dict(room_data)
                new_region.add_room(room_id, new_room)

                # --- START OF FIX: VALIDATE NPC SPAWNING ---
                if "spawner" in room_data and "initial_spawn" in room_data["spawner"]:
                    for spawn_info in room_data["spawner"]["initial_spawn"]:
                        template_id_to_spawn = spawn_info.get("template_id")
                        if not template_id_to_spawn:
                            self.cleanup_quest_region(quest_instance_id) # Clean up partial instance
                            return False, f"Quest template '{quest_instance_id}' has invalid spawner config.", None

                        for _ in range(spawn_info.get("count", 1)):
                            npc = NPCFactory.create_npc_from_template(
                                template_id_to_spawn,
                                self,
                                current_region_id=unique_region_id,
                                current_room_id=room_id
                            )
                            # CRITICAL CHECK: If npc is None, creation failed. Abort.
                            if not npc:
                                self.cleanup_quest_region(quest_instance_id) # Clean up partial instance
                                return False, f"Could not spawn required creature '{template_id_to_spawn}'. Check template ID.", None
                            
                            self.add_npc(npc)
                # --- END OF FIX ---

            self.regions[unique_region_id] = new_region
            permanent_entry_region = self.get_region(entry_point['region_id'])
            if not permanent_entry_region: return False, f"Could not get permanent entry region.", None
            permanent_entry_room = permanent_entry_region.get_room(entry_point['room_id'])
            exit_command = entry_point['exit_command']
            if permanent_entry_room:
                permanent_entry_room.exits[exit_command] = f"{unique_region_id}:{entry_room_id}"
                if self.game and self.game.debug_mode:
                    print(f"[World DEBUG] Adding temporary exit '{exit_command}' to room '{entry_point['region_id']}:{entry_point['room_id']}' -> leads to instance '{unique_region_id}:{entry_room_id}'")

            giver_npc_id = None
            spawn_message = "You decide to take on the task."
            giver_tid = quest_data.get("giver_npc_template_id")
            
            if giver_tid:
                giver_instance_id = f"giver_{quest_instance_id}"
                # --- START OF MODIFICATION ---
                # Spawn the giver NPC at the PLAYER'S location, not the remote entry point.
                giver_npc = NPCFactory.create_npc_from_template(
                    giver_tid, self, giver_instance_id,
                    current_region_id=self.player.current_region_id,
                    current_room_id=self.player.current_room_id
                )
                # --- END OF MODIFICATION ---
                if giver_npc:
                    self.add_npc(giver_npc)
                    giver_npc_id = giver_npc.obj_id
                    # --- START OF MODIFICATION ---
                    # Update the spawn message to reflect the new logic.
                    spawn_message = (f"{giver_npc.name} notices you taking their notice from the board and approaches you.\n"
                                     f"\"{giver_npc.dialog.get('greeting', 'Please help me!')}\"")
                    # --- END OF MODIFICATION ---
                else:
                    self.cleanup_quest_region(quest_instance_id) 
                    return False, f"Could not spawn giver NPC '{giver_tid}'.", None

            return True, spawn_message, giver_npc_id

        except KeyError as e:
            return False, f"Quest template is missing a required key: {e}", None
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"An unexpected error occurred creating the quest instance: {e}", None

    def cleanup_quest_region(self, quest_id: str):
        """Removes a temporary quest region and its associated exit."""
        if not self.player or quest_id not in self.player.completed_quest_log:
            return

        quest_data = self.player.completed_quest_log[quest_id]
        instance_region_id = quest_data.get("instance_region_id")
        entry_point = quest_data.get("entry_point")

        if not instance_region_id or not entry_point:
            return # Not an instance quest or data is missing

        # 1. Remove the temporary exit from the permanent room
        perm_region = self.get_region(entry_point['region_id'])
        if perm_region:
            perm_room = perm_region.get_room(entry_point['room_id'])
            if perm_room and entry_point['exit_command'] in perm_room.exits:
                del perm_room.exits[entry_point['exit_command']]

        # 2. Remove all NPCs that are inside the instance region
        npcs_to_remove = [npc.obj_id for npc in self.npcs.values() if npc.current_region_id == instance_region_id]
        for npc_id in npcs_to_remove:
            del self.npcs[npc_id]

        # 3. Remove the region itself from the world
        if instance_region_id in self.regions:
            del self.regions[instance_region_id]
            
        # 4. Move quest to a final "archived" log to prevent re-cleanup
        del self.player.completed_quest_log[quest_id]
        if not hasattr(self.player, 'archived_quest_log'):
            self.player.archived_quest_log = {}
        self.player.archived_quest_log[quest_id] = quest_data
        
        print(f"[DEBUG] Cleaned up instance region: {instance_region_id}")

    def _check_and_cleanup_completed_instances(self):
        """Called in the main update loop to handle instance cleanup."""
        if not self.player or not hasattr(self.player, 'completed_quest_log'):
            return

        # Iterate over a copy of the keys to allow modification during the loop
        for quest_id in list(self.player.completed_quest_log.keys()):
            quest_data = self.player.completed_quest_log[quest_id]
            if quest_data.get("type") == "instance":
                instance_id = quest_data.get("instance_region_id")
                # If the player is NOT in the instance region, it's safe to clean up.
                if instance_id and self.player.current_region_id != instance_id:
                    self.cleanup_quest_region(quest_id)
