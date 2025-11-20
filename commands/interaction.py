# commands/interaction.py

from typing import Any, Dict, List, Optional, Tuple
from commands.command_system import command, registered_commands
from config import (
    FOLLOW_COMMAND_STOP_ALIASES, GET_COMMAND_PREPOSITION, GIVE_COMMAND_PREPOSITION, PUT_COMMAND_PREPOSITION, QUEST_BOARD_ALIASES,
    USE_COMMAND_PREPOSITIONS, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, VENDOR_LIST_ITEM_NAME_WIDTH,
    VENDOR_LIST_PRICE_WIDTH, DEFAULT_VENDOR_BUY_MULTIPLIER, DEFAULT_VENDOR_SELL_MULTIPLIER, REPAIR_COST_PER_VALUE_POINT,
    REPAIR_MINIMUM_COST, VENDOR_CAN_BUY_ALL_ITEMS, VENDOR_MIN_BUY_PRICE, VENDOR_MIN_SELL_PRICE
)
from items.consumable import Consumable
from items.item_factory import ItemFactory
from items.junk import Junk
from items.key import Key
from items.container import Container
from utils.utils import simple_plural, get_article
from player import Player
from npcs.npc import NPC
from items.item import Item

# ... (Helper functions _display_vendor_inventory and _calculate_repair_cost remain unchanged) ...

def _display_vendor_inventory(player: Player, vendor: NPC, world) -> str:
    vendor_items_refs = vendor.properties.get("sells_items", [])
    if not vendor_items_refs: return f"{vendor.name} has nothing to sell right now."
    display_lines = [f"{FORMAT_TITLE}{vendor.name}'s Wares:{FORMAT_RESET}\n"]
    for item_ref in vendor_items_refs:
        item_id = item_ref.get("item_id")
        template = world.item_templates.get(item_id)
        if not template: continue
        item_name = template.get("name", "Unknown Item")
        base_value = template.get("value", 0)
        price_multiplier = item_ref.get("price_multiplier", DEFAULT_VENDOR_SELL_MULTIPLIER)
        buy_price = max(VENDOR_MIN_BUY_PRICE, int(base_value * price_multiplier))
        display_lines.append(f"- {item_name:<{VENDOR_LIST_ITEM_NAME_WIDTH}} | Price: {buy_price:>{VENDOR_LIST_PRICE_WIDTH}} gold")
    display_lines.append(f"\nYour Gold: {player.gold}\n\nCommands: list, buy <item> [qty], sell <item> [qty], stoptrade")
    return "\n".join(display_lines)

def _calculate_repair_cost(item: Item) -> Tuple[Optional[int], Optional[str]]:
    current_durability = item.get_property("durability")
    max_durability = item.get_property("max_durability")
    if current_durability is None or max_durability is None: return None, f"The {item.name} doesn't have durability."
    if current_durability >= max_durability: return 0, None
    repair_cost = max(REPAIR_MINIMUM_COST, int(item.value * REPAIR_COST_PER_VALUE_POINT))
    return repair_cost, None

# ... (Item Acquisition/Disposal Helpers remain unchanged) ...

