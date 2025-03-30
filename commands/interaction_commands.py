"""
commands/interaction_commands.py
Interaction commands for the MUD game using the unified command system.
This combines commands from look, item, and NPC interactions.
"""
from commands.command_system import command
from core.config import FORMAT_TITLE, FORMAT_HIGHLIGHT, FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_SUCCESS, FORMAT_RESET

# Basic interaction commands
@command("look", aliases=["l"], category="interaction", 
         help_text="Look around the current room to see what's there.\n\nIn the future, you'll be able to 'look <object>' to examine specific things.")
def look_handler(args, context):
    """Handle the look command."""
    world = context["world"]
    
    # If no args, look at the room
    if not args:
        return world.look()
    
    # Looking at something specific
    target = " ".join(args)
    
    # Try to find a matching NPC first
    npcs = world.get_current_room_npcs()
    for npc in npcs:
        if target.lower() in npc.name.lower():
            return f"{FORMAT_TITLE}{npc.name}{FORMAT_RESET}\n\n{npc.get_description()}"
    
    # Then try to find a matching item in the room
    items = world.get_items_in_current_room()
    for item in items:
        if target.lower() in item.name.lower():
            return f"{FORMAT_TITLE}EXAMINE: {item.name}{FORMAT_RESET}\n\n{item.examine()}"
    
    # Then try to find a matching item in inventory
    for slot in world.player.inventory.slots:
        if slot.item and target.lower() in slot.item.name.lower():
            return f"{FORMAT_TITLE}EXAMINE: {slot.item.name}{FORMAT_RESET}\n\n{slot.item.examine()}"
    
    # No match found
    return f"{FORMAT_TITLE}You look at: {target}{FORMAT_RESET}\n\nYou don't see anything special."

@command("examine", aliases=["x", "exam"], category="interaction", 
         help_text="Examine something specific in more detail.\n\nUsage: examine <object>")
def examine_handler(args, context):
    """Handle the examine command."""
    # This is essentially the same as 'look' with a target
    if not args:
        return f"{FORMAT_ERROR}What do you want to examine?{FORMAT_RESET}"
    
    return look_handler(args, context)

# Item-related commands
@command("take", aliases=["get", "pickup"], category="interaction", 
         help_text="Pick up an item from the current room and add it to your inventory.\n\nUsage: take <item>")
def take_handler(args, context):
    """Handle the take command."""
    world = context["world"]
    
    if not args:
        return f"{FORMAT_ERROR}What do you want to take?{FORMAT_RESET}"
    
    # Get the item name from args
    item_name = " ".join(args).lower()
    
    # Try to find a matching item in the current room
    current_region_id = world.current_region_id
    current_room_id = world.current_room_id
    items = world.get_items_in_current_room()
    
    for item in items:
        if item_name in item.name.lower():
            # Found a matching item, try to add it to inventory
            success, message = world.player.inventory.add_item(item)
            
            if success:
                # Remove the item from the room
                world.remove_item_from_room(current_region_id, current_room_id, item.item_id)
                return f"{FORMAT_SUCCESS}You take the {item.name}.{FORMAT_RESET}\n\n{message}"
            else:
                return f"{FORMAT_ERROR}{message}{FORMAT_RESET}"
    
    return f"{FORMAT_ERROR}You don't see a {item_name} here.{FORMAT_RESET}"

@command("drop", aliases=["put"], category="interaction", 
         help_text="Drop an item from your inventory into the current room.\n\nUsage: drop <item>")
def drop_handler(args, context):
    """Handle the drop command."""
    world = context["world"]
    
    if not args:
        return f"{FORMAT_ERROR}What do you want to drop?{FORMAT_RESET}"
    
    # Get the item name from args
    item_name = " ".join(args).lower()
    
    # Try to find a matching item in the inventory
    for slot in world.player.inventory.slots:
        if slot.item and item_name in slot.item.name.lower():
            # Found a matching item, remove it from inventory
            item, quantity, message = world.player.inventory.remove_item(slot.item.item_id)
            
            if item:
                # Add the item to the current room
                world.add_item_to_room(world.current_region_id, world.current_room_id, item)
                return f"{FORMAT_SUCCESS}You drop the {item.name}.{FORMAT_RESET}"
            else:
                return f"{FORMAT_ERROR}{message}{FORMAT_RESET}"
    
    return f"{FORMAT_ERROR}You don't have a {item_name}.{FORMAT_RESET}"

