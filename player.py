# player.py
from typing import List, Dict, Optional, Any, Tuple
from items.inventory import Inventory
from utils.text_formatter import TextFormatter
from items.weapon import Weapon
from items.consumable import Consumable
from items.item import Item # Import base Item

class Player:
    """
    Represents the player character in the game.
    """
    def __init__(self, name: str):
        # ... (existing attributes - no change) ...
        self.name = name
        self.inventory = Inventory(max_slots=20, max_weight=100.0)
        self.health = 100
        self.max_health = 100
        self.stats = {
            "strength": 10,
            "dexterity": 10,
            "intelligence": 10
        }
        self.level = 1
        self.experience = 0
        self.experience_to_level = 100
        self.skills = {}
        self.effects = []
        self.quest_log = {}
        self.equipment: Dict[str, Optional[Item]] = {
            "main_hand": None, "off_hand": None, "body": None, "head": None,
            "feet": None, "hands": None, "neck": None,
        }
        self.valid_slots_for_type = {
            "Weapon": ["main_hand", "off_hand"],
            "Armor": ["body", "head", "feet", "hands"],
            "Shield": ["off_hand"], "Amulet": ["neck"],
        }
        self.attack_power = 5
        self.defense = 3
        self.is_alive = True # Start alive
        self.faction = "player"
        self.in_combat = False
        self.combat_target = None
        self.attack_cooldown = 2.0
        self.last_attack_time = 0
        self.combat_targets = set()
        self.combat_messages = []
        self.max_combat_messages = 10
        self.follow_target: Optional[str] = None

        self.respawn_region_id: Optional[str] = "town" # Default respawn region
        self.respawn_room_id: Optional[str] = "town_square" # Default respawn room

    # ... (get_status, gain_experience, level_up, add_effect, update_effects - unchanged) ...
    # ... (add_skill, get_skill_level, update_quest, get_quest_progress, heal - unchanged) ...

    def get_status(self) -> str:
        # ... (implementation unchanged) ...
        health_percent = (self.health / self.max_health) * 100 if self.max_health > 0 else 0 # Prevent division by zero
        health_text = f"{self.health}/{self.max_health}"
        if health_percent <= 25: health_display = f"{TextFormatter.FORMAT_ERROR}{health_text}{TextFormatter.FORMAT_RESET}"
        elif health_percent <= 50: health_display = f"{TextFormatter.FORMAT_HIGHLIGHT}{health_text}{TextFormatter.FORMAT_RESET}"
        else: health_display = f"{TextFormatter.FORMAT_SUCCESS}{health_text}{TextFormatter.FORMAT_RESET}"

        status = f"{TextFormatter.FORMAT_CATEGORY}Name:{TextFormatter.FORMAT_RESET} {self.name}\n"
        status += f"{TextFormatter.FORMAT_CATEGORY}Level:{TextFormatter.FORMAT_RESET} {self.level} (XP: {self.experience}/{self.experience_to_level})\n"
        status += f"{TextFormatter.FORMAT_CATEGORY}Health:{TextFormatter.FORMAT_RESET} {health_display}\n"
        status += f"{TextFormatter.FORMAT_CATEGORY}Stats:{TextFormatter.FORMAT_RESET} "
        status += f"STR {self.stats['strength']}, DEX {self.stats['dexterity']}, INT {self.stats['intelligence']}\n"
        status += f"{TextFormatter.FORMAT_CATEGORY}Attack:{TextFormatter.FORMAT_RESET} {self.get_attack_power()}, "
        status += f"{TextFormatter.FORMAT_CATEGORY}Defense:{TextFormatter.FORMAT_RESET} {self.get_defense()}\n"

        status += f"\n{TextFormatter.FORMAT_TITLE}EQUIPMENT{TextFormatter.FORMAT_RESET}\n"
        equipped_items = False
        for slot, item in self.equipment.items():
            if item:
                status += f"- {slot.replace('_', ' ').capitalize()}: {item.name}\n"
                equipped_items = True
        if not equipped_items:
            status += "  (Nothing equipped)\n"

        if self.effects: status += f"\n{TextFormatter.FORMAT_TITLE}Active Effects:{TextFormatter.FORMAT_RESET}\n" # ... (effects - unchanged) ...
        if self.skills: status += f"\n{TextFormatter.FORMAT_TITLE}Skills:{TextFormatter.FORMAT_RESET}\n" # ... (skills - unchanged) ...
        if self.quest_log: status += f"\n{TextFormatter.FORMAT_TITLE}Active Quests:{TextFormatter.FORMAT_RESET} {len(self.quest_log)}\n" # ... (quests - unchanged) ...
        if self.in_combat: # ... (combat status - unchanged) ...
            target_names = ", ".join([t.name for t in self.combat_targets if hasattr(t, 'name')])
            if not target_names: target_names = "unknown foes"
            status += f"\n{TextFormatter.FORMAT_ERROR}In combat with {target_names}!{TextFormatter.FORMAT_RESET}\n"

        # --- NEW: Indicate if dead ---
        if not self.is_alive:
             status += f"\n{TextFormatter.FORMAT_ERROR}** YOU ARE DEAD **{TextFormatter.FORMAT_RESET}\n"
        # --- END NEW ---

        return status

    def gain_experience(self, amount: int) -> bool:
        self.experience += amount
        if self.experience >= self.experience_to_level:
            self.level_up()
            return True
        return False

    def level_up(self) -> None:
        self.level += 1
        self.experience -= self.experience_to_level
        self.experience_to_level = int(self.experience_to_level * 1.5)
        self.stats["strength"] += 1
        self.stats["dexterity"] += 1
        self.stats["intelligence"] += 1
        old_max_health = self.max_health
        self.max_health = int(self.max_health * 1.1)
        self.health += (self.max_health - old_max_health)

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

    def take_damage(self, amount: int) -> int:
        if not self.is_alive: return 0 # Cannot take damage if already dead

        defense = self.get_defense() # Uses updated get_defense
        reduced_damage = max(0, amount - defense)
        actual_damage = max(1, reduced_damage) if amount > 0 else 0
        old_health = self.health
        self.health = max(0, self.health - actual_damage)

        if self.health <= 0:
            self.die() # Call the die method

        return old_health - self.health

    # --- NEW: Die method ---
    def die(self) -> None:
        """Handles the player's death."""
        if not self.is_alive: return # Already dead

        self.health = 0
        self.is_alive = False
        self.in_combat = False # Exit combat on death
        self.combat_targets.clear()
        self.effects = [] # Clear temporary effects on death

        print(f"{self.name} has died!") # Console log for debugging
        # Note: Dropping items or XP penalty logic could be added here or in GameManager
    # --- END NEW ---

    # --- NEW: Respawn method ---
    def respawn(self) -> None:
        """Resets the player's state upon respawning."""
        self.health = self.max_health
        self.is_alive = True
        self.effects = [] # Clear effects again just in case
        self.in_combat = False
        self.combat_targets.clear()
        # Add any other necessary resets here (e.g., hunger/thirst if implemented)
    # --- END NEW ---

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

    def to_dict(self) -> Dict[str, Any]:
        # ... (implementation unchanged, but added respawn location) ...
        equipped_items_data = {}
        for slot, item in self.equipment.items():
            equipped_items_data[slot] = item.to_dict() if item else None

        return {
            "name": self.name,
            "inventory": self.inventory.to_dict(),
            "equipment": equipped_items_data,
            "health": self.health,
            "max_health": self.max_health,
            "stats": self.stats,
            "level": self.level,
            "experience": self.experience,
            "experience_to_level": self.experience_to_level,
            "skills": self.skills,
            "effects": self.effects,
            "quest_log": self.quest_log,
            "attack_power": self.attack_power,
            "defense": self.defense,
            "is_alive": self.is_alive, # Save alive status
            "in_combat": self.in_combat,
            "respawn_region_id": self.respawn_region_id, # Save respawn location
            "respawn_room_id": self.respawn_room_id,     # Save respawn location
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Player':
        # ... (implementation unchanged, but load respawn location) ...
        player = cls(data["name"])
        player.health = data.get("health", 100)
        player.max_health = data.get("max_health", 100)
        player.stats = data.get("stats", {"strength": 10, "dexterity": 10, "intelligence": 10})
        player.level = data.get("level", 1)
        player.experience = data.get("experience", 0)
        player.experience_to_level = data.get("experience_to_level", 100)
        player.skills = data.get("skills", {})
        player.effects = data.get("effects", [])
        player.quest_log = data.get("quest_log", {})
        player.attack_power = data.get("attack_power", 5)
        player.defense = data.get("defense", 3)
        player.is_alive = data.get("is_alive", True) # Load alive status
        player.in_combat = data.get("in_combat", False)
        player.respawn_region_id = data.get("respawn_region_id", "town") # Load respawn location
        player.respawn_room_id = data.get("respawn_room_id", "town_square") # Load respawn location

        if "inventory" in data:
            player.inventory = Inventory.from_dict(data["inventory"])
        else:
            player.inventory = Inventory()

        if "equipment" in data:
            from items.item_factory import ItemFactory
            for slot, item_data in data["equipment"].items():
                if item_data and slot in player.equipment:
                    item = ItemFactory.from_dict(item_data)
                    if item:
                        player.equipment[slot] = item
                    else:
                         print(f"Warning: Failed to load item for equipment slot '{slot}'")
        return player

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
        # ... (implementation unchanged) ...
        if not self.in_combat or not self.combat_targets: return "You are not in combat."
        status = f"{TextFormatter.FORMAT_TITLE}COMBAT STATUS{TextFormatter.FORMAT_RESET}\n\n"
        status += f"{TextFormatter.FORMAT_CATEGORY}Fighting against:{TextFormatter.FORMAT_RESET}\n"
        for target in self.combat_targets:
            if hasattr(target, "health") and hasattr(target, "max_health") and target.max_health > 0:
                health_percent = (target.health / target.max_health) * 100
                if health_percent <= 25: health_display = f"{TextFormatter.FORMAT_ERROR}{target.health}/{target.max_health}{TextFormatter.FORMAT_RESET}"
                elif health_percent <= 50: health_display = f"{TextFormatter.FORMAT_HIGHLIGHT}{target.health}/{target.max_health}{TextFormatter.FORMAT_RESET}"
                else: health_display = f"{TextFormatter.FORMAT_SUCCESS}{target.health}/{target.max_health}{TextFormatter.FORMAT_RESET}"
                status += f"- {target.name}: {health_display} HP\n"
            else: status += f"- {target.name}\n"
        if self.combat_messages:
            status += f"\n{TextFormatter.FORMAT_CATEGORY}Recent combat actions:{TextFormatter.FORMAT_RESET}\n"
            for msg in self.combat_messages: status += f"- {msg}\n"
        return status

    def _add_combat_message(self, message: str) -> None:
        self.combat_messages.append(message)
        while len(self.combat_messages) > self.max_combat_messages: self.combat_messages.pop(0)

    def attack(self, target) -> Dict[str, Any]:
        # --- NEW: Check if player is alive ---
        if not self.is_alive:
             return {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": 0, "missed": False, "message": "You cannot attack while dead."}
        # --- END NEW ---

        # ... (Hit Chance Calculation - unchanged) ...
        import random
        import time
        base_hit_chance = 0.85
        attacker_dex = self.stats.get("dexterity", 10)
        target_dex = getattr(target, "stats", {}).get("dexterity", 10)
        hit_chance = max(0.10, min(base_hit_chance + (attacker_dex - target_dex) * 0.02, 0.98))
        if random.random() > hit_chance:
            miss_message = f"You swing at {getattr(target, 'name', 'the target')} but miss!"
            self._add_combat_message(miss_message)
            self.last_attack_time = time.time()
            return {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": 0, "missed": True, "message": miss_message}

        # ... (HIT, Damage Calculation, Durability - unchanged) ...
        self.enter_combat(target)
        attack_power = self.get_attack_power()
        damage_variation = random.randint(-1, 2)
        attack_damage = max(1, attack_power + damage_variation)

        actual_damage = 0
        if hasattr(target, "take_damage"): actual_damage = target.take_damage(attack_damage)
        elif hasattr(target, "health"):
            old_health = target.health
            target.health = max(0, target.health - attack_damage)
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

        hit_message = f"You attack {getattr(target, 'name', 'the target')} with your {weapon_name} for {actual_damage} damage!"
        if weapon_broke:
            hit_message += f"\n{TextFormatter.FORMAT_ERROR}Your {weapon_name} breaks!{TextFormatter.FORMAT_RESET}"

        result = {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": actual_damage, "weapon": weapon_name, "missed": False, "message": hit_message}
        self._add_combat_message(result["message"])

        # ... (Check Target Death & XP/Loot - unchanged) ...
        if hasattr(target, "health") and target.health <= 0:
            if hasattr(target, 'is_alive'): target.is_alive = False
            death_message = f"{target.name} has been defeated!"
            self._add_combat_message(death_message)
            self.exit_combat(target)

            xp_gained = max(1, getattr(target, "max_health", 10) // 5) + getattr(target, "level", 1) * 5
            leveled_up = self.gain_experience(xp_gained)
            exp_message = f"You gained {xp_gained} experience points!"
            self._add_combat_message(exp_message)
            if leveled_up: self._add_combat_message(f"You leveled up to level {self.level}!")

            world_context = getattr(self, '_context', {}).get("world")
            if hasattr(target, "die"):
                dropped_loot = target.die(world_context)
                if dropped_loot:
                     for item in dropped_loot:
                         self._add_combat_message(f"{target.name} dropped: {item.name}")
            elif hasattr(target, "loot_table"):
                for item_name, chance in target.loot_table.items():
                    if random.random() < chance: self._add_combat_message(f"{target.name} dropped: {item_name}")

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
