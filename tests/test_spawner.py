# tests/test_spawner.py
import time
from unittest.mock import patch, MagicMock
from tests.fixtures import GameTestBase
from engine.world.spawner import Spawner
from engine.world.region import Region
from engine.world.room import Room
from engine.npcs.npc_factory import NPCFactory

class TestSpawner(GameTestBase):
    
    def test_spawn_caps_and_cooldowns(self):
        """Verify spawner respects population limits and time intervals."""
        spawner = Spawner(self.world)
        
        # 1. Setup a region with aggressive spawning
        region = Region("Spawn Test Zone", "Testing", obj_id="test_zone")
        # Add a room
        room = Room("Spawn Room", "Empty", obj_id="spawn_room")
        region.add_room("spawn_room", room)
        
        region.spawner_config = {
            "monster_types": {"goblin": 1},
            "level_range": [1, 1]
        }
        # Ensure not safe
        region.properties["safe_zone"] = False 
        
        self.world.add_region("test_zone", region)
        self.world.current_region_id = "test_zone" # Player must be in region for spawner to activate
        self.world.current_room_id = "other_room" # Player shouldn't be in spawn room ideally, though config allows it usually
        
        # Add a secondary room for the player to be in so they don't block the spawn room logic
        player_room = Room("Player Room", "Safe", obj_id="player_room")
        region.add_room("player_room", player_room)
        self.player.current_region_id = "test_zone"
        self.player.current_room_id = "player_room"

        # 2. Mock NPCFactory to ensure it doesn't fail on "goblin" template
        # We'll rely on the actual factory if the template exists, otherwise mock
        if "goblin" not in self.world.npc_templates:
             self.world.npc_templates["goblin"] = {
                 "name": "Goblin", "description": "Ugly.", "faction": "hostile", "health": 10
             }

        # 3. First Spawn Tick
        # Force RNG to always spawn (random() returns 0.0)
        with patch('random.random', return_value=0.0): 
            spawner.update(time.time())
            
        # Count hostiles
        hostiles = [n for n in self.world.npcs.values() 
                    if n.faction == "hostile" and n.current_region_id == "test_zone"]
        initial_count = len(hostiles)
        self.assertGreater(initial_count, 0, "Spawner should have created a goblin.")
        
        # 4. Test Cooldown (Immediate Update)
        # 0.1s passed, cooldown is typically 5.0s
        spawner.update(time.time() + 0.1) 
        hostiles_after_fast = [n for n in self.world.npcs.values() 
                               if n.faction == "hostile" and n.current_region_id == "test_zone"]
        self.assertEqual(len(hostiles_after_fast), initial_count, "Should not spawn during cooldown.")
        
        # 5. Test Cap
        # Manually fill the region with Goblins to exceed typical cap (3-5)
        for i in range(10):
            g = NPCFactory.create_npc_from_template("goblin", self.world, instance_id=f"extra_goblin_{i}")
            if g:
                g.current_region_id = "test_zone"
                g.current_room_id = "spawn_room"
                self.world.add_npc(g)
            
        # Try to spawn again after significant time
        with patch('random.random', return_value=0.0):
            spawner.update(time.time() + 100.0)
            
        # Ensure we didn't exceed logic (count should stay same, no new ones)
        final_count = len([n for n in self.world.npcs.values() 
                           if n.faction == "hostile" and n.current_region_id == "test_zone"])
        
        # We added 10 manually + 1 initial = 11. Spawner shouldn't add more.
        self.assertEqual(final_count, 10 + initial_count)