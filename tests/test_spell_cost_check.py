# tests/test_spell_cost_check.py
import time
from tests.fixtures import GameTestBase
from engine.magic.spell import Spell
from engine.magic.spell_registry import register_spell

class TestSpellCostCheck(GameTestBase):

    def setUp(self):
        super().setUp()
        self.spell = Spell(
            spell_id="cost_test", name="Costly", description="x",
            mana_cost=10, effect_type="damage", effect_value=1, level_required=1
        )
        register_spell(self.spell)
        self.player.learn_spell("cost_test")

    def test_insufficient_mana(self):
        """Verify casting fails if mana is just below cost."""
        self.player.mana = 9
        
        can_cast, msg = self.player.can_cast_spell(self.spell, time.time())
        self.assertFalse(can_cast)
        self.assertIn("Not enough mana", msg)

    def test_exact_mana(self):
        """Verify casting succeeds if mana matches cost exactly."""
        self.player.mana = 10
        
        can_cast, _ = self.player.can_cast_spell(self.spell, time.time())
        self.assertTrue(can_cast)
        
        # Execute cast to verify consumption
        self.player.cast_spell(self.spell, self.player, time.time())
        self.assertEqual(self.player.mana, 0)