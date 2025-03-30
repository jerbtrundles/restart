"""
main.py
Main entry point for the MUD game.
"""
import argparse
from core.game_manager import GameManager
from core.config import DEFAULT_WORLD_FILE


def main():
    """
    Main function to start the game.
    """
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Pygame MUD Game')
    parser.add_argument('--world', '-w', type=str, default=DEFAULT_WORLD_FILE,
                        help=f'Path to world JSON file (default: {DEFAULT_WORLD_FILE})')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Create and run the game
    game = GameManager(args.world)
    game.run()


if __name__ == "__main__":
    main()

"""
player.py
Enhanced Player module for the MUD game.
"""
from typing import List, Dict, Optional, Any
from items.inventory import Inventory


class Player:
    """
    Represents the player character in the game.
    """
    def __init__(self, name: str):
        """
        Initialize a player.
        
        Args:
            name: The player's name.
        """
        self.name = name
        self.inventory = Inventory(max_slots=20, max_weight=100.0)
        self.health = 100
        self.max_health = 100
        self.stats = {
            "strength": 10,
            "dexterity": 10,
            "intelligence": 10
        }
        self.level = 1
        self.experience = 0
        self.experience_to_level = 100
        self.skills = {}  # Skill name to proficiency level mapping
        self.effects = []  # Temporary effects on the player
        self.quest_log = {}  # Quest ID to progress mapping
    
    def get_status(self) -> str:
        """
        Returns a string with the player's current status.
        
        Returns:
            A formatted status string.
        """
        status = f"Name: {self.name}\n"
        status += f"Level: {self.level} (XP: {self.experience}/{self.experience_to_level})\n"
        status += f"Health: {self.health}/{self.max_health}\n"
        status += f"Stats: STR {self.stats['strength']}, "
        status += f"DEX {self.stats['dexterity']}, "
        status += f"INT {self.stats['intelligence']}\n"
        
        # Add effect information if there are any
        if self.effects:
            status += "\nActive Effects:\n"
            for effect in self.effects:
                status += f"- {effect['name']}: {effect['description']}\n"
        
        # Skills information if the player has any skills
        if self.skills:
            status += "\nSkills:\n"
            for skill, level in self.skills.items():
                status += f"- {skill}: {level}\n"
        
        return status
    
    def gain_experience(self, amount: int) -> bool:
        """
        Award experience points to the player and check for level up.
        
        Args:
            amount: The amount of experience to gain.
            
        Returns:
            True if the player leveled up, False otherwise.
        """
        self.experience += amount
        
        if self.experience >= self.experience_to_level:
            self.level_up()
            return True
            
        return False
    
    def level_up(self) -> None:
        """Level up the player, increasing stats and resetting experience."""
        self.level += 1
        self.experience -= self.experience_to_level
        self.experience_to_level = int(self.experience_to_level * 1.5)  # Increase XP required for next level
        
        # Increase stats
        self.stats["strength"] += 1
        self.stats["dexterity"] += 1
        self.stats["intelligence"] += 1
        
        # Increase max health
        old_max_health = self.max_health
        self.max_health = int(self.max_health * 1.1)  # 10% health increase per level
        self.health += (self.max_health - old_max_health)  # Heal by the amount of max health increase
    
    def add_effect(self, name: str, description: str, duration: int, 
                  stat_modifiers: Dict[str, int] = None) -> None:
        """
        Add a temporary effect to the player.
        
        Args:
            name: The name of the effect.
            description: A description of what the effect does.
            duration: How many turns the effect lasts.
            stat_modifiers: Modifications to player stats while the effect is active.
        """
        self.effects.append({
            "name": name,
            "description": description,
            "duration": duration,
            "stat_modifiers": stat_modifiers or {}
        })
        
        # Apply stat modifiers
        if stat_modifiers:
            for stat, modifier in stat_modifiers.items():
                if stat in self.stats:
                    self.stats[stat] += modifier
    
    def update_effects(self) -> List[str]:
        """
        Update all active effects, reducing their duration and removing expired ones.
        
        Returns:
            A list of messages about effects that have expired.
        """
        messages = []
        expired_effects = []
        
        for effect in self.effects:
            effect["duration"] -= 1
            
            if effect["duration"] <= 0:
                expired_effects.append(effect)
                messages.append(f"The {effect['name']} effect has worn off.")
        
        # Remove expired effects and their stat modifiers
        for effect in expired_effects:
            self.effects.remove(effect)
            
            # Remove stat modifiers
            if "stat_modifiers" in effect:
                for stat, modifier in effect["stat_modifiers"].items():
                    if stat in self.stats:
                        self.stats[stat] -= modifier
        
        return messages
    
    def add_skill(self, skill_name: str, level: int = 1) -> None:
        """
        Add a new skill or increase an existing skill's level.
        
        Args:
            skill_name: The name of the skill.
            level: The level to set or add.
        """
        if skill_name in self.skills:
            self.skills[skill_name] += level
        else:
            self.skills[skill_name] = level
    
    def get_skill_level(self, skill_name: str) -> int:
        """
        Get the player's level in a specific skill.
        
        Args:
            skill_name: The name of the skill.
            
        Returns:
            The skill level, or 0 if the player doesn't have the skill.
        """
        return self.skills.get(skill_name, 0)
    
    def update_quest(self, quest_id: str, progress: Any) -> None:
        """
        Update the progress of a quest.
        
        Args:
            quest_id: The ID of the quest.
            progress: The new progress value.
        """
        self.quest_log[quest_id] = progress
    
    def get_quest_progress(self, quest_id: str) -> Optional[Any]:
        """
        Get the progress of a quest.
        
        Args:
            quest_id: The ID of the quest.
            
        Returns:
            The quest progress, or None if the quest is not in the log.
        """
        return self.quest_log.get(quest_id)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the player to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the player.
        """
        return {
            "name": self.name,
            "inventory": self.inventory.to_dict(),
            "health": self.health,
            "max_health": self.max_health,
            "stats": self.stats,
            "level": self.level,
            "experience": self.experience,
            "experience_to_level": self.experience_to_level,
            "skills": self.skills,
            "effects": self.effects,
            "quest_log": self.quest_log
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Player':
        """
        Create a player from a dictionary.
        
        Args:
            data: The dictionary containing player data.
            
        Returns:
            A Player instance.
        """
        player = cls(data["name"])
        
        player.health = data.get("health", 100)
        player.max_health = data.get("max_health", 100)
        player.stats = data.get("stats", {"strength": 10, "dexterity": 10, "intelligence": 10})
        player.level = data.get("level", 1)
        player.experience = data.get("experience", 0)
        player.experience_to_level = data.get("experience_to_level", 100)
        player.skills = data.get("skills", {})
        player.effects = data.get("effects", [])
        player.quest_log = data.get("quest_log", {})
        
        # Load inventory if present
        if "inventory" in data:
            player.inventory = Inventory.from_dict(data["inventory"])
        
        return player

"""
commands/command_system.py
Unified command system for the MUD game.
Consolidates different command approaches into a single system.
"""
from typing import Callable, List, Dict, Any, Optional, Set
from functools import wraps
import inspect

# Dictionary to store all registered commands
registered_commands: Dict[str, Dict[str, Any]] = {}
command_categories: Dict[str, List[Dict[str, Any]]] = {
    "movement": [],
    "interaction": [],
    "inventory": [],
    "combat": [],
    "system": [],
    "other": []
}

# Direction aliases for movement commands
direction_aliases = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest",
    "u": "up", "d": "down"
}

def command(name: str, aliases: List[str] = None, category: str = "other", 
           help_text: str = "No help available.", plugin_id: str = None):
    """
    Decorator for registering game commands.
    
    Args:
        name: The primary name of the command.
        aliases: Alternative names for the command.
        category: Category to group the command under.
        help_text: Description of the command for help system.
        plugin_id: The ID of the plugin that registers this command (if any).
        
    Returns:
        Decorated function.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
            
        # Store command info in the function
        wrapper._command_info = {
            "name": name,
            "aliases": aliases or [],
            "category": category,
            "help_text": help_text,
            "plugin_id": plugin_id
        }
        
        # Register the command
        cmd_data = {
            "name": name,
            "aliases": aliases or [],
            "handler": wrapper,
            "help_text": help_text,
            "category": category,
            "plugin_id": plugin_id
        }
        
        # Store in main commands dictionary by name
        registered_commands[name] = cmd_data
        
        # Also store by each alias
        for alias in aliases or []:
            registered_commands[alias] = cmd_data
            
        # Add to appropriate category
        if category in command_categories:
            command_categories[category].append(cmd_data)
        else:
            command_categories["other"].append(cmd_data)
        
        return wrapper
    return decorator

def get_registered_commands() -> Dict[str, Dict[str, Any]]:
    """
    Get all registered commands.
    
    Returns:
        Dictionary of command name to command data.
    """
    return registered_commands

def get_command_categories() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get commands organized by category.
    
    Returns:
        Dictionary of category name to list of commands.
    """
    return command_categories

def unregister_command(name: str) -> bool:
    """
    Unregister a command by name.
    
    Args:
        name: The name of the command to unregister.
        
    Returns:
        True if the command was unregistered, False otherwise.
    """
    if name not in registered_commands:
        return False
        
    cmd_data = registered_commands[name]
    cmd_name = cmd_data["name"]
    cmd_aliases = cmd_data["aliases"]
    cmd_category = cmd_data["category"]
    
    # Remove from main dictionary
    if cmd_name in registered_commands:
        registered_commands.pop(cmd_name)
    
    # Remove aliases
    for alias in cmd_aliases:
        if alias in registered_commands:
            registered_commands.pop(alias)
    
    # Remove from category
    if cmd_category in command_categories:
        command_categories[cmd_category] = [c for c in command_categories[cmd_category] 
                                          if c["name"] != cmd_name]
    
    return True

def unregister_plugin_commands(plugin_id: str) -> int:
    """
    Unregister all commands for a plugin.
    
    Args:
        plugin_id: The ID of the plugin.
        
    Returns:
        Number of commands unregistered.
    """
    if not plugin_id:
        return 0
        
    # Find all commands for this plugin
    plugin_commands = [cmd_name for cmd_name, cmd_data in registered_commands.items()
                     if cmd_data.get("plugin_id") == plugin_id and cmd_data["name"] == cmd_name]
    
    # Unregister each command
    count = 0
    for cmd_name in plugin_commands:
        if unregister_command(cmd_name):
            count += 1
    
    return count

class CommandProcessor:
    """Processes user input and dispatches commands to appropriate handlers."""
    
    def __init__(self):
        """Initialize the command processor."""
        # We don't need to store commands locally anymore since they're in the global registry
        pass
    
    def process_input(self, text: str, context: Any = None) -> str:
        """
        Process user input and execute the corresponding command.
        
        Args:
            text: The raw user input.
            context: Any context object needed by command handlers.
            
        Returns:
            The response text from the command handler.
        """
        text = text.strip().lower()
        
        if not text:
            return ""
        
        parts = text.split()
        command_word = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        # Check if it's a movement command (special case)
        if command_word in direction_aliases:
            command_word = direction_aliases[command_word]
        
        # Look for matching command
        if command_word in registered_commands:
            cmd = registered_commands[command_word]
            return cmd["handler"](args, context)
        
        # No matching command found
        return f"Unknown command: {command_word}"
    
    def get_help_text(self) -> str:
        """Generate help text for all registered commands."""
        from core.config import FORMAT_TITLE, FORMAT_CATEGORY, FORMAT_RESET
        
        help_text = f"{FORMAT_TITLE}AVAILABLE COMMANDS{FORMAT_RESET}\n\n"
        
        # List commands by category
        for category, commands in command_categories.items():
            if not commands:
                continue
                
            # Format category names
            category_title = category.capitalize()
            help_text += f"{FORMAT_CATEGORY}{category_title}{FORMAT_RESET}\n"
            
            # Group identical commands (those with the same handler)
            unique_commands = {}
            for cmd in commands:
                handler_id = id(cmd["handler"])
                if handler_id not in unique_commands:
                    unique_commands[handler_id] = cmd
            
            # Format the commands in this category
            for cmd in sorted(unique_commands.values(), key=lambda c: c["name"]):
                aliases = f" ({', '.join(cmd['aliases'])})" if cmd['aliases'] else ""
                help_text += f"  {cmd['name']}{aliases}\n"
            
            help_text += "\n"
        
        help_text += f"{FORMAT_TITLE}HELP SYSTEM{FORMAT_RESET}\n\n"
        help_text += "Use 'help <command>' for detailed information about a specific command.\n"
        help_text += "Example: 'help look' or 'help north'\n\n"
        
        help_text += f"{FORMAT_TITLE}NAVIGATION{FORMAT_RESET}\n\n"
        help_text += "- Use mouse wheel to scroll text\n"
        help_text += "- Use Page Up/Down keys for faster scrolling\n"
        help_text += "- Use Up/Down arrow keys to navigate command history\n"
        
        return help_text
    
    def get_command_help(self, command_name: str) -> str:
        """Get detailed help for a specific command."""
        from core.config import FORMAT_TITLE, FORMAT_CATEGORY, FORMAT_RESET, FORMAT_HIGHLIGHT
        
        # First, normalize command name using direction aliases
        if command_name in direction_aliases:
            command_name = direction_aliases[command_name]
        
        if command_name in registered_commands:
            cmd = registered_commands[command_name]
            
            # Find the category
            category = cmd["category"].capitalize()
            
            # Format the help text
            help_text = f"{FORMAT_TITLE}COMMAND: {cmd['name'].upper()}{FORMAT_RESET}\n\n"
            help_text += f"{FORMAT_CATEGORY}Category:{FORMAT_RESET} {category}\n"
            
            if cmd['aliases']:
                help_text += f"{FORMAT_CATEGORY}Aliases:{FORMAT_RESET} {', '.join(cmd['aliases'])}\n"
            
            help_text += f"\n{cmd['help_text']}\n"
            
            # Show examples if it's a complex command
            if cmd['name'] in ["save", "load", "help"]:
                help_text += f"\n{FORMAT_CATEGORY}Examples:{FORMAT_RESET}\n"
                if cmd['name'] == "save":
                    help_text += "  save           (saves to default world file)\n"
                    help_text += "  save mygame    (saves to mygame.json)\n"
                elif cmd['name'] == "load":
                    help_text += "  load           (loads from default world file)\n"
                    help_text += "  load mygame    (loads from mygame.json)\n"
                elif cmd['name'] == "help":
                    help_text += "  help           (shows command list)\n"
                    help_text += "  help look      (shows details about the look command)\n"
            
            return help_text
        
        # No matching command found
        return f"{FORMAT_HIGHLIGHT}No help available for '{command_name}'{FORMAT_RESET}\n\nType 'help' to see a list of all available commands."
    
    def get_command_suggestions(self, partial_command: str) -> List[str]:
        """
        Get a list of commands that start with the given partial command.
        Useful for tab completion.
        
        Args:
            partial_command: The partial command to match.
            
        Returns:
            A list of matching command names and aliases.
        """
        partial = partial_command.lower()
        suggestions = []
        
        # Check command names and aliases
        for cmd_name, cmd_data in registered_commands.items():
            if cmd_name.startswith(partial):
                # Only add each command once
                if cmd_name not in suggestions:
                    suggestions.append(cmd_name)
        
        # Also check direction aliases
        for alias, direction in direction_aliases.items():
            if alias.startswith(partial):
                suggestions.append(alias)
        
        return sorted(suggestions)

def register_command_module(module):
    """
    Register all commands from a module.
    
    Args:
        module: The module containing decorated command functions.
    """
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if callable(attr) and hasattr(attr, '_command_info'):
            # Command is automatically registered via decorator,
            # so we don't need to do anything here
            pass

def create_default_command_processor() -> CommandProcessor:
    """
    Create and configure a CommandProcessor with default commands.
    
    Returns:
        A configured CommandProcessor instance.
    """
    processor = CommandProcessor()
    return processor

"""
commands/core_commands.py
Core commands for the MUD game using the unified command system.
This combines commands from system, inventory, and help modules.
"""
from typing import List, Dict, Any
from commands.command_system import command
from core.config import FORMAT_TITLE, FORMAT_HIGHLIGHT, FORMAT_SUCCESS, FORMAT_ERROR, FORMAT_RESET, DEFAULT_WORLD_FILE

# System commands
@command("help", aliases=["h", "?"], category="system", 
         help_text="Display help information about available commands.\n\nUsage: help [command]\n\nIf no command is specified, shows a list of all commands.")
def help_handler(args, context):
    """Handle the help command."""
    command_processor = context["command_processor"]
    
    if args:
        return command_processor.get_command_help(args[0])
    else:
        return command_processor.get_help_text()

@command("quit", aliases=["q", "exit"], category="system", 
         help_text="Exit the game. Your progress will not be automatically saved.")
def quit_handler(args, context):
    """Handle the quit command."""
    if "game" in context:
        context["game"].quit_game()
    return f"{FORMAT_HIGHLIGHT}Goodbye!{FORMAT_RESET}"

@command("save", aliases=[], category="system", 
         help_text="Save the current game state to a file.\n\nUsage: save [filename]\n\nIf no filename is provided, saves to the default world file.")
def save_handler(args, context):
    """Handle the save command."""
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

@command("load", aliases=[], category="system", 
         help_text="Load a game state from a file.\n\nUsage: load [filename]\n\nIf no filename is provided, loads from the default world file.")
def load_handler(args, context):
    """Handle the load command."""
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

# Inventory and status commands
@command("inventory", aliases=["i", "inv"], category="inventory", 
         help_text="Show the items you are carrying.")
def inventory_handler(args, context):
    """Handle the inventory command."""
    world = context["world"]
    
    inventory_text = f"{FORMAT_TITLE}INVENTORY{FORMAT_RESET}\n\n"
    inventory_text += world.player.inventory.list_items()
    
    return inventory_text

@command("status", aliases=["stat", "st"], category="inventory", 
         help_text="Display your character's health, stats, and other information.")
def status_handler(args, context):
    """Handle the status command."""
    world = context["world"]
    
    status = world.get_player_status()
    return f"{FORMAT_TITLE}CHARACTER STATUS{FORMAT_RESET}\n\n{status}"

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

"""
core/config.py
Configuration settings for the game.
"""

# Display settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FONT_SIZE = 18
LINE_SPACING = 5
INPUT_HEIGHT = 30

# Colors
TEXT_COLOR = (255, 255, 255)
BG_COLOR = (0, 0, 0)
INPUT_BG_COLOR = (50, 50, 50)

# Text formatting codes
# These will be replaced with appropriate color codes when rendering text
FORMAT_TITLE = "[[TITLE]]"       # Yellow, for headings
FORMAT_CATEGORY = "[[CAT]]"      # Cyan, for categories and labels
FORMAT_HIGHLIGHT = "[[HI]]"      # Green, for important information
FORMAT_SUCCESS = "[[OK]]"        # Green, for success messages
FORMAT_ERROR = "[[ERR]]"         # Red, for error messages
FORMAT_RESET = "[[/]]"           # Reset to default text color

# Color values for formatting codes
FORMAT_COLORS = {
    FORMAT_TITLE: (255, 255, 0),      # Yellow
    FORMAT_CATEGORY: (0, 255, 255),   # Cyan
    FORMAT_HIGHLIGHT: (0, 255, 0),    # Green
    FORMAT_SUCCESS: (0, 255, 0),      # Green
    FORMAT_ERROR: (255, 0, 0),        # Red
    FORMAT_RESET: TEXT_COLOR          # Default text color
}

# Scrolling
SCROLL_SPEED = 3  # Lines to scroll per mouse wheel movement

# Game settings
DEFAULT_WORLD_FILE = "world.json"

"""
core/game_manager.py
Updated Game Manager module for the MUD game with consolidated command system.
"""
import time
import pygame
import sys
import textwrap
import importlib
from typing import Any, List

import core.config as config
from world.world import World
from commands.command_system import registered_commands, CommandProcessor
from utils.colored_text import ColoredText
from plugins.plugin_system import PluginManager
import commands.core_commands  # Import command modules to register them
import commands.movement_commands
import commands.interaction_commands


class GameManager:
    """
    Manages the game's UI, input handling, and main loop.
    """
    def __init__(self, world_file: str = config.DEFAULT_WORLD_FILE):
        """
        Initialize the game manager.
        
        Args:
            world_file: Path to the JSON world file to load.
        """
        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont("monospace", config.FONT_SIZE)
        self.clock = pygame.time.Clock()
        
        # Calculate the textwrap width based on screen dimensions
        self._calculate_textwrap_width()
        
        # Initialize world
        self.world = World()
        self.world.start_time = time.time()  # Set the game world start time
        
        self.world.game = self

        if not self.world.load_from_json(world_file):
            print(f"Failed to load world from {world_file}. Creating test world.")
            self._create_test_world()

        # Time display data
        self.time_data = {
            "hour": 12,
            "minute": 0,
            "day": 1,
            "month": 1,
            "year": 1,
            "day_name": "Moonday",
            "month_name": "Deepwinter",
            "time_period": "day",
            "time_str": "12:00",
            "date_str": "Moonday, 1 Deepwinter, Year 1"
        }
        
        # Initialize command processor
        self.command_processor = CommandProcessor()
        
        # Initialize plugin manager
        self.plugin_manager = PluginManager(self.world, self.command_processor)

        # Subscribe to events
        self.plugin_manager.event_system.subscribe("display_message", self._on_display_message)
        self.plugin_manager.event_system.subscribe("time_data", self._on_time_data_event)
        self.plugin_manager.event_system.subscribe("time_period_changed", self._on_time_period_changed)
        
        # Load all plugins
        self.plugin_manager.load_all_plugins()

        # Message buffer for NPC updates
        self.npc_messages = []
        self.last_npc_message_time = time.time()  # Initialize this to avoid errors

        # Text buffers and input
        self.text_buffer: List[str] = []
        self.input_text = ""
        self.cursor_visible = True
        self.cursor_timer = 0
        
        # Command history
        self.command_history = []
        self.history_index = -1
        
        # Set up tab completion state
        self.tab_completion_buffer = ""
        self.tab_suggestions = []
        self.tab_index = -1
        
        # For scrolling
        self.scroll_offset = 0
        self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 20) // (config.FONT_SIZE + config.LINE_SPACING)
        
        # Initialize text rendering
        self.colored_text = ColoredText(self.font, config.FORMAT_COLORS)
        
        # Debug mode
        self.debug_mode = False
        
        # Welcome message
        welcome_message = f"{config.FORMAT_TITLE}Welcome to Pygame MUD!{config.FORMAT_RESET}\n\n"
        welcome_message += "Type 'help' to see available commands.\n\n"
        welcome_message += "=" * 40 + "\n\n"
        welcome_message += self.world.look()  # Start with room description
        
        self.text_buffer.append(self._sanitize_text(welcome_message))
    
    def _calculate_textwrap_width(self):
        """
        Calculate the appropriate textwrap width based on screen dimensions and font.
        For monospace fonts, we can calculate how many characters fit in the screen width.
        """
        # Get the width of a single character (for monospace fonts)
        test_text = "X"
        text_width = self.font.size(test_text)[0]
        
        # Calculate how many characters can fit in the display area (with some margin)
        usable_width = config.SCREEN_WIDTH - 20  # 10px margin on each side
        chars_per_line = usable_width // text_width
        
        # Create the textwrapper with the calculated width
        self.wrapper = textwrap.TextWrapper(width=chars_per_line)
        
        # Recalculate max_visible_lines to account for time bar
        self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 50) // (config.FONT_SIZE + config.LINE_SPACING)
    
    def handle_input(self, text: str) -> str:
        """
        Process user input and return the result.
        
        Args:
            text: The user's input text.
            
        Returns:
            A string response to display to the user.
        """
        # Add the input to the text buffer and command history
        self.text_buffer.append(text)
        
        if text.strip():  # Only add non-empty commands to history
            self.command_history.append(text)
            self.history_index = -1  # Reset history index
        
        # Extract command and args for plugin notification
        parts = text.strip().split()
        command = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        
        # Process the command using the command processor
        context = {
            "game": self,
            "world": self.world,
            "command_processor": self.command_processor
        }
        
        # Notify plugins about the command
        self.plugin_manager.on_command(command, args, context)
        
        # Process the command
        result = self.command_processor.process_input(text, context)
        
        # Sanitize the result before returning
        return self._sanitize_text(result)
    
    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text by normalizing newlines and removing problematic characters.
        
        Args:
            text: The text to sanitize.
            
        Returns:
            Sanitized text.
        """
        if not text:
            return ""
            
        # Normalize newlines to \n
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove any control characters except for newlines
        text = ''.join(ch if ch == '\n' or ord(ch) >= 32 else ' ' for ch in text)
        
        # Collapse multiple consecutive newlines into at most two
        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
            
        return text
    
    def update(self):
        """Update game state."""
        current_time = time.time() - self.world.start_time
        
        # Explicitly publish the on_tick event for plugins
        if hasattr(self, 'plugin_manager') and hasattr(self.plugin_manager, 'event_system'):
            self.plugin_manager.event_system.publish("on_tick", current_time)
        
        # Call the plugin manager's on_tick method
        if hasattr(self, 'plugin_manager'):
            self.plugin_manager.on_tick(current_time)
        
        # Update the game world
        npc_updates = self.world.update()
        
        # Process all NPC messages immediately
        if npc_updates:
            for message in npc_updates:
                if message:  # Only add non-empty messages
                    self.text_buffer.append(message)
                    
        # Update the cursor blink timer
        self.cursor_timer += self.clock.get_time()
        if self.cursor_timer >= 500:  # Toggle cursor every 500ms
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0


    def draw(self):
        """Render the game UI."""
        self.screen.fill(config.BG_COLOR)
        
        # Time bar at the top
        self._draw_time_bar()
        
        # Calculate total number of lines in the buffer
        total_lines = 0
        formatted_lines = []
        
        for text in self.text_buffer:
            # Process each line from the buffer
            lines = text.split('\n')
            for line in lines:
                formatted_lines.append(line)
                total_lines += 1
        
        # Calculate how many lines we can show
        visible_lines = min(total_lines, self.max_visible_lines)
        start_line = max(0, total_lines - visible_lines - self.scroll_offset)
        
        # Draw the visible lines
        y_offset = 40  # Increased to make room for time bar
        for i in range(start_line, min(total_lines, start_line + self.max_visible_lines)):
            if i < len(formatted_lines):
                line = formatted_lines[i]
                self.colored_text.render(self.screen, line, (10, y_offset))
                y_offset += config.FONT_SIZE + config.LINE_SPACING
        
        # Draw the input box
        pygame.draw.rect(self.screen, config.INPUT_BG_COLOR, 
                        (0, config.SCREEN_HEIGHT - config.INPUT_HEIGHT, 
                        config.SCREEN_WIDTH, config.INPUT_HEIGHT))
        
        # Draw input text
        input_display = "> " + self.input_text
        if self.cursor_visible:
            input_display += "|"
        
        input_surface = self.font.render(input_display, True, config.TEXT_COLOR)
        self.screen.blit(input_surface, (10, config.SCREEN_HEIGHT - config.INPUT_HEIGHT + 5))
        
        # Draw debug indicator if in debug mode
        if self.debug_mode:
            debug_text = "DEBUG MODE"
            debug_surface = self.font.render(debug_text, True, (255, 0, 0))
            self.screen.blit(debug_surface, 
                            (config.SCREEN_WIDTH - debug_surface.get_width() - 10, 40))
        
        pygame.display.flip()
    
    def _draw_time_bar(self):
        """Draw a time display bar at the top of the screen."""
        # Use cached time data
        time_str = self.time_data.get("time_str", "??:??")
        date_str = self.time_data.get("date_str", "Unknown Date")
        time_period = self.time_data.get("time_period", "unknown")
        
        # Draw time bar background
        pygame.draw.rect(self.screen, (40, 40, 60), 
                        (0, 0, config.SCREEN_WIDTH, 30))
        
        # Draw time on left
        time_color = self._get_time_period_color(time_period)
        time_surface = self.font.render(time_str, True, time_color)
        self.screen.blit(time_surface, (10, 5))
        
        # Draw date in center
        date_surface = self.font.render(date_str, True, config.TEXT_COLOR)
        date_x = (config.SCREEN_WIDTH - date_surface.get_width()) // 2
        self.screen.blit(date_surface, (date_x, 5))
        
        # Draw time period on right
        period_surface = self.font.render(time_period.capitalize(), True, time_color)
        period_x = config.SCREEN_WIDTH - period_surface.get_width() - 10
        self.screen.blit(period_surface, (period_x, 5))
        
        # Draw separator line
        pygame.draw.line(self.screen, (80, 80, 100), 
                        (0, 30), (config.SCREEN_WIDTH, 30), 1)

    def _get_time_period_color(self, time_period):
        """Return a color based on the time period."""
        period_colors = {
            "dawn": (255, 165, 0),    # Orange
            "day": (255, 255, 150),   # Bright yellow
            "dusk": (255, 100, 100),  # Reddish
            "night": (100, 100, 255)  # Blue
        }
        return period_colors.get(time_period, config.TEXT_COLOR)
    
    def navigate_history(self, direction: int):
        """
        Navigate through command history.
        
        Args:
            direction: 1 for older commands, -1 for newer commands
        """
        if not self.command_history:
            return
            
        if direction > 0:  # Up key - older commands
            self.history_index = min(self.history_index + 1, len(self.command_history) - 1)
        else:  # Down key - newer commands
            self.history_index = max(self.history_index - 1, -1)
            
        if self.history_index >= 0:
            self.input_text = self.command_history[-(self.history_index + 1)]
        else:
            self.input_text = ""
        
        # Reset tab completion when navigating history
        self.tab_completion_buffer = ""
        self.tab_suggestions = []
        self.tab_index = -1
        
    def handle_tab_completion(self):
        """Handle tab completion for commands and directions."""
        # Get the current text and cursor position
        current_text = self.input_text.strip()
        
        # If no text, do nothing
        if not current_text:
            return
            
        # If this is first tab press for current text, get suggestions
        if current_text != self.tab_completion_buffer or not self.tab_suggestions:
            self.tab_completion_buffer = current_text
            self.tab_suggestions = self.command_processor.get_command_suggestions(current_text)
            self.tab_index = -1
        
        # If there are suggestions, cycle through them
        if self.tab_suggestions:
            self.tab_index = (self.tab_index + 1) % len(self.tab_suggestions)
            self.input_text = self.tab_suggestions[self.tab_index]
    
    def quit_game(self):
        """Cleanly exit the game."""
        # Unload all plugins
        if hasattr(self, 'plugin_manager'):
            self.plugin_manager.unload_all_plugins()
        pygame.quit()
        sys.exit()
    
    def run(self):
        """Main game loop."""
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        result = self.handle_input(self.input_text)
                        if result:
                            self.text_buffer.append(result)
                        self.input_text = ""
                    
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    
                    # Command history navigation
                    elif event.key == pygame.K_UP:
                        self.navigate_history(1)
                    
                    elif event.key == pygame.K_DOWN:
                        self.navigate_history(-1)
                        
                    # Handle tab completion
                    elif event.key == pygame.K_TAB:
                        self.handle_tab_completion()
                    
                    # Handle scrolling with page up/down keys
                    elif event.key == pygame.K_PAGEUP:
                        self.scroll_offset = min(len(self.text_buffer) * 10, 
                                                 self.scroll_offset + self.max_visible_lines // 2)
                    
                    elif event.key == pygame.K_PAGEDOWN:
                        self.scroll_offset = max(0, self.scroll_offset - self.max_visible_lines // 2)
                        
                    # Toggle debug mode
                    elif event.key == pygame.K_F1:
                        self.debug_mode = not self.debug_mode
                        if self.debug_mode:
                            self.text_buffer.append(f"{config.FORMAT_HIGHLIGHT}Debug mode enabled. Press F1 to disable.{config.FORMAT_RESET}")
                        else:
                            self.text_buffer.append(f"{config.FORMAT_HIGHLIGHT}Debug mode disabled.{config.FORMAT_RESET}")
                    
                    else:
                        # Only add printable characters
                        if event.unicode.isprintable():
                            self.input_text += event.unicode
                
                # Handle mouse wheel for scrolling
                elif event.type == pygame.MOUSEWHEEL:
                    if event.y > 0:  # Scroll up
                        self.scroll_offset = min(len(self.text_buffer) * 10, 
                                                 self.scroll_offset + config.SCROLL_SPEED)
                    elif event.y < 0:  # Scroll down
                        self.scroll_offset = max(0, self.scroll_offset - config.SCROLL_SPEED)
                        
                # Handle window resize events
                elif event.type == pygame.VIDEORESIZE:
                    # Update screen size
                    config.SCREEN_WIDTH = event.w
                    config.SCREEN_HEIGHT = event.h
                    self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), 
                                                         pygame.RESIZABLE)
                    # Recalculate text wrapping
                    self._calculate_textwrap_width()
                    # Update max visible lines
                    self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 20) // (config.FONT_SIZE + config.LINE_SPACING)
            
            self.update()
            self.draw()
            self.clock.tick(30)
        
        pygame.quit()

    def _create_test_world(self):
        """Create a test world with a few rooms, items, and NPCs."""
        # Create a basic region
        from world.region import Region
        from world.room import Room
        
        test_region = Region("Test Region", "A small test area.")
        
        # Create a few rooms
        entrance = Room("Entrance", "The entrance to the test region.")
        hall = Room("Main Hall", "A large hall with high ceilings.")
        garden = Room("Garden", "A beautiful garden with many plants.")
        
        # Connect the rooms
        entrance.exits = {"north": "hall"}
        hall.exits = {"south": "entrance", "east": "garden"}
        garden.exits = {"west": "hall"}
        
        # Add rooms to the region
        test_region.add_room("entrance", entrance)
        test_region.add_room("hall", hall)
        test_region.add_room("garden", garden)
        
        # Add region to the world
        self.world.add_region("test", test_region)
        
        # Set starting location
        self.world.current_region_id = "test"
        self.world.current_room_id = "entrance"
        
        # Create some test items
        from items.item import ItemFactory
        
        sword = ItemFactory.create_item("Weapon", name="Steel Sword", 
                                      description="A sharp steel sword.", damage=10)
        
        potion = ItemFactory.create_item("Consumable", name="Healing Potion",
                                       description="A potion that restores health.",
                                       effect_value=20, effect_type="heal")
        
        key = ItemFactory.create_item("Key", name="Brass Key",
                                    description="A small brass key.")
        
        # Add items to rooms
        self.world.add_item_to_room("test", "hall", sword)
        self.world.add_item_to_room("test", "garden", potion)
        
        # Add key to player inventory
        self.world.player.inventory.add_item(key)
        
        # Create some test NPCs
        from npcs.npc_factory import NPCFactory
        
        guard = NPCFactory.create_npc("guard", name="Guard Bob")
        guard.current_region_id = "test"
        guard.current_room_id = "entrance"
        guard.patrol_points = ["entrance", "hall"]  # Set up a patrol route
        
        merchant = NPCFactory.create_npc("shopkeeper", name="Merchant Alice")
        merchant.current_region_id = "test"
        merchant.current_room_id = "hall"
        
        villager = NPCFactory.create_npc("villager", name="Villager Charlie")
        villager.current_region_id = "test"
        villager.current_room_id = "garden"
        
        # Add NPCs to the world
        self.world.add_npc(guard)
        self.world.add_npc(merchant)
        self.world.add_npc(villager)

    def _on_time_data_event(self, event_type: str, data: dict) -> None:
        """
        Handle time data events.
        
        Args:
            event_type: The event type.
            data: The event data.
        """
        self.time_data = data

    def _on_time_period_changed(self, event_type: str, data: dict) -> None:
        """
        Handle time period change events.
        
        Args:
            event_type: The event type.
            data: The event data.
        """
        # Update time period
        if "new_period" in data:
            self.time_data["time_period"] = data["new_period"]
        
        # Add message to text buffer if there's a transition message
        if "transition_message" in data and data["transition_message"]:
            self.text_buffer.append(data['transition_message'])

    def _on_display_message(self, event_type: str, data: Any) -> None:
        """
        Handle display message events.
        
        Args:
            event_type: The event type.
            data: The message to display or message data.
        """
        # Handle different message formats
        if isinstance(data, str):
            message = data
        elif isinstance(data, dict) and "message" in data:
            message = data["message"]
        else:
            # Try to convert to string
            try:
                message = str(data)
            except:
                message = "Unprintable message"
        
        # Add the message to the text buffer
        self.text_buffer.append(message)

