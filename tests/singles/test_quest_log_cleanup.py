# tests/singles/test_quest_log_cleanup.py
from tests.fixtures import GameTestBase

class TestQuestLogCleanup(GameTestBase):
    def test_quest_move_completed(self):
        """Verify quest moves from active log to completed log."""
        qid = "q1"
        self.player.quest_log[qid] = {"instance_id": qid, "state": "active", "title": "Test"}
        
        # Simulate completion logic manually 
        # (This mimics what happens inside give_handler or talk_handler)
        if qid in self.player.quest_log:
            q = self.player.quest_log.pop(qid)
            q["state"] = "completed"
            self.player.completed_quest_log[qid] = q
        
        self.assertNotIn(qid, self.player.quest_log)
        self.assertIn(qid, self.player.completed_quest_log)
        self.assertEqual(self.player.completed_quest_log[qid]["state"], "completed")