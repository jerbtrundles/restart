"""
npc.py
Enhanced NPC module with integrated combat capabilities
"""
from typing import Dict, List, Optional, Any, Tuple, Callable
import random
import time
from game_object import GameObject
from items.inventory import Inventory
from items.item import Item


class NPC(GameObject):
    """Base class for all non-player characters and monsters."""

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
        
        # Combat-related attributes
        self.is_alive = True
        self.aggression = 0.0  # 0.0 = never attacks, 1.0 = always attacks
        self.attack_power = 3
        self.defense = 2
        self.flee_threshold = 0.2  # Flee when health below 20%
        self.respawn_cooldown = 600  # 10 minutes default respawn time
        self.spawn_time = 0
        self.loot_table = {}  # Item ID to drop chance mapping
        self.in_combat = False
        self.combat_target = None
        self.last_combat_action = 0
        self.combat_cooldown = 3  # Seconds between attacks
        self.attack_cooldown = 3.0       # Seconds between attacks
        self.last_attack_time = 0        # Last time this NPC attacked
        self.combat_targets = set()      # Set of entities this NPC is fighting
        self.combat_messages = []        # Recent combat messages
        self.max_combat_messages = 5     # Maximum number of combat messages to store
        
        # Add faction system for determining friend/foe
        self.faction = "neutral"  # neutral, friendly, hostile
        self.faction_relations = {
            "friendly": 100,
            "neutral": 0,
            "hostile": -100
        }
        
        # Store in properties
        self.update_property("health", health)
        self.update_property("max_health", health)
        self.update_property("friendly", friendly)
        self.update_property("behavior_type", self.behavior_type)
        self.update_property("wander_chance", self.wander_chance)
        self.update_property("move_cooldown", self.move_cooldown)
        self.update_property("aggression", self.aggression)
        self.update_property("attack_power", self.attack_power)
        self.update_property("defense", self.defense)
        self.update_property("is_alive", self.is_alive)
        self.update_property("faction", self.faction)

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
        
        faction_desc = ""
        if self.faction == "hostile":
            faction_desc = f"The {self.name} looks hostile."
        elif self.faction == "friendly":
            faction_desc = f"The {self.name} appears friendly."
            
        combat_desc = ""
        if self.in_combat:
            combat_desc = f"The {self.name} is engaged in combat!"
        
        return f"{self.name}\n\n{self.description}\n\n{health_desc}" + \
               (f"\n{faction_desc}" if faction_desc else "") + \
               (f"\n{combat_desc}" if combat_desc else "")
        
    def talk(self, topic: str = None) -> str:
        """Get dialog from the NPC based on a topic."""
        # If in combat, respond with combat dialog
        if self.in_combat:
            combat_responses = [
                f"The {self.name} is too busy fighting to talk!",
                f"The {self.name} growls angrily, focused on the battle.",
                f"\"Can't talk now!\" shouts the {self.name}."
            ]
            return random.choice(combat_responses)
        
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
        
        # Default response
        return self.default_dialog.format(name=self.name)
    
    def attack(self, target) -> Dict[str, Any]:
        """
        Attack a target (player or another NPC), now includes hit chance.

        Returns: Dict with attack details or miss info
        """
        # --- HIT CHANCE CALCULATION ---
        base_hit_chance = 0.80  # NPCs might be slightly less accurate by default
        attacker_dex = getattr(self, "stats", {}).get("dexterity", 8) # NPC default dex
        target_dex = getattr(target, "stats", {}).get("dexterity", 10) # Target dex

        hit_chance = base_hit_chance + (attacker_dex - target_dex) * 0.02
        hit_chance = max(0.10, min(hit_chance, 0.95)) # Clamp

        import random
        if random.random() > hit_chance:
            # --- MISS ---
            miss_message = f"{self.name} attacks {getattr(target, 'name', 'target')} but misses!"
            # Note: We don't add to NPC's combat log here, maybe player's if target is player?
            # Or handle message display in the calling code (NPC update loop / game manager)
            return {
                "attacker": self.name,
                "target": getattr(target, "name", "target"),
                "damage": 0,
                "missed": True,
                "message": miss_message
            }
        # --- END HIT CHANCE ---

        # --- HIT ---
        self.in_combat = True # Ensure combat state on hit
        self.combat_target = target
        self.last_combat_action = time.time()

        # Calculate base damage (No durability check for NPCs for now)
        base_damage = self.attack_power
        if hasattr(self, "stats") and "strength" in self.stats:
            base_damage += self.stats["strength"] // 3

        # Add small random factor (-1 to +2)
        damage_variation = random.randint(-1, 2)
        base_damage += damage_variation

        # Consider target defense if available (use get_defense if target has it)
        if hasattr(target, 'get_defense'):
             defense = target.get_defense()
        else:
             defense = getattr(target, "defense", 0)
             if hasattr(target, "stats") and "dexterity" in target.stats:
                  defense += target.stats["dexterity"] // 3


        # Calculate final damage (minimum 1)
        damage = max(1, base_damage - defense)

        # Apply damage to target
        actual_damage = 0
        if hasattr(target, "take_damage"):
            actual_damage = target.take_damage(damage)
        elif hasattr(target, "health"):
            old_health = target.health
            target.health = max(0, target.health - damage)
            actual_damage = old_health - target.health
            if target.health <= 0 and hasattr(target, 'is_alive'):
                target.is_alive = False # Ensure dead state if simple health attribute

        hit_message = f"{self.name} attacks {getattr(target, 'name', 'target')} for {actual_damage} damage!"

        # Return attack results
        return {
            "attacker": self.name,
            "target": getattr(target, "name", "target"),
            "damage": actual_damage,
            "missed": False,
            "message": hit_message
        }
    
    def take_damage(self, amount: int) -> int:
        """
        Handle taking damage from combat
        
        Returns: Actual damage taken
        """
        # Calculate damage reduction from defense (minimum 0)
        reduced_damage = max(0, amount - self.defense)
        
        # Minimum 1 damage if attack hits
        if amount > 0:
            actual_damage = max(1, reduced_damage)
        else:
            actual_damage = 0
        
        # Apply damage
        old_health = self.health
        self.health = max(0, self.health - actual_damage)
        
        # Enter combat state when damaged
        self.in_combat = True
        
        # Check for death
        if self.health <= 0:
            self.is_alive = False
            self.update_property("is_alive", False)
            self.health = 0
            
        return old_health - self.health
    
    def heal(self, amount: int) -> int:
        """
        Heal the NPC for the specified amount
        
        Returns: Amount actually healed
        """
        if not self.is_alive:
            return 0
            
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - old_health
        
    def should_flee(self) -> bool:
        """Determine if NPC should flee from combat"""
        # If health below threshold, consider fleeing
        health_percent = self.health / self.max_health
        return health_percent <= self.flee_threshold
    
    def get_relation_to(self, other) -> int:
        """Get relationship value to another entity"""
        # If other has faction, use faction relations
        if hasattr(other, "faction"):
            return self.faction_relations.get(other.faction, 0)
        return 0
    
    def is_hostile_to(self, other) -> bool:
        """Check if NPC is hostile to another entity"""
        relation = self.get_relation_to(other)
        return relation < 0
    
    def update(self, world, current_time: float) -> Optional[str]:
        """
        Update the NPC's state and perform actions.
        
        Args:
            world: The game world object.
            current_time: The current game time.
            
        Returns:
            An optional message if the NPC did something visible.
        """
        # Dead NPCs don't do anything unless it's time to respawn
        if not self.is_alive:
            if hasattr(self, "respawn_cooldown") and (current_time - self.spawn_time) > self.respawn_cooldown:
                # Respawn the NPC
                self.health = self.max_health
                self.is_alive = True
                self.update_property("is_alive", True)
                self.in_combat = False
                self.combat_targets.clear()
                
                # Reset last moved time
                self.last_moved = current_time
                
                # Return to home location if available
                if self.home_region_id and self.home_room_id:
                    self.current_region_id = self.home_region_id
                    self.current_room_id = self.home_room_id
                
                # NPC has respawned message if player is present
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == self.current_room_id):
                    return f"{self.name} has returned."
            return None
            
        # Check if NPC is sleeping - no movement or combat
        if hasattr(self, "ai_state") and self.ai_state.get("is_sleeping", False):
            return None
        
        # Handle combat if in combat
        combat_message = None
        if self.in_combat:
            combat_message = self.try_attack(world, current_time)
            
            # Check for fleeing if health is low
            if self.health < self.max_health * self.flee_threshold:
                should_flee = True
                
                # Prioritize player as target
                player_target = next((t for t in self.combat_targets 
                                if hasattr(t, "faction") and t.faction == "player"), None)
                
                # Don't flee if player is almost dead
                if player_target and hasattr(player_target, "health") and player_target.health <= 10:
                    should_flee = False
                
                if should_flee:
                    # Try to flee to a random exit
                    region = world.get_region(self.current_region_id)
                    if region:
                        room = region.get_room(self.current_room_id)
                        if room and room.exits:
                            # Pick a random exit
                            direction = random.choice(list(room.exits.keys()))
                            destination = room.exits[direction]
                            
                            # Update location
                            old_region_id = self.current_region_id
                            old_room_id = self.current_room_id
                            
                            # Handle region transitions
                            if ":" in destination:
                                new_region_id, new_room_id = destination.split(":")
                                self.current_region_id = new_region_id
                                self.current_room_id = new_room_id
                            else:
                                self.current_room_id = destination
                            
                            # Exit combat
                            self.exit_combat()
                            
                            # Message if player is in the room
                            if (world.current_region_id == old_region_id and 
                                world.current_room_id == old_room_id):
                                return combat_message or f"{self.name} flees to the {direction}!"
                            
                            return None
        
        # Check for player in room to potentially initiate combat
        elif (self.faction == "hostile" and self.aggression > 0 and
            world.current_region_id == self.current_region_id and
            world.current_room_id == self.current_room_id):
            
            # Chance to attack player based on aggression
            if random.random() < self.aggression:
                self.enter_combat(world.player)
                
                # First attack might be delayed by the cooldown
                if self.can_attack(current_time):
                    combat_message = self.try_attack(world, current_time)
                else:
                    # Just show threat message
                    combat_message = f"{self.name} prepares to attack you!"
        
        # If in combat, prioritize combat over movement
        if self.in_combat:
            return combat_message
        
        # Standard NPC update logic for movement
        # Only move if not in combat and enough time has passed
        if current_time - self.last_moved < self.move_cooldown:
            return combat_message
                
        # Update according to behavior type
        if self.behavior_type == "wanderer":
            message = self._wander_behavior(world, current_time)
            if message:
                # Only update the last_moved time if the NPC actually moved
                self.last_moved = current_time
            return message or combat_message
        elif self.behavior_type == "patrol":
            message = self._patrol_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message or combat_message
        elif self.behavior_type == "follower":
            message = self._follower_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message or combat_message
        elif self.behavior_type == "scheduled":
            message = self._schedule_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message or combat_message
        elif self.behavior_type == "aggressive":
            # Aggressive NPCs actively seek out the player if nearby
            if self.current_region_id == world.current_region_id:
                # Check if player is in an adjacent room
                region = world.get_region(self.current_region_id)
                if region:
                    room = region.get_room(self.current_room_id)
                    if room and room.exits:
                        for direction, destination in room.exits.items():
                            if destination == world.current_room_id:
                                # Move toward player
                                old_room_id = self.current_room_id
                                self.current_room_id = destination
                                self.last_moved = current_time
                                return f"{self.name} enters from the {self._reverse_direction(direction)}!"
            
            # If player not found nearby, wander randomly
            message = self._wander_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message or combat_message
                    
        # Default stationary behavior
        return combat_message
            
    def die(self, world) -> List[Dict[str, Any]]:
        """
        Handle death and create loot drops
        
        Returns: List of loot items created
        """
        self.is_alive = False
        self.update_property("is_alive", False)
        self.health = 0
        self.in_combat = False
        self.combat_target = None
        
        # Record time of death for respawn calculation
        self.spawn_time = time.time() - world.start_time
        
        # Generate loot from loot table
        dropped_items = []
        if self.loot_table:
            from items.item_factory import ItemFactory
            
            for item_id, chance in self.loot_table.items():
                if random.random() < chance:
                    try:
                        # Create item from loot table
                        item = ItemFactory.create_item(item_id)
                        
                        # Add to room
                        if world.add_item_to_room(self.current_region_id, self.current_room_id, item):
                            dropped_items.append(item)
                    except Exception as e:
                        print(f"Error creating loot item {item_id}: {e}")
        
        # Also drop inventory items with 50% chance per item
        for slot in self.inventory.slots:
            if slot.item and random.random() < 0.5:
                item = slot.item
                world.add_item_to_room(self.current_region_id, self.current_room_id, item)
                dropped_items.append(item)
        
        return dropped_items
    
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
        
        # Add combat data
        data["is_alive"] = self.is_alive
        data["aggression"] = self.aggression
        data["attack_power"] = self.attack_power
        data["defense"] = self.defense
        data["flee_threshold"] = self.flee_threshold
        data["respawn_cooldown"] = self.respawn_cooldown
        data["loot_table"] = self.loot_table
        data["faction"] = self.faction
        
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
        
        # Set combat properties
        npc.is_alive = data.get("is_alive", True)
        npc.aggression = data.get("aggression", 0.0)
        npc.attack_power = data.get("attack_power", 3)
        npc.defense = data.get("defense", 2)
        npc.flee_threshold = data.get("flee_threshold", 0.2)
        npc.respawn_cooldown = data.get("respawn_cooldown", 600)
        npc.loot_table = data.get("loot_table", {})
        npc.faction = data.get("faction", "neutral")
        
        # Set inventory if present
        if "inventory" in data:
            try:
                from items.inventory import Inventory
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
        
    # [All the behavior methods (_wander_behavior, etc.) would remain unchanged]
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

    def enter_combat(self, target) -> None:
        """
        Enter combat with a target.
        
        Args:
            target: The target to fight with
        """
        self.in_combat = True
        self.combat_targets.add(target)
        
        # Set as target's enemy too if it supports it, but avoid recursion
        if hasattr(target, "enter_combat") and target not in self.combat_targets:
            # Add self to target's combat targets directly to avoid recursion
            if hasattr(target, "combat_targets"):
                target.combat_targets.add(self)
                target.in_combat = True

    def exit_combat(self, target=None) -> None:
        """
        Exit combat with a target or all targets.
        
        Args:
            target: Specific target to stop fighting, or None for all targets
        """
        if target:
            if target in self.combat_targets:
                self.combat_targets.remove(target)
                
                # Remove self from target's enemies if it supports it
                if hasattr(target, "exit_combat"):
                    target.exit_combat(self)
        else:
            # Exit combat with all targets
            for t in list(self.combat_targets):
                if hasattr(t, "exit_combat"):
                    t.exit_combat(self)
            self.combat_targets.clear()
        
        # Check if we're still in combat
        if not self.combat_targets:
            self.in_combat = False

    def can_attack(self, current_time: float) -> bool:
        """
        Check if this NPC can attack based on cooldown.
        
        Args:
            current_time: Current game time
            
        Returns:
            True if attack is ready, False otherwise
        """
        return current_time - self.last_attack_time >= self.attack_cooldown

    def try_attack(self, world, current_time: float) -> Optional[str]:
        """
        Try to attack a target based on cooldown. Handles misses.

        Args:
            world: Game world object (should be the main World instance)
            current_time: Current game time

        Returns:
            Attack message if attack happened and player is present, None otherwise
        """
        if not self.can_attack(current_time):
            return None

        # Filter out invalid targets (ensure world and player exist for checks)
        player = getattr(world, 'player', None)
        valid_targets = [t for t in self.combat_targets
                        if hasattr(t, "is_alive") and t.is_alive
                        and hasattr(t, "health") and t.health > 0
                        ]

        if not valid_targets:
            self.exit_combat()
            return None

        # Choose target (prioritize player if player is a valid target)
        target = None
        if player in valid_targets:
            target = player
        else:
            target = random.choice(valid_targets) # Choose randomly among others

        # Check if target is in same room
        target_in_room = False
        if target == player:
            # Check if the player's world location matches NPC's location
            if world and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
                target_in_room = True
        elif (hasattr(target, "current_region_id") and hasattr(target, "current_room_id") and
              target.current_region_id == self.current_region_id and
              target.current_room_id == self.current_room_id):
             # Check for other NPCs in the room
            target_in_room = True


        if target_in_room:
            # Perform attack
            attack_result = self.attack(target)
            self.last_attack_time = current_time # Update time even on miss

            # Only process hit messages further
            if not attack_result.get("missed", False):
                self._add_combat_message(attack_result["message"]) # Add hit message to NPC log

                # Check if target died from the hit
                if hasattr(target, "health") and target.health <= 0:
                    # Ensure target state is updated if needed
                    if hasattr(target, 'is_alive'): target.is_alive = False

                    self.exit_combat(target)
                    death_message = f"{target.name} has been defeated!"
                    self._add_combat_message(death_message)
                    if not self.combat_targets:
                        self.in_combat = False # Exit combat if no targets left

            # --- CORRECTION IS HERE ---
            # Return the message (hit or miss) only if the *world's current location*
            # (where the player is) matches the NPC's location.
            if world and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
                return attack_result["message"] # Return hit or miss message for the player to see
            # --- END CORRECTION ---

        else: # Target not in room
            self.exit_combat(target)

        return None # No message if player not present or target not in room

    def _add_combat_message(self, message: str) -> None:
        """
        Add a message to the combat log.
        
        Args:
            message: The message to add
        """
        self.combat_messages.append(message)
        
        # Trim to max size
        while len(self.combat_messages) > self.max_combat_messages:
            self.combat_messages.pop(0)
