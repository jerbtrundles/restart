# npcs/npc.py
# --- THIS IS THE REFACTORED CORE NPC MODULE ---
# It now imports combat and behavior logic from separate files to keep this class focused.

from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple
import time
from game_object import GameObject
from items.inventory import Inventory
from items.item import Item
from items.item_factory import ItemFactory
from utils.utils import format_loot_drop_message, format_name_for_display, calculate_xp_gain
from core.config import (
    NPC_BASE_HEALTH, NPC_BASE_XP_TO_LEVEL,
    NPC_CON_HEALTH_MULTIPLIER, NPC_DEFAULT_BEHAVIOR, NPC_DEFAULT_STATS,
    NPC_DEFAULT_WANDER_CHANCE, NPC_DEFAULT_MOVE_COOLDOWN, NPC_DEFAULT_RESPAWN_COOLDOWN,
    NPC_HEALTH_DESC_THRESHOLDS, NPC_LEVEL_HEALTH_BASE_INCREASE, NPC_LEVEL_CON_HEALTH_MULTIPLIER,
    NPC_LEVEL_UP_HEALTH_HEAL_PERCENT, NPC_LEVEL_UP_STAT_INCREASE, NPC_MANA_REGEN_WISDOM_DIVISOR,
    NPC_BASE_MANA_REGEN_RATE, NPC_MAX_COMBAT_MESSAGES, NPC_XP_TO_LEVEL_MULTIPLIER,
    PLAYER_REGEN_TICK_INTERVAL, WORLD_UPDATE_INTERVAL, NAMED_NPC_RESPAWN_COOLDOWN
)

# Import the new modules for delegation
from . import behaviors as npc_behaviors
from . import combat as npc_combat

if TYPE_CHECKING:
    from world.world import World
    from player import Player
    from core.game_manager import GameManager