"""
items/inventory.py
Inventory system for the MUD game.
Handles storage and management of items.
"""
from typing import Dict, List, Optional, Tuple, Any
from items.item import Item, ItemFactory


class InventorySlot:
    """Represents a slot in an inventory that can hold items."""
    
    def __init__(self, item: Optional[Item] = None, quantity: int = 1):
        """
        Initialize an inventory slot.
        
        Args:
            item: The item in this slot, or None for an empty slot.
            quantity: The quantity of the item.
        """
        self.item = item
        self.quantity = quantity if item and item.stackable else 1
    
    def add(self, item: Item, quantity: int = 1) -> int:
        """
        Add an item to this slot.
        
        Args:
            item: The item to add.
            quantity: The quantity to add.
            
        Returns:
            The quantity that was added (may be less than requested if the slot is full).
        """
        # If slot is empty, can add any item
        if not self.item:
            self.item = item
            self.quantity = quantity if item.stackable else 1
            return quantity
        
        # If slot has same item and is stackable, can add more
        if self.item.item_id == item.item_id and self.item.stackable:
            self.quantity += quantity
            return quantity
            
        # Otherwise, can't add to this slot
        return 0
    
    def remove(self, quantity: int = 1) -> Tuple[Optional[Item], int]:
        """
        Remove items from this slot.
        
        Args:
            quantity: The quantity to remove.
            
        Returns:
            A tuple of (item, quantity_removed).
        """
        if not self.item:
            return None, 0
            
        quantity_to_remove = min(self.quantity, quantity)
        item = self.item
        
        # If removing all, clear the slot
        if quantity_to_remove >= self.quantity:
            self.item = None
            self.quantity = 0
            return item, quantity_to_remove
            
        # Otherwise, just reduce the quantity
        self.quantity -= quantity_to_remove
        return item, quantity_to_remove
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the slot to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the slot.
        """
        return {
            "item": self.item.to_dict() if self.item else None,
            "quantity": self.quantity
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InventorySlot':
        """
        Create a slot from a dictionary.
        
        Args:
            data: Dictionary data to convert.
            
        Returns:
            An InventorySlot instance.
        """
        item = ItemFactory.from_dict(data["item"]) if data.get("item") else None
        return cls(item, data.get("quantity", 1))


class Inventory:
    """Manages a collection of items in inventory slots."""
    
    def __init__(self, max_slots: int = 20, max_weight: float = 100.0):
        """
        Initialize an inventory.
        
        Args:
            max_slots: The maximum number of slots in the inventory.
            max_weight: The maximum weight the inventory can hold.
        """
        self.slots: List[InventorySlot] = [InventorySlot() for _ in range(max_slots)]
        self.max_slots = max_slots
        self.max_weight = max_weight
    
    def add_item(self, item: Item, quantity: int = 1) -> Tuple[bool, str]:
        """
        Add an item to the inventory.
        
        Args:
            item: The item to add.
            quantity: The quantity to add.
            
        Returns:
            A tuple of (success, message).
        """
        # Check weight constraints
        current_weight = self.get_total_weight()
        added_weight = item.weight * quantity
        
        if current_weight + added_weight > self.max_weight:
            return False, f"The {item.name} is too heavy to carry."
        
        # First, try to add to existing stacks
        if item.stackable:
            for slot in self.slots:
                if slot.item and slot.item.item_id == item.item_id:
                    added = slot.add(item, quantity)
                    quantity -= added
                    if quantity <= 0:
                        return True, f"Added {item.name} to inventory."
        
        # Then, try to add to empty slots
        remaining = quantity
        while remaining > 0:
            # Find an empty slot
            empty_slot = next((slot for slot in self.slots if not slot.item), None)
            
            if not empty_slot:
                if quantity > 1:
                    return False, f"Not enough space for {remaining} {item.name}."
                else:
                    return False, f"Not enough space for {item.name}."
            
            # Add to the empty slot
            to_add = 1 if not item.stackable else remaining
            empty_slot.add(item, to_add)
            remaining -= to_add
        
        return True, f"Added {item.name} to inventory."
    
    def remove_item(self, item_id: str, quantity: int = 1) -> Tuple[Optional[Item], int, str]:
        """
        Remove an item from the inventory.
        
        Args:
            item_id: The ID of the item to remove.
            quantity: The quantity to remove.
            
        Returns:
            A tuple of (item, quantity_removed, message).
        """
        # First, count how many of this item we have
        total_available = sum(slot.quantity for slot in self.slots 
                             if slot.item and slot.item.item_id == item_id)
        
        if total_available == 0:
            return None, 0, f"You don't have that item."
        
        if total_available < quantity:
            return None, 0, f"You don't have {quantity} of that item."
        
        # Remove the items
        remaining = quantity
        removed_item = None
        
        for slot in self.slots:
            if slot.item and slot.item.item_id == item_id and remaining > 0:
                item, removed = slot.remove(remaining)
                if not removed_item and item:
                    removed_item = item
                remaining -= removed
                
                if remaining <= 0:
                    break
        
        return removed_item, quantity, f"Removed {quantity} {removed_item.name if removed_item else 'unknown item'} from inventory."
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """
        Get an item from the inventory without removing it.
        
        Args:
            item_id: The ID of the item to get.
            
        Returns:
            The item, or None if not found.
        """
        for slot in self.slots:
            if slot.item and slot.item.item_id == item_id:
                return slot.item
        return None
    
    def get_total_weight(self) -> float:
        """
        Calculate the total weight of all items in the inventory.
        
        Returns:
            The total weight.
        """
        return sum(slot.item.weight * slot.quantity for slot in self.slots if slot.item)
    
    def get_empty_slots(self) -> int:
        """
        Calculate the number of empty slots in the inventory.
        
        Returns:
            The number of empty slots.
        """
        return sum(1 for slot in self.slots if not slot.item)
    
    def list_items(self) -> str:
        """
        Get a formatted list of all items in the inventory.
        
        Returns:
            A string listing the inventory contents.
        """
        if all(not slot.item for slot in self.slots):
            return "Your inventory is empty."
        
        result = []
        for i, slot in enumerate(self.slots):
            if slot.item:
                if slot.quantity > 1:
                    result.append(f"[{i+1}] {slot.item.name} (x{slot.quantity}) - {slot.quantity * slot.item.weight:.1f} weight")
                else:
                    result.append(f"[{i+1}] {slot.item.name} - {slot.item.weight:.1f} weight")
        
        total_weight = self.get_total_weight()
        result.append(f"\nTotal weight: {total_weight:.1f}/{self.max_weight:.1f}")
        result.append(f"Slots used: {self.max_slots - self.get_empty_slots()}/{self.max_slots}")
        
        return "\n".join(result)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the inventory to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the inventory.
        """
        return {
            "max_slots": self.max_slots,
            "max_weight": self.max_weight,
            "slots": [slot.to_dict() for slot in self.slots]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Inventory':
        """
        Create an inventory from a dictionary.
        
        Args:
            data: Dictionary data to convert.
            
        Returns:
            An Inventory instance.
        """
        inventory = cls(
            max_slots=data.get("max_slots", 20),
            max_weight=data.get("max_weight", 100.0)
        )
        
        # Clear default slots and replace with loaded ones
        inventory.slots = [InventorySlot.from_dict(slot_data) 
                          for slot_data in data.get("slots", [])]
        
        # If we have fewer slots than max_slots, add empty ones
        while len(inventory.slots) < inventory.max_slots:
            inventory.slots.append(InventorySlot())
            
        return inventory

"""
items/item.py
Item system for the MUD game.
Base classes for all items in the game.
"""
from typing import Dict, List, Optional, Any
import uuid
import json


class Item:
    """Base class for all items in the game."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Item", 
                 description: str = "No description", weight: float = 1.0,
                 value: int = 0, stackable: bool = False):
        """
        Initialize an item.
        
        Args:
            item_id: Unique ID for the item. If None, one will be generated.
            name: The display name of the item.
            description: A textual description of the item.
            weight: The weight of the item in arbitrary units.
            value: The monetary value of the item.
            stackable: Whether multiple instances of this item can be stacked in inventory.
        """
        self.item_id = item_id if item_id else f"item_{uuid.uuid4().hex[:8]}"
        self.name = name
        self.description = description
        self.weight = weight
        self.value = value
        self.stackable = stackable
        self.properties: Dict[str, Any] = {}  # Additional properties for derived item types
    
    def examine(self) -> str:
        """
        Get a detailed description of the item.
        
        Returns:
            A formatted description of the item.
        """
        return f"{self.name}\n\n{self.description}\n\nWeight: {self.weight}, Value: {self.value}"
    
    def use(self, user) -> str:
        """
        Use this item (default behavior, to be overridden).
        
        Args:
            user: The entity using the item.
            
        Returns:
            A string describing what happened.
        """
        return f"You don't know how to use the {self.name}."
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the item to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the item.
        """
        return {
            "type": self.__class__.__name__,
            "item_id": self.item_id,
            "name": self.name,
            "description": self.description,
            "weight": self.weight,
            "value": self.value,
            "stackable": self.stackable,
            "properties": self.properties
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Item':
        """
        Create an item from a dictionary.
        
        Args:
            data: Dictionary data to convert into an item.
            
        Returns:
            An item instance.
        """
        item = cls(
            item_id=data["item_id"],
            name=data["name"],
            description=data["description"],
            weight=data["weight"],
            value=data["value"],
            stackable=data["stackable"]
        )
        item.properties = data.get("properties", {})
        return item


class Weapon(Item):
    """A weapon item that can be used in combat."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Weapon", 
                 description: str = "No description", weight: float = 2.0,
                 value: int = 10, damage: int = 5, durability: int = 100):
        """
        Initialize a weapon.
        
        Args:
            damage: The base damage value of the weapon.
            durability: The durability/condition of the weapon.
        """
        super().__init__(item_id, name, description, weight, value, stackable=False)
        self.properties["damage"] = damage
        self.properties["durability"] = durability
        self.properties["max_durability"] = durability
    
    def examine(self) -> str:
        """Get a detailed description of the weapon."""
        base_desc = super().examine()
        return f"{base_desc}\n\nDamage: {self.properties['damage']}\nDurability: {self.properties['durability']}/{self.properties['max_durability']}"
    
    def use(self, user) -> str:
        """Use the weapon (practice attack)."""
        return f"You practice swinging the {self.name}. It feels {'sturdy' if self.properties['durability'] > 50 else 'fragile'}."


class Consumable(Item):
    """A consumable item like food or potion."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Consumable", 
                 description: str = "No description", weight: float = 0.5,
                 value: int = 5, uses: int = 1, effect_value: int = 10, 
                 effect_type: str = "heal"):
        """
        Initialize a consumable.
        
        Args:
            uses: The number of uses before the item is consumed.
            effect_value: How strong the effect is.
            effect_type: What type of effect (heal, damage, etc.).
        """
        super().__init__(item_id, name, description, weight, value, stackable=(uses == 1))
        self.properties["uses"] = uses
        self.properties["max_uses"] = uses
        self.properties["effect_value"] = effect_value
        self.properties["effect_type"] = effect_type
    
    def examine(self) -> str:
        """Get a detailed description of the consumable."""
        base_desc = super().examine()
        if self.properties["max_uses"] > 1:
            return f"{base_desc}\n\nUses remaining: {self.properties['uses']}/{self.properties['max_uses']}"
        return base_desc
    
    def use(self, user) -> str:
        """Use the consumable item."""
        if self.properties["uses"] <= 0:
            return f"The {self.name} has been completely used up."
        
        self.properties["uses"] -= 1
        
        effect_type = self.properties["effect_type"]
        effect_value = self.properties["effect_value"]
        
        if effect_type == "heal":
            # Attempt to heal the user if it has health
            if hasattr(user, "health") and hasattr(user, "max_health"):
                old_health = user.health
                user.health = min(user.health + effect_value, user.max_health)
                gained = user.health - old_health
                return f"You consume the {self.name} and regain {gained} health."
            
            return f"You consume the {self.name}, but it has no effect on you."
        
        # Other effect types can be added here
        return f"You consume the {self.name}."


class Container(Item):
    """A container that can hold other items."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Container", 
                 description: str = "No description", weight: float = 2.0,
                 value: int = 20, capacity: float = 50.0):
        """
        Initialize a container.
        
        Args:
            capacity: The maximum weight the container can hold.
        """
        super().__init__(item_id, name, description, weight, value, stackable=False)
        self.properties["capacity"] = capacity
        self.properties["contains"] = []  # List of item IDs
        self.properties["locked"] = False
        self.properties["key_id"] = None  # ID of key that can open this container
    
    def examine(self) -> str:
        """Get a detailed description of the container."""
        base_desc = super().examine()
        if self.properties["locked"]:
            return f"{base_desc}\n\nThe {self.name} is locked."
        
        # We'll need inventory management to show contents
        return f"{base_desc}\n\nCapacity: {self.properties['capacity']} weight units."
    
    def use(self, user) -> str:
        """Use the container (open it)."""
        if self.properties["locked"]:
            return f"The {self.name} is locked."
        
        # We'll need inventory management to handle this properly
        return f"You open the {self.name}."


class Key(Item):
    """A key that can unlock containers or doors."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Key", 
                 description: str = "No description", weight: float = 0.1,
                 value: int = 15, target_id: str = None):
        """
        Initialize a key.
        
        Args:
            target_id: The ID of the container or door this key unlocks.
        """
        super().__init__(item_id, name, description, weight, value, stackable=False)
        self.properties["target_id"] = target_id
    
    def use(self, user) -> str:
        """Use the key (attempt to unlock something)."""
        return f"You need to specify what to use the {self.name} on."


