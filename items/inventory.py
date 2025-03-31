"""
items/inventory.py
Enhanced inventory system for the MUD game with improved text formatting.
Handles storage and management of items.
"""
from typing import Dict, List, Optional, Tuple, Any
from items.item import Item
from items.item_factory import ItemFactory
from utils.text_formatter import TextFormatter


class InventorySlot:
    """Represents a slot in an inventory that can hold items."""
    
    def __init__(self, item: Optional[Item] = None, quantity: int = 1):
        """
        Initialize an inventory slot.
        
        Args:
            item: The item in this slot, or None for an empty slot.
            quantity: The quantity of the item.
        """
        self.item = item
        self.quantity = quantity if item and item.stackable else 1
    
    def add(self, item: Item, quantity: int = 1) -> int:
        """
        Add an item to this slot.
        
        Args:
            item: The item to add.
            quantity: The quantity to add.
            
        Returns:
            The quantity that was added (may be less than requested if the slot is full).
        """
        # If slot is empty, can add any item
        if not self.item:
            self.item = item
            self.quantity = quantity if item.stackable else 1
            return quantity
        
        # If slot has same item and is stackable, can add more
        if self.item.obj_id == item.obj_id and self.item.stackable:
            self.quantity += quantity
            return quantity
            
        # Otherwise, can't add to this slot
        return 0
    
    def remove(self, quantity: int = 1) -> Tuple[Optional[Item], int]:
        """
        Remove items from this slot.
        
        Args:
            quantity: The quantity to remove.
            
        Returns:
            A tuple of (item, quantity_removed).
        """
        if not self.item:
            return None, 0
            
        quantity_to_remove = min(self.quantity, quantity)
        item = self.item
        
        # If removing all, clear the slot
        if quantity_to_remove >= self.quantity:
            self.item = None
            self.quantity = 0
            return item, quantity_to_remove
            
        # Otherwise, just reduce the quantity
        self.quantity -= quantity_to_remove
        return item, quantity_to_remove
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the slot to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the slot.
        """
        return {
            "item": self.item.to_dict() if self.item else None,
            "quantity": self.quantity
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InventorySlot':
        """
        Create a slot from a dictionary.
        
        Args:
            data: Dictionary data to convert.
            
        Returns:
            An InventorySlot instance.
        """
        item = ItemFactory.from_dict(data["item"]) if data.get("item") else None
        return cls(item, data.get("quantity", 1))


class Inventory:
    """Manages a collection of items in inventory slots."""
    
    def __init__(self, max_slots: int = 20, max_weight: float = 100.0):
        """
        Initialize an inventory.
        
        Args:
            max_slots: The maximum number of slots in the inventory.
            max_weight: The maximum weight the inventory can hold.
        """
        self.slots: List[InventorySlot] = [InventorySlot() for _ in range(max_slots)]
        self.max_slots = max_slots
        self.max_weight = max_weight
    
    def add_item(self, item: Item, quantity: int = 1) -> Tuple[bool, str]:
        """
        Add an item to the inventory.
        
        Args:
            item: The item to add.
            quantity: The quantity to add.
            
        Returns:
            A tuple of (success, message).
        """
        # Check weight constraints
        current_weight = self.get_total_weight()
        added_weight = item.weight * quantity
        
        if current_weight + added_weight > self.max_weight:
            return False, f"The {item.name} is too heavy to carry."
        
        # First, try to add to existing stacks
        if item.stackable:
            for slot in self.slots:
                if slot.item and slot.item.obj_id == item.obj_id:
                    added = slot.add(item, quantity)
                    quantity -= added
                    if quantity <= 0:
                        return True, f"Added {item.name} to inventory."
        
        # Then, try to add to empty slots
        remaining = quantity
        while remaining > 0:
            # Find an empty slot
            empty_slot = next((slot for slot in self.slots if not slot.item), None)
            
            if not empty_slot:
                if quantity > 1:
                    return False, f"Not enough space for {remaining} {item.name}."
                else:
                    return False, f"Not enough space for {item.name}."
            
            # Add to the empty slot
            to_add = 1 if not item.stackable else remaining
            empty_slot.add(item, to_add)
            remaining -= to_add
        
        return True, f"Added {item.name} to inventory."
    
    def remove_item(self, obj_id: str, quantity: int = 1) -> Tuple[Optional[Item], int, str]:
        """
        Remove an item from the inventory.
        
        Args:
            obj_id: The ID of the item to remove.
            quantity: The quantity to remove.
            
        Returns:
            A tuple of (item, quantity_removed, message).
        """
        # First, count how many of this item we have
        total_available = sum(slot.quantity for slot in self.slots 
                             if slot.item and slot.item.obj_id == obj_id)
        
        if total_available == 0:
            return None, 0, f"You don't have that item."
        
        if total_available < quantity:
            return None, 0, f"You don't have {quantity} of that item."
        
        # Remove the items
        remaining = quantity
        removed_item = None
        
        for slot in self.slots:
            if slot.item and slot.item.obj_id == obj_id and remaining > 0:
                item, removed = slot.remove(remaining)
                if not removed_item and item:
                    removed_item = item
                remaining -= removed
                
                if remaining <= 0:
                    break
        
        return removed_item, quantity, f"Removed {quantity} {removed_item.name if removed_item else 'unknown item'} from inventory."
    
    def get_item(self, obj_id: str) -> Optional[Item]:
        """
        Get an item from the inventory without removing it.
        
        Args:
            obj_id: The ID of the item to get.
            
        Returns:
            The item, or None if not found.
        """
        for slot in self.slots:
            if slot.item and slot.item.obj_id == obj_id:
                return slot.item
        return None
    
    def get_total_weight(self) -> float:
        """
        Calculate the total weight of all items in the inventory.
        
        Returns:
            The total weight.
        """
        return sum(slot.item.weight * slot.quantity for slot in self.slots if slot.item)
    
    def get_empty_slots(self) -> int:
        """
        Calculate the number of empty slots in the inventory.
        
        Returns:
            The number of empty slots.
        """
        return sum(1 for slot in self.slots if not slot.item)
    
    def list_items(self) -> str:
        """
        Get a formatted list of all items in the inventory.
        
        Returns:
            A string listing the inventory contents.
        """
        if all(not slot.item for slot in self.slots):
            return f"{TextFormatter.FORMAT_CATEGORY}Your inventory is empty.{TextFormatter.FORMAT_RESET}"
        
        result = []
        for i, slot in enumerate(self.slots):
            if slot.item:
                if slot.quantity > 1:
                    item_text = f"[{i+1}] {TextFormatter.FORMAT_HIGHLIGHT}{slot.item.name}{TextFormatter.FORMAT_RESET} (x{slot.quantity}) - {slot.quantity * slot.item.weight:.1f} weight"
                else:
                    item_text = f"[{i+1}] {TextFormatter.FORMAT_HIGHLIGHT}{slot.item.name}{TextFormatter.FORMAT_RESET} - {slot.item.weight:.1f} weight"
                result.append(item_text)
        
        # Weight information
        total_weight = self.get_total_weight()
        weight_percent = (total_weight / self.max_weight) * 100
        
        # Color-code weight based on percentage of capacity
        if weight_percent >= 90:
            weight_text = f"{TextFormatter.FORMAT_ERROR}{total_weight:.1f}/{self.max_weight:.1f}{TextFormatter.FORMAT_RESET}"
        elif weight_percent >= 75:
            weight_text = f"{TextFormatter.FORMAT_HIGHLIGHT}{total_weight:.1f}/{self.max_weight:.1f}{TextFormatter.FORMAT_RESET}"
        else:
            weight_text = f"{total_weight:.1f}/{self.max_weight:.1f}"
            
        weight_info = f"{TextFormatter.FORMAT_CATEGORY}Total weight:{TextFormatter.FORMAT_RESET} {weight_text}"
        
        # Slot information
        used_slots = self.max_slots - self.get_empty_slots()
        slot_percent = (used_slots / self.max_slots) * 100
        
        # Color-code slots based on percentage of capacity
        if slot_percent >= 90:
            slot_text = f"{TextFormatter.FORMAT_ERROR}{used_slots}/{self.max_slots}{TextFormatter.FORMAT_RESET}"
        elif slot_percent >= 75:
            slot_text = f"{TextFormatter.FORMAT_HIGHLIGHT}{used_slots}/{self.max_slots}{TextFormatter.FORMAT_RESET}"
        else:
            slot_text = f"{used_slots}/{self.max_slots}"
            
        slot_info = f"{TextFormatter.FORMAT_CATEGORY}Slots used:{TextFormatter.FORMAT_RESET} {slot_text}"
        
        # Combine everything
        return "\n".join(result) + f"\n\n{weight_info}\n{slot_info}"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the inventory to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the inventory.
        """
        return {
            "max_slots": self.max_slots,
            "max_weight": self.max_weight,
            "slots": [slot.to_dict() for slot in self.slots]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Inventory':
        """
        Create an inventory from a dictionary.
        
        Args:
            data: Dictionary data to convert.
            
        Returns:
            An Inventory instance.
        """
        inventory = cls(
            max_slots=data.get("max_slots", 20),
            max_weight=data.get("max_weight", 100.0)
        )
        
        # Clear default slots and replace with loaded ones
        inventory.slots = [InventorySlot.from_dict(slot_data) 
                          for slot_data in data.get("slots", [])]
        
        # If we have fewer slots than max_slots, add empty ones
        while len(inventory.slots) < inventory.max_slots:
            inventory.slots.append(InventorySlot())
            
        return inventory

    def find_item_by_name(self, name: str, partial: bool = True) -> Optional[Item]:
        """
        Find an item in the inventory by name.
        
        Args:
            name: The name or partial name to search for
            partial: Whether to allow partial name matches
            
        Returns:
            The first matching item, or None if not found
        """
        name_lower = name.lower()
        
        for slot in self.slots:
            if slot.item:
                if partial and name_lower in slot.item.name.lower():
                    return slot.item
                elif not partial and name_lower == slot.item.name.lower():
                    return slot.item
                    
        return None
        
    def sort_items(self) -> None:
        """
        Sort inventory items for better organization.
        Puts items of the same type together and moves empty slots to the end.
        """
        # Group items by type
        item_slots = [slot for slot in self.slots if slot.item]
        empty_slots = [slot for slot in self.slots if not slot.item]
        
        # Sort item slots by item type and name
        item_slots.sort(key=lambda slot: (
            type(slot.item).__name__,
            slot.item.name
        ))
        
        # Reconstruct the slots list
        self.slots = item_slots + empty_slots