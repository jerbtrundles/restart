"""
items/inventory.py
Enhanced inventory system for the MUD game with improved text formatting.
Handles storage and management of items.
"""
from typing import Dict, List, Optional, Tuple, Any
from core.config import FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET
from items.item import Item
from items.item_factory import ItemFactory

class InventorySlot:
    """Represents a slot in an inventory that can hold items."""

    def __init__(self, item: Optional[Item] = None, quantity: int = 1):
        self.item = item
        # Ensure quantity matches stackability
        if item and not item.stackable:
             self.quantity = 1
        else:
             self.quantity = quantity if item else 0 # Quantity is 0 if no item

    def add(self, item: Item, quantity: int = 1) -> int:
        """Adds quantity to existing item or sets new item."""
        if not self.item:
            self.item = item
            self.quantity = quantity if item.stackable else 1
            return quantity # Added all requested (up to stack limit implicitly 1 if not stackable)

        if self.item.obj_id == item.obj_id and self.item.stackable:
            # No stack limit enforced here, assume inventory checks capacity
            self.quantity += quantity
            return quantity

        return 0 # Could not add to this slot

    def remove(self, quantity: int = 1) -> Tuple[Optional[Item], int]:
        """Removes quantity, clears slot if quantity becomes zero."""
        if not self.item: return None, 0

        quantity_to_remove = min(self.quantity, quantity)
        removed_item = self.item # Keep reference to the item type

        self.quantity -= quantity_to_remove

        if self.quantity <= 0:
            self.item = None # Clear the slot fully
            self.quantity = 0

        return removed_item, quantity_to_remove # Return item type and amount removed

    def to_dict(self) -> Dict[str, Any]:
        return {"item": self.item.to_dict() if self.item else None, "quantity": self.quantity}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InventorySlot':
        item = ItemFactory.from_dict(data["item"]) if data.get("item") else None
        return cls(item, data.get("quantity", 1 if item else 0))


