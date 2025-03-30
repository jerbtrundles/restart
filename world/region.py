"""world/region.py"""
from typing import Dict, Optional
from world.room import Room

class Region:
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.rooms: Dict[str, Room] = {}
    
    def add_room(self, room_id: str, room: Room):
        self.rooms[room_id] = room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)