# plugins/quest_system_plugin/commands.py
from commands.command_system import command, registered_commands
from core.config import FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, FORMAT_HIGHLIGHT, FORMAT_CATEGORY, FORMAT_TITLE
from items.item_factory import ItemFactory # Needed for Deliver quest item generation

from core.config import FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, FORMAT_HIGHLIGHT, FORMAT_CATEGORY
from items.item_factory import ItemFactory

# Use the original function name convention, it's fine now
def register_commands(plugin):

    @command(name="look board", aliases=["examine board", "l board"], category="interaction",
             help_text="Look at the quest board for available tasks.", plugin_id=plugin.plugin_id) # <<< CORRECT DECORATOR + plugin_id arg
    def look_board_handler(args, context):
        # ... (handler logic) ...
        world = plugin.world
        player = world.player
        board_loc = plugin.config.get("quest_board_location", "town:town_square")
        board_region, board_room = board_loc.split(":")

        if player.current_region_id != board_region or player.current_room_id != board_room:
            return f"{FORMAT_ERROR}You don't see a quest board here.{FORMAT_RESET}"

        board_data = world.get_plugin_data(plugin.plugin_id, plugin.quest_board_key, {"available_quests": []})
        available_quests = board_data.get("available_quests", [])

        if not available_quests:
            return "The quest board is currently empty."

        response = f"{FORMAT_TITLE}Quest Board{FORMAT_RESET}\n"
        response += f"{'-'*20}\n"
        response += "Available Tasks:\n\n"

        for i, quest_data in enumerate(available_quests):
            quest_id = i + 1
            giver_npc = world.get_npc(quest_data.get("giver_instance_id"))
            giver_name = giver_npc.name if giver_npc else "Unknown"
            rewards = quest_data.get("rewards", {})
            reward_str = f"{rewards.get('xp', 0)} XP, {rewards.get('gold', 0)} Gold"

            response += f"{FORMAT_CATEGORY}[{quest_id}]{FORMAT_RESET} {quest_data.get('title', 'Unnamed Quest')} ({quest_data.get('type', '?').capitalize()})\n"
            response += f"   Giver: {giver_name}\n"
            response += f"   Reward: {reward_str}\n\n"

        response += f"Type '{FORMAT_HIGHLIGHT}accept quest <#>{FORMAT_RESET}' to take a task."
        return response

    @command(name="accept quest", aliases=["accept"], category="interaction",
             help_text="Accept a quest from the board.\nUsage: accept quest <board_#>", plugin_id=plugin.plugin_id) # <<< CORRECT
    def accept_quest_handler(args, context):
        world = plugin.world
        player = world.player
        board_loc = plugin.config.get("quest_board_location", "town:town_square")
        board_region, board_room = board_loc.split(":")

        if player.current_region_id != board_region or player.current_room_id != board_room: return f"{FORMAT_ERROR}You need to be at the quest board to accept tasks.{FORMAT_RESET}"
        if not args: return f"{FORMAT_ERROR}Which quest number do you want to accept? Look at the board first.{FORMAT_RESET}"
        try: quest_index = int(args[0]) - 1
        except ValueError: return f"{FORMAT_ERROR}'{args[0]}' is not a valid quest number.{FORMAT_RESET}"

        board_data = world.get_plugin_data(plugin.plugin_id, plugin.quest_board_key, {"available_quests": []})
        available_quests = board_data.get("available_quests", [])

        if quest_index < 0 or quest_index >= len(available_quests): return f"{FORMAT_ERROR}Invalid quest number. Check the board again.{FORMAT_RESET}"

        quest_to_accept = available_quests.pop(quest_index)
        quest_to_accept["state"] = "active"
        if quest_to_accept.get("type") == "kill": quest_to_accept["objective"]["current_quantity"] = 0

        delivery_package_instance = None
        if quest_to_accept.get("type") == "deliver":
             objective = quest_to_accept.get("objective", {})
             item_template_id = objective.get("item_template_id")
             item_instance_id = objective.get("item_instance_id")
             item_name = objective.get("item_to_deliver_name")
             item_description = objective.get("item_to_deliver_description")

             if not all([item_template_id, item_instance_id, item_name, item_description]):
                  available_quests.insert(quest_index, quest_to_accept); world.set_plugin_data(plugin.plugin_id, plugin.quest_board_key, board_data)
                  return f"{FORMAT_ERROR}Quest data seems corrupted. Cannot accept delivery.{FORMAT_RESET}"

             package_item = ItemFactory.create_item_from_template(item_template_id, world, obj_id=item_instance_id, name=item_name, description=item_description)
             if not package_item:
                 available_quests.insert(quest_index, quest_to_accept); world.set_plugin_data(plugin.plugin_id, plugin.quest_board_key, board_data)
                 return f"{FORMAT_ERROR}Error preparing delivery package item. Cannot accept quest.{FORMAT_RESET}"

             can_add, msg = player.inventory.can_add_item(package_item, 1)
             if not can_add:
                 available_quests.insert(quest_index, quest_to_accept); world.set_plugin_data(plugin.plugin_id, plugin.quest_board_key, board_data)
                 return f"{FORMAT_ERROR}You cannot accept this delivery, your inventory is too full for the package! ({msg}){FORMAT_RESET}"

             delivery_package_instance = package_item
             quest_to_accept["objective"]["item_instance_id"] = item_instance_id
             objective.pop("item_template_id", None); objective.pop("item_to_deliver_description", None)

        if not hasattr(player, 'quest_log'): player.quest_log = {}
        player.quest_log[quest_to_accept["instance_id"]] = quest_to_accept

        if delivery_package_instance:
             added, add_msg = player.inventory.add_item(delivery_package_instance, 1)
             if not added:
                 print(f"{FORMAT_ERROR}CRITICAL ERROR: Failed to add delivery package '{delivery_package_instance.name}' after accepting quest! {add_msg}{FORMAT_RESET}")
                 del player.quest_log[quest_to_accept["instance_id"]]
                 available_quests.insert(quest_index, quest_to_accept); world.set_plugin_data(plugin.plugin_id, plugin.quest_board_key, board_data)
                 return f"{FORMAT_ERROR}Error adding delivery package to inventory. Quest cancelled.{FORMAT_RESET}"

        world.set_plugin_data(plugin.plugin_id, plugin.quest_board_key, board_data)
        plugin.replenish_board(None)
        return f"{FORMAT_SUCCESS}[Quest Accepted] {quest_to_accept.get('title', 'Task')}{FORMAT_RESET}\n(Check your 'journal' for details)"


    # --- USE THE CORRECT DECORATOR ---
    @command(name="journal", aliases=["quests", "log", "j"], category="information",
             help_text="View your active quests.", plugin_id=plugin.plugin_id) # <<< CORRECT
    def journal_handler(args, context):
        # ... (handler logic - ensure it's complete from previous steps) ...
        player = plugin.world.player
        if not hasattr(player, 'quest_log') or not player.quest_log: return "Your quest journal is empty."

        response = f"{FORMAT_TITLE}Active Quests{FORMAT_RESET}\n{'-'*20}\n\n"; found_active = False
        for quest_id, quest_data in player.quest_log.items():
             if quest_data.get("state") in ["active", "ready_to_complete"]:
                 found_active = True
                 objective = quest_data.get("objective", {}); q_type = quest_data.get("type", "unknown")
                 title = quest_data.get("title", "Unnamed Quest")
                 giver_npc = plugin.world.get_npc(quest_data.get("giver_instance_id")); giver_name = giver_npc.name if giver_npc else "Unknown"
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
