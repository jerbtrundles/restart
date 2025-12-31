import time
from unittest.mock import patch
from tests.fixtures import GameTestBase
from engine.world.region_generator import RegionGenerator
from engine.npcs.npc_factory import NPCFactory

class TestBatchQuestFlow(GameTestBase):
    """
    Stress tests for the full lifecycle of dynamic instance quests.
    """
    
    def test_instance_quest_lifecycle(self):
        """Full run-through: Accept -> Enter -> Kill -> Complete -> Cleanup."""
        qm = self.world.quest_manager
        
        # 1. Setup Data for Generation
        self.world.npc_templates["boss_mob"] = {"name": "Boss", "faction": "hostile", "level": 1, "health": 10}
        
        qm.instance_quest_templates = {
            "test_dungeon": {
                "type": "instance",
                "title": "Kill the Boss",
                "level": 1,
                "objective": {"type": "clear_region", "possible_target_template_ids": ["boss_mob"]},
                "layout_generation_config": {"min_rooms": 3, "max_rooms": 3, "target_count": [1, 1]},
                "possible_entry_regions": ["town"]
            }
        }
        
        # 2. Generate and Accept
        quest = qm.generator.generate_instance_quest(1)
        self.assertIsNotNone(quest, "Failed to generate instance quest")
        
        if quest:
            # Manually accept to bypass board UI logic, but trigger instantiation
            quest_id = quest["instance_id"]
            quest["state"] = "active"
            quest["completion_check_enabled"] = False # Logic enables this on entry
            
            # Instantiate Region
            success, msg, giver_id = self.world.instantiate_quest_region(quest)
            self.assertTrue(success, f"Instantiation failed: {msg}")
            
            self.player.quest_log[quest_id] = quest
            
            # 3. Check Portal Linkage
            # Quest config usually links to town_square if town is possible region
            region = self.world.get_region("town")
            self.assertIsNotNone(region)
            if region:
                found_portal = False
                portal_room = None
                for room in region.rooms.values():
                    if "house" in room.exits: # "house" is the default exit command in generator
                        found_portal = True
                        portal_room = room
                        break
                self.assertTrue(found_portal, "Portal not found in town region")
                
                # 4. Enter Instance
                if portal_room:
                    # Move player to portal room first
                    self.player.current_region_id = "town"
                    self.player.current_room_id = portal_room.obj_id
                    
                    # FIX: Sync World location too, as change_room uses world.current_room_id to calculate exits
                    self.world.current_region_id = "town"
                    self.world.current_room_id = portal_room.obj_id
                    
                    # Enter
                    self.world.change_room("house")
                    
                    # Assert Entry
                    self.assertIsNotNone(self.player.current_region_id)
                    if self.player.current_region_id:
                        self.assertTrue(self.player.current_region_id.startswith("instance_"), "Failed to enter instance")
                    
                    # Verify Quest Trigger (completion check enabled)
                    self.assertTrue(self.player.quest_log[quest_id]["completion_check_enabled"])

            # 5. Kill Target
            # Find the boss in the instance
            current_reg_id = self.player.current_region_id
            if current_reg_id:
                instance_region = self.world.get_region(current_reg_id)
                self.assertIsNotNone(instance_region)
                
                if instance_region:
                    boss = None
                    for npc in self.world.npcs.values():
                        if npc.template_id == "boss_mob" and npc.current_region_id == instance_region.obj_id:
                            boss = npc
                            break
                    
                    self.assertIsNotNone(boss, "Boss not found in instance")
                    
                    # Kill boss
                    if boss:
                        boss.health = 0
                        boss.is_alive = False
                        
                        # Trigger update
                        self.world.quest_manager.check_quest_completion()
                        
                        # 6. Verify Completion State
                        self.assertEqual(self.player.quest_log[quest_id]["state"], "ready_to_complete")
                    
                    # 7. Cleanup
                    # Simulate turn-in
                    # (We just call cleanup directly to verify world state)
                    self.player.completed_quest_log[quest_id] = self.player.quest_log.pop(quest_id)
                    self.world.cleanup_quest_region(quest_id)
                    
                    # Verify region gone
                    self.assertNotIn(instance_region.obj_id, self.world.regions)
                    
            # Verify portal gone
            if portal_room:
                self.assertNotIn("house", portal_room.exits)