def _handle_item_acquisition(args: List[str], context: Dict[str, Any], command_verb: str) -> str:
    """
    Handles picking up items from the ground (Room) OR from open containers in the room.
    """
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You can't {command_verb} things while dead.{FORMAT_RESET}"
    
    if not args: return f"{FORMAT_ERROR}{command_verb.capitalize()} what?{FORMAT_RESET}"

    # --- Parsing Logic ---
    item_name = ""
    quantity_requested: Optional[int] = 1 
    take_all_of_type = False
    
    if args[0].lower() == "all":
        take_all_of_type = True
        quantity_requested = None 
        if len(args) > 1:
            item_name = " ".join(args[1:]).lower()
        else:
            item_name = "" 
    elif args[0].isdigit():
        try:
            quantity_requested = int(args[0])
            if quantity_requested <= 0: return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            item_name = " ".join(args[1:]).lower()
            if not item_name: return f"{FORMAT_ERROR}{command_verb.capitalize()} {quantity_requested} of what?{FORMAT_RESET}"
        except ValueError:
            return f"{FORMAT_ERROR}Invalid quantity '{args[0]}'.{FORMAT_RESET}"
    else:
        item_name = " ".join(args).lower()
        quantity_requested = 1

    # --- Build Candidate List (Floor + Open Containers) ---
    visible_candidates: List[Tuple[Item, Optional[Container]]] = []
    
    # 1. Floor Items
    for item in world.get_items_in_current_room():
        visible_candidates.append((item, None))
        
        # 2. Check inside Open Containers on the floor
        if isinstance(item, Container) and item.properties.get("is_open", False):
            contents = item.properties.get("contains", [])
            for sub_item in contents:
                visible_candidates.append((sub_item, item))

    if not visible_candidates:
        return f"{FORMAT_ERROR}There is nothing here to {command_verb}.{FORMAT_RESET}"

    # --- Matching Logic ---
    targets_to_process: List[Tuple[Item, Optional[Container]]] = []

    if take_all_of_type and not item_name: 
        # "take all" -> Defaults to FLOOR ONLY to prevent looting massive chests accidentally
        targets_to_process = [t for t in visible_candidates if t[1] is None]
        if not targets_to_process:
             return f"{FORMAT_ERROR}There is nothing on the floor to {command_verb}.{FORMAT_RESET}"
    else:
        # Specific search (searches floor AND open containers)
        exact_matches = []
        partial_matches = []
        
        for item, source in visible_candidates:
            if item_name == item.name.lower():
                exact_matches.append((item, source))
            elif item_name in item.name.lower():
                partial_matches.append((item, source))
        
        matches = exact_matches or partial_matches

        if not matches:
            return f"{FORMAT_ERROR}You don't see any '{item_name}' here (or in open containers).{FORMAT_RESET}"

        # Sort matches alphabetically
        matches.sort(key=lambda x: x[0].name)

        if take_all_of_type or (quantity_requested and quantity_requested > 1):
            targets_to_process = matches
        elif matches:
            targets_to_process = [matches[0]]

    qty_to_attempt = len(targets_to_process)
    if quantity_requested is not None:
        qty_to_attempt = min(quantity_requested, len(targets_to_process))

    # --- Acquisition Logic ---
    items_taken_by_source: Dict[str, Dict[str, Any]] = {}
    cant_carry_message = ""
    
    for i in range(qty_to_attempt):
        item_instance, source_container = targets_to_process[i]
        
        # 1. Capacity Check
        can_add, msg = player.inventory.can_add_item(item_instance, 1)
        if not can_add:
            cant_carry_message = f" (You cannot carry any more)."
            break 

        # 2. Remove from Source
        removal_successful = False
        if source_container:
            if source_container.remove_item(item_instance):
                removal_successful = True
            else:
                print(f"Error: Failed to remove {item_instance.name} from container {source_container.name}")
        else:
            if world.remove_item_instance_from_room(world.current_region_id, world.current_room_id, item_instance):
                removal_successful = True
            else:
                print(f"Error: Failed to remove {item_instance.name} from room.")

        # 3. Add to Player
        if removal_successful:
            added_to_inv, add_msg = player.inventory.add_item(item_instance, 1)
            
            if added_to_inv:
                # Determine Source String
                source_desc = ""
                if source_container:
                    # Check if container is on the ground
                    is_on_ground = False
                    if any(itm is source_container for itm in world.get_items_in_current_room()):
                        is_on_ground = True
                    
                    if is_on_ground:
                        source_desc = f"from the {source_container.name} on the ground"
                    else:
                        source_desc = f"from the {source_container.name}"
                else:
                    source_desc = "__ground__"
                
                summary_key = f"{item_instance.obj_id}_{item_instance.name}"
                
                if source_desc not in items_taken_by_source:
                    items_taken_by_source[source_desc] = {}
                
                if summary_key not in items_taken_by_source[source_desc]:
                    items_taken_by_source[source_desc][summary_key] = {"name": item_instance.name, "count": 0}
                
                items_taken_by_source[source_desc][summary_key]["count"] += 1
            else:
                # Rollback
                if source_container:
                    source_container.add_item(item_instance)
                else:
                    world.add_item_to_room(world.current_region_id, world.current_room_id, item_instance)
                cant_carry_message = f" (An unexpected inventory error occurred for {item_instance.name})."
                break
        else:
            break 
    
    # --- Result Feedback Generation ---
    if not items_taken_by_source:
        if cant_carry_message:
            return f"{FORMAT_ERROR}{cant_carry_message.strip()}{FORMAT_RESET}"
        return f"{FORMAT_ERROR}You couldn't {command_verb} anything.{FORMAT_RESET}"

    final_sentences = []
    
    for source_desc, items_dict in items_taken_by_source.items():
        item_parts = []
        for data in items_dict.values():
            name = data["name"]; count = data["count"]
            if count == 1:
                item_parts.append(f"{get_article(name)} {name}")
            else:
                item_parts.append(f"{count} {simple_plural(name)}")
        
        items_str = ""
        if len(item_parts) == 1:
            items_str = item_parts[0]
        elif len(item_parts) == 2:
            items_str = f"{item_parts[0]} and {item_parts[1]}"
        else:
            items_str = ", ".join(item_parts[:-1]) + f", and {item_parts[-1]}"
            
        if source_desc == "__ground__":
             final_sentences.append(f"You pick up {items_str}.")
        else:
             final_sentences.append(f"You {command_verb} {items_str} {source_desc}.")

    final_message = f"{FORMAT_SUCCESS}{' '.join(final_sentences)}{FORMAT_RESET}"
    
    if cant_carry_message:
        final_message += f"{FORMAT_HIGHLIGHT}{cant_carry_message}{FORMAT_RESET}"
        
    return final_message

def _handle_item_disposal(args: List[str], context: Dict[str, Any], command_verb: str) -> str:
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You can't {command_verb} items while dead.{FORMAT_RESET}"

    if not args: return f"{FORMAT_ERROR}{command_verb.capitalize()} what?{FORMAT_RESET}"

    item_name = ""
    quantity_requested: Optional[int] = 1
    drop_all_of_type = False
    
    if args[0].lower() == "all":
        drop_all_of_type = True
        quantity_requested = None 
        if len(args) > 1:
            item_name = " ".join(args[1:]).lower()
        else:
            item_name = "" 
    elif args[0].isdigit():
        try:
            quantity_requested = int(args[0])
            if quantity_requested <= 0: return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            item_name = " ".join(args[1:]).lower()
            if not item_name: return f"{FORMAT_ERROR}{command_verb.capitalize()} {quantity_requested} of what?{FORMAT_RESET}"
        except ValueError:
            return f"{FORMAT_ERROR}Invalid quantity '{args[0]}'.{FORMAT_RESET}"
    else:
        item_name = " ".join(args).lower()
        quantity_requested = 1

    items_in_inventory = [slot.item for slot in player.inventory.slots if slot.item]
    if not items_in_inventory: return f"{FORMAT_ERROR}Your inventory is empty.{FORMAT_RESET}"
    
    # --- Matching Logic ---
    items_to_drop: List[Item] = []

    if drop_all_of_type and not item_name:
        items_to_drop = list(items_in_inventory)
    else:
        exact_matches, partial_matches = [], []
        for item in items_in_inventory:
            if item_name == item.name.lower():
                exact_matches.append(item)
            elif item_name in item.name.lower():
                partial_matches.append(item)
        
        matches = exact_matches or partial_matches

        if not matches:
            return f"{FORMAT_ERROR}You don't have any '{item_name}'.{FORMAT_RESET}"

        matches.sort(key=lambda item: item.name)

        if drop_all_of_type or (quantity_requested and quantity_requested > 1):
            items_to_drop = matches
        elif matches:
            items_to_drop = [matches[0]]

    if not items_to_drop:
        return f"{FORMAT_ERROR}You don't have any '{item_name}' to {command_verb}.{FORMAT_RESET}"

    qty_to_attempt = len(items_to_drop)
    if quantity_requested is not None:
        qty_to_attempt = min(quantity_requested, len(items_to_drop))

    items_dropped_summary: Dict[str, Any] = {}
    
    for i in range(qty_to_attempt):
        item_instance = items_to_drop[i]
        
        if player.inventory.remove_item_instance(item_instance):
            world.add_item_to_room(world.current_region_id, world.current_room_id, item_instance)
            
            summary_key = f"{item_instance.obj_id}_{item_instance.name}"
            if summary_key not in items_dropped_summary:
                items_dropped_summary[summary_key] = {"name": item_instance.name, "count": 0}
            items_dropped_summary[summary_key]["count"] += 1
        else:
            print(f"CRITICAL ERROR: Failed to remove {item_instance.name} instance from inventory during drop!")
            break

    if not items_dropped_summary:
        return f"{FORMAT_ERROR}You couldn't {command_verb} any '{item_name}'.{FORMAT_RESET}"
    
    success_parts = []
    for data in items_dropped_summary.values():
        name = data["name"]; count = data["count"]
        if count == 1:
            success_parts.append(f"{get_article(name)} {name}")
        else:
            success_parts.append(f"{count} {simple_plural(name)}")

    if not success_parts: return f"{FORMAT_ERROR}An unknown error occurred.{FORMAT_RESET}"
    
    return f"{FORMAT_SUCCESS}You {command_verb} {', '.join(success_parts)}.{FORMAT_RESET}"

