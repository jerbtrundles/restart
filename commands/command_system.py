# commands/command_system.py
# --- THIS IS THE REFACTORED AND CORRECTED VERSION ---
# - Corrected type hints in the @command decorator for 'aliases' and 'plugin_id'.
# - Added a # type: ignore comment to resolve the Pylance error on wrapper._command_info.
# - Removed the obsolete and unnecessary register_command_module function.

from typing import Callable, List, Dict, Any, Optional, Set
from functools import wraps
import inspect

from core.config import FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_TITLE, HELP_MAX_COMMANDS_PER_CATEGORY

# Dictionary to store all registered commands
registered_commands: Dict[str, Dict[str, Any]] = {}
command_groups: Dict[str, List[Dict[str, Any]]] = {
    "movement": [], "interaction": [], "inventory": [],
    "combat": [], "magic": [], "system": [], "other": []
}

# Direction aliases for movement commands
direction_aliases = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest",
    "u": "up", "d": "down"
}

# --- MODIFIED: Corrected Type Hints and Logic ---
def command(name: str, aliases: Optional[List[str]] = None, category: str = "other",
           help_text: str = "No help available.", plugin_id: Optional[str] = None):
    """
    Decorator for registering game commands.
    """
    # Use idiomatic default for optional list
    aliases = aliases or []

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # --- MODIFIED: Added '# type: ignore' to resolve Pylance error ---
        wrapper._command_info = { # type: ignore
            "name": name,
            "aliases": aliases,
            "category": category,
            "help_text": help_text,
            "plugin_id": plugin_id
        }
        
        cmd_data = {
            "name": name,
            "aliases": aliases,
            "handler": wrapper,
            "help_text": help_text,
            "category": category,
            "plugin_id": plugin_id
        }
        
        registered_commands[name] = cmd_data
        for alias in aliases:
            registered_commands[alias] = cmd_data
            
        if category in command_groups:
            command_groups[category].append(cmd_data)
        else:
            # Create category if it doesn't exist (useful for plugins)
            command_groups.setdefault(category, []).append(cmd_data)
        
        return wrapper
    return decorator

def get_registered_commands() -> Dict[str, Dict[str, Any]]:
    """Get all registered commands."""
    return registered_commands

def get_command_groups() -> Dict[str, List[Dict[str, Any]]]:
    """Get commands organized by category."""
    return command_groups

def unregister_command(name: str) -> bool:
    """Unregister a command and all its aliases."""
    if name not in registered_commands:
        return False
        
    cmd_data = registered_commands[name]
    cmd_name = cmd_data["name"]
    cmd_aliases = cmd_data["aliases"]
    cmd_category = cmd_data["category"]
    
    # Remove from main dictionary by primary name
    if cmd_name in registered_commands:
        del registered_commands[cmd_name]
    
    # Remove all aliases
    for alias in cmd_aliases:
        if alias in registered_commands:
            del registered_commands[alias]
    
    # Remove from category group
    if cmd_category in command_groups:
        command_groups[cmd_category] = [c for c in command_groups[cmd_category] if c["name"] != cmd_name]
    
    return True

def unregister_plugin_commands(plugin_id: str) -> int:
    """Unregister all commands registered by a specific plugin."""
    if not plugin_id: return 0
        
    # Find all primary command names associated with this plugin
    plugin_command_names = [
        cmd_data["name"] for cmd_data in registered_commands.values()
        if cmd_data.get("plugin_id") == plugin_id
    ]
    # Use a set to avoid unregistering the same command multiple times
    unique_names_to_unregister = set(plugin_command_names)
    
    count = 0
    for cmd_name in unique_names_to_unregister:
        if unregister_command(cmd_name):
            count += 1
    
    return count

