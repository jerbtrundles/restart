# engine/commands/interaction/npcs.py
from engine.commands.command_system import command
from engine.config import (
    FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE,
    FOLLOW_COMMAND_STOP_ALIASES
)
from engine.utils.utils import format_name_for_display

@command("talk", ["speak", "chat", "ask"], "interaction", "Talk to an NPC.\nUsage: talk <npc_name> [topic | complete quest]")
def talk_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    
    if args and args[0].lower() == "to": args = args[1:]
    if not args: return f"{FORMAT_ERROR}Talk to whom?{FORMAT_RESET}"

    npcs_in_room = world.get_current_room_npcs()
    best_match_npc = None
    best_match_len = 0

    # Greedy Name Matching
    for i in range(len(args), 0, -1):
        potential_name = " ".join(args[:i]).lower()
        found = None
        for npc in npcs_in_room:
            if npc.name.lower() == potential_name or npc.obj_id == potential_name: found = npc; break
        if not found:
            for npc in npcs_in_room:
                if potential_name in npc.name.lower(): found = npc; break
        if found:
            best_match_npc = found; best_match_len = i
            if found.name.lower() == potential_name: break
            break

    if not best_match_npc: return f"{FORMAT_ERROR}There's no one matching '{args[0]}' here.{FORMAT_RESET}"

    target_npc = best_match_npc
    
    if target_npc.faction == "hostile":
        formatted_name = format_name_for_display(player, target_npc, start_of_sentence=True)
        return f"{formatted_name} {FORMAT_ERROR}refuses to listen and prepares to attack!{FORMAT_RESET}"

    player.last_talked_to = target_npc.obj_id

    remaining_args = args[best_match_len:]
    topic = None
    is_quest_turn_in = False
    
    if remaining_args:
        topic_str = " ".join(remaining_args)
        if topic_str.lower() in ["complete quest", "report quest", "finish quest", "turnin quest", "complete", "turnin"]: 
            is_quest_turn_in = True
        else: 
            topic = topic_str
    
    if is_quest_turn_in:
        return _handle_quest_dialogue(player, target_npc, world)
    else:
        # Standard Dialogue
        ready_quests_for_npc = []
        if hasattr(player, 'quest_log') and player.quest_log:
            for q_id, q_data in player.quest_log.items():
                if (q_data.get("state") == "ready_to_complete" and q_data.get("giver_instance_id") == target_npc.obj_id):
                    ready_quests_for_npc.append(q_id)
        
        turn_in_hint = f"\n{FORMAT_HIGHLIGHT}(You have tasks to report. Type 'talk {target_npc.name} complete quest'){FORMAT_RESET}" if ready_quests_for_npc else ""
        offer_hint = f"\n{FORMAT_HIGHLIGHT}({target_npc.name} might have work. Try 'talk {target_npc.name} work'){FORMAT_RESET}" if target_npc.properties.get("can_give_generic_quests", False) else ""
        
        response = target_npc.talk(topic)
        npc_title = f"{FORMAT_TITLE}CONVERSATION WITH {target_npc.name.upper()}{FORMAT_RESET}\n\n"
        
        if topic: 
            return f"{npc_title}You ask {target_npc.name} about '{topic}'.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}{turn_in_hint}{offer_hint}"
        else: 
            return f"{npc_title}You greet {target_npc.name}.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}{turn_in_hint}{offer_hint}"

@command("turnin", ["donate", "deposit"], "interaction", "Turn in collection items to a collector.\nUsage: turnin")
def turnin_handler(args, context):
    world = context["world"]
    player = world.player
    game = context["game"]
    manager = game.collection_manager 
    
    if not player: return "Error."
    
    target_npc = None
    if player.trading_with: target_npc = world.get_npc(player.trading_with)
    elif player.last_talked_to:
        c = world.get_npc(player.last_talked_to)
        if c and c.current_room_id == player.current_room_id: target_npc = c
    
    if not target_npc:
        for npc in world.get_current_room_npcs():
            if npc.properties.get("is_collector"): target_npc = npc; break
    
    if not target_npc: return f"{FORMAT_ERROR}There is no one here to accept collections.{FORMAT_RESET}"
        
    return manager.turn_in_items(player, target_npc)

