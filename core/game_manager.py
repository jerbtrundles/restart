# core/game_manager.py
import time
import pygame
import sys
from typing import Any, List, Optional

from core.config import BG_COLOR, DEFAULT_COLORS, DEFAULT_WORLD_FILE, FONT_SIZE, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_RESET, FORMAT_TITLE, INPUT_BG_COLOR, INPUT_HEIGHT, LINE_SPACING, SCREEN_HEIGHT, SCREEN_WIDTH, SCROLL_SPEED, TEXT_COLOR
from world.world import World
from commands.command_system import CommandProcessor
from utils.text_formatter import TextFormatter
from plugins.plugin_system import PluginManager
from commands.commands import register_movement_commands

class GameManager:
    def __init__(self, world_file: str = DEFAULT_WORLD_FILE):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont("monospace", FONT_SIZE)
        self.clock = pygame.time.Clock()

        self.text_formatter = TextFormatter(
            font=self.font, screen_width=SCREEN_WIDTH,
            colors=DEFAULT_COLORS, margin=10, line_spacing=LINE_SPACING
        )
        self.world = World()
        self.world.start_time = time.time(); self.world.game = self
        if not self.world.load_from_json(world_file):
            print(f"Failed to load world from {world_file}. Creating test world.")
            self._create_test_world()

        self.time_data = { # ... (time data init - unchanged) ...
            "hour": 12, "minute": 0, "day": 1, "month": 1, "year": 1,
            "day_name": "Moonday", "month_name": "Deepwinter",
            "time_period": "day", "time_str": "12:00",
            "date_str": "Moonday, 1 Deepwinter, Year 1"
        }
        self.command_processor = CommandProcessor() # ... (command processor init - unchanged) ...
        register_movement_commands()

        self.plugin_manager = PluginManager(self.world, self.command_processor) # ... (plugin manager init - unchanged) ...
        self.plugin_manager.event_system.subscribe("display_message", self._on_display_message)
        self.plugin_manager.event_system.subscribe("time_data", self._on_time_data_event)
        self.plugin_manager.event_system.subscribe("time_period_changed", self._on_time_period_changed)
        self.plugin_manager.load_all_plugins()

        self.text_buffer: List[str] = [] # ... (text buffer, input, cursor - unchanged) ...
        self.input_text = ""; self.cursor_visible = True; self.cursor_timer = 0
        self.command_history = []; self.history_index = -1
        self.tab_completion_buffer = ""; self.tab_suggestions = []; self.tab_index = -1
        self.scroll_offset = 0
        self.max_visible_lines = (SCREEN_HEIGHT - INPUT_HEIGHT - 40) // (FONT_SIZE + LINE_SPACING)
        self.debug_mode = False

        # --- NEW: Game State ---
        self.game_state = "playing" # Possible states: playing, game_over
        # --- END NEW ---

        welcome_message = f"{FORMAT_TITLE}Welcome to Pygame MUD!{FORMAT_RESET}\n\n"
        welcome_message += "Type 'help' to see available commands.\n\n"
        welcome_message += "=" * 40 + "\n\n"
        welcome_message += self.world.look()
        self.text_buffer.append(self._sanitize_text(welcome_message))

    def handle_input(self, text: str) -> str:
        """Process user input and get the result."""
        input_text = "> " + text
        self.text_buffer.append(input_text)

        if text.strip():
            self.command_history.append(text)
            self.history_index = -1

        context = {
            "game": self,
            "world": self.world,
            "command_processor": self.command_processor
        }

        # --- NEW: Block input if player is dead ---
        if not self.world.player.is_alive:
             return f"{FORMAT_ERROR}You are dead. You cannot do that.{FORMAT_RESET}"
             # Or return "" if no message is desired
        # --- END NEW ---

        result = self.command_processor.process_input(text, context)
        if result:
            return self._sanitize_text(result)
        return ""

    # ... (_sanitize_text - unchanged) ...
    def _sanitize_text(self, text: str) -> str:
        if not text: return ""
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = ''.join(ch if ch == '\n' or ord(ch) >= 32 else ' ' for ch in text)
        while '\n\n\n' in text: text = text.replace('\n\n\n', '\n\n')
        return text

    def update(self):
        """Update game state."""
        # --- NEW: Don't update world/plugins if game is over ---
        if self.game_state == "game_over":
             # Update cursor blink
             self.cursor_timer += self.clock.get_time()
             if self.cursor_timer >= 500:
                 self.cursor_visible = not self.cursor_visible
                 self.cursor_timer = 0
             return # Skip world updates
        # --- END NEW ---

        current_time = time.time() - self.world.start_time

        # This might be managed by the TimePlugin now, access it if needed
        # For mana regen, using real time might be simpler unless tied to game speed
        if self.world and self.world.player:
             self.world.player.update(current_time) # Pass time for regen calc
        # Or get game time from TimePlugin if precise game time needed:
        # time_plugin = self.service_locator.get_service("plugin:time_plugin")
        # current_game_time = time_plugin.game_time if time_plugin else 0

        # Update plugins (as before)
        if hasattr(self, 'plugin_manager'):
            if hasattr(self.plugin_manager, 'event_system'):
                self.plugin_manager.event_system.publish("on_tick", current_time)
            self.plugin_manager.on_tick(current_time)

        # Update NPCs (as before)
        npc_updates = self.world.update()
        if npc_updates:
            for message in npc_updates:
                if message:
                    self.text_buffer.append(message)

        # --- NEW: Check for player death ---
        if not self.world.player.is_alive and self.game_state == "playing":
             self.game_state = "game_over"
             # Add a clear death message to the buffer
             self.text_buffer.append("\n" + "="*40)
             self.text_buffer.append(f"{FORMAT_ERROR}{FORMAT_TITLE}YOU HAVE DIED{FORMAT_RESET}")
             self.text_buffer.append("Press 'R' to Respawn or 'Q' to Quit.")
             self.text_buffer.append("="*40 + "\n")
             self.scroll_offset = 0 # Scroll to show death message
        # --- END NEW ---

        # Update cursor blink (as before)
        self.cursor_timer += self.clock.get_time()
        if self.cursor_timer >= 500:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

    def draw(self):
        """Render the game to the screen with proper layout."""
        self._calculate_layout()
        self.screen.fill(BG_COLOR)
        self._draw_time_bar()

        # --- MODIFIED: Handle Game Over Screen ---
        if self.game_state == "game_over":
            # Render a specific game over message centered
            game_over_font = pygame.font.SysFont("monospace", 36, bold=True)
            death_text = "YOU HAVE DIED"
            respawn_text = "Press 'R' to Respawn or 'Q' to Quit"

            death_surface = game_over_font.render(death_text, True, DEFAULT_COLORS[FORMAT_ERROR])
            respawn_surface = self.font.render(respawn_text, True, TEXT_COLOR)

            death_rect = death_surface.get_rect(center=(self.layout["screen_width"] // 2, self.layout["screen_height"] // 2 - 20))
            respawn_rect = respawn_surface.get_rect(center=(self.layout["screen_width"] // 2, self.layout["screen_height"] // 2 + 20))

            self.screen.blit(death_surface, death_rect)
            self.screen.blit(respawn_surface, respawn_rect)

        else: # Normal drawing logic
            # Calculate total text content (as before)
            total_text = ""
            for text in self.text_buffer:
                if total_text: total_text += "\n\n"
                total_text += text

            formatted_lines = self.text_formatter.format_text(total_text)
            total_lines = len(formatted_lines)

            if self.scroll_offset > total_lines - self.max_visible_lines:
                self.scroll_offset = max(0, total_lines - self.max_visible_lines)

            start_line = max(0, total_lines - self.max_visible_lines - self.scroll_offset)
            visible_lines = min(self.max_visible_lines, total_lines - start_line)
            visible_text = "\n".join(formatted_lines[start_line:start_line + visible_lines])

            # Render the text (as before)
            self.text_formatter.render(
                surface=self.screen, text=visible_text,
                position=(10, self.layout["text_area"]["y"]),
                max_height=self.layout["text_area"]["y"] + self.layout["text_area"]["height"]
            )
            self._draw_scroll_indicator()

            # Draw input area (as before)
            pygame.draw.rect(self.screen, INPUT_BG_COLOR,
                             (0, self.layout["input_area"]["y"], self.layout["screen_width"], self.layout["input_area"]["height"]))
            input_display = "> " + self.input_text
            if self.cursor_visible: input_display += "|"
            input_surface = self.font.render(input_display, True, TEXT_COLOR)
            self.screen.blit(input_surface, (10, self.layout["input_area"]["y"] + 5))

            # Draw status area (as before)
            self._draw_status_indicators()
        # --- END MODIFIED ---

        if self.debug_mode: # ... (debug indicator - unchanged) ...
            debug_text = "DEBUG MODE"
            debug_surface = self.font.render(debug_text, True, (255, 0, 0))
            self.screen.blit(debug_surface,
                            (self.layout["screen_width"] - debug_surface.get_width() - 10, 40))

        pygame.display.flip()

    # ... (_draw_time_bar, _get_time_period_color, navigate_history, handle_tab_completion - unchanged) ...
    # ... (resize_screen, quit_game - unchanged) ...
    def _draw_time_bar(self):
        # ... (implementation unchanged) ...
        time_str = self.time_data.get("time_str", "??:??")
        date_str = self.time_data.get("date_str", "Unknown Date")
        time_period = self.time_data.get("time_period", "unknown")
        pygame.draw.rect(self.screen, (40, 40, 60), (0, 0, self.layout["screen_width"], self.layout["time_bar"]["height"]))
        time_color = self._get_time_period_color(time_period)
        time_surface = self.font.render(time_str, True, time_color)
        self.screen.blit(time_surface, (10, 5))
        date_surface = self.font.render(date_str, True, TEXT_COLOR)
        date_x = (self.layout["screen_width"] - date_surface.get_width()) // 2
        self.screen.blit(date_surface, (date_x, 5))
        period_surface = self.font.render(time_period.capitalize(), True, time_color)
        period_x = self.layout["screen_width"] - period_surface.get_width() - 10
        self.screen.blit(period_surface, (period_x, 5))
        pygame.draw.line(self.screen, (80, 80, 100), (0, self.layout["time_bar"]["height"]), (self.layout["screen_width"], self.layout["time_bar"]["height"]), 1)

    def _get_time_period_color(self, time_period):
        # ... (implementation unchanged) ...
        period_colors = {"dawn": (255, 165, 0), "day": (255, 255, 150), "dusk": (255, 100, 100), "night": (100, 100, 255)}
        return period_colors.get(time_period, TEXT_COLOR)

    def navigate_history(self, direction: int):
        # ... (implementation unchanged) ...
        if not self.command_history: return
        if direction > 0: self.history_index = min(self.history_index + 1, len(self.command_history) - 1)
        else: self.history_index = max(self.history_index - 1, -1)
        if self.history_index >= 0: self.input_text = self.command_history[-(self.history_index + 1)]
        else: self.input_text = ""
        self.tab_completion_buffer = ""; self.tab_suggestions = []; self.tab_index = -1

    def handle_tab_completion(self):
        # ... (implementation unchanged) ...
        current_text = self.input_text.strip()
        if not current_text: return
        if current_text != self.tab_completion_buffer or not self.tab_suggestions:
            self.tab_completion_buffer = current_text
            self.tab_suggestions = self.command_processor.get_command_suggestions(current_text)
            self.tab_index = -1
        if self.tab_suggestions:
            self.tab_index = (self.tab_index + 1) % len(self.tab_suggestions)
            self.input_text = self.tab_suggestions[self.tab_index]

    def resize_screen(self, new_width, new_height):
        # ... (implementation unchanged) ...
        SCREEN_WIDTH = new_width; SCREEN_HEIGHT = new_height
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
        self.text_formatter.update_screen_width(new_width)

    def quit_game(self):
        # ... (implementation unchanged) ...
        if hasattr(self, 'plugin_manager'): self.plugin_manager.unload_all_plugins()
        pygame.quit()
        sys.exit()

    # --- NEW: Handle Respawn ---
    def handle_respawn(self):
        """Handles the player respawn logic."""
        if self.game_state != "game_over": return

        player = self.world.player
        player.respawn() # Reset player state

        # Move player to respawn location
        self.world.current_region_id = player.respawn_region_id
        self.world.current_room_id = player.respawn_room_id

        # Add respawn message
        self.text_buffer = [f"{FORMAT_HIGHLIGHT}You feel your spirit return to your body...{FORMAT_RESET}\n"]
        self.text_buffer.append(self.world.look()) # Show new location

        # Change game state back
        self.game_state = "playing"
        self.input_text = "" # Clear input
    # --- END NEW ---


    def run(self):
        """Main game loop."""
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                # --- MODIFIED: Handle Input Based on Game State ---
                if self.game_state == "game_over":
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_r: # Respawn
                            self.handle_respawn()
                        elif event.key == pygame.K_q: # Quit
                            running = False
                elif self.game_state == "playing":
                     if event.type == pygame.KEYDOWN:
                          if event.key == pygame.K_RETURN:
                               result = self.handle_input(self.input_text)
                               if result: self.text_buffer.append(result)
                               self.input_text = ""
                               self.scroll_offset = 0
                          elif event.key == pygame.K_BACKSPACE: self.input_text = self.input_text[:-1]
                          elif event.key == pygame.K_UP: self.navigate_history(1)
                          elif event.key == pygame.K_DOWN: self.navigate_history(-1)
                          elif event.key == pygame.K_TAB: self.handle_tab_completion()
                          elif event.key == pygame.K_PAGEUP: self.scroll_offset = min(len(self.text_buffer) * 20, self.scroll_offset + self.max_visible_lines // 2)
                          elif event.key == pygame.K_PAGEDOWN: self.scroll_offset = max(0, self.scroll_offset - self.max_visible_lines // 2)
                          elif event.key == pygame.K_HOME: self.scroll_offset = len(self.text_buffer) * 20
                          elif event.key == pygame.K_END: self.scroll_offset = 0
                          elif event.key == pygame.K_F1: # ... (debug toggle - unchanged) ...
                               self.debug_mode = not self.debug_mode
                               if self.debug_mode: self.text_buffer.append(f"{FORMAT_HIGHLIGHT}Debug mode enabled. Press F1 to disable.{FORMAT_RESET}")
                               else: self.text_buffer.append(f"{FORMAT_HIGHLIGHT}Debug mode disabled.{FORMAT_RESET}")
                          else:
                               if event.unicode.isprintable(): self.input_text += event.unicode
                     elif event.type == pygame.MOUSEWHEEL: # ... (scrolling - unchanged) ...
                          if event.y > 0: self.scroll_offset = min(len(self.text_buffer) * 20, self.scroll_offset + SCROLL_SPEED)
                          elif event.y < 0: self.scroll_offset = max(0, self.scroll_offset - SCROLL_SPEED)
                     elif event.type == pygame.VIDEORESIZE: self.resize_screen(event.w, event.h)
                # --- END MODIFIED ---

            self.update()
            self.draw()
            self.clock.tick(30)

        self.quit_game()

    # ... (_on_display_message, _on_time_data_event, _on_time_period_changed - unchanged) ...
    # ... (_create_test_world, _trim_text_buffer, _draw_status_indicators, _draw_scroll_indicator, _calculate_layout - unchanged) ...
    def _on_display_message(self, event_type: str, data: Any) -> None:
        if isinstance(data, str): message = data
        elif isinstance(data, dict) and "message" in data: message = data["message"]
        else:
            try: message = str(data)
            except: message = "Unprintable message"
        self.text_buffer.append(message)

    def _on_time_data_event(self, event_type: str, data: dict) -> None: self.time_data = data
    def _on_time_period_changed(self, event_type: str, data: dict) -> None:
        if "new_period" in data: self.time_data["time_period"] = data["new_period"]
        if "transition_message" in data and data["transition_message"]: self.text_buffer.append(data['transition_message'])

    def _create_test_world(self):
        # ... (implementation unchanged) ...
        from world.region import Region; from world.room import Room
        test_region = Region("Test Region", "A small test area.")
        entrance = Room("Entrance", "The entrance to the test region.")
        hall = Room("Main Hall", "A large hall with high ceilings.")
        garden = Room("Garden", "A beautiful garden with many plants.")
        entrance.exits = {"north": "hall"}; hall.exits = {"south": "entrance", "east": "garden"}; garden.exits = {"west": "hall"}
        garden.env_properties["outdoors"] = True; hall.env_properties["has_windows"] = True
        test_region.add_room("entrance", entrance); test_region.add_room("hall", hall); test_region.add_room("garden", garden)
        self.world.add_region("test", test_region)
        self.world.current_region_id = "test"; self.world.current_room_id = "entrance"
        from items.item_factory import ItemFactory
        sword = ItemFactory.create_item("Weapon", name="Steel Sword", description="A sharp steel sword.", damage=10)
        potion = ItemFactory.create_item("Consumable", name="Healing Potion", description="A potion that restores health.", effect_value=20, effect_type="heal")
        key = ItemFactory.create_item("Key", name="Brass Key", description="A small brass key.")
        self.world.add_item_to_room("test", "hall", sword); self.world.add_item_to_room("test", "garden", potion)
        self.world.player.inventory.add_item(key)
        from npcs.npc_factory import NPCFactory
        guard = NPCFactory.create_npc("guard", name="Guard Bob"); guard.current_region_id = "test"; guard.current_room_id = "entrance"; guard.patrol_points = ["entrance", "hall"]
        merchant = NPCFactory.create_npc("shopkeeper", name="Merchant Alice"); merchant.current_region_id = "test"; merchant.current_room_id = "hall"
        villager = NPCFactory.create_npc("villager", name="Villager Charlie"); villager.current_region_id = "test"; villager.current_room_id = "garden"
        self.world.add_npc(guard); self.world.add_npc(merchant); self.world.add_npc(villager)

    def _trim_text_buffer(self):
        # ... (implementation unchanged) ...
        max_buffer_size = 1000 # pygame.GL_BUFFER_SIZE if hasattr(core.config, 'MAX_BUFFER_SIZE') else 1000
        if len(self.text_buffer) > max_buffer_size:
            excess = len(self.text_buffer) - max_buffer_size; self.text_buffer = self.text_buffer[excess:]
            self.text_buffer.insert(0, f"{FORMAT_HIGHLIGHT}(Older messages have been removed to save memory){FORMAT_RESET}")

    def _draw_status_indicators(self):
        """Draws health, mana, XP, etc. in the status area."""
        if not hasattr(self.world, 'player') or not self.world.player: return
        player = self.world.player

        status_y_offset = 5 # How far down from the top of the status area the bars/text start

        # --- Health Bar ---
        health_width = 100
        health_height = 10 # Slightly taller bar
        health_x = 10
        health_y = self.layout["status_area"]["y"] + status_y_offset

        # Background
        pygame.draw.rect(self.screen, (80, 0, 0), (health_x, health_y, health_width, health_height))

        # Foreground (Filled portion)
        health_percent = player.health / player.max_health if player.max_health > 0 else 0
        filled_health_width = int(health_width * health_percent)
        if health_percent < 0.3: health_color = (200, 0, 0)      # Red
        elif health_percent < 0.7: health_color = (200, 200, 0)  # Yellow
        else: health_color = (0, 200, 0)                         # Green
        pygame.draw.rect(self.screen, health_color, (health_x, health_y, filled_health_width, health_height))

        # Health Text
        health_text = f"HP: {player.health}/{player.max_health}"
        health_surface = self.font.render(health_text, True, TEXT_COLOR)
        hp_text_x = health_x + health_width + 10
        # Center text vertically with the bar center
        hp_text_y = health_y + (health_height // 2) - (health_surface.get_height() // 2)
        self.screen.blit(health_surface, (hp_text_x, hp_text_y))


        # --- Mana Bar (NEW) ---
        mana_width = 100
        mana_height = 10 # Same height as HP bar
        # Position mana bar after HP text, with some padding
        mana_x = hp_text_x + health_surface.get_width() + 25
        mana_y = self.layout["status_area"]["y"] + status_y_offset # Same vertical position as HP bar

        # Mana Background
        mana_bg_color = (0, 0, 80) # Dark Blue
        pygame.draw.rect(self.screen, mana_bg_color, (mana_x, mana_y, mana_width, mana_height))

        # Mana Foreground (Filled portion)
        mana_percent = player.mana / player.max_mana if player.max_mana > 0 else 0
        filled_mana_width = int(mana_width * mana_percent)
        mana_fill_color = (50, 100, 255) # Bright Blue
        pygame.draw.rect(self.screen, mana_fill_color, (mana_x, mana_y, filled_mana_width, mana_height))

        # Mana Text
        mana_text = f"MP: {player.mana}/{player.max_mana}"
        mana_surface = self.font.render(mana_text, True, TEXT_COLOR)
        mp_text_x = mana_x + mana_width + 10
        # Center text vertically with the bar center
        mp_text_y = mana_y + (mana_height // 2) - (mana_surface.get_height() // 2)
        self.screen.blit(mana_surface, (mp_text_x, mp_text_y))
        # --- End Mana Bar ---


        # --- XP Text ---
        if hasattr(player, 'experience') and hasattr(player, 'experience_to_level'):
            xp_text = f"XP: {player.experience}/{player.experience_to_level} (Lvl {player.level})"
            xp_surface = self.font.render(xp_text, True, TEXT_COLOR)
            # Align XP text to the far right, before the margin
            xp_x = self.layout["screen_width"] - xp_surface.get_width() - 10
            # Center text vertically with the bars
            xp_y = health_y + (health_height // 2) - (xp_surface.get_height() // 2)
            self.screen.blit(xp_surface, (xp_x, xp_y))

        # --- Separator Line ---
        # Draw line above the status area content
        line_y = self.layout["status_area"]["y"]
        pygame.draw.line(self.screen, (80, 80, 100), (0, line_y -1), (self.layout["screen_width"], line_y - 1), 1)

    def _draw_scroll_indicator(self):
        # ... (implementation unchanged) ...
        total_text = "";
        for text in self.text_buffer:
            if total_text: total_text += "\n\n";
            total_text += text
        formatted_lines = self.text_formatter.format_text(total_text); total_lines = len(formatted_lines)
        start_line = max(0, total_lines - self.max_visible_lines - self.scroll_offset)
        if self.scroll_offset > 0:
            arrow_points = [(self.layout["screen_width"] - 30, self.layout["text_area"]["y"] + 10), (self.layout["screen_width"] - 20, self.layout["text_area"]["y"]), (self.layout["screen_width"] - 10, self.layout["text_area"]["y"] + 10)]
            pygame.draw.polygon(self.screen, (200, 200, 200), arrow_points)
        if start_line + self.max_visible_lines < total_lines:
            bottom_y = self.layout["input_area"]["y"] - 10
            arrow_points = [(self.layout["screen_width"] - 30, bottom_y - 10), (self.layout["screen_width"] - 20, bottom_y), (self.layout["screen_width"] - 10, bottom_y - 10)]
            pygame.draw.polygon(self.screen, (200, 200, 200), arrow_points)

    def _calculate_layout(self):
        """Recalculates UI element positions and sizes."""
        # Ensure status area height is sufficient
        status_area_height = 30 # Increase height slightly to accommodate bars and text comfortably

        self.layout = {
            "screen_width": SCREEN_WIDTH,
            "screen_height": SCREEN_HEIGHT,
            "time_bar": {"height": 30, "y": 0},
            "input_area": {"height": INPUT_HEIGHT, "y": SCREEN_HEIGHT - INPUT_HEIGHT},
            # Calculate status area position based on input area
            "status_area": {"height": status_area_height, "y": SCREEN_HEIGHT - INPUT_HEIGHT - status_area_height}
        }
        # Calculate text area based on time bar and status area
        self.layout["text_area"] = {
            "y": self.layout["time_bar"]["height"] + 10,
            "height": self.layout["status_area"]["y"] - (self.layout["time_bar"]["height"] + 20) # Space between text and status
        }

        # Recalculate max visible lines (important!)
        line_height = self.font.get_linesize() + LINE_SPACING
        self.max_visible_lines = self.layout["text_area"]["height"] // line_height if line_height > 0 else 20
