# tests/singles/test_minion_complex.py
import time
from typing import cast
from unittest.mock import patch
from tests.fixtures import GameTestBase
from engine.npcs.npc_factory import NPCFactory
from engine.npcs.npc import NPC
from engine.npcs.ai import handle_ai

class TestMinionComplex(GameTestBase):
    
    def test_minion_expiry(self):
        """Verify minions despawn after their summon duration ends."""
        minion = NPCFactory.create_npc_from_template("skeleton_minion", self.world)
        self.assertIsNotNone(minion)
        
        if minion:
            minion.properties["owner_id"] = self.player.obj_id
            minion.properties["creation_time"] = time.time()
            minion.properties["summon_duration"] = 10.0 # 10 seconds
            self.world.add_npc(minion)
            
            # 1. Update while still active (5s passed)
            minion.update(self.world, time.time() + 5.0)
            self.assertTrue(minion.is_alive, "Minion should still be alive.")
            
            # 2. Update after expiry (11s passed)
            # Minion behavior logic marks it as dead
            handle_ai(minion, self.world, time.time() + 11.0, self.player)
            self.assertFalse(minion.is_alive, "Minion should be marked dead after duration.")
            
            # 3. Trigger World update to perform cleanup
            self.world.update()
            
            self.assertNotIn(minion.obj_id, self.world.npcs, "Minion should be removed from world dictionary.")

    def test_minion_kill_credits_player(self):
        """Verify player gains XP when their minion kills a target."""
        minion = NPCFactory.create_npc_from_template("skeleton_minion", self.world)
        target = NPCFactory.create_npc_from_template("giant_rat", self.world)
        
        self.assertIsNotNone(minion)
        self.assertIsNotNone(target)
        
        if minion and target and self.player:
            # Setup locations and ownership
            rid, room_id = "town", "town_square"
            minion.current_region_id, minion.current_room_id = rid, room_id
            target.current_region_id, target.current_room_id = rid, room_id
            self.player.current_region_id, self.player.current_room_id = rid, room_id
            
            minion.properties["owner_id"] = self.player.obj_id
            
            self.world.add_npc(minion)
            self.world.add_npc(target)
            
            # Target is almost dead
            target.health = 1
            start_xp = self.player.experience
            
            # Perform attack
            from engine.npcs import combat as npc_combat
            minion.enter_combat(target)
            
            # Patch random.random to 0.0 to ensure a hit and deterministic outcome
            with patch('random.random', return_value=0.0):
                # We use a large time offset to ensure cooldowns are passed
                npc_combat.try_attack(minion, self.world, time.time() + 1000)
            
            # Assertions
            self.assertFalse(target.is_alive, "Target should have been killed by the minion.")
            self.assertGreater(self.player.experience, start_xp, "Player should have received XP for minion's kill.")