@command("use", aliases=["activate", "drink", "eat"], category="interaction", 
         help_text="Use an item from your inventory.\n\nUsage: use <item>")
def use_handler(args, context):
    """Handle the use command."""
    world = context["world"]
    
    if not args:
        return f"{FORMAT_ERROR}What do you want to use?{FORMAT_RESET}"
    
    # Get the item name from args
    item_name = " ".join(args).lower()
    
    # Try to find a matching item in the inventory
    for slot in world.player.inventory.slots:
        if slot.item and item_name in slot.item.name.lower():
            # Found a matching item, use it
            result = slot.item.use(world.player)
            
            # If the item is fully used up, remove it from inventory
            if hasattr(slot.item, "properties") and "uses" in slot.item.properties:
                if slot.item.properties["uses"] <= 0:
                    world.player.inventory.remove_item(slot.item.item_id)
            
            return f"{FORMAT_HIGHLIGHT}{result}{FORMAT_RESET}"
    
    return f"{FORMAT_ERROR}You don't have a {item_name} to use.{FORMAT_RESET}"

# NPC interaction commands
@command("talk", aliases=["speak", "chat", "ask"], category="interaction", 
         help_text="Talk to an NPC in the current room.\n\nUsage: talk <npc> [topic]\n\nIf a topic is provided, you'll ask the NPC about that specific topic.")
def talk_handler(args, context):
    """Handle the talk command."""
    world = context["world"]
    
    if not args:
        return f"{FORMAT_ERROR}Who do you want to talk to?{FORMAT_RESET}"
    
    # Get the NPC name from the first argument
    npc_name = args[0].lower()
    
    # Get the topic from remaining arguments, if any
    topic = " ".join(args[1:]) if len(args) > 1 else None
    
    # Get NPCs in the current room
    npcs = world.get_current_room_npcs()
    
    for npc in npcs:
        if npc_name in npc.name.lower():
            # Found a matching NPC, talk to them
            response = npc.talk(topic)
            
            # Format the response nicely
            npc_title = f"{FORMAT_TITLE}CONVERSATION WITH {npc.name.upper()}{FORMAT_RESET}\n\n"
            
            if topic:
                return f"{npc_title}You ask {npc.name} about {topic}.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}"
            else:
                return f"{npc_title}You greet {npc.name}.\n\n{FORMAT_HIGHLIGHT}{response}{FORMAT_RESET}"
    
    return f"{FORMAT_ERROR}There's no {npc_name} here to talk to.{FORMAT_RESET}"

@command("follow", aliases=[], category="interaction", 
         help_text="Follow an NPC as they move between rooms.\n\nUsage: follow <npc>")
def follow_handler(args, context):
    """Handle the follow command."""
    world = context["world"]
    
    if not args:
        return f"{FORMAT_ERROR}Who do you want to follow?{FORMAT_RESET}"
    
    # Get the NPC name from args
    npc_name = " ".join(args).lower()
    
    # Get NPCs in the current room
    npcs = world.get_current_room_npcs()
    
    for npc in npcs:
        if npc_name in npc.name.lower():
            # This is a stub for now - actual implementation would require more state tracking
            return f"{FORMAT_HIGHLIGHT}You start following {npc.name}. (This feature is not fully implemented yet.){FORMAT_RESET}"
    
    return f"{FORMAT_ERROR}There's no {npc_name} here to follow.{FORMAT_RESET}"

@command("trade", aliases=["shop", "buy", "sell"], category="interaction", 
         help_text="Trade with a shopkeeper NPC.\n\nUsage: trade <npc>")
def trade_handler(args, context):
    """Handle the trade command."""
    world = context["world"]
    
    if not args:
        return f"{FORMAT_ERROR}Who do you want to trade with?{FORMAT_RESET}"
    
    # Get the NPC name from args
    npc_name = " ".join(args).lower()
    
    # Get NPCs in the current room
    npcs = world.get_current_room_npcs()
    
    for npc in npcs:
        if npc_name in npc.name.lower():
            # Check if NPC is a shopkeeper
            if hasattr(npc, "dialog") and "buy" in npc.dialog:
                return f"{FORMAT_HIGHLIGHT}{npc.name} says: \"{npc.dialog.get('buy')}\"\n\n(Trading is not fully implemented yet.){FORMAT_RESET}"
            else:
                return f"{FORMAT_ERROR}{npc.name} doesn't seem interested in trading.{FORMAT_RESET}"
    
    return f"{FORMAT_ERROR}There's no {npc_name} here to trade with.{FORMAT_RESET}"