@command("ask", ["topic", "query"], "interaction", "Ask an NPC about a topic.\nUsage: ask [npc_name] <topic>")
def ask_handler(args, context):
    world = context["world"]
    player = world.player
    manager = world.game.knowledge_manager

    if not args:
        return f"{FORMAT_ERROR}Ask who/what? Usage: ask [npc_name] <topic>{FORMAT_RESET}"

    # 1. Determine Target (Greedy Matching Logic)
    target_npc = None
    topic_start_index = 0

    # A. Check for explicit NPC match in args
    npcs_in_room = world.get_current_room_npcs()
    best_match_npc = None
    best_match_len = 0

    for i in range(len(args), 0, -1):
        potential_name = " ".join(args[:i]).lower()
        found = None
        for npc in npcs_in_room:
            if npc.name.lower() == potential_name or npc.obj_id == potential_name:
                found = npc; break
        if not found:
            for npc in npcs_in_room:
                if potential_name in npc.name.lower():
                    found = npc; break
        if found:
            best_match_npc = found
            best_match_len = i
            if found.name.lower() == potential_name: break
            break

    if best_match_npc:
        target_npc = best_match_npc
        topic_start_index = best_match_len
    else:
        # B. Fallback to Context
        if player.trading_with:
            target_npc = world.get_npc(player.trading_with)
        elif player.last_talked_to:
            candidate = world.get_npc(player.last_talked_to)
            if candidate and candidate.current_region_id == player.current_region_id and candidate.current_room_id == player.current_room_id:
                target_npc = candidate
        
        if not target_npc:
            valid_npcs = [n for n in npcs_in_room if n.faction != "hostile" and n.faction != "player_minion"]
            if valid_npcs:
                target_npc = valid_npcs[0]

    if not target_npc:
        return f"{FORMAT_ERROR}There is no one here to ask.{FORMAT_RESET}"
    
    if target_npc.faction == "hostile":
        formatted_name = format_name_for_display(player, target_npc, start_of_sentence=True)
        return f"{formatted_name} {FORMAT_ERROR}refuses to listen.{FORMAT_RESET}"

    player.last_talked_to = target_npc.obj_id

    # 2. Extract Topic String
    topic_words = args[topic_start_index:]
    if not topic_words:
        return f"{FORMAT_ERROR}Ask {target_npc.name} about what?{FORMAT_RESET}"
    
    raw_input = " ".join(topic_words)

    # 3. Resolve Topic ID
    topic_id = manager.resolve_topic_id(raw_input)

    if not topic_id:
        topic_id = raw_input.lower().replace(" ", "_")

    # 4. Mark Discussed
    player.conversation.mark_discussed(target_npc.obj_id, topic_id)
    
    # 5. Get Response
    raw_response = manager.get_response(target_npc, topic_id, player)
    
    # 6. Highlight & Reveal
    formatted_response = manager.parse_and_highlight(raw_response, player, source_npc=target_npc)
    
    return f"{FORMAT_TITLE}{target_npc.name}{FORMAT_RESET}: {formatted_response}"

@command("follow", [], "interaction", "Follow an NPC.\nUsage: follow <npc_name> | follow stop")
def follow_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args:
        target_npc = world.get_npc(player.follow_target) if player.follow_target else None
        target_name = target_npc.name if target_npc else "someone"
        return f"You are currently following {target_name}. Type 'follow stop'." if player.follow_target else "Follow whom?"
    cmd_arg = " ".join(args).lower()
    if cmd_arg in FOLLOW_COMMAND_STOP_ALIASES:
        if player.follow_target: player.follow_target = None; return f"{FORMAT_HIGHLIGHT}You stop following.{FORMAT_RESET}"
        else: return "You aren't following anyone."
    found_npc = world.find_npc_in_room(cmd_arg)
    if found_npc:
        if player.follow_target == found_npc.obj_id: return f"You are already following {found_npc.name}."
        player.follow_target = found_npc.obj_id
        return f"{FORMAT_HIGHLIGHT}You start following {found_npc.name}.{FORMAT_RESET}"
    else: return f"{FORMAT_ERROR}No '{cmd_arg}' here to follow.{FORMAT_RESET}"

@command("guide", [], "interaction", "Ask a quest giver to guide you to your destination.\nUsage: guide <npc_name>")
def guide_handler(args, context):
    world = context["world"]; player = world.player; game = context["game"]
    if not player or not game: return f"{FORMAT_ERROR}System error: context missing.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Who do you want to guide you?{FORMAT_RESET}"

    npc_name = " ".join(args); guide_npc = world.find_npc_in_room(npc_name)
    if not guide_npc: return f"{FORMAT_ERROR}You don't see '{npc_name}' here.{FORMAT_RESET}"
    
    if guide_npc.faction == "hostile": return f"{FORMAT_ERROR}{guide_npc.name} growls at you. They won't guide you anywhere.{FORMAT_RESET}"

    quest_to_guide = None
    for quest in player.quest_log.values():
        if quest.get("giver_instance_id") == guide_npc.obj_id and quest.get("type") == "instance": quest_to_guide = quest; break
    
    if not quest_to_guide: return f"{guide_npc.name} has not offered to guide you anywhere."
    entry_point = quest_to_guide.get("entry_point")
    if not entry_point: return f"{FORMAT_ERROR}Quest '{quest_to_guide.get('title')}' has no destination.{FORMAT_RESET}"

    destination_region = entry_point.get("region_id"); destination_room = entry_point.get("room_id")
    path = world.find_path(player.current_region_id, player.current_room_id, destination_region, destination_room)

    if path is None: return f"{guide_npc.name} seems confused and can't find a path from here."
    if not path: return f"You are already at the destination!"

    game.start_auto_travel(path, guide_npc)
    return f"{FORMAT_HIGHLIGHT}\"{guide_npc.dialog.get('accept_guide', 'Follow me!')}\"{FORMAT_RESET}"