class Treasure(Item):
    """A valuable item that exists primarily for its value."""
    
    def __init__(self, item_id: str = None, name: str = "Unknown Treasure", 
                 description: str = "No description", weight: float = 0.5,
                 value: int = 100):
        """Initialize a treasure item."""
        super().__init__(item_id, name, description, weight, value, stackable=False)
        self.properties["treasure_type"] = "generic"  # Can be 'coin', 'gem', 'jewelry', etc.
    
    def use(self, user) -> str:
        """Use the treasure (admire it)."""
        return f"You admire the {self.name}. It looks quite valuable."


class ItemFactory:
    """Factory class for creating items from templates or data."""
    
    @staticmethod
    def create_item(item_type: str, **kwargs) -> Item:
        """
        Create an item of the specified type.
        
        Args:
            item_type: The type of item to create.
            **kwargs: Additional arguments to pass to the item constructor.
            
        Returns:
            An instance of the requested item type.
        """
        item_classes = {
            "Item": Item,
            "Weapon": Weapon,
            "Consumable": Consumable,
            "Container": Container,
            "Key": Key,
            "Treasure": Treasure
        }
        
        if item_type not in item_classes:
            raise ValueError(f"Unknown item type: {item_type}")
        
        return item_classes[item_type](**kwargs)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Item:
        """
        Create an item from a dictionary.
        
        Args:
            data: Dictionary containing item data.
            
        Returns:
            An item instance of the appropriate type.
        """
        item_type = data.get("type", "Item")
        
        # Create a base item first
        item = ItemFactory.create_item(item_type, 
                                      item_id=data.get("item_id"),
                                      name=data.get("name", "Unknown Item"),
                                      description=data.get("description", "No description"),
                                      weight=data.get("weight", 1.0),
                                      value=data.get("value", 0))
        
        # Set additional properties
        if "properties" in data:
            item.properties.update(data["properties"])
            
        return item

"""
npcs/npc.py
NPC system for the MUD game.
Defines non-player characters and their behavior.
"""
from typing import Dict, List, Optional, Any, Tuple, Callable
import random
import time
from items.inventory import Inventory
from items.item import Item


class NPC:
    """Base class for all non-player characters."""
    
    def __init__(self, npc_id: str = None, name: str = "Unknown NPC", 
                 description: str = "No description", health: int = 100,
                 friendly: bool = True):
        """
        Initialize an NPC.
        
        Args:
            npc_id: Unique ID for the NPC.
            name: The display name of the NPC.
            description: A textual description of the NPC.
            health: The current health of the NPC.
            friendly: Whether the NPC is friendly to the player.
        """
        self.npc_id = npc_id if npc_id else f"npc_{random.randint(1000, 9999)}"
        self.name = name
        self.description = description
        self.health = health
        self.max_health = health
        self.friendly = friendly
        self.inventory = Inventory(max_slots=10, max_weight=50.0)
        
        # Movement and location data
        self.current_region_id = None
        self.current_room_id = None
        self.home_region_id = None
        self.home_room_id = None

        self.current_activity = None
        
        # Behavior data
        self.behavior_type = "stationary"  # 'stationary', 'wanderer', 'patrol', 'follower'
        self.patrol_points = []  # List of room IDs for patrol routes
        self.patrol_index = 0
        self.follow_target = None  # ID of entity to follow
        self.wander_chance = 0.3  # Chance to wander each update
        self.schedule = {}  # Time-based schedule of room IDs
        self.last_moved = 0  # Time of last movement
        self.move_cooldown = 10  # Seconds between movements
        
        # Interaction data
        self.dialog = {}  # Mapping of keywords to responses
        self.default_dialog = "The {name} doesn't respond."
        self.ai_state = {}  # Custom state for NPC behavior
    
    def get_description(self) -> str:
        """
        Get a description of the NPC.
        
        Returns:
            A formatted description.
        """
        health_percent = self.health / self.max_health * 100
        health_desc = ""
        
        if health_percent <= 25:
            health_desc = f"The {self.name} looks severely injured."
        elif health_percent <= 50:
            health_desc = f"The {self.name} appears to be wounded."
        elif health_percent <= 75:
            health_desc = f"The {self.name} has some minor injuries."
        else:
            health_desc = f"The {self.name} looks healthy."
        
        return f"{self.name}\n\n{self.description}\n\n{health_desc}"
        
    def talk(self, topic: str = None) -> str:
        """
        Get dialog from the NPC based on a topic.
        
        Args:
            topic: The topic to discuss, or None for default greeting.
            
        Returns:
            The NPC's response.
        """
        # Check if NPC is busy with an activity
        if hasattr(self, "ai_state"):
            # Check for activity-specific responses
            if self.ai_state.get("is_sleeping", False):
                # NPC is sleeping
                responses = self.ai_state.get("sleeping_responses", [])
                if responses:
                    import random
                    return random.choice(responses).format(name=self.name)
            
            elif self.ai_state.get("is_eating", False):
                # NPC is eating
                responses = self.ai_state.get("eating_responses", [])
                if responses:
                    import random
                    return random.choice(responses).format(name=self.name)
            
            elif self.ai_state.get("is_working", False) and topic != "work":
                # NPC is working but might respond to work-related topics
                responses = self.ai_state.get("working_responses", [])
                if responses:
                    import random
                    return random.choice(responses).format(name=self.name)
        
        # Normal dialog processing for NPCs not engaged in busy activities
        if not topic:
            # Default greeting
            if "greeting" in self.dialog:
                return self.dialog["greeting"].format(name=self.name)
            return f"The {self.name} greets you."
        
        # Look for the topic in the dialog dictionary
        topic = topic.lower()
        if topic in self.dialog:
            return self.dialog[topic].format(name=self.name)
        
        # Try partial matching
        for key in self.dialog:
            if topic in key:
                return self.dialog[key].format(name=self.name)
        
        # If NPC is engaged in an activity, reference it in default response
        if hasattr(self, "ai_state") and "current_activity" in self.ai_state:
            activity = self.ai_state["current_activity"]
            return f"The {self.name} continues {activity} and doesn't respond about that topic."
        
        # Default response
        return self.default_dialog.format(name=self.name)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the NPC to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the NPC.
        """
        return {
            "npc_id": self.npc_id,
            "name": self.name,
            "description": self.description,
            "health": self.health,
            "max_health": self.max_health,
            "friendly": self.friendly,
            "inventory": self.inventory.to_dict(),
            "current_region_id": self.current_region_id,
            "current_room_id": self.current_room_id,
            "home_region_id": self.home_region_id,
            "home_room_id": self.home_room_id,
            "behavior_type": self.behavior_type,
            "patrol_points": self.patrol_points,
            "patrol_index": self.patrol_index,
            "follow_target": self.follow_target,
            "wander_chance": self.wander_chance,
            "schedule": self.schedule,
            "move_cooldown": self.move_cooldown,
            "dialog": self.dialog,
            "default_dialog": self.default_dialog,
            "ai_state": self.ai_state
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NPC':
        """
        Create an NPC from a dictionary.
        
        Args:
            data: Dictionary data to convert.
            
        Returns:
            An NPC instance.
        """
        npc = cls(
            npc_id=data.get("npc_id"),
            name=data.get("name", "Unknown NPC"),
            description=data.get("description", "No description"),
            health=data.get("health", 100),
            friendly=data.get("friendly", True)
        )
        
        # Set basic properties
        npc.max_health = data.get("max_health", 100)
        npc.current_region_id = data.get("current_region_id")
        npc.current_room_id = data.get("current_room_id")
        npc.home_region_id = data.get("home_region_id")
        npc.home_room_id = data.get("home_room_id")
        
        # Set behavior properties
        npc.behavior_type = data.get("behavior_type", "stationary")
        npc.patrol_points = data.get("patrol_points", [])
        npc.patrol_index = data.get("patrol_index", 0)
        npc.follow_target = data.get("follow_target")
        npc.wander_chance = data.get("wander_chance", 0.3)
        npc.schedule = data.get("schedule", {})
        npc.move_cooldown = data.get("move_cooldown", 10)
        
        # Set interaction properties
        npc.dialog = data.get("dialog", {})
        npc.default_dialog = data.get("default_dialog", "The {name} doesn't respond.")
        npc.ai_state = data.get("ai_state", {})
        
        # Set inventory if present
        if "inventory" in data:
            npc.inventory = Inventory.from_dict(data["inventory"])
            
        return npc
        
    def update(self, world, current_time: float) -> Optional[str]:
        """
        Update the NPC's state and perform actions.
        
        Args:
            world: The game world object.
            current_time: The current game time.
            
        Returns:
            An optional message if the NPC did something visible.
        """
        # Check if NPC is sleeping - no movement
        if hasattr(self, "ai_state") and self.ai_state.get("is_sleeping", False):
            return None
        
        # Check if NPC is eating or working - reduced movement
        if hasattr(self, "ai_state") and (self.ai_state.get("is_eating", False) or self.ai_state.get("is_working", False)):
            # Only move rarely
            import random
            if random.random() > 0.9:  # 10% chance to still move
                pass  # Continue to normal movement logic
            else:
                return None  # No movement most of the time
            
        # Check if it's time to move
        if current_time - self.last_moved < self.move_cooldown:
            return None
                
        # Update according to behavior type
        if self.behavior_type == "wanderer":
            message = self._wander_behavior(world, current_time)
            if message:
                # Only update the last_moved time if the NPC actually moved
                self.last_moved = current_time
            return message
        elif self.behavior_type == "patrol":
            message = self._patrol_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message
        elif self.behavior_type == "follower":
            message = self._follower_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message
        elif self.behavior_type == "scheduled":
            message = self._schedule_behavior(world, current_time)
            if message:
                self.last_moved = current_time
            return message
                    
        # Default stationary behavior
        return None
            
    def _schedule_behavior(self, world, current_time: float) -> Optional[str]:
        """
        Implement schedule-based behavior.
        This improved version better coordinates with the NPC Schedule plugin.
        """
        if not self.schedule:
            return None
            
        # Convert the current time to hours (assuming current_time is in seconds)
        current_hour = int((current_time // 3600) % 24)
        
        # Check if there's a scheduled destination for this hour
        if current_hour in self.schedule:
            destination = self.schedule[current_hour]
            
            # If we're already there, do nothing related to movement
            # but still return possible activity message
            if destination == self.current_room_id:
                # Get current activity from ai_state if available
                if hasattr(self, "ai_state") and "current_activity" in self.ai_state:
                    activity = self.ai_state["current_activity"]
                    
                    # Only return a message if the player is in the same room
                    if (world.current_region_id == self.current_region_id and 
                        world.current_room_id == self.current_room_id):
                        
                        # Check if we've already notified about this activity
                        last_notified = self.ai_state.get("last_notified_activity")
                        if last_notified != f"{current_hour}_{activity}":
                            self.ai_state["last_notified_activity"] = f"{current_hour}_{activity}"
                            return f"{self.name} continues {activity}."
                
                return None
                
            # Handle region transitions in the destination
            old_region_id = self.current_region_id
            old_room_id = self.current_room_id
            
            # Parse destination
            if ":" in destination:
                new_region_id, new_room_id = destination.split(":")
                self.current_region_id = new_region_id
                self.current_room_id = new_room_id
            else:
                # Assume same region
                new_room_id = destination
                self.current_room_id = new_room_id
                new_region_id = self.current_region_id
                
            # Update last_moved time
            self.last_moved = current_time
            
            # Get current activity if available
            activity_msg = ""
            if hasattr(self, "ai_state") and "current_activity" in self.ai_state:
                activity = self.ai_state["current_activity"]
                activity_msg = f" to {activity}"
                
                # Update last notified activity
                self.ai_state["last_notified_activity"] = f"{current_hour}_{activity}"
            
            # Only return a message if the player is in either the old or new room
            if (world.current_region_id == old_region_id and 
                world.current_room_id == old_room_id):
                return f"{self.name} leaves{activity_msg}."
                
            if (world.current_region_id == self.current_region_id and 
                world.current_room_id == self.current_room_id):
                return f"{self.name} arrives{activity_msg}."
        
        return None
    
    def _reverse_direction(self, direction: str) -> str:
        """Get the opposite direction."""
        opposites = {
            "north": "south", "south": "north",
            "east": "west", "west": "east",
            "northeast": "southwest", "southwest": "northeast",
            "northwest": "southeast", "southeast": "northwest",
            "up": "down", "down": "up"
        }
        return opposites.get(direction, "somewhere")

    def _wander_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement wandering behavior."""
        # Only wander sometimes
        if random.random() > self.wander_chance:
            return None
            
        # Get current room and its exits
        region = world.get_region(self.current_region_id)
        if not region:
            return None
            
        room = region.get_room(self.current_room_id)
        if not room:
            return None
            
        exits = list(room.exits.keys())
        if not exits:
            return None
            
        # Choose a random exit and move through it
        direction = random.choice(exits)
        destination = room.exits[direction]
        
        # Save old location info
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        
        # Handle region transitions
        if ":" in destination:
            new_region_id, new_room_id = destination.split(":")
            
            # Update location
            self.current_region_id = new_region_id
            self.current_room_id = new_room_id
            
        else:
            # Same region, different room
            self.current_room_id = destination
        
        # Note: We no longer update self.last_moved here
        # It will be updated in the main update method
        
        # Check if the player is in the room to see the NPC leave
        if (world.current_region_id == old_region_id and 
            world.current_room_id == old_room_id):
            return f"{self.name} leaves to the {direction}."
            
        # Check if the player is in the destination room to see the NPC arrive
        if (world.current_region_id == self.current_region_id and 
            world.current_room_id == self.current_room_id):
            return f"{self.name} arrives from the {self._reverse_direction(direction)}."
        
        return None
    
    def _patrol_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement patrol behavior."""
        if not self.patrol_points:
            return None
            
        # Get next patrol point
        next_point = self.patrol_points[self.patrol_index]
        
        # If we're already there, move to the next point in the list
        if next_point == self.current_room_id:
            self.patrol_index = (self.patrol_index + 1) % len(self.patrol_points)
            return None
            
        # Find a path to the next patrol point (simplified version)
        # In a real implementation, you'd want a proper pathfinding algorithm
        
        # Get current room
        region = world.get_region(self.current_region_id)
        if not region:
            return None
            
        room = region.get_room(self.current_room_id)
        if not room:
            return None
            
        # Look for a direct path first
        for direction, destination in room.exits.items():
            if destination == next_point:
                old_room_id = self.current_room_id
                self.current_room_id = destination
                
                # Check if the player is in the room to see the NPC leave
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == old_room_id):
                    message = f"{self.name} leaves to the {direction}."
                    return message
                    
                # Check if the player is in the destination room to see the NPC arrive
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == destination):
                    message = f"{self.name} arrives from the {self._reverse_direction(direction)}."
                    return message
                
                self.last_moved = current_time
                return None
        
        # If no direct path, just pick a random exit (this is a simplification)
        return self._wander_behavior(world, current_time)
    
    def _follower_behavior(self, world, current_time: float) -> Optional[str]:
        """Implement follower behavior."""
        if not self.follow_target:
            return None
            
        # For now, we'll just assume the follow target is the player
        if self.follow_target == "player":
            # Check if we're already in the same room as the player
            if (self.current_region_id == world.current_region_id and
                self.current_room_id == world.current_room_id):
                return None
                
            # We need to find a path to the player (simplified)
            # In a full implementation, you'd want proper pathfinding
            
            # Get current room
            region = world.get_region(self.current_region_id)
            if not region:
                return None
                
            room = region.get_room(self.current_room_id)
            if not room:
                return None
                
            # Try to move toward the player by picking an exit that feels right
            # This is a very simplified approach
            best_direction = None
            
            # If in the same region, try to find a direct path
            if self.current_region_id == world.current_region_id:
                for direction, destination in room.exits.items():
                    if destination == world.current_room_id:
                        best_direction = direction
                        break
            
            # If no direct path or different region, just pick a random exit
            if not best_direction:
                exits = list(room.exits.keys())
                if exits:
                    best_direction = random.choice(exits)
            
            # Move in the chosen direction
            if best_direction:
                destination = room.exits[best_direction]
                old_room_id = self.current_room_id
                
                # Handle region transitions
                if ":" in destination:
                    new_region_id, new_room_id = destination.split(":")
                    self.current_region_id = new_region_id
                    self.current_room_id = new_room_id
                else:
                    self.current_room_id = destination
                    
                # Check if the player is in the room to see the NPC leave
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == old_room_id):
                    message = f"{self.name} leaves to the {best_direction}."
                    return message
                    
                # Check if the player is in the destination room to see the NPC arrive
                if (world.current_region_id == self.current_region_id and 
                    world.current_room_id == destination):
                    message = f"{self.name} arrives from the {self._reverse_direction(best_direction)}."
                    return message
                
                self.last_moved = current_time
                
        return None

"""
npcs/npc_factory.py
NPC Factory for the MUD game.
Creates NPCs from templates and manages NPC instances.
"""
from typing import Dict, List, Optional, Any
from npcs.npc import NPC
from items.item import ItemFactory


class NPCFactory:
    """Factory class for creating NPCs from templates."""
    
    # Template library
    _templates = {
        "shopkeeper": {
            "name": "Shopkeeper",
            "description": "A friendly merchant with various goods to sell.",
            "health": 100,
            "friendly": True,
            "behavior_type": "stationary",
            "dialog": {
                "greeting": "Welcome to my shop! What can I help you with?",
                "buy": "I have many items for sale. What would you like to buy?",
                "sell": "I'll give you a fair price for your items.",
                "goods": "I have various goods for sale. Take a look!",
                "price": "All my prices are fair and reasonable.",
                "haggle": "I don't haggle, my prices are already quite fair."
            },
            "default_dialog": "The {name} doesn't seem interested in that topic."
        },
        
        "guard": {
            "name": "Guard",
            "description": "A vigilant guard patrolling the area.",
            "health": 150,
            "friendly": True,
            "behavior_type": "patrol",
            "dialog": {
                "greeting": "Greetings, citizen. All is well, I hope?",
                "trouble": "Report any trouble you see, and I'll handle it.",
                "law": "Keep the peace and we'll get along just fine.",
                "directions": "I know this area well. Where are you trying to go?",
                "threat": "I'm watching you. Don't cause any trouble."
            },
            "default_dialog": "The {name} nods but doesn't respond."
        },
        
        "villager": {
            "name": "Villager",
            "description": "A simple villager going about their business.",
            "health": 80,
            "friendly": True,
            "behavior_type": "wanderer",
            "wander_chance": 0.4,
            "dialog": {
                "greeting": "Hello there! Nice day, isn't it?",
                "weather": "The weather has been quite typical for this time of year.",
                "news": "I haven't heard anything interesting lately.",
                "gossip": "Well, between you and me, there have been some strange happenings...",
                "life": "Life is simple here, but I enjoy it."
            },
            "default_dialog": "The {name} shrugs."
        },
        
        "quest_giver": {
            "name": "Village Elder",
            "description": "An elderly person with an air of wisdom and authority.",
            "health": 70,
            "friendly": True,
            "behavior_type": "scheduled",
            "dialog": {
                "greeting": "Ah, a traveler! Welcome to our humble village.",
                "quest": "We have a problem that needs solving. Are you interested in helping?",
                "reward": "Help us and you'll be well rewarded, I assure you.",
                "history": "This village has stood for generations. Let me tell you about it...",
                "advice": "Listen carefully to what the locals tell you. They know this area well."
            },
            "default_dialog": "The {name} ponders for a moment but doesn't respond to that."
        },
        
        "bartender": {
            "name": "Bartender",
            "description": "A friendly bartender serving drinks and tales.",
            "health": 90,
            "friendly": True,
            "behavior_type": "stationary",
            "dialog": {
                "greeting": "Welcome to my tavern! What'll it be?",
                "drink": "I've got ale, wine, and mead. What's your poison?",
                "rumors": "I hear all sorts of things in this place. Like just yesterday...",
                "news": "News? Well, they say the mountain pass has been having trouble with bandits.",
                "gossip": "I don't like to gossip... but between us..."
            },
            "default_dialog": "The {name} wipes a glass clean but doesn't respond."
        },
        
        "hostile_bandit": {
            "name": "Bandit",
            "description": "A rough-looking character with weapons at the ready.",
            "health": 80,
            "friendly": False,
            "behavior_type": "wanderer",
            "wander_chance": 0.3,
            "dialog": {
                "greeting": "Your money or your life!",
                "threat": "Don't try anything stupid if you want to live.",
                "mercy": "Maybe I'll let you go if you give me something valuable...",
                "fight": "You want a fight? I'll be happy to oblige!",
                "flee": "This isn't worth my time. I'm out of here!"
            },
            "default_dialog": "The {name} snarls threateningly."
        }
    }
    
    @classmethod
    def create_npc(cls, template_name: str, **kwargs) -> Optional[NPC]:
        """
        Create an NPC from a template.
        
        Args:
            template_name: The name of the template to use.
            **kwargs: Additional arguments to override template values.
            
        Returns:
            An NPC instance, or None if the template doesn't exist.
        """
        if template_name not in cls._templates:
            return None
            
        # Start with the template
        template = cls._templates[template_name].copy()
        
        # Override with any provided values
        template.update(kwargs)
        
        # Create the NPC
        npc = NPC(
            npc_id=template.get("npc_id"),
            name=template.get("name", "Unknown NPC"),
            description=template.get("description", "No description"),
            health=template.get("health", 100),
            friendly=template.get("friendly", True)
        )
        
        # Set behavior properties
        npc.behavior_type = template.get("behavior_type", "stationary")
        npc.patrol_points = template.get("patrol_points", [])
        npc.wander_chance = template.get("wander_chance", 0.3)
        npc.schedule = template.get("schedule", {})
        npc.follow_target = template.get("follow_target")
        
        # Set dialog
        npc.dialog = template.get("dialog", {})
        npc.default_dialog = template.get("default_dialog", "The {name} doesn't respond.")
        
        # Add items to inventory if specified
        if "inventory_items" in template:
            for item_data in template["inventory_items"]:
                item = ItemFactory.from_dict(item_data)
                quantity = item_data.get("quantity", 1)
                npc.inventory.add_item(item, quantity)
        
        return npc
    
    @classmethod
    def get_template_names(cls) -> List[str]:
        """
        Get a list of available template names.
        
        Returns:
            A list of template names.
        """
        return list(cls._templates.keys())
    
    @classmethod
    def get_template(cls, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a copy of a template.
        
        Args:
            template_name: The name of the template.
            
        Returns:
            A copy of the template, or None if it doesn't exist.
        """
        if template_name not in cls._templates:
            return None
            
        return cls._templates[template_name].copy()
    
    @classmethod
    def add_template(cls, name: str, template: Dict[str, Any]) -> None:
        """
        Add a new template or update an existing one.
        
        Args:
            name: The name of the template.
            template: The template data.
        """
        cls._templates[name] = template.copy()

"""
plugins/event_system.py
Event system for the MUD game.
Provides a centralized way for plugins and game components to communicate.
"""
from typing import Dict, List, Any, Callable, Set


class EventSystem:
    """
    Centralized event system for game-wide communication.
    
    This allows components to communicate without direct dependencies.
    Components can publish events and subscribe to events from other components.
    """
    
    def __init__(self):
        """Initialize the event system."""
        self.subscribers: Dict[str, List[Callable]] = {}
        self.event_history: Dict[str, Any] = {}  # Last value for each event type
    
    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Subscribe to an event type.
        
        Args:
            event_type: The type of event to subscribe to.
            callback: The function to call when the event occurs.
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        
        if callback not in self.subscribers[event_type]:
            self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable) -> None:
        """
        Unsubscribe from an event type.
        
        Args:
            event_type: The type of event to unsubscribe from.
            callback: The callback to remove.
        """
        if event_type in self.subscribers and callback in self.subscribers[event_type]:
            self.subscribers[event_type].remove(callback)
            
            # Clean up empty event types
            if not self.subscribers[event_type]:
                self.subscribers.pop(event_type)
    
    def publish(self, event_type: str, data: Any = None) -> None:
        """
        Publish an event.
        
        Args:
            event_type: The type of event to publish.
            data: The event data.
        """
        # Store the event in history
        self.event_history[event_type] = data
        
        # Notify subscribers
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(event_type, data)
                except Exception as e:
                    print(f"Error in event callback for {event_type}: {e}")
    
    def get_last_event_data(self, event_type: str, default: Any = None) -> Any:
        """
        Get the data from the last occurrence of an event type.
        
        Args:
            event_type: The event type to get data for.
            default: Default value if no event of this type has occurred.
            
        Returns:
            The event data, or default if no such event has occurred.
        """
        return self.event_history.get(event_type, default)
    
    def clear_history(self, event_types: Set[str] = None) -> None:
        """
        Clear event history.
        
        Args:
            event_types: Set of event types to clear. If None, clear all.
        """
        if event_types is None:
            self.event_history.clear()
        else:
            for event_type in event_types:
                if event_type in self.event_history:
                    self.event_history.pop(event_type)

"""
plugins/plugin_system.py
Updated Plugin system for the MUD game.
Provides infrastructure for loading and managing plugins.
"""
import json
from typing import Dict, List, Any, Callable, Optional
import importlib
import os
import sys
import inspect

