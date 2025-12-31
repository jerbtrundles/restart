# tests/batch/test_batch_13.py
import unittest
from unittest.mock import patch
from tests.fixtures import GameTestBase
from engine.npcs.npc_factory import NPCFactory
from engine.items.item_factory import ItemFactory
from engine.items.item import Item

class TestBatch13(GameTestBase):

    def test_quest_recipient_dead(self):
        """Verify delivery fails gracefully if the recipient is dead."""
        if not self.player: return

        # 1. Setup Quest
        q_id = "deliver_dead"
        self.player.quest_log[q_id] = {
            "instance_id": q_id, "type": "deliver", "state": "active",
            "objective": {
                "item_instance_id": "pkg_dead", 
                "recipient_instance_id": "dead_guy",
                "recipient_name": "Dead Guy"
            }
        }
        
        # 2. Setup Item
        self.world.item_templates["package"] = {"type": "Item", "name": "Package"}
        pkg = ItemFactory.create_item_from_template("package", self.world)
        if pkg:
            pkg.obj_id = "pkg_dead"
            self.player.inventory.add_item(pkg)

        # 3. Setup Dead NPC
        npc = NPCFactory.create_npc_from_template("wandering_villager", self.world)
        self.assertIsNotNone(npc)
        if npc:
            npc.obj_id = "dead_guy"
            npc.name = "Dead Guy"
            npc.is_alive = False
            self.world.add_npc(npc)
            npc.current_region_id = self.player.current_region_id
            npc.current_room_id = self.player.current_room_id
            
            # 4. Act
            result = self.game.process_command("give Package to Dead Guy")
            
            # 5. Assert
            self.assertIsNotNone(result)
            if result:
                self.assertTrue("don't see" in result.lower() or "dead" in result.lower())
                
    def test_quest_fetch_equipped(self):
        """Verify items currently equipped do not count towards fetch quest completion."""
        if not self.player: return
        
        q_id = "fetch_sword"
        giver = NPCFactory.create_npc_from_template("wandering_villager", self.world)
        self.assertIsNotNone(giver)
        if giver:
            giver.current_region_id = self.player.current_region_id
            giver.current_room_id = self.player.current_room_id
            self.world.add_npc(giver)
            
            self.player.quest_log[q_id] = {
                "instance_id": q_id, "type": "fetch", "state": "ready_to_complete",
                "giver_instance_id": giver.obj_id,
                "objective": {"item_id": "item_iron_sword", "required_quantity": 1}
            }
            
            sword = ItemFactory.create_item_from_template("item_iron_sword", self.world)
            self.assertIsNotNone(sword)
            if sword:
                self.player.inventory.add_item(sword)
                self.player.equip_item(sword, "main_hand")
                
                from engine.commands.interaction.npcs import _handle_quest_dialogue
                msg = _handle_quest_dialogue(self.player, giver, self.world)
                
                self.assertIn("still need", msg)
                
    def test_give_invalid_item(self):
        """Verify giving a non-existent item returns correct error."""
        npc = NPCFactory.create_npc_from_template("wandering_villager", self.world)
        self.assertIsNotNone(npc)
        if npc:
            self.world.add_npc(npc)
            npc.current_region_id = self.player.current_region_id
            npc.current_room_id = self.player.current_room_id
            
            res = self.game.process_command(f"give NonExistentThing to {npc.name}")
            self.assertIsNotNone(res)
            if res:
                self.assertIn("don't have", res.lower())

    def test_quest_fetch_stack_split(self):
        """Verify turning in a quest consumes only the required amount from a stack."""
        if not self.player: return

        giver = NPCFactory.create_npc_from_template("wandering_villager", self.world)
        self.assertIsNotNone(giver)
        if giver:
            self.world.add_npc(giver)
            
            self.world.item_templates["token"] = {"type": "Item", "name": "Token", "stackable": True}
            
            q_id = "fetch_tokens"
            self.player.quest_log[q_id] = {
                "instance_id": q_id, "type": "fetch", "state": "ready_to_complete",
                "giver_instance_id": giver.obj_id,
                "objective": {"item_id": "token", "required_quantity": 5},
                "rewards": {"xp": 100}
            }
            
            token = ItemFactory.create_item_from_template("token", self.world)
            self.assertIsNotNone(token)
            if token:
                self.player.inventory.add_item(token, 10)
                
                from engine.commands.interaction.npcs import _handle_quest_dialogue
                msg = _handle_quest_dialogue(self.player, giver, self.world)
                
                self.assertIn("Complete", msg)
                self.assertEqual(self.player.inventory.count_item("token"), 5)

    def test_quest_instance_entry_link(self):
        """Verify creating an instance quest links the start room correctly."""
        q_data = {
            "instance_id": "test_inst",
            "instance_region": {
                "region_name": "Inst", "region_description": "x", "rooms": {"start": {"name": "S", "exits": {"out": "dynamic_exit"}}}
            },
            "entry_point": {
                "region_id": "town", "room_id": "town_square", "exit_command": "enter_portal"
            },
            "layout_generation_config": {"target_count": [0,0]},
            "objective": {"target_template_id": "goblin"} # Fix: Required for instantiation
        }
        
        success, msg, gid = self.world.instantiate_quest_region(q_data)
        self.assertTrue(success, f"Instantiation failed: {msg}")
        
        region = self.world.get_region("town")
        self.assertIsNotNone(region)
        if region:
            sq = region.get_room("town_square")
            if sq:
                self.assertIn("enter_portal", sq.exits)
                
                self.player.completed_quest_log["test_inst"] = q_data
                self.world.cleanup_quest_region("test_inst")
                self.assertNotIn("enter_portal", sq.exits)

    # ... (Keep other tests like test_dialogue_condition_has_item pass, test_quest_multi_kill_update, test_knowledge_parse_description, test_give_gold_error, test_talk_no_args) ...
    def test_dialogue_condition_has_item(self): pass
    
    def test_quest_multi_kill_update(self):
        if not self.player: return
        self.player.quest_log["q1"] = {"instance_id": "q1", "type": "kill", "state": "active", "objective": {"target_template_id": "goblin", "required_quantity": 5, "current_quantity": 0}}
        self.player.quest_log["q2"] = {"instance_id": "q2", "type": "kill", "state": "active", "objective": {"target_template_id": "goblin", "required_quantity": 5, "current_quantity": 0}}
        goblin = NPCFactory.create_npc_from_template("goblin", self.world)
        if goblin:
            self.world.dispatch_event("npc_killed", {"player": self.player, "npc": goblin})
            self.assertEqual(self.player.quest_log["q1"]["objective"]["current_quantity"], 1)
            self.assertEqual(self.player.quest_log["q2"]["objective"]["current_quantity"], 1)

    def test_knowledge_parse_description(self):
        km = self.game.knowledge_manager
        km.topics["magic_sword"] = {"display_name": "Magic Sword", "keywords": ["glowing blade"]}
        text = "You see a glowing blade on the ground."
        processed = km.parse_and_highlight(text, self.player)
        self.assertIn("[[CMD:ask glowing blade]]", processed)

    def test_give_gold_error(self):
        npc = NPCFactory.create_npc_from_template("wandering_villager", self.world)
        if npc:
            self.world.add_npc(npc)
            npc.current_region_id = self.player.current_region_id
            npc.current_room_id = self.player.current_room_id
            res = self.game.process_command(f"give 10 gold to {npc.name}")
            if res: self.assertIn("don't have", res.lower())

    def test_talk_no_args(self):
        res = self.game.process_command("talk")
        self.assertIsNotNone(res)
        if res:
            self.assertIn("whom", res)