class Inventory:
    """Manages a collection of items in inventory slots."""

    def __init__(self, max_slots: int = 20, max_weight: float = 100.0):
        self.slots: List[InventorySlot] = [InventorySlot() for _ in range(max_slots)]
        self.max_slots = max_slots
        self.max_weight = max_weight

    # --- NEW: Helper to check if an item can be added ---
    def can_add_item(self, item: Item, quantity: int = 1) -> Tuple[bool, str]:
         """Check weight and slot constraints before adding."""
         current_weight = self.get_total_weight()
         added_weight = item.weight * quantity
         if current_weight + added_weight > self.max_weight:
             return False, f"Adding {item.name} would exceed your carry weight ({self.max_weight:.1f})."

         # Check slots needed
         slots_needed = 0
         remaining_quantity = quantity
         temp_slots_used = [False] * self.max_slots

         # Check existing stacks
         if item.stackable:
              for i, slot in enumerate(self.slots):
                   if slot.item and slot.item.obj_id == item.obj_id:
                        # This slot can take more, doesn't count as a *new* slot needed
                        temp_slots_used[i] = True # Mark as potentially used
                        remaining_quantity = 0 # Assume stack can hold it (no max stack size yet)
                        break # Found a stack

         # Check empty slots needed for remaining quantity
         if remaining_quantity > 0:
             if not item.stackable:
                  slots_needed = remaining_quantity # Need one slot per non-stackable item
             else:
                  slots_needed = 1 # Need one new slot for the stack

             empty_slots_available = 0
             for i, slot in enumerate(self.slots):
                  if not slot.item and not temp_slots_used[i]:
                       empty_slots_available += 1

             if empty_slots_available < slots_needed:
                  return False, f"You don't have enough empty inventory slots for {item.name}."

         return True, ""
    # --- END NEW ---


    def add_item(self, item: Item, quantity: int = 1) -> Tuple[bool, str]:
        """
        Add an item to the inventory after checking constraints.
        """
        can_add, message = self.can_add_item(item, quantity)
        if not can_add:
             return False, message

        # Add to existing stacks first
        if item.stackable:
            for slot in self.slots:
                if slot.item and slot.item.obj_id == item.obj_id:
                    added = slot.add(item, quantity) # add returns quantity added
                    quantity -= added
                    if quantity <= 0:
                        return True, f"Added {item.name} to inventory." # Use generic message

        # Add remaining to empty slots
        while quantity > 0:
            empty_slot = next((slot for slot in self.slots if not slot.item), None)
            if not empty_slot:
                 # This case should be caught by can_add_item, but safety check
                 return False, f"Not enough space for the remaining {quantity} {item.name}."

            to_add_this_slot = 1 if not item.stackable else quantity
            empty_slot.add(item, to_add_this_slot)
            quantity -= to_add_this_slot

        return True, f"Added {item.name} to inventory." # Use generic message


    def remove_item(self, obj_id: str, quantity: int = 1) -> Tuple[Optional[Item], int, str]:
        """
        Remove an item from the inventory by obj_id.
        """
        total_available = sum(slot.quantity for slot in self.slots
                             if slot.item and slot.item.obj_id == obj_id)

        if total_available == 0:
            return None, 0, "You don't have that item."

        quantity_to_remove = min(total_available, quantity)
        actual_removed_count = 0
        removed_item_type = None # To store the type of item removed

        # Iterate backwards to handle removing from multiple slots correctly
        for slot in reversed(self.slots):
            if slot.item and slot.item.obj_id == obj_id:
                 if actual_removed_count < quantity_to_remove:
                      needed = quantity_to_remove - actual_removed_count
                      item_ref, removed_from_slot = slot.remove(needed)
                      if item_ref and not removed_item_type:
                           removed_item_type = item_ref # Get the item type
                      actual_removed_count += removed_from_slot

            if actual_removed_count >= quantity_to_remove:
                 break

        if removed_item_type:
             # Return a *copy* or the reference depending on desired behavior.
             # Returning the type allows creating a new instance if needed.
             # For dropping, returning the type might be enough.
             # If putting in container, maybe pass the actual instance? Let's return type for now.
             return removed_item_type, actual_removed_count, f"Removed {actual_removed_count} {removed_item_type.name}."
        else:
             # Should not happen if total_available > 0
             return None, 0, "Error removing item."


    def get_item(self, obj_id: str) -> Optional[Item]:
        """Get an item reference by obj_id without removing."""
        for slot in self.slots:
            if slot.item and slot.item.obj_id == obj_id:
                return slot.item
        return None

    def get_total_weight(self) -> float:
        """Calculate total weight."""
        return sum(slot.item.weight * slot.quantity for slot in self.slots if slot.item)

    def get_empty_slots(self) -> int:
        """Count empty slots."""
        return sum(1 for slot in self.slots if not slot.item)

    def list_items(self) -> str:
        """Get a formatted list of items."""
        from utils.text_formatter import TextFormatter

        if all(not slot.item for slot in self.slots):
            return f"{FORMAT_CATEGORY}Your inventory is empty.{FORMAT_RESET}"

        result = []
        items_found = False
        for i, slot in enumerate(self.slots):
            if slot.item:
                items_found = True
                # Use obj_id for potentially more unique lookup if needed later
                # item_ref = f"({slot.item.obj_id})" # Optional: Show obj_id
                if slot.item.stackable and slot.quantity > 1:
                    item_text = f"- {FORMAT_HIGHLIGHT}{slot.item.name}{FORMAT_RESET} (x{slot.quantity})"
                else:
                    item_text = f"- {FORMAT_HIGHLIGHT}{slot.item.name}{FORMAT_RESET}"
                # Add weight info per item/stack
                item_text += f" [{slot.item.weight * slot.quantity:.1f} wt]"
                result.append(item_text)

        if not items_found: return f"{FORMAT_CATEGORY}Your inventory is empty.{FORMAT_RESET}"

        # Weight and Slot info (with color coding)
        total_weight = self.get_total_weight()
        weight_percent = (total_weight / self.max_weight) * 100 if self.max_weight > 0 else 0
        if weight_percent >= 90: weight_text = f"{FORMAT_ERROR}{total_weight:.1f}/{self.max_weight:.1f}{FORMAT_RESET}"
        elif weight_percent >= 75: weight_text = f"{FORMAT_HIGHLIGHT}{total_weight:.1f}/{self.max_weight:.1f}{FORMAT_RESET}"
        else: weight_text = f"{total_weight:.1f}/{self.max_weight:.1f}"
        weight_info = f"{FORMAT_CATEGORY}Total weight:{FORMAT_RESET} {weight_text}"

        used_slots = self.max_slots - self.get_empty_slots()
        slot_percent = (used_slots / self.max_slots) * 100 if self.max_slots > 0 else 0
        if slot_percent >= 90: slot_text = f"{FORMAT_ERROR}{used_slots}/{self.max_slots}{FORMAT_RESET}"
        elif slot_percent >= 75: slot_text = f"{FORMAT_HIGHLIGHT}{used_slots}/{self.max_slots}{FORMAT_RESET}"
        else: slot_text = f"{used_slots}/{self.max_slots}"
        slot_info = f"{FORMAT_CATEGORY}Slots used:{FORMAT_RESET} {slot_text}"

        return "\n".join(result) + f"\n\n{weight_info}\n{slot_info}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_slots": self.max_slots,
            "max_weight": self.max_weight,
            "slots": [slot.to_dict() for slot in self.slots]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Inventory':
        inventory = cls(max_slots=data.get("max_slots", 20), max_weight=data.get("max_weight", 100.0))
        loaded_slots_data = data.get("slots", [])
        inventory.slots = [] # Clear default slots

        for slot_data in loaded_slots_data:
             inventory.slots.append(InventorySlot.from_dict(slot_data))

        # Ensure correct number of slots
        while len(inventory.slots) < inventory.max_slots:
            inventory.slots.append(InventorySlot())
        # Truncate if save file had more slots than current max_slots
        inventory.slots = inventory.slots[:inventory.max_slots]

        return inventory

    def find_item_by_name(self, name: str, partial: bool = True, exclude: Optional[Item] = None) -> Optional[Item]:
        """Find the first matching item by name."""
        name_lower = name.lower()
        for slot in self.slots:
            if slot.item:
                # Skip excluded item
                if exclude and slot.item is exclude:
                     continue

                match = False
                if partial and name_lower in slot.item.name.lower():
                    match = True
                elif not partial and name_lower == slot.item.name.lower():
                    match = True
                # Allow matching by obj_id as well
                elif name_lower == slot.item.obj_id:
                     match = True

                if match:
                    return slot.item # Return the actual item instance
        return None

    # sort_items method remains useful
    def sort_items(self) -> None:
        item_slots = [slot for slot in self.slots if slot.item]
        empty_slots = [slot for slot in self.slots if not slot.item]
        item_slots.sort(key=lambda slot: (type(slot.item).__name__, slot.item.name))
        self.slots = item_slots + empty_slots
