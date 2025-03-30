"""
world/region.py
Region module for the MUD game.
"""
from typing import Dict, Optional
from world.room import Room


class Region:
    """
    Represents a collection of rooms forming a region in the game world.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.rooms: Dict[str, Room] = {}
    
    def add_room(self, room_id: str, room: Room):
        """
        Adds a room to the region.
        """
        self.rooms[room_id] = room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """
        Returns the room with the given ID, or None if it doesn't exist.
        """
        return self.rooms.get(room_id)