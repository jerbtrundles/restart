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
        """Initialize the plugin, loading saved state if available."""

        loaded_from_save = False
        # --- Load Saved State ---
        if self.world and hasattr(self.world, 'plugin_data'):
            # Load the entire time_state block saved by _update_world_time_data
            plugin_state = self.world.get_plugin_data(self.plugin_id, "time_state", {}) # Use get_plugin_data

            if plugin_state: # Check if data was actually loaded
                self.game_time = plugin_state.get("game_time", 0) # Load game_time preferentially
                self.hour = plugin_state.get("hour", 12)
                self.minute = plugin_state.get("minute", 0)
                self.day = plugin_state.get("day", 1)
                self.month = plugin_state.get("month", 1)
                self.year = plugin_state.get("year", 1)
                # Time period will be recalculated below based on loaded hour
                print(f"[TimePlugin] Loaded time state: Y{self.year} M{self.month} D{self.day} {self.hour:02d}:{self.minute:02d} (game_time: {self.game_time})")
                loaded_from_save = True
            else:
                 print("[TimePlugin] No saved time state found in world data, using defaults.")
                 self.game_time = 0 # Ensure default if no state loaded
        else:
            print("[TimePlugin] Warning: World or plugin_data not available during init, starting with default time.")
            self.game_time = 0 # Ensure default if world missing

        # Register event listeners AFTER potentially loading state
        if self.event_system:
            self.event_system.subscribe("on_tick", self._on_tick)

        # Register commands (as before)
        from .commands import register_commands
        register_commands(self)

        # Set last_real_time *after* potentially loading game_time
        self.last_real_time = time.time()

        # Ensure time period and world data reflect loaded/current state
        self._update_time_period() # Recalculate period based on loaded hour
        self._update_world_time_data() # Push the (potentially loaded) state back to world data

        print(f"Time plugin initialized. Current time: {self.hour:02d}:{self.minute:02d}. Period: {self.current_time_period}")
    
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
        seasons = ["winter", "spring", "summer", "fall"]
        season_idx = ((self.month - 1) // 3) % 4
        current_season = seasons[season_idx]
        
        time_data = {
            "game_time": self.game_time,
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
            # Use set_plugin_data for the whole block for efficiency
            self.world.set_plugin_data(self.plugin_id, "time_state", time_data) # Save as one block

        # Publish time data event (consider publishing the whole block)
        if self.event_system:
            self.event_system.publish("time_data", time_data) # Publish the whole dict
    
    def cleanup(self):
        """Clean up plugin resources."""
        if self.event_system:
            self.event_system.unsubscribe("on_tick", self._on_tick)