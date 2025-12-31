# engine/commands/interaction/items.py
from typing import Any, List, Dict
from engine.commands.command_system import command
from engine.config import (
    FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, 
    GET_COMMAND_PREPOSITION, PUT_COMMAND_PREPOSITION, GIVE_COMMAND_PREPOSITION,
    USE_COMMAND_PREPOSITIONS
)
from engine.items.container import Container
from engine.items.consumable import Consumable
from engine.items.key import Key
from engine.utils.utils import simple_plural, get_article
from engine.items.item_factory import ItemFactory  # Needed for cloning/creating dropped items

# --- Internal Helpers ---

def _handle_item_acquisition(args: List[str], context: Dict[str, Any], command_verb: str) -> str:
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You can't {command_verb} things while dead.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}{command_verb.capitalize()} what?{FORMAT_RESET}"
    
    item_name = ""
    quantity_requested = 1
    take_all_of_type = False
    
    if args[0].lower() == "all":
        take_all_of_type = True
        quantity_requested = None 
        item_name = " ".join(args[1:]).lower() if len(args) > 1 else "" 
    elif args[0].isdigit():
        try:
            quantity_requested = int(args[0])
            item_name = " ".join(args[1:]).lower()
            if quantity_requested <= 0: return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            if not item_name: return f"{FORMAT_ERROR}{command_verb.capitalize()} {quantity_requested} of what?{FORMAT_RESET}"
        except ValueError: return f"{FORMAT_ERROR}Invalid quantity '{args[0]}'.{FORMAT_RESET}"
    else: 
        item_name = " ".join(args).lower()

    visible_candidates = []
    # Scan room items
    for item in world.get_items_in_current_room():
        visible_candidates.append((item, None))
        # Scan open containers in room
        if isinstance(item, Container) and item.properties.get("is_open", False):
            for sub_item in item.properties.get("contains", []): 
                visible_candidates.append((sub_item, item))

    if not visible_candidates: return f"{FORMAT_ERROR}There is nothing here to {command_verb}.{FORMAT_RESET}"

    targets_to_process = []
    if take_all_of_type and not item_name: 
        targets_to_process = [t for t in visible_candidates if t[1] is None] # Only ground items for "take all"
        if not targets_to_process: return f"{FORMAT_ERROR}There is nothing on the floor to {command_verb}.{FORMAT_RESET}"
    else:
        exact_matches = []
        partial_matches = []
        for item, source in visible_candidates:
            if item_name == item.name.lower(): exact_matches.append((item, source))
            elif item_name in item.name.lower(): partial_matches.append((item, source))
        
        matches = exact_matches or partial_matches
        if not matches: return f"{FORMAT_ERROR}You don't see any '{item_name}' here (or in open containers).{FORMAT_RESET}"
        
        matches.sort(key=lambda x: x[0].name)
        
        if take_all_of_type or (quantity_requested and quantity_requested > 1): 
            targets_to_process = matches
        elif matches: 
            targets_to_process = [matches[0]]

    qty_to_attempt = len(targets_to_process)
    if quantity_requested is not None: 
        qty_to_attempt = min(quantity_requested, len(targets_to_process))

    items_taken_by_source = {}
    cant_carry_message = ""
    hints = []
    
    for i in range(qty_to_attempt):
        item_instance, source_container = targets_to_process[i]
        
        if not item_instance.get_property("can_take", True): 
            cant_carry_message = f" (The {item_instance.name} is too heavy or fixed in place)."
            break
            
        can_add, msg = player.inventory.can_add_item(item_instance, 1)
        if not can_add: 
            cant_carry_message = f" (You cannot carry any more)."
            break 
            
        removal_successful = False
        if source_container: 
            removal_successful = source_container.remove_item(item_instance)
        else: 
            removal_successful = world.remove_item_instance_from_room(world.current_region_id, world.current_room_id, item_instance)

        if removal_successful:
            added_to_inv, add_msg = player.inventory.add_item(item_instance, 1)
            if added_to_inv:
                # Collection Check
                col_manager = context["game"].collection_manager
                col_hint = col_manager.handle_collection_discovery(player, item_instance)
                if col_hint: hints.append(col_hint)
                
                source_desc = f"from the {source_container.name}" if source_container else "__ground__"
                if source_container:
                     if any(itm is source_container for itm in world.get_items_in_current_room()): 
                         source_desc += " on the ground"
                
                summary_key = f"{item_instance.obj_id}_{item_instance.name}"
                if source_desc not in items_taken_by_source: 
                    items_taken_by_source[source_desc] = {}
                if summary_key not in items_taken_by_source[source_desc]: 
                    items_taken_by_source[source_desc][summary_key] = {"name": item_instance.name, "count": 0}
                
                items_taken_by_source[source_desc][summary_key]["count"] += 1
            else:
                # Rollback if inventory add failed unexpectedly
                if source_container: source_container.add_item(item_instance)
                else: world.add_item_to_room(world.current_region_id, world.current_room_id, item_instance)
                cant_carry_message = f" (An unexpected inventory error occurred for {item_instance.name})."
                break
        else: 
            break 
    
    if not items_taken_by_source: 
        return f"{FORMAT_ERROR}{cant_carry_message.strip()}{FORMAT_RESET}" if cant_carry_message else f"{FORMAT_ERROR}You couldn't {command_verb} anything.{FORMAT_RESET}"

    final_sentences = []
    for source_desc, items_dict in items_taken_by_source.items():
        item_parts = []
        for data in items_dict.values():
            name = data["name"]
            count = data["count"]
            item_parts.append(f"{get_article(name)} {name}" if count == 1 else f"{count} {simple_plural(name)}")
        
        items_str = ", ".join(item_parts[:-1]) + f", and {item_parts[-1]}" if len(item_parts) > 2 else " and ".join(item_parts)
        
        if source_desc == "__ground__":
            final_sentences.append(f"You pick up {items_str}.")
        else:
            final_sentences.append(f"You {command_verb} {items_str} {source_desc}.")

    final_message = f"{FORMAT_SUCCESS}{' '.join(final_sentences)}{FORMAT_RESET}"
    if cant_carry_message: final_message += f"{FORMAT_HIGHLIGHT}{cant_carry_message}{FORMAT_RESET}"
    if hints: final_message += "\n" + "\n".join(set(hints))
    return final_message

