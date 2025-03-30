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
from commands.commands import register_movement_commands

class GameManager:
    def __init__(self, world_file: str = config.DEFAULT_WORLD_FILE):
        pygame.init()
        self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT))
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont("monospace", config.FONT_SIZE)
        self.clock = pygame.time.Clock()
        self._calculate_textwrap_width()
        self.world = World()
        self.world.start_time = time.time()  # Set the game world start time       
        self.world.game = self
        if not self.world.load_from_json(world_file):
            print(f"Failed to load world from {world_file}. Creating test world.")
            self._create_test_world()
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
        self.command_processor = CommandProcessor()
        self.plugin_manager = PluginManager(self.world, self.command_processor)
        self.plugin_manager.event_system.subscribe("display_message", self._on_display_message)
        self.plugin_manager.event_system.subscribe("time_data", self._on_time_data_event)
        self.plugin_manager.event_system.subscribe("time_period_changed", self._on_time_period_changed)
        self.plugin_manager.load_all_plugins()
        self.npc_messages = []
        self.last_npc_message_time = time.time()  # Initialize this to avoid errors
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
        self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 20) // (config.FONT_SIZE + config.LINE_SPACING)
        self.colored_text = ColoredText(self.font, config.FORMAT_COLORS)
        self.debug_mode = False
        welcome_message = f"{config.FORMAT_TITLE}Welcome to Pygame MUD!{config.FORMAT_RESET}\n\n"
        welcome_message += "Type 'help' to see available commands.\n\n"
        welcome_message += "=" * 40 + "\n\n"
        welcome_message += self.world.look()  # Start with room description        
        self.text_buffer.append(self._sanitize_text(welcome_message))
    
    def _calculate_textwrap_width(self):
        test_text = "X"
        text_width = self.font.size(test_text)[0]
        usable_width = config.SCREEN_WIDTH - 20  # 10px margin on each side
        chars_per_line = usable_width // text_width
        self.wrapper = textwrap.TextWrapper(width=chars_per_line)
        self.max_visible_lines = (config.SCREEN_HEIGHT - config.INPUT_HEIGHT - 50) // (config.FONT_SIZE + config.LINE_SPACING)
    
    def handle_input(self, text: str) -> str:
        self.text_buffer.append(text)
        if text.strip():  # Only add non-empty commands to history
            self.command_history.append(text)
            self.history_index = -1  # Reset history index
        context = {
            "game": self,
            "world": self.world,
            "command_processor": self.command_processor
        }
        result = self.command_processor.process_input(text, context)
        return self._sanitize_text(result)
    
    def _sanitize_text(self, text: str) -> str:
        if not text:
            return ""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = ''.join(ch if ch == '\n' or ord(ch) >= 32 else ' ' for ch in text)
        while '\n\n\n' in text:
            text = text.replace('\n\n\n', '\n\n')
        return text
    
    def update(self):
        current_time = time.time() - self.world.start_time
        if hasattr(self, 'plugin_manager') and hasattr(self.plugin_manager, 'event_system'):
            self.plugin_manager.event_system.publish("on_tick", current_time)
        if hasattr(self, 'plugin_manager'):
            self.plugin_manager.on_tick(current_time)
        npc_updates = self.world.update()
        if npc_updates:
            for message in npc_updates:
                if message:  # Only add non-empty messages
                    self.text_buffer.append(message)
        self.cursor_timer += self.clock.get_time()
        if self.cursor_timer >= 500:  # Toggle cursor every 500ms
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

    def draw(self):
        self.screen.fill(config.BG_COLOR)
        self._draw_time_bar()
        total_lines = 0
        formatted_lines = []
        for text in self.text_buffer:
            lines = text.split('\n')
            for line in lines:
                formatted_lines.append(line)
                total_lines += 1
        visible_lines = min(total_lines, self.max_visible_lines)
        start_line = max(0, total_lines - visible_lines - self.scroll_offset)
        y_offset = 40  # Increased to make room for time bar
        for i in range(start_line, min(total_lines, start_line + self.max_visible_lines)):
            if i < len(formatted_lines):
                line = formatted_lines[i]
                self.colored_text.render(self.screen, line, (10, y_offset))
                y_offset += config.FONT_SIZE + config.LINE_SPACING
        pygame.draw.rect(self.screen, config.INPUT_BG_COLOR, 
                        (0, config.SCREEN_HEIGHT - config.INPUT_HEIGHT, 
                        config.SCREEN_WIDTH, config.INPUT_HEIGHT))
        input_display = "> " + self.input_text
        if self.cursor_visible:
            input_display += "|"
        input_surface = self.font.render(input_display, True, config.TEXT_COLOR)
        self.screen.blit(input_surface, (10, config.SCREEN_HEIGHT - config.INPUT_HEIGHT + 5))
        if self.debug_mode:
            debug_text = "DEBUG MODE"
            debug_surface = self.font.render(debug_text, True, (255, 0, 0))
            self.screen.blit(debug_surface, 
                            (config.SCREEN_WIDTH - debug_surface.get_width() - 10, 40))
        pygame.display.flip()
    
    def _draw_time_bar(self):
        time_str = self.time_data.get("time_str", "??:??")
        date_str = self.time_data.get("date_str", "Unknown Date")
        time_period = self.time_data.get("time_period", "unknown")
        pygame.draw.rect(self.screen, (40, 40, 60), 
                        (0, 0, config.SCREEN_WIDTH, 30))
        time_color = self._get_time_period_color(time_period)
        time_surface = self.font.render(time_str, True, time_color)
        self.screen.blit(time_surface, (10, 5))
        date_surface = self.font.render(date_str, True, config.TEXT_COLOR)
        date_x = (config.SCREEN_WIDTH - date_surface.get_width()) // 2
        self.screen.blit(date_surface, (date_x, 5))
        period_surface = self.font.render(time_period.capitalize(), True, time_color)
        period_x = config.SCREEN_WIDTH - period_surface.get_width() - 10
        self.screen.blit(period_surface, (period_x, 5))
        pygame.draw.line(self.screen, (80, 80, 100), 
                        (0, 30), (config.SCREEN_WIDTH, 30), 1)

    def _get_time_period_color(self, time_period):
        period_colors = {
            "dawn": (255, 165, 0),    # Orange
            "day": (255, 255, 150),   # Bright yellow
            "dusk": (255, 100, 100),  # Reddish
            "night": (100, 100, 255)  # Blue
        }
        return period_colors.get(time_period, config.TEXT_COLOR)
    
    def navigate_history(self, direction: int):
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
        self.tab_completion_buffer = ""
        self.tab_suggestions = []
        self.tab_index = -1
        
    def handle_tab_completion(self):
        current_text = self.input_text.strip()
        if not current_text:
            return
        if current_text != self.tab_completion_buffer or not self.tab_suggestions:
            self.tab_completion_buffer = current_text
            self.tab_suggestions = self.command_processor.get_command_suggestions(current_text)
            self.tab_index = -1
        if self.tab_suggestions:
            self.tab_index = (self.tab_index + 1) % len(self.tab_suggestions)
            self.input_text = self.tab_suggestions[self.tab_index]
    
    def quit_game(self):
        if hasattr(self, 'plugin_manager'):
            self.plugin_manager.unload_all_plugins()
        pygame.quit()
        sys.exit()
    
    def run(self):
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
                    elif event.key == pygame.K_UP:
                        self.navigate_history(1)
                    elif event.key == pygame.K_DOWN:
                        self.navigate_history(-1)
                    elif event.key == pygame.K_TAB:
                        self.handle_tab_completion()
                    elif event.key == pygame.K_PAGEUP:
                        self.scroll_offset = min(len(self.text_buffer) * 10, 
                                                 self.scroll_offset + self.max_visible_lines // 2)
                    elif event.key == pygame.K_PAGEDOWN:
                        self.scroll_offset = max(0, self.scroll_offset - self.max_visible_lines // 2)
                    elif event.key == pygame.K_F1:
                        self.debug_mode = not self.debug_mode
                        if self.debug_mode:
                            self.text_buffer.append(f"{config.FORMAT_HIGHLIGHT}Debug mode enabled. Press F1 to disable.{config.FORMAT_RESET}")
                        else:
                            self.text_buffer.append(f"{config.FORMAT_HIGHLIGHT}Debug mode disabled.{config.FORMAT_RESET}")
                    else:
                        if event.unicode.isprintable():
                            self.input_text += event.unicode
                elif event.type == pygame.MOUSEWHEEL:
                    if event.y > 0:  # Scroll up
                        self.scroll_offset = min(len(self.text_buffer) * 10, 
                                                 self.scroll_offset + config.SCROLL_SPEED)
                    elif event.y < 0:  # Scroll down
                        self.scroll_offset = max(0, self.scroll_offset - config.SCROLL_SPEED)
                elif event.type == pygame.VIDEORESIZE:
                    config.SCREEN_WIDTH = event.w
                    config.SCREEN_HEIGHT = event.h
                    self.screen = pygame.display.set_mode((config.SCREEN_WIDTH, config.SCREEN_HEIGHT), 
                                                         pygame.RESIZABLE)
                    self._calculate_textwrap_width()
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
        if "new_period" in data:
            self.time_data["time_period"] = data["new_period"]
        if "transition_message" in data and data["transition_message"]:
            self.text_buffer.append(data['transition_message'])

    def _on_display_message(self, event_type: str, data: Any) -> None:
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