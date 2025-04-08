"""
commands/command_system.py
Unified command system for the MUD game.
Consolidates different command approaches into a single system.
"""
from typing import Callable, List, Dict, Any, Optional, Set
from functools import wraps
import inspect

from core.config import FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_TITLE, HELP_MAX_COMMANDS_PER_CATEGORY

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
        # Commands are stored in a global registry
        pass

    def process_input(self, text: str, context: Any = None) -> str:
        """
        Process user input and execute the corresponding command.
        """
        text = text.strip().lower()
        if not text: return ""
        parts = text.split()
        command_word = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        if command_word in direction_aliases: command_word = direction_aliases[command_word]

        if command_word in registered_commands:
            cmd = registered_commands[command_word]
            # --- Add context about the specific command being executed ---
            # This isn't strictly necessary for help, but useful elsewhere
            if context and isinstance(context, dict):
                 context['executed_command_name'] = cmd.get('name', command_word)
                 context['executed_command_aliases'] = cmd.get('aliases', [])
            # --- End context addition ---
            return cmd["handler"](args, context)

        return f"{FORMAT_ERROR}Unknown command: {command_word}{FORMAT_RESET}" # Use error format

    def get_help_text(self) -> str:
        """Generate the top-level help text showing categories and associated commands."""
        help_text = f"{FORMAT_TITLE}===== Pygame MUD Help ====={FORMAT_RESET}\n\n"
        help_text += "Interact by typing commands. Use the following categories for guidance:\n\n" # Simplified intro

        help_text += f"{FORMAT_HIGHLIGHT}How to Get More Help:{FORMAT_RESET}\n"
        help_text += f"  - Type '{FORMAT_HIGHLIGHT}help <category>{FORMAT_RESET}' for all commands in a category.\n" # Clarified help <category> usage
        help_text += f"  - Type '{FORMAT_HIGHLIGHT}help <command>{FORMAT_RESET}' for details on a specific command.\n\n"

        help_text += f"{FORMAT_TITLE}Command Categories & Examples:{FORMAT_RESET}\n"
        # List categories alphabetically, skipping empty ones
        categories = sorted([cat for cat, cmds in command_groups.items() if cmds])

        # --- MODIFIED CATEGORY LISTING ---
        max_cmds_to_show = HELP_MAX_COMMANDS_PER_CATEGORY

        for category in categories:
            commands_in_category = command_groups[category]
            if not commands_in_category: continue # Skip empty (shouldn't happen with outer check, but safe)

            # Get unique primary command names for this category
            unique_primary_names = sorted(list({cmd['name'] for cmd in commands_in_category}))

            # Create the command list string with potential truncation
            command_list_str = ""
            if unique_primary_names:
                if len(unique_primary_names) > max_cmds_to_show:
                    command_list_str = ", ".join(unique_primary_names[:max_cmds_to_show]) + ", ..."
                else:
                    command_list_str = ", ".join(unique_primary_names)

            # Add the line to the help text
            help_text += f"  - {FORMAT_CATEGORY}{category.capitalize()}{FORMAT_RESET}"
            if command_list_str:
                # Add commands in highlight color
                help_text += f" ({FORMAT_HIGHLIGHT}{command_list_str}{FORMAT_RESET})\n"
            else:
                help_text += "\n" # Just newline if no commands somehow
        help_text += "\n"
        # --- END MODIFIED CATEGORY LISTING ---

        # Keep Getting Started and Other Tips sections
        help_text += f"{FORMAT_TITLE}Getting Started Examples:{FORMAT_RESET}\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}look{FORMAT_RESET}\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}north{FORMAT_RESET} (or {FORMAT_HIGHLIGHT}n{FORMAT_RESET})\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}take potion{FORMAT_RESET}\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}inventory{FORMAT_RESET}\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}talk <npc_name>{FORMAT_RESET}\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}attack goblin{FORMAT_RESET}\n\n"

        help_text += f"{FORMAT_TITLE}Other Tips:{FORMAT_RESET}\n"
        help_text += "  - Use Up/Down arrows for command history.\n"
        help_text += "  - Use Tab for command/category completion.\n"
        help_text += "  - Use PageUp/PageDown/Mouse Wheel to scroll text.\n"

        return help_text
    
    def get_command_help(self, command_or_category_name: str) -> str:
        """Get detailed help for a specific command OR a category."""
        name_lower = command_or_category_name.lower()

        # --- Check if it's a category name ---
        if name_lower in command_groups and command_groups[name_lower]:
            return self._get_category_help(name_lower)

        # --- If not a category, assume it's a command name ---
        # Normalize potential direction aliases
        if name_lower in direction_aliases:
            name_lower = direction_aliases[name_lower]

        if name_lower in registered_commands:
            cmd = registered_commands[name_lower]

            help_text = f"{FORMAT_TITLE}Command: {cmd['name'].upper()}{FORMAT_RESET}\n\n"
            help_text += f"{FORMAT_CATEGORY}Category:{FORMAT_RESET} {cmd['category'].capitalize()}\n"

            if cmd['aliases']:
                help_text += f"{FORMAT_CATEGORY}Aliases:{FORMAT_RESET} {', '.join(cmd['aliases'])}\n"

            # Display full help text, nicely formatted
            help_text += f"\n{FORMAT_CATEGORY}Description:{FORMAT_RESET}\n"
            # Indent the description for readability
            description_lines = cmd['help_text'].split('\n')
            for line in description_lines:
                help_text += f"  {line}\n" # Add indentation

            # Add examples if available (could be parsed from help_text or added explicitly)
            # Example parsing (simple):
            usage_lines = [line.strip() for line in description_lines if line.strip().lower().startswith("usage:")]
            if usage_lines:
                help_text += f"\n{FORMAT_CATEGORY}Usage:{FORMAT_RESET}\n"
                for usage in usage_lines:
                    # Remove "Usage: " prefix and display
                    help_text += f"  {usage[len('usage: '):].strip()}\n"

            return help_text

        # No matching command or category found
        return f"{FORMAT_ERROR}No help found for '{command_or_category_name}'. It is not a valid command or category.{FORMAT_RESET}\nType '{FORMAT_HIGHLIGHT}help{FORMAT_RESET}' for available categories."
    
    def get_command_suggestions(self, partial_command: str) -> List[str]:
        """ Get a list of commands that start with the given partial command."""
        partial = partial_command.lower()
        suggestions = set() # Use a set to avoid duplicates easily

        # Check command names and aliases
        for cmd_name, cmd_data in registered_commands.items():
            primary_name = cmd_data['name']
            if primary_name.startswith(partial):
                 suggestions.add(primary_name)
            for alias in cmd_data.get('aliases', []):
                 if alias.startswith(partial):
                      suggestions.add(alias)

        # Also check direction aliases (these might not be in registered_commands aliases)
        for alias, direction in direction_aliases.items():
            if alias.startswith(partial):
                suggestions.add(alias)

        # Also check category names for `help <category>` completion
        for category_name in command_groups.keys():
             if category_name.startswith(partial):
                  suggestions.add(category_name) # Add category name itself

        return sorted(list(suggestions))

    # --- NEW: Helper for Category Help ---
    def _get_category_help(self, category_name: str) -> str:
        """Generate help text for a specific command category."""
        category_name_lower = category_name.lower()
        if category_name_lower not in command_groups or not command_groups[category_name_lower]:
            return f"{FORMAT_ERROR}Unknown help category: '{category_name}'{FORMAT_RESET}"

        commands_in_category = command_groups[category_name_lower]

        help_text = f"{FORMAT_TITLE}Help: {category_name.capitalize()} Commands{FORMAT_RESET}\n\n"

        # Group by unique command handler to avoid listing aliases separately here
        unique_commands = {}
        for cmd in commands_in_category:
            handler_id = id(cmd["handler"]) # Use handler identity
            if handler_id not in unique_commands:
                unique_commands[handler_id] = cmd

        # Sort unique commands by name
        sorted_unique_commands = sorted(unique_commands.values(), key=lambda c: c["name"])

        for cmd in sorted_unique_commands:
            aliases = f" ({', '.join(cmd['aliases'])})" if cmd['aliases'] else ""
            # Get the first line of the help text for a brief description
            first_line_help = cmd['help_text'].split('\n')[0] if cmd['help_text'] else "No description."
            help_text += f"  {FORMAT_HIGHLIGHT}{cmd['name']}{aliases}{FORMAT_RESET}\n"
            help_text += f"    - {first_line_help}\n"
        help_text += f"\nType '{FORMAT_HIGHLIGHT}help <command>{FORMAT_RESET}' for more details on a specific command."
        return help_text

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