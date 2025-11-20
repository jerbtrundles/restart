# commands/quest.py
import uuid
from commands.command_system import command, registered_commands
from config import FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, FORMAT_HIGHLIGHT, FORMAT_CATEGORY, FORMAT_TITLE, QUEST_BOARD_ALIASES
from items.item_factory import ItemFactory
from player import Player
from world import world

def _is_player_at_quest_board(player: Player, quest_manager) -> bool:
    """Checks if the player's current location is one of the valid quest board locations."""
    board_locations = quest_manager.config.get("quest_board_locations", [])
    player_location_str = f"{player.current_region_id}:{player.current_room_id}"
    return player_location_str in board_locations

@command(name="look board", aliases=QUEST_BOARD_ALIASES, category="interaction", help_text="Look at the quest board for available tasks.")
def look_board_handler(args, context):
    world = context["world"]
    player = world.player
    quest_manager = world.quest_manager

    if not _is_player_at_quest_board(player, quest_manager):
        return f"{FORMAT_ERROR}You don't see a quest board here.{FORMAT_RESET}"

    # <<< FIX #1: Define 'available_quests' by getting it from the world object.
    available_quests = world.quest_board

    if not available_quests:
        return "The quest board is currently empty."

    response = f"{FORMAT_TITLE}Quest Board{FORMAT_RESET}\n" + "-"*20 + "\nAvailable Tasks:\n\n"
    for i, quest_data in enumerate(available_quests):
        giver_instance_id = quest_data.get("giver_instance_id")
        rewards = quest_data.get("rewards", {})
        
        giver_name = "Quest Board Notice"
        if giver_instance_id != "quest_board":
            # <<< FIX #2: Call get_npc() directly on the 'world' instance.
            giver_npc = world.get_npc(giver_instance_id) 
            giver_name = giver_npc.name if giver_npc else "Unknown"

        objective = quest_data.get("objective", {});
        quest_type = quest_data.get("type")
        quantity_summary = ""
        if quest_type in ["kill", "fetch"]:
            quantity = objective.get("required_quantity")
            if quantity:
                quantity_summary = f" ({quantity})"
        
        response += (f"{FORMAT_CATEGORY}[{i + 1}]{FORMAT_RESET} {quest_data.get('title', 'Unnamed Quest')}{FORMAT_HIGHLIGHT}{quantity_summary}{FORMAT_RESET}\n"
                    f"   Giver: {giver_name}\n"
                    f"   Reward: {rewards.get('xp', 0)} XP, {rewards.get('gold', 0)} Gold\n\n")
        
    response += f"Type '{FORMAT_HIGHLIGHT}accept quest <#>{FORMAT_RESET}' to take a task."
    return response

@command(name="accept quest", aliases=["accept"], category="interaction", help_text="Accept a quest from the board.\nUsage: accept quest <number>")
def accept_quest_handler(args, context):
    world = context["world"]
    player = world.player
    quest_manager = world.quest_manager

    if not _is_player_at_quest_board(player, quest_manager):
        return f"{FORMAT_ERROR}You need to be at a quest board to accept tasks.{FORMAT_RESET}"
    if not args:
        return f"{FORMAT_ERROR}Which quest number do you want to accept?{FORMAT_RESET}"

    quest_num_str = args[0]
    if not quest_num_str.isdigit():
        return f"{FORMAT_ERROR}'{quest_num_str}' is not a valid quest number.{FORMAT_RESET}"

    try:
        quest_index = int(quest_num_str) - 1
    except ValueError:
        return f"{FORMAT_ERROR}'{quest_num_str}' is not a valid quest number.{FORMAT_RESET}"

    if quest_index < 0 or quest_index >= len(world.quest_board):
        return f"{FORMAT_ERROR}Invalid quest number. Check the board again.{FORMAT_RESET}"

    quest_to_accept = world.quest_board.pop(quest_index)
    quest_to_accept["state"] = "active"
    
    quest_instance_id = quest_to_accept.get("instance_id")
    if not quest_instance_id:
        # safety fallback in case a quest somehow gets on the board without an ID
        quest_instance_id = f"quest_fallback_{uuid.uuid4().hex[:6]}"
        quest_to_accept["instance_id"] = quest_instance_id

    if quest_to_accept.get("type") == "instance":
        quest_to_accept["completion_check_enabled"] = False
        success, message, giver_npc_id = world.instantiate_quest_region(quest_to_accept)
        if not success:
            world.quest_board.insert(quest_index, quest_to_accept)
            return f"{FORMAT_ERROR}Could not start quest: {message}{FORMAT_RESET}"
        
        giver_npc = world.get_npc(giver_npc_id)
        if giver_npc:
            entry_point = quest_to_accept.get("entry_point", {})
            entry_region = world.get_region(entry_point.get("region_id"))
            entry_room = entry_region.get_room(entry_point.get("room_id")) if entry_region else None
            location_desc = entry_room.name if entry_room else "a nearby house"
            
            extended_greeting = giver_npc.dialog.get("greeting_extended", "").format(entry_location_desc=location_desc)
            message += f" \"{extended_greeting}\""
            message += f"\n(You can now ask {giver_npc.name} to '{FORMAT_HIGHLIGHT}guide{FORMAT_RESET}' you there.)"

        quest_to_accept["giver_instance_id"] = giver_npc_id if giver_npc_id else "quest_board"

        acceptance_message = f"{FORMAT_SUCCESS}[Quest Accepted] {quest_to_accept.get('title')}{FORMAT_RESET}"
        acceptance_message += f"\n{FORMAT_HIGHLIGHT}{message}{FORMAT_RESET}"
        acceptance_message += "\n(Check your 'journal' for details)"

        player.quest_log[quest_instance_id] = quest_to_accept
        quest_manager.replenish_board(None)
        return acceptance_message

    if quest_to_accept.get("type") == "kill":
        quest_to_accept["objective"]["current_quantity"] = 0

    if quest_to_accept.get("type") == "deliver":
        objective = quest_to_accept["objective"]
        package = ItemFactory.create_item_from_template(
            objective["item_template_id"],
            world,
            obj_id=objective["item_instance_id"],
            name=objective["item_to_deliver_name"],
            description=objective["item_to_deliver_description"]
        )
        can_add, msg = player.inventory.can_add_item(package)
        if not can_add:
            world.quest_board.insert(quest_index, quest_to_accept)
            return f"{FORMAT_ERROR}Cannot accept delivery, your inventory is too full! ({msg}){FORMAT_RESET}"
        player.inventory.add_item(package)

    player.quest_log[quest_instance_id] = quest_to_accept
    quest_manager.replenish_board(None)
    return f"{FORMAT_SUCCESS}[Quest Accepted] {quest_to_accept.get('title')}{FORMAT_RESET}\n(Check your 'journal' for details)"