# --- Command Handlers ---

@command("get", ["take", "pickup", "grab"], "interaction", "Get an item from the room or a container.\nUsage:\n  get <item>\n  get <item> from <container>")
def get_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot get items.{FORMAT_RESET}"

    # Check for "from" preposition
    if GET_COMMAND_PREPOSITION in [a.lower() for a in args]:
        try:
            from_index = [a.lower() for a in args].index(GET_COMMAND_PREPOSITION)
            item_name = " ".join(args[:from_index]).lower()
            container_name = " ".join(args[from_index + 1:]).lower()
        except ValueError: return f"{FORMAT_ERROR}Usage: get <item> from <container>{FORMAT_RESET}"

        if not item_name or not container_name: return f"{FORMAT_ERROR}Specify both an item and a container.{FORMAT_RESET}"

        # Find container in Room OR Inventory
        container = None
        # 1. Check Room
        for item in world.get_items_in_current_room():
            if isinstance(item, Container) and container_name in item.name.lower(): 
                container = item; break
        # 2. Check Inventory (if not found in room)
        if not container:
            inv_item = player.inventory.find_item_by_name(container_name)
            if isinstance(inv_item, Container): container = inv_item
        
        if not container: return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"
        if not container.properties.get("is_open", False): return f"{FORMAT_ERROR}The {container.name} is closed.{FORMAT_RESET}"

        # Handle "take all from container" (Optional enhancement, but useful)
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

        # Remove from container
        if container.remove_item(item_to_get):
            # Add to inventory
            added_success, add_msg = player.inventory.add_item(item_to_get, 1)
            if added_success:
                return f"{FORMAT_SUCCESS}You get the {item_to_get.name} from the {container.name}.{FORMAT_RESET}"
            else:
                # Rollback (put back in container if inventory add failed unexpectedly)
                container.add_item(item_to_get)
                return f"{FORMAT_ERROR}Could not take the {item_to_get.name}: {add_msg}{FORMAT_RESET}"
        else: return f"{FORMAT_ERROR}Could not get the {item_to_get.name} from the {container.name}.{FORMAT_RESET}"

    else:
        # Fallback to standard pickup from room
        return _handle_item_acquisition(args, context, "take")

@command("guide", [], "interaction", "Ask a quest giver to guide you to your destination.\nUsage: guide <npc_name>")
def guide_handler(args, context):
    world = context["world"]; player = world.player; game = context["game"]
    if not player or not game: return f"{FORMAT_ERROR}System error: context missing.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Who do you want to guide you?{FORMAT_RESET}"

    npc_name = " ".join(args)
    guide_npc = world.find_npc_in_room(npc_name)
    if not guide_npc: return f"{FORMAT_ERROR}You don't see '{npc_name}' here.{FORMAT_RESET}"

    # Find an active instance quest given by this NPC
    quest_to_guide = None
    for quest in player.quest_log.values():
        if quest.get("giver_instance_id") == guide_npc.obj_id and quest.get("type") == "instance":
            quest_to_guide = quest
            break
    
    if not quest_to_guide: return f"{guide_npc.name} has not offered to guide you anywhere."

    entry_point = quest_to_guide.get("entry_point")
    if not entry_point: return f"{FORMAT_ERROR}Quest '{quest_to_guide.get('title')}' has no destination.{FORMAT_RESET}"

    destination_region = entry_point.get("region_id")
    destination_room = entry_point.get("room_id")

    path = world.find_path(player.current_region_id, player.current_room_id, destination_region, destination_room)

    if path is None: return f"{guide_npc.name} seems confused and can't find a path from here."
    if not path: return f"You are already at the destination!"

    game.start_auto_travel(path, guide_npc)
    return f"{FORMAT_HIGHLIGHT}\"{guide_npc.dialog.get('accept_guide', 'Follow me!')}\"{FORMAT_RESET}"

@command("read", category="interaction", help_text="Read something, like a book, scroll, or sign.\nUsage: read <object>")
def read_handler(args, context):
    """
    Handles the 'read' command by delegating to the 'look' command.
    This allows 'read board', 'read scroll', etc., to work as expected.
    """
    if not args:
        return f"{FORMAT_ERROR}What do you want to read?{FORMAT_RESET}"
    
    # The look_handler already contains all the logic for examining items,
    # the board, etc., so we can just reuse it.
    return look_handler(args, context)