class CommandProcessor:
    """Processes user input and dispatches commands to appropriate handlers."""

    def process_input(self, text: str, context: Any = None) -> str:
        """Process user input and execute the corresponding command."""
        text = text.strip().lower()
        if not text: return ""
        parts = text.split()
        command_word = parts[0]
        args = parts[1:] if len(parts) > 1 else []
        
        if command_word in direction_aliases:
            command_word = direction_aliases[command_word]

        if command_word in registered_commands:
            cmd = registered_commands[command_word]
            if context and isinstance(context, dict):
                 context['executed_command_name'] = cmd.get('name', command_word)
                 context['executed_command_aliases'] = cmd.get('aliases', [])
            return cmd["handler"](args, context)

        return f"{FORMAT_ERROR}Unknown command: {command_word}{FORMAT_RESET}"

    def get_help_text(self) -> str:
        """Generate the top-level help text showing categories and commands."""
        help_text = f"{FORMAT_TITLE}===== Pygame MUD Help ====={FORMAT_RESET}\n\n"
        help_text += "Interact by typing commands. Use the following categories for guidance:\n\n"
        help_text += f"{FORMAT_HIGHLIGHT}How to Get More Help:{FORMAT_RESET}\n"
        help_text += f"  - Type '{FORMAT_HIGHLIGHT}help <category>{FORMAT_RESET}' for all commands in a category.\n"
        help_text += f"  - Type '{FORMAT_HIGHLIGHT}help <command>{FORMAT_RESET}' for details on a specific command.\n\n"
        help_text += f"{FORMAT_TITLE}Command Categories & Examples:{FORMAT_RESET}\n"
        
        categories = sorted([cat for cat, cmds in command_groups.items() if cmds])
        max_cmds_to_show = HELP_MAX_COMMANDS_PER_CATEGORY

        for category in categories:
            commands_in_category = command_groups[category]
            unique_primary_names = sorted(list({cmd['name'] for cmd in commands_in_category}))
            command_list_str = ""
            if unique_primary_names:
                if len(unique_primary_names) > max_cmds_to_show:
                    command_list_str = ", ".join(unique_primary_names[:max_cmds_to_show]) + ", ..."
                else:
                    command_list_str = ", ".join(unique_primary_names)
            help_text += f"  - {FORMAT_CATEGORY}{category.capitalize()}{FORMAT_RESET}"
            if command_list_str:
                help_text += f" ({FORMAT_HIGHLIGHT}{command_list_str}{FORMAT_RESET})\n"
            else:
                help_text += "\n"
        help_text += "\n"
        
        help_text += f"{FORMAT_TITLE}Getting Started Examples:{FORMAT_RESET}\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}look{FORMAT_RESET}\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}north{FORMAT_RESET} (or {FORMAT_HIGHLIGHT}n{FORMAT_RESET})\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}take potion{FORMAT_RESET}\n"
        help_text += f"  - {FORMAT_HIGHLIGHT}inventory{FORMAT_RESET}\n\n"
        help_text += f"{FORMAT_TITLE}Other Tips:{FORMAT_RESET}\n"
        help_text += "  - Use Up/Down arrows for command history.\n"
        help_text += "  - Use Tab for command/category completion.\n"
        help_text += "  - Use PageUp/PageDown/Mouse Wheel to scroll text.\n"

        return help_text
    
    def get_command_help(self, command_or_category_name: str) -> str:
        """Get detailed help for a specific command OR a category."""
        name_lower = command_or_category_name.lower()

        if name_lower in command_groups and command_groups[name_lower]:
            return self._get_category_help(name_lower)

        if name_lower in direction_aliases:
            name_lower = direction_aliases[name_lower]

        if name_lower in registered_commands:
            cmd = registered_commands[name_lower]
            help_text = f"{FORMAT_TITLE}Command: {cmd['name'].upper()}{FORMAT_RESET}\n\n"
            help_text += f"{FORMAT_CATEGORY}Category:{FORMAT_RESET} {cmd['category'].capitalize()}\n"
            if cmd['aliases']:
                help_text += f"{FORMAT_CATEGORY}Aliases:{FORMAT_RESET} {', '.join(cmd['aliases'])}\n"
            help_text += f"\n{FORMAT_CATEGORY}Description:{FORMAT_RESET}\n"
            for line in cmd['help_text'].split('\n'):
                help_text += f"  {line}\n"
            return help_text

        return f"{FORMAT_ERROR}No help found for '{command_or_category_name}'. It is not a valid command or category.{FORMAT_RESET}\nType '{FORMAT_HIGHLIGHT}help{FORMAT_RESET}' for available categories."
    
    def get_command_suggestions(self, partial_command: str) -> List[str]:
        """Get a list of commands that start with the given partial command."""
        partial = partial_command.lower()
        suggestions = set()

        for cmd_name, cmd_data in registered_commands.items():
            primary_name = cmd_data['name']
            if primary_name.startswith(partial): suggestions.add(primary_name)
            for alias in cmd_data.get('aliases', []):
                 if alias.startswith(partial): suggestions.add(alias)
        for alias, direction in direction_aliases.items():
            if alias.startswith(partial): suggestions.add(alias)
        for category_name in command_groups.keys():
             if category_name.startswith(partial): suggestions.add(category_name)

        return sorted(list(suggestions))

    def _get_category_help(self, category_name: str) -> str:
        """Generate help text for a specific command category."""
        category_name_lower = category_name.lower()
        commands_in_category = command_groups[category_name_lower]
        help_text = f"{FORMAT_TITLE}Help: {category_name.capitalize()} Commands{FORMAT_RESET}\n\n"
        
        unique_commands = {}
        for cmd in commands_in_category:
            handler_id = id(cmd["handler"])
            if handler_id not in unique_commands:
                unique_commands[handler_id] = cmd
        
        sorted_unique_commands = sorted(unique_commands.values(), key=lambda c: c["name"])
        for cmd in sorted_unique_commands:
            aliases = f" ({', '.join(cmd['aliases'])})" if cmd['aliases'] else ""
            first_line_help = cmd['help_text'].split('\n')[0]
            help_text += f"  {FORMAT_HIGHLIGHT}{cmd['name']}{aliases}{FORMAT_RESET}\n"
            help_text += f"    - {first_line_help}\n"
        help_text += f"\nType '{FORMAT_HIGHLIGHT}help <command>{FORMAT_RESET}' for more details on a specific command."
        return help_text