def _handle_item_disposal(args: List[str], context: Dict[str, Any], command_verb: str) -> str:
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You can't {command_verb} items while dead.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}{command_verb.capitalize()} what?{FORMAT_RESET}"

    item_name = ""
    quantity_requested = 1
    drop_all_of_type = False
    
    if args[0].lower() == "all":
        drop_all_of_type = True
        quantity_requested = None 
        item_name = " ".join(args[1:]).lower() if len(args) > 1 else "" 
    elif args[0].isdigit():
        try:
            quantity_requested = int(args[0])
            item_name = " ".join(args[1:]).lower()
            if quantity_requested <= 0: return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            if not item_name: return f"{FORMAT_ERROR}{command_verb.capitalize()} {quantity_requested} of what?{FORMAT_RESET}"
        except ValueError: return f"{FORMAT_ERROR}Invalid quantity '{args[0]}'.{FORMAT_RESET}"
    else: 
        item_name = " ".join(args).lower()

    items_in_inventory = [slot.item for slot in player.inventory.slots if slot.item]
    if not items_in_inventory: return f"{FORMAT_ERROR}Your inventory is empty.{FORMAT_RESET}"
    
    # Matching Logic
    items_to_drop = []
    if drop_all_of_type and not item_name: 
        items_to_drop = list(items_in_inventory)
    else:
        exact_matches = []
        partial_matches = []
        for item in items_in_inventory:
            if item_name == item.name.lower(): exact_matches.append(item)
            elif item_name in item.name.lower(): partial_matches.append(item)
        matches = exact_matches or partial_matches
        
        if not matches: return f"{FORMAT_ERROR}You don't have any '{item_name}'.{FORMAT_RESET}"
        matches.sort(key=lambda item: item.name)
        
        # If dropping all matching items OR multiple (non-stackable handling), we might use list
        # BUT for stackables, we want to handle the first match and drop quantity.
        items_to_drop = matches

    if not items_to_drop: return f"{FORMAT_ERROR}You don't have any '{item_name}' to {command_verb}.{FORMAT_RESET}"

    # Execution Logic
    items_dropped_summary = {}
    
    # If quantity was explicit (e.g., "drop 4 coin"), we process quantity logic
    # If "drop all", we process list logic.
    
    qty_remaining_to_drop = quantity_requested if quantity_requested is not None else float('inf')
    
    # Use a copy to iterate because we modify inventory structure? 
    # remove_item modifies slots but items_to_drop are item references.
    
    # We iterate through the matched candidates.
    for item_instance in items_to_drop:
        if qty_remaining_to_drop <= 0: break
        
        # Case 1: Stackable Item
        if item_instance.stackable:
            # How many do we have in this instance? (Actually we check by ID)
            # The player.inventory.remove_item method handles finding the slot and decrementing qty.
            
            # We want to drop `min(qty_remaining_to_drop, amount_in_inventory)`
            # Note: items_to_drop might contain the same object reference if we scanned slots, 
            # but matches came from `items_in_inventory` which is `[slot.item ...]`.
            # So duplicates are possible if multiple slots hold the same item instance (unlikely for stackables, but safe to check).
            
            count_in_inv = player.inventory.count_item(item_instance.obj_id)
            if count_in_inv == 0: continue # Already processed this ID
            
            amount_to_process = min(qty_remaining_to_drop, count_in_inv)
            
            removed_item_type, actual_removed, _ = player.inventory.remove_item(item_instance.obj_id, amount_to_process)
            
            if removed_item_type and actual_removed > 0:
                # IMPORTANT: For stackables, we must create NEW instances for the room 
                # because the original instance might remain in the inventory (just with lower qty).
                # We add 'actual_removed' copies to the room.
                for _ in range(actual_removed):
                    # We try to clone via factory to get fresh properties/stats if possible
                    # or deepcopy if template lookup fails.
                    dropped_copy = ItemFactory.create_item_from_template(item_instance.obj_id, world)
                    if not dropped_copy:
                        import copy
                        dropped_copy = copy.deepcopy(item_instance)
                    
                    world.add_item_to_room(world.current_region_id, world.current_room_id, dropped_copy)
                
                # Update Summary
                summary_key = f"{item_instance.obj_id}_{item_instance.name}"
                if summary_key not in items_dropped_summary:
                    items_dropped_summary[summary_key] = {"name": item_instance.name, "count": 0}
                items_dropped_summary[summary_key]["count"] += actual_removed
                
                qty_remaining_to_drop -= actual_removed
                
        # Case 2: Non-Stackable Item
        else:
            # We remove 1 instance at a time
            if player.inventory.remove_item_instance(item_instance):
                world.add_item_to_room(world.current_region_id, world.current_room_id, item_instance)
                
                summary_key = f"{item_instance.obj_id}_{item_instance.name}"
                if summary_key not in items_dropped_summary: 
                    items_dropped_summary[summary_key] = {"name": item_instance.name, "count": 0}
                items_dropped_summary[summary_key]["count"] += 1
                
                qty_remaining_to_drop -= 1

    if not items_dropped_summary: return f"{FORMAT_ERROR}You couldn't {command_verb} any '{item_name}'.{FORMAT_RESET}"
    
    success_parts = []
    for data in items_dropped_summary.values():
        name = data["name"]
        count = data["count"]
        success_parts.append(f"{get_article(name)} {name}" if count == 1 else f"{count} {simple_plural(name)}")

    return f"{FORMAT_SUCCESS}You {command_verb} {', '.join(success_parts)}.{FORMAT_RESET}"

