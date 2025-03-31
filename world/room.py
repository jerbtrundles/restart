"""
world/room.py
Enhanced Room class with improved text descriptions.
"""
from typing import Dict, List, Optional, Any
from game_object import GameObject
from items.item import Item
from utils.text_formatter import TextFormatter

class Room(GameObject):
    def __init__(self, name: str, description: str, exits: Dict[str, str] = None, obj_id: str = None):
        super().__init__(obj_id, name, description)
        self.exits = exits or {}  # Direction -> room_id mapping
        self.items: List[Item] = []  # Items in the room
        self.visited = False  # Whether the player has visited this room
        
        # Store in properties
        self.update_property("exits", self.exits)
        self.update_property("visited", self.visited)
        
        # Time-specific descriptions
        self.time_descriptions = {
            "dawn": "",
            "day": "",
            "dusk": "",
            "night": ""
        }
        self.update_property("time_descriptions", self.time_descriptions)
        
        # Environmental properties
        self.env_properties = {
            "dark": False,      # Is the room dark?
            "outdoors": False,  # Is the room outdoors?
            "has_windows": False,  # Can you see outside?
            "noisy": False,     # Is the room noisy?
            "smell": "",        # Distinctive smell if any
            "temperature": "normal"  # Temperature (cold, normal, warm, hot)
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
        desc = f"{TextFormatter.FORMAT_TITLE}{self.name.upper()}{TextFormatter.FORMAT_RESET}\n\n"
        
        # Add the base description
        desc += self.description
        
        # Add time-specific description if available
        if time_period and time_period in self.time_descriptions and self.time_descriptions[time_period]:
            desc += f"\n\n{self.time_descriptions[time_period]}"
        
        # Add weather description for outdoor rooms
        if weather and self.env_properties.get("outdoors", False):
            desc += f"\n\nThe weather is {weather}."
        
        # Add environment-specific descriptions
        if self.env_properties.get("dark", False):
            if time_period == "night":
                desc += "\n\nIt's pitch black here. You can barely see anything."
            else:
                desc += "\n\nIt's dark here. You can barely make out your surroundings."
                
        if self.env_properties.get("noisy", False):
            desc += "\n\nThe room is filled with noise."
            
        if self.env_properties.get("smell"):
            desc += f"\n\nYou detect a {self.env_properties['smell']} smell."
            
        if self.env_properties.get("temperature") != "normal":
            temp = self.env_properties["temperature"]
            if temp == "cold":
                desc += "\n\nIt's noticeably cold in here."
            elif temp == "warm":
                desc += "\n\nIt's comfortably warm in here."
            elif temp == "hot":
                desc += "\n\nThe air is stifling hot."
        
        # Add exits list
        exits_list = list(self.exits.keys())
        exits_list.sort()  # Sort directions alphabetically
        exit_desc = ", ".join(exits_list) if exits_list else "none"
        desc += f"\n\n{TextFormatter.FORMAT_CATEGORY}Exits:{TextFormatter.FORMAT_RESET} {exit_desc}"
        
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
        """
        Convert the room to a dictionary for serialization.
        
        Returns:
            Dictionary representation of the room
        """
        # Start with the base implementation
        data = super().to_dict()
        
        # Add Room-specific fields
        data["exits"] = self.exits
        data["items"] = [item.to_dict() for item in self.items]
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
        # Create the room with base fields
        room = cls(
            name=data.get("name", "Unknown Room"),
            description=data.get("description", "No description"),
            exits=data.get("exits", {}),
            obj_id=data.get("id") or data.get("obj_id")
        )
        
        # Set additional fields
        room.visited = data.get("visited", False)
        
        if "time_descriptions" in data:
            room.time_descriptions = data["time_descriptions"]
            
        if "env_properties" in data:
            room.env_properties = data["env_properties"]
            
        # Load properties
        if "properties" in data:
            room.properties = data["properties"]
            
        return room