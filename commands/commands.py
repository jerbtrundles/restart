"""
commands/commands.py
Unified command system for the MUD game.
"""
import os
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple
from commands.command_system import command, registered_commands
from core.config import (
    CAST_COMMAND_PREPOSITION, DEFAULT_WORLD_FILE, EQUIP_COMMAND_SLOT_PREPOSITION, FOLLOW_COMMAND_STOP_ALIASES, FORMAT_CATEGORY, FORMAT_TITLE, FORMAT_HIGHLIGHT,
    FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, GET_COMMAND_PREPOSITION, GIVE_COMMAND_PREPOSITION, PUT_COMMAND_PREPOSITION, QUEST_BOARD_ALIASES, REPAIR_COST_PER_VALUE_POINT, REPAIR_MINIMUM_COST, SAVE_GAME_DIR,
    # --- Import Trading Config ---
    DEFAULT_VENDOR_SELL_MULTIPLIER, DEFAULT_VENDOR_BUY_MULTIPLIER, TARGET_SELF_ALIASES, USE_COMMAND_PREPOSITIONS,
    VENDOR_CAN_BUY_JUNK, VENDOR_CAN_BUY_ALL_ITEMS, VENDOR_ID_HINTS, VENDOR_LIST_ITEM_NAME_WIDTH, VENDOR_LIST_PRICE_WIDTH, VENDOR_MIN_BUY_PRICE, VENDOR_MIN_SELL_PRICE
)
from items.consumable import Consumable
from items.item_factory import ItemFactory
from items.junk import Junk
from items.key import Key
from items.container import Container
from plugins.service_locator import get_service_locator
from utils.text_formatter import TextFormatter, format_target_name # Added format_target_name
from utils.utils import format_name_for_display, get_article, simple_plural # Added utils
from magic.spell_registry import get_spell, get_spell_by_name # Import registry access
from magic.spell import Spell # Import Spell definition
from player import Player # Import Player to check type
from npcs.npc import NPC # Import NPC to check type


DIRECTIONS = [
    {"name": "north", "aliases": ["n"], "description": "Move north."}, 
    {"name": "south", "aliases": ["s"], "description": "Move south."},
    {"name": "east", "aliases": ["e"], "description": "Move east."}, 
    {"name": "west", "aliases": ["w"], "description": "Move west."},
    {"name": "northeast", "aliases": ["ne"], "description": "Move northeast."}, 
    {"name": "northwest", "aliases": ["nw"], "description": "Move northwest."},
    {"name": "southeast", "aliases": ["se"], "description": "Move southeast."}, 
    {"name": "southwest", "aliases": ["sw"], "description": "Move southwest."},
    {"name": "up", "aliases": ["u"], "description": "Move up."}, 
    {"name": "down", "aliases": ["d"], "description": "Move down."},
    {"name": "in", "aliases": ["enter", "inside"], "description": "Enter."}, 
    {"name": "out", "aliases": ["exit", "outside", "o"], "description": "Exit."}
]

def register_movement_commands():
    """Registers specific direction commands (n, s, e, w, etc.)"""
    registered = {}
    for direction_info in DIRECTIONS:
        direction_name = direction_info["name"]
        direction_aliases = direction_info["aliases"]
        direction_description = direction_info["description"]
        if direction_name in registered_commands: continue

        # --- Create the handler dynamically for this specific direction ---
        def create_direction_handler(dir_name):
            def handler(args, context):
                world = context["world"] # Get world context
                player = world.player

                # --- Stop Trading Logic ---
                if player.trading_with:
                    vendor = world.get_npc(player.trading_with)
                    if vendor:
                         vendor.is_trading = False # <<< Tell vendor to stop trading
                    player.trading_with = None
                # --- End Stop Trading ---

                # Check if player is alive (redundant with change_room check, but good practice)
                if not player.is_alive:
                    return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"

                # Execute the move using the specific direction name
                return context["world"].change_room(dir_name)
            return handler
        # --- End handler creation ---

        # Create and decorate the handler
        handler_func = create_direction_handler(direction_name)
        decorated_handler = command(
            name=direction_name,
            aliases=direction_aliases,
            category="movement",
            help_text=direction_description
        )(handler_func)

        # Store reference if needed elsewhere (though registration handles it)
        registered[direction_name] = decorated_handler

    return registered

@command("go", ["move", "walk"], "movement", "Move in a direction.\nUsage: go <direction>")
def go_handler(args, context):
    world = context["world"]
    player = world.player
    
    # --- Stop Trading Logic ---
    if player.trading_with:
        vendor = world.get_npc(player.trading_with)
        if vendor:
            vendor.is_trading = False # <<< Tell vendor to stop trading
        player.trading_with = None
    # --- End Stop Trading ---

    # Player alive check (moved up slightly)
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"

    if not args:
        return "Go where?"

    # Proceed with the move using the provided argument
    return context["world"].change_room(args[0].lower())


@command("help", ["h", "?"], "system", "Show help.\nUsage: help [command]")
def help_handler(args, context):
    cp = context["command_processor"]
    return cp.get_command_help(args[0]) if args else cp.get_help_text()

@command("quit", ["q", "exit"], "system", "Return to the main title screen.")
def quit_handler(args, context):
    game = context.get("game")
    if game:
        game._shutdown_gameplay_systems() # Unload plugins, etc.
        game.game_state = "title_screen"
        # Optionally reset world object? Depends if you want a 'clean slate'
        # game.world = World()
        # game.world.game = game
        # game.world._load_definitions()
        return f"{FORMAT_HIGHLIGHT}Returning to title screen...{FORMAT_RESET}" # Message shown briefly before screen changes

@command("save", [], "system", "Save game state.\nUsage: save [filename]")
def save_handler(args, context):
    world = context["world"]
    game = context["game"] # Get game manager from context
    # Use filename arg or game manager's current file
    fname = (args[0] if args else game.current_save_file)
    # Ensure .json extension
    if not fname.endswith(".json"): fname += ".json"

    if world.save_game(fname): # Call new save method
        game.current_save_file = fname # Update game manager's current file on successful save
        return f"{FORMAT_SUCCESS}World state saved to {fname}{FORMAT_RESET}"
    else:
        return f"{FORMAT_ERROR}Error saving world state to {fname}{FORMAT_RESET}"

@command("load", [], "system", "Load game state.\nUsage: load [filename]")
def load_handler(args, context):
    # Loading during gameplay is complex (need to reset plugins, UI state etc.)
    # For now, this command might just report what *would* be loaded on restart
    # Or, implement a full game state reset and load here. Let's try the reset.

    world = context["world"]
    game = context["game"]
    fname = (args[0] if args else game.current_save_file)
    if not fname.endswith(".json"): fname += ".json"
    save_path = os.path.join(SAVE_GAME_DIR, fname) # Use config

    if not os.path.exists(save_path):
         return f"{FORMAT_ERROR}Save file '{fname}' not found in '{SAVE_GAME_DIR}'.{FORMAT_RESET}"

    # --- Perform Load ---
    print(f"Attempting to load game state from {fname}...")
    # 1. Unload plugins (important to reset their state)
    if game.plugin_manager: game.plugin_manager.unload_all_plugins()

    # 2. Call world's load function
    success = world.load_save_game(fname)

    if success:
         # 3. Update game manager state
         game.current_save_file = fname
         game.text_buffer = [] # Clear buffer
         game.scroll_offset = 0
         game.input_text = ""
         game.command_history = []
         game.history_index = -1
         game.game_state = "playing" # Ensure state is correct

         # 4. Re-initialize and load plugins
         if game.plugin_manager:
             # Re-register core services if needed, though they might persist
             game.plugin_manager.service_locator.register_service("world", game.world)
             # Reload plugins
             game.plugin_manager.load_all_plugins()
             # Manually trigger initial time/weather updates if plugins rely on them immediately
             time_plugin = game.plugin_manager.get_plugin("time_plugin")
             if time_plugin: time_plugin._update_world_time_data()
             weather_plugin = game.plugin_manager.get_plugin("weather_plugin")
             if weather_plugin: weather_plugin._notify_weather_change()


         # 5. Return success message + initial look
         return f"{FORMAT_SUCCESS}World state loaded from {fname}{FORMAT_RESET}\n\n{world.look()}"
    else:
         # If load failed critically, might need to quit or revert
         return f"{FORMAT_ERROR}Error loading world state from {fname}. Game state might be unstable.{FORMAT_RESET}"

@command("inventory", ["i", "inv"], "inventory", "Show items you are carrying.")
def inventory_handler(args, context):
    world = context["world"]
    inventory_text = f"{FORMAT_TITLE}INVENTORY{FORMAT_RESET}\n\n"
    inventory_text += world.player.inventory.list_items()
    equipped_text = f"\n{FORMAT_TITLE}EQUIPPED{FORMAT_RESET}\n"
    equipped_items_found = False
    for slot, item in world.player.equipment.items():
        if item:
            equipped_text += f"- {slot.replace('_', ' ').capitalize()}: {item.name}\n"
            equipped_items_found = True
    if not equipped_items_found:
        equipped_text += "  (Nothing equipped)\n"
    return inventory_text + equipped_text

@command("status", ["stat", "st"], "inventory", "Display character status.")
def status_handler(args, context):
    world = context["world"]
    status = world.player.get_status()
    return status