# --- Command Handlers ---

@command("get", ["take", "pickup", "grab"], "interaction", "Pick up an item from the room.\nUsage: take [all|quantity] <item_name> | take all")
def get_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot get items.{FORMAT_RESET}"

    if GET_COMMAND_PREPOSITION in [a.lower() for a in args]:
        # Handle "get X from Y"
        try:
            from_index = [a.lower() for a in args].index(GET_COMMAND_PREPOSITION)
            item_name = " ".join(args[:from_index]).lower()
            container_name = " ".join(args[from_index + 1:]).lower()
        except ValueError: return f"{FORMAT_ERROR}Usage: get <item> from <container>{FORMAT_RESET}"
        if not item_name or not container_name: return f"{FORMAT_ERROR}Specify both an item and a container.{FORMAT_RESET}"

        container = None
        for item in world.get_items_in_current_room():
            if isinstance(item, Container) and container_name in item.name.lower(): 
                container = item; break
        if not container:
            inv_item = player.inventory.find_item_by_name(container_name)
            if isinstance(inv_item, Container): container = inv_item
        
        if not container: return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"
        if not container.properties.get("is_open", False): return f"{FORMAT_ERROR}The {container.name} is closed.{FORMAT_RESET}"

        if item_name == "all":
             items_to_take = list(container.properties.get("contains", []))
             if not items_to_take: return f"The {container.name} is empty."
             count = 0
             for it in items_to_take:
                  if player.inventory.can_add_item(it)[0] and container.remove_item(it):
                       player.inventory.add_item(it)
                       count += 1
             return f"{FORMAT_SUCCESS}You take {count} items from the {container.name}.{FORMAT_RESET}"

        item_to_get = container.find_item_by_name(item_name)
        if not item_to_get: return f"{FORMAT_ERROR}You don't see '{item_name}' inside the {container.name}.{FORMAT_RESET}"
        
        can_carry, carry_msg = player.inventory.can_add_item(item_to_get)
        if not can_carry: return f"{FORMAT_ERROR}{carry_msg}{FORMAT_RESET}"

        if container.remove_item(item_to_get):
            added_success, add_msg = player.inventory.add_item(item_to_get, 1)
            if added_success: return f"{FORMAT_SUCCESS}You get the {item_to_get.name} from the {container.name}.{FORMAT_RESET}"
            else: 
                container.add_item(item_to_get)
                return f"{FORMAT_ERROR}Could not take the {item_to_get.name}: {add_msg}{FORMAT_RESET}"
        else: 
            return f"{FORMAT_ERROR}Could not get the {item_to_get.name} from the {container.name}.{FORMAT_RESET}"
    else: 
        return _handle_item_acquisition(args, context, "take")

