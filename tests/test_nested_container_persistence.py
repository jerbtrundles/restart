# tests/test_nested_container_persistence.py
import os
from typing import cast
from tests.fixtures import GameTestBase
from engine.items.item_factory import ItemFactory
from engine.items.container import Container

class TestNestedContainerPersistence(GameTestBase):
    
    TEST_SAVE = "test_nesting.json"

    def tearDown(self):
        path = os.path.join("data", "saves", self.TEST_SAVE)
        if os.path.exists(path):
            try: os.remove(path)
            except: pass
        super().tearDown()

    def test_nested_structure(self):
        """Verify Item C inside Bag B inside Chest A persists."""
        # 1. Setup
        chest = ItemFactory.create_item_from_template("item_empty_crate", self.world)
        bag = ItemFactory.create_item_from_template("item_empty_crate", self.world) # Using crate template as generic container
        gem = ItemFactory.create_item_from_template("item_ruby", self.world)
        
        if not (chest and bag and gem): return
        
        # Cast
        chest = cast(Container, chest); chest.name = "Big Chest"; chest.properties["is_open"] = True
        bag = cast(Container, bag); bag.name = "Small Bag"; bag.properties["is_open"] = True
        
        # 2. Nest: Gem -> Bag -> Chest -> Inventory
        bag.add_item(gem)
        chest.add_item(bag)
        self.player.inventory.add_item(chest)
        
        # 3. Save
        self.world.save_game(self.TEST_SAVE)
        
        # 4. Wipe
        self.player.inventory.slots = []
        
        # 5. Load
        self.world.load_save_game(self.TEST_SAVE)
        loaded = self.world.player
        
        # 6. Verify Hierarchy
        if loaded:
            # Find Chest
            loaded_chest = loaded.inventory.find_item_by_name("Big Chest")
            self.assertIsInstance(loaded_chest, Container)
            loaded_chest = cast(Container, loaded_chest)
            
            # Find Bag inside Chest
            loaded_bag = loaded_chest.find_item_by_name("Small Bag")
            self.assertIsInstance(loaded_bag, Container)
            loaded_bag = cast(Container, loaded_bag)
            
            # Find Gem inside Bag
            loaded_gem = loaded_bag.find_item_by_name("ruby")
            self.assertIsNotNone(loaded_gem)
            if loaded_gem:
                self.assertEqual(loaded_gem.name, "ruby")