@command("look", ["l"], "interaction", "Look around or examine something.\nUsage: look [target]")
def look_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"

    if not args: return world.look(minimal=True)

    # --- Preposition Parsing ---
    args_lower = [a.lower() for a in args]
    target_name = ""
    look_inside = False

    if "in" in args_lower:
        idx = args_lower.index("in")
        if idx + 1 < len(args):
            target_name = " ".join(args[idx+1:]).lower()
            look_inside = True
        else:
            return f"{FORMAT_ERROR}Look in what?{FORMAT_RESET}"
    elif "inside" in args_lower:
        idx = args_lower.index("inside")
        if idx + 1 < len(args):
            target_name = " ".join(args[idx+1:]).lower()
            look_inside = True
        else:
            return f"{FORMAT_ERROR}Look inside what?{FORMAT_RESET}"
    elif "at" in args_lower:
        idx = args_lower.index("at")
        if idx + 1 < len(args):
            target_name = " ".join(args[idx+1:]).lower()
        else:
            return f"{FORMAT_ERROR}Look at what?{FORMAT_RESET}"
    else:
        target_name = " ".join(args).lower()

    # --- "Look in Inventory" Redirect ---
    if look_inside and target_name in ["inventory", "my inventory", "bag", "backpack"]:
        from commands.inventory import inventory_handler
        return inventory_handler([], context)

    # --- Quest Board Check ---
    if not look_inside and target_name in QUEST_BOARD_ALIASES:
        quest_manager = world.quest_manager
        if quest_manager:
            board_look_command = registered_commands.get("look board")
            if board_look_command and 'handler' in board_look_command:
                return board_look_command['handler']([], context)
        return f"{FORMAT_ERROR}The quest system seems to be unavailable.{FORMAT_RESET}"

    # --- Find Target ---
    target = None
    
    # 1. NPC in room
    target = world.find_npc_in_room(target_name)
    
    # 2. Item in room
    if not target:
        target = world.find_item_in_room(target_name)
    
    # 3. Item in inventory
    if not target:
        target = player.inventory.find_item_by_name(target_name)
    
    # 4. Equipped item
    if not target:
        for slot, item in player.equipment.items():
            if item and (target_name == item.name.lower() or target_name in item.name.lower()):
                target = item
                break

    if not target:
        return f"{FORMAT_ERROR}You don't see '{target_name}' here.{FORMAT_RESET}"

    # --- Action ---
    if look_inside:
        if isinstance(target, Container):
            if target.properties.get("is_open", False):
                return f"{FORMAT_TITLE}Inside the {target.name}:{FORMAT_RESET}\n{target.list_contents()}"
            else:
                status = "locked" if target.properties.get("locked", False) else "closed"
                return f"The {target.name} is {status}."
        else:
            return f"{FORMAT_ERROR}That is not a container.{FORMAT_RESET}"
    else:
        # Standard examine
        if isinstance(target, NPC):
            return target.get_description()
        elif isinstance(target, Item):
            return target.examine()
        
    return f"You see {target.name}."

@command("examine", ["x", "exam"], "interaction", "Examine something.\nUsage: examine <target>")
def examine_handler(args, context):
    player = context["world"].player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}What do you want to examine?{FORMAT_RESET}"
    return look_handler(args, context)

@command("drop", ["putdown"], "interaction", "Drop one, multiple, or all matching items.\nUsage: drop [all|quantity] <item_name>")
def drop_handler(args, context):
    return _handle_item_disposal(args, context, "drop")

@command("take", ["pickup", "grab"], "interaction", "Pick up an item from the room.\nUsage: take [all|quantity] <item_name> | take all")
def take_handler(args, context):
    return _handle_item_acquisition(args, context, "take")

@command("put", ["store"], "interaction", "Put an item into a container.\nUsage: put <item_name> in <container_name>")
def put_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot store items.{FORMAT_RESET}"

    if PUT_COMMAND_PREPOSITION not in [a.lower() for a in args]: return f"{FORMAT_ERROR}Usage: put <item_name> {PUT_COMMAND_PREPOSITION} <container_name>{FORMAT_RESET}"

    try:
        in_index = [a.lower() for a in args].index(PUT_COMMAND_PREPOSITION)
        item_name = " ".join(args[:in_index]).lower()
        container_name = " ".join(args[in_index + 1:]).lower()
    except ValueError: return f"{FORMAT_ERROR}Usage: put <item_name> in <container_name>{FORMAT_RESET}"

    if not item_name or not container_name: return f"{FORMAT_ERROR}Specify both an item and a container.{FORMAT_RESET}"
    item_to_put = player.inventory.find_item_by_name(item_name)
    if not item_to_put: return f"{FORMAT_ERROR}You don't have '{item_name}'.{FORMAT_RESET}"

    container = None
    for item in world.get_items_in_current_room():
        if isinstance(item, Container) and container_name in item.name.lower(): container = item; break
    if not container:
        inv_item = player.inventory.find_item_by_name(container_name)
        if isinstance(inv_item, Container): container = inv_item
    if not container: return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"

    can_add, msg = container.can_add(item_to_put)
    if not can_add: return f"{FORMAT_ERROR}{msg}{FORMAT_RESET}"

    removed_item, quantity_removed, remove_msg = player.inventory.remove_item(item_to_put.obj_id, 1)
    if not removed_item: return f"{FORMAT_ERROR}Failed to get '{item_name}' from inventory: {remove_msg}{FORMAT_RESET}"

    if container.add_item(removed_item): return f"{FORMAT_SUCCESS}You put the {removed_item.name} in the {container.name}.{FORMAT_RESET}"
    else:
        player.inventory.add_item(removed_item, 1)
        return f"{FORMAT_ERROR}Could not put the {removed_item.name} in the {container.name}.{FORMAT_RESET}"

@command("open", [], "interaction", "Open a container.\nUsage: open <container_name>")
def open_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot open things.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Open what?{FORMAT_RESET}"
    
    container_name = " ".join(args).lower(); container = None
    for item in world.get_items_in_current_room():
        if isinstance(item, Container) and container_name in item.name.lower(): container = item; break
    if not container:
        inv_item = player.inventory.find_item_by_name(container_name)
        if isinstance(inv_item, Container): container = inv_item
    if not container: return f"{FORMAT_ERROR}You don't see a container called '{container_name}' here.{FORMAT_RESET}"
    return f"{FORMAT_HIGHLIGHT}{container.open()}{FORMAT_RESET}"