def _handle_quest_dialogue(player, target_npc, world) -> str:
    """Helper to process quest completions via dialogue."""
    ready_quests_for_npc = []
    if hasattr(player, 'quest_log') and player.quest_log:
        for q_id, q_data in player.quest_log.items():
            if (q_data.get("state") == "ready_to_complete" and q_data.get("giver_instance_id") == target_npc.obj_id):
                ready_quests_for_npc.append((q_id, q_data))

    if not ready_quests_for_npc: return f"{target_npc.name} doesn't seem to be expecting anything from you right now."
    
    quest_turn_in_id, quest_data = ready_quests_for_npc[0]
    quest_type = quest_data.get("type")
    objective = quest_data.get("objective", {})
    can_complete = True
    completion_error_msg = ""
    
    if quest_type == "fetch":
        required_item_id = objective.get("item_id")
        required_qty = objective.get("required_quantity", 1)
        player_has_qty = player.inventory.count_item(required_item_id)
        
        if player_has_qty < required_qty:
            can_complete = False
            completion_error_msg = f"You still need {required_qty - player_has_qty} more {objective.get('item_name_plural', 'items')}."
        else:
            removed_type, removed_count, remove_msg = player.inventory.remove_item(required_item_id, required_qty)
            if not removed_type or removed_count != required_qty:
                    can_complete = False
                    completion_error_msg = "Error removing required items from your inventory. Cannot complete quest."
                    
    elif quest_type == "deliver":
        required_instance_id = objective.get("item_instance_id")
        package_instance = player.inventory.find_item_by_id(required_instance_id)
        if not package_instance:
            can_complete = False
            completion_error_msg = f"You don't seem to have the {objective.get('item_to_deliver_name', 'package')} anymore!"
        else:
            if not player.inventory.remove_item_instance(package_instance):
                    can_complete = False
                    completion_error_msg = f"Error removing the {objective.get('item_to_deliver_name', 'package')} from your inventory."
    
    if can_complete:
        rewards = quest_data.get("rewards", {})
        xp_reward = rewards.get("xp", 0)
        gold_reward = rewards.get("gold", 0)
        leveled_up, level_up_message = False, ""
        reward_messages = []

        if xp_reward > 0:
                leveled_up, level_up_message = player.gain_experience(xp_reward)
                reward_messages.append(f"{xp_reward} XP")

        if gold_reward > 0: 
            player.gold += gold_reward
            reward_messages.append(f"{gold_reward} Gold")
            
        if quest_turn_in_id in player.quest_log:
            completed_quest = player.quest_log.pop(quest_turn_in_id)
            player.completed_quest_log[quest_turn_in_id] = completed_quest

        quest_manager = world.quest_manager
        if quest_manager: quest_manager.replenish_board(quest_turn_in_id)

        completion_message = f"{FORMAT_SUCCESS}[Quest Complete] {quest_data.get('title', 'Task')}{FORMAT_RESET}\n"
        npc_response = target_npc.dialog.get(f"complete_{quest_turn_in_id}", target_npc.dialog.get("quest_complete", f"\"Ah, thank you for your help!\" says {target_npc.name}."))
        completion_message += f"{FORMAT_HIGHLIGHT}{npc_response}{FORMAT_RESET}\n"
        if reward_messages: completion_message += "You receive: " + ", ".join(reward_messages) + "."

        if quest_type == "instance":
            giver_id = quest_data.get("giver_instance_id")
            if giver_id and giver_id in world.npcs:
                del world.npcs[giver_id]
                completion_message += f"\nHaving given you your reward, {target_npc.name} heads back inside their home."

        if leveled_up and level_up_message: completion_message += "\n\n" + level_up_message
        return completion_message
    else: 
        return f"{FORMAT_ERROR}You haven't fully met the requirements for '{quest_data.get('title', 'this quest')}'. {completion_error_msg}{FORMAT_RESET}"