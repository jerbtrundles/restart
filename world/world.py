"""world/world.py"""
from typing import Dict, List, Optional, Any
import time
import json
import os

from player import Player
from world.region import Region
from world.room import Room
from items.item import Item, ItemFactory
from items.inventory import Inventory
from npcs.npc import NPC
from npcs.npc_factory import NPCFactory

class World:
    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.player = Player("Adventurer")
        if not hasattr(self.player, "inventory"):
            self.player.inventory = Inventory(max_slots=20, max_weight=100.0)
        self.npcs: Dict[str, NPC] = {}
        self.start_time = time.time()
        self.last_update_time = 0
        self.plugin_data = {}
   
    def add_region(self, region_id: str, region: Region):
        self.regions[region_id] = region
    
    def get_region(self, region_id: str) -> Optional[Region]:
        return self.regions.get(region_id)
    
    def get_current_region(self) -> Optional[Region]:
        if self.current_region_id:
            return self.regions.get(self.current_region_id)
        return None
    
    def get_current_room(self) -> Optional[Room]:
        region = self.get_current_region()
        if region and self.current_room_id:
            return region.get_room(self.current_room_id)
        return None
    
    def add_npc(self, npc: NPC):
        npc.last_moved = time.time() - self.start_time
        self.npcs[npc.npc_id] = npc
    
    def get_npc(self, npc_id: str) -> Optional[NPC]:
        return self.npcs.get(npc_id)
    
    def get_npcs_in_room(self, region_id: str, room_id: str) -> List[NPC]:
        return [npc for npc in self.npcs.values() 
                if npc.current_region_id == region_id and npc.current_room_id == room_id]
    
    def get_current_room_npcs(self) -> List[NPC]:
        if not self.current_region_id or not self.current_room_id:
            return []
            
        return self.get_npcs_in_room(self.current_region_id, self.current_room_id)
    
    def update(self):
        current_time = time.time() - self.start_time
        messages = []
        if current_time - self.last_update_time < 1:
            return messages
        for npc in self.npcs.values():
            npc_message = npc.update(self, current_time)
            if npc_message:
                messages.append(npc_message)        
        self.last_update_time = current_time
        return messages

    def change_room(self, direction: str) -> str:
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id        
        current_room = self.get_current_room()
        if not current_room:
            return "You are nowhere."
        new_room_id = current_room.get_exit(direction)
        if not new_room_id:
            return f"You can't go {direction}."
        region = self.get_current_region()
        if region and new_room_id in region.rooms:
            self.current_room_id = new_room_id
            npcs_in_room = self.get_current_room_npcs()
            npc_descriptions = ""
            if npcs_in_room:
                npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
            if hasattr(self, "game") and hasattr(self.game, "plugin_manager"):
                self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
                self.game.plugin_manager.on_room_enter(self.current_region_id, self.current_room_id)            
            return self.get_current_room().get_full_description() + npc_descriptions
        if ":" in new_room_id:
            new_region_id, new_room_id = new_room_id.split(":")
            if new_region_id in self.regions:
                new_region = self.regions[new_region_id]
                if new_room_id in new_region.rooms:
                    self.current_region_id = new_region_id
                    self.current_room_id = new_room_id
                    npcs_in_room = self.get_current_room_npcs()
                    npc_descriptions = ""
                    if npcs_in_room:
                        npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
                    if hasattr(self, "game") and hasattr(self.game, "plugin_manager"):
                        self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
                        self.game.plugin_manager.on_room_enter(self.current_region_id, self.current_room_id)
                    return f"You've entered {new_region.name}.\n\n{self.get_current_room().get_full_description()}{npc_descriptions}"        
        return "That exit leads nowhere usable."
    
    def look(self) -> str:
        current_room = self.get_current_room()
        if current_room:
            time_period = None
            if hasattr(self, "plugin_data") and "time_plugin" in self.plugin_data:
                time_period = self.plugin_data["time_plugin"].get("current_time_period")
            room_desc = current_room.get_full_description(time_period)
            npcs_in_room = self.get_current_room_npcs()
            npc_descriptions = ""
            if npcs_in_room:
                npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
            items_in_room = self.get_items_in_current_room()
            item_descriptions = ""
            if items_in_room:
                item_descriptions = "\n\n" + "\n".join([f"There is {item.name} here." for item in items_in_room])
            return room_desc + npc_descriptions + item_descriptions
        return "You are nowhere."
        
    def get_player_status(self) -> str:
        status = self.player.get_status()
        if hasattr(self.player, "inventory"):
            inventory_desc = "\n\n" + self.player.inventory.list_items()
            status += inventory_desc            
        return status
        
    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        region = self.get_region(region_id)
        if not region:
            return []            
        room = region.get_room(room_id)
        if not room:
            return []
        return room.items if hasattr(room, "items") else []
    
    def get_items_in_current_room(self) -> List[Item]:
        if not self.current_region_id or not self.current_room_id:
            return []
        return self.get_items_in_room(self.current_region_id, self.current_room_id)
    
    def add_item_to_room(self, region_id: str, room_id: str, item: Item) -> bool:
        region = self.get_region(region_id)
        if not region:
            return False            
        room = region.get_room(room_id)
        if not room:
            return False
        if not hasattr(room, "items"):
            room.items = []
        room.items.append(item)
        return True
    
    def remove_item_from_room(self, region_id: str, room_id: str, item_id: str) -> Optional[Item]:
        items = self.get_items_in_room(region_id, room_id)
        for i, item in enumerate(items):
            if item.item_id == item_id:
                return items.pop(i)                
        return None

    def save_to_json(self, filename: str) -> bool:
        try:
            world_data = {
                "current_region_id": self.current_region_id,
                "current_room_id": self.current_room_id,
                "player": self.player.to_dict(),
                "regions": {},
                "npcs": {},
                "plugin_data": self.plugin_data  # Save plugin data
            }
            for region_id, region in self.regions.items():
                region_data = {
                    "name": region.name,
                    "description": region.description,
                    "rooms": {}
                }                
                for room_id, room in region.rooms.items():
                    room_data = room.to_dict()
                    room_data["items"] = [item.to_dict() for item in getattr(room, "items", [])]
                    region_data["rooms"][room_id] = room_data
                world_data["regions"][region_id] = region_data
            for npc_id, npc in self.npcs.items():
                world_data["npcs"][npc_id] = npc.to_dict()
            with open(filename, 'w') as f:
                json.dump(world_data, f, indent=2)
            return True            
        except Exception as e:
            print(f"Error saving world: {e}")
            return False

    def load_from_json(self, filename: str) -> bool:
        try:
            if not os.path.exists(filename):
                print(f"File not found: {filename}")
                return False
            with open(filename, 'r') as f:
                world_data = json.load(f)
            self.regions = {}
            self.npcs = {}
            self.start_time = time.time()
            if "plugin_data" in world_data:
                self.plugin_data = world_data["plugin_data"]
            else:
                self.plugin_data = {}
            if "player" in world_data:
                self.player = Player.from_dict(world_data["player"])
            for region_id, region_data in world_data.get("regions", {}).items():
                region = Region(region_data["name"], region_data["description"])
                for room_id, room_data in region_data.get("rooms", {}).items():
                    room = Room.from_dict(room_data)
                    if "items" in room_data:
                        room.items = []
                        for item_data in room_data["items"]:
                            item = ItemFactory.from_dict(item_data)
                            room.items.append(item)
                    region.add_room(room_id, room)
                self.add_region(region_id, region)
            current_time = time.time() - self.start_time
            for npc_id, npc_data in world_data.get("npcs", {}).items():
                npc = NPC.from_dict(npc_data)
                npc.last_moved = current_time
                self.npcs[npc_id] = npc
            self.current_region_id = world_data.get("current_region_id")
            self.current_room_id = world_data.get("current_room_id")
            return True            
        except Exception as e:
            print(f"Error loading world: {e}")
            return False

    def set_plugin_data(self, plugin_id: str, key: str, value: Any) -> None:
        if plugin_id not in self.plugin_data:
            self.plugin_data[plugin_id] = {}
        self.plugin_data[plugin_id][key] = value

    def get_plugin_data(self, plugin_id: str, key: str, default: Any = None) -> Any:
        if plugin_id not in self.plugin_data:
            return default
        return self.plugin_data[plugin_id].get(key, default)

    def find_path(self, source_region_id, source_room_id, target_region_id, target_room_id):
        """
        Find the shortest path between two rooms in the world.
        
        Args:
            source_region_id: Starting region ID
            source_room_id: Starting room ID
            target_region_id: Target region ID
            target_room_id: Target room ID
        
        Returns:
            A list of direction strings representing the path, or None if no path exists
        """
        # Starting and target nodes
        start = (source_region_id, source_room_id)
        goal = (target_region_id, target_room_id)
        
        # Queue of nodes to explore (priority queue)
        # Format: (priority, cost_so_far, (region_id, room_id), [path_so_far])
        frontier = [(0, 0, start, [])]
        
        # Set of explored nodes
        visited = set()
        
        while frontier:
            # Get the node with lowest priority
            _, cost, current, path = frontier.pop(0)
            
            # If we reached the goal, return the path
            if current == goal:
                return path
            
            # Skip if already visited
            if current in visited:
                continue
            
            visited.add(current)
            
            # Get current region and room
            current_region_id, current_room_id = current
            region = self.get_region(current_region_id)
            if not region:
                continue
                
            room = region.get_room(current_room_id)
            if not room:
                continue
            
            # Explore each exit from the current room
            for direction, exit_path in room.exits.items():
                next_room_id = exit_path
                next_region_id = current_region_id
                
                # Handle region transitions
                if ":" in exit_path:
                    next_region_id, next_room_id = exit_path.split(":")
                
                next_node = (next_region_id, next_room_id)
                
                # Skip if already visited
                if next_node in visited:
                    continue
                
                # Calculate new cost (always +1 for a step)
                new_cost = cost + 1
                
                # Calculate heuristic (estimate to goal)
                # For simplicity, just use 0 or 1 for same/different region
                h = 0 if next_region_id == target_region_id else 10
                
                # Calculate priority (cost + heuristic)
                priority = new_cost + h
                
                # Add to frontier with priority
                new_path = path + [direction]
                
                # Insert into frontier while maintaining sort by priority
                i = 0
                while i < len(frontier) and frontier[i][0] < priority:
                    i += 1
                frontier.insert(i, (priority, new_cost, next_node, new_path))
        
        # No path found
        return None