@command("close", [], "interaction", "Close a container.\nUsage: close <container_name>")
def close_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot close things.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Close what?{FORMAT_RESET}"

    container_name = " ".join(args).lower(); container = None
    for item in world.get_items_in_current_room():
        if isinstance(item, Container) and container_name in item.name.lower(): container = item; break
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

    world = context["world"]; item_name = ""; target_name = ""; prep_index = -1
    supported_prepositions = USE_COMMAND_PREPOSITIONS
    for i, word in enumerate(args):
        if word.lower() in supported_prepositions: prep_index = i; break
    if prep_index != -1:
        item_name = " ".join(args[:prep_index]).lower()
        target_name = " ".join(args[prep_index + 1:]).lower()
    else: item_name = " ".join(args).lower()
    item_to_use = player.inventory.find_item_by_name(item_name)
    if not item_to_use: return f"{FORMAT_ERROR}You don't have a '{item_name}'.{FORMAT_RESET}"

    if target_name:
        target = world.find_item_in_room(target_name) or player.inventory.find_item_by_name(target_name, exclude=item_to_use) or world.find_npc_in_room(target_name)
        if not target and target_name in ["self", "me", player.name.lower()]: target = player
        if not target: return f"{FORMAT_ERROR}You don't see a '{target_name}' here to use the {item_to_use.name} on.{FORMAT_RESET}"
        try:
            result = item_to_use.use(user=player, target=target)
            if isinstance(item_to_use, Consumable) and item_to_use.get_property("uses", 1) <= 0: player.inventory.remove_item(item_to_use.obj_id)
            return f"{FORMAT_HIGHLIGHT}{result}{FORMAT_RESET}"
        except TypeError as e:
             if "unexpected keyword argument 'target'" in str(e) or "takes 2 positional arguments but 3 were given" in str(e): return f"{FORMAT_ERROR}You can't use the {item_to_use.name} on the {getattr(target, 'name', 'target')}.{FORMAT_RESET}"
             else: raise e
        except Exception as e: return f"{FORMAT_ERROR}Something went wrong trying to use the {item_to_use.name}: {e}{FORMAT_RESET}"
    else:
        if isinstance(item_to_use, Key): return f"{FORMAT_ERROR}What do you want to use the {item_to_use.name} on? Usage: use <key> on <target>.{FORMAT_RESET}"
        try:
            result = item_to_use.use(user=player)
            if isinstance(item_to_use, Consumable) and item_to_use.get_property("uses", 1) <= 0: player.inventory.remove_item(item_to_use.obj_id)
            return f"{FORMAT_HIGHLIGHT}{result}{FORMAT_RESET}"
        except Exception as e: return f"{FORMAT_ERROR}Something went wrong trying to use the {item_to_use.name}: {e}{FORMAT_RESET}"

@command("talk", ["speak", "chat", "ask"], "interaction", "Talk to an NPC.\nUsage: talk <npc_name> [topic | complete quest]")
def talk_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Talk to whom?{FORMAT_RESET}"

    npc_name = args[0].lower(); topic = None; is_quest_turn_in = False
    if len(args) > 1:
        if args[1].lower() in ["complete", "report", "finish", "turnin"] and (len(args) < 3 or args[2].lower() == "quest"): is_quest_turn_in = True
        else: topic = " ".join(args[1:])
    target_npc = world.find_npc_in_room(npc_name)
    if not target_npc: return f"{FORMAT_ERROR}There's no '{args[0]}' here.{FORMAT_RESET}"
    
    if hasattr(player, 'quest_log') and player.quest_log:
        for q_id, q_data in player.quest_log.items():
            if (q_data.get("state") == "active" and
                q_data.get("type") == "fetch" and
                q_data.get("giver_instance_id") == target_npc.obj_id):
                
                objective = q_data.get("objective", {})
                required_item_id = objective.get("item_id")
                required_qty = objective.get("required_quantity", 1)
                
                if required_item_id and player.inventory.count_item(required_item_id) >= required_qty:
                    # The player has the items! Update the quest state in their log.
                    q_data["state"] = "ready_to_complete"

    ready_quests_for_npc = []
    if hasattr(player, 'quest_log') and player.quest_log:
        for q_id, q_data in player.quest_log.items():
            if (q_data.get("state") == "ready_to_complete" and q_data.get("giver_instance_id") == target_npc.obj_id):
                ready_quests_for_npc.append((q_id, q_data))
    
    if is_quest_turn_in:
        if not ready_quests_for_npc: return f"{target_npc.name} doesn't seem to be expecting anything from you right now."
        quest_turn_in_id, quest_data = ready_quests_for_npc[0]
        quest_type = quest_data.get("type"); objective = quest_data.get("objective", {}); can_complete = True; completion_error_msg = ""
        if quest_type == "fetch":
            required_item_id = objective.get("item_id"); required_qty = objective.get("required_quantity", 1)
            player_has_qty = player.inventory.count_item(required_item_id)
            if player_has_qty < required_qty:
                can_complete = False; completion_error_msg = f"You still need {required_qty - player_has_qty} more {objective.get('item_name_plural', 'items')}."
            else:
                removed_type, removed_count, remove_msg = player.inventory.remove_item(required_item_id, required_qty)
                if not removed_type or removed_count != required_qty:
                     can_complete = False; completion_error_msg = "Error removing required items from your inventory. Cannot complete quest."
        elif quest_type == "deliver":
            required_instance_id = objective.get("item_instance_id")
            package_instance = player.inventory.find_item_by_id(required_instance_id)
            if not package_instance:
                can_complete = False; completion_error_msg = f"You don't seem to have the {objective.get('item_to_deliver_name', 'package')} anymore!"
            else:
                if not player.inventory.remove_item_instance(package_instance):
                     can_complete = False; completion_error_msg = f"Error removing the {objective.get('item_to_deliver_name', 'package')} from your inventory."
        if can_complete:
            rewards = quest_data.get("rewards", {}); xp_reward = rewards.get("xp", 0); gold_reward = rewards.get("gold", 0)

            leveled_up, level_up_message = False, ""
            reward_messages = []

            if xp_reward > 0:
                 leveled_up, level_up_message = player.gain_experience(xp_reward) # Capture both return values
                 reward_messages.append(f"{xp_reward} XP")

            if gold_reward > 0: player.gold += gold_reward; reward_messages.append(f"{gold_reward} Gold")
            if quest_turn_in_id in player.quest_log:
                completed_quest = player.quest_log.pop(quest_turn_in_id)
                player.completed_quest_log[quest_turn_in_id] = completed_quest

            quest_manager = context["world"].quest_manager
            if quest_manager: quest_manager.replenish_board(quest_turn_in_id)

            completion_message = f"{FORMAT_SUCCESS}[Quest Complete] {quest_data.get('title', 'Task')}{FORMAT_RESET}\n"
            npc_response = target_npc.dialog.get(f"complete_{quest_turn_in_id}", target_npc.dialog.get("quest_complete", f"\"Ah, thank you for your help!\" says {target_npc.name}."))
            completion_message += f"{FORMAT_HIGHLIGHT}{npc_response}{FORMAT_RESET}\n"
            if reward_messages: completion_message += "You receive: " + ", ".join(reward_messages) + "."

            if quest_type == "instance":
                # Despawn the giver NPC after instance turn-in ---
                giver_id = quest_data.get("giver_instance_id")
                if giver_id and giver_id in world.npcs:
                    del world.npcs[giver_id]
                    completion_message += f"\nHaving given you your reward, {target_npc.name} heads back inside their home."

            if leveled_up and level_up_message:
                completion_message += "\n\n" + level_up_message

            return completion_message
        else: return f"{FORMAT_ERROR}You haven't fully met the requirements for '{quest_data.get('title', 'this quest')}'. {completion_error_msg}{FORMAT_RESET}"
    else:
        turn_in_hint = f"\n{FORMAT_HIGHLIGHT}(You have tasks to report. Type 'talk {npc_name} complete quest'){FORMAT_RESET}" if ready_quests_for_npc else ""
        offer_hint = f"\n{FORMAT_HIGHLIGHT}({target_npc.name} might have work. Try 'talk {npc_name} work'){FORMAT_RESET}" if target_npc.properties.get("can_give_generic_quests", False) else ""
        response = target_npc.talk(topic)
        npc_title = f"{FORMAT_TITLE}CONVERSATION WITH {target_npc.name.upper()}{FORMAT_RESET}\n\n"
        if topic: return f"{npc_title}You ask {target_npc.name} about '{topic}'.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}{turn_in_hint}{offer_hint}"
        else: return f"{npc_title}You greet {target_npc.name}.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}{turn_in_hint}{offer_hint}"

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

