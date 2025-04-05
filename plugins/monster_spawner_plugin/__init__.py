# plugins/monster_spawner_plugin/__init__.py
"""
Monster spawner plugin for the MUD game.
Periodically spawns monsters in the world.
"""
from typing import Dict, List, Any, Optional, Tuple
import random
import time
from core.config import FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE # Added missing imports
from plugins.plugin_system import PluginBase
from npcs.npc import NPC
from npcs.monster_factory import MonsterFactory
# from utils.text_formatter import TextFormatter # Not used directly

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

        # Import config from the config.py file
        from .config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG.copy() # Use defaults from config file

        # Spawn tracking
        self.last_spawn_time = 0
        self.total_spawned = 0
        # self.active_monsters = {}  # Removed - counting dynamically is better

    def initialize(self):
        """Initialize the plugin."""
        if self.event_system:
            self.event_system.subscribe("on_tick", self._on_tick)
            # No need to subscribe to room enter here, spawning is time-based

        # Register commands
        self._register_commands()

        ratio = self.config.get('rooms_per_monster', 5)
        min_m = self.config.get('min_monsters_per_region', 1)
        max_cap = self.config.get('max_monsters_per_region_cap', 15)
        print(f"Monster spawner plugin initialized. Spawn interval: {self.config['spawn_interval']}s. Target: ~1 monster / {ratio} rooms (Min: {min_m}, Max Cap: {max_cap}).")

        self.last_spawn_time = time.time() # Initialize last spawn time

    def _register_commands(self):
        """Register plugin commands."""
        if not hasattr(self, "service_locator") or not self.service_locator:
            print(f"{FORMAT_ERROR}Warning: ServiceLocator not available for MonsterSpawnerPlugin command registration.{FORMAT_RESET}")
            return

        try:
            from plugins.plugin_system import register_plugin_command

            register_plugin_command(
                self.plugin_id,
                "spawnmonster", # Changed command name slightly to avoid conflict?
                self._spawn_command_handler,
                aliases=["spawnmob"],
                category="debug", # Changed category to debug
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
            print(f"Error registering MonsterSpawner commands: {e}")

    def _on_tick(self, event_type, data):
        """Handle tick events for monster spawning."""
        # Use game time if available, otherwise fallback to real time
        current_time = time.time()
        # TODO: If TimePlugin exists, use game time for more deterministic spawning relative to game days/hours?
        # time_plugin = self.service_locator.get_service("plugin:time_plugin")
        # current_game_time = time_plugin.game_time if time_plugin else current_time

        # Check if it's time to spawn
        if current_time - self.last_spawn_time < self.config["spawn_interval"]:
            return

        self.last_spawn_time = current_time

        # Attempt to spawn monsters in each region
        if self.world and hasattr(self.world, "regions"):
            for region_id, region in self.world.regions.items():
                self._spawn_monsters_in_region(region_id, region)

    def _spawn_monsters_in_region(self, region_id, region):
        """
        Attempt to spawn monsters in a region.
        """
        if not self.world or not region or not hasattr(region, 'rooms'): return

        # --- Safety/Config Checks ---
        if self.world.is_location_safe(region_id):
             if self.config.get("debug", False) and self.event_system:
                 self.event_system.publish("display_message", f"[SpawnerDebug] Skipping spawn in safe region: {region_id}")
             return

        # --- Calculate Dynamic Max Monsters ---
        num_rooms = len(region.rooms)
        if num_rooms <= 0: return # Don't spawn in empty regions

        ratio = self.config.get("rooms_per_monster", 5)
        min_limit = self.config.get("min_monsters_per_region", 1)
        max_cap = self.config.get("max_monsters_per_region_cap", 15)

        # Calculate based on ratio (ensure at least 1 if ratio > num_rooms)
        # Using integer division // is simple. Using math.ceil might feel slightly better for density.
        # calculated_limit = max(1, math.ceil(num_rooms / ratio)) # Option 1: Ceiling
        calculated_limit = max(1, num_rooms // ratio) # Option 2: Floor (integer division)

        # Apply min and max caps
        dynamic_max_for_region = max(min_limit, min(calculated_limit, max_cap))
        # --- End Calculate Dynamic Max ---

        # --- Check Current Count Against Dynamic Limit ---
        current_monster_count = self._count_monsters_in_region(region_id)
        if current_monster_count >= dynamic_max_for_region:
            if self.config.get("debug", False) and self.event_system:
                # Include calculated limit in debug message
                self.event_system.publish("display_message", f"[SpawnerDebug] Max monsters ({current_monster_count}/{dynamic_max_for_region}) reached in region: {region_id}")
            return
        # --- End Check ---

        if random.random() > self.config.get("spawn_chance", 0.3): # Use .get()
            return

        # --- Find Suitable Room ---
        suitable_rooms = []
        no_spawn_keywords = self.config.get("no_spawn_rooms", [])
        for room_id, room in region.rooms.items():
            is_no_spawn = any(keyword in room_id.lower() or keyword in room.name.lower() for keyword in no_spawn_keywords)
            if is_no_spawn: continue

            # Skip rooms with the player currently in them
            if (self.world.current_region_id == region_id and
                self.world.current_room_id == room_id):
                continue

            # Optional: Check if room already has max monsters? (Could add room cap)
            # if self._count_monsters_in_room(region_id, room_id) >= MAX_PER_ROOM: continue

            suitable_rooms.append(room_id)

        if not suitable_rooms:
            if self.config.get("debug", False) and self.event_system:
                self.event_system.publish("display_message", f"[SpawnerDebug] No suitable spawn rooms in region: {region_id}")
            return

        room_id_to_spawn = random.choice(suitable_rooms)

        # --- Choose Monster Type and Level ---
        region_monster_weights = self.config.get("region_monsters", {}).get(region_id, self.config.get("region_monsters", {}).get("default", {}))
        if not region_monster_weights:
             if self.config.get("debug", False) and self.event_system:
                 self.event_system.publish("display_message", f"[SpawnerDebug] No monster types for region: {region_id}")
             return

        monster_template_id = self._weighted_choice(region_monster_weights)
        if not monster_template_id:
            if self.config.get("debug", False) and self.event_system:
                self.event_system.publish("display_message", f"[SpawnerDebug] Could not choose monster type for: {region_id}")
            return

        level_range = self.config.get("region_levels", {}).get(region_id, self.config.get("region_levels", {}).get("default", [1, 1]))
        level = random.randint(level_range[0], level_range[1])

        # --- Prepare Overrides and Spawn ---
        overrides = {
            "level": level,
            "current_region_id": region_id,
            "current_room_id": room_id_to_spawn,
            "home_region_id": region_id,
            "home_room_id": room_id_to_spawn
        }

        # === FIX: Pass self.world and overrides ===
        monster = MonsterFactory.create_monster(monster_template_id, self.world, **overrides)
        # ==========================================

        if monster:
            self.world.add_npc(monster) # Add to world.npcs using instance ID
            self.total_spawned += 1

            if self.config.get("debug", False) and self.event_system:
                self.event_system.publish(
                    "display_message",
                    f"[SpawnerDebug] Spawned {monster.name} (L{level}) in {region_id}:{room_id_to_spawn}"
                )
        elif self.config.get("debug", False) and self.event_system:
             self.event_system.publish("display_message", f"[SpawnerDebug] Failed to create monster: {monster_template_id}")

    def _count_monsters_in_region(self, region_id):
        """Count active hostile monsters currently in a region."""
        if not self.world: return 0
        return sum(1 for npc in self.world.npcs.values() if
                   npc.current_region_id == region_id and
                   getattr(npc, 'faction', 'neutral') == "hostile" and
                   getattr(npc, 'is_alive', False))

    def _get_monsters_in_room(self, region_id, room_id):
        """Get hostile monsters currently in a specific room."""
        if not self.world: return []
        return [npc for npc in self.world.npcs.values() if
                npc.current_region_id == region_id and
                npc.current_room_id == room_id and
                getattr(npc, 'faction', 'neutral') == "hostile" and
                getattr(npc, 'is_alive', False)]

    def _weighted_choice(self, choices: Dict[str, int]):
        """Make a weighted random choice."""
        if not choices: return None
        options = list(choices.keys())
        weights = list(choices.values())
        try:
             # Ensure weights are valid numbers (non-negative)
             valid_weights = [max(0, w) for w in weights]
             if sum(valid_weights) <= 0: # Handle case where all weights are zero
                  return random.choice(options) if options else None
             return random.choices(options, weights=valid_weights, k=1)[0]
        except ValueError as e: # Catch potential errors from random.choices
             print(f"Error in weighted choice: {e}. Choices: {choices}")
             return random.choice(options) if options else None # Fallback

    def _spawn_command_handler(self, args, context):
        """Handler for the spawnmonster command."""
        if not self.world: return f"{FORMAT_ERROR}World not available{FORMAT_RESET}"

        if not args:
            monster_types = MonsterFactory.get_monster_template_names(self.world)
            return f"Available monster types: {', '.join(monster_types)}\n\nUsage: spawnmonster <monster_template_id> [level]"

        monster_template_id = args[0]
        level = 1

        if len(args) > 1:
            try:
                level = int(args[1])
                if level < 1: level = 1
            except ValueError:
                return f"{FORMAT_ERROR}Invalid level. Usage: spawnmonster <monster_template_id> [level]{FORMAT_RESET}"

        # --- Prepare Overrides ---
        overrides = {
            "level": level,
            "current_region_id": self.world.current_region_id,
            "current_room_id": self.world.current_room_id,
            "home_region_id": self.world.current_region_id,
            "home_room_id": self.world.current_room_id
        }

        # === FIX: Pass self.world and overrides ===
        monster = MonsterFactory.create_monster(monster_template_id, self.world, **overrides)
        # ==========================================

        if not monster:
            return f"{FORMAT_ERROR}Failed to create monster from template: {monster_template_id}{FORMAT_RESET}"

        self.world.add_npc(monster)
        self.total_spawned += 1

        return f"{FORMAT_SUCCESS}{monster.name} appears!{FORMAT_RESET}"

    def _monsters_command_handler(self, args, context):
        """Handler for the monsters command."""
        if not self.world: return f"{FORMAT_ERROR}World not available{FORMAT_RESET}"

        monsters_by_region: Dict[str, List[NPC]] = {}
        total_monsters = 0

        for npc in self.world.npcs.values():
            if getattr(npc, 'faction', 'neutral') == "hostile" and getattr(npc, 'is_alive', False):
                region = npc.current_region_id or "unknown"
                if region not in monsters_by_region:
                    monsters_by_region[region] = []
                monsters_by_region[region].append(npc)
                total_monsters += 1

        if total_monsters == 0: return "No active monsters found in the world."

        result = f"{FORMAT_TITLE}ACTIVE MONSTERS ({total_monsters}){FORMAT_RESET}\n\n"

        target_region_id = args[0].lower() if args else None

        if target_region_id:
            if target_region_id in monsters_by_region:
                 monsters = monsters_by_region[target_region_id]
                 monsters.sort(key=lambda m: m.current_room_id) # Sort by room
                 result += f"{FORMAT_CATEGORY}Monsters in region '{target_region_id}':{FORMAT_RESET}\n"
                 for monster in monsters:
                      # Format name with level color coding
                      player = self.world.player # Assuming player exists
                      formatted_name = format_target_name(player, monster) if player else monster.name

                      result += f"- {formatted_name} ({monster.health}/{monster.max_health} HP) in room {monster.current_room_id}\n"
            else:
                 result += f"No active monsters found in region '{target_region_id}'."
        else:
            # Show summary by region, sorted
            for region_id in sorted(monsters_by_region.keys()):
                monsters = monsters_by_region[region_id]
                result += f"{FORMAT_CATEGORY}Region: {region_id}{FORMAT_RESET} ({len(monsters)} monsters)\n"
                # Optionally list a few monsters per region for summary
                # for monster in sorted(monsters, key=lambda m: m.name)[:5]: # Show top 5 sorted by name
                #    result += f"- {monster.name} (L{monster.level})\n"
                # if len(monsters) > 5: result += "- ... and others\n"
                result += "\n"
            result += "Use 'monsters <region_id>' to list monsters in a specific region."


        return result

    def cleanup(self):
        """Clean up plugin resources."""
        if self.event_system:
            self.event_system.unsubscribe("on_tick", self._on_tick)

# Required imports for type checking
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from world.world import World
    from utils.text_formatter import format_target_name # Import for the monster list command