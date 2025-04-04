"""
world/room.py
Enhanced Room class with improved text descriptions.
"""
from typing import Dict, List, Optional, Any
import uuid
from core.config import FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_RESET, FORMAT_TITLE, FORMAT_HIGHLIGHT # Added missing
from game_object import GameObject
from items.item import Item

class Room(GameObject):
    def __init__(self, name: str, description: str, exits: Dict[str, str] = None, obj_id: str = None):
        room_obj_id = obj_id if obj_id else f"room_{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:4]}" # Add uuid
        super().__init__(room_obj_id, name, description) # Pass correct obj_id
        self.exits = exits or {}
        # --- Live items in the room (dynamic) ---
        self.items: List[Item] = [] # This holds *instances* during gameplay
        # --- Initial state references (static definition) ---
        self.initial_item_refs: List[Dict[str, Any]] = [] # e.g., [{"item_id": "id", "quantity": 1}, ...]
        self.initial_npc_refs: List[Dict[str, Any]] = [] # e.g., [{"template_id": "id", "instance_id": "id"}, ...]

        self.visited = False
        self.time_descriptions = {"dawn": "", "day": "", "dusk": "", "night": ""}
        self.env_properties = {"dark": False, "outdoors": False, "has_windows": False, "noisy": False, "smell": "", "temperature": "normal"}

        # Base properties are handled by GameObject
        self.update_property("exits", self.exits)
        self.update_property("visited", self.visited)
        self.update_property("time_descriptions", self.time_descriptions)
        self.update_property("env_properties", self.env_properties)
        # Store initial refs in properties too? Maybe not necessary if only used during init.

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
        """Serialize room definition."""
        data = super().to_dict()
        data["exits"] = self.exits
        # --- Save only the *initial* references ---
        data["initial_items"] = self.initial_item_refs
        data["initial_npcs"] = self.initial_npc_refs
        # --- Do NOT save self.items here (dynamic state saved separately) ---
        data["visited"] = self.visited # Visited might be definition or state? Let's keep in definition for now.
        data["time_descriptions"] = self.time_descriptions
        data["env_properties"] = self.env_properties
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Room':
        """Deserialize room definition."""
        # Create instance using GameObject's from_dict
        room = super(Room, cls).from_dict(data)

        # Load specific Room definition attributes
        room.exits = data.get("exits", {})
        room.visited = data.get("visited", False) # Load visited status from definition
        room.time_descriptions = data.get("time_descriptions", {"dawn":"", "day":"", "dusk":"", "night":""})
        room.env_properties = data.get("env_properties", {})

        # --- Store initial item/npc references ---
        room.initial_item_refs = data.get("initial_items", [])
        room.initial_npc_refs = data.get("initial_npcs", [])

        # --- Initialize live items list as empty ---
        # This will be populated by World.load_save_game or World.initialize_new_world
        room.items = []

        # Update properties dict (redundant if super() handles it, but safe)
        room.update_property("exits", room.exits)
        room.update_property("visited", room.visited)
        room.update_property("time_descriptions", room.time_descriptions)
        room.update_property("env_properties", room.env_properties)

        return room
