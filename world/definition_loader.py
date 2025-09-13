# world/definition_loader.py
"""
Handles loading all game definitions from JSON files and initializing a new world state.
"""
import json
import os
import uuid
from typing import TYPE_CHECKING

from core.config import (FORMAT_ERROR, FORMAT_RESET, ITEM_TEMPLATE_DIR,
                         NPC_TEMPLATE_DIR, REGION_DIR)
from items.item_factory import ItemFactory
from npcs.npc_factory import NPCFactory
from npcs.npc_schedules import initialize_npc_schedules
from player import Player
from world.region import Region

if TYPE_CHECKING:
    from world.world import World


def load_all_definitions(world: 'World'):
    """Populates the world's template dictionaries by loading from disk."""
    print("Loading definitions...")
    _load_item_templates(world)
    _load_npc_templates(world)
    world.quest_manager._load_npc_interests()
    _load_regions(world)
    print("Definitions loaded.")

def _load_item_templates(world: 'World'):
    world.item_templates = {}
    if not os.path.isdir(ITEM_TEMPLATE_DIR):
        print(f"Warning: Item template directory not found: {ITEM_TEMPLATE_DIR}")
        return
    for filename in os.listdir(ITEM_TEMPLATE_DIR):
        if filename.endswith(".json"):
            path = os.path.join(ITEM_TEMPLATE_DIR, filename)
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    for item_id, template_data in data.items():
                        if item_id in world.item_templates:
                            print(f"Warning: Duplicate item template ID '{item_id}' found in {filename}.")
                        if "name" not in template_data or "type" not in template_data:
                            print(f"Warning: Item template '{item_id}' in {filename} is missing 'name' or 'type'. Skipping.")
                            continue
                        world.item_templates[item_id] = template_data
            except Exception as e:
                print(f"Error loading item templates from {path}: {e}")

def _load_npc_templates(world: 'World'):
    world.npc_templates = {}
    if not os.path.isdir(NPC_TEMPLATE_DIR):
        print(f"Warning: NPC template directory not found: {NPC_TEMPLATE_DIR}")
        return
    for filename in os.listdir(NPC_TEMPLATE_DIR):
        if filename.endswith(".json"):
            path = os.path.join(NPC_TEMPLATE_DIR, filename)
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    for template_id, template_data in data.items():
                        if template_id in world.npc_templates:
                            print(f"Warning: Duplicate NPC template ID '{template_id}' found in {filename}.")
                        if "name" not in template_data:
                            print(f"Warning: NPC template '{template_id}' in {filename} is missing 'name'. Skipping.")
                            continue
                        world.npc_templates[template_id] = template_data
            except Exception as e:
                print(f"Error loading NPC templates from {path}: {e}")
    print(f"[NPC Templates] Loaded {len(world.npc_templates)} NPC templates.")

def _load_regions(world: 'World'):
    world.regions = {}
    if not os.path.isdir(REGION_DIR):
        print(f"Warning: Region directory not found: {REGION_DIR}")
        return
    for filename in os.listdir(REGION_DIR):
        if filename.endswith(".json"):
            path = os.path.join(REGION_DIR, filename)
            try:
                with open(path, 'r') as f:
                    region_data = json.load(f)
                    region_id = filename[:-5]
                    region_data['obj_id'] = region_id
                    region = Region.from_dict(region_data)
                    world.add_region(region_id, region)
            except Exception as e:
                print(f"Error loading region from {path}: {e}")

def initialize_new_world(world: 'World', start_region="town", start_room="town_square"):
    print("Initializing new world state...")
    world.player = Player("Adventurer")
    world.player.world = world
    starter_dagger = ItemFactory.create_item_from_template("item_starter_dagger", world)
    potion = ItemFactory.create_item_from_template("item_healing_potion_small", world)
    if starter_dagger: world.player.inventory.add_item(starter_dagger)
    if potion: world.player.inventory.add_item(potion, 2)

    world.current_region_id = start_region
    world.current_room_id = start_room
    if world.player:
        world.player.current_region_id = start_region
        world.player.current_room_id = start_room

    world.npcs = {}
    world.respawn_manager.respawn_queue = []
    
    # Clear and populate initial room items and NPCs from definitions
    npcs_created_count = 0
    for region_id, region in world.regions.items():
        for room_id, room in region.rooms.items():
            room.items = [] # Clear items from previous sessions
            for item_ref in getattr(room, 'initial_item_refs', []):
                item = ItemFactory.create_item_from_template(item_ref.get("item_id"), world, **item_ref.get("properties_override", {}))
                if item: room.add_item(item)
            for npc_ref in getattr(room, 'initial_npc_refs', []):
                instance_id = npc_ref.get("instance_id", f"{npc_ref.get('template_id')}_{uuid.uuid4().hex[:8]}")
                if npc_ref.get("template_id") and instance_id not in world.npcs:
                    overrides = {"current_region_id": region_id, "current_room_id": room_id, "home_region_id": region_id, "home_room_id": room_id}
                    npc = NPCFactory.create_npc_from_template(npc_ref.get("template_id"), world, instance_id, **overrides)
                    if npc:
                        world.add_npc(npc)
                        npcs_created_count += 1

    if npcs_created_count == 0:
        print(f"{FORMAT_ERROR}[World Warning] No initial NPCs were spawned. The world may feel empty.{FORMAT_RESET}")

    world.quest_board = []
    initialize_npc_schedules(world)
    world.quest_manager.ensure_initial_quests()
    
    print(f"New world initialized. Player at {start_region}:{start_room}")