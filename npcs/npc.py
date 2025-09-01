# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Added pathfinding-based movement to the `_schedule_behavior` method, replacing teleportation.
# - NPCs now find a path to their destination and move one room at a time.
# - Added `current_path` and `schedule_destination` attributes to the NPC class to manage movement state.

from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple
import random
import time
from game_object import GameObject
from items.inventory import Inventory
from items.item import Item
from items.item_factory import ItemFactory
from magic.spell import Spell
from magic.spell_registry import get_spell
from utils.text_formatter import format_target_name
from utils.utils import _reverse_direction, calculate_xp_gain, format_loot_drop_message, format_name_for_display, format_npc_arrival_message, format_npc_departure_message, get_arrival_phrase, get_article, get_departure_phrase
from core.config import (
    DEFAULT_FACTION_RELATIONS, EFFECT_DEFAULT_TICK_INTERVAL, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, HIT_CHANCE_AGILITY_FACTOR, LEVEL_DIFF_COMBAT_MODIFIERS, MAX_HIT_CHANCE, MIN_HIT_CHANCE, MINIMUM_DAMAGE_TAKEN, NPC_ATTACK_DAMAGE_VARIATION_RANGE, NPC_BASE_ATTACK_POWER, NPC_BASE_DEFENSE,
    NPC_BASE_HEALTH, NPC_BASE_HIT_CHANCE, NPC_BASE_XP_TO_LEVEL, NPC_CON_HEALTH_MULTIPLIER, NPC_DEFAULT_AGGRESSION, NPC_DEFAULT_ATTACK_COOLDOWN, NPC_DEFAULT_BEHAVIOR, NPC_DEFAULT_COMBAT_COOLDOWN, NPC_DEFAULT_FLEE_THRESHOLD, NPC_DEFAULT_MOVE_COOLDOWN, NPC_DEFAULT_RESPAWN_COOLDOWN, NPC_DEFAULT_SPELL_CAST_CHANCE, NPC_DEFAULT_STATS, NPC_DEFAULT_WANDER_CHANCE, NPC_HEALTH_DESC_THRESHOLDS,
    NPC_LEVEL_HEALTH_BASE_INCREASE, NPC_LEVEL_CON_HEALTH_MULTIPLIER, NPC_LEVEL_UP_HEALTH_HEAL_PERCENT, NPC_LEVEL_UP_STAT_INCREASE, NPC_MAX_COMBAT_MESSAGES, NPC_XP_TO_LEVEL_MULTIPLIER, WORLD_UPDATE_INTERVAL
)

if TYPE_CHECKING:
    from world.world import World
    from player import Player

