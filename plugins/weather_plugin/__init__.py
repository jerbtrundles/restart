"""
plugins/weather_plugin/__init__.py
Weather plugin for the MUD game.
Implements a dynamic weather system affected by time of day and season.
"""
import random
from typing import Dict, Any
from core.config import WEATHER_INTENSITY_WEIGHTS, WEATHER_PERSISTENCE_CHANCE, WEATHER_TRANSITION_CHANGE_CHANCE
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
            if random.random() < WEATHER_TRANSITION_CHANGE_CHANCE:
                self._update_weather()
    
    def _update_weather(self):
        """Update the current weather based on configured probabilities."""
        # Get weather chances for current season
        season_chances = self.config["weather_chances"].get(
            self.current_season,
            self.config["weather_chances"]["summer"]  # Default to summer
        )
        
        # Weather persistence - sometimes keep the same weather
        if random.random() < WEATHER_PERSISTENCE_CHANCE and self.current_weather in season_chances:
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
        return random.choices(intensities, weights=WEATHER_INTENSITY_WEIGHTS, k=1)[0]
    
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