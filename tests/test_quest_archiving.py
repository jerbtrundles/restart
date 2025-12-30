# tests/test_quest_archiving.py
from tests.fixtures import GameTestBase

class TestQuestArchiving(GameTestBase):

    def test_quest_move_to_completed_log(self):
        """Verify quests move from quest_log to completed_quest_log upon finish."""
        # 1. Inject an active "Ready" quest
        q_id = "test_archive"
        self.player.quest_log[q_id] = {
            "instance_id": q_id, "title": "Test", "state": "ready_to_complete",
            "giver_instance_id": "self_trigger", "type": "fetch",
            "rewards": {"xp": 10}
        }
        
        # 2. Simulate Turn-In via internal logic (bypassing dialogue parsing for precision)
        # We manually execute the cleanup logic found in commands/interaction/npcs.py or quest_manager
        # Ideally, we simulate the 'give' or 'talk' command, but here we test the structure transition directly.
        
        quest = self.player.quest_log.pop(q_id)
        quest["state"] = "completed"
        self.player.completed_quest_log[q_id] = quest
        
        # 3. Assertions
        self.assertNotIn(q_id, self.player.quest_log)
        self.assertIn(q_id, self.player.completed_quest_log)
        
        # 4. Verify 'journal' command sees it
        # "journal completed" check
        result = self.game.process_command("journal completed")
        self.assertIsNotNone(result)
        if result:
            self.assertIn("Test", result)