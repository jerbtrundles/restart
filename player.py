# player.py

from typing import List, Dict, Optional, Any, Tuple, Set, TYPE_CHECKING
import time
import random

from config import (
    HIT_CHANCE_AGILITY_FACTOR, LEVEL_DIFF_COMBAT_MODIFIERS, MAX_HIT_CHANCE, MIN_ATTACK_COOLDOWN, MIN_HIT_CHANCE, MINIMUM_DAMAGE_TAKEN,
    FORMAT_BLUE, FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, FORMAT_YELLOW,
    DEFAULT_INVENTORY_MAX_SLOTS, DEFAULT_INVENTORY_MAX_WEIGHT, EQUIPMENT_SLOTS, EQUIPMENT_VALID_SLOTS_BY_TYPE, ITEM_DURABILITY_LOSS_ON_HIT,
    ITEM_DURABILITY_LOW_THRESHOLD, PLAYER_ATTACK_DAMAGE_VARIATION_RANGE, PLAYER_ATTACK_POWER_STR_DIVISOR, PLAYER_BASE_ATTACK_COOLDOWN,
    PLAYER_BASE_ATTACK_POWER, PLAYER_BASE_DEFENSE, PLAYER_BASE_HEALTH, PLAYER_BASE_HEALTH_REGEN_RATE, PLAYER_BASE_HIT_CHANCE,
    PLAYER_BASE_MANA_REGEN_RATE, PLAYER_BASE_XP_TO_LEVEL, PLAYER_CON_HEALTH_MULTIPLIER, PLAYER_DEFAULT_KNOWN_SPELLS, PLAYER_DEFAULT_MAX_MANA,
    PLAYER_DEFAULT_MAX_TOTAL_SUMMONS, PLAYER_DEFAULT_NAME, PLAYER_DEFAULT_RESPAWN_REGION, PLAYER_DEFAULT_RESPAWN_ROOM, PLAYER_DEFAULT_STATS,
    PLAYER_DEFENSE_DEX_DIVISOR, PLAYER_HEALTH_REGEN_STRENGTH_DIVISOR, PLAYER_LEVEL_CON_HEALTH_MULTIPLIER, PLAYER_LEVEL_HEALTH_BASE_INCREASE,
    PLAYER_LEVEL_UP_STAT_INCREASE, PLAYER_MANA_LEVEL_UP_INT_DIVISOR, PLAYER_MANA_LEVEL_UP_MULTIPLIER, PLAYER_MANA_REGEN_WISDOM_DIVISOR,
    PLAYER_MAX_COMBAT_MESSAGES, PLAYER_REGEN_TICK_INTERVAL, PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD, PLAYER_STATUS_HEALTH_LOW_THRESHOLD,
    PLAYER_XP_TO_LEVEL_MULTIPLIER
)
from game_object import GameObject
from items.inventory import Inventory
from items.weapon import Weapon
from items.consumable import Consumable
from items.item import Item
from magic.spell import Spell
from magic.spell_registry import get_spell
from magic.effects import apply_spell_effect
from utils.utils import _serialize_item_reference, calculate_xp_gain, format_loot_drop_message, format_name_for_display, get_article
from utils.text_formatter import format_target_name, get_level_diff_category

if TYPE_CHECKING:
    from world.world import World

