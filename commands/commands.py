"""
commands/commands.py
Unified command system for the MUD game.
"""
import os
import time
from commands.command_system import command, registered_commands
from core.config import DEFAULT_WORLD_FILE, FORMAT_CATEGORY, FORMAT_TITLE, FORMAT_HIGHLIGHT, FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, SAVE_GAME_DIR
from items.consumable import Consumable
from items.item_factory import ItemFactory
from items.junk import Junk
from items.key import Key
from items.container import Container
from utils.text_formatter import TextFormatter
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
    registered = {}
    for direction_info in DIRECTIONS:
        direction_name = direction_info["name"]; direction_aliases = direction_info["aliases"]; direction_description = direction_info["description"]
        if direction_name in registered_commands: continue
        def create_direction_handler(dir_name):
            def handler(args, context): return context["world"].change_room(dir_name)
            return handler
        handler = create_direction_handler(direction_name)
        decorated_handler = command(direction_name, direction_aliases, "movement", direction_description)(handler)
        registered[direction_name] = decorated_handler
    return registered

@command("go", ["move", "walk"], "movement", "Move in a direction.\nUsage: go <direction>")
def go_handler(args, context):
    player = context["world"].player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args: return "Go where?"
    return context["world"].change_room(args[0].lower())

@command("help", ["h", "?"], "system", "Show help.\nUsage: help [command]")
def help_handler(args, context):
    cp = context["command_processor"]
    return cp.get_command_help(args[0]) if args else cp.get_help_text()

@command("quit", ["q", "exit"], "system", "Exit the game.")
def quit_handler(args, context):
    if "game" in context: context["game"].quit_game()
    return f"{FORMAT_HIGHLIGHT}Goodbye!{FORMAT_RESET}"

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
    if not args:
        return world.get_room_description_for_display()

    target = " ".join(args).lower()

    # Prioritize NPCs
    npcs = world.get_current_room_npcs()
    for npc in npcs:
        if target == npc.name.lower() or target == npc.obj_id:
            return npc.get_description()
        elif target in npc.name.lower():
             return npc.get_description() # Return first partial match

    # Check items in room
    items = world.get_items_in_current_room()
    for item in items:
        if target == item.name.lower() or target == item.obj_id:
            return item.examine()
        elif target in item.name.lower():
             return item.examine() # Return first partial match

    # Check items in inventory
    inv_item = world.player.inventory.find_item_by_name(target)
    if inv_item:
        return inv_item.examine()

    # Check equipped items
    for slot, equipped_item in world.player.equipment.items():
        if equipped_item and (target == equipped_item.name.lower() or target == equipped_item.obj_id):
            return equipped_item.examine()
        elif equipped_item and target in equipped_item.name.lower():
             return equipped_item.examine() # Return first partial match

    return f"You see no '{' '.join(args)}' here."

@command("examine", ["x", "exam"], "interaction", "Examine something.\nUsage: examine <target>")
def examine_handler(args, context):
    if not args: return f"{FORMAT_ERROR}What do you want to examine?{FORMAT_RESET}"
    return look_handler(args, context) # Delegate to look handler

@command("take", ["get", "pickup"], "interaction", "Pick up an item.\nUsage: take <item>")
def take_handler(args, context):
    player = context["world"].player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    world = context["world"]
    if not args: return f"{FORMAT_ERROR}Take what?{FORMAT_RESET}"
    item_name = " ".join(args).lower()
    items = world.get_items_in_current_room()
    for item in items:
        if item_name in item.name.lower() or item_name == item.obj_id:
            success, message = world.player.inventory.add_item(item)
            if success:
                world.remove_item_from_room(world.current_region_id, world.current_room_id, item.obj_id)
                return f"{FORMAT_SUCCESS}You take the {item.name}.{FORMAT_RESET}\n{message}"
            else: return f"{FORMAT_ERROR}{message}{FORMAT_RESET}"
    return f"{FORMAT_ERROR}You don't see a {' '.join(args)} here.{FORMAT_RESET}"

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