@command("look", ["l"], "interaction", "Look around or examine something.\nUsage: look [target]")
def look_handler(args, context):
    world = context["world"]
    player = world.player # Get player reference

    # --- 1. Handle looking at the 'board' specifically ---
    target_name = " ".join(args).lower() if args else None
    quest_plugin = world.game.plugin_manager.get_plugin("quest_system_plugin") if world.game and world.game.plugin_manager else None

    if target_name in QUEST_BOARD_ALIASES:
        if quest_plugin:
            # Check if player is in the correct location defined in plugin config
            board_loc_str = quest_plugin.config.get("quest_board_location", "town:town_square")
            board_region, board_room = board_loc_str.split(":")
            if player.current_region_id == board_region and player.current_room_id == board_room: # Use player location
                # Call the plugin's command handler logic directly or trigger it
                board_look_command = registered_commands.get("look board")
                if board_look_command and 'handler' in board_look_command:
                     # The plugin command handler doesn't expect args for 'look board'
                     return board_look_command['handler']([], context)
                else:
                     return f"{FORMAT_ERROR}Quest board command not registered correctly.{FORMAT_RESET}"
            else:
                return "You don't see a quest board here."
        else:
            return f"{FORMAT_ERROR}Quest system seems unavailable.{FORMAT_RESET}"

    # --- 2. Handle looking at the room (no args) ---
    if not args:
        return world.get_room_description_for_display() # This function now handles NPC/item listing

    # --- 3. Handle looking at other targets (NPCs, Items - Refined Logic) ---
    target_input_lower = target_name # User input, already lowercased if args existed

    # --- Prioritize NPCs ---
    npcs_in_room = world.get_current_room_npcs()
    found_npc = None

    # First pass: Exact match (Name or ID)
    for npc in npcs_in_room:
        # Compare user input directly against NPC name (lower) and ID
        if target_input_lower == npc.name.lower() or target_input_lower == npc.obj_id:
            found_npc = npc
            break # Found exact match

    # Second pass: Partial name match (if no exact match found)
    if not found_npc:
        for npc in npcs_in_room:
            # Check if user input is PART of the NPC's name
            if target_input_lower in npc.name.lower():
                found_npc = npc
                break # Found partial match

    if found_npc:
        return found_npc.get_description() # Return description of the found NPC
    # --- End NPC Check ---


    # --- Check Items in Room ---
    items_in_room = world.get_items_in_current_room()
    found_item = None

    # First pass: Exact match (Name or ID)
    for item in items_in_room:
        if target_input_lower == item.name.lower() or target_input_lower == item.obj_id:
            found_item = item
            break

    # Second pass: Partial name match
    if not found_item:
        for item in items_in_room:
            if target_input_lower in item.name.lower():
                found_item = item
                break

    if found_item:
        return found_item.examine()
    # --- End Room Item Check ---


    # --- Check Items in Inventory ---
    # find_item_by_name handles partial matching internally
    inv_item = player.inventory.find_item_by_name(target_input_lower)
    if inv_item:
        return inv_item.examine()
    # --- End Inventory Check ---


    # --- Check Equipped Items ---
    found_equipped_item = None
    # First pass: Exact match (Name or ID)
    for slot, equipped_item in player.equipment.items():
        if equipped_item and (target_input_lower == equipped_item.name.lower() or target_input_lower == equipped_item.obj_id):
            found_equipped_item = equipped_item
            break
    # Second pass: Partial name match
    if not found_equipped_item:
        for slot, equipped_item in player.equipment.items():
            if equipped_item and target_input_lower in equipped_item.name.lower():
                found_equipped_item = equipped_item
                break

    if found_equipped_item:
        return found_equipped_item.examine()
    # --- End Equipped Check ---

    # --- Target Not Found ---
    return f"You see no '{target_input_lower}' here."

@command("examine", ["x", "exam"], "interaction", "Examine something.\nUsage: examine <target>")
def examine_handler(args, context):
    if not args: return f"{FORMAT_ERROR}What do you want to examine?{FORMAT_RESET}"
    return look_handler(args, context) # Delegate to look handler

@command("drop", ["putdown"], "interaction", "Drop an item.\nUsage: drop <item>")
def drop_handler(args, context):
    player = context["world"].player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    world = context["world"]
    if not args: return f"{FORMAT_ERROR}Drop what?{FORMAT_RESET}"
    item_name = " ".join(args).lower()
    # Use find_item_by_name for easier searching
    item_to_drop = world.player.inventory.find_item_by_name(item_name)
    if item_to_drop:
        item, quantity, message = world.player.inventory.remove_item(item_to_drop.obj_id, 1)
        if item:
            world.add_item_to_room(world.current_region_id, world.current_room_id, item)
            return f"{FORMAT_SUCCESS}You drop the {item.name}.{FORMAT_RESET}"
        else: return f"{FORMAT_ERROR}{message}{FORMAT_RESET}" # Should not happen if find_item worked
    return f"{FORMAT_ERROR}You don't have a {' '.join(args)}.{FORMAT_RESET}"

@command("talk", ["speak", "chat", "ask"], "interaction", "Talk to an NPC.\nUsage: talk <npc_name> [topic | complete quest <quest_title_part>]")
def talk_handler(args, context):
    world = context["world"]
    player = world.player
    if not args: return f"{FORMAT_ERROR}Talk to whom?{FORMAT_RESET}"

    npc_name = args[0].lower()
    topic = None
    is_quest_turn_in = False
    quest_turn_in_id = None

    # --- Parse arguments for topic or quest completion ---
    if len(args) > 1:
        # Check for "complete quest" keywords
        if args[1].lower() in ["complete", "report", "finish", "turnin"] and (len(args) < 3 or args[2].lower() == "quest"):
             is_quest_turn_in = True
             # Optional: Allow specifying part of the quest title?
             # if len(args) > 3:
             #     quest_title_part = " ".join(args[3:]).lower()
             #     # We'll use this later to find the specific quest
        else:
            topic = " ".join(args[1:])

    # --- Find NPC ---
    target_npc = world.find_npc_in_room(npc_name)
    if not target_npc: return f"{FORMAT_ERROR}There's no '{args[0]}' here.{FORMAT_RESET}"

    # --- Quest Turn-in Logic ---
    ready_quests_for_npc = []
    if hasattr(player, 'quest_log') and player.quest_log:
        for quest_id, quest_data in player.quest_log.items():
            # Find quests ready to complete given by *this* NPC
            if (quest_data.get("state") == "ready_to_complete" and
                quest_data.get("giver_instance_id") == target_npc.obj_id):
                ready_quests_for_npc.append((quest_id, quest_data))

    # If player used "complete quest" command and has quests ready for this NPC
    if is_quest_turn_in:
        if not ready_quests_for_npc:
            return f"{target_npc.name} doesn't seem to be expecting anything from you right now."

        if len(ready_quests_for_npc) == 1:
            # Only one quest ready, assume they mean that one
            quest_turn_in_id, quest_data = ready_quests_for_npc[0]
        else:
            # Multiple quests ready - TODO: Need a way to disambiguate
            # For now, just process the first one found. Later, could list them.
            quest_turn_in_id, quest_data = ready_quests_for_npc[0]
            # Maybe print a warning: f"You have multiple quests for {target_npc.name}. Completing '{quest_data['title']}' first."

        # --- Perform Turn-in Checks & Completion ---
        quest_type = quest_data.get("type")
        objective = quest_data.get("objective", {})
        can_complete = True
        completion_error_msg = ""

        # Check Fetch quest item requirements
        if quest_type == "fetch":
            required_item_id = objective.get("item_id")
            required_qty = objective.get("required_quantity", 1)
            player_has_qty = player.inventory.count_item(required_item_id)
            if player_has_qty < required_qty:
                can_complete = False
                completion_error_msg = f"You still need {required_qty - player_has_qty} more {objective.get('item_name_plural', 'items')}."
            else:
                # Player has enough, remove them (if flag set - assume removal for generic fetch)
                removed_type, removed_count, remove_msg = player.inventory.remove_item(required_item_id, required_qty)
                if not removed_type or removed_count != required_qty:
                     # Failed to remove items - critical error, stop completion
                     can_complete = False
                     completion_error_msg = "Error removing required items from your inventory. Cannot complete quest."
                     print(f"{FORMAT_ERROR}Quest Turn-in Error: {completion_error_msg} Quest: {quest_turn_in_id}{FORMAT_RESET}")

        # Check Deliver quest item requirements
        elif quest_type == "deliver":
            required_instance_id = objective.get("item_instance_id")
            package_instance = player.inventory.find_item_by_id(required_instance_id)
            if not package_instance:
                can_complete = False
                completion_error_msg = f"You don't seem to have the {objective.get('item_to_deliver_name', 'package')} anymore!"
            else:
                # Player has the specific package, remove it
                removed = player.inventory.remove_item_instance(package_instance)
                if not removed:
                     # Failed to remove item - critical error
                     can_complete = False
                     completion_error_msg = f"Error removing the {objective.get('item_to_deliver_name', 'package')} from your inventory."
                     print(f"{FORMAT_ERROR}Quest Turn-in Error: {completion_error_msg} Quest: {quest_turn_in_id}{FORMAT_RESET}")


        # If all checks passed, complete the quest
        if can_complete:
            # Grant Rewards
            rewards = quest_data.get("rewards", {})
            xp_reward = rewards.get("xp", 0)
            gold_reward = rewards.get("gold", 0)
            reward_messages = []
            if xp_reward > 0:
                 player.gain_experience(xp_reward)
                 reward_messages.append(f"{xp_reward} XP")
            if gold_reward > 0:
                 player.gold += gold_reward
                 reward_messages.append(f"{gold_reward} Gold")
            # TODO: Add item rewards later

            # Update Quest State
            quest_data["state"] = "completed"
            # Remove from active log (or move to a completed section later)
            if quest_turn_in_id in player.quest_log:
                 del player.quest_log[quest_turn_in_id]

            # Trigger Board Replenishment
            quest_plugin = context["game"].plugin_manager.get_plugin("quest_system_plugin") # Get plugin instance
            if quest_plugin:
                 quest_plugin.replenish_board(quest_turn_in_id)

            # Format Completion Message
            completion_message = f"{FORMAT_SUCCESS}[Quest Complete] {quest_data.get('title', 'Task')}{FORMAT_RESET}\n"
            npc_response = f"\"Thank you for your help, adventurer!\" says {target_npc.name}." # Generic response
            # TODO: Could add quest-specific completion dialog nodes later
            completion_message += f"{FORMAT_HIGHLIGHT}{npc_response}{FORMAT_RESET}\n"
            if reward_messages:
                 completion_message += "You receive: " + ", ".join(reward_messages) + "."

            return completion_message
        else:
            # Completion checks failed
            return f"{FORMAT_ERROR}You haven't fully met the requirements for '{quest_data.get('title', 'this quest')}'. {completion_error_msg}{FORMAT_RESET}"

    # --- Standard Dialog / Quest Offer Logic ---
    else:
        # Check if this NPC has any quests ready for turn-in (even if player didn't type "complete")
        if ready_quests_for_npc:
             # Add a hint to the standard dialog options or response
             turn_in_hint = f"\n{FORMAT_HIGHLIGHT}(You have tasks to report to {target_npc.name}. Type 'talk {npc_name} complete quest'){FORMAT_RESET}"
        else:
             turn_in_hint = ""

        # Check if this NPC can offer generic quests
        can_offer_generic = target_npc.properties.get("can_give_generic_quests", False)
        offer_hint = ""
        if can_offer_generic:
             offer_hint = f"\n{FORMAT_HIGHLIGHT}({target_npc.name} might have work available. Try 'talk {npc_name} work'){FORMAT_RESET}"

        # --- Handle specific topic or default dialog ---
        response = target_npc.talk(topic) # Get the base dialog response

        # Append hints if applicable
        npc_title = f"{FORMAT_TITLE}CONVERSATION WITH {target_npc.name.upper()}{FORMAT_RESET}\n\n"
        if topic:
            formatted_response = f"{npc_title}You ask {target_npc.name} about '{topic}'.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}{turn_in_hint}{offer_hint}"
        else:
            formatted_response = f"{npc_title}You greet {target_npc.name}.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}{turn_in_hint}{offer_hint}"

        # TODO: Add logic here to handle the 'work' topic to trigger quest generation

        return formatted_response


