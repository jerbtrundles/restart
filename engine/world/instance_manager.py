# engine/world/instance_manager.py
import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from engine.config import FORMAT_HIGHLIGHT, FORMAT_RESET
from engine.npcs.npc_factory import NPCFactory
from engine.world.region import Region
from engine.world.room import Room

if TYPE_CHECKING:
    from engine.world.world import World

class InstanceManager:
    def __init__(self, world: 'World'):
        self.world = world

    def instantiate_quest_region(self, quest_data: Dict[str, Any]) -> Tuple[bool, str, Optional[str]]:
        if not self.world.player:
            return False, "Cannot instantiate region without a player.", None

        try:
            entry_point = quest_data['entry_point']
            instance_region = quest_data['instance_region']
            quest_instance_id = quest_data['instance_id']
            objective = quest_data.get("objective", {})
            layout_config = quest_data.get("layout_generation_config", {})

            unique_region_id = f"instance_{quest_instance_id}"
            quest_data['instance_region_id'] = unique_region_id
            
            new_region = Region(
                obj_id=unique_region_id,
                name=instance_region['region_name'],
                description=instance_region['region_description']
            )
            new_region.properties = instance_region.get("properties", {})
            
            entry_room_id = ""
            for room_id, room_data in instance_region['rooms'].items():
                if not entry_room_id: entry_room_id = room_id
                for direction, exit_dest in list(room_data.get('exits', {}).items()):
                    if exit_dest == "dynamic_exit":
                        room_data['exits'][direction] = f"{entry_point['region_id']}:{entry_point['room_id']}"
                    elif ":" not in exit_dest:
                        room_data['exits'][direction] = f"{unique_region_id}:{exit_dest}"
                
                new_room = Room.from_dict(room_data)
                new_region.add_room(room_id, new_room)

            self.world.regions[unique_region_id] = new_region

            target_template_id = objective.get("target_template_id")
            target_count_range = layout_config.get("target_count", [2, 4])
            num_to_spawn = random.randint(target_count_range[0], target_count_range[1])
            spawnable_room_ids = [rid for rid in new_region.rooms.keys() if rid != entry_room_id]
            
            if not target_template_id: return False, f"Quest '{quest_instance_id}' has no target creature.", None
            
            for _ in range(num_to_spawn):
                if not spawnable_room_ids: break 
                chosen_room_id = random.choice(spawnable_room_ids)
                npc = NPCFactory.create_npc_from_template(
                    target_template_id, self.world,
                    current_region_id=unique_region_id, current_room_id=chosen_room_id
                )
                if not npc:
                    self.cleanup_quest_region(quest_instance_id) 
                    return False, f"Could not spawn required creature '{target_template_id}'.", None
                self.world.add_npc(npc)

            permanent_entry_region = self.world.get_region(entry_point['region_id'])
            if not permanent_entry_region: return False, "Could not get permanent entry region.", None
            permanent_entry_room = permanent_entry_region.get_room(entry_point['room_id'])
            exit_command = entry_point['exit_command']
            if permanent_entry_room:
                permanent_entry_room.exits[exit_command] = f"{unique_region_id}:{entry_room_id}"

            giver_npc_id = None
            spawn_message = "You decide to take on the task."
            giver_tid = quest_data.get("giver_npc_template_id")
            if giver_tid:
                giver_instance_id = f"giver_{quest_instance_id}"
                giver_npc = NPCFactory.create_npc_from_template(
                    giver_tid, self.world, giver_instance_id,
                    current_region_id=self.world.player.current_region_id,
                    current_room_id=self.world.player.current_room_id
                )
                if giver_npc:
                    self.world.add_npc(giver_npc)
                    giver_npc_id = giver_npc.obj_id
                    spawn_message = (f"{giver_npc.name} notices you taking their notice from the board and approaches you.\n"
                                     f"\"{giver_npc.dialog.get('greeting', 'Please help me!')}\"")
                else:
                    self.cleanup_quest_region(quest_instance_id) 
                    return False, f"Could not spawn giver NPC '{giver_tid}'.", None

            return True, spawn_message, giver_npc_id

        except KeyError as e: return False, f"Quest template is missing a required key: {e}", None
        except Exception as e:
            import traceback; traceback.print_exc()
            return False, f"An unexpected error occurred: {e}", None

    def cleanup_quest_region(self, quest_id: str):
        if not self.world.player or quest_id not in self.world.player.completed_quest_log: return
        quest_data = self.world.player.completed_quest_log[quest_id]
        instance_region_id = quest_data.get("instance_region_id")
        entry_point = quest_data.get("entry_point")

        if not instance_region_id or not entry_point: return

        perm_region = self.world.get_region(entry_point['region_id'])
        if perm_region:
            perm_room = perm_region.get_room(entry_point['room_id'])
            if perm_room and entry_point['exit_command'] in perm_room.exits:
                del perm_room.exits[entry_point['exit_command']]

        npcs_to_remove = [npc.obj_id for npc in self.world.npcs.values() if npc.current_region_id == instance_region_id]
        for npc_id in npcs_to_remove: del self.world.npcs[npc_id]
        if instance_region_id in self.world.regions: del self.world.regions[instance_region_id]
            
        del self.world.player.completed_quest_log[quest_id]
        if not hasattr(self.world.player, 'archived_quest_log'): self.world.player.archived_quest_log = {}
        self.world.player.archived_quest_log[quest_id] = quest_data

    def check_and_cleanup_completed_instances(self):
        if not self.world.player or not hasattr(self.world.player, 'completed_quest_log'): return
        for quest_id in list(self.world.player.completed_quest_log.keys()):
            quest_data = self.world.player.completed_quest_log[quest_id]
            if quest_data.get("type") == "instance":
                instance_id = quest_data.get("instance_region_id")
                if instance_id and self.world.player.current_region_id != instance_id:
                    self.cleanup_quest_region(quest_id)