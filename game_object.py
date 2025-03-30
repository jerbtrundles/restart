"""
game_object.py
Base class for all game objects with common functionality.
"""
from typing import Dict, Any, Optional
import uuid


class GameObject:
    def __init__(self, obj_id: str = None, name: str = "Unknown", 
                 description: str = "No description"):
        self.obj_id = obj_id if obj_id else f"{self.__class__.__name__.lower()}_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.properties: Dict[str, Any] = {}  # Additional properties for derived classes
    
    def get_description(self) -> str:
        return f"{self.name}\n\n{self.description}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "id": self.obj_id,
            "name": self.name,
            "description": self.description,
            "properties": self.properties
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GameObject':
        obj = cls(
            obj_id=data.get("id"),
            name=data.get("name", "Unknown"),
            description=data.get("description", "No description")
        )
        obj.properties = data.get("properties", {})
        return obj
    
    def update_property(self, key: str, value: Any) -> None:
        self.properties[key] = value
    
    def get_property(self, key: str, default: Any = None) -> Any:
        return self.properties.get(key, default)