@command("path", ["navigate", "goto"], "movement", "Find path to a room.\nUsage: path <room_id> [region_id]")
def path_handler(args, context):
    if not args: return "Specify destination room."
    world = context["world"]
    target_room_id = args[0]; target_region_id = args[1] if len(args) > 1 else world.current_region_id
    path = world.find_path(world.current_region_id, world.current_room_id, target_region_id, target_room_id)
    if path: return f"Path to {target_region_id}:{target_room_id}: {' → '.join(path)}"
    else: return f"No path found to {target_region_id}:{target_room_id}."

@command("use", ["activate", "drink", "eat", "apply"], "interaction",
         "Use an item from inventory, optionally on a target.\nUsage: use <item> [on <target>]")
def use_handler(args, context):
    player = context["world"].player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args:
        return f"{FORMAT_ERROR}Use what?{FORMAT_RESET}"

    world = context["world"]
    item_name = ""
    target_name = ""
    preposition = "on" # Default preposition
    prep_index = -1

    # Find preposition index ('on', potentially others later)
    supported_prepositions = USE_COMMAND_PREPOSITIONS
    for i, word in enumerate(args):
        if word.lower() in supported_prepositions:
            prep_index = i
            preposition = word.lower()
            break

    if prep_index != -1:
        item_name = " ".join(args[:prep_index]).lower()
        target_name = " ".join(args[prep_index + 1:]).lower()
    else:
        item_name = " ".join(args).lower()

    # Find the item in player's inventory
    item_to_use = player.inventory.find_item_by_name(item_name)
    if not item_to_use:
        return f"{FORMAT_ERROR}You don't have a '{item_name}'.{FORMAT_RESET}"

    # --- Targetted Use ---
    if target_name:
        target = None
        # Search room items
        target = world.find_item_in_room(target_name)
        # Search inventory items (excluding self)
        if not target: target = player.inventory.find_item_by_name(target_name, exclude=item_to_use)
        # Search room NPCs
        if not target: target = world.find_npc_in_room(target_name)
        # Search player self
        if not target and target_name in ["self", "me", player.name.lower()]: target = player

        if not target:
            return f"{FORMAT_ERROR}You don't see a '{target_name}' here to use the {item_to_use.name} on.{FORMAT_RESET}"

        # Call item's use method with target context
        try:
            # Pass player and target to use method
            result = item_to_use.use(user=player, target=target)
            # Handle consumable removal (check uses property)
            if isinstance(item_to_use, Consumable) and item_to_use.get_property("uses", 1) <= 0:
                 player.inventory.remove_item(item_to_use.obj_id)
                 # result might already contain 'used up' message
            return f"{FORMAT_HIGHLIGHT}{result}{FORMAT_RESET}"
        except TypeError as e:
             # Handle cases where use doesn't accept target or specific type
             # Check if the error message indicates wrong arguments
             if "unexpected keyword argument 'target'" in str(e) or "takes 2 positional arguments but 3 were given" in str(e):
                  return f"{FORMAT_ERROR}You can't use the {item_to_use.name} on the {getattr(target, 'name', 'target')}.{FORMAT_RESET}"
             else: # Reraise other TypeErrors
                  raise e
        except Exception as e: # Catch other potential errors during use
             return f"{FORMAT_ERROR}Something went wrong trying to use the {item_to_use.name}: {e}{FORMAT_RESET}"

    # --- Self Use ---
    else:
        # Check if item expects a target
        if isinstance(item_to_use, Key):
             return f"{FORMAT_ERROR}What do you want to use the {item_to_use.name} on? Usage: use <key> on <target>.{FORMAT_RESET}"

        # Call item's use method (only user provided)
        try:
            result = item_to_use.use(user=player)
             # Handle consumable removal
            if isinstance(item_to_use, Consumable) and item_to_use.get_property("uses", 1) <= 0:
                 player.inventory.remove_item(item_to_use.obj_id)
            return f"{FORMAT_HIGHLIGHT}{result}{FORMAT_RESET}"
        except Exception as e:
             return f"{FORMAT_ERROR}Something went wrong trying to use the {item_to_use.name}: {e}{FORMAT_RESET}"

@command("follow", [], "interaction", "Follow an NPC.\nUsage: follow <npc_name> | follow stop")
def follow_handler(args, context):
    world = context["world"]
    player = world.player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args:
        target_npc = world.get_npc(world.player.follow_target) if world.player.follow_target else None
        target_name = target_npc.name if target_npc else "someone"
        return f"You are currently following {target_name}. Type 'follow stop'." if world.player.follow_target else f"Follow whom?"
    cmd_arg = " ".join(args).lower()
    if cmd_arg in FOLLOW_COMMAND_STOP_ALIASES:
        if world.player.follow_target: world.player.follow_target = None; return f"{FORMAT_HIGHLIGHT}You stop following.{FORMAT_RESET}"
        else: return "You aren't following anyone."
    npc_name = cmd_arg; npcs = world.get_current_room_npcs(); found_npc = None
    for npc in npcs:
        if npc_name in npc.name.lower() or npc_name == npc.obj_id: found_npc = npc; break
    if found_npc:
        if world.player.follow_target == found_npc.obj_id: return f"You are already following {found_npc.name}."
        world.player.follow_target = found_npc.obj_id
        return f"{FORMAT_HIGHLIGHT}You start following {found_npc.name}.{FORMAT_RESET}"
    else: return f"{FORMAT_ERROR}No '{npc_name}' here to follow.{FORMAT_RESET}"

# --- Modify trade_handler ---
@command("trade", ["shop"], "interaction", "Initiate trade with a vendor.\nUsage: trade <npc_name>")
def trade_handler(args, context):
    world = context["world"]
    player = world.player

    if not player.is_alive: return f"{FORMAT_ERROR}You cannot trade while dead.{FORMAT_RESET}"

    # Stop previous trade if starting a new one
    if player.trading_with:
        old_vendor = world.get_npc(player.trading_with)
        if old_vendor:
             old_vendor.is_trading = False # <<< Make old vendor resume AI
        player.trading_with = None

    if not args: return f"{FORMAT_ERROR}Trade with whom?{FORMAT_RESET}"

    npc_name = " ".join(args).lower()
    vendor = world.find_npc_in_room(npc_name)

    if not vendor: return f"{FORMAT_ERROR}You don't see '{npc_name}' here.{FORMAT_RESET}"
    if not vendor.properties.get("is_vendor", False): return f"{FORMAT_ERROR}{vendor.name} doesn't seem interested in trading.{FORMAT_RESET}"

    # --- Initiate trade ---
    vendor.is_trading = True # <<< Tell vendor to pause AI
    player.trading_with = vendor.obj_id
    # --- End Initiate ---

    greeting = vendor.dialog.get("trade", vendor.dialog.get("greeting", "What can I do for you?")).format(name=vendor.name)
    response = f"You approach {vendor.name} to trade.\n"
    response += f"{FORMAT_HIGHLIGHT}\"{greeting}\"{FORMAT_RESET}\n\n"
    response += _display_vendor_inventory(player, vendor, world)
    return response

@command("attack", ["kill", "fight", "hit"], "combat", "Attack a target.\nUsage: attack <target_name>")
def attack_handler(args, context):
    world = context["world"]
    player = world.player

    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot attack.{FORMAT_RESET}" # Changed msg slightly
    if not args: return f"{FORMAT_ERROR}Attack whom?{FORMAT_RESET}"

    # --- Stop Trading Logic ---
    if player.trading_with:
        vendor = world.get_npc(player.trading_with)
        vendor_name = vendor.name if vendor else "the vendor"
        if vendor:
            vendor.is_trading = False # Tell vendor to resume AI
        player.trading_with = None
        # Optional: Add message like "(You stop trading to attack.)"
    # --- End Stop Trading ---
    
    target_name = " ".join(args).lower()
    npcs = world.get_current_room_npcs(); target_npc = None
    for npc in npcs: # Prioritize exact match
        if target_name == npc.name.lower() or target_name == npc.obj_id: target_npc = npc; break
    if not target_npc: # Fallback partial match
        for npc in npcs:
            if target_name in npc.name.lower(): target_npc = npc; break
    if not target_npc: return f"{FORMAT_ERROR}No '{target_name}' here to attack.{FORMAT_RESET}"
    if not target_npc.is_alive: return f"{FORMAT_ERROR}{target_npc.name} is already defeated.{FORMAT_RESET}"

    current_time = time.time()
    
    if not player.can_attack(current_time):
        effective_cooldown = player.get_effective_attack_cooldown()
        time_left = effective_cooldown - (current_time - player.last_attack_time)
        time_left = max(0, time_left)
        return f"Not ready. Wait {time_left:.1f}s."

    attack_result = player.attack(target_npc, world)
    return attack_result["message"] # Return the primary message

@command("combat", ["cstat", "fightstatus"], "combat", "Show combat status.")
def combat_status_handler(args, context):
    world = context.get("world"); player = getattr(world, "player", None)
    if not world or not player: return "Error: World/Player missing."
    if not player.in_combat: return "You are not in combat."
    return player.get_combat_status()


# --- NEW COMMANDS ---

@command("equip", ["wear", "wield"], "inventory", "Equip an item from your inventory.\nUsage: equip <item_name> [to <slot_name>]")
def equip_handler(args, context):
    player = context["world"].player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args:
        return f"{FORMAT_ERROR}What do you want to equip?{FORMAT_RESET}"

    item_name = ""
    slot_name = None
    to_index = -1

    # Find 'to' preposition
    if EQUIP_COMMAND_SLOT_PREPOSITION in [a.lower() for a in args]:
         try:
              to_index = [a.lower() for a in args].index(EQUIP_COMMAND_SLOT_PREPOSITION)
              item_name = " ".join(args[:to_index]).lower()
              slot_name = " ".join(args[to_index + 1:]).lower().replace(" ", "_") # e.g. "main hand" -> "main_hand"
         except ValueError: # Should not happen if 'to' is found
              item_name = " ".join(args).lower() # Fallback
    else:
        item_name = " ".join(args).lower()

    # Find item in inventory
    item_to_equip = player.inventory.find_item_by_name(item_name)
    if not item_to_equip:
        return f"{FORMAT_ERROR}You don't have '{item_name}' in your inventory.{FORMAT_RESET}"

    # Call player's equip method
    success, message = player.equip_item(item_to_equip, slot_name)

    if success:
        return f"{FORMAT_SUCCESS}{message}{FORMAT_RESET}"
    else:
        return f"{FORMAT_ERROR}{message}{FORMAT_RESET}"


