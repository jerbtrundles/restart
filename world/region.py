# world/region.py
# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Corrected the from_dict method to instantiate the Region class directly,
#   resolving both the attribute assignment and return type Pylance errors.

from typing import Dict, List, Optional, Any
from world.room import Room
from game_object import GameObject

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
        data["rooms"] = {room_id: room.to_dict() for room_id, room in self.rooms.items()}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Region':
        """
        Deserialize region definition by directly instantiating the Region class.
        This resolves the type assignment errors.
        """
        # 1. Directly instantiate the 'Region' class ('cls') to create an object of the correct type.
        region = cls(
            name=data.get("name", "Unknown Region"),
            description=data.get("description", "No description"),
            obj_id=data.get("obj_id") or data.get("id")
        )

        # 2. Now that `region` is a proper `Region` instance, we can safely populate its attributes.
        # The `rooms` attribute was already initialized as an empty dict by the __init__ method.
        for room_id, room_data in data.get("rooms", {}).items():
            try:
                # Ensure the room's obj_id is passed from the dictionary key if not present in its data
                room_data['obj_id'] = room_data.get('obj_id', room_id)
                room = Room.from_dict(room_data)
                region.add_room(room_id, room)
            except Exception as e:
                print(f"Warning: Failed to load room '{room_id}' in region '{region.name}': {e}")

        # 3. Load any additional generic properties from the base GameObject.
        region.properties = data.get("properties", {})

        # 4. Return the correctly typed 'Region' object.
        return region