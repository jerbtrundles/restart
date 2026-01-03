# engine/player/core.py
import time
import random
from typing import List, Dict, Optional, Any, Tuple, Set, TYPE_CHECKING, cast

from engine.config import (
    DEFAULT_INVENTORY_MAX_SLOTS, DEFAULT_INVENTORY_MAX_WEIGHT, EQUIPMENT_SLOTS, EQUIPMENT_VALID_SLOTS_BY_TYPE, 
    PLAYER_BASE_ATTACK_COOLDOWN,
    PLAYER_BASE_ATTACK_POWER, PLAYER_BASE_DEFENSE, PLAYER_BASE_HEALTH, PLAYER_BASE_HEALTH_REGEN_RATE, 
    PLAYER_BASE_MANA_REGEN_RATE, PLAYER_BASE_XP_TO_LEVEL, PLAYER_CON_HEALTH_MULTIPLIER, PLAYER_DEFAULT_KNOWN_SPELLS, 
    PLAYER_DEFAULT_MAX_MANA, PLAYER_DEFAULT_MAX_TOTAL_SUMMONS, PLAYER_DEFAULT_NAME, PLAYER_DEFAULT_RESPAWN_REGION, 
    PLAYER_DEFAULT_RESPAWN_ROOM, PLAYER_DEFAULT_STATS, PLAYER_MANA_REGEN_WISDOM_DIVISOR,
    PLAYER_MAX_COMBAT_MESSAGES, PLAYER_REGEN_TICK_INTERVAL, PLAYER_HEALTH_REGEN_STRENGTH_DIVISOR
)
from engine.game_object import GameObject
from engine.items.inventory import Inventory
from engine.items.item import Item
from engine.items.item_factory import ItemFactory
from engine.items.set_manager import SetManager
from engine.core.conversation_history import ConversationHistory

# Import Mixins
from engine.player.display import PlayerDisplayMixin
from engine.player.persistence import PlayerPersistenceMixin
from engine.player.combat import PlayerCombatMixin
from engine.player.magic import PlayerMagicMixin
from engine.player.equipment import PlayerEquipmentMixin
from engine.player.progression import PlayerProgressionMixin

if TYPE_CHECKING:
    from engine.world.world import World