@command("take", ["pickup", "grab"], "interaction", "Pick up an item from the room.\nUsage: take [all|quantity] <item_name> | take all")
def take_handler(args, context):
    return get_handler(args, context)

@command("drop", ["putdown"], "interaction", "Drop one, multiple, or all matching items.\nUsage: drop [all|quantity] <item_name>")
def drop_handler(args, context): 
    return _handle_item_disposal(args, context, "drop")

@command("put", ["store"], "interaction", "Put an item into a container.\nUsage: put <item_name> in <container_name>")
def put_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot store items.{FORMAT_RESET}"

    if PUT_COMMAND_PREPOSITION not in [a.lower() for a in args]: 
        return f"{FORMAT_ERROR}Usage: put <item_name> {PUT_COMMAND_PREPOSITION} <container_name>{FORMAT_RESET}"

    try:
        in_index = [a.lower() for a in args].index(PUT_COMMAND_PREPOSITION)
        item_name = " ".join(args[:in_index]).lower()
        container_name = " ".join(args[in_index + 1:]).lower()
    except ValueError: return f"{FORMAT_ERROR}Usage: put <item_name> in <container_name>{FORMAT_RESET}"

    if not item_name or not container_name: return f"{FORMAT_ERROR}Specify both an item and a container.{FORMAT_RESET}"
    
    item_to_put = player.inventory.find_item_by_name(item_name)
    if not item_to_put: return f"{FORMAT_ERROR}You don't have '{item_name}'.{FORMAT_RESET}"

    container = None
    # 1. Search ground
    for item in world.get_items_in_current_room():
        if isinstance(item, Container) and container_name in item.name.lower(): 
            container = item
            break
    # 2. Search inventory
    if not container:
        inv_item = player.inventory.find_item_by_name(container_name)
        if isinstance(inv_item, Container): container = inv_item
    
    if not container: return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"

    # --- Recursion Check ---
    if item_to_put is container:
        return f"{FORMAT_ERROR}You cannot put the {item_to_put.name} inside itself.{FORMAT_RESET}"

    # Deep Recursion Check: Is the target container actually inside the item we are trying to put?
    # (e.g., trying to put Bag A into Bag B, while Bag B is already inside Bag A)
    if isinstance(item_to_put, Container):
        # We check if the 'container' instance exists anywhere in the 'item_to_put' hierarchy
        def is_inside(potential_parent, target):
            contents = potential_parent.properties.get("contains", [])
            if target in contents: return True
            for sub in contents:
                if isinstance(sub, Container) and is_inside(sub, target): return True
            return False
            
        if is_inside(item_to_put, container):
            return f"{FORMAT_ERROR}You cannot put the {item_to_put.name} into the {container.name}, because the {container.name} is already inside it!{FORMAT_RESET}"

    # Proceed with standard logic
    can_add, msg = container.can_add(item_to_put)
    if not can_add: return f"{FORMAT_ERROR}{msg}{FORMAT_RESET}"

    removed_item, quantity_removed, remove_msg = player.inventory.remove_item(item_to_put.obj_id, 1)
    if not removed_item: return f"{FORMAT_ERROR}Failed to get '{item_name}' from inventory: {remove_msg}{FORMAT_RESET}"

    if container.add_item(removed_item): 
        return f"{FORMAT_SUCCESS}You put the {removed_item.name} in the {container.name}.{FORMAT_RESET}"
    else:
        player.inventory.add_item(removed_item, 1)
        return f"{FORMAT_ERROR}Could not put the {removed_item.name} in the {container.name}.{FORMAT_RESET}"