@command("trade", ["shop"], "interaction", "Initiate trade with a vendor.\nUsage: trade <npc_name>")
def trade_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You cannot trade while dead.{FORMAT_RESET}"
    if player.trading_with:
        old_vendor = world.get_npc(player.trading_with)
        if old_vendor: old_vendor.is_trading = False
        player.trading_with = None
    if not args: return f"{FORMAT_ERROR}Trade with whom?{FORMAT_RESET}"
    npc_name = " ".join(args).lower()
    vendor = world.find_npc_in_room(npc_name)
    if not vendor: return f"{FORMAT_ERROR}You don't see '{npc_name}' here.{FORMAT_RESET}"
    if not vendor.properties.get("is_vendor", False): return f"{FORMAT_ERROR}{vendor.name} doesn't seem interested in trading.{FORMAT_RESET}"
    vendor.is_trading = True
    player.trading_with = vendor.obj_id
    greeting = vendor.dialog.get("trade", vendor.dialog.get("greeting", "What can I do for you?")).format(name=vendor.name)
    response = f"You approach {vendor.name} to trade.\n{FORMAT_HIGHLIGHT}\"{greeting}\"{FORMAT_RESET}\n\n"
    response += _display_vendor_inventory(player, vendor, world)
    return response

@command("list", ["browse"], "interaction", "List items available from the current vendor.\nUsage: list")
def list_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.trading_with: return f"{FORMAT_ERROR}You are not currently trading with anyone.{FORMAT_RESET}"
    vendor = world.get_npc(player.trading_with)
    if not vendor or vendor.current_region_id != player.current_region_id or vendor.current_room_id != player.current_room_id:
        player.trading_with = None; return f"{FORMAT_ERROR}The vendor you were trading with is no longer here.{FORMAT_RESET}"
    return _display_vendor_inventory(player, vendor, world)

