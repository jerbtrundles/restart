# engine/core/quest_manager.py
import json
import os
import random
from typing import TYPE_CHECKING, Dict, Any, List, Optional

from engine.config import (
    FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, MAX_QUESTS_ON_BOARD, QUEST_SYSTEM_CONFIG, QUEST_TYPES_ALL
)
from engine.npcs.npc_factory import NPCFactory
from engine.core.quest_generator import QuestGenerator

if TYPE_CHECKING:
    from engine.world.world import World

class QuestManager:
    def __init__(self, world: 'World'):
        self.world = world
        self.config = QUEST_SYSTEM_CONFIG.copy()
        self.npc_interests: Dict[str, List[str]] = {}
        self.instance_quest_templates: Dict[str, Any] = {}
        
        self.generator = QuestGenerator(world, self)

        self._load_instance_quest_templates()

    def _load_instance_quest_templates(self):
        """Loads instance quest definitions from the dedicated JSON file."""
        file_path = os.path.join("data", "quests", "instances.json")
        if not os.path.exists(file_path):
            if self.config.get("debug"):
                print(f"[QuestManager Debug] Instance quest file not found at '{file_path}'.")
            return
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
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
        current_types_on_board = {q.get("type") for q in current_quests}
        types_to_ensure = [t for t in possible_types if t not in current_types_on_board]
        
        for specific_type in types_to_ensure:
            if slots_to_fill <= 0: break
            new_quest = None
            
            if specific_type == "instance":
                new_quest = self.generator.generate_instance_quest(player.level)
            else:
                new_quest = self.generator.generate_noninstance_quest(player.level, specific_type)

            if new_quest:
                current_quests.append(new_quest)
                generated_count += 1
                slots_to_fill -= 1

        # --- Phase 2: Fill Remaining Slots ---
        while slots_to_fill > 0:
            quest_type = random.choice(possible_types)
            new_quest = None

            if quest_type == "instance":
                new_quest = self.generator.generate_instance_quest(player.level)
            else:
                new_quest = self.generator.generate_noninstance_quest(player.level, quest_type)

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

        if completed_quest_instance_id:
            self.world.quest_board = [q for q in self.world.quest_board if q.get("instance_id") != completed_quest_instance_id]

        self.ensure_initial_quests()
        
        if self.config.get("debug"):
            if completed_quest_instance_id:
                print(f"[QuestManager Debug] Replenished board after quest '{completed_quest_instance_id}' was completed.")
            else:
                print(f"[QuestManager Debug] Replenished board.")

    def handle_npc_killed(self, event_type: str, data: Dict[str, Any]) -> Optional[str]:
        player = data.get("player")
        killed_npc = data.get("npc")
        if not self.world or not player or not killed_npc or not hasattr(player, 'quest_log'): return None
        
        killed_template_id = getattr(killed_npc, 'template_id', None)
        if not killed_template_id: return None
        
        messages = []
        
        # Iterate over all quests to allow multiple updates per kill
        for quest_id, quest_data in list(player.quest_log.items()):
            if quest_data.get("type") == "kill" and quest_data.get("state") == "active":
                objective = quest_data.get("objective", {})
                if objective.get("target_template_id") == killed_template_id:
                    current_quest_in_log = player.quest_log[quest_id]
                    current_objective = current_quest_in_log.get("objective", {})
                    
                    current_objective["current_quantity"] = current_objective.get("current_quantity", 0) + 1
                    required = current_objective.get("required_quantity", 1)
                    
                    if current_objective["current_quantity"] >= required:
                        current_quest_in_log["state"] = "ready_to_complete"
                        giver = self.world.get_npc(quest_data.get("giver_instance_id"))
                        giver_name = giver.name if giver else "the quest giver"
                        messages.append(f"{FORMAT_HIGHLIGHT}[Quest Update]{FORMAT_RESET} {quest_data.get('title', 'Task')}: Objective complete! Report back to {giver_name}.")
                    else:
                        messages.append(f"{FORMAT_HIGHLIGHT}[Quest Update]{FORMAT_RESET} {quest_data.get('title', 'Task')}: ({current_objective['current_quantity']}/{required} killed).")
        
        return "\n".join(messages) if messages else None

    def check_quest_completion(self):
        if not self.world or not self.world.player or not self.world.player.quest_log:
            return

        for quest_id, quest_data in list(self.world.player.quest_log.items()):
            if (quest_data.get("state") == "active" and
                quest_data.get("objective", {}).get("type") == "clear_region" and
                quest_data.get("completion_check_enabled", False)):
                
                objective = quest_data.get("objective", {})
                instance_region_id = quest_data.get("instance_region_id")
                target_template_id = objective.get("target_template_id")

                if not instance_region_id or not target_template_id:
                    continue

                hostiles_remaining = sum(
                    1 for npc in self.world.npcs.values()
                    if npc.is_alive and 
                       npc.current_region_id == instance_region_id and 
                       npc.template_id == target_template_id
                )

                if hostiles_remaining == 0:
                    if self.world.game and self.world.game.renderer:
                        completion_npc_tid = objective.get("completion_npc_template_id")
                        completion_npc_template = self.world.npc_templates.get(completion_npc_tid)
                        completion_npc_name = completion_npc_template.get("name", "the quest giver") if completion_npc_template else "the quest giver"
                        
                        instance_region = quest_data.get("instance_region", {})
                        instance_name = instance_region.get("region_name", "area")

                        message = f"{FORMAT_HIGHLIGHT}[Quest Update] You have cleared the {instance_name}! Report back to {completion_npc_name} outside.{FORMAT_RESET}"
                        self.world.game.renderer.add_message(message)

                    quest_data["state"] = "ready_to_complete"
                    
                    original_giver_id = quest_data.get("giver_instance_id")
                    if original_giver_id and original_giver_id in self.world.npcs:
                        del self.world.npcs[original_giver_id]

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
                                if (self.world.game and self.world.player.current_region_id == spawn_region and
                                    self.world.player.current_room_id == spawn_room):
                                    self.world.game.renderer.add_message(
                                        f"{FORMAT_HIGHLIGHT}The homeowner returns, looking much more cheerful now that the noise from the cellar has stopped.{FORMAT_RESET}"
                                    )