@command("open", [], "interaction", "Open a container.\nUsage: open <container_name>")
def open_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot open things.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Open what?{FORMAT_RESET}"
    
    container_name = " ".join(args).lower()
    
    # Search room items and player inventory for ANY item matching the name
    target_item = world.find_item_in_room(container_name)
    if not target_item:
        target_item = player.inventory.find_item_by_name(container_name)
    
    if not target_item:
        return f"{FORMAT_ERROR}You don't see '{container_name}' here.{FORMAT_RESET}"
        
    # Check if it is actually a container
    from engine.items.container import Container
    if not isinstance(target_item, Container):
        return f"{FORMAT_ERROR}The {target_item.name} is not a container.{FORMAT_RESET}"
        
    return f"{FORMAT_HIGHLIGHT}{target_item.open()}{FORMAT_RESET}"

@command("close", [], "interaction", "Close a container.\nUsage: close <container_name>")
def close_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot close things.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Close what?{FORMAT_RESET}"

    container_name = " ".join(args).lower()
    container = None
    
    for item in world.get_items_in_current_room():
        if isinstance(item, Container) and container_name in item.name.lower(): 
            container = item
            break
    if not container:
        inv_item = player.inventory.find_item_by_name(container_name)
        if isinstance(inv_item, Container): container = inv_item
    
    if not container: return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"
    return f"{FORMAT_HIGHLIGHT}{container.close()}{FORMAT_RESET}"

@command("use", ["activate", "drink", "eat", "apply"], "interaction", "Use an item from inventory, optionally on a target.\nUsage: use <item> [on <target>]")
def use_handler(args, context):
    player = context["world"].player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot use items.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Use what?{FORMAT_RESET}"

    world = context["world"]
    item_name = ""
    target_name = ""
    prep_index = -1
    
    supported_prepositions = USE_COMMAND_PREPOSITIONS
    for i, word in enumerate(args):
        if word.lower() in supported_prepositions: 
            prep_index = i
            break
            
    if prep_index != -1:
        item_name = " ".join(args[:prep_index]).lower()
        target_name = " ".join(args[prep_index + 1:]).lower()
    else: 
        item_name = " ".join(args).lower()
        
    item_to_use = player.inventory.find_item_by_name(item_name)
    if not item_to_use: return f"{FORMAT_ERROR}You don't have a '{item_name}'.{FORMAT_RESET}"

    if target_name:
        target = world.find_item_in_room(target_name) or player.inventory.find_item_by_name(target_name, exclude=item_to_use) or world.find_npc_in_room(target_name)
        if not target and target_name in ["self", "me", player.name.lower()]: target = player
        
        if not target: return f"{FORMAT_ERROR}You don't see a '{target_name}' here to use the {item_to_use.name} on.{FORMAT_RESET}"
        
        try:
            result = item_to_use.use(user=player, target=target)
            if isinstance(item_to_use, Consumable) and item_to_use.get_property("uses", 1) <= 0: 
                player.inventory.remove_item(item_to_use.obj_id)
            return f"{FORMAT_HIGHLIGHT}{result}{FORMAT_RESET}"
        except TypeError as e:
             if "unexpected keyword argument 'target'" in str(e) or "takes 2 positional arguments but 3 were given" in str(e): 
                 return f"{FORMAT_ERROR}You can't use the {item_to_use.name} on the {getattr(target, 'name', 'target')}.{FORMAT_RESET}"
             else: raise e
        except Exception as e: 
            return f"{FORMAT_ERROR}Something went wrong trying to use the {item_to_use.name}: {e}{FORMAT_RESET}"
    else:
        if isinstance(item_to_use, Key): 
            return f"{FORMAT_ERROR}What do you want to use the {item_to_use.name} on? Usage: use <key> on <target>.{FORMAT_RESET}"
        
        try:
            result = item_to_use.use(user=player)
            if isinstance(item_to_use, Consumable) and item_to_use.get_property("uses", 1) <= 0: 
                player.inventory.remove_item(item_to_use.obj_id)
            return f"{FORMAT_HIGHLIGHT}{result}{FORMAT_RESET}"
        except Exception as e: 
            return f"{FORMAT_ERROR}Something went wrong trying to use the {item_to_use.name}: {e}{FORMAT_RESET}"

