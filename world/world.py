"""
world/world.py
Enhanced World class with improved text formatting.
"""
from typing import Dict, List, Optional, Any, Tuple
import time
import json
import os

from player import Player
from world.region import Region
from world.room import Room
from items.item import Item
from items.item_factory import ItemFactory
from items.inventory import Inventory
from npcs.npc import NPC
from npcs.npc_factory import NPCFactory
from utils.text_formatter import TextFormatter

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
   
    def add_region(self, region_id: str, region: Region) -> None:
        """
        Add a region to the world.
        
        Args:
            region_id: Unique identifier for the region
            region: The Region object to add
        """
        self.regions[region_id] = region
    
    def get_region(self, region_id: str) -> Optional[Region]:
        """
        Get a region by ID.
        
        Args:
            region_id: The ID of the region to get
            
        Returns:
            The Region object, or None if not found
        """
        return self.regions.get(region_id)
    
    def get_current_region(self) -> Optional[Region]:
        """
        Get the player's current region.
        
        Returns:
            The current Region object, or None if not in any region
        """
        if self.current_region_id:
            return self.regions.get(self.current_region_id)
        return None
    
    def get_current_room(self) -> Optional[Room]:
        """
        Get the player's current room.
        
        Returns:
            The current Room object, or None if not in any room
        """
        region = self.get_current_region()
        if region and self.current_room_id:
            return region.get_room(self.current_room_id)
        return None
    
    def add_npc(self, npc: NPC) -> None:
        """
        Add an NPC to the world.
        
        Args:
            npc: The NPC object to add
        """
        npc.last_moved = time.time() - self.start_time
        self.npcs[npc.obj_id] = npc
    
    def get_npc(self, obj_id: str) -> Optional[NPC]:
        """
        Get an NPC by ID.
        
        Args:
            obj_id: The ID of the NPC to get
            
        Returns:
            The NPC object, or None if not found
        """
        return self.npcs.get(obj_id)
    
    def get_npcs_in_room(self, region_id: str, room_id: str) -> List[NPC]:
        """
        Get all NPCs in a specific room.
        
        Args:
            region_id: The region ID
            room_id: The room ID
            
        Returns:
            List of NPC objects in the room
        """
        return [npc for npc in self.npcs.values() 
                if npc.current_region_id == region_id and npc.current_room_id == room_id]
    
    def get_current_room_npcs(self) -> List[NPC]:
        """
        Get all NPCs in the player's current room.
        
        Returns:
            List of NPC objects in the current room
        """
        if not self.current_region_id or not self.current_room_id:
            return []
            
        return self.get_npcs_in_room(self.current_region_id, self.current_room_id)
    
    def update(self) -> List[str]:
        """
        Update the world state (NPCs, events, etc.).
        
        Returns:
            List of messages generated during the update
        """
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
        """
        Move the player in the given direction.
        
        Args:
            direction: The direction to move
            
        Returns:
            A description of the new room or an error message
        """
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        
        current_room = self.get_current_room()
        if not current_room:
            return f"{TextFormatter.FORMAT_ERROR}You are nowhere.{TextFormatter.FORMAT_RESET}"
            
        new_room_id = current_room.get_exit(direction)
        if not new_room_id:
            return f"{TextFormatter.FORMAT_ERROR}You can't go {direction}.{TextFormatter.FORMAT_RESET}"
            
        # Handle movement within the same region
        region = self.get_current_region()
        if region and new_room_id in region.rooms:
            self.current_room_id = new_room_id
            
            # Update plugins
            if hasattr(self, "game") and hasattr(self.game, "plugin_manager"):
                self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
                self.game.plugin_manager.on_room_enter(self.current_region_id, self.current_room_id)
                
            # Return the look description of the new room
            return self.look()
            
        # Handle movement between regions
        if ":" in new_room_id:
            new_region_id, new_room_id = new_room_id.split(":")
            if new_region_id in self.regions:
                new_region = self.regions[new_region_id]
                if new_room_id in new_region.rooms:
                    self.current_region_id = new_region_id
                    self.current_room_id = new_room_id
                    
                    # Update plugins
                    if hasattr(self, "game") and hasattr(self.game, "plugin_manager"):
                        self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
                        self.game.plugin_manager.on_room_enter(self.current_region_id, self.current_room_id)
                    
                    # Return the look description with region transition text
                    region_intro = f"{TextFormatter.FORMAT_HIGHLIGHT}You've entered {new_region.name}.{TextFormatter.FORMAT_RESET}\n\n"
                    return region_intro + self.look()
        
        return f"{TextFormatter.FORMAT_ERROR}That exit leads nowhere usable.{TextFormatter.FORMAT_RESET}"
    
    def look(self) -> str:
        """
        Get a description of the player's current surroundings.
        
        Returns:
            Formatted description of the current room
        """
        from utils.text_formatter import TextFormatter
        
        current_room = self.get_current_room()
        if not current_room:
            return f"{TextFormatter.FORMAT_ERROR}You are nowhere.{TextFormatter.FORMAT_RESET}"
            
        # Get current time period and weather from plugin data
        time_period = None
        weather = None
        
        if hasattr(self, "plugin_data"):
            if "time_plugin" in self.plugin_data:
                time_period = self.plugin_data["time_plugin"].get("time_period")
                
            if "weather_plugin" in self.plugin_data:
                weather = self.plugin_data["weather_plugin"].get("current_weather")
        
        # Get room description
        room_desc = current_room.get_full_description(time_period, weather)
        
        # Add NPCs
        npcs_in_room = self.get_current_room_npcs()
        if npcs_in_room:
            room_desc += "\n\n"
            for npc in npcs_in_room:
                room_desc += f"{TextFormatter.FORMAT_HIGHLIGHT}{npc.name} is here.{TextFormatter.FORMAT_RESET}\n"
        
        # Add items
        items_in_room = self.get_items_in_current_room()
        if items_in_room:
            room_desc += "\n\n"
            for item in items_in_room:
                room_desc += f"There is {TextFormatter.FORMAT_CATEGORY}{item.name}{TextFormatter.FORMAT_RESET} here.\n"
        
        return room_desc
        
    def get_player_status(self) -> str:
        """
        Get the player's status information.
        
        Returns:
            Formatted player status text
        """
        status = self.player.get_status()
        
        # Add inventory information if available
        if hasattr(self.player, "inventory"):
            status += "\n\n" + self.player.inventory.list_items()
            
        return status
        
    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        """
        Get all items in a specific room.
        
        Args:
            region_id: The region ID
            room_id: The room ID
            
        Returns:
            List of Item objects in the room
        """
        region = self.get_region(region_id)
        if not region:
            return []
            
        room = region.get_room(room_id)
        if not room:
            return []
            
        return room.items if hasattr(room, "items") else []
    
    def get_items_in_current_room(self) -> List[Item]:
        """
        Get all items in the player's current room.
        
        Returns:
            List of Item objects in the current room
        """
        if not self.current_region_id or not self.current_room_id:
            return []
            
        return self.get_items_in_room(self.current_region_id, self.current_room_id)
    
    def add_item_to_room(self, region_id: str, room_id: str, item: Item) -> bool:
        """
        Add an item to a room.
        
        Args:
            region_id: The region ID
            room_id: The room ID
            item: The Item object to add
            
        Returns:
            True if successful, False otherwise
        """
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
    
    def remove_item_from_room(self, region_id: str, room_id: str, obj_id: str) -> Optional[Item]:
        """
        Remove an item from a room.
        
        Args:
            region_id: The region ID
            room_id: The room ID
            obj_id: The ID of the item to remove
            
        Returns:
            The removed Item object, or None if not found
        """
        items = self.get_items_in_room(region_id, room_id)
        for i, item in enumerate(items):
            if item.obj_id == obj_id:
                return items.pop(i)
                
        return None

    def save_to_json(self, filename: str) -> bool:
        """
        Save the world state to a JSON file.
        
        Args:
            filename: The filename to save to
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to resolve the proper save directory
            save_paths = [
                filename,                             # Direct path
                os.path.join(os.getcwd(), filename),  # Current working directory
                os.path.join(os.path.dirname(os.getcwd()), filename),  # Parent directory
                os.path.join(os.path.dirname(__file__), filename),     # Module directory
                os.path.join(os.path.dirname(os.path.dirname(__file__)), filename)  # Parent of module directory
            ]
            
            # Use the first path that looks reasonable - prioritize existing files
            save_path = None
            
            # First check if any of these paths already exist
            for path in save_paths:
                if os.path.exists(path):
                    save_path = path
                    break
            
            # If not found, use the first path that has a writable directory
            if not save_path:
                for path in save_paths:
                    try:
                        dir_path = os.path.dirname(path)
                        if not dir_path:  # If it's just a filename
                            dir_path = os.getcwd()
                        if os.path.exists(dir_path) and os.access(dir_path, os.W_OK):
                            save_path = path
                            break
                    except:
                        continue
            
            # If still not found, default to current directory
            if not save_path:
                save_path = os.path.join(os.getcwd(), filename)
            
            # Build world data
            world_data = {
                "current_region_id": self.current_region_id,
                "current_room_id": self.current_room_id,
                "player": self.player.to_dict(),
                "regions": {},
                "npcs": {},
                "plugin_data": self.plugin_data  # Save plugin data
            }
            
            # Save regions and rooms
            for region_id, region in self.regions.items():
                region_data = {
                    "name": region.name,
                    "description": region.description,
                    "rooms": {}
                }
                
                for room_id, room in region.rooms.items():
                    room_data = room.to_dict()
                    # Explicitly handle items to ensure consistent format
                    if hasattr(room, "items"):
                        room_data["items"] = [item.to_dict() for item in room.items]
                    else:
                        room_data["items"] = []
                    region_data["rooms"][room_id] = room_data
                    
                world_data["regions"][region_id] = region_data
                
            # Save NPCs
            for obj_id, npc in self.npcs.items():
                world_data["npcs"][obj_id] = npc.to_dict()
                
            # Write to file with nice formatting
            with open(save_path, 'w') as f:
                json.dump(world_data, f, indent=2)
                
            print(f"World saved successfully to {save_path}")
            return True
            
        except Exception as e:
            print(f"Error saving world: {e}")
            import traceback
            traceback.print_exc()
            return False

    def load_from_json(self, filename: str) -> bool:
        """
        Load the world state from a JSON file.
        
        Args:
            filename: The filename to load from
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Try multiple potential paths to find the file
            paths_to_try = [
                filename,                             # Direct path
                os.path.join(os.getcwd(), filename),  # Current working directory
                os.path.join(os.path.dirname(os.getcwd()), filename),  # Parent directory
                os.path.join(os.path.dirname(__file__), filename),     # Module directory
                os.path.join(os.path.dirname(os.path.dirname(__file__)), filename)  # Parent of module directory
            ]
            
            file_path = None
            for path in paths_to_try:
                if os.path.exists(path):
                    file_path = path
                    print(f"Found world file at: {path}")
                    break
                    
            if not file_path:
                print(f"Error: Could not find world file '{filename}' in any of the expected locations")
                print(f"Searched in: {', '.join(paths_to_try)}")
                return False
                
            with open(file_path, 'r') as f:
                world_data = json.load(f)
                
            # Clear current state
            self.regions = {}
            self.npcs = {}
            self.start_time = time.time()
            
            # Load plugin data
            if "plugin_data" in world_data:
                self.plugin_data = world_data["plugin_data"]
            else:
                self.plugin_data = {}
                
            # Load player data
            if "player" in world_data:
                self.player = Player.from_dict(world_data["player"])
                
            # Load regions and rooms
            for region_id, region_data in world_data.get("regions", {}).items():
                region = Region(region_data["name"], region_data["description"])
                
                for room_id, room_data in region_data.get("rooms", {}).items():
                    room = Room.from_dict(room_data)
                    
                    # Load items in room
                    if "items" in room_data:
                        room.items = []
                        for item_data in room_data["items"]:
                            item = ItemFactory.from_dict(item_data)
                            if item:  # Make sure item was created successfully
                                room.items.append(item)
                    else:
                        room.items = []
                        
                    region.add_room(room_id, room)
                    
                self.add_region(region_id, region)
                
            # Load NPCs
            current_time = time.time() - self.start_time
            for obj_id, npc_data in world_data.get("npcs", {}).items():
                npc = NPC.from_dict(npc_data)
                npc.last_moved = current_time
                
                # Make sure NPC has an inventory
                if not hasattr(npc, "inventory") or npc.inventory is None:
                    npc.inventory = Inventory(max_slots=10, max_weight=50.0)
                    
                self.npcs[obj_id] = npc
                
            # Set current location
            self.current_region_id = world_data.get("current_region_id")
            self.current_room_id = world_data.get("current_room_id")
            
            print(f"World loaded successfully from {file_path}")
            print(f"Regions: {len(self.regions)}, NPCs: {len(self.npcs)}")
            print(f"Current location: {self.current_region_id}:{self.current_room_id}")
            
            return True
            
        except Exception as e:
            print(f"Error loading world: {e}")
            import traceback
            traceback.print_exc()
            return False

    def set_plugin_data(self, plugin_id: str, key: str, value: Any) -> None:
        """
        Store plugin-specific data in the world.
        
        Args:
            plugin_id: The ID of the plugin
            key: The data key
            value: The data value
        """
        if plugin_id not in self.plugin_data:
            self.plugin_data[plugin_id] = {}
        self.plugin_data[plugin_id][key] = value

    def get_plugin_data(self, plugin_id: str, key: str, default: Any = None) -> Any:
        """
        Retrieve plugin-specific data from the world.
        
        Args:
            plugin_id: The ID of the plugin
            key: The data key
            default: Default value if the key doesn't exist
            
        Returns:
            The stored data value or the default
        """
        if plugin_id not in self.plugin_data:
            return default
        return self.plugin_data[plugin_id].get(key, default)

    def find_path(self, source_region_id: str, source_room_id: str, 
                 target_region_id: str, target_room_id: str) -> Optional[List[str]]:
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
    
    def get_room_description_for_display(self) -> str:
        """
        Get a fully formatted room description for display.
        This adds all environmental elements like NPCs and items.
        
        Returns:
            Formatted room description with all elements
        """
        current_room = self.get_current_room()
        if not current_room:
            return f"{TextFormatter.FORMAT_ERROR}You are nowhere.{TextFormatter.FORMAT_RESET}"
        
        # Get current time period and weather
        time_period = self.get_plugin_data("time_plugin", "time_period")
        weather = self.get_plugin_data("weather_plugin", "current_weather")
        
        # Get basic room description
        room_desc = current_room.get_full_description(time_period, weather)
        
        # Add NPCs
        npcs_in_room = self.get_current_room_npcs()
        npcs_text = []
        if npcs_in_room:
            for npc in npcs_in_room:
                activity = ""
                if hasattr(npc, "ai_state") and "current_activity" in npc.ai_state:
                    activity = f" ({npc.ai_state['current_activity']})"
                    
                npcs_text.append(f"{TextFormatter.FORMAT_HIGHLIGHT}{npc.name}{TextFormatter.FORMAT_RESET} is here{activity}.")
        
        # Add items
        items_in_room = self.get_items_in_current_room()
        items_text = []
        if items_in_room:
            for item in items_in_room:
                items_text.append(f"There is {TextFormatter.FORMAT_CATEGORY}{item.name}{TextFormatter.FORMAT_RESET} here.")
        
        # Combine all elements
        full_description = room_desc
        
        if npcs_text:
            full_description += "\n\n" + "\n".join(npcs_text)
            
        if items_text:
            full_description += "\n\n" + "\n".join(items_text)
        
        return full_description