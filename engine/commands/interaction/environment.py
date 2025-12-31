# engine/commands/interaction/environment.py
from engine.commands.command_system import command
from engine.config import FORMAT_ERROR, FORMAT_RESET
from engine.items.interactive import Interactive

@command("pull", ["push", "interact", "flip"], "interaction", "Interact with an object (lever, button, etc).\nUsage: pull <object>")
def interact_handler(args, context):
    world = context["world"]
    player = world.player
    if not args: return f"{FORMAT_ERROR}Interact with what?{FORMAT_RESET}"
    
    target_name = " ".join(args).lower()
    target = world.find_item_in_room(target_name)
    
    if not target: return f"{FORMAT_ERROR}You don't see '{target_name}' here.{FORMAT_RESET}"
    
    if isinstance(target, Interactive):
        return target.interact(player, world)
    else:
        return f"{FORMAT_ERROR}Nothing happens when you interact with the {target.name}.{FORMAT_RESET}"