@command(name="give", aliases=[], category="interaction", help_text="Give an item from your inventory to someone.\nUsage: give <item_name> to <npc_name>")
def give_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You can't give items while dead.{FORMAT_RESET}"
    
    if GIVE_COMMAND_PREPOSITION not in [a.lower() for a in args]: 
        return f"{FORMAT_ERROR}Usage: give <item_name> {GIVE_COMMAND_PREPOSITION} <npc_name>{FORMAT_RESET}"
    
    try:
        to_index = [a.lower() for a in args].index(GIVE_COMMAND_PREPOSITION)
        item_name = " ".join(args[:to_index]).lower()
        npc_name = " ".join(args[to_index + 1:]).lower()
    except ValueError: return f"{FORMAT_ERROR}Usage: give <item_name> to <npc_name>{FORMAT_RESET}"
    
    if not item_name or not npc_name: return f"{FORMAT_ERROR}Specify both an item and who to give it to.{FORMAT_RESET}"
    
    item_to_give = player.inventory.find_item_by_name(item_name)
    if not item_to_give and "package" in item_name:
        for slot in player.inventory.slots:
             if slot.item and "package" in slot.item.name.lower(): 
                 item_to_give = slot.item
                 break
                 
    if not item_to_give: return f"{FORMAT_ERROR}You don't have '{item_name}'.{FORMAT_RESET}"
    
    target_npc = world.find_npc_in_room(npc_name)
    if not target_npc: return f"{FORMAT_ERROR}You don't see '{npc_name}' here.{FORMAT_RESET}"

    # Quest Delivery Check
    matching_quest_data = None
    if hasattr(player, 'quest_log'):
        for quest_data in player.quest_log.values():
            objective = quest_data.get("objective", {})
            if (quest_data.get("state") == "active" and
                quest_data.get("type") == "deliver" and
                objective.get("item_instance_id") == item_to_give.obj_id):
                matching_quest_data = quest_data
                break

    if matching_quest_data:
        objective = matching_quest_data.get("objective", {})
        required_recipient_id = objective.get("recipient_instance_id")
        matching_quest_id = matching_quest_data.get("instance_id")
        
        if target_npc.obj_id == required_recipient_id:
            if not player.inventory.remove_item_instance(item_to_give):
                return f"{FORMAT_ERROR}Something went wrong removing the package. Please report this bug.{FORMAT_RESET}"
            
            rewards = matching_quest_data.get("rewards", {})
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
            
            if matching_quest_id in player.quest_log:
                completed_quest = player.quest_log.pop(matching_quest_id)
                player.completed_quest_log[matching_quest_id] = completed_quest
            
            quest_manager = context["world"].quest_manager
            if quest_manager: quest_manager.replenish_board(matching_quest_id)
            
            completion_message = f"{FORMAT_SUCCESS}[Quest Complete] {matching_quest_data.get('title', 'Task')}{FORMAT_RESET}\n"
            npc_response = target_npc.dialog.get(f"complete_{matching_quest_id}", target_npc.dialog.get("quest_complete", f"\"Ah, thank you!\" says {target_npc.name}."))
            completion_message += f"{FORMAT_HIGHLIGHT}{npc_response}{FORMAT_RESET}\n"
            if reward_messages: completion_message += "You receive: " + ", ".join(reward_messages) + "."

            if leveled_up and level_up_message:
                completion_message += "\n\n" + level_up_message

            return completion_message
        else:
            correct_recipient_name = objective.get("recipient_name", "someone else")
            return f"{FORMAT_ERROR}You should give the {item_to_give.name} to {correct_recipient_name}, not {target_npc.name}.{FORMAT_RESET}"
    else:
        # Standard Gift
        removed_item_type, removed_count, remove_msg = player.inventory.remove_item(item_to_give.obj_id, 1)
        if not removed_item_type or removed_count != 1: return f"{FORMAT_ERROR}Failed to take '{item_to_give.name}' from inventory: {remove_msg}{FORMAT_RESET}"
        return f"{FORMAT_SUCCESS}You give the {item_to_give.name} to {target_npc.name}.{FORMAT_RESET}"