class NPC(GameObject):
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown NPC",
                 description: str = "No description", health: int = 100,
                 friendly: bool = True, level: int = 1):
        # ... (the __init__ method remains largely the same as before) ...
        self.template_id: Optional[str] = None
        super().__init__(obj_id=obj_id, name=name, description=description)
        self.stats = NPC_DEFAULT_STATS.copy()
        self.level = level
        self.experience: int = 0
        self.experience_to_level: int = NPC_BASE_XP_TO_LEVEL
        self.is_trading: bool = False
        base_hp = NPC_BASE_HEALTH + int(self.stats.get('constitution', 8) * NPC_CON_HEALTH_MULTIPLIER)
        level_hp_bonus = (self.level - 1) * (NPC_LEVEL_HEALTH_BASE_INCREASE + int(self.stats.get('constitution', 8) * NPC_LEVEL_CON_HEALTH_MULTIPLIER))
        self.max_health = base_hp + level_hp_bonus
        self.health = min(health, self.max_health)
        self.max_mana: int = 10
        self.mana: int = 10
        self.last_regen_time: float = 0
        self.faction = "neutral"
        self.friendly = friendly
        self.inventory = Inventory(max_slots=10, max_weight=50.0)
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.home_region_id: Optional[str] = None
        self.home_room_id: Optional[str] = None
        self.behavior_type = NPC_DEFAULT_BEHAVIOR
        self.wander_chance = NPC_DEFAULT_WANDER_CHANCE
        self.move_cooldown = NPC_DEFAULT_MOVE_COOLDOWN
        self.aggression = 0.0
        self.attack_power = 5
        self.defense = 2
        self.flee_threshold = 0.2
        self.respawn_cooldown = NPC_DEFAULT_RESPAWN_COOLDOWN
        self.combat_cooldown = 3.0
        self.attack_cooldown = 3.0
        self.max_combat_messages = NPC_MAX_COMBAT_MESSAGES
        self.spell_cast_chance: float = 0.0
        self.patrol_points = []
        self.patrol_index = 0
        self.follow_target: Optional[str] = None
        self.schedule = {}
        self.last_moved: float = 0
        self.dialog = {}
        self.default_dialog = "The {name} doesn't respond."
        self.ai_state = {}
        self.is_alive = True
        self.spawn_time = 0
        self.loot_table = {}
        self.in_combat = False
        self.combat_target = None
        self.last_combat_action: float = 0
        self.last_attack_time: float = 0
        self.combat_targets = set()
        self.combat_messages = []
        self.usable_spells: List[str] = []
        self.spell_cooldowns: Dict[str, float] = {}
        self.world: Optional['World'] = None
        self.owner_id: Optional[str] = None
        self.creation_time: float = 0.0
        self.summon_duration: float = 0.0
        self.current_path: List[str] = []
        self.schedule_destination: Optional[Tuple[str, str, str]] = None
        self.retreat_destination: Optional[Tuple[str, str]] = None
        self.original_behavior: Optional[str] = None

    def get_description(self) -> str:
        # ... (this method is unchanged) ...
        health_percent = self.health / self.max_health * 100 if self.max_health > 0 else 0
        health_desc = ""
        if health_percent <= NPC_HEALTH_DESC_THRESHOLDS[0] * 100: health_desc = f"The {self.name} looks severely injured."
        elif health_percent <= NPC_HEALTH_DESC_THRESHOLDS[1] * 100: health_desc = f"The {self.name} appears to be wounded."
        elif health_percent <= NPC_HEALTH_DESC_THRESHOLDS[2] * 100: health_desc = f"The {self.name} has some minor injuries."
        else: health_desc = f"The {self.name} looks healthy."
        return f"{self.name}\n\n{self.description}\n\n{health_desc}"

    def talk(self, topic: Optional[str] = None) -> str:
        # ... (this method is unchanged) ...
        if self.in_combat: return "They are too busy fighting to talk!"
        if not topic: return self.dialog.get("greeting", self.default_dialog.format(name=self.name))
        return self.dialog.get(topic.lower(), self.default_dialog.format(name=self.name))

    def take_damage(self, amount: int, damage_type: str) -> int:
        # ... (this method is unchanged) ...
        if not self.is_alive: return 0
        reduction = self.defense if damage_type == "physical" else self.stats.get("magic_resist", 0)
        damage_taken = max(1, amount - reduction) if amount > 0 else 0
        self.health -= damage_taken
        if self.health <= 0: self.is_alive = False; self.health = 0
        return damage_taken

    def heal(self, amount: int) -> int:
        # ... (this method is unchanged) ...
        if not self.is_alive: return 0
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - old_health

    def die(self, world: 'World') -> List[Item]:
        # ... (this method is unchanged) ...
        if self.properties.get("is_summoned"):
            self.despawn(world, silent=True)
            return []

        is_respawnable = (
            self.faction in ["friendly", "neutral"] and
            self.home_room_id is not None and
            self.template_id and
            "wandering_villager" not in self.template_id
        )
        if is_respawnable:
            world.add_to_respawn_queue(self)

        self.is_alive = False
        dropped_items: List[Item] = []
        if self.loot_table and self.current_region_id and self.current_room_id:
            for item_id, loot_data in self.loot_table.items():
                if isinstance(loot_data, dict) and loot_data.get("chance", 0) > 0:
                     if loot_data["chance"] >= 1.0 or loot_data["chance"] > 0:
                         item = ItemFactory.create_item_from_template(item_id, world)
                         if item: world.add_item_to_room(self.current_region_id, self.current_room_id, item); dropped_items.append(item)
        return dropped_items
        
    def to_dict(self) -> Dict[str, Any]:
        # ... (this method is unchanged) ...
        return {
            "template_id": self.template_id, "obj_id": self.obj_id, "name": self.name,
            "current_region_id": self.current_region_id, "current_room_id": self.current_room_id,
            "health": self.health, "mana": self.mana, "level": self.level,
            "is_alive": self.is_alive, "stats": self.stats,
            "ai_state": self.ai_state, "spell_cooldowns": self.spell_cooldowns,
            "faction": self.faction, "inventory": self.inventory.to_dict(self.world) if self.world else {}
        }

    def despawn(self, world: 'World', silent: bool = False) -> Optional[str]:
        # ... (this method is unchanged) ...
        if not self.properties.get("is_summoned"): return None
        self.is_alive = False
        owner_id = self.owner_id or self.properties.get("owner_id")
        if owner_id and world and world.player and world.player.obj_id == owner_id:
            for spell_id, summon_ids in list(world.player.active_summons.items()):
                if self.obj_id in summon_ids:
                    summon_ids.remove(self.obj_id)
                    if not summon_ids: del world.player.active_summons[spell_id]
                    break
        return f"Your {self.name} crumbles to dust." if not silent else None

    def _handle_regen(self, current_time: float):
        # ... (this method is unchanged) ...
        if current_time - self.last_regen_time >= PLAYER_REGEN_TICK_INTERVAL:
            mana_regen = NPC_BASE_MANA_REGEN_RATE * (1 + self.stats.get('wisdom', 5) / NPC_MANA_REGEN_WISDOM_DIVISOR)
            self.mana = int(min(self.max_mana, self.mana + mana_regen))
            self.last_regen_time = current_time

    def gain_experience(self, amount: int) -> Tuple[bool, str]:
        # ... (this method is unchanged) ...
        if not self.is_alive or amount <= 0: return False, ""
        self.experience += amount
        leveled_up = False
        while self.experience >= self.experience_to_level: self.level_up(); leveled_up = True
        return leveled_up, f"{self.name} is now level {self.level}!" if leveled_up else ""

    def level_up(self) -> None:
        # ... (this method is unchanged) ...
        self.level += 1
        self.experience -= self.experience_to_level
        self.experience_to_level = int(self.experience_to_level * NPC_XP_TO_LEVEL_MULTIPLIER)
        for stat in self.stats: self.stats[stat] += NPC_LEVEL_UP_STAT_INCREASE
        old_max_health = self.max_health
        final_con = self.stats.get('constitution', 8)
        self.max_health += NPC_LEVEL_HEALTH_BASE_INCREASE + int(final_con * NPC_LEVEL_CON_HEALTH_MULTIPLIER)
        self.heal(int((self.max_health - old_max_health) * NPC_LEVEL_UP_HEALTH_HEAL_PERCENT))

    # --- DELEGATED METHODS ---
    def attack(self, target) -> Dict[str, Any]:
        return npc_combat.attack(self, target)

    def cast_spell(self, spell, target, current_time: float) -> Dict[str, Any]:
        return npc_combat.cast_spell(self, spell, target, current_time)

    def is_hostile_to(self, other) -> bool:
        return npc_combat.is_hostile_to(self, other)

    def enter_combat(self, target):
        npc_combat.enter_combat(self, target)

    def exit_combat(self, target=None):
        npc_combat.exit_combat(self, target)
        
    def _add_combat_message(self, message: str) -> None:
        self.combat_messages.append(message)
        if len(self.combat_messages) > self.max_combat_messages:
            self.combat_messages.pop(0)

    # --- MAIN UPDATE LOOP ---
    def update(self, world, current_time: float) -> Optional[str]:
        if not self.is_alive: return None
        
        player = getattr(world, 'player', None)
        if not player: return None
        
        all_messages_for_player = []

        self._handle_regen(current_time)
        effect_messages = self.process_active_effects(current_time, WORLD_UPDATE_INTERVAL)
        if effect_messages and player and player.current_room_id == self.current_room_id:
             all_messages_for_player.extend(effect_messages)

        if self.is_alive:
            ai_message = npc_behaviors.handle_ai(self, world, current_time, player)
            if ai_message: all_messages_for_player.append(ai_message)

        return "\n".join(msg for msg in all_messages_for_player if msg) or None