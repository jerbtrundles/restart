"""
plugins/event_system.py
Event system for the MUD game.
Provides a centralized way for plugins and game components to communicate.
"""
from typing import Dict, List, Any, Callable, Set


class EventSystem:
    """
    Centralized event system for game-wide communication.
    
    This allows components to communicate without direct dependencies.
    Components can publish events and subscribe to events from other components.
    """
    
    def __init__(self):
        """Initialize the event system."""
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: Dict[str, Any] = {}  # Last value for each event type
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: The type of event to subscribe to.
            callback: The function to call when the event occurs.
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: The type of event to unsubscribe from.
            callback: The callback to remove.
        """
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            
            # Clean up empty event types
            if not self.subscribers[event_type]:
                self.subscribers.pop(event_type)
    
    def publish(self, event_type: str, data: Any = None) -> None:
        """
        Publish an event.
        
        Args:
            event_type: The type of event to publish.
            data: The event data.
        """
        # Store the event in history
        self.event_history[event_type] = data
        
        # Notify subscribers
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(event_type, data)
                except Exception as e:
                    print(f"Error in event callback for {event_type}: {e}")
    
    def get_last_event_data(self, event_type: str, default: Any = None) -> Any:
        """
        Get the data from the last occurrence of an event type.
        
        Args:
            event_type: The event type to get data for.
            default: Default value if no event of this type has occurred.
            
        Returns:
            The event data, or default if no such event has occurred.
        """
        return self.event_history.get(event_type, default)
    
    def clear_history(self, event_types: Set[str] = None) -> None:
        """
        Clear event history.
        
        Args:
            event_types: Set of event types to clear. If None, clear all.
        """
        if event_types is None:
            self.event_history.clear()
        else:
            for event_type in event_types:
                if event_type in self.event_history:
                    self.event_history.pop(event_type)