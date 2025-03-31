"""
npcs/npc.py
NPC system for the MUD game.
Defines non-player characters and their behavior.
"""
from typing import Dict, List, Optional, Any, Tuple, Callable
import random
import time
from game_object import GameObject
from items.inventory import Inventory
from items.item import Item


class NPC(GameObject):
    """Base class for all non-player characters."""

    def __init__(self, obj_id: str = None, name: str = "Unknown NPC", 
                 description: str = "No description", health: int = 100,
                 friendly: bool = True):
        super().__init__(obj_id if obj_id else f"npc_{random.randint(1000, 9999)}", name, description)        
        self.health = health
        self.max_health = health
        self.friendly = friendly
        self.inventory = Inventory(max_slots=10, max_weight=50.0)
        self.current_region_id = None
        self.current_room_id = None
        self.home_region_id = None
        self.home_room_id = None
        self.current_activity = None
        self.behavior_type = "stationary"
        self.patrol_points = []
        self.patrol_index = 0
        self.follow_target = None
        self.wander_chance = 0.3
        self.schedule = {}
        self.last_moved = 0
        self.move_cooldown = 10
        self.dialog = {}
        self.default_dialog = "The {name} doesn't respond."
        self.ai_state = {}
        self.update_property("health", health)
        self.update_property("max_health", health)
        self.update_property("friendly", friendly)
        self.update_property("behavior_type", self.behavior_type)
        self.update_property("wander_chance", self.wander_chance)
        self.update_property("move_cooldown", self.move_cooldown)    

    def get_description(self) -> str:
        """Override the base get_description method with NPC-specific info."""
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
        """
        # Check if NPC is busy with an activity
        if hasattr(self, "ai_state"):
            # Activity-specific responses
            if self.ai_state.get("is_sleeping", False):
                responses = self.ai_state.get("sleeping_responses", [])
                if responses:
                    return random.choice(responses).format(name=self.name)
            
            elif self.ai_state.get("is_eating", False):
                responses = self.ai_state.get("eating_responses", [])
                if responses:
                    return random.choice(responses).format(name=self.name)
            
            elif self.ai_state.get("is_working", False) and topic != "work":
                responses = self.ai_state.get("working_responses", [])
                if responses:
                    return random.choice(responses).format(name=self.name)
        
        # Normal dialog processing
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
        
        # Activity reference
        if hasattr(self, "ai_state") and "current_activity" in self.ai_state:
            activity = self.ai_state["current_activity"]
            return f"The {self.name} continues {activity} and doesn't respond about that topic."
        
        # Default response
        return self.default_dialog.format(name=self.name)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the NPC to a dictionary for serialization.
        """
        # Start with the base implementation
        data = super().to_dict()
        
        # Add NPC-specific fields for backward compatibility
        data["obj_id"] = self.obj_id
        data["health"] = self.health
        data["max_health"] = self.max_health
        data["friendly"] = self.friendly
        
        # Add location data
        data["current_region_id"] = self.current_region_id
        data["current_room_id"] = self.current_room_id
        data["home_region_id"] = self.home_region_id
        data["home_room_id"] = self.home_room_id
        
        # Add behavior data
        data["behavior_type"] = self.behavior_type
        data["patrol_points"] = self.patrol_points
        data["patrol_index"] = self.patrol_index
        data["follow_target"] = self.follow_target
        data["wander_chance"] = self.wander_chance
        data["schedule"] = self.schedule
        data["move_cooldown"] = self.move_cooldown
        
        # Add interaction data
        data["dialog"] = self.dialog
        data["default_dialog"] = self.default_dialog
        data["ai_state"] = self.ai_state
        
        # Add inventory
        data["inventory"] = self.inventory.to_dict()
        
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPC':
        """
        Create an NPC from a dictionary.
        """
        # Get the ID (handle backward compatibility)
        obj_id = data.get("id") or data.get("obj_id")
        
        npc = cls(
            obj_id=obj_id,
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
            try:
                npc.inventory = Inventory.from_dict(data["inventory"])
            except Exception as e:
                print(f"Error loading inventory for NPC {npc.name}: {e}")
                npc.inventory = Inventory(max_slots=10, max_weight=50.0)
        else:
            npc.inventory = Inventory(max_slots=10, max_weight=50.0)
        
        # Set properties
        if "properties" in data:
            npc.properties = data["properties"]
        
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
        """Improved follower behavior with pathfinding."""
        if not self.follow_target:
            return None
            
        # For now, assume the follow target is the player
        if self.follow_target == "player":
            # Check if we're already in the same room as the player
            if (self.current_region_id == world.current_region_id and
                self.current_room_id == world.current_room_id):
                return None
                
            # Find path to player
            path = world.find_path(self.current_region_id,
                            self.current_room_id,
                            world.current_region_id,
                            world.current_room_id)
            
            if path and len(path) > 0:
                # Get the first step in the path
                direction = path[0]
                
                # Get current room
                region = world.get_region(self.current_region_id)
                if not region:
                    return None
                    
                room = region.get_room(self.current_room_id)
                if not room:
                    return None
                
                # Get destination
                destination = room.exits.get(direction)
                if not destination:
                    return None
                    
                # Save old location
                old_region_id = self.current_region_id
                old_room_id = self.current_room_id
                
                # Handle region transitions
                if ":" in destination:
                    new_region_id, new_room_id = destination.split(":")
                    self.current_region_id = new_region_id
                    self.current_room_id = new_room_id
                else:
                    self.current_room_id = destination
                
                # Update last moved
                self.last_moved = current_time
                
                # Return message if player can see
                if (world.current_region_id == old_region_id and 
                    world.current_room_id == old_room_id):
                    return f"{self.name} leaves to the {direction}."
                    
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == self.current_room_id):
                    return f"{self.name} arrives from the {self._reverse_direction(direction)}."
        
        return None