# player.py
# --- Standard Imports ---
from typing import List, Dict, Optional, Any, Tuple, Set
import time
import random

# --- Imports for Classes Used Directly ---
from core.config import (
    FORMAT_BLUE, FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_GREEN, FORMAT_HIGHLIGHT,
    FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, FORMAT_YELLOW, LEVEL_DIFF_COMBAT_MODIFIERS, MIN_ATTACK_COOLDOWN,
    MIN_HIT_CHANCE, MAX_HIT_CHANCE, MIN_XP_GAIN,
    PLAYER_BASE_HEALTH, PLAYER_CON_HEALTH_MULTIPLIER,
    PLAYER_LEVEL_HEALTH_BASE_INCREASE, PLAYER_LEVEL_CON_HEALTH_MULTIPLIER
)

from items.inventory import Inventory
from items.weapon import Weapon
from items.consumable import Consumable
from items.item import Item
from magic.spell import Spell
from magic.spell_registry import get_spell
from magic.effects import apply_spell_effect
from utils.utils import _serialize_item_reference, format_name_for_display, get_article, simple_plural # If defined in utils/utils.py
from utils.text_formatter import format_target_name, get_level_diff_category # Import category calculation

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from world.world import World # Only import for type checkers
    from items.item_factory import ItemFactory # For loading