@command("unequip", ["remove"], "inventory", "Unequip an item.\nUsage: unequip <slot_name>")
def unequip_handler(args, context):
    player = context["world"].player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args:
        # List equipped items if no args
        equipped_text = f"{FORMAT_TITLE}EQUIPPED ITEMS{FORMAT_RESET}\n"
        has_equipped = False
        for slot, item in player.equipment.items():
            if item:
                equipped_text += f"- {slot.replace('_', ' ').capitalize()}: {item.name}\n"
                has_equipped = True
        if not has_equipped: equipped_text += "  (Nothing equipped)\n"
        equipped_text += "\nUsage: unequip <slot_name>"
        return equipped_text

    slot_name = " ".join(args).lower().replace(" ", "_") # e.g., "main hand" -> "main_hand"

    if slot_name not in player.equipment:
        valid_slots = ", ".join(player.equipment.keys())
        return f"{FORMAT_ERROR}Invalid slot '{slot_name}'. Valid slots: {valid_slots}{FORMAT_RESET}"

    success, message = player.unequip_item(slot_name)

    if success:
        return f"{FORMAT_SUCCESS}{message}{FORMAT_RESET}"
    else:
        return f"{FORMAT_ERROR}{message}{FORMAT_RESET}"


@command("put", ["store"], "interaction", "Put an item into a container.\nUsage: put <item_name> in <container_name>")
def put_handler(args, context):
    world = context["world"]
    player = world.player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"

    if PUT_COMMAND_PREPOSITION not in [a.lower() for a in args]:
        return f"{FORMAT_ERROR}Usage: put <item_name> {PUT_COMMAND_PREPOSITION} <container_name>{FORMAT_RESET}"

    try:
        in_index = [a.lower() for a in args].index(PUT_COMMAND_PREPOSITION)
        item_name = " ".join(args[:in_index]).lower()
        container_name = " ".join(args[in_index + 1:]).lower()
    except ValueError:
         return f"{FORMAT_ERROR}Usage: put <item_name> in <container_name>{FORMAT_RESET}"

    if not item_name or not container_name:
        return f"{FORMAT_ERROR}Specify both an item and a container.{FORMAT_RESET}"

    # Find item in player inventory
    item_to_put = player.inventory.find_item_by_name(item_name)
    if not item_to_put:
        return f"{FORMAT_ERROR}You don't have '{item_name}'.{FORMAT_RESET}"

    # Find container (in room or player inventory)
    container = None
    # Check room items
    room_items = world.get_items_in_current_room()
    for item in room_items:
        if isinstance(item, Container) and container_name in item.name.lower():
            container = item
            break
    # Check player inventory
    if not container:
        inv_item = player.inventory.find_item_by_name(container_name)
        if isinstance(inv_item, Container):
            container = inv_item

    if not container:
        return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"

    # Check if container can accept the item
    can_add, msg = container.can_add(item_to_put)
    if not can_add:
        return f"{FORMAT_ERROR}{msg}{FORMAT_RESET}"

    # Remove item from player inventory (quantity 1)
    removed_item, quantity_removed, remove_msg = player.inventory.remove_item(item_to_put.obj_id, 1)
    if not removed_item:
        return f"{FORMAT_ERROR}Failed to get '{item_name}' from inventory: {remove_msg}{FORMAT_RESET}"

    # Add item to container
    if container.add_item(removed_item):
        return f"{FORMAT_SUCCESS}You put the {removed_item.name} in the {container.name}.{FORMAT_RESET}"
    else:
        # Should not happen if can_add passed, but attempt to put back in inventory
        player.inventory.add_item(removed_item, 1)
        return f"{FORMAT_ERROR}Could not put the {removed_item.name} in the {container.name}.{FORMAT_RESET}"

@command("open", [], "interaction", "Open a container.\nUsage: open <container_name>")
def open_handler(args, context):
    world = context["world"]
    player = world.player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args:
        return f"{FORMAT_ERROR}Open what?{FORMAT_RESET}"

    container_name = " ".join(args).lower()

    # Find container (in room or player inventory)
    container = None
    # Check room items first
    room_items = world.get_items_in_current_room()
    for item in room_items:
        if isinstance(item, Container) and container_name in item.name.lower():
            container = item
            break
    # Check player inventory if not found in room
    if not container:
        inv_item = player.inventory.find_item_by_name(container_name)
        if isinstance(inv_item, Container):
            container = inv_item

    if not container:
        return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"

    # Try to open it using the container's method
    result_message = container.open()
    return f"{FORMAT_HIGHLIGHT}{result_message}{FORMAT_RESET}"

@command("close", [], "interaction", "Close a container.\nUsage: close <container_name>")
def close_handler(args, context):
    world = context["world"]
    player = world.player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args:
        return f"{FORMAT_ERROR}Close what?{FORMAT_RESET}"

    container_name = " ".join(args).lower()

    # Find container (in room or player inventory)
    container = None
    # Check room items first
    room_items = world.get_items_in_current_room()
    for item in room_items:
        if isinstance(item, Container) and container_name in item.name.lower():
            container = item
            break
    # Check player inventory if not found in room
    if not container:
        inv_item = player.inventory.find_item_by_name(container_name)
        if isinstance(inv_item, Container):
            container = inv_item

    if not container:
        return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"

    # Try to close it
    result_message = container.close()
    return f"{FORMAT_HIGHLIGHT}{result_message}{FORMAT_RESET}"

@command("cast", ["c"], "magic", "Cast a known spell.\nUsage: cast <spell_name> [on <target_name>]")
def cast_handler(args, context):
    world = context["world"]
    player = world.player
    current_time = time.time()

    if not player.is_alive:
        return f"{FORMAT_ERROR}You cannot cast spells while dead.{FORMAT_RESET}"

    if not args:
        # List known spells if no args given
        spells_known_text = player.get_status().split(f"{FORMAT_TITLE}SPELLS KNOWN{FORMAT_RESET}")
        if len(spells_known_text) > 1:
             return f"{FORMAT_TITLE}SPELLS KNOWN{FORMAT_RESET}\n" + spells_known_text[1].strip() + "\n\nUsage: cast <spell_name> [on <target_name>]"
        else:
             return f"{FORMAT_ERROR}You don't know any spells.{FORMAT_RESET}\n\nUsage: cast <spell_name> [on <target_name>]"

    target_name = ""
    spell_name = ""
    on_index = -1

    # Find 'on' preposition
    if CAST_COMMAND_PREPOSITION in [a.lower() for a in args]:
         try:
              on_index = [a.lower() for a in args].index(CAST_COMMAND_PREPOSITION)
              spell_name = " ".join(args[:on_index]).lower()
              target_name = " ".join(args[on_index + 1:]).lower()
         except ValueError: # Should not happen
              spell_name = " ".join(args).lower() # Fallback
    else:
        spell_name = " ".join(args).lower()

    # Find the spell
    spell = get_spell_by_name(spell_name)
    if not spell:
        return f"{FORMAT_ERROR}You don't know a spell called '{spell_name}'.{FORMAT_RESET}"

    # Determine the target
    target = None
    if spell.target_type == "self":
        target = player
    elif target_name:
        # Look for target: NPCs first, then player self
        target = world.find_npc_in_room(target_name)
        if not target and target_name in TARGET_SELF_ALIASES + [player.name.lower()]:
             target = player
        # Add finding other players later if multiplayer
        if not target:
             return f"{FORMAT_ERROR}You don't see '{target_name}' here to target.{FORMAT_RESET}"
    elif spell.target_type == "enemy":
         # If no target specified for enemy spell, try player's combat target
         if player.in_combat and player.combat_target and player.combat_target.is_alive:
              target = player.combat_target
              # Verify target is still in the room
              if target not in world.get_current_room_npcs():
                   target = None # Target left the room
         if not target:
              # Or target the first hostile NPC in the room? Or require target?
              hostiles = [npc for npc in world.get_current_room_npcs() if npc.faction == 'hostile']
              if hostiles:
                   target = hostiles[0] # Target first hostile if no combat target
              else:
                   return f"{FORMAT_ERROR}Who do you want to cast {spell.name} on?{FORMAT_RESET}"
    elif spell.target_type == "friendly":
         # Default to self if no target specified
         target = player
    else: # Default target if not self/enemy/friendly and no name given
        target = player # Default to self

    if not target:
         # Should have been caught earlier, but safety check
         return f"{FORMAT_ERROR}Invalid target for {spell.name}.{FORMAT_RESET}"

    # Validate target type vs spell requirement
    is_enemy = isinstance(target, NPC) and target.faction == "hostile"
    is_friendly_npc = isinstance(target, NPC) and target.faction != "hostile"
    is_self = target == player

    # can't target friendlies right now; if this changes, remember to add stoptrade logic similar to this:
    # --- Stop Trading Logic ---
    # if player.trading_with:
    #     vendor = world.get_npc(player.trading_with)
    #     vendor_name = vendor.name if vendor else "the vendor"
    #     if vendor:
    #         vendor.is_trading = False # Tell vendor to resume AI
    #     player.trading_with = None
    # Optional: Add message like "(You stop trading to cast a spell.)"
    # --- End Stop Trading ---

    if spell.target_type == "enemy" and not is_enemy:
         return f"{FORMAT_ERROR}You can only cast {spell.name} on hostile targets.{FORMAT_RESET}"
    if spell.target_type == "friendly" and not (is_friendly_npc or is_self):
         return f"{FORMAT_ERROR}You can only cast {spell.name} on yourself or friendly targets.{FORMAT_RESET}"
    # Add self check if needed, though often friendly includes self

    # Attempt to cast
    result = player.cast_spell(spell, target, current_time, world)

    # Return the resulting message
    return result["message"]

