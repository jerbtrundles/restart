"""
npcs/npc.py
NPC system for the MUD game.
Defines non-player characters and their behavior.
"""
from typing import Dict, List, Optional, Any, Tuple, Callable
import random
import time
from items.inventory import Inventory
from items.item import Item


class NPC:
    """Base class for all non-player characters."""
    
    def __init__(self, npc_id: str = None, name: str = "Unknown NPC", 
                 description: str = "No description", health: int = 100,
                 friendly: bool = True):
        """
        Initialize an NPC.
        
        Args:
            npc_id: Unique ID for the NPC.
            name: The display name of the NPC.
            description: A textual description of the NPC.
            health: The current health of the NPC.
            friendly: Whether the NPC is friendly to the player.
        """
        self.npc_id = npc_id if npc_id else f"npc_{random.randint(1000, 9999)}"
        self.name = name
        self.description = description
        self.health = health
        self.max_health = health
        self.friendly = friendly
        self.inventory = Inventory(max_slots=10, max_weight=50.0)
        
        # Movement and location data
        self.current_region_id = None
        self.current_room_id = None
        self.home_region_id = None
        self.home_room_id = None

        self.current_activity = None
        
        # Behavior data
        self.behavior_type = "stationary"  # 'stationary', 'wanderer', 'patrol', 'follower'
        self.patrol_points = []  # List of room IDs for patrol routes
        self.patrol_index = 0
        self.follow_target = None  # ID of entity to follow
        self.wander_chance = 0.3  # Chance to wander each update
        self.schedule = {}  # Time-based schedule of room IDs
        self.last_moved = 0  # Time of last movement
        self.move_cooldown = 10  # Seconds between movements
        
        # Interaction data
        self.dialog = {}  # Mapping of keywords to responses
        self.default_dialog = "The {name} doesn't respond."
        self.ai_state = {}  # Custom state for NPC behavior
    
    def get_description(self) -> str:
        """
        Get a description of the NPC.
        
        Returns:
            A formatted description.
        """
        health_percent = self.health / self.max_health * 100
        health_desc = ""
        
        if health_percent <= 25:
            health_desc = f"The {self.name} looks severely injured."
        elif health_percent <= 50:
            health_desc = f"The {self.name} appears to be wounded."
        elif health_percent <= 75:
            health_desc = f"The {self.name} has some minor injuries."
        else:
            health_desc = f"The {self.name} looks healthy."
        
        return f"{self.name}\n\n{self.description}\n\n{health_desc}"
        
    def talk(self, topic: str = None) -> str:
        """
        Get dialog from the NPC based on a topic.
        
        Args:
            topic: The topic to discuss, or None for default greeting.
            
        Returns:
            The NPC's response.
        """
        # Check if NPC is busy with an activity
        if hasattr(self, "ai_state"):
            # Check for activity-specific responses
            if self.ai_state.get("is_sleeping", False):
                # NPC is sleeping
                responses = self.ai_state.get("sleeping_responses", [])
                if responses:
                    import random
                    return random.choice(responses).format(name=self.name)
            
            elif self.ai_state.get("is_eating", False):
                # NPC is eating
                responses = self.ai_state.get("eating_responses", [])
                if responses:
                    import random
                    return random.choice(responses).format(name=self.name)
            
            elif self.ai_state.get("is_working", False) and topic != "work":
                # NPC is working but might respond to work-related topics
                responses = self.ai_state.get("working_responses", [])
                if responses:
                    import random
                    return random.choice(responses).format(name=self.name)
        
        # Normal dialog processing for NPCs not engaged in busy activities
        if not topic:
            # Default greeting
            if "greeting" in self.dialog:
                return self.dialog["greeting"].format(name=self.name)
            return f"The {self.name} greets you."
        
        # Look for the topic in the dialog dictionary
        topic = topic.lower()
        if topic in self.dialog:
            return self.dialog[topic].format(name=self.name)
        
        # Try partial matching
        for key in self.dialog:
            if topic in key:
                return self.dialog[key].format(name=self.name)
        
        # If NPC is engaged in an activity, reference it in default response
        if hasattr(self, "ai_state") and "current_activity" in self.ai_state:
            activity = self.ai_state["current_activity"]
            return f"The {self.name} continues {activity} and doesn't respond about that topic."
        
        # Default response
        return self.default_dialog.format(name=self.name)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the NPC to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the NPC.
        """
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "description": self.description,
            "health": self.health,
            "max_health": self.max_health,
            "friendly": self.friendly,
            "inventory": self.inventory.to_dict(),
            "current_region_id": self.current_region_id,
            "current_room_id": self.current_room_id,
            "home_region_id": self.home_region_id,
            "home_room_id": self.home_room_id,
            "behavior_type": self.behavior_type,
            "patrol_points": self.patrol_points,
            "patrol_index": self.patrol_index,
            "follow_target": self.follow_target,
            "wander_chance": self.wander_chance,
            "schedule": self.schedule,
            "move_cooldown": self.move_cooldown,
            "dialog": self.dialog,
            "default_dialog": self.default_dialog,
            "ai_state": self.ai_state
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPC':
        """
        Create an NPC from a dictionary.
        
        Args:
            data: Dictionary data to convert.
            
        Returns:
            An NPC instance.
        """
        npc = cls(
            npc_id=data.get("npc_id"),
            name=data.get("name", "Unknown NPC"),
            description=data.get("description", "No description"),
            health=data.get("health", 100),
            friendly=data.get("friendly", True)
        )
        
        # Set basic properties
        npc.max_health = data.get("max_health", 100)
        npc.current_region_id = data.get("current_region_id")
        npc.current_room_id = data.get("current_room_id")
        npc.home_region_id = data.get("home_region_id")
        npc.home_room_id = data.get("home_room_id")
        
        # Set behavior properties
        npc.behavior_type = data.get("behavior_type", "stationary")
        npc.patrol_points = data.get("patrol_points", [])
        npc.patrol_index = data.get("patrol_index", 0)
        npc.follow_target = data.get("follow_target")
        npc.wander_chance = data.get("wander_chance", 0.3)
        npc.schedule = data.get("schedule", {})
        npc.move_cooldown = data.get("move_cooldown", 10)
        
        # Set interaction properties
        npc.dialog = data.get("dialog", {})
        npc.default_dialog = data.get("default_dialog", "The {name} doesn't respond.")
        npc.ai_state = data.get("ai_state", {})
        
        # Set inventory if present
        if "inventory" in data:
            npc.inventory = Inventory.from_dict(data["inventory"])
            
        return npc
        
    def update(self, world, current_time: float) -> Optional[str]:
        """
        Update the NPC's state and perform actions.
        
        Args:
            world: The game world object.
            current_time: The current game time.
            
        Returns:
            An optional message if the NPC did something visible.
        """
        # Check if NPC is sleeping - no movement
        if hasattr(self, "ai_state") and self.ai_state.get("is_sleeping", False):
            return None
        
        # Check if NPC is eating or working - reduced movement
        if hasattr(self, "ai_state") and (self.ai_state.get("is_eating", False) or self.ai_state.get("is_working", False)):
            # Only move rarely
            import random
            if random.random() > 0.9:  # 10% chance to still move
                pass  # Continue to normal movement logic
            else:
                return None  # No movement most of the time
            
        # Check if it's time to move
        if current_time - self.last_moved < self.move_cooldown:
            return None
                
        # Update according to behavior type
        if self.behavior_type == "wanderer":
            message = self._wander_behavior(world, current_time)
            if message:
                # Only update the last_moved time if the NPC actually moved
                self.last_moved = current_time
            return message
        elif self.behavior_type == "patrol":
            message = self._patrol_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message
        elif self.behavior_type == "follower":
            message = self._follower_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message
        elif self.behavior_type == "scheduled":
            message = self._schedule_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message
                    
        # Default stationary behavior
        return None
            
    def _schedule_behavior(self, world, current_time: float) -> Optional[str]:
        """
        Implement schedule-based behavior.
        This improved version better coordinates with the NPC Schedule plugin.
        """
        if not self.schedule:
            return None
            
        # Convert the current time to hours (assuming current_time is in seconds)
        current_hour = int((current_time // 3600) % 24)
        
        # Check if there's a scheduled destination for this hour
        if current_hour in self.schedule:
            destination = self.schedule[current_hour]
            
            # If we're already there, do nothing related to movement
            # but still return possible activity message
            if destination == self.current_room_id:
                # Get current activity from ai_state if available
                if hasattr(self, "ai_state") and "current_activity" in self.ai_state:
                    activity = self.ai_state["current_activity"]
                    
                    # Only return a message if the player is in the same room
                    if (world.current_region_id == self.current_region_id and 
                        world.current_room_id == self.current_room_id):
                        
                        # Check if we've already notified about this activity
                        last_notified = self.ai_state.get("last_notified_activity")
                        if last_notified != f"{current_hour}_{activity}":
                            self.ai_state["last_notified_activity"] = f"{current_hour}_{activity}"
                            return f"{self.name} continues {activity}."
                
                return None
                
            # Handle region transitions in the destination
            old_region_id = self.current_region_id
            old_room_id = self.current_room_id
            
            # Parse destination
            if ":" in destination:
                new_region_id, new_room_id = destination.split(":")
                self.current_region_id = new_region_id
                self.current_room_id = new_room_id
            else:
                # Assume same region
                new_room_id = destination
                self.current_room_id = new_room_id
                new_region_id = self.current_region_id
                
            # Update last_moved time
            self.last_moved = current_time
            
            # Get current activity if available
            activity_msg = ""
            if hasattr(self, "ai_state") and "current_activity" in self.ai_state:
                activity = self.ai_state["current_activity"]
                activity_msg = f" to {activity}"
                
                # Update last notified activity
                self.ai_state["last_notified_activity"] = f"{current_hour}_{activity}"
            
            # Only return a message if the player is in either the old or new room
            if (world.current_region_id == old_region_id and 
                world.current_room_id == old_room_id):
                return f"{self.name} leaves{activity_msg}."
                
            if (world.current_region_id == self.current_region_id and 
                world.current_room_id == self.current_room_id):
                return f"{self.name} arrives{activity_msg}."
        
        return None
    
    def _reverse_direction(self, direction: str) -> str:
        """Get the opposite direction."""
        opposites = {
            "north": "south", "south": "north",
            "east": "west", "west": "east",
            "northeast": "southwest", "southwest": "northeast",
            "northwest": "southeast", "southeast": "northwest",
            "up": "down", "down": "up"
        }
        return opposites.get(direction, "somewhere")

    def _wander_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement wandering behavior."""
        # Only wander sometimes
        if random.random() > self.wander_chance:
            return None
            
        # Get current room and its exits
        region = world.get_region(self.current_region_id)
        if not region:
            return None
            
        room = region.get_room(self.current_room_id)
        if not room:
            return None
            
        exits = list(room.exits.keys())
        if not exits:
            return None
            
        # Choose a random exit and move through it
        direction = random.choice(exits)
        destination = room.exits[direction]
        
        # Save old location info
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        
        # Handle region transitions
        if ":" in destination:
            new_region_id, new_room_id = destination.split(":")
            
            # Update location
            self.current_region_id = new_region_id
            self.current_room_id = new_room_id
            
        else:
            # Same region, different room
            self.current_room_id = destination
        
        # Note: We no longer update self.last_moved here
        # It will be updated in the main update method
        
        # Check if the player is in the room to see the NPC leave
        if (world.current_region_id == old_region_id and 
            world.current_room_id == old_room_id):
            return f"{self.name} leaves to the {direction}."
            
        # Check if the player is in the destination room to see the NPC arrive
        if (world.current_region_id == self.current_region_id and 
            world.current_room_id == self.current_room_id):
            return f"{self.name} arrives from the {self._reverse_direction(direction)}."
        
        return None
    
    def _patrol_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement patrol behavior."""
        if not self.patrol_points:
            return None
            
        # Get next patrol point
        next_point = self.patrol_points[self.patrol_index]
        
        # If we're already there, move to the next point in the list
        if next_point == self.current_room_id:
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
            return None
            
        # Find a path to the next patrol point (simplified version)
        # In a real implementation, you'd want a proper pathfinding algorithm
        
        # Get current room
        region = world.get_region(self.current_region_id)
        if not region:
            return None
            
        room = region.get_room(self.current_room_id)
        if not room:
            return None
            
        # Look for a direct path first
        for direction, destination in room.exits.items():
            if destination == next_point:
                old_room_id = self.current_room_id
                self.current_room_id = destination
                
                # Check if the player is in the room to see the NPC leave
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == old_room_id):
                    message = f"{self.name} leaves to the {direction}."
                    return message
                    
                # Check if the player is in the destination room to see the NPC arrive
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == destination):
                    message = f"{self.name} arrives from the {self._reverse_direction(direction)}."
                    return message
                
                self.last_moved = current_time
                return None
        
        # If no direct path, just pick a random exit (this is a simplification)
        return self._wander_behavior(world, current_time)
    
    def _follower_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement follower behavior."""
        if not self.follow_target:
            return None
            
        # For now, we'll just assume the follow target is the player
        if self.follow_target == "player":
            # Check if we're already in the same room as the player
            if (self.current_region_id == world.current_region_id and
                self.current_room_id == world.current_room_id):
                return None
                
            # We need to find a path to the player (simplified)
            # In a full implementation, you'd want proper pathfinding
            
            # Get current room
            region = world.get_region(self.current_region_id)
            if not region:
                return None
                
            room = region.get_room(self.current_room_id)
            if not room:
                return None
                
            # Try to move toward the player by picking an exit that feels right
            # This is a very simplified approach
            best_direction = None
            
            # If in the same region, try to find a direct path
            if self.current_region_id == world.current_region_id:
                for direction, destination in room.exits.items():
                    if destination == world.current_room_id:
                        best_direction = direction
                        break
            
            # If no direct path or different region, just pick a random exit
            if not best_direction:
                exits = list(room.exits.keys())
                if exits:
                    best_direction = random.choice(exits)
            
            # Move in the chosen direction
            if best_direction:
                destination = room.exits[best_direction]
                old_room_id = self.current_room_id
                
                # Handle region transitions
                if ":" in destination:
                    new_region_id, new_room_id = destination.split(":")
                    self.current_region_id = new_region_id
                    self.current_room_id = new_room_id
                else:
                    self.current_room_id = destination
                    
                # Check if the player is in the room to see the NPC leave
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == old_room_id):
                    message = f"{self.name} leaves to the {best_direction}."
                    return message
                    
                # Check if the player is in the destination room to see the NPC arrive
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == destination):
                    message = f"{self.name} arrives from the {self._reverse_direction(best_direction)}."
                    return message
                
                self.last_moved = current_time
                
        return None