class Player:
    def __init__(self, name: str):
        self.name = name
        self.inventory = Inventory(max_slots=20, max_weight=100.0)
        self.max_mana = 50
        self.mana = self.max_mana
        self.mana_regen_rate = 1.0
        self.last_mana_regen_time = 0
        self.stats = {
            "strength": 10, "dexterity": 10, "intelligence": 10,
            "wisdom": 10, "constitution": 10, "agility": 10, # Added CON, AGI
            "spell_power": 5, "magic_resist": 2
        }
        self.max_health = PLAYER_BASE_HEALTH + int(self.stats.get('constitution', 10)) * PLAYER_CON_HEALTH_MULTIPLIER
        self.health = self.max_health
        self.level = 1
        self.experience = 0
        self.experience_to_level = 100
        self.skills = {} # Example: {"swordsmanship": 1}
        self.effects = [] # Example: [{"name": "Regen", "duration": 10}]
        self.quest_log = {} # Example: {"missing_supplies": "started"}
        self.equipment: Dict[str, Optional[Item]] = {
            "main_hand": None, "off_hand": None, "body": None, "head": None,
            "feet": None, "hands": None, "neck": None,
        }
        self.valid_slots_for_type = {
            "Weapon": ["main_hand", "off_hand"], "Armor": ["body", "head", "feet", "hands"],
            "Shield": ["off_hand"], "Amulet": ["neck"],
            "Item": ["body", "head", "feet", "hands"] # Generic Item might fit armor slots?
        }
        self.attack_power = 5 # Base physical attack power before stats/weapon
        self.defense = 3 # Base physical defense before stats/armor
        self.is_alive = True
        self.faction = "player"
        self.in_combat = False
        self.combat_target = None # Primarily used by NPCs, maybe player focuses one?
        self.attack_cooldown = 2.0 # Base cooldown in seconds
        self.last_attack_time = 0
        self.combat_targets = set() # All entities player is currently in combat with
        self.combat_messages = []
        self.max_combat_messages = 10
        self.follow_target: Optional[str] = None
        self.respawn_region_id: Optional[str] = "town"
        self.respawn_room_id: Optional[str] = "town_square"
        self.known_spells: Set[str] = {"magic_missile", "minor_heal"}
        self.spell_cooldowns: Dict[str, float] = {}
        # Add world reference if needed, e.g. set externally after creation
        self.world: Optional['World'] = None
        self.current_region_id: Optional[str] = None # Tracked by player for saving
        self.current_room_id: Optional[str] = None
        self.gold: int = 0 # <<< ADDED GOLD ATTRIBUTE
        self.trading_with: Optional[str] = None # <<< ADDED for Phase 3

    # *** NEW: Update method for regeneration ***
    def update(self, current_time: float):
        """Update player state like mana and health regeneration."""
        if not self.is_alive: return # Don't update if dead

        # --- Regeneration ---
        time_since_last_update = current_time - self.last_mana_regen_time # Use one timer for both

        if time_since_last_update >= 1.0: # Regenerate every second
            # Calculate base regen
            base_mana_regen = self.mana_regen_rate * (1 + self.stats.get('wisdom', 10) / 20)
            base_health_regen = 1.0 * (1 + self.stats.get('strength', 10) / 25) # Example base health regen

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

            # Update effects (if you have duration-based effects)
            # effect_messages = self.update_effects()
            # if effect_messages:
            #     for msg in effect_messages: self._add_combat_message(msg) # Or display differently

            # --- End Regeneration ---

    def get_status(self) -> str:
        """Returns a formatted string representing the player's current status."""

        # --- Health and Mana Formatting ---
        health_percent = (self.health / self.max_health) * 100 if self.max_health > 0 else 0
        health_text = f"{self.health}/{self.max_health}"
        if health_percent <= 25: health_display = f"{FORMAT_ERROR}{health_text}{FORMAT_RESET}"
        elif health_percent <= 50: health_display = f"{FORMAT_HIGHLIGHT}{health_text}{FORMAT_RESET}" # Using HIGHLIGHT for mid-health
        else: health_display = f"{FORMAT_SUCCESS}{health_text}{FORMAT_RESET}"

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
                          elif dura_percent <= 30: dura_color = FORMAT_YELLOW
                          else: dura_color = FORMAT_GREEN # Use green for good condition
                          durability_str = f" [{dura_color}{current_dura}/{max_dura}{FORMAT_RESET}]"

                equip_lines.append(f"  - {slot_display}: {item.name}{durability_str}")

        if equipped_items_found:
            status += f"\n{FORMAT_TITLE}EQUIPPED{FORMAT_RESET}\n"
            status += "\n".join(equip_lines) + "\n"
        # --- End Equipment ---

        # --- Effects ---
        if self.effects:
            status += f"\n{FORMAT_TITLE}EFFECTS{FORMAT_RESET}\n"
            effect_lines = []
            for effect in self.effects:
                # Assuming effects are dictionaries with 'name' and 'duration'
                name = effect.get('name', 'Unknown Effect')
                duration = effect.get('duration', '?')
                effect_lines.append(f"  - {name} ({duration} remaining)")
            status += "\n".join(effect_lines) + "\n"
        # --- End Effects ---

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
        self.experience_to_level = int(self.experience_to_level * 1.5)
        self.stats["strength"] += 1
        self.stats["dexterity"] += 1
        self.stats["intelligence"] += 1
        self.stats["wisdom"] += 1
        self.stats["constitution"] += 1 # Increase CON on level up
        self.stats["agility"] += 1      # Increase AGI on level up

        old_max_health = self.max_health
        health_increase = PLAYER_LEVEL_HEALTH_BASE_INCREASE + int(self.stats.get('constitution', 10) * PLAYER_LEVEL_CON_HEALTH_MULTIPLIER)
        self.max_health += health_increase
        self.health += (self.max_health - old_max_health) # Add the gained max health to current health

        old_max_mana = self.max_mana
        self.max_mana = int(self.max_mana * 1.15 + self.stats["intelligence"] / 2) # Increase based on level and INT
        self.mana += (self.max_mana - old_max_mana)


    def add_effect(self, name: str, description: str, duration: int,
                  stat_modifiers: Dict[str, int] = None) -> None:
        self.effects.append({
            "name": name, "description": description, "duration": duration,
            "stat_modifiers": stat_modifiers or {}
        })
        if stat_modifiers:
            for stat, modifier in stat_modifiers.items():
                if stat in self.stats: self.stats[stat] += modifier

    def update_effects(self) -> List[str]:
        messages = []
        expired_effects = []
        for effect in self.effects:
            effect["duration"] -= 1
            if effect["duration"] <= 0:
                expired_effects.append(effect)
                messages.append(f"The {effect['name']} effect has worn off.")
        for effect in expired_effects:
            self.effects.remove(effect)
            if "stat_modifiers" in effect:
                for stat, modifier in effect["stat_modifiers"].items():
                    if stat in self.stats: self.stats[stat] -= modifier
        return messages

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
        actual_damage = max(1, reduced_damage) if amount > 0 and reduced_damage > 0 else 0

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
        self.effects = []
        # *** Reset mana on death? Optional. ***
        # self.mana = 0
        print(f"{self.name} has died!")

    def respawn(self) -> None:
        self.health = self.max_health
        # *** Restore mana on respawn ***
        self.mana = self.max_mana
        self.is_alive = True
        self.effects = []
        self.in_combat = False
        self.combat_targets.clear()
        self.spell_cooldowns.clear() # Reset cooldowns on respawn

    # Make sure method name matches usage
    def get_is_alive(self) -> bool:
        # Ensure health check reflects dead state correctly
        return self.is_alive and self.health > 0


    # Make sure get_attack_power and get_defense are present
    def get_attack_power(self) -> int:
        attack = self.attack_power + self.stats.get("strength", 0) // 3
        weapon_bonus = 0
        main_hand_weapon = self.equipment.get("main_hand")
        if main_hand_weapon and isinstance(main_hand_weapon, Weapon):
            if main_hand_weapon.get_property("durability", 1) > 0:
                weapon_bonus = main_hand_weapon.get_property("damage", 0)
        attack += weapon_bonus
        # Add effects bonus if implemented
        return attack

    def get_defense(self) -> int:
        defense = self.defense + self.stats.get("dexterity", 10) // 4
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

    def exit_combat(self, target=None) -> None:
        if target:
            if target in self.combat_targets:
                self.combat_targets.remove(target)
                if hasattr(target, "exit_combat"): target.exit_combat(self)
        else:
            for t in list(self.combat_targets):
                if hasattr(t, "exit_combat"): t.exit_combat(self)
            self.combat_targets.clear()

        if not self.combat_targets: self.in_combat = False

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
            base_hit_chance = 0.85

            # Calculate hit chance modifier based on Agility difference
            # Increase hit chance by 2% for each point of AGI advantage
            # Decrease hit chance by 2% for each point of AGI disadvantage
            attacker_agi = self.stats.get("agility", 10)
            target_agi = getattr(target, "stats", {}).get("agility", 8)
            agi_modifier = (attacker_agi - target_agi) * 0.02
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
        damage_variation = random.randint(-1, 2)
        base_attack_damage = max(1, attack_power + damage_variation)

        _, damage_dealt_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        modified_attack_damage = int(base_attack_damage * damage_dealt_mod)
        modified_attack_damage = max(1, modified_attack_damage) # Ensure at least 1 damage before defense

        actual_damage = 0
        if hasattr(target, "take_damage"):
            actual_damage = target.take_damage(modified_attack_damage, damage_type="physical")
        elif hasattr(target, "health"):
            old_health = target.health
            target.health = max(0, target.health - modified_attack_damage)
            actual_damage = old_health - target.health
            if target.health <= 0 and hasattr(target, 'is_alive'): target.is_alive = False

        weapon_name = "bare hands"
        weapon_broke = False
        equipped_weapon = self.equipment.get("main_hand")


        if equipped_weapon and isinstance(equipped_weapon, Weapon):
            weapon_name = equipped_weapon.name
            current_durability = equipped_weapon.get_property("durability", 0)
            if current_durability > 0:
                equipped_weapon.update_property("durability", current_durability - 1)
                if current_durability - 1 <= 0:
                    weapon_broke = True

        hit_message = f"You attack {formatted_target_name} with your {weapon_name} for {actual_damage} damage!"
        if weapon_broke: hit_message += f"\n{FORMAT_ERROR}Your {weapon_name} breaks!{FORMAT_RESET}"
        result = {
            "attacker": self.name,
            "target": getattr(target, 'name', 'target'),
            "damage": actual_damage,
            "weapon": weapon_name,
            "missed": False,
            "message": hit_message,
            "hit_chance": final_hit_chance
        }
        self._add_combat_message(result["message"])

        # ... (Check Target Death & XP/Loot ) ...
        if hasattr(target, "health") and target.health <= 0:
            if hasattr(target, 'is_alive'): target.is_alive = False
            formatted_target_name_start = format_name_for_display(self, target, start_of_sentence=True)
            death_message = f"{formatted_target_name_start} has been defeated!"
            self._add_combat_message(death_message)
            self.exit_combat(target)
            result["target_defeated"] = True
            result["message"] += "\n" + death_message

            # Calculate XP
            base_xp_gained = max(1, getattr(target, "max_health", 10) // 5) + getattr(target, "level", 1) * 5
            _, _, xp_mod = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0)) # Apply XP Modifier based on level difference category
            final_xp_gained = int(base_xp_gained * xp_mod)
            final_xp_gained = max(MIN_XP_GAIN, final_xp_gained) # Ensure minimum XP

            leveled_up = self.gain_experience(final_xp_gained)
            exp_message = f"You gained {final_xp_gained} experience points!" # Show final XP
            self._add_combat_message(exp_message)
            result["message"] += "\n" + exp_message

            if leveled_up:
                level_up_msg = f"You leveled up to level {self.level}!"
                self._add_combat_message(level_up_msg)
                result["message"] += "\n" + level_up_msg

            # --- NEW: Gold Award Logic ---
            gold_awarded = 0
            if hasattr(target, "loot_table"):
                 # Check specifically for a 'gold_value' entry in the loot table
                 gold_loot_data = target.loot_table.get("gold_value") # Use a specific key like 'gold_value'
                 if isinstance(gold_loot_data, dict) and "chance" in gold_loot_data:
                      if random.random() < gold_loot_data["chance"]:
                           qty_range = gold_loot_data.get("quantity", [1, 1])
                           if isinstance(qty_range, (list, tuple)) and len(qty_range) == 2:
                                gold_awarded = random.randint(qty_range[0], qty_range[1])
                           else: # Fallback if quantity format is wrong
                                gold_awarded = 1
                           if gold_awarded > 0:
                                self.gold += gold_awarded
                                gold_message = f"You receive {gold_awarded} gold from the remains of {formatted_target_name}." # Target NOT start here
                                self._add_combat_message(gold_message)
                                result["message"] += "\n" + gold_message
                                result["gold_awarded"] = gold_awarded # Add to result dict

            if hasattr(target, "die"):
                # NPC.die now returns List[Item]
                dropped_loot_items: List[Item] = target.die(world)

                if dropped_loot_items:
                    # --- Aggregate Loot ---
                    loot_counts: Dict[str, Dict[str, Any]] = {} # item_id -> {"name": str, "count": int}
                    for item in dropped_loot_items:
                        item_id = item.obj_id
                        if item_id not in loot_counts:
                            loot_counts[item_id] = {"name": item.name, "count": 0}
                        loot_counts[item_id]["count"] += 1

                    # --- Format Loot Message ---
                    loot_message_parts = []
                    # Import helpers if needed: from utils.utils import get_article, simple_plural
                    for item_id, data in loot_counts.items():
                        name = data["name"]
                        count = data["count"]
                        if count == 1:
                            # Use helper for a/an
                            article = get_article(name)
                            loot_message_parts.append(f"{article} {name}")
                        else:
                            # Use helper for pluralization
                            plural_name = simple_plural(name)
                            loot_message_parts.append(f"{count} {plural_name}")

                    # --- Construct the Sentence ---
                    loot_str = ""
                    if not loot_message_parts:
                        # Should not happen if dropped_loot_items was not empty, but safety check
                        loot_str = f"{formatted_target_name_start} dropped something."
                    elif len(loot_message_parts) == 1:
                        loot_str = f"{formatted_target_name_start} dropped {loot_message_parts[0]}."
                    elif len(loot_message_parts) == 2:
                        loot_str = f"{formatted_target_name_start} dropped {loot_message_parts[0]} and {loot_message_parts[1]}."
                    else: # More than 2 items
                        # Join all but the last with commas, then add "and" before the last one
                        all_but_last = ", ".join(loot_message_parts[:-1])
                        last_item = loot_message_parts[-1]
                        loot_str = f"{formatted_target_name_start} dropped {all_but_last}, and {last_item}."

                    if loot_str: # Check if loot_str was generated
                        self._add_combat_message(loot_str)
                        result["message"] += "\n" + loot_str

        self.last_attack_time = time.time()
        return result

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

    # *** NEW: Spell related methods ***
    def learn_spell(self, spell_id: str) -> bool:
        """Adds a spell ID to the player's known spells."""
        spell = get_spell(spell_id)
        if spell and spell_id not in self.known_spells:
            if self.level >= spell.level_required:
                 self.known_spells.add(spell_id)
                 return True
            else:
                 # Maybe store it as learnable later? For now, just fail.
                 return False # Level too low
        return False # Spell doesn't exist or already known

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

        # Check target death (similar to attack)
        if spell.effect_type == "damage" and hasattr(target, "health") and target.health <= 0:
            formatted_target_name_start = format_name_for_display(self, target, start_of_sentence=True)
            
            if hasattr(target, 'is_alive'): target.is_alive = False # Make sure state is updated
            death_message = f"{formatted_target_name_start} has been defeated by {spell.name}!"
            self._add_combat_message(death_message)
            self.exit_combat(target)
            result["target_defeated"] = True
            result["message"] += "\n" + death_message

            # Calculate Base XP (can be adjusted for spells vs attacks if desired)
            base_xp_gained = max(1, getattr(target, "max_health", 10) // 4) + getattr(target, "level", 1) * 6 # Slightly different base for spells?

            # Apply XP Modifier
            target_level = getattr(target, 'level', 1)
            category = get_level_diff_category(self.level, target_level)
            _, _, xp_mod = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
            final_xp_gained = max(MIN_XP_GAIN, int(base_xp_gained * xp_mod))
            
            leveled_up = self.gain_experience(final_xp_gained)
            exp_message = f"You gained {final_xp_gained} experience points!"
            self._add_combat_message(exp_message)
            result["message"] += "\n" + exp_message
            if leveled_up:
                level_up_msg = f"You leveled up to level {self.level}!"
                self._add_combat_message(level_up_msg)
                result["message"] += "\n" + level_up_msg

            # --- NEW: Gold Award Logic (Identical to attack method's) ---
            gold_awarded = 0
            if hasattr(target, "loot_table"):
                 gold_loot_data = target.loot_table.get("gold_value")
                 if isinstance(gold_loot_data, dict) and "chance" in gold_loot_data:
                      if random.random() < gold_loot_data["chance"]:
                           qty_range = gold_loot_data.get("quantity", [1, 1])
                           if isinstance(qty_range, (list, tuple)) and len(qty_range) == 2:
                                gold_awarded = random.randint(qty_range[0], qty_range[1])
                           else: gold_awarded = 1
                           if gold_awarded > 0:
                                self.gold += gold_awarded
                                gold_message = f"You receive {gold_awarded} gold."
                                self._add_combat_message(gold_message)
                                result["message"] += "\n" + gold_message
                                result["gold_awarded"] = gold_awarded

            if hasattr(target, "die"):
                # NPC.die now returns List[Item]
                dropped_loot_items: List[Item] = target.die(world)

                if dropped_loot_items:
                    # --- Aggregate Loot ---
                    loot_counts: Dict[str, Dict[str, Any]] = {} # item_id -> {"name": str, "count": int}
                    for item in dropped_loot_items:
                        item_id = item.obj_id
                        if item_id not in loot_counts:
                            loot_counts[item_id] = {"name": item.name, "count": 0}
                        loot_counts[item_id]["count"] += 1

                    # --- Format Loot Message ---
                    loot_message_parts = []
                    # Import helpers if needed: from utils.utils import get_article, simple_plural
                    for item_id, data in loot_counts.items():
                        name = data["name"]
                        count = data["count"]
                        if count == 1:
                            # Use helper for a/an
                            article = get_article(name)
                            loot_message_parts.append(f"{article} {name}")
                        else:
                            # Use helper for pluralization
                            plural_name = simple_plural(name)
                            loot_message_parts.append(f"{count} {plural_name}")

                    # --- Construct the Sentence ---
                    loot_str = ""
                    if not loot_message_parts:
                        # Should not happen if dropped_loot_items was not empty, but safety check
                        loot_str = f"{formatted_target_name_start} dropped something."
                    elif len(loot_message_parts) == 1:
                        loot_str = f"{formatted_target_name_start} dropped {loot_message_parts[0]}."
                    elif len(loot_message_parts) == 2:
                        loot_str = f"{formatted_target_name_start} dropped {loot_message_parts[0]} and {loot_message_parts[1]}."
                    else: # More than 2 items
                        # Join all but the last with commas, then add "and" before the last one
                        all_but_last = ", ".join(loot_message_parts[:-1])
                        last_item = loot_message_parts[-1]
                        loot_str = f"{formatted_target_name_start} dropped {all_but_last}, and {last_item}."

                    if loot_str: # Check if loot_str was generated
                        self._add_combat_message(loot_str)
                        result["message"] += "\n" + loot_str

        return result

    def to_dict(self, world: 'World') -> Dict[str, Any]: # Needs world context
        """Serialize player state for saving."""
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

        return {
            "gold": self.gold, # <<< ADDED GOLD
            "name": self.name,
            "health": self.health, "max_health": self.max_health,
            "mana": self.mana, "max_mana": self.max_mana,
            "stats": self.stats,
            "level": self.level, "experience": self.experience, "experience_to_level": self.experience_to_level,
            "skills": self.skills,
            "effects": self.effects,
            "quest_log": self.quest_log,
            "is_alive": self.is_alive,
            "current_location": current_location,
            "respawn_region_id": self.respawn_region_id,
            "respawn_room_id": self.respawn_room_id,
            "known_spells": list(self.known_spells),
            "spell_cooldowns": self.spell_cooldowns,
            "inventory": inventory_data,
            "equipment": equipped_items_data,
        }
    # --- END MODIFIED ---

    # --- MODIFIED: Player.from_dict ---
    @classmethod
    def from_dict(cls, data: Dict[str, Any], world: Optional['World']) -> 'Player':
        """Deserialize player state from save game data."""
        if not world:
             print(f"{FORMAT_ERROR}Error: World context required to load player.{FORMAT_RESET}")
             # Return a default player or raise error?
             player = cls("DefaultPlayer")
             player.current_region_id = "town" # Set defaults
             player.current_room_id = "town_square"
             return player

        player = cls(data["name"])
        player.gold = data.get("gold", 0) # <<< ADDED GOLD (default to 0)
        player.trading_with = None # <<< Ensure trading state is reset on load

        player.stats = data.get("stats", {"strength": 10, "dexterity": 10, "intelligence": 10, "wisdom": 10, "spell_power": 5, "magic_resist": 2, "constitution": 10, "agility": 10})
        player.stats.setdefault("wisdom", 10)
        player.stats.setdefault("spell_power", 5)
        player.stats.setdefault("magic_resist", 2)
        player.stats.setdefault("constitution", 10)
        player.stats.setdefault("agility", 10)
        player.level = data.get("level", 1)

        player.max_health = PLAYER_BASE_HEALTH + int(player.stats.get('constitution', 10) * PLAYER_CON_HEALTH_MULTIPLIER)
        player.health = data.get("health", player.max_health)
        player.health = min(player.health, player.max_health) # Clamp loaded health
        player.mana = data.get("mana", 50)
        player.max_mana = data.get("max_mana", 50)

        player.experience = data.get("experience", 0)
        player.experience_to_level = data.get("experience_to_level", 100)
        player.skills = data.get("skills", {})
        player.effects = data.get("effects", []) # Assumes effects are simple lists/dicts
        player.quest_log = data.get("quest_log", {})
        player.is_alive = data.get("is_alive", True)
        player.known_spells = set(data.get("known_spells", ["magic_missile", "minor_heal"]))
        player.spell_cooldowns = data.get("spell_cooldowns", {})
        player.respawn_region_id = data.get("respawn_region_id", "town") # Default respawn
        player.respawn_room_id = data.get("respawn_room_id", "town_square")

        # --- Load Location (set temporarily, world confirms) ---
        loc = data.get("current_location", {})
        player.current_region_id = loc.get("region_id", player.respawn_region_id) # Fallback to respawn
        player.current_room_id = loc.get("room_id", player.respawn_room_id)

        # Reset transient state
        player.last_mana_regen_time = time.time()
        player.in_combat = False
        player.combat_targets.clear()
        player.combat_messages = []
        player.last_attack_time = 0

        # Load inventory
        if "inventory" in data:
            player.inventory = Inventory.from_dict(data["inventory"], world)
        else:
            player.inventory = Inventory() # Default empty

        # Load equipment
        player.equipment = { "main_hand": None, "off_hand": None, "body": None, "head": None, "feet": None, "hands": None, "neck": None }
        if "equipment" in data:
            from items.item_factory import ItemFactory # Local import
            for slot, item_ref in data["equipment"].items():
                 if item_ref and isinstance(item_ref, dict) and "item_id" in item_ref:
                     item_id = item_ref["item_id"]
                     overrides = item_ref.get("properties_override", {})
                     item = ItemFactory.create_item_from_template(item_id, world, **overrides)
                     if item and slot in player.equipment:
                          player.equipment[slot] = item
                     elif item: print(f"Warning: Invalid equip slot '{slot}' in save.")
                     else: print(f"Warning: Failed to load equipped item '{item_id}'.")

        return player
    # --- END MODIFIED ---

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