@command(name="journal", aliases=["quests", "log", "j"], category="information",
         help_text="View your active or completed quests.\nUsage: journal [completed]")
def journal_handler(args, context):
    player = context["world"].player
    if not hasattr(player, 'quest_log'): player.quest_log = {}
    if not hasattr(player, 'completed_quest_log'): player.completed_quest_log = {}
    
    # Ensure the archived log exists for the check
    if not hasattr(player, 'archived_quest_log'): player.archived_quest_log = {}

    if args and args[0].lower() == "completed":
        # Combine both completed and archived quests for display
        all_completed_quests = {**player.completed_quest_log, **player.archived_quest_log}

        if not all_completed_quests:
            return "You have not completed any quests yet."
        
        response = f"{FORMAT_TITLE}Completed Quests ({len(all_completed_quests)}){FORMAT_RESET}\n{'-'*20}\n\n"
        # Sort by title for consistent display
        sorted_completed = sorted(all_completed_quests.values(), key=lambda q: q.get("title", ""))
        
        for quest_data in sorted_completed:
            response += f"- {quest_data.get('title', 'Unnamed Quest')}\n"
        return response.strip()

    # --- Active quest logic ---
    if not player.quest_log: return "Your quest journal is empty."

    response = f"{FORMAT_TITLE}Active Quests{FORMAT_RESET}\n{'-'*20}\n\n"
    found_active = False
    sorted_active = sorted(player.quest_log.values(), key=lambda q: q.get("title", ""))
    
    for quest_data in sorted_active:
         if quest_data.get("state") in ["active", "ready_to_complete"]:
             found_active = True
             objective = quest_data.get("objective", {}); q_type = quest_data.get("type", "unknown")
             title = quest_data.get("title", "Unnamed Quest")
             giver_npc = context["world"].get_npc(quest_data.get("giver_instance_id")); giver_name = giver_npc.name if giver_npc else "Unknown"
             response += f"{FORMAT_CATEGORY}{title}{FORMAT_RESET} (Giver: {giver_name})\n"
             state_display = quest_data.get("state", "unknown").replace('_', ' ').capitalize(); response += f"  Status: {state_display}\n"
             if q_type == "kill": response += f"  Task: Defeat {objective.get('current_quantity', 0)}/{objective.get('required_quantity', '?')} {objective.get('target_name_plural', '?')} in {objective.get('location_hint', '?')}.\n"
             elif q_type == "fetch":
                  required_item_id = objective.get("item_id", ""); current_have = player.inventory.count_item(required_item_id)
                  response += f"  Task: Gather {current_have}/{objective.get('required_quantity', '?')} {objective.get('item_name_plural', '?')} (from {objective.get('source_enemy_name_plural', '?')} in {objective.get('location_hint', '?')}).\n"
             elif q_type == "deliver":
                  package_instance_id = objective.get("item_instance_id", ""); has_package = player.inventory.find_item_by_id(package_instance_id) is not None
                  package_status = f"{FORMAT_HIGHLIGHT}(You have the package){FORMAT_RESET}" if has_package else f"{FORMAT_ERROR}(You don't have the package!){FORMAT_RESET}"
                  response += f"  Task: Deliver the {objective.get('item_to_deliver_name', '?')} to {objective.get('recipient_name', '?')} in {objective.get('recipient_location_description', '?')}. {package_status}\n"
             else: response += f"  Task: {quest_data.get('description', 'Complete the objective.')}\n"
             if quest_data.get('state') == "ready_to_complete": response += f"  {FORMAT_HIGHLIGHT}Ready to turn in to {giver_name}!{FORMAT_RESET}\n"
             response += "\n"

    if not found_active: return "You have no active quests."
    return response.strip()