@command("buy", [], "interaction", "Buy an item from the current vendor.\nUsage: buy <item_name> [quantity]")
def buy_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.trading_with: return f"{FORMAT_ERROR}You need to 'trade' with someone first.{FORMAT_RESET}"
    vendor = world.get_npc(player.trading_with)
    if not vendor or vendor.current_region_id != player.current_region_id or vendor.current_room_id != player.current_room_id:
        player.trading_with = None; return f"{FORMAT_ERROR}The vendor you were trading with is gone.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Buy what? Usage: buy <item_name> [quantity]{FORMAT_RESET}"

    item_name = ""; quantity = 1
    try:
        if args[-1].isdigit():
            quantity = int(args[-1])
            if quantity <= 0: return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            item_name = " ".join(args[:-1]).lower()
        else: item_name = " ".join(args).lower()
    except ValueError: return f"{FORMAT_ERROR}Invalid quantity specified.{FORMAT_RESET}"
    if not item_name: return f"{FORMAT_ERROR}You must specify an item name.{FORMAT_RESET}"

    found_item_ref = None; found_template = None
    for item_ref in vendor.properties.get("sells_items", []):
        item_id = item_ref.get("item_id")
        if not item_id: continue
        template = world.item_templates.get(item_id)
        if template:
            name_in_template = template.get("name", "").lower()
            if item_name == item_id.lower() or item_name == name_in_template:
                found_item_ref = item_ref; found_template = template; break
            elif item_name in name_in_template:
                 found_item_ref = item_ref; found_template = template
    if not found_item_ref or not found_template:
        return f"{FORMAT_ERROR}{vendor.name} doesn't sell '{item_name}'. Type 'list' to see wares.{FORMAT_RESET}"

    item_id = found_template["obj_id"] = found_item_ref["item_id"]
    base_value = found_template.get("value", 0)
    price_multiplier = found_item_ref.get("price_multiplier", DEFAULT_VENDOR_SELL_MULTIPLIER)
    buy_price_per_item = max(VENDOR_MIN_BUY_PRICE, int(base_value * price_multiplier))
    total_cost = buy_price_per_item * quantity
    if player.gold < total_cost: return f"{FORMAT_ERROR}You don't have enough gold (Need {total_cost}, have {player.gold}).{FORMAT_RESET}"
    
    temp_item = ItemFactory.create_item_from_template(item_id, world)
    if not temp_item: return f"{FORMAT_ERROR}Internal error creating item '{item_id}'. Cannot buy.{FORMAT_RESET}"
    can_add, inv_msg = player.inventory.can_add_item(temp_item, quantity)
    if not can_add: return f"{FORMAT_ERROR}{inv_msg}{FORMAT_RESET}"

    player.gold -= total_cost
    items_added_successfully = 0
    for _ in range(quantity):
         item_instance = ItemFactory.create_item_from_template(item_id, world)
         if item_instance:
              added, add_msg = player.inventory.add_item(item_instance, 1)
              if added: items_added_successfully += 1
              else:
                   print(f"Error: Failed to add '{item_instance.name}' to inventory despite passing checks: {add_msg}")
                   player.gold += buy_price_per_item * (quantity - items_added_successfully)
                   return f"{FORMAT_ERROR}Failed to add all items to inventory. Transaction partially reverted.{FORMAT_RESET}"
         else:
              player.gold += buy_price_per_item * (quantity - items_added_successfully)
              return f"{FORMAT_ERROR}Failed to create item instance during purchase. Transaction cancelled.{FORMAT_RESET}"
    item_display_name = found_template.get("name", item_id)
    return f"{FORMAT_SUCCESS}You buy {quantity} {item_display_name}{'' if quantity == 1 else 's'} for {total_cost} gold.{FORMAT_RESET}\nYour Gold: {player.gold}"

@command("sell", [], "interaction", "Sell an item from your inventory to the current vendor.\nUsage: sell <item_name> [quantity]")
def sell_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.trading_with: return f"{FORMAT_ERROR}You need to 'trade' with someone first.{FORMAT_RESET}"
    vendor = world.get_npc(player.trading_with)
    if not vendor or vendor.current_region_id != player.current_region_id or vendor.current_room_id != player.current_room_id:
        player.trading_with = None; return f"{FORMAT_ERROR}The vendor you were trading with is gone.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Sell what? Usage: sell <item_name> [quantity]{FORMAT_RESET}"

    item_name = ""; quantity = 1
    try:
        if args[-1].isdigit():
            quantity = int(args[-1])
            if quantity <= 0: return f"{FORMAT_ERROR}Quantity must be positive.{FORMAT_RESET}"
            item_name = " ".join(args[:-1]).lower()
        else: item_name = " ".join(args).lower()
    except ValueError: return f"{FORMAT_ERROR}Invalid quantity specified.{FORMAT_RESET}"
    if not item_name: return f"{FORMAT_ERROR}You must specify an item name.{FORMAT_RESET}"
    
    item_to_sell = player.inventory.find_item_by_name(item_name)
    if not item_to_sell: return f"{FORMAT_ERROR}You don't have '{item_name}' to sell.{FORMAT_RESET}"
    if player.inventory.count_item(item_to_sell.obj_id) < quantity: return f"{FORMAT_ERROR}You only have {player.inventory.count_item(item_to_sell.obj_id)} {item_to_sell.name}(s) to sell.{FORMAT_RESET}"

    can_sell = False
    vendor_buy_types = vendor.properties.get("buys_item_types", [])
    item_type_name = item_to_sell.__class__.__name__
    if VENDOR_CAN_BUY_ALL_ITEMS or item_type_name in vendor_buy_types or ("Item" in vendor_buy_types and item_type_name == "Item"):
        can_sell = True
    if not can_sell: return f"{FORMAT_ERROR}{vendor.name} is not interested in buying {item_to_sell.name}.{FORMAT_RESET}"
    
    sell_price_per_item = max(VENDOR_MIN_SELL_PRICE, int(item_to_sell.value * DEFAULT_VENDOR_BUY_MULTIPLIER))
    total_gold_gain = sell_price_per_item * quantity
    removed_item_type, actual_removed_count, remove_msg = player.inventory.remove_item(item_to_sell.obj_id, quantity)
    if not removed_item_type or actual_removed_count != quantity:
         return f"{FORMAT_ERROR}Something went wrong removing {item_to_sell.name} from your inventory. Sale cancelled.{FORMAT_RESET}"
    player.gold += total_gold_gain
    return f"{FORMAT_SUCCESS}You sell {quantity} {removed_item_type.name}{'' if quantity == 1 else 's'} for {total_gold_gain} gold.{FORMAT_RESET}\nYour Gold: {player.gold}"

@command("stoptrade", ["stop", "done"], "interaction", "Stop trading with the current vendor.\nUsage: stoptrade")
def stoptrade_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.trading_with: return "You are not currently trading with anyone."
    vendor = world.get_npc(player.trading_with)
    if vendor: vendor.is_trading = False
    player.trading_with = None
    return f"You stop trading with {vendor.name if vendor else 'the vendor'}."

