# commands/information.py
from commands.command_system import command
from core.config import (
    FORMAT_TITLE, FORMAT_RESET, TIME_DAY_NAMES, TIME_MONTHS_PER_YEAR,
    TIME_DAYS_PER_WEEK, TIME_DAYS_PER_MONTH, TIME_MONTH_NAMES
)

@command("time", ["clock"], "information", "Display the current in-game time and date.")
def time_handler(args, context):
    """Time command handler."""
    game = context.get("game")
    if not game:
        return "Time is unavailable."

    time_data = game.time_manager.time_data
    response = f"{FORMAT_TITLE}Current Time:{FORMAT_RESET} {time_data.get('time_str', 'N/A')}\n"
    response += f"{FORMAT_TITLE}Current Date:{FORMAT_RESET} {time_data.get('date_str', 'N/A')}\n"
    response += f"{FORMAT_TITLE}Time Period:{FORMAT_RESET} {time_data.get('time_period', 'N/A').capitalize()}\n"
    
    return response

@command("calendar", ["cal", "date"], "information", "Display the in-game calendar details.")
def calendar_handler(args, context):
    """Calendar command handler."""
    game = context.get("game")
    if not game:
        return "The calendar is unavailable."
        
    time_data = game.time_manager.time_data
    
    response = f"{FORMAT_TITLE}Current Date:{FORMAT_RESET} {time_data.get('date_str', 'N/A')}\n\n"
    response += f"Days in a week: {TIME_DAYS_PER_WEEK}\n"
    response += f"Days in a month: {TIME_DAYS_PER_MONTH}\n"
    response += f"Months in a year: {TIME_MONTHS_PER_YEAR}\n\n"
    
    response += f"{FORMAT_TITLE}Day Names:{FORMAT_RESET}\n" + ", ".join(TIME_DAY_NAMES) + "\n\n"
    response += f"{FORMAT_TITLE}Month Names:{FORMAT_RESET}\n" + ", ".join(TIME_MONTH_NAMES) + "\n"
    
    return response

@command("weather", ["forecast"], "information", "Check the current weather conditions.")
def weather_handler(args, context):
    """Weather command handler."""
    game = context.get("game")
    world = context.get("world")
    if not game or not world:
        return "The weather is currently unknown."

    weather_manager = game.weather_manager
    current_room = world.get_current_room()
    is_outdoors = current_room.properties.get("outdoors", False) if current_room else False

    if not is_outdoors:
        return f"You can't see the weather from inside, but you can hear sounds indicating {weather_manager.current_weather} conditions outside."
    
    weather_desc_map = {
        "clear": "The sky is clear and blue.",
        "cloudy": "Clouds fill the sky.",
        "rain": "Rain falls steadily.",
        "storm": "Thunder rumbles as a storm rages.",
        "snow": "Snowflakes drift down from the sky."
    }
    description = weather_desc_map.get(weather_manager.current_weather, "The weather is unremarkable.")
    
    return f"Current Weather: {weather_manager.current_weather.capitalize()} ({weather_manager.current_intensity})\n\n{description}"