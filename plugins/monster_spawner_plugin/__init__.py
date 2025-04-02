"""
plugins/monster_spawner_plugin/__init__.py
Monster spawner plugin for the MUD game.
Periodically spawns monsters in the world.
"""
from typing import Dict, List, Any, Optional, Tuple
import random
import time
from plugins.plugin_system import PluginBase
from npcs.npc import NPC
from npcs.monster_factory import MonsterFactory
from utils.text_formatter import TextFormatter

class MonsterSpawnerPlugin(PluginBase):
    """Plugin that spawns monsters in the world."""
    
    plugin_id = "monster_spawner_plugin"
    plugin_name = "Monster Spawner"
    
    def __init__(self, world=None, command_processor=None, event_system=None, 
                 data_provider=None, service_locator=None):
        """Initialize the monster spawner plugin."""
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator
        
        # Spawn configuration
        self.config = {
            # How often to attempt spawns (in seconds)
            "spawn_interval": 120,
            
            # Maximum monsters per region
            "max_monsters_per_region": 10,
            
            # Chance to spawn a monster on each attempt (0.0-1.0)
            "spawn_chance": 0.3,
            
            # Rooms that shouldn't have monsters spawn in them
            "no_spawn_rooms": ["town_square", "tavern", "inn", "shop"],
            
            # Weighted monster types by region (region_id -> monster types)
            "region_monsters": {
                "default": {
                    "goblin": 3,
                    "wolf": 3,
                    "giant_rat": 2,
                    "skeleton": 1
                },
                "forest": {
                    "wolf": 5,
                    "goblin": 2,
                    "giant_rat": 1
                },
                "cave": {
                    "giant_rat": 4,
                    "goblin": 2,
                    "skeleton": 3
                },
                "dungeon": {
                    "skeleton": 5,
                    "goblin": 2,
                    "troll": 1
                }
            },
            
            # Level ranges by region (region_id -> [min, max])
            "region_levels": {
                "default": [1, 3],
                "forest": [1, 4],
                "cave": [2, 5],
                "dungeon": [4, 8]
            },
            
            # Debug mode
            "debug": False
        }
        
        # Spawn tracking
        self.last_spawn_time = 0
        self.total_spawned = 0
        self.active_monsters = {}  # region_id -> count
        
    def initialize(self):
        """Initialize the plugin."""
        if self.event_system:
            self.event_system.subscribe("on_tick", self._on_tick)
            self.event_system.subscribe("on_room_enter", self._on_room_enter)
            
        # Register commands
        self._register_commands()
        
        print(f"Monster spawner plugin initialized. Will spawn every {self.config['spawn_interval']} seconds.")
    
    def _register_commands(self):
        """Register plugin commands."""
        if not hasattr(self, "service_locator") or not self.service_locator:
            return
            
        try:
            from plugins.plugin_system import register_plugin_command
            
            # Register the spawn command
            register_plugin_command(
                self.plugin_id,
                "spawn",
                self._spawn_command_handler,
                aliases=["spawnmonster"],
                category="monster",
                help_text="Spawn a monster in the current room.\n\nUsage: spawn <monster_type> [level]"
            )
            
            # Register the monsters command
            register_plugin_command(
                self.plugin_id,
                "monsters",
                self._monsters_command_handler,
                aliases=["listmonsters"],
                category="monster",
                help_text="List all active monsters in the world or current region."
            )

        except Exception as e:
            print(f"Error registering commands: {e}")
    
    def _on_tick(self, event_type, data):
        """Handle tick events for monster spawning."""
        current_time = time.time()
        
        # Check if it's time to spawn
        if current_time - self.last_spawn_time < self.config["spawn_interval"]:
            return
            
        self.last_spawn_time = current_time
        
        # Attempt to spawn monsters in each region
        if self.world and hasattr(self.world, "regions"):
            for region_id, region in self.world.regions.items():
                self._spawn_monsters_in_region(region_id, region)
    
    def _on_room_enter(self, event_type, data):
        """Handle room enter events."""
        if len(data) >= 2:
            region_id, room_id = data
            
            # Check for monsters in the room
            monsters = self._get_monsters_in_room(region_id, room_id)
            
            # Notify player about monsters
            if monsters and self.event_system:
                for monster in monsters:
                    message = f"{TextFormatter.FORMAT_ERROR}{monster.name} is here and looks hostile!{TextFormatter.FORMAT_RESET}"
                    self.event_system.publish("display_message", message)
    
    def _spawn_monsters_in_region(self, region_id, region):
        """
        Attempt to spawn monsters in a region.
        
        Args:
            region_id: The ID of the region
            region: The Region object
        """
        if self.world.is_location_safe(region_id):
             if self.config.get("debug", False) and self.event_system:
                 self.event_system.publish("display_message", f"[Debug Spawner] Skipping spawn in safe region: {region_id}")
             return # Do not spawn in safe regions
        
        # Check if we've reached the maximum for this region
        # (Ensure you have a reliable way to count monsters, _count_monsters_in_region might need adjustment
        # if monsters can move between regions easily)
        if self._count_monsters_in_region(region_id) >= self.config["max_monsters_per_region"]:
            if self.config.get("debug", False) and self.event_system:
                self.event_system.publish("display_message", f"[Debug Spawner] Max monsters reached in region: {region_id}")
            return
        
        # Only spawn with the configured chance
        if random.random() > self.config["spawn_chance"]:
            return
            
        # Get suitable rooms for spawning
        suitable_rooms = []
        for room_id, room in region.rooms.items():
            # Skip no-spawn rooms
            if any(keyword in room_id.lower() for keyword in self.config["no_spawn_rooms"]):
                continue
                
            # Skip rooms with the player in them
            if (self.world.current_region_id == region_id and 
                self.world.current_room_id == room_id):
                continue
                
            suitable_rooms.append(room_id)
        
        if not suitable_rooms:
            if self.config.get("debug", False) and self.event_system:
                self.event_system.publish("display_message", f"[Debug Spawner] No suitable spawn rooms found in region: {region_id}")
            return
            
        # Pick a random room
        room_id = random.choice(suitable_rooms)
        
        # Get monster types for this region
        monster_types = self.config["region_monsters"].get(
            region_id, 
            self.config["region_monsters"]["default"]
        )
        if not monster_types: # Ensure we have monster types to choose from
             if self.config.get("debug", False) and self.event_system:
                 self.event_system.publish("display_message", f"[Debug Spawner] No monster types defined for region: {region_id}")
             return
        
        # Get level range for this region
        level_range = self.config["region_levels"].get(
            region_id,
            self.config["region_levels"]["default"]
        )
        
        # Choose a monster type based on weights
        monster_type = self._weighted_choice(monster_types)
        if not monster_type: # Handle case where weighted choice fails (e.g., empty dict)
            if self.config.get("debug", False) and self.event_system:
                self.event_system.publish("display_message", f"[Debug Spawner] Could not choose monster type for region: {region_id}")
            return

        # Create and add the monster
        monster = MonsterFactory.create_monster(monster_type)
        if monster:
            # Set location
            monster.current_region_id = region_id
            monster.current_room_id = room_id
            monster.spawn_region_id = region_id
            monster.spawn_room_id = room_id
            
            # Scale stats based on level
            level = random.randint(level_range[0], level_range[1])
            if level > 1:
                monster.health = monster.health * level
                monster.max_health = monster.health
                monster.attack_power = monster.attack_power + level - 1
                monster.defense = monster.defense + (level // 2)
                monster.name = f"{monster.name} (Level {level})"
            
            # Add to world
            self.world.add_npc(monster)
            
            # Update tracking
            self.total_spawned += 1
            if region_id not in self.active_monsters:
                self.active_monsters[region_id] = 0
            self.active_monsters[region_id] += 1
            
            if self.config.get("debug", False) and self.event_system:
                self.event_system.publish(
                    "display_message",
                    f"[Debug Spawner] Spawned {monster.name} (Lvl {level}) in {region_id}:{room_id}"
                )
        elif self.config.get("debug", False) and self.event_system:
             self.event_system.publish("display_message", f"[Debug Spawner] Failed to create monster of type: {monster_type}")

    def _count_monsters_in_region(self, region_id):
        """Count monsters in a region."""
        # This check is okay, but be aware monsters might wander out.
        # A more complex system might track spawns per region rather than current location.
        count = 0
        for npc in self.world.npcs.values():
            # Count only hostile, alive NPCs currently in the specified region
            if (npc.current_region_id == region_id and
                npc.faction == "hostile" and # Assuming monsters are 'hostile'
                hasattr(npc, 'is_alive') and npc.is_alive):
                count += 1
        return count
    
    def _get_monsters_in_room(self, region_id, room_id):
        """
        Get monsters in a specific room.
        
        Args:
            region_id: The region ID
            room_id: The room ID
            
        Returns:
            List of monster NPCs in the room
        """
        monsters = []
        for npc in self.world.npcs.values():
            if (npc.current_region_id == region_id and 
                npc.current_room_id == room_id and
                npc.faction == "hostile" and
                npc.is_alive):
                monsters.append(npc)
        return monsters
    
    def _weighted_choice(self, choices):
        """
        Make a weighted random choice.
        
        Args:
            choices: Dictionary of {option: weight}
            
        Returns:
            A randomly selected option based on weights
        """
        options = list(choices.keys())
        weights = list(choices.values())
        
        # Ensure we have options
        if not options:
            return None
            
        # Use random.choices (with an 's') for weighted selection
        return random.choices(options, weights=weights, k=1)[0]
    
    def _spawn_command_handler(self, args, context):
        """
        Handler for the spawn command.
        
        Args:
            args: Command arguments
            context: Command context
            
        Returns:
            Command result message
        """
        if not self.world:
            return "World not available"
            
        if not args:
            # List available monster types
            monster_types = MonsterFactory.get_template_names()
            return f"Available monster types: {', '.join(monster_types)}\n\nUsage: spawn <monster_type> [level]"
        
        monster_type = args[0]
        level = 1
        
        # Check for level argument
        if len(args) > 1:
            try:
                level = int(args[1])
                if level < 1:
                    level = 1
            except ValueError:
                return f"Invalid level. Usage: spawn <monster_type> [level]"
        
        # Create monster
        monster = MonsterFactory.create_monster(monster_type)
        if not monster:
            return f"Unknown monster type: {monster_type}"
            
        # Set location to current room
        monster.current_region_id = self.world.current_region_id
        monster.current_room_id = self.world.current_room_id
        monster.spawn_region_id = self.world.current_region_id
        monster.spawn_room_id = self.world.current_room_id
        
        # Scale stats based on level
        if level > 1:
            monster.health = monster.health * level
            monster.max_health = monster.health
            monster.attack_power = monster.attack_power + level - 1
            monster.defense = monster.defense + (level // 2)
            monster.name = f"{monster.name} (Level {level})"
        
        # Add to world
        self.world.add_npc(monster)
        
        return f"{TextFormatter.FORMAT_SUCCESS}{monster.name} appears!{TextFormatter.FORMAT_RESET}"
    
    def _monsters_command_handler(self, args, context):
        """
        Handler for the monsters command.
        
        Args:
            args: Command arguments
            context: Command context
            
        Returns:
            Command result message
        """
        if not self.world:
            return "World not available"
            
        # Count monsters by region
        monsters_by_region = {}
        total_monsters = 0
        
        for npc in self.world.npcs.values():
            if npc.faction == "hostile" and npc.is_alive:
                region = npc.current_region_id or "unknown"
                if region not in monsters_by_region:
                    monsters_by_region[region] = []
                monsters_by_region[region].append(npc)
                total_monsters += 1
                
        if total_monsters == 0:
            return "No monsters found in the world."
            
        # Format the response
        result = f"{TextFormatter.FORMAT_TITLE}ACTIVE MONSTERS ({total_monsters}){TextFormatter.FORMAT_RESET}\n\n"
        
        # Check for region argument
        if args and args[0] in monsters_by_region:
            region_id = args[0]
            monsters = monsters_by_region[region_id]
            result += f"Monsters in region '{region_id}':\n"
            for monster in monsters:
                result += f"- {monster.name} ({monster.health}/{monster.max_health} HP) in room {monster.current_room_id}\n"
        else:
            # Show summary by region
            for region_id, monsters in monsters_by_region.items():
                result += f"{TextFormatter.FORMAT_CATEGORY}Region: {region_id}{TextFormatter.FORMAT_RESET} ({len(monsters)} monsters)\n"
                for monster in monsters:
                    result += f"- {monster.name} (HP: {monster.health}/{monster.max_health})\n"
                result += "\n"
        
        return result
   
    def cleanup(self):
        """Clean up plugin resources."""
        if self.event_system:
            self.event_system.unsubscribe("on_tick", self._on_tick)
            self.event_system.unsubscribe("on_room_enter", self._on_room_enter)