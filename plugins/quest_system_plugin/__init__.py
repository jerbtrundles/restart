# plugins/quest_system_plugin/__init__.py
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
        board_data = self.world.get_plugin_data(self.plugin_id, self.quest_board_key)
        if board_data is None or not isinstance(board_data, dict) or "available_quests" not in board_data:
            self.world.set_plugin_data(self.plugin_id, self.quest_board_key, {"available_quests": []})
            print("[QuestSys] Initialized empty quest board state.")
        else:
            # Optional: Validate existing board data on load?
             print(f"[QuestSys] Found existing quest board state with {len(board_data['available_quests'])} quests.")


    def _register_event_listeners(self):
        """Subscribe to game events needed for quest tracking."""
        self.event_system.subscribe("npc_killed", self._handle_npc_killed)
        self.event_system.subscribe("item_obtained", self._handle_item_obtained)
        # We handle delivery turn-in via the 'talk' command modification later
        # self.event_system.subscribe("npc_talk", self._handle_npc_talk)

    def _register_commands(self):
        """Register commands related to the quest board."""
        from .commands import register_commands # Ensure this matches the function name in commands.py
        register_commands(self)

    def _ensure_initial_quests(self):
        """Ensure the board has a minimum number of quests and attempts to fill it, ensuring variety."""
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
        # Increase max attempts to give more chances for variety and filling
        max_total_attempts = (slots_to_fill * 5) + len(required_types) # More generous limit

        # --- Phase 1: Ensure Variety ---
        current_types_on_board = {q.get("type") for q in current_quests}
        types_to_ensure = [t for t in required_types if t not in current_types_on_board]

        if types_to_ensure:
            print(f"[QuestSys Debug] Ensuring missing basic types: {', '.join(types_to_ensure)}")
            for specific_type in types_to_ensure:
                if slots_to_fill <= 0: break # Stop if board becomes full

                type_attempts = 0
                max_type_attempts = 3 # Try a few times for each required type
                generated_this_type = False

                while not generated_this_type and type_attempts < max_type_attempts and slots_to_fill > 0 and attempts < max_total_attempts:
                    type_attempts += 1
                    attempts += 1 # Count towards overall limit
                    if self.config.get("debug"): print(f"[QuestSys Debug] Generating required type: {specific_type} (Attempt {type_attempts}/{max_type_attempts})")

                    new_quest = self.generate_quest(player.level, specific_type)
                    if new_quest:
                        # Check for duplicates (basic check)
                        is_duplicate = any(
                            existing_q.get("title") == new_quest.get("title") and
                            existing_q.get("giver_instance_id") == new_quest.get("giver_instance_id")
                            for existing_q in current_quests # Check against already added ones too
                        )
                        if not is_duplicate:
                            current_quests.append(new_quest) # Add directly to list being checked
                            generated_count += 1
                            slots_to_fill -= 1
                            generated_this_type = True # Move to next required type
                            if self.config.get("debug"):
                                # --- Enhanced Debug Print ---
                                quest_type = new_quest.get('type', '?')
                                title = new_quest.get('title', 'Unknown Title')
                                objective = new_quest.get('objective', {})
                                details = ""
                                if quest_type == 'kill':
                                    details = f" (Target: {objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')})"
                                elif quest_type == 'fetch':
                                    details = f" (Item: {objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')})"
                                elif quest_type == 'deliver':
                                    details = f" (To: {objective.get('recipient_name', '?')})"
                            print(f"[QuestSys Debug]   -> Success: Generated {new_quest.get('instance_id')} [{quest_type.capitalize()} - {title}{details}]")
                        elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Duplicate quest generated.")
                    elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Generation returned None.")

        # --- Phase 2: Fill Remaining Slots Randomly ---
        if slots_to_fill > 0:
            print(f"[QuestSys Debug] Filling remaining {slots_to_fill} slots randomly...")
            while slots_to_fill > 0 and attempts < max_total_attempts:
                attempts += 1
                quest_type = random.choice(required_types) # Choose from basic types
                if self.config.get("debug"): print(f"[QuestSys Debug] Generating random fill type: {quest_type} (Attempt {attempts}/{max_total_attempts})")

                new_quest = self.generate_quest(player.level, quest_type)
                if new_quest:
                    # Check for duplicates
                    is_duplicate = any(
                        existing_q.get("title") == new_quest.get("title") and
                        existing_q.get("giver_instance_id") == new_quest.get("giver_instance_id")
                        for existing_q in current_quests
                    )
                    if not is_duplicate:
                        current_quests.append(new_quest)
                        generated_count += 1
                        slots_to_fill -= 1
                        if self.config.get("debug"):
                            # --- Enhanced Debug Print ---
                            quest_type = new_quest.get('type', '?')
                            title = new_quest.get('title', 'Unknown Title')
                            objective = new_quest.get('objective', {})
                            details = ""
                            if quest_type == 'kill':
                                details = f" (Target: {objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')})"
                            elif quest_type == 'fetch':
                                details = f" (Item: {objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')})"
                            elif quest_type == 'deliver':
                                details = f" (To: {objective.get('recipient_name', '?')})"
                        print(f"[QuestSys Debug]   -> Success: Generated {new_quest.get('instance_id')} [{quest_type.capitalize()} - {title}{details}]")
                    elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Duplicate quest generated.")
                elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Generation returned None.")

        # --- Final Update ---
        if generated_count > 0:
            # Update the list in the board data dictionary
            board_data["available_quests"] = current_quests
            self.world.set_plugin_data(self.plugin_id, self.quest_board_key, board_data)
            print(f"[QuestSys] Added {generated_count} new quests to the board. Board now has {len(current_quests)} quests.")
        elif slots_to_fill > 0:
            print(f"[QuestSys] Warning: Could not fill all {slots_to_fill} required slots after {attempts} attempts.")

    def replenish_board(self, completed_quest_instance_id: Optional[str]): # Can be None if called without a specific completion
        """Generate a new quest, prioritizing missing basic types if the board isn't full."""
        # Ensure player exists
        player = self.world.player
        if not player:
            print(f"{FORMAT_ERROR}[QuestSys] Cannot replenish board: Player not found.{FORMAT_RESET}")
            return

        board_data = self.world.get_plugin_data(self.plugin_id, self.quest_board_key)
        if not board_data or "available_quests" not in board_data:
            print(f"{FORMAT_ERROR}[QuestSys] Cannot replenish board: Board data missing.{FORMAT_RESET}")
            return # Should exist, but safety check

        available_quests = board_data["available_quests"]
        max_quests = self.config.get("max_quests_on_board", 5)
        required_types = ["kill", "fetch", "deliver"]

        # --- Optional: Remove completed quest ID if provided and still present ---
        # This step might be redundant if the quest is removed from the player log elsewhere,
        # but it's safe to ensure it's not on the board definition.
        if completed_quest_instance_id:
            available_quests = [q for q in available_quests if q.get("instance_id") != completed_quest_instance_id]
            board_data["available_quests"] = available_quests # Update list in data

        # --- Check if a slot needs filling ---
        current_count = len(available_quests)
        if current_count >= max_quests:
            # print(f"[QuestSys Debug] Board already full ({current_count}/{max_quests}), no replenishment needed.")
            return # Board is full

        print(f"[QuestSys Debug] Replenishing board ({current_count}/{max_quests})...")

        # --- Determine which type to generate ---
        current_types_on_board = {q.get("type") for q in available_quests}
        missing_types = [t for t in required_types if t not in current_types_on_board]

        quest_type_to_generate = None
        if missing_types:
            # Prioritize generating a missing type
            quest_type_to_generate = random.choice(missing_types)
            if self.config.get("debug"): print(f"[QuestSys Debug] Prioritizing missing type: {quest_type_to_generate}")
        else:
            # All required types are present, generate a random one
            quest_type_to_generate = random.choice(required_types)
            if self.config.get("debug"): print(f"[QuestSys Debug] Generating random type (variety met): {quest_type_to_generate}")

        # --- Attempt to Generate and Add the Quest ---
        new_quest = None
        attempts = 0
        max_attempts = 5 # Limit attempts to generate one quest

        while not new_quest and attempts < max_attempts:
            attempts += 1
            if self.config.get("debug"): print(f"[QuestSys Debug] Generating {quest_type_to_generate} (Attempt {attempts}/{max_attempts})")

            generated_quest = self.generate_quest(player.level, quest_type_to_generate)
            if generated_quest:
                # Check for duplicates against current board
                is_duplicate = any(
                    existing_q.get("title") == generated_quest.get("title") and
                    existing_q.get("giver_instance_id") == generated_quest.get("giver_instance_id")
                    for existing_q in available_quests
                )
                if not is_duplicate:
                    new_quest = generated_quest # Found a valid, non-duplicate quest
                    if self.config.get("debug"):
                        # --- Enhanced Debug Print ---
                        quest_type = new_quest.get('type', '?')
                        title = new_quest.get('title', 'Unknown Title')
                        objective = new_quest.get('objective', {})
                        details = ""
                        if quest_type == 'kill':
                            details = f" (Target: {objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')})"
                        elif quest_type == 'fetch':
                            details = f" (Item: {objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')})"
                        elif quest_type == 'deliver':
                            details = f" (To: {objective.get('recipient_name', '?')})"
                    print(f"[QuestSys Debug]   -> Success: Generated {new_quest.get('instance_id')} [{quest_type.capitalize()} - {title}{details}]")
                elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Duplicate quest generated.")
            elif self.config.get("debug"): print(f"[QuestSys Debug]   -> Failed: Generation returned None.")

            # If we failed to generate the *required* missing type, maybe try another missing one?
            # Or just try random next time? For simplicity, we'll stick with the chosen type for these attempts.

        # --- Add the generated quest if successful ---
        if new_quest:
            available_quests.append(new_quest)
            # No need to update board_data["available_quests"] again, we modified the list directly
            self.world.set_plugin_data(self.plugin_id, self.quest_board_key, board_data)
            print(f"[QuestSys] Replenished board with new {new_quest.get('type')} quest: {new_quest.get('instance_id')}")
        else:
            print(f"[QuestSys] Warning: Failed to generate replacement quest for board after {attempts} attempts (Type: {quest_type_to_generate}).")

    # --- Quest Generation Logic ---
    def generate_quest(self, player_level: int, quest_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        if quest_type is None: quest_type = random.choice(["kill", "fetch", "deliver"])
        giver_instance_id = self._select_giver_npc(quest_type) # <<< CHANGED
        if not giver_instance_id:
            if self.config.get("debug"): print(f"[QuestSys Debug] No suitable giver found for quest type {quest_type}")
            return None

        giver_npc = self.world.get_npc(giver_instance_id)
        if not giver_npc: return None

        # 2. Generate Objective
        objective_data = None
        if quest_type == "kill": objective_data = self._generate_kill_objective(player_level, giver_npc)
        elif quest_type == "fetch": objective_data = self._generate_fetch_objective(player_level, giver_npc)
        elif quest_type == "deliver": objective_data = self._generate_deliver_objective(player_level, giver_npc)

        if not objective_data:
            if self.config.get("debug"): print(f"[QuestSys Debug] Failed to generate objective for {quest_type} from {giver_npc.name}")
            return None

        # 3. Assemble Quest Instance
        quest_instance = {
            "instance_id": f"{quest_type}_{giver_npc.template_id}_{uuid.uuid4().hex[:6]}",
            "type": quest_type,
            "giver_instance_id": giver_instance_id,
            "objective": objective_data,
            "state": "available" # Initial state when on board
        }
        quest_instance["rewards"] = self._calculate_rewards(quest_instance)
        quest_instance["title"] = self._format_quest_text("title", quest_instance, giver_npc)
        quest_instance["description"] = self._format_quest_text("description", quest_instance, giver_npc)

        return quest_instance

    def _select_giver_npc(self, quest_type: str) -> Optional[str]: # Pass quest_type directly
        """Selects a suitable online NPC instance ID based on mapped interests."""
        potential_givers = []
        if not hasattr(self, 'npc_interests'): self._load_npc_interests()

        # Get the list of relevant interests for this quest type from config
        interest_map = self.config.get("quest_type_interest_map", {})
        required_interests = interest_map.get(quest_type, [])
        if not required_interests:
            print(f"{FORMAT_ERROR}[QuestSys] No interests mapped for quest type '{quest_type}' in config.{FORMAT_RESET}")
            return None # Cannot find giver if no interests are mapped

        for npc_instance_id, npc in self.world.npcs.items():
            if (npc and npc.is_alive and npc.faction != "hostile" and
                npc.properties.get("can_give_generic_quests")):
                template_id = getattr(npc, 'template_id', None)
                # Get interests defined for this NPC's template
                npc_template_interests = self.npc_interests.get(template_id, [])

                # Check if *any* of the NPC's interests match *any* of the required interests for the quest type
                if any(interest in npc_template_interests for interest in required_interests):
                    potential_givers.append(npc_instance_id)

        return random.choice(potential_givers) if potential_givers else None

    def _generate_kill_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        """
        Generates a level-appropriate kill quest objective by checking NPC templates.
        Location hint is based on the giver's region.
        """
        if not self.world or not hasattr(self.world, 'npc_templates'):
            print(f"{FORMAT_ERROR}[QuestSys] Cannot generate kill quest: World or NPC templates missing.{FORMAT_RESET}")
            return None

        # --- 1. Determine Target Level Range --- (Unchanged)
        level_range = self.config.get("quest_level_range_player", 3)
        min_lvl = max(self.config.get("quest_level_min", 1), player_level - level_range)
        max_lvl = player_level + level_range
        if self.config.get("debug"): print(f"[QuestSys Debug] Kill Target Level Range: {min_lvl}-{max_lvl}")

        # --- 2. Find Potential Targets from ALL Hostile Templates ---
        valid_target_template_ids = [] # Stores suitable template IDs

        # Iterate through all loaded NPC templates
        for target_tid, template in self.world.npc_templates.items():
            if not isinstance(template, dict): continue # Skip invalid template data

            # Check if the template is hostile
            if template.get("faction") != "hostile": continue

            # Check the template's base level against the player's acceptable range
            mob_level = template.get("level", 1)
            if not (min_lvl <= mob_level <= max_lvl): continue

            # Optional: Check difficulty category (avoid grey/purple if possible)
            difficulty_category = get_level_diff_category(player_level, mob_level)
            if difficulty_category in ["gray", "purple"] and random.random() < 0.8: # 80% chance to skip grey/purple
                continue

            # If all checks pass, this template ID is a valid option
            valid_target_template_ids.append(target_tid)

        if not valid_target_template_ids:
            if self.config.get("debug"): print(f"[QuestSys Debug] No suitable hostile NPC templates found in level range {min_lvl}-{max_lvl}")
            return None

        # --- 3. Select Target Template ---
        selected_tid = random.choice(valid_target_template_ids)
        target_template = self.world.npc_templates.get(selected_tid, {}) # Should exist
        target_level = target_template.get("level", 1) # Get level from selected template

        # --- 4. Determine Location Hint (Based on Giver's Region) ---
        giver_region_id = giver_npc.current_region_id or giver_npc.home_region_id
        location_hint = "nearby regions" # Default hint
        if giver_region_id:
            region_obj = self.world.get_region(giver_region_id)
            if region_obj:
                location_hint = f"the area around {region_obj.name}" # More specific generic hint

        # --- 5. Determine Quantity --- (Unchanged)
        qty_base = self.config.get("kill_quest_quantity_base", 3)
        qty_per_lvl = self.config.get("kill_quest_quantity_per_level", 0.5)
        level_diff_factor = max(0.5, min(1.5, 1 + (target_level - player_level) * 0.1))
        required_quantity = max(1, int((qty_base + (player_level * qty_per_lvl)) * level_diff_factor + random.uniform(-1, 1)))

        # --- 6. Return Objective Data ---
        target_name_plural = simple_plural(target_template.get("name", selected_tid))
        return {
            "target_template_id": selected_tid,
            "target_name_plural": target_name_plural,
            "required_quantity": required_quantity,
            "current_quantity": 0,
            "location_hint": location_hint, # Use the less precise hint
            "difficulty_level": target_level
        }

    def _generate_fetch_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        """Generates a level-appropriate fetch quest objective."""
        if not self.world or not hasattr(self.world, 'item_templates') or not hasattr(self.world, 'npc_templates'):
            return None

        # --- 1. Determine Target Mob Level Range (for item source) ---
        level_range = self.config.get("quest_level_range_player", 3)
        min_mob_lvl = max(self.config.get("quest_level_min", 1), player_level - level_range)
        max_mob_lvl = player_level + level_range

        # --- 2. Find Potential Items based on Giver Interest & Obtainability ---
        giver_template_id = getattr(giver_npc, 'template_id', None)
        # Get interests from config first, fallback to empty list
        giver_interests = self.config.get("npc_quest_interests", {}).get(giver_template_id, [])
        # Example interests: "fetch_materials_metal", "fetch_ingredients", "fetch_trade_goods"

        valid_fetch_options = [] # Stores tuples: (item_id, source_mob_tid, source_mob_level, location_hint_region_id)

        # Iterate through all item templates
        for item_id, item_template in self.world.item_templates.items():
            if not isinstance(item_template, dict): continue # Skip invalid templates

            # Simple check: Can this item be fetched? (e.g., not unique quest items unless specifically designed)
            # Could add an "is_fetchable" property to items later. For now, assume most non-key/non-unique items are okay.
            item_type = item_template.get("type", "Item")
            if item_type in ["Key"]: continue # Don't fetch keys usually

            # TODO: Match item category/type to giver interest (requires item categories or more complex matching)
            # Simple Example (replace with better logic):
            # is_material = item_id.endswith(("_pelt", "_hide", "_ore", "_scale", "_fang", "_bone"))
            # is_ingredient = item_id.endswith(("_herb", "_fungus", "_meat", "_tail")) # Crude check
            # if "fetch_materials" in giver_interests and not is_material: continue
            # if "fetch_ingredients" in giver_interests and not is_ingredient: continue

            # Find mobs that drop this item and fit level criteria
            found_source = False
            possible_sources = [] # (source_mob_tid, source_mob_level, region_id)
            for mob_tid, mob_template in self.world.npc_templates.items():
                 if isinstance(mob_template, dict) and mob_template.get("faction") == "hostile":
                      mob_level = mob_template.get("level", 1)
                      # Check if mob level is appropriate for player
                      if not (min_mob_lvl <= mob_level <= max_mob_lvl): continue

                      loot_table = mob_template.get("loot_table", {})
                      if item_id in loot_table:
                           # This mob drops the item and is level-appropriate
                           # Now check where this mob spawns
                           spawner_plugin = self.service_locator.get_service("plugin:monster_spawner_plugin")
                           if not spawner_plugin: continue # Cannot check spawns

                           spawner_region_monsters = spawner_plugin.config.get("region_monsters", {})
                           spawner_region_levels = spawner_plugin.config.get("region_levels", {})

                           for region_id, monsters_in_region in spawner_region_monsters.items():
                                if mob_tid in monsters_in_region:
                                     region_level_range = spawner_region_levels.get(region_id, [1, 99])
                                     # Check mob level fits region level AND region isn't safe
                                     if (region_level_range[0] <= mob_level <= region_level_range[1] and
                                         not self.world.is_location_safe(region_id)):
                                         possible_sources.append((mob_tid, mob_level, region_id))
                                         found_source = True
                                         break # Found at least one region for this mob

            # If suitable dropping mobs found, add item to potential fetch list
            if found_source and possible_sources:
                # Choose one representative source for the quest objective display
                source_mob_tid, source_mob_level, location_hint_region_id = random.choice(possible_sources)
                valid_fetch_options.append((item_id, source_mob_tid, source_mob_level, location_hint_region_id))

        if not valid_fetch_options:
            if self.config.get("debug"): print(f"[QuestSys Debug] No suitable fetch items found for {giver_npc.name} / level {player_level}")
            return None

        # --- 3. Select Item, Source, and Location ---
        selected_item_id, source_mob_tid, source_mob_level, selected_region_id = random.choice(valid_fetch_options)
        item_template = self.world.item_templates.get(selected_item_id, {})
        source_mob_template = self.world.npc_templates.get(source_mob_tid, {})
        region_obj = self.world.get_region(selected_region_id)
        location_hint = region_obj.name if region_obj else selected_region_id

        # --- 4. Determine Quantity ---
        qty_base = self.config.get("fetch_quest_quantity_base", 5)
        qty_per_lvl = self.config.get("fetch_quest_quantity_per_level", 1)
        item_value_factor = max(0.5, min(2.0, 10 / (item_template.get("value", 10) + 1))) # More valuable items require fewer?
        required_quantity = max(1, int((qty_base + (player_level * qty_per_lvl)) * item_value_factor + random.uniform(-1, 2)))

        # --- 5. Return Objective Data ---
        item_name = item_template.get("name", selected_item_id)
        item_name_plural = simple_plural(item_name)
        source_enemy_name_plural = simple_plural(source_mob_template.get("name", source_mob_tid))

        return {
            "item_id": selected_item_id,
            "item_name": item_name,
            "item_name_plural": item_name_plural,
            "required_quantity": required_quantity,
            "current_quantity": 0, # Checked at turn-in via inventory count
            "source_enemy_name_plural": source_enemy_name_plural,
            "location_hint": location_hint,
            "difficulty_level": item_template.get("value", 1) * required_quantity // 2 # Difficulty scales with value*quantity
        }

    # --- Implement _generate_deliver_objective ---
    def _generate_deliver_objective(self, player_level: int, giver_npc: NPC) -> Optional[Dict[str, Any]]:
        """Generates a level-appropriate delivery quest objective."""
        if not self.world: return None

        # --- 1. Select Recipient ---
        potential_recipients = []
        giver_loc_key = f"{giver_npc.current_region_id}:{giver_npc.current_room_id}"
        excluded_ids = ["wandering_villager"]
        generic_villager_template_id = "wandering_villager" # <<< Define the template ID to exclude

        for r_instance_id, r_npc in self.world.npcs.items():
            if (r_npc and r_npc.is_alive and
                r_npc.faction != "hostile" and
                r_instance_id != giver_npc.obj_id):

                recipient_template_id = getattr(r_npc, 'template_id', None)
                if recipient_template_id in excluded_ids:
                    if self.config.get("debug"): print(f"[QuestSys Debug] Skipping ineligible recipient: {r_npc.name} ({r_instance_id})")
                    continue
                    
                if recipient_template_id == generic_villager_template_id:
                    if self.config.get("debug"): print(f"[QuestSys Debug] Skipping generic villager {r_npc.name} ({r_instance_id}) as recipient.")
                    continue
                # --- END FILTER ---

                # Optional: Add more complex filtering (e.g., based on properties) later if needed
                # if not r_npc.properties.get("can_receive_deliveries", True): continue

                potential_recipients.append(r_instance_id)


        if not potential_recipients:
            if self.config.get("debug"): print(f"[QuestSys Debug] No valid recipients found for delivery quest from {giver_npc.name}.")
            return None

        recipient_instance_id = random.choice(potential_recipients)
        recipient_npc = self.world.get_npc(recipient_instance_id)
        if not recipient_npc: return None # Recipient doesn't exist? Should not happen.

        # --- 2. Define Package Details (Template and Instance) ---
        # We use a generic template but generate unique instance details
        package_template_id = "quest_package_generic"
        package_instance_id = f"delivery_{giver_npc.obj_id[:4]}_{recipient_instance_id[:4]}_{uuid.uuid4().hex[:4]}" # Unique ID

        # Get base name from template (ensure template exists!)
        package_template = self.world.item_templates.get(package_template_id)
        if not package_template:
             print(f"{FORMAT_ERROR}[QuestSys] Critical: Delivery item template '{package_template_id}' not found!{FORMAT_RESET}")
             # Fallback: create a basic placeholder item info
             item_name = "A Simple Package"
             item_description = f"A package meant for {recipient_npc.name}."
             item_value = 1 # Minimal value for difficulty calc
        else:
             item_name = package_template.get("name", "Package")
             item_description = f"A package to be delivered to {recipient_npc.name}. Seems to be from {giver_npc.name}."
             item_value = package_template.get("value", 1) # Use template value if exists

        # --- 3. Determine Location Description ---
        recipient_region = self.world.get_region(recipient_npc.current_region_id)
        recipient_room = recipient_region.get_room(recipient_npc.current_room_id) if recipient_region else None
        # Use descriptive names if available
        region_name_str = recipient_region.name if recipient_region else recipient_npc.current_region_id
        room_name_str = recipient_room.name if recipient_room else recipient_npc.current_room_id
        recipient_location_description = f"{region_name_str} ({room_name_str})"

        # --- 4. Return Objective Data ---
        # Note: The actual item instance is created later when the quest is accepted.
        return {
            "item_template_id": package_template_id, # Template for creation
            "item_instance_id": package_instance_id, # Unique ID for the item *to be created*
            "item_to_deliver_name": item_name, # For display/formatting
            "item_to_deliver_description": item_description, # For creation override
            "recipient_instance_id": recipient_instance_id,
            "recipient_name": recipient_npc.name,
            "recipient_location_description": recipient_location_description,
            "difficulty_level": 5 + item_value # Base difficulty + item value proxy
        }

    def _calculate_rewards(self, quest_instance: Dict[str, Any]) -> Dict[str, int]:
        # --- ACTUAL IMPLEMENTATION NEEDED ---
        base_xp = self.config.get("reward_base_xp", 50)
        xp_per_lvl = self.config.get("reward_xp_per_level", 15)
        xp_per_qty = self.config.get("reward_xp_per_quantity", 5)
        base_gold = self.config.get("reward_base_gold", 10)
        gold_per_lvl = self.config.get("reward_gold_per_level", 5)
        gold_per_qty = self.config.get("reward_gold_per_quantity", 2)

        objective = quest_instance.get("objective", {})
        difficulty_level = objective.get("difficulty_level", 1)
        quantity = objective.get("required_quantity", 1)
        quest_type = quest_instance.get("type")

        xp = base_xp + (difficulty_level * xp_per_lvl)
        gold = base_gold + (difficulty_level * gold_per_lvl)

        if quest_type in ["kill", "fetch"]:
             xp += quantity * xp_per_qty
             gold += quantity * gold_per_qty
        elif quest_type == "deliver":
             # Delivery reward could be based on distance later
             xp *= 1.5 # Slightly more XP for travel?
             gold *= 1.2

        return {"xp": max(1, int(xp)), "gold": max(0, int(gold))}


    def _format_quest_text(self, text_type: str, quest_instance: Dict[str, Any], giver_npc: NPC) -> str:
        # --- ACTUAL IMPLEMENTATION NEEDED ---
        # Use templates (defined in code or loaded) and fill based on quest_instance data
        objective = quest_instance.get("objective", {})
        template_map = { # Simple templates defined here for now
            "kill": {
                "title": "Bounty: {target_name_plural}",
                "description": "{giver_name} is offering a bounty for slaying {quantity} {target_name_plural} sighted in {location_description}.",
            },
            "fetch": {
                "title": "Gather: {item_name_plural}",
                "description": "{giver_name} needs {quantity} {item_name_plural}. They believe {source_enemy_name_plural} in {location_description} may carry them.",
            },
            "deliver": {
                "title": "Delivery: {item_to_deliver_name} to {recipient_name}",
                "description": "{giver_name} asks you to deliver a {item_to_deliver_name} to {recipient_name}, who can be found in {recipient_location_description}.",
            }
        }
        quest_type = quest_instance.get("type")
        format_template = template_map.get(quest_type, {}).get(text_type, f"Quest {text_type}")

        details = {
            "giver_name": giver_npc.name,
            "quantity": objective.get("required_quantity"),
            "target_name_plural": objective.get("target_name_plural", "?"),
            "item_name": objective.get("item_name", "?"),
            "item_name_plural": objective.get("item_name_plural", "?"),
            "source_enemy_name_plural": objective.get("source_enemy_name_plural", "?"),
            "location_description": objective.get("location_hint", "?"),
            "item_to_deliver_name": objective.get("item_to_deliver_name", "?"),
            "recipient_name": objective.get("recipient_name", "?"),
            "recipient_location_description": objective.get("recipient_location_description", "?")
        }
        valid_details = {k: v for k, v in details.items() if v is not None}
        try: return format_template.format(**valid_details)
        except KeyError as e: return f"Error formatting quest {text_type} ({e})"


    # --- Event Handlers ---
    def _handle_npc_killed(self, event_type: str, data: Dict[str, Any]):
        player = data.get("player")
        killed_npc = data.get("npc")
        if not player or not killed_npc or not hasattr(player, 'quest_log'): return

        killed_template_id = getattr(killed_npc, 'template_id', None)
        if not killed_template_id: return

        # Use items() for safe iteration if dict changes
        for quest_id, quest_data in list(player.quest_log.items()):
            if (quest_data.get("state") == "active" and
                quest_data.get("type") == "kill"):
                objective = quest_data.get("objective", {})
                quest_target_id = objective.get("target_template_id") # Get target from quest

                # --- Add Debug Print ---
                print(f"[Quest Kill Debug] Comparing Killed='{killed_template_id}' vs Quest='{quest_target_id}'")
                # --- End Debug Print ---

                if quest_target_id == killed_template_id: # <<< Case-sensitive compare
                    # Increment progress
                    objective["current_quantity"] = objective.get("current_quantity", 0) + 1
                    required = objective.get("required_quantity", 1)
                    # Persist change
                    player.update_quest(quest_id, quest_data)

                    # Check for completion
                    if objective["current_quantity"] >= required:
                        quest_data["state"] = "ready_to_complete"
                        player.update_quest(quest_id, quest_data) # Update state
                        # Notify player
                        giver = self.world.get_npc(quest_data.get("giver_instance_id"))
                        giver_name = giver.name if giver else "the quest giver"
                        message = f"{FORMAT_HIGHLIGHT}[Quest Update]{FORMAT_RESET} {quest_data.get('title', 'Task')}: Objective complete! Report back to {giver_name}."
                        self.event_system.publish("display_message", message)
                    else:
                         # Optional: Notify player of progress
                         message = f"{FORMAT_HIGHLIGHT}[Quest Update]{FORMAT_RESET} {quest_data.get('title', 'Task')}: ({objective['current_quantity']}/{required} killed)."
                         self.event_system.publish("display_message", message)


    def _handle_item_obtained(self, event_type: str, data: Dict[str, Any]):
        player = data.get("player")
        item_id = data.get("item_id")
        if not player or not item_id or not hasattr(player, 'quest_log'): return

        # Use items() for safe iteration
        for quest_id, quest_data in list(player.quest_log.items()):
            if (quest_data.get("state") == "active" and
                quest_data.get("type") == "fetch"):
                objective = quest_data.get("objective", {})
                if objective.get("item_id") == item_id:
                    # Fetch quests completion is checked at turn-in, not pickup
                    # We *could* add a notification here if desired:
                    # current_count = player.inventory.count_item(item_id) # Assumes count_item exists
                    # required = objective.get("required_quantity", 1)
                    # message = f"[Quest Info] {quest_data.get('title')}: You now have {current_count}/{required} {objective.get('item_name_plural')}."
                    # self.event_system.publish("display_message", message)
                    pass # Do nothing on pickup, check happens during talk

    # Need npc_talk handler in commands.py to trigger turn-ins
    # def _handle_npc_talk(self, event_type: str, data: Dict[str, Any]):
    #     pass # Turn-in logic will be handled in the talk command

    # ... (Other methods like cleanup) ...
    def cleanup(self):
        if self.event_system:
             self.event_system.unsubscribe("npc_killed", self._handle_npc_killed)
             self.event_system.unsubscribe("item_obtained", self._handle_item_obtained)
        print("[QuestSys] Quest System plugin cleaned up.")

    def _load_npc_interests(self):
        """Loads quest interest lists from NPC templates."""
        self.npc_interests = {} # Reset just in case
        if not self.world or not hasattr(self.world, 'npc_templates'):
            print(f"{FORMAT_ERROR}[QuestSys] Cannot load NPC interests: World or NPC templates missing.{FORMAT_RESET}")
            return

        loaded_count = 0
        # Use config interests as a base/default if templates lack them
        config_interests = self.config.get("npc_quest_interests", {})

        for template_id, template_data in self.world.npc_templates.items():
            if not isinstance(template_data, dict): continue # Skip invalid template data

            # Prioritize interests defined directly in the template's properties
            interests = template_data.get("properties", {}).get("quest_interests")

            # If not in template properties, try getting from plugin config as fallback
            if interests is None: # Explicitly check for None vs empty list
                 interests = config_interests.get(template_id)

            # Ensure it's a list if found
            if interests is not None and isinstance(interests, list):
                # Validate that elements are strings? Optional.
                valid_interests = [str(i) for i in interests if isinstance(i, str)]
                if valid_interests:
                    self.npc_interests[template_id] = valid_interests
                    loaded_count += 1
            elif interests is not None:
                 print(f"[QuestSys] Warning: quest_interests for '{template_id}' is not a list: {interests}")

        if self.config.get("debug"):
            print(f"[QuestSys Debug] Loaded quest interests for {loaded_count} NPC templates.")
            # print(f"[QuestSys Debug] Interests Loaded: {self.npc_interests}") # Very verbose debug
    # --- END METHOD IMPLEMENTATION ---

# --- Need to add the 'quest_package_generic' item template ---
# Add this to a relevant file in data/items/ (e.g., misc_items.json or a new quest_items.json)
# Example for data/items/misc_items.json:
# "quest_package_generic": {
#     "type": "Item",
#     "name": "Sealed Package",
#     "description": "A package that needs delivering. It's sealed, so its contents are unknown.",
#     "weight": 1.0,
#     "value": 0, # No direct sell value
#     "stackable": false,
#     "category": "misc", # Or "quest" category if you add it
#     "properties": {
#         "is_quest_item": true // Flag to prevent selling/dropping maybe?
#     }
# }