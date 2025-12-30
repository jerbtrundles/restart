# tests/test_minion_owner_death.py
from tests.fixtures import GameTestBase
from engine.npcs.npc_factory import NPCFactory

class TestMinionOwnerDeath(GameTestBase):

    def test_minion_despawns_on_player_death(self):
        """Verify minions are removed when the player dies."""
        # 1. Summon Minion
        minion = NPCFactory.create_npc_from_template("skeleton_minion", self.world)
        if minion:
            minion.properties["owner_id"] = self.player.obj_id
            self.world.add_npc(minion)
            
            # Register in player's active summons
            self.player.active_summons["spell_raise_dead"] = [minion.obj_id]
            
            # 2. Kill Player
            # Player.die() calls internal cleanup
            self.player.die(self.world)
            
            # 3. Assert Minion Despawned
            # Note: die() usually marks minion !is_alive. Actual removal from world happens in World.update()
            self.assertFalse(minion.is_alive)
            self.assertNotIn("spell_raise_dead", self.player.active_summons)