@command("spells", ["spl", "magic"], "magic", "List spells you know.\nUsage: spells [spell_name]")
def spells_handler(args, context):
    world = context["world"]
    player = world.player
    current_time = time.time() # For checking cooldowns

    if not player.known_spells:
        return f"{FORMAT_ERROR}You don't know any spells.{FORMAT_RESET}"

    # If a spell name is provided, show detailed info for that spell
    if args:
        spell_name = " ".join(args).lower()
        found_spell = None
        for spell_id in player.known_spells:
            spell = get_spell(spell_id)
            if spell and spell.name.lower() == spell_name:
                found_spell = spell
                break

        if not found_spell:
             # Allow searching by partial name if exact match failed
             for spell_id in player.known_spells:
                 spell = get_spell(spell_id)
                 if spell and spell_name in spell.name.lower():
                      found_spell = spell
                      break

        if found_spell:
            # Display detailed info for one spell
            spell = found_spell
            cooldown_end = player.spell_cooldowns.get(spell.spell_id, 0)
            cooldown_status = ""
            if current_time < cooldown_end:
                time_left = cooldown_end - current_time
                cooldown_status = f" [{FORMAT_ERROR}On Cooldown: {time_left:.1f}s{FORMAT_RESET}]"

            info = f"{FORMAT_TITLE}{spell.name.upper()}{FORMAT_RESET}\n\n"
            info += f"{FORMAT_CATEGORY}Description:{FORMAT_RESET} {spell.description}\n"
            info += f"{FORMAT_CATEGORY}Mana Cost:{FORMAT_RESET} {spell.mana_cost}\n"
            info += f"{FORMAT_CATEGORY}Cooldown:{FORMAT_RESET} {spell.cooldown:.1f}s{cooldown_status}\n"
            info += f"{FORMAT_CATEGORY}Target:{FORMAT_RESET} {spell.target_type.capitalize()}\n"
            info += f"{FORMAT_CATEGORY}Effect:{FORMAT_RESET} {spell.effect_type.capitalize()} ({spell.effect_value} base value)\n"
            if spell.level_required > 1:
                 req_color = FORMAT_SUCCESS if player.level >= spell.level_required else FORMAT_ERROR
                 info += f"{FORMAT_CATEGORY}Level Req:{FORMAT_RESET} {req_color}{spell.level_required}{FORMAT_RESET}\n"
            return info
        else:
            return f"{FORMAT_ERROR}You don't know a spell called '{' '.join(args)}'.{FORMAT_RESET}\nType 'spells' to see all known spells."

    # If no specific spell name, list all known spells
    else:
        response = f"{FORMAT_TITLE}KNOWN SPELLS{FORMAT_RESET}\n\n"
        spell_lines = []
        sorted_spells = sorted(list(player.known_spells), key=lambda sid: getattr(get_spell(sid), 'name', sid))

        for spell_id in sorted_spells:
            spell = get_spell(spell_id)
            if spell:
                cooldown_end = player.spell_cooldowns.get(spell_id, 0)
                cooldown_status = ""
                if current_time < cooldown_end:
                    time_left = cooldown_end - current_time
                    cooldown_status = f" [{FORMAT_ERROR}CD {time_left:.1f}s{FORMAT_RESET}]"

                level_req_str = f" (L{spell.level_required})" if spell.level_required > 1 else ""
                req_color = FORMAT_SUCCESS if player.level >= spell.level_required else FORMAT_ERROR
                level_req_display = f" ({req_color}L{spell.level_required}{FORMAT_RESET})" if spell.level_required > 1 else ""


                line = f"- {FORMAT_HIGHLIGHT}{spell.name}{FORMAT_RESET}{level_req_display}: {spell.mana_cost} MP{cooldown_status}"
                spell_lines.append(line)
            else:
                spell_lines.append(f"- {FORMAT_ERROR}Unknown Spell ID: {spell_id}{FORMAT_RESET}")

        response += "\n".join(spell_lines)
        response += f"\n\n{FORMAT_CATEGORY}Mana:{FORMAT_RESET} {player.mana}/{player.max_mana}\n"
        response += "\nType 'spells <spell_name>' for more details."
        return response

@command("selljunk", ["sj"], "interaction", "Sell all junk items in your inventory to a nearby vendor.")
def sell_junk_handler(args, context):
    world = context["world"]
    player = world.player

    if not player.is_alive:
        return f"{FORMAT_ERROR}You can't trade while dead.{FORMAT_RESET}"

    # Find a vendor in the current room
    vendor = None
    npcs = world.get_current_room_npcs()
    for npc in npcs:
        # Check if NPC is marked as a vendor or has trade dialog
        is_vendor = npc.get_property("is_vendor", False) or \
                    (hasattr(npc, 'dialog') and "trade" in npc.dialog) or \
                    any(vt in npc.obj_id.lower() for vt in VENDOR_ID_HINTS)
        if is_vendor:
            vendor = npc
            break

    if not vendor:
        return f"{FORMAT_ERROR}There is no one here to sell junk to.{FORMAT_RESET}"

    items_to_sell = []
    total_value_calculated = 0 # calculate expected gold

    # Iterate through a copy of inventory slots to allow removal
    slots_to_process = list(player.inventory.slots)
    for slot in slots_to_process:
        if slot.item and isinstance(slot.item, Junk):
            items_to_sell.append({"item": slot.item, "quantity": slot.quantity})
            # Calculate sell price using the BUY multiplier (from vendor's perspective)
            sell_price_per_item = int(slot.item.value * DEFAULT_VENDOR_BUY_MULTIPLIER)
            sell_price_per_item = max(0, sell_price_per_item) # Ensure non-negative price, 0 if value * multiplier < 1
            total_value_calculated += sell_price_per_item * slot.quantity

    if not items_to_sell:
        return f"You have no junk items to sell to {vendor.name}."

    # Confirm sale (optional, for now just sell)
    # print(f"DEBUG: Items to sell: {items_to_sell}") # Debug print
    # print(f"DEBUG: Total value: {total_value}")     # Debug print

    sell_messages = []
    items_actually_sold_count = 0
    gold_actually_received = 0

    for item_info in items_to_sell:
        item_obj = item_info["item"]
        quantity_to_remove = item_info["quantity"]

        removed_item_type, actual_removed_count, remove_msg = player.inventory.remove_item(
            item_obj.obj_id, quantity_to_remove
        )

        if removed_item_type and actual_removed_count > 0:
            items_actually_sold_count += actual_removed_count
            # Calculate gold received for *this specific transaction*
            sell_price = max(0, int(removed_item_type.value * DEFAULT_VENDOR_BUY_MULTIPLIER))
            gold_for_this_batch = sell_price * actual_removed_count
            gold_actually_received += gold_for_this_batch
            # Add to message
            sell_messages.append(f"- Sold {actual_removed_count} x {removed_item_type.name} for {gold_for_this_batch} gold.")
        else:
            print(f"Warning: Failed to remove {item_obj.name} during sell junk: {remove_msg}")
            sell_messages.append(f"- {FORMAT_ERROR}Failed to sell {item_obj.name}.{FORMAT_RESET}")

    # Grant gold directly to player attribute
    if gold_actually_received > 0:
        player.gold += gold_actually_received
        sell_messages.append(f"\nReceived {gold_actually_received} gold.")
    elif items_actually_sold_count > 0:
         sell_messages.append("\nReceived no gold (items were worthless).") # If sold items had 0 value after multiplier

    # Format final message
    final_message = f"You sell your junk to {vendor.name}:\n"
    final_message += "\n".join(sell_messages)
    final_message += f"\n\nYour gold: {player.gold}" # Show updated gold

    return final_message

@command("list", ["browse"], "interaction", "List items available from the current vendor.\nUsage: list")
def list_handler(args, context):
    world = context["world"]
    player = world.player

    if not player.trading_with:
        return f"{FORMAT_ERROR}You are not currently trading with anyone.{FORMAT_RESET}"

    vendor = world.get_npc(player.trading_with)
    if not vendor:
        # Vendor might have despawned or moved? End trade.
        player.trading_with = None
        return f"{FORMAT_ERROR}The person you were trading with is no longer here.{FORMAT_RESET}"

    # Check if still in the same room
    if vendor.current_region_id != player.current_region_id or vendor.current_room_id != player.current_room_id:
        player.trading_with = None
        return f"{FORMAT_ERROR}{vendor.name} is no longer here.{FORMAT_RESET}"

    return _display_vendor_inventory(player, vendor, world)

@command("buy", [], "interaction", "Buy an item from the current vendor.\nUsage: buy <item_name> [quantity]")
def buy_handler(args, context):
    world = context["world"]
    player = world.player

    if not player.trading_with:
        return f"{FORMAT_ERROR}You need to 'trade' with someone first.{FORMAT_RESET}"

    vendor = world.get_npc(player.trading_with)
    if not vendor:
        player.trading_with = None
        return f"{FORMAT_ERROR}The vendor you were trading with is gone.{FORMAT_RESET}"

    # Check if still in the same room
    if vendor.current_region_id != player.current_region_id or vendor.current_room_id != player.current_room_id:
        player.trading_with = None
        return f"{FORMAT_ERROR}{vendor.name} is no longer here.{FORMAT_RESET}"

    if not args:
        return f"{FORMAT_ERROR}Buy what? Usage: buy <item_name> [quantity]{FORMAT_RESET}"

    # Parse arguments
    item_name = ""
    quantity = 1
    try:
        # Check if last argument is a number for quantity
        if args[-1].isdigit():
            quantity = int(args[-1])
            if quantity <= 0:
                return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            item_name = " ".join(args[:-1]).lower()
        else:
            item_name = " ".join(args).lower()
    except ValueError:
        return f"{FORMAT_ERROR}Invalid quantity specified.{FORMAT_RESET}"

    if not item_name:
         return f"{FORMAT_ERROR}You must specify an item name.{FORMAT_RESET}"

    # Find the item in vendor's stock list
    found_item_ref = None
    found_template = None
    for item_ref in vendor.properties.get("sells_items", []):
        item_id = item_ref.get("item_id")
        if not item_id: continue
        template = world.item_templates.get(item_id)
        if template:
            name_in_template = template.get("name", "").lower()
            # Allow matching by template ID or name
            if item_name == item_id.lower() or item_name == name_in_template:
                found_item_ref = item_ref
                found_template = template
                break
            # Fallback: partial name match
            elif item_name in name_in_template:
                 found_item_ref = item_ref
                 found_template = template
                 # Don't break here, maybe a more exact match exists later

    if not found_item_ref or not found_template:
        return f"{FORMAT_ERROR}{vendor.name} doesn't sell '{item_name}'. Type 'list' to see wares.{FORMAT_RESET}"

    # Calculate price
    item_id = found_template["obj_id"] = found_item_ref["item_id"] # Ensure obj_id is set for factory
    base_value = found_template.get("value", 0)
    price_multiplier = found_item_ref.get("price_multiplier", DEFAULT_VENDOR_SELL_MULTIPLIER)
    buy_price_per_item = max(VENDOR_MIN_BUY_PRICE, int(base_value * price_multiplier))
    total_cost = buy_price_per_item * quantity

    # Check player gold
    if player.gold < total_cost:
        return f"{FORMAT_ERROR}You don't have enough gold (Need {total_cost}, have {player.gold}).{FORMAT_RESET}"

    # Check if item is stackable (needed for inventory check)
    is_stackable = found_template.get("stackable", False)

    # Create a temporary item instance to check inventory constraints
    # Pass world context to factory
    temp_item = ItemFactory.create_item_from_template(item_id, world)
    if not temp_item:
         return f"{FORMAT_ERROR}Internal error creating item '{item_id}'. Cannot buy.{FORMAT_RESET}"

    can_add, inv_msg = player.inventory.can_add_item(temp_item, quantity)
    if not can_add:
        return f"{FORMAT_ERROR}{inv_msg}{FORMAT_RESET}" # Use message from inventory check

    # --- Transaction ---
    player.gold -= total_cost

    # Add item(s) to player inventory
    items_added_successfully = 0
    for _ in range(quantity):
         # Create a new instance for each item added
         item_instance = ItemFactory.create_item_from_template(item_id, world)
         if item_instance:
              added, add_msg = player.inventory.add_item(item_instance, 1) # Add one at a time
              if added:
                   items_added_successfully += 1
              else:
                   # This *shouldn't* happen if can_add_item passed, but handle it
                   print(f"Error: Failed to add '{item_instance.name}' to inventory despite passing checks: {add_msg}")
                   # Attempt to refund gold for items that couldn't be added
                   player.gold += buy_price_per_item * (quantity - items_added_successfully)
                   return f"{FORMAT_ERROR}Failed to add all items to inventory. Transaction partially reverted.{FORMAT_RESET}"
         else:
              # Handle creation failure
              player.gold += buy_price_per_item * (quantity - items_added_successfully) # Refund
              return f"{FORMAT_ERROR}Failed to create item instance during purchase. Transaction cancelled.{FORMAT_RESET}"

    item_display_name = found_template.get("name", item_id)
    plural_suffix = "" if quantity == 1 else "s" # Simple plural
    return f"{FORMAT_SUCCESS}You buy {quantity} {item_display_name}{plural_suffix} for {total_cost} gold.{FORMAT_RESET}\nYour Gold: {player.gold}"


