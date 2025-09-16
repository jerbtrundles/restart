# npcs/npc_factory.py

import inspect
import random
import time
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional, Any

from config import (
    FORMAT_ERROR, FORMAT_RESET, NPC_BASE_HEALTH, NPC_BASE_XP_TO_LEVEL, NPC_CON_HEALTH_MULTIPLIER, NPC_DEFAULT_AGGRESSION,
    NPC_DEFAULT_FLEE_THRESHOLD, NPC_DEFAULT_MAX_MANA, NPC_DEFAULT_MOVE_COOLDOWN, NPC_DEFAULT_RESPAWN_COOLDOWN,
    NPC_DEFAULT_SPELL_CAST_CHANCE, NPC_DEFAULT_WANDER, NPC_LEVEL_CON_HEALTH_MULTIPLIER, NPC_LEVEL_HEALTH_BASE_INCREASE,
    NPC_XP_TO_LEVEL_MULTIPLIER, VILLAGER_FIRST_NAMES_FEMALE, VILLAGER_FIRST_NAMES_MALE
)
from items.item_factory import ItemFactory
from .npc import NPC
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
                if template_id in ["wandering_villager", "wandering_mage", "wandering_priest"]:
                    # Select a random first name
                    first_names = VILLAGER_FIRST_NAMES_MALE + VILLAGER_FIRST_NAMES_FEMALE
                    random_first_name = random.choice(first_names) if first_names else "Wanderer"
                    
                    # Determine the title from the template's base name
                    # e.g., "Wandering Villager" -> "Villager"
                    base_title = template.get("name", "Villager").split(" ")[-1]
                    
                    final_npc_name = f"{random_first_name} the {base_title}"
                else:
                    # Fallback for all other NPCs (like monsters, quest givers, etc.)
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
            final_int = npc.stats.get('intelligence', 5)

            # Health Calculation (unchanged)
            # TODO: standardize either stat-based or explicit values for health, mana
            base_hp = NPC_BASE_HEALTH + int(final_con * NPC_CON_HEALTH_MULTIPLIER)
            level_hp_bonus = (npc.level - 1) * (NPC_LEVEL_HEALTH_BASE_INCREASE + int(final_con * NPC_LEVEL_CON_HEALTH_MULTIPLIER))
            npc.max_health = base_hp + level_hp_bonus

            # Set health and mana correctly for new vs. loaded NPCs
            npc.health = overrides.get("health", npc.max_health)
            npc.health = max(1, min(npc.health, npc.max_health))
            # common hostiles start with default max mana
            npc.mana = template.get("mana", NPC_DEFAULT_MAX_MANA)
            npc.max_mana = npc.mana

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
            npc.usable_spells = []
            npc.schedule = creation_args.get("schedule", {}).copy()

            template_props = template.get("properties", {})
            
            if "required_spells" in template_props:
                for spell_id in template_props["required_spells"]:
                    if spell_id not in npc.usable_spells:
                        npc.usable_spells.append(spell_id)
            
            if "random_spells" in template_props:
                spell_config = template_props["random_spells"]
                pool = spell_config.get("pool", [])
                count_range = spell_config.get("count", [1, 1])
                num_to_learn = random.randint(count_range[0], count_range[1])
                
                available_to_learn = [s for s in pool if s not in npc.usable_spells]
                
                if available_to_learn and num_to_learn > 0:
                    spells_learned = random.sample(available_to_learn, min(num_to_learn, len(available_to_learn)))
                    npc.usable_spells.extend(spells_learned)

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
                # --- REPLACE THIS ENTIRE BLOCK ---
                npc.inventory = Inventory(max_slots=10, max_weight=50.0)
                template_inventory = template.get("initial_inventory", [])
                
                # NEW: Add safety checks
                if isinstance(template_inventory, list):
                    for item_ref in template_inventory:
                        # Check that the item reference itself is a dictionary
                        if not isinstance(item_ref, dict):
                            print(f"Warning: Invalid item reference in initial_inventory for NPC '{template.get('name')}': not a dictionary. Skipping.")
                            continue

                        item_id = item_ref.get("item_id")
                        quantity = item_ref.get("quantity", 1)

                        # Check that item_id is a valid, non-empty string
                        if item_id and isinstance(item_id, str):
                            item = ItemFactory.create_item_from_template(item_id, world)
                            if item:
                                npc.inventory.add_item(item, quantity)
                        else:
                            # This debug message will pinpoint the exact problem
                            print(f"Warning: Skipping invalid item reference in initial_inventory for NPC '{template.get('name')}': {item_ref}")
                else:
                    print(f"Warning: 'initial_inventory' for NPC '{template.get('name')}' is not a list. Skipping inventory creation.")
                # --- END REPLACEMENT BLOCK ---

            npc.world = world

            print("[NPCFactory create_npc_from_template()]")
            print(f"Spawning {npc.name} - {npc.health}/{npc.max_health}hp {npc.current_region_id} - {npc.current_room_id}")

            return npc

        except Exception as e:
            print(f"{FORMAT_ERROR}Error instantiating NPC '{template_id}' from template: {e}{FORMAT_RESET}")
            import traceback
            traceback.print_exc()
            return None