@command("talk", ["speak", "chat", "ask"], "interaction", "Talk to an NPC.\nUsage: talk <npc> [topic]")
def talk_handler(args, context):
    world = context["world"]
    if not args: return f"{FORMAT_ERROR}Talk to whom?{FORMAT_RESET}"
    npc_name = args[0].lower()
    topic = " ".join(args[1:]) if len(args) > 1 else None
    npcs = world.get_current_room_npcs()
    for npc in npcs:
        if npc_name in npc.name.lower() or npc_name == npc.obj_id:
            response = npc.talk(topic)
            npc_title = f"{FORMAT_TITLE}CONVERSATION WITH {npc.name.upper()}{FORMAT_RESET}\n\n"
            if topic: return f"{npc_title}You ask {npc.name} about '{topic}'.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}"
            else: return f"{npc_title}You greet {npc.name}.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}"
    return f"{FORMAT_ERROR}There's no '{args[0]}' here.{FORMAT_RESET}"

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
    supported_prepositions = ["on"]
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
    if cmd_arg == "stop" or cmd_arg == "none":
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

@command("trade", ["shop", "buy", "sell"], "interaction", "Trade with NPC.\nUsage: trade <npc_name>")
def trade_handler(args, context):
    world = context["world"]
    player = world.player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"

    if not args: return f"{FORMAT_ERROR}Trade with whom?{FORMAT_RESET}"
    npc_name = " ".join(args).lower(); npcs = world.get_current_room_npcs(); found_npc = None
    for npc in npcs:
        if npc_name in npc.name.lower() or npc_name == npc.obj_id: found_npc = npc; break
    if not found_npc: return f"{FORMAT_ERROR}No '{npc_name}' here.{FORMAT_RESET}"
    is_vendor = found_npc.get_property("is_vendor", False) or ("trade" in found_npc.dialog) or any(vt in found_npc.obj_id.lower() for vt in ["shop","merchant"])
    if is_vendor:
        greeting = found_npc.dialog.get("trade", found_npc.dialog.get("greeting", "What can I do for you?")).format(name=found_npc.name)
        return f"{FORMAT_HIGHLIGHT}{found_npc.name} says: \"{greeting}\"{FORMAT_RESET}\n\n(Trade commands 'list', 'buy', 'sell' pending.)"
    else: return f"{FORMAT_ERROR}{found_npc.name} doesn't want to trade.{FORMAT_RESET}"


# ... (attack_handler, combat_status_handler - unchanged) ...
@command("attack", ["kill", "fight", "hit"], "combat", "Attack a target.\nUsage: attack <target_name>")
def attack_handler(args, context):
    world = context["world"]
    player = world.player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}Attack whom?{FORMAT_RESET}"
    target_name = " ".join(args).lower()
    npcs = world.get_current_room_npcs(); target_npc = None
    # Prioritize exact match
    for npc in npcs:
        if target_name == npc.name.lower() or target_name == npc.obj_id: target_npc = npc; break
    # Fallback partial match
    if not target_npc:
        for npc in npcs:
            if target_name in npc.name.lower(): target_npc = npc; break
    if not target_npc: return f"{FORMAT_ERROR}No '{target_name}' here to attack.{FORMAT_RESET}"
    if not target_npc.is_alive: return f"{FORMAT_ERROR}{target_npc.name} is already defeated.{FORMAT_RESET}"
    current_time = time.time()
    if not player.can_attack(current_time):
        time_left = player.attack_cooldown - (current_time - player.last_attack_time)
        return f"Not ready. Wait {time_left:.1f}s."
    attack_result = player.attack(target_npc, world) # Player method handles messages/combat log
    # Return only the primary message to the game loop
    return attack_result["message"]

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
    if "to" in [a.lower() for a in args]:
         try:
              to_index = [a.lower() for a in args].index("to")
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
    if not args or "in" not in [a.lower() for a in args]:
        return f"{FORMAT_ERROR}Usage: put <item_name> in <container_name>{FORMAT_RESET}"

    try:
        in_index = [a.lower() for a in args].index("in")
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


