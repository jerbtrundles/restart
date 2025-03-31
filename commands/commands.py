"""
commands/commands.py
Unified command system for the MUD game.
"""
from commands.command_system import command
from core.config import DEFAULT_WORLD_FILE, FORMAT_TITLE, FORMAT_HIGHLIGHT, FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET

DIRECTIONS = [
    {"name": "north", "aliases": ["n"], "description": "Move to the north if an exit exists."},
    {"name": "south", "aliases": ["s"], "description": "Move to the south if an exit exists."},
    {"name": "east", "aliases": ["e"], "description": "Move to the east if an exit exists."},
    {"name": "west", "aliases": ["w"], "description": "Move to the west if an exit exists."},
    {"name": "northeast", "aliases": ["ne"], "description": "Move to the northeast if an exit exists."},
    {"name": "northwest", "aliases": ["nw"], "description": "Move to the northwest if an exit exists."},
    {"name": "southeast", "aliases": ["se"], "description": "Move to the southeast if an exit exists."},
    {"name": "southwest", "aliases": ["sw"], "description": "Move to the southwest if an exit exists."},
    {"name": "up", "aliases": ["u"], "description": "Move upwards if an exit exists."},
    {"name": "down", "aliases": ["d"], "description": "Move downwards if an exit exists."},
    {"name": "in", "aliases": ["enter", "inside"], "description": "Enter a location if an entrance exists."},
    {"name": "out", "aliases": ["exit", "outside"], "description": "Exit a location if an exit exists."}
]

"""
commands/consolidated_movement_commands.py
Consolidated movement commands for the MUD game.
This reduces code duplication by generating similar commands programmatically.
"""
from commands.command_system import command, registered_commands

# Direction mappings for movement commands
DIRECTIONS = [
    {"name": "north", "aliases": ["n"], "description": "Move to the north if an exit exists."},
    {"name": "south", "aliases": ["s"], "description": "Move to the south if an exit exists."},
    {"name": "east", "aliases": ["e"], "description": "Move to the east if an exit exists."},
    {"name": "west", "aliases": ["w"], "description": "Move to the west if an exit exists."},
    {"name": "northeast", "aliases": ["ne"], "description": "Move to the northeast if an exit exists."},
    {"name": "northwest", "aliases": ["nw"], "description": "Move to the northwest if an exit exists."},
    {"name": "southeast", "aliases": ["se"], "description": "Move to the southeast if an exit exists."},
    {"name": "southwest", "aliases": ["sw"], "description": "Move to the southwest if an exit exists."},
    {"name": "up", "aliases": ["u"], "description": "Move upwards if an exit exists."},
    {"name": "down", "aliases": ["d"], "description": "Move downwards if an exit exists."},
    {"name": "in", "aliases": ["enter", "inside"], "description": "Enter a location if an entrance exists."},
    {"name": "out", "aliases": ["exit", "outside"], "description": "Exit a location if an exit exists."}
]

def register_movement_commands():
    registered = {}
    for direction_info in DIRECTIONS:
        direction_name = direction_info["name"]
        direction_aliases = direction_info["aliases"]
        direction_description = direction_info["description"]
        if direction_name in registered_commands:
            continue
        def create_direction_handler(dir_name):
            def handler(args, context):
                return context["world"].change_room(dir_name)
            return handler
        handler = create_direction_handler(direction_name)
        decorated_handler = command(direction_name, direction_aliases, "movement", direction_description)(handler)
        registered[direction_name] = decorated_handler
    return registered

@command("go", ["move", "walk"], "movement", "Move in the specified direction.\n\nUsage: go <direction>\n\nExample: 'go north' or 'go in'")
def go_handler(args, context):
    if not args:
        return "Go where?"
    direction = args[0].lower()
    return context["world"].change_room(direction)

@command("help", ["h", "?"], "system", 
              "Display help information about available commands.\n\nUsage: help [command]\n\n"
              "If no command is specified, shows a list of all commands.")
def help_handler(args, context):
    command_processor = context["command_processor"]
    if args:
        return command_processor.get_command_help(args[0])
    else:
        return command_processor.get_help_text()

@command("quit", ["q", "exit"], "system", "Exit the game. Your progress will not be automatically saved.")
def quit_handler(args, context):
    if "game" in context:
        context["game"].quit_game()
    return f"{FORMAT_HIGHLIGHT}Goodbye!{FORMAT_RESET}"

