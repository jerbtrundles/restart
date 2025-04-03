"""
world/room.py
Enhanced Room class with improved text descriptions.
"""
from typing import Dict, List, Optional, Any
from core.config import FORMAT_CATEGORY, FORMAT_RESET, FORMAT_TITLE
from game_object import GameObject
from items.item import Item
from utils.text_formatter import TextFormatter
from items.item_factory import ItemFactory # Ensure this is imported

class Room(GameObject):
    def __init__(self, name: str, description: str, exits: Dict[str, str] = None, obj_id: str = None):
        super().__init__(obj_id, name, description)
        self.exits = exits or {}
        # *** Initialize and type-hint items here in __init__ ***
        self.items: List[Item] = []
        self.visited = False

        self.update_property("exits", self.exits)
        self.update_property("visited", self.visited)

        self.time_descriptions = {
            "dawn": "", "day": "", "dusk": "", "night": ""
        }
        self.update_property("time_descriptions", self.time_descriptions)

        self.env_properties = {
            "dark": False, "outdoors": False, "has_windows": False,
            "noisy": False, "smell": "", "temperature": "normal"
        }
        self.update_property("env_properties", self.env_properties)

    def get_full_description(self, time_period: str = None, weather: str = None) -> str:
        """
        Get a full formatted description of the room.
        
        Args:
            time_period: Current time period (dawn, day, dusk, night)
            weather: Current weather conditions
            
        Returns:
            Formatted room description
        """
        # Format the room name as a title
        desc = f"{FORMAT_TITLE}{self.name.upper()}{FORMAT_RESET}\n\n"

        # Add the base description
        desc += self.description

        # Add time-specific description if available
        if time_period and time_period in self.time_descriptions and self.time_descriptions[time_period]:
            desc += f"\n\n{self.time_descriptions[time_period]}"

        # Add weather description for outdoor rooms
        # Use .get() for safety
        if weather and self.env_properties.get("outdoors", False):
            desc += f"\n\nThe weather is {weather}."

        # Add environment-specific descriptions using .get() for safety
        if self.env_properties.get("dark", False):
            if time_period == "night":
                desc += "\n\nIt's pitch black here. You can barely see anything."
            else:
                desc += "\n\nIt's dark here. You can barely make out your surroundings."

        if self.env_properties.get("noisy", False):
            desc += "\n\nThe room is filled with noise."

        smell = self.env_properties.get("smell") # Get potentially missing value
        if smell: # Check if a smell exists
            desc += f"\n\nYou detect a {smell} smell."

        # *** FIX HERE: Use .get() for temperature ***
        temp = self.env_properties.get("temperature", "normal") # Default to "normal" if key is missing
        if temp != "normal":
        # *** END FIX ***
            if temp == "cold":
                desc += "\n\nIt's noticeably cold in here."
            elif temp == "warm":
                desc += "\n\nIt's comfortably warm in here."
            elif temp == "hot":
                desc += "\n\nThe air is stifling hot."

        # Add exits list
        exits_list = list(self.exits.keys())
        exits_list.sort()
        exit_desc = ", ".join(exits_list) if exits_list else "none"
        desc += f"\n\n{FORMAT_CATEGORY}Exits:{FORMAT_RESET} {exit_desc}"

        return desc
    
    def get_exit(self, direction: str) -> Optional[str]:
        """
        Get the destination room_id for a given exit direction.
        
        Args:
            direction: The direction to move
            
        Returns:
            Destination room_id or None if no exit exists
        """
        return self.exits.get(direction.lower())
    
    def add_item(self, item: Item) -> None:
        """
        Add an item to the room.
        
        Args:
            item: The item to add
        """
        self.items.append(item)
    
    def remove_item(self, obj_id: str) -> Optional[Item]:
        """
        Remove an item from the room by its ID.
        
        Args:
            obj_id: The ID of the item to remove
            
        Returns:
            The removed item, or None if not found
        """
        for i, item in enumerate(self.items):
            if item.obj_id == obj_id:
                return self.items.pop(i)
        return None
    
    def get_item(self, obj_id: str) -> Optional[Item]:
        """
        Get an item from the room by its ID without removing it.
        
        Args:
            obj_id: The ID of the item to get
            
        Returns:
            The item, or None if not found
        """
        for item in self.items:
            if item.obj_id == obj_id:
                return item
        return None
    
    def is_outdoors(self) -> bool:
        """
        Check if the room is outdoors.
        
        Returns:
            True if the room is outdoors, False otherwise
        """
        return self.env_properties.get("outdoors", False)
    
    def has_windows(self) -> bool:
        """
        Check if the room has windows.
        
        Returns:
            True if the room has windows, False otherwise
        """
        return self.env_properties.get("has_windows", False)
    
    def can_see_outside(self) -> bool:
        """
        Check if the player can see outside from this room.
        
        Returns:
            True if the player can see outside, False otherwise
        """
        return self.is_outdoors() or self.has_windows()
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["exits"] = self.exits
        # getattr ensures it doesn't crash if self.items somehow doesn't exist
        data["items"] = [item.to_dict() for item in getattr(self, 'items', []) if item]
        data["visited"] = self.visited
        data["time_descriptions"] = self.time_descriptions
        data["env_properties"] = self.env_properties
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Room':
        """
        Create a room from a dictionary.
        Args:
            data: Dictionary containing room data
        Returns:
            A new Room instance
        """
        # Create instance using GameObject's from_dict
        # __init__ will have already created the self.items list
        room = super(Room, cls).from_dict(data)

        # Load specific Room attributes
        room.exits = data.get("exits", {})
        room.visited = data.get("visited", False)
        room.time_descriptions = data.get("time_descriptions", {"dawn":"", "day":"", "dusk":"", "night":""})
        room.env_properties = data.get("env_properties", {})

        # Properties dictionary is loaded by super().from_dict

        # *** Load items into the existing room.items list ***
        # No need to re-initialize or type hint here
        loaded_items: List[Item] = [] # Use a temporary list
        for item_data in data.get("items", []):
            if item_data:
                item = ItemFactory.from_dict(item_data)
                if item:
                    loaded_items.append(item)
                else:
                    item_name = item_data.get('name', 'Unknown Item')
                    item_id = item_data.get('id', item_data.get('obj_id', 'No ID'))
                    print(f"Warning: Failed to load item '{item_name}' (ID: {item_id}) in room '{room.name}'. Skipping item.")
        room.items = loaded_items # Assign the populated list

        return room
