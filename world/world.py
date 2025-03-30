"""
world/world.py
World module for the MUD game.
Represents the game world, containing regions, rooms, NPCs, and items.
"""
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
    """
    Represents the game world, containing regions, rooms, NPCs, and items.
    """
    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.player = Player("Adventurer")
        
        # Add inventory to player
        if not hasattr(self.player, "inventory"):
            self.player.inventory = Inventory(max_slots=20, max_weight=100.0)
        
        # NPCs in the world
        self.npcs: Dict[str, NPC] = {}
        
        # Game time tracking (seconds since game start)
        self.start_time = time.time()
        self.last_update_time = 0
        
        self.plugin_data = {}


    
    def add_region(self, region_id: str, region: Region):
        """
        Adds a region to the world.
        """
        self.regions[region_id] = region
    
    def get_region(self, region_id: str) -> Optional[Region]:
        """
        Returns the region with the given ID, or None if it doesn't exist.
        """
        return self.regions.get(region_id)
    
    def get_current_region(self) -> Optional[Region]:
        """
        Returns the current region the player is in, or None if not set.
        """
        if self.current_region_id:
            return self.regions.get(self.current_region_id)
        return None
    
    def get_current_room(self) -> Optional[Room]:
        """
        Returns the current room the player is in, or None if not set.
        """
        region = self.get_current_region()
        if region and self.current_room_id:
            return region.get_room(self.current_room_id)
        return None
    
    def add_npc(self, npc: NPC):
        """
        Add an NPC to the world.
        
        Args:
            npc: The NPC to add.
        """
        # Initialize the NPC's last_moved time to the current game time
        # This ensures the cooldown starts from when the NPC is added to the world
        npc.last_moved = time.time() - self.start_time
        self.npcs[npc.npc_id] = npc
    
    def get_npc(self, npc_id: str) -> Optional[NPC]:
        """
        Get an NPC by ID.
        
        Args:
            npc_id: The ID of the NPC.
            
        Returns:
            The NPC, or None if not found.
        """
        return self.npcs.get(npc_id)
    
    def get_npcs_in_room(self, region_id: str, room_id: str) -> List[NPC]:
        """
        Get all NPCs in a specific room.
        
        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            
        Returns:
            A list of NPCs in the room.
        """
        return [npc for npc in self.npcs.values() 
                if npc.current_region_id == region_id and npc.current_room_id == room_id]
    
    def get_current_room_npcs(self) -> List[NPC]:
        """
        Get all NPCs in the player's current room.
        
        Returns:
            A list of NPCs in the room.
        """
        if not self.current_region_id or not self.current_room_id:
            return []
            
        return self.get_npcs_in_room(self.current_region_id, self.current_room_id)
    
    def update(self):
        """
        Update the game world state.
        
        Returns:
            A list of messages about world events.
        """
        current_time = time.time() - self.start_time
        messages = []
        
        # Only update every second
        if current_time - self.last_update_time < 1:
            return messages
            
        # Update all NPCs
        for npc in self.npcs.values():
            npc_message = npc.update(self, current_time)
            if npc_message:
                messages.append(npc_message)
        
        self.last_update_time = current_time
        return messages

    """
    Updated version of World.change_room method to support plugin notifications.
    This should replace the existing method in the World class.
    """

    def change_room(self, direction: str) -> str:
        """
        Attempts to move the player in the given direction.
        Returns a description of the result.
        """
        # Store old location
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        
        current_room = self.get_current_room()
        if not current_room:
            return "You are nowhere."
        
        new_room_id = current_room.get_exit(direction)
        if not new_room_id:
            return f"You can't go {direction}."
        
        # Check if room exists in current region
        region = self.get_current_region()
        if region and new_room_id in region.rooms:
            self.current_room_id = new_room_id
            
            # Get NPCs in the new room
            npcs_in_room = self.get_current_room_npcs()
            npc_descriptions = ""
            
            if npcs_in_room:
                npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
            
            # Notify plugins about room change if game manager is available
            if hasattr(self, "game") and hasattr(self.game, "plugin_manager"):
                # Notify about room exit
                self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
                
                # Notify about room enter
                self.game.plugin_manager.on_room_enter(self.current_region_id, self.current_room_id)
            
            return self.get_current_room().get_full_description() + npc_descriptions
        
        # Check if it's a special format for region transition: region_id:room_id
        if ":" in new_room_id:
            new_region_id, new_room_id = new_room_id.split(":")
            if new_region_id in self.regions:
                new_region = self.regions[new_region_id]
                if new_room_id in new_region.rooms:
                    # Update location
                    self.current_region_id = new_region_id
                    self.current_room_id = new_room_id
                    
                    # Get NPCs in the new room
                    npcs_in_room = self.get_current_room_npcs()
                    npc_descriptions = ""
                    
                    if npcs_in_room:
                        npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
                    
                    # Notify plugins about room change if game manager is available
                    if hasattr(self, "game") and hasattr(self.game, "plugin_manager"):
                        # Notify about room exit
                        self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
                        
                        # Notify about room enter
                        self.game.plugin_manager.on_room_enter(self.current_region_id, self.current_room_id)
                    
                    return f"You've entered {new_region.name}.\n\n{self.get_current_room().get_full_description()}{npc_descriptions}"
        
        return "That exit leads nowhere usable."
    
    # Update World.look method:
    def look(self) -> str:
        """
        Returns a description of the current room.
        """
        current_room = self.get_current_room()
        if current_room:
            # Get the current time period from time plugin if available
            time_period = None
            if hasattr(self, "plugin_data") and "time_plugin" in self.plugin_data:
                time_period = self.plugin_data["time_plugin"].get("current_time_period")
            
            # Get room description with time period
            room_desc = current_room.get_full_description(time_period)
            
            # Get NPCs in the room
            npcs_in_room = self.get_current_room_npcs()
            npc_descriptions = ""
            
            if npcs_in_room:
                npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
            
            # Get items in the room
            items_in_room = self.get_items_in_current_room()
            item_descriptions = ""
            
            if items_in_room:
                item_descriptions = "\n\n" + "\n".join([f"There is {item.name} here." for item in items_in_room])
            
            return room_desc + npc_descriptions + item_descriptions
            
        return "You are nowhere."
        
    def get_player_status(self) -> str:
        """
        Returns the player's status information.
        """
        status = self.player.get_status()
        
        # Add inventory information if the player has an inventory
        if hasattr(self.player, "inventory"):
            inventory_desc = "\n\n" + self.player.inventory.list_items()
            status += inventory_desc
            
        return status
        
    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        """
        Get all items in a specific room.
        
        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            
        Returns:
            A list of items in the room.
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
            A list of items in the room.
        """
        if not self.current_region_id or not self.current_room_id:
            return []
            
        return self.get_items_in_room(self.current_region_id, self.current_room_id)
    
    def add_item_to_room(self, region_id: str, room_id: str, item: Item) -> bool:
        """
        Add an item to a room.
        
        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            item: The item to add.
            
        Returns:
            True if successful, False otherwise.
        """
        region = self.get_region(region_id)
        if not region:
            return False
            
        room = region.get_room(room_id)
        if not room:
            return False
            
        # Initialize the items list if it doesn't exist
        if not hasattr(room, "items"):
            room.items = []
            
        room.items.append(item)
        return True
    
    def remove_item_from_room(self, region_id: str, room_id: str, item_id: str) -> Optional[Item]:
        """
        Remove an item from a room.
        
        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            item_id: The ID of the item to remove.
            
        Returns:
            The removed item, or None if not found.
        """
        items = self.get_items_in_room(region_id, room_id)
        for i, item in enumerate(items):
            if item.item_id == item_id:
                return items.pop(i)
                
        return None

    # Update World.save_to_json method:
    def save_to_json(self, filename: str) -> bool:
        """
        Save the world state to a JSON file.
        
        Args:
            filename: The filename to save to.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Build a dictionary representing the world state
            world_data = {
                "current_region_id": self.current_region_id,
                "current_room_id": self.current_room_id,
                "player": self.player.to_dict(),
                "regions": {},
                "npcs": {},
                "plugin_data": self.plugin_data  # Save plugin data
            }
            
            # Save regions and their rooms
            for region_id, region in self.regions.items():
                region_data = {
                    "name": region.name,
                    "description": region.description,
                    "rooms": {}
                }
                
                for room_id, room in region.rooms.items():
                    room_data = room.to_dict()
                    # Convert items to dictionary format
                    room_data["items"] = [item.to_dict() for item in getattr(room, "items", [])]
                    region_data["rooms"][room_id] = room_data
                
                world_data["regions"][region_id] = region_data
            
            # Save NPCs
            for npc_id, npc in self.npcs.items():
                world_data["npcs"][npc_id] = npc.to_dict()
            
            # Write to file
            with open(filename, 'w') as f:
                json.dump(world_data, f, indent=2)
                
            return True
            
        except Exception as e:
            print(f"Error saving world: {e}")
            return False

    # Update World.load_from_json method:
    def load_from_json(self, filename: str) -> bool:
        """
        Load the world state from a JSON file.
        
        Args:
            filename: The filename to load from.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Check if file exists
            if not os.path.exists(filename):
                print(f"File not found: {filename}")
                return False
                
            # Read the file
            with open(filename, 'r') as f:
                world_data = json.load(f)
            
            # Clear current state
            self.regions = {}
            self.npcs = {}
            
            # Set game start time
            self.start_time = time.time()
            
            # Load plugin data if available
            if "plugin_data" in world_data:
                self.plugin_data = world_data["plugin_data"]
            else:
                self.plugin_data = {}
            
            # Load player
            if "player" in world_data:
                self.player = Player.from_dict(world_data["player"])
            
            # Load regions and rooms
            for region_id, region_data in world_data.get("regions", {}).items():
                region = Region(region_data["name"], region_data["description"])
                
                # Load rooms
                for room_id, room_data in region_data.get("rooms", {}).items():
                    room = Room.from_dict(room_data)
                    
                    # Load items in the room
                    if "items" in room_data:
                        room.items = []
                        for item_data in room_data["items"]:
                            item = ItemFactory.from_dict(item_data)
                            room.items.append(item)
                    
                    region.add_room(room_id, room)
                
                self.add_region(region_id, region)
            
            # Load NPCs
            current_time = time.time() - self.start_time
            for npc_id, npc_data in world_data.get("npcs", {}).items():
                npc = NPC.from_dict(npc_data)
                
                # Initialize last_moved time to current time to ensure proper cooldown
                npc.last_moved = current_time
                self.npcs[npc_id] = npc
            
            # Set current location
            self.current_region_id = world_data.get("current_region_id")
            self.current_room_id = world_data.get("current_room_id")
            
            return True
            
        except Exception as e:
            print(f"Error loading world: {e}")
            return False

    # Add method to store plugin data:
    def set_plugin_data(self, plugin_id: str, key: str, value: Any) -> None:
        """
        Store plugin-specific data in the world.
        
        Args:
            plugin_id: The ID of the plugin.
            key: The data key.
            value: The data value.
        """
        if plugin_id not in self.plugin_data:
            self.plugin_data[plugin_id] = {}
        self.plugin_data[plugin_id][key] = value

    # Add method to retrieve plugin data:
    def get_plugin_data(self, plugin_id: str, key: str, default: Any = None) -> Any:
        """
        Retrieve plugin-specific data from the world.
        
        Args:
            plugin_id: The ID of the plugin.
            key: The data key.
            default: The default value if not found.
            
        Returns:
            The stored data value, or default if not found.
        """
        if plugin_id not in self.plugin_data:
            return default
        return self.plugin_data[plugin_id].get(key, default)
