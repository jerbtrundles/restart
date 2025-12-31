import time
from unittest.mock import patch
from tests.fixtures import GameTestBase
from engine.items.item_factory import ItemFactory
from engine.items.weapon import Weapon
from engine.items.armor import Armor
from engine.magic.spell import Spell
from engine.magic.spell_registry import register_spell
from engine.npcs.npc_factory import NPCFactory
from engine.core.combat_system import CombatSystem

class TestBatchMechanicsDeep(GameTestBase):
    """
    Stress tests for advanced mechanics: Curses, Requirements, Status Flags, and Complex Spells.
    """

    def setUp(self):
        super().setUp()
        # --- INJECT NEW CONTENT TEMPLATES ---
        
        # 1. Cursed Ring
        self.world.item_templates["cursed_ring"] = {
            "type": "Armor", "name": "Ring of Burden", "value": 500,
            "properties": {
                "equip_slot": ["hands"], "defense": 5,
                "cursed": True,
                "equip_effect": {"type": "stat_mod", "name": "Burden", "modifiers": {"agility": -5}}
            }
        }

        # 2. Heavy Plate (Requirement)
        self.world.item_templates["heavy_plate"] = {
            "type": "Armor", "name": "Titan Plate", "value": 1000,
            "properties": {
                "equip_slot": ["body"], "defense": 10,
                "requirements": {"strength": 100} # High req
            }
        }

        # 3. Glass Dagger (Fragile)
        self.world.item_templates["glass_dagger"] = {
            "type": "Weapon", "name": "Glass Dagger", "value": 200,
            "properties": {
                "equip_slot": ["main_hand"], "damage": 50, # High damage
                "durability": 2, "max_durability": 2
            }
        }

        # 4. Spells
        self.silence_spell = Spell("silence_ray", "Silence Ray", "Shhh.", 
                                  effect_type="apply_effect", target_type="enemy",
                                  effect_data={"type": "debuff", "name": "Silenced", "tags": ["curse"], "base_duration": 10.0})
        
        self.cleanse_spell = Spell("cleanse", "Cleanse", "Cures poison/curse.", 
                                  effect_type="cleanse", target_type="friendly",
                                  effect_data={"tags": ["curse", "poison"]})
        
        self.remove_curse_spell = Spell("remove_curse", "Remove Curse", "Unbinds items.", 
                                       effect_type="remove_curse", target_type="friendly")

        self.life_tap = Spell("life_tap", "Life Tap", "Drain life.", 
                             effect_type="life_tap", target_type="enemy", 
                             effect_value=20, damage_type="magical")

        register_spell(self.silence_spell)
        register_spell(self.cleanse_spell)
        register_spell(self.remove_curse_spell)
        register_spell(self.life_tap)
        
        self.player.known_spells.update(["cleanse", "remove_curse", "life_tap"])

    def test_stat_requirements_block_equip(self):
        """Verify items cannot be equipped if stats are too low."""
        plate = ItemFactory.create_item_from_template("heavy_plate", self.world)
        self.assertIsNotNone(plate, "Failed to create heavy_plate")
        
        if plate:
            self.player.inventory.add_item(plate)
            self.player.stats["strength"] = 10
            
            success, msg = self.player.equip_item(plate)
            self.assertFalse(success)
            self.assertIn("need 100 Strength", msg)
            
            # Buff stats
            self.player.stats["strength"] = 100
            success, msg = self.player.equip_item(plate)
            self.assertTrue(success)

    def test_cursed_item_lock(self):
        """Verify cursed items cannot be unequipped until cleansed."""
        ring = ItemFactory.create_item_from_template("cursed_ring", self.world)
        self.assertIsNotNone(ring, "Failed to create cursed_ring")
        
        if ring:
            self.player.inventory.add_item(ring)
            self.player.equip_item(ring)
            
            # Try unequip
            success, msg = self.player.unequip_item("hands")
            self.assertFalse(success)
            self.assertIn("binds to your flesh", msg)
            
            # Cast Remove Curse
            res = self.player.cast_spell(self.remove_curse_spell, self.player, time.time(), self.world)
            self.assertTrue(res["success"])
            self.assertIn("cleansing", res["message"])
            self.assertFalse(ring.get_property("cursed"))
            
            # Retry unequip
            success, msg = self.player.unequip_item("hands")
            self.assertTrue(success)

    def test_silence_prevents_casting(self):
        """Verify the 'Silenced' status effect blocks magic."""
        # Apply Silence
        self.player.apply_effect({"name": "Silenced", "type": "debuff"}, time.time())
        
        res = self.player.cast_spell(self.cleanse_spell, self.player, time.time(), self.world)
        self.assertFalse(res["success"])
        self.assertIn("silenced", res["message"].lower())

    def test_blind_hit_chance_cap(self):
        """Verify Blind status caps hit chance significantly."""
        self.player.apply_effect({"name": "Blind", "type": "debuff"}, time.time())
        
        # Setup dummy target with low agility (should normally be easy to hit)
        target = NPCFactory.create_npc_from_template("goblin", self.world)
        self.assertIsNotNone(target, "Failed to create goblin")
        
        if target:
            target.stats["agility"] = 1 
            self.player.stats["agility"] = 100 
            
            # Normal calc would be > 95%. Blind cap is 20%.
            chance = CombatSystem.calculate_hit_chance(self.player, target)
            self.assertEqual(chance, 0.20)

    def test_life_tap_mechanic(self):
        """Verify Life Tap damages enemy and heals caster."""
        target = NPCFactory.create_npc_from_template("goblin", self.world)
        self.assertIsNotNone(target, "Failed to create goblin")
        
        if target:
            target.health = 100
            target.stats["magic_resist"] = 0
            
            self.player.max_health = 100
            self.player.health = 50
            
            # Neutralize variance for math check
            with patch('random.uniform', return_value=0.0):
                res = self.player.cast_spell(self.life_tap, target, time.time(), self.world)
            
            # Damage should be ~20 (base) + scaling. Assume stats make it 20.
            # Actually base is 20. Int 10 -> +0. Power 5 -> +5. Total 25.
            # Damage 25. Heal 12.
            
            self.assertTrue(res["success"])
            self.assertLess(target.health, 100)
            self.assertGreater(self.player.health, 50)
            self.assertIn("heals", res["message"])

    def test_cleanse_specific_tags(self):
        """Verify Cleanse removes tagged effects but leaves others."""
        # Add Poison (Tagged)
        self.player.apply_effect({"name": "Venom", "type": "dot", "tags": ["poison"]}, time.time())
        # Add Buff (Untagged/Different Tag)
        self.player.apply_effect({"name": "Might", "type": "buff", "tags": ["magic"]}, time.time())
        
        self.assertTrue(self.player.has_effect("Venom"))
        self.assertTrue(self.player.has_effect("Might"))
        
        # Cast Cleanse (Targets poison/curse)
        self.player.cast_spell(self.cleanse_spell, self.player, time.time(), self.world)
        
        self.assertFalse(self.player.has_effect("Venom"))
        self.assertTrue(self.player.has_effect("Might"))

    def test_glass_dagger_breaking(self):
        """Verify item breaks after exactly 2 hits."""
        dagger = ItemFactory.create_item_from_template("glass_dagger", self.world)
        self.assertIsNotNone(dagger, "Failed to create glass dagger")
        
        target = NPCFactory.create_npc_from_template("goblin", self.world)
        self.assertIsNotNone(target, "Failed to create goblin")
        
        if dagger and target:
            self.player.inventory.add_item(dagger)
            self.player.equip_item(dagger, "main_hand")
            
            target.health = 1000
            
            # Force hits
            with patch('random.random', return_value=0.0):
                # Hit 1 (Durability 2 -> 1)
                self.player.attack(target, self.world)
                self.assertEqual(dagger.get_property("durability"), 1)
                
                # Hit 2 (Durability 1 -> 0, Break)
                res = self.player.attack(target, self.world)
                self.assertEqual(dagger.get_property("durability"), 0)
                self.assertIn("breaks", res["message"])