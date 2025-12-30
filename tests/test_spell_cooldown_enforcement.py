# tests/test_spell_cooldown_enforcement.py
import time
from tests.fixtures import GameTestBase
from engine.magic.spell import Spell
from engine.magic.spell_registry import register_spell

class TestSpellCooldownEnforcement(GameTestBase):

    def setUp(self):
        super().setUp()
        self.spell = Spell(
            spell_id="cd_test", name="Slow Spell", description="x",
            mana_cost=0, cooldown=10.0, effect_type="damage", effect_value=1, level_required=1
        )
        register_spell(self.spell)
        self.player.learn_spell("cd_test")

    def test_cooldown_lifecycle(self):
        """Verify cast -> cooldown -> wait -> cast."""
        now = time.time()
        
        # 1. First Cast (Success)
        can_cast, _ = self.player.can_cast_spell(self.spell, now)
        self.assertTrue(can_cast)
        
        self.player.cast_spell(self.spell, self.player, now)
        
        # 2. Immediate Recast (Fail)
        can_cast_immediate, msg = self.player.can_cast_spell(self.spell, now + 1.0)
        self.assertFalse(can_cast_immediate)
        self.assertIn("cooldown", msg)
        
        # 3. Wait (Success)
        future = now + 11.0
        can_cast_later, _ = self.player.can_cast_spell(self.spell, future)
        self.assertTrue(can_cast_later, "Cooldown should expire.")