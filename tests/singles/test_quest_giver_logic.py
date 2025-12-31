# tests/singles/test_quest_giver_logic.py
from tests.fixtures import GameTestBase
from engine.npcs.npc_factory import NPCFactory

class TestQuestGiverLogic(GameTestBase):
    
    def test_npc_quest_interests(self):
        """Verify that quest board replenishment respects NPC interests."""
        qm = self.world.quest_manager
        
        # 1. Setup a specific NPC interest
        self.world.npc_templates["quest_npc"] = {
            "name": "Quest NPC", "faction": "friendly",
            "properties": { "can_give_generic_quests": True, "quest_interests": ["kill"] }
        }
        
        # 2. IMPORTANT: Setup a hostile target template. 
        # The generator needs an enemy to exist to successfully build a 'kill' quest.
        self.world.npc_templates["target_mob"] = {
            "name": "Target Mob", "faction": "hostile", "level": 1
        }
        
        npc = NPCFactory.create_npc_from_template("quest_npc", self.world)
        if npc:
            # Ensure NPC is in a valid region for the generator to associate with
            npc.current_region_id = "town"
            self.world.add_npc(npc)
            
        # 3. Trigger replenishment
        qm.npc_interests["quest_npc"] = ["kill"]
        self.world.quest_board = [] # Clear board
        
        # 4. Generate
        # ensure_initial_quests uses Variety logic first
        qm.ensure_initial_quests()
        
        # 5. Assert
        # There should be at least one 'kill' quest since our NPC interest forces it
        found_kill = any(q.get("type") == "kill" for q in self.world.quest_board)
        self.assertTrue(found_kill, "Quest board should have generated a kill quest for our NPC.")