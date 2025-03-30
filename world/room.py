"""
world/room.py
Enhanced Room module for the MUD game.
"""
from typing import Dict, List, Optional
from items.item import Item


class Room:
    # Add to Room.__init__ method:
    def __init__(self, name: str, description: str, exits: Dict[str, str] = None):
        """
        Initialize a room.
        
        Args:
            name: The name of the room.
            description: The description of the room.
            exits: A dictionary mapping directions to destination room IDs.
        """
        self.name = name
        self.description = description
        self.exits = exits or {}  # Direction -> room_id mapping
        self.items: List[Item] = []  # Items in the room
        
        # Additional properties
        self.visited = False  # Whether the player has visited this room
        self.properties = {}  # Custom properties like "dark", "noisy", etc.
        
        # Time-of-day descriptions
        self.time_descriptions = {
            "dawn": "",
            "day": "",
            "dusk": "",
            "night": ""
        }
    
    # Update Room.get_full_description method:
    def get_full_description(self, time_period: str = None) -> str:
        """
        Returns a full textual description of the room, including exits.
        
        Args:
            time_period: The current time period (dawn, day, dusk, night).
            
        Returns:
            A complete room description.
        """
        # Format exits in a more organized way
        exits_list = list(self.exits.keys())
        exits_list.sort()  # Sort directions alphabetically
        exit_desc = ", ".join(exits_list) if exits_list else "none"
        
        # Basic description
        desc = f"{self.name}\n\n{self.description}"
        
        # Add time-specific description if available
        if time_period and time_period in self.time_descriptions and self.time_descriptions[time_period]:
            desc += f"\n\n{self.time_descriptions[time_period]}"
        
        # Add exits
        desc += f"\n\nExits: {exit_desc}"
        
        # Add special property descriptions
        if "dark" in self.properties and self.properties["dark"]:
            # Make darkness more pronounced at night
            if time_period == "night":
                desc = "It's pitch black here. You can barely see anything.\n\n" + desc
            else:
                desc = "It's dark here. You can barely make out your surroundings.\n\n" + desc
                
        if "noisy" in self.properties and self.properties["noisy"]:
            desc += "\n\nThe room is filled with noise."
            
        if "smell" in self.properties:
            desc += f"\n\nYou detect a {self.properties['smell']} smell."
        
        return desc
    
    def get_exit(self, direction: str) -> Optional[str]:
        """
        Returns the destination room ID for the given direction, or None if there's no exit.
        """
        return self.exits.get(direction.lower())
    
    def add_item(self, item: Item) -> None:
        """
        Add an item to the room.
        
        Args:
            item: The item to add.
        """
        self.items.append(item)
    
    def remove_item(self, item_id: str) -> Optional[Item]:
        """
        Remove an item from the room.
        
        Args:
            item_id: The ID of the item to remove.
            
        Returns:
            The removed item, or None if not found.
        """
        for i, item in enumerate(self.items):
            if item.item_id == item_id:
                return self.items.pop(i)
        return None
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """
        Get an item from the room without removing it.
        
        Args:
            item_id: The ID of the item to get.
            
        Returns:
            The item, or None if not found.
        """
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None
    
    # Update Room.to_dict method:
    def to_dict(self) -> Dict:
        """
        Convert the room to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the room.
        """
        return {
            "name": self.name,
            "description": self.description,
            "exits": self.exits,
            "items": [item.to_dict() for item in self.items],
            "visited": self.visited,
            "properties": self.properties,
            "time_descriptions": self.time_descriptions
        }

    # Update Room.from_dict method:
    @classmethod
    def from_dict(cls, data: Dict) -> 'Room':
        """
        Create a room from a dictionary.
        
        Args:
            data: The dictionary containing room data.
            
        Returns:
            A Room instance.
        """
        room = cls(
            name=data["name"],
            description=data["description"],
            exits=data.get("exits", {})
        )
        
        # Set additional properties
        room.visited = data.get("visited", False)
        room.properties = data.get("properties", {})
        
        # Set time descriptions if present
        if "time_descriptions" in data:
            room.time_descriptions = data["time_descriptions"]
        
        # Items will be loaded separately by the world loader
        
        return room