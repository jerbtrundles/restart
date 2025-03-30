"""world/room.py"""
from typing import Dict, List, Optional
from items.item import Item

class Room:
    def __init__(self, name: str, description: str, exits: Dict[str, str] = None):
        self.name = name
        self.description = description
        self.exits = exits or {}  # Direction -> room_id mapping
        self.items: List[Item] = []  # Items in the room
        self.visited = False  # Whether the player has visited this room
        self.properties = {}  # Custom properties like "dark", "noisy", etc.
        self.time_descriptions = {
            "dawn": "",
            "day": "",
            "dusk": "",
            "night": ""
        }

    def get_full_description(self, time_period: str = None) -> str:
        exits_list = list(self.exits.keys())
        exits_list.sort()  # Sort directions alphabetically
        exit_desc = ", ".join(exits_list) if exits_list else "none"
        desc = f"{self.name}\n\n{self.description}"
        if time_period and time_period in self.time_descriptions and self.time_descriptions[time_period]:
            desc += f"\n\n{self.time_descriptions[time_period]}"
        desc += f"\n\nExits: {exit_desc}"
        if "dark" in self.properties and self.properties["dark"]:
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
        return self.exits.get(direction.lower())
    
    def add_item(self, item: Item) -> None:
        self.items.append(item)
    
    def remove_item(self, item_id: str) -> Optional[Item]:
        for i, item in enumerate(self.items):
            if item.item_id == item_id:
                return self.items.pop(i)
        return None
    
    def get_item(self, item_id: str) -> Optional[Item]:
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "exits": self.exits,
            "items": [item.to_dict() for item in self.items],
            "visited": self.visited,
            "properties": self.properties,
            "time_descriptions": self.time_descriptions
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Room':
        room = cls(
            name=data["name"],
            description=data["description"],
            exits=data.get("exits", {})
        )
        room.visited = data.get("visited", False)
        room.properties = data.get("properties", {})
        if "time_descriptions" in data:
            room.time_descriptions = data["time_descriptions"]
        return room