# world/spawner.py
"""
Handles the logic for dynamically spawning monsters in the game world.
"""
import random
import time
from typing import TYPE_CHECKING

from config import (SPAWN_CHANCE_PER_TICK, SPAWN_DEBUG,
                         SPAWN_INTERVAL_SECONDS, SPAWN_MAX_MONSTERS_PER_REGION_CAP,
                         SPAWN_MIN_MONSTERS_PER_REGION,
                         SPAWN_NO_SPAWN_ROOM_KEYWORDS, SPAWN_ROOMS_PER_MONSTER)
from npcs.npc_factory import NPCFactory
from utils.utils import weighted_choice
from world.region import Region

if TYPE_CHECKING:
    from world.world import World


class Spawner:
    def __init__(self, world: 'World'):
        self.world = world
        self.last_spawn_time = 0

    def update(self, current_time: float):
        """Main update tick for the spawner."""
        if current_time - self.last_spawn_time < SPAWN_INTERVAL_SECONDS:
            return
        self.last_spawn_time = current_time

        if random.random() > SPAWN_CHANCE_PER_TICK:
            return

        for region in self.world.regions.values():
            self._spawn_monsters_in_region(region)

    def _count_monsters_in_region(self, region_id: str) -> int:
        """Counts active hostile monsters currently in a region."""
        return sum(1 for npc in self.world.npcs.values() if
                   npc and npc.current_region_id == region_id and
                   npc.faction == "hostile" and npc.is_alive)

    def _spawn_monsters_in_region(self, region: Region):
        """Attempts to spawn a monster in a suitable room within a given region."""
        if self.world.is_location_safe(region.obj_id) or not region.spawner_config:
            return

        num_rooms = len(region.rooms)
        if num_rooms <= 0: return

        # Determine the dynamic monster limit for this region
        ratio = SPAWN_ROOMS_PER_MONSTER
        min_limit = SPAWN_MIN_MONSTERS_PER_REGION
        max_cap = SPAWN_MAX_MONSTERS_PER_REGION_CAP
        calculated_limit = max(1, num_rooms // max(1, ratio))
        dynamic_max_for_region = max(min_limit, min(calculated_limit, max_cap))

        current_monster_count = self._count_monsters_in_region(region.obj_id)
        if current_monster_count >= dynamic_max_for_region:
            return

        # Find a suitable room to spawn in (not player's room, not a no-spawn zone)
        suitable_rooms = []
        player_location = (self.world.current_region_id, self.world.current_room_id)
        for room_id, room in region.rooms.items():
            if not room: continue
            if room.get_property('no_monster_spawn', False): continue
            
            room_name_lower = room.name.lower()
            room_id_lower = room_id.lower()
            if any(keyword in room_id_lower or keyword in room_name_lower for keyword in SPAWN_NO_SPAWN_ROOM_KEYWORDS): continue
            
            # Don't spawn in the player's current room
            if player_location == (region.obj_id, room_id): continue
            suitable_rooms.append(room_id)

        if not suitable_rooms: return
        room_id_to_spawn = random.choice(suitable_rooms)

        # Choose a monster from the region's weighted list
        region_monster_weights = region.spawner_config.get("monster_types", {})
        if not region_monster_weights: return
        monster_template_id = weighted_choice(region_monster_weights)
        if not monster_template_id or monster_template_id not in self.world.npc_templates: return

        level_range = region.spawner_config.get("level_range", [1, 1])
        level = random.randint(level_range[0], level_range[1])
        
        overrides = {
            "level": level,
            "current_region_id": region.obj_id,
            "current_room_id": room_id_to_spawn,
            "home_region_id": region.obj_id,
            "home_room_id": room_id_to_spawn
        }
        monster = NPCFactory.create_npc_from_template(monster_template_id, self.world, **overrides)

        if monster:
            self.world.add_npc(monster)
            if SPAWN_DEBUG and self.world.game:
                 self.world.game.renderer.add_message(f"[SpawnerDebug] Spawned {monster.name} in {region.obj_id}:{room_id_to_spawn}")
