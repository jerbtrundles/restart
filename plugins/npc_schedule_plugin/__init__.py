"""
plugins/npc_schedule_plugin/__init__.py
A fixed and simplified NPC scheduling plugin that makes NPCs wander during the day
and gather at taverns/social areas at night.
"""
from typing import Dict, Any, List, Optional
from plugins.plugin_system import PluginBase
import random
import time

from utils.utils import format_name_for_display

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
        """Update non-hostile NPC behavior based on time period, including vendor location affinity."""
        if not self.world: return
        current_time = time.time()

        if not force and (current_time - self.last_update_time < self.config["update_interval"]): return

        self.last_update_time = current_time
        self.movement_count = 0

        for obj_id, npc in self.world.npcs.items():
            # Skip hostile, trading, or busy NPCs (existing checks)
            if npc.faction == "hostile": continue
            if npc.is_trading: continue
            if getattr(npc, 'in_combat', False) or getattr(npc, 'ai_state', {}).get("is_sleeping") or getattr(npc, 'ai_state', {}).get("is_busy"): continue

            is_day = self.current_period == "day"
            is_vendor = npc.properties.get("is_vendor", False)
            work_location_str = npc.properties.get("work_location") # e.g., "town:market"

            # --- Day Logic ---
            if is_day:
                # --- Vendor Daytime Logic ---
                if is_vendor and work_location_str:
                    try:
                        # Parse work location
                        work_region_id, work_room_id = work_location_str.split(":")
                        is_at_work = (npc.current_region_id == work_region_id and npc.current_room_id == work_room_id)

                        if is_at_work:
                            # Vendor is at work, should stay put and work
                            npc.ai_state["current_activity"] = "working"
                            npc.wander_chance = 0.0 # Prevent wandering away
                            # No movement needed, skip to next NPC
                            continue
                        else:
                            # Vendor is NOT at work, move them there
                            # Check if enough time has passed since last move attempt
                            move_cooldown = npc.move_cooldown # Use NPC's specific cooldown
                            if current_time - npc.last_moved >= move_cooldown:
                                # --- Move NPC directly to work location ---
                                old_region = npc.current_region_id
                                old_room = npc.current_room_id

                                npc.current_region_id = work_region_id
                                npc.current_room_id = work_room_id
                                npc.ai_state["current_activity"] = "working"
                                npc.last_moved = current_time # Update last moved time
                                npc.wander_chance = 0.0 # Stay put once arrived

                                self.movement_count += 1

                                # Announce arrival/departure if player can see it
                                player_loc = (self.world.current_region_id, self.world.current_room_id)
                                old_npc_loc = (old_region, old_room)
                                new_npc_loc = (work_region_id, work_room_id)

                                if self.event_system:
                                    work_room_name = self.world.get_region(work_region_id).get_room(work_room_id).name if self.world.get_region(work_region_id) and self.world.get_region(work_region_id).get_room(work_room_id) else work_room_id

                                    npc_display_name = format_name_for_display(self.world.player, self)

                                    if player_loc == old_npc_loc:
                                        self.event_system.publish("display_message", f"{npc_display_name} leaves, heading to work at the {work_room_name}.")
                                    elif player_loc == new_npc_loc:
                                        self.event_system.publish("display_message", f"{npc_display_name} arrives at the {work_room_name} to work.")
                                # --- End Move ---
                                # Skip to next NPC after moving
                                continue
                            else:
                                # On cooldown, skip to next NPC
                                continue

                    except ValueError:
                        print(f"Warning: Invalid work_location format for vendor {npc.name}: '{work_location_str}'. Should be 'region:room'.")
                        # Fall through to default day behavior if format is wrong

                # --- Default Daytime Logic (Non-Vendors or Vendors without Work Location) ---
                npc.wander_chance = self.config["day_wander_chance"] # Regular wander chance
                if random.random() < 0.1:
                     npc.ai_state["current_activity"] = random.choice(self.config["day_activities"])
                # The actual wandering movement for these NPCs will be handled by their
                # base behavior type ('wanderer', 'patrol', etc.) called in World.update(),
                # respecting their individual move_cooldown.

            # --- Night Logic (Applies to ALL non-hostile, non-busy NPCs, including vendors) ---
            else: # It's night
                npc.wander_chance = self.config["night_wander_chance"] # Low wander chance

                destination = self._get_night_destination(obj_id)
                if destination:
                    target_region = destination["region_id"]
                    target_room = destination["room_id"]

                    # If the NPC is not already at the destination AND cooldown allows
                    move_cooldown = npc.move_cooldown
                    if (npc.current_region_id != target_region or npc.current_room_id != target_room) and \
                       (current_time - npc.last_moved >= move_cooldown):
                        # --- Move NPC directly to night destination ---
                        old_region = npc.current_region_id
                        old_room = npc.current_room_id

                        npc.current_region_id = target_region
                        npc.current_room_id = target_room
                        npc.ai_state["current_activity"] = random.choice(self.config["night_activities"])
                        npc.last_moved = current_time

                        self.movement_count += 1

                        # Announce arrival/departure (existing logic)
                        player_loc = (self.world.current_region_id, self.world.current_room_id)
                        old_npc_loc = (old_region, old_room)
                        new_npc_loc = (target_region, target_room)
                        if self.event_system:
                             dest_name = destination.get('name', 'a gathering place')
                             activity_name = npc.ai_state['current_activity']

                             npc_display_name = format_name_for_display(self.world.player, self)
                             
                             if player_loc == old_npc_loc: self.event_system.publish("display_message", f"{npc_display_name} leaves, heading towards {dest_name}.")
                             elif player_loc == new_npc_loc: self.event_system.publish("display_message", f"{npc_display_name} arrives at {dest_name}, looking to {activity_name}.")
                        # --- End Move ---
                        continue # Skip to next NPC after moving

                    elif npc.current_region_id == target_region and npc.current_room_id == target_room:
                        # Already at destination, maybe change activity
                        if random.random() < 0.2:
                             npc.ai_state["current_activity"] = random.choice(self.config["night_activities"])
                        # Stay put (don't wander away from night spot unless wander chance hits)
                        # The low night_wander_chance handles this implicitly
    
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