# world/region.py
from typing import Dict, List, Optional, Any # Import Any
from world.room import Room
from game_object import GameObject # Import GameObject

class Region(GameObject):
    def __init__(self, name: str, description: str, obj_id: Optional[str] = None):
        region_obj_id = obj_id if obj_id else f"region_{name.lower().replace(' ', '_')}"
        super().__init__(obj_id=region_obj_id, name=name, description=description)
        self.rooms: Dict[str, Room] = {}

    def add_room(self, room_id: str, room: Room):
        self.rooms[room_id] = room

    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize region definition."""
        data = super().to_dict()
        # Serialize rooms using their to_dict (which includes initial refs)
        data["rooms"] = {room_id: room.to_dict() for room_id, room in self.rooms.items()}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Region':
        """Deserialize region definition."""
        # Use GameObject's from_dict first
        region = super(Region, cls).from_dict(data)

        # Load rooms using Room.from_dict
        region.rooms = {}
        for room_id, room_data in data.get("rooms", {}).items():
            try:
                # Ensure room_id hint is passed if needed
                room_data['obj_id'] = room_data.get('obj_id', room_id)
                room = Room.from_dict(room_data) # Room.from_dict now handles initial refs
                region.rooms[room_id] = room
            except Exception as e:
                print(f"Warning: Failed to load room '{room_id}' in region '{region.name}': {e}")
                # Continue loading other rooms

        return region
