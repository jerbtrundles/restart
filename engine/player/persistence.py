# engine/player/persistence.py
from typing import Dict, Any, TYPE_CHECKING, cast
from engine.utils.utils import _serialize_item_reference

if TYPE_CHECKING:
    from engine.player.core import Player
    from engine.world.world import World

class PlayerPersistenceMixin:
    """
    Mixin class handling serialization for the Player.
    """
    def to_dict(self, world: 'World') -> Dict[str, Any]:
        # Cast self to Player to satisfy static analysis
        p = cast('Player', self)
        
        # Use super().to_dict() from GameObject (which Player inherits from)
        data = super().to_dict() # type: ignore
        data.update({
            "gold": p.gold, "health": p.health, "max_health": p.max_health,
            "mana": p.mana, "max_mana": p.max_mana, "stats": p.stats,
            "player_class": p.player_class,
            "level": p.level, "experience": p.experience, "experience_to_level": p.experience_to_level,
            "skills": p.skills, "effects": p.active_effects, 
            "quest_log": p.quest_log,
            "completed_quest_log": p.completed_quest_log,
            "archived_quest_log": p.archived_quest_log,
            "is_alive": p.is_alive,
            "current_location": {"region_id": p.current_region_id, "room_id": p.current_room_id},
            "respawn_region_id": p.respawn_region_id, "respawn_room_id": p.respawn_room_id,
            "known_spells": list(p.known_spells), "spell_cooldowns": p.spell_cooldowns,
            "inventory": p.inventory.to_dict(world),
            "equipment": {slot: _serialize_item_reference(item, 1, world) for slot, item in p.equipment.items() if item},
            "conversation_history": p.conversation.to_dict(),
            "last_talked_to": p.last_talked_to,
            "collections_progress": p.collections_progress,
            "collections_completed": p.collections_completed,
            "follow_target": p.follow_target
        })
        return data