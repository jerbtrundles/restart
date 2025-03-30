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
command_groups: Dict[str, List[Dict[str, Any]]] = {
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
        if category in command_groups:
            command_groups[category].append(cmd_data)
        else:
            command_groups["other"].append(cmd_data)
        
        return wrapper
    return decorator

def get_registered_commands() -> Dict[str, Dict[str, Any]]:
    """
    Get all registered commands.
    
    Returns:
        Dictionary of command name to command data.
    """
    return registered_commands

def get_command_groups() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get commands organized by category.
    
    Returns:
        Dictionary of category name to list of commands.
    """
    return command_groups

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
    if cmd_category in command_groups:
        command_groups[cmd_category] = [c for c in command_groups[cmd_category] 
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
        
        # Look for matching command directly in registered_commands
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
        for category, commands in command_groups.items():
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