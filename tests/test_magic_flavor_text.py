# tests/test_magic_flavor_text.py
from tests.fixtures import GameTestBase
from engine.magic.spell import Spell
from engine.magic.effects import apply_spell_effect

class TestMagicFlavorText(GameTestBase):

    def test_weakness_flavor_trigger(self):
        """Verify that negative resistance triggers 'weakness' flavor text."""
        if self.player:
            self.player.stats["resistances"] = {"fire": -50}
            self.player.stats["magic_resist"] = 0
            self.player.stats["intelligence"] = 10 
            
            fire_spell = Spell(
                spell_id="test_fire", name="Fire", description="test",
                effect_type="damage", effect_value=10, damage_type="fire"
            )
            
            # Act
            val, msg = apply_spell_effect(self.player, self.player, fire_spell, self.player)
            
            # from engine.config: FIRE -> weakness -> "The flames roar to life..."
            self.assertIn("roar to life", msg.lower())

    def test_strong_resistance_flavor_trigger(self):
        """Verify that high resistance triggers 'strong resistance' flavor text."""
        if self.player:
            self.player.stats["resistances"] = {"cold": 75} 
            self.player.stats["magic_resist"] = 0
            
            ice_spell = Spell(
                spell_id="test_ice", name="Ice", description="test",
                effect_type="damage", effect_value=10, damage_type="cold"
            )
            
            # Act
            val, msg = apply_spell_effect(self.player, self.player, ice_spell, self.player)
            
            # from engine.config: COLD -> strong_resistance -> "The icy blast dissipates harmlessly..."
            self.assertIn("dissipates harmlessly", msg.lower())