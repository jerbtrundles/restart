# engine/world/room.py
from typing import Dict, List, Optional, Any
import uuid
from engine.config import FORMAT_CATEGORY, FORMAT_RESET
from engine.game_object import GameObject
from engine.items.item import Item

class Room(GameObject):
    def __init__(self, name: str, description: str, exits: Optional[Dict[str, str]] = None, obj_id: Optional[str] = None):
        room_obj_id = obj_id if obj_id else f"room_{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:4]}"
        
        super().__init__(obj_id=room_obj_id, name=name, description=description)

        self.exits = exits or {}
        self.items: List[Item] = []
        self.initial_item_refs: List[Dict[str, Any]] = []
        self.initial_npc_refs: List[Dict[str, Any]] = []
        self.visited = False
        self.time_descriptions = {"dawn": "", "day": "", "dusk": "", "night": ""}
        self.env_properties = {"dark": False, "outdoors": False, "has_windows": False, "noisy": False, "smell": "", "temperature": "normal"}
        
        self.update_property("exits", self.exits)
        self.update_property("visited", self.visited)
        self.update_property("time_descriptions", self.time_descriptions)
        self.update_property("env_properties", self.env_properties)

    def get_full_description(self, time_period: str = "day", weather: str = "clear", is_outdoors: bool = True) -> str:
        """Get a full formatted description of the room's state, WITHOUT the title."""
        desc = self.description
        
        # 1. Try exact time period match (e.g., "dawn", "dusk", "night")
        time_desc = self.time_descriptions.get(time_period)
        
        # 2. Fallback for day phases (morning/afternoon) to generic "day" if specific is missing
        if not time_desc:
            if time_period in ["morning", "afternoon"]:
                time_desc = self.time_descriptions.get("day")
                
        if time_desc: desc += f"\n\n{time_desc}"
        
        if weather and is_outdoors: desc += f"\n\nThe weather is {weather}."
        if self.properties.get("dark", False): desc += "\n\nIt is very dark here."
        if self.properties.get("noisy", False): desc += "\n\nThe area is filled with noise."
        smell = self.properties.get("smell")
        if smell: desc += f"\n\nYou detect a {smell} smell."
        temp = self.properties.get("temperature", "normal")
        if temp == "cold": desc += "\n\nIt's noticeably cold in here."
        elif temp == "hot": desc += "\n\nThe air is stiflingly hot."
        exits_list = sorted(list(self.exits.keys()))
        exit_desc = ", ".join(exits_list) if exits_list else "none"
        desc += f"\n\n{FORMAT_CATEGORY}Exits:{FORMAT_RESET} {exit_desc}"
        return desc
    
    def get_exit(self, direction: str) -> Optional[str]:
        return self.exits.get(direction.lower())
    
    def add_item(self, item: Item) -> None:
        self.items.append(item)
    
    def remove_item(self, obj_id: str) -> Optional[Item]:
        for i, item in enumerate(self.items):
            if item.obj_id == obj_id:
                return self.items.pop(i)
        return None
    
    def get_item(self, obj_id: str) -> Optional[Item]:
        for item in self.items:
            if item.obj_id == obj_id:
                return item
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize room definition."""
        data = super().to_dict()
        data["exits"] = self.exits
        data["initial_items"] = self.initial_item_refs
        data["initial_npcs"] = self.initial_npc_refs
        data["visited"] = self.visited
        data["time_descriptions"] = self.time_descriptions
        data["env_properties"] = self.env_properties
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Room':
        """Deserialize room definition safely by directly instantiating the class."""
        room = cls(
            name=data.get("name", "Unknown Room"),
            description=data.get("description", "No description"),
            obj_id=data.get("obj_id") or data.get("id"),
            exits=data.get("exits", {})
        )

        room.properties = data.get("properties", {})
        room.is_alive = data.get("is_alive", True)
        room.visited = data.get("visited", False)
        room.time_descriptions = data.get("time_descriptions", {"dawn":"", "day":"", "dusk":"", "night":""})
        room.env_properties = data.get("env_properties", {})
        
        room.initial_item_refs = data.get("initial_items", [])
        if not room.initial_item_refs and "items" in data:
            room.initial_item_refs = data.get("items", [])
        room.initial_npc_refs = data.get("initial_npcs", [])

        room.items = []

        room.update_property("exits", room.exits)
        room.update_property("visited", room.visited)
        room.update_property("time_descriptions", room.time_descriptions)
        room.update_property("env_properties", room.env_properties)

        return room