# player.py
# --- Standard Imports ---
from typing import List, Dict, Optional, Any, Tuple, Set
import time
import random

# --- Imports for Classes Used Directly ---
from core.config import (
    DEFAULT_INVENTORY_MAX_SLOTS, DEFAULT_INVENTORY_MAX_WEIGHT, EFFECT_DEFAULT_TICK_INTERVAL, EQUIPMENT_SLOTS, EQUIPMENT_VALID_SLOTS_BY_TYPE, FORMAT_BLUE, FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_GREEN, FORMAT_HIGHLIGHT,
    FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, FORMAT_YELLOW, HIT_CHANCE_AGILITY_FACTOR, ITEM_DURABILITY_LOSS_ON_HIT, ITEM_DURABILITY_LOW_THRESHOLD, LEVEL_DIFF_COMBAT_MODIFIERS, MIN_ATTACK_COOLDOWN,
    MIN_HIT_CHANCE, MAX_HIT_CHANCE, MIN_XP_GAIN, MINIMUM_DAMAGE_TAKEN, PLAYER_ATTACK_DAMAGE_VARIATION_RANGE, PLAYER_ATTACK_POWER_STR_DIVISOR, PLAYER_BASE_ATTACK_COOLDOWN, PLAYER_BASE_ATTACK_POWER, PLAYER_BASE_DEFENSE,
    PLAYER_BASE_HEALTH, PLAYER_BASE_HEALTH_REGEN_RATE, PLAYER_BASE_HIT_CHANCE, PLAYER_BASE_MANA_REGEN_RATE, PLAYER_BASE_XP_TO_LEVEL, PLAYER_CON_HEALTH_MULTIPLIER, PLAYER_DEFAULT_KNOWN_SPELLS, PLAYER_DEFAULT_MAX_MANA, PLAYER_DEFAULT_MAX_TOTAL_SUMMONS, PLAYER_DEFAULT_NAME, PLAYER_DEFAULT_RESPAWN_REGION, PLAYER_DEFAULT_RESPAWN_ROOM, PLAYER_DEFAULT_STATS, PLAYER_DEFENSE_DEX_DIVISOR, PLAYER_HEALTH_REGEN_STRENGTH_DIVISOR,
    PLAYER_LEVEL_HEALTH_BASE_INCREASE, PLAYER_LEVEL_CON_HEALTH_MULTIPLIER, PLAYER_LEVEL_UP_STAT_INCREASE, PLAYER_MANA_LEVEL_UP_INT_DIVISOR, PLAYER_MANA_LEVEL_UP_MULTIPLIER, PLAYER_MANA_REGEN_WISDOM_DIVISOR, PLAYER_MAX_COMBAT_MESSAGES, PLAYER_REGEN_TICK_INTERVAL, PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD, PLAYER_STATUS_HEALTH_LOW_THRESHOLD, PLAYER_XP_TO_LEVEL_MULTIPLIER, SPELL_XP_GAIN_HEALTH_DIVISOR, SPELL_XP_GAIN_LEVEL_MULTIPLIER, XP_GAIN_HEALTH_DIVISOR, XP_GAIN_LEVEL_MULTIPLIER
)

from game_object import GameObject
from items.inventory import Inventory
from items.weapon import Weapon
from items.consumable import Consumable
from items.item import Item
from magic.spell import Spell
from magic.spell_registry import get_spell
from magic.effects import apply_spell_effect
from utils.utils import _serialize_item_reference, calculate_xp_gain, format_loot_drop_message, format_name_for_display, get_article, simple_plural # If defined in utils/utils.py
from utils.text_formatter import format_target_name, get_level_diff_category # Import category calculation

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from world.world import World # Only import for type checkers
    from items.item_factory import ItemFactory # For loading

