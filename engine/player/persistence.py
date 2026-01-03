# engine/player/persistence.py

# engine/player/persistence.py
from typing import Dict, Any, TYPE_CHECKING, cast, Optional
from engine.utils.utils import _serialize_item_reference
from engine.items.inventory import Inventory
from engine.items.item_factory import ItemFactory
from engine.core.conversation_history import ConversationHistory
from engine.config import (
    PLAYER_DEFAULT_NAME, PLAYER_BASE_XP_TO_LEVEL, PLAYER_DEFAULT_STATS,
    PLAYER_DEFAULT_RESPAWN_REGION, PLAYER_DEFAULT_RESPAWN_ROOM,
    PLAYER_DEFAULT_KNOWN_SPELLS, EQUIPMENT_SLOTS, PLAYER_DEFAULT_MAX_TOTAL_SUMMONS
)

if TYPE_CHECKING:
    from engine.player.core import Player
    from engine.world.world import World

class PlayerPersistenceMixin:
    """
    Mixin class handling serialization for the Player.
    """
    def to_dict(self, world: 'World') -> Dict[str, Any]:
        p = cast('Player', self)
        
        # Serialize superclass (GameObject) data
        data = super().to_dict() # type: ignore
        
        # Add Player-specific data
        data.update({
            "gold": p.gold,
            "health": p.health,
            "max_health": p.max_health,
            "mana": p.mana,
            "max_mana": p.max_mana,
            "stats": p.stats,
            "player_class": p.player_class,
            "level": p.level,
            "experience": p.experience,
            "experience_to_level": p.experience_to_level,
            "skills": p.skills,
            "effects": p.active_effects, 
            "quest_log": p.quest_log,
            "completed_quest_log": p.completed_quest_log,
            "archived_quest_log": p.archived_quest_log,
            "is_alive": p.is_alive,
            "current_location": {
                "region_id": p.current_region_id,
                "room_id": p.current_room_id
            },
            "respawn_region_id": p.respawn_region_id,
            "respawn_room_id": p.respawn_room_id,
            "known_spells": list(p.known_spells),
            "spell_cooldowns": p.spell_cooldowns,
            "inventory": p.inventory.to_dict(world),
            "equipment": {
                slot: _serialize_item_reference(item, 1, world) 
                for slot, item in p.equipment.items() if item
            },
            "conversation_history": p.conversation.to_dict(),
            "last_talked_to": p.last_talked_to,
            "collections_progress": p.collections_progress,
            "collections_completed": p.collections_completed,
            "follow_target": p.follow_target,
            "reputation": p.reputation,
            "active_campaigns": p.active_campaigns,
            "completed_campaigns": p.completed_campaigns
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], world: 'World') -> Optional['Player']:
        """
        Reconstructs a Player object from a dictionary.
        """
        # Import locally to avoid circular dependency
        from engine.player.core import Player

        # Create instance using base init
        player_obj = cls(name=data.get("name", PLAYER_DEFAULT_NAME)) # type: ignore
        
        # Cast to Player to satisfy Pylance about attribute access
        player = cast(Player, player_obj)
        
        # Core GameObject properties
        player.obj_id = data.get("id", "player")
        player.description = data.get("description", "The main character.")
        player.properties = data.get("properties", {})
        player.is_alive = data.get("is_alive", True)

        # Player Stats & Progression
        player.player_class = data.get("player_class", "Adventurer")
        player.gold = data.get("gold", 0)
        player.level = data.get("level", 1)
        player.experience = data.get("experience", 0)
        player.experience_to_level = data.get("experience_to_level", PLAYER_BASE_XP_TO_LEVEL)
        
        player.stats = PLAYER_DEFAULT_STATS.copy()
        player.stats.update(data.get("stats", {}))
        
        # Skills (Handle legacy integer format if present)
        raw_skills = data.get("skills", {})
        player.skills = {}
        for k, v in raw_skills.items():
            if isinstance(v, int):
                player.skills[k] = {"level": v, "xp": 0}
            else:
                player.skills[k] = v

        # Quests & Campaign
        player.quest_log = data.get("quest_log", {})
        player.completed_quest_log = data.get("completed_quest_log", {})
        player.archived_quest_log = data.get("archived_quest_log", {})
        player.active_campaigns = data.get("active_campaigns", {})
        player.completed_campaigns = data.get("completed_campaigns", {})

        # Status Effects
        player.active_effects = data.get("effects", [])
        # Re-apply stat modifiers from active effects
        player.stat_modifiers = {}
        for effect in player.active_effects:
            if effect.get("type") == "stat_mod":
                for stat, value in effect.get("modifiers", {}).items():
                    player.stat_modifiers[stat] = player.stat_modifiers.get(stat, 0) + value

        # Magic
        player.known_spells = set(data.get("known_spells", PLAYER_DEFAULT_KNOWN_SPELLS))
        player.spell_cooldowns = data.get("spell_cooldowns", {})
        player.max_total_summons = PLAYER_DEFAULT_MAX_TOTAL_SUMMONS

        # Vitals
        player.max_health = data.get("max_health", player.max_health)
        player.health = data.get("health", player.max_health)
        player.max_mana = data.get("max_mana", player.max_mana)
        player.mana = data.get("mana", player.max_mana)
        
        # Location
        loc = data.get("current_location", {})
        player.current_region_id = loc.get("region_id")
        player.current_room_id = loc.get("room_id")
        player.respawn_region_id = data.get("respawn_region_id", PLAYER_DEFAULT_RESPAWN_REGION)
        player.respawn_room_id = data.get("respawn_room_id", PLAYER_DEFAULT_RESPAWN_ROOM)
        
        # Inventory
        inventory_data = data.get("inventory", {})
        player.inventory = Inventory.from_dict(inventory_data, world)
        
        # Equipment
        equipment_data = data.get("equipment", {})
        player.equipment = {slot: None for slot in EQUIPMENT_SLOTS}
        
        for slot, item_ref in equipment_data.items():
            if slot in player.equipment and item_ref and "item_id" in item_ref:
                item_id = item_ref["item_id"]
                overrides = item_ref.get("properties_override", {})
                item = ItemFactory.create_item_from_template(item_id, world, **overrides)
                if item:
                    player.equipment[slot] = item
                else:
                    print(f"Warning: Failed to load equipped item '{item_id}' for slot '{slot}'.")

        # Interaction State
        player.last_talked_to = data.get("last_talked_to")
        if "conversation_history" in data:
            player.conversation = ConversationHistory.from_dict(data["conversation_history"])
        
        player.collections_progress = data.get("collections_progress", {})
        player.collections_completed = data.get("collections_completed", {})
        player.follow_target = data.get("follow_target")
        player.reputation = data.get("reputation", {})

        player.world = world
        return player
