"""
core/game_manager.py
Updated Game Manager module for the MUD game with consolidated command system.
"""
import time
import pygame
import sys
import textwrap
import importlib
from typing import Any, List

import core.config as config
from world.world import World
from commands.command_system import registered_commands, CommandProcessor
from utils.colored_text import ColoredText
from plugins.plugin_system import PluginManager
import commands.core_commands  # Import command modules to register them
import commands.movement_commands
import commands.interaction_commands


class GameManager:
    """
    Manages the game's UI, input handling, and main loop.
    """
    def __init__(self, world_file: str = config.DEFAULT_WORLD_FILE):
        """
        Initialize the game manager.
        
        Args:
            world_file: Path to the JSON world file to load.
        """
        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont("monospace", config.FONT_SIZE)
        self.clock = pygame.time.Clock()
        
        # Calculate the textwrap width based on screen dimensions
        self._calculate_textwrap_width()
        
        # Initialize world
        self.world = World()
        self.world.start_time = time.time()  # Set the game world start time
        
        self.world.game = self

        if not self.world.load_from_json(world_file):
            print(f"Failed to load world from {world_file}. Creating test world.")
            self._create_test_world()

        # Time display data
        self.time_data = {
            "hour": 12,
            "minute": 0,
            "day": 1,
            "month": 1,
            "year": 1,
            "day_name": "Moonday",
            "month_name": "Deepwinter",
            "time_period": "day",
            "time_str": "12:00",
            "date_str": "Moonday, 1 Deepwinter, Year 1"
        }
        
        # Initialize command processor
        self.command_processor = CommandProcessor()
        
        # Initialize plugin manager
        self.plugin_manager = PluginManager(self.world, self.command_processor)

        # Subscribe to events
        self.plugin_manager.event_system.subscribe("display_message", self._on_display_message)
        self.plugin_manager.event_system.subscribe("time_data", self._on_time_data_event)
        self.plugin_manager.event_system.subscribe("time_period_changed", self._on_time_period_changed)
        
        # Load all plugins
        self.plugin_manager.load_all_plugins()

        # Message buffer for NPC updates
        self.npc_messages = []
        self.last_npc_message_time = time.time()  # Initialize this to avoid errors

        # Text buffers and input
        self.text_buffer: List[str] = []
        self.input_text = ""
        self.cursor_visible = True
        self.cursor_timer = 0
        
        # Command history
        self.command_history = []
        self.history_index = -1
        
        # Set up tab completion state
        self.tab_completion_buffer = ""
        self.tab_suggestions = []
        self.tab_index = -1
        
        # For scrolling
        self.scroll_offset = 0
        self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 20) // (config.FONT_SIZE + config.LINE_SPACING)
        
        # Initialize text rendering
        self.colored_text = ColoredText(self.font, config.FORMAT_COLORS)
        
        # Debug mode
        self.debug_mode = False
        
        # Welcome message
        welcome_message = f"{config.FORMAT_TITLE}Welcome to Pygame MUD!{config.FORMAT_RESET}\n\n"
        welcome_message += "Type 'help' to see available commands.\n\n"
        welcome_message += "=" * 40 + "\n\n"
        welcome_message += self.world.look()  # Start with room description
        
        self.text_buffer.append(self._sanitize_text(welcome_message))
    
    def _calculate_textwrap_width(self):
        """
        Calculate the appropriate textwrap width based on screen dimensions and font.
        For monospace fonts, we can calculate how many characters fit in the screen width.
        """
        # Get the width of a single character (for monospace fonts)
        test_text = "X"
        text_width = self.font.size(test_text)[0]
        
        # Calculate how many characters can fit in the display area (with some margin)
        usable_width = config.SCREEN_WIDTH - 20  # 10px margin on each side
        chars_per_line = usable_width // text_width
        
        # Create the textwrapper with the calculated width
        self.wrapper = textwrap.TextWrapper(width=chars_per_line)
        
        # Recalculate max_visible_lines to account for time bar
        self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 50) // (config.FONT_SIZE + config.LINE_SPACING)
    
    def handle_input(self, text: str) -> str:
        """
        Process user input and return the result.
        
        Args:
            text: The user's input text.
            
        Returns:
            A string response to display to the user.
        """
        # Add the input to the text buffer and command history
        self.text_buffer.append(text)
        
        if text.strip():  # Only add non-empty commands to history
            self.command_history.append(text)
            self.history_index = -1  # Reset history index
        
        # Extract command and args for plugin notification
        parts = text.strip().split()
        command = parts[0].lower() if parts else ""
        args = parts[1:] if len(parts) > 1 else []
        
        # Process the command using the command processor
        context = {
            "game": self,
            "world": self.world,
            "command_processor": self.command_processor
        }
        
        # Notify plugins about the command
        self.plugin_manager.on_command(command, args, context)
        
        # Process the command
        result = self.command_processor.process_input(text, context)
        
        # Sanitize the result before returning
        return self._sanitize_text(result)
    
    def _sanitize_text(self, text: str) -> str:
        """
        Sanitize text by normalizing newlines and removing problematic characters.
        
        Args:
            text: The text to sanitize.
            
        Returns:
            Sanitized text.
        """
        if not text:
            return ""
            
        # Normalize newlines to \n
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove any control characters except for newlines
        text = ''.join(ch if ch == '\n' or ord(ch) >= 32 else ' ' for ch in text)
        
        # Collapse multiple consecutive newlines into at most two
        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
            
        return text
    
    def update(self):
        """Update game state."""
        current_time = time.time() - self.world.start_time
        
        # Explicitly publish the on_tick event for plugins
        if hasattr(self, 'plugin_manager') and hasattr(self.plugin_manager, 'event_system'):
            self.plugin_manager.event_system.publish("on_tick", current_time)
        
        # Call the plugin manager's on_tick method
        if hasattr(self, 'plugin_manager'):
            self.plugin_manager.on_tick(current_time)
        
        # Update the game world
        npc_updates = self.world.update()
        
        # Process all NPC messages immediately
        if npc_updates:
            for message in npc_updates:
                if message:  # Only add non-empty messages
                    self.text_buffer.append(message)
                    
        # Update the cursor blink timer
        self.cursor_timer += self.clock.get_time()
        if self.cursor_timer >= 500:  # Toggle cursor every 500ms
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0


    def draw(self):
        """Render the game UI."""
        self.screen.fill(config.BG_COLOR)
        
        # Time bar at the top
        self._draw_time_bar()
        
        # Calculate total number of lines in the buffer
        total_lines = 0
        formatted_lines = []
        
        for text in self.text_buffer:
            # Process each line from the buffer
            lines = text.split('\n')
            for line in lines:
                formatted_lines.append(line)
                total_lines += 1
        
        # Calculate how many lines we can show
        visible_lines = min(total_lines, self.max_visible_lines)
        start_line = max(0, total_lines - visible_lines - self.scroll_offset)
        
        # Draw the visible lines
        y_offset = 40  # Increased to make room for time bar
        for i in range(start_line, min(total_lines, start_line + self.max_visible_lines)):
            if i < len(formatted_lines):
                line = formatted_lines[i]
                self.colored_text.render(self.screen, line, (10, y_offset))
                y_offset += config.FONT_SIZE + config.LINE_SPACING
        
        # Draw the input box
        pygame.draw.rect(self.screen, config.INPUT_BG_COLOR, 
                        (0, config.SCREEN_HEIGHT - config.INPUT_HEIGHT, 
                        config.SCREEN_WIDTH, config.INPUT_HEIGHT))
        
        # Draw input text
        input_display = "> " + self.input_text
        if self.cursor_visible:
            input_display += "|"
        
        input_surface = self.font.render(input_display, True, config.TEXT_COLOR)
        self.screen.blit(input_surface, (10, config.SCREEN_HEIGHT - config.INPUT_HEIGHT + 5))
        
        # Draw debug indicator if in debug mode
        if self.debug_mode:
            debug_text = "DEBUG MODE"
            debug_surface = self.font.render(debug_text, True, (255, 0, 0))
            self.screen.blit(debug_surface, 
                            (config.SCREEN_WIDTH - debug_surface.get_width() - 10, 40))
        
        pygame.display.flip()
    
    def _draw_time_bar(self):
        """Draw a time display bar at the top of the screen."""
        # Use cached time data
        time_str = self.time_data.get("time_str", "??:??")
        date_str = self.time_data.get("date_str", "Unknown Date")
        time_period = self.time_data.get("time_period", "unknown")
        
        # Draw time bar background
        pygame.draw.rect(self.screen, (40, 40, 60), 
                        (0, 0, config.SCREEN_WIDTH, 30))
        
        # Draw time on left
        time_color = self._get_time_period_color(time_period)
        time_surface = self.font.render(time_str, True, time_color)
        self.screen.blit(time_surface, (10, 5))
        
        # Draw date in center
        date_surface = self.font.render(date_str, True, config.TEXT_COLOR)
        date_x = (config.SCREEN_WIDTH - date_surface.get_width()) // 2
        self.screen.blit(date_surface, (date_x, 5))
        
        # Draw time period on right
        period_surface = self.font.render(time_period.capitalize(), True, time_color)
        period_x = config.SCREEN_WIDTH - period_surface.get_width() - 10
        self.screen.blit(period_surface, (period_x, 5))
        
        # Draw separator line
        pygame.draw.line(self.screen, (80, 80, 100), 
                        (0, 30), (config.SCREEN_WIDTH, 30), 1)

    def _get_time_period_color(self, time_period):
        """Return a color based on the time period."""
        period_colors = {
            "dawn": (255, 165, 0),    # Orange
            "day": (255, 255, 150),   # Bright yellow
            "dusk": (255, 100, 100),  # Reddish
            "night": (100, 100, 255)  # Blue
        }
        return period_colors.get(time_period, config.TEXT_COLOR)
    
    def navigate_history(self, direction: int):
        """
        Navigate through command history.
        
        Args:
            direction: 1 for older commands, -1 for newer commands
        """
        if not self.command_history:
            return
            
        if direction > 0:  # Up key - older commands
            self.history_index = min(self.history_index + 1, len(self.command_history) - 1)
        else:  # Down key - newer commands
            self.history_index = max(self.history_index - 1, -1)
            
        if self.history_index >= 0:
            self.input_text = self.command_history[-(self.history_index + 1)]
        else:
            self.input_text = ""
        
        # Reset tab completion when navigating history
        self.tab_completion_buffer = ""
        self.tab_suggestions = []
        self.tab_index = -1
        
    def handle_tab_completion(self):
        """Handle tab completion for commands and directions."""
        # Get the current text and cursor position
        current_text = self.input_text.strip()
        
        # If no text, do nothing
        if not current_text:
            return
            
        # If this is first tab press for current text, get suggestions
        if current_text != self.tab_completion_buffer or not self.tab_suggestions:
            self.tab_completion_buffer = current_text
            self.tab_suggestions = self.command_processor.get_command_suggestions(current_text)
            self.tab_index = -1
        
        # If there are suggestions, cycle through them
        if self.tab_suggestions:
            self.tab_index = (self.tab_index + 1) % len(self.tab_suggestions)
            self.input_text = self.tab_suggestions[self.tab_index]
    
    def quit_game(self):
        """Cleanly exit the game."""
        # Unload all plugins
        if hasattr(self, 'plugin_manager'):
            self.plugin_manager.unload_all_plugins()
        pygame.quit()
        sys.exit()
    
    def run(self):
        """Main game loop."""
        running = True
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        result = self.handle_input(self.input_text)
                        if result:
                            self.text_buffer.append(result)
                        self.input_text = ""
                    
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                    
                    # Command history navigation
                    elif event.key == pygame.K_UP:
                        self.navigate_history(1)
                    
                    elif event.key == pygame.K_DOWN:
                        self.navigate_history(-1)
                        
                    # Handle tab completion
                    elif event.key == pygame.K_TAB:
                        self.handle_tab_completion()
                    
                    # Handle scrolling with page up/down keys
                    elif event.key == pygame.K_PAGEUP:
                        self.scroll_offset = min(len(self.text_buffer) * 10, 
                                                 self.scroll_offset + self.max_visible_lines // 2)
                    
                    elif event.key == pygame.K_PAGEDOWN:
                        self.scroll_offset = max(0, self.scroll_offset - self.max_visible_lines // 2)
                        
                    # Toggle debug mode
                    elif event.key == pygame.K_F1:
                        self.debug_mode = not self.debug_mode
                        if self.debug_mode:
                            self.text_buffer.append(f"{config.FORMAT_HIGHLIGHT}Debug mode enabled. Press F1 to disable.{config.FORMAT_RESET}")
                        else:
                            self.text_buffer.append(f"{config.FORMAT_HIGHLIGHT}Debug mode disabled.{config.FORMAT_RESET}")
                    
                    else:
                        # Only add printable characters
                        if event.unicode.isprintable():
                            self.input_text += event.unicode
                
                # Handle mouse wheel for scrolling
                elif event.type == pygame.MOUSEWHEEL:
                    if event.y > 0:  # Scroll up
                        self.scroll_offset = min(len(self.text_buffer) * 10, 
                                                 self.scroll_offset + config.SCROLL_SPEED)
                    elif event.y < 0:  # Scroll down
                        self.scroll_offset = max(0, self.scroll_offset - config.SCROLL_SPEED)
                        
                # Handle window resize events
                elif event.type == pygame.VIDEORESIZE:
                    # Update screen size
                    config.SCREEN_WIDTH = event.w
                    config.SCREEN_HEIGHT = event.h
                    self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), 
                                                         pygame.RESIZABLE)
                    # Recalculate text wrapping
                    self._calculate_textwrap_width()
                    # Update max visible lines
                    self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 20) // (config.FONT_SIZE + config.LINE_SPACING)
            
            self.update()
            self.draw()
            self.clock.tick(30)
        
        pygame.quit()

    def _create_test_world(self):
        """Create a test world with a few rooms, items, and NPCs."""
        # Create a basic region
        from world.region import Region
        from world.room import Room
        
        test_region = Region("Test Region", "A small test area.")
        
        # Create a few rooms
        entrance = Room("Entrance", "The entrance to the test region.")
        hall = Room("Main Hall", "A large hall with high ceilings.")
        garden = Room("Garden", "A beautiful garden with many plants.")
        
        # Connect the rooms
        entrance.exits = {"north": "hall"}
        hall.exits = {"south": "entrance", "east": "garden"}
        garden.exits = {"west": "hall"}
        
        # Add rooms to the region
        test_region.add_room("entrance", entrance)
        test_region.add_room("hall", hall)
        test_region.add_room("garden", garden)
        
        # Add region to the world
        self.world.add_region("test", test_region)
        
        # Set starting location
        self.world.current_region_id = "test"
        self.world.current_room_id = "entrance"
        
        # Create some test items
        from items.item import ItemFactory
        
        sword = ItemFactory.create_item("Weapon", name="Steel Sword", 
                                      description="A sharp steel sword.", damage=10)
        
        potion = ItemFactory.create_item("Consumable", name="Healing Potion",
                                       description="A potion that restores health.",
                                       effect_value=20, effect_type="heal")
        
        key = ItemFactory.create_item("Key", name="Brass Key",
                                    description="A small brass key.")
        
        # Add items to rooms
        self.world.add_item_to_room("test", "hall", sword)
        self.world.add_item_to_room("test", "garden", potion)
        
        # Add key to player inventory
        self.world.player.inventory.add_item(key)
        
        # Create some test NPCs
        from npcs.npc_factory import NPCFactory
        
        guard = NPCFactory.create_npc("guard", name="Guard Bob")
        guard.current_region_id = "test"
        guard.current_room_id = "entrance"
        guard.patrol_points = ["entrance", "hall"]  # Set up a patrol route
        
        merchant = NPCFactory.create_npc("shopkeeper", name="Merchant Alice")
        merchant.current_region_id = "test"
        merchant.current_room_id = "hall"
        
        villager = NPCFactory.create_npc("villager", name="Villager Charlie")
        villager.current_region_id = "test"
        villager.current_room_id = "garden"
        
        # Add NPCs to the world
        self.world.add_npc(guard)
        self.world.add_npc(merchant)
        self.world.add_npc(villager)

    def _on_time_data_event(self, event_type: str, data: dict) -> None:
        """
        Handle time data events.
        
        Args:
            event_type: The event type.
            data: The event data.
        """
        self.time_data = data

    def _on_time_period_changed(self, event_type: str, data: dict) -> None:
        """
        Handle time period change events.
        
        Args:
            event_type: The event type.
            data: The event data.
        """
        # Update time period
        if "new_period" in data:
            self.time_data["time_period"] = data["new_period"]
        
        # Add message to text buffer if there's a transition message
        if "transition_message" in data and data["transition_message"]:
            self.text_buffer.append(data['transition_message'])

    def _on_display_message(self, event_type: str, data: Any) -> None:
        """
        Handle display message events.
        
        Args:
            event_type: The event type.
            data: The message to display or message data.
        """
        # Handle different message formats
        if isinstance(data, str):
            message = data
        elif isinstance(data, dict) and "message" in data:
            message = data["message"]
        else:
            # Try to convert to string
            try:
                message = str(data)
            except:
                message = "Unprintable message"
        
        # Add the message to the text buffer
        self.text_buffer.append(message)