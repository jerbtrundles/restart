# plugins/monster_spawner_plugin/__init__.py
"""
Monster spawner plugin for the MUD game.
Periodically spawns monsters in the world based on region settings and templates.
"""
from typing import Dict, List, Any, Optional, Tuple # Keep necessary type hints
import random
import time
import math # Needed if you use math.ceil for limit calculation

# --- Core/Plugin System Imports ---
from core.config import FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, FORMAT_HIGHLIGHT # Import format codes
from plugins.plugin_system import PluginBase, register_plugin_command # Import base and command registration

# --- Game Object Imports ---
from npcs.npc import NPC
from npcs.npc_factory import NPCFactory # Use the unified NPC Factory

# --- Utility Imports ---
from utils.text_formatter import format_target_name # For formatting monster names in commands

# Required imports for type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from world.world import World


class MonsterSpawnerPlugin(PluginBase):
    """Plugin that spawns monsters in the world."""

    plugin_id = "monster_spawner_plugin"
    plugin_name = "Monster Spawner"

    def __init__(self, world: Optional['World'] = None, command_processor=None, event_system=None,
                 data_provider=None, service_locator=None):
        """Initialize the monster spawner plugin."""
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator

        # Import config from the config.py file within this plugin's directory
        try:
            from .config import DEFAULT_CONFIG
            self.config = DEFAULT_CONFIG.copy() # Use defaults from config file
        except ImportError:
            print(f"{FORMAT_ERROR}[Spawner] Error: Could not import config.py. Using empty config.{FORMAT_RESET}")
            self.config = {} # Fallback to empty config

        # Spawn tracking
        self.last_spawn_time = 0.0 # Initialize as float
        self.total_spawned = 0

    def initialize(self):
        """Initialize the plugin after world and other services are ready."""
        if not self.world:
            print(f"{FORMAT_ERROR}[Spawner] Error: World object not provided during initialization.{FORMAT_RESET}")
            return

        if self.event_system:
            self.event_system.subscribe("on_tick", self._on_tick)
        else:
            print(f"{FORMAT_ERROR}[Spawner] Warning: Event system not available.{FORMAT_RESET}")


        # Register commands
        self._register_commands()

        # --- Initialize Print Message ---
        ratio = self.config.get('rooms_per_monster', 5)
        min_m = self.config.get('min_monsters_per_region', 1)
        max_cap = self.config.get('max_monsters_per_region_cap', 15)
        interval = self.config.get('spawn_interval', 5)
        print(f"Monster spawner plugin initialized. Spawn interval: {interval}s. Target: ~1 monster / {ratio} rooms (Min: {min_m}, Max Cap: {max_cap}).")
        # --- End Initialize ---

        self.last_spawn_time = time.time() # Initialize last spawn time correctly

    def _register_commands(self):
        """Register plugin commands."""
        # Use register_plugin_command safely
        try:
            register_plugin_command(
                self.plugin_id,
                "spawnmonster",
                self._spawn_command_handler,
                aliases=["spawnmob"],
                category="debug",
                help_text="Spawn a specific monster in the current room.\n\nUsage: spawnmonster <monster_template_id> [level]"
            )

            register_plugin_command(
                self.plugin_id,
                "monsters",
                self._monsters_command_handler,
                aliases=["listmonsters"],
                category="world",
                help_text="List active monsters in the world or current region.\n\nUsage: monsters [region_id]"
            )
        except Exception as e:
            print(f"{FORMAT_ERROR}[Spawner] Error registering commands: {e}{FORMAT_RESET}")

    def _on_tick(self, event_type, data):
        """Handle tick events for monster spawning."""
        current_time = time.time() # Use absolute time for interval checking

        # Check if it's time to attempt spawns
        interval = self.config.get('spawn_interval', 5)
        if current_time - self.last_spawn_time < interval:
            return

        self.last_spawn_time = current_time

        # Attempt to spawn monsters in each region
        if self.world and hasattr(self.world, "regions"):
            for region_id, region in self.world.regions.items():
                # Check if region object is valid before passing
                if region and hasattr(region, 'rooms'):
                    self._spawn_monsters_in_region(region_id, region)
        elif not self.world:
             print(f"{FORMAT_ERROR}[Spawner] Warning: World object missing in _on_tick.{FORMAT_RESET}")


    def _spawn_monsters_in_region(self, region_id, region):
        """
        Attempt to spawn monsters in a region, using dynamic limits.
        """
        # Basic checks
        if not self.world or not region or not hasattr(region, 'rooms'):
            # print(f"[SpawnerDebug] Invalid world/region object for {region_id}") # Debug
            return
        if not hasattr(self.world, 'npc_templates'):
            if self.config.get("debug", False) and self.event_system:
                 self.event_system.publish("display_message", f"[SpawnerDebug] Error: NPC templates not loaded in world.")
            return

        # --- Safety/Config Checks ---
        if self.world.is_location_safe(region_id):
             if self.config.get("debug", False) and self.event_system:
                 self.event_system.publish("display_message", f"[SpawnerDebug] Skipping spawn in safe region: {region_id}")
             return

        # --- Calculate Dynamic Max Monsters ---
        num_rooms = len(region.rooms)
        if num_rooms <= 0: return

        ratio = self.config.get("rooms_per_monster", 5)
        min_limit = self.config.get("min_monsters_per_region", 1)
        max_cap = self.config.get("max_monsters_per_region_cap", 15)

        # Ensure ratio is positive to avoid division by zero
        ratio = max(1, ratio)
        # Calculate based on ratio using integer division (floor)
        calculated_limit = max(1, num_rooms // ratio)
        # Apply min and max caps
        dynamic_max_for_region = max(min_limit, min(calculated_limit, max_cap))
        # --- End Calculate ---

        # --- Check Current Count ---
        current_monster_count = self._count_monsters_in_region(region_id)
        if current_monster_count >= dynamic_max_for_region:
            # ... (debug message if max reached) ...
            return
        # --- End Check ---

        # Check spawn chance
        if random.random() > self.config.get("spawn_chance", 1.0): # Default to 1.0 if missing
            return

        # --- Find Suitable Room ---
        suitable_rooms = []
        no_spawn_keywords = self.config.get("no_spawn_rooms", [])
        player_location = (self.world.current_region_id, self.world.current_room_id)

        for room_id, room in region.rooms.items():
            # Basic check if room object exists
            if not room: continue

            # Check if room is specifically marked as no-spawn
            is_no_spawn_prop = getattr(room, 'properties', {}).get('no_monster_spawn', False)
            if is_no_spawn_prop: continue

            # Check against keyword list (room ID and name)
            room_name_lower = room.name.lower()
            room_id_lower = room_id.lower()
            is_no_spawn_keyword = any(keyword in room_id_lower or keyword in room_name_lower for keyword in no_spawn_keywords)
            if is_no_spawn_keyword: continue

            # Skip player's current room
            if player_location == (region_id, room_id): continue

            suitable_rooms.append(room_id)

        if not suitable_rooms:
            # ... (debug message if no suitable rooms) ...
            return
        room_id_to_spawn = random.choice(suitable_rooms)
        # --- End Find Room ---

        # --- Choose Monster Type and Level ---
        # Get all hostile template IDs loaded in the world
        hostile_template_ids = [
            tid for tid, template in self.world.npc_templates.items()
            if isinstance(template, dict) and template.get('faction') == 'hostile' # Added isinstance check
        ]
        if not hostile_template_ids:
             # ... (debug message if no hostile templates) ...
             return

        # Get weights for this region
        region_monster_weights = self.config.get("region_monsters", {}).get(region_id, self.config.get("region_monsters", {}).get("default", {}))
        # Filter weights to only include available hostile templates
        available_monster_weights = {
            tid: weight for tid, weight in region_monster_weights.items()
            if tid in hostile_template_ids
        }
        # Fallback if no specific weights match available hostiles
        if not available_monster_weights:
            available_monster_weights = {tid: 1 for tid in hostile_template_ids}

        if not available_monster_weights: return # Still none possible

        # Choose the template ID
        monster_template_id = self._weighted_choice(available_monster_weights)
        if not monster_template_id: return # Choice failed

        # Determine level
        level_range = self.config.get("region_levels", {}).get(region_id, self.config.get("region_levels", {}).get("default", [1, 1]))
        level = random.randint(level_range[0], level_range[1])
        # --- End Choose Monster ---

        # --- Prepare Overrides and Spawn ---
        overrides = {
            "level": level,
            "current_region_id": region_id,
            "current_room_id": room_id_to_spawn,
            "home_region_id": region_id,
            "home_room_id": room_id_to_spawn
        }
        # Use NPCFactory
        monster = NPCFactory.create_npc_from_template(monster_template_id, self.world, **overrides)
        # --- End Spawn ---

        # --- Add to World ---
        if monster:
            if level > 1: monster.name = f"{monster.name} (Level {level})"
            self.world.add_npc(monster)
            self.total_spawned += 1
            if self.config.get("debug", False) and self.event_system:
                 self.event_system.publish(
                     "display_message",
                     f"[SpawnerDebug] Spawned {monster.name} (T: {monster_template_id}) in {region_id}:{room_id_to_spawn}"
                 )
        elif self.config.get("debug", False) and self.event_system:
             self.event_system.publish("display_message", f"[SpawnerDebug] Failed creation: {monster_template_id}")
        # --- End Add ---

    def _count_monsters_in_region(self, region_id):
        """Count active hostile monsters currently in a region."""
        if not self.world or not hasattr(self.world, 'npcs'): return 0
        return sum(1 for npc in self.world.npcs.values() if
                   npc and # Check if NPC object exists
                   npc.current_region_id == region_id and
                   getattr(npc, 'faction', 'neutral') == "hostile" and
                   getattr(npc, 'is_alive', False))

    # Optional: _get_monsters_in_room (not used by core logic but might be useful)
    def _get_monsters_in_room(self, region_id, room_id):
        """Get hostile monsters currently in a specific room."""
        if not self.world or not hasattr(self.world, 'npcs'): return []
        return [npc for npc in self.world.npcs.values() if
                npc and
                npc.current_region_id == region_id and
                npc.current_room_id == room_id and
                getattr(npc, 'faction', 'neutral') == "hostile" and
                getattr(npc, 'is_alive', False)]

    def _weighted_choice(self, choices: Dict[str, int]):
        """Make a weighted random choice."""
        if not choices: return None
        options = list(choices.keys())
        weights = [max(0, w) for w in choices.values()] # Ensure non-negative weights

        total_weight = sum(weights)
        if total_weight <= 0:
            return random.choice(options) if options else None # Equal chance if all weights are 0

        try:
             return random.choices(options, weights=weights, k=1)[0]
        except Exception as e: # Catch potential errors
             print(f"{FORMAT_ERROR}[Spawner] Error in weighted choice: {e}. Choices: {choices}{FORMAT_RESET}")
             return random.choice(options) if options else None

    def _spawn_command_handler(self, args, context):
        """Handler for the spawnmonster command."""
        if not self.world: return f"{FORMAT_ERROR}World not available{FORMAT_RESET}"
        if not hasattr(self.world, 'npc_templates'): return f"{FORMAT_ERROR}NPC templates not loaded{FORMAT_RESET}"

        if not args:
            hostile_template_ids = sorted([
                tid for tid, template in self.world.npc_templates.items()
                if isinstance(template, dict) and template.get('faction') == 'hostile'
            ])
            monster_list_str = ', '.join(hostile_template_ids) if hostile_template_ids else "(None found)"
            return f"Available monster template IDs: {monster_list_str}\n\nUsage: spawnmonster <monster_template_id> [level]"

        monster_template_id = args[0]
        level = 1
        if len(args) > 1:
            try: level = max(1, int(args[1]))
            except ValueError: return f"{FORMAT_ERROR}Invalid level.{FORMAT_RESET}"

        # Check if template exists *before* creating overrides
        if monster_template_id not in self.world.npc_templates:
             return f"{FORMAT_ERROR}Template ID '{monster_template_id}' not found.{FORMAT_RESET}"
        # Check if it's actually hostile
        if self.world.npc_templates[monster_template_id].get('faction') != 'hostile':
             return f"{FORMAT_ERROR}Template '{monster_template_id}' exists but is not hostile.{FORMAT_RESET}"


        overrides = {
            "level": level,
            "current_region_id": self.world.current_region_id,
            "current_room_id": self.world.current_room_id,
            "home_region_id": self.world.current_region_id,
            "home_room_id": self.world.current_room_id
        }
        # Use NPCFactory
        monster = NPCFactory.create_npc_from_template(monster_template_id, self.world, **overrides)

        if not monster: # Should not happen if template check passed, but safety
            return f"{FORMAT_ERROR}Failed to create monster from template ID: {monster_template_id}{FORMAT_RESET}"

        # Add level to name if desired
        if level > 1: monster.name = f"{monster.name} (Level {level})"

        self.world.add_npc(monster)
        self.total_spawned += 1

        player = self.world.player # Get player for formatting context
        formatted_name = format_target_name(player, monster) if player else monster.name
        return f"{FORMAT_SUCCESS}{formatted_name} appears!{FORMAT_RESET}"


    def _monsters_command_handler(self, args, context):
        """Handler for the monsters command."""
        if not self.world or not hasattr(self.world, 'npcs'): return f"{FORMAT_ERROR}World/NPCs not available{FORMAT_RESET}"

        monsters_by_region: Dict[str, List[NPC]] = {}
        total_monsters = 0

        for npc in self.world.npcs.values():
            if npc and getattr(npc, 'faction', 'neutral') == "hostile" and getattr(npc, 'is_alive', False):
                region = npc.current_region_id or "unknown_region"
                if region not in monsters_by_region: monsters_by_region[region] = []
                monsters_by_region[region].append(npc)
                total_monsters += 1

        if total_monsters == 0: return "No active monsters found in the world."

        result = f"{FORMAT_TITLE}ACTIVE MONSTERS ({total_monsters}){FORMAT_RESET}\n\n"
        target_region_id = args[0].lower() if args else None
        player = self.world.player # Get player for formatting

        if target_region_id:
            if target_region_id in monsters_by_region:
                 monsters = sorted(monsters_by_region[target_region_id], key=lambda m: (m.current_room_id or "", m.name or ""))
                 result += f"{FORMAT_CATEGORY}Monsters in region '{target_region_id}':{FORMAT_RESET}\n"
                 for monster in monsters:
                      formatted_name = format_target_name(player, monster) if player else monster.name
                      room_id_str = monster.current_room_id or "unknown_room"
                      result += f"- {formatted_name} ({monster.health}/{monster.max_health} HP) in room '{room_id_str}'\n"
            else:
                 result += f"No active monsters found in region '{target_region_id}'."
        else:
            for region_id in sorted(monsters_by_region.keys()):
                count = len(monsters_by_region[region_id])
                result += f"{FORMAT_CATEGORY}Region: {region_id}{FORMAT_RESET} ({count} monster{'s' if count != 1 else ''})\n"
            result += "\nUse 'monsters <region_id>' to list monsters in a specific region."

        return result

    def cleanup(self):
        """Clean up plugin resources."""
        if self.event_system:
            self.event_system.unsubscribe("on_tick", self._on_tick)
        print("Monster spawner plugin cleaned up.")