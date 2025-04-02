# world/region.py
from typing import Dict, List, Optional, Any # Import Any
from world.room import Room
from game_object import GameObject # Import GameObject
# Need these for from_dict
from items.item_factory import ItemFactory
from items.item import Item


class Region(GameObject): # Inherit from GameObject
    def __init__(self, name: str, description: str, obj_id: Optional[str] = None): # Added obj_id
        # Generate obj_id if not provided
        region_obj_id = obj_id if obj_id else f"region_{name.lower().replace(' ', '_')}"
        # Call GameObject's init
        super().__init__(obj_id=region_obj_id, name=name, description=description)
        self.rooms: Dict[str, Room] = {}
        # Properties dict is now inherited

    def add_room(self, room_id: str, room: Room):
        self.rooms[room_id] = room

    def get_room(self, room_id: str) -> Optional[Room]:
        return self.rooms.get(room_id)

    # *** ADDED: Serialization Methods ***
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict() # Get base GameObject data (id, name, desc, properties)
        # Serialize rooms
        data["rooms"] = {room_id: room.to_dict() for room_id, room in self.rooms.items()}
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Region':
        # Use GameObject's from_dict first to initialize name, description, properties etc.
        # We pass cls=Region to ensure it creates a Region instance
        region = super(Region, cls).from_dict(data)

        # Now load the rooms specific to the Region
        region.rooms = {}
        for room_id, room_data in data.get("rooms", {}).items():
            try:
                room = Room.from_dict(room_data)
                # Defer item loading to Room.from_dict if possible, otherwise do it here.
                # Assuming Room.from_dict doesn't handle items yet:
                if "items" in room_data:
                     loaded_items: List[Item] = []
                     for item_data in room_data["items"]:
                          if item_data: # Check if item data exists
                               item = ItemFactory.from_dict(item_data)
                               if item:
                                   loaded_items.append(item)
                     room.items = loaded_items # Assign loaded items to the room instance
                else:
                     room.items = [] # Ensure items list exists

                region.rooms[room_id] = room
            except Exception as e:
                # Log error and potentially skip the problematic room
                print(f"Warning: Failed to load room '{room_id}' in region '{region.name}': {e}")
                # Depending on desired robustness, you might want to raise the error
                # or just continue loading the rest of the world.

        return region
