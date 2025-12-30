# engine/core/quest_generator.py
import random
import uuid
from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple

from engine.config import (
    FORMAT_ERROR, FORMAT_RESET, QUEST_TYPES_NO_INSTANCE
)
from engine.utils.utils import simple_plural
from engine.npcs.npc import NPC

if TYPE_CHECKING:
    from engine.world.world import World
    from engine.core.quest_manager import QuestManager

class QuestGenerator:
    def __init__(self, world: 'World', quest_manager: 'QuestManager'):
        self.world = world
        self.qm = quest_manager

    def generate_noninstance_quest(self, player_level: int, quest_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if not self.world: return None
        if quest_type is None: quest_type = random.choice(QUEST_TYPES_NO_INSTANCE)
        
        giver_instance_id = self._select_giver_npc(quest_type)
        if not giver_instance_id: return None

        giver_npc = self.world.get_npc(giver_instance_id)
        if not giver_npc: return None

        objective_data = None
        if quest_type == "kill": objective_data = self._generate_kill_objective(player_level, giver_npc)
        elif quest_type == "fetch": objective_data = self._generate_fetch_objective(player_level, giver_npc)
        elif quest_type == "deliver": objective_data = self._generate_deliver_objective(player_level, giver_npc)

        if not objective_data: return None

        quest_instance = {"instance_id": f"{quest_type}_{giver_npc.template_id}_{uuid.uuid4().hex[:6]}", "type": quest_type, "giver_instance_id": giver_instance_id, "objective": objective_data, "state": "available"}
        quest_instance["rewards"] = self._calculate_rewards(quest_instance)
        quest_instance["title"] = self._format_quest_text("title", quest_instance, giver_npc)
        quest_instance["description"] = self._format_quest_text("description", quest_instance, giver_npc)
        return quest_instance

    def generate_instance_quest(self, player_level: int) -> Optional[Dict[str, Any]]:
        if not self.qm.instance_quest_templates: return None
        if not self.world or not self.world.regions: return None

        valid_quests = [
            (qid, qd) for qid, qd in self.qm.instance_quest_templates.items()
            if qd.get("level", 1) <= player_level
        ]
        if not valid_quests: return None

        chosen_quest_id, chosen_template = random.choice(valid_quests)
        
        quest_instance = chosen_template.copy()
        # Deep copy objective to avoid modifying template
        if 'objective' in chosen_template:
             quest_instance['objective'] = chosen_template['objective'].copy()
        else:
             quest_instance['objective'] = {}
        
        quest_instance["instance_id"] = f"{chosen_quest_id}_{uuid.uuid4().hex[:6]}"
        quest_instance["state"] = "available"
        quest_instance["giver_instance_id"] = "quest_board"

        possible_creatures = quest_instance.get("objective", {}).get("possible_target_template_ids", [])
        if not possible_creatures:
            print(f"{FORMAT_ERROR}[QuestGenerator] Quest template '{chosen_quest_id}' has no possible creatures defined.{FORMAT_RESET}")
            return None
        chosen_creature_id = random.choice(possible_creatures)
        
        quest_instance["objective"]["target_template_id"] = chosen_creature_id

        creature_template = self.world.npc_templates.get(chosen_creature_id)
        if creature_template:
            creature_name = creature_template.get("name", "Creatures")
            quest_instance["title"] = f"Bounty: {simple_plural(creature_name).title()} Infestation"
        
        layout_config = chosen_template.get("layout_generation_config", {})
        instance_region = self._generate_random_house_layout(layout_config)
        if not instance_region:
            print(f"{FORMAT_ERROR}[QuestGenerator] Failed to generate random layout for quest '{chosen_quest_id}'.{FORMAT_RESET}")
            return None
        quest_instance["instance_region"] = instance_region

        possible_regions = chosen_template.get("possible_entry_regions", ["town"])
        valid_entry_points = []
        for region_id in possible_regions:
            region = self.world.get_region(region_id)
            if region:
                for room_id, room in region.rooms.items():
                    if self.world.is_location_outdoors(region_id, room_id):
                        valid_entry_points.append({"region_id": region_id, "room_id": room_id})
        
        if not valid_entry_points:
            print(f"{FORMAT_ERROR}[QuestGenerator] No valid OUTDOOR entry points found for quest '{chosen_quest_id}' in regions {possible_regions}.{FORMAT_RESET}")
            return None

        chosen_entry = random.choice(valid_entry_points)
            
        entry_point_data = {
            **chosen_entry,
            "exit_command": "house",
            "description_when_visible": "A previously unnoticed, rundown house stands here, a hastily scrawled notice about an infestation tacked to its door."
        }
        quest_instance["entry_point"] = entry_point_data

        return quest_instance

    def _select_giver_npc(self, quest_type: str) -> Optional[str]:
        if not self.world: return None
        potential_givers = []
        
        for npc_instance in self.world.npcs.values():
            if (npc_instance and npc_instance.is_alive and npc_instance.faction != "hostile" and
                    npc_instance.properties.get("can_give_generic_quests")):
                
                template_id = getattr(npc_instance, 'template_id', None)
                if not template_id: continue

                npc_template_interests = self.qm.npc_interests.get(template_id, [])
                if quest_type in npc_template_interests:
                    potential_givers.append(npc_instance.obj_id)

        if not potential_givers:
            if self.qm.config.get("debug"):
                print(f"{FORMAT_ERROR}[QuestGenerator Debug] Could not find any valid quest givers for a '{quest_type}' quest.{FORMAT_RESET}")
            return None

        return random.choice(potential_givers)

    def _generate_kill_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        if not self.world or not hasattr(self.world, 'npc_templates'): return None
        level_range = self.qm.config.get("quest_level_range_player", 3)
        min_lvl, max_lvl = max(1, player_level - level_range), player_level + level_range
        
        valid_targets = [tid for tid, t in self.world.npc_templates.items() if t.get("faction") == "hostile" and min_lvl <= t.get("level", 1) <= max_lvl]
        if not valid_targets: return None
        
        selected_tid = random.choice(valid_targets)
        target_template = self.world.npc_templates[selected_tid]
        
        if not (giver_npc.current_region_id): return None
        giver_region = self.world.get_region(giver_npc.current_region_id)
        location_hint = f"the area around {giver_region.name}" if giver_region else "nearby regions"
        
        qty = max(1, int(self.qm.config.get("kill_quest_quantity_base", 3) + (player_level * self.qm.config.get("kill_quest_quantity_per_level", 0.5))))
        
        return {
            "target_template_id": selected_tid,
            "target_name_plural": simple_plural(target_template.get("name", selected_tid)),
            "required_quantity": qty, "current_quantity": 0, "location_hint": location_hint,
            "difficulty_level": target_template.get("level", 1)
        }

    def _generate_fetch_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        if not self.world: return None
        level_range = self.qm.config.get("quest_level_range_player", 3)
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
        
        qty = max(1, int(self.qm.config.get("fetch_quest_quantity_base", 5) + (player_level * self.qm.config.get("fetch_quest_quantity_per_level", 1))))
        
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
        
        xp = self.qm.config.get("reward_base_xp", 50) + (difficulty * self.qm.config.get("reward_xp_per_level", 15))
        gold = self.qm.config.get("reward_base_gold", 10) + (difficulty * self.qm.config.get("reward_gold_per_level", 5))
        
        if q_type in ["kill", "fetch"]:
            xp += quantity * self.qm.config.get("reward_xp_per_quantity", 5)
            gold += quantity * self.qm.config.get("reward_gold_per_quantity", 2)
        
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
            },
            "instance": {
                "title": "Bounty: Clear out the {target_name_plural}",
                "description": "{giver_name} has posted a bounty to clear out an infestation of {target_name_plural} from a nearby location."
            }
        }
        
        q_type = quest_instance.get("type", "")
        objective = quest_instance.get("objective", {})
        template = templates.get(q_type, {}).get(text_type, "Quest")

        if q_type == "instance" and "target_name_plural" not in objective:
            target_tid = objective.get("target_template_id")
            if target_tid and self.world:
                target_template = self.world.npc_templates.get(target_tid)
                if target_template:
                    target_name = target_template.get("name", "creatures")
                    objective["target_name_plural"] = simple_plural(target_name)

        details = {
            "giver_name": giver_npc.name,
            "quantity": objective.get("required_quantity"),
            "target_name_plural": objective.get("target_name_plural"),
            "location_description": objective.get("location_hint"),
            "item_name_plural": objective.get("item_name_plural"),
            "source_enemy_name_plural": objective.get("source_enemy_name_plural"),
            "item_to_deliver_name": objective.get("item_to_deliver_name"),
            "recipient_name": objective.get("recipient_name"),
            "recipient_location_description": objective.get("recipient_location_description")
        }

        valid_details = {k: v for k, v in details.items() if v is not None}
        
        try:
            return template.format(**valid_details)
        except KeyError as e:
            print(f"{FORMAT_ERROR}[QuestGenerator Error] Formatting quest text failed for type '{q_type}'. Missing key: {e}{FORMAT_RESET}")
            return "Error: Could not generate quest text."

    def _generate_random_house_layout(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates a non-linear, branching, and GEOMETRICALLY CONSISTENT layout
        for an instance region using a grid-based random walk algorithm.
        """
        num_rooms = random.randint(config.get("min_rooms", 3), config.get("max_rooms", 7))
        possible_room_names = config.get("possible_room_names", ["Room", "Chamber", "Hallway"])

        # Prepare room names
        if len(possible_room_names) < num_rooms:
            room_names = random.choices(possible_room_names, k=num_rooms)
        else:
            room_names = random.sample(possible_room_names, k=num_rooms)
        
        # Helper data structures for grid generation
        direction_vectors = {"north": (0, -1), "south": (0, 1), "east": (1, 0), "west": (-1, 0)}
        opposite_direction = {"north": "south", "south": "north", "east": "west", "west": "east"}
        
        # Grid state
        coords_to_id: Dict[Tuple[int, int], str] = {}
        id_to_coords: Dict[str, Tuple[int, int]] = {}
        rooms_data: Dict[str, Any] = {}
        
        # 1. Place the first room (the entrance)
        start_room_id = f"room_0"
        coords_to_id[(0, 0)] = start_room_id
        id_to_coords[start_room_id] = (0, 0)
        rooms_data[start_room_id] = {
            "name": room_names[0],
            "description": f"The entrance. A dusty and forgotten {room_names[0].lower()}.",
            "exits": {"out": "dynamic_exit"} # The way back to the main world
        }
        
        # Frontier of rooms to expand from
        frontier = [start_room_id]

        # 2. Grow the dungeon until the desired number of rooms is placed
        for i in range(1, num_rooms):
            new_room_id = f"room_{i}"
            connection_made = False
            
            # Try to connect to a random frontier room to encourage branching
            random.shuffle(frontier)
            for current_room_id in frontier:
                cx, cy = id_to_coords[current_room_id]
                
                # Find valid, empty adjacent grid cells
                possible_directions = []
                for direction, (dx, dy) in direction_vectors.items():
                    if (cx + dx, cy + dy) not in coords_to_id:
                        possible_directions.append(direction)
                
                if possible_directions:
                    # Choose a random direction to build in
                    chosen_direction = random.choice(possible_directions)
                    nx, ny = cx + direction_vectors[chosen_direction][0], cy + direction_vectors[chosen_direction][1]
                    
                    # Place the new room
                    coords_to_id[(nx, ny)] = new_room_id
                    id_to_coords[new_room_id] = (nx, ny)
                    rooms_data[new_room_id] = {
                        "name": room_names[i],
                        "description": f"A dusty and forgotten {room_names[i].lower()}.",
                        "exits": {}
                    }
                    
                    # Connect the two rooms
                    rooms_data[current_room_id]["exits"][chosen_direction] = new_room_id
                    rooms_data[new_room_id]["exits"][opposite_direction[chosen_direction]] = current_room_id
                    
                    # Add the new room to the frontier for further expansion
                    frontier.append(new_room_id)
                    connection_made = True
                    break # Stop trying to connect this new room, move to the next
            
            if not connection_made:
                # This can happen if the frontier gets boxed in. We'll just have fewer rooms.
                if self.qm.config.get("debug"):
                    print(f"[QuestGenerator Debug] Could not place room {i + 1}/{num_rooms}. Dungeon is boxed in.")
                break

        # 3. Add extra connections to create loops and make the layout more interesting
        num_extra_connections = random.randint(num_rooms // 3, num_rooms - 1)
        for _ in range(num_extra_connections):
            # Pick a random room that isn't a dead end (has at least one potential connection)
            room_id = random.choice(list(id_to_coords.keys()))
            cx, cy = id_to_coords[room_id]
            
            # Find neighbors that exist but are not yet connected
            possible_connections = []
            for direction, (dx, dy) in direction_vectors.items():
                neighbor_coords = (cx + dx, cy + dy)
                if neighbor_coords in coords_to_id and direction not in rooms_data[room_id]["exits"]:
                    possible_connections.append(direction)
            
            if possible_connections:
                chosen_direction = random.choice(possible_connections)
                neighbor_id = coords_to_id[(cx + direction_vectors[chosen_direction][0], cy + direction_vectors[chosen_direction][1])]
                
                # Add the new connection
                rooms_data[room_id]["exits"][chosen_direction] = neighbor_id
                rooms_data[neighbor_id]["exits"][opposite_direction[chosen_direction]] = room_id

        # Finalize the layout structure
        layout = {
            "region_name": config.get("region_name", "Mysterious Location"),
            "region_description": config.get("region_description", "A strange, temporary place."),
            "properties": {"outdoors": False},
            "rooms": rooms_data,
        }
        
        return layout