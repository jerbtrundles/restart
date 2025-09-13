# core/quest_manager.py
import time
import random
import uuid
from typing import TYPE_CHECKING, Dict, Any, List, Optional

from core.config import FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, FORMAT_HIGHLIGHT, QUEST_SYSTEM_CONFIG
from utils.utils import simple_plural
from items.item_factory import ItemFactory
from player import Player
from npcs.npc import NPC

if TYPE_CHECKING:
    from world.world import World

class QuestManager:
    def __init__(self, world: 'World'):
        self.world = world
        self.config = QUEST_SYSTEM_CONFIG.copy()
        self.npc_interests: Dict[str, List[str]] = {}

    def _load_npc_interests(self):
        if not self.world or not hasattr(self.world, 'npc_templates'):
            print(f"{FORMAT_ERROR}[QuestManager] Cannot load NPC interests: World/templates missing.{FORMAT_RESET}")
            return

        if self.config.get("debug"):
            print(f"[QuestManager Debug] Loading quest interests from {len(self.world.npc_templates)} NPC templates...")

        config_interests = self.config.get("npc_quest_interests", {})
        for template_id, template_data in self.world.npc_templates.items():
            if not isinstance(template_data, dict): continue
            interests = template_data.get("properties", {}).get("quest_interests")
            if interests is None: interests = config_interests.get(template_id)
            if isinstance(interests, list): self.npc_interests[template_id] = [str(i) for i in interests if isinstance(i, str)]

    def ensure_initial_quests(self):
        if not self.world: return
        player = self.world.player
        if not player: return

        current_quests = self.world.quest_board
        current_count = len(current_quests)
        max_quests = self.config.get("max_quests_on_board", 5)
        required_types = ["kill", "fetch", "deliver"]
        slots_to_fill = max(0, max_quests - current_count)

        if slots_to_fill == 0:
            if self.config.get("debug"): print(f"[QuestManager Debug] Quest board is already full ({current_count}/{max_quests}).")
            return
        
        if self.config.get("debug"):
            print(f"[QuestManager Debug] Board has {current_count}/{max_quests} quests. Attempting to generate {slots_to_fill} more.")

        generated_count = 0
        current_types_on_board = {q.get("type") for q in current_quests}
        types_to_ensure = [t for t in required_types if t not in current_types_on_board]

        # Phase 1: Ensure Variety
        for specific_type in types_to_ensure:
            if slots_to_fill <= 0: break
            new_quest = self.generate_quest(player.level, specific_type)
            if new_quest and not any(q.get("title") == new_quest.get("title") for q in current_quests):
                current_quests.append(new_quest)
                generated_count += 1
                slots_to_fill -= 1
                # --- ADD DETAILED LOG ---
                if self.config.get("debug"):
                    quest_type = new_quest.get('type', '?'); title = new_quest.get('title', 'N/A'); objective = new_quest.get('objective', {})
                    details = ""
                    if quest_type == 'kill': details = f" (Target: {objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')})"
                    elif quest_type == 'fetch': details = f" (Item: {objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')})"
                    elif quest_type == 'deliver': details = f" (To: {objective.get('recipient_name', '?')})"
                    print(f"[QuestManager Debug]   -> Success: Generated {new_quest.get('instance_id')} [{quest_type.capitalize()} - {title}{details}]")
                # --- END DETAILED LOG ---

        # Phase 2: Fill Remaining Slots
        attempts = 0
        while slots_to_fill > 0 and attempts < slots_to_fill * 5:
            attempts += 1
            quest_type = random.choice(required_types)
            new_quest = self.generate_quest(player.level, quest_type)
            if new_quest and not any(q.get("title") == new_quest.get("title") for q in current_quests):
                current_quests.append(new_quest)
                generated_count += 1
                slots_to_fill -= 1
                # --- ADD DETAILED LOG ---
                if self.config.get("debug"):
                    quest_type = new_quest.get('type', '?'); title = new_quest.get('title', 'N/A'); objective = new_quest.get('objective', {})
                    details = ""
                    if quest_type == 'kill': details = f" (Target: {objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')})"
                    elif quest_type == 'fetch': details = f" (Item: {objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')})"
                    elif quest_type == 'deliver': details = f" (To: {objective.get('recipient_name', '?')})"
                    print(f"[QuestManager Debug]   -> Success: Generated {new_quest.get('instance_id')} [{quest_type.capitalize()} - {title}{details}]")
                # --- END DETAILED LOG ---
        
        if generated_count > 0:
            print(f"[QuestManager] Added {generated_count} new quests to the board.")

    def replenish_board(self, completed_quest_instance_id: Optional[str]):
        if not self.world or not self.world.player: return

        if completed_quest_instance_id:
            self.world.quest_board = [q for q in self.world.quest_board if q.get("instance_id") != completed_quest_instance_id]

        if len(self.world.quest_board) >= self.config.get("max_quests_on_board", 5):
            return

        new_quest = self.generate_quest(self.world.player.level)
        if new_quest:
            self.world.quest_board.append(new_quest)
            # <<< ADD DETAILED LOGGING >>>
            if self.config.get("debug"):
                quest_type = new_quest.get('type', '?'); title = new_quest.get('title', 'N/A'); objective = new_quest.get('objective', {})
                details = ""
                if quest_type == 'kill': details = f" (Target: {objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')})"
                elif quest_type == 'fetch': details = f" (Item: {objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')})"
                elif quest_type == 'deliver': details = f" (To: {objective.get('recipient_name', '?')})"
                print(f"[QuestManager Debug] Replenished board with new quest: [{quest_type.capitalize()} - {title}{details}]")
            # <<< END LOGGING >>>

    def generate_quest(self, player_level: int, quest_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.world: return None
        if quest_type is None: quest_type = random.choice(["kill", "fetch", "deliver"])
        
        print(f"Quest type: {quest_type}")
        
        giver_instance_id = self._select_giver_npc(quest_type)
        if not giver_instance_id: return None

        print(f"Giver instance id: {giver_instance_id}")

        giver_npc = self.world.get_npc(giver_instance_id)
        if not giver_npc: return None

        print(f"Giver npc: {giver_npc}")

        objective_data = None
        if quest_type == "kill": objective_data = self._generate_kill_objective(player_level, giver_npc)
        elif quest_type == "fetch": objective_data = self._generate_fetch_objective(player_level, giver_npc)
        elif quest_type == "deliver": objective_data = self._generate_deliver_objective(player_level, giver_npc)

        if not objective_data: return None

        print(f"Objective: {objective_data}")

        quest_instance = {"instance_id": f"{quest_type}_{giver_npc.template_id}_{uuid.uuid4().hex[:6]}", "type": quest_type, "giver_instance_id": giver_instance_id, "objective": objective_data, "state": "available"}
        quest_instance["rewards"] = self._calculate_rewards(quest_instance)
        quest_instance["title"] = self._format_quest_text("title", quest_instance, giver_npc)
        quest_instance["description"] = self._format_quest_text("description", quest_instance, giver_npc)
        return quest_instance

    def _select_giver_npc(self, quest_type: str) -> Optional[str]:
        if not self.world: return None
        potential_givers = []
        
        # This is the list of NPCs that have the "can_give_generic_quests" property.
        valid_npc_templates = self.npc_interests.keys()
        
        for npc_instance in self.world.npcs.values():
            # Filter for NPCs that are alive, not hostile, and have the quest giver property.
            if (npc_instance and npc_instance.is_alive and npc_instance.faction != "hostile" and
                    npc_instance.properties.get("can_give_generic_quests")):
                
                template_id = getattr(npc_instance, 'template_id', None)
                if not template_id: continue

                # Get the interests for this NPC's template (e.g., ["kill", "fetch"])
                npc_template_interests = self.npc_interests.get(template_id, [])

                # <<< FIX: Check if the broad quest_type is in the NPC's interest list. >>>
                # This correctly matches "kill" to the ["kill", "fetch", "deliver"] list.
                if quest_type in npc_template_interests:
                    potential_givers.append(npc_instance.obj_id)

        if not potential_givers:
            # <<< ADDED: Detailed logging for when no givers are found. >>>
            if self.config.get("debug"):
                print(f"{FORMAT_ERROR}[QuestManager Debug] Could not find any valid quest givers for a '{quest_type}' quest.{FORMAT_RESET}")
                print(f"  - Searched {len(self.world.npcs)} NPCs. Check if any are loaded, alive, and have 'can_give_generic_quests' set to true in their template.")
            return None

        return random.choice(potential_givers)

    def _generate_kill_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        if not self.world or not hasattr(self.world, 'npc_templates'): return None
        level_range = self.config.get("quest_level_range_player", 3)
        min_lvl, max_lvl = max(1, player_level - level_range), player_level + level_range
        
        valid_targets = [tid for tid, t in self.world.npc_templates.items() if t.get("faction") == "hostile" and min_lvl <= t.get("level", 1) <= max_lvl]
        if not valid_targets: return None
        
        selected_tid = random.choice(valid_targets)
        target_template = self.world.npc_templates[selected_tid]
        
        if not (giver_npc.current_region_id): return None
        giver_region = self.world.get_region(giver_npc.current_region_id)
        location_hint = f"the area around {giver_region.name}" if giver_region else "nearby regions"
        
        qty = max(1, int(self.config.get("kill_quest_quantity_base", 3) + (player_level * self.config.get("kill_quest_quantity_per_level", 0.5))))
        
        return {
            "target_template_id": selected_tid,
            "target_name_plural": simple_plural(target_template.get("name", selected_tid)),
            "required_quantity": qty, "current_quantity": 0, "location_hint": location_hint,
            "difficulty_level": target_template.get("level", 1)
        }

    def _generate_fetch_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        if not self.world: return None
        level_range = self.config.get("quest_level_range_player", 3)
        min_mob_lvl, max_mob_lvl = max(1, player_level - level_range), player_level + level_range
        valid_options = []
        for item_id, item_template in self.world.item_templates.items():
            if item_template.get("type") == "Key": continue
            for mob_tid, mob_template in self.world.npc_templates.items():
                if mob_template.get("faction") == "hostile" and min_mob_lvl <= mob_template.get("level", 1) <= max_mob_lvl:
                    if item_id in mob_template.get("loot_table", {}):
                        for region in self.world.regions.values():
                            if region.spawner_config and mob_tid in region.spawner_config.get("monster_types", {}) and not self.world.is_location_safe(region.obj_id):
                                valid_options.append((item_id, mob_tid, region.obj_id))
                                break
        if not valid_options: return None
        
        item_id, source_mob_tid, region_id = random.choice(valid_options)
        item_template = self.world.item_templates[item_id]
        source_mob_template = self.world.npc_templates[source_mob_tid]
        location_hint = self.world.regions[region_id].name
        
        qty = max(1, int(self.config.get("fetch_quest_quantity_base", 5) + (player_level * self.config.get("fetch_quest_quantity_per_level", 1))))
        
        return {
            "item_id": item_id, "item_name": item_template.get("name", item_id),
            "item_name_plural": simple_plural(item_template.get("name", item_id)),
            "required_quantity": qty, "current_quantity": 0,
            "source_enemy_name_plural": simple_plural(source_mob_template.get("name", source_mob_tid)),
            "location_hint": location_hint, "difficulty_level": item_template.get("value", 1) * qty
        }

    def _generate_deliver_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        if not self.world: return None
        recipients = [npc for npc in self.world.npcs.values() if npc.is_alive and npc.faction != "hostile" and npc.obj_id != giver_npc.obj_id]
        if not recipients: return None
        
        recipient_npc = random.choice(recipients)
        package_template = self.world.item_templates["quest_package_generic"]
        
        item_name = package_template.get("name", "Package")
        item_desc = f"A package for {recipient_npc.name} from {giver_npc.name}."

        if not recipient_npc.current_region_id: return None
        if not recipient_npc.current_room_id: return None
        
        region_name = self.world.regions[recipient_npc.current_region_id].name
        room_name = self.world.regions[recipient_npc.current_region_id].rooms[recipient_npc.current_room_id].name
        location_desc = f"{region_name} ({room_name})"
        
        return {
            "item_template_id": "quest_package_generic",
            "item_instance_id": f"delivery_{uuid.uuid4().hex[:4]}",
            "item_to_deliver_name": item_name, "item_to_deliver_description": item_desc,
            "recipient_instance_id": recipient_npc.obj_id, "recipient_name": recipient_npc.name,
            "recipient_location_description": location_desc, "difficulty_level": 5
        }

    def _calculate_rewards(self, quest_instance: Dict[str, Any]) -> Dict[str, int]:
        objective = quest_instance.get("objective", {})
        difficulty = objective.get("difficulty_level", 1)
        quantity = objective.get("required_quantity", 1)
        q_type = quest_instance.get("type")
        
        xp = self.config.get("reward_base_xp", 50) + (difficulty * self.config.get("reward_xp_per_level", 15))
        gold = self.config.get("reward_base_gold", 10) + (difficulty * self.config.get("reward_gold_per_level", 5))
        
        if q_type in ["kill", "fetch"]:
            xp += quantity * self.config.get("reward_xp_per_quantity", 5)
            gold += quantity * self.config.get("reward_gold_per_quantity", 2)
        
        return {"xp": int(xp), "gold": int(gold)}

    def _format_quest_text(self, text_type: str, quest_instance: Dict[str, Any], giver_npc: NPC) -> str:
        templates = {
            "kill": {
                "title": "Bounty: {target_name_plural}",
                "description": "{giver_name} is offering a bounty for slaying {quantity} {target_name_plural} sighted in {location_description}."
            },
            "fetch": {
                "title": "Gather: {item_name_plural}",
                "description": "{giver_name} needs {quantity} {item_name_plural}. They believe {source_enemy_name_plural} in {location_description} may carry them."
            },
            "deliver": {
                "title": "Delivery: {item_to_deliver_name} to {recipient_name}",
                "description": "{giver_name} asks you to deliver a {item_to_deliver_name} to {recipient_name}, who can be found in {recipient_location_description}."
            }
        }
        
        q_type = quest_instance.get("type", "")
        objective = quest_instance.get("objective", {})
        template = templates.get(q_type, {}).get(text_type, "Quest")

        # <<< FIX: Create a new 'details' dictionary that maps the objective data to the template's placeholder names >>>
        details = {
            "giver_name": giver_npc.name,
            # Mapping for kill/fetch quests
            "quantity": objective.get("required_quantity"),
            "target_name_plural": objective.get("target_name_plural"),
            "location_description": objective.get("location_hint"),
            "item_name_plural": objective.get("item_name_plural"),
            "source_enemy_name_plural": objective.get("source_enemy_name_plural"),
            # Mapping for deliver quests
            "item_to_deliver_name": objective.get("item_to_deliver_name"),
            "recipient_name": objective.get("recipient_name"),
            "recipient_location_description": objective.get("recipient_location_description")
        }

        # Filter out any keys that have a None value to prevent formatting errors
        valid_details = {k: v for k, v in details.items() if v is not None}
        
        try:
            return template.format(**valid_details)
        except KeyError as e:
            print(f"{FORMAT_ERROR}[QuestManager Error] Formatting quest text failed for type '{q_type}'. Missing key: {e}{FORMAT_RESET}")
            print(f"  - Template: {template}")
            print(f"  - Details provided: {valid_details}")
            return "Error: Could not generate quest text."
    
    def handle_npc_killed(self, event_type: str, data: Dict[str, Any]):
        player = data.get("player")
        killed_npc = data.get("npc")
        if not self.world or not player or not killed_npc or not hasattr(player, 'quest_log'): return
        
        killed_template_id = getattr(killed_npc, 'template_id', None)
        if not killed_template_id: return
        
        for quest_id, quest_data in list(player.quest_log.items()):
            if quest_data.get("type") == "kill" and quest_data.get("state") == "active":
                objective = quest_data.get("objective", {})
                if objective.get("target_template_id") == killed_template_id:
                    objective["current_quantity"] = objective.get("current_quantity", 0) + 1
                    required = objective.get("required_quantity", 1)
                    
                    message = f"{FORMAT_HIGHLIGHT}[Quest Update]{FORMAT_RESET} {quest_data.get('title', 'Task')}: ({objective['current_quantity']}/{required} killed)."
                    
                    if objective["current_quantity"] >= required:
                        quest_data["state"] = "ready_to_complete"
                        giver = self.world.get_npc(quest_data.get("giver_instance_id"))
                        giver_name = giver.name if giver else "the quest giver"
                        message = f"{FORMAT_HIGHLIGHT}[Quest Update]{FORMAT_RESET} {quest_data.get('title', 'Task')}: Objective complete! Report back to {giver_name}."

    def handle_item_obtained(self, event_type: str, data: Dict[str, Any]):
        # This can be expanded later to automatically update fetch quests.
        pass