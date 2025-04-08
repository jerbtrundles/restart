# plugins/time_plugin/__init__.py
import time
from typing import Dict, Any
from plugins.plugin_system import PluginBase
# --- Add imports for config ---
from core.config import FORMAT_ERROR, FORMAT_RESET, FORMAT_HIGHLIGHT, FORMAT_SUCCESS, TIME_PLUGIN_MAX_CATCHUP_SECONDS, TIME_PLUGIN_UPDATE_THRESHOLD
# --- End imports ---

class TimePlugin(PluginBase):
    plugin_id = "time_plugin"
    plugin_name = "Time and Calendar"

    def __init__(self, world=None, command_processor=None, event_system=None, data_provider=None, service_locator=None):
        """Initialize the time plugin."""
        super().__init__(world, command_processor, event_system)
        self.data_provider = data_provider
        self.service_locator = service_locator

        self._tick_called_flag = False # <<< ADD FLAG

        # Import config from the config.py file
        from .config import DEFAULT_CONFIG
        self.config = DEFAULT_CONFIG.copy()

        # Time tracking
        self.game_time: float = 0.0  # <<< Use float for more precision
        self.last_real_time: float = 0.0 # <<< Initialize as float

        # Time periods
        self.time_periods = ["dawn", "day", "dusk", "night"]
        self.current_time_period = "day"

        # Initialize time data
        self.hour = 12
        self.minute = 0
        self.day = 1
        self.month = 1
        self.year = 1
        self.update_count = 0 # <<< Add for debugging

    def initialize(self):
        """Initialize the plugin, loading saved state if available."""
        if self.event_system:
            # <<< MAKE SURE THIS EXACT EVENT NAME IS PUBLISHED by PluginManager >>>
            self.event_system.subscribe("on_tick", self._on_tick)
        else:
            print(f"{FORMAT_ERROR}[TimePlugin] Warning: Event system not available.{FORMAT_RESET}")

        if self.world and hasattr(self.world, 'plugin_data'):
            plugin_state = self.world.get_plugin_data(self.plugin_id, "time_state", {})

            if plugin_state:
                self.game_time = float(plugin_state.get("game_time", 0.0)) # <<< Load as float
                self.hour = plugin_state.get("hour", 12)
                self.minute = plugin_state.get("minute", 0)
                self.day = plugin_state.get("day", 1)
                self.month = plugin_state.get("month", 1)
                self.year = plugin_state.get("year", 1)
                # --- Recalculate based on game_time on load for consistency ---
                self._recalculate_date_from_game_time()
                # --- End Recalculation ---
                print(f"[TimePlugin] Loaded time state: Y{self.year} M{self.month} D{self.day} {self.hour:02d}:{self.minute:02d} (game_time: {self.game_time:.2f})") # Show float game_time
                loaded_from_save = True
            else:
                 print("[TimePlugin] No saved time state found, using defaults.")
                 self.game_time = 0.0 # Ensure default if no state loaded
                 self._recalculate_date_from_game_time() # Calculate based on 0 time
        else:
            print("[TimePlugin] Warning: World or plugin_data not available during init, starting with default time.")
            self.game_time = 0.0 # Ensure default if world missing
            self._recalculate_date_from_game_time()

        # Register event listeners AFTER potentially loading state
        if self.event_system:
            self.event_system.subscribe("on_tick", self._on_tick)
        else:
            print(f"{FORMAT_ERROR}[TimePlugin] Warning: Event system not available.{FORMAT_RESET}")


        # Register commands (as before)
        from .commands import register_commands
        register_commands(self)

        # Set last_real_time *after* potentially loading game_time
        self.last_real_time = time.time() # <<< Use time.time() directly

        # Ensure time period and world data reflect loaded/current state
        self._update_time_period() # Recalculate period based on loaded/recalculated hour
        self._update_world_time_data() # Push the (potentially loaded) state back to world data

        print(f"Time plugin initialized. Current time: {self.hour:02d}:{self.minute:02d}. Period: {self.current_time_period}")

    def _on_tick(self, event_type, data):
        if not self._tick_called_flag: # Print once flag
            print(f"{FORMAT_SUCCESS}[TimePlugin] _on_tick HAS BEEN CALLED!{FORMAT_RESET}")
            self._tick_called_flag = True

        current_real_time = time.time()
        elapsed_real_time = current_real_time - self.last_real_time
        elapsed_real_time = min(elapsed_real_time, TIME_PLUGIN_MAX_CATCHUP_SECONDS)
        self.last_real_time = current_real_time

        seconds_per_day = self.config.get("real_seconds_per_game_day", 600)
        if seconds_per_day <= 0: game_seconds_per_real_second = 0
        else: game_seconds_per_real_second = 86400 / seconds_per_day

        elapsed_game_time = elapsed_real_time * game_seconds_per_real_second

        old_game_time = self.game_time
        self.game_time += elapsed_game_time
        time_diff = abs(self.game_time - old_game_time)
        threshold = 0.001 # Use a small threshold

        # <<< DETAILED PRINTING >>>
        # print(f"[TimeTick] RealElapsed={elapsed_real_time:.4f}s GameElapsed={elapsed_game_time:.4f}s Diff={time_diff:.6f} MetThreshold={time_diff > threshold}")
        # <<< END PRINTING >>>

        if time_diff > TIME_PLUGIN_UPDATE_THRESHOLD:
            self.update_count += 1
            # print(f"          -> Update #{self.update_count}: Recalc & Publish...") # Indented print

            # Store old values *before* recalculating for event checks
            old_hour = self.hour
            old_day = self.day
            old_month = self.month
            old_year = self.year
            old_time_period = self.current_time_period

            # Recalculate everything from the new game_time
            self._recalculate_date_from_game_time()

            # Update the time period based on the new hour
            self._update_time_period() # Updates self.current_time_period

            # <<< CRITICAL: Update world data AND publish the time_data event >>>
            # This ensures the GameManager gets the latest hour/minute/etc.
            self._update_world_time_data()
            # <<< END CRITICAL CHANGE >>>

            # --- Now, check for specific changes to publish discrete events ---
            if self.event_system:
                if self.hour != old_hour:
                    self.event_system.publish("hour_changed", {"hour": self.hour, "old_hour": old_hour})
                if self.day != old_day:
                    self.event_system.publish("day_changed", {"day": self.day, "old_day": old_day})
                if self.month != old_month:
                    self.event_system.publish("month_changed", {"month": self.month, "old_month": old_month})
                if self.year != old_year:
                    self.event_system.publish("year_changed", {"year": self.year, "old_year": old_year})
                if self.current_time_period != old_time_period:
                    transition_message = self._get_time_period_transition_message(old_time_period, self.current_time_period)
                    self.event_system.publish("time_period_changed", {
                        "old_period": old_time_period,
                        "new_period": self.current_time_period,
                        "transition_message": transition_message
                    })
        # else: No significant game time passed, do nothing this tick.

    # --- NEW: Centralized calculation from game_time ---
    def _recalculate_date_from_game_time(self):
        """Calculates hour, minute, day, month, year from self.game_time."""
        days_per_month = self.config.get("days_per_month", 30)
        months_per_year = self.config.get("months_per_year", 12)

        # Ensure positive divisors
        days_per_month = max(1, days_per_month)
        months_per_year = max(1, months_per_year)

        total_seconds = self.game_time
        total_minutes = int(total_seconds / 60)
        total_hours = int(total_minutes / 60)
        total_days = int(total_hours / 24) # Total full days elapsed since start

        # Calculate current time within the day
        self.minute = total_minutes % 60
        self.hour = total_hours % 24

        # Calculate current date (Year 1, Month 1, Day 1 is the start)
        days_this_year = total_days % (days_per_month * months_per_year)
        self.year = (total_days // (days_per_month * months_per_year)) + 1
        self.month = (days_this_year // days_per_month) + 1
        self.day = (days_this_year % days_per_month) + 1
    # --- End new method ---

    def _update_time_period(self):
        """Update the current time period based on the hour."""
        dawn_hour = self.config.get("dawn_hour", 6)
        day_hour = self.config.get("day_hour", 8)
        dusk_hour = self.config.get("dusk_hour", 18)
        night_hour = self.config.get("night_hour", 20)

        # Check night first (wraps around midnight)
        if self.hour >= night_hour or self.hour < dawn_hour:
            self.current_time_period = "night"
        elif self.hour >= dawn_hour and self.hour < day_hour:
            self.current_time_period = "dawn"
        elif self.hour >= day_hour and self.hour < dusk_hour:
            self.current_time_period = "day"
        else:  # Between dusk and night
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
        """Store time data in the world and publish the 'time_data' event."""
        # Calculate display names/strings (same as before)
        days_per_week = self.config.get("days_per_week", 7)
        day_names = self.config.get("day_names", ["Day"] * days_per_week)
        month_names = self.config.get("month_names", ["Month"] * 12)
        day_name = day_names[(self.day - 1) % days_per_week]
        month_name = month_names[(self.month - 1) % len(month_names)]
        time_str = f"{self.hour:02d}:{self.minute:02d}"
        date_str = f"{day_name}, {self.day} {month_name}, Year {self.year}"
        seasons = ["winter", "spring", "summer", "fall"]
        season_idx = ((self.month - 1) * len(seasons) // len(month_names)) % len(seasons)
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
            self.world.set_plugin_data(self.plugin_id, "time_state", time_data)

        # <<< This publish MUST happen every time this function is called >>>
        if self.event_system:
            self.event_system.publish("time_data", time_data)
        else:
             # This suggests a deeper problem if event_system is missing here
             print(f"{FORMAT_ERROR}[TimePlugin] CRITICAL: Cannot publish time_data, EventSystem missing in _update_world_time_data!{FORMAT_RESET}")

    def cleanup(self):
        """Clean up plugin resources."""
        if self.event_system:
            self.event_system.unsubscribe("on_tick", self._on_tick)
        print("Time plugin cleaned up.")