@command("sell", [], "interaction", "Sell an item from your inventory to the current vendor.\nUsage: sell <item_name> [quantity]")
def sell_handler(args, context):
    world = context["world"]
    player = world.player

    if not player.trading_with:
        return f"{FORMAT_ERROR}You need to 'trade' with someone first.{FORMAT_RESET}"

    vendor = world.get_npc(player.trading_with)
    if not vendor:
        player.trading_with = None
        return f"{FORMAT_ERROR}The vendor you were trading with is gone.{FORMAT_RESET}"

    # Check if still in the same room
    if vendor.current_region_id != player.current_region_id or vendor.current_room_id != player.current_room_id:
        player.trading_with = None
        return f"{FORMAT_ERROR}{vendor.name} is no longer here.{FORMAT_RESET}"

    if not args:
        return f"{FORMAT_ERROR}Sell what? Usage: sell <item_name> [quantity]{FORMAT_RESET}"

    # Parse arguments
    item_name = ""
    quantity = 1
    try:
        if args[-1].isdigit():
            quantity = int(args[-1])
            if quantity <= 0: return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            item_name = " ".join(args[:-1]).lower()
        else:
            item_name = " ".join(args).lower()
    except ValueError: return f"{FORMAT_ERROR}Invalid quantity specified.{FORMAT_RESET}"

    if not item_name: return f"{FORMAT_ERROR}You must specify an item name.{FORMAT_RESET}"

    # Find item in player's inventory
    item_to_sell = player.inventory.find_item_by_name(item_name)
    if not item_to_sell:
        return f"{FORMAT_ERROR}You don't have '{item_name}' to sell.{FORMAT_RESET}"

    # Check if player has enough quantity
    player_has_quantity = sum(slot.quantity for slot in player.inventory.slots if slot.item and slot.item.obj_id == item_to_sell.obj_id)
    if player_has_quantity < quantity:
        return f"{FORMAT_ERROR}You only have {player_has_quantity} {item_to_sell.name}(s) to sell.{FORMAT_RESET}"

    # --- NEW: Check if vendor buys this item TYPE ---
    can_sell = False
    vendor_buy_types = vendor.properties.get("buys_item_types", []) # Get list like ["Weapon", "Armor"]
    item_type_name = item_to_sell.__class__.__name__ # Get class name ("Weapon", "Consumable", etc.)

    if VENDOR_CAN_BUY_ALL_ITEMS: # Check global config override
        can_sell = True
    elif item_type_name in vendor_buy_types: # Check vendor's specific list
        can_sell = True
    # If the item's direct type isn't listed, check if the vendor buys the base "Item" type
    # AND the item is *actually* just a base Item instance (not a subclass like Weapon/Armor etc.)
    # This prevents selling Weapons to someone who only buys "Item" unless "Weapon" is also listed.
    elif "item" in vendor_buy_types and item_type_name == "item":
         can_sell = True

    if not can_sell:
        return f"{FORMAT_ERROR}{vendor.name} is not interested in buying {item_to_sell.name}.{FORMAT_RESET}"

    # Calculate sell price
    sell_price_per_item = max(VENDOR_MIN_SELL_PRICE, int(item_to_sell.value * DEFAULT_VENDOR_BUY_MULTIPLIER))
    total_gold_gain = sell_price_per_item * quantity

    # --- Transaction ---
    # Remove item(s) from player inventory
    removed_item_type, actual_removed_count, remove_msg = player.inventory.remove_item(item_to_sell.obj_id, quantity)

    if not removed_item_type or actual_removed_count != quantity:
         # This indicates an issue - maybe quantity check failed or item vanished?
         # It's safer to not give gold if removal failed partially/completely.
         print(f"Error selling {item_to_sell.name}: Removal failed or removed wrong quantity ({actual_removed_count}/{quantity}). Msg: {remove_msg}")
         # Attempt to add back what might have been removed? Complex. Best to just fail.
         return f"{FORMAT_ERROR}Something went wrong removing {item_to_sell.name} from your inventory. Sale cancelled.{FORMAT_RESET}"

    # Add gold to player
    player.gold += total_gold_gain

    # Optional: Add sold item to vendor's dynamic inventory (future enhancement)
    # vendor.inventory.add_item(removed_item_type, actual_removed_count)

    plural_suffix = "" if quantity == 1 else "s"
    return f"{FORMAT_SUCCESS}You sell {quantity} {removed_item_type.name}{plural_suffix} for {total_gold_gain} gold.{FORMAT_RESET}\nYour Gold: {player.gold}"


@command("stoptrade", ["stop", "done"], "interaction", "Stop trading with the current vendor.\nUsage: stoptrade")
def stoptrade_handler(args, context):
    player = context["world"].player
    world = context["world"] # Get world context

    if not player.trading_with:
        return "You are not currently trading with anyone."

    vendor = world.get_npc(player.trading_with)
    vendor_name = vendor.name if vendor else "the vendor"

    # --- Stop Trading Logic ---
    if vendor:
        vendor.is_trading = False # <<< Tell vendor to resume AI
    player.trading_with = None
    # --- End Stop Trading ---

    return f"You stop trading with {vendor_name}."

@command("repair", [], "interaction", "Ask a capable NPC to repair an item.\nUsage: repair <item_name>")
def repair_handler(args, context):
    world = context["world"]
    player = world.player

    if not player.is_alive:
        return f"{FORMAT_ERROR}You can't get items repaired while dead.{FORMAT_RESET}"
    if not args:
        return f"{FORMAT_ERROR}What item do you want to repair? Usage: repair <item_name>{FORMAT_RESET}"

    item_name_to_repair = " ".join(args).lower()

    # --- Find Repair NPC ---
    repair_npc = None
    npcs_in_room = world.get_current_room_npcs()
    for npc in npcs_in_room:
        if npc.properties.get("can_repair", False):
            repair_npc = npc
            break # Found someone who can repair

    if not repair_npc:
        return f"{FORMAT_ERROR}There is no one here who can repair items.{FORMAT_RESET}"

    # --- Find Item (Inventory or Equipment) ---
    item_to_repair = None
    # Check inventory first
    item_to_repair = player.inventory.find_item_by_name(item_name_to_repair)

    # Check equipment if not in inventory
    if not item_to_repair:
        for slot, equipped_item in player.equipment.items():
            if equipped_item and item_name_to_repair in equipped_item.name.lower():
                 # Check if this item actually *can* be repaired (has durability)
                 if equipped_item.get_property("durability") is not None and \
                    equipped_item.get_property("max_durability") is not None:
                     item_to_repair = equipped_item
                     break
                 else: # Found by name, but not repairable
                      return f"{FORMAT_ERROR}The {equipped_item.name} cannot be repaired.{FORMAT_RESET}"

    if not item_to_repair:
        return f"{FORMAT_ERROR}You don't have an item called '{item_name_to_repair}' that can be repaired.{FORMAT_RESET}"

    # --- USE HELPER TO CALCULATE COST AND CHECK VALIDITY ---
    repair_cost, error_msg = _calculate_repair_cost(item_to_repair)

    if error_msg: # Item not repairable
        return f"{FORMAT_ERROR}{error_msg}{FORMAT_RESET}"
    if repair_cost == 0: # Item already repaired
        return f"Your {item_to_repair.name} is already in perfect condition."
    if repair_cost is None: # Should be caught by error_msg, but safety check
         return f"{FORMAT_ERROR}Cannot determine repair cost for {item_to_repair.name}.{FORMAT_RESET}"
    # --- END COST CALCULATION ---

    # Check Player Gold (existing logic)
    if player.gold < repair_cost:
        return f"{FORMAT_ERROR}You need {repair_cost} gold to repair the {item_to_repair.name}, but you only have {player.gold}.{FORMAT_RESET}"

    # Perform Repair (existing logic)
    player.gold -= repair_cost
    max_durability = item_to_repair.get_property("max_durability") # Get max dura again
    item_to_repair.update_property("durability", max_durability)

    return f"{FORMAT_SUCCESS}You pay {repair_cost} gold. {repair_npc.name} repairs your {item_to_repair.name} to perfect condition.{FORMAT_RESET}\nYour Gold: {player.gold}"

@command("repaircost", ["checkrepair", "rcost"], "interaction", "Check the cost to repair an item.\nUsage: repaircost <item_name>")
def repaircost_handler(args, context):
    world = context["world"]
    player = world.player

    if not args:
        return f"{FORMAT_ERROR}What item do you want to check the repair cost for? Usage: repaircost <item_name>{FORMAT_RESET}"

    item_name_to_check = " ".join(args).lower()

    # --- Find Repair NPC (Still need one present to quote price) ---
    repair_npc = None
    npcs_in_room = world.get_current_room_npcs()
    for npc in npcs_in_room:
        if npc.properties.get("can_repair", False):
            repair_npc = npc
            break

    if not repair_npc:
        # Maybe allow checking price even if no repairer is present? Or require one?
        # Let's require one for now for consistency.
        return f"{FORMAT_ERROR}There is no one here who can quote a repair price.{FORMAT_RESET}"

    # --- Find Item (Inventory or Equipment - same logic as repair) ---
    item_to_check = None
    # Check inventory first
    item_to_check = player.inventory.find_item_by_name(item_name_to_check)
    # Check equipment if not in inventory
    if not item_to_check:
        for slot, equipped_item in player.equipment.items():
             if equipped_item and item_name_to_check in equipped_item.name.lower():
                  if equipped_item.get_property("durability") is not None and \
                     equipped_item.get_property("max_durability") is not None:
                      item_to_check = equipped_item
                      break
                  else: return f"{FORMAT_ERROR}The {equipped_item.name} cannot be repaired.{FORMAT_RESET}"

    if not item_to_check:
        return f"{FORMAT_ERROR}You don't have an item called '{item_name_to_check}' that can be repaired.{FORMAT_RESET}"

    # --- USE HELPER TO CALCULATE COST AND CHECK VALIDITY ---
    repair_cost, error_msg = _calculate_repair_cost(item_to_check)

    if error_msg: # Item not repairable
        return f"{FORMAT_ERROR}{error_msg}{FORMAT_RESET}"
    if repair_cost == 0: # Item already repaired
        return f"Your {item_to_check.name} does not need repairing."
    if repair_cost is None: # Should be caught by error_msg
         return f"{FORMAT_ERROR}Cannot determine repair cost for {item_to_check.name}.{FORMAT_RESET}"
    # --- END COST CALCULATION ---

    # --- Display the cost ---
    return f"{repair_npc.name} quotes a price of {FORMAT_HIGHLIGHT}{repair_cost} gold{FORMAT_RESET} to fully repair your {item_to_check.name}."

