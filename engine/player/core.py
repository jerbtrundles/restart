# engine/player/core.py
import time
import random
from typing import List, Dict, Optional, Any, Tuple, Set, TYPE_CHECKING, cast

from engine.config import (
    DEFAULT_INVENTORY_MAX_SLOTS, DEFAULT_INVENTORY_MAX_WEIGHT, EQUIPMENT_SLOTS, EQUIPMENT_VALID_SLOTS_BY_TYPE, 
    ITEM_DURABILITY_LOSS_ON_HIT, PLAYER_ATTACK_POWER_STR_DIVISOR, PLAYER_BASE_ATTACK_COOLDOWN,
    PLAYER_BASE_ATTACK_POWER, PLAYER_BASE_DEFENSE, PLAYER_BASE_HEALTH, PLAYER_BASE_HEALTH_REGEN_RATE, 
    PLAYER_BASE_MANA_REGEN_RATE, PLAYER_BASE_XP_TO_LEVEL, PLAYER_CON_HEALTH_MULTIPLIER, PLAYER_DEFAULT_KNOWN_SPELLS, 
    PLAYER_DEFAULT_MAX_MANA, PLAYER_DEFAULT_MAX_TOTAL_SUMMONS, PLAYER_DEFAULT_NAME, PLAYER_DEFAULT_RESPAWN_REGION, 
    PLAYER_DEFAULT_RESPAWN_ROOM, PLAYER_DEFAULT_STATS, PLAYER_DEFENSE_DEX_DIVISOR, PLAYER_HEALTH_REGEN_STRENGTH_DIVISOR, 
    PLAYER_LEVEL_CON_HEALTH_MULTIPLIER, PLAYER_LEVEL_HEALTH_BASE_INCREASE, PLAYER_LEVEL_UP_STAT_INCREASE, 
    PLAYER_MANA_LEVEL_UP_INT_DIVISOR, PLAYER_MANA_LEVEL_UP_MULTIPLIER, PLAYER_MANA_REGEN_WISDOM_DIVISOR,
    PLAYER_MAX_COMBAT_MESSAGES, PLAYER_REGEN_TICK_INTERVAL, PLAYER_XP_TO_LEVEL_MULTIPLIER, 
    FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, MIN_ATTACK_COOLDOWN
)
from engine.config.config_display import FORMAT_CATEGORY
from engine.game_object import GameObject
from engine.items.inventory import Inventory
from engine.items.item import Item
from engine.items.weapon import Weapon
from engine.items.item_factory import ItemFactory
from engine.magic.spell import Spell
from engine.magic.spell_registry import get_spell
from engine.magic.effects import apply_spell_effect
from engine.utils.utils import calculate_xp_gain, format_loot_drop_message
from engine.core.combat_system import CombatSystem 
from engine.core.conversation_history import ConversationHistory

# Import Mixins
from engine.player.display import PlayerDisplayMixin
from engine.player.persistence import PlayerPersistenceMixin

if TYPE_CHECKING:
    from engine.world.world import World

