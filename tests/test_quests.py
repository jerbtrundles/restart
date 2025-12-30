# tests/test_quests.py
from tests.fixtures import GameTestBase
from engine.npcs.npc_factory import NPCFactory
from engine.items.item_factory import ItemFactory

class TestQuests(GameTestBase):

    def test_quest_lifecycle_kill(self):
        """Verify full lifecycle of a Kill quest."""
        # 1. Setup Board
        quest_id = "test_kill_quest"
        self.world.quest_board = [{
            "instance_id": quest_id,
            "title": "Kill Rats",
            "type": "kill",
            "giver_instance_id": "quest_board",
            "rewards": {"xp": 100},
            "objective": {"target_template_id": "giant_rat", "required_quantity": 1}
        }]
        
        # 2. Accept
        self.game.process_command("accept quest 1")
        self.assertIn(quest_id, self.player.quest_log)
        
        # 3. Complete Objective
        rat = NPCFactory.create_npc_from_template("giant_rat", self.world)
        if rat:
            self.world.dispatch_event("npc_killed", {"player": self.player, "npc": rat})
            self.assertEqual(self.player.quest_log[quest_id]["state"], "ready_to_complete")

    def test_quest_fetch_mechanics(self):
        """Verify Fetch quests remove items from inventory."""
        # CRITICAL FIX: Clear default NPCs to prevent ambiguity (Two "Elder Thorne"s)
        self.world.npcs = {}

        # 1. Setup Quest manually in log
        quest_id = "test_fetch"
        giver = NPCFactory.create_npc_from_template("village_elder", self.world, instance_id="elder_1")
        
        # Ensure giver is spawned and co-located
        if giver:
            self.world.add_npc(giver)
            if self.player.current_region_id and self.player.current_room_id:
                giver.current_region_id = self.player.current_region_id
                giver.current_room_id = self.player.current_room_id
            
            self.player.quest_log[quest_id] = {
                "instance_id": quest_id,
                "type": "fetch",
                "state": "ready_to_complete",
                "giver_instance_id": "elder_1",
                "rewards": {"gold": 100},
                "objective": {"item_id": "item_iron_ingot", "required_quantity": 1}
            }
            
            # 2. Give Items
            ingot = ItemFactory.create_item_from_template("item_iron_ingot", self.world)
            if ingot: self.player.inventory.add_item(ingot)
            
            # 3. Turn In
            result = self.game.process_command(f"talk {giver.name} complete")
            
            # 4. Assert
            self.assertIsNotNone(result)
            if result:
                self.assertIn("Quest Complete", result)
            
            self.assertEqual(self.player.inventory.count_item("item_iron_ingot"), 0)
            self.assertEqual(self.player.gold, 100)

    def test_quest_deliver_mechanics(self):
        """Verify Deliver quests work with 'give' command."""
        # 1. Setup Recipient
        recipient = NPCFactory.create_npc_from_template("tavern_keeper", self.world, instance_id="recipient_1")
        if recipient:
            self.world.add_npc(recipient)
            # Ensure co-location for 'give' command to work
            if self.player.current_region_id and self.player.current_room_id:
                recipient.current_region_id = self.player.current_region_id
                recipient.current_room_id = self.player.current_room_id

            # 2. Setup Quest
            package_id = "pkg_123"
            self.player.quest_log["test_deliver"] = {
                "instance_id": "test_deliver",
                "type": "deliver",
                "state": "active",
                "giver_instance_id": "sender",
                "rewards": {"xp": 50},
                "objective": {
                    "item_instance_id": package_id,
                    "recipient_instance_id": "recipient_1",
                    "item_to_deliver_name": "Package"
                }
            }
            
            # 3. Add Package to Inventory
            package = ItemFactory.create_item_from_template("quest_package_generic", self.world)
            if package:
                package.obj_id = package_id
                package.name = "Package"
                self.player.inventory.add_item(package)
                
            # 4. Deliver
            result = self.game.process_command(f"give Package to {recipient.name}")
            
            # 5. Assert
            self.assertIsNotNone(result)
            if result:
                self.assertIn("Quest Complete", result)
            
            self.assertIsNone(self.player.inventory.find_item_by_id(package_id))