class NPC(GameObject):
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown NPC",
                    description: str = "No description", health: int = 100,
                    friendly: bool = True, level: int = 1):
        self.template_id: Optional[str] = None

        final_obj_id = obj_id if obj_id else f"npc_{random.randint(1000, 9999)}"
        super().__init__(obj_id=final_obj_id, name=name, description=description)

        self.stats = NPC_DEFAULT_STATS.copy()
        self.level = level
        self.experience: int = 0
        self.experience_to_level: int = NPC_BASE_XP_TO_LEVEL
        self.is_trading: bool = False
        base_hp = NPC_BASE_HEALTH + int(self.stats.get('constitution', 8) * NPC_CON_HEALTH_MULTIPLIER)
        level_hp_bonus = (self.level - 1) * (NPC_LEVEL_HEALTH_BASE_INCREASE + int(self.stats.get('constitution', 8) * NPC_LEVEL_CON_HEALTH_MULTIPLIER))
        self.max_health = base_hp + level_hp_bonus
        self.health = min(health, self.max_health)
        self.faction = "neutral"
        self.friendly = friendly
        self.inventory = Inventory(max_slots=10, max_weight=50.0)
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.home_region_id: Optional[str] = None
        self.home_room_id: Optional[str] = None
        self.current_activity = None
        self.behavior_type = NPC_DEFAULT_BEHAVIOR
        self.wander_chance = NPC_DEFAULT_WANDER_CHANCE
        self.move_cooldown = NPC_DEFAULT_MOVE_COOLDOWN
        self.aggression = NPC_DEFAULT_AGGRESSION
        self.attack_power = NPC_BASE_ATTACK_POWER
        self.defense = NPC_BASE_DEFENSE
        self.flee_threshold = NPC_DEFAULT_FLEE_THRESHOLD
        self.respawn_cooldown = NPC_DEFAULT_RESPAWN_COOLDOWN
        self.combat_cooldown = NPC_DEFAULT_COMBAT_COOLDOWN
        self.attack_cooldown = NPC_DEFAULT_ATTACK_COOLDOWN
        self.max_combat_messages = NPC_MAX_COMBAT_MESSAGES
        self.spell_cast_chance: float = NPC_DEFAULT_SPELL_CAST_CHANCE
        self.patrol_points = []
        self.patrol_index = 0
        self.follow_target = None
        self.schedule = {}
        self.last_moved = 0
        self.dialog = {}
        self.default_dialog = "The {name} doesn't respond."
        self.ai_state = {}
        self.is_alive = True
        self.spawn_time = 0
        self.loot_table = {}
        self.in_combat = False
        self.combat_target = None
        self.last_combat_action = 0
        self.last_attack_time = 0
        self.combat_targets = set()
        self.combat_messages = []
        self.faction_relations = {"friendly": 100, "neutral": 0, "hostile": -100}
        self.usable_spells: List[str] = []
        self.spell_cooldowns: Dict[str, float] = {}
        self.world: Optional['World'] = None
        self.owner_id: Optional[str] = None
        self.creation_time: float = 0.0
        self.summon_duration: float = 0.0
        self.faction_relations = DEFAULT_FACTION_RELATIONS.copy()
        self.current_path: List[str] = []
        self.schedule_destination: Optional[Tuple[str, str, str]] = None

    def get_description(self) -> str:
        health_percent = self.health / self.max_health * 100
        health_desc = ""
        if health_percent <= NPC_HEALTH_DESC_THRESHOLDS[0]: health_desc = f"The {self.name} looks severely injured."
        elif health_percent <= NPC_HEALTH_DESC_THRESHOLDS[1]: health_desc = f"The {self.name} appears to be wounded."
        elif health_percent <= NPC_HEALTH_DESC_THRESHOLDS[2]: health_desc = f"The {self.name} has some minor injuries."
        else: health_desc = f"The {self.name} looks healthy."
        faction_desc = ""
        if self.faction == "hostile": faction_desc = f"The {self.name} looks hostile."
        elif self.faction == "friendly": faction_desc = f"The {self.name} appears friendly."
        combat_desc = ""
        if self.in_combat: combat_desc = f"The {self.name} is engaged in combat!"
        return f"{self.name}\n\n{self.description}\n\n{health_desc}" + (f"\n{faction_desc}" if faction_desc else "") + (f"\n{combat_desc}" if combat_desc else "")
        
    def talk(self, topic: Optional[str] = None) -> str:
        if self.in_combat:
            combat_responses = [f"The {self.name} is too busy fighting to talk!", f"The {self.name} growls angrily, focused on the battle.", f"\"Can't talk now!\" shouts the {self.name}."]
            return random.choice(combat_responses)
        if hasattr(self, "ai_state"):
            if self.ai_state.get("is_sleeping", False):
                responses = self.ai_state.get("sleeping_responses", [])
                if responses: return random.choice(responses).format(name=self.name)
            elif self.ai_state.get("is_eating", False):
                responses = self.ai_state.get("eating_responses", [])
                if responses: return random.choice(responses).format(name=self.name)
            elif self.ai_state.get("is_working", False) and topic != "work":
                responses = self.ai_state.get("working_responses", [])
                if responses: return random.choice(responses).format(name=self.name)
        if not topic:
            if "greeting" in self.dialog: return self.dialog["greeting"].format(name=self.name)
            return f"The {self.name} greets you."
        topic = topic.lower()
        if topic in self.dialog: return self.dialog[topic].format(name=self.name)
        for key in self.dialog:
            if topic in key: return self.dialog[key].format(name=self.name)
        return self.default_dialog.format(name=self.name)

    def attack(self, target) -> Dict[str, Any]:
        from utils.text_formatter import format_target_name, get_level_diff_category
        viewer = self.world.player if self.world and hasattr(self.world, 'player') else None
        target_level = getattr(target, 'level', 1)
        category = get_level_diff_category(self.level, target_level)
        base_hit_chance = NPC_BASE_HIT_CHANCE
        attacker_agi = self.stats.get("agility", 8)
        target_agi = getattr(target, "stats", {}).get("agility", 10)
        agi_modifier = (attacker_agi - target_agi) * HIT_CHANCE_AGILITY_FACTOR
        agi_modified_hit_chance = base_hit_chance + agi_modifier
        hit_chance_mod, _, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        level_modified_hit_chance = agi_modified_hit_chance * hit_chance_mod
        final_hit_chance = max(MIN_HIT_CHANCE, min(level_modified_hit_chance, MAX_HIT_CHANCE))
        formatted_caster_name = format_name_for_display(viewer, self, start_of_sentence=True)
        formatted_target_name = format_name_for_display(viewer, target, start_of_sentence=False)
        target_defeated = False
        if random.random() > final_hit_chance:
            miss_message = f"{formatted_caster_name} attacks {formatted_target_name} but misses!"
            return {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": 0, "missed": True, "message": miss_message, "hit_chance": final_hit_chance, "target_defeated": False}
        self.in_combat = True
        self.combat_target = target
        self.last_combat_action = time.time()
        base_damage = self.attack_power
        damage_variation = random.randint(NPC_ATTACK_DAMAGE_VARIATION_RANGE[0], NPC_ATTACK_DAMAGE_VARIATION_RANGE[1])
        base_damage += damage_variation
        _, damage_dealt_mod, _ = LEVEL_DIFF_COMBAT_MODIFIERS.get(category, (1.0, 1.0, 1.0))
        modified_attack_damage = max(MINIMUM_DAMAGE_TAKEN, int(base_damage * damage_dealt_mod))
        actual_damage = target.take_damage(modified_attack_damage, damage_type="physical")
        if not target.is_alive: target_defeated = True
        hit_message = f"{formatted_caster_name} attacks {formatted_target_name} for {int(actual_damage)} damage!"
        apply_effect_message = ""
        effect_chance = self.properties.get("on_hit_effect_chance", 0.0)
        if effect_chance > 0 and random.random() < effect_chance:
            effect_data = self.properties.get("on_hit_effect")
            if effect_data and isinstance(effect_data, dict):
                if hasattr(target, 'apply_effect'):
                    success, _ = target.apply_effect(effect_data, time.time())
                    if success:
                        viewer = self.world.player if self.world else None
                        eff_name = effect_data.get('name', 'an effect')
                        caster_name_fmt = format_name_for_display(viewer, self, True)
                        tgt_name_fmt = format_name_for_display(viewer, target, False)
                        apply_effect_message = f"{caster_name_fmt}'s attack afflicts {tgt_name_fmt} with {FORMAT_HIGHLIGHT}{eff_name}{FORMAT_RESET}!"
        result_message = hit_message
        if(apply_effect_message): result_message += "\n" + apply_effect_message
        result = {"attacker": self.name, "target": getattr(target, 'name', 'target'), "damage": actual_damage, "missed": False, "message": result_message, "hit_chance": final_hit_chance, "target_defeated": target_defeated}
        return result

    def take_damage(self, amount: int, damage_type: str) -> int:
        if not self.is_alive: return 0
        final_reduction = 0
        if damage_type == "physical": final_reduction = self.defense
        else: final_reduction = self.stats.get("magic_resist", 0)
        reduced_damage = max(0, amount - final_reduction)
        actual_damage = max(MINIMUM_DAMAGE_TAKEN, reduced_damage) if amount > 0 and reduced_damage > 0 else 0
        old_health = self.health
        new_health = old_health - actual_damage
        self.health = new_health
        self.in_combat = True 
        if self.health <= 0:
            self.is_alive = False
            self.health = 0
        return old_health - self.health

    def heal(self, amount: int) -> int:
        if not self.is_alive: return 0
        old_health = self.health
        self.health = min(self.max_health, self.health + amount)
        return self.health - old_health
        
    def should_flee(self) -> bool:
        health_percent = self.health / self.max_health
        return health_percent <= self.flee_threshold

    def get_relation_to(self, other) -> int:
        if hasattr(other, "faction"): return self.faction_relations.get(other.faction, 0)
        return 0

    def is_hostile_to(self, other) -> bool:
        relation = self.get_relation_to(other)
        return relation < 0

    def die(self, world: 'World') -> List[Item]:
        if self.properties.get("is_summoned"):
            self.despawn(world, silent=True)
            return []
        self.is_alive = False
        self.health = 0
        self.in_combat = False
        self.combat_target = None
        self.combat_targets.clear()
        self.spawn_time = time.time() - getattr(world, 'start_time', time.time())
        dropped_items: List[Item] = []
        if self.loot_table and self.current_region_id and self.current_room_id:
            for item_id, loot_data in self.loot_table.items():
                if item_id == "gold_value": continue
                if isinstance(loot_data, dict):
                    chance = loot_data.get("chance", 0)
                    if random.random() < chance:
                        try:
                            qty_range = loot_data.get("quantity", [1, 1])
                            if not isinstance(qty_range, (list, tuple)) or len(qty_range) != 2: qty_range = [1, 1]
                            quantity = random.randint(qty_range[0], qty_range[1])
                            for _ in range(quantity):
                                item = ItemFactory.create_item_from_template(item_id, world)
                                if item:
                                    if world and world.add_item_to_room(self.current_region_id, self.current_room_id, item): dropped_items.append(item)
                                    elif not world: print(f"Warning: World object missing in die() for {self.name}, cannot drop {item_id}")
                                else: print(f"Warning: ItemFactory failed to create loot item '{item_id}' for {self.name}.")
                        except Exception as e:
                            print(f"Error processing loot item '{item_id}' for {self.name}: {e}"); import traceback; traceback.print_exc()
                else:
                    chance = loot_data
                    if random.random() < chance:
                            print(f"Warning: Deprecated loot format for {item_id} in {self.name}. Use object format.")
                            item = ItemFactory.create_item_from_template(item_id, world)
                            if item:
                                if world and world.add_item_to_room(self.current_region_id, self.current_room_id, item): dropped_items.append(item)
        if hasattr(self, 'inventory') and self.current_region_id and self.current_room_id:
                for slot in self.inventory.slots:
                    if slot.item and random.random() < 0.1:
                        item_to_drop = slot.item
                        qty_to_drop = slot.quantity if slot.item.stackable else 1
                        for _ in range(qty_to_drop):
                            item_copy = ItemFactory.create_item_from_template(item_to_drop.obj_id, world)
                            if item_copy:
                                if world and world.add_item_to_room(self.current_region_id, self.current_room_id, item_copy): dropped_items.append(item_copy)
                            elif not world: print(f"Warning: World object missing in die() for {self.name}, cannot drop inventory item {item_to_drop.name}")
        return dropped_items

    def to_dict(self) -> Dict[str, Any]:
        state = {"template_id": self.template_id, "obj_id": self.obj_id, "name": self.name, "current_region_id": self.current_region_id, "current_room_id": self.current_room_id, "health": self.health, "level": self.level, "experience": self.experience, "experience_to_level": self.experience_to_level, "is_alive": self.is_alive, "stats": self.stats.copy(), "ai_state": self.ai_state.copy(), "spell_cooldowns": self.spell_cooldowns.copy(), "faction": self.faction, "inventory": self.inventory.to_dict(self.world) if self.world else {}}
        return state
        
    def _reverse_direction(self, direction: str) -> str:
        from utils.text_formatter import format_target_name
        opposites = {"north": "south", "south": "north", "east": "west", "west": "east", "northeast": "southwest", "southwest": "northeast", "northwest": "southeast", "southeast": "northwest", "up": "down", "down": "up"}
        return opposites.get(direction, "somewhere")

    def _schedule_behavior(self, world: 'World', current_time: float, player: Optional['Player']) -> Optional[str]:
        time_plugin = world.game.plugin_manager.get_plugin("time_plugin") if world.game and world.game.plugin_manager else None
        if not time_plugin: return None

        current_hour = time_plugin.hour
        npc_schedule = getattr(self, 'schedule', {})
        if not npc_schedule: return None

        target_entry = None
        sorted_hours = sorted([int(h) for h in npc_schedule.keys()], reverse=True)
        for hour in sorted_hours:
            if current_hour >= hour:
                target_entry = npc_schedule[str(hour)]
                break
        if target_entry is None and sorted_hours:
            target_entry = npc_schedule[str(sorted_hours[0])]
        if not target_entry: return None

        dest_region = target_entry.get("region_id")
        dest_room = target_entry.get("room_id")
        activity = target_entry.get("activity", "idle")
        if not dest_region or not dest_room: return None

        new_destination = (dest_region, dest_room, activity)
        if self.schedule_destination != new_destination:
            self.schedule_destination = new_destination
            self.current_path = []
            if hasattr(self, 'ai_state'): self.ai_state["current_activity"] = activity

        if self.current_region_id == dest_region and self.current_room_id == dest_room:
            self.current_path = []
            return None

        if not self.current_path:
            if not self.current_region_id: return None
            if not self.current_room_id: return None

            path = world.find_path(self.current_region_id, self.current_room_id, dest_region, dest_room)
            if path: self.current_path = path
            else:
                if not world.game: return None
                if world.game.debug_mode: print(f"DEBUG: NPC {self.name} cannot find path from {self.current_region_id}:{self.current_room_id} to {dest_region}:{dest_room}")
                return None

        if self.current_path:
            direction = self.current_path.pop(0)

            if not self.current_region_id: return None
            if not self.current_room_id: return None
            region = world.get_region(self.current_region_id)
            if not region: return None
            current_room_obj = region.get_room(self.current_room_id)
            if not current_room_obj or direction not in current_room_obj.exits:
                self.current_path = []
                return None
            destination_id = current_room_obj.exits[direction]
            
            old_region_id, old_room_id = self.current_region_id, self.current_room_id
            
            if ":" in destination_id: self.current_region_id, self.current_room_id = destination_id.split(":")
            else: self.current_room_id = destination_id
            
            departure_message, arrival_message = None, None
            if player and player.is_alive:
                player_loc = (player.current_region_id, player.current_room_id)
                if player_loc == (old_region_id, old_room_id): departure_message = format_npc_departure_message(self, direction, player)
                elif player_loc == (self.current_region_id, self.current_room_id): arrival_message = format_npc_arrival_message(self, direction, player)

            return departure_message or arrival_message
            
        return None

    def _wander_behavior(self, world: 'World', current_time: float, player: Optional['Player']) -> Optional[str]:
        from utils.text_formatter import format_target_name
        if random.random() > self.wander_chance: return None
        if not self.current_region_id or not self.current_room_id: return None
        region = world.get_region(self.current_region_id)
        if not region: return None
        room = region.get_room(self.current_room_id)
        if not room or not room.exits: return None
        valid_exits = {}
        is_hostile = (self.faction == "hostile")
        for direction, destination in room.exits.items():
            next_region_id = self.current_region_id
            next_room_id = destination
            if ":" in destination: next_region_id, next_room_id = destination.split(":")
            destination_is_safe = world.is_location_safe(next_region_id, next_room_id)
            if is_hostile and destination_is_safe: continue
            valid_exits[direction] = destination
        if not valid_exits: return None
        direction = random.choice(list(valid_exits.keys()))
        destination = valid_exits[direction]
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        if ":" in destination:
            new_region_id, new_room_id = destination.split(":")
            self.current_region_id = new_region_id
            self.current_room_id = new_room_id
        else:
            self.current_room_id = destination
        if player and world.current_region_id == old_region_id and world.current_room_id == old_room_id: return format_npc_departure_message(self, direction, player)
        if player and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id: return format_npc_arrival_message(self, direction, player)
        return None

    def _patrol_behavior(self, world: 'World', current_time: float, player: Optional['Player']) -> Optional[str]:
        if not self.patrol_points: return None
        next_point_room_id = self.patrol_points[self.patrol_index]
        if not self.current_region_id or not self.current_room_id: return None
        next_point_region_id = self.current_region_id
        is_hostile = (self.faction == "hostile")
        if is_hostile and world.is_location_safe(next_point_region_id, next_point_room_id):
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
            return None
        if next_point_room_id == self.current_room_id:
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
            return None
        region = world.get_region(self.current_region_id)
        if not region: return None
        room = region.get_room(self.current_room_id)
        if not room: return None
        chosen_direction: Optional[str] = None
        chosen_destination: Optional[str] = None
        for direction, destination in room.exits.items():
            if destination == next_point_room_id:
                    next_region_id = self.current_region_id
                    next_room_id = destination
                    if ":" in destination: next_region_id, next_room_id = destination.split(":")
                    if is_hostile and world.is_location_safe(next_region_id, next_room_id): continue
                    chosen_direction = direction
                    chosen_destination = destination
                    break
        if not chosen_direction or not chosen_destination:
            return self._wander_behavior(world, current_time, player)
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        if ":" in chosen_destination:
            new_region_id, new_room_id = chosen_destination.split(":")
            self.current_region_id = new_region_id
            self.current_room_id = new_room_id
        else:
            self.current_room_id = chosen_destination
        if player and world.current_region_id == old_region_id and world.current_room_id == old_room_id: return format_npc_departure_message(self, chosen_direction, player)
        if player and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id: return format_npc_arrival_message(self, chosen_direction, player)
        return None

    def _follower_behavior(self, world: 'World', current_time: float, player: Optional['Player']) -> Optional[str]:
        target_id_to_follow = self.follow_target
        if not target_id_to_follow and self.behavior_type == 'minion': target_id_to_follow = self.properties.get("owner_id")
        if not target_id_to_follow: return None
        target_entity = None
        if world.player and world.player.obj_id == target_id_to_follow: target_entity = world.player
        else: target_entity = world.get_npc(target_id_to_follow)
        if not target_entity or not target_entity.is_alive:
            if self.behavior_type == 'minion': self.despawn(world, silent=True)
            self.follow_target = None
            return None
        target_region_id = target_entity.current_region_id
        target_room_id = target_entity.current_room_id
        if (self.current_region_id == target_region_id and self.current_room_id == target_room_id): return None
        if not self.current_region_id or not self.current_room_id or not target_region_id or not target_room_id: return None
        path = world.find_path(self.current_region_id, self.current_room_id, target_region_id, target_room_id)
        if path and len(path) > 0:
            direction = path[0]
            region = world.get_region(self.current_region_id)
            if not region: return None
            room = region.get_room(self.current_room_id)
            if not room or direction not in room.exits: return None
            destination = room.exits[direction]
            next_region_id = self.current_region_id
            next_room_id = destination
            if ":" in destination: next_region_id, next_room_id = destination.split(":")
            is_hostile = (self.faction == "hostile")
            if is_hostile and world.is_location_safe(next_region_id, next_room_id): return None
            old_region_id = self.current_region_id
            old_room_id = self.current_room_id
            self.current_region_id = next_region_id
            self.current_room_id = next_room_id
            if player and player.current_region_id == old_region_id and player.current_room_id == old_room_id: return format_npc_departure_message(self, direction, player)
            if player and player.current_region_id == self.current_region_id and self.current_room_id == self.current_room_id: return format_npc_arrival_message(self, direction, player)
        return None

    def enter_combat(self, target) -> None:
            if not self.is_alive:
                return
            if not target or not getattr(target, 'is_alive', False):
                return
            if target is self:
                return

            if self.faction != "hostile" and getattr(target, 'faction', 'neutral') == self.faction:
                if target not in self.combat_targets:
                    return

            self.in_combat = True
            self.combat_targets.add(target)

            if hasattr(target, 'enter_combat') and not (hasattr(target, 'combat_targets') and self in target.combat_targets):
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
        return current_time - self.last_attack_time >= self.attack_cooldown

    def try_attack(self, world, current_time: float) -> Optional[str]:
        if current_time - self.last_combat_action < self.combat_cooldown: return None
        player = getattr(world, 'player', None)
        target = self.combat_target
        target_is_currently_valid = False
        if target:
            if target.is_alive and target.current_region_id == self.current_region_id and target.current_room_id == self.current_room_id: target_is_currently_valid = True
            else: self.combat_target = None; self.combat_targets.discard(target); target = None
        if not target:
            valid_targets_in_set = [t for t in self.combat_targets if t and t.is_alive and hasattr(t, 'current_region_id') and t.current_region_id == self.current_region_id and t.current_room_id == self.current_room_id]
            if not valid_targets_in_set: self.exit_combat(); return None
            target = random.choice(valid_targets_in_set); self.combat_target = target; target_is_currently_valid = True
        if not target_is_currently_valid or not target: self.exit_combat(); return None
        chosen_spell = None
        if self.usable_spells and random.random() < self.spell_cast_chance:
            available_spells = [];
            for spell_id in self.usable_spells:
                spell = get_spell(spell_id); cooldown_end = self.spell_cooldowns.get(spell_id, 0)
                if spell and current_time >= cooldown_end:
                    spell_target = target if spell.target_type != "self" else self
                    if (not spell_target or not spell_target.is_alive or spell_target.current_region_id != self.current_region_id or spell_target.current_room_id != self.current_room_id): continue
                    is_enemy = spell_target.faction != self.faction; is_friendly = (spell_target == self or spell_target.faction == self.faction)
                    if (spell.target_type == "enemy" and is_enemy) or (spell.target_type == "friendly" and is_friendly) or (spell.target_type == "self"): available_spells.append(spell)
            if available_spells: chosen_spell = random.choice(available_spells)
        action_result: Optional[Dict[str, Any]] = None
        target_defeated_this_turn = False
        if chosen_spell:
            spell_target = target if chosen_spell.target_type != "self" else self
            action_result = self.cast_spell(chosen_spell, spell_target, current_time)
            if action_result: target_defeated_this_turn = action_result.get("target_defeated", False)
            self.last_combat_action = current_time
        elif self.can_attack(current_time):
            if target.is_alive and target.current_region_id == self.current_region_id and target.current_room_id == self.current_room_id:
                action_result = self.attack(target)
                if action_result: target_defeated_this_turn = action_result.get("target_defeated", False)
                self.last_attack_time = current_time
                self.last_combat_action = current_time
        messages_for_player = []
        base_action_message = action_result.get("message") if action_result else None
        if base_action_message: messages_for_player.append(base_action_message)
        if target_defeated_this_turn:
            self.exit_combat(target)
            if self.combat_target == target: self.combat_target = None
            viewer = player
            attacker_name_fmt = format_name_for_display(viewer, self, True)
            target_name_fmt = format_name_for_display(viewer, target, False)
            defeat_message = f"{attacker_name_fmt} has defeated {target_name_fmt}!"
            messages_for_player.append(defeat_message)
            dropped_loot_items = []; loot_message = ""
            if target is not player and hasattr(target, 'die'):
                try: dropped_loot_items = target.die(self.world)
                except Exception as e: print(f"Error calling die() on target {target.name}: {e}")
                if dropped_loot_items: loot_message = format_loot_drop_message(viewer, target, dropped_loot_items)
            if loot_message: messages_for_player.append(loot_message)
            target_max_hp = getattr(target, 'max_health', 10); target_lvl = getattr(target, 'level', 1)
            is_player_minion = False
            if player:
                if self.properties.get("is_summoned", False) and self.properties.get("owner_id") == player.obj_id:
                    is_player_minion = True
            if is_player_minion and player:
                xp_gained = calculate_xp_gain(player.level, target_lvl, target_max_hp)
                if xp_gained > 0:
                    leveled_up = player.gain_experience(xp_gained)
                    messages_for_player.append(f"{FORMAT_SUCCESS}Your {self.name} earns you {xp_gained} experience!{FORMAT_RESET}")
                    if leveled_up: messages_for_player.append(f"{FORMAT_HIGHLIGHT}You leveled up to level {player.level}!{FORMAT_RESET}")
            else:
                xp_gained = calculate_xp_gain(self.level, target_lvl, target_max_hp)
                if xp_gained > 0:
                    npc_leveled_up = self.gain_experience(xp_gained)
                    if world and world.game:
                        if npc_leveled_up:
                            messages_for_player.append(f"{self.name} is now level {self.level}!")
                            print(f"{self.name} is now level {self.level}!")
                        if world.game.debug_mode:
                            messages_for_player.append(f"[NPC XP DBG] {self.name} (L{self.level}) gained {xp_gained} XP defeating {target.name} (L{target_lvl}).")
                            print(f"[NPC XP DBG] {self.name} (L{self.level}) gained {xp_gained} XP defeating {target.name} (L{target_lvl}).")
        final_message_for_player = "\n".join(msg for msg in messages_for_player if msg)
        player_present = player and player.is_alive and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id
        return final_message_for_player if player_present and final_message_for_player else None

    def _add_combat_message(self, message: str) -> None:
        self.combat_messages.append(message)
        while len(self.combat_messages) > self.max_combat_messages: self.combat_messages.pop(0)

    def cast_spell(self, spell: Spell, target, current_time: float) -> Dict[str, Any]:
            from magic.effects import apply_spell_effect
            from utils.text_formatter import format_target_name
            self.spell_cooldowns[spell.spell_id] = current_time + spell.cooldown
            viewer = self.world.player if self.world and hasattr(self.world, 'player') else None
            value, effect_message = apply_spell_effect(self, target, spell, viewer)
            formatted_caster_name = format_name_for_display(viewer, self, start_of_sentence=True) if viewer else self.name
            base_cast_message = spell.format_cast_message(self)
            formatted_cast_message = base_cast_message.replace(self.name, formatted_caster_name, 1)
            full_message = formatted_cast_message + "\n" + effect_message
            target_defeated = False
            if spell.effect_type == "damage" and hasattr(target, "health") and target.health <= 0:
                 if hasattr(target, 'is_alive'): target.is_alive = False
                 target_defeated = True
            return {"success": True, "message": full_message, "cast_message": formatted_cast_message, "effect_message": effect_message, "target": getattr(target, 'name', 'target'), "value": value, "spell": spell.name, "target_defeated": target_defeated}

    def despawn(self, world: 'World', silent: bool = False) -> Optional[str]:
        if not self.properties.get("is_summoned"): return None
        self.is_alive = False
        owner_id = self.owner_id or self.properties.get("owner_id")
        if owner_id and world:
            owner = world.player
            if owner and owner.obj_id == owner_id and hasattr(owner, 'active_summons'):
                removed = False
                for spell_id, summon_ids in list(owner.active_summons.items()):
                    if self.obj_id in summon_ids:
                        try:
                            summon_ids.remove(self.obj_id)
                            removed = True
                            if not summon_ids: del owner.active_summons[spell_id]
                            break
                        except ValueError: pass
        if not silent: return f"Your {self.name} crumbles to dust."
        return None

    def update(self, world, current_time: float) -> Optional[str]:
        player = getattr(world, 'player', None)
        time_delta_effects = WORLD_UPDATE_INTERVAL 
        all_messages_for_player = []
        if self.is_alive:
            effect_messages = self.process_active_effects(current_time, time_delta_effects)
            if effect_messages:
                player_present_for_effects = (player and player.is_alive and self.current_region_id == player.current_region_id and self.current_room_id == player.current_room_id)
                if player_present_for_effects: all_messages_for_player.extend(effect_messages)
        ai_message_for_player = None
        if self.is_alive: 
            if self.behavior_type == "minion": ai_message_for_player = self._handle_minion_ai(world, current_time, player)
            else: ai_message_for_player = self._handle_standard_ai(world, current_time, player)
        if ai_message_for_player: all_messages_for_player.append(ai_message_for_player)
        final_message = "\n".join(msg for msg in all_messages_for_player if msg)
        return final_message if final_message else None

    def _handle_minion_ai(self, world, current_time, player):
         owner = player
         if not owner or owner.obj_id != self.properties.get("owner_id"):
              self.despawn(world, silent=True); return None
         duration = self.properties.get("summon_duration", 0)
         created = self.properties.get("creation_time", 0)
         if duration > 0 and current_time > created + duration:
              despawn_message = self.despawn(world)
              player = world.player
              if despawn_message and player and self.current_region_id == player.current_region_id and self.current_room_id == player.current_room_id: return despawn_message
              return None
         owner_loc = (owner.current_region_id, owner.current_room_id)
         my_loc = (self.current_region_id, self.current_room_id)
         if self.in_combat:
              valid_targets = [t for t in self.combat_targets if t and t.is_alive and hasattr(t, 'current_region_id') and t.current_region_id == self.current_region_id and t.current_room_id == self.current_room_id]
              if not valid_targets: self.exit_combat();
              else:
                   target_to_attack = None
                   if owner.in_combat and owner.combat_target and owner.combat_target in valid_targets: target_to_attack = owner.combat_target
                   else:
                        targets_attacking_owner = [t for t in valid_targets if hasattr(t, 'combat_targets') and owner in t.combat_targets]
                        if targets_attacking_owner: target_to_attack = random.choice(targets_attacking_owner)
                        elif self.combat_target and self.combat_target in valid_targets: target_to_attack = self.combat_target
                        else: target_to_attack = random.choice(valid_targets)
                   self.combat_target = target_to_attack
                   return self.try_attack(world, current_time)
              return None
         elif my_loc != owner_loc:
              move_cooldown = self.properties.get("move_cooldown", 5)
              if current_time - self.last_moved >= move_cooldown:
                   self.follow_target = owner.obj_id; follow_message = self._follower_behavior(world, current_time, owner); self.follow_target = None
                   if follow_message: self.last_moved = current_time
                   return follow_message
              else: return None
         elif my_loc == owner_loc:
              if owner.in_combat and owner.combat_target and owner.combat_target.is_alive:
                   target_npc = owner.combat_target
                   if target_npc in world.get_npcs_in_room(self.current_region_id, self.current_room_id):
                        self.enter_combat(target_npc); self.combat_target = target_npc
                        target_name_fmt = format_name_for_display(owner, target_npc)
                        return f"{self.name} moves to assist against {target_name_fmt}!"
              else:
                   npcs_in_room = world.get_npcs_in_room(self.current_region_id, self.current_room_id)
                   intercept_target = None
                   for npc in npcs_in_room:
                        if npc.faction == "hostile" and npc.is_alive and hasattr(npc, 'combat_targets') and owner in npc.combat_targets: intercept_target = npc; break
                   if intercept_target:
                        self.enter_combat(intercept_target); self.combat_target = intercept_target
                        npc_name_fmt = format_name_for_display(owner, intercept_target)
                        return f"{self.name} intercepts {npc_name_fmt} attacking you!"
                   if not self.in_combat:
                        hostile_target_found = None
                        for potential_target in npcs_in_room:
                             if potential_target.faction == "hostile" and potential_target.is_alive: hostile_target_found = potential_target; break
                        if hostile_target_found:
                             self.enter_combat(hostile_target_found); self.combat_target = hostile_target_found
                             target_name_fmt = format_name_for_display(owner, hostile_target_found)
                             return f"{self.name} moves to attack {target_name_fmt}!"
         return None

    def _handle_standard_ai(self, world, current_time, player):
        if self.is_trading:
             if (player and player.trading_with == self.obj_id and player.current_region_id == self.current_region_id and player.current_room_id == self.current_room_id): return None
             else: self.is_trading = False;
        if self.in_combat:
             combat_message = self.try_attack(world, current_time)
             if self.is_alive and self.health < self.max_health * self.flee_threshold:
                 flee_message = self._try_flee(world, current_time, player)
                 if flee_message: return flee_message
             if self.in_combat: return combat_message
        elif (self.faction == "hostile" and self.aggression > 0 and player and player.is_alive and world.current_region_id == self.current_region_id and world.current_room_id == self.current_room_id):
             if random.random() < self.aggression:
                 self.enter_combat(player)
                 action_result_message = self.try_attack(world, current_time)
                 if action_result_message: return action_result_message
                 else: return f"{get_article(self.name).upper()} {format_target_name(player, self)} prepares to attack you!"
        elif not self.in_combat and not self.is_trading and self.is_alive:
            if self.faction != "hostile":
                npcs_in_room = world.get_npcs_in_room(self.current_region_id, self.current_room_id)
                hostiles_in_room = [npc for npc in npcs_in_room if npc.faction == "hostile" and npc.is_alive]
                if hostiles_in_room:
                    target_hostile = random.choice(hostiles_in_room)
                    self.enter_combat(target_hostile)
                    engage_message = ""
                    if player and player.is_alive and player.current_region_id == self.current_region_id and player.current_room_id == self.current_room_id:
                        viewer = player
                        attacker_name_fmt = format_name_for_display(viewer, self, start_of_sentence=True)
                        target_name_fmt = format_name_for_display(viewer, target_hostile, start_of_sentence=False)
                        engage_message = f"{attacker_name_fmt} moves to attack {target_name_fmt}!"
                        immediate_attack_msg = self.try_attack(world, current_time)
                        if immediate_attack_msg: engage_message += "\n" + immediate_attack_msg
                    return engage_message
        if current_time - self.last_moved < self.move_cooldown: return None
        move_message = None
        if self.behavior_type == "wanderer": move_message = self._wander_behavior(world, current_time, player)
        elif self.behavior_type == "patrol": move_message = self._patrol_behavior(world, current_time, player)
        elif self.behavior_type == "follower": move_message = self._follower_behavior(world, current_time, player)
        elif self.behavior_type == "scheduled": move_message = self._schedule_behavior(world, current_time, player)
        elif self.behavior_type == "aggressive": move_message = self._wander_behavior(world, current_time, player)
        if move_message: self.last_moved = current_time
        return move_message

    def _try_flee(self, world, current_time, player):
        from player import Player
        should_flee = True
        player_target = next((t for t in self.combat_targets if isinstance(t, Player)), None)
        if player_target and hasattr(player_target, "health") and player_target.health <= 10: should_flee = False
        if should_flee:
            if not self.current_region_id or not self.current_room_id: return None
            region = world.get_region(self.current_region_id)
            if region:
                room = region.get_room(self.current_room_id)
                if room and room.exits:
                    valid_exits = [d for d, dest in room.exits.items() if not world.is_location_safe(self.current_region_id, dest.split(':')[-1])] if self.faction == 'hostile' else list(room.exits.keys())
                    if valid_exits:
                        direction = random.choice(valid_exits)
                        destination = room.exits[direction]
                        old_region_id, old_room_id = self.current_region_id, self.current_room_id
                        new_region_id, new_room_id = old_region_id, destination
                        if ":" in destination: new_region_id, new_room_id = destination.split(":")
                        self.current_region_id = new_region_id
                        self.current_room_id = new_room_id
                        self.exit_combat()
                        self.last_moved = current_time
                        player_present = (player and player.is_alive and old_region_id == player.current_region_id and old_room_id == player.current_room_id)
                        if player_present:
                            npc_display_name = format_name_for_display(player, self, start_of_sentence=True)
                            return f"{npc_display_name} flees to the {direction}!"
        return None

    def gain_experience(self, amount: int) -> bool:
        if not self.is_alive: return False
        if amount <= 0: return False
        self.experience += amount
        leveled_up = False
        while self.experience >= self.experience_to_level:
            self.level_up()
            leveled_up = True
        return leveled_up

    def level_up(self) -> None:
        self.level += 1
        self.experience -= self.experience_to_level
        self.experience_to_level = int(self.experience_to_level * NPC_XP_TO_LEVEL_MULTIPLIER)
        for stat in self.stats:
            if stat not in ["spell_power", "magic_resist"]: self.stats[stat] += NPC_LEVEL_UP_STAT_INCREASE
        old_max_health = self.max_health
        final_con = self.stats.get('constitution', 8)
        base_hp = NPC_BASE_HEALTH + int(final_con * NPC_CON_HEALTH_MULTIPLIER)
        level_hp_bonus = (self.level - 1) * (NPC_LEVEL_HEALTH_BASE_INCREASE + int(final_con * NPC_LEVEL_CON_HEALTH_MULTIPLIER))
        self.max_health = base_hp + level_hp_bonus
        health_gained = self.max_health - old_max_health
        heal_amount = int(health_gained * NPC_LEVEL_UP_HEALTH_HEAL_PERCENT)
        self.heal(heal_amount)