@command("save", [], "system", "Save the current game state to a file.\n\nUsage: save [filename]\n\nIf no filename is provided, saves to the default world file.")
def save_handler(args, context):
    world = context["world"]
    if args:
        filename = args[0] + ".json" if not args[0].endswith(".json") else args[0]
        if world.save_to_json(filename):
            return f"{FORMAT_SUCCESS}World saved to {filename}{FORMAT_RESET}"
        else:
            return f"{FORMAT_ERROR}Error saving world to {filename}{FORMAT_RESET}"
    else:
        if world.save_to_json(DEFAULT_WORLD_FILE):
            return f"{FORMAT_SUCCESS}World saved to {DEFAULT_WORLD_FILE}{FORMAT_RESET}"
        else:
            return f"{FORMAT_ERROR}Error saving world{FORMAT_RESET}"

@command("load", [], "system", "Load a game state from a file.\n\nUsage: load [filename]\n\nIf no filename is provided, loads from the default world file.")
def load_handler(args, context):
    world = context["world"]
    if args:
        filename = args[0] + ".json" if not args[0].endswith(".json") else args[0]
        if world.load_from_json(filename):
            return f"{FORMAT_SUCCESS}World loaded from {filename}{FORMAT_RESET}\n\n{world.look()}"
        else:
            return f"{FORMAT_ERROR}Error loading world from {filename}{FORMAT_RESET}"
    else:
        if world.load_from_json(DEFAULT_WORLD_FILE):
            return f"{FORMAT_SUCCESS}World loaded from {DEFAULT_WORLD_FILE}{FORMAT_RESET}\n\n{world.look()}"
        else:
            return f"{FORMAT_ERROR}Error loading world or file not found{FORMAT_RESET}"

@command("inventory", ["i", "inv"], "inventory", "Show the items you are carrying.")
def inventory_handler(args, context):
    world = context["world"]
    inventory_text = f"{FORMAT_TITLE}INVENTORY{FORMAT_RESET}\n\n"
    inventory_text += world.player.inventory.list_items()
    return inventory_text

@command("status", ["stat", "st"], "inventory", "Display your character's health, stats, and other information.")
def status_handler(args, context):
    world = context["world"]
    status = world.get_player_status()
    return f"{FORMAT_TITLE}CHARACTER STATUS{FORMAT_RESET}\n\n{status}"

@command("look", ["l"], "interaction", "Look around the current room to see what's there.\n\nIn the future, you'll be able to 'look <object>' to examine specific things.")
def look_handler(args, context):
    world = context["world"]
    if not args:
        return world.look()
    target = " ".join(args)
    npcs = world.get_current_room_npcs()
    for npc in npcs:
        if target.lower() in npc.name.lower():
            return f"{FORMAT_TITLE}{npc.name}{FORMAT_RESET}\n\n{npc.get_description()}"
    items = world.get_items_in_current_room()
    for item in items:
        if target.lower() in item.name.lower():
            return f"{FORMAT_TITLE}EXAMINE: {item.name}{FORMAT_RESET}\n\n{item.examine()}"
    for slot in world.player.inventory.slots:
        if slot.item and target.lower() in slot.item.name.lower():
            return f"{FORMAT_TITLE}EXAMINE: {slot.item.name}{FORMAT_RESET}\n\n{slot.item.examine()}"
    return f"{FORMAT_TITLE}You look at: {target}{FORMAT_RESET}\n\nYou don't see anything special."

@command("examine", ["x", "exam"], "interaction", "Examine something specific in more detail.\n\nUsage: examine <object>")
def examine_handler(args, context):
    if not args:
        return f"{FORMAT_ERROR}What do you want to examine?{FORMAT_RESET}"
    return look_handler(args, context)

# Item-related commands
@command("take", ["get", "pickup"], "interaction", "Pick up an item from the current room and add it to your inventory.\n\nUsage: take <item>")
def take_handler(args, context):
    world = context["world"]
    if not args:
        return f"{FORMAT_ERROR}What do you want to take?{FORMAT_RESET}"
    item_name = " ".join(args).lower()
    current_region_id = world.current_region_id
    current_room_id = world.current_room_id
    items = world.get_items_in_current_room()
    for item in items:
        if item_name in item.name.lower():
            success, message = world.player.inventory.add_item(item)
            if success:
                world.remove_item_from_room(current_region_id, current_room_id, item.obj_id)
                return f"{FORMAT_SUCCESS}You take the {item.name}.{FORMAT_RESET}\n\n{message}"
            else:
                return f"{FORMAT_ERROR}{message}{FORMAT_RESET}"
    return f"{FORMAT_ERROR}You don't see a {item_name} here.{FORMAT_RESET}"

