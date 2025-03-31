"""
core/game_manager.py
Fixed Game Manager module with working commands and scrolling.
"""
import time
import pygame
import sys
from typing import Any, List, Optional

import core.config as config
from world.world import World
from commands.command_system import CommandProcessor
from utils.text_formatter import TextFormatter
from plugins.plugin_system import PluginManager
from commands.commands import register_movement_commands

class GameManager:
    def __init__(self, world_file: str = config.DEFAULT_WORLD_FILE):
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont("monospace", config.FONT_SIZE)
        self.clock = pygame.time.Clock()
        
        # Initialize the enhanced text system
        self.text_formatter = TextFormatter(
            font=self.font,
            screen_width=config.SCREEN_WIDTH,
            colors=config.FORMAT_COLORS,
            margin=10,
            line_spacing=config.LINE_SPACING
        )
        
        # Initialize the world
        self.world = World()
        self.world.start_time = time.time()
        self.world.game = self
        
        if not self.world.load_from_json(world_file):
            print(f"Failed to load world from {world_file}. Creating test world.")
            self._create_test_world()
            
        # Time data for display
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
        
        # Command system
        self.command_processor = CommandProcessor()
        
        # Register movement commands - important!
        register_movement_commands()
        
        # Plugin system
        self.plugin_manager = PluginManager(self.world, self.command_processor)
        self.plugin_manager.event_system.subscribe("display_message", self._on_display_message)
        self.plugin_manager.event_system.subscribe("time_data", self._on_time_data_event)
        self.plugin_manager.event_system.subscribe("time_period_changed", self._on_time_period_changed)
        self.plugin_manager.load_all_plugins()
        
        # Text and input handling
        self.text_buffer: List[str] = []
        self.input_text = ""
        self.cursor_visible = True
        self.cursor_timer = 0
        self.command_history = []
        self.history_index = -1
        self.tab_completion_buffer = ""
        self.tab_suggestions = []
        self.tab_index = -1
        self.scroll_offset = 0
        
        # Calculate visible lines
        self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 40) // (config.FONT_SIZE + config.LINE_SPACING)
        
        # Debug mode
        self.debug_mode = False
        
        # Welcome message
        welcome_message = f"{TextFormatter.FORMAT_TITLE}Welcome to Pygame MUD!{TextFormatter.FORMAT_RESET}\n\n"
        welcome_message += "Type 'help' to see available commands.\n\n"
        welcome_message += "=" * 40 + "\n\n"
        welcome_message += self.world.look()
        self.text_buffer.append(self._sanitize_text(welcome_message))
    
    def handle_input(self, text: str) -> str:
        """Process user input and get the result."""
        input_text = "> " + text  # Show what the user typed
        self.text_buffer.append(input_text)
        
        if text.strip():  # Only add non-empty commands to history
            self.command_history.append(text)
            self.history_index = -1  # Reset history index
            
        context = {
            "game": self,
            "world": self.world,
            "command_processor": self.command_processor
        }
        
        # Process the command
        result = self.command_processor.process_input(text, context)
        if result:
            return self._sanitize_text(result)
        return ""
    
    def _sanitize_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
            
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Replace control characters with spaces
        text = ''.join(ch if ch == '\n' or ord(ch) >= 32 else ' ' for ch in text)
        
        # Normalize paragraph spacing
        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
            
        return text
    
    def update(self):
        """Update game state."""
        current_time = time.time() - self.world.start_time
        
        # Update plugins
        if hasattr(self, 'plugin_manager'):
            if hasattr(self.plugin_manager, 'event_system'):
                self.plugin_manager.event_system.publish("on_tick", current_time)
            self.plugin_manager.on_tick(current_time)
        
        # Update NPCs
        npc_updates = self.world.update()
        if npc_updates:
            for message in npc_updates:
                if message:  # Only add non-empty messages
                    self.text_buffer.append(message)
        
        # Update cursor blink
        self.cursor_timer += self.clock.get_time()
        if self.cursor_timer >= 500:  # Toggle cursor every 500ms
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

    def draw(self):
        """Render the game to the screen with proper layout."""
        # Recalculate layout for current screen size
        self._calculate_layout()
        
        # Clear screen
        self.screen.fill(config.BG_COLOR)
        
        # Draw time bar at the top
        self._draw_time_bar()
        
        # Calculate total text content
        total_text = ""
        for text in self.text_buffer:
            if total_text:
                total_text += "\n\n"
            total_text += text
        
        # Calculate total lines
        formatted_lines = self.text_formatter.format_text(total_text)
        total_lines = len(formatted_lines)
        
        # Adjust scroll offset if needed
        if self.scroll_offset > total_lines - self.max_visible_lines:
            self.scroll_offset = max(0, total_lines - self.max_visible_lines)
        
        # Calculate visible range
        start_line = max(0, total_lines - self.max_visible_lines - self.scroll_offset)
        visible_lines = min(self.max_visible_lines, total_lines - start_line)
        
        # Extract the visible lines
        visible_text = "\n".join(formatted_lines[start_line:start_line + visible_lines])
        
        # Render the text with height limit
        self.text_formatter.render(
            surface=self.screen,
            text=visible_text,
            position=(10, self.layout["text_area"]["y"]),
            max_height=self.layout["text_area"]["y"] + self.layout["text_area"]["height"]
        )
        
        # Draw scroll indicators if needed
        self._draw_scroll_indicator()
        
        # Draw input area above status bar
        pygame.draw.rect(
            self.screen, 
            config.INPUT_BG_COLOR, 
            (0, self.layout["input_area"]["y"], 
            self.layout["screen_width"], self.layout["input_area"]["height"])
        )
        
        # Draw input text with cursor
        input_display = "> " + self.input_text
        if self.cursor_visible:
            input_display += "|"
            
        input_surface = self.font.render(input_display, True, config.TEXT_COLOR)
        self.screen.blit(input_surface, (10, self.layout["input_area"]["y"] + 5))
        
        # Draw status area at the bottom
        self._draw_status_indicators()
        
        # Draw debug indicator if in debug mode
        if self.debug_mode:
            debug_text = "DEBUG MODE"
            debug_surface = self.font.render(debug_text, True, (255, 0, 0))
            self.screen.blit(
                debug_surface, 
                (self.layout["screen_width"] - debug_surface.get_width() - 10, 40)
            )
        
        pygame.display.flip()

    def _draw_time_bar(self):
        """Draw the time and date bar at the top of the screen."""
        time_str = self.time_data.get("time_str", "??:??")
        date_str = self.time_data.get("date_str", "Unknown Date")
        time_period = self.time_data.get("time_period", "unknown")
        
        # Draw time bar background
        pygame.draw.rect(
            self.screen, 
            (40, 40, 60), 
            (0, 0, self.layout["screen_width"], self.layout["time_bar"]["height"])
        )
        
        # Get appropriate color for time period
        time_color = self._get_time_period_color(time_period)
        
        # Draw time
        time_surface = self.font.render(time_str, True, time_color)
        self.screen.blit(time_surface, (10, 5))
        
        # Draw date (centered)
        date_surface = self.font.render(date_str, True, config.TEXT_COLOR)
        date_x = (self.layout["screen_width"] - date_surface.get_width()) // 2
        self.screen.blit(date_surface, (date_x, 5))
        
        # Draw time period (right-aligned)
        period_surface = self.font.render(time_period.capitalize(), True, time_color)
        period_x = self.layout["screen_width"] - period_surface.get_width() - 10
        self.screen.blit(period_surface, (period_x, 5))
        
        # Draw separator line
        pygame.draw.line(
            self.screen, 
            (80, 80, 100), 
            (0, self.layout["time_bar"]["height"]), 
            (self.layout["screen_width"], self.layout["time_bar"]["height"]), 
            1
        )   

    def _get_time_period_color(self, time_period):
        """Get the color for a time period."""
        period_colors = {
            "dawn": (255, 165, 0),    # Orange
            "day": (255, 255, 150),   # Bright yellow
            "dusk": (255, 100, 100),  # Reddish
            "night": (100, 100, 255)  # Blue
        }
        return period_colors.get(time_period, config.TEXT_COLOR)
    
    def navigate_history(self, direction: int):
        """Navigate through command history."""
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
            
        # Reset tab completion
        self.tab_completion_buffer = ""
        self.tab_suggestions = []
        self.tab_index = -1
        
    def handle_tab_completion(self):
        """Handle tab completion for commands and arguments."""
        current_text = self.input_text.strip()
        if not current_text:
            return
            
        # If the text has changed or we have no suggestions yet, get new ones
        if current_text != self.tab_completion_buffer or not self.tab_suggestions:
            self.tab_completion_buffer = current_text
            self.tab_suggestions = self.command_processor.get_command_suggestions(current_text)
            self.tab_index = -1
            
        # If we have suggestions, cycle through them
        if self.tab_suggestions:
            self.tab_index = (self.tab_index + 1) % len(self.tab_suggestions)
            self.input_text = self.tab_suggestions[self.tab_index]
    
    def resize_screen(self, new_width, new_height):
        """Handle screen resize events."""
        config.SCREEN_WIDTH = new_width
        config.SCREEN_HEIGHT = new_height
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        
        # Update text formatter
        self.text_formatter.update_screen_width(new_width)
    
    def quit_game(self):
        """Clean up and exit the game."""
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
                        self.scroll_offset = 0  # Reset scroll when command is entered
                        
                    elif event.key == pygame.K_BACKSPACE:
                        self.input_text = self.input_text[:-1]
                        
                    elif event.key == pygame.K_UP:
                        self.navigate_history(1)
                        
                    elif event.key == pygame.K_DOWN:
                        self.navigate_history(-1)
                        
                    elif event.key == pygame.K_TAB:
                        self.handle_tab_completion()
                        
                    elif event.key == pygame.K_PAGEUP:
                        self.scroll_offset = min(
                            len(self.text_buffer) * 20,  # Arbitrary large number
                            self.scroll_offset + self.max_visible_lines // 2
                        )
                        
                    elif event.key == pygame.K_PAGEDOWN:
                        self.scroll_offset = max(0, self.scroll_offset - self.max_visible_lines // 2)
                        
                    elif event.key == pygame.K_HOME:
                        # Scroll to the beginning
                        self.scroll_offset = len(self.text_buffer) * 20
                        
                    elif event.key == pygame.K_END:
                        # Scroll to the end
                        self.scroll_offset = 0
                        
                    elif event.key == pygame.K_F1:
                        self.debug_mode = not self.debug_mode
                        if self.debug_mode:
                            self.text_buffer.append(f"{TextFormatter.FORMAT_HIGHLIGHT}Debug mode enabled. Press F1 to disable.{TextFormatter.FORMAT_RESET}")
                        else:
                            self.text_buffer.append(f"{TextFormatter.FORMAT_HIGHLIGHT}Debug mode disabled.{TextFormatter.FORMAT_RESET}")
                            
                    else:
                        if event.unicode.isprintable():
                            self.input_text += event.unicode
                            
                elif event.type == pygame.MOUSEWHEEL:
                    if event.y > 0:  # Scroll up
                        self.scroll_offset = min(
                            len(self.text_buffer) * 20,
                            self.scroll_offset + config.SCROLL_SPEED
                        )
                    elif event.y < 0:  # Scroll down
                        self.scroll_offset = max(0, self.scroll_offset - config.SCROLL_SPEED)
                        
                elif event.type == pygame.VIDEORESIZE:
                    self.resize_screen(event.w, event.h)
            
            # Update game state
            self.update()
            
            # Draw everything
            self.draw()
            
            # Cap the frame rate
            self.clock.tick(30)
        
        # Clean up and exit
        self.quit_game()
    
    def _on_display_message(self, event_type: str, data: Any) -> None:
        """Handle display message events."""
        if isinstance(data, str):
            message = data
        elif isinstance(data, dict) and "message" in data:
            message = data["message"]
        else:
            try:
                message = str(data)
            except:
                message = "Unprintable message"
                
        self.text_buffer.append(message)
    
    def _on_time_data_event(self, event_type: str, data: dict) -> None:
        """Handle time data events."""
        self.time_data = data
    
    def _on_time_period_changed(self, event_type: str, data: dict) -> None:
        """Handle time period change events."""
        if "new_period" in data:
            self.time_data["time_period"] = data["new_period"]
            
        if "transition_message" in data and data["transition_message"]:
            self.text_buffer.append(data['transition_message'])
    
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
        
        # Set environment properties
        garden.env_properties["outdoors"] = True
        hall.env_properties["has_windows"] = True
        
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
        from items.item_factory import ItemFactory
        
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

    def _trim_text_buffer(self):
        """Trim the text buffer to prevent memory issues with very long sessions."""
        max_buffer_size = config.MAX_BUFFER_SIZE if hasattr(config, 'MAX_BUFFER_SIZE') else 1000
        
        if len(self.text_buffer) > max_buffer_size:
            # Keep the most recent messages
            excess = len(self.text_buffer) - max_buffer_size
            self.text_buffer = self.text_buffer[excess:]
            
            # Add a message indicating older text was removed
            self.text_buffer.insert(0, f"{TextFormatter.FORMAT_HIGHLIGHT}(Older messages have been removed to save memory){TextFormatter.FORMAT_RESET}")

    def _draw_status_indicators(self):
        """Draw status indicators for health, etc. (now at the bottom)"""
        # Only draw if we have a player
        if not hasattr(self.world, 'player'):
            return
            
        player = self.world.player
        
        # Draw a small health bar
        health_width = 100
        health_height = 5
        health_x = 10
        health_y = self.layout["status_area"]["y"] + 8  # Centered in status area
        
        # Draw background
        pygame.draw.rect(self.screen, (80, 0, 0), 
                        (health_x, health_y, health_width, health_height))
        
        # Draw filled portion
        health_percent = player.health / player.max_health
        filled_width = int(health_width * health_percent)
        
        # Choose color based on health percentage
        if health_percent < 0.3:
            health_color = (200, 0, 0)  # Red for low health
        elif health_percent < 0.7:
            health_color = (200, 200, 0)  # Yellow for medium health
        else:
            health_color = (0, 200, 0)  # Green for good health
        
        pygame.draw.rect(self.screen, health_color, 
                        (health_x, health_y, filled_width, health_height))
        
        # Draw health text
        health_text = f"HP: {player.health}/{player.max_health}"
        health_surface = self.font.render(health_text, True, (255, 255, 255))
        self.screen.blit(health_surface, 
                        (health_x + health_width + 10, health_y - 5))
        
        # Draw XP if available
        if hasattr(player, 'experience') and hasattr(player, 'experience_to_level'):
            # XP text on right side
            xp_text = f"XP: {player.experience}/{player.experience_to_level} (Lvl {player.level})"
            xp_surface = self.font.render(xp_text, True, (255, 255, 255))
            self.screen.blit(xp_surface, 
                            (self.layout["screen_width"] - xp_surface.get_width() - 10, 
                            health_y - 5))
        
        # Draw status area separator line
        pygame.draw.line(
            self.screen,
            (80, 80, 100),
            (0, self.layout["status_area"]["y"] - 1),  # Line above status area
            (self.layout["screen_width"], self.layout["status_area"]["y"] - 1),
            1
        )

    def _draw_scroll_indicator(self):
        """Draw scroll indicators to show if there's more text above or below."""
        # Get formatted lines count
        total_text = ""
        for text in self.text_buffer:
            if total_text:
                total_text += "\n\n"
            total_text += text
            
        formatted_lines = self.text_formatter.format_text(total_text)
        total_lines = len(formatted_lines)
        start_line = max(0, total_lines - self.max_visible_lines - self.scroll_offset)
        
        # Draw "more above" indicator if needed
        if self.scroll_offset > 0:
            arrow_points = [
                (self.layout["screen_width"] - 30, self.layout["text_area"]["y"] + 10),
                (self.layout["screen_width"] - 20, self.layout["text_area"]["y"]),
                (self.layout["screen_width"] - 10, self.layout["text_area"]["y"] + 10)
            ]
            pygame.draw.polygon(self.screen, (200, 200, 200), arrow_points)
        
        # Draw "more below" indicator if needed
        if start_line + self.max_visible_lines < total_lines:
            bottom_y = self.layout["input_area"]["y"] - 10
            arrow_points = [
                (self.layout["screen_width"] - 30, bottom_y - 10),
                (self.layout["screen_width"] - 20, bottom_y),
                (self.layout["screen_width"] - 10, bottom_y - 10)
            ]
            pygame.draw.polygon(self.screen, (200, 200, 200), arrow_points)

    def _calculate_layout(self):
        """
        Calculate layout positions and sizes for all UI elements.
        This centralizes all positioning logic in one place.
        Status bar is now at the bottom, below the input area.
        """
        # Basic dimensions
        self.layout = {
            # Screen dimensions
            "screen_width": config.SCREEN_WIDTH,
            "screen_height": config.SCREEN_HEIGHT,
            
            # Time bar at the top
            "time_bar": {
                "height": 30,
                "y": 0
            },
            
            # Status area (health bar, etc.) now at the very bottom
            "status_area": {
                "height": 20,
                "y": config.SCREEN_HEIGHT - 20  # Takes the bottom 20px of screen
            },
            
            # Input area now above the status bar
            "input_area": {
                "height": config.INPUT_HEIGHT,
                "y": config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 20  # Above status area
            }
        }
        
        # Calculate text area dimensions
        self.layout["text_area"] = {
            "y": self.layout["time_bar"]["height"] + 10,  # 10px padding below time bar
            "height": (self.layout["input_area"]["y"] - 
                    (self.layout["time_bar"]["height"] + 20))  # 10px padding above & below
        }
        
        # Recalculate visible lines based on text area height
        line_height = self.font.get_linesize() + config.LINE_SPACING
        self.max_visible_lines = self.layout["text_area"]["height"] // line_height
