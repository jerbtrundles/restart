# core/quest_manager.py
import json
import os
import time
import random
import uuid
from typing import TYPE_CHECKING, Dict, Any, List, Optional

from config import (
    FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, MAX_QUESTS_ON_BOARD, QUEST_SYSTEM_CONFIG, QUEST_TYPES_ALL, QUEST_TYPES_NO_INSTANCE
)
from npcs.npc_factory import NPCFactory
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
        self.instance_quest_templates: Dict[str, Any] = {}

        self._load_instance_quest_templates()

    def _load_instance_quest_templates(self):
        """Loads instance quest definitions from the dedicated JSON file."""
        # 1. Define the path to your quest data file
        file_path = os.path.join("data", "quests", "instances.json")
        if not os.path.exists(file_path):
            if self.config.get("debug"):
                print(f"[QuestManager Debug] Instance quest file not found at '{file_path}'.")
            return
        
        try:
            # 2. Open and read the file
            with open(file_path, 'r') as f:
                data = json.load(f)
                
                # 3. Filter and store the quests in the dictionary
                # It iterates through all entries in the JSON and only keeps the ones
                # that have "type": "instance".
                self.instance_quest_templates = {
                    quest_id: quest_data for quest_id, quest_data in data.items()
                    if quest_data.get("type") == "instance"
                }
            if self.config.get("debug"):
                print(f"[QuestManager Debug] Loaded {len(self.instance_quest_templates)} instance quest templates.")
        except Exception as e:
            print(f"{FORMAT_ERROR}[QuestManager] Error loading instance quests from {file_path}: {e}{FORMAT_RESET}")

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
        if not self.world or not self.world.player: return

        player = self.world.player
        current_quests = self.world.quest_board

        slots_to_fill = max(0, MAX_QUESTS_ON_BOARD - len(current_quests))
        if slots_to_fill == 0:
            return

        possible_types = QUEST_TYPES_ALL
        generated_count = 0
        
        # --- Phase 1: Ensure Variety ---
        # This phase tries to add one of each missing quest type.
        current_types_on_board = {q.get("type") for q in current_quests}
        types_to_ensure = [t for t in possible_types if t not in current_types_on_board]
        
        for specific_type in types_to_ensure:
            if slots_to_fill <= 0: break
            new_quest = None
            
            if specific_type == "instance":
                new_quest = self._generate_instance_quest(player.level)
            else:
                new_quest = self.generate_noninstance_quest(player.level, specific_type)

            if new_quest:
                current_quests.append(new_quest)
                generated_count += 1
                slots_to_fill -= 1

        # --- Phase 2: Fill Remaining Slots ---
        # This phase fills the rest of the board randomly.
        while slots_to_fill > 0:
            quest_type = random.choice(possible_types)
            new_quest = None

            if quest_type == "instance":
                new_quest = self._generate_instance_quest(player.level)
            else:
                new_quest = self.generate_noninstance_quest(player.level, quest_type)

            print(new_quest)

            if new_quest:
                current_quests.append(new_quest)
                generated_count += 1
                slots_to_fill -= 1
        
        if self.config.get("debug") and generated_count > 0:
            print(f"[QuestManager Debug]   -> Generated {generated_count} quests to fill board.")

    def replenish_board(self, completed_quest_instance_id: Optional[str]):
        """
        Removes a completed quest and refills the board, prioritizing instance quests if one is missing.
        """
        if not self.world or not self.world.player: return

        # Remove the just-completed quest from the board's list
        if completed_quest_instance_id:
            self.world.quest_board = [q for q in self.world.quest_board if q.get("instance_id") != completed_quest_instance_id]

        # --- START OF MODIFICATION ---
        # Instead of generating one simple quest, call the full "ensure" logic.
        # This will check if an instance quest is missing and add one, then fill
        # the remaining slots with basic quests.
        self.ensure_initial_quests()
        
        if self.config.get("debug"):
            if completed_quest_instance_id:
                print(f"[QuestManager Debug] Replenished board after quest '{completed_quest_instance_id}' was completed.")
            else:
                print(f"[QuestManager Debug] Replenished board.")
        # --- END OF MODIFICATION ---

    def generate_noninstance_quest(self, player_level: int, quest_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.world: return None
        if quest_type is None: quest_type = random.choice(QUEST_TYPES_NO_INSTANCE)
        
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

    def _generate_instance_quest(self, player_level: int) -> Optional[Dict[str, Any]]:
        """Selects and formats a suitable instance quest from loaded templates."""

        if not self.instance_quest_templates: return None
        if not self.world or not self.world.regions: return None

        valid_quests = [
            (qid, qd) for qid, qd in self.instance_quest_templates.items()
            if qd.get("level", 1) <= player_level
        ]
        if not valid_quests: return None

        chosen_quest_id, chosen_template = random.choice(valid_quests)
        
        if self.world.game: # and self.world.game.debug_mode:
            print(f"[QuestManager DEBUG] Generating instance from template: '{chosen_quest_id}'")

        quest_instance = chosen_template.copy()
        quest_instance["instance_id"] = f"{chosen_quest_id}_{uuid.uuid4().hex[:6]}"
        quest_instance["state"] = "available"
        quest_instance["giver_instance_id"] = "quest_board"

        # --- START OF DYNAMIC GENERATION ---
        
        # 1. Randomly select the creature for this instance
        possible_creatures = chosen_template.get("objective", {}).get("possible_target_template_ids", [])
        if not possible_creatures:
            print(f"{FORMAT_ERROR}[QuestManager] Quest template '{chosen_quest_id}' has no possible creatures defined.{FORMAT_RESET}")
            return None
        chosen_creature_id = random.choice(possible_creatures)
        
        # Store the chosen creature in the objective so the completion check knows what to look for
        quest_instance["objective"]["target_template_id"] = chosen_creature_id

        # 2. Generate a dynamic title based on the chosen creature
        creature_template = self.world.npc_templates.get(chosen_creature_id)
        if creature_template:
            creature_name = creature_template.get("name", "Creatures")
            quest_instance["title"] = f"Bounty: {simple_plural(creature_name).title()} Infestation"
        
        # 3. Generate a random house layout using the chosen creature
        layout_config = chosen_template.get("layout_generation_config", {})
        instance_definition = self._generate_random_house_layout(quest_instance["instance_id"], layout_config, chosen_creature_id)
        if not instance_definition:
            print(f"{FORMAT_ERROR}[QuestManager] Failed to generate random layout for quest '{chosen_quest_id}'.{FORMAT_RESET}")
            return None
        quest_instance["instance_definition"] = instance_definition

        # --- (Rest of the function is unchanged, selecting a random entry point) ---
        possible_regions = chosen_template.get("possible_entry_regions", ["town"])
        valid_entry_points = []
        for region_id in possible_regions:
            region = self.world.get_region(region_id)
            if region:
                for room_id, room in region.rooms.items():
                    if self.world.is_location_outdoors(region_id, room_id):
                        valid_entry_points.append({"region_id": region_id, "room_id": room_id})
        
        if not valid_entry_points:
            print(f"{FORMAT_ERROR}[QuestManager] No valid OUTDOOR entry points found for quest '{chosen_quest_id}' in regions {possible_regions}.{FORMAT_RESET}")
            return None

        chosen_entry = random.choice(valid_entry_points)

        
        if self.world.game: # and self.world.game.debug_mode:
            print(f"[QuestManager DEBUG]   -> Selected entry point: {chosen_entry['region_id']}:{chosen_entry['room_id']}")
            
        entry_point_data = {
            **chosen_entry,
            "exit_command": "house",
            "description_when_visible": "A previously unnoticed, rundown house stands here, a hastily scrawled notice about an infestation tacked to its door."
        }
        quest_instance["entry_point"] = entry_point_data

        return quest_instance

    def _generate_random_house_layout(self, instance_id: str, config: Dict[str, Any], chosen_creature_id: str) -> Dict[str, Any]:
        """Procedurally generates a simple, multi-room house layout."""
        # determine a random number of creatures to spawn
        count_range = config.get("target_count", [2, 4])
        num_to_spawn = random.randint(count_range[0], count_range[1])
        
        num_rooms = random.randint(config.get("min_rooms", 2), config.get("max_rooms", 4))
        room_names = random.sample(config.get("possible_room_names", ["Room", "Chamber"]), k=num_rooms)
        
        print(f"[QuestManager DEBUG]   -> Generating layout with {num_rooms} rooms...")
        print(f"[QuestManager DEBUG]   -> Spawning {num_to_spawn} of '{chosen_creature_id}'")

        layout = { "region_name": config.get("region_name", "Mysterious House"), "region_description": config.get("region_description", "A strange, temporary place."), "properties": {"indoors": True}, "rooms": {} }
        room_ids = [f"room_{i}" for i in range(num_rooms)]
        for i, room_id in enumerate(room_ids):
            layout["rooms"][room_id] = { "name": room_names[i], "description": f"A dusty and forgotten {room_names[i].lower()}. Cobwebs hang from the ceiling.", "exits": {} }
        for i in range(num_rooms - 1):
            dir1, dir2 = random.choice([("north", "south"), ("east", "west"), ("down", "up")])
            layout["rooms"][room_ids[i]]["exits"][dir1] = room_ids[i+1]
            layout["rooms"][room_ids[i+1]]["exits"][dir2] = room_ids[i]
            
        first_room_id = room_ids[0]
        layout["rooms"][first_room_id]["exits"]["out"] = "dynamic_exit"
        
        last_room_id = room_ids[-1]
        layout["rooms"][last_room_id]["spawner"] = {
            "initial_spawn": [{"template_id": chosen_creature_id, "count": num_to_spawn}]
        }
        
        if self.world.game and self.world.game.debug_mode:
            print(f"[QuestManager DEBUG]   -> Layout complete. Spawner in '{last_room_id}'.")
            
        return layout

    def check_quest_completion(self):
        """
        Iterates through active quests and updates their state if objectives are met.
        This is called by the World's main update loop.
        """
        if not self.world or not self.world.player or not self.world.player.quest_log:
            return

        # Iterate over a copy of the items to allow for modification during the loop
        for quest_id, quest_data in list(self.world.player.quest_log.items()):
            # --- Check for "clear_region" objective completion ---
            if (quest_data.get("state") == "active" and 
                quest_data.get("objective", {}).get("type") == "clear_region"):
                
                objective = quest_data.get("objective", {})
                instance_region_id = quest_data.get("instance_region_id")
                target_template_id = objective.get("target_template_id")

                if not instance_region_id or not target_template_id:
                    continue

                # Count how many of the target NPCs are still alive in the instance
                hostiles_remaining = sum(
                    1 for npc in self.world.npcs.values()
                    if npc.is_alive and 
                       npc.current_region_id == instance_region_id and 
                       npc.template_id == target_template_id
                )

                # --- If all hostiles are defeated, complete the objective ---
                if hostiles_remaining == 0:
                    quest_data["state"] = "ready_to_complete"
                    
                    # Despawn the original quest giver
                    original_giver_id = quest_data.get("giver_instance_id")
                    if original_giver_id and original_giver_id in self.world.npcs:
                        del self.world.npcs[original_giver_id]

                    # Spawn the completion NPC in the same spot
                    completion_npc_tid = objective.get("completion_npc_template_id")
                    if completion_npc_tid:
                        entry_point = quest_data.get("entry_point", {})
                        spawn_region = entry_point.get("region_id")
                        spawn_room = entry_point.get("room_id")
                        
                        if spawn_region and spawn_room:
                            completion_npc = NPCFactory.create_npc_from_template(
                                completion_npc_tid, self.world, original_giver_id,
                                current_region_id=spawn_region,
                                current_room_id=spawn_room
                            )
                            if completion_npc:
                                self.world.add_npc(completion_npc)
                                
                                # Announce the change if the player is there to see it
                                if (self.world.game and self.world.player.current_region_id == spawn_region and
                                    self.world.player.current_room_id == spawn_room):
                                    self.world.game.renderer.add_message(
                                        f"{FORMAT_HIGHLIGHT}The homeowner returns, looking much more cheerful now that the noise from the cellar has stopped.{FORMAT_RESET}"
                                    )