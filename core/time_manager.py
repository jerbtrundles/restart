# core/time_manager.py
"""
Core system for managing in-game time, date, and seasons.
"""
import time
from typing import Dict, Any, Optional, Tuple

from config import (TIME_DAWN_HOUR, TIME_DAY_HOUR, TIME_DAY_NAMES,
                         TIME_DAYS_PER_MONTH, TIME_DUSK_HOUR,
                         TIME_MAX_CATCHUP_SECONDS, TIME_MONTH_NAMES,
                         TIME_MONTHS_PER_YEAR, TIME_NIGHT_HOUR,
                         TIME_REAL_SECONDS_PER_GAME_DAY, TIME_UPDATE_THRESHOLD)


class TimeManager:
    def __init__(self):
        self.game_time: float = 0.0
        self.last_real_time_update: float = 0.0
        self.hour: int = 12
        self.minute: int = 0
        self.day: int = 1
        self.month: int = 1
        self.year: int = 1
        self.current_time_period: str = "day"
        self.time_data: Dict[str, Any] = {}
        self.initialize_time()

    def initialize_time(self, game_time: float = 0.0):
        """Resets or initializes the time state."""
        self.game_time = game_time
        self._recalculate_date_from_game_time()
        self._update_time_period()
        self._update_time_data_for_ui()
        self.last_real_time_update = time.time()

    def update(self, current_real_time: float) -> Optional[Tuple[str, str]]:
        """
        Updates the game time based on real-world elapsed time.
        Returns old and new time periods if a change occurred.
        """
        elapsed_real_time = current_real_time - self.last_real_time_update
        elapsed_real_time = min(elapsed_real_time, TIME_MAX_CATCHUP_SECONDS)
        self.last_real_time_update = current_real_time

        seconds_per_day = TIME_REAL_SECONDS_PER_GAME_DAY
        game_seconds_per_real_second = 86400 / seconds_per_day if seconds_per_day > 0 else 0

        elapsed_game_time = elapsed_real_time * game_seconds_per_real_second
        old_game_time = self.game_time
        self.game_time += elapsed_game_time
        
        if abs(self.game_time - old_game_time) > TIME_UPDATE_THRESHOLD:
            old_period = self.current_time_period
            self._recalculate_date_from_game_time()
            self._update_time_period()
            self._update_time_data_for_ui()

            if self.current_time_period != old_period:
                return (old_period, self.current_time_period)
        return None

    def _recalculate_date_from_game_time(self):
        total_seconds = int(self.game_time)
        self.minute = (total_seconds // 60) % 60
        self.hour = (total_seconds // 3600) % 24
        total_days = total_seconds // 86400
        self.year = 1 + (total_days // (TIME_DAYS_PER_MONTH * TIME_MONTHS_PER_YEAR))
        days_this_year = total_days % (TIME_DAYS_PER_MONTH * TIME_MONTHS_PER_YEAR)
        self.month = 1 + (days_this_year // TIME_DAYS_PER_MONTH)
        self.day = 1 + (days_this_year % TIME_DAYS_PER_MONTH)

    def _update_time_period(self):
        if self.hour >= TIME_NIGHT_HOUR or self.hour < TIME_DAWN_HOUR: self.current_time_period = "night"
        elif TIME_DAWN_HOUR <= self.hour < TIME_DAY_HOUR: self.current_time_period = "dawn"
        elif TIME_DAY_HOUR <= self.hour < TIME_DUSK_HOUR: self.current_time_period = "day"
        else: self.current_time_period = "dusk"

    def _update_time_data_for_ui(self):
        day_name = TIME_DAY_NAMES[(self.day - 1) % len(TIME_DAY_NAMES)]
        month_name = TIME_MONTH_NAMES[(self.month - 1) % len(TIME_MONTH_NAMES)]
        seasons = ["winter", "spring", "summer", "fall"]
        season_idx = (self.month - 1) * len(seasons) // TIME_MONTHS_PER_YEAR
        self.time_data = {
            "hour": self.hour, "minute": self.minute, "day": self.day, "month": self.month, "year": self.year,
            "day_name": day_name, "month_name": month_name, "season": seasons[season_idx],
            "time_period": self.current_time_period, "time_str": f"{self.hour:02d}:{self.minute:02d}",
            "date_str": f"{day_name}, {self.day} {month_name}, Year {self.year}"
        }

    def get_time_transition_message(self, old_period: str, new_period: str) -> str:
        transitions = {
            "night-dawn": "Dawn breaks.",
            "dawn-day": "The sun rises.",
            "day-dusk": "Dusk falls.",
            "dusk-night": "Night descends."
        }
        return transitions.get(f"{old_period}-{new_period}", "")

    def get_time_state_for_save(self) -> Dict[str, Any]:
         return {"game_time": self.game_time}

    def apply_loaded_time_state(self, time_state: Optional[Dict[str, Any]]):
        if time_state and isinstance(time_state, dict):
             self.initialize_time(time_state.get("game_time", 0.0))
        else:
             self.initialize_time()