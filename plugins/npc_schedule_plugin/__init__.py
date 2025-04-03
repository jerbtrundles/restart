"""
plugins/npc_schedule_plugin/__init__.py
A fixed and simplified NPC scheduling plugin that makes NPCs wander during the day
and gather at taverns/social areas at night.
"""
from typing import Dict, Any, List, Optional
from plugins.plugin_system import PluginBase
import random
import time

class NPCSchedulePlugin(PluginBase):
    """
    Improved NPC movement and scheduling system.
    Makes NPCs wander during the day and gather socially at night.
    """
    
    plugin_id = "npc_schedule_plugin"
    plugin_name = "Improved NPC Scheduler"
    
    def __init__(self, world=None, command_processor=None, event_system=None, data_provider=None, service_locator=None):
        """Initialize the improved NPC plugin."""
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator
        
        # Import config from config.py
        from .config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG.copy()
        
        # Track time info
        self.current_hour = 12
        self.current_period = "day"
        
        # Keep track of room types
        self.taverns = []       # Places to gather at night
        self.social_areas = []  # Alternative gathering places
        self.home_locations = {} # NPC ID -> home location
        
        # Movement tracking
        self.last_update_time = 0
        self.movement_count = 0
    
    def initialize(self):
        """Initialize the plugin."""
        # Subscribe to time events
        if self.event_system:
            self.event_system.subscribe("time_data", self._on_time_data)
            self.event_system.subscribe("hour_changed", self._on_hour_changed)
        
        # Register commands
        self._register_commands()
        
        # Discover key locations
        self._discover_locations()
        
        # Initialize NPCs
        self._initialize_npcs()
        
        # Debug message
        tavern_count = len(self.taverns)
        social_count = len(self.social_areas)
        print(f"Improved NPC plugin initialized with {tavern_count} taverns and {social_count} social areas")
        
        # Force an initial update
        self._update_npcs(force=True)
    
    def _register_commands(self):
        """Register plugin commands."""
        # Import and register commands from commands.py
        from .commands import register_commands
        register_commands(self)
    
    def _on_time_data(self, event_type, data):
        """Handle time data updates."""
        self.current_hour = data.get("hour", 12)
        self.current_period = data.get("time_period", "day")
    
    def _on_hour_changed(self, event_type, data):
        """Handle hourly updates."""
        hour = data.get("hour", 0)
        self.current_hour = hour
        
        # Update time period (day/night)
        if hour >= self.config["day_start_hour"] and hour < self.config["night_start_hour"]:
            self.current_period = "day"
        else:
            self.current_period = "night"
        
        # Force an update at period changes
        if hour == self.config["day_start_hour"] or hour == self.config["night_start_hour"]:
            self._update_npcs(force=True)
            
            # Send message about period change
            if self.event_system:
                if hour == self.config["day_start_hour"]:
                    self.event_system.publish("display_message", "As morning arrives, people begin to move about for the day.")
                else:
                    self.event_system.publish("display_message", "As night falls, people head to taverns and gathering places.")
    
    def _discover_locations(self):
        """Discover taverns, social areas, and other key locations in the world."""
        if not self.world:
            return
        
        # Clear existing locations
        self.taverns = []
        self.social_areas = []
        
        # Examine all rooms in the world
        for region_id, region in self.world.regions.items():
            for room_id, room in region.rooms.items():
                room_name = room.name.lower()
                
                # Identify taverns
                if any(term in room_name for term in ["tavern", "inn", "pub", "bar"]):
                    self.taverns.append({
                        "region_id": region_id,
                        "room_id": room_id,
                        "name": room.name
                    })
                
                # Identify social areas
                elif any(term in room_name for term in ["hall", "square", "garden", "plaza", "center"]):
                    self.social_areas.append({
                        "region_id": region_id,
                        "room_id": room_id,
                        "name": room.name
                    })
        
        # If no taverns found, use social areas as fallback
        if not self.taverns and self.social_areas:
            self.taverns = self.social_areas.copy()
        
        # If no social areas at all, create a default from the first available room
        if not self.taverns and not self.social_areas and self.world.regions:
            first_region = next(iter(self.world.regions.values()))
            if first_region.rooms:
                first_room = next(iter(first_region.rooms.values()))
                default_area = {
                    "region_id": next(iter(self.world.regions.keys())),
                    "room_id": next(iter(first_region.rooms.keys())),
                    "name": first_room.name
                }
                self.taverns.append(default_area)
                self.social_areas.append(default_area)
    
    def _initialize_npcs(self):
        """Initialize non-hostile NPCs with proper movement settings."""
        if not self.world:
            return

        for obj_id, npc in self.world.npcs.items():
            # *** ADD THIS CHECK ***
            # Skip hostile NPCs (monsters) - they don't follow schedules
            if npc.faction == "hostile":
                continue
            # *** END CHECK ***

            # Store original behavior if not already done
            if not hasattr(npc, "ai_state"):
                npc.ai_state = {}
            if "original_behavior_type" not in npc.ai_state:
                npc.ai_state["original_behavior_type"] = getattr(npc, "behavior_type", "wanderer")

            # Set behavior to wanderer (we'll handle scheduling ourselves)
            # Only do this for non-hostile NPCs now
            npc.behavior_type = "wanderer"

            # Store current home location
            self.home_locations[obj_id] = {
                "region_id": npc.current_region_id,
                "room_id": npc.current_room_id
            }

            # Set a reasonable move cooldown
            npc.move_cooldown = random.randint(5, 15)

            # Initialize wander chance based on time period
            if self.current_period == "day":
                npc.wander_chance = self.config["day_wander_chance"]
            else:
                npc.wander_chance = self.config["night_wander_chance"]

            # Add activity tracking
            if "current_activity" not in npc.ai_state:
                activity = random.choice(self.config["day_activities"]) if self.current_period == "day" else random.choice(self.config["night_activities"])
                npc.ai_state["current_activity"] = activity
    
    def _get_night_destination(self, obj_id):
        """Get a destination for an NPC at night (tavern or social area)."""
        # Try to find a tavern
        if self.taverns:
            return random.choice(self.taverns)
        
        # Fallback to social areas
        elif self.social_areas:
            return random.choice(self.social_areas)
        
        # Last resort - use home location
        elif obj_id in self.home_locations:
            return self.home_locations[obj_id]
        
        # No suitable destination found
        return None
    
    def _update_npcs(self, force=False):
        """Update non-hostile NPC behavior based on time period."""
        if not self.world:
            return

        current_time = time.time()

        # Only update at specified interval unless forced
        if not force and (current_time - self.last_update_time < self.config["update_interval"]):
            return

        self.last_update_time = current_time
        self.movement_count = 0 # Reset movement count for this update cycle

        # Loop through all NPCs and update their behavior
        for obj_id, npc in self.world.npcs.items():
            # *** ADD THIS CHECK ***
            # Skip hostile NPCs (monsters) - they don't follow schedules
            if npc.faction == "hostile":
                continue
            # *** END CHECK ***

            # Skip NPCs that are busy with activities defined by other means (e.g., combat)
            # Use getattr for safety in case ai_state doesn't exist yet
            if getattr(npc, 'in_combat', False) or getattr(npc, 'ai_state', {}).get("is_sleeping") or getattr(npc, 'ai_state', {}).get("is_busy"):
                 continue

            is_day = self.current_period == "day"

            # --- Day Logic ---
            if is_day:
                # Set appropriate wander chance for the day
                npc.wander_chance = self.config["day_wander_chance"]

                # Optionally change daytime activity occasionally
                if random.random() < 0.1: # e.g., 10% chance per update cycle
                     npc.ai_state["current_activity"] = random.choice(self.config["day_activities"])

                # Let the NPC's own wander behavior handle the actual movement attempt
                # No direct movement code needed here for daytime wanderers

            # --- Night Logic ---
            else:
                # Set wander chance low for night
                npc.wander_chance = self.config["night_wander_chance"]

                # Determine night destination (tavern/social area)
                destination = self._get_night_destination(obj_id)
                if destination:
                    target_region = destination["region_id"]
                    target_room = destination["room_id"]

                    # If the NPC is not already at the destination
                    if npc.current_region_id != target_region or npc.current_room_id != target_room:
                        # Directly update NPC location to the gathering spot
                        old_region = npc.current_region_id
                        old_room = npc.current_room_id

                        npc.current_region_id = target_region
                        npc.current_room_id = target_room

                        # Assign a nighttime activity
                        npc.ai_state["current_activity"] = random.choice(self.config["night_activities"])

                        # Reset movement timer to allow immediate action in the new room if needed
                        npc.last_moved = current_time # Use current time to prevent immediate wander *out*

                        self.movement_count += 1

                        # Announce arrival/departure if player can see it
                        player_loc = (self.world.current_region_id, self.world.current_room_id)
                        old_npc_loc = (old_region, old_room)
                        new_npc_loc = (target_region, target_room)

                        if self.event_system:
                            if player_loc == old_npc_loc:
                                self.event_system.publish("display_message", f"{npc.name} leaves, heading towards {destination.get('name', 'a gathering place')}.")
                            elif player_loc == new_npc_loc:
                                self.event_system.publish("display_message", f"{npc.name} arrives at {destination.get('name', 'the gathering place')}, looking to {npc.ai_state['current_activity']}.")

                    else:
                        # If already at the destination, maybe change activity?
                        if random.random() < 0.2:
                             npc.ai_state["current_activity"] = random.choice(self.config["night_activities"])

        # Optionally log the number of NPCs moved this cycle for debugging
        # if self.movement_count > 0:
        #     print(f"NPC Scheduler moved {self.movement_count} NPCs to night locations.")
    
    def on_tick(self, current_time):
        """Update on each game tick."""
        self._update_npcs()
        
    def cleanup(self):
        """Clean up plugin resources."""
        # Restore original behaviors
        if self.world:
            for obj_id, npc in self.world.npcs.items():
                if hasattr(npc, "ai_state") and "original_behavior_type" in npc.ai_state:
                    npc.behavior_type = npc.ai_state["original_behavior_type"]
        
        # Unsubscribe from events
        if self.event_system:
            self.event_system.unsubscribe("time_data", self._on_time_data)
            self.event_system.unsubscribe("hour_changed", self._on_hour_changed)