@command("drop", ["put"], "interaction", "Drop an item from your inventory into the current room.\n\nUsage: drop <item>")
def drop_handler(args, context):
    world = context["world"]
    if not args:
        return f"{FORMAT_ERROR}What do you want to drop?{FORMAT_RESET}"
    item_name = " ".join(args).lower()
    for slot in world.player.inventory.slots:
        if slot.item and item_name in slot.item.name.lower():
            item, quantity, message = world.player.inventory.remove_item(slot.item.obj_id)
            if item:
                world.add_item_to_room(world.current_region_id, world.current_room_id, item)
                return f"{FORMAT_SUCCESS}You drop the {item.name}.{FORMAT_RESET}"
            else:
                return f"{FORMAT_ERROR}{message}{FORMAT_RESET}"
    return f"{FORMAT_ERROR}You don't have a {item_name}.{FORMAT_RESET}"

@command("use", ["activate", "drink", "eat"], "interaction", "Use an item from your inventory.\n\nUsage: use <item>")
def use_handler(args, context):
    world = context["world"]
    if not args:
        return f"{FORMAT_ERROR}What do you want to use?{FORMAT_RESET}"
    item_name = " ".join(args).lower()
    for slot in world.player.inventory.slots:
        if slot.item and item_name in slot.item.name.lower():
            result = slot.item.use(world.player)
            if hasattr(slot.item, "properties") and "uses" in slot.item.properties:
                if slot.item.properties["uses"] <= 0:
                    world.player.inventory.remove_item(slot.item.obj_id)
            return f"{FORMAT_HIGHLIGHT}{result}{FORMAT_RESET}"
    return f"{FORMAT_ERROR}You don't have a {item_name} to use.{FORMAT_RESET}"

@command("talk", ["speak", "chat", "ask"], "interaction", "Talk to an NPC in the current room.\n\nUsage: talk <npc> [topic]\n\nIf a topic is provided, you'll ask the NPC about that specific topic.")
def talk_handler(args, context):
    world = context["world"]
    if not args:
        return f"{FORMAT_ERROR}Who do you want to talk to?{FORMAT_RESET}"
    npc_name = args[0].lower()
    topic = " ".join(args[1:]) if len(args) > 1 else None
    npcs = world.get_current_room_npcs()
    for npc in npcs:
        if npc_name in npc.name.lower():
            response = npc.talk(topic)
            npc_title = f"{FORMAT_TITLE}CONVERSATION WITH {npc.name.upper()}{FORMAT_RESET}\n\n"
            if topic:
                return f"{npc_title}You ask {npc.name} about {topic}.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}"
            else:
                return f"{npc_title}You greet {npc.name}.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}"
    return f"{FORMAT_ERROR}There's no {npc_name} here to talk to.{FORMAT_RESET}"

@command("follow", [], "interaction", "Follow an NPC as they move between rooms.\n\nUsage: follow <npc>")
def follow_handler(args, context):
    world = context["world"]
    if not args:
        return f"{FORMAT_ERROR}Who do you want to follow?{FORMAT_RESET}"
    npc_name = " ".join(args).lower()
    npcs = world.get_current_room_npcs()
    for npc in npcs:
        if npc_name in npc.name.lower():
            return f"{FORMAT_HIGHLIGHT}You start following {npc.name}. (This feature is not fully implemented yet.){FORMAT_RESET}"
    return f"{FORMAT_ERROR}There's no {npc_name} here to follow.{FORMAT_RESET}"

@command("trade", ["shop", "buy", "sell"], "interaction", "Trade with a shopkeeper NPC.\n\nUsage: trade <npc>")
def trade_handler(args, context):
    world = context["world"]
    if not args:
        return f"{FORMAT_ERROR}Who do you want to trade with?{FORMAT_RESET}"
    npc_name = " ".join(args).lower()
    npcs = world.get_current_room_npcs()
    for npc in npcs:
        if npc_name in npc.name.lower():
            if hasattr(npc, "dialog") and "buy" in npc.dialog:
                return f"{FORMAT_HIGHLIGHT}{npc.name} says: \"{npc.dialog.get('buy')}\"\n\n(Trading is not fully implemented yet.){FORMAT_RESET}"
            else:
                return f"{FORMAT_ERROR}{npc.name} doesn't seem interested in trading.{FORMAT_RESET}"
    return f"{FORMAT_ERROR}There's no {npc_name} here to trade with.{FORMAT_RESET}"

@command("path", ["navigate", "goto"], "movement", "Find a path to a room.\n\nUsage: path <room_id> [region_id]")
def path_handler(args, context):
    if not args:
        return "Specify a destination room."
    
    world = context["world"]
    target_room_id = args[0]
    target_region_id = args[1] if len(args) > 1 else world.current_region_id
    
    path = world.find_path(
                    world.current_region_id, 
                    world.current_room_id,
                    target_region_id, 
                    target_room_id)
    
    if path:
        return f"Path to {target_region_id}:{target_room_id}: {' → '.join(path)}"
    else:
        return f"No path found to {target_region_id}:{target_room_id}."