@command(name="give", aliases=[], category="interaction",
         help_text="Give an item from your inventory to someone.\nUsage: give <item_name> to <npc_name>")
def give_handler(args, context):
    world = context["world"]
    player = world.player

    if not player.is_alive:
        return f"{FORMAT_ERROR}You can't give items while dead.{FORMAT_RESET}"

    # --- Argument Parsing ---
    if GIVE_COMMAND_PREPOSITION not in [a.lower() for a in args]:
        return f"{FORMAT_ERROR}Usage: give <item_name> {GIVE_COMMAND_PREPOSITION} <npc_name>{FORMAT_RESET}"

    try:
        to_index = [a.lower() for a in args].index(GIVE_COMMAND_PREPOSITION)
        item_name = " ".join(args[:to_index]).lower()
        npc_name = " ".join(args[to_index + 1:]).lower()
    except ValueError:
         return f"{FORMAT_ERROR}Usage: give <item_name> to <npc_name>{FORMAT_RESET}"

    if not item_name or not npc_name:
        return f"{FORMAT_ERROR}Specify both an item and who to give it to.{FORMAT_RESET}"
    # --- End Argument Parsing ---

    # --- Find Item in Player Inventory ---
    item_to_give = player.inventory.find_item_by_name(item_name) # find_item_by_name returns the instance
    if not item_to_give:
        # Special check for "package" if the generated name is different
        if "package" in item_name:
            for slot in player.inventory.slots:
                 if slot.item and "package" in slot.item.name.lower():
                      item_to_give = slot.item
                      break # Found a package-like item
        if not item_to_give: # Still not found
             return f"{FORMAT_ERROR}You don't have '{item_name}'.{FORMAT_RESET}"
    # --- End Find Item ---

    # --- Find NPC in Current Room ---
    target_npc = world.find_npc_in_room(npc_name)
    if not target_npc:
        return f"{FORMAT_ERROR}You don't see '{npc_name}' here.{FORMAT_RESET}"
    # --- End Find NPC ---

    # --- NEW: Quest Item Pre-Check ---
    is_delivery_quest_item = False
    required_recipient_id = None
    matching_quest_id = None
    matching_quest_data = None
    quest_plugin = None # Will get later if needed

    # Check player's quest log for active delivery quests matching THIS item instance
    if hasattr(player, 'quest_log'):
        for q_id, q_data in player.quest_log.items():
            objective = q_data.get("objective", {})
            # Check using the *specific instance ID* stored in the quest objective
            if (q_data.get("state") == "active" and
                q_data.get("type") == "deliver" and
                objective.get("item_instance_id") == item_to_give.obj_id): # Match specific item instance
                is_delivery_quest_item = True
                required_recipient_id = objective.get("recipient_instance_id")
                matching_quest_id = q_id
                matching_quest_data = q_data
                # Load plugin instance now that we know we might need it
                if get_service_locator().has_service("plugin:quest_system_plugin"):
                    quest_plugin = get_service_locator().get_service("plugin:quest_system_plugin")
                break # Found the quest associated with this exact package

    # --- Decision Branch based on Quest Item Check ---
    if is_delivery_quest_item:
        # This IS a specific delivery item
        if target_npc.obj_id == required_recipient_id:
            # --- CORRECT RECIPIENT: Perform Quest Completion ---
            # 1. Remove the specific quest item instance from player inventory
            removed = player.inventory.remove_item_instance(item_to_give)
            if not removed:
                # This indicates a problem, the item existed but couldn't be removed
                print(f"{FORMAT_ERROR}CRITICAL ERROR: Failed to remove quest package '{item_to_give.name}' instance {item_to_give.obj_id} from inventory. Quest {matching_quest_id}{FORMAT_RESET}")
                return f"{FORMAT_ERROR}Something went wrong removing the package. Please report this bug.{FORMAT_RESET}"

            # 2. Grant Rewards
            rewards = matching_quest_data.get("rewards", {})
            xp_reward = rewards.get("xp", 0)
            gold_reward = rewards.get("gold", 0)
            reward_messages = []
            if xp_reward > 0:
                 leveled_up_msg = ""
                 leveled_up = player.gain_experience(xp_reward)
                 reward_messages.append(f"{xp_reward} XP")
                 if leveled_up: reward_messages.append(f"{FORMAT_HIGHLIGHT}(Leveled up!){FORMAT_RESET}")
            if gold_reward > 0:
                 player.gold += gold_reward
                 reward_messages.append(f"{gold_reward} Gold")

            # 3. Update Quest State (Remove from active log)
            if matching_quest_id in player.quest_log:
                 del player.quest_log[matching_quest_id]
                 # Persist the change (though quest log is usually saved with player anyway)
                 # player.update_quest(matching_quest_id, None) # Or similar if needed

            # 4. Trigger Board Replenishment
            if quest_plugin:
                 quest_plugin.replenish_board(matching_quest_id)

            # 5. Format Completion Message
            completion_message = f"{FORMAT_SUCCESS}[Quest Complete] {matching_quest_data.get('title', 'Task')}{FORMAT_RESET}\n"
            # Get specific NPC completion dialog if available, else generic
            npc_response_key = f"complete_{matching_quest_id}" # Check specific first
            npc_response = target_npc.dialog.get(npc_response_key,
                          target_npc.dialog.get("quest_complete", # Generic completion
                          f"\"Ah, thank you for delivering this!\" says {target_npc.name}."))
            completion_message += f"{FORMAT_HIGHLIGHT}{npc_response}{FORMAT_RESET}\n"
            if reward_messages:
                 completion_message += "You receive: " + ", ".join(reward_messages) + "."

            return completion_message
            # --- End Quest Completion Logic ---

        else:
            # --- WRONG RECIPIENT: Block the 'give' action ---
            correct_recipient_name = matching_quest_data.get("objective", {}).get("recipient_name", "someone else")
            return f"{FORMAT_ERROR}You should give the {item_to_give.name} to {correct_recipient_name}, not {target_npc.name}.{FORMAT_RESET}"

    else:
        # --- NOT a specific delivery quest item: Allow normal 'give' ---
        # (Remove item from player, maybe add to NPC, maybe just consumed)
        removed_item_type, removed_count, remove_msg = player.inventory.remove_item(item_to_give.obj_id, 1)
        if not removed_item_type or removed_count != 1:
            return f"{FORMAT_ERROR}Failed to take '{item_to_give.name}' from inventory: {remove_msg}{FORMAT_RESET}"

        # --- Optional: Add to NPC inventory ---
        # added_to_npc, npc_inv_msg = target_npc.inventory.add_item(removed_item_type, 1)
        # if not added_to_npc:
        #     print(f"Warning: NPC {target_npc.name} could not receive item {removed_item_type.name}: {npc_inv_msg}")
        #     # Give item back to player? Drop it? For now, let it vanish.
        # --- End Optional Add to NPC ---

        # Standard success message for non-quest giving
        return f"{FORMAT_SUCCESS}You give the {item_to_give.name} to {target_npc.name}.{FORMAT_RESET}"


@command("take", ["pickup"], "interaction", "Pick up an item from the room.\nUsage: take [all|quantity] <item_name> | take all")
def take_handler(args, context):
    return _handle_item_acquisition(args, context, "take")

@command("get", ["takefrom"], "interaction", "Get an item from a container.\nUsage: get <item_name> from <container_name>")
def get_handler(args, context):
    world = context["world"]
    player = world.player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"

    if GET_COMMAND_PREPOSITION in [a.lower() for a in args]: 
        try:
            from_index = [a.lower() for a in args].index(GET_COMMAND_PREPOSITION)
            item_name = " ".join(args[:from_index]).lower()
            container_name = " ".join(args[from_index + 1:]).lower()
        except ValueError:
            return f"{FORMAT_ERROR}Usage: get <item_name> from <container_name>{FORMAT_RESET}"

        if not item_name or not container_name:
            return f"{FORMAT_ERROR}Specify both an item and a container.{FORMAT_RESET}"

        # Find container (in room or player inventory)
        container = None
        # Check room items
        room_items = world.get_items_in_current_room()
        for item in room_items:
            if isinstance(item, Container) and container_name in item.name.lower():
                container = item
                break
        # Check player inventory
        if not container:
            inv_item = player.inventory.find_item_by_name(container_name)
            if isinstance(inv_item, Container):
                container = inv_item

        if not container:
            return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"

        # Check if container is open
        if not container.properties.get("is_open", False):
            return f"{FORMAT_ERROR}The {container.name} is closed.{FORMAT_RESET}"

        # Find item inside container
        item_to_get = container.find_item_by_name(item_name)
        if not item_to_get:
            return f"{FORMAT_ERROR}You don't see '{item_name}' inside the {container.name}.{FORMAT_RESET}"

        # Check if player can carry the item
        can_carry, carry_msg = player.inventory.can_add_item(item_to_get)
        if not can_carry:
            return f"{FORMAT_ERROR}{carry_msg}{FORMAT_RESET}"

        # Remove item from container
        if container.remove_item(item_to_get):
            # Add item to player inventory
            added_success, add_msg = player.inventory.add_item(item_to_get, 1)
            if added_success:
                return f"{FORMAT_SUCCESS}You get the {item_to_get.name} from the {container.name}.{FORMAT_RESET}\n{add_msg}"
            else:
                # Put item back in container if adding to inventory failed
                container.add_item(item_to_get)
                return f"{FORMAT_ERROR}Could not take the {item_to_get.name}: {add_msg}{FORMAT_RESET}"
    else: # Assume 'take' logic if 'from' is missing
        return _handle_item_acquisition(args, context, "get") # Pass correct verb

if TYPE_CHECKING:
    from world.world import World
