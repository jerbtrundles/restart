# engine/commands/gathering.py
from engine.commands.command_system import command
from engine.config import FORMAT_ERROR, FORMAT_RESET
from engine.items.resource_node import ResourceNode

@command("gather", ["mine", "harvest", "chop"], "interaction", "Gather resources from a node.\nUsage: gather <target>")
def gather_handler(args, context):
    world = context["world"]
    player = world.player
    if not args: return f"{FORMAT_ERROR}Gather from what?{FORMAT_RESET}"
    
    target_name = " ".join(args).lower()
    target = world.find_item_in_room(target_name)
    
    if not target: return f"{FORMAT_ERROR}You don't see '{target_name}' here.{FORMAT_RESET}"
    
    if isinstance(target, ResourceNode):
        return target.gather(player, world)
    else:
        return f"{FORMAT_ERROR}You cannot gather from {target.name}.{FORMAT_RESET}"