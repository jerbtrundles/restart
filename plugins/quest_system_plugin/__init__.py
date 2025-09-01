# plugins/quest_system_plugin/__init__.py
# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Added "guard clauses" to safely handle optional world/event_system attributes.
# - Fixed Pylance reportCallIssue by ensuring keys passed to .get() are not None.

import time
import random
import uuid
from typing import Dict, Any, List, Optional, Tuple

from plugins.plugin_system import PluginBase
from core.config import FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, FORMAT_HIGHLIGHT, FORMAT_CATEGORY
from utils.text_formatter import get_level_diff_category
from utils.utils import simple_plural # Assuming utils are accessible
from items.item_factory import ItemFactory # Needed for rewards/delivery items
from player import Player # Type hint
from npcs.npc import NPC # Type hint

class QuestSystemPlugin(PluginBase):
    plugin_id = "quest_system_plugin"
    plugin_name = "Quest System"

    def __init__(self, world=None, command_processor=None, event_system=None, data_provider=None, service_locator=None):
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator

        # Load config
        from .config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG.copy()

        # --- Quest State ---
        # Active quests are stored on the player (self.world.player.quest_log)
        # Available quests are stored on the board (in world plugin data)
        self.quest_board_key = "quest_board_data" # Key for world.plugin_data

        self.npc_interests: Dict[str, List[str]] = {} # Initialize the dictionary
        self._load_npc_interests()

    def initialize(self):
        """Initialize the quest system."""
        # Guard clause for core components
        if not self.world or not self.event_system:
            print(f"{FORMAT_ERROR}[QuestSys] World or EventSystem missing. Cannot initialize.{FORMAT_RESET}")
            return

        print("[QuestSys] Initializing...")
        self._init_quest_board_state()
        self._register_event_listeners()
        self._register_commands()
        self._ensure_initial_quests() # Populate board if empty
        print(f"[QuestSys] Initialization complete. Board at {self.config.get('quest_board_location')}")

    def _init_quest_board_state(self):
        """Initialize the quest board data in world plugin data if it doesn't exist."""
        # Guard clause
        if not self.world: return

        board_data = self.world.get_plugin_data(self.plugin_id, self.quest_board_key)
        if board_data is None or not isinstance(board_data, dict) or "available_quests" not in board_data:
            self.world.set_plugin_data(self.plugin_id, self.quest_board_key, {"available_quests": []})
            print("[QuestSys] Initialized empty quest board state.")
        else:
            # Optional: Validate existing board data on load?
             print(f"[QuestSys] Found existing quest board state with {len(board_data['available_quests'])} quests.")


    def _register_event_listeners(self):
        """Subscribe to game events needed for quest tracking."""
        if self.event_system:
            self.event_system.subscribe("npc_killed", self._handle_npc_killed)
            self.event_system.subscribe("item_obtained", self._handle_item_obtained)

    def _register_commands(self):
        """Register commands related to the quest board."""
        from .commands import register_commands # Ensure this matches the function name in commands.py
        register_commands(self)

    def _ensure_initial_quests(self):
        """Ensure the board has a minimum number of quests and attempts to fill it, ensuring variety."""
        # Guard clause for world
        if not self.world:
            print(f"{FORMAT_ERROR}[QuestSys] Cannot ensure initial quests: World not available.{FORMAT_RESET}")
            return

        board_data = self.world.get_plugin_data(self.plugin_id, self.quest_board_key)
        if not board_data:
            self._init_quest_board_state()
            board_data = self.world.get_plugin_data(self.plugin_id, self.quest_board_key)

        current_quests = board_data.get("available_quests", [])
        current_count = len(current_quests)
        max_quests = self.config.get("max_quests_on_board", 5)
        required_types = ["kill", "fetch", "deliver"] # Basic types to ensure

        # Ensure player exists for level check
        player = self.world.player
        if not player:
            print(f"{FORMAT_ERROR}[QuestSys] Cannot generate initial quests: Player not loaded.{FORMAT_RESET}")
            return

        slots_to_fill = max(0, max_quests - current_count)
        if slots_to_fill == 0:
            print(f"[QuestSys] Quest board is already full ({current_count}/{max_quests}).")
            return

        print(f"[QuestSys] Board has {current_count}/{max_quests} quests. Attempting to generate {slots_to_fill} more.")

        generated_count = 0
        attempts = 0
        max_total_attempts = (slots_to_fill * 5) + len(required_types)

        # Phase 1: Ensure Variety
        current_types_on_board = {q.get("type") for q in current_quests}
        types_to_ensure = [t for t in required_types if t not in current_types_on_board]

        if types_to_ensure:
            if self.config.get("debug"): print(f"[QuestSys Debug] Ensuring missing basic types: {', '.join(types_to_ensure)}")
            for specific_type in types_to_ensure:
                if slots_to_fill <= 0: break

                type_attempts = 0; max_type_attempts = 3; generated_this_type = False
                while not generated_this_type and type_attempts < max_type_attempts and slots_to_fill > 0 and attempts < max_total_attempts:
                    type_attempts += 1; attempts += 1
                    if self.config.get("debug"): print(f"[QuestSys Debug] Generating required type: {specific_type} (Attempt {type_attempts}/{max_type_attempts})")

                    new_quest = self.generate_quest(player.level, specific_type)
                    if new_quest:
                        is_duplicate = any(q.get("title") == new_quest.get("title") for q in current_quests)
                        if not is_duplicate:
                            current_quests.append(new_quest)
                            generated_count += 1; slots_to_fill -= 1; generated_this_type = True
                            if self.config.get("debug"):
                                quest_type = new_quest.get('type', '?'); title = new_quest.get('title', 'N/A'); objective = new_quest.get('objective', {})
                                details = ""
                                if quest_type == 'kill': details = f" (Target: {objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')})"
                                elif quest_type == 'fetch': details = f" (Item: {objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')})"
                                elif quest_type == 'deliver': details = f" (To: {objective.get('recipient_name', '?')})"
                                print(f"[QuestSys Debug]   -> Success: Generated {new_quest.get('instance_id')} [{quest_type.capitalize()} - {title}{details}]")
                        elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Duplicate quest generated.")
                    elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Generation returned None.")

        # Phase 2: Fill Remaining Slots Randomly
        if slots_to_fill > 0:
            if self.config.get("debug"): print(f"[QuestSys Debug] Filling remaining {slots_to_fill} slots randomly...")
            while slots_to_fill > 0 and attempts < max_total_attempts:
                attempts += 1; quest_type = random.choice(required_types)
                if self.config.get("debug"): print(f"[QuestSys Debug] Generating random fill type: {quest_type} (Attempt {attempts}/{max_total_attempts})")

                new_quest = self.generate_quest(player.level, quest_type)
                if new_quest:
                    is_duplicate = any(q.get("title") == new_quest.get("title") for q in current_quests)
                    if not is_duplicate:
                        current_quests.append(new_quest); generated_count += 1; slots_to_fill -= 1
                        if self.config.get("debug"):
                            quest_type = new_quest.get('type', '?'); title = new_quest.get('title', 'N/A'); objective = new_quest.get('objective', {})
                            details = ""
                            if quest_type == 'kill': details = f" (Target: {objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')})"
                            elif quest_type == 'fetch': details = f" (Item: {objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')})"
                            elif quest_type == 'deliver': details = f" (To: {objective.get('recipient_name', '?')})"
                            print(f"[QuestSys Debug]   -> Success: Generated {new_quest.get('instance_id')} [{quest_type.capitalize()} - {title}{details}]")
                    elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Duplicate quest generated.")
                elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Generation returned None.")

        # Final Update
        if generated_count > 0:
            board_data["available_quests"] = current_quests
            self.world.set_plugin_data(self.plugin_id, self.quest_board_key, board_data)
            print(f"[QuestSys] Added {generated_count} new quests to the board. Board now has {len(current_quests)} quests.")
        elif slots_to_fill > 0:
            print(f"[QuestSys] Warning: Could not fill all {slots_to_fill} required slots after {attempts} attempts.")

    def replenish_board(self, completed_quest_instance_id: Optional[str]):
        if not self.world: return
        player = self.world.player
        if not player: return

        board_data = self.world.get_plugin_data(self.plugin_id, self.quest_board_key)
        if not board_data or "available_quests" not in board_data: return

        available_quests = board_data["available_quests"]
        max_quests = self.config.get("max_quests_on_board", 5)
        required_types = ["kill", "fetch", "deliver"]

        if completed_quest_instance_id:
            available_quests = [q for q in available_quests if q.get("instance_id") != completed_quest_instance_id]
            board_data["available_quests"] = available_quests

        if len(available_quests) >= max_quests: return

        current_types = {q.get("type") for q in available_quests}
        missing_types = [t for t in required_types if t not in current_types]
        quest_type = random.choice(missing_types) if missing_types else random.choice(required_types)

        new_quest = None; attempts = 0
        while not new_quest and attempts < 5:
            attempts += 1
            generated = self.generate_quest(player.level, quest_type)
            if generated and not any(q.get("title") == generated.get("title") for q in available_quests):
                new_quest = generated
        
        if new_quest:
            available_quests.append(new_quest)
            self.world.set_plugin_data(self.plugin_id, self.quest_board_key, board_data)
            print(f"[QuestSys] Replenished board with new {new_quest.get('type')} quest.")
        else:
            print(f"[QuestSys] Warning: Failed to generate replacement quest.")

    def generate_quest(self, player_level: int, quest_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.world: return None # Guard clause for world
        if quest_type is None: quest_type = random.choice(["kill", "fetch", "deliver"])
        
        giver_instance_id = self._select_giver_npc(quest_type)
        if not giver_instance_id:
            if self.config.get("debug"): print(f"[QuestSys Debug] No suitable giver for quest type {quest_type}")
            return None

        giver_npc = self.world.get_npc(giver_instance_id)
        if not giver_npc: return None

        objective_data = None
        if quest_type == "kill": objective_data = self._generate_kill_objective(player_level, giver_npc)
        elif quest_type == "fetch": objective_data = self._generate_fetch_objective(player_level, giver_npc)
        elif quest_type == "deliver": objective_data = self._generate_deliver_objective(player_level, giver_npc)

        if not objective_data:
            if self.config.get("debug"): print(f"[QuestSys Debug] Failed to generate objective for {quest_type} from {giver_npc.name}")
            return None

        quest_instance = {"instance_id": f"{quest_type}_{giver_npc.template_id}_{uuid.uuid4().hex[:6]}", "type": quest_type, "giver_instance_id": giver_instance_id, "objective": objective_data, "state": "available"}
        quest_instance["rewards"] = self._calculate_rewards(quest_instance)
        quest_instance["title"] = self._format_quest_text("title", quest_instance, giver_npc)
        quest_instance["description"] = self._format_quest_text("description", quest_instance, giver_npc)
        return quest_instance

    def _select_giver_npc(self, quest_type: str) -> Optional[str]:
        if not self.world: return None # Guard clause for world
        potential_givers = []
        if not hasattr(self, 'npc_interests'): self._load_npc_interests()

        interest_map = self.config.get("quest_type_interest_map", {})
        required_interests = interest_map.get(quest_type, [])
        if not required_interests:
            print(f"{FORMAT_ERROR}[QuestSys] No interests mapped for quest type '{quest_type}'.{FORMAT_RESET}")
            return None

        for npc_instance_id, npc in self.world.npcs.items():
            if (npc and npc.is_alive and npc.faction != "hostile" and
                npc.properties.get("can_give_generic_quests")):
                template_id = getattr(npc, 'template_id', None)
                # FIX: Ensure template_id is not None before using it as a key
                if template_id:
                    npc_template_interests = self.npc_interests.get(template_id, [])
                    if any(interest in npc_template_interests for interest in required_interests):
                        potential_givers.append(npc_instance_id)

        return random.choice(potential_givers) if potential_givers else None

    def _generate_kill_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        if not self.world or not hasattr(self.world, 'npc_templates'): return None
        level_range = self.config.get("quest_level_range_player", 3)
        min_lvl = max(self.config.get("quest_level_min", 1), player_level - level_range)
        max_lvl = player_level + level_range
        valid_targets = [tid for tid, t in self.world.npc_templates.items() if isinstance(t, dict) and t.get("faction") == "hostile" and min_lvl <= t.get("level", 1) <= max_lvl]
        if not valid_targets: return None
        selected_tid = random.choice(valid_targets)
        target_template = self.world.npc_templates.get(selected_tid, {})
        giver_region = self.world.get_region(giver_npc.current_region_id) if giver_npc.current_region_id else None
        location_hint = f"the area around {giver_region.name}" if giver_region else "nearby regions"
        qty_base = self.config.get("kill_quest_quantity_base", 3)
        qty_per_lvl = self.config.get("kill_quest_quantity_per_level", 0.5)
        required_qty = max(1, int(qty_base + (player_level * qty_per_lvl) + random.uniform(-1, 1)))
        return {"target_template_id": selected_tid, "target_name_plural": simple_plural(target_template.get("name", selected_tid)), "required_quantity": required_qty, "current_quantity": 0, "location_hint": location_hint, "difficulty_level": target_template.get("level", 1)}

    def _generate_fetch_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        if not self.world or not hasattr(self.world, 'item_templates') or not hasattr(self.world, 'npc_templates'): return None
        level_range = self.config.get("quest_level_range_player", 3)
        min_mob_lvl, max_mob_lvl = max(1, player_level - level_range), player_level + level_range
        valid_options = []
        for item_id, item_template in self.world.item_templates.items():
            if not isinstance(item_template, dict) or item_template.get("type") in ["Key"]: continue
            sources = []
            for mob_tid, mob_template in self.world.npc_templates.items():
                if isinstance(mob_template, dict) and mob_template.get("faction") == "hostile" and min_mob_lvl <= mob_template.get("level", 1) <= max_mob_lvl:
                    if item_id in mob_template.get("loot_table", {}):
                        spawner = self.service_locator.get_service("plugin:monster_spawner_plugin") if self.service_locator else None
                        if spawner:
                            for region_id, monsters in spawner.config.get("region_monsters", {}).items():
                                if mob_tid in monsters and not self.world.is_location_safe(region_id):
                                    sources.append((mob_tid, mob_template.get("level", 1), region_id)); break
            if sources:
                source_mob_tid, source_mob_level, region_id = random.choice(sources)
                valid_options.append((item_id, source_mob_tid, source_mob_level, region_id))
        if not valid_options: return None
        item_id, source_mob_tid, source_mob_level, region_id = random.choice(valid_options)
        item_template = self.world.item_templates.get(item_id, {})
        source_mob_template = self.world.npc_templates.get(source_mob_tid, {})
        region = self.world.get_region(region_id)
        location_hint = region.name if region else region_id
        qty_base = self.config.get("fetch_quest_quantity_base", 5)
        qty_per_lvl = self.config.get("fetch_quest_quantity_per_level", 1)
        required_qty = max(1, int(qty_base + (player_level * qty_per_lvl) + random.uniform(-1, 2)))
        return {"item_id": item_id, "item_name": item_template.get("name", item_id), "item_name_plural": simple_plural(item_template.get("name", item_id)), "required_quantity": required_qty, "current_quantity": 0, "source_enemy_name_plural": simple_plural(source_mob_template.get("name", source_mob_tid)), "location_hint": location_hint, "difficulty_level": item_template.get("value", 1) * required_qty // 2}

    def _generate_deliver_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        if not self.world: return None
        recipients = [rid for rid, r in self.world.npcs.items() if r and r.is_alive and r.faction != "hostile" and rid != giver_npc.obj_id and getattr(r, 'template_id', None) != "wandering_villager"]
        if not recipients: return None
        recipient_id = random.choice(recipients)
        recipient_npc = self.world.get_npc(recipient_id)
        if not recipient_npc: return None
        package_template_id = "quest_package_generic"
        package_instance_id = f"delivery_{giver_npc.obj_id[:4]}_{recipient_id[:4]}_{uuid.uuid4().hex[:4]}"
        package_template = self.world.item_templates.get(package_template_id, {})
        item_name = package_template.get("name", "Package")
        item_desc = f"A package for {recipient_npc.name} from {giver_npc.name}."
        region_name = self.world.get_region(recipient_npc.current_region_id).name if recipient_npc.current_region_id and self.world.get_region(recipient_npc.current_region_id) else recipient_npc.current_region_id
        room_name = self.world.get_region(recipient_npc.current_region_id).get_room(recipient_npc.current_room_id).name if recipient_npc.current_region_id and recipient_npc.current_room_id and self.world.get_region(recipient_npc.current_region_id) and self.world.get_region(recipient_npc.current_region_id).get_room(recipient_npc.current_room_id) else recipient_npc.current_room_id
        location_desc = f"{region_name} ({room_name})"
        return {"item_template_id": package_template_id, "item_instance_id": package_instance_id, "item_to_deliver_name": item_name, "item_to_deliver_description": item_desc, "recipient_instance_id": recipient_id, "recipient_name": recipient_npc.name, "recipient_location_description": location_desc, "difficulty_level": 5 + package_template.get("value", 1)}

    def _calculate_rewards(self, quest_instance: Dict[str, Any]) -> Dict[str, int]:
        base_xp = self.config.get("reward_base_xp", 50); xp_per_lvl = self.config.get("reward_xp_per_level", 15); xp_per_qty = self.config.get("reward_xp_per_quantity", 5)
        base_gold = self.config.get("reward_base_gold", 10); gold_per_lvl = self.config.get("reward_gold_per_level", 5); gold_per_qty = self.config.get("reward_gold_per_quantity", 2)
        objective = quest_instance.get("objective", {}); difficulty = objective.get("difficulty_level", 1); quantity = objective.get("required_quantity", 1); q_type = quest_instance.get("type")
        xp = base_xp + (difficulty * xp_per_lvl); gold = base_gold + (difficulty * gold_per_lvl)
        if q_type in ["kill", "fetch"]: xp += quantity * xp_per_qty; gold += quantity * gold_per_qty
        elif q_type == "deliver": xp *= 1.5; gold *= 1.2
        return {"xp": max(1, int(xp)), "gold": max(0, int(gold))}

    def _format_quest_text(self, text_type: str, quest_instance: Dict[str, Any], giver_npc: NPC) -> str:
        objective = quest_instance.get("objective", {})
        template_map = {"kill": {"title": "Bounty: {target_name_plural}", "description": "{giver_name} is offering a bounty for slaying {quantity} {target_name_plural} sighted in {location_description}."}, "fetch": {"title": "Gather: {item_name_plural}", "description": "{giver_name} needs {quantity} {item_name_plural}. They believe {source_enemy_name_plural} in {location_description} may carry them."}, "deliver": {"title": "Delivery: {item_to_deliver_name} to {recipient_name}", "description": "{giver_name} asks you to deliver a {item_to_deliver_name} to {recipient_name}, who can be found in {recipient_location_description}."}}
        quest_type = quest_instance.get("type")
        # FIX: Ensure quest_type is not None before dictionary access
        if not quest_type: return f"Quest {text_type}"
        format_template = template_map.get(quest_type, {}).get(text_type, f"Quest {text_type}")
        details = {"giver_name": giver_npc.name, "quantity": objective.get("required_quantity"), "target_name_plural": objective.get("target_name_plural"), "item_name": objective.get("item_name"), "item_name_plural": objective.get("item_name_plural"), "source_enemy_name_plural": objective.get("source_enemy_name_plural"), "location_description": objective.get("location_hint"), "item_to_deliver_name": objective.get("item_to_deliver_name"), "recipient_name": objective.get("recipient_name"), "recipient_location_description": objective.get("recipient_location_description")}
        valid_details = {k: v for k, v in details.items() if v is not None}
        try: return format_template.format(**valid_details)
        except KeyError as e: return f"Error formatting quest {text_type} ({e})"

    def _handle_npc_killed(self, event_type: str, data: Dict[str, Any]):
        player = data.get("player"); killed_npc = data.get("npc")
        if not self.world or not player or not killed_npc or not hasattr(player, 'quest_log'): return
        killed_template_id = getattr(killed_npc, 'template_id', None)
        if not killed_template_id: return
        for quest_id, quest_data in list(player.quest_log.items()):
            if quest_data.get("state") == "active" and quest_data.get("type") == "kill":
                objective = quest_data.get("objective", {})
                if objective.get("target_template_id") == killed_template_id:
                    objective["current_quantity"] = objective.get("current_quantity", 0) + 1
                    required = objective.get("required_quantity", 1)
                    player.update_quest(quest_id, quest_data)
                    message = f"{FORMAT_HIGHLIGHT}[Quest Update]{FORMAT_RESET} {quest_data.get('title', 'Task')}: ({objective['current_quantity']}/{required} killed)."
                    if objective["current_quantity"] >= required:
                        quest_data["state"] = "ready_to_complete"
                        player.update_quest(quest_id, quest_data)
                        giver = self.world.get_npc(quest_data.get("giver_instance_id"))
                        giver_name = giver.name if giver else "the quest giver"
                        message = f"{FORMAT_HIGHLIGHT}[Quest Update]{FORMAT_RESET} {quest_data.get('title', 'Task')}: Objective complete! Report back to {giver_name}."
                    if self.event_system: self.event_system.publish("display_message", message)

    def _handle_item_obtained(self, event_type: str, data: Dict[str, Any]):
        pass

    def cleanup(self):
        if self.event_system:
             self.event_system.unsubscribe("npc_killed", self._handle_npc_killed)
             self.event_system.unsubscribe("item_obtained", self._handle_item_obtained)
        print("[QuestSys] Quest System plugin cleaned up.")

    def _load_npc_interests(self):
        if not self.world or not hasattr(self.world, 'npc_templates'):
            print(f"{FORMAT_ERROR}[QuestSys] Cannot load NPC interests: World/templates missing.{FORMAT_RESET}")
            return
        config_interests = self.config.get("npc_quest_interests", {})
        for template_id, template_data in self.world.npc_templates.items():
            if not isinstance(template_data, dict): continue
            interests = template_data.get("properties", {}).get("quest_interests")
            if interests is None: interests = config_interests.get(template_id)
            if isinstance(interests, list): self.npc_interests[template_id] = [str(i) for i in interests if isinstance(i, str)]