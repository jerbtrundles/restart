"""
plugins/world_data_provider.py
Provides a standardized interface for accessing world data.
"""
from typing import Dict, Any, Optional, List, Tuple


class WorldDataProvider:
    """
    Provides a standardized way to access world data for plugins.
    
    This reduces direct coupling between plugins and the world model.
    """
    
    def __init__(self, world=None, event_system=None):
        """
        Initialize the world data provider.
        
        Args:
            world: The game world object.
            event_system: The event system for communication.
        """
        self.world = world
        self.event_system = event_system
        
        # Cache for frequently accessed data
        self._cache = {}
        
        # Register for events that would invalidate cache
        if event_system:
            event_system.subscribe("room_changed", self._invalidate_location_cache)
    
    def get_current_location(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the player's current location.
        
        Returns:
            A tuple of (region_id, room_id).
        """
        if not self.world:
            return None, None
        
        return self.world.current_region_id, self.world.current_room_id
    
    def get_current_room_properties(self) -> Dict[str, Any]:
        """
        Get properties of the current room.
        
        Returns:
            A dictionary of room properties.
        """
        if not self.world:
            return {}
        
        room = self.world.get_current_room()
        if not room:
            return {}
        
        return getattr(room, "properties", {})
    
    def is_outdoors_or_has_windows(self) -> bool:
        """
        Check if the current room is outdoors or has windows.
        
        Returns:
            True if outdoors or has windows, False otherwise.
        """
        properties = self.get_current_room_properties()
        return properties.get("outdoors", False) or properties.get("has_windows", False)
    
    def get_npcs_in_current_room(self) -> List[Dict[str, Any]]:
        """
        Get NPCs in the current room.
        
        Returns:
            A list of NPC data dictionaries.
        """
        if not self.world:
            return []
        
        npcs = self.world.get_current_room_npcs()
        return [self._npc_to_dict(npc) for npc in npcs]
    
    def get_items_in_current_room(self) -> List[Dict[str, Any]]:
        """
        Get items in the current room.
        
        Returns:
            A list of item data dictionaries.
        """
        if not self.world:
            return []
        
        items = self.world.get_items_in_current_room()
        return [self._item_to_dict(item) for item in items]
    
    def get_npc_by_id(self, npc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get NPC data by ID.
        
        Args:
            npc_id: The ID of the NPC.
            
        Returns:
            NPC data dictionary, or None if not found.
        """
        if not self.world:
            return None
            
        npc = self.world.get_npc(npc_id)
        if not npc:
            return None
            
        return self._npc_to_dict(npc)
    
    def get_all_npcs(self) -> List[Dict[str, Any]]:
        """
        Get all NPCs in the world.
        
        Returns:
            A list of NPC data dictionaries.
        """
        if not self.world or not hasattr(self.world, "npcs"):
            return []
            
        return [self._npc_to_dict(npc) for npc in self.world.npcs.values()]
    
    def _npc_to_dict(self, npc) -> Dict[str, Any]:
        """
        Convert an NPC object to a dictionary.
        
        Args:
            npc: The NPC object.
            
        Returns:
            A dictionary representation of the NPC.
        """
        return {
            "id": npc.npc_id,
            "name": npc.name,
            "description": npc.description,
            "region_id": npc.current_region_id,
            "room_id": npc.current_room_id,
            "friendly": getattr(npc, "friendly", True),
            "ai_state": getattr(npc, "ai_state", {}),
            # Add other properties as needed
        }
    
    def _item_to_dict(self, item) -> Dict[str, Any]:
        """
        Convert an item object to a dictionary.
        
        Args:
            item: The item object.
            
        Returns:
            A dictionary representation of the item.
        """
        return {
            "id": item.item_id,
            "name": item.name,
            "description": item.description,
            "weight": getattr(item, "weight", 0),
            "value": getattr(item, "value", 0),
            "properties": getattr(item, "properties", {}),
            # Add other properties as needed
        }
    
    def _invalidate_location_cache(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Invalidate location-related cache when location changes.
        
        Args:
            event_type: The event type.
            data: The event data.
        """
        # Clear relevant cache entries
        for key in list(self._cache.keys()):
            if key.startswith("location_") or key.startswith("room_"):
                self._cache.pop(key)