from commands.command_system import get_registered_commands, unregister_plugin_commands
from plugins.event_system import EventSystem
from plugins.world_data_provider import WorldDataProvider
from plugins.service_locator import ServiceLocator, get_service_locator

class PluginManager:
    def __init__(self, world=None, command_processor=None):
        self.world = world
        self.command_processor = command_processor
        self.plugins: Dict[str, Any] = {}  # Plugin ID to instance mapping
        self.hooks: Dict[str, List[Callable]] = {}  # Hook name to callbacks

        # Event system for loosely coupled communication
        self.event_system = EventSystem()
        # World data provider for standardized data access
        self.world_data_provider = WorldDataProvider(world, self.event_system)
        # register services
        self.service_locator = get_service_locator()
        self.service_locator.register_service("event_system", self.event_system)
        self.service_locator.register_service("data_provider", self.world_data_provider)        
        self.service_locator.register_service("plugin_manager", self)
        
        if world:
            self.service_locator.register_service("world", world)
        if command_processor:
            self.service_locator.register_service("command_processor", command_processor)
        
        # Event callbacks
        self.on_tick_callbacks = []
        self.on_room_enter_callbacks = []
        self.on_room_exit_callbacks = []
        self.on_command_callbacks = []
        
        # Initialize plugin path
        self.plugin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins")
        if self.plugin_path not in sys.path:
            sys.path.append(self.plugin_path)
    
    def register_hook(self, hook_name: str, callback: Callable) -> None:
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(callback)
    
    def call_hook(self, hook_name: str, *args, **kwargs) -> List[Any]:
        results = []
        for callback in self.hooks.get(hook_name, []):
            try:
                result = callback(*args, **kwargs)
                results.append(result)
            except Exception as e:
                print(f"Error in plugin hook {hook_name}: {e}")
        return results
    
    def discover_plugins(self) -> List[str]:
        plugin_modules = []
        
        # Ensure the plugins directory exists
        os.makedirs(self.plugin_path, exist_ok=True)
        
        # First check for direct plugin directories
        for dirname in os.listdir(self.plugin_path):
            full_dir_path = os.path.join(self.plugin_path, dirname)
            init_file = os.path.join(full_dir_path, "__init__.py")
            
            # Check if it's a directory with an __init__.py file
            if os.path.isdir(full_dir_path) and os.path.exists(init_file):
                # Skip standard Python package directories
                if dirname != "__pycache__":
                    plugin_modules.append(dirname)
        
        print(f"Discovered plugin modules: {plugin_modules}")
        return plugin_modules

    def load_plugin(self, plugin_name: str) -> bool:
        try:
            # Import the plugin module
            module = importlib.import_module(f"plugins.{plugin_name}")
            
            # Find the plugin class
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    hasattr(obj, "plugin_id") and
                    obj.__module__ == module.__name__):
                    plugin_class = obj
                    break
            
            if plugin_class is None:
                print(f"No plugin class found in {plugin_name}")
                return False
            
            # Check if plugin is already loaded
            if plugin_class.plugin_id in self.plugins:
                print(f"Plugin {plugin_class.plugin_id} is already loaded")
                return True
            
            # Get constructor parameters
            params = inspect.signature(plugin_class.__init__).parameters
            
            # Prepare kwargs dict based on available parameters
            kwargs = {}
            
            # Add standard dependencies if parameter exists
            if "world" in params:
                kwargs["world"] = self.world
            if "command_processor" in params:
                kwargs["command_processor"] = self.command_processor
            if "event_system" in params:
                kwargs["event_system"] = self.event_system
            if "data_provider" in params:
                kwargs["data_provider"] = self.world_data_provider
            if "service_locator" in params:
                kwargs["service_locator"] = self.service_locator
            
            # Create an instance of the plugin with appropriate parameters
            plugin = plugin_class(**kwargs)
            
            # Initialize the plugin
            if hasattr(plugin, "initialize"):
                plugin.initialize()
            
            # Register plugin as service
            self.service_locator.register_service(f"plugin:{plugin.plugin_id}", plugin)
            
            # Store the plugin
            self.plugins[plugin.plugin_id] = plugin
            
            # Register plugin hooks
            if hasattr(plugin, "register_hooks"):
                plugin.register_hooks(self)
            
            # Log success
            print(f"Loaded plugin: {plugin.plugin_id}")
            
            # Publish plugin loaded event
            self.event_system.publish("plugin_loaded", {
                "plugin_id": plugin.plugin_id,
                "plugin_name": getattr(plugin, "plugin_name", plugin.plugin_id)
            })
            
            return True
            
        except Exception as e:
            print(f"Error loading plugin {plugin_name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_all_plugins(self) -> None:
        for plugin_name in self.discover_plugins():
            if plugin_name != "plugin_system":  # Don't try to load the system itself
                self.load_plugin(plugin_name)
    
    def unload_plugin(self, plugin_id: str) -> bool:
        if plugin_id not in self.plugins:
            return False
        
        plugin = self.plugins[plugin_id]
        
        # Call plugin cleanup method if it exists
        if hasattr(plugin, "cleanup"):
            try:
                plugin.cleanup()
            except Exception as e:
                print(f"Error cleaning up plugin {plugin_id}: {e}")
        
        # Remove plugin hooks
        for hook_name, callbacks in self.hooks.items():
            self.hooks[hook_name] = [cb for cb in callbacks 
                                if not hasattr(cb, "__self__") or 
                                cb.__self__ is not plugin]
        
        # Remove plugin commands
        unregister_plugin_commands(plugin_id)
        
        # Unregister plugin as a service
        self.service_locator.unregister_service(f"plugin:{plugin_id}")
        
        # Remove plugin from loaded plugins
        self.plugins.pop(plugin_id)
        
        # Publish plugin unloaded event
        self.event_system.publish("plugin_unloaded", {
            "plugin_id": plugin_id
        })
        
        print(f"Unloaded plugin: {plugin_id}")
        return True
    
    def unload_all_plugins(self) -> None:
        for plugin_id in list(self.plugins.keys()):
            self.unload_plugin(plugin_id)
    
    def get_plugin(self, plugin_id: str) -> Optional[Any]:
        return self.plugins.get(plugin_id)
    
    def on_tick(self, current_time: float) -> None:
        # Call on_tick method of all plugins
        for plugin in self.plugins.values():
            self._safe_call(plugin, "on_tick", current_time)
        
        # Call tick hook callbacks
        self.call_hook("on_tick", current_time)
                    
    def on_room_enter(self, region_id: str, room_id: str) -> None:
        # Call on_room_enter method of all plugins
        for plugin in self.plugins.values():
            self._safe_call(plugin, "on_room_enter", region_id, room_id)
        
        # Call room_enter hook callbacks
        self.call_hook("on_room_enter", region_id, room_id)
                    
    def on_room_exit(self, region_id: str, room_id: str) -> None:
        # Call on_room_exit method of all plugins
        for plugin in self.plugins.values():
            self._safe_call(plugin, "on_room_exit", region_id, room_id)
        
        # Call room_exit hook callbacks
        self.call_hook("on_room_exit", region_id, room_id)
                        
    def on_command(self, command: str, args: List[str], context: Any) -> None:
        # Call on_command method of all plugins
        for plugin in self.plugins.values():
            self._safe_call(plugin, "on_command", command, args, context)
        
        # Call command hook callbacks
        self.call_hook("on_command", command, args, context)

    def broadcast_message(self, message: str) -> None:
        if self.event_system:
            self.event_system.publish("display_message", message)

    def _safe_call(self, plugin, method_name, *args, **kwargs):
        """
        Safely call a plugin method with error handling.
        
        Args:
            plugin: The plugin instance.
            method_name: The name of the method to call.
            *args: Arguments to pass to the method.
            **kwargs: Keyword arguments to pass to the method.
            
        Returns:
            The result of the method call, or None if an error occurred.
        """
        if not hasattr(plugin, method_name):
            return None
            
        method = getattr(plugin, method_name)
        if not callable(method):
            return None
            
        try:
            return method(*args, **kwargs)
        except Exception as e:
            print(f"Error in plugin {plugin.plugin_id} {method_name}: {e}")
            import traceback
            traceback.print_exc()
            return None


# Modified plugin_system.py (simplified PluginBase)
class PluginBase:
    plugin_id = "base_plugin"
    plugin_name = "Base Plugin"
    
    def __init__(self, world=None, command_processor=None, event_system=None):
        self.world = world
        self.command_processor = command_processor
        self.event_system = event_system
        self.config = self.load_config()
    
    def load_config(self):
        # Default implementation loads config from JSON file
        config_path = os.path.join(os.path.dirname(__file__), 
                                  f"{self.plugin_id}/config.json")
        
        # Load defaults from config.py if it exists
        try:
            module_name = f"plugins.{self.plugin_id}.config"
            config_module = importlib.import_module(module_name)
            default_config = getattr(config_module, "DEFAULT_CONFIG", {})
        except (ImportError, AttributeError):
            default_config = {}
        
        # Override with JSON if it exists
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    user_config = json.load(f)
                default_config.update(user_config)
            except Exception as e:
                print(f"Error loading config for {self.plugin_id}: {e}")
        
        return default_config
    
    def initialize(self):
        pass
    
    def cleanup(self):
        pass


# Create plugin directory if it doesn't exist
def ensure_plugin_directory():
    """Ensure the plugins directory exists."""
    # Get the directory of this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get the parent directory (should be the game root)
    parent_dir = os.path.dirname(current_dir)
    
    # Create the plugins directory if it doesn't exist
    plugins_dir = os.path.join(parent_dir, "plugins")
    os.makedirs(plugins_dir, exist_ok=True)
    
    # Create an __init__.py file in the plugins directory
    init_file = os.path.join(plugins_dir, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("# Plugins package\n")

# Call this when the module is imported
ensure_plugin_directory()


from typing import Callable, List, Dict, Any, Optional
import inspect
from commands.command_system import command, unregister_plugin_commands, registered_commands

def register_plugin_command(plugin_id: str, name: str, handler: Callable, 
                          aliases: List[str] = None, category: str = "other", 
                          help_text: str = "No help available.") -> bool:
    """
    Register a command for a plugin.
    
    Args:
        plugin_id: The ID of the plugin registering the command.
        name: The name of the command.
        handler: The function that handles the command.
        aliases: Alternative names for the command.
        category: The category of the command.
        help_text: Help text for the command.
        
    Returns:
        True if the command was registered, False otherwise.
    """
    # Check if command already exists
    if name in registered_commands and registered_commands[name].get("plugin_id") != plugin_id:
        # Command exists and is owned by a different plugin or the core system
        return False
    
    # Wrap the handler in the command decorator
    decorated_handler = command(
        name=name,
        aliases=aliases or [],
        category=category,
        help_text=help_text,
        plugin_id=plugin_id
    )(handler)
    
    # The command decorator automatically registers the command
    return True

def get_plugin_commands(plugin_id: str) -> List[Dict[str, Any]]:
    """
    Get all commands registered by a plugin.
    
    Args:
        plugin_id: The ID of the plugin.
        
    Returns:
        A list of command data dictionaries.
    """
    plugin_cmds = []
    
    for cmd_name, cmd_data in registered_commands.items():
        if cmd_data.get("plugin_id") == plugin_id and cmd_data["name"] == cmd_name:
            # Only include primary command names, not aliases
            plugin_cmds.append(cmd_data)
    
    return plugin_cmds

def unregister_all_plugin_commands(plugin_id: str) -> int:
    """
    Unregister all commands for a plugin.
    
    Args:
        plugin_id: The ID of the plugin.
        
    Returns:
        Number of commands unregistered.
    """
    return unregister_plugin_commands(plugin_id)

def get_plugin_commands(plugin_id: str) -> List[Dict[str, Any]]:
    """
    Get all commands registered by a plugin.
    
    Args:
        plugin_id: The ID of the plugin.
        
    Returns:
        A list of command data dictionaries.
    """
    plugin_cmds = []
    
    for cmd_name, cmd_data in registered_commands.items():
        if cmd_data.get("plugin_id") == plugin_id and cmd_data["name"] == cmd_name:
            # Only include primary command names, not aliases
            plugin_cmds.append(cmd_data)
    
    return plugin_cmds

def has_plugin_command(plugin_id: str, command_name: str) -> bool:
    """
    Check if a plugin has registered a specific command.
    
    Args:
        plugin_id: The ID of the plugin.
        command_name: The name of the command.
        
    Returns:
        True if the plugin has registered the command, False otherwise.
    """
    if command_name not in registered_commands:
        return False
        
    return registered_commands[command_name].get("plugin_id") == plugin_id

def wrap_plugin_command_handler(plugin_id: str, handler: Callable) -> Callable:
    """
    Wrap a plugin command handler with error handling and plugin context.
    
    Args:
        plugin_id: The ID of the plugin.
        handler: The command handler function.
        
    Returns:
        A wrapped handler function.
    """
    def wrapper(args, context):
        try:
            # Add plugin_id to context
            context["plugin_id"] = plugin_id
            
            # Call the original handler
            return handler(args, context)
        except Exception as e:
            # Handle errors
            import traceback
            traceback.print_exc()
            return f"Error in plugin command: {str(e)}"
    
    return wrapper

"""
plugins/service_locator.py
Service locator for plugin dependencies.

This implements the service locator pattern to further reduce coupling
between plugins and other components.
"""
from typing import Dict, Any, Optional, Type, List
import inspect


class ServiceNotFoundException(Exception):
    """Exception raised when a requested service is not found."""
    pass


class ServiceLocator:
    """
    Service locator for finding and using services.
    
    This provides a central registry of services that plugins can use
    without directly depending on specific implementations.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'ServiceLocator':
        """
        Get the singleton instance of the service locator.
        
        Returns:
            The service locator instance.
        """
        if cls._instance is None:
            cls._instance = ServiceLocator()
        return cls._instance
    
    def __init__(self):
        """Initialize the service locator."""
        self._services: Dict[str, Any] = {}
        self._service_by_type: Dict[Type, str] = {}
    
    def register_service(self, service_name: str, service: Any) -> None:
        """
        Register a service with the locator.
        
        Args:
            service_name: The name of the service.
            service: The service instance.
        """
        self._services[service_name] = service
        
        # Register by type for type-based lookups
        if service is not None:
            self._service_by_type[type(service)] = service_name
    
    def get_service(self, service_name: str) -> Any:
        """
        Get a service by name.
        
        Args:
            service_name: The name of the service.
            
        Returns:
            The service instance.
            
        Raises:
            ServiceNotFoundException: If the service is not found.
        """
        if service_name in self._services:
            return self._services[service_name]
        raise ServiceNotFoundException(f"Service '{service_name}' not found")
    
    def get_service_by_type(self, service_type: Type) -> Any:
        """
        Get a service by type.
        
        Args:
            service_type: The type of the service.
            
        Returns:
            The service instance.
            
        Raises:
            ServiceNotFoundException: If no service of the given type is found.
        """
        for service_name, service in self._services.items():
            if isinstance(service, service_type):
                return service
        raise ServiceNotFoundException(f"No service of type '{service_type.__name__}' found")
    
    def get_all_services(self) -> Dict[str, Any]:
        """
        Get all registered services.
        
        Returns:
            A dictionary of service names to service instances.
        """
        return self._services.copy()
    
    def unregister_service(self, service_name: str) -> None:
        """
        Unregister a service.
        
        Args:
            service_name: The name of the service to unregister.
        """
        if service_name in self._services:
            service = self._services[service_name]
            self._services.pop(service_name)
            
            # Also remove from type mapping
            for service_type, name in list(self._service_by_type.items()):
                if name == service_name:
                    self._service_by_type.pop(service_type)
    
    def has_service(self, service_name: str) -> bool:
        """
        Check if a service exists.
        
        Args:
            service_name: The name of the service.
            
        Returns:
            True if the service exists, False otherwise.
        """
        return service_name in self._services
    
    def get_service_names(self) -> List[str]:
        """
        Get a list of all registered service names.
        
        Returns:
            A list of service names.
        """
        return list(self._services.keys())


# Helper function to get service locator instance
def get_service_locator() -> ServiceLocator:
    """
    Get the service locator instance.
    
    Returns:
        The service locator instance.
    """
    return ServiceLocator.get_instance()

"""
plugins/world_data_provider.py
Provides a standardized interface for accessing world data.
"""
from typing import Dict, Any, Optional, List, Tuple


class WorldDataProvider:
    """
    Provides a standardized way to access world data for plugins.
    
    This reduces direct coupling between plugins and the world model.
    """
    
    def __init__(self, world=None, event_system=None):
        """
        Initialize the world data provider.
        
        Args:
            world: The game world object.
            event_system: The event system for communication.
        """
        self.world = world
        self.event_system = event_system
        
        # Cache for frequently accessed data
        self._cache = {}
        
        # Register for events that would invalidate cache
        if event_system:
            event_system.subscribe("room_changed", self._invalidate_location_cache)
    
    def get_current_location(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Get the player's current location.
        
        Returns:
            A tuple of (region_id, room_id).
        """
        if not self.world:
            return None, None
        
        return self.world.current_region_id, self.world.current_room_id
    
    def get_current_room_properties(self) -> Dict[str, Any]:
        """
        Get properties of the current room.
        
        Returns:
            A dictionary of room properties.
        """
        if not self.world:
            return {}
        
        room = self.world.get_current_room()
        if not room:
            return {}
        
        return getattr(room, "properties", {})
    
    def is_outdoors_or_has_windows(self) -> bool:
        """
        Check if the current room is outdoors or has windows.
        
        Returns:
            True if outdoors or has windows, False otherwise.
        """
        properties = self.get_current_room_properties()
        return properties.get("outdoors", False) or properties.get("has_windows", False)
    
    def get_npcs_in_current_room(self) -> List[Dict[str, Any]]:
        """
        Get NPCs in the current room.
        
        Returns:
            A list of NPC data dictionaries.
        """
        if not self.world:
            return []
        
        npcs = self.world.get_current_room_npcs()
        return [self._npc_to_dict(npc) for npc in npcs]
    
    def get_items_in_current_room(self) -> List[Dict[str, Any]]:
        """
        Get items in the current room.
        
        Returns:
            A list of item data dictionaries.
        """
        if not self.world:
            return []
        
        items = self.world.get_items_in_current_room()
        return [self._item_to_dict(item) for item in items]
    
    def get_npc_by_id(self, npc_id: str) -> Optional[Dict[str, Any]]:
        """
        Get NPC data by ID.
        
        Args:
            npc_id: The ID of the NPC.
            
        Returns:
            NPC data dictionary, or None if not found.
        """
        if not self.world:
            return None
            
        npc = self.world.get_npc(npc_id)
        if not npc:
            return None
            
        return self._npc_to_dict(npc)
    
    def get_all_npcs(self) -> List[Dict[str, Any]]:
        """
        Get all NPCs in the world.
        
        Returns:
            A list of NPC data dictionaries.
        """
        if not self.world or not hasattr(self.world, "npcs"):
            return []
            
        return [self._npc_to_dict(npc) for npc in self.world.npcs.values()]
    
    def _npc_to_dict(self, npc) -> Dict[str, Any]:
        """
        Convert an NPC object to a dictionary.
        
        Args:
            npc: The NPC object.
            
        Returns:
            A dictionary representation of the NPC.
        """
        return {
            "id": npc.npc_id,
            "name": npc.name,
            "description": npc.description,
            "region_id": npc.current_region_id,
            "room_id": npc.current_room_id,
            "friendly": getattr(npc, "friendly", True),
            "ai_state": getattr(npc, "ai_state", {}),
            # Add other properties as needed
        }
    
    def _item_to_dict(self, item) -> Dict[str, Any]:
        """
        Convert an item object to a dictionary.
        
        Args:
            item: The item object.
            
        Returns:
            A dictionary representation of the item.
        """
        return {
            "id": item.item_id,
            "name": item.name,
            "description": item.description,
            "weight": getattr(item, "weight", 0),
            "value": getattr(item, "value", 0),
            "properties": getattr(item, "properties", {}),
            # Add other properties as needed
        }
    
    def _invalidate_location_cache(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Invalidate location-related cache when location changes.
        
        Args:
            event_type: The event type.
            data: The event data.
        """
        # Clear relevant cache entries
        for key in list(self._cache.keys()):
            if key.startswith("location_") or key.startswith("room_"):
                self._cache.pop(key)

# Plugins package

"""
plugins/debug_plugin/commands.py
Command module for the Debug plugin.
"""
from plugins.plugin_system import register_plugin_command
import random

def register_commands(plugin):
    """Register debug plugin commands."""
    
    def debug_command_handler(args, context):
        """Debug command handler."""
        if not args:
            return "Debug plugin commands:\n" + "\n".join([
                f"- {cmd}" for cmd in plugin.config["debug_commands"]
            ])
        
        subcommand = args[0].lower()
        subargs = args[1:]
        
        # Handle subcommands
        if subcommand == "on":
            return plugin.enable_debug_mode()
        elif subcommand == "off":
            return plugin.disable_debug_mode()
        elif subcommand == "status":
            services = plugin.service_locator.get_service_names() if plugin.service_locator else []
            return f"Debug status:\n- Debug mode: {plugin.debug_mode_enabled}\n- Available services: {', '.join(services)}"
        else:
            return f"Unknown debug subcommand: {subcommand}"
    
    def settime_command_handler(args, context):
        """Set time command handler."""
        # Get time plugin
        time_plugin = plugin.get_service("plugin:time_plugin")
        if not time_plugin:
            return "Time plugin not found"
        
        if not args:
            return "Usage: settime <hour> [minute] or settime <period> (dawn/day/dusk/night)"
        
        # Check if setting time period
        if args[0].lower() in plugin.config["available_time_periods"]:
            period = args[0].lower()
            
            # Map periods to hours
            period_hours = {
                "dawn": time_plugin.config["dawn_hour"],
                "day": time_plugin.config["day_hour"],
                "dusk": time_plugin.config["dusk_hour"],
                "night": time_plugin.config["night_hour"]
            }
            
            # Update the time by directly modifying the game_time
            # Calculate minutes since start of day
            minutes_since_day_start = period_hours[period] * 60
            
            # Calculate current day in minutes
            current_day_minutes = (time_plugin.day - 1) * 24 * 60
            current_month_minutes = (time_plugin.month - 1) * time_plugin.config["days_per_month"] * 24 * 60
            current_year_minutes = (time_plugin.year - 1) * time_plugin.config["months_per_year"] * time_plugin.config["days_per_month"] * 24 * 60
            
            # Set game_time to keep the current date but change the time
            time_plugin.game_time = (current_year_minutes + current_month_minutes + current_day_minutes + minutes_since_day_start) * 60
            
            # Update hour and minute
            time_plugin.hour = period_hours[period]
            time_plugin.minute = 0
            
            # Update time period and all data
            time_plugin._update_time_period()
            time_plugin._update_world_time_data()
            
            # Force an update
            time_plugin._on_tick("force_update", None)
            
            return f"Time set to {period} ({time_plugin.hour:02d}:00)"
        
        # Otherwise, set specific hour/minute
        try:
            hour = int(args[0])
            if hour < 0 or hour > 23:
                return "Hour must be between 0 and 23"
            
            minute = 0
            if len(args) > 1:
                minute = int(args[1])
                if minute < 0 or minute > 59:
                    return "Minute must be between 0 and 59"
            
            # Same process but with specified hours and minutes
            # Calculate minutes since start of day
            minutes_since_day_start = hour * 60 + minute
            
            # Calculate current day in minutes
            current_day_minutes = (time_plugin.day - 1) * 24 * 60
            current_month_minutes = (time_plugin.month - 1) * time_plugin.config["days_per_month"] * 24 * 60
            current_year_minutes = (time_plugin.year - 1) * time_plugin.config["months_per_year"] * time_plugin.config["days_per_month"] * 24 * 60
            
            # Set game_time to keep the current date but change the time
            time_plugin.game_time = (current_year_minutes + current_month_minutes + current_day_minutes + minutes_since_day_start) * 60
            
            # Update hour and minute directly
            time_plugin.hour = hour
            time_plugin.minute = minute
            
            # Update time period
            old_period = time_plugin.current_time_period
            time_plugin._update_time_period()
            time_plugin._update_world_time_data()
            
            # Force an update
            time_plugin._on_tick("force_update", None)
            
            return f"Time set to {hour:02d}:{minute:02d} ({time_plugin.current_time_period})"
        except ValueError:
            return "Invalid time format. Use: settime <hour> [minute] or settime <period>"
    
    def setweather_command_handler(args, context):
        """Set weather command handler."""
        # Get weather plugin
        weather_plugin = plugin.get_service("plugin:weather_plugin")
        if not weather_plugin:
            return "Weather plugin not found"
        
        if not args:
            available = ", ".join(plugin.config["available_weather_types"])
            return f"Usage: setweather <type> [intensity]\nAvailable types: {available}\nIntensities: mild, moderate, strong, severe"
        
        weather_type = args[0].lower()
        if weather_type not in plugin.config["available_weather_types"]:
            available = ", ".join(plugin.config["available_weather_types"])
            return f"Invalid weather type. Available types: {available}"
        
        intensity = "moderate"
        if len(args) > 1 and args[1] in ["mild", "moderate", "strong", "severe"]:
            intensity = args[1]
        
        # Update the weather
        old_weather = weather_plugin.current_weather
        old_intensity = weather_plugin.current_intensity
        
        weather_plugin.current_weather = weather_type
        weather_plugin.current_intensity = intensity
        
        # Make sure to update world state
        if weather_plugin.world:
            weather_plugin.world.set_plugin_data(weather_plugin.plugin_id, "current_weather", weather_type)
            weather_plugin.world.set_plugin_data(weather_plugin.plugin_id, "current_intensity", intensity)
        
        # Ensure notification event is triggered to update UI
        if weather_plugin.event_system:
            description = weather_plugin.config["weather_descriptions"].get(
                weather_type, 
                "The weather is changing."
            )
            
            weather_plugin.event_system.publish("weather_changed", {
                "weather": weather_type,
                "intensity": intensity,
                "description": description,
                "old_weather": old_weather,
                "old_intensity": old_intensity
            })
            
            # Also send display message if player is outdoors
            if weather_plugin.data_provider and weather_plugin.data_provider.is_outdoors_or_has_windows():
                message = f"The weather changes to {weather_type} ({intensity})."
                weather_plugin.event_system.publish("display_message", message)
        
        # Force a UI redraw to ensure changes are shown immediately
        plugin.force_draw_game_ui()
        
        return f"Weather set to {weather_type} ({intensity})"
    
    def teleport_command_handler(args, context):
        """Teleport command handler."""
        if not plugin.world:
            return "World not available"
        
        if not args:
            return "Usage: teleport <region_id> <room_id> or teleport <room_id> (same region)"
        
        # Store old location
        old_region_id = plugin.world.current_region_id
        old_room_id = plugin.world.current_room_id
        
        # If only one arg, assume it's a room in the current region
        if len(args) == 1:
            room_id = args[0]
            region_id = plugin.world.current_region_id
        else:
            region_id = args[0]
            room_id = args[1]
        
        # Validate region
        region = plugin.world.get_region(region_id)
        if not region:
            return f"Region '{region_id}' not found"
        
        # Validate room
        room = region.get_room(room_id)
        if not room:
            return f"Room '{room_id}' not found in region '{region_id}'"
        
        # Perform teleport
        plugin.world.current_region_id = region_id
        plugin.world.current_room_id = room_id
        
        # Notify plugins about room change if game manager is available
        if hasattr(plugin.world, "game") and hasattr(plugin.world.game, "plugin_manager"):
            # Notify about room exit
            plugin.world.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
            
            # Notify about room enter
            plugin.world.game.plugin_manager.on_room_enter(region_id, room_id)
        
        # Get room description
        return f"Teleported to {region_id}:{room_id}\n\n{plugin.world.look()}"
    
    def spawn_command_handler(args, context):
        """Spawn item or NPC command handler."""
        if not plugin.world:
            return "World not available"
        
        if not args or args[0] not in ["item", "npc"]:
            return "Usage: spawn item <item_type> [<name>] or spawn npc <template_name> [<name>]"
        
        spawn_type = args[0]
        
        if spawn_type == "item" and len(args) > 1:
            from items.item import ItemFactory
            
            item_type = args[1]
            name = " ".join(args[2:]) if len(args) > 2 else f"Debug {item_type}"
            
            try:
                # Create the item
                item = ItemFactory.create_item(item_type, name=name, description=f"A debug {item_type.lower()} item.")
                
                # Add to current room
                plugin.world.add_item_to_room(
                    plugin.world.current_region_id,
                    plugin.world.current_room_id,
                    item
                )
                
                return f"Spawned {item.name} ({item_type}) in current room"
            except Exception as e:
                return f"Error spawning item: {str(e)}"
        
        elif spawn_type == "npc" and len(args) > 1:
            from npcs.npc_factory import NPCFactory
            
            template_name = args[1]
            name = " ".join(args[2:]) if len(args) > 2 else None
            
            try:
                # Create the NPC
                npc_args = {"name": name} if name else {}
                npc = NPCFactory.create_npc(template_name, **npc_args)
                
                if not npc:
                    return f"Unknown NPC template: {template_name}"
                
                # Set NPC location to current room
                npc.current_region_id = plugin.world.current_region_id
                npc.current_room_id = plugin.world.current_room_id
                
                # Add to world
                plugin.world.add_npc(npc)
                
                return f"Spawned {npc.name} ({template_name}) in current room"
            except Exception as e:
                return f"Error spawning NPC: {str(e)}"
        
        return "Invalid spawn command"
    
    def heal_command_handler(args, context):
        """Heal player command handler."""
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        
        amount = 0
        if not args:
            # Full heal
            old_health = plugin.world.player.health
            plugin.world.player.health = plugin.world.player.max_health
            amount = plugin.world.player.health - old_health
        else:
            try:
                # Heal specific amount
                amount = int(args[0])
                old_health = plugin.world.player.health
                plugin.world.player.health = min(plugin.world.player.health + amount, plugin.world.player.max_health)
                amount = plugin.world.player.health - old_health
            except ValueError:
                return "Invalid amount. Usage: heal [amount]"
        
        return f"Healed player for {amount} health. Current health: {plugin.world.player.health}/{plugin.world.player.max_health}"
    
    def damage_command_handler(args, context):
        """Damage player command handler."""
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        
        if not args:
            return "Usage: damage <amount>"
        
        try:
            amount = int(args[0])
            if amount <= 0:
                return "Damage amount must be positive"
            
            old_health = plugin.world.player.health
            plugin.world.player.health = max(plugin.world.player.health - amount, 0)
            actual_damage = old_health - plugin.world.player.health
            
            status = f"Player took {actual_damage} damage. Current health: {plugin.world.player.health}/{plugin.world.player.max_health}"
            
            if plugin.world.player.health <= 0:
                status += "\nPlayer would be dead in a real game."
            
            return status
        except ValueError:
            return "Invalid amount. Usage: damage <amount>"
    
    def level_command_handler(args, context):
        """Level up player command handler."""
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        
        levels = 1
        if args:
            try:
                levels = int(args[0])
                if levels <= 0:
                    return "Number of levels must be positive"
            except ValueError:
                return "Invalid number. Usage: level [count]"
        
        # Store initial stats
        old_level = plugin.world.player.level
        old_max_health = plugin.world.player.max_health
        old_stats = plugin.world.player.stats.copy()
        
        # Level up the specified number of times
        for _ in range(levels):
            plugin.world.player.level_up()
        
        # Format the result
        result = f"Leveled up player from {old_level} to {plugin.world.player.level}\n"
        result += f"Health increased: {old_max_health} -> {plugin.world.player.max_health}\n"
        result += "Stats increased:\n"
        for stat_name, old_value in old_stats.items():
            new_value = plugin.world.player.stats[stat_name]
            result += f"- {stat_name}: {old_value} -> {new_value}\n"
        
        return result
    
    def give_command_handler(args, context):
        """Give item to player command handler."""
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        
        if not args or len(args) < 2:
            return "Usage: give <item_type> <name> [quantity]"
        
        from items.item import ItemFactory
        
        item_type = args[0]
        name = args[1]
        quantity = 1
        
        if len(args) > 2:
            try:
                quantity = int(args[2])
                if quantity <= 0:
                    return "Quantity must be positive"
            except ValueError:
                return "Invalid quantity. Usage: give <item_type> <name> [quantity]"
        
        try:
            # Create the item
            item = ItemFactory.create_item(item_type, name=name, description=f"A debug {item_type.lower()} item.")
            
            # Add to player inventory
            success, message = plugin.world.player.inventory.add_item(item, quantity)
            
            if success:
                return f"Added {quantity} {item.name} to player inventory"
            else:
                return f"Failed to add item: {message}"
        except Exception as e:
            return f"Error creating item: {str(e)}"
    
    def setstats_command_handler(args, context):
        """Set player stats command handler."""
        if not plugin.world or not plugin.world.player:
            return "Player not available"
        
        if not args or len(args) % 2 != 0:
            return "Usage: setstats <stat_name> <value> [<stat_name> <value> ...]"
        
        # Parse stat pairs
        stats_updated = []
        for i in range(0, len(args), 2):
            stat_name = args[i].lower()
            try:
                value = int(args[i + 1])
                if value < 0:
                    return f"Stat value must be non-negative: {stat_name}"
                
                # Update stat if it exists
                if stat_name in plugin.world.player.stats:
                    old_value = plugin.world.player.stats[stat_name]
                    plugin.world.player.stats[stat_name] = value
                    stats_updated.append(f"{stat_name}: {old_value} -> {value}")
                else:
                    return f"Unknown stat: {stat_name}"
            except ValueError:
                return f"Invalid value for {stat_name}. Must be a number."
        
        if stats_updated:
            return "Stats updated:\n" + "\n".join(stats_updated)
        else:
            return "No stats were updated"
    
    def listregions_command_handler(args, context):
        """List regions command handler."""
        if not plugin.world:
            return "World not available"
        
        if not plugin.world.regions:
            return "No regions found in the world"
        
        result = "Regions in the world:\n"
        for region_id, region in plugin.world.regions.items():
            room_count = len(region.rooms)
            result += f"- {region_id}: {region.name} ({room_count} rooms)\n"
        
        return result
    
    def listrooms_command_handler(args, context):
        """List rooms command handler."""
        if not plugin.world:
            return "World not available"
        
        region_id = None
        if args:
            region_id = args[0]
        else:
            region_id = plugin.world.current_region_id
        
        region = plugin.world.get_region(region_id)
        if not region:
            return f"Region '{region_id}' not found"
        
        if not region.rooms:
            return f"No rooms found in region '{region_id}'"
        
        result = f"Rooms in region '{region_id}' ({region.name}):\n"
        for room_id, room in region.rooms.items():
            exits = ", ".join(room.exits.keys()) if room.exits else "none"
            current = " (current)" if plugin.world.current_region_id == region_id and plugin.world.current_room_id == room_id else ""
            result += f"- {room_id}: {room.name}{current} (Exits: {exits})\n"
        
        return result
    
    def listnpcs_command_handler(args, context):
        """List NPCs command handler."""
        if not plugin.world:
            return "World not available"
        
        if not plugin.world.npcs:
            return "No NPCs found in the world"
        
        # Filter by region/room if args provided
        if args:
            if len(args) == 1:
                # Filter by region
                region_id = args[0]
                npcs = [npc for npc in plugin.world.npcs.values() if npc.current_region_id == region_id]
                
                if not npcs:
                    return f"No NPCs found in region '{region_id}'"
                
                result = f"NPCs in region '{region_id}':\n"
                for npc in npcs:
                    result += f"- {npc.npc_id}: {npc.name} (Room: {npc.current_room_id})\n"
                
                return result
            elif len(args) == 2:
                # Filter by region and room
                region_id, room_id = args
                npcs = plugin.world.get_npcs_in_room(region_id, room_id)
                
                if not npcs:
                    return f"No NPCs found in room '{room_id}' of region '{region_id}'"
                
                result = f"NPCs in room '{room_id}' of region '{region_id}':\n"
                for npc in npcs:
                    result += f"- {npc.npc_id}: {npc.name} (Health: {npc.health}/{npc.max_health})\n"
                
                return result
        
        # List all NPCs
        result = "All NPCs in the world:\n"
        for npc_id, npc in plugin.world.npcs.items():
            result += f"- {npc_id}: {npc.name} (Location: {npc.current_region_id}:{npc.current_room_id})\n"
        
        return result
    
    def listitems_command_handler(args, context):
        """List items command handler."""
        if not plugin.world:
            return "World not available"
        
        # If no args, show items in current room
        if not args:
            items = plugin.world.get_items_in_current_room()
            
            if not items:
                return "No items in current room"
            
            result = "Items in current room:\n"
            for item in items:
                result += f"- {item.item_id}: {item.name}\n"
            
            return result
        
        # If 'player' arg, show player inventory
        if args[0] == "player":
            if not plugin.world.player.inventory:
                return "Player has no inventory"
            
            return plugin.world.player.inventory.list_items()
        
        # If region/room args, show items in that room
        if len(args) == 2:
            region_id, room_id = args
            items = plugin.world.get_items_in_room(region_id, room_id)
            
            if not items:
                return f"No items in room '{room_id}' of region '{region_id}'"
            
            result = f"Items in room '{room_id}' of region '{region_id}':\n"
            for item in items:
                result += f"- {item.item_id}: {item.name}\n"
            
            return result
        
        return "Usage: listitems [player|<region_id> <room_id>]"
    
    def time_command_handler(args, context):
        """Time command handler to display current time."""
        # Get time plugin
        time_plugin = plugin.get_service("plugin:time_plugin")
        if not time_plugin:
            return "Time plugin not found"
        
        # Format time information
        hour = time_plugin.hour
        minute = time_plugin.minute
        day = time_plugin.day
        month = time_plugin.month
        year = time_plugin.year
        period = time_plugin.current_time_period
        
        # Get day and month names
        day_idx = (day - 1) % len(time_plugin.config["day_names"])
        day_name = time_plugin.config["day_names"][day_idx]
        month_name = time_plugin.config["month_names"][month - 1]
        
        # Build response
        response = f"Current Time: {hour:02d}:{minute:02d} ({period.capitalize()})\n"
        response += f"Current Date: {day_name}, {day} {month_name}, Year {year}\n\n"
        
        # Add time periods info
        response += "Time Periods:\n"
        response += f"- Dawn: {time_plugin.config['dawn_hour']:02d}:00\n"
        response += f"- Day: {time_plugin.config['day_hour']:02d}:00\n"
        response += f"- Dusk: {time_plugin.config['dusk_hour']:02d}:00\n"
        response += f"- Night: {time_plugin.config['night_hour']:02d}:00\n"
        
        # Add update count for debugging
        if hasattr(time_plugin, "update_count"):
            response += f"\nTime updates: {time_plugin.update_count}"
        
        return response
        
    # Register the debug commands
    register_plugin_command(
        plugin.plugin_id,
        "debug",
        debug_command_handler,
        aliases=["dbg"],
        category="system",
        help_text="Control debug mode and list available debug commands.\n\nUsage: debug [on|off|status]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "time",
        time_command_handler,
        aliases=["clock"],
        category="world",
        help_text="Display the current time and date information."
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "settime",
        settime_command_handler,
        aliases=[],
        category="debug",
        help_text="Set game time.\n\nUsage: settime <hour> [minute] or settime <period> (dawn/day/dusk/night)"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "setweather",
        setweather_command_handler,
        aliases=["weather"],
        category="debug",
        help_text="Set game weather.\n\nUsage: setweather <type> [intensity]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "teleport",
        teleport_command_handler,
        aliases=["tp"],
        category="debug",
        help_text="Teleport to any room.\n\nUsage: teleport <region_id> <room_id> or teleport <room_id> (same region)"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "spawn",
        spawn_command_handler,
        aliases=["create"],
        category="debug",
        help_text="Spawn an item or NPC.\n\nUsage: spawn item <item_type> [<name>] or spawn npc <template_name> [<name>]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "heal",
        heal_command_handler,
        aliases=["restore"],
        category="debug",
        help_text="Heal the player.\n\nUsage: heal [amount]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "damage",
        damage_command_handler,
        aliases=["hurt"],
        category="debug",
        help_text="Damage the player.\n\nUsage: damage <amount>"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "level",
        level_command_handler,
        aliases=["levelup"],
        category="debug",
        help_text="Level up the player.\n\nUsage: level [count]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "give",
        give_command_handler,
        aliases=["giveitem"],
        category="debug",
        help_text="Give an item to the player.\n\nUsage: give <item_type> <name> [quantity]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "setstats",
        setstats_command_handler,
        aliases=["stats"],
        category="debug",
        help_text="Set player stats.\n\nUsage: setstats <stat_name> <value> [<stat_name> <value> ...]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listregions",
        listregions_command_handler,
        aliases=["regions"],
        category="debug",
        help_text="List all regions in the world.\n\nUsage: listregions"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listrooms",
        listrooms_command_handler,
        aliases=["rooms"],
        category="debug",
        help_text="List rooms in a region.\n\nUsage: listrooms [region_id]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listnpcs",
        listnpcs_command_handler,
        aliases=["npcs"],
        category="debug",
        help_text="List NPCs in the world.\n\nUsage: listnpcs [region_id [room_id]]"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listitems",
        listitems_command_handler,
        aliases=["items"],
        category="debug",
        help_text="List items in a location.\n\nUsage: listitems [player|<region_id> <room_id>]"
    )

"""
plugins/debug_plugin/config.py
Default configuration for the Debug plugin.
"""

DEFAULT_CONFIG = {
    # General debug settings
    "debug_message_prefix": "[DEBUG] ",
    
    # Time manipulation settings
    "available_time_periods": ["dawn", "day", "dusk", "night"],
    
    # Weather manipulation settings
    "available_weather_types": ["clear", "cloudy", "rain", "storm", "snow"],
    
    # Default values for teleport when no args provided
    "default_teleport_region": "test",
    "default_teleport_room": "entrance",
    
    # Maximum values for game mechanics
    "max_items_to_spawn": 10,
    "max_npcs_to_spawn": 5,
    
    # Available debug commands
    "debug_commands": [
        "settime", "setweather", "teleport", "spawn", 
        "heal", "damage", "level", "give", "setstats",
        "listregions", "listrooms", "listnpcs", "listitems"
    ]
}

"""
plugins/debug_plugin/__init__.py
Debug plugin for the MUD game.
Provides commands for debugging and testing the game.
"""
from plugins.plugin_system import PluginBase
from typing import Dict, Any

class DebugPlugin(PluginBase):
    """Debug tools for the MUD game."""
    
    plugin_id = "debug_plugin"
    plugin_name = "Debug Tools"
    
    def __init__(self, world=None, command_processor=None, event_system=None, data_provider=None, service_locator=None):
        """Initialize the debug plugin."""
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator
        
        # Import config from the config.py file
        from .config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG.copy()
        
        # Store the original debug mode state
        self.debug_mode_enabled = False
        if hasattr(world, "game") and hasattr(world.game, "debug_mode"):
            self.debug_mode_enabled = world.game.debug_mode
    
    def initialize(self):
        """Initialize the plugin."""
        # Register commands
        from .commands import register_commands
        register_commands(self)
        
        # Subscribe to game events if needed
        if self.event_system:
            self.event_system.subscribe("on_tick", self._on_tick)
        
        print(f"Debug plugin initialized. Debug mode: {self.debug_mode_enabled}")
    
    def _on_tick(self, event_type, data):
        """Handle tick events for debugging."""
        # Empty for now - can be used for debug logging or other debugging tasks
        pass
    
    def get_service(self, service_name):
        """Get a service from the service locator."""
        if self.service_locator:
            try:
                return self.service_locator.get_service(service_name)
            except:
                return None
        return None
        
    def force_update_time_ui(self, time_data=None):
        """Force update the game UI with new time data."""
        # Get time plugin if data not provided
        if not time_data and hasattr(self, "world") and self.world:
            time_plugin = self.get_service("plugin:time_plugin")
            if time_plugin and hasattr(time_plugin, "hour"):
                # Build time data
                time_str = f"{time_plugin.hour:02d}:{time_plugin.minute:02d}"
                day_name = time_plugin.config["day_names"][(time_plugin.day - 1) % len(time_plugin.config["day_names"])]
                month_name = time_plugin.config["month_names"][time_plugin.month - 1]
                date_str = f"{day_name}, {time_plugin.day} {month_name}, Year {time_plugin.year}"
                
                time_data = {
                    "hour": time_plugin.hour,
                    "minute": time_plugin.minute,
                    "day": time_plugin.day,
                    "month": time_plugin.month,
                    "year": time_plugin.year,
                    "day_name": day_name,
                    "month_name": month_name,
                    "time_period": time_plugin.current_time_period,
                    "time_str": time_str,
                    "date_str": date_str
                }
        
        # If we have time data and the game manager, update it directly
        if time_data and hasattr(self, "world") and self.world and hasattr(self.world, "game"):
            game_manager = self.world.game
            if hasattr(game_manager, "_on_time_data_event"):
                game_manager._on_time_data_event("time_data", time_data)
            
            # Also update the time_data directly
            if hasattr(game_manager, "time_data"):
                game_manager.time_data = time_data
                
                # Force a redraw of the game UI
                if hasattr(game_manager, "draw"):
                    try:
                        game_manager.draw()
                    except:
                        pass
                
                return True
                
        return False
        
    def force_draw_game_ui(self):
        """Force redraw of the game UI."""
        if hasattr(self, "world") and self.world and hasattr(self.world, "game"):
            game_manager = self.world.game
            if hasattr(game_manager, "draw"):
                try:
                    game_manager.draw()
                    return True
                except:
                    pass
        return False
    
    def enable_debug_mode(self):
        """Enable debug mode in the game."""
        if self.world and hasattr(self.world, "game"):
            self.world.game.debug_mode = True
            self.debug_mode_enabled = True
            return "Debug mode enabled"
        return "Could not enable debug mode"
    
    def disable_debug_mode(self):
        """Disable debug mode in the game."""
        if self.world and hasattr(self.world, "game"):
            self.world.game.debug_mode = False
            self.debug_mode_enabled = False
            return "Debug mode disabled"
        return "Could not disable debug mode"
    
    def cleanup(self):
        """Clean up plugin resources."""
        if self.event_system:
            self.event_system.unsubscribe("on_tick", self._on_tick)

"""
plugins/npc_schedule_plugin/commands.py
Command module for the Improved NPC plugin.
"""
from plugins.plugin_system import register_plugin_command

def register_commands(plugin):
    """Register plugin commands."""
    
    def force_npc_update_command(args, context):
        """Force NPC update command handler."""
        # Force NPC update
        plugin._update_npcs(force=True)
        
        # Get counts
        in_tavern = 0
        in_social = 0
        wandering = 0
        
        for npc in plugin.world.npcs.values():
            location = f"{npc.current_region_id}:{npc.current_room_id}"
            if any(location == f"{t['region_id']}:{t['room_id']}" for t in plugin.taverns):
                in_tavern += 1
            elif any(location == f"{s['region_id']}:{s['room_id']}" for s in plugin.social_areas):
                in_social += 1
            else:
                wandering += 1
        
        return f"Forced NPC update. NPCs in taverns: {in_tavern}, in social areas: {in_social}, wandering: {wandering}"
    
    def list_locations_command(args, context):
        """List NPC gathering locations command."""
        response = "NPC Gathering Locations:\n\n"
        
        if plugin.taverns:
            response += "Taverns/Inns:\n"
            for t in plugin.taverns:
                response += f"- {t['name']} (in {t['region_id']})\n"
            response += "\n"
        else:
            response += "No taverns or inns found.\n\n"
            
        if plugin.social_areas:
            response += "Social Areas:\n"
            for s in plugin.social_areas:
                response += f"- {s['name']} (in {s['region_id']})\n"
        else:
            response += "No social areas found.\n"
            
        return response
    
    def npc_activity_command(args, context):
        """Check what NPCs are doing."""
        if not args:
            return "Please specify which NPC you want to check."
        
        npc_name = " ".join(args).lower()
        found_npc = None
        
        # First try to find NPC in current room
        for npc in plugin.world.get_current_room_npcs():
            if npc_name in npc.name.lower():
                found_npc = npc
                break
        
        # If not found in current room, search all NPCs
        if not found_npc:
            for npc in plugin.world.npcs.values():
                if npc_name in npc.name.lower():
                    found_npc = npc
                    break
        
        if not found_npc:
            return f"No NPC named '{npc_name}' found."
            
        # Build response with NPC details
        activity = found_npc.ai_state.get("current_activity", "unknown")
        location = f"{found_npc.current_region_id}:{found_npc.current_room_id}"
        
        # Get room name if possible
        room_name = location
        if (found_npc.current_region_id in plugin.world.regions and 
            found_npc.current_room_id in plugin.world.regions[found_npc.current_region_id].rooms):
            room = plugin.world.regions[found_npc.current_region_id].rooms[found_npc.current_room_id]
            room_name = room.name
        
        # Determine location type
        location_type = "somewhere"
        if any(location == f"{t['region_id']}:{t['room_id']}" for t in plugin.taverns):
            location_type = "at a tavern"
        elif any(location == f"{s['region_id']}:{s['room_id']}" for s in plugin.social_areas):
            location_type = "in a social area"
        
        response = f"{found_npc.name} is currently {activity} {location_type}.\n"
        response += f"Location: {room_name}\n"
        response += f"Behavior type: {found_npc.behavior_type}\n"
        
        # Add more details
        if hasattr(found_npc, "wander_chance"):
            response += f"Movement probability: {found_npc.wander_chance * 100:.1f}%\n"
        
        if hasattr(found_npc, "dialog") and found_npc.dialog:
            response += "\nThis NPC can talk about: "
            topics = list(found_npc.dialog.keys())[:5]  # Show up to 5 topics
            response += ", ".join(topics)
            if len(found_npc.dialog) > 5:
                response += f" and {len(found_npc.dialog) - 5} more topics"
        
        return response
    
    def set_period_command(args, context):
        """Set the current period for testing."""
        if not args:
            return "Usage: setperiod <day|night>"
        
        period = args[0].lower()
        if period not in ["day", "night"]:
            return "Period must be either 'day' or 'night'"
        
        # Set the period
        plugin.current_period = period
        
        # Force update
        plugin._update_npcs(force=True)
        
        return f"Period set to {period}. NPCs will behave accordingly."
    
    # Register the commands
    register_plugin_command(
        plugin.plugin_id,
        "forcenpcupdate",
        force_npc_update_command,
        aliases=["forcenpcs"],
        category="debug",
        help_text="Force NPCs to update their positions based on the current time period."
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "listlocations",
        list_locations_command,
        aliases=["npclocs"],
        category="world",
        help_text="List all taverns and social areas where NPCs may gather."
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "npcactivity",
        npc_activity_command,
        aliases=["checkactivity"],
        category="world",
        help_text="Check what a specific NPC is currently doing.\n\nUsage: npcactivity <npc_name>"
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "setperiod",
        set_period_command,
        aliases=[],
        category="debug",
        help_text="Set the current period (day/night) for testing NPC behavior.\n\nUsage: setperiod <day|night>"
    )

"""
plugins/npc_schedule_plugin/config.py
Default configuration for the Improved NPC plugin.
"""

DEFAULT_CONFIG = {
    # Day/night settings
    "day_start_hour": 6,    # 6 AM
    "night_start_hour": 20,  # 8 PM
    
    # Movement probabilities
    "day_wander_chance": 0.3,   # 30% chance to move each update during day
    "night_wander_chance": 0.1,  # 10% chance during night
    
    # Activity descriptions
    "day_activities": [
        "wandering", "exploring", "looking around", "browsing", "working",
        "shopping", "searching", "inspecting", "studying", "observing"
    ],
    "night_activities": [
        "relaxing", "chatting", "drinking", "resting", "socializing",
        "dining", "telling stories", "listening to music", "playing games", "sleeping"
    ],
    
    # Update interval (in seconds)
    "update_interval": 30,
    
    # Room type identification keywords
    "tavern_keywords": ["tavern", "inn", "pub", "bar", "drink", "beer", "ale"],
    "social_keywords": ["hall", "square", "garden", "plaza", "center", "meeting", "gather"],
    
    # Debug mode
    "debug": False
}

"""
plugins/npc_schedule_plugin/schedule_templates.py
Creates more dynamic schedules with NPCs moving between different locations
"""
import random

def create_example_schedules(plugin):
    """Create example schedules for NPCs in the world."""
    if not plugin.world:
        return
    
    # First collect all available rooms for use in schedules
    available_rooms = collect_available_rooms(plugin.world)
    
    # Designate special rooms for common activities
    town_spaces = designate_town_spaces(plugin.world, available_rooms)
    
    # Debug information
    if hasattr(plugin.world, "game") and hasattr(plugin.world.game, "debug_mode") and plugin.world.game.debug_mode:
        debug_msg = f"Found {len(available_rooms)} total rooms and designated special locations:\n"
        for space_type, locations in town_spaces.items():
            if locations:
                sample = locations[0]
                debug_msg += f"- {space_type}: {sample['region_id']}:{sample['room_id']} and {len(locations)-1} others\n"
        
        if plugin.event_system:
            plugin.event_system.publish("display_message", debug_msg)
        
    # Find existing NPCs and create schedules based on their types
    for npc_id, npc in plugin.world.npcs.items():
        # Store original behavior
        if not hasattr(npc, "ai_state"):
            npc.ai_state = {}
        
        # Only set this if not already set
        if "original_behavior_type" not in npc.ai_state:
            npc.ai_state["original_behavior_type"] = getattr(npc, "behavior_type", "wanderer")
        
        # Create schedules based on NPC type
        if "guard" in npc_id.lower() or "guard" in npc.name.lower():
            create_guard_schedule(plugin, npc_id, town_spaces)
        elif "shopkeeper" in npc_id.lower() or "merchant" in npc.name.lower():
            create_merchant_schedule(plugin, npc_id, town_spaces)
        elif "elder" in npc_id.lower() or "elder" in npc.name.lower():
            create_elder_schedule(plugin, npc_id, town_spaces)
        elif "bartender" in npc_id.lower() or "bartender" in npc.name.lower():
            create_bartender_schedule(plugin, npc_id, town_spaces)
        elif "villager" in npc_id.lower() or "villager" in npc.name.lower():
            create_villager_schedule(plugin, npc_id, town_spaces)
        # Default schedule for other NPCs
        else:
            create_default_schedule(plugin, npc_id, town_spaces)
        
        # Now that the NPC has a schedule, set behavior type to scheduled
        npc.behavior_type = "scheduled"
        
        # Initialize current activity
        current_hour = plugin.current_hour if hasattr(plugin, "current_hour") else 12
        schedule = plugin.get_npc_schedule(npc_id)
        
        if current_hour in schedule:
            activity = schedule[current_hour].get("activity", "idle")
            npc.ai_state["current_activity"] = activity
            
            # Set specific activity flags
            for state in ["is_sleeping", "is_eating", "is_working", "is_socializing"]:
                npc.ai_state[state] = False
            
            if activity == "sleeping":
                npc.ai_state["is_sleeping"] = True
            elif activity == "eating":
                npc.ai_state["is_eating"] = True
            elif activity == "working":
                npc.ai_state["is_working"] = True
            elif activity == "socializing":
                npc.ai_state["is_socializing"] = True
            
            # Add tracking for last notification
            npc.ai_state["last_notified_activity"] = ""
        
        # Reset move cooldown to ensure immediate movement if needed
        npc.last_moved = 0

def collect_available_rooms(world):
    """Collect all available rooms in the world."""
    available_rooms = []
    
    for region_id, region in world.regions.items():
        for room_id, room in region.rooms.items():
            available_rooms.append({
                "region_id": region_id,
                "room_id": room_id,
                "room_name": room.name,
                "properties": getattr(room, "properties", {})
            })
    
    return available_rooms

def designate_town_spaces(world, available_rooms):
    """Designate special rooms for common activities."""
    # Categories we need
    town_spaces = {
        "homes": [],
        "shops": [],
        "taverns": [],
        "markets": [],
        "town_square": [],
        "gardens": [],
        "temple": [],
        "guard_posts": [],
        "work_areas": [],
        "social_areas": []
    }
    
    # First pass: identify rooms by name hints
    for room_info in available_rooms:
        room_name = room_info["room_name"].lower()
        
        if "home" in room_name or "house" in room_name or "cottage" in room_name:
            town_spaces["homes"].append(room_info)
        
        if "shop" in room_name or "store" in room_name:
            town_spaces["shops"].append(room_info)
        
        if "tavern" in room_name or "inn" in room_name or "pub" in room_name:
            town_spaces["taverns"].append(room_info)
        
        if "market" in room_name or "bazaar" in room_name:
            town_spaces["markets"].append(room_info)
        
        if "square" in room_name or "plaza" in room_name or "center" in room_name:
            town_spaces["town_square"].append(room_info)
        
        if "garden" in room_name or "park" in room_name:
            town_spaces["gardens"].append(room_info)
        
        if "temple" in room_name or "church" in room_name or "shrine" in room_name:
            town_spaces["temple"].append(room_info)
        
        if "guard" in room_name or "post" in room_name or "watch" in room_name:
            town_spaces["guard_posts"].append(room_info)
        
        if "workshop" in room_name or "forge" in room_name or "mill" in room_name:
            town_spaces["work_areas"].append(room_info)
        
        if "hall" in room_name or "social" in room_name or "meeting" in room_name:
            town_spaces["social_areas"].append(room_info)
    
    # Second pass: ensure we have at least some locations for each type
    # If not enough specific rooms, allocate some generic ones
    for space_type in town_spaces.keys():
        if len(town_spaces[space_type]) < 2:
            # For each missing type, find some suitable rooms
            available_count = min(3, len(available_rooms))  # Take up to 3 rooms
            if available_count > 0:
                selected_rooms = random.sample(available_rooms, available_count)
                town_spaces[space_type].extend(selected_rooms)
    
    # If there's a "garden" in the room names, make sure it's in the gardens category
    for room_info in available_rooms:
        if "garden" in room_info["room_name"].lower() and room_info not in town_spaces["gardens"]:
            town_spaces["gardens"].append(room_info)
    
    # If there's an "entrance" room, make sure it's in town_square
    for room_info in available_rooms:
        if "entrance" in room_info["room_id"].lower() and room_info not in town_spaces["town_square"]:
            town_spaces["town_square"].append(room_info)
    
    return town_spaces

def get_random_location(locations, exclude_region=None, exclude_room=None):
    """Get a random location, excluding specified region/room if provided."""
    if not locations:
        return None
        
    valid_locations = [loc for loc in locations 
                      if (exclude_region is None or loc["region_id"] != exclude_region) 
                      and (exclude_room is None or loc["room_id"] != exclude_room)]
    
    if valid_locations:
        return random.choice(valid_locations)
    elif locations:
        return random.choice(locations)
    else:
        return None

def create_default_schedule(plugin, npc_id, town_spaces):
    """Create a default dynamic schedule for an NPC."""
    npc = plugin.world.get_npc(npc_id)
    if not npc:
        return
    
    # Use the NPC's current room as their home
    home_region = npc.current_region_id
    home_room = npc.current_room_id
    
    # Find potential activity locations
    work_location = get_random_location(town_spaces["work_areas"], home_region, home_room)
    market_location = get_random_location(town_spaces["markets"])
    social_location = get_random_location(town_spaces["social_areas"])
    garden_location = get_random_location(town_spaces["gardens"])
    
    # If any locations weren't found, use a generic location
    if not work_location:
        work_location = {"region_id": home_region, "room_id": home_room}
    if not market_location:
        market_location = work_location
    if not social_location:
        social_location = work_location
    if not garden_location:
        garden_location = social_location
    
    # Create a dynamic schedule with movement between locations
    schedule = {
        7: {"activity": "waking up", "region_id": home_region, "room_id": home_room},
        8: {"activity": "eating", "region_id": home_region, "room_id": home_room},
        9: {"activity": "going to work", "region_id": work_location["region_id"], "room_id": work_location["room_id"]},
        10: {"activity": "working", "region_id": work_location["region_id"], "room_id": work_location["room_id"]},
        12: {"activity": "visiting the market", "region_id": market_location["region_id"], "room_id": market_location["room_id"]},
        13: {"activity": "eating", "region_id": home_region, "room_id": home_room},
        14: {"activity": "working", "region_id": work_location["region_id"], "room_id": work_location["room_id"]},
        17: {"activity": "walking in the garden", "region_id": garden_location["region_id"], "room_id": garden_location["room_id"]},
        18: {"activity": "socializing", "region_id": social_location["region_id"], "room_id": social_location["room_id"]},
        20: {"activity": "heading home", "region_id": home_region, "room_id": home_room},
        21: {"activity": "eating", "region_id": home_region, "room_id": home_room},
        22: {"activity": "sleeping", "region_id": home_region, "room_id": home_room}
    }
    
    # Set sleeping responses
    npc.ai_state["sleeping_responses"] = [
        "The {name} is sleeping soundly.",
        "The {name} mumbles something in their sleep.",
        "The {name} doesn't respond, being fast asleep."
    ]
    
    # Set eating responses
    npc.ai_state["eating_responses"] = [
        "The {name} is busy eating right now.",
        "The {name} talks to you between bites of food.",
        "The {name} gestures for you to wait until they finish eating."
    ]
    
    # Set working responses
    npc.ai_state["working_responses"] = [
        "The {name} is busy with their work at the moment.",
        "The {name} briefly pauses their work to acknowledge you.",
        "The {name} seems focused on the task at hand."
    ]
    
    # Register the schedule
    plugin.add_npc_schedule(npc_id, schedule)

def create_guard_schedule(plugin, npc_id, town_spaces):
    """Create a dynamic guard schedule."""
    npc = plugin.world.get_npc(npc_id)
    if not npc:
        return
    
    # Guards patrol between different posts
    patrol_points = getattr(npc, "patrol_points", [])
    
    # Find guard posts to patrol between
    guard_posts = town_spaces["guard_posts"]
    town_square = town_spaces["town_square"]
    market = town_spaces["markets"]
    
    # Create the list of patrol locations
    patrol_locations = []
    
    # Add existing patrol points first
    for point in patrol_points:
        patrol_locations.append({"region_id": npc.current_region_id, "room_id": point})
    
    # Add guard posts
    for post in guard_posts:
        if post not in patrol_locations:
            patrol_locations.append(post)
    
    # Add town square
    for square in town_square:
        if square not in patrol_locations:
            patrol_locations.append(square)
    
    # Add market areas during daytime hours
    for m in market:
        if m not in patrol_locations:
            patrol_locations.append(m)
    
    # If we don't have enough patrol points, add the current room
    if not patrol_locations:
        patrol_locations.append({"region_id": npc.current_region_id, "room_id": npc.current_room_id})
    
    # Get barracks or resting area
    barracks = get_random_location(guard_posts)
    if not barracks:
        barracks = {"region_id": npc.current_region_id, "room_id": npc.current_room_id}
    
    # Get tavern for evening break
    tavern = get_random_location(town_spaces["taverns"])
    if not tavern:
        tavern = barracks
    
    # Create a dynamic schedule with patrols
    schedule = {}
    
    # Morning shift
    schedule[6] = {"activity": "waking up", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    schedule[7] = {"activity": "eating breakfast", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    
    # Morning patrol covering different areas
    if len(patrol_locations) >= 3:
        schedule[8] = {"activity": "morning patrol", "region_id": patrol_locations[0]["region_id"], "room_id": patrol_locations[0]["room_id"]}
        schedule[9] = {"activity": "morning patrol", "region_id": patrol_locations[1]["region_id"], "room_id": patrol_locations[1]["room_id"]}
        schedule[10] = {"activity": "morning patrol", "region_id": patrol_locations[2]["region_id"], "room_id": patrol_locations[2]["room_id"]}
    else:
        # Use what we have and cycle if needed
        for hour, i in zip(range(8, 11), range(len(patrol_locations))):
            idx = i % len(patrol_locations)
            schedule[hour] = {"activity": "morning patrol", "region_id": patrol_locations[idx]["region_id"], "room_id": patrol_locations[idx]["room_id"]}
    
    # Midday break
    schedule[12] = {"activity": "lunch break", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    
    # Afternoon patrol
    if len(patrol_locations) >= 3:
        schedule[13] = {"activity": "afternoon patrol", "region_id": patrol_locations[2]["region_id"], "room_id": patrol_locations[2]["room_id"]}
        schedule[14] = {"activity": "afternoon patrol", "region_id": patrol_locations[1]["region_id"], "room_id": patrol_locations[1]["room_id"]}
        schedule[15] = {"activity": "afternoon patrol", "region_id": patrol_locations[0]["region_id"], "room_id": patrol_locations[0]["room_id"]}
    else:
        # Use what we have and cycle if needed
        for hour, i in zip(range(13, 16), range(len(patrol_locations))):
            idx = (len(patrol_locations) - 1 - i) % len(patrol_locations)  # Reverse order
            schedule[hour] = {"activity": "afternoon patrol", "region_id": patrol_locations[idx]["region_id"], "room_id": patrol_locations[idx]["room_id"]}
    
    # Evening routine
    schedule[17] = {"activity": "shift change", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    schedule[18] = {"activity": "eating dinner", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    schedule[19] = {"activity": "relaxing", "region_id": tavern["region_id"], "room_id": tavern["room_id"]}
    
    # Night patrol (if night guard)
    night_shift = random.choice([True, False])
    if night_shift:
        if len(patrol_locations) >= 2:
            schedule[21] = {"activity": "night patrol", "region_id": patrol_locations[0]["region_id"], "room_id": patrol_locations[0]["room_id"]}
            schedule[23] = {"activity": "night patrol", "region_id": patrol_locations[1]["region_id"], "room_id": patrol_locations[1]["room_id"]}
        else:
            schedule[21] = {"activity": "night patrol", "region_id": patrol_locations[0]["region_id"], "room_id": patrol_locations[0]["room_id"]}
        schedule[1] = {"activity": "sleeping", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    else:
        schedule[21] = {"activity": "sleeping", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    
    # Set custom responses
    npc.ai_state["sleeping_responses"] = [
        "The {name} is resting after a long shift.",
        "Even guards need sleep. The {name} is off duty right now."
    ]
    
    # Register the schedule
    plugin.add_npc_schedule(npc_id, schedule)

def create_merchant_schedule(plugin, npc_id, town_spaces):
    """Create a dynamic merchant schedule."""
    npc = plugin.world.get_npc(npc_id)
    if not npc:
        return
    
    # Use current room as shop
    shop_region = npc.current_region_id
    shop_room = npc.current_room_id
    
    # Find a home for the merchant
    homes = town_spaces["homes"]
    home = get_random_location(homes, shop_region, shop_room)
    if not home:
        home = {"region_id": shop_region, "room_id": shop_room}
    
    # Find market and social spaces
    market = get_random_location(town_spaces["markets"], shop_region, shop_room)
    if not market:
        market = {"region_id": shop_region, "room_id": shop_room}
    
    tavern = get_random_location(town_spaces["taverns"])
    if not tavern:
        tavern = home
    
    # Create a dynamic schedule
    schedule = {
        6: {"activity": "waking up", "region_id": home["region_id"], "room_id": home["room_id"]},
        7: {"activity": "eating breakfast", "region_id": home["region_id"], "room_id": home["room_id"]},
        8: {"activity": "walking to shop", "region_id": shop_region, "room_id": shop_room},
        9: {"activity": "preparing shop", "region_id": shop_region, "room_id": shop_room},
        10: {"activity": "working", "region_id": shop_region, "room_id": shop_room},
        12: {"activity": "shopping for supplies", "region_id": market["region_id"], "room_id": market["room_id"]},
        13: {"activity": "eating lunch", "region_id": shop_region, "room_id": shop_room},
        14: {"activity": "working", "region_id": shop_region, "room_id": shop_room},
        17: {"activity": "closing shop", "region_id": shop_region, "room_id": shop_room},
        18: {"activity": "heading to dinner", "region_id": tavern["region_id"], "room_id": tavern["room_id"]},
        20: {"activity": "walking home", "region_id": home["region_id"], "room_id": home["room_id"]},
        21: {"activity": "counting coins", "region_id": home["region_id"], "room_id": home["room_id"]},
        22: {"activity": "sleeping", "region_id": home["region_id"], "room_id": home["room_id"]}
    }
    
    # Set custom responses
    npc.ai_state["working_responses"] = [
        "The {name} says, 'Welcome! Are you looking to buy something?'",
        "The {name} says, 'I have the finest wares in the region!'",
        "The {name} says, 'Feel free to browse, but please don't touch the merchandise unless you're buying.'"
    ]
    
    # Register the schedule
    plugin.add_npc_schedule(npc_id, schedule)

def create_elder_schedule(plugin, npc_id, town_spaces):
    """Create a dynamic elder schedule."""
    npc = plugin.world.get_npc(npc_id)
    if not npc:
        return
    
    # Elders spend time in important town locations
    home_region = npc.current_region_id
    home_room = npc.current_room_id
    
    # Find key locations
    temple = get_random_location(town_spaces["temple"])
    if not temple:
        temple = {"region_id": home_region, "room_id": home_room}
        
    town_square = get_random_location(town_spaces["town_square"])
    if not town_square:
        town_square = {"region_id": home_region, "room_id": home_room}
    
    garden = get_random_location(town_spaces["gardens"])
    if not garden:
        garden = town_square
    
    # Create a thoughtful schedule with quiet contemplation and community guidance
    schedule = {
        7: {"activity": "waking up", "region_id": home_region, "room_id": home_room},
        8: {"activity": "morning meditation", "region_id": home_region, "room_id": home_room},
        9: {"activity": "eating breakfast", "region_id": home_region, "room_id": home_room},
        10: {"activity": "visiting the temple", "region_id": temple["region_id"], "room_id": temple["room_id"]},
        11: {"activity": "praying", "region_id": temple["region_id"], "room_id": temple["room_id"]},
        12: {"activity": "walking to the square", "region_id": town_square["region_id"], "room_id": town_square["room_id"]},
        13: {"activity": "counseling villagers", "region_id": town_square["region_id"], "room_id": town_square["room_id"]},
        15: {"activity": "walking in the garden", "region_id": garden["region_id"], "room_id": garden["room_id"]},
        16: {"activity": "resting", "region_id": garden["region_id"], "room_id": garden["room_id"]},
        17: {"activity": "returning home", "region_id": home_region, "room_id": home_room},
        18: {"activity": "eating dinner", "region_id": home_region, "room_id": home_room},
        19: {"activity": "evening reflection", "region_id": home_region, "room_id": home_room},
        21: {"activity": "sleeping", "region_id": home_region, "room_id": home_room}
    }
    
    # Register the schedule
    plugin.add_npc_schedule(npc_id, schedule)

def create_villager_schedule(plugin, npc_id, town_spaces):
    """Create a dynamic villager schedule with varied activities."""
    npc = plugin.world.get_npc(npc_id)
    if not npc:
        return
    
    # Villagers have a variety of possible patterns
    home_region = npc.current_region_id
    home_room = npc.current_room_id
    
    # Find a separate home if possible
    possible_home = get_random_location(town_spaces["homes"])
    if possible_home and possible_home["room_id"] != home_room:
        home = possible_home
    else:
        home = {"region_id": home_region, "room_id": home_room}
    
    # Find work location (different for each villager)
    possible_work_places = [
        town_spaces["work_areas"],
        town_spaces["shops"],
        town_spaces["markets"],
        town_spaces["gardens"]
    ]
    
    # Select a work category randomly
    work_category = random.choice(possible_work_places)
    work_place = get_random_location(work_category, home["region_id"], home["room_id"])
    if not work_place:
        work_place = {"region_id": home_region, "room_id": home_room}
    
    # Social locations
    tavern = get_random_location(town_spaces["taverns"])
    if not tavern:
        tavern = home
    
    market = get_random_location(town_spaces["markets"])
    if not market:
        market = work_place
    
    square = get_random_location(town_spaces["town_square"])
    if not square:
        square = market
    
    # Special location (shop, garden, temple etc.)
    special_categories = [cat for cat in town_spaces.keys() if cat not in ["homes", "work_areas"]]
    if special_categories:
        special_category = random.choice(special_categories)
        special_place = get_random_location(town_spaces[special_category])
    else:
        special_place = square
    
    # Create a varied schedule
    schedule = {
        7: {"activity": "waking up", "region_id": home["region_id"], "room_id": home["room_id"]},
        8: {"activity": "eating breakfast", "region_id": home["region_id"], "room_id": home["room_id"]},
        9: {"activity": "heading to work", "region_id": work_place["region_id"], "room_id": work_place["room_id"]},
        11: {"activity": "working", "region_id": work_place["region_id"], "room_id": work_place["room_id"]},
        13: {"activity": "lunch break", "region_id": market["region_id"], "room_id": market["room_id"]},
        14: {"activity": "shopping", "region_id": market["region_id"], "room_id": market["room_id"]},
        15: {"activity": "working", "region_id": work_place["region_id"], "room_id": work_place["room_id"]},
        17: {"activity": "visiting", "region_id": special_place["region_id"], "room_id": special_place["room_id"]},
        18: {"activity": "socializing", "region_id": tavern["region_id"], "room_id": tavern["room_id"]},
        20: {"activity": "heading home", "region_id": home["region_id"], "room_id": home["room_id"]},
        21: {"activity": "relaxing", "region_id": home["region_id"], "room_id": home["room_id"]},
        22: {"activity": "sleeping", "region_id": home["region_id"], "room_id": home["room_id"]}
    }
    
    # Randomize: sometimes villagers have a different pattern on specific days
    # This is just a placeholder for future day-specific scheduling
    if random.random() < 0.3:  # 30% chance of having some variation
        # For now, just add a minor variation in the late afternoon
        schedule[16] = {"activity": "taking a walk", "region_id": square["region_id"], "room_id": square["room_id"]}
    
    # Register the schedule
    plugin.add_npc_schedule(npc_id, schedule)

def create_bartender_schedule(plugin, npc_id, town_spaces):
    """Create a dynamic bartender schedule."""
    npc = plugin.world.get_npc(npc_id)
    if not npc:
        return
    
    # Bartenders work in taverns but may live elsewhere
    tavern_region = npc.current_region_id
    tavern_room = npc.current_room_id
    
    # Find a home separate from the tavern if possible
    home = get_random_location(town_spaces["homes"], tavern_region, tavern_room)
    if not home:
        home = {"region_id": tavern_region, "room_id": tavern_room}
    
    # Market for supplies
    market = get_random_location(town_spaces["markets"])
    if not market:
        market = {"region_id": tavern_region, "room_id": tavern_room}
    
    # Create a schedule with later hours
    schedule = {
        9: {"activity": "waking up", "region_id": home["region_id"], "room_id": home["room_id"]},
        10: {"activity": "eating breakfast", "region_id": home["region_id"], "room_id": home["room_id"]},
        11: {"activity": "shopping for supplies", "region_id": market["region_id"], "room_id": market["room_id"]},
        12: {"activity": "heading to tavern", "region_id": tavern_region, "room_id": tavern_room},
        13: {"activity": "preparing the tavern", "region_id": tavern_region, "room_id": tavern_room},
        14: {"activity": "working", "region_id": tavern_region, "room_id": tavern_room},
        16: {"activity": "serving customers", "region_id": tavern_region, "room_id": tavern_room},
        18: {"activity": "busy hour", "region_id": tavern_region, "room_id": tavern_room},
        20: {"activity": "entertaining patrons", "region_id": tavern_region, "room_id": tavern_room},
        23: {"activity": "closing up", "region_id": tavern_region, "room_id": tavern_room},
        0: {"activity": "walking home", "region_id": home["region_id"], "room_id": home["room_id"]},
        1: {"activity": "sleeping", "region_id": home["region_id"], "room_id": home["room_id"]}
    }
    
    # Set custom responses
    npc.ai_state["working_responses"] = [
        "The {name} says, 'What'll it be?'",
        "The {name} wipes down the counter while listening to you.",
        "The {name} says, 'I've heard all sorts of stories working here...'"
    ]
    
    # Register the schedule
    plugin.add_npc_schedule(npc_id, schedule)

def create_town_activity(plugin, town_spaces):
    """
    Create a dynamic town routine with NPCs meeting each other at various times.
    This helps create a sense of a living town where NPCs interact.
    
    Call this after creating individual schedules.
    """
    if not plugin.world:
        return
    
    # Get all NPCs with schedules
    scheduled_npcs = [npc_id for npc_id in plugin.npc_schedules.keys()]
    
    # If not enough NPCs, do nothing
    if len(scheduled_npcs) < 2:
        return
    
    # Create special meeting events
    # For example: scheduled gatherings, meetings between NPCs
    
    # 1. Morning market gathering
    morning_market_hour = 10
    market_location = None
    if town_spaces["markets"]:
        market_location = random.choice(town_spaces["markets"])
    elif town_spaces["town_square"]:
        market_location = random.choice(town_spaces["town_square"])
    
    # 2. Evening tavern gathering
    evening_tavern_hour = 19
    tavern_location = None
    if town_spaces["taverns"]:
        tavern_location = random.choice(town_spaces["taverns"])
    
    # 3. Afternoon garden/square meeting
    afternoon_meeting_hour = 16
    meeting_location = None
    if town_spaces["gardens"]:
        meeting_location = random.choice(town_spaces["gardens"])
    elif town_spaces["town_square"]:
        meeting_location = random.choice(town_spaces["town_square"])
    
    # Apply gatherings to some NPCs
    if market_location:
        # Select random NPCs to visit the market
        market_visitors = random.sample(scheduled_npcs, min(3, len(scheduled_npcs)))
        for npc_id in market_visitors:
            if npc_id in plugin.npc_schedules:
                schedule = plugin.npc_schedules[npc_id]
                # Only override if they're not already doing something critical
                if morning_market_hour not in schedule or "working" not in schedule[morning_market_hour].get("activity", ""):
                    schedule[morning_market_hour] = {
                        "activity": "visiting the morning market",
                        "region_id": market_location["region_id"],
                        "room_id": market_location["room_id"]
                    }
                    # Update the NPC's schedule
                    plugin.add_npc_schedule(npc_id, schedule)
    
    if tavern_location:
        # Select random NPCs to visit the tavern
        tavern_visitors = random.sample(scheduled_npcs, min(5, len(scheduled_npcs)))
        for npc_id in tavern_visitors:
            if npc_id in plugin.npc_schedules:
                schedule = plugin.npc_schedules[npc_id]
                # Only override if they're not already doing something critical
                if evening_tavern_hour not in schedule or "sleeping" not in schedule[evening_tavern_hour].get("activity", ""):
                    schedule[evening_tavern_hour] = {
                        "activity": "visiting the tavern",
                        "region_id": tavern_location["region_id"],
                        "room_id": tavern_location["room_id"]
                    }
                    # Update the NPC's schedule
                    plugin.add_npc_schedule(npc_id, schedule)
    
    if meeting_location:
        # Select random NPCs for afternoon gathering
        meeting_attendees = random.sample(scheduled_npcs, min(4, len(scheduled_npcs)))
        for npc_id in meeting_attendees:
            if npc_id in plugin.npc_schedules:
                schedule = plugin.npc_schedules[npc_id]
                # Only override if they're not already doing something critical
                if afternoon_meeting_hour not in schedule or "working" not in schedule[afternoon_meeting_hour].get("activity", ""):
                    schedule[afternoon_meeting_hour] = {
                        "activity": "meeting with friends",
                        "region_id": meeting_location["region_id"],
                        "room_id": meeting_location["room_id"]
                    }
                    # Update the NPC's schedule
                    plugin.add_npc_schedule(npc_id, schedule)

"""
plugins/npc_schedule_plugin/__init__.py
A fixed and simplified NPC scheduling plugin that makes NPCs wander during the day
and gather at taverns/social areas at night.
"""
from typing import Dict, Any, List, Optional
from plugins.plugin_system import PluginBase
import random
import time

class NPCSchedulePlugin(PluginBase):
    """
    Improved NPC movement and scheduling system.
    Makes NPCs wander during the day and gather socially at night.
    """
    
    plugin_id = "npc_schedule_plugin"
    plugin_name = "Improved NPC Scheduler"
    
    def __init__(self, world=None, command_processor=None, event_system=None, data_provider=None, service_locator=None):
        """Initialize the improved NPC plugin."""
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator
        
        # Import config from config.py
        from .config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG.copy()
        
        # Track time info
        self.current_hour = 12
        self.current_period = "day"
        
        # Keep track of room types
        self.taverns = []       # Places to gather at night
        self.social_areas = []  # Alternative gathering places
        self.home_locations = {} # NPC ID -> home location
        
        # Movement tracking
        self.last_update_time = 0
        self.movement_count = 0
    
    def initialize(self):
        """Initialize the plugin."""
        # Subscribe to time events
        if self.event_system:
            self.event_system.subscribe("time_data", self._on_time_data)
            self.event_system.subscribe("hour_changed", self._on_hour_changed)
        
        # Register commands
        self._register_commands()
        
        # Discover key locations
        self._discover_locations()
        
        # Initialize NPCs
        self._initialize_npcs()
        
        # Debug message
        tavern_count = len(self.taverns)
        social_count = len(self.social_areas)
        print(f"Improved NPC plugin initialized with {tavern_count} taverns and {social_count} social areas")
        
        # Force an initial update
        self._update_npcs(force=True)
    
    def _register_commands(self):
        """Register plugin commands."""
        # Import and register commands from commands.py
        from .commands import register_commands
        register_commands(self)
    
    def _on_time_data(self, event_type, data):
        """Handle time data updates."""
        self.current_hour = data.get("hour", 12)
        self.current_period = data.get("time_period", "day")
    
    def _on_hour_changed(self, event_type, data):
        """Handle hourly updates."""
        hour = data.get("hour", 0)
        self.current_hour = hour
        
        # Update time period (day/night)
        if hour >= self.config["day_start_hour"] and hour < self.config["night_start_hour"]:
            self.current_period = "day"
        else:
            self.current_period = "night"
        
        # Force an update at period changes
        if hour == self.config["day_start_hour"] or hour == self.config["night_start_hour"]:
            self._update_npcs(force=True)
            
            # Send message about period change
            if self.event_system:
                if hour == self.config["day_start_hour"]:
                    self.event_system.publish("display_message", "As morning arrives, people begin to move about for the day.")
                else:
                    self.event_system.publish("display_message", "As night falls, people head to taverns and gathering places.")
    
    def _discover_locations(self):
        """Discover taverns, social areas, and other key locations in the world."""
        if not self.world:
            return
        
        # Clear existing locations
        self.taverns = []
        self.social_areas = []
        
        # Examine all rooms in the world
        for region_id, region in self.world.regions.items():
            for room_id, room in region.rooms.items():
                room_name = room.name.lower()
                
                # Identify taverns
                if any(term in room_name for term in ["tavern", "inn", "pub", "bar"]):
                    self.taverns.append({
                        "region_id": region_id,
                        "room_id": room_id,
                        "name": room.name
                    })
                
                # Identify social areas
                elif any(term in room_name for term in ["hall", "square", "garden", "plaza", "center"]):
                    self.social_areas.append({
                        "region_id": region_id,
                        "room_id": room_id,
                        "name": room.name
                    })
        
        # If no taverns found, use social areas as fallback
        if not self.taverns and self.social_areas:
            self.taverns = self.social_areas.copy()
        
        # If no social areas at all, create a default from the first available room
        if not self.taverns and not self.social_areas and self.world.regions:
            first_region = next(iter(self.world.regions.values()))
            if first_region.rooms:
                first_room = next(iter(first_region.rooms.values()))
                default_area = {
                    "region_id": next(iter(self.world.regions.keys())),
                    "room_id": next(iter(first_region.rooms.keys())),
                    "name": first_room.name
                }
                self.taverns.append(default_area)
                self.social_areas.append(default_area)
    
    def _initialize_npcs(self):
        """Initialize all NPCs with proper movement settings."""
        if not self.world:
            return
        
        for npc_id, npc in self.world.npcs.items():
            # Store original behavior
            if not hasattr(npc, "ai_state"):
                npc.ai_state = {}
            
            # Save original behavior type
            if "original_behavior_type" not in npc.ai_state:
                npc.ai_state["original_behavior_type"] = getattr(npc, "behavior_type", "wanderer")
            
            # Set behavior to wanderer (we'll handle scheduling ourselves)
            npc.behavior_type = "wanderer"
            
            # Store current home location
            self.home_locations[npc_id] = {
                "region_id": npc.current_region_id,
                "room_id": npc.current_room_id
            }
            
            # Set a reasonable move cooldown
            npc.move_cooldown = random.randint(5, 15)  # Varied cooldowns for more natural movement
            
            # Initialize wander chance based on time period
            if self.current_period == "day":
                npc.wander_chance = self.config["day_wander_chance"]
            else:
                npc.wander_chance = self.config["night_wander_chance"]
            
            # Add activity tracking
            if "current_activity" not in npc.ai_state:
                activity = random.choice(self.config["day_activities"]) if self.current_period == "day" else random.choice(self.config["night_activities"])
                npc.ai_state["current_activity"] = activity
    
    def _get_night_destination(self, npc_id):
        """Get a destination for an NPC at night (tavern or social area)."""
        # Try to find a tavern
        if self.taverns:
            return random.choice(self.taverns)
        
        # Fallback to social areas
        elif self.social_areas:
            return random.choice(self.social_areas)
        
        # Last resort - use home location
        elif npc_id in self.home_locations:
            return self.home_locations[npc_id]
        
        # No suitable destination found
        return None
    
    def _update_npcs(self, force=False):
        """Update NPC behavior based on time period."""
        if not self.world:
            return
        
        current_time = time.time()
        
        # Only update at specified interval unless forced
        if not force and (current_time - self.last_update_time < self.config["update_interval"]):
            return
        
        self.last_update_time = current_time
        
        # Loop through all NPCs and update their behavior
        for npc_id, npc in self.world.npcs.items():
            # Skip NPCs that are busy with activities
            if npc.ai_state.get("is_sleeping") or npc.ai_state.get("is_busy"):
                continue
            
            # Day/night behavior switch
            is_day = self.current_period == "day"
            
            # During the day: wander randomly
            if is_day:
                # Set appropriate wander chance
                npc.wander_chance = self.config["day_wander_chance"]
                
                # Set a daytime activity
                if random.random() < 0.2:  # 20% chance to change activity
                    npc.ai_state["current_activity"] = random.choice(self.config["day_activities"])
                
                # Let the normal wanderer behavior handle movement
                
            # At night: head to tavern or social area
            else:
                # First approach: try to use their built-in movement
                destination = self._get_night_destination(npc_id)
                if destination:
                    # Set the destination
                    target_region = destination["region_id"]
                    target_room = destination["room_id"]
                    
                    # If not already there, update location
                    if npc.current_region_id != target_region or npc.current_room_id != target_room:
                        # Directly update NPC location
                        old_region = npc.current_region_id
                        old_room = npc.current_room_id
                        
                        # Update location
                        npc.current_region_id = target_region
                        npc.current_room_id = target_room
                        
                        # Set a nighttime activity
                        npc.ai_state["current_activity"] = random.choice(self.config["night_activities"])
                        
                        # Reset movement timers
                        npc.last_moved = 0
                        
                        # Count the movement
                        self.movement_count += 1
                        
                        # Notify if player is in either room
                        if self.world.current_region_id == old_region and self.world.current_room_id == old_room:
                            if self.event_system:
                                self.event_system.publish("display_message", f"{npc.name} leaves to find a place for the night.")
                        
                        if self.world.current_region_id == target_region and self.world.current_room_id == target_room:
                            if self.event_system:
                                self.event_system.publish("display_message", f"{npc.name} arrives, looking for a place to {npc.ai_state['current_activity']}.")
                    
                    # Reduce wandering at night
                    npc.wander_chance = self.config["night_wander_chance"]
    
    def on_tick(self, current_time):
        """Update on each game tick."""
        self._update_npcs()
        
    def cleanup(self):
        """Clean up plugin resources."""
        # Restore original behaviors
        if self.world:
            for npc_id, npc in self.world.npcs.items():
                if hasattr(npc, "ai_state") and "original_behavior_type" in npc.ai_state:
                    npc.behavior_type = npc.ai_state["original_behavior_type"]
        
        # Unsubscribe from events
        if self.event_system:
            self.event_system.unsubscribe("time_data", self._on_time_data)
            self.event_system.unsubscribe("hour_changed", self._on_hour_changed)

# plugins/time_plugin/commands.py
from commands.command_system import command
from plugins.plugin_system import register_plugin_command

def register_commands(plugin):
    """Register plugin commands."""
    
    def time_command_handler(args, context):
        """Time command handler."""
        time_str = f"{plugin.hour:02d}:{plugin.minute:02d}"
        day_name = plugin.config["day_names"][plugin.day % len(plugin.config["day_names"]) - 1]
        month_name = plugin.config["month_names"][plugin.month - 1]
        
        response = f"Current Time: {time_str}\n"
        response += f"Current Date: {day_name}, {plugin.day} {month_name}, Year {plugin.year}\n"
        response += f"Time Period: {plugin.current_time_period.capitalize()}\n"
        
        return response
    
    def calendar_command_handler(args, context):
        """Calendar command handler."""
        day_name = plugin.config["day_names"][plugin.day % len(plugin.config["day_names"]) - 1]
        month_name = plugin.config["month_names"][plugin.month - 1]
        
        response = f"Current Date: {day_name}, {plugin.day} {month_name}, Year {plugin.year}\n\n"
        response += f"Days in a week: {plugin.config['days_per_week']}\n"
        response += f"Days in a month: {plugin.config['days_per_month']}\n"
        response += f"Months in a year: {plugin.config['months_per_year']}\n\n"
        
        response += "Day names: " + ", ".join(plugin.config["day_names"]) + "\n\n"
        response += "Month names: " + ", ".join(plugin.config["month_names"]) + "\n"
        
        return response
    
    # Register the commands
    register_plugin_command(
        plugin.plugin_id,
        "time", 
        time_command_handler,
        aliases=["clock"], 
        category="system", 
        help_text="Display the current in-game time and date."
    )
    
    register_plugin_command(
        plugin.plugin_id,
        "calendar", 
        calendar_command_handler,
        aliases=["cal", "date"], 
        category="system", 
        help_text="Display the current in-game calendar."
    )

"""
plugins/time_plugin/config.py
Default configuration for the Time plugin.
"""

DEFAULT_CONFIG = {
    # Time settings (in real seconds)
    "real_seconds_per_game_day": 600,  # 10 minutes = 1 day
    "days_per_week": 7,
    "days_per_month": 30,
    "months_per_year": 12,
    "day_names": [
        "Moonday", "Tideday", "Windday", "Thunderday", 
        "Fireday", "Starday", "Sunday"
    ],
    "month_names": [
        "Deepwinter", "Icemelt", "Springbloom", "Rainshower",
        "Meadowgrow", "Highsun", "Fireheat", "Goldenfield",
        "Harvestide", "Leaffall", "Frostwind", "Darknight"
    ],
    "dawn_hour": 6,
    "day_hour": 8,
    "dusk_hour": 18,
    "night_hour": 20
}

"""
plugins/time_plugin/__init__.py
Time plugin for the MUD game.
Implements an in-game time and calendar system.
"""
import time
from typing import Dict, Any
from plugins.plugin_system import PluginBase

class TimePlugin(PluginBase):
    plugin_id = "time_plugin"
    plugin_name = "Time and Calendar"
    
    def __init__(self, world=None, command_processor=None, event_system=None, data_provider=None, service_locator=None):
        """Initialize the time plugin."""
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator
        
        # Import config from the config.py file
        from .config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG.copy()
        
        # Time tracking
        self.game_time = 0  # Seconds of game time elapsed
        self.last_real_time = time.time()
        
        # Time periods
        self.time_periods = ["dawn", "day", "dusk", "night"]
        self.current_time_period = "day"
        
        # Initialize time data
        self.hour = 12
        self.minute = 0
        self.day = 1
        self.month = 1
        self.year = 1
    
    def initialize(self):
        """Initialize the plugin."""
        # Register event listeners
        if self.event_system:
            self.event_system.subscribe("on_tick", self._on_tick)
        
        # Register commands
        from .commands import register_commands
        register_commands(self)
        
        # Store initial time data in the world
        self._update_world_time_data()
        
        print(f"Time plugin initialized. Current time period: {self.current_time_period}")
    
    def _on_tick(self, event_type, data):
        """Update time on each game tick."""
        # Get real time elapsed
        current_real_time = time.time()
        elapsed_real_time = current_real_time - self.last_real_time
        self.last_real_time = current_real_time
        
        # Convert to game time
        seconds_per_day = self.config["real_seconds_per_game_day"]
        game_seconds_per_real_second = 86400 / seconds_per_day  # 86400 = seconds in a day
        elapsed_game_time = elapsed_real_time * game_seconds_per_real_second
        
        # Update game time
        self.game_time += elapsed_game_time
        
        # Convert game time to hour, minute, day, month, year
        old_hour = self.hour
        old_day = self.day
        old_month = self.month
        old_year = self.year
        
        total_minutes = int(self.game_time / 60) % 1440  # 1440 = minutes in a day
        self.hour = total_minutes // 60
        self.minute = total_minutes % 60
        
        total_days = int(self.game_time / 86400) + 1  # +1 to start from day 1
        days_per_month = self.config["days_per_month"]
        months_per_year = self.config["months_per_year"]
        
        self.year = ((total_days - 1) // (days_per_month * months_per_year)) + 1
        days_in_year = (total_days - 1) % (days_per_month * months_per_year)
        self.month = (days_in_year // days_per_month) + 1
        self.day = (days_in_year % days_per_month) + 1
        
        # Check for time period changes
        old_time_period = self.current_time_period
        self._update_time_period()
        
        # Update world with time data
        self._update_world_time_data()
        
        # Publish events when time changes
        if self.event_system:
            # Hourly event
            if self.hour != old_hour:
                self.event_system.publish("hour_changed", {
                    "hour": self.hour,
                    "old_hour": old_hour
                })
            
            # Daily event
            if self.day != old_day:
                self.event_system.publish("day_changed", {
                    "day": self.day,
                    "old_day": old_day
                })
            
            # Monthly event
            if self.month != old_month:
                self.event_system.publish("month_changed", {
                    "month": self.month,
                    "old_month": old_month
                })
            
            # Yearly event
            if self.year != old_year:
                self.event_system.publish("year_changed", {
                    "year": self.year,
                    "old_year": old_year
                })
            
            # Time period change event
            if self.current_time_period != old_time_period:
                transition_message = self._get_time_period_transition_message(old_time_period, self.current_time_period)
                self.event_system.publish("time_period_changed", {
                    "old_period": old_time_period,
                    "new_period": self.current_time_period,
                    "transition_message": transition_message
                })
    
    def _update_time_period(self):
        """Update the current time period based on the hour."""
        if self.hour >= self.config["night_hour"] or self.hour < self.config["dawn_hour"]:
            self.current_time_period = "night"
        elif self.hour >= self.config["dawn_hour"] and self.hour < self.config["day_hour"]:
            self.current_time_period = "dawn"
        elif self.hour >= self.config["day_hour"] and self.hour < self.config["dusk_hour"]:
            self.current_time_period = "day"
        else:  # dusk_hour to night_hour
            self.current_time_period = "dusk"
    
    def _get_time_period_transition_message(self, old_period, new_period):
        """Get a message describing the time period transition."""
        transitions = {
            "night-dawn": "The first rays of sunlight appear on the horizon as dawn breaks.",
            "dawn-day": "The sun rises fully into the sky, bathing the world in daylight.",
            "day-dusk": "The sun begins to set, casting long shadows as dusk approaches.",
            "dusk-night": "Darkness falls as the sun disappears below the horizon."
        }
        
        transition_key = f"{old_period}-{new_period}"
        return transitions.get(transition_key, "")
    
    def _update_world_time_data(self):
        """Store time data in the world for other plugins to access."""
        day_name = self.config["day_names"][(self.day - 1) % len(self.config["day_names"])]
        month_name = self.config["month_names"][self.month - 1]
        
        time_str = f"{self.hour:02d}:{self.minute:02d}"
        date_str = f"{day_name}, {self.day} {month_name}, Year {self.year}"
        
        # Get season
        seasons = ["winter", "spring", "summer", "fall"]
        season_idx = ((self.month - 1) // 3) % 4
        current_season = seasons[season_idx]
        
        time_data = {
            "hour": self.hour,
            "minute": self.minute,
            "day": self.day,
            "month": self.month,
            "year": self.year,
            "day_name": day_name,
            "month_name": month_name,
            "season": current_season,
            "time_period": self.current_time_period,
            "time_str": time_str,
            "date_str": date_str
        }
        
        # Store in world plugin data
        if self.world:
            for key, value in time_data.items():
                self.world.set_plugin_data(self.plugin_id, key, value)
        
        # Publish time data event
        if self.event_system:
            self.event_system.publish("time_data", time_data)
    
    def cleanup(self):
        """Clean up plugin resources."""
        if self.event_system:
            self.event_system.unsubscribe("on_tick", self._on_tick)

"""
plugins/weather_plugin/commands.py
Command module for the Weather plugin.
"""
from plugins.plugin_system import register_plugin_command

def register_commands(plugin):
    """Register plugin commands."""
    
    def weather_command_handler(args, context):
        """Weather command handler."""
        # Get description from config
        description = plugin.config["weather_descriptions"].get(
            plugin.current_weather, 
            "The weather is unremarkable."
        )
        
        # Check if player is indoors
        is_outdoors = True
        if plugin.data_provider:
            is_outdoors = plugin.data_provider.is_outdoors_or_has_windows()
        
        if not is_outdoors:
            return f"You can't see the weather from inside, but you can hear sounds indicating {plugin.current_weather} conditions outside."
        
        # Return formatted response
        return f"Current Weather: {plugin.current_weather.capitalize()} ({plugin.current_intensity})\n\n{description}"
    
    # Register the commands
    register_plugin_command(
        plugin.plugin_id,
        "weather",
        weather_command_handler,
        aliases=["forecast"],
        category="world",
        help_text="Check the current weather conditions."
    )

"""
plugins/weather_plugin/config.py
Default configuration for the Weather plugin.
"""

DEFAULT_CONFIG = {
    # Weather change settings
    "hourly_change_chance": 0.2,  # 20% chance per hour
    
    # Weather type probabilities by season
    "weather_chances": {
        "spring": {"clear": 0.4, "cloudy": 0.3, "rain": 0.3, "storm": 0.1},
        "summer": {"clear": 0.6, "cloudy": 0.2, "rain": 0.1, "storm": 0.1},
        "fall": {"clear": 0.3, "cloudy": 0.4, "rain": 0.2, "storm": 0.1},
        "winter": {"clear": 0.5, "cloudy": 0.3, "snow": 0.2}
    },
    
    # Weather descriptions
    "weather_descriptions": {
        "clear": "The sky is clear and blue.",
        "cloudy": "Clouds fill the sky.",
        "rain": "Rain falls steadily.",
        "storm": "Thunder rumbles as a storm rages.",
        "snow": "Snowflakes drift down from the sky."
    },
    
    # Weather intensity descriptions
    "intensity_descriptions": {
        "mild": "mild",
        "moderate": "moderate",
        "strong": "strong",
        "severe": "severe"
    }
}

"""
plugins/weather_plugin/__init__.py
Weather plugin for the MUD game.
Implements a dynamic weather system affected by time of day and season.
"""
import random
from typing import Dict, Any
from plugins.plugin_system import PluginBase

class WeatherPlugin(PluginBase):
    """Weather system for the MUD game."""
    
    plugin_id = "weather_plugin"
    plugin_name = "Weather System"
    
    def __init__(self, world=None, command_processor=None, event_system=None, data_provider=None, service_locator=None):
        """Initialize the weather plugin."""
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator
        
        # Import config from the config.py file
        from .config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG.copy()
        
        # Current weather state
        self.current_weather = "clear"
        self.current_intensity = "mild"
        self.current_season = "summer"  # Default season
        self.last_weather_change = 0  # Game time of last weather change
    
    def initialize(self):
        """Initialize the plugin."""
        # Subscribe to time events
        if self.event_system:
            self.event_system.subscribe("hour_changed", self._on_hour_changed)
            self.event_system.subscribe("time_period_changed", self._on_time_period_changed)
            self.event_system.subscribe("time_data", self._on_time_data)
        
        # Register commands
        from .commands import register_commands
        register_commands(self)
        
        # Set initial weather
        self._update_weather()
        
        print(f"Weather plugin initialized. Current weather: {self.current_weather} ({self.current_intensity})")
    
    def _on_time_data(self, event_type, data):
        """Process time data updates."""
        # Update the current season
        if "season" in data:
            self.current_season = data["season"]
    
    def _on_hour_changed(self, event_type, data):
        """Handle hourly weather updates."""
        # Check for weather change based on config probabilities
        if random.random() < self.config["hourly_change_chance"]:
            self._update_weather()
    
    def _on_time_period_changed(self, event_type, data):
        """Handle time period changes affecting weather."""
        old_period = data.get("old_period")
        new_period = data.get("new_period")
        
        # Weather changes are more likely at dawn and dusk
        if new_period in ["dawn", "dusk"]:
            if random.random() < 0.5:  # 50% chance
                self._update_weather()
    
    def _update_weather(self):
        """Update the current weather based on configured probabilities."""
        # Get weather chances for current season
        season_chances = self.config["weather_chances"].get(
            self.current_season,
            self.config["weather_chances"]["summer"]  # Default to summer
        )
        
        # Weather persistence - sometimes keep the same weather
        if random.random() < 0.3 and self.current_weather in season_chances:
            # Just update intensity
            self.current_intensity = self._get_random_intensity()
            return
        
        # Choose a new weather type based on season probabilities
        weather_types = list(season_chances.keys())
        weights = list(season_chances.values())
        
        try:
            self.current_weather = random.choices(weather_types, weights=weights, k=1)[0]
            self.current_intensity = self._get_random_intensity()
            
            # Notify about weather change
            self._notify_weather_change()
        except Exception as e:
            print(f"Error updating weather: {e}")
    
    def _get_random_intensity(self):
        """Get a random weather intensity."""
        intensities = list(self.config["intensity_descriptions"].keys())
        weights = [0.4, 0.3, 0.2, 0.1]  # Higher chance for milder weather
        
        return random.choices(intensities, weights=weights, k=1)[0]
    
    def _notify_weather_change(self):
        """Notify the game about weather changes."""
        # Only notify if world and event system are available
        if self.world and self.event_system:
            # Store weather data in world
            self.world.set_plugin_data(self.plugin_id, "current_weather", self.current_weather)
            self.world.set_plugin_data(self.plugin_id, "current_intensity", self.current_intensity)
            
            # Get description
            description = self.config["weather_descriptions"].get(
                self.current_weather, 
                "The weather is changing."
            )
            
            # Publish event
            self.event_system.publish("weather_changed", {
                "weather": self.current_weather,
                "intensity": self.current_intensity,
                "description": description
            })
            
            # If player is outdoors, also send a display message
            if self.data_provider and self.data_provider.is_outdoors_or_has_windows():
                message = f"The weather changes to {self.current_weather} ({self.current_intensity})."
                self.event_system.publish("display_message", message)
    
    def cleanup(self):
        """Clean up plugin resources."""
        if self.event_system:
            self.event_system.unsubscribe("hour_changed", self._on_hour_changed)
            self.event_system.unsubscribe("time_period_changed", self._on_time_period_changed)
            self.event_system.unsubscribe("time_data", self._on_time_data)

"""
utils/colored_text.py
Colored text rendering module for the MUD game.
"""
import pygame
from typing import List, Tuple, Dict, Optional


class ColoredText:
    """
    A utility class for rendering text with color formatting codes.
    """
    def __init__(self, font, format_colors: Dict[str, Tuple[int, int, int]]):
        """
        Initialize the ColoredText renderer.
        
        Args:
            font: The Pygame font to use for rendering.
            format_colors: A dictionary mapping format codes to RGB color tuples.
        """
        self.font = font
        self.format_colors = format_colors
        self.default_color = (255, 255, 255)

    def render(self, surface, text: str, position: Tuple[int, int], default_color=None) -> None:
        """
        Render text with color formatting codes to the given surface.
        Properly handles newlines in the text.
        
        Args:
            surface: The Pygame surface to render onto.
            text: The text to render, which may contain format codes.
            position: The (x, y) position to start rendering.
            default_color: The default text color to use. If None, uses the instance default.
        """
        if default_color is None:
            default_color = self.default_color
        
        x_orig, y = position  # Keep track of original x position for newlines
        x = x_orig
        
        # Split the text into lines first
        lines = text.split('\n')
        line_height = self.font.get_linesize()
        
        for line_idx, line in enumerate(lines):
            # Reset x position for each new line
            x = x_orig
            
            # For empty lines, just advance y
            if not line:
                y += line_height
                continue
                
            # Split the line into segments based on format codes
            segments = self._split_by_format_codes(line)
            
            # Render each segment with its color
            current_color = default_color
            for segment in segments:
                if segment in self.format_colors:
                    # This is a format code, update the current color
                    current_color = self.format_colors[segment]
                else:
                    # This is regular text, render it
                    # Skip any segments containing only control characters
                    if segment and any(ord(c) >= 32 for c in segment):
                        # Replace any control characters with spaces
                        cleaned_segment = ''.join(c if ord(c) >= 32 else ' ' for c in segment)
                        
                        if cleaned_segment:  # Only render non-empty segments
                            text_surface = self.font.render(cleaned_segment, True, current_color)
                            surface.blit(text_surface, (x, y))
                            x += text_surface.get_width()
            
            # Move to the next line
            y += line_height    
    
    def remove_format_codes(self, text: str) -> str:
        """
        Remove all format codes from the text and normalize newlines.
        
        Args:
            text: The text containing format codes.
            
        Returns:
            Text with all format codes removed.
        """
        if not text:
            return ""
            
        # First remove all format codes
        result = text
        for code in self.format_colors.keys():
            result = result.replace(code, "")
        
        # Normalize newlines
        result = result.replace('\r\n', '\n').replace('\r', '\n')
        
        # Replace control characters (except newlines) with spaces
        result = ''.join(c if c == '\n' or ord(c) >= 32 else ' ' for c in result)
        
        # Collapse multiple consecutive newlines into at most two
        while '\n\n\n' in result:
            result = result.replace('\n\n\n', '\n\n')
        
        return result
    
    def _split_by_format_codes(self, text: str) -> List[str]:
        """
        Split the text into segments, separating format codes from regular text.
        
        Args:
            text: The text to split.
            
        Returns:
            A list of segments, where format codes are separate items.
        """
        result = []
        
        # Start with the whole text
        current_text = text
        
        while current_text:
            # Find the earliest format code
            earliest_pos = len(current_text)
            earliest_code = None
            
            for code in self.format_colors.keys():
                pos = current_text.find(code)
                if pos != -1 and pos < earliest_pos:
                    earliest_pos = pos
                    earliest_code = code
            
            if earliest_code is None:
                # No more format codes, add the remaining text
                result.append(current_text)
                break
            
            # Add the text before the format code
            if earliest_pos > 0:
                result.append(current_text[:earliest_pos])
                
            # Add the format code itself
            result.append(earliest_code)
            
            # Continue with the rest of the text
            current_text = current_text[earliest_pos + len(earliest_code):]
        
        return result

# utils/utils.py
# Debug helper to see what's in the string
def debug_string(s):
    print("String content:")
    for i, ch in enumerate(s):
        print(f"Position {i}: '{ch}' (ord: {ord(ch)})")
    print("End of string")

"""
world/region.py
Region module for the MUD game.
"""
from typing import Dict, Optional
from world.room import Room


class Region:
    """
    Represents a collection of rooms forming a region in the game world.
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.rooms: Dict[str, Room] = {}
    
    def add_room(self, room_id: str, room: Room):
        """
        Adds a room to the region.
        """
        self.rooms[room_id] = room
    
    def get_room(self, room_id: str) -> Optional[Room]:
        """
        Returns the room with the given ID, or None if it doesn't exist.
        """
        return self.rooms.get(room_id)

"""
world/room.py
Enhanced Room module for the MUD game.
"""
from typing import Dict, List, Optional
from items.item import Item


class Room:
    # Add to Room.__init__ method:
    def __init__(self, name: str, description: str, exits: Dict[str, str] = None):
        """
        Initialize a room.
        
        Args:
            name: The name of the room.
            description: The description of the room.
            exits: A dictionary mapping directions to destination room IDs.
        """
        self.name = name
        self.description = description
        self.exits = exits or {}  # Direction -> room_id mapping
        self.items: List[Item] = []  # Items in the room
        
        # Additional properties
        self.visited = False  # Whether the player has visited this room
        self.properties = {}  # Custom properties like "dark", "noisy", etc.
        
        # Time-of-day descriptions
        self.time_descriptions = {
            "dawn": "",
            "day": "",
            "dusk": "",
            "night": ""
        }
    
    # Update Room.get_full_description method:
    def get_full_description(self, time_period: str = None) -> str:
        """
        Returns a full textual description of the room, including exits.
        
        Args:
            time_period: The current time period (dawn, day, dusk, night).
            
        Returns:
            A complete room description.
        """
        # Format exits in a more organized way
        exits_list = list(self.exits.keys())
        exits_list.sort()  # Sort directions alphabetically
        exit_desc = ", ".join(exits_list) if exits_list else "none"
        
        # Basic description
        desc = f"{self.name}\n\n{self.description}"
        
        # Add time-specific description if available
        if time_period and time_period in self.time_descriptions and self.time_descriptions[time_period]:
            desc += f"\n\n{self.time_descriptions[time_period]}"
        
        # Add exits
        desc += f"\n\nExits: {exit_desc}"
        
        # Add special property descriptions
        if "dark" in self.properties and self.properties["dark"]:
            # Make darkness more pronounced at night
            if time_period == "night":
                desc = "It's pitch black here. You can barely see anything.\n\n" + desc
            else:
                desc = "It's dark here. You can barely make out your surroundings.\n\n" + desc
                
        if "noisy" in self.properties and self.properties["noisy"]:
            desc += "\n\nThe room is filled with noise."
            
        if "smell" in self.properties:
            desc += f"\n\nYou detect a {self.properties['smell']} smell."
        
        return desc
    
    def get_exit(self, direction: str) -> Optional[str]:
        """
        Returns the destination room ID for the given direction, or None if there's no exit.
        """
        return self.exits.get(direction.lower())
    
    def add_item(self, item: Item) -> None:
        """
        Add an item to the room.
        
        Args:
            item: The item to add.
        """
        self.items.append(item)
    
    def remove_item(self, item_id: str) -> Optional[Item]:
        """
        Remove an item from the room.
        
        Args:
            item_id: The ID of the item to remove.
            
        Returns:
            The removed item, or None if not found.
        """
        for i, item in enumerate(self.items):
            if item.item_id == item_id:
                return self.items.pop(i)
        return None
    
    def get_item(self, item_id: str) -> Optional[Item]:
        """
        Get an item from the room without removing it.
        
        Args:
            item_id: The ID of the item to get.
            
        Returns:
            The item, or None if not found.
        """
        for item in self.items:
            if item.item_id == item_id:
                return item
        return None
    
    # Update Room.to_dict method:
    def to_dict(self) -> Dict:
        """
        Convert the room to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the room.
        """
        return {
            "name": self.name,
            "description": self.description,
            "exits": self.exits,
            "items": [item.to_dict() for item in self.items],
            "visited": self.visited,
            "properties": self.properties,
            "time_descriptions": self.time_descriptions
        }

    # Update Room.from_dict method:
    @classmethod
    def from_dict(cls, data: Dict) -> 'Room':
        """
        Create a room from a dictionary.
        
        Args:
            data: The dictionary containing room data.
            
        Returns:
            A Room instance.
        """
        room = cls(
            name=data["name"],
            description=data["description"],
            exits=data.get("exits", {})
        )
        
        # Set additional properties
        room.visited = data.get("visited", False)
        room.properties = data.get("properties", {})
        
        # Set time descriptions if present
        if "time_descriptions" in data:
            room.time_descriptions = data["time_descriptions"]
        
        # Items will be loaded separately by the world loader
        
        return room

"""
world/world.py
World module for the MUD game.
Represents the game world, containing regions, rooms, NPCs, and items.
"""
from typing import Dict, List, Optional, Any
import time
import json
import os

from player import Player
from world.region import Region
from world.room import Room
from items.item import Item, ItemFactory
from items.inventory import Inventory
from npcs.npc import NPC
from npcs.npc_factory import NPCFactory


class World:
    """
    Represents the game world, containing regions, rooms, NPCs, and items.
    """
    def __init__(self):
        self.regions: Dict[str, Region] = {}
        self.current_region_id: Optional[str] = None
        self.current_room_id: Optional[str] = None
        self.player = Player("Adventurer")
        
        # Add inventory to player
        if not hasattr(self.player, "inventory"):
            self.player.inventory = Inventory(max_slots=20, max_weight=100.0)
        
        # NPCs in the world
        self.npcs: Dict[str, NPC] = {}
        
        # Game time tracking (seconds since game start)
        self.start_time = time.time()
        self.last_update_time = 0
        
        self.plugin_data = {}


    
    def add_region(self, region_id: str, region: Region):
        """
        Adds a region to the world.
        """
        self.regions[region_id] = region
    
    def get_region(self, region_id: str) -> Optional[Region]:
        """
        Returns the region with the given ID, or None if it doesn't exist.
        """
        return self.regions.get(region_id)
    
    def get_current_region(self) -> Optional[Region]:
        """
        Returns the current region the player is in, or None if not set.
        """
        if self.current_region_id:
            return self.regions.get(self.current_region_id)
        return None
    
    def get_current_room(self) -> Optional[Room]:
        """
        Returns the current room the player is in, or None if not set.
        """
        region = self.get_current_region()
        if region and self.current_room_id:
            return region.get_room(self.current_room_id)
        return None
    
    def add_npc(self, npc: NPC):
        """
        Add an NPC to the world.
        
        Args:
            npc: The NPC to add.
        """
        # Initialize the NPC's last_moved time to the current game time
        # This ensures the cooldown starts from when the NPC is added to the world
        npc.last_moved = time.time() - self.start_time
        self.npcs[npc.npc_id] = npc
    
    def get_npc(self, npc_id: str) -> Optional[NPC]:
        """
        Get an NPC by ID.
        
        Args:
            npc_id: The ID of the NPC.
            
        Returns:
            The NPC, or None if not found.
        """
        return self.npcs.get(npc_id)
    
    def get_npcs_in_room(self, region_id: str, room_id: str) -> List[NPC]:
        """
        Get all NPCs in a specific room.
        
        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            
        Returns:
            A list of NPCs in the room.
        """
        return [npc for npc in self.npcs.values() 
                if npc.current_region_id == region_id and npc.current_room_id == room_id]
    
    def get_current_room_npcs(self) -> List[NPC]:
        """
        Get all NPCs in the player's current room.
        
        Returns:
            A list of NPCs in the room.
        """
        if not self.current_region_id or not self.current_room_id:
            return []
            
        return self.get_npcs_in_room(self.current_region_id, self.current_room_id)
    
    def update(self):
        """
        Update the game world state.
        
        Returns:
            A list of messages about world events.
        """
        current_time = time.time() - self.start_time
        messages = []
        
        # Only update every second
        if current_time - self.last_update_time < 1:
            return messages
            
        # Update all NPCs
        for npc in self.npcs.values():
            npc_message = npc.update(self, current_time)
            if npc_message:
                messages.append(npc_message)
        
        self.last_update_time = current_time
        return messages

    """
    Updated version of World.change_room method to support plugin notifications.
    This should replace the existing method in the World class.
    """

    def change_room(self, direction: str) -> str:
        """
        Attempts to move the player in the given direction.
        Returns a description of the result.
        """
        # Store old location
        old_region_id = self.current_region_id
        old_room_id = self.current_room_id
        
        current_room = self.get_current_room()
        if not current_room:
            return "You are nowhere."
        
        new_room_id = current_room.get_exit(direction)
        if not new_room_id:
            return f"You can't go {direction}."
        
        # Check if room exists in current region
        region = self.get_current_region()
        if region and new_room_id in region.rooms:
            self.current_room_id = new_room_id
            
            # Get NPCs in the new room
            npcs_in_room = self.get_current_room_npcs()
            npc_descriptions = ""
            
            if npcs_in_room:
                npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
            
            # Notify plugins about room change if game manager is available
            if hasattr(self, "game") and hasattr(self.game, "plugin_manager"):
                # Notify about room exit
                self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
                
                # Notify about room enter
                self.game.plugin_manager.on_room_enter(self.current_region_id, self.current_room_id)
            
            return self.get_current_room().get_full_description() + npc_descriptions
        
        # Check if it's a special format for region transition: region_id:room_id
        if ":" in new_room_id:
            new_region_id, new_room_id = new_room_id.split(":")
            if new_region_id in self.regions:
                new_region = self.regions[new_region_id]
                if new_room_id in new_region.rooms:
                    # Update location
                    self.current_region_id = new_region_id
                    self.current_room_id = new_room_id
                    
                    # Get NPCs in the new room
                    npcs_in_room = self.get_current_room_npcs()
                    npc_descriptions = ""
                    
                    if npcs_in_room:
                        npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
                    
                    # Notify plugins about room change if game manager is available
                    if hasattr(self, "game") and hasattr(self.game, "plugin_manager"):
                        # Notify about room exit
                        self.game.plugin_manager.on_room_exit(old_region_id, old_room_id)
                        
                        # Notify about room enter
                        self.game.plugin_manager.on_room_enter(self.current_region_id, self.current_room_id)
                    
                    return f"You've entered {new_region.name}.\n\n{self.get_current_room().get_full_description()}{npc_descriptions}"
        
        return "That exit leads nowhere usable."
    
    # Update World.look method:
    def look(self) -> str:
        """
        Returns a description of the current room.
        """
        current_room = self.get_current_room()
        if current_room:
            # Get the current time period from time plugin if available
            time_period = None
            if hasattr(self, "plugin_data") and "time_plugin" in self.plugin_data:
                time_period = self.plugin_data["time_plugin"].get("current_time_period")
            
            # Get room description with time period
            room_desc = current_room.get_full_description(time_period)
            
            # Get NPCs in the room
            npcs_in_room = self.get_current_room_npcs()
            npc_descriptions = ""
            
            if npcs_in_room:
                npc_descriptions = "\n\n" + "\n".join([f"{npc.name} is here." for npc in npcs_in_room])
            
            # Get items in the room
            items_in_room = self.get_items_in_current_room()
            item_descriptions = ""
            
            if items_in_room:
                item_descriptions = "\n\n" + "\n".join([f"There is {item.name} here." for item in items_in_room])
            
            return room_desc + npc_descriptions + item_descriptions
            
        return "You are nowhere."
        
    def get_player_status(self) -> str:
        """
        Returns the player's status information.
        """
        status = self.player.get_status()
        
        # Add inventory information if the player has an inventory
        if hasattr(self.player, "inventory"):
            inventory_desc = "\n\n" + self.player.inventory.list_items()
            status += inventory_desc
            
        return status
        
    def get_items_in_room(self, region_id: str, room_id: str) -> List[Item]:
        """
        Get all items in a specific room.
        
        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            
        Returns:
            A list of items in the room.
        """
        region = self.get_region(region_id)
        if not region:
            return []
            
        room = region.get_room(room_id)
        if not room:
            return []
            
        return room.items if hasattr(room, "items") else []
    
    def get_items_in_current_room(self) -> List[Item]:
        """
        Get all items in the player's current room.
        
        Returns:
            A list of items in the room.
        """
        if not self.current_region_id or not self.current_room_id:
            return []
            
        return self.get_items_in_room(self.current_region_id, self.current_room_id)
    
    def add_item_to_room(self, region_id: str, room_id: str, item: Item) -> bool:
        """
        Add an item to a room.
        
        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            item: The item to add.
            
        Returns:
            True if successful, False otherwise.
        """
        region = self.get_region(region_id)
        if not region:
            return False
            
        room = region.get_room(room_id)
        if not room:
            return False
            
        # Initialize the items list if it doesn't exist
        if not hasattr(room, "items"):
            room.items = []
            
        room.items.append(item)
        return True
    
    def remove_item_from_room(self, region_id: str, room_id: str, item_id: str) -> Optional[Item]:
        """
        Remove an item from a room.
        
        Args:
            region_id: The ID of the region.
            room_id: The ID of the room.
            item_id: The ID of the item to remove.
            
        Returns:
            The removed item, or None if not found.
        """
        items = self.get_items_in_room(region_id, room_id)
        for i, item in enumerate(items):
            if item.item_id == item_id:
                return items.pop(i)
                
        return None

    # Update World.save_to_json method:
    def save_to_json(self, filename: str) -> bool:
        """
        Save the world state to a JSON file.
        
        Args:
            filename: The filename to save to.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Build a dictionary representing the world state
            world_data = {
                "current_region_id": self.current_region_id,
                "current_room_id": self.current_room_id,
                "player": self.player.to_dict(),
                "regions": {},
                "npcs": {},
                "plugin_data": self.plugin_data  # Save plugin data
            }
            
            # Save regions and their rooms
            for region_id, region in self.regions.items():
                region_data = {
                    "name": region.name,
                    "description": region.description,
                    "rooms": {}
                }
                
                for room_id, room in region.rooms.items():
                    room_data = room.to_dict()
                    # Convert items to dictionary format
                    room_data["items"] = [item.to_dict() for item in getattr(room, "items", [])]
                    region_data["rooms"][room_id] = room_data
                
                world_data["regions"][region_id] = region_data
            
            # Save NPCs
            for npc_id, npc in self.npcs.items():
                world_data["npcs"][npc_id] = npc.to_dict()
            
            # Write to file
            with open(filename, 'w') as f:
                json.dump(world_data, f, indent=2)
                
            return True
            
        except Exception as e:
            print(f"Error saving world: {e}")
            return False

    # Update World.load_from_json method:
    def load_from_json(self, filename: str) -> bool:
        """
        Load the world state from a JSON file.
        
        Args:
            filename: The filename to load from.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Check if file exists
            if not os.path.exists(filename):
                print(f"File not found: {filename}")
                return False
                
            # Read the file
            with open(filename, 'r') as f:
                world_data = json.load(f)
            
            # Clear current state
            self.regions = {}
            self.npcs = {}
            
            # Set game start time
            self.start_time = time.time()
            
            # Load plugin data if available
            if "plugin_data" in world_data:
                self.plugin_data = world_data["plugin_data"]
            else:
                self.plugin_data = {}
            
            # Load player
            if "player" in world_data:
                self.player = Player.from_dict(world_data["player"])
            
            # Load regions and rooms
            for region_id, region_data in world_data.get("regions", {}).items():
                region = Region(region_data["name"], region_data["description"])
                
                # Load rooms
                for room_id, room_data in region_data.get("rooms", {}).items():
                    room = Room.from_dict(room_data)
                    
                    # Load items in the room
                    if "items" in room_data:
                        room.items = []
                        for item_data in room_data["items"]:
                            item = ItemFactory.from_dict(item_data)
                            room.items.append(item)
                    
                    region.add_room(room_id, room)
                
                self.add_region(region_id, region)
            
            # Load NPCs
            current_time = time.time() - self.start_time
            for npc_id, npc_data in world_data.get("npcs", {}).items():
                npc = NPC.from_dict(npc_data)
                
                # Initialize last_moved time to current time to ensure proper cooldown
                npc.last_moved = current_time
                self.npcs[npc_id] = npc
            
            # Set current location
            self.current_region_id = world_data.get("current_region_id")
            self.current_room_id = world_data.get("current_room_id")
            
            return True
            
        except Exception as e:
            print(f"Error loading world: {e}")
            return False

    # Add method to store plugin data:
    def set_plugin_data(self, plugin_id: str, key: str, value: Any) -> None:
        """
        Store plugin-specific data in the world.
        
        Args:
            plugin_id: The ID of the plugin.
            key: The data key.
            value: The data value.
        """
        if plugin_id not in self.plugin_data:
            self.plugin_data[plugin_id] = {}
        self.plugin_data[plugin_id][key] = value

    # Add method to retrieve plugin data:
    def get_plugin_data(self, plugin_id: str, key: str, default: Any = None) -> Any:
        """
        Retrieve plugin-specific data from the world.
        
        Args:
            plugin_id: The ID of the plugin.
            key: The data key.
            default: The default value if not found.
            
        Returns:
            The stored data value, or default if not found.
        """
        if plugin_id not in self.plugin_data:
            return default
        return self.plugin_data[plugin_id].get(key, default)