class Player(
    PlayerCombatMixin,
    PlayerMagicMixin,
    PlayerEquipmentMixin,
    PlayerProgressionMixin,
    PlayerDisplayMixin, 
    PlayerPersistenceMixin, 
    GameObject
):
    def __init__(self, name: str, obj_id: str = "player"):
        super().__init__(obj_id=obj_id, name=name, description="The main character.")
        self.inventory = Inventory(max_slots=DEFAULT_INVENTORY_MAX_SLOTS, max_weight=DEFAULT_INVENTORY_MAX_WEIGHT)
        self.max_mana = PLAYER_DEFAULT_MAX_MANA
        self.mana = self.max_mana
        self.mana_regen_rate = PLAYER_BASE_MANA_REGEN_RATE
        self.last_mana_regen_time = 0.0
        self.stats = PLAYER_DEFAULT_STATS.copy()
        self.max_health = PLAYER_BASE_HEALTH + int(self.stats.get('constitution', 10)) * PLAYER_CON_HEALTH_MULTIPLIER
        self.health = self.max_health
        self.level = 1
        self.player_class = "Adventurer"
        self.experience = 0
        self.experience_to_level = PLAYER_BASE_XP_TO_LEVEL
        
        self.skills: Dict[str, Dict[str, int]] = {}
        
        self.quest_log: Dict[str, Any] = {}
        self.completed_quest_log: Dict[str, Any] = {}
        self.archived_quest_log: Dict[str, Any] = {}
        
        # Campaign Tracking
        self.active_campaigns: Dict[str, Any] = {}
        self.completed_campaigns: Dict[str, Any] = {}
        
        self.equipment: Dict[str, Optional[Item]] = {slot: None for slot in EQUIPMENT_SLOTS}
        self.valid_slots_for_type = EQUIPMENT_VALID_SLOTS_BY_TYPE.copy()
        self.attack_power = PLAYER_BASE_ATTACK_POWER
        self.defense = PLAYER_BASE_DEFENSE
        self.is_alive = True
        self.faction = "player"
        self.in_combat = False
        self.combat_target: Optional[Any] = None
        self.attack_cooldown = PLAYER_BASE_ATTACK_COOLDOWN
        self.last_attack_time = 0.0 # Float
        self.combat_targets: Set[Any] = set()
        self.combat_messages: List[str] = []
        self.max_combat_messages = PLAYER_MAX_COMBAT_MESSAGES
        self.respawn_region_id: Optional[str] = PLAYER_DEFAULT_RESPAWN_REGION
        self.respawn_room_id: Optional[str] = PLAYER_DEFAULT_RESPAWN_ROOM
        self.known_spells: Set[str] = set(PLAYER_DEFAULT_KNOWN_SPELLS)
        self.spell_cooldowns: Dict[str, float] = {}
        self.world: Optional['World'] = None
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.gold: int = 0
        self.active_summons: Dict[str, List[str]] = {}
        self.max_total_summons: int = PLAYER_DEFAULT_MAX_TOTAL_SUMMONS
        
        self.trading_with: Optional[str] = None
        self.active_minigame: Optional[Dict[str, Any]] = None
        self.follow_target: Optional[str] = None 
        
        self.conversation = ConversationHistory()
        self.last_talked_to: Optional[str] = None 

        self.collections_progress: Dict[str, List[str]] = {} 
        self.collections_completed: Dict[str, bool] = {} 

        self.reputation: Dict[str, int] = {} 
        self.set_manager = SetManager()

    def get_effective_stat(self, stat_name: str) -> int:
        """Calculates stat including base, buffs, equipment, AND set bonuses."""
        val = super().get_effective_stat(stat_name)
        
        equipped_ids = [item.obj_id for item in self.equipment.values() if item]
        bonuses = self.set_manager.get_active_bonuses(equipped_ids)
        
        for bonus in bonuses:
            if bonus.get("type") == "stat_mod":
                mods = bonus.get("modifiers", {})
                val += mods.get(stat_name, 0)

        return val

    def apply_class_template(self, class_data: Dict[str, Any]):
        if not self.world: return
        if "name" in class_data: self.player_class = class_data["name"]
        if "stats" in class_data:
            self.stats.update(class_data["stats"])
            self.max_health = PLAYER_BASE_HEALTH + int(self.stats.get('constitution', 10)) * PLAYER_CON_HEALTH_MULTIPLIER
            self.health = self.max_health
            final_int = self.stats.get("intelligence", 10)
            self.max_mana = PLAYER_DEFAULT_MAX_MANA + (final_int - 10) * 5 
            self.mana = self.max_mana
        
        from engine.items.inventory import InventorySlot
        self.inventory.slots = [InventorySlot() for _ in range(self.inventory.max_slots)]
        
        for item_ref in class_data.get("inventory", []):
            item_id = item_ref.get("item_id")
            qty = item_ref.get("quantity", 1)
            if item_id:
                item = ItemFactory.create_item_from_template(item_id, self.world)
                if item: self.inventory.add_item(item, qty)

        equip_defs = class_data.get("equipment", {})
        for slot, item_id in equip_defs.items():
            item = ItemFactory.create_item_from_template(item_id, self.world)
            if item: self.equipment[slot] = item

        self.known_spells = set(class_data.get("spells", []))
        if not self.known_spells: self.known_spells = set(PLAYER_DEFAULT_KNOWN_SPELLS)

    def update(self, current_time: float, time_delta_effects: float) -> List[str]:
        messages = []
        if not self.is_alive: return []
        
        # --- Environment Logic ---
        if self.world and self.current_region_id and self.current_room_id:
            room = self.world.get_current_room()
            if room:
                hazard_msg = room.apply_hazards(self, current_time)
                if hazard_msg: messages.append(hazard_msg)

        if self.current_region_id:
             is_in_safe_zone = self.world and self.world.is_location_safe(self.current_region_id, self.current_room_id)
             if is_in_safe_zone and not self.in_combat:
                 if current_time - self.last_mana_regen_time >= PLAYER_REGEN_TICK_INTERVAL:                
                     effective_wisdom = self.get_effective_stat('wisdom')
                     effective_strength = self.get_effective_stat('strength')
                     base_mana_regen = self.mana_regen_rate * (1 + effective_wisdom / PLAYER_MANA_REGEN_WISDOM_DIVISOR)
                     base_health_regen = PLAYER_BASE_HEALTH_REGEN_RATE * (1 + effective_strength / PLAYER_HEALTH_REGEN_STRENGTH_DIVISOR)
                     mana_regen_amount = int(PLAYER_REGEN_TICK_INTERVAL * base_mana_regen)
                     health_regen_amount = int(PLAYER_REGEN_TICK_INTERVAL * base_health_regen)
                     self.mana = min(self.max_mana, self.mana + mana_regen_amount)
                     self.health = min(self.max_health, self.health + health_regen_amount)
                     self.last_mana_regen_time = current_time 
             
        effect_msgs = self.process_active_effects(current_time, time_delta_effects)
        messages.extend(effect_msgs)
        
        return messages

    def update_quest(self, quest_id: str, progress: Any) -> None: self.quest_log[quest_id] = progress
    def get_quest_progress(self, quest_id: str) -> Optional[Any]: return self.quest_log.get(quest_id)
    
    def heal(self, amount: int) -> int:
        if not self.is_alive: return 0
        old = self.health; self.health = min(self.health + amount, self.max_health)
        return int(self.health - old)
        
    def restore_mana(self, amount: int) -> int:
        if not self.is_alive: return 0
        old = self.mana; self.mana = min(self.mana + amount, self.max_mana)
        return int(self.mana - old)
        
    def take_damage(self, amount: int, damage_type: str = "physical") -> int:
        d = super().take_damage(amount, damage_type)
        if self.health <= 0: self.die()
        return d
    
    def die(self, world: Optional['World'] = None) -> None:
        if not self.is_alive: return
        self.health = 0; self.is_alive = False; self.in_combat = False
        
        target_world = world or self.world
        if target_world and hasattr(target_world, 'npcs'):
            for npc in target_world.npcs.values():
                if npc.in_combat and self in npc.combat_targets: npc.exit_combat(self)
        self.combat_targets.clear(); self.active_effects.clear()
        
        local_world = self.world
        if local_world:
            all_summon_ids = [inst_id for ids in self.active_summons.values() for inst_id in ids]
            for instance_id in all_summon_ids:
                summon = local_world.get_npc(instance_id)
                if summon and hasattr(summon, 'despawn'): summon.despawn(local_world, silent=True)
        self.active_summons = {}

    def respawn(self) -> None:
        self.health = self.max_health; self.mana = self.max_mana
        self.is_alive = True; self.in_combat = False; self.combat_targets.clear()
        self.spell_cooldowns.clear(); self.active_summons = {}; self.active_effects = []
        self.current_region_id = self.respawn_region_id
        self.current_room_id = self.respawn_room_id
