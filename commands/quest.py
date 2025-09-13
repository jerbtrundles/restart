# commands/quest.py
from commands.command_system import command, registered_commands
from core.config import FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, FORMAT_HIGHLIGHT, FORMAT_CATEGORY, FORMAT_TITLE, QUEST_BOARD_ALIASES
from items.item_factory import ItemFactory
from player import Player

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

    available_quests = world.quest_board
    if not available_quests:
        return "The quest board is currently empty."

    response = f"{FORMAT_TITLE}Quest Board{FORMAT_RESET}\n" + "-"*20 + "\nAvailable Tasks:\n\n"
    for i, quest_data in enumerate(available_quests):
        giver = world.get_npc(quest_data.get("giver_instance_id"))
        rewards = quest_data.get("rewards", {})
        
        # <<< ADD THIS BLOCK TO GET THE QUEST QUANTITY >>>
        objective = quest_data.get("objective", {})
        quest_type = quest_data.get("type")
        quantity_summary = ""
        if quest_type in ["kill", "fetch"]:
            quantity = objective.get("required_quantity")
            if quantity:
                quantity_summary = f" ({quantity})"
        # <<< END BLOCK >>>

        # <<< MODIFY THIS LINE TO INCLUDE THE SUMMARY >>>
        response += (f"{FORMAT_CATEGORY}[{i + 1}]{FORMAT_RESET} {quest_data.get('title', 'Unnamed Quest')}{FORMAT_HIGHLIGHT}{quantity_summary}{FORMAT_RESET}\n"
                    f"   Giver: {giver.name if giver else 'Unknown'}\n"
                    f"   Reward: {rewards.get('xp', 0)} XP, {rewards.get('gold', 0)} Gold\n\n")
        
    response += f"Type '{FORMAT_HIGHLIGHT}accept quest <#>{FORMAT_RESET}' to take a task."
    return response

@command(name="accept", category="interaction", help_text="Accept a quest from the board.\nUsage: accept [quest] <number>")
def accept_quest_handler(args, context):
    world = context["world"]
    player = world.player
    quest_manager = world.quest_manager

    if not _is_player_at_quest_board(player, quest_manager):
        return f"{FORMAT_ERROR}You need to be at a quest board to accept tasks.{FORMAT_RESET}"
    if not args:
        return f"{FORMAT_ERROR}Which quest number do you want to accept?{FORMAT_RESET}"

    # --- FIX: Robust argument parsing ---
    quest_num_str = ""
    # Handles "accept quest 3"
    if len(args) > 1 and args[0].lower() == "quest" and args[1].isdigit():
        quest_num_str = args[1]
    # Handles "accept 3"
    elif len(args) == 1 and args[0].isdigit():
        quest_num_str = args[0]
    # Handles errors
    else:
        potential_num_arg = args[1] if len(args) > 1 and args[0].lower() == "quest" else args[0]
        return f"{FORMAT_ERROR}'{potential_num_arg}' is not a valid quest number.{FORMAT_RESET}"
    # --- END FIX ---

    try:
        quest_index = int(quest_num_str) - 1
    except ValueError:
        # This is a fallback, but the logic above should prevent this.
        return f"{FORMAT_ERROR}'{quest_num_str}' is not a valid quest number.{FORMAT_RESET}"

    if quest_index < 0 or quest_index >= len(world.quest_board):
        return f"{FORMAT_ERROR}Invalid quest number. Check the board again.{FORMAT_RESET}"

    quest_to_accept = world.quest_board.pop(quest_index)
    quest_to_accept["state"] = "active"
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

    player.quest_log[quest_to_accept["instance_id"]] = quest_to_accept
    quest_manager.replenish_board(None)
    return f"{FORMAT_SUCCESS}[Quest Accepted] {quest_to_accept.get('title')}{FORMAT_RESET}\n(Check your 'journal' for details)"

@command(name="journal", aliases=["quests", "log", "j"], category="information",
         help_text="View your active or completed quests.\nUsage: journal [completed]")
def journal_handler(args, context):
    player = context["world"].player
    if not hasattr(player, 'quest_log'): player.quest_log = {}
    if not hasattr(player, 'completed_quest_log'): player.completed_quest_log = {}

    # <<< ADD LOGIC TO HANDLE "completed" ARGUMENT >>>
    if args and args[0].lower() == "completed":
        if not player.completed_quest_log:
            return "You have not completed any quests yet."
        
        response = f"{FORMAT_TITLE}Completed Quests ({len(player.completed_quest_log)}){FORMAT_RESET}\n{'-'*20}\n\n"
        # Sort by title for consistent display
        sorted_completed = sorted(player.completed_quest_log.values(), key=lambda q: q.get("title", ""))
        
        for quest_data in sorted_completed:
            response += f"- {quest_data.get('title', 'Unnamed Quest')}\n"
        return response.strip()
    # <<< END ADDITION >>>

    # --- Existing logic for active quests ---
    if not player.quest_log: return "Your quest journal is empty."

    response = f"{FORMAT_TITLE}Active Quests{FORMAT_RESET}\n{'-'*20}\n\n"
    found_active = False
    # Sort active quests by title
    sorted_active = sorted(player.quest_log.values(), key=lambda q: q.get("title", ""))
    
    for quest_data in sorted_active:
         if quest_data.get("state") in ["active", "ready_to_complete"]:
             found_active = True
             # ... (rest of the existing display logic for active quests is unchanged) ...
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
