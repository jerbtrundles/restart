# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Fixed a bug where newly spawned NPCs had their current health set to the template's base value
#   instead of their calculated maximum health.
# - The logic now correctly sets `npc.health = npc.max_health` for new spawns,
#   while still respecting the saved health value when loading a game.

import inspect
import random
import time
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from core.config import (
    FORMAT_ERROR, FORMAT_RESET,
    NPC_BASE_HEALTH, NPC_BASE_XP_TO_LEVEL, NPC_CON_HEALTH_MULTIPLIER, NPC_DEFAULT_AGGRESSION, NPC_DEFAULT_FLEE_THRESHOLD, NPC_DEFAULT_MOVE_COOLDOWN, NPC_DEFAULT_RESPAWN_COOLDOWN, NPC_DEFAULT_SPELL_CAST_CHANCE, NPC_DEFAULT_WANDER, NPC_LEVEL_HEALTH_BASE_INCREASE, NPC_LEVEL_CON_HEALTH_MULTIPLIER, NPC_XP_TO_LEVEL_MULTIPLIER, VILLAGER_FIRST_NAMES_FEMALE, VILLAGER_FIRST_NAMES_MALE, VILLAGER_LAST_NAMES
)
from items.item_factory import ItemFactory
from npcs.npc import NPC
from items.inventory import Inventory

if TYPE_CHECKING:
    from world.world import World

