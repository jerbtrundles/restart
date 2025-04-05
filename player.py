# player.py
# --- Standard Imports ---
from typing import List, Dict, Optional, Any, Tuple, Set
import time
import random

# --- Imports for Classes Used Directly ---
from core.config import (
    FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT,
    FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, LEVEL_DIFF_COMBAT_MODIFIERS,
    MIN_HIT_CHANCE, MAX_HIT_CHANCE, MIN_XP_GAIN
)

from items.inventory import Inventory
from items.weapon import Weapon
from items.consumable import Consumable
from items.item import Item
from magic.spell import Spell
from magic.spell_registry import get_spell
from magic.effects import apply_spell_effect
from utils.utils import _serialize_item_reference, get_article, simple_plural # If defined in utils/utils.py
from utils.text_formatter import format_target_name, get_level_diff_category # Import category calculation

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from world.world import World # Only import for type checkers
    from items.item_factory import ItemFactory # For loading

class Player:
    def __init__(self, name: str):
        self.name = name
        self.inventory = Inventory(max_slots=20, max_weight=100.0)
        self.health = 100
        self.max_health = 100
        # *** NEW: Mana ***
        self.mana = 50
        self.max_mana = 50
        self.mana_regen_rate = 1.0 # Mana per second
        self.last_mana_regen_time = 0
        # *** END NEW ***
        self.stats = {
            "strength": 10, "dexterity": 10, "intelligence": 10,
            # Add optional magic-related stats
             "wisdom": 10, # Could affect mana regen or spell power
             "spell_power": 5, # Base bonus spell damage/healing
             "magic_resist": 2 # Base magic resistance
        }
        self.level = 1
        self.experience = 0
        self.experience_to_level = 100
        self.skills = {}
        self.effects = []
        self.quest_log = {}
        self.equipment: Dict[str, Optional[Item]] = { # No change needed here yet
            "main_hand": None, "off_hand": None, "body": None, "head": None,
            "feet": None, "hands": None, "neck": None,
        }
        self.valid_slots_for_type = { # No change needed here yet
            "Weapon": ["main_hand", "off_hand"], "Armor": ["body", "head", "feet", "hands"],
            "Shield": ["off_hand"], "Amulet": ["neck"],
        }
        self.attack_power = 5
        self.defense = 3
        self.is_alive = True
        self.faction = "player"
        self.in_combat = False
        self.combat_target = None
        self.attack_cooldown = 2.0
        self.last_attack_time = 0
        self.combat_targets = set()
        self.combat_messages = []
        self.max_combat_messages = 10
        self.follow_target: Optional[str] = None

        self.respawn_region_id: Optional[str] = "town"
        self.respawn_room_id: Optional[str] = "town_square"

        # *** NEW: Spellbook and Cooldowns ***
        self.known_spells: Set[str] = {"magic_missile", "minor_heal"} # Start with some spells (IDs)
        self.spell_cooldowns: Dict[str, float] = {} # spell_id -> time when cooldown ends
        # *** END NEW ***

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
        from utils.text_formatter import TextFormatter
        # ... (previous status parts) ...
        health_percent = (self.health / self.max_health) * 100 if self.max_health > 0 else 0
        health_text = f"{self.health}/{self.max_health}"
        if health_percent <= 25: health_display = f"{FORMAT_ERROR}{health_text}{FORMAT_RESET}"
        elif health_percent <= 50: health_display = f"{FORMAT_HIGHLIGHT}{health_text}{FORMAT_RESET}"
        else: health_display = f"{FORMAT_SUCCESS}{health_text}{FORMAT_RESET}"

        # *** ADD Mana Display ***
        mana_percent = (self.mana / self.max_mana) * 100 if self.max_mana > 0 else 0
        mana_text = f"{self.mana}/{self.max_mana}"
        mana_display = f"{FORMAT_CATEGORY}{mana_text}{FORMAT_RESET}" # Default color for now
        # *** END ADD ***

        status = f"{FORMAT_CATEGORY}Name:{FORMAT_RESET} {self.name}\n"
        status += f"{FORMAT_CATEGORY}Level:{FORMAT_RESET} {self.level} (XP: {self.experience}/{self.experience_to_level})\n"
        status += f"{FORMAT_CATEGORY}Health:{FORMAT_RESET} {health_display}  " # Add space
        # *** ADD Mana to line ***
        status += f"{FORMAT_CATEGORY}Mana:{FORMAT_RESET} {mana_display}\n"
        # *** END ADD ***
        status += f"{FORMAT_CATEGORY}Stats:{FORMAT_RESET} "
        status += f"STR {self.stats['strength']}, DEX {self.stats['dexterity']}, INT {self.stats['intelligence']}"
        # Add magic stats if you want them visible
        status += f", WIS {self.stats['wisdom']}, POW {self.stats['spell_power']}, RES {self.stats['magic_resist']}\n"
        status += f"{FORMAT_CATEGORY}Attack:{FORMAT_RESET} {self.get_attack_power()}, "
        status += f"{FORMAT_CATEGORY}Defense:{FORMAT_RESET} {self.get_defense()}\n"

        # ... (Equipment, Effects, Skills, Quests - unchanged) ...

        # *** NEW: Known Spells ***
        if self.known_spells:
             status += f"\n{FORMAT_TITLE}SPELLS KNOWN{FORMAT_RESET}\n"
             spell_list = []
             current_time = time.time() # Need current time to check cooldowns
             for spell_id in sorted(list(self.known_spells)):
                  spell = get_spell(spell_id)
                  if spell:
                       cooldown_end = self.spell_cooldowns.get(spell_id, 0)
                       if current_time < cooldown_end:
                            time_left = cooldown_end - current_time
                            spell_list.append(f"- {spell.name} ({spell.mana_cost} MP) [{FORMAT_ERROR}CD {time_left:.1f}s{FORMAT_RESET}]")
                       else:
                            spell_list.append(f"- {spell.name} ({spell.mana_cost} MP)")
             status += "\n".join(spell_list) + "\n"
        # *** END NEW ***

        if self.in_combat: # ... (combat status - unchanged) ...
            target_names = ", ".join([t.name for t in self.combat_targets if hasattr(t, 'name')])
            if not target_names: target_names = "unknown foes"
            status += f"\n{FORMAT_ERROR}In combat with {target_names}!{FORMAT_RESET}\n"

        if not self.is_alive:
             status += f"\n{FORMAT_ERROR}** YOU ARE DEAD **{FORMAT_RESET}\n"

        return status

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
        self.stats["wisdom"] += 1 # Increase wisdom on level up
        self.max_health = int(self.max_health * 1.1)
        self.health = self.max_health
        # *** ADD Mana Increase ***
        old_max_mana = self.max_mana
        self.max_mana = int(self.max_mana * 1.15 + self.stats["intelligence"] / 2) # Increase based on level and INT
        self.mana += (self.max_mana - old_max_mana)
        # *** END ADD ***

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


    def get_attack_power(self) -> int:
        # ... (implementation unchanged) ...
        attack = self.attack_power
        attack += self.stats["strength"] // 3

        weapon_bonus = 0
        main_hand_weapon = self.equipment.get("main_hand")
        if main_hand_weapon and isinstance(main_hand_weapon, Weapon):
            if main_hand_weapon.get_property("durability", 1) > 0:
                weapon_bonus = main_hand_weapon.get_property("damage", 0)
        attack += weapon_bonus

        for effect in self.effects:
            if "stat_modifiers" in effect and "attack" in effect["stat_modifiers"]:
                attack += effect["stat_modifiers"]["attack"]
        return attack

    def get_defense(self) -> int:
        # ... (implementation unchanged) ...
        defense = self.defense
        defense += self.stats["dexterity"] // 4

        armor_bonus = 0
        for slot_name, item in self.equipment.items():
            if item:
                item_defense = item.get_property("defense", 0)
                if item_defense > 0: armor_bonus += item_defense
        defense += armor_bonus

        for effect in self.effects:
            if "stat_modifiers" in effect and "defense" in effect["stat_modifiers"]:
                defense += effect["stat_modifiers"]["defense"]
        return defense

    # ... (enter_combat, exit_combat, can_attack, get_combat_status, _add_combat_message - unchanged) ...
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
        return self.is_alive and current_time - self.last_attack_time >= self.attack_cooldown # Add is_alive check

    def get_combat_status(self) -> str:
        if not self.in_combat or not self.combat_targets: return "You are not in combat."
        status = f"{FORMAT_TITLE}COMBAT STATUS{FORMAT_RESET}\n\n"
        status += f"{FORMAT_CATEGORY}Fighting against:{FORMAT_RESET}\n"
        for target in self.combat_targets:
            formatted_name = format_target_name(self, target) # <<< USE FORMATTER
            if hasattr(target, "health") and hasattr(target, "max_health") and target.max_health > 0:
                health_percent = (target.health / target.max_health) * 100
                if health_percent <= 25: health_display = f"{FORMAT_ERROR}{target.health}/{target.max_health}{FORMAT_RESET}"
                elif health_percent <= 50: health_display = f"{FORMAT_HIGHLIGHT}{target.health}/{target.max_health}{FORMAT_RESET}"
                else: health_display = f"{FORMAT_SUCCESS}{target.health}/{target.max_health}{FORMAT_RESET}"
                # Use formatted_name in the status line
                status += f"- {formatted_name}: {health_display} HP\n"
            else:
                 # Use formatted_name here too
                status += f"- {formatted_name}\n"
        if self.combat_messages:
            status += f"\n{FORMAT_CATEGORY}Recent combat actions:{FORMAT_RESET}\n"
            for msg in self.combat_messages: status += f"- {msg}\n"
        return status

    def _add_combat_message(self, message: str) -> None:
        self.combat_messages.append(message)
        while len(self.combat_messages) > self.max_combat_messages: self.combat_messages.pop(0)

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
            # ... (rest of dex calculation for dex_modified_hit_chance) ...
            attacker_dex = self.stats.get("dexterity", 10)
            target_dex = getattr(target, "stats", {}).get("dexterity", 10)
            dex_modified_hit_chance = max(0.10, min(base_hit_chance + (attacker_dex - target_dex) * 0.02, 0.98))

            hit_chance_mod, _, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))

            final_hit_chance = dex_modified_hit_chance * hit_chance_mod
            final_hit_chance = max(MIN_HIT_CHANCE, min(final_hit_chance, MAX_HIT_CHANCE))

        formatted_target_name = format_target_name(self, target) # <<< Format name

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

        # ... (Check Target Death & XP/Loot - unchanged) ...
        if hasattr(target, "health") and target.health <= 0:
            if hasattr(target, 'is_alive'): target.is_alive = False
            death_message = f"{formatted_target_name} has been defeated!"
            self._add_combat_message(death_message)
            self.exit_combat(target)
            result["target_defeated"] = True
            result["message"] += "\n" + death_message

            # Calculate Base XP
            base_xp_gained = max(1, getattr(target, "max_health", 10) // 5) + getattr(target, "level", 1) * 5

            # Apply XP Modifier based on level difference category
            _, _, xp_mod = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
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
                        loot_str = f"{formatted_target_name} dropped something."
                    elif len(loot_message_parts) == 1:
                        loot_str = f"{formatted_target_name} dropped {loot_message_parts[0]}."
                    elif len(loot_message_parts) == 2:
                        loot_str = f"{formatted_target_name} dropped {loot_message_parts[0]} and {loot_message_parts[1]}."
                    else: # More than 2 items
                        # Join all but the last with commas, then add "and" before the last one
                        all_but_last = ", ".join(loot_message_parts[:-1])
                        last_item = loot_message_parts[-1]
                        loot_str = f"{formatted_target_name} dropped {all_but_last}, and {last_item}."

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
            formatted_target_name = format_target_name(self, target) # <<< Format name
            
            if hasattr(target, 'is_alive'): target.is_alive = False # Make sure state is updated
            death_message = f"{formatted_target_name} has been defeated by {spell.name}!"
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
                        loot_str = f"{formatted_target_name} dropped something."
                    elif len(loot_message_parts) == 1:
                        loot_str = f"{formatted_target_name} dropped {loot_message_parts[0]}."
                    elif len(loot_message_parts) == 2:
                        loot_str = f"{formatted_target_name} dropped {loot_message_parts[0]} and {loot_message_parts[1]}."
                    else: # More than 2 items
                        # Join all but the last with commas, then add "and" before the last one
                        all_but_last = ", ".join(loot_message_parts[:-1])
                        last_item = loot_message_parts[-1]
                        loot_str = f"{formatted_target_name} dropped {all_but_last}, and {last_item}."

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
            "name": self.name,
            "health": self.health, "max_health": self.max_health,
            "mana": self.mana, "max_mana": self.max_mana,
            "stats": self.stats,
            "level": self.level, "experience": self.experience, "experience_to_level": self.experience_to_level,
            "skills": self.skills,
            "effects": self.effects, # Assumes effects are simple serializable dicts
            "quest_log": self.quest_log,
            "is_alive": self.is_alive,
            "current_location": current_location, # Store resolved location
            "respawn_region_id": self.respawn_region_id,
            "respawn_room_id": self.respawn_room_id,
            "known_spells": list(self.known_spells),
            "spell_cooldowns": self.spell_cooldowns,
            # --- Embed serialized inventory and equipment references ---
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
        # --- Load Basic Stats (mostly unchanged) ---
        player.health = data.get("health", 100)
        player.max_health = data.get("max_health", 100)
        player.mana = data.get("mana", 50)
        player.max_mana = data.get("max_mana", 50)
        player.stats = data.get("stats", {"strength": 10, "dexterity": 10, "intelligence": 10, "wisdom": 10, "spell_power": 5, "magic_resist": 2})
        # Ensure new stats have defaults
        player.stats.setdefault("wisdom", 10)
        player.stats.setdefault("spell_power", 5)
        player.stats.setdefault("magic_resist", 2)
        player.level = data.get("level", 1)
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

        # --- Load Inventory (using its modified from_dict) ---
        if "inventory" in data:
            # Pass world context to Inventory.from_dict
            player.inventory = Inventory.from_dict(data["inventory"], world)
        else:
            player.inventory = Inventory() # Default empty

        # --- Load Equipment (using references) ---
        player.equipment = { "main_hand": None, "off_hand": None, "body": None, "head": None, "feet": None, "hands": None, "neck": None } # Initialize empty
        if "equipment" in data:
            from items.item_factory import ItemFactory # Local import needed
            for slot, item_ref in data["equipment"].items():
                 # Check if item_ref is a valid reference dictionary
                 if item_ref and isinstance(item_ref, dict) and "item_id" in item_ref:
                     item_id = item_ref["item_id"]
                     overrides = item_ref.get("properties_override", {})
                     # Use ItemFactory with world context
                     item = ItemFactory.create_item_from_template(item_id, world, **overrides)
                     if item and slot in player.equipment:
                          player.equipment[slot] = item
                     elif item:
                          print(f"Warning: Invalid equipment slot '{slot}' found in save data for item '{item.name}'.")
                     else:
                          print(f"Warning: Failed to load equipped item '{item_id}' for slot '{slot}'.")

        return player
    # --- END MODIFIED ---
