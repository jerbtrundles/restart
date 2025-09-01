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
        # --- Publish the generic 'tick' event ---
        # This is what TimePlugin._on_tick is listening for
        if self.event_system:
            # --- DEBUG PRINT ---
            # print(f"[PluginManager] Publishing 'on_tick' event with time: {current_time:.2f}")
            # --- END DEBUG ---
            self.event_system.publish("on_tick", {"current_time": current_time})
                    
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
                          aliases: Optional[List[str]] = None, category: str = "other", 
                          help_text: str = "No help available.") -> bool:
    """
    Register a command for a plugin.
    """
    # Import from command_system to ensure we're using the right structure
    from commands.command_system import command, command_groups, registered_commands
    
    # Check if command already exists
    if name in registered_commands and registered_commands[name].get("plugin_id") != plugin_id:
        # Command exists and is owned by a different plugin or the core system
        return False
    
    # Use the command decorator directly
    wrapped_handler = wrap_plugin_command_handler(plugin_id, handler)
    decorated_handler = command(
        name=name,
        aliases=aliases or [],
        category=category,
        help_text=help_text,
        plugin_id=plugin_id
    )(wrapped_handler)
    
    # The command is now registered through the decorator
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