class Player(GameObject):
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
        self.experience = 0
        self.experience_to_level = PLAYER_BASE_XP_TO_LEVEL
        self.skills: Dict[str, int] = {}
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
        self.trading_with: Optional[str] = None

    def update(self, current_time: float, time_delta_effects: float) -> List[str]:
        if not self.is_alive: return []

        if current_time - self.last_mana_regen_time >= PLAYER_REGEN_TICK_INTERVAL:
            base_mana_regen = self.mana_regen_rate * (1 + self.stats.get('wisdom', 10) / PLAYER_MANA_REGEN_WISDOM_DIVISOR)
            base_health_regen = PLAYER_BASE_HEALTH_REGEN_RATE * (1 + self.stats.get('strength', 10) / PLAYER_HEALTH_REGEN_STRENGTH_DIVISOR)
            regen_boost = 0
            for item in self.equipment.values():
                 if isinstance(item, Item):
                     regen_boost += item.get_property("regen_boost", 0)
            
            mana_regen_amount = int(PLAYER_REGEN_TICK_INTERVAL * (base_mana_regen + regen_boost))
            health_regen_amount = int(PLAYER_REGEN_TICK_INTERVAL * (base_health_regen + regen_boost))
            self.mana = min(self.max_mana, self.mana + mana_regen_amount)
            self.health = min(self.max_health, self.health + health_regen_amount)
            self.last_mana_regen_time = current_time 
        
        effect_messages = self.process_active_effects(current_time, time_delta_effects)
        return effect_messages

    def get_status(self) -> str:
        health_percent = (self.health / self.max_health) * 100 if self.max_health > 0 else 0
        health_text = f"{int(self.health)}/{int(self.max_health)}"
        if health_percent <= PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD: health_display = f"{FORMAT_ERROR}{health_text}{FORMAT_RESET}"
        elif health_percent <= PLAYER_STATUS_HEALTH_LOW_THRESHOLD: health_display = f"{FORMAT_HIGHLIGHT}{health_text}{FORMAT_RESET}"
        else: health_display = f"{FORMAT_SUCCESS}{health_text}{FORMAT_RESET}"
            
        mana_text = f"{int(self.mana)}/{int(self.max_mana)}"
        mana_display = f"{FORMAT_BLUE}{mana_text}{FORMAT_RESET}"
        
        status = f"{FORMAT_CATEGORY}Name:{FORMAT_RESET} {self.name}\n"
        status += f"{FORMAT_CATEGORY}Level:{FORMAT_RESET} {self.level} ({FORMAT_CATEGORY}XP:{FORMAT_RESET} {self.experience}/{self.experience_to_level})\n"
        status += f"{FORMAT_CATEGORY}Health:{FORMAT_RESET} {health_display}  {FORMAT_CATEGORY}Mana:{FORMAT_RESET} {mana_display}\n"
        
        stat_parts = []
        stats_to_show = ["strength", "dexterity", "constitution", "agility", "intelligence", "wisdom", "spell_power", "magic_resist"]
        for stat_name in stats_to_show:
            stat_value = self.stats.get(stat_name, 0)
            abbr = stat_name[:3].upper() if stat_name not in ["spell_power", "magic_resist"] else stat_name.upper()
            stat_parts.append(f"{abbr} {stat_value}")
        status += f"{FORMAT_CATEGORY}Stats:{FORMAT_RESET} {', '.join(stat_parts)}\n"
        
        status += f"{FORMAT_CATEGORY}Gold:{FORMAT_RESET} {self.gold}\n"
        
        effective_cd = self.get_effective_attack_cooldown()
        status += f"{FORMAT_CATEGORY}Attack:{FORMAT_RESET} {self.get_attack_power()} ({effective_cd:.1f}s CD), {FORMAT_CATEGORY}Defense:{FORMAT_RESET} {self.get_defense()}\n"
        
        equipped_items_found = False; equip_lines = []
        for slot in EQUIPMENT_SLOTS:
            item = self.equipment.get(slot)
            if isinstance(item, Item):
                equipped_items_found = True
                slot_display = slot.replace('_', ' ').capitalize()
                durability_str = ""
                max_dura = item.get_property("max_durability", 0)
                if max_dura > 0:
                     current_dura = item.get_property("durability", max_dura)
                     dura_percent = (current_dura / max_dura) * 100
                     dura_color = FORMAT_SUCCESS
                     if current_dura <= 0: dura_color = FORMAT_ERROR
                     elif dura_percent <= (ITEM_DURABILITY_LOW_THRESHOLD * 100): dura_color = FORMAT_YELLOW
                     durability_str = f" [{dura_color}{int(current_dura)}/{int(max_dura)}{FORMAT_RESET}]"
                equip_lines.append(f"  - {slot_display}: {item.name}{durability_str}")
        if equipped_items_found: status += f"\n{FORMAT_TITLE}EQUIPPED{FORMAT_RESET}\n" + "\n".join(equip_lines) + "\n"
        
        if self.active_effects:
            status += f"\n{FORMAT_TITLE}EFFECTS{FORMAT_RESET}\n"
            effect_lines = []
            for effect in sorted(self.active_effects, key=lambda e: e.get("name", "zzz")):
                name = effect.get('name', 'Unknown Effect'); duration = effect.get('duration_remaining', 0)
                duration_str = f"{duration / 60:.1f}m" if duration > 60 else f"{duration:.1f}s"
                details = ""
                if effect.get("type") == "dot":
                     details = f" ({effect.get('damage_per_tick', 0)} {effect.get('damage_type', '')}/ {effect.get('tick_interval', 3.0):.0f}s)"
                elif effect.get("type") == "hot":
                    details = f" (+{effect.get('heal_per_tick', 0)} HP/ {effect.get('tick_interval', 3.0):.0f}s)"

                duration_display = f" ({duration_str} remaining)" if "duration_remaining" in effect else ""
                effect_lines.append(f"  - {name}{details}{duration_display}")
            status += "\n".join(effect_lines) + "\n"
        
        if self.known_spells:
             status += f"\n{FORMAT_TITLE}SPELLS KNOWN{FORMAT_RESET}\n"
             spell_list = []; current_time = time.time()
             for spell_id in sorted(list(self.known_spells)):
                  spell = get_spell(spell_id)
                  if spell:
                       cooldown_end = self.spell_cooldowns.get(spell_id, 0)
                       cd_status = f" [{FORMAT_ERROR}CD {max(0, cooldown_end - current_time):.1f}s{FORMAT_RESET}]" if current_time < cooldown_end else ""
                       req_color = FORMAT_SUCCESS if self.level >= spell.level_required else FORMAT_ERROR
                       level_req_display = f" ({req_color}L{spell.level_required}{FORMAT_RESET})" if spell.level_required > 1 else ""
                       spell_list.append(f"  - {FORMAT_HIGHLIGHT}{spell.name}{FORMAT_RESET}{level_req_display}: {spell.mana_cost} MP{cd_status}")
             status += "\n".join(spell_list) + "\n"

        if self.in_combat: status += "\n" + self.get_combat_status()
        if not self.is_alive: status += f"\n{FORMAT_ERROR}** YOU ARE DEAD **{FORMAT_RESET}\n"
        return status.strip()

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
        old_stats = self.stats.copy()
        old_max_health = self.max_health
        old_max_mana = self.max_mana

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
        
        # Build the detailed message
        message = f"{FORMAT_HIGHLIGHT}You have reached level {self.level}!{FORMAT_RESET}\n"
        message += f"  - Max Health: {old_max_health} -> {self.max_health} (+{self.max_health - old_max_health})\n"
        message += f"  - Max Mana:   {old_max_mana} -> {self.max_mana} (+{self.max_mana - old_max_mana})\n"
        message += f"{FORMAT_CATEGORY}Stats Increased:{FORMAT_RESET}\n"
        for stat_name, old_value in old_stats.items():
            new_value = self.stats[stat_name]
            if new_value > old_value:
                message += f"  - {stat_name.capitalize()}: {old_value} -> {new_value} (+{new_value - old_value})\n"
        
        return message.strip()

    def add_skill(self, skill_name: str, level: int = 1) -> None:
        self.skills[skill_name] = self.skills.get(skill_name, 0) + level

    def get_skill_level(self, skill_name: str) -> int:
        return self.skills.get(skill_name, 0)

    def update_quest(self, quest_id: str, progress: Any) -> None:
        self.quest_log[quest_id] = progress

    def get_quest_progress(self, quest_id: str) -> Optional[Any]:
        return self.quest_log.get(quest_id)

    def heal(self, amount: int) -> int:
        if not self.is_alive: return 0
        old_health = self.health
        self.health = min(self.health + amount, self.max_health)
        return int(self.health - old_health)

    def take_damage(self, amount: int, damage_type: str = "physical") -> int:
        if not self.is_alive: return 0
        immunity_chance = 0.0
        for item in self.equipment.values():
            if isinstance(item, Item):
                immunity_chance = max(immunity_chance, item.get_property("damage_immunity_chance", 0.0))
        if immunity_chance > 0 and random.random() < immunity_chance: return 0
        final_reduction = 0
        if damage_type == "physical": final_reduction = self.get_defense()
        else:
            final_reduction = self.stats.get("magic_resist", 0)
            for item in self.equipment.values():
                if isinstance(item, Item): final_reduction += item.get_property("magic_resist", 0)
        reduced_damage = max(0, amount - final_reduction)
        actual_damage = max(MINIMUM_DAMAGE_TAKEN, reduced_damage) if amount > 0 and reduced_damage > 0 else 0
        old_health = self.health
        self.health = max(0, self.health - actual_damage)
        if self.health <= 0: self.die()
        return int(old_health - self.health)

    def die(self, world: Optional['World'] = None) -> None:
        if not self.is_alive: return
        self.health = 0
        self.is_alive = False
        self.in_combat = False

        # # --- BUG FIX: Notify all NPCs that were targeting the player ---
        # if world and hasattr(world, 'npcs'):
        #     player_instance = self
        #     for npc in world.npcs.values():
        #         # Check if the NPC is in combat and targeting the player
        #         if npc.in_combat and player_instance in npc.combat_targets:
        #             # Force the NPC to disengage from the now-dead player
        #             npc.exit_combat(player_instance)
        # # --- END BUG FIX ---

        self.combat_targets.clear()
        self.active_effects.clear()

        # Despawn any active summons
        if self.world:
            all_summon_ids = [inst_id for ids in self.active_summons.values() for inst_id in ids]
            for instance_id in all_summon_ids:
                summon = self.world.get_npc(instance_id)
                if summon and hasattr(summon, 'despawn'):
                    summon.despawn(self.world, silent=True)
        self.active_summons = {}

    def respawn(self) -> None:
        self.health = self.max_health; self.mana = self.max_mana
        self.is_alive = True; self.in_combat = False; self.combat_targets.clear()
        self.spell_cooldowns.clear(); self.active_summons = {}; self.active_effects = []
        self.current_region_id = self.respawn_region_id
        self.current_room_id = self.respawn_room_id

    def get_attack_power(self) -> int:
        attack = self.attack_power + self.stats.get("strength", 0) // PLAYER_ATTACK_POWER_STR_DIVISOR
        main_hand_weapon = self.equipment.get("main_hand")
        if isinstance(main_hand_weapon, Weapon) and main_hand_weapon.get_property("durability", 1) > 0:
            attack += main_hand_weapon.get_property("damage", 0)
        return attack

    def get_defense(self) -> int:
        defense = self.defense + self.stats.get("dexterity", 10) // PLAYER_DEFENSE_DEX_DIVISOR
        for item in self.equipment.values():
            if isinstance(item, Item) and item.get_property("durability", 1) > 0:
                defense += item.get_property("defense", 0)
        return defense
    
    def get_effective_attack_cooldown(self) -> float:
        base_cooldown = self.attack_cooldown
        haste_factor = 1.0
        for item in self.equipment.values():
            if isinstance(item, Item):
                multiplier = item.get_property("haste_multiplier")
                if multiplier and multiplier > 0: haste_factor *= multiplier
        effective_cooldown = base_cooldown * haste_factor
        return max(MIN_ATTACK_COOLDOWN, effective_cooldown)

    def can_attack(self, current_time: float) -> bool:
        return self.is_alive and current_time - self.last_attack_time >= self.get_effective_attack_cooldown()
        
    def enter_combat(self, target) -> None:
        if not self.is_alive: return
        if not target or not getattr(target, 'is_alive', False): return
        if target is self: return

        self.in_combat = True
        self.combat_targets.add(target)

        if hasattr(target, 'enter_combat') and not (hasattr(target, 'combat_targets') and self in target.combat_targets):
            target.enter_combat(self)

        if self.world:
            for instance_ids in self.active_summons.values():
                for instance_id in instance_ids:
                    summon = self.world.get_npc(instance_id)
                    if summon and summon.is_alive and hasattr(summon, 'enter_combat'):
                        summon.enter_combat(target)

    def exit_combat(self, target=None) -> None:
        target_list_to_exit = [target] if target and target in self.combat_targets else list(self.combat_targets)
        for t in target_list_to_exit:
            self.combat_targets.discard(t)
            if hasattr(t, "exit_combat"): t.exit_combat(self)
        if not self.combat_targets: self.in_combat = False
        if self.world:
            for instance_ids in self.active_summons.values():
                for instance_id in instance_ids:
                    summon = self.world.get_npc(instance_id)
                    if summon and summon.is_alive and hasattr(summon, 'exit_combat'):
                        if target: summon.exit_combat(target)
                        elif not self.in_combat: summon.exit_combat()
    
    def get_combat_status(self) -> str:
        if not self.in_combat or not self.combat_targets: return ""
        status = f"{FORMAT_TITLE}COMBAT STATUS{FORMAT_RESET}\n{FORMAT_CATEGORY}Fighting:{FORMAT_RESET}\n"
        valid_targets = [t for t in self.combat_targets if hasattr(t, 'is_alive') and t.is_alive]
        if not valid_targets: status += "  (No current targets)\n"
        else:
            for target in valid_targets:
                formatted_name = format_name_for_display(self, target, start_of_sentence=True)
                if hasattr(target, "health") and hasattr(target, "max_health") and target.max_health > 0:
                    hp_percent = (target.health / target.max_health) * 100
                    hp_color = FORMAT_SUCCESS if hp_percent > 50 else (FORMAT_HIGHLIGHT if hp_percent > 25 else FORMAT_ERROR)
                    status += f"  - {formatted_name}: {hp_color}{int(target.health)}/{int(target.max_health)}{FORMAT_RESET} HP\n"
                else: status += f"  - {formatted_name}\n"
        if self.combat_messages:
            status += f"\n{FORMAT_CATEGORY}Recent Actions:{FORMAT_RESET}\n"
            for msg in self.combat_messages: status += f"  - {msg}\n"
        return status
        
    def _add_combat_message(self, message: str) -> None:
        for line in message.strip().splitlines():
            self.combat_messages.append(line)
            while len(self.combat_messages) > self.max_combat_messages:
                self.combat_messages.pop(0)

    def attack(self, target, world: Optional['World'] = None) -> Dict[str, Any]:
        if not self.is_alive: return {"message": "You cannot attack while dead."}
        equipped_weapon = self.equipment.get("main_hand")
        always_hits = isinstance(equipped_weapon, Item) and equipped_weapon.get_property("always_hit", False)
        target_level = getattr(target, 'level', 1)
        category = get_level_diff_category(self.level, target_level)
        final_hit_chance = 1.0
        
        if not always_hits:
            base_hit_chance = PLAYER_BASE_HIT_CHANCE
            agi_modifier = (self.stats.get("agility", 10) - getattr(target, "stats", {}).get("agility", 8)) * HIT_CHANCE_AGILITY_FACTOR
            hit_chance_mod, _, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
            final_hit_chance = max(MIN_HIT_CHANCE, min((base_hit_chance + agi_modifier) * hit_chance_mod, MAX_HIT_CHANCE))

        if not always_hits and random.random() > final_hit_chance:
            miss_message = f"You swing at {format_name_for_display(self, target, False)} but miss!"
            self._add_combat_message(miss_message)
            self.last_attack_time = time.time()
            return {"message": miss_message, "missed": True}
        
        self.enter_combat(target)
        attack_power = self.get_attack_power()
        damage_variation = random.randint(*PLAYER_ATTACK_DAMAGE_VARIATION_RANGE)
        base_attack_damage = max(1, attack_power + damage_variation)
        
        _, damage_dealt_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        modified_attack_damage = max(MINIMUM_DAMAGE_TAKEN, int(base_attack_damage * damage_dealt_mod))
        
        actual_damage = target.take_damage(modified_attack_damage, damage_type="physical")
        
        weapon_name = "bare hands"; weapon_broke = False
        if isinstance(equipped_weapon, Weapon):
            weapon_name = equipped_weapon.name
            current_durability = equipped_weapon.get_property("durability", 0)
            if current_durability > 0:
                equipped_weapon.update_property("durability", current_durability - ITEM_DURABILITY_LOSS_ON_HIT)
                if current_durability - ITEM_DURABILITY_LOSS_ON_HIT <= 0: weapon_broke = True

        hit_message = f"You attack {format_name_for_display(self, target, False)} with your {weapon_name} for {int(actual_damage)} damage!"
        if weapon_broke: hit_message += f"\n{FORMAT_ERROR}Your {weapon_name} breaks!{FORMAT_RESET}"
        
        self._add_combat_message(hit_message)
        result_message = hit_message

        if not target.is_alive:
            death_message = f"{format_name_for_display(self, target, True)} has been defeated!"
            self._add_combat_message(death_message)
            result_message += "\n" + death_message
            self.exit_combat(target)

            if world:
                world.dispatch_event("npc_killed", {"player": self, "npc": target})

            # --- Handle Gold and XP ---
            gold_dropped = 0
            if hasattr(target, 'loot_table'):
                gold_data = target.loot_table.get("gold_value")
                if gold_data and isinstance(gold_data, dict):
                    if random.random() < gold_data.get("chance", 0.0):
                        qty_range = gold_data.get("quantity", [1, 1])
                        gold_dropped = random.randint(qty_range[0], qty_range[1])
                        if gold_dropped > 0:
                            self.gold += gold_dropped
                            gold_message = f"{FORMAT_SUCCESS}You find {gold_dropped} gold.{FORMAT_RESET}"
                            self._add_combat_message(gold_message)
                            result_message += "\n" + gold_message
            
            final_xp_gained = calculate_xp_gain(self.level, target_level, getattr(target, 'max_health', 10))
            if final_xp_gained > 0:
                xp_message = f"{FORMAT_SUCCESS}You gain {final_xp_gained} experience!{FORMAT_RESET}"
                self._add_combat_message(xp_message)
                result_message += "\n" + xp_message
                leveled_up, level_up_msg = self.gain_experience(final_xp_gained)
                if leveled_up and level_up_msg:
                    self._add_combat_message(level_up_msg)
                    result_message += "\n" + level_up_msg
            
            loot_str = format_loot_drop_message(self, target, target.die(world) if hasattr(target, 'die') else [])
            if loot_str:
                self._add_combat_message(loot_str)
                result_message += "\n" + loot_str

        self.last_attack_time = time.time()
        return {"message": result_message}

    def cast_spell(self, spell: Spell, target, current_time: float, world: Optional['World'] = None) -> Dict[str, Any]:
        can_cast, reason = self.can_cast_spell(spell, current_time)
        if not can_cast: return {"success": False, "message": reason, "mana_cost": 0}
        self.mana -= spell.mana_cost
        self.spell_cooldowns[spell.spell_id] = current_time + spell.cooldown
        if spell.target_type == "enemy" and target != self:
             self.enter_combat(target)
        
        value, effect_message = apply_spell_effect(self, target, spell, self)
        full_message = f"{spell.format_cast_message(self)}\n{effect_message}"
        if spell.target_type == "enemy" or target != self: self._add_combat_message(effect_message)
        
        result = {"success": True, "message": full_message, "value": value}
        if not target.is_alive and spell.effect_type == "damage":
            death_message = f"{format_name_for_display(self, target, True)} has been defeated!"
            self._add_combat_message(death_message)
            result["message"] += "\n" + death_message
            self.exit_combat(target)
            
            if world:
                world.dispatch_event("npc_killed", {"player": self, "npc": target})

            # --- Handle Gold and XP ---
            gold_dropped = 0
            if hasattr(target, 'loot_table'):
                gold_data = target.loot_table.get("gold_value")
                if gold_data and isinstance(gold_data, dict):
                    if random.random() < gold_data.get("chance", 0.0):
                        qty_range = gold_data.get("quantity", [1, 1])
                        gold_dropped = random.randint(qty_range[0], qty_range[1])
                        if gold_dropped > 0:
                            self.gold += gold_dropped
                            gold_message = f"{FORMAT_SUCCESS}You find {gold_dropped} gold.{FORMAT_RESET}"
                            self._add_combat_message(gold_message)
                            result["message"] += "\n" + gold_message
            
            final_xp_gained = calculate_xp_gain(self.level, getattr(target, 'level', 1), getattr(target, 'max_health', 10))
            if final_xp_gained > 0:
                xp_message = f"{FORMAT_SUCCESS}You gain {final_xp_gained} experience!{FORMAT_RESET}"
                self._add_combat_message(xp_message)
                result["message"] += "\n" + xp_message
                leveled_up, level_up_msg = self.gain_experience(final_xp_gained)
                if leveled_up and level_up_msg:
                    self._add_combat_message(level_up_msg)
                    result["message"] += "\n" + level_up_msg

            loot_str = format_loot_drop_message(self, target, target.die(world) if hasattr(target, 'die') else [])
            if loot_str:
                self._add_combat_message(loot_str)
                result["message"] += "\n" + loot_str
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
        if effect_data and isinstance(effect_data, dict):
            self.apply_effect(effect_data, time.time())

        return True, f"{unequip_message}You equip the {item.name} in your {target_slot.replace('_', ' ')}."

    def unequip_item(self, slot_name: str) -> Tuple[bool, str]:
        if not self.is_alive: return False, "You cannot unequip items while dead."
        if slot_name not in self.equipment: return False, f"Invalid equipment slot: {slot_name}"
        item_to_unequip = self.equipment.get(slot_name)
        if not item_to_unequip: return False, f"You have nothing equipped in your {slot_name.replace('_', ' ')}."
        
        effect_data = item_to_unequip.get_property("equip_effect")
        if effect_data and isinstance(effect_data, dict):
            effect_name = effect_data.get("name")
            if effect_name:
                self.remove_effect(effect_name)

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

    def to_dict(self, world: 'World') -> Dict[str, Any]:
        """Converts the player object to a dictionary for saving."""
        data = super().to_dict()
        data.update({
            "gold": self.gold, "health": self.health, "max_health": self.max_health,
            "mana": self.mana, "max_mana": self.max_mana, "stats": self.stats,
            "level": self.level, "experience": self.experience, "experience_to_level": self.experience_to_level,
            "skills": self.skills, "effects": self.active_effects, 
            "quest_log": self.quest_log,
            # --- START OF MODIFICATION ---
            "completed_quest_log": self.completed_quest_log,
            "archived_quest_log": self.archived_quest_log,
            # --- END OF MODIFICATION ---
            "is_alive": self.is_alive,
            "current_location": {"region_id": self.current_region_id, "room_id": self.current_room_id},
            "respawn_region_id": self.respawn_region_id, "respawn_room_id": self.respawn_room_id,
            "known_spells": list(self.known_spells), "spell_cooldowns": self.spell_cooldowns,
            "inventory": self.inventory.to_dict(world),
            "equipment": {slot: _serialize_item_reference(item, 1, world) for slot, item in self.equipment.items() if item},
        })
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], world: 'World') -> Optional['Player']:
        """Creates a Player instance from a dictionary."""
        from items.item_factory import ItemFactory
        player = cls(name=data.get("name", PLAYER_DEFAULT_NAME))
        
        player.obj_id = data.get("id", "player")
        player.gold = data.get("gold", 0)
        player.level = data.get("level", 1)
        player.experience = data.get("experience", 0)
        player.experience_to_level = data.get("experience_to_level", PLAYER_BASE_XP_TO_LEVEL)
        player.is_alive = data.get("is_alive", True)
        
        player.stats = PLAYER_DEFAULT_STATS.copy(); player.stats.update(data.get("stats", {}))
        player.skills = data.get("skills", {})
        player.quest_log = data.get("quest_log", {})
        # --- START OF MODIFICATION ---
        player.completed_quest_log = data.get("completed_quest_log", {})
        player.archived_quest_log = data.get("archived_quest_log", {})
        # --- END OF MODIFICATION ---
        player.active_effects = data.get("effects", [])
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
        
        player.equipment = {slot: None for slot in EQUIPMENT_SLOTS}
        equipment_data = data.get("equipment", {})
        for slot, item_ref in equipment_data.items():
            if slot in player.equipment and item_ref and "item_id" in item_ref:
                item = ItemFactory.create_item_from_template(item_ref["item_id"], world, **item_ref.get("properties_override", {}))
                if item: player.equipment[slot] = item
        
        player.world = world
        return player