def _display_vendor_inventory(player: Player, vendor: NPC, world: 'World') -> str:
    """Helper function to format and display a vendor's inventory for sale."""
    if not vendor or not hasattr(vendor, 'properties'):
        return f"{FORMAT_ERROR}Cannot access vendor data.{FORMAT_RESET}"

    vendor_items_refs = vendor.properties.get("sells_items", [])
    if not vendor_items_refs:
        return f"{vendor.name} has nothing to sell right now."

    display_lines = [f"{FORMAT_TITLE}{vendor.name}'s Wares:{FORMAT_RESET}\n"]
    items_available = False

    for item_ref in vendor_items_refs:
        item_id = item_ref.get("item_id")
        if not item_id: continue

        template = world.item_templates.get(item_id)
        if not template:
            print(f"Warning: Vendor {vendor.name} has unknown item_id '{item_id}' in sells_list.")
            continue

        item_name = template.get("name", "Unknown Item")
        base_value = template.get("value", 0)
        price_multiplier = item_ref.get("price_multiplier", DEFAULT_VENDOR_SELL_MULTIPLIER)

        # Calculate final price (player buys from vendor)
        buy_price = max(VENDOR_MIN_BUY_PRICE, int(base_value * price_multiplier))

        display_lines.append(f"- {item_name:<{VENDOR_LIST_ITEM_NAME_WIDTH}} | Price: {buy_price:>{VENDOR_LIST_PRICE_WIDTH}} gold")
        items_available = True

    if not items_available:
        return f"{vendor.name} has nothing to sell right now."

    display_lines.append(f"\nYour Gold: {player.gold}")
    display_lines.append("\nCommands: list, buy <item> [qty], sell <item> [qty], stoptrade")
    return "\n".join(display_lines)

from items.item import Item
def _calculate_repair_cost(item: Item) -> Tuple[Optional[int], Optional[str]]:
    """
    Calculates the cost to repair an item.

    Args:
        item: The Item instance to check.

    Returns:
        A tuple: (cost, error_message).
        - If repairable and needs repair: (cost, None)
        - If already repaired: (0, None)
        - If not repairable: (None, error_message)
    """
    current_durability = item.get_property("durability")
    max_durability = item.get_property("max_durability")

    if current_durability is None or max_durability is None:
        return None, f"The {item.name} doesn't have durability."

    if current_durability >= max_durability:
        return 0, None # No cost, already repaired

    # Calculate cost (Simple Full Repair Cost)
    base_value = item.value
    repair_cost = max(REPAIR_MINIMUM_COST, int(base_value * REPAIR_COST_PER_VALUE_POINT))

    return repair_cost, None # Return calculated cost, no error

def _handle_item_acquisition(args: List[str], context: Dict[str, Any], command_verb: str) -> str:
    """Core logic for taking/getting items from the current room."""
    world = context["world"]
    player = world.player
    if not player.is_alive: return f"{FORMAT_ERROR}You can't {command_verb} things while dead.{FORMAT_RESET}"

    item_name = ""
    quantity_requested = 1
    take_all = False
    take_all_specific = False # Flag for "take all <item>"

    if not args:
        return f"{FORMAT_ERROR}{command_verb.capitalize()} what?{FORMAT_RESET}"

    # --- Argument Parsing ---
    if args[0].lower() == "all":
        take_all = True
        if len(args) > 1:
            item_name = " ".join(args[1:]).lower()
            take_all_specific = True # Taking all of a specific item
        else:
            # Just "take all" - target all items in the room
            item_name = "" # No specific item name
    elif args[0].isdigit():
        try:
            quantity_requested = int(args[0])
            if quantity_requested <= 0:
                return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            if len(args) > 1:
                item_name = " ".join(args[1:]).lower()
            else:
                # User typed "take 5" with no item name
                return f"{FORMAT_ERROR}{command_verb.capitalize()} {quantity_requested} of what?{FORMAT_RESET}"
        except ValueError: # Should not happen due to isdigit(), but safety
             return f"{FORMAT_ERROR}Invalid quantity '{args[0]}'.{FORMAT_RESET}"
    else:
        # Default: take 1 <item name>
        quantity_requested = 1
        item_name = " ".join(args).lower()

    # --- Item Identification ---
    items_in_room = world.get_items_in_current_room()
    if not items_in_room and not take_all: # Check if room is empty only if not taking 'all'
        if item_name:
            return f"{FORMAT_ERROR}You don't see any '{item_name}' here.{FORMAT_RESET}"
        else: # Should be caught by initial arg check, but safety
             return f"{FORMAT_ERROR}There is nothing here to {command_verb}.{FORMAT_RESET}"

    target_items_by_id: Dict[str, List[Item]] = {} # item_id -> list of instances

    if take_all and not take_all_specific:
        # "take all" - grab everything possible
        for item in items_in_room:
            if item.obj_id not in target_items_by_id:
                target_items_by_id[item.obj_id] = []
            target_items_by_id[item.obj_id].append(item)
        if not target_items_by_id:
            return f"There is nothing here to {command_verb}."

    elif item_name:
        # Find specific item(s) by name
        matches = []
        exact_match_found = False
        # Pass 1: Exact matches (name or ID)
        for item in items_in_room:
            if item_name == item.name.lower() or item_name == item.obj_id:
                matches.append(item)
                exact_match_found = True

        # Pass 2: Partial matches (only if no exact match)
        if not exact_match_found:
            for item in items_in_room:
                if item_name in item.name.lower():
                    matches.append(item)

        if not matches:
            return f"{FORMAT_ERROR}You don't see any '{item_name}' here.{FORMAT_RESET}"

        # Handle ambiguity (multiple *different* item types matched)
        matched_ids = {item.obj_id for item in matches}
        if len(matched_ids) > 1:
            # Create list of unique names for ambiguous matches
            ambiguous_names = sorted(list({item.name for item in matches}))
            return f"{FORMAT_ERROR}Did you mean: {', '.join(ambiguous_names)}?{FORMAT_RESET}"

        # If only one item type matched, group all its instances
        target_item_id = matches[0].obj_id
        target_items_by_id[target_item_id] = [item for item in items_in_room if item.obj_id == target_item_id]

    else:
        # Should have been caught earlier (e.g., "take 5" with no item)
        return f"{FORMAT_ERROR}{command_verb.capitalize()} what?{FORMAT_RESET}"


    # --- Process Acquisition ---
    items_taken_summary: Dict[str, Dict[str, Any]] = {} # item_id -> {"name": str, "taken": int}
    cant_carry_message = ""
    room_depleted_message = ""
    total_items_processed = 0

    # Iterate through the identified item types to take
    # Use list() to allow modifying the dict during iteration if needed later
    for item_id, instances_in_room in list(target_items_by_id.items()):
        if not instances_in_room: continue # Skip if somehow empty

        first_item = instances_in_room[0] # Sample item for properties
        available_quantity = len(instances_in_room)

        if take_all: # take all OR take all <item>
            qty_to_attempt = available_quantity
        else: # take <qty> <item> OR take <item>
            qty_to_attempt = min(quantity_requested, available_quantity)

        if qty_to_attempt <= 0: continue # Nothing to take of this type

        # Check inventory capacity iteratively
        actually_taken_count = 0
        for i in range(qty_to_attempt):
            item_instance = instances_in_room[i] # Get the specific instance
            can_add, msg = player.inventory.can_add_item(item_instance, 1)

            if can_add:
                # Transfer this specific instance
                removed_from_room = world.remove_item_instance_from_room(
                    world.current_region_id, world.current_room_id, item_instance
                )
                if removed_from_room:
                    added_to_inv, add_msg = player.inventory.add_item(item_instance, 1)
                    if added_to_inv:
                        actually_taken_count += 1
                    else:
                        # Critical error: Failed to add after check and removal. Try to put back.
                        print(f"CRITICAL ERROR: Failed to add {item_instance.name} to inventory after check! {add_msg}")
                        world.add_item_to_room(world.current_region_id, world.current_room_id, item_instance) # Put back
                        cant_carry_message = f" (Stopped because inventory became full unexpectedly for {item_instance.name})"
                        break # Stop processing this item type
                else:
                     # Critical error: Failed to remove from room
                     print(f"CRITICAL ERROR: Failed to remove {item_instance.name} from room!")
                     # Don't increment count, stop processing this item
                     break
            else:
                # Cannot carry this item (or any more)
                if actually_taken_count == 0 and i == 0: # Couldn't even take the first one
                     cant_carry_message = f" You cannot carry the {first_item.name}."
                else: # Took some, but couldn't take more
                     cant_carry_message = f" (You cannot carry any more {simple_plural(first_item.name)})"
                break # Stop trying to take this item type

        # Update summary
        if actually_taken_count > 0:
            if item_id not in items_taken_summary:
                items_taken_summary[item_id] = {"name": first_item.name, "taken": 0}
            items_taken_summary[item_id]["taken"] += actually_taken_count
            total_items_processed += actually_taken_count

        # Check if we took less than available because we didn't request "all" or hit inv limits
        if not take_all and actually_taken_count < available_quantity and not cant_carry_message:
             pass # Normal operation, took requested amount < available
        elif actually_taken_count < available_quantity and cant_carry_message:
             pass # Stopped due to inventory limit, message already set
        elif actually_taken_count > 0 and actually_taken_count == available_quantity and qty_to_attempt < available_quantity:
             # This case means we requested less than available, took all we requested, and emptied the room *of the requested amount*
             pass # Handled by success message construction
        elif actually_taken_count < available_quantity and take_all and not cant_carry_message:
             # This should not happen if take_all=True unless there was an error
             print(f"Warning: Logic error during 'take all {first_item.name}'. Took {actually_taken_count}/{available_quantity}")


    # --- Construct Final Message ---
    if not items_taken_summary:
        # Nothing was taken at all
        if cant_carry_message:
             return f"{FORMAT_ERROR}{cant_carry_message.strip()}{FORMAT_RESET}"
        elif take_all and not take_all_specific: # 'take all' but room was empty
             return "There is nothing here to take."
        else: # Specific item requested but none found/taken
             # Initial check should have caught this, but fallback
             return f"{FORMAT_ERROR}You couldn't {command_verb} any '{item_name}'.{FORMAT_RESET}"

    # Build success message parts
    success_parts = []
    for item_id, data in items_taken_summary.items():
        name = data["name"]
        taken_count = data["taken"]
        if taken_count == 1:
             success_parts.append(f"{get_article(name)} {name}")
        else:
             success_parts.append(f"{taken_count} {simple_plural(name)}")

    # Combine parts into a sentence
    if not success_parts: # Should not happen if items_taken_summary is populated
         final_message = f"{FORMAT_ERROR}An unknown error occurred during item acquisition.{FORMAT_RESET}"
    elif len(success_parts) == 1:
         final_message = f"{FORMAT_SUCCESS}You {command_verb} {success_parts[0]}.{FORMAT_RESET}"
    elif len(success_parts) == 2:
         final_message = f"{FORMAT_SUCCESS}You {command_verb} {success_parts[0]} and {success_parts[1]}.{FORMAT_RESET}"
    else:
         all_but_last = ", ".join(success_parts[:-1])
         last_item_part = success_parts[-1]
         final_message = f"{FORMAT_SUCCESS}You {command_verb} {all_but_last}, and {last_item_part}.{FORMAT_RESET}"

    # Append carry/depletion messages if they occurred
    if cant_carry_message:
        final_message += f"{FORMAT_HIGHLIGHT}{cant_carry_message}{FORMAT_RESET}"

    return final_message
