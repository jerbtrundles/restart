# npcs/npc.py
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple, Callable, Set # Added Set
import random
import time
from game_object import GameObject
from items.inventory import Inventory
from items.item import Item
from items.item_factory import ItemFactory
from magic.spell import Spell # Import Spell
from magic.spell_registry import get_spell # Import registry access
from utils.utils import format_name_for_display
from core.config import (
    LEVEL_DIFF_COMBAT_MODIFIERS, MAX_HIT_CHANCE, MIN_HIT_CHANCE,
    NPC_BASE_HEALTH, NPC_CON_HEALTH_MULTIPLIER,
    NPC_LEVEL_HEALTH_BASE_INCREASE, NPC_LEVEL_CON_HEALTH_MULTIPLIER
)

if TYPE_CHECKING:
    from world.world import World
    from player import Player # Need player type hint

class NPC(GameObject):
    def __init__(self, obj_id: str = None, name: str = "Unknown NPC",
                    description: str = "No description", health: int = 100,
                    friendly: bool = True, level: int = 1):
        # Add template_id storage
        self.template_id: Optional[str] = None # Will be set by factory
        # ... rest of __init__ mostly unchanged ...
        super().__init__(obj_id if obj_id else f"npc_{random.randint(1000, 9999)}", name, description)

        self.stats = {
            "strength": 8, "dexterity": 8, "intelligence": 5,
            "wisdom": 5, "constitution": 8, "agility": 8, # Added CON, AGI defaults
            "spell_power": 0, "magic_resist": 0
        }

        self.level = level
        self.is_trading: bool = False # <<< ADDED: Flag to indicate trading state

        base_hp = NPC_BASE_HEALTH + int(self.stats.get('constitution', 8) * NPC_CON_HEALTH_MULTIPLIER)
        level_hp_bonus = (self.level - 1) * (NPC_LEVEL_HEALTH_BASE_INCREASE + int(self.stats.get('constitution', 8) * NPC_LEVEL_CON_HEALTH_MULTIPLIER))
        self.max_health = base_hp + level_hp_bonus
        self.health = min(health, self.max_health) # Use provided health arg, clamped by calculated max

        self.friendly = friendly
        self.faction = "neutral"

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
        self.is_alive = True
        self.aggression = 0.0
        self.attack_power = 3
        self.defense = 2
        self.flee_threshold = 0.2
        self.respawn_cooldown = 600
        self.spawn_time = 0
        self.loot_table = {}
        self.in_combat = False
        self.combat_target = None
        self.last_combat_action = 0
        self.combat_cooldown = 3
        self.attack_cooldown = 3.0
        self.last_attack_time = 0
        self.combat_targets = set()
        self.combat_messages = []
        self.max_combat_messages = 5
        self.faction_relations = {"friendly": 100, "neutral": 0, "hostile": -100}
        self.usable_spells: List[str] = []
        self.spell_cast_chance: float = 0.3
        self.spell_cooldowns: Dict[str, float] = {}
        self.world: Optional['World'] = None # Add world reference

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
        """NPC attacks a target, modified by level difference."""
        from utils.text_formatter import format_target_name, get_level_diff_category

        viewer = self.world.player if self.world and hasattr(self.world, 'player') else None
        target_level = getattr(target, 'level', 1)
        category = get_level_diff_category(self.level, target_level) # NPC vs Target

        # --- Calculate Hit Chance using Agility ---
        base_hit_chance = 0.80 # Base chance for NPCs
        attacker_agi = self.stats.get("agility", 8) # Use NPC's agility
        # Safely get target stats, default agility if missing
        target_agi = getattr(target, "stats", {}).get("agility", 10) # Assume player default AGI is 10

        agi_modifier = (attacker_agi - target_agi) * 0.02
        agi_modified_hit_chance = base_hit_chance + agi_modifier
        # --- End Agility Use ---

        # Apply level difference modifier
        hit_chance_mod, _, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        level_modified_hit_chance = agi_modified_hit_chance * hit_chance_mod

        # Clamp the final hit chance
        final_hit_chance = max(MIN_HIT_CHANCE, min(level_modified_hit_chance, MAX_HIT_CHANCE))

        formatted_caster_name = format_name_for_display(viewer, self, start_of_sentence=True)
        formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False)

        if random.random() > final_hit_chance:
            # --- MISS ---
            miss_message = f"{formatted_caster_name} attacks {formatted_target_name} but misses!"
            # Note: We don't add to NPC's combat log here, maybe player's if target is player?
            # Or handle message display in the calling code (NPC update loop / game manager)
            return {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": 0, "missed": True, "message": miss_message, "hit_chance": final_hit_chance}

        # --- HIT ---
        self.in_combat = True # Ensure combat state on hit
        self.combat_target = target
        self.last_combat_action = time.time()

        # Calculate base damage (No durability check for NPCs for now)
        base_damage = self.attack_power
        damage_variation = random.randint(-1, 1)
        base_damage += damage_variation

        _, damage_dealt_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        modified_attack_damage = max(1, int(base_damage * damage_dealt_mod))

        # Apply damage to target
        actual_damage = 0
        if hasattr(target, "take_damage"):
                actual_damage = target.take_damage(modified_attack_damage, damage_type="physical")
        elif hasattr(target, "health"):
            old_health = target.health
            target.health = max(0, target.health - modified_attack_damage)
            actual_damage = old_health - target.health
            if target.health <= 0 and hasattr(target, 'is_alive'):
                target.is_alive = False # Ensure dead state if simple health attribute

        hit_message = f"{formatted_caster_name} attacks {formatted_target_name} for {actual_damage} damage!"

        # Return attack results
        return {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": actual_damage, "missed": False, "message": hit_message, "hit_chance": final_hit_chance}

    def take_damage(self, amount: int, damage_type: str) -> int:
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
        Dead NPCs no longer respawn via this method.
        """
        from utils.text_formatter import format_target_name

        # Dead NPCs simply do nothing until removed by the World update cycle.
        if not self.is_alive:
            return None

        # Check if we need to keep trading
        if self.is_trading:
                # Check if still trading with *this* NPC and in same room
                player = world.player
                if (player and player.trading_with == self.obj_id and
                    player.current_region_id == self.current_region_id and
                    player.current_room_id == self.current_room_id):
                    # Player still here and trading, so do nothing
                    return None
                else:
                    # Player stopped trading (moved, targeted someone else, etc.)
                    # or is no longer present. Resume normal AI.
                    self.is_trading = False
                    print(f"NPC {self.name} resuming AI as player stopped trading.")
            
        # Check if NPC is sleeping - no movement or combat
        if hasattr(self, "ai_state") and self.ai_state.get("is_sleeping", False):
            return None
        
        # Handle combat if in combat
        combat_message = None
        if self.in_combat:
            combat_message = self.try_attack(world, current_time)
            
            # Check for fleeing if health is low
            if self.is_alive and self.health < self.max_health * self.flee_threshold:
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
                            valid_exits = [d for d, dest in room.exits.items() if not world.is_location_safe(self.current_region_id, dest.split(':')[-1])] if self.faction == 'hostile' else list(room.exits.keys())
                            if valid_exits:
                                direction = random.choice(valid_exits)
                                destination = room.exits[direction]

                                old_region_id = self.current_region_id
                                old_room_id = self.current_room_id
                                old_region_id = self.current_region_id
                                old_room_id = self.current_room_id
                                if ":" in destination:
                                    new_region_id, new_room_id = destination.split(":")
                                    self.current_region_id = new_region_id
                                    self.current_room_id = new_room_id
                                else: self.current_room_id = destination
                                self.exit_combat()
                                self.last_moved = time.time() # Update move timer after fleeing

                                npc_display_name = format_name_for_display(player, self, start_of_sentence=True)
                                
                                # Message if player is in the room
                                if (world.current_region_id == old_region_id and 
                                    world.current_room_id == old_room_id):
                                    return combat_message or f"{npc_display_name} flees to the {direction}!"
                            
                            return None
            if self.in_combat:
                return combat_message
        
        # Check for player in room to potentially initiate combat
        elif (self.faction == "hostile" and self.aggression > 0 and
            world.current_region_id == self.current_region_id and
            world.current_room_id == self.current_room_id and
            world.player and world.player.is_alive): # Check player exists and is alive
            
            if random.random() < self.aggression:
                self.enter_combat(world.player)
                # Immediately try an action after entering combat
                action_result_message = self.try_attack(world, current_time)
                if action_result_message:
                        combat_message = action_result_message # This is shown to player
                else:
                    viewer = world.player # Viewer is player here
                    combat_message = f"{format_target_name(viewer, self)} prepares to attack you!"

        # If combat message generated (either from ongoing or initiating), return it
        if combat_message:
            return combat_message
        
        # Standard NPC update logic for movement
        # Only move if not in combat and enough time has passed
        if current_time - self.last_moved < self.move_cooldown:
            return combat_message
                
        move_message = None
        if self.behavior_type == "wanderer":
            move_message = self._wander_behavior(world, current_time)
        elif self.behavior_type == "patrol":
            move_message = self._patrol_behavior(world, current_time)
        # ... (handle follower, scheduled, aggressive movement) ...
        elif self.behavior_type == "follower":
                move_message = self._follower_behavior(world, current_time)
        elif self.behavior_type == "scheduled":
                move_message = self._schedule_behavior(world, current_time)
        elif self.behavior_type == "aggressive":
            # # Aggressive NPCs actively seek out the player if nearby
            # if self.current_region_id == world.current_region_id:
            #     # Check if player is in an adjacent room
            #     region = world.get_region(self.current_region_id)
            #     if region:
            #         room = region.get_room(self.current_room_id)
            #         if room and room.exits:
            #             for direction, destination in room.exits.items():
            #                 if destination == world.current_room_id:
            #                     # Move toward player
            #                     old_room_id = self.current_room_id
            #                     self.current_room_id = destination
            #                     self.last_moved = current_time
            #                     return f"{format_target_name(world.player, self)} enters from the {self._reverse_direction(direction)}!"
            
            # If player not found nearby, wander randomly
            move_message = self._wander_behavior(world, current_time)

        if move_message:
            self.last_moved = current_time # Update move timer *only* if movement occurred
            return move_message

        return None # No significant action or visible message generated

            
    def die(self, world: 'World') -> List[Item]: # Return Item instances
        """
        Handle death and create loot drops based on item_ids in loot_table.

        Returns: List of loot Item instances created and added to the room.
        """
        self.is_alive = False
        # self.update_property("is_alive", False) # Properties may not exist if loaded minimally
        self.health = 0
        self.in_combat = False
        self.combat_target = None
        self.combat_targets.clear() # Clear targets on death

        # Record time of death for respawn calculation
        self.spawn_time = time.time() - getattr(world, 'start_time', time.time())

        # Generate loot from loot table (references item_ids)
        dropped_items: List[Item] = []
        if self.loot_table:
            for item_id, loot_data in self.loot_table.items():
                if item_id == "gold_value":
                    continue # Gold is handled directly on kill, not as a dropped item

                # Check if loot_data is a dictionary (new format)
                if isinstance(loot_data, dict):
                    chance = loot_data.get("chance", 0)
                    if random.random() < chance:
                        try:
                            # Determine quantity
                            qty_range = loot_data.get("quantity", [1, 1])
                            # Ensure qty_range is a list/tuple of two ints
                            if not isinstance(qty_range, (list, tuple)) or len(qty_range) != 2:
                                qty_range = [1, 1]
                            quantity = random.randint(qty_range[0], qty_range[1])

                            # Create item(s) using ItemFactory
                            for _ in range(quantity):
                                item = ItemFactory.create_item_from_template(item_id, world) # Pass world
                                if item:
                                    if world and world.add_item_to_room(self.current_region_id, self.current_room_id, item):
                                        dropped_items.append(item)
                                    elif not world:
                                            print(f"Warning: World object missing in die() for {self.name}, cannot drop {item_id}")
                                else:
                                        print(f"Warning: ItemFactory failed to create loot item '{item_id}' for {self.name}.")

                        except Exception as e:
                            print(f"Error processing loot item '{item_id}' for {self.name}: {e}")
                            import traceback
                            traceback.print_exc()
                else:
                    # Handle old format (direct chance) - DEPRECATED?
                    chance = loot_data
                    if random.random() < chance:
                            print(f"Warning: Deprecated loot format for {item_id} in {self.name}. Use object format.")
                            # Attempt to create item assuming item_id is the template ID
                            item = ItemFactory.create_item_from_template(item_id, world)
                            if item:
                                if world and world.add_item_to_room(self.current_region_id, self.current_room_id, item):
                                    dropped_items.append(item)


        # Drop inventory items (optional, based on game design)
        if hasattr(self, 'inventory'):
                for slot in self.inventory.slots:
                    if slot.item and random.random() < 0.1: # Low chance to drop inventory
                        item_to_drop = slot.item
                        qty_to_drop = slot.quantity if slot.item.stackable else 1
                        # Create copies to drop if needed, or drop instance? Dropping instance is simpler
                        for _ in range(qty_to_drop):
                            # Need to handle removing from NPC inventory vs dropping instance
                            # Let's just add the item type to the room for now
                            item_copy = ItemFactory.create_item_from_template(item_to_drop.obj_id, world) # Create a fresh copy
                            if item_copy:
                                if world and world.add_item_to_room(self.current_region_id, self.current_room_id, item_copy):
                                    dropped_items.append(item_copy)
                            elif not world:
                                print(f"Warning: World object missing in die() for {self.name}, cannot drop inventory item {item_to_drop.name}")

        return dropped_items # Return the list of actual Item instances dropped

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the NPC state to a dictionary for serialization.
        Saves only essential state and template reference.
        """

        state = {
            "template_id": self.template_id, # Crucial reference
            "obj_id": self.obj_id, # Instance ID is important
            "name": self.name, # Save current name in case it changes
            "current_region_id": self.current_region_id,
            "current_room_id": self.current_room_id,
            "health": self.health,
            "is_alive": self.is_alive,
            "stats": self.stats.copy(), # --- SAVE STATS ---
            "ai_state": self.ai_state,
            "spell_cooldowns": self.spell_cooldowns,
            "faction": self.faction,
            "inventory": self.inventory.to_dict(self.world)
        }

        return state
        
    # [All the behavior methods (_wander_behavior, etc.) would remain unchanged]
    def _reverse_direction(self, direction: str) -> str:
        """Get the opposite direction."""
        from utils.text_formatter import format_target_name

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
        from utils.text_formatter import format_target_name

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

            npc_display_name = format_name_for_display(world.player, self)
            
            # Only return a message if the player is in either the old or new room
            if (world.current_region_id == old_region_id and 
                world.current_room_id == old_room_id):
                return f"{npc_display_name} leaves{activity_msg}."
                
            if (world.current_region_id == self.current_region_id and 
                world.current_room_id == self.current_room_id):
                return f"{npc_display_name} arrives{activity_msg}."
        
        return None

    def _wander_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement wandering behavior, avoiding safe zones for hostile NPCs."""
        from utils.text_formatter import format_target_name
        
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

        npc_display_name = format_name_for_display(world.player, self, start_of_sentence=True)

        # Update last_moved in the main update() loop after the behavior returns a message

        # Return message if player can see the movement
        if world.current_region_id == old_region_id and world.current_room_id == old_room_id:
            return f"{npc_display_name} leaves to the {direction}."
        if world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
            return f"{npc_display_name} arrives from the {self._reverse_direction(direction)}."

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

        npc_display_name = format_name_for_display(world.player, self)

        # Return message if player can see
        if world.current_region_id == old_region_id and world.current_room_id == old_room_id:
            return f"{npc_display_name} leaves to the {chosen_direction}."
        if world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
            return f"{npc_display_name} arrives from the {self._reverse_direction(chosen_direction)}."

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

                npc_display_name = format_name_for_display(world.player, self)

                # Return message if player can see
                if world.current_region_id == old_region_id and world.current_room_id == old_room_id:
                    return f"{npc_display_name} leaves to the {direction}."
                if world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
                    return f"{npc_display_name} arrives from the {self._reverse_direction(direction)}."

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
        from utils.text_formatter import format_target_name
        
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
                formatted_target_name_start = format_name_for_display(world.player, target, start_of_sentence=True)
                death_message = f"{formatted_target_name_start} has been defeated!"
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

    def cast_spell(self, spell: Spell, target, current_time: float) -> Dict[str, Any]:
            """Applies spell effect and sets cooldown. NPCs don't use mana."""
            from magic.effects import apply_spell_effect
            from utils.text_formatter import format_target_name

            # Set cooldown
            self.spell_cooldowns[spell.spell_id] = current_time + spell.cooldown

            formatted_caster_name = format_name_for_display(self.world.player, self, start_of_sentence=True)
            formatted_target_name = format_name_for_display(self.world.player, target, start_of_sentence=False)

            # Apply effect, passing the viewer context
            value, effect_message = apply_spell_effect(self, target, spell, self.world.player) # Pass viewer

            # Format the initial cast message (usually doesn't need coloring)
            # The caster name here is plain, which is often fine for the cast part.
            base_cast_message = spell.format_cast_message(self) # This uses the *plain* name

            # The effect_message now contains correctly formatted names relative to the viewer
            formatted_cast_message = base_cast_message.replace(self.name, formatted_caster_name, 1)

            full_message = formatted_cast_message + "\n" + effect_message

            return {
                "success": True,
                "message": full_message, # This now contains the formatted effect message
                "cast_message": formatted_cast_message, # Keep the simpler cast message separate if needed
                "effect_message": effect_message, # The detailed, formatted effect message
                "target": getattr(target, 'name', 'target'), # Keep raw target name here
                "value": value,
                "spell": spell.name
            }

