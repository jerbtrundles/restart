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