# MIXINS MUST COME BEFORE GameObject TO OVERRIDE METHODS CORRECTLY
class Player(PlayerDisplayMixin, PlayerPersistenceMixin, GameObject):
    def __init__(self, name: str, obj_id: str = "player"):
        super().__init__(obj_id=obj_id, name=name, description="The main character.")
        self.inventory = Inventory(max_slots=DEFAULT_INVENTORY_MAX_SLOTS, max_weight=DEFAULT_INVENTORY_MAX_WEIGHT)
        self.max_mana = PLAYER_DEFAULT_MAX_MANA
        self.mana = self.max_mana
        self.mana_regen_rate = PLAYER_BASE_MANA_REGEN_RATE
        self.last_mana_regen_time = 0
        self.stats = PLAYER_DEFAULT_STATS.copy()
        self.max_health = PLAYER_BASE_HEALTH + int(self.stats.get('constitution', 10)) * PLAYER_CON_HEALTH_MULTIPLIER
        self.health = self.max_health
        self.level = 1
        self.player_class = "Adventurer"
        self.experience = 0
        self.experience_to_level = PLAYER_BASE_XP_TO_LEVEL
        
        # Skills: Dict[SkillName, Dict[property, value]]
        self.skills: Dict[str, Dict[str, int]] = {}
        
        self.quest_log: Dict[str, Any] = {}
        self.completed_quest_log: Dict[str, Any] = {}
        self.archived_quest_log: Dict[str, Any] = {}
        self.equipment: Dict[str, Optional[Item]] = {slot: None for slot in EQUIPMENT_SLOTS}
        self.valid_slots_for_type = EQUIPMENT_VALID_SLOTS_BY_TYPE.copy()
        self.attack_power = PLAYER_BASE_ATTACK_POWER
        self.defense = PLAYER_BASE_DEFENSE
        self.is_alive = True
        self.faction = "player"
        self.in_combat = False
        self.combat_target: Optional[Any] = None
        self.attack_cooldown = PLAYER_BASE_ATTACK_COOLDOWN
        self.last_attack_time = 0
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
        
        # Interaction State
        self.trading_with: Optional[str] = None
        self.active_minigame: Optional[Dict[str, Any]] = None
        self.follow_target: Optional[str] = None # Added for follow command
        
        # Conversation System
        self.conversation = ConversationHistory()
        self.last_talked_to: Optional[str] = None 

        # Collections
        self.collections_progress: Dict[str, List[str]] = {} 
        self.collections_completed: Dict[str, bool] = {} 

    def get_skill_level(self, skill_name: str) -> int:
        """Safely gets the level of a skill, defaulting to 0."""
        skill_data = self.skills.get(skill_name)
        if not skill_data:
            return 0
        if isinstance(skill_data, int):
            return skill_data
        return skill_data.get("level", 0)

    def add_skill(self, skill_name: str, level: int = 1) -> None:
        """Initializes or increments a skill."""
        if skill_name not in self.skills:
            self.skills[skill_name] = {"level": level, "xp": 0}
        else:
            # Legacy check
            if isinstance(self.skills[skill_name], int):
                self.skills[skill_name] = {"level": self.skills[skill_name], "xp": 0} # type: ignore
                
            self.skills[skill_name]["level"] += level

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
        if not self.is_alive: return []
        if not self.current_region_id: return []
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
        return self.process_active_effects(current_time, time_delta_effects)

    def get_resistance(self, damage_type: str) -> int:
        total_res = super().get_resistance(damage_type)
        for item in self.equipment.values():
            if item:
                item_resistances = item.get_property("resistances", {})
                total_res += item_resistances.get(damage_type, 0)
        return total_res

    def gain_experience(self, amount: int) -> Tuple[bool, str]:
        self.experience += amount
        leveled_up = False
        level_up_messages = []
        while self.experience >= self.experience_to_level:
            level_up_message = self.level_up()
            level_up_messages.append(level_up_message)
            leveled_up = True
        return (leveled_up, "\n".join(level_up_messages))

    def level_up(self) -> str:
        old_stats = self.stats.copy(); old_max_health = self.max_health; old_max_mana = self.max_mana
        self.level += 1
        self.experience -= self.experience_to_level
        self.experience_to_level = int(self.experience_to_level * PLAYER_XP_TO_LEVEL_MULTIPLIER)
        for stat in ["strength", "dexterity", "intelligence", "wisdom", "constitution", "agility"]:
            self.stats[stat] += PLAYER_LEVEL_UP_STAT_INCREASE
        health_increase = PLAYER_LEVEL_HEALTH_BASE_INCREASE + int(self.stats.get('constitution', 10) * PLAYER_LEVEL_CON_HEALTH_MULTIPLIER)
        self.max_health += health_increase
        self.health += (self.max_health - old_max_health)
        mana_increase = int(self.max_mana * (PLAYER_MANA_LEVEL_UP_MULTIPLIER - 1) + self.stats["intelligence"] / PLAYER_MANA_LEVEL_UP_INT_DIVISOR)
        self.max_mana += mana_increase
        self.mana += (self.max_mana - old_max_mana)
        message = f"{FORMAT_HIGHLIGHT}You have reached level {self.level}!{FORMAT_RESET}\n  - Max Health: {old_max_health} -> {self.max_health} (+{self.max_health - old_max_health})\n  - Max Mana:   {old_max_mana} -> {self.max_mana} (+{self.max_mana - old_max_mana})\n{FORMAT_CATEGORY}Stats Increased:{FORMAT_RESET}\n"
        for stat_name, old_value in old_stats.items():
            if stat_name == "resistances": continue
            new_value = self.stats[stat_name]
            if new_value > old_value: message += f"  - {stat_name.capitalize()}: {old_value} -> {new_value} (+{new_value - old_value})\n"
        return message.strip()

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
        if world and hasattr(world, 'npcs'):
            for npc in world.npcs.values():
                if npc.in_combat and self in npc.combat_targets: npc.exit_combat(self)
        self.combat_targets.clear(); self.active_effects.clear()
        if self.world:
            all_summon_ids = [inst_id for ids in self.active_summons.values() for inst_id in ids]
            for instance_id in all_summon_ids:
                summon = self.world.get_npc(instance_id)
                if summon and hasattr(summon, 'despawn'): summon.despawn(self.world, silent=True)
        self.active_summons = {}

    def respawn(self) -> None:
        self.health = self.max_health; self.mana = self.max_mana
        self.is_alive = True; self.in_combat = False; self.combat_targets.clear()
        self.spell_cooldowns.clear(); self.active_summons = {}; self.active_effects = []
        self.current_region_id = self.respawn_region_id
        self.current_room_id = self.respawn_room_id

    def get_attack_power(self) -> int:
        attack = self.attack_power + self.get_effective_stat("strength") // PLAYER_ATTACK_POWER_STR_DIVISOR
        main_hand_weapon = self.equipment.get("main_hand")
        if isinstance(main_hand_weapon, Weapon) and main_hand_weapon.get_property("durability", 1) > 0:
            attack += main_hand_weapon.get_property("damage", 0)
        return attack

    def get_defense(self) -> int:
        defense = self.defense + self.get_effective_stat("dexterity") // PLAYER_DEFENSE_DEX_DIVISOR
        for item in self.equipment.values():
            if isinstance(item, Item) and item.get_property("durability", 1) > 0:
                defense += item.get_property("defense", 0)
        return defense
    
    def get_effective_attack_cooldown(self) -> float:
        base_cooldown = self.attack_cooldown
        effective_agility = self.get_effective_stat('agility')
        speed_modifier = (effective_agility - 10) * 0.01
        effective_cooldown = base_cooldown / (1 + speed_modifier)
        return max(MIN_ATTACK_COOLDOWN, effective_cooldown)

    def can_attack(self, current_time: float) -> bool: return self.is_alive and current_time - self.last_attack_time >= self.get_effective_attack_cooldown()
        
    def enter_combat(self, target) -> None:
        if not self.is_alive: return
        if not target or not getattr(target, 'is_alive', False): return
        if target is self: return
        self.in_combat = True; self.combat_targets.add(target)
        if hasattr(target, 'enter_combat') and not (hasattr(target, 'combat_targets') and self in target.combat_targets): target.enter_combat(self)
        if self.world:
            for instance_ids in self.active_summons.values():
                for instance_id in instance_ids:
                    summon = self.world.get_npc(instance_id)
                    if summon and summon.is_alive and hasattr(summon, 'enter_combat'): summon.enter_combat(target)

    def exit_combat(self, target: Optional[Any] = None) -> None:
        """
        Exits combat with a specific target or all targets.
        """
        if target:
            # Safe removal of a single target
            if target in self.combat_targets:
                self.combat_targets.discard(target)
                if hasattr(target, "exit_combat"):
                    target.exit_combat(self)
        else:
            # Clear everything only if target is explicitly None
            target_list = list(self.combat_targets)
            for t in target_list:
                self.combat_targets.discard(t)
                if hasattr(t, "exit_combat"):
                    t.exit_combat(self)

        # Only stop the combat state if no enemies remain
        if not self.combat_targets:
            self.in_combat = False
            self.combat_target = None

        if self.world:
            for instance_ids in self.active_summons.values():
                for instance_id in instance_ids:
                    summon = self.world.get_npc(instance_id)
                    if summon and summon.is_alive and hasattr(summon, 'exit_combat'):
                        if target:
                            summon.exit_combat(target)
                        elif not self.in_combat:
                            summon.exit_combat()

    def _add_combat_message(self, message: str) -> None:
        for line in message.strip().splitlines():
            self.combat_messages.append(line)
            while len(self.combat_messages) > self.max_combat_messages: self.combat_messages.pop(0)

    def attack(self, target, world: Optional['World'] = None) -> Dict[str, Any]:
        if not self.is_alive: return {"message": "You cannot attack while dead."}
        if self.has_effect("Stun"): return {"message": f"{FORMAT_ERROR}You are stunned and cannot attack!{FORMAT_RESET}"}
        
        equipped_weapon = self.equipment.get("main_hand")
        always_hits = isinstance(equipped_weapon, Item) and equipped_weapon.get_property("always_hit", False)
        weapon_name = equipped_weapon.name if isinstance(equipped_weapon, Item) else "bare hands"
        attack_power = self.get_attack_power()
        
        self.enter_combat(target)
        combat_result = CombatSystem.execute_attack(attacker=self, defender=target, attack_power=attack_power, weapon_name=weapon_name, always_hit=always_hits, viewer=self)
        
        message = combat_result["message"]
        if combat_result["is_hit"] and isinstance(equipped_weapon, Weapon):
            current_durability = equipped_weapon.get_property("durability", 0)
            if current_durability > 0:
                equipped_weapon.update_property("durability", current_durability - ITEM_DURABILITY_LOSS_ON_HIT)
                if current_durability - ITEM_DURABILITY_LOSS_ON_HIT <= 0: message += f"\n{FORMAT_ERROR}Your {weapon_name} breaks!{FORMAT_RESET}"

        self._add_combat_message(message)
        result_message = message

        if combat_result["target_defeated"]:
            self.exit_combat(target)
            quest_update_message = None
            if world: quest_update_message = world.dispatch_event("npc_killed", {"player": self, "npc": target})
            
            gold_dropped = 0
            if hasattr(target, 'loot_table'):
                gold_data = target.loot_table.get("gold_value")
                if gold_data and isinstance(gold_data, dict):
                    if random.random() < gold_data.get("chance", 0.0):
                        qty_range = gold_data.get("quantity", [1, 1])
                        gold_dropped = random.randint(qty_range[0], qty_range[1])
                        if gold_dropped > 0:
                            self.gold += gold_dropped
                            result_message += f"\n{FORMAT_SUCCESS}You find {gold_dropped} gold.{FORMAT_RESET}"
            
            target_level = getattr(target, 'level', 1)
            final_xp_gained = calculate_xp_gain(self.level, target_level, getattr(target, 'max_health', 10))
            if final_xp_gained > 0:
                result_message += f"\n{FORMAT_SUCCESS}You gain {final_xp_gained} experience!{FORMAT_RESET}"
                leveled_up, level_up_msg = self.gain_experience(final_xp_gained)
                if leveled_up and level_up_msg: result_message += "\n" + level_up_msg
            
            loot_str = format_loot_drop_message(self, target, target.die(world) if hasattr(target, 'die') else [])
            if loot_str: result_message += "\n" + loot_str
            if quest_update_message: result_message += "\n" + quest_update_message
            
            self._add_combat_message(result_message.replace(message, "").strip())

        self.last_attack_time = time.time()
        return {"message": result_message}

    def cast_spell(self, spell: Spell, target, current_time: float, world: Optional['World'] = None) -> Dict[str, Any]:
        if self.has_effect("Stun"): return {"success": False, "message": f"{FORMAT_ERROR}You are stunned!{FORMAT_RESET}", "mana_cost": 0}
        can_cast, reason = self.can_cast_spell(spell, current_time)
        if not can_cast: return {"success": False, "message": reason, "mana_cost": 0}
        self.mana -= spell.mana_cost
        self.spell_cooldowns[spell.spell_id] = current_time + spell.cooldown
        if spell.target_type == "enemy" and target != self: self.enter_combat(target)
        
        value, effect_message = apply_spell_effect(self, target, spell, self)
        full_message = f"{spell.format_cast_message(self)}\n{effect_message}"
        if spell.target_type == "enemy" or target != self: self._add_combat_message(effect_message)
        
        result = {"success": True, "message": full_message, "value": value}
        if not getattr(target, 'is_alive', True) and spell.effect_type == "damage":
            self.exit_combat(target)
            quest_update_message = None
            if world: quest_update_message = world.dispatch_event("npc_killed", {"player": self, "npc": target})

            gold_dropped = 0
            if hasattr(target, 'loot_table'):
                gold_data = target.loot_table.get("gold_value")
                if gold_data:
                    if random.random() < gold_data.get("chance", 0.0):
                        qty_range = gold_data.get("quantity", [1, 1])
                        gold_dropped = random.randint(qty_range[0], qty_range[1])
                        if gold_dropped > 0:
                            self.gold += gold_dropped
                            result["message"] += f"\n{FORMAT_SUCCESS}You find {gold_dropped} gold.{FORMAT_RESET}"
            
            final_xp_gained = calculate_xp_gain(self.level, getattr(target, 'level', 1), getattr(target, 'max_health', 10))
            if final_xp_gained > 0:
                result["message"] += f"\n{FORMAT_SUCCESS}You gain {final_xp_gained} experience!{FORMAT_RESET}"
                leveled_up, level_up_msg = self.gain_experience(final_xp_gained)
                if leveled_up and level_up_msg: result["message"] += "\n" + level_up_msg

            loot_str = format_loot_drop_message(self, target, target.die(world) if hasattr(target, 'die') else [])
            if loot_str: result["message"] += "\n" + loot_str
            if quest_update_message: result["message"] += "\n" + quest_update_message
            self._add_combat_message(result["message"].replace(full_message, "").strip())
        return result
    
    def get_valid_slots(self, item: Item) -> List[str]:
        valid = []; item_type_name = item.__class__.__name__
        item_slots = item.get_property("equip_slot")
        if isinstance(item_slots, str): item_slots = [item_slots]
        if isinstance(item_slots, list):
             for slot in item_slots:
                  if slot in self.equipment: valid.append(slot)
             if valid: return valid
        if item_type_name in self.valid_slots_for_type:
             for slot in self.valid_slots_for_type[item_type_name]:
                  if slot in self.equipment: valid.append(slot)
             return valid
        return valid

    def equip_item(self, item: Item, slot_name: Optional[str] = None) -> Tuple[bool, str]:
        if not self.is_alive: return False, "You cannot equip items while dead."
        valid_slots = self.get_valid_slots(item)
        if not valid_slots: return False, f"You can't figure out how to equip the {item.name}."
        target_slot = None
        if slot_name:
            if slot_name in valid_slots: target_slot = slot_name
            else: return False, f"The {item.name} cannot be equipped in the '{slot_name}' slot. Valid: {', '.join(valid_slots)}"
        else:
            for s in valid_slots:
                if self.equipment[s] is None: target_slot = s; break
            if target_slot is None: target_slot = valid_slots[0]
        if not self.inventory.get_item(item.obj_id): return False, f"You don't have the {item.name} in your inventory."
        
        unequip_message = ""
        currently_equipped = self.equipment.get(target_slot)
        if currently_equipped:
            success, msg = self.unequip_item(target_slot)
            if not success: return False, f"Could not unequip {currently_equipped.name} to make space: {msg}"
            unequip_message = f"(You unequip the {currently_equipped.name}) "

        removed_item, _, remove_msg = self.inventory.remove_item(item.obj_id, 1)
        if not removed_item: return False, f"Failed to remove {item.name} from inventory: {remove_msg}"
        self.equipment[target_slot] = item
        
        effect_data = item.get_property("equip_effect")
        if effect_data and isinstance(effect_data, dict): self.apply_effect(effect_data, time.time())
        return True, f"{unequip_message}You equip the {item.name} in your {target_slot.replace('_', ' ')}."

    def unequip_item(self, slot_name: str) -> Tuple[bool, str]:
        if not self.is_alive: return False, "You cannot unequip items while dead."
        if slot_name not in self.equipment: return False, f"Invalid equipment slot: {slot_name}"
        item_to_unequip = self.equipment.get(slot_name)
        if not item_to_unequip: return False, f"You have nothing equipped in your {slot_name.replace('_', ' ')}."
        
        effect_data = item_to_unequip.get_property("equip_effect")
        if effect_data and isinstance(effect_data, dict):
            effect_name = effect_data.get("name")
            if effect_name: self.remove_effect(effect_name)

        success, add_message = self.inventory.add_item(item_to_unequip, 1)
        if not success: 
            if effect_data: self.apply_effect(effect_data, time.time())
            return False, f"Could not unequip {item_to_unequip.name}: {add_message}"

        self.equipment[slot_name] = None
        return True, f"You unequip the {item_to_unequip.name} from your {slot_name.replace('_', ' ')}."

    def learn_spell(self, spell_id: str) -> Tuple[bool, str]:
        spell = get_spell(spell_id)
        if not spell: return False, f"The secrets of '{spell_id}' seem non-existent."
        if spell_id in self.known_spells: return False, f"You already know how to cast {spell.name}."
        if self.level < spell.level_required: return False, f"You lack the experience to grasp {spell.name} (requires level {spell.level_required})."
        self.known_spells.add(spell_id)
        return True, f"You study the technique and successfully learn {spell.name}!"

    def forget_spell(self, spell_id: str) -> bool:
        if spell_id in self.known_spells:
            self.known_spells.remove(spell_id)
            self.spell_cooldowns.pop(spell_id, None)
            return True
        return False

    def can_cast_spell(self, spell: Spell, current_time: float) -> Tuple[bool, str]:
        if not self.is_alive: return False, "You cannot cast spells while dead."
        if spell.spell_id not in self.known_spells: return False, "You don't know that spell."
        if self.level < spell.level_required: return False, f"You need to be level {spell.level_required} to cast {spell.name}."
        if self.mana < spell.mana_cost: return False, f"Not enough mana (need {spell.mana_cost}, have {int(self.mana)})."
        cooldown_end_time = self.spell_cooldowns.get(spell.spell_id, 0)
        if current_time < cooldown_end_time: return False, f"{spell.name} is on cooldown for {max(0, cooldown_end_time - current_time):.1f}s."
        return True, ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any], world: 'World') -> Optional['Player']:
        player = cls(name=data.get("name", PLAYER_DEFAULT_NAME))
        player.obj_id = data.get("id", "player")
        player.player_class = data.get("player_class", "Adventurer")
        player.gold = data.get("gold", 0)
        player.level = data.get("level", 1)
        player.experience = data.get("experience", 0)
        player.experience_to_level = data.get("experience_to_level", PLAYER_BASE_XP_TO_LEVEL)
        player.is_alive = data.get("is_alive", True)
        
        player.stats = PLAYER_DEFAULT_STATS.copy(); player.stats.update(data.get("stats", {}))
        
        # --- Skill Migration Logic with explicit casting ---
        raw_skills = data.get("skills", {})
        player.skills = {}
        for k, v in raw_skills.items():
            if isinstance(v, int):
                player.skills[k] = {"level": v, "xp": 0}
            else:
                # Explicit cast to satisfy Pylance
                player.skills[k] = cast(Dict[str, int], v)
        # -----------------------------

        player.quest_log = data.get("quest_log", {})
        player.completed_quest_log = data.get("completed_quest_log", {})
        player.archived_quest_log = data.get("archived_quest_log", {})
        player.active_effects = data.get("effects", [])
        
        # --- FIX: Re-calculate stat_modifiers from loaded effects ---
        # stat_modifiers is a runtime cache and not saved directly.
        # We must iterate loaded effects and re-apply any stat_mods.
        for effect in player.active_effects:
            if effect.get("type") == "stat_mod":
                for stat, value in effect.get("modifiers", {}).items():
                    player.stat_modifiers[stat] = player.stat_modifiers.get(stat, 0) + value
        # -----------------------------------------------------------

        player.spell_cooldowns = data.get("spell_cooldowns", {})
        
        loc = data.get("current_location", {})
        player.current_region_id = loc.get("region_id")
        player.current_room_id = loc.get("room_id")
        player.respawn_region_id = data.get("respawn_region_id", PLAYER_DEFAULT_RESPAWN_REGION)
        player.respawn_room_id = data.get("respawn_room_id", PLAYER_DEFAULT_RESPAWN_ROOM)
        
        player.known_spells = set(data.get("known_spells", PLAYER_DEFAULT_KNOWN_SPELLS))
        
        player.max_health = data.get("max_health", player.max_health)
        player.health = data.get("health", player.max_health)
        player.max_mana = data.get("max_mana", player.max_mana)
        player.mana = data.get("mana", player.max_mana)
        
        player.inventory = Inventory.from_dict(data.get("inventory", {}), world)
        
        equipment_data = data.get("equipment", {})
        
        # Use Factory to recreate items
        player.equipment = {slot: None for slot in EQUIPMENT_SLOTS}
        for slot, item_ref in equipment_data.items():
            if slot in player.equipment and item_ref and "item_id" in item_ref:
                item = ItemFactory.create_item_from_template(item_ref["item_id"], world, **item_ref.get("properties_override", {}))
                if item: player.equipment[slot] = item

        player.last_talked_to = data.get("last_talked_to")
        if "conversation_history" in data:
            player.conversation = ConversationHistory.from_dict(data["conversation_history"])
        
        player.collections_progress = data.get("collections_progress", {})
        player.collections_completed = data.get("collections_completed", {})
        
        player.follow_target = data.get("follow_target")

        player.world = world
        return player