# npcs/npc.py
from typing import Dict, List, Optional, Any, Tuple, Callable, Set # Added Set
import random
import time
from game_object import GameObject
from items.inventory import Inventory
from items.item import Item
from items.item_factory import ItemFactory
from magic.spell import Spell # Import Spell
from magic.spell_registry import get_spell # Import registry access
from magic.effects import apply_spell_effect
from player import Player
from utils.text_formatter import TextFormatter, format_target_name


class NPC(GameObject):
    """Base class for all non-player characters and monsters."""

    def __init__(self, obj_id: str = None, name: str = "Unknown NPC", 
                 description: str = "No description", health: int = 100,
                 friendly: bool = True, level: int = 1):
        super().__init__(obj_id if obj_id else f"npc_{random.randint(1000, 9999)}", name, description)        
        self.health = health
        self.max_health = health
        self.friendly = friendly
        self.level = level # <<< ADD level attribute
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

        self.usable_spells: List[str] = [] # List of spell IDs the NPC can cast
        self.spell_cast_chance: float = 0.3 # Chance to cast a spell instead of attacking (if available)
        self.spell_cooldowns: Dict[str, float] = {} # spell_id -> time when cooldown ends
        # NPCs generally don't use mana in simple systems

        # Store in properties
        self.update_property("health", health)
        self.update_property("max_health", health)
        self.update_property("friendly", friendly)
        self.update_property("level", self.level) # <<< ADD level to properties
        self.update_property("behavior_type", self.behavior_type)
        self.update_property("wander_chance", self.wander_chance)
        self.update_property("move_cooldown", self.move_cooldown)
        self.update_property("aggression", self.aggression)
        self.update_property("attack_power", self.attack_power)
        self.update_property("defense", self.defense)
        self.update_property("is_alive", self.is_alive)
        self.update_property("faction", self.faction)
        self.update_property("usable_spells", self.usable_spells) # Add new property

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
        # *** Determine the viewer (usually the player if they are the target) ***
        # We assume the formatting is always from the Player's perspective
        # If the target is the player, the player is the viewer.
        # If the target is another NPC, the player is still the viewer observing.
        # We need access to the player object here. How?
        # Option 1: Pass player into NPC.attack (adds coupling)
        # Option 2: Get player from world (requires world access)
        # Option 3: Format the message OUTSIDE this method (better)

        # Let's stick to Option 3 conceptually, but implement simply for now:
        # We won't format the target name *inside* NPC.attack's returned message string.
        # The formatting will happen when the message is *displayed* or logged *by the player*.
        # However, the Player._add_combat_message needs the already formatted string.
        # --> Modify Player._add_combat_message? No, that's complex.
        # --> Decision: Format inside NPC.attack for simplicity, ASSUMING world.player exists.

        viewer = None
        if hasattr(self, 'world') and hasattr(self.world, 'player'): # Need to ensure NPC has world access
            viewer = self.world.player
        elif isinstance(target, Player): # If target is player, they are the viewer
            viewer = target

        formatted_target_name = target.name # Default if no viewer
        if viewer:
            formatted_target_name = format_target_name(viewer, target)

        # --- HIT CHANCE CALCULATION ---
        base_hit_chance = 0.80  # NPCs might be slightly less accurate by default
        attacker_dex = getattr(self, "stats", {}).get("dexterity", 8) # NPC default dex
        target_dex = getattr(target, "stats", {}).get("dexterity", 10) # Target dex

        hit_chance = base_hit_chance + (attacker_dex - target_dex) * 0.02
        hit_chance = max(0.10, min(hit_chance, 0.95)) # Clamp

        import random
        if random.random() > hit_chance:
            # --- MISS ---
            miss_message = f"{format_target_name(viewer, self)} attacks {formatted_target_name} but misses!"
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

        hit_message = f"{format_target_name(viewer, self)} attacks {formatted_target_name} for {actual_damage} damage!"

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
        # Add basic magic resist?
        magic_resist = getattr(self, 'stats', {}).get('magic_resist', 0) # Check if NPC has stats and resist
        # How to know if damage is magic? Needs more info passed to take_damage potentially.
        # For now, just use physical defense.
        reduced_damage = max(0, amount - self.defense)
        actual_damage = max(1, reduced_damage) if amount > 0 else 0

        old_health = self.health
        self.health = max(0, self.health - actual_damage)
        self.in_combat = True # Enter combat when damaged
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
                                return combat_message or f"{format_target_name(world.player, self)} flees to the {direction}!"
                            
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
                    combat_message = f"{format_target_name(world.player, self)} prepares to attack you!"
        
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
                                return f"{format_target_name(world.player, self)} enters from the {self._reverse_direction(direction)}!"
            
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
        dropped_items: List[Item] = []
        if self.loot_table:
            # *** UPDATED Loot Table Logic ***
            for item_name, loot_data in self.loot_table.items():
                # Check for chance
                if isinstance(loot_data, dict) and random.random() < loot_data.get("chance", 0):
                    try:
                        # Get item type, default to Junk if not specified
                        item_type = loot_data.get("type", "Junk")
                        # Prepare arguments for the factory
                        item_args = {
                            "item_type": item_type,
                            "name": item_name, # Use the key as the name
                            "obj_id": f"loot_{self.obj_id}_{item_name.lower().replace(' ', '_')}_{random.randint(1000,9999)}",
                            # Pass other properties from loot_data if they exist
                            **{k: v for k, v in loot_data.items() if k not in ["chance", "type"]}
                        }
                        # Add a default description if none provided in loot_data
                        if "description" not in item_args:
                            item_args["description"] = f"A {item_name.lower()} dropped by a {self.name}."

                        item = ItemFactory.create_item(**item_args)

                        if item:
                            if world and world.add_item_to_room(self.current_region_id, self.current_room_id, item):
                                dropped_items.append(item)
                            elif not world:
                                 print(f"Warning: World object missing in die() for {self.name}, cannot drop {item.name}")
                        else:
                             print(f"Warning: ItemFactory failed to create item '{item_name}' for {self.name}.")

                    except Exception as e:
                        print(f"Error processing loot item '{item_name}' for {self.name}: {e}")
                        import traceback
                        traceback.print_exc()
            # *** END UPDATED Loot Table Logic ***

        # Drop inventory items (same as before, check world)
        if hasattr(self, 'inventory'):
             for slot in self.inventory.slots:
                 if slot.item and random.random() < 0.5:
                     item = slot.item
                     if world and world.add_item_to_room(self.current_region_id, self.current_room_id, item):
                         dropped_items.append(item)
                     elif not world:
                         print(f"Warning: World object missing in die() for {self.name}, cannot drop inventory item {item.name}")

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

        data["level"] = self.level # <<< ADD level

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
        data["faction"] = self.faction

        data["usable_spells"] = self.usable_spells
        data["spell_cooldowns"] = self.spell_cooldowns
        data["spell_cast_chance"] = self.spell_cast_chance
        
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPC':
        """
        Create an NPC from a dictionary.
        """
        npc = super(NPC, cls).from_dict(data) # Use GameObject.from_dict

        # Set basic properties
        npc.max_health = data.get("max_health", 100)
        npc.current_region_id = data.get("current_region_id")
        npc.current_room_id = data.get("current_room_id")
        npc.home_region_id = data.get("home_region_id")
        npc.home_room_id = data.get("home_room_id")

        npc.level = data.get("level", 1)
        
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

        npc.usable_spells = data.get("usable_spells", [])
        npc.spell_cooldowns = data.get("spell_cooldowns", {})
        npc.spell_cast_chance = data.get("spell_cast_chance", 0.3)
        
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
                return f"{format_target_name(world.player, self)} leaves{activity_msg}."
                
            if (world.current_region_id == self.current_region_id and 
                world.current_room_id == self.current_room_id):
                return f"{format_target_name(world.player, self)} arrives{activity_msg}."
        
        return None

    def _wander_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement wandering behavior, avoiding safe zones for hostile NPCs."""
        # Only wander sometimes
        if random.random() > self.wander_chance:
            return None

        # Get current room and its exits
        region = world.get_region(self.current_region_id)
        if not region: return None
        room = region.get_room(self.current_room_id)
        if not room or not room.exits: return None

        # --- MODIFIED: Consider only valid exits ---
        valid_exits = {}
        is_hostile = (self.faction == "hostile") # Check if this NPC is hostile

        for direction, destination in room.exits.items():
            next_region_id = self.current_region_id
            next_room_id = destination
            if ":" in destination:
                next_region_id, next_room_id = destination.split(":")

            # Check if the destination is safe
            destination_is_safe = world.is_location_safe(next_region_id, next_room_id)

            # Hostile NPCs avoid entering safe zones
            if is_hostile and destination_is_safe:
                continue # Skip this exit

            # Optional: Non-hostile NPCs might also avoid certain dangerous zones? (Not implemented here)

            valid_exits[direction] = destination
        # --- END MODIFICATION ---

        if not valid_exits:
            return None # No valid places to wander to

        # Choose a random *valid* exit and move through it
        direction = random.choice(list(valid_exits.keys()))
        destination = valid_exits[direction]

        # Save old location info
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id

        # Handle region transitions
        if ":" in destination:
            new_region_id, new_room_id = destination.split(":")
            self.current_region_id = new_region_id
            self.current_room_id = new_room_id
        else:
            self.current_room_id = destination

        # Update last_moved in the main update() loop after the behavior returns a message

        # Return message if player can see the movement
        if world.current_region_id == old_region_id and world.current_room_id == old_room_id:
            return f"{format_target_name(world.player, self)} leaves to the {direction}."
        if world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
            return f"{format_target_name(world.player, self)} arrives from the {self._reverse_direction(direction)}."

        return None # Return None if player didn't see the movement directly

    def _patrol_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement patrol behavior, avoiding moving *into* safe zones for hostile NPCs."""
        if not self.patrol_points:
            return None

        # Get next patrol point
        next_point_room_id = self.patrol_points[self.patrol_index]
        # Assume patrol points are within the same region for simplicity here
        next_point_region_id = self.current_region_id # Adjust if patrol points can cross regions

        # Check if the target patrol point itself is in a safe zone (hostile patrols shouldn't target safe zones)
        is_hostile = (self.faction == "hostile")
        if is_hostile and world.is_location_safe(next_point_region_id, next_point_room_id):
            # Skip this patrol point or the whole patrol? Let's skip the point for now.
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
            return None # Re-evaluate next tick

        # If we're already there, move to the next point in the list
        if next_point_room_id == self.current_room_id:
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
            return None

        # Find a path (simplified: find direct exit)
        region = world.get_region(self.current_region_id)
        if not region: return None
        room = region.get_room(self.current_room_id)
        if not room: return None

        chosen_direction = None
        chosen_destination = None

        # Look for a direct path first
        for direction, destination in room.exits.items():
            if destination == next_point_room_id: # Assuming same region for now
                 # *** ADD SAFETY CHECK ***
                 next_region_id = self.current_region_id
                 next_room_id = destination
                 if ":" in destination:
                     next_region_id, next_room_id = destination.split(":")

                 if is_hostile and world.is_location_safe(next_region_id, next_room_id):
                     continue # Don't choose this path if it leads directly into a safe zone

                 chosen_direction = direction
                 chosen_destination = destination
                 break # Found a direct, valid path


        # If no direct path found OR direct path was into safe zone, maybe wander?
        if not chosen_direction:
             # Fallback to wandering *away* from safe zones if possible
             return self._wander_behavior(world, current_time)

        # --- Move using the chosen direction ---
        old_region_id = self.current_region_id # Save before changing
        old_room_id = self.current_room_id

        # Handle region transitions if destination format includes it
        if ":" in chosen_destination:
            new_region_id, new_room_id = chosen_destination.split(":")
            self.current_region_id = new_region_id
            self.current_room_id = new_room_id
        else:
            self.current_room_id = chosen_destination


        # Return message if player can see
        if world.current_region_id == old_region_id and world.current_room_id == old_room_id:
            return f"{self.name} leaves to the {chosen_direction}."
        if world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
            return f"{self.name} arrives from the {self._reverse_direction(chosen_direction)}."

        return None


    def _follower_behavior(self, world, current_time: float) -> Optional[str]:
        """Follower behavior, avoiding moving *into* safe zones for hostile NPCs."""
        if not self.follow_target:
            return None

        # Simplified: Assume target is player
        if self.follow_target == "player":
            player_region_id = world.current_region_id
            player_room_id = world.current_room_id

            # If already in the same room, do nothing
            if (self.current_region_id == player_region_id and
                self.current_room_id == player_room_id):
                return None

            # Find path to player
            path = world.find_path(self.current_region_id, self.current_room_id,
                                   player_region_id, player_room_id)

            if path and len(path) > 0:
                # Get the first step (direction)
                direction = path[0]

                # Get current room and the exit destination
                region = world.get_region(self.current_region_id)
                if not region: return None
                room = region.get_room(self.current_room_id)
                if not room or direction not in room.exits: return None
                destination = room.exits[direction]

                # Determine next location
                next_region_id = self.current_region_id
                next_room_id = destination
                if ":" in destination:
                    next_region_id, next_room_id = destination.split(":")

                # *** ADD SAFETY CHECK ***
                is_hostile = (self.faction == "hostile")
                if is_hostile and world.is_location_safe(next_region_id, next_room_id):
                    # Hostile NPC stops following if the next step is into a safe zone
                    # Optionally, could clear self.follow_target here
                    # print(f"{self.name} stops following into safe zone {next_region_id}:{next_room_id}") # Debug
                    return None # Don't take the step

                # --- If not entering a safe zone, proceed with movement ---
                old_region_id = self.current_region_id
                old_room_id = self.current_room_id

                self.current_region_id = next_region_id
                self.current_room_id = next_room_id

                # Return message if player can see
                if world.current_region_id == old_region_id and world.current_room_id == old_room_id:
                    return f"{self.name} leaves to the {direction}."
                if world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
                    return f"{self.name} arrives from the {self._reverse_direction(direction)}."

        return None # No path or other issue

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

    # Modify try_attack to incorporate spellcasting chance
    def try_attack(self, world, current_time: float) -> Optional[str]:
        """
        Try to perform a combat action (attack or spell) based on cooldowns and chance.
        """
        # General action cooldown check
        if current_time - self.last_combat_action < self.combat_cooldown:
             return None

        # Filter out invalid targets
        player = getattr(world, 'player', None)
        valid_targets = [t for t in self.combat_targets
                         if hasattr(t, "is_alive") and t.is_alive
                         and hasattr(t, "health") and t.health > 0]
        if not valid_targets:
            self.exit_combat()
            return None

        # Choose target (prioritize player)
        target = player if player in valid_targets else random.choice(valid_targets)

        # Check if target is in the same room
        target_in_room = False
        # ... (same room check logic as before) ...
        if target == player:
             if world and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
                  target_in_room = True
        elif (hasattr(target, "current_region_id") and hasattr(target, "current_room_id") and
               target.current_region_id == self.current_region_id and
               target.current_room_id == self.current_room_id):
             target_in_room = True

        if not target_in_room:
             self.exit_combat(target)
             return None # Target not here

        # --- Spellcasting Logic ---
        chosen_spell = None
        if self.usable_spells and random.random() < self.spell_cast_chance:
            # Try to cast a spell
            available_spells = []
            for spell_id in self.usable_spells:
                 spell = get_spell(spell_id)
                 cooldown_end = self.spell_cooldowns.get(spell_id, 0)
                 if spell and current_time >= cooldown_end:
                      # Basic target type check
                      is_enemy = (hasattr(target, 'faction') and target.faction != self.faction) # Simple enemy check
                      is_friendly = (target == self or (hasattr(target, 'faction') and target.faction == self.faction))

                      if spell.target_type == "enemy" and is_enemy:
                           available_spells.append(spell)
                      elif spell.target_type == "friendly" and is_friendly:
                           available_spells.append(spell)
                      elif spell.target_type == "self":
                           # Allow casting self-targeted spell if any valid spell is available
                           available_spells.append(spell) # NPC casts on self

            if available_spells:
                 chosen_spell = random.choice(available_spells)

        # --- Perform Action ---
        action_message = None
        if chosen_spell:
            # Cast the spell
            spell_target = target if chosen_spell.target_type != "self" else self # Target self if needed
            cast_result = self.cast_spell(chosen_spell, spell_target, current_time)
            action_message = cast_result.get("message")
            # Apply general combat cooldown
            self.last_combat_action = current_time

        else:
            # Perform physical attack if spell wasn't chosen or available
            if self.can_attack(current_time): # Check specific attack cooldown
                attack_result = self.attack(target)
                action_message = attack_result.get("message")
                self.last_attack_time = current_time # Update attack cooldown time
                # Apply general combat cooldown
                self.last_combat_action = current_time
            # Else: No action possible this tick (both attack and spells on CD)

        # --- Process Message and Target Death ---
        if action_message:
            self._add_combat_message(action_message) # Log action

            # Check if target died (check needed for both attack and damaging spells)
            if hasattr(target, "health") and target.health <= 0:
                if hasattr(target, 'is_alive'): target.is_alive = False
                self.exit_combat(target)
                formatted_target_name = format_target_name(world.player, target)
                death_message = f"{formatted_target_name} has been defeated!"
                self._add_combat_message(death_message)
                if not self.combat_targets: self.in_combat = False

            # Return message ONLY if the player is in the room to see it
            if world and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
                return action_message

        return None # No visible action or message generated for the player

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

    # *** NEW: NPC Spell Cast Method ***
    def cast_spell(self, spell: Spell, target, current_time: float) -> Dict[str, Any]:
         """Applies spell effect and sets cooldown. NPCs don't use mana."""

         # Set cooldown
         self.spell_cooldowns[spell.spell_id] = current_time + spell.cooldown

         # Apply effect
         value, effect_message = apply_spell_effect(self, target, spell) # Use central function

         # Format messages
         cast_message = spell.format_cast_message(self)
         full_message = cast_message + "\n" + effect_message

         return {
              "success": True,
              "message": full_message,
              "cast_message": cast_message,
              "effect_message": effect_message,
              "target": getattr(target, 'name', 'target'),
              "value": value,
              "spell": spell.name
         }
    # *** END NEW ***
