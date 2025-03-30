"""
commands/movement_commands.py
Movement commands for the MUD game using the unified command system.
"""
from commands.command_system import command

@command("north", aliases=["n"], category="movement", 
         help_text="Move to the north if an exit exists.")
def north_handler(args, context):
    """Handle movement to the north."""
    return context["world"].change_room("north")

@command("south", aliases=["s"], category="movement", 
         help_text="Move to the south if an exit exists.")
def south_handler(args, context):
    """Handle movement to the south."""
    return context["world"].change_room("south")

@command("east", aliases=["e"], category="movement", 
         help_text="Move to the east if an exit exists.")
def east_handler(args, context):
    """Handle movement to the east."""
    return context["world"].change_room("east")

@command("west", aliases=["w"], category="movement", 
         help_text="Move to the west if an exit exists.")
def west_handler(args, context):
    """Handle movement to the west."""
    return context["world"].change_room("west")

@command("northeast", aliases=["ne"], category="movement", 
         help_text="Move to the northeast if an exit exists.")
def northeast_handler(args, context):
    """Handle movement to the northeast."""
    return context["world"].change_room("northeast")

@command("northwest", aliases=["nw"], category="movement", 
         help_text="Move to the northwest if an exit exists.")
def northwest_handler(args, context):
    """Handle movement to the northwest."""
    return context["world"].change_room("northwest")

@command("southeast", aliases=["se"], category="movement", 
         help_text="Move to the southeast if an exit exists.")
def southeast_handler(args, context):
    """Handle movement to the southeast."""
    return context["world"].change_room("southeast")

@command("southwest", aliases=["sw"], category="movement", 
         help_text="Move to the southwest if an exit exists.")
def southwest_handler(args, context):
    """Handle movement to the southwest."""
    return context["world"].change_room("southwest")

@command("up", aliases=["u"], category="movement", 
         help_text="Move upwards if an exit exists.")
def up_handler(args, context):
    """Handle movement upwards."""
    return context["world"].change_room("up")

@command("down", aliases=["d"], category="movement", 
         help_text="Move downwards if an exit exists.")
def down_handler(args, context):
    """Handle movement downwards."""
    return context["world"].change_room("down")

@command("in", aliases=["enter", "inside"], category="movement", 
         help_text="Enter a location if an entrance exists.")
def in_handler(args, context):
    """Handle movement inwards."""
    return context["world"].change_room("in")

@command("out", aliases=["exit", "outside"], category="movement", 
         help_text="Exit a location if an exit exists.")
def out_handler(args, context):
    """Handle movement outwards."""
    return context["world"].change_room("out")

@command("go", aliases=["move", "walk"], category="movement", 
         help_text="Move in the specified direction.\n\nUsage: go <direction>\n\nExample: 'go north' or 'go in'")
def go_handler(args, context):
    """Handle the 'go' command for movement in any direction."""
    if not args:
        return "Go where?"
    
    direction = args[0].lower()
    return context["world"].change_room(direction)