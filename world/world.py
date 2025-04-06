# world/world.py
from typing import Dict, List, Optional, Any, Tuple
import time
import json
import os
import uuid # For NPC instance IDs
import heapq # For pathfinding

# --- Core Imports ---
from core.config import DEFAULT_SAVE_FILE, FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, ITEM_TEMPLATE_DIR, NPC_TEMPLATE_DIR, REGION_DIR, SAVE_GAME_DIR # Use config
from player import Player
from world.region import Region
from world.room import Room
from items.item import Item
from items.key import Key
from items.inventory import Inventory
from npcs.npc import NPC
from utils.text_formatter import format_target_name

# --- Factory Imports ---
from items.item_factory import ItemFactory
from npcs.npc_factory import NPCFactory
# MonsterFactory might just use NPCFactory now
# from npcs.monster_factory import MonsterFactory

from utils.utils import _serialize_item_reference, format_name_for_display, get_article, simple_plural # If defined in utils/utils.py

class World:
    def __init__(self):
        # --- Static Definitions ---
        self.regions: Dict[str, Region] = {}
        self.item_templates: Dict[str, Dict[str, Any]] = {} # item_id -> template_data
        self.npc_templates: Dict[str, Dict[str, Any]] = {} # template_id -> template_data

        # --- Dynamic State ---
        self.player: Player = None # Loaded/Created later
        self.npcs: Dict[str, NPC] = {} # instance_id -> NPC object
        # Current location is now part of player state for saving, but world tracks it live
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None

        # --- Meta ---
        self.start_time = time.time()
        self.last_update_time = 0
        self.plugin_data = {}
        self.game = None # Link back to game manager

        # --- Load Definitions ---
        self._load_definitions()

    # --- Definition Loading ---
    def _load_definitions(self):
        """Loads static definitions (regions, items, npcs) from the data directory."""
        print("Loading definitions...")
        self._load_item_templates()
        self._load_npc_templates()
        self._load_regions()
        print("Definitions loaded.")

    def _load_item_templates(self):
        """Loads item templates from JSON files."""
        self.item_templates = {}
        if not os.path.isdir(ITEM_TEMPLATE_DIR):
            print(f"Warning: Item template directory not found: {ITEM_TEMPLATE_DIR}")
            return
        for filename in os.listdir(ITEM_TEMPLATE_DIR):
            if filename.endswith(".json"):
                path = os.path.join(ITEM_TEMPLATE_DIR, filename)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        for item_id, template_data in data.items():
                            if item_id in self.item_templates:
                                print(f"Warning: Duplicate item template ID '{item_id}' found in {filename}.")
                            # Basic validation
                            if "name" not in template_data or "type" not in template_data:
                                print(f"Warning: Item template '{item_id}' in {filename} is missing 'name' or 'type'. Skipping.")
                                continue
                            self.item_templates[item_id] = template_data
                    # print(f"Loaded item templates from {filename}")
                except Exception as e:
                    print(f"Error loading item templates from {path}: {e}")

    def _load_npc_templates(self):
        """Loads NPC templates from JSON files."""
        self.npc_templates = {}
        if not os.path.isdir(NPC_TEMPLATE_DIR):
            print(f"Warning: NPC template directory not found: {NPC_TEMPLATE_DIR}")
            return
        for filename in os.listdir(NPC_TEMPLATE_DIR):
            if filename.endswith(".json"):
                path = os.path.join(NPC_TEMPLATE_DIR, filename)
                try:
                    with open(path, 'r') as f:
                        data = json.load(f)
                        for template_id, template_data in data.items():
                            if template_id in self.npc_templates:
                                print(f"Warning: Duplicate NPC template ID '{template_id}' found in {filename}.")
                             # Basic validation
                            if "name" not in template_data:
                                print(f"Warning: NPC template '{template_id}' in {filename} is missing 'name'. Skipping.")
                                continue
                            self.npc_templates[template_id] = template_data
                    # print(f"Loaded NPC templates from {filename}")
                except Exception as e:
                    print(f"Error loading NPC templates from {path}: {e}")
        print(f"[NPC Templates] Loaded {len(self.npc_templates)} NPC templates.")

    def _load_regions(self):
        """Loads region and room definitions from JSON files."""
        self.regions = {}
        if not os.path.isdir(REGION_DIR):
            print(f"Warning: Region directory not found: {REGION_DIR}")
            return
        for filename in os.listdir(REGION_DIR):
            if filename.endswith(".json"):
                path = os.path.join(REGION_DIR, filename)
                try:
                    with open(path, 'r') as f:
                        region_data = json.load(f)
                        region_id = filename[:-5] # Use filename base as ID
                        region_data['obj_id'] = region_id # Add obj_id hint
                        region = Region.from_dict(region_data)
                        self.add_region(region_id, region)
                    # print(f"Loaded region '{region_id}' from {filename}")
                except Exception as e:
                    print(f"Error loading region from {path}: {e}")

    # --- Game State Management ---

    def initialize_new_world(self, start_region="town", start_room="town_square"):
         """Sets up the world for a new game."""
         print("Initializing new world state...")
         self.player = Player("Adventurer") # Create default player
         # Give player starting items (using templates)
         starter_dagger = ItemFactory.create_item_from_template("item_starter_dagger", self)
         potion = ItemFactory.create_item_from_template("item_healing_potion_small", self)
         if starter_dagger: self.player.inventory.add_item(starter_dagger)
         if potion: self.player.inventory.add_item(potion, 2) # Give 2 potions

         # Set starting location
         self.current_region_id = start_region
         self.current_room_id = start_room
         self.player.current_region_id = start_region # Also store on player
         self.player.current_room_id = start_room

         # Reset dynamic state
         self.npcs = {}
         for region in self.regions.values():
              for room in region.rooms.values():
                   room.items = [] # Clear dynamic items

         # Place initial NPCs and Items from definitions
         for region_id, region in self.regions.items():
              for room_id, room in region.rooms.items():
                   # Initial Items
                   for item_ref in getattr(room, 'initial_item_refs', []):
                        item_id = item_ref.get("item_id")
                        qty = item_ref.get("quantity", 1)
                        overrides = item_ref.get("properties_override", {})
                        if item_id:
                             item = ItemFactory.create_item_from_template(item_id, self, **overrides)
                             if item:
                                  # Add quantity separately if stackable
                                  if item.stackable:
                                       for _ in range(qty): room.add_item(item) # Add individual stackable items
                                  else:
                                       room.add_item(item) # Add single non-stackable item
                             else: print(f"Warning: Failed to create initial item '{item_id}' in {region_id}:{room_id}")

                   # Initial NPCs
                   for npc_ref in getattr(room, 'initial_npc_refs', []):
                        template_id = npc_ref.get("template_id")
                        instance_id = npc_ref.get("instance_id") # Use predefined instance ID
                        if not instance_id:
                             instance_id = f"{template_id}_{uuid.uuid4().hex[:8]}" # Generate if missing
                        if template_id and instance_id not in self.npcs: # Avoid duplicates
                             overrides = npc_ref.get("overrides", {})
                             # Set initial location
                             overrides["current_region_id"] = region_id
                             overrides["current_room_id"] = room_id
                             overrides["home_region_id"] = region_id # Initial pos is home
                             overrides["home_room_id"] = room_id
                             npc = NPCFactory.create_npc_from_template(template_id, self, instance_id, **overrides)
                             if npc:
                                  self.add_npc(npc) # Add to world.npcs
                             else: print(f"Warning: Failed to create initial NPC '{template_id}' (ID: {instance_id}) in {region_id}:{room_id}")

         self.start_time = time.time() # Reset start time
         self.last_update_time = 0
         self.plugin_data = {} # Reset plugin data
         print(f"New world initialized. Player at {start_region}:{start_room}")

    def load_save_game(self, filename: str = DEFAULT_SAVE_FILE) -> bool:
        """Loads dynamic game state from a save file using references."""
        save_path = self._resolve_load_path(filename, SAVE_GAME_DIR)
        if not save_path or not os.path.exists(save_path):
            print(f"Save file not found: {filename}. Starting new game.")
            self.initialize_new_world() # Start new game if save doesn't exist
            return True # Technically successful, started new game

        print(f"Loading save game from {save_path}...")
        try:
            with open(save_path, 'r') as f:
                save_data = json.load(f)

            save_version = save_data.get("save_format_version", 1) # Assume version 1 if missing
            print(f"Save Format Version: {save_version}")
            # Add version compatibility checks if needed later

            # --- Load Player State ---
            if "player" in save_data:
                self.player = Player.from_dict(save_data["player"], self) # Pass world context
                if not self.player: raise ValueError("Player.from_dict returned None") # Critical failure
                self.current_region_id = self.player.current_region_id
                self.current_room_id = self.player.current_room_id
                # Validate location
                if not self.get_current_room():
                    print(f"Warning: Loaded player location {self.current_region_id}:{self.current_room_id} is invalid. Resetting to respawn.")
                    self.current_region_id = self.player.respawn_region_id
                    self.current_room_id = self.player.respawn_room_id
                    self.player.current_region_id = self.current_region_id # Update player too
                    self.player.current_room_id = self.current_room_id
                    if not self.get_current_room(): # Still invalid? Fallback hard.
                        print(f"{FORMAT_ERROR}Critical: Respawn invalid. Resetting to town_square.{FORMAT_RESET}")
                        self.current_region_id = "town"
                        self.current_room_id = "town_square"
                        self.player.current_region_id = self.current_region_id
                        self.player.current_room_id = self.current_room_id

            else:
                print("Warning: Player data missing in save file. Starting new game.")
                self.initialize_new_world()
                print(f"Save game load failed (missing player data), new world started.")
                return True # New world is a valid state

            # --- Clear Dynamic World State ---
            self.npcs = {}
            for region in self.regions.values():
                if region: # Check region exists
                    for room in region.rooms.values():
                        if room: room.items = [] # Clear dynamic items list

            # --- Load NPC States ---
            print("Loading NPCs...")
            npc_load_count = 0
            for instance_id, npc_state in save_data.get("npc_states", {}).items():
                try:
                    template_id = npc_state.get("template_id")
                    if template_id:
                        # Create a copy of npc_state to avoid modifying the original save data dict
                        state_overrides = npc_state.copy()
                        # Remove template_id from the overrides dict *before* unpacking
                        state_overrides.pop("template_id", None) # Use .pop with None default for safety

                        # Now unpack the modified dictionary
                        npc = NPCFactory.create_npc_from_template(template_id, self, instance_id, **state_overrides)
                        if npc:
                            self.add_npc(npc) # Adds to self.npcs and sets world ref
                            npc_load_count += 1
                        else:
                            print(f"Warning: Failed to create NPC instance '{instance_id}' (Template: {template_id}).")
                    else:
                        print(f"Warning: NPC state for '{instance_id}' missing template_id. Skipping.")
                except Exception as npc_err:
                    print(f"{FORMAT_ERROR}Error loading NPC '{instance_id}': {npc_err}{FORMAT_RESET}")
                    # Optionally print traceback for detailed debugging
                    # import traceback
                    # traceback.print_exc()

            print(f"Loaded {npc_load_count} NPCs.")

            # --- Load Room Items State ---
            # This replaces the need to separately load initial items, as save_game now saves all items present.
            print("Loading Room Items...")
            item_load_count = 0
            # Use the key corresponding to the revised save logic
            room_items_state = save_data.get("room_items_state", {})
            for location_key, item_refs in room_items_state.items():
                try:
                    region_id, room_id = location_key.split(":")
                    region = self.get_region(region_id)
                    room = region.get_room(room_id) if region else None
                    if room:
                        # Ensure room.items is initialized
                        if not hasattr(room, 'items'): room.items = []

                        for item_ref in item_refs:
                            if item_ref and isinstance(item_ref, dict) and "item_id" in item_ref:
                                item_id = item_ref["item_id"]
                                overrides = item_ref.get("properties_override", {})
                                qty = item_ref.get("quantity", 1) # Get quantity from ref

                                item = ItemFactory.create_item_from_template(item_id, self, **overrides)
                                if item:
                                    # Add correct quantity based on stackability
                                    count_to_add = qty if item.stackable else 1
                                    for _ in range(count_to_add):
                                        room.add_item(item) # Add instance(s)
                                        item_load_count += 1
                                    if not item.stackable and qty > 1:
                                        print(f"Warning: Loaded non-stackable item '{item.name}' with qty > 1 in {location_key}. Added {qty} instances.")
                                else: print(f"Warning: Failed to create item '{item_id}' in {location_key} during load.")
                            else: print(f"Warning: Invalid item reference in {location_key}: {item_ref}")
                    else:
                        print(f"Warning: Room '{location_key}' not found for items during load.")
                except ValueError:
                    print(f"Warning: Invalid location key format for room items: {location_key}")
                except Exception as item_err:
                    print(f"{FORMAT_ERROR}Error loading items for {location_key}: {item_err}{FORMAT_RESET}")
                    # import traceback
                    # traceback.print_exc()

            print(f"Loaded {item_load_count} item instances into rooms.")


            # --- Load Plugin Data ---
            self.plugin_data = save_data.get("plugin_data", {})

            # --- Finalize ---
            self.start_time = time.time() # Reset clock relative to load
            self.last_update_time = 0 # Ensure updates run soon
            print(f"Save game '{filename}' loaded successfully. Player at {self.current_region_id}:{self.current_room_id}")
            return True

        except json.JSONDecodeError as json_err:
            print(f"{FORMAT_ERROR}FATAL: Error decoding JSON from save file {save_path}: {json_err}{FORMAT_RESET}")
            print("Attempting to start a new game...")
            self.initialize_new_world()
            return False # Indicate load failure, but game continues with new world
        except Exception as e:
            print(f"{FORMAT_ERROR}Critical Error loading save game '{filename}': {e}{FORMAT_RESET}")
            import traceback
            traceback.print_exc()
            print("Attempting to start a new game...")
            self.initialize_new_world()
            return False # Indicate load failure, but game continues with new world

    def save_game(self, filename: str = DEFAULT_SAVE_FILE) -> bool:
        """Saves the dynamic game state to a save file using references."""
        save_path = self._resolve_save_path(filename, SAVE_GAME_DIR)
        if not save_path: return False

        print(f"Saving game to {save_path}...")
        try:
            # --- Player State ---
            if not self.player:
                print(f"{FORMAT_ERROR}Error: Player object missing, cannot save.{FORMAT_RESET}")
                return False
            # Ensure player's current location is up-to-date before saving
            self.player.current_region_id = self.current_region_id
            self.player.current_room_id = self.current_room_id
            player_data = self.player.to_dict(self) # Pass world context

            # --- NPC States ---
            npc_states = {}
            for instance_id, npc in self.npcs.items():
                if npc: # Check if NPC object exists
                    npc_states[instance_id] = npc.to_dict() # Uses refined NPC.to_dict
                else:
                    print(f"Warning: Found None for NPC ID '{instance_id}' during save.")

            # --- Dynamic Items ---
            dynamic_items = {}
            for region_id, region in self.regions.items():
                if not region: continue
                for room_id, room in region.rooms.items():
                    if not room or not hasattr(room, 'items'): continue

                    # Items currently in the room (instances)
                    current_items_in_room = room.items

                    # Get item IDs defined initially for this room (from templates)
                    initial_item_refs = getattr(room, 'initial_item_refs', [])
                    initial_item_counts = {}
                    for ref in initial_item_refs:
                        iid = ref.get("item_id")
                        if iid: initial_item_counts[iid] = initial_item_counts.get(iid, 0) + ref.get("quantity", 1)

                    # Find items present now that differ from initial state
                    items_to_save_in_room = []
                    processed_stacks = set() # Track stackable items processed

                    for item_instance in current_items_in_room:
                        item_id = item_instance.obj_id # Assumes this is the template ID
                        if item_id in processed_stacks: continue

                        # Count how many instances of this item_id are currently in the room
                        current_count = sum(1 for i in current_items_in_room if i.obj_id == item_id)
                        initial_count = initial_item_counts.get(item_id, 0)

                        # Calculate how many are "dynamic" (added or remaining after removal)
                        dynamic_count_needed = current_count

                        # Logic Adjustment: Save *all* currently present items that weren't initially present *in this exact state*
                        # OR save items whose dynamic properties (durability, etc.) have changed.

                        # Simpler approach: Save *all* items currently in the room, EXCEPT those
                        # that perfectly match an initial item definition AND have no dynamic property changes.
                        # Even simpler: Save ALL items currently in the room state. Rely on load to handle it.
                        # Let's try saving ALL current items and let load figure it out.

                    # --- Revised Dynamic Item Logic: Save *all* current items ---
                    # Group current items by ID for saving quantities
                    grouped_current_items: Dict[str, List[Item]] = {}
                    for item_instance in current_items_in_room:
                        if item_instance.obj_id not in grouped_current_items:
                            grouped_current_items[item_instance.obj_id] = []
                        grouped_current_items[item_instance.obj_id].append(item_instance)

                    for item_id, instances in grouped_current_items.items():
                        if not instances: continue
                        first_instance = instances[0]
                        quantity = len(instances)

                        # Serialize using the reference function. It handles overrides.
                        # For stackables, quantity > 1 is handled.
                        # For non-stackables, we save one reference per instance.
                        if first_instance.stackable:
                            ref = _serialize_item_reference(first_instance, quantity, self)
                            if ref: items_to_save_in_room.append(ref)
                        else:
                            for instance in instances: # Save each non-stackable individually
                                    ref = _serialize_item_reference(instance, 1, self)
                                    if ref: items_to_save_in_room.append(ref)
                    # --- End Revised Logic ---


                    if items_to_save_in_room:
                        dynamic_items[f"{region_id}:{room_id}"] = items_to_save_in_room

            # --- Assemble Save Data ---
            save_data = {
                "save_format_version": 3, # Increment version for new save logic
                "save_name": filename.replace(".json", ""),
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "player": player_data,
                "npc_states": npc_states,
                # Renamed for clarity - this now holds ALL items present in rooms at save time
                "room_items_state": dynamic_items,
                "plugin_data": self.plugin_data.copy() # Save a copy
            }

            # --- Write to File ---
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, 'w') as f:
                # Use default=str for basic fallback, but complex objects might still fail
                json.dump(save_data, f, indent=2, default=str)

            print(f"Game saved successfully to {save_path}.")
            return True

        except Exception as e:
            print(f"{FORMAT_ERROR}Error saving game: {e}{FORMAT_RESET}")
            import traceback
            traceback.print_exc()
            return False
        
    # --- Getters (mostly unchanged, verify they work with new structure) ---
    def get_region(self, region_id: str) -> Optional[Region]: return self.regions.get(region_id)
    def get_current_region(self) -> Optional[Region]: return self.regions.get(self.current_region_id) if self.current_region_id else None
    def get_current_room(self) -> Optional[Room]:
        region = self.get_current_region()
        return region.get_room(self.current_room_id) if region and self.current_room_id else None
    def add_region(self, region_id: str, region: Region) -> None: self.regions[region_id] = region
    def add_npc(self, npc: NPC) -> None:
        npc.last_moved = time.time() - self.start_time
        # Ensure NPC has world reference if needed by its methods
        npc.world = self # Give NPC access to world (for target formatting, etc.)
        self.npcs[npc.obj_id] = npc # Use obj_id (instance_id) as key
    def get_npc(self, instance_id: str) -> Optional[NPC]: return self.npcs.get(instance_id)
    def get_npcs_in_room(self, region_id: str, room_id: str) -> List[NPC]:
        return [npc for npc in self.npcs.values() if npc.current_region_id == region_id and npc.current_room_id == room_id and npc.is_alive]
    def get_current_room_npcs(self) -> List[NPC]:
        if not self.current_region_id or not self.current_room_id: return []
        return self.get_npcs_in_room(self.current_region_id, self.current_room_id)

    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        region = self.get_region(region_id)
        room = region.get_room(room_id) if region else None
        return getattr(room, 'items', []) if room else [] # Return dynamic items list
    def get_items_in_current_room(self) -> List[Item]:
        if not self.current_region_id or not self.current_room_id: return []
        return self.get_items_in_room(self.current_region_id, self.current_room_id)

    def add_item_to_room(self, region_id: str, room_id: str, item: Item) -> bool:
        room = self.get_region(region_id).get_room(room_id) if self.get_region(region_id) else None
        if room:
             room.add_item(item) # Use Room's method
             return True
        return False
    def remove_item_from_room(self, region_id: str, room_id: str, obj_id: str) -> Optional[Item]:
         room = self.get_region(region_id).get_room(room_id) if self.get_region(region_id) else None
         return room.remove_item(obj_id) if room else None # Use Room's method

    # --- Update & Actions (minor changes) ---
    def update(self) -> List[str]:
        """Update NPCs and remove dead ones."""
        current_time_abs = time.time() # Absolute time for NPC updates
        messages = []
        if current_time_abs - self.last_update_time < 0.5: # Throttle updates
             return messages
        self.last_update_time = current_time_abs

        # Update Player
        if self.player and self.player.is_alive:
             self.player.update(current_time_abs) # Pass absolute time

        # --- NPC Update and Removal ---
        npcs_to_remove = [] # Store IDs of NPCs to remove
        # Iterate over a copy of keys, as we might modify the dictionary
        for npc_id in list(self.npcs.keys()):
            npc = self.npcs.get(npc_id)
            if not npc: continue # Should not happen, but safety check

            if npc.is_alive:
                # Update living NPCs
                npc_message = npc.update(self, current_time_abs) # Pass absolute time
                if npc_message:
                     messages.append(npc_message)
            else:
                # Mark dead NPCs for removal
                npcs_to_remove.append(npc_id)

        # Remove the dead NPCs after the update loop
        for npc_id in npcs_to_remove:
             removed_npc = self.npcs.pop(npc_id, None)
             if removed_npc:
                  # Optional: Add a message if the player is in the same room
                  if (self.player and self.player.is_alive and
                      self.current_region_id == removed_npc.current_region_id and
                      self.current_room_id == removed_npc.current_room_id):
                       # Use plain name for removal message, color isn't needed
                       messages.append(f"{FORMAT_HIGHLIGHT}The corpse of the {removed_npc.name} fades away.{FORMAT_RESET}")
                  # Optional: Publish an event
                  # if self.game and hasattr(self.game, 'plugin_manager'):
                  #    self.game.plugin_manager.event_system.publish("npc_removed", {"npc_id": npc_id})
        # --- End NPC Update and Removal ---

        return messages

    # ... (get_items_in_room, get_items_in_current_room - unchanged) ...
    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        region = self.get_region(region_id)
        if region: room = region.get_room(room_id)
        return room.items if region and room and hasattr(room, "items") else []
    def get_items_in_current_room(self) -> List[Item]:
        if not self.current_region_id or not self.current_room_id: return []
        return self.get_items_in_room(self.current_region_id, self.current_room_id)

    # ... (add_item_to_room, remove_item_from_room - unchanged) ...
    def add_item_to_room(self, region_id: str, room_id: str, item: Item) -> bool:
        region = self.get_region(region_id); room = region.get_room(room_id) if region else None
        if not room: return False
        if not hasattr(room, "items"): room.items = []
        room.items.append(item); return True
    def remove_item_from_room(self, region_id: str, room_id: str, obj_id: str) -> Optional[Item]:
        items = self.get_items_in_room(region_id, room_id)
        for i, item in enumerate(items):
            if item.obj_id == obj_id: return items.pop(i)
        return None

    # --- NEW: Helper methods for finding things ---
    def find_item_in_room(self, name: str) -> Optional[Item]:
         """Finds an item in the current room by name/id."""
         items = self.get_items_in_current_room()
         name_lower = name.lower()
         for item in items:
              if name_lower == item.name.lower() or name_lower == item.obj_id:
                   return item
         # Fallback partial match
         for item in items:
              if name_lower in item.name.lower():
                   return item
         return None

    def save_to_json(self, filename: str) -> bool:
        save_path = self._resolve_save_path(filename)
        if not save_path: return False
        try:
            world_data = {
                "current_region_id": self.current_region_id,
                "current_room_id": self.current_room_id,
                "player": self.player.to_dict(), # Player dict now includes equipment
                "regions": {}, "npcs": {},
                "plugin_data": self.plugin_data
            }
            for region_id, region in self.regions.items():
                region_data = {"name": region.name, "description": region.description, "rooms": {}}
                for room_id, room in region.rooms.items():
                     room_dict = room.to_dict()
                     # Explicitly ensure items list is serialized correctly
                     room_dict["items"] = [item.to_dict() for item in getattr(room, 'items', [])]
                     region_data["rooms"][room_id] = room_dict
                world_data["regions"][region_id] = region_data
            for npc_id, npc in self.npcs.items():
                world_data["npcs"][npc_id] = npc.to_dict()

            with open(save_path, 'w') as f:
                json.dump(world_data, f, indent=2, default=lambda o: '<not serializable>') # Handle non-serializable gently
            print(f"World saved to {save_path}")
            return True
        except Exception as e:
            print(f"Error saving world: {e}"); import traceback; traceback.print_exc(); return False

    def load_from_json(self, filename: str) -> bool:
        file_path = self._resolve_load_path(filename)
        if not file_path: return False
        try:
            with open(file_path, 'r') as f: world_data = json.load(f)

            self.regions = {}; self.npcs = {}; self.start_time = time.time()
            self.plugin_data = world_data.get("plugin_data", {})

            if "player" in world_data:
                self.player = Player.from_dict(world_data["player"])
            else: self.player = Player("Adventurer")

            if not hasattr(self.player, "inventory") or self.player.inventory is None:
                 self.player.inventory = Inventory()
            if not hasattr(self.player, "equipment") or self.player.equipment is None:
                 self.player.equipment = { "main_hand": None, "off_hand": None, "body": None, "head": None, "feet": None, "hands": None, "neck": None }

            # *** Use Region.from_dict ***
            for region_id, region_data in world_data.get("regions", {}).items():
                try:
                    # Pass region_id as obj_id hint for Region.from_dict
                    region_data['obj_id'] = region_data.get('obj_id', region_id)
                    region = Region.from_dict(region_data)
                    self.add_region(region_id, region) # Use the original key for the world dict
                except Exception as region_load_error:
                    print(f"Warning: Failed to load region '{region_data.get('name', region_id)}': {region_load_error}")
                    import traceback
                    traceback.print_exc() # Print traceback for region loading errors
            # *** End Change ***

            current_time = time.time() - self.start_time
            for npc_id, npc_data in world_data.get("npcs", {}).items():
                 try:
                      # Pass npc_id as obj_id hint
                      npc_data['obj_id'] = npc_data.get('obj_id', npc_id)
                      npc = NPC.from_dict(npc_data)
                      npc.last_moved = current_time
                      if not hasattr(npc, "inventory") or npc.inventory is None:
                           npc.inventory = Inventory(max_slots=10, max_weight=50.0)
                      self.npcs[npc.obj_id] = npc # Use npc.obj_id as key now
                 except Exception as npc_load_error:
                      print(f"Warning: Failed to load NPC '{npc_data.get('name', npc_id)}': {npc_load_error}")
                      import traceback
                      traceback.print_exc() # Print traceback for NPC loading errors

            self.current_region_id = world_data.get("current_region_id")
            self.current_room_id = world_data.get("current_room_id")

            if not self.get_current_room():
                 print(f"Warning: Loaded location {self.current_region_id}:{self.current_room_id} is invalid. Resetting.")
                 if self.regions:
                      first_region_id = next(iter(self.regions))
                      first_region = self.regions[first_region_id]
                      if first_region.rooms:
                           self.current_region_id = first_region_id
                           self.current_room_id = next(iter(first_region.rooms))
                           print(f"Reset location to {self.current_region_id}:{self.current_room_id}")
                      else: self.current_region_id = self.current_room_id = None
                 else: self.current_region_id = self.current_room_id = None

            print(f"World loaded from {file_path}. Location: {self.current_region_id}:{self.current_room_id}")
            return True
        except json.JSONDecodeError as json_err:
             print(f"FATAL: Error decoding JSON from {file_path}: {json_err}")
             return False
        except Exception as e:
            print(f"Error loading world: {e}"); import traceback; traceback.print_exc(); return False

    # Helper for resolving save/load paths (internal)
    def _resolve_save_path(self, filename):
         paths = [filename, os.path.join(os.getcwd(), filename)]
         # Add parent dir path if relevant
         parent_dir = os.path.dirname(os.getcwd())
         if parent_dir != os.getcwd(): paths.append(os.path.join(parent_dir, filename))
         # Try to use existing file path first
         for path in paths:
              if os.path.exists(path): return path
         # Fallback: use path with writable directory
         for path in paths:
             try:
                 dir_path = os.path.dirname(path) or os.getcwd()
                 if os.path.exists(dir_path) and os.access(dir_path, os.W_OK): return path
             except: continue
         # Default to current dir if all else fails
         return os.path.join(os.getcwd(), filename)

    # ... (set_plugin_data, get_plugin_data - unchanged) ...
    def set_plugin_data(self, plugin_id: str, key: str, value: Any) -> None:
        if plugin_id not in self.plugin_data: self.plugin_data[plugin_id] = {}
        self.plugin_data[plugin_id][key] = value
    def get_plugin_data(self, plugin_id: str, key: str, default: Any = None) -> Any:
        return self.plugin_data.get(plugin_id, {}).get(key, default)

    # ... (find_path - unchanged) ...
    def find_path(self, source_region_id: str, source_room_id: str,
                 target_region_id: str, target_room_id: str) -> Optional[List[str]]:
        start_node = (source_region_id, source_room_id)
        goal_node = (target_region_id, target_room_id)
        if start_node == goal_node: return []

        queue = [(0, start_node, [])] # (cost, node, path)
        visited = {start_node}
        cheapest_path_to = {start_node: []} # Store the actual path directions

        import heapq
        pq = [(0, start_node)] # (priority, node) for A*
        g_score = {start_node: 0} # Cost from start

        while pq:
            current_priority, current_node = heapq.heappop(pq)

            if current_node == goal_node:
                return cheapest_path_to[goal_node]

            current_region_id, current_room_id = current_node
            region = self.get_region(current_region_id)
            if not region: continue
            room = region.get_room(current_room_id)
            if not room: continue

            for direction, exit_id in room.exits.items():
                next_region_id, next_room_id = current_region_id, exit_id
                if ":" in exit_id: next_region_id, next_room_id = exit_id.split(":")

                next_node = (next_region_id, next_room_id)

                # Basic validation if next room/region exists
                next_region = self.get_region(next_region_id)
                if not next_region or not next_region.get_room(next_room_id): continue # Skip invalid exits

                new_cost = g_score[current_node] + 1 # Simple cost = 1 per step

                if next_node not in g_score or new_cost < g_score[next_node]:
                    g_score[next_node] = new_cost
                    # Heuristic: 0 if same region, 1 if different (very basic)
                    heuristic = 0 if next_region_id == target_region_id else 1
                    priority = new_cost + heuristic
                    heapq.heappush(pq, (priority, next_node))
                    # Update path
                    cheapest_path_to[next_node] = cheapest_path_to[current_node] + [direction]

        return None # No path found

    def is_location_safe(self, region_id: str, room_id: Optional[str] = None) -> bool:
        """
        Check if a given region (and optionally room) is considered safe
        from hostile monster spawns and entry.
        """
        region = self.get_region(region_id)
        if not region:
            return False # Unknown regions are not considered safe

        # Check the region's safe_zone property
        if region.get_property("safe_zone", False):
            return True

        # Optional: Add specific room checks here if needed later
        # e.g., if room_id in config.SAFE_ROOMS_EVEN_IN_DANGEROUS_REGIONS: return True

        return False # Default to not safe if region isn't marked

    def _get_item_overrides(self, item: Item) -> Dict[str, Any]:
        """Helper to find properties differing from the template."""
        overrides = {}
        template = self.item_templates.get(item.obj_id)
        if template:
             template_props = template.get("properties", {})
             for key, current_value in item.properties.items():
                  # Simple comparison, might need refinement for complex types
                  if key not in template_props or template_props[key] != current_value:
                       if key not in ["weight", "value", "stackable", "name", "description"]:
                            overrides[key] = current_value
        else:
             # No template? Save all properties?
             print(f"Warning: No template for item {item.obj_id} during save override check.")
             overrides = item.properties.copy()
             # Remove potentially problematic core props if saving all
             for core in ["weight", "value", "stackable", "name", "description"]:
                  overrides.pop(core, None)

        return overrides

    # --- Path Resolution Helpers ---
    def _resolve_save_path(self, filename: str, base_dir: str) -> Optional[str]:
        """Resolves the absolute path for saving, ensuring the directory exists."""
        try:
            # Ensure base_dir exists
            os.makedirs(base_dir, exist_ok=True)
            # Basic sanitation
            safe_filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))
            if not safe_filename.endswith(".json"):
                 safe_filename += ".json"
            return os.path.abspath(os.path.join(base_dir, safe_filename))
        except Exception as e:
            print(f"Error resolving save path '{filename}' in '{base_dir}': {e}")
            return None

    def _resolve_load_path(self, filename: str, base_dir: str) -> Optional[str]:
         """Resolves the absolute path for loading."""
         try:
             safe_filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))
             if not safe_filename.endswith(".json"):
                  safe_filename += ".json"
             path = os.path.abspath(os.path.join(base_dir, safe_filename))
             if os.path.exists(path):
                  return path
             else:
                  print(f"Load path not found: {path}")
                  # Try finding in CWD as fallback?
                  cwd_path = os.path.abspath(safe_filename)
                  if os.path.exists(cwd_path):
                       print(f"Found in CWD instead: {cwd_path}")
                       return cwd_path
                  return None # Not found
         except Exception as e:
              print(f"Error resolving load path '{filename}' in '{base_dir}': {e}")
              return None

    def find_npc_in_room(self, name: str) -> Optional[NPC]:
         """Finds an NPC in the current room by name or instance_id."""
         npcs = self.get_current_room_npcs()
         name_lower = name.lower()
         # Exact match first (name or instance ID)
         for npc in npcs:
              if name_lower == npc.name.lower() or name_lower == npc.obj_id:
                   return npc
         # Fallback partial match on name
         for npc in npcs:
              if name_lower in npc.name.lower():
                   return npc
         return None

    def get_player_status(self) -> str:
        return self.player.get_status() if self.player else "Player not loaded."

    def change_room(self, direction: str) -> str:
        if not self.player or not self.player.is_alive:
             return f"{FORMAT_ERROR}You cannot move while dead.{FORMAT_RESET}" # Check player state

        old_region_id = self.current_region_id; old_room_id = self.current_room_id
        current_room = self.get_current_room()
        if not current_room: return f"{FORMAT_ERROR}You are lost in the void.{FORMAT_RESET}"

        # --- Check for locked exits ---
        # Check room properties first
        lock_key_id = current_room.get_property("locked_by")
        lock_target_id = current_room.get_property("lock_target_id")
        # TODO: Need a way to associate lock properties with specific *exits*, not just the room.
        # This requires extending the Room/Region definition format.
        # For now, assume lock applies to all exits if defined on the room (simplified).
        if lock_key_id:
             # Check if player has the key
             has_key = False
             if self.player.inventory.find_item_by_name(lock_key_id): # Crude check by ID/name
                  has_key = True
             # More robust check if key has target_id property matching lock_target_id
             for slot in self.player.inventory.slots:
                  if slot.item and isinstance(slot.item, Key):
                       if slot.item.get_property("target_id") == lock_target_id:
                            has_key = True
                            break
             if not has_key:
                  return f"{FORMAT_ERROR}The way is locked.{FORMAT_RESET}"
        # --- End Lock Check ---


        destination_id = current_room.get_exit(direction)
        if not destination_id: return f"{FORMAT_ERROR}You cannot go {direction}.{FORMAT_RESET}"

        new_region_id = self.current_region_id
        new_room_id = destination_id
        if ":" in destination_id:
             new_region_id, new_room_id = destination_id.split(":")

        target_region = self.get_region(new_region_id)
        target_room = target_region.get_room(new_room_id) if target_region else None # Get target room
        if not target_room:
             return f"{FORMAT_ERROR}That path leads to an unknown place.{FORMAT_RESET}"

        # --- Check if target room is locked from the *other* side (requires definition change) ---
        # target_lock_key = target_room.get_property("locked_by")
        # if target_lock_key and not self.player_has_key(target_lock_key):
        #      return f"{FORMAT_ERROR}The door is locked from the other side.{FORMAT_RESET}"
        # --- End Target Lock Check ---

        # Successfully moving
        self.current_region_id = new_region_id
        self.current_room_id = new_room_id
        target_room.visited = True

        # Update player location tracking
        self.player.current_region_id = new_region_id
        self.player.current_room_id = new_room_id

        # Trigger hooks/events
        if self.game and hasattr(self.game, "plugin_manager"):
             self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
             self.game.plugin_manager.on_room_enter(new_region_id, new_room_id)

        region_change_msg = ""
        if new_region_id != old_region_id:
             region_change_msg = f"{FORMAT_HIGHLIGHT}You have entered {target_region.name}.{FORMAT_RESET}\n\n"

        return region_change_msg + self.look()

    def look(self) -> str:
        return self.get_room_description_for_display()

    def get_room_description_for_display(self) -> str:
        current_room = self.get_current_room()
        if not current_room: return f"{FORMAT_ERROR}You are nowhere.{FORMAT_RESET}"

        time_period = self.get_plugin_data("time_plugin", "time_period", "day")
        weather = self.get_plugin_data("weather_plugin", "current_weather", "clear")

        room_desc = current_room.get_full_description(time_period, weather)
        npcs_in_room = self.get_current_room_npcs()
        items_in_room = self.get_items_in_current_room()

        # --- Format NPC List ---
        npcs_sentence = ""
        if npcs_in_room:
            formatted_npc_list = [] # Store fully formatted names with status
            for npc in npcs_in_room:
                # format_name_for_display now handles article, color, level (if debug)
                # Pass start_of_sentence=False as it's part of a list/sentence here
                formatted_name = format_name_for_display(self.player, npc, start_of_sentence=False)

                # Add status suffix
                status_suffix = ""
                if npc.in_combat:
                    status_suffix = f" {FORMAT_ERROR}(Fighting!){FORMAT_RESET}"
                elif hasattr(npc, "ai_state") and "current_activity" in npc.ai_state:
                    # Optionally shorten activity name if needed
                    activity = npc.ai_state["current_activity"]
                    # if len(activity) > 20: activity = activity[:17] + "..."
                    status_suffix = f" ({activity})"

                formatted_npc_list.append(f"{formatted_name}{status_suffix}")

            prefix = "You also see "
            
            if len(formatted_npc_list) == 1:
                npcs_sentence = f"{prefix}{formatted_npc_list[0]}."
            elif len(formatted_npc_list) == 2:
                npcs_sentence = f"{prefix}{formatted_npc_list[0]} and {formatted_npc_list[1]}."
            else: # More than 2 NPCs
                all_but_last = ", ".join(formatted_npc_list[:-1])
                last_npc = formatted_npc_list[-1]
                npcs_sentence = f"{prefix}{all_but_last}, and {last_npc}."
        # --- END NPC Formatting ---

        # --- Format Item List (as before) ---
        items_sentence = ""
        if items_in_room:
            item_counts: Dict[str, Dict[str, Any]] = {}
            for item in items_in_room:
                item_id = item.obj_id
                if item_id not in item_counts: item_counts[item_id] = {"name": item.name, "count": 0}
                item_counts[item_id]["count"] += 1
            item_message_parts = []
            for item_id, data in item_counts.items():
                base_name = data["name"]; count = data["count"]
                formatted_name = f"{FORMAT_CATEGORY}{base_name}{FORMAT_RESET}"
                if count == 1: item_message_parts.append(f"{get_article(base_name)} {formatted_name}")
                else:
                    plural_base_name = simple_plural(base_name)
                    formatted_plural_name = f"{FORMAT_CATEGORY}{plural_base_name}{FORMAT_RESET}"
                    item_message_parts.append(f"{count} {formatted_plural_name}")

            prefix = "You also see "

            if len(item_message_parts) == 1: items_sentence = f"{prefix}{item_message_parts[0]} here."
            elif len(item_message_parts) == 2: items_sentence = f"{prefix}{item_message_parts[0]} and {item_message_parts[1]} here."
            else: items_sentence = f"{prefix}{', '.join(item_message_parts[:-1])}, and {item_message_parts[-1]} here."
        # --- END Item Formatting ---


        # --- Combine Description Parts ---
        full_description = room_desc
        # Append NPC and Item sentences with appropriate spacing
        if npcs_sentence:
            full_description += "\n\n" + npcs_sentence
        if items_sentence:
            # Add extra newline only if BOTH are present
            full_description += ("\n\n" if npcs_sentence else "\n\n") + items_sentence

        return full_description

    def remove_item_instance_from_room(self, region_id: str, room_id: str, item_instance: Item) -> bool:
        """
        Removes a specific item instance from a room's item list.

        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            item_instance: The specific Item object instance to remove.

        Returns:
            True if the instance was found and removed, False otherwise.
        """
        room = self.get_region(region_id).get_room(room_id) if self.get_region(region_id) else None
        if not room or not hasattr(room, 'items'):
            return False

        try:
            # Use 'is' for identity check to remove the specific instance
            room.items.remove(item_instance)
            return True
        except ValueError:
            # Instance not found in the list
            return False
