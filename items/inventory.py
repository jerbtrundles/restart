"""
items/inventory.py
Inventory system for the MUD game.
Handles storage and management of items.
"""
from typing import Dict, List, Optional, Tuple, Any
from items.item import Item, ItemFactory


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
        if self.item.item_id == item.item_id and self.item.stackable:
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
                if slot.item and slot.item.item_id == item.item_id:
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
    
    def remove_item(self, item_id: str, quantity: int = 1) -> Tuple[Optional[Item], int, str]:
        """
        Remove an item from the inventory.
        
        Args:
            item_id: The ID of the item to remove.
            quantity: The quantity to remove.
            
        Returns:
            A tuple of (item, quantity_removed, message).
        """
        # First, count how many of this item we have
        total_available = sum(slot.quantity for slot in self.slots 
                             if slot.item and slot.item.item_id == item_id)
        
        if total_available == 0:
            return None, 0, f"You don't have that item."
        
        if total_available < quantity:
            return None, 0, f"You don't have {quantity} of that item."
        
        # Remove the items
        remaining = quantity
        removed_item = None
        
        for slot in self.slots:
            if slot.item and slot.item.item_id == item_id and remaining > 0:
                item, removed = slot.remove(remaining)
                if not removed_item and item:
                    removed_item = item
                remaining -= removed
                
                if remaining <= 0:
                    break
        
        return removed_item, quantity, f"Removed {quantity} {removed_item.name if removed_item else 'unknown item'} from inventory."
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """
        Get an item from the inventory without removing it.
        
        Args:
            item_id: The ID of the item to get.
            
        Returns:
            The item, or None if not found.
        """
        for slot in self.slots:
            if slot.item and slot.item.item_id == item_id:
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
            return "Your inventory is empty."
        
        result = []
        for i, slot in enumerate(self.slots):
            if slot.item:
                if slot.quantity > 1:
                    result.append(f"[{i+1}] {slot.item.name} (x{slot.quantity}) - {slot.quantity * slot.item.weight:.1f} weight")
                else:
                    result.append(f"[{i+1}] {slot.item.name} - {slot.item.weight:.1f} weight")
        
        total_weight = self.get_total_weight()
        result.append(f"\nTotal weight: {total_weight:.1f}/{self.max_weight:.1f}")
        result.append(f"Slots used: {self.max_slots - self.get_empty_slots()}/{self.max_slots}")
        
        return "\n".join(result)
    
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