@command("get", ["takefrom"], "interaction", "Get an item from a container.\nUsage: get <item_name> from <container_name>")
def get_handler(args, context):
    world = context["world"]
    player = world.player
    if not player.is_alive:
        return f"{FORMAT_ERROR}You are dead. You cannot move.{FORMAT_RESET}"
    if not args or "from" not in [a.lower() for a in args]:
        return f"{FORMAT_ERROR}Usage: get <item_name> from <container_name>{FORMAT_RESET}"

    try:
        from_index = [a.lower() for a in args].index("from")
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
    else:
        return f"{FORMAT_ERROR}Could not get '{item_name}' from the {container.name}.{FORMAT_RESET}"


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
    if "on" in [a.lower() for a in args]:
         try:
              on_index = [a.lower() for a in args].index("on")
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
        if not target and target_name in ["self", "me", player.name.lower()]:
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
                    any(vt in npc.obj_id.lower() for vt in ["shop","merchant", "bartender"]) # Added bartender
        if is_vendor:
            vendor = npc
            break

    if not vendor:
        return f"{FORMAT_ERROR}There is no one here to sell junk to.{FORMAT_RESET}"

    items_to_sell = []
    total_value = 0

    # Iterate through a copy of inventory slots to allow removal
    slots_to_process = list(player.inventory.slots)
    for slot in slots_to_process:
        if slot.item and isinstance(slot.item, Junk):
            # Add item and its quantity to list
            items_to_sell.append({"item": slot.item, "quantity": slot.quantity})
            total_value += slot.item.value * slot.quantity

    if not items_to_sell:
        return f"You have no junk items to sell to {vendor.name}."

    # Confirm sale (optional, for now just sell)
    # print(f"DEBUG: Items to sell: {items_to_sell}") # Debug print
    # print(f"DEBUG: Total value: {total_value}")     # Debug print

    # Remove items from inventory and collect messages
    sell_messages = []
    items_actually_sold = 0
    value_actually_received = 0

    for item_info in items_to_sell:
        item_obj = item_info["item"]
        quantity_to_remove = item_info["quantity"]

        # Attempt to remove from inventory
        removed_item_type, actual_removed_count, remove_msg = player.inventory.remove_item(
            item_obj.obj_id, quantity_to_remove
        )

        # print(f"DEBUG: Tried removing {quantity_to_remove} of {item_obj.name} (ID: {item_obj.obj_id}). Actual removed: {actual_removed_count}") # Debug print

        if removed_item_type and actual_removed_count > 0:
             items_actually_sold += actual_removed_count
             value_actually_received += removed_item_type.value * actual_removed_count
             # Use the name from the removed item type
             sell_messages.append(f"- Sold {actual_removed_count} x {removed_item_type.name} for {removed_item_type.value * actual_removed_count} value.")
        else:
             # This shouldn't happen if we found it initially, but log if it does
             print(f"Warning: Failed to remove {item_obj.name} during sell junk operation: {remove_msg}")
             sell_messages.append(f"- {FORMAT_ERROR}Failed to sell {item_obj.name}.{FORMAT_RESET}")


    # Grant "currency" (for now, just increase a property or maybe add a 'Gold' item)
    # Let's add a Gold item for simplicity
    if value_actually_received > 0:
        # Try to create Gold Coin item
        gold_item = ItemFactory.create_item(
            item_type="Treasure",
            name="Gold Coin",
            description="A shiny gold coin.",
            value=1,
            weight=0.01,
            stackable=True,
            treasure_type="coin"
        )
        if gold_item:
            added_gold, add_msg = player.inventory.add_item(gold_item, value_actually_received)
            if not added_gold:
                 # Handle failure to add gold (e.g., inventory full) - maybe drop it?
                 world.add_item_to_room(world.current_region_id, world.current_room_id, gold_item)
                 sell_messages.append(f"{FORMAT_ERROR}Your inventory is full! Dropped {value_actually_received} gold instead.{FORMAT_RESET}")
            else:
                 sell_messages.append(f"\nReceived {value_actually_received} gold.")
        else:
             # Fallback if Gold Coin can't be created
             sell_messages.append(f"\n{FORMAT_ERROR}Error creating gold coin item!{FORMAT_RESET}")
             # Maybe add value to a player property instead?
             # player.update_property("gold", player.get_property("gold", 0) + value_actually_received)

    # Format final message
    final_message = f"You sell your junk to {vendor.name}:\n"
    final_message += "\n".join(sell_messages)

    return final_message