class Player(GameObject):
    def __init__(self, name: str, obj_id: str = "player"):
        super().__init__(obj_id=obj_id, name=name, description="The main character.")
        self.name = name
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
        self.skills = {} # Example: {"swordsmanship": 1}
        self.quest_log = {} # Example: {"missing_supplies": "started"}
        self.equipment: Dict[str, Optional[Item]] = {slot: None for slot in EQUIPMENT_SLOTS} # Use config slots
        self.valid_slots_for_type = EQUIPMENT_VALID_SLOTS_BY_TYPE.copy() # Use copy
        self.attack_power = PLAYER_BASE_ATTACK_POWER # Base physical attack power before stats/weapon
        self.defense = PLAYER_BASE_DEFENSE # Base physical defense before stats/armor
        self.is_alive = True
        self.faction = "player"
        self.in_combat = False
        self.combat_target = None # Primarily used by NPCs, maybe player focuses one?
        self.attack_cooldown = PLAYER_BASE_ATTACK_COOLDOWN # Base cooldown in seconds
        self.last_attack_time = 0
        self.combat_targets = set() # All entities player is currently in combat with
        self.combat_messages = []
        self.max_combat_messages = PLAYER_MAX_COMBAT_MESSAGES
        self.follow_target: Optional[str] = None
        self.respawn_region_id: Optional[str] = PLAYER_DEFAULT_RESPAWN_REGION
        self.respawn_room_id: Optional[str] = PLAYER_DEFAULT_RESPAWN_ROOM
        self.known_spells: Set[str] = set(PLAYER_DEFAULT_KNOWN_SPELLS)
        self.spell_cooldowns: Dict[str, float] = {}
        self.world: Optional['World'] = None
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.gold: int = 0

        # --- ADD Summon Tracking ---
        self.active_summons: Dict[str, List[str]] = {} # spell_id -> list[instance_id]
        self.max_total_summons: int = PLAYER_DEFAULT_MAX_TOTAL_SUMMONS
        # --- END Summon Tracking ---

        self.trading_with: Optional[str] = None

    def update(self, current_time: float):
        """Update player state like mana and health regeneration."""
        if not self.is_alive: return

        # --- Regeneration ---
        time_since_last_update = current_time - self.last_mana_regen_time # Use one timer for both

        if time_since_last_update >= PLAYER_REGEN_TICK_INTERVAL:
            base_mana_regen = self.mana_regen_rate * (1 + self.stats.get('wisdom', 10) / PLAYER_MANA_REGEN_WISDOM_DIVISOR)
            base_health_regen = PLAYER_BASE_HEALTH_REGEN_RATE * (1 + self.stats.get('strength', 10) / PLAYER_HEALTH_REGEN_STRENGTH_DIVISOR)

            # Calculate boost from gear
            regen_boost = 0
            for item in self.equipment.values():
                 if item:
                      regen_boost += item.get_property("regen_boost", 0)

            # Apply boost and time factor
            mana_regen_amount = int(time_since_last_update * (base_mana_regen + regen_boost))
            health_regen_amount = int(time_since_last_update * (base_health_regen + regen_boost))

            # Apply regeneration (clamped)
            self.mana = min(self.max_mana, self.mana + mana_regen_amount)
            self.health = min(self.max_health, self.health + health_regen_amount) # Regen health too

            self.last_mana_regen_time = current_time # Reset timer
            # --- End Regeneration ---

        # --- Process Active Effects ---
        effects_processed_this_tick = [] # Track IDs processed
        expired_effects_indices = []
        tick_messages = []

        # Iterate backwards to allow safe removal by index
        for i in range(len(self.active_effects) - 1, -1, -1):
            effect = self.active_effects[i]
            effect_id = effect.get("id")
            if not effect_id or effect_id in effects_processed_this_tick: continue # Skip if no ID or already processed

            effects_processed_this_tick.append(effect_id)

            # 1. Update Duration (Using suggested accurate method)
            last_processed = effect.get("last_processed_time", current_time)
            actual_delta = current_time - last_processed
            effect["duration_remaining"] -= actual_delta
            effect["last_processed_time"] = current_time

            # 2. Check Expiration
            if effect["duration_remaining"] <= 0:
                expired_effects_indices.append(i)
                # Add expiration message to the list to be returned
                tick_messages.append(f"{FORMAT_HIGHLIGHT}The {effect.get('name', 'effect')} on you wears off.{FORMAT_RESET}")
                continue # Move to next effect if expired

            # 3. Process Ticks (for DoTs)
            if effect.get("type") == "dot":
                tick_interval = effect.get("tick_interval", EFFECT_DEFAULT_TICK_INTERVAL)
                last_tick = effect.get("last_tick_time", 0)

                if current_time - last_tick >= tick_interval:
                    damage = effect.get("damage_per_tick", 0)
                    dmg_type = effect.get("damage_type", "unknown")
                    if damage > 0:
                        damage_taken = self.take_damage(damage, dmg_type)
                        effect["last_tick_time"] = current_time

                        # Add DoT damage message to the list to be returned
                        if damage_taken > 0:
                             tick_messages.append(f"{FORMAT_ERROR}You take {damage_taken} {dmg_type} damage from {effect.get('name', 'effect')}!{FORMAT_RESET}")
                        else:
                             tick_messages.append(f"You resist the {dmg_type} damage from {effect.get('name', 'effect')}.")

                        # Check for death RIGHT AFTER taking DoT damage
                        if not self.is_alive:
                            # Add death message if DoT killed player
                            tick_messages.append(f"{FORMAT_ERROR}You succumb to the {effect.get('name', 'effect')}!{FORMAT_RESET}")
                            break # Exit the effect processing loop

            # 4. Process Buffs/Debuffs (placeholder)
            # if effect.get("type") in ["buff", "debuff"]:
                # Apply continuous effects or reapply periodic ones if needed

        # Remove expired effects safely (after iteration)
        # Sort indices descending to avoid messing up subsequent indices during removal
        for index in sorted(expired_effects_indices, reverse=True):
             if 0 <= index < len(self.active_effects): # Bounds check
                  del self.active_effects[index]

        return tick_messages

    def get_status(self) -> str:
        """Returns a formatted string representing the player's current status."""


        # --- Health and Mana Formatting ---
        health_percent = (self.health / self.max_health) * 100 if self.max_health > 0 else 0
        health_text = f"{self.health}/{self.max_health}"
        if health_percent <= (PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD * 100):
            health_display = f"{FORMAT_ERROR}{health_text}{FORMAT_RESET}"
        elif health_percent <= (PLAYER_STATUS_HEALTH_LOW_THRESHOLD * 100):
            health_display = f"{FORMAT_HIGHLIGHT}{health_text}{FORMAT_RESET}"
        else:
            health_display = f"{FORMAT_SUCCESS}{health_text}{FORMAT_RESET}"
            
        mana_percent = (self.mana / self.max_mana) * 100 if self.max_mana > 0 else 0
        mana_text = f"{self.mana}/{self.max_mana}"
        # Using a blueish color for mana
        mana_display = f"{FORMAT_BLUE}{mana_text}{FORMAT_RESET}"
        # --- End Health/Mana Formatting ---

        # --- Basic Info ---
        status = f"{FORMAT_CATEGORY}Name:{FORMAT_RESET} {self.name}\n"
        status += f"{FORMAT_CATEGORY}Level:{FORMAT_RESET} {self.level} ({FORMAT_CATEGORY}XP:{FORMAT_RESET} {self.experience}/{self.experience_to_level})\n"
        status += f"{FORMAT_CATEGORY}Health:{FORMAT_RESET} {health_display}  "
        status += f"{FORMAT_CATEGORY}Mana:{FORMAT_RESET} {mana_display}\n"
        # --- End Basic Info ---

        # --- Stats - ADD CON & AGI ---
        status += f"{FORMAT_CATEGORY}Stats:{FORMAT_RESET} "
        stat_parts = []
        # Define which stats to show - ADDED CON, AGI
        stats_to_show = ["strength", "dexterity", "constitution", "agility", "intelligence", "wisdom", "spell_power", "magic_resist"]
        for stat_name in stats_to_show:
            stat_value = self.stats.get(stat_name, 0)
            # Abbreviate common stats
            abbr = stat_name[:3].upper() if stat_name in ["strength", "dexterity", "intelligence", "wisdom", "constitution", "agility"] else stat_name.upper() # Added CON, AGI to abbr
            stat_parts.append(f"{abbr} {stat_value}")
        status += ", ".join(stat_parts) + "\n"
        # --- End Stats ---

        status += f"{FORMAT_CATEGORY}Gold:{FORMAT_RESET} {self.gold}\n"

        # --- Combat Stats (with Effective Cooldown) ---
        effective_cd = self.get_effective_attack_cooldown()
        status += f"{FORMAT_CATEGORY}Attack:{FORMAT_RESET} {self.get_attack_power()} ({effective_cd:.1f}s CD), "
        status += f"{FORMAT_CATEGORY}Defense:{FORMAT_RESET} {self.get_defense()}\n"
        # --- End Combat Stats ---

        # --- Equipment ---
        equipped_items_found = False
        equip_lines = []
        # Iterate through standard slots in a defined order
        slot_order = ["main_hand", "off_hand", "head", "body", "hands", "feet", "neck"]
        for slot in slot_order:
            item = self.equipment.get(slot)
            if item:
                equipped_items_found = True
                slot_display = slot.replace('_', ' ').capitalize()
                # Add durability info if applicable
                durability_str = ""
                if "durability" in item.properties and "max_durability" in item.properties:
                     current_dura = item.get_property("durability")
                     max_dura = item.get_property("max_durability")
                     if max_dura > 0: # Avoid division by zero and irrelevant info
                          dura_percent = (current_dura / max_dura) * 100
                          if current_dura <= 0: dura_color = FORMAT_ERROR
                          elif dura_percent <= (ITEM_DURABILITY_LOW_THRESHOLD * 100): dura_color = FORMAT_YELLOW
                          else: dura_color = FORMAT_GREEN # Use green for good condition
                          durability_str = f" [{dura_color}{current_dura}/{max_dura}{FORMAT_RESET}]"

                equip_lines.append(f"  - {slot_display}: {item.name}{durability_str}")

        if equipped_items_found:
            status += f"\n{FORMAT_TITLE}EQUIPPED{FORMAT_RESET}\n"
            status += "\n".join(equip_lines) + "\n"
        # --- End Equipment ---

        # --- Effects --- # <<< MODIFY THIS SECTION
        if self.active_effects: # Check the actual list now
            status += f"\n{FORMAT_TITLE}EFFECTS{FORMAT_RESET}\n"
            effect_lines = []
            # Sort effects maybe? Alphabetically by name?
            sorted_effects = sorted(self.active_effects, key=lambda e: e.get("name", "zzz"))
            for effect in sorted_effects:
                name = effect.get('name', 'Unknown Effect')
                duration = effect.get('duration_remaining', 0)
                # Format duration nicely
                if duration > 60: # Show minutes if long
                    duration_str = f"{duration / 60:.1f}m"
                else:
                    duration_str = f"{duration:.1f}s"
                # Add details for DoTs
                details = ""
                if effect.get("type") == "dot":
                     dmg = effect.get("damage_per_tick", 0)
                     interval = effect.get("tick_interval", EFFECT_DEFAULT_TICK_INTERVAL)
                     dmg_type = effect.get("damage_type", "")
                     details = f" ({dmg} {dmg_type}/ {interval:.0f}s)" # e.g. (5 poison/3s)

                effect_lines.append(f"  - {name}{details} ({duration_str} remaining)")
            status += "\n".join(effect_lines) + "\n"
        # --- End Effects --- # <<< END MODIFICATION

        # --- Skills ---
        if self.skills:
            status += f"\n{FORMAT_TITLE}SKILLS{FORMAT_RESET}\n"
            skill_lines = []
            # Sort skills alphabetically
            for skill_name, level in sorted(self.skills.items()):
                skill_lines.append(f"  - {skill_name.capitalize()}: {level}")
            status += "\n".join(skill_lines) + "\n"
        # --- End Skills ---

        # --- Quests ---
        if self.quest_log:
            status += f"\n{FORMAT_TITLE}QUEST LOG{FORMAT_RESET}\n"
            quest_lines = []
             # Sort quests alphabetically by ID
            for quest_id, progress in sorted(self.quest_log.items()):
                # Simple display, replace underscores in ID for readability
                quest_display_name = quest_id.replace('_', ' ').title()
                # Truncate long progress strings
                progress_str = str(progress)
                if len(progress_str) > 30: progress_str = progress_str[:27] + "..."
                quest_lines.append(f"  - {quest_display_name}: {progress_str}")
            status += "\n".join(quest_lines) + "\n"
        # --- End Quests ---

        # --- Known Spells ---
        if self.known_spells:
             status += f"\n{FORMAT_TITLE}SPELLS KNOWN{FORMAT_RESET}\n"
             spell_list = []
             current_time_abs = time.time() # Use absolute time for cooldown check
             for spell_id in sorted(list(self.known_spells)):
                  spell = get_spell(spell_id)
                  if spell:
                       cooldown_end = self.spell_cooldowns.get(spell_id, 0)
                       cd_status = ""
                       if current_time_abs < cooldown_end:
                            time_left = cooldown_end - current_time_abs
                            cd_status = f" [{FORMAT_ERROR}CD {time_left:.1f}s{FORMAT_RESET}]"
                       spell_list.append(f"  - {spell.name} ({spell.mana_cost} MP){cd_status}")
             status += "\n".join(spell_list) + "\n"
        # --- End Known Spells ---

        # --- Combat Status ---
        if self.in_combat:
            status += "\n" + self.get_combat_status() # Use existing combat status method
        # --- End Combat Status ---

        # --- Death Message ---
        if not self.is_alive:
             status += f"\n{FORMAT_ERROR}** YOU ARE DEAD **{FORMAT_RESET}\n"
        # --- End Death Message ---

        return status.strip() # Remove potential trailing newline

    def gain_experience(self, amount: int) -> bool:
        self.experience += amount
        if self.experience >= self.experience_to_level:
            self.level_up()
            return True
        return False

    def level_up(self) -> None:
        # ... (previous level up logic) ...
        self.level += 1
        self.experience -= self.experience_to_level
        self.experience_to_level = int(self.experience_to_level * PLAYER_XP_TO_LEVEL_MULTIPLIER)
        self.stats["strength"] += PLAYER_LEVEL_UP_STAT_INCREASE
        self.stats["dexterity"] += PLAYER_LEVEL_UP_STAT_INCREASE
        self.stats["intelligence"] += PLAYER_LEVEL_UP_STAT_INCREASE
        self.stats["wisdom"] += PLAYER_LEVEL_UP_STAT_INCREASE
        self.stats["constitution"] += PLAYER_LEVEL_UP_STAT_INCREASE
        self.stats["agility"] += PLAYER_LEVEL_UP_STAT_INCREASE

        old_max_health = self.max_health
        health_increase = PLAYER_LEVEL_HEALTH_BASE_INCREASE + int(self.stats.get('constitution', 10) * PLAYER_LEVEL_CON_HEALTH_MULTIPLIER)
        self.max_health += health_increase
        self.health += (self.max_health - old_max_health) # Add the gained max health to current health

        old_max_mana = self.max_mana
        self.max_mana = int(self.max_mana * 1.15 + self.stats["intelligence"] / 2) # Increase based on level and INT
        self.mana += (self.max_mana - old_max_mana)

    def add_skill(self, skill_name: str, level: int = 1) -> None:
        if skill_name in self.skills: self.skills[skill_name] += level
        else: self.skills[skill_name] = level

    def get_skill_level(self, skill_name: str) -> int:
        return self.skills.get(skill_name, 0)

    def update_quest(self, quest_id: str, progress: Any) -> None:
        self.quest_log[quest_id] = progress

    def get_quest_progress(self, quest_id: str) -> Optional[Any]:
        return self.quest_log.get(quest_id)

    def heal(self, amount: int) -> int:
        if not self.is_alive: return 0 # Cannot heal if dead
        old_health = self.health
        self.health = min(self.health + amount, self.max_health)
        return self.health - old_health

    def take_damage(self, amount: int, damage_type: str = "physical") -> int:
        """Handles taking damage, applying defense, resistance, and debug immunity."""
        if not self.is_alive: return 0

        # --- Check for Debug Damage Immunity ---
        immunity_chance = 0.0
        for item in self.equipment.values():
            if item:
                # Get the highest immunity chance from any equipped item
                immunity_chance = max(immunity_chance, item.get_property("damage_immunity_chance", 0.0))

        if immunity_chance > 0 and random.random() < immunity_chance:
            # Maybe add a message to combat log? Optional.
            # self._add_combat_message(f"You effortlessly shrug off the incoming {damage_type} damage!")
            return 0 # Take zero damage
        # --- End Immunity Check ---

        # Calculate total defense/resistance for the type
        final_reduction = 0
        if damage_type == "physical":
            final_reduction = self.get_defense() # Uses existing method which sums armor defense
        elif damage_type == "magical":
            # Base magic resist stat
            final_reduction = self.stats.get("magic_resist", 0)
            # Add magic resist from equipped items
            for item in self.equipment.values():
                if item:
                    final_reduction += item.get_property("magic_resist", 0)
        # Add other damage types (e.g., "fire", "cold") if needed
        reduced_damage = max(0, amount - final_reduction)
        # Ensure minimum 1 damage IF damage got past immunity AND reduction wasn't total
        actual_damage = max(MINIMUM_DAMAGE_TAKEN, reduced_damage) if amount > 0 and reduced_damage > 0 else 0

        old_health = self.health
        self.health = max(0, self.health - actual_damage)

        if self.health <= 0:
            self.die()

        return old_health - self.health

    def die(self) -> None:
        if not self.is_alive: return
        self.health = 0
        self.is_alive = False
        self.in_combat = False
        self.combat_targets.clear()
        self.active_effects = []
        # *** Reset mana on death? Optional. ***
        # self.mana = 0
        print(f"{self.name} has died!")

        # --- Despawn Summons on Player Death ---
        if self.world:
            all_summon_ids = []
            for ids in self.active_summons.values():
                all_summon_ids.extend(ids)

            for instance_id in all_summon_ids:
                summon = self.world.get_npc(instance_id)
                if summon and hasattr(summon, 'despawn'):
                    summon.despawn(self.world, silent=True) # Despawn silently

        self.active_summons = {} # Clear the tracking dict
        # --- End Despawn ---

    def respawn(self) -> None:
        self.health = self.max_health
        # *** Restore mana on respawn ***
        self.mana = self.max_mana
        self.is_alive = True
        self.in_combat = False
        self.combat_targets.clear()
        self.spell_cooldowns.clear() # Reset cooldowns on respawn
        self.active_summons = {} # Clear summons on respawn too
        self.active_effects = []

    # Make sure method name matches usage
    def get_is_alive(self) -> bool:
        # Ensure health check reflects dead state correctly
        return self.is_alive and self.health > 0


    # Make sure get_attack_power and get_defense are present
    def get_attack_power(self) -> int:
        attack = self.attack_power + self.stats.get("strength", 0) // PLAYER_ATTACK_POWER_STR_DIVISOR
        weapon_bonus = 0
        main_hand_weapon = self.equipment.get("main_hand")
        if main_hand_weapon and isinstance(main_hand_weapon, Weapon):
            if main_hand_weapon.get_property("durability", 1) > 0:
                weapon_bonus = main_hand_weapon.get_property("damage", 0)
        attack += weapon_bonus
        # Add effects bonus if implemented
        return attack

    def get_defense(self) -> int:
        defense = self.defense + self.stats.get("dexterity", 10) // PLAYER_DEFENSE_DEX_DIVISOR
        armor_bonus = 0
        for item in self.equipment.values():
            if item:
                 item_defense = item.get_property("defense", 0)
                 # Check item durability if applicable
                 if item.get_property("durability", 1) > 0:
                    if item_defense > 0: armor_bonus += item_defense
        defense += armor_bonus
        # Add effects bonus if implemented
        return defense

    def enter_combat(self, target) -> None:
        if not self.is_alive: return # Cannot enter combat if dead
        self.in_combat = True
        self.combat_targets.add(target)
        if hasattr(target, "enter_combat"):
             is_target_already_targeting = False
             if hasattr(target, "combat_targets") and self in target.combat_targets:
                  is_target_already_targeting = True
             if not is_target_already_targeting:
                  target.enter_combat(self)

        # --- Notify Summons ---
        if self.world:
            for spell_id, instance_ids in self.active_summons.items():
                for instance_id in instance_ids:
                    summon = self.world.get_npc(instance_id)
                    if summon and summon.is_alive and hasattr(summon, 'enter_combat'):
                        # Tell summon to fight the same target
                        summon.enter_combat(target)
        # --- End Notify Summons ---

    def exit_combat(self, target=None) -> None:
        target_list_to_exit = []
        if target:
            if target in self.combat_targets:
                self.combat_targets.remove(target)
                target_list_to_exit.append(target)
        else:
            target_list_to_exit = list(self.combat_targets)
            self.combat_targets.clear()

        if not self.combat_targets: self.in_combat = False

        # --- Notify Summons ---
        if self.world:
            for spell_id, instance_ids in self.active_summons.items():
                for instance_id in instance_ids:
                    summon = self.world.get_npc(instance_id)
                    if summon and summon.is_alive and hasattr(summon, 'exit_combat'):
                        # Tell summon to stop fighting specific target(s) or all
                        if target:
                             summon.exit_combat(target)
                        else:
                             # If exiting all, check if summon should also exit all
                             # Only exit summon fully if player is fully out of combat
                             if not self.in_combat:
                                  summon.exit_combat() # Exit all for summon
        # --- End Notify Summons ---

        # Now notify the targets the player is no longer fighting them
        for t in target_list_to_exit:
             if hasattr(t, "exit_combat"):
                  t.exit_combat(self)

    def can_attack(self, current_time: float) -> bool:
        """Checks if the player can attack based on the effective cooldown."""
        effective_cooldown = self.get_effective_attack_cooldown()
        time_elapsed = current_time - self.last_attack_time
        # Use a small tolerance (epsilon) if needed, but usually >= is fine
        # epsilon = 0.001
        # return self.is_alive and time_elapsed >= (effective_cooldown - epsilon)
        return self.is_alive and time_elapsed >= effective_cooldown # Standard check is usually okay

    def get_combat_status(self) -> str:
        if not self.in_combat or not self.combat_targets: return "" # Return empty if not in combat for status integration

        status = f"{FORMAT_TITLE}COMBAT STATUS{FORMAT_RESET}\n"
        status += f"{FORMAT_CATEGORY}Fighting:{FORMAT_RESET}\n"
        valid_targets = [t for t in self.combat_targets if hasattr(t, 'is_alive') and t.is_alive]

        if not valid_targets:
            status += "  (No current targets)\n"
            # Maybe auto-exit combat here if no valid targets?
            # self.in_combat = False
        else:
            for target in valid_targets:
                formatted_name = format_name_for_display(self, target, start_of_sentence=True)
                if hasattr(target, "health") and hasattr(target, "max_health") and target.max_health > 0:
                    health_percent = (target.health / target.max_health) * 100
                    if health_percent <= 25: health_display = f"{FORMAT_ERROR}{target.health}/{target.max_health}{FORMAT_RESET}"
                    elif health_percent <= 50: health_display = f"{FORMAT_HIGHLIGHT}{target.health}/{target.max_health}{FORMAT_RESET}"
                    else: health_display = f"{FORMAT_SUCCESS}{target.health}/{target.max_health}{FORMAT_RESET}"
                    status += f"  - {formatted_name}: {health_display} HP\n"
                else:
                    status += f"  - {formatted_name}\n"

        if self.combat_messages:
            status += f"\n{FORMAT_CATEGORY}Recent Actions:{FORMAT_RESET}\n"
            for msg in self.combat_messages: status += f"  - {msg}\n" # Indent actions

        return status

    def _add_combat_message(self, message: str) -> None:
        # Strip leading/trailing whitespace and newlines before adding
        clean_message = message.strip()
        if not clean_message: return

        # Split potential multi-line messages passed in
        for line in clean_message.splitlines():
            self.combat_messages.append(line)
            while len(self.combat_messages) > self.max_combat_messages:
                self.combat_messages.pop(0)

    def attack(self, target, world: Optional['World'] = None) -> Dict[str, Any]:
        if not self.is_alive:
             return {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": 0, "missed": False, "message": "You cannot attack while dead."}

        equipped_weapon = self.equipment.get("main_hand")
        always_hits = False
        if equipped_weapon and equipped_weapon.get_property("always_hit"):
            always_hits = True

        target_level = getattr(target, 'level', 1)
        category = get_level_diff_category(self.level, target_level)

        final_hit_chance = 1.0 # Default to 1.0 if always_hits is true
        if not always_hits:
            base_hit_chance = PLAYER_BASE_HIT_CHANCE

            # Calculate hit chance modifier based on Agility difference
            # Increase hit chance by 2% for each point of AGI advantage
            # Decrease hit chance by 2% for each point of AGI disadvantage
            attacker_agi = self.stats.get("agility", 10)
            target_agi = getattr(target, "stats", {}).get("agility", 8)
            agi_modifier = (attacker_agi - target_agi) * HIT_CHANCE_AGILITY_FACTOR
            agi_modified_hit_chance = base_hit_chance + agi_modifier

            # Level difference modifier
            hit_chance_mod, _, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
            level_modified_hit_chance = agi_modified_hit_chance * hit_chance_mod

            # Clamp final hit chance
            final_hit_chance = max(MIN_HIT_CHANCE, min(level_modified_hit_chance, MAX_HIT_CHANCE))

        formatted_target_name = format_name_for_display(self, target, start_of_sentence=False)

        if not always_hits and random.random() > final_hit_chance:
            # --- Miss ---
            miss_message = f"You swing at {formatted_target_name} but miss!"
            self._add_combat_message(miss_message)
            self.last_attack_time = time.time()
            # Add hit chance info to result for debugging/clarity
            result = {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": 0, "missed": True, "message": miss_message, "hit_chance": final_hit_chance}
            return result

        # ... (HIT, Damage Calculation, Durability - unchanged) ...
        self.enter_combat(target)
        attack_power = self.get_attack_power()
        damage_variation = random.randint(PLAYER_ATTACK_DAMAGE_VARIATION_RANGE[0], PLAYER_ATTACK_DAMAGE_VARIATION_RANGE[1])
        base_attack_damage = max(1, attack_power + damage_variation)

        _, damage_dealt_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        modified_attack_damage = int(base_attack_damage * damage_dealt_mod)
        modified_attack_damage = max(MINIMUM_DAMAGE_TAKEN, modified_attack_damage)

        # actual_damage = 0
        # if hasattr(target, "take_damage"):
        actual_damage = target.take_damage(modified_attack_damage, damage_type="physical")
        # elif hasattr(target, "health"):
        #     old_health = target.health
        #     target.health = max(0, target.health - modified_attack_damage)
        #     actual_damage = old_health - target.health
        #     if target.health <= 0 and hasattr(target, 'is_alive'): target.is_alive = False

        weapon_name = "bare hands"
        weapon_broke = False
        equipped_weapon = self.equipment.get("main_hand")

        if equipped_weapon and isinstance(equipped_weapon, Weapon):
            weapon_name = equipped_weapon.name
            current_durability = equipped_weapon.get_property("durability", 0)
            if current_durability > 0:
                equipped_weapon.update_property("durability", current_durability - ITEM_DURABILITY_LOSS_ON_HIT)
                if current_durability - ITEM_DURABILITY_LOSS_ON_HIT <= 0:
                    weapon_broke = True

        hit_message = f"You attack {formatted_target_name} with your {weapon_name} for {int(actual_damage)} damage!"
        if weapon_broke: hit_message += f"\n{FORMAT_ERROR}Your {weapon_name} breaks!{FORMAT_RESET}"

        # --- NEW: Check for on-hit effects ---
        apply_effect_message = ""
        if equipped_weapon and hasattr(equipped_weapon, 'properties'):
            effect_chance = equipped_weapon.get_property("on_hit_effect_chance", 0.0)
            if effect_chance > 0 and random.random() < effect_chance:
                effect_data = equipped_weapon.get_property("on_hit_effect")
                if effect_data and isinstance(effect_data, dict):
                    if hasattr(target, 'apply_effect'):
                        # Pass current time to apply_effect
                        success, _ = target.apply_effect(effect_data, time.time())
                        if success:
                            # Create message viewable by the player (attacker is self)
                            eff_name = effect_data.get('name', 'an effect')
                            tgt_name_fmt = format_name_for_display(self, target, False) # Target formatted for player view
                            apply_effect_message = f"{FORMAT_HIGHLIGHT}Your {equipped_weapon.name} afflicts {tgt_name_fmt} with {eff_name}!{FORMAT_RESET}"
                            self._add_combat_message(apply_effect_message) # Log it

        result_message = hit_message
        if(apply_effect_message):
            result_message += "\n" + apply_effect_message
        
        result = {
            "attacker": self.name,
            "target": getattr(target, 'name', 'target'),
            "damage": actual_damage,
            "weapon": weapon_name,
            "missed": False,
            "message": result_message,
            "hit_chance": final_hit_chance
        }
        self._add_combat_message(result["message"])

        # --- Check Target Death & XP/Loot ---
        if hasattr(target, "health") and target.health <= 0:
            if hasattr(target, 'is_alive'): target.is_alive = False
            formatted_target_name_start = format_name_for_display(self, target, start_of_sentence=True)
            death_message = f"{formatted_target_name_start} has been defeated!"
            self._add_combat_message(death_message)
            self.exit_combat(target)
            result["target_defeated"] = True
            result["message"] += "\n" + death_message # Append death message

            # --- Calculate XP using utility function ---
            target_max_hp = getattr(target, 'max_health', 10)
            final_xp_gained = calculate_xp_gain(self.level, target_level, target_max_hp)
            # --- End XP Calculation ---

            leveled_up = self.gain_experience(final_xp_gained)
            exp_message = f"You gained {final_xp_gained} experience points!"
            self._add_combat_message(exp_message)
            result["message"] += "\n" + exp_message # Append XP message

            if leveled_up:
                level_up_msg = f"You leveled up to level {self.level}!"
                self._add_combat_message(level_up_msg)
                result["message"] += "\n" + level_up_msg # Append level up message

            # --- Gold Award Logic (unchanged) ---
            gold_awarded = 0
            if hasattr(target, "loot_table"):
                 gold_loot_data = target.loot_table.get("gold_value")
                 if isinstance(gold_loot_data, dict) and "chance" in gold_loot_data:
                      if random.random() < gold_loot_data["chance"]:
                           # ... (gold calculation logic - unchanged) ...
                           if gold_awarded > 0:
                                self.gold += gold_awarded
                                gold_message = f"You receive {gold_awarded} gold from the remains of {formatted_target_name}."
                                self._add_combat_message(gold_message)
                                result["message"] += "\n" + gold_message
                                result["gold_awarded"] = gold_awarded

            # --- Loot Dropping and Message Formatting ---
            dropped_loot_items = []
            if hasattr(target, "die"):
                dropped_loot_items = target.die(world) # Call die to drop items

            # Use utility function to format loot message
            loot_str = format_loot_drop_message(self, target, dropped_loot_items)
            if loot_str:
                self._add_combat_message(loot_str) # Log loot message
                result["message"] += "\n" + loot_str # Append loot message
            # --- End Loot Handling ---

        self.last_attack_time = time.time()
        return result # Return the final result dictionary

    # ... (get_valid_slots, equip_item, unequip_item - unchanged) ...
    def get_valid_slots(self, item: Item) -> List[str]:
        valid = []
        item_type_name = item.__class__.__name__
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
        if item.get_property("defense", 0) > 0:
             if "body" in self.equipment: valid.append("body")
             if "head" in self.equipment: valid.append("head")
        return valid

    def equip_item(self, item: Item, slot_name: Optional[str] = None) -> Tuple[bool, str]:
        if not self.is_alive: return False, "You cannot equip items while dead." # NEW check
        valid_slots = self.get_valid_slots(item)
        if not valid_slots:
            return False, f"You can't figure out how to equip the {item.name}."

        target_slot = None
        if slot_name:
            if slot_name in valid_slots: target_slot = slot_name
            else: return False, f"The {item.name} cannot be equipped in the '{slot_name}' slot. Valid: {', '.join(valid_slots)}"
        else:
            for s in valid_slots:
                if self.equipment[s] is None: target_slot = s; break
            if target_slot is None: target_slot = valid_slots[0]

        found_in_inv = self.inventory.get_item(item.obj_id)
        if not found_in_inv: return False, f"You don't have the {item.name} in your inventory."

        unequip_message = ""
        currently_equipped = self.equipment.get(target_slot)
        if currently_equipped:
            success, msg = self.unequip_item(target_slot)
            if not success: return False, f"Could not unequip {currently_equipped.name} to make space: {msg}"
            unequip_message = f"(You unequip the {currently_equipped.name}) "

        removed_item, quantity_removed, remove_msg = self.inventory.remove_item(item.obj_id, 1)
        if not removed_item: return False, f"Failed to remove {item.name} from inventory: {remove_msg}"

        self.equipment[target_slot] = item
        return True, f"{unequip_message}You equip the {item.name} in your {target_slot.replace('_', ' ')}."

    def unequip_item(self, slot_name: str) -> Tuple[bool, str]:
        if not self.is_alive: return False, "You cannot unequip items while dead." # NEW check
        if slot_name not in self.equipment: return False, f"Invalid equipment slot: {slot_name}"

        item_to_unequip = self.equipment.get(slot_name)
        if not item_to_unequip: return False, f"You have nothing equipped in your {slot_name.replace('_', ' ')}."

        success, add_message = self.inventory.add_item(item_to_unequip, 1)
        if not success: return False, f"Could not unequip {item_to_unequip.name}: {add_message}"

        self.equipment[slot_name] = None
        return True, f"You unequip the {item_to_unequip.name} from your {slot_name.replace('_', ' ')}."

    def learn_spell(self, spell_id: str) -> Tuple[bool, str]:
        """
        Adds a spell ID to the player's known spells if possible.

        Returns:
            Tuple[bool, str]: (success_status, message)
        """
        spell = get_spell(spell_id)
        if not spell:
            # Spell definition doesn't exist in the registry
            return False, f"The secrets of '{spell_id}' seem non-existent."

        if spell_id in self.known_spells:
            # Already knows the spell
            return False, f"You already know how to cast {spell.name}."

        if self.level < spell.level_required:
            # Level requirement not met
            return False, f"You feel you lack the experience to grasp {spell.name} (requires level {spell.level_required})."

        # All checks passed, learn the spell
        self.known_spells.add(spell_id)
        # Maybe add a small XP reward for learning? Optional.
        # self.gain_experience(5)
        return True, f"You study the technique and successfully learn {spell.name}!"

    def forget_spell(self, spell_id: str) -> bool:
        """Removes a spell ID from the player's known spells."""
        if spell_id in self.known_spells:
            self.known_spells.remove(spell_id)
            # Remove from cooldowns too if present
            if spell_id in self.spell_cooldowns:
                 del self.spell_cooldowns[spell_id]
            return True
        return False

    def can_cast_spell(self, spell: Spell, current_time: float) -> Tuple[bool, str]:
        """Checks if the player can cast a given spell."""
        if not self.is_alive:
            return False, "You cannot cast spells while dead."
        if spell.spell_id not in self.known_spells:
            return False, "You don't know that spell."
        if self.level < spell.level_required:
            return False, f"You need to be level {spell.level_required} to cast {spell.name}."
        if self.mana < spell.mana_cost:
            return False, f"Not enough mana (need {spell.mana_cost}, have {self.mana})."
        cooldown_end_time = self.spell_cooldowns.get(spell.spell_id, 0)
        if current_time < cooldown_end_time:
            time_left = cooldown_end_time - current_time
            return False, f"{spell.name} is on cooldown for {time_left:.1f}s."
        return True, ""

    def cast_spell(self, spell: Spell, target, current_time: float, world: Optional['World'] = None) -> Dict[str, Any]:
        """Attempts to cast a spell on a target."""
        can_cast, reason = self.can_cast_spell(spell, current_time)
        if not can_cast:
            return {"success": False, "message": reason, "mana_cost": 0}

        # Deduct mana
        self.mana -= spell.mana_cost

        # Set cooldown
        self.spell_cooldowns[spell.spell_id] = current_time + spell.cooldown

        # Trigger combat if targeting an enemy
        if spell.target_type == "enemy" and target != self:
             self.enter_combat(target)
             if hasattr(target, 'enter_combat'):
                  target.enter_combat(self)

        # Apply effect
        value, effect_message = apply_spell_effect(self, target, spell, self) # Pass self as viewer

        cast_message = spell.format_cast_message(self)
        full_message = cast_message + "\n" + effect_message
        if spell.target_type == "enemy" or target != self:
            self._add_combat_message(effect_message)

        result = {
            "success": True,
            "message": full_message,
            "cast_message": cast_message,
            "effect_message": effect_message,
            "mana_cost": spell.mana_cost,
            "target": getattr(target, 'name', 'target'),
            "value": value,
            "spell": spell.name
        }

        # --- Check target death & XP/Loot (similar updates as attack method) ---
        if spell.effect_type == "damage" and hasattr(target, "health") and target.health <= 0:
            formatted_target_name_start = format_name_for_display(self, target, start_of_sentence=True)

            if hasattr(target, 'is_alive'): target.is_alive = False
            death_message = f"{formatted_target_name_start} has been defeated by {spell.name}!"
            self._add_combat_message(death_message)
            self.exit_combat(target)
            result["target_defeated"] = True
            result["message"] += "\n" + death_message # Append death message

            # --- Calculate XP using utility function ---
            target_level = getattr(target, 'level', 1)
            target_max_hp = getattr(target, 'max_health', 10)
            # Use spell-specific constants? Or stick to standard? Let's use standard for now via the function.
            final_xp_gained = calculate_xp_gain(self.level, target_level, target_max_hp)
            # --- End XP Calculation ---

            leveled_up = self.gain_experience(final_xp_gained)
            exp_message = f"You gained {final_xp_gained} experience points!"
            self._add_combat_message(exp_message)
            result["message"] += "\n" + exp_message # Append XP message
            if leveled_up:
                level_up_msg = f"You leveled up to level {self.level}!"
                self._add_combat_message(level_up_msg)
                result["message"] += "\n" + level_up_msg # Append level up message

            # --- Gold Award Logic (unchanged) ---
            gold_awarded = 0
            if hasattr(target, "loot_table"):
                 gold_loot_data = target.loot_table.get("gold_value")
                 if isinstance(gold_loot_data, dict) and "chance" in gold_loot_data:
                     # ... (gold calculation logic - unchanged) ...
                     if gold_awarded > 0:
                          self.gold += gold_awarded
                          # Use non-start-of-sentence format for target here
                          formatted_target_name_mid = format_name_for_display(self, target, start_of_sentence=False)
                          gold_message = f"You receive {gold_awarded} gold from the remains of {formatted_target_name_mid}."
                          self._add_combat_message(gold_message)
                          result["message"] += "\n" + gold_message
                          result["gold_awarded"] = gold_awarded

            # --- Loot Dropping and Message Formatting ---
            dropped_loot_items = []
            if hasattr(target, "die"):
                dropped_loot_items = target.die(world) # Call die to drop items

            # Use utility function to format loot message
            loot_str = format_loot_drop_message(self, target, dropped_loot_items)
            if loot_str:
                self._add_combat_message(loot_str) # Log loot message
                result["message"] += "\n" + loot_str # Append loot message
            # --- End Loot Handling ---

        return result # Return the final result dictionary

    def to_dict(self, world: 'World') -> Dict[str, Any]: # Needs world context
        """Serialize player state for saving."""
        data = super().to_dict()

        # Serialize equipment by reference
        equipped_items_data = {}
        for slot, item in self.equipment.items():
            if item:
                 # Use helper to serialize reference (quantity is 1 for equipped)
                 item_ref = _serialize_item_reference(item, 1, world)
                 equipped_items_data[slot] = item_ref
            else:
                 equipped_items_data[slot] = None

        # Serialize inventory using its own to_dict (which now needs world)
        inventory_data = self.inventory.to_dict(world)

        # --- Store current location explicitly ---
        current_location = {
            "region_id": getattr(self, 'current_region_id', self.respawn_region_id), # Use current or fallback
            "room_id": getattr(self, 'current_room_id', self.respawn_room_id)
        }

        # Add player-specific fields to the data dictionary from super()
        data.update({
            # "name": self.name, # Already handled by super().to_dict()
            # "obj_id": self.obj_id, # Already handled by super().to_dict()
            # "description": self.description, # Already handled by super().to_dict()
            "gold": self.gold,
            "health": self.health, "max_health": self.max_health,
            "mana": self.mana, "max_mana": self.max_mana,
            "stats": self.stats,
            "level": self.level, "experience": self.experience, "experience_to_level": self.experience_to_level,
            "skills": self.skills,
            "quest_log": self.quest_log,
            "is_alive": self.is_alive,
            "current_location": current_location,
            "respawn_region_id": self.respawn_region_id,
            "respawn_room_id": self.respawn_room_id,
            "known_spells": list(self.known_spells),
            "spell_cooldowns": self.spell_cooldowns,
            "inventory": inventory_data,
            "equipment": equipped_items_data,
            # properties dict from GameObject is already included by super().to_dict()
        })
        
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any], world: Optional['World']) -> 'Player':
        if not world:
             print(f"{FORMAT_ERROR}Error: World context required to load player.{FORMAT_RESET}")
             player = cls(PLAYER_DEFAULT_NAME) # Create with default name
             player.current_region_id = PLAYER_DEFAULT_RESPAWN_REGION
             player.current_room_id = PLAYER_DEFAULT_RESPAWN_ROOM
             return player

        # --- Create Player instance using name and obj_id ---
        # Get obj_id from data, default to "player" if missing
        player_obj_id = data.get("obj_id", data.get("id", "player"))
        player = cls(name=data["name"], obj_id=player_obj_id) # Pass obj_id to constructor
        # --- End instance creation ---

        # Load GameObject properties (like description, base properties dict)
        player.description = data.get("description", "The main character.")
        player.properties = data.get("properties", {}) # Load base properties

        # Load Player-specific attributes
        player.gold = data.get("gold", 0)
        player.trading_with = None

        # --- Stats loading (use PLAYER_DEFAULT_STATS) ---
        player.stats = PLAYER_DEFAULT_STATS.copy() # Start with defaults
        player.stats.update(data.get("stats", {})) # Update with saved values
        # --- End Stats Loading ---

        # ... (rest of loading: level, health/mana calculation, xp, skills, etc.) ...
        # Ensure max health/mana calculations use the loaded stats
        player.level = data.get("level", 1)
        player.max_health = PLAYER_BASE_HEALTH + int(player.stats.get('constitution', 10) * PLAYER_CON_HEALTH_MULTIPLIER) # Recalculate based on final stats
        player.health = data.get("health", player.max_health)
        player.health = min(player.health, player.max_health) # Clamp

        player.max_mana = int(PLAYER_DEFAULT_MAX_MANA * (PLAYER_MANA_LEVEL_UP_MULTIPLIER**(player.level-1)) + player.stats.get("intelligence", 10) / PLAYER_MANA_LEVEL_UP_INT_DIVISOR * (player.level-1)) # Recalculate Max Mana based on level/int
        player.mana = data.get("mana", player.max_mana)
        player.mana = min(player.mana, player.max_mana) # Clamp

        # ... (load xp, skills, effects, quest_log, is_alive, known_spells, cooldowns, respawn loc) ...
        player.experience = data.get("experience", 0)
        player.experience_to_level = data.get("experience_to_level", PLAYER_BASE_XP_TO_LEVEL)
        player.skills = data.get("skills", {})
        player.quest_log = data.get("quest_log", {})
        player.is_alive = data.get("is_alive", True)
        player.known_spells = set(data.get("known_spells", PLAYER_DEFAULT_KNOWN_SPELLS))
        player.spell_cooldowns = data.get("spell_cooldowns", {})
        player.respawn_region_id = data.get("respawn_region_id", PLAYER_DEFAULT_RESPAWN_REGION)
        player.respawn_room_id = data.get("respawn_room_id", PLAYER_DEFAULT_RESPAWN_ROOM)


        # Load Location
        loc = data.get("current_location", {})
        player.current_region_id = loc.get("region_id", player.respawn_region_id)
        player.current_room_id = loc.get("room_id", player.respawn_room_id)

        # Reset transient state
        player.last_mana_regen_time = time.time()
        player.in_combat = False
        player.combat_targets.clear()
        player.combat_messages = []
        player.last_attack_time = 0
        player.active_summons = {} # Ensure initialized

        # Load inventory (no change needed here)
        if "inventory" in data:
            player.inventory = Inventory.from_dict(data["inventory"], world)
        else:
            player.inventory = Inventory(max_slots=DEFAULT_INVENTORY_MAX_SLOTS, max_weight=DEFAULT_INVENTORY_MAX_WEIGHT)

        # Load equipment (no change needed here)
        player.equipment = {slot: None for slot in EQUIPMENT_SLOTS} # Initialize slots
        if "equipment" in data:
            from items.item_factory import ItemFactory
            for slot, item_ref in data["equipment"].items():
                 if item_ref and isinstance(item_ref, dict) and "item_id" in item_ref:
                     item_id = item_ref["item_id"]
                     overrides = item_ref.get("properties_override", {})
                     item = ItemFactory.create_item_from_template(item_id, world, **overrides)
                     if item and slot in player.equipment:
                          player.equipment[slot] = item
                     elif item: print(f"Warning: Invalid equip slot '{slot}' in save.")
                     else: print(f"Warning: Failed to load equipped item '{item_id}'.")

        player.world = world # Assign world reference
        return player

    def get_effective_attack_cooldown(self) -> float:
        """Calculates the current attack cooldown considering haste effects."""
        base_cooldown = self.attack_cooldown
        haste_factor = 1.0

        # Check equipped items for haste multipliers
        for item in self.equipment.values():
            if item:
                multiplier = item.get_property("haste_multiplier")
                if multiplier and multiplier > 0: # Ensure multiplier is valid
                    haste_factor *= multiplier

        # TODO: Check active player effects for haste multipliers if needed
        # for effect in self.effects:
        #     if "stat_modifiers" in effect and "attack_speed_multiplier" in effect["stat_modifiers"]:
        #         haste_factor *= effect["stat_modifiers"]["attack_speed_multiplier"]

        effective_cooldown = base_cooldown * haste_factor

        # Clamp to a minimum cooldown
        effective_cooldown = max(MIN_ATTACK_COOLDOWN, effective_cooldown)

        return effective_cooldown
