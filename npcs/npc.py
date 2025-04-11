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
from utils.text_formatter import format_target_name
from utils.utils import _reverse_direction, calculate_xp_gain, format_loot_drop_message, format_name_for_display, format_npc_arrival_message, format_npc_departure_message, get_arrival_phrase, get_departure_phrase
from core.config import (
    DEFAULT_FACTION_RELATIONS, EFFECT_DEFAULT_TICK_INTERVAL, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, HIT_CHANCE_AGILITY_FACTOR, LEVEL_DIFF_COMBAT_MODIFIERS, MAX_HIT_CHANCE, MIN_HIT_CHANCE, MINIMUM_DAMAGE_TAKEN, NPC_ATTACK_DAMAGE_VARIATION_RANGE, NPC_BASE_ATTACK_POWER, NPC_BASE_DEFENSE,
    NPC_BASE_HEALTH, NPC_BASE_HIT_CHANCE, NPC_CON_HEALTH_MULTIPLIER, NPC_DEFAULT_AGGRESSION, NPC_DEFAULT_ATTACK_COOLDOWN, NPC_DEFAULT_BEHAVIOR, NPC_DEFAULT_COMBAT_COOLDOWN, NPC_DEFAULT_FLEE_THRESHOLD, NPC_DEFAULT_MOVE_COOLDOWN, NPC_DEFAULT_RESPAWN_COOLDOWN, NPC_DEFAULT_SPELL_CAST_CHANCE, NPC_DEFAULT_STATS, NPC_DEFAULT_WANDER_CHANCE, NPC_HEALTH_DESC_THRESHOLDS,
    NPC_LEVEL_HEALTH_BASE_INCREASE, NPC_LEVEL_CON_HEALTH_MULTIPLIER, NPC_MAX_COMBAT_MESSAGES, WORLD_UPDATE_INTERVAL
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

        self.stats = NPC_DEFAULT_STATS.copy() # Use copy

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
        self.behavior_type = NPC_DEFAULT_BEHAVIOR
        self.wander_chance = NPC_DEFAULT_WANDER_CHANCE
        self.move_cooldown = NPC_DEFAULT_MOVE_COOLDOWN
        self.aggression = NPC_DEFAULT_AGGRESSION
        self.attack_power = NPC_BASE_ATTACK_POWER
        self.defense = NPC_BASE_DEFENSE
        self.flee_threshold = NPC_DEFAULT_FLEE_THRESHOLD
        self.respawn_cooldown = NPC_DEFAULT_RESPAWN_COOLDOWN
        self.combat_cooldown = NPC_DEFAULT_COMBAT_COOLDOWN
        self.attack_cooldown = NPC_DEFAULT_ATTACK_COOLDOWN
        self.max_combat_messages = NPC_MAX_COMBAT_MESSAGES
        self.spell_cast_chance: float = NPC_DEFAULT_SPELL_CAST_CHANCE
        self.patrol_points = []
        self.patrol_index = 0
        self.follow_target = None
        self.schedule = {}
        self.last_moved = 0
        self.dialog = {}
        self.default_dialog = "The {name} doesn't respond."
        self.ai_state = {}
        self.is_alive = True
        self.spawn_time = 0
        self.loot_table = {}
        self.in_combat = False
        self.combat_target = None
        self.last_combat_action = 0
        self.last_attack_time = 0
        self.combat_targets = set()
        self.combat_messages = []
        self.faction_relations = {"friendly": 100, "neutral": 0, "hostile": -100}
        self.usable_spells: List[str] = []
        self.spell_cooldowns: Dict[str, float] = {}
        self.world: Optional['World'] = None # Add world reference

        self.owner_id: Optional[str] = None # ID of the player who summoned this NPC
        self.creation_time: float = 0.0     # Timestamp when summoned
        self.summon_duration: float = 0.0   # How long it lasts (set from spell/override)

        self.faction_relations = DEFAULT_FACTION_RELATIONS.copy()

    def get_description(self) -> str:
        """Override the base get_description method with NPC-specific info."""
        health_percent = self.health / self.max_health * 100
        health_desc = ""
        
        if health_percent <= NPC_HEALTH_DESC_THRESHOLDS[0]: health_desc = f"The {self.name} looks severely injured."
        elif health_percent <= NPC_HEALTH_DESC_THRESHOLDS[1]: health_desc = f"The {self.name} appears to be wounded."
        elif health_percent <= NPC_HEALTH_DESC_THRESHOLDS[2]: health_desc = f"The {self.name} has some minor injuries."
        else: health_desc = f"The {self.name} looks healthy."
       
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
        base_hit_chance = NPC_BASE_HIT_CHANCE
        attacker_agi = self.stats.get("agility", 8) # Use NPC's agility
        # Safely get target stats, default agility if missing
        target_agi = getattr(target, "stats", {}).get("agility", 10) # Assume player default AGI is 10

        agi_modifier = (attacker_agi - target_agi) * HIT_CHANCE_AGILITY_FACTOR
        agi_modified_hit_chance = base_hit_chance + agi_modifier
        # --- End Agility Use ---

        # Apply level difference modifier
        hit_chance_mod, _, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        level_modified_hit_chance = agi_modified_hit_chance * hit_chance_mod

        # Clamp the final hit chance
        final_hit_chance = max(MIN_HIT_CHANCE, min(level_modified_hit_chance, MAX_HIT_CHANCE))

        formatted_caster_name = format_name_for_display(viewer, self, start_of_sentence=True)
        formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False)

        target_defeated = False
        
        if random.random() > final_hit_chance:
            # --- MISS ---
            miss_message = f"{formatted_caster_name} attacks {formatted_target_name} but misses!"
            # Note: We don't add to NPC's combat log here, maybe player's if target is player?
            # Or handle message display in the calling code (NPC update loop / game manager)
            return {
                "attacker": self.name,
                "target": getattr(target, 'name', 'target'),
                "damage": 0,
                "missed": True,
                "message": miss_message,
                "hit_chance": final_hit_chance,
                "target_defeated": False
            } # Add flag

        # --- HIT ---
        self.in_combat = True # Ensure combat state on hit
        self.combat_target = target
        self.last_combat_action = time.time()

        # Calculate base damage (No durability check for NPCs for now)
        base_damage = self.attack_power
        damage_variation = random.randint(NPC_ATTACK_DAMAGE_VARIATION_RANGE[0], NPC_ATTACK_DAMAGE_VARIATION_RANGE[1])
        base_damage += damage_variation

        _, damage_dealt_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        modified_attack_damage = max(MINIMUM_DAMAGE_TAKEN, int(base_damage * damage_dealt_mod))

        # Apply damage to target
        # actual_damage = 0
        # if hasattr(target, "take_damage"):
        actual_damage = target.take_damage(modified_attack_damage, damage_type="physical")
        if not target.is_alive:
            target_defeated = True
        # elif hasattr(target, "health"):
        #     print("health")
        #     old_health = target.health
        #     target.health = max(0, old_health - modified_attack_damage)
        #     actual_damage = old_health - target.health
        #     if target.health <= 0:
        #         target.is_alive = False # Ensure dead state if simple health attribute
        #         target_defeated = True # Set the flag

        hit_message = f"{formatted_caster_name} attacks {formatted_target_name} for {int(actual_damage)} damage!"

        # --- NEW: Check for on-hit effects ---
        apply_effect_message = ""
        # Check if NPC has an equipped weapon concept or if effect comes from template properties
        # Assuming effect comes from NPC properties for simplicity for now
        effect_chance = self.properties.get("on_hit_effect_chance", 0.0)
        if effect_chance > 0 and random.random() < effect_chance:
            effect_data = self.properties.get("on_hit_effect")
            if effect_data and isinstance(effect_data, dict):
                if hasattr(target, 'apply_effect'):
                    success, _ = target.apply_effect(effect_data, time.time())
                    if success:
                        # Message formatted for the *viewer* (player)
                        viewer = self.world.player if self.world else None
                        eff_name = effect_data.get('name', 'an effect')
                        caster_name_fmt = format_name_for_display(viewer, self, True)
                        tgt_name_fmt = format_name_for_display(viewer, target, False)
                        apply_effect_message = f"{FORMAT_HIGHLIGHT}{caster_name_fmt}'s attack afflicts {tgt_name_fmt} with {eff_name}!{FORMAT_RESET}"
                        # We don't add this to the NPC's log, but it will be part of the returned message dict

        # --- Construct Result ---
        # (Return dictionary structure remains the same, but include the effect message)
        result_message = hit_message
        if(apply_effect_message):
            result_message += "\n" + apply_effect_message

        result = {
            "attacker": self.name,
            "target": getattr(target, 'name', 'target'),
            "damage": actual_damage,
            "missed": False,
            "message": result_message, # Base hit message
            "hit_chance": final_hit_chance,
            "target_defeated": target_defeated
        }

        return result


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
        actual_damage = max(MINIMUM_DAMAGE_TAKEN, reduced_damage) if amount > 0 else 0

        old_health = self.health
        new_health = old_health - actual_damage
        self.health = new_health
        self.in_combat = True # Enter combat when damaged       
        
        if self.health <= 0:
            self.is_alive = False
            self.health = 0
        return actual_damage

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

    def die(self, world: 'World') -> List[Item]: # Return Item instances
        """Handle death - check if summoned before dropping loot."""
        # --- Check if Summoned ---
        if self.properties.get("is_summoned"):
            self.despawn(world, silent=True) # Despawn silently on death
            return [] # Return empty list, no loot from summons
        # --- End Summon Check ---
        self.is_alive = False
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
        Saves essential state, template reference, actual level, and CLEAN name.
        """
        state = {
            "template_id": self.template_id,
            "obj_id": self.obj_id,
            "name": self.name,               # <<< SAVE CURRENT CLEAN NAME
            "current_region_id": self.current_region_id,
            "current_room_id": self.current_room_id,
            "health": self.health,
            "level": self.level,             # <<< SAVE ACTUAL LEVEL
            "is_alive": self.is_alive,
            "stats": self.stats.copy(),
            "ai_state": self.ai_state.copy(),
            "spell_cooldowns": self.spell_cooldowns.copy(),
            "faction": self.faction,
            "inventory": self.inventory.to_dict(self.world) if self.world else {}
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

    def _schedule_behavior(self, world: 'World', current_time: float, player: Optional['Player']) -> Optional[str]:
        """
        Moves the NPC based on its hourly schedule.

        Args:
            world: The game world instance.
            current_time: The current absolute time (not used directly here, time comes from TimePlugin).
            player: The player object (for visibility checks and message formatting).

        Returns:
            A message string if the player sees the NPC move, otherwise None.
        """
        # Get the current game hour from the TimePlugin service
        time_plugin = world.game.plugin_manager.get_plugin("time_plugin") if world.game and world.game.plugin_manager else None
        if not time_plugin:
            # print("[Schedule Behavior] TimePlugin not found.") # Debug
            return None # Cannot determine schedule without time

        current_hour = time_plugin.hour

        # Get the NPC's schedule (assuming it's stored in self.schedule)
        npc_schedule = getattr(self, 'schedule', {})
        if not npc_schedule:
            # print(f"[Schedule Behavior] NPC {self.name} has no schedule.") # Debug
            return None # No schedule defined for this NPC

        # Find the relevant schedule entry for the current hour
        schedule_entry = None
        # Find the latest schedule time <= current_hour
        scheduled_hour = -1
        for hour_key in sorted(npc_schedule.keys(), reverse=True):
             try:
                  hour_int = int(hour_key) # Ensure key is integer
                  if hour_int <= current_hour:
                       schedule_entry = npc_schedule[hour_key]
                       scheduled_hour = hour_int
                       break
             except ValueError:
                  continue # Skip non-integer keys

        # If no entry found for <= current_hour, wrap around to the latest entry of the previous day
        if schedule_entry is None and npc_schedule:
            latest_hour_key = max(npc_schedule.keys(), key=lambda k: int(k) if k.isdigit() else -1)
            if latest_hour_key.isdigit(): # Check if the key is actually a digit
                 schedule_entry = npc_schedule[latest_hour_key]
                 scheduled_hour = int(latest_hour_key) # Store the hour


        if not schedule_entry or not isinstance(schedule_entry, dict):
            # print(f"[Schedule Behavior] No valid schedule entry for {self.name} at hour {current_hour}.") # Debug
            return None # No valid schedule entry found for this time

        # --- Determine Destination and Activity ---
        # Use .get() for safe access
        destination_region_id = schedule_entry.get("region_id", self.current_region_id)
        destination_room_id = schedule_entry.get("room_id") # Required for movement
        activity = schedule_entry.get("activity", "idle")

        # Update NPC's current activity state
        if hasattr(self, 'ai_state'):
             self.ai_state["current_activity"] = activity
             # Optional: Update specific flags like is_sleeping, is_working etc.
             for state_flag in ["is_sleeping", "is_eating", "is_working", "is_socializing"]:
                 self.ai_state[state_flag] = (activity == state_flag.replace("is_", ""))


        # --- Check if Movement is Needed ---
        if not destination_room_id:
            # print(f"[Schedule Behavior] Schedule entry for {self.name} at hour {current_hour} missing room_id.") # Debug
            return None # Cannot move without a destination room

        # Ensure region is valid if provided, otherwise use current
        if destination_region_id is None:
            destination_region_id = self.current_region_id

        # Check if already at the destination
        if (self.current_region_id == destination_region_id and
            self.current_room_id == destination_room_id):
            # print(f"[Schedule Behavior] {self.name} already at scheduled location for hour {current_hour}.") # Debug
            # Already at location, no movement message needed
            # Could potentially return an activity message if player is present?
            # player_loc = (player.current_region_id, player.current_room_id) if player else None
            # my_loc = (self.current_region_id, self.current_room_id)
            # if player and player_loc == my_loc:
            #     # Maybe return "NPC continues {activity}" if activity changed? Complex to track.
            #     pass
            return None

        # --- Movement Required ---
        # Basic validation: Does the target location exist?
        target_region = world.get_region(destination_region_id)
        if not target_region or not target_region.get_room(destination_room_id):
            print(f"[Schedule Behavior] Warning: Scheduled destination {destination_region_id}:{destination_room_id} for {self.name} does not exist.") # Warning
            return None # Cannot move to non-existent location

        # --- Perform the Move ---
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id

        self.current_region_id = destination_region_id
        self.current_room_id = destination_room_id

        # Note: We don't know the *exact* path/direction taken for a scheduled move.
        # The messages will be more generic.

        # --- Generate Message if Player Can See ---
        departure_message = None
        arrival_message = None

        # Need player object to format name correctly and check visibility
        if player and player.is_alive:
            player_loc = (player.current_region_id, player.current_room_id)
            old_npc_loc = (old_region_id, old_room_id)
            new_npc_loc = (self.current_region_id, self.current_room_id)

            npc_display_name = format_name_for_display(player, self, start_of_sentence=True)
            activity_phrase = f" to {activity}" if activity and activity != "idle" else ""

            # Check if player sees departure
            if player_loc == old_npc_loc:
                departure_message = f"{npc_display_name} leaves{activity_phrase}."

            # Check if player sees arrival
            elif player_loc == new_npc_loc:
                arrival_message = f"{npc_display_name} arrives{activity_phrase}."

        # Return the relevant message (priority to departure if both seen?)
        # Usually player is only in one place, so only one will be non-None.
        return departure_message if departure_message else arrival_message

    def _wander_behavior(self, world: 'World', current_time: float, player: Optional['Player']) -> Optional[str]:
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

        if not valid_exits: return None
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

        # Return message if player can see
        if player and world.current_region_id == old_region_id and world.current_room_id == old_room_id:
            return format_npc_departure_message(self, direction, player) # <<< PASS PLAYER
        if player and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
            return format_npc_arrival_message(self, direction, player) # <<< PASS PLAYER
        return None

    def _patrol_behavior(self, world: 'World', current_time: float, player: Optional['Player']) -> Optional[str]:
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
                return self._wander_behavior(world, current_time, player)

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
        if player and world.current_region_id == old_region_id and world.current_room_id == old_room_id:
            return format_npc_departure_message(self, chosen_direction, player) # <<< PASS PLAYER
        if player and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id:
            return format_npc_arrival_message(self, chosen_direction, player) # <<< PASS PLAYER
        return None

    def _follower_behavior(self, world: 'World', current_time: float, player: Optional['Player']) -> Optional[str]:
        target_id_to_follow = self.follow_target # Explicit follow target

        if not target_id_to_follow and self.behavior_type == 'minion':
            # Minion implicitly follows owner if no explicit target
            target_id_to_follow = self.properties.get("owner_id")

        if not target_id_to_follow: return None # No one to follow

        # Find the target (check player first, then NPCs)
        target_entity = None
        if world.player and world.player.obj_id == target_id_to_follow:
            target_entity = world.player
        else:
            target_entity = world.get_npc(target_id_to_follow)

        if not target_entity or not target_entity.is_alive:
            if self.behavior_type == 'minion': self.despawn(world, silent=True) # Despawn if owner gone
            self.follow_target = None # Stop following
            return None

        target_region_id = target_entity.current_region_id
        target_room_id = target_entity.current_room_id

        # If already in the same room, do nothing
        if (self.current_region_id == target_region_id and
            self.current_room_id == target_room_id):
            return None

        # Find path to target
        path = world.find_path(self.current_region_id, self.current_room_id,
                                target_region_id, target_room_id)

        if path and len(path) > 0:
            # ... (existing movement logic: get direction, destination, check safe zones) ...
            direction = path[0]
            region = world.get_region(self.current_region_id)
            if not region: return None
            room = region.get_room(self.current_room_id)
            if not room or direction not in room.exits: return None
            destination = room.exits[direction]
            next_region_id = self.current_region_id
            next_room_id = destination
            if ":" in destination: next_region_id, next_room_id = destination.split(":")

            # Safety check (hostile followers shouldn't enter safe zones)
            is_hostile = (self.faction == "hostile")
            if is_hostile and world.is_location_safe(next_region_id, next_room_id):
                return None # Don't take the step

            # --- Proceed with movement ---
            old_region_id = self.current_region_id
            old_room_id = self.current_room_id
            self.current_region_id = next_region_id
            self.current_room_id = next_room_id

            if player and player.current_region_id == old_region_id and player.current_room_id == old_room_id:
                return format_npc_departure_message(self, direction, player) # <<< PASS VIEWER
            if player.current_region_id == self.current_region_id and player.current_room_id == self.current_room_id:
                return format_npc_arrival_message(self, direction, player) # <<< PASS VIEWER
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
        Try to perform a combat action (attack or spell) based on cooldowns and chance.
        Awards XP to player if minion gets kill, and handles loot drops.
        """
        # General action cooldown check
        if current_time - self.last_combat_action < self.combat_cooldown:
            return None

        # --- Target Validation ---
        player = getattr(world, 'player', None) # Get player reference
        target = self.combat_target
        if not target:
            # Try finding a valid target from the set if primary is invalid/missing
            valid_targets_in_set = [t for t in self.combat_targets
                                    if hasattr(t, "is_alive") and t.is_alive
                                    and hasattr(t, "health") and t.health > 0
                                    and hasattr(t, 'current_region_id')
                                    and t.current_region_id == self.current_region_id
                                    and t.current_room_id == self.current_room_id]
            if not valid_targets_in_set:
                # print(f"[NPC Debug] {self.name}: No valid targets left in room. Exiting combat.") # Debug
                self.exit_combat()
                return None
            target = random.choice(valid_targets_in_set)
            self.combat_target = target # Assign the new primary target

        # --- Spellcasting Logic ---
        chosen_spell = None
        if self.usable_spells and random.random() < self.spell_cast_chance:
            available_spells = []
            for spell_id in self.usable_spells:
                spell = get_spell(spell_id)
                cooldown_end = self.spell_cooldowns.get(spell_id, 0)
                if spell and current_time >= cooldown_end:
                    # Simplified target type check for brevity
                    is_enemy = target.faction != self.faction
                    is_friendly = (target == self or target.faction == self.faction)
                    if (spell.target_type == "enemy" and is_enemy) or \
                       (spell.target_type == "friendly" and is_friendly) or \
                       (spell.target_type == "self"):
                         available_spells.append(spell)
            if available_spells: chosen_spell = random.choice(available_spells)


        # --- Perform Action ---
        action_result: Optional[Dict[str, Any]] = None # Explicitly type hint
        target_defeated_this_turn = False

        if chosen_spell:
            spell_target = target if chosen_spell.target_type != "self" else self
            action_result = self.cast_spell(chosen_spell, spell_target, current_time)
            if action_result: target_defeated_this_turn = action_result.get("target_defeated", False)
            self.last_combat_action = current_time
            # print(f"[NPC Debug] {self.name} CAST {chosen_spell.name} on {spell_target.name}. Target defeated: {target_defeated_this_turn}") # Debug
        else:
            if self.can_attack(current_time):
                action_result = self.attack(target)
                if action_result: target_defeated_this_turn = action_result.get("target_defeated", False)
                self.last_attack_time = current_time
                self.last_combat_action = current_time
                # print(f"[NPC Debug] {self.name} ATTACKED {target.name}. Target defeated: {target_defeated_this_turn}") # Debug
            # else:
                # print(f"[NPC Debug] {self.name} Attack on cooldown.") # Debug


        # --- Process Message and Target Death ---
        # Initialize messages
        message_to_return = ""
        base_action_message = action_result.get("message") if action_result else ""
        loot_message = ""
        xp_message = ""
        level_up_message = ""

        # Log the base action internally
        if base_action_message:
            self._add_combat_message(base_action_message)
            message_to_return += base_action_message # Start building the return message

        # Handle target defeat
        if target_defeated_this_turn:
            self.exit_combat(target)
            if self.combat_target == target: self.combat_target = None

            # --- Call target.die() and Format Loot Message (REVISED) ---
            dropped_loot_items = []
            loot_message = "" # Initialize loot message

            # Check if the target is NOT the player before calling die() with world context
            # Also ensure the target actually has a 'die' method
            if target is not player and hasattr(target, 'die'):
                try:
                    # Only call die with world for non-player targets (like other NPCs)
                    # that are expected to drop loot into the world.
                    dropped_loot_items = target.die(self.world) # Call NPC.die() or similar
                except TypeError:
                    # Fallback if a non-player target's die() doesn't take world (less likely for NPCs)
                    target.die() # Call without world
                    print(f"Warning: target {target.name}'s die() method might not accept world argument.")
                except Exception as e:
                    print(f"Error calling die() on target {target.name}: {e}")

                # Format loot message ONLY if items were dropped (relevant for NPCs)
                if dropped_loot_items:
                    # Need viewer context for formatting
                    viewer = self.world.player if self.world and hasattr(self.world, 'player') else None
                    # --- Make sure format_loot_drop_message is imported ---
                    from utils.utils import format_loot_drop_message
                    # ---
                    loot_message = format_loot_drop_message(viewer, target, dropped_loot_items)

            # If the target WAS the player, player.die() was already called internally via take_damage.
            # No loot is generated by Player.die(), so dropped_loot_items remains empty.

            # Log and append loot message if generated
            if loot_message:
                self._add_combat_message(loot_message) # Log internally
                if message_to_return: message_to_return += "\n" # Add newline if action message exists
                message_to_return += loot_message # Append to return message
            # --- End Revised Loot Handling ---

            # --- Check for Player XP Gain (Minion Kill) ---
            is_player_minion = (self.properties.get("is_summoned", False) and
                                player and
                                self.properties.get("owner_id") == player.obj_id)

            if is_player_minion:
                # Calculate XP using PLAYER's level
                target_max_hp = getattr(target, 'max_health', 10)
                target_lvl = getattr(target, 'level', 1)
                xp_gained = calculate_xp_gain(player.level, target_lvl, target_max_hp)

                if xp_gained > 0:
                    leveled_up = player.gain_experience(xp_gained)
                    xp_message = f"{FORMAT_SUCCESS}Your {self.name} earns you {xp_gained} experience!{FORMAT_RESET}"
                    self._add_combat_message(xp_message) # Log internally
                    if message_to_return: message_to_return += "\n"
                    message_to_return += xp_message # Append to return message

                    if leveled_up:
                        level_up_message = f"{FORMAT_HIGHLIGHT}You leveled up to level {player.level}!{FORMAT_RESET}"
                        self._add_combat_message(level_up_message) # Log internally
                        if message_to_return: message_to_return += "\n"
                        message_to_return += level_up_message # Append to return message
            # --- End Player XP Gain ---

        # --- Return message ONLY if the player is in the room AND a message was generated ---
        player_present = player and player.is_alive and \
                         world.current_region_id == self.current_region_id and \
                         world.current_room_id == self.current_room_id

        return message_to_return if player_present and message_to_return else None

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

            # Ensure world and player references are available (needed for formatting)
            viewer = self.world.player if self.world and hasattr(self.world, 'player') else None

            # Apply effect, passing the viewer context
            value, effect_message = apply_spell_effect(self, target, spell, viewer) # Pass viewer

            # Format the initial cast message (usually doesn't need coloring)
            formatted_caster_name = format_name_for_display(viewer, self, start_of_sentence=True) if viewer else self.name
            base_cast_message = spell.format_cast_message(self) # This uses the *plain* name
            # Replace plain name with formatted name in cast message
            formatted_cast_message = base_cast_message.replace(self.name, formatted_caster_name, 1)

            # The effect_message now contains correctly formatted names relative to the viewer
            full_message = formatted_cast_message + "\n" + effect_message

            # --- Check for target death AFTER applying effect ---
            target_defeated = False
            if spell.effect_type == "damage" and hasattr(target, "health") and target.health <= 0:
                 if hasattr(target, 'is_alive'): target.is_alive = False
                 target_defeated = True
                 # We don't need to exit combat here; try_attack handles that
            # --- End Check ---

            return {
                "success": True,
                "message": full_message,
                "cast_message": formatted_cast_message,
                "effect_message": effect_message,
                "target": getattr(target, 'name', 'target'),
                "value": value,
                "spell": spell.name,
                "target_defeated": target_defeated # <<< INCLUDE FLAG HERE
            }

    def despawn(self, world: 'World', silent: bool = False) -> Optional[str]:
        """Removes a summoned creature from the world and notifies the owner."""
        # Check the property set by the factory/effect
        if not self.properties.get("is_summoned"):
            return None # Not a summon, do nothing

        self.is_alive = False # Mark for removal by world update loop

        # Try to get owner_id from properties if not set directly (might happen during load?)
        owner_id = self.owner_id or self.properties.get("owner_id")

        # Notify Owner to remove from active list
        if owner_id and world:
            # Assuming single player for now
            owner = world.player
            if owner and owner.obj_id == owner_id and hasattr(owner, 'active_summons'):
                removed = False
                for spell_id, summon_ids in list(owner.active_summons.items()): # Iterate copy
                    if self.obj_id in summon_ids:
                        try:
                            summon_ids.remove(self.obj_id)
                            removed = True
                            if not summon_ids: # Remove spell key if list is empty
                                del owner.active_summons[spell_id]
                            break # Found and removed
                        except ValueError: pass # Should not happen if check passes
                # if removed: print(f"[Debug] Removed summon {self.obj_id} from owner {owner_id}")
                # else: print(f"[Debug] Failed to find summon {self.obj_id} in owner's list {owner.active_summons}")

        # Return message to be displayed (if not silent)
        if not silent:
            return f"Your {self.name} crumbles to dust."
        return None

    def update(self, world, current_time: float) -> Optional[str]:
        """
        Update the NPC's state, perform actions, and process effects.
        """
        player = getattr(world, 'player', None)
        # Calculate time delta since last World update (approximate)
        time_delta = WORLD_UPDATE_INTERVAL # Use world update interval as rough delta

        # --- Process Active Effects (Similar to Player) ---
        effects_processed_this_tick = []
        expired_effects_indices = []
        effect_messages_for_player = [] # Messages relevant if player sees the NPC

        # Check if player is present *before* iterating effects
        player_present = (
            player and player.is_alive and
            self.current_region_id == player.current_region_id and
            self.current_room_id == player.current_room_id
        )

        # Iterate backwards for safe removal
        if self.is_alive: # Only process effects if alive
            for i in range(len(self.active_effects) - 1, -1, -1):
                effect = self.active_effects[i]
                effect_id = effect.get("id")
                if not effect_id or effect_id in effects_processed_this_tick: continue
                effects_processed_this_tick.append(effect_id)

                # 1. Update Duration
                effect["duration_remaining"] -= time_delta

                # 2. Check Expiration
                if effect["duration_remaining"] <= 0:
                    expired_effects_indices.append(i)
                    if player_present: # Only generate message if player sees it
                        effect_messages_for_player.append(f"{FORMAT_HIGHLIGHT}The {effect.get('name', 'effect')} on {self.name} wears off.{FORMAT_RESET}")
                    continue

                # 3. Process Ticks (DoTs)
                if effect.get("type") == "dot":
                    tick_interval = effect.get("tick_interval", EFFECT_DEFAULT_TICK_INTERVAL)
                    last_tick = effect.get("last_tick_time", 0)

                    if current_time - last_tick >= tick_interval:
                        damage = effect.get("damage_per_tick", 0)
                        dmg_type = effect.get("damage_type", "unknown")
                        if damage > 0:
                            damage_taken = self.take_damage(damage, dmg_type) # Apply damage
                            effect["last_tick_time"] = current_time # Update tick time

                            if player_present: # Only generate message if player sees it
                                if damage_taken > 0:
                                    effect_messages_for_player.append(f"{self.name} takes {damage_taken} {dmg_type} damage from {effect.get('name', 'effect')}.")
                                # else: Optional message if resisted? Might be too spammy.

                            # Check for death from DoT
                            if not self.is_alive:
                                if player_present:
                                    effect_messages_for_player.append(f"{FORMAT_ERROR}{self.name} succumbs to the {effect.get('name', 'effect')}!{FORMAT_RESET}")
                                # Handle death - loot/XP should be handled elsewhere (e.g., when `is_alive` is checked later or by the effect source)
                                # For now, just break effect processing loop if dead
                                break


        # Remove expired effects after iteration
        for index in sorted(expired_effects_indices, reverse=True):
            if 0 <= index < len(self.active_effects):
                del self.active_effects[index]

        # --- Combine effect messages with AI messages ---
        # Run the normal AI logic *after* effect processing
        ai_message = None
        if self.is_alive: # Don't run AI if DoT killed the NPC
            # ... (existing NPC AI logic: check idle, minion logic, trading, combat, movement) ...
            # Replace the existing 'return None' or 'return combat_message' etc.
            # with assigning the result to `ai_message`
            if self.behavior_type == "minion":
                 ai_message = self._handle_minion_ai(world, current_time, player) # Encapsulate minion logic
            else:
                 ai_message = self._handle_standard_ai(world, current_time, player) # Encapsulate standard logic

        # Combine messages, prioritizing AI action message if both exist
        final_message = ""
        if ai_message:
            final_message += ai_message
        if effect_messages_for_player:
            if final_message: final_message += "\n" # Add separator
            final_message += "\n".join(effect_messages_for_player)

        return final_message if final_message else None # Return combined message or None

    # --- NEW: Helper methods to organize AI ---
    def _handle_minion_ai(self, world, current_time, player):
         # ... (Cut and paste ALL the logic previously under `if self.behavior_type == "minion":`) ...
         # Remember to return the message string or None from this helper.
         # --- Start Minion Logic (Copied from original update) ---
         owner = player
         if not owner or owner.obj_id != self.properties.get("owner_id"):
              self.despawn(world, silent=True); return None
         duration = self.properties.get("summon_duration", 0)
         created = self.properties.get("creation_time", 0)
         if duration > 0 and current_time > created + duration:
              despawn_message = self.despawn(world)
              player = world.player # Re-get player inside scope if needed
              if despawn_message and player and self.current_region_id == player.current_region_id and self.current_room_id == player.current_room_id: return despawn_message
              return None
         owner_loc = (owner.current_region_id, owner.current_room_id)
         my_loc = (self.current_region_id, self.current_room_id)
         if self.in_combat:
              valid_targets = [t for t in self.combat_targets if t and t.is_alive and hasattr(t, 'current_region_id') and t.current_region_id == self.current_region_id and t.current_room_id == self.current_room_id]
              if not valid_targets: self.exit_combat(); # Exit combat handled here, no message needed from here
              else:
                   target_to_attack = None
                   if owner.in_combat and owner.combat_target and owner.combat_target in valid_targets: target_to_attack = owner.combat_target
                   else:
                        targets_attacking_owner = [t for t in valid_targets if hasattr(t, 'combat_targets') and owner in t.combat_targets]
                        if targets_attacking_owner: target_to_attack = random.choice(targets_attacking_owner)
                        elif self.combat_target and self.combat_target in valid_targets: target_to_attack = self.combat_target
                        else: target_to_attack = random.choice(valid_targets)
                   self.combat_target = target_to_attack
                   return self.try_attack(world, current_time) # try_attack returns message if player present
              return None # Exited combat or took combat action
         elif my_loc != owner_loc:
              move_cooldown = self.properties.get("move_cooldown", 5)
              if current_time - self.last_moved >= move_cooldown:
                   self.follow_target = owner.obj_id; follow_message = self._follower_behavior(world, current_time, owner); self.follow_target = None
                   if follow_message: self.last_moved = current_time
                   return follow_message
              else: return None
         elif my_loc == owner_loc:
              if owner.in_combat and owner.combat_target and owner.combat_target.is_alive:
                   target_npc = owner.combat_target
                   if target_npc in world.get_npcs_in_room(self.current_region_id, self.current_room_id):
                        self.enter_combat(target_npc); self.combat_target = target_npc
                        target_name_fmt = format_name_for_display(owner, target_npc)
                        return f"{self.name} moves to assist against {target_name_fmt}!"
              else:
                   npcs_in_room = world.get_npcs_in_room(self.current_region_id, self.current_room_id)
                   intercept_target = None
                   for npc in npcs_in_room:
                        if npc.faction == "hostile" and npc.is_alive and hasattr(npc, 'combat_targets') and owner in npc.combat_targets: intercept_target = npc; break
                   if intercept_target:
                        self.enter_combat(intercept_target); self.combat_target = intercept_target
                        npc_name_fmt = format_name_for_display(owner, intercept_target)
                        return f"{self.name} intercepts {npc_name_fmt} attacking you!"
                   if not self.in_combat:
                        hostile_target_found = None
                        for potential_target in npcs_in_room:
                             if potential_target.faction == "hostile" and potential_target.is_alive: hostile_target_found = potential_target; break
                        if hostile_target_found:
                             self.enter_combat(hostile_target_found); self.combat_target = hostile_target_found
                             target_name_fmt = format_name_for_display(owner, hostile_target_found)
                             return f"{self.name} moves to attack {target_name_fmt}!"
         return None # Idle
         # --- End Minion Logic ---

    def _handle_standard_ai(self, world, current_time, player):
        # ... (Cut and paste the logic previously under the `else:` block for non-minions) ...
        # Remember to return the message string or None.
        # --- Start Standard Logic (Copied) ---
        if self.is_trading:
            if (player and player.trading_with == self.obj_id and
                player.current_region_id == self.current_region_id and
                player.current_room_id == self.current_room_id): return None # Still trading
            else: self.is_trading = False; # print(f"NPC {self.name} resuming AI")

        combat_message = None
        if self.in_combat:
            combat_message = self.try_attack(world, current_time) # This now returns message if needed
            if self.is_alive and self.health < self.max_health * self.flee_threshold:
                # ... (flee logic - unchanged, but returns message if player sees) ...
                # IMPORTANT: Flee logic needs to return the generated message string or None
                flee_message = self._try_flee(world, current_time, player)
                if flee_message: return flee_message # Return flee message if successful and seen
            if self.in_combat: return combat_message # Return combat message if still fighting and action happened

        elif (self.faction == "hostile" and self.aggression > 0 and
              player and player.is_alive and
              world.current_region_id == self.current_region_id and
              world.current_room_id == self.current_room_id):
            if random.random() < self.aggression:
                self.enter_combat(player)
                action_result_message = self.try_attack(world, current_time)
                if action_result_message: return action_result_message # Show attack message
                else: return f"{format_target_name(player, self)} prepares to attack you!" # Show engage message

        # If combat message generated above (e.g., initial aggro), return it
        # This check might be redundant now as returns happen inside the blocks
        # if combat_message: return combat_message

        if current_time - self.last_moved < self.move_cooldown: return None # Wait for move cooldown

        move_message = None
        if self.behavior_type == "wanderer": move_message = self._wander_behavior(world, current_time, player)
        elif self.behavior_type == "patrol": move_message = self._patrol_behavior(world, current_time, player)
        elif self.behavior_type == "follower": move_message = self._follower_behavior(world, current_time, player)
        elif self.behavior_type == "scheduled": move_message = self._schedule_behavior(world, current_time, player)
        elif self.behavior_type == "aggressive": move_message = self._wander_behavior(world, current_time, player) # Aggressive just wanders for now

        if move_message: self.last_moved = current_time # Update timer *if* movement occurred
        return move_message # Return movement message or None
        # --- End Standard Logic ---

    def _try_flee(self, world, current_time, player):
        from player import Player
        """Handles the fleeing logic and returns a message if seen by player."""
        should_flee = True
        player_target = next((t for t in self.combat_targets if isinstance(t, Player)), None)
        if player_target and hasattr(player_target, "health") and player_target.health <= 10: # Don't flee weak player
            should_flee = False

        if should_flee:
            region = world.get_region(self.current_region_id)
            if region:
                room = region.get_room(self.current_room_id)
                if room and room.exits:
                    valid_exits = [d for d, dest in room.exits.items() if not world.is_location_safe(self.current_region_id, dest.split(':')[-1])] if self.faction == 'hostile' else list(room.exits.keys())
                    if valid_exits:
                        direction = random.choice(valid_exits)
                        destination = room.exits[direction]
                        old_region_id, old_room_id = self.current_region_id, self.current_room_id
                        new_region_id, new_room_id = old_region_id, destination
                        if ":" in destination: new_region_id, new_room_id = destination.split(":")

                        # Perform move
                        self.current_region_id = new_region_id
                        self.current_room_id = new_room_id
                        self.exit_combat() # Exit combat state
                        self.last_moved = current_time

                        # Check if player saw the flee
                        player_present = (
                            player and player.is_alive and
                            old_region_id == player.current_region_id and
                            old_room_id == player.current_room_id
                        )
                        if player_present:
                            npc_display_name = format_name_for_display(player, self, start_of_sentence=True)
                            return f"{npc_display_name} flees to the {direction}!"
        return None # Did not flee or player didn't see