@command("repair", [], "interaction", "Ask a capable NPC to repair an item.\nUsage: repair <item_name>")
def repair_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You can't get items repaired while dead.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}What item do you want to repair? Usage: repair <item_name>{FORMAT_RESET}"
    item_name_to_repair = " ".join(args).lower()
    
    repair_npc = None
    for npc in world.get_current_room_npcs():
        if npc.properties.get("can_repair", False): repair_npc = npc; break
    if not repair_npc: return f"{FORMAT_ERROR}There is no one here who can repair items.{FORMAT_RESET}"
    
    item_to_repair = player.inventory.find_item_by_name(item_name_to_repair)
    if not item_to_repair:
        for slot, equipped_item in player.equipment.items():
            if equipped_item and item_name_to_repair in equipped_item.name.lower():
                 if equipped_item.get_property("durability") is not None:
                     item_to_repair = equipped_item; break
                 else: return f"{FORMAT_ERROR}The {equipped_item.name} cannot be repaired.{FORMAT_RESET}"
    if not item_to_repair: return f"{FORMAT_ERROR}You don't have an item called '{item_name_to_repair}' that can be repaired.{FORMAT_RESET}"

    repair_cost, error_msg = _calculate_repair_cost(item_to_repair)
    if error_msg: return f"{FORMAT_ERROR}{error_msg}{FORMAT_RESET}"
    if repair_cost == 0: return f"Your {item_to_repair.name} is already in perfect condition."
    if repair_cost is None: return f"{FORMAT_ERROR}Cannot determine repair cost for {item_to_repair.name}.{FORMAT_RESET}"
    if player.gold < repair_cost: return f"{FORMAT_ERROR}You need {repair_cost} gold to repair the {item_to_repair.name}, but you only have {player.gold}.{FORMAT_RESET}"

    player.gold -= repair_cost
    item_to_repair.update_property("durability", item_to_repair.get_property("max_durability"))
    return f"{FORMAT_SUCCESS}You pay {repair_cost} gold. {repair_npc.name} repairs your {item_to_repair.name} to perfect condition.{FORMAT_RESET}\nYour Gold: {player.gold}"

@command("repaircost", ["checkrepair", "rcost"], "interaction", "Check the cost to repair an item.\nUsage: repaircost <item_name>")
def repaircost_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}What item do you want to check the repair cost for? Usage: repaircost <item_name>{FORMAT_RESET}"
    item_name_to_check = " ".join(args).lower()
    
    repair_npc = None
    for npc in world.get_current_room_npcs():
        if npc.properties.get("can_repair", False): repair_npc = npc; break
    if not repair_npc: return f"{FORMAT_ERROR}There is no one here who can quote a repair price.{FORMAT_RESET}"

    item_to_check = player.inventory.find_item_by_name(item_name_to_check)
    if not item_to_check:
        for slot, equipped_item in player.equipment.items():
            if equipped_item and item_name_to_check in equipped_item.name.lower():
                if equipped_item.get_property("durability") is not None: item_to_check = equipped_item; break
                else: return f"{FORMAT_ERROR}The {equipped_item.name} cannot be repaired.{FORMAT_RESET}"
    if not item_to_check: return f"{FORMAT_ERROR}You don't have an item called '{item_name_to_check}' that can be repaired.{FORMAT_RESET}"
    
    repair_cost, error_msg = _calculate_repair_cost(item_to_check)
    if error_msg: return f"{FORMAT_ERROR}{error_msg}{FORMAT_RESET}"
    if repair_cost == 0: return f"Your {item_to_check.name} does not need repairing."
    if repair_cost is None: return f"{FORMAT_ERROR}Cannot determine repair cost for {item_to_check.name}.{FORMAT_RESET}"
    
    return f"{repair_npc.name} quotes a price of {FORMAT_HIGHLIGHT}{repair_cost} gold{FORMAT_RESET} to fully repair your {item_to_check.name}."

@command(name="give", aliases=[], category="interaction", help_text="Give an item from your inventory to someone.\nUsage: give <item_name> to <npc_name>")
def give_handler(args, context):
    world = context["world"]; player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You can't give items while dead.{FORMAT_RESET}"
    if GIVE_COMMAND_PREPOSITION not in [a.lower() for a in args]: return f"{FORMAT_ERROR}Usage: give <item_name> {GIVE_COMMAND_PREPOSITION} <npc_name>{FORMAT_RESET}"
    try:
        to_index = [a.lower() for a in args].index(GIVE_COMMAND_PREPOSITION)
        item_name = " ".join(args[:to_index]).lower()
        npc_name = " ".join(args[to_index + 1:]).lower()
    except ValueError: return f"{FORMAT_ERROR}Usage: give <item_name> to <npc_name>{FORMAT_RESET}"
    if not item_name or not npc_name: return f"{FORMAT_ERROR}Specify both an item and who to give it to.{FORMAT_RESET}"
    
    item_to_give = player.inventory.find_item_by_name(item_name)
    if not item_to_give and "package" in item_name:
        for slot in player.inventory.slots:
             if slot.item and "package" in slot.item.name.lower(): item_to_give = slot.item; break
    if not item_to_give: return f"{FORMAT_ERROR}You don't have '{item_name}'.{FORMAT_RESET}"
    
    target_npc = world.find_npc_in_room(npc_name)
    if not target_npc: return f"{FORMAT_ERROR}You don't see '{npc_name}' here.{FORMAT_RESET}"

    # quest turn-in
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
            
            rewards = matching_quest_data.get("rewards", {}); xp_reward = rewards.get("xp", 0); gold_reward = rewards.get("gold", 0)


            leveled_up, level_up_message = False, ""
            reward_messages = []
            if xp_reward > 0:
                leveled_up, level_up_message = player.gain_experience(xp_reward)
                reward_messages.append(f"{xp_reward} XP")

            if gold_reward > 0: player.gold += gold_reward; reward_messages.append(f"{gold_reward} Gold")
            
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
        removed_item_type, removed_count, remove_msg = player.inventory.remove_item(item_to_give.obj_id, 1)
        if not removed_item_type or removed_count != 1: return f"{FORMAT_ERROR}Failed to take '{item_to_give.name}' from inventory: {remove_msg}{FORMAT_RESET}"
        return f"{FORMAT_SUCCESS}You give the {item_to_give.name} to {target_npc.name}.{FORMAT_RESET}"