# tests/test_npc_naming.py
from tests.fixtures import GameTestBase
from engine.npcs.npc_factory import NPCFactory

class TestNPCNaming(GameTestBase):

    def test_procedural_wandering_names(self):
        """Verify that wandering NPCs receive randomized names."""
        # The factory uses VILLAGER_FIRST_NAMES lists for these templates
        template_id = "wandering_villager"
        
        # Create several to check for variety
        name1 = NPCFactory.create_npc_from_template(template_id, self.world)
        name2 = NPCFactory.create_npc_from_template(template_id, self.world)
        
        self.assertIsNotNone(name1)
        self.assertIsNotNone(name2)
        
        if name1 and name2:
            # They should both end with "the Villager" (default title for that template)
            self.assertTrue(name1.name.endswith("the Villager"))
            self.assertTrue(name2.name.endswith("the Villager"))
            
            # Statistically, with 40+ names in the pool, 
            # two consecutive names are unlikely to be identical.
            self.assertNotEqual(name1.name, name2.name, "Names should be randomized.")

    def test_static_naming(self):
        """Verify that unique NPCs (like the Elder) keep their specific names."""
        elder = NPCFactory.create_npc_from_template("village_elder", self.world)
        self.assertIsNotNone(elder)
        if elder:
            self.assertEqual(elder.name, "Elder Thorne")