# tests/test_quest_concurrency.py
from tests.fixtures import GameTestBase
from engine.npcs.npc_factory import NPCFactory

class TestQuestConcurrency(GameTestBase):

    def test_double_dipping_kills(self):
        """Verify killing one monster updates multiple active quests for that target."""
        # 1. Setup two identical quests from different givers
        q1_id = "kill_rats_guild"
        q2_id = "kill_rats_baker"
        
        target_template = "giant_rat"
        
        self.player.quest_log[q1_id] = {
            "instance_id": q1_id, "type": "kill", "state": "active",
            "title": "Guild Rat Hunt",
            "objective": {"target_template_id": target_template, "required_quantity": 5, "current_quantity": 0}
        }
        
        self.player.quest_log[q2_id] = {
            "instance_id": q2_id, "type": "kill", "state": "active",
            "title": "Baker's Rat Problem",
            "objective": {"target_template_id": target_template, "required_quantity": 3, "current_quantity": 0}
        }
        
        # 2. Create and Kill ONE rat
        rat = NPCFactory.create_npc_from_template(target_template, self.world)
        if rat:
            # Simulate death event
            self.world.dispatch_event("npc_killed", {"player": self.player, "npc": rat})
            
            # 3. Assert BOTH quests updated
            q1_progress = self.player.quest_log[q1_id]["objective"]["current_quantity"]
            q2_progress = self.player.quest_log[q2_id]["objective"]["current_quantity"]
            
            self.assertEqual(q1_progress, 1, "First quest should update.")
            self.assertEqual(q2_progress, 1, "Second quest should update from the same kill.")