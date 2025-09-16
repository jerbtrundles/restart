# items/container.py

from typing import TYPE_CHECKING, Any, Dict, Optional, List, Tuple
from config import FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS
from items.item import Item
# --- FIX: Removed circular import from the top of the file ---
# from items.key import Key
from utils.utils import _serialize_item_reference

if TYPE_CHECKING:
    from world.world import World
    from items.item_factory import ItemFactory
    from items.key import Key # Keep for type checking only

class Container(Item):
     """A container that can hold other items."""
     def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Container",
                    description: str = "No description", weight: float = 2.0,
                    value: int = 20, capacity: float = 50.0, locked: bool = False,
                    key_id: Optional[str] = None, is_open: bool = False,
                    **kwargs):
          super().__init__(obj_id, name, description, weight, value, stackable=False, **kwargs)
          self.properties["capacity"] = capacity
          self.properties.setdefault("contains", [])
          self.properties["locked"] = locked
          self.properties["key_id"] = key_id
          self.properties["is_open"] = is_open

     def get_current_weight(self) -> float:
          """Calculate the current weight of items inside."""
          return sum(item.weight * getattr(item, 'quantity', 1) for item in self.properties.get("contains", []))

     def examine(self) -> str:
          """Get a detailed description of the container."""
          base_desc = super().examine()
          lock_status = f"[{FORMAT_ERROR}Locked{FORMAT_RESET}]" if self.properties["locked"] else f"[{FORMAT_SUCCESS}Unlocked{FORMAT_RESET}]"
          open_status = f"({FORMAT_HIGHLIGHT}Open{FORMAT_RESET})" if self.properties["is_open"] else "(Closed)"

          contents_desc = self.list_contents() if self.properties["is_open"] else "It's closed."
          if self.properties["locked"]:
               contents_desc = "It's locked."

          current_weight = self.get_current_weight()
          capacity = self.properties.get('capacity', 0)

          desc = f"{base_desc}\n\nStatus: {lock_status} {open_status}\nCapacity: {current_weight:.1f} / {capacity:.1f} weight units."
          if not self.properties["locked"] and self.properties["is_open"]:
               desc += f"\n\n{FORMAT_CATEGORY}Contents:{FORMAT_RESET}\n{contents_desc}"

          return desc

     def list_contents(self) -> str:
          """Return a string listing the contents of the container."""
          contained_items: List[Item] = self.properties.get("contains", [])
          if not contained_items:
               return "  (Empty)"

          grouped: Dict[str, Dict[str, Any]] = {}
          for item in contained_items:
               if item.stackable:
                    if item.obj_id not in grouped:
                         grouped[item.obj_id] = {'item': item, 'count': 0}
                    grouped[item.obj_id]['count'] += 1
               else:
                    grouped[f"{item.obj_id}_{id(item)}"] = {'item': item, 'count': 1}

          content_lines = []
          for group in grouped.values():
               item = group['item']
               count = group['count']
               if count > 1:
                    content_lines.append(f"  - {item.name} (x{count})")
               else:
                    content_lines.append(f"  - {item.name}")

          return "\n".join(content_lines)

     def open(self) -> str:
          """Open the container."""
          if self.properties["locked"]:
               return f"The {self.name} is locked."
          if self.properties["is_open"]:
               return f"The {self.name} is already open."
          self.properties["is_open"] = True
          contents_desc = self.list_contents()
          return f"You open the {self.name}.\n\n{FORMAT_CATEGORY}Contents:{FORMAT_RESET}\n{contents_desc}"

     def close(self) -> str:
          """Close the container."""
          if not self.properties["is_open"]:
               return f"The {self.name} is already closed."
          self.properties["is_open"] = False
          return f"You close the {self.name}."

     def toggle_lock(self, key_item: Optional['Key']) -> bool:
          """Toggles the lock state if the correct key is provided."""
          # --- FIX: Import Key locally, only when this method is called ---
          from items.key import Key

          if not key_item or not isinstance(key_item, Key):
               return False

          correct_key = False
          container_key_id = self.properties.get("key_id")
          key_target_id = key_item.properties.get("target_id")

          if container_key_id and container_key_id == key_item.obj_id:
               correct_key = True
          elif key_target_id and key_target_id == self.obj_id:
               correct_key = True
          elif not container_key_id and not key_target_id and key_item.name in self.name:
               correct_key = True

          if correct_key:
               self.properties["locked"] = not self.properties["locked"]
               if self.properties["locked"]:
                    self.properties["is_open"] = False
               return True
          else:
               return False

     def can_add(self, item: Item) -> Tuple[bool, str]:
          """Check if an item can be added."""
          if not self.properties.get("is_open", False):
               return False, f"The {self.name} is closed."
          current_weight = self.get_current_weight()
          capacity = self.properties.get("capacity", 0)
          if current_weight + item.weight > capacity:
               return False, f"The {self.name} is too full to hold the {item.name}."
          return True, ""

     def add_item(self, item: Item) -> bool:
          """Add an item to the container."""
          can_add, _ = self.can_add(item)
          if not can_add:
               return False
          self.properties.setdefault("contains", []).append(item)
          return True

     def find_item_by_name(self, item_name: str) -> Optional[Item]:
          """Find an item inside the container by name."""
          item_name_lower = item_name.lower()
          contained_items: List[Item] = self.properties.get("contains", [])
          for item in contained_items:
               if item_name_lower in item.name.lower():
                    return item
          return None

     def remove_item(self, item_to_remove: Item) -> bool:
          """Remove a specific item instance from the container."""
          contained_items: List[Item] = self.properties.get("contains", [])
          if not self.properties.get("is_open", False):
               return False

          try:
               contained_items.remove(item_to_remove)
               return True
          except ValueError:
               for i, item in enumerate(contained_items):
                    if item.obj_id == item_to_remove.obj_id:
                         contained_items.pop(i)
                         return True
          return False

     def to_dict(self, world: 'World') -> Dict[str, Any]:
          data = super().to_dict()

          contained_item_refs = []
          contained_items: List[Item] = self.properties.get("contains", [])
          for item in contained_items:
               item_ref = _serialize_item_reference(item, 1, world)
               if item_ref:
                    contained_item_refs.append(item_ref)

          if "properties" not in data: data["properties"] = {}
          data["properties"]["contains"] = contained_item_refs
          data["properties"]["locked"] = self.properties.get("locked", False)
          data["properties"]["is_open"] = self.properties.get("is_open", False)
          return data

     @classmethod
     def from_dict(cls, data: Dict[str, Any], world: Optional['World'] = None) -> Optional['Container']:
        if not world:
            print(f"{FORMAT_ERROR}Error: World context needed to load container '{data.get('name', 'Unknown')}'.{FORMAT_RESET}")
            return None

        container = super(Container, cls).from_dict(data)
        if not isinstance(container, Container):
            temp_container = cls(obj_id=data.get("obj_id"), name=data.get("name", "Unknown"))
            temp_container.properties = container.properties
            container = temp_container

        loaded_items: List[Item] = []
        if "properties" in data and "contains" in data["properties"]:
            items_data = data["properties"]["contains"]
            from items.item_factory import ItemFactory
            if isinstance(items_data, list):
                for item_ref in items_data:
                    if item_ref and isinstance(item_ref, dict) and "item_id" in item_ref:
                        item_id = item_ref["item_id"]
                        overrides = item_ref.get("properties_override", {})
                        item = ItemFactory.create_item_from_template(item_id, world, **overrides)
                        if item:
                            loaded_items.append(item)
                        else:
                            print(f"Warning: Failed to load contained item '{item_id}' inside container '{container.name}'.")
            else:
                print(f"Warning: 'contains' property for container '{container.name}' is not a list: {items_data}")

        container.properties["contains"] = loaded_items
        container.properties.setdefault("capacity", 50.0)
        container.properties.setdefault("locked", False)
        container.properties.setdefault("key_id", None)
        container.properties.setdefault("is_open", False)

        return container