class NPCFactory:
    """Factory class for creating NPCs from templates."""
    
    @staticmethod
    def get_template_names(world: 'World') -> List[str]:
        """Get a list of available NPC template names from the world."""
        if world and hasattr(world, 'npc_templates'):
             return list(world.npc_templates.keys())
        return []

    @staticmethod
    def get_template(template_id: str, world: 'World') -> Optional[Dict[str, Any]]:
         """Get a copy of an NPC template from the world."""
         if world and hasattr(world, 'npc_templates'):
              template = world.npc_templates.get(template_id)
              return template.copy() if template else None
         return None
    
    @staticmethod
    def create_npc_from_template(template_id: str, world: 'World', instance_id: Optional[str] = None, **overrides) -> Optional[NPC]:
        """Creates an NPC instance from a template ID and applies overrides."""
        if not world or not hasattr(world, 'npc_templates'):
            print(f"{FORMAT_ERROR}Error: World context with npc_templates required.{FORMAT_RESET}")
            return None

        template = world.npc_templates.get(template_id)
        if not template:
            print(f"{FORMAT_ERROR}Error: NPC template '{template_id}' not found.{FORMAT_RESET}")
            return None

        try:
            creation_args = template.copy()
            npc_instance_id = instance_id if instance_id else f"{template_id}_{uuid.uuid4().hex[:8]}"
            creation_args.update(overrides)

            final_npc_name = overrides.get("name")
            if not final_npc_name:
                if template_id == "wandering_villager":
                    first_names = VILLAGER_FIRST_NAMES_MALE + VILLAGER_FIRST_NAMES_FEMALE
                    if first_names and VILLAGER_LAST_NAMES:
                        final_npc_name = f"{random.choice(first_names)} {random.choice(VILLAGER_LAST_NAMES)}"
                    else:
                        final_npc_name = template.get("name", "Villager")
                else:
                    final_npc_name = template.get("name", "Unknown NPC")

            init_args = {
                "obj_id": npc_instance_id,
                "name": final_npc_name,
                "description": creation_args.get("description", "No description"),
                "level": overrides.get("level", template.get("level", 1)),
                "friendly": creation_args.get("friendly", True),
            }
            npc = NPC(**init_args)
            npc.template_id = template_id

            base_stats = npc.stats.copy()
            template_stats = template.get("stats", {})
            saved_stats = overrides.get("stats", {})
            npc.stats = {**base_stats, **template_stats, **saved_stats}

            npc.level = init_args["level"]
            final_con = npc.stats.get('constitution', 8)
            base_hp = NPC_BASE_HEALTH + int(final_con * NPC_CON_HEALTH_MULTIPLIER)
            level_hp_bonus = (npc.level - 1) * (NPC_LEVEL_HEALTH_BASE_INCREASE + int(final_con * NPC_LEVEL_CON_HEALTH_MULTIPLIER))
            npc.max_health = base_hp + level_hp_bonus

            # --- FIX: Set health correctly for new vs. loaded NPCs ---
            # Prioritize health from saved data (overrides). If not present (a new spawn), default to max_health.
            npc.health = overrides.get("health", npc.max_health)
            npc.health = max(0, min(npc.health, npc.max_health)) # Clamp value to be safe
            # --- END FIX ---

            npc.experience = overrides.get("experience", 0)
            npc.experience_to_level = overrides.get("experience_to_level", int(NPC_BASE_XP_TO_LEVEL * (NPC_XP_TO_LEVEL_MULTIPLIER**(npc.level - 1))))

            npc.faction = creation_args.get("faction", npc.faction)
            npc.behavior_type = creation_args.get("behavior_type", npc.behavior_type)
            npc.attack_power = creation_args.get("attack_power", 3) + npc.stats.get('strength', 8) // 3
            npc.defense = creation_args.get("defense", 2)

            npc.current_region_id = creation_args.get("current_region_id")
            npc.current_room_id = creation_args.get("current_room_id")
            npc.home_region_id = creation_args.get("home_region_id", npc.current_region_id)
            npc.home_room_id = creation_args.get("home_room_id", npc.current_room_id)

            npc.dialog = creation_args.get("dialog", {}).copy()
            npc.default_dialog = creation_args.get("default_dialog", npc.default_dialog)

            npc.loot_table = creation_args.get("loot_table", {}).copy()
            npc.usable_spells = creation_args.get("usable_spells", [])[:]
            npc.schedule = creation_args.get("schedule", {}).copy()
            npc.patrol_index = creation_args.get("patrol_index", 0)
            npc.patrol_points = creation_args.get("patrol_points", [])[:]

            npc.is_alive = overrides.get("is_alive", npc.is_alive) if npc.health > 0 else False
            npc.ai_state = overrides.get("ai_state", {}).copy()
            npc.spell_cooldowns = overrides.get("spell_cooldowns", {}).copy()

            npc.properties = template.get("properties", {}).copy()
            prop_overrides = overrides.get("properties_override", {})
            npc.properties.update(prop_overrides)

            npc.aggression = npc.properties.get("aggression", NPC_DEFAULT_AGGRESSION)
            npc.flee_threshold = npc.properties.get("flee_threshold", NPC_DEFAULT_FLEE_THRESHOLD)
            npc.respawn_cooldown = npc.properties.get("respawn_cooldown", NPC_DEFAULT_RESPAWN_COOLDOWN)
            npc.wander_chance = npc.properties.get("wander_chance", NPC_DEFAULT_WANDER)
            npc.move_cooldown = npc.properties.get("move_cooldown", NPC_DEFAULT_MOVE_COOLDOWN)
            npc.spell_cast_chance = npc.properties.get("spell_cast_chance", NPC_DEFAULT_SPELL_CAST_CHANCE)
            
            saved_inv_data = overrides.get("inventory")
            if saved_inv_data and isinstance(saved_inv_data, dict):
                npc.inventory = Inventory.from_dict(saved_inv_data, world)
            else:
                npc.inventory = Inventory(max_slots=10, max_weight=50.0)
                template_inventory = template.get("initial_inventory", [])
                for item_ref in template_inventory:
                    item_id = item_ref.get("item_id")
                    quantity = item_ref.get("quantity", 1)
                    if item_id:
                        item = ItemFactory.create_item_from_template(item_id, world)
                        if item: npc.inventory.add_item(item, quantity)

            npc.world = world
            return npc

        except Exception as e:
            print(f"{FORMAT_ERROR}Error instantiating NPC '{template_id}' from template: {e}{FORMAT_RESET}")
            import traceback
            traceback.print_exc()
            return None