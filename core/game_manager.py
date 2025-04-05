# core/game_manager.py
import time
import pygame
import sys
import os # Needed for path joining
from typing import Any, List, Optional

from core.config import (
    BG_COLOR, DEFAULT_COLORS, FONT_SIZE, FORMAT_ERROR, FORMAT_HIGHLIGHT,
    FORMAT_RESET, FORMAT_TITLE, INPUT_BG_COLOR, INPUT_HEIGHT, LINE_SPACING, MAX_BUFFER_LINES,
    SCREEN_HEIGHT, SCREEN_WIDTH, SCROLL_SPEED, TEXT_COLOR, SAVE_GAME_DIR,
    DATA_DIR, COLOR_ORANGE # <<< Added COLOR_ORANGE
)

from world.world import World
from commands.command_system import CommandProcessor
from utils.text_formatter import TextFormatter
from plugins.plugin_system import PluginManager
from commands.commands import register_movement_commands, save_handler, load_handler # Import specific handlers


class GameManager:
    def __init__(self, save_file: str = "default_save.json"): # Use save file name
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Pygame MUD")
        self.font = pygame.font.SysFont("monospace", FONT_SIZE)
        self.clock = pygame.time.Clock()
        self.current_save_file = save_file # Store the target save file

        self.text_formatter = TextFormatter(
            font=self.font, screen_width=SCREEN_WIDTH,
            colors=DEFAULT_COLORS, margin=10, line_spacing=LINE_SPACING
        )
        
        self.world = World()
        self.world.start_time = time.time()
        self.world.game = self

        # --- Attempt to Load Save Game ---
        if not self.world.load_save_game(self.current_save_file):
             # If loading failed critically (not just file not found), maybe exit?
             # For now, initialize_new_world is called by load_save_game if file not found.
             print("Proceeding with a new game world.")
             # Ensure world is initialized if load_save_game failed early
             if not self.world.player:
                  self.world.initialize_new_world()

        # Ensure player location is set in world
        if self.world.player:
             self.world.current_region_id = self.world.player.current_region_id
             self.world.current_room_id = self.world.player.current_room_id
        else: # Should not happen if init/load worked, but safety
             print(f"{FORMAT_ERROR}Critical Error: Player object not found after world load/init.{FORMAT_RESET}")
             # Handle error appropriately - maybe force quit?
             self.world.current_region_id = "town"
             self.world.current_room_id = "town_square"

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

        self.text_buffer: List[str] = [] # Stores raw text strings with format codes
        self._trim_message_added = False
        
        self.input_text = ""; self.cursor_visible = True; self.cursor_timer = 0
        self.command_history = []; self.history_index = -1
        self.tab_completion_buffer = ""; self.tab_suggestions = []; self.tab_index = -1

        self.scroll_offset = 0 # Now conceptually represents pixel offset from the *bottom*
        self.total_rendered_height = 0 # Keep track of the height of the rendered buffer

        self.debug_mode = False
        self.game_state = "playing" # Possible states: playing, game_over

        # --- Initial Message ---
        welcome_message = f"{FORMAT_TITLE}Welcome to Pygame MUD!{FORMAT_RESET}\n"
        # Indicate if loaded or new
        save_path = os.path.join(SAVE_GAME_DIR, self.current_save_file)
        if os.path.exists(save_path):
             welcome_message += f"(Loaded game: {self.current_save_file})\n"
        else:
             welcome_message += "(Started new game)\n"
        welcome_message += "Type 'help' to see available commands.\n\n"
        welcome_message += "=" * 40 + "\n\n"
        welcome_message += self.world.look()
        self.text_buffer.append(self._sanitize_text(welcome_message))
        self._trim_text_buffer() # Trim after adding initial messages

    def handle_input(self, text: str) -> str:
        """Process user input and get the result."""
        input_text = "> " + text
        self.text_buffer.append(input_text)
        self._trim_text_buffer() # <-- Call trim

        if text.strip():
            self.command_history.append(text)
            self.history_index = -1

        context = {
            "game": self,
            "world": self.world,
            "command_processor": self.command_processor,
            "current_save_file": self.current_save_file # Pass current save name
        }

        if not self.world.player.is_alive:
             result = f"{FORMAT_ERROR}You are dead. You cannot do that.{FORMAT_RESET}"
             self.text_buffer.append(result)
             self._trim_text_buffer() # <-- Call trim after adding error message
             return "" # Return empty as the message is already in buffer

        command_result = self.command_processor.process_input(text, context)
        if command_result:
            # Sanitize and add command result to buffer
            sanitized_result = self._sanitize_text(command_result)
            self.text_buffer.append(sanitized_result)
            self._trim_text_buffer() # <-- Call trim after adding command result

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

        current_time = time.time() # Use absolute time

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
        npc_updates = self.world.update() # world.update now returns messages
        if npc_updates:
            for message in npc_updates:
                if message:
                    # Sanitize and add NPC update messages
                    self.text_buffer.append(self._sanitize_text(message))
            # Trim *after* processing all NPC updates for this tick
            self._trim_text_buffer() # <-- Call trim

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

        else:
            full_text_to_render = "\n\n".join(self.text_buffer)

            # --- Render to get total height ---
            # Make buffer surface taller just in case
            estimated_max_height = len(self.text_buffer) * 6 * self.text_formatter.line_height # Even more space
            buffer_surface_height = max(self.layout["text_area"]["height"] + 500, estimated_max_height)

            buffer_surface = pygame.Surface((self.layout["text_area"]["width"], buffer_surface_height), pygame.SRCALPHA)
            buffer_surface.fill((0, 0, 0, 0))

            # Render the entire buffer
            final_y = self.text_formatter.render(
                surface=buffer_surface,
                text=full_text_to_render,
                position=(0, 0)
            )
            # Use the final_y directly, assuming it's the coord *below* the last line
            # Clamp it to be at least the visible height for calculation safety
            self.total_rendered_height = max(self.layout["text_area"]["height"], final_y)

            # --- Scrolling Calculation (Same as before) ---
            visible_height = self.layout["text_area"]["height"]
            max_scroll = max(0, self.total_rendered_height - visible_height)
            self.scroll_offset = max(0, min(self.scroll_offset, max_scroll))
            source_y = max(0, self.total_rendered_height - visible_height - self.scroll_offset)
            source_rect = pygame.Rect(
                0, source_y,
                self.layout["text_area"]["width"],
                min(visible_height, self.total_rendered_height - source_y) # Height to actually copy
            )
            dest_pos = (self.layout["text_area"]["x"], self.layout["text_area"]["y"])
            self.screen.blit(buffer_surface, dest_pos, source_rect)
            # --- End Rendering with Scrolling ---

            self._draw_scroll_indicator()
            self._draw_input_area()
            self._draw_status_indicators()

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
                          elif event.key == pygame.K_BACKSPACE:
                              self.input_text = self.input_text[:-1]
                          elif event.key == pygame.K_UP:
                              self.navigate_history(1)
                          elif event.key == pygame.K_DOWN:
                              self.navigate_history(-1)
                          elif event.key == pygame.K_TAB:
                              self.handle_tab_completion()
                          elif event.key == pygame.K_PAGEUP:
                              scroll_amount = self.layout["text_area"]["height"] // 2
                              max_scroll = max(0, self.total_rendered_height - self.layout["text_area"]["height"])
                              self.scroll_offset = min(max_scroll, self.scroll_offset + scroll_amount)
                          elif event.key == pygame.K_PAGEDOWN:
                              # Scroll down by roughly half the text area height
                              scroll_amount = self.layout["text_area"]["height"] // 2
                              self.scroll_offset = max(0, self.scroll_offset - scroll_amount)
                          elif event.key == pygame.K_HOME:
                              # Go to the very top (max scroll)
                              max_scroll = max(0, self.total_rendered_height - self.layout["text_area"]["height"])
                              self.scroll_offset = max_scroll
                          elif event.key == pygame.K_END:
                              self.scroll_offset = 0
                          elif event.key == pygame.K_F1: # ... (debug toggle - unchanged) ...
                               self.debug_mode = not self.debug_mode
                               if self.debug_mode:
                                   self.text_buffer.append(f"{FORMAT_HIGHLIGHT}Debug mode enabled. Press F1 to disable.{FORMAT_RESET}")
                               else:
                                   self.text_buffer.append(f"{FORMAT_HIGHLIGHT}Debug mode disabled.{FORMAT_RESET}")
                          else:
                               if event.unicode.isprintable():
                                   self.input_text += event.unicode
                     elif event.type == pygame.MOUSEWHEEL:
                          # Scroll up/down by a fixed pixel amount per wheel tick
                          scroll_amount = SCROLL_SPEED * self.text_formatter.line_height # Scroll by lines
                          max_scroll = max(0, self.total_rendered_height - self.layout["text_area"]["height"])
                          if event.y > 0: # Scroll up (show older)
                              self.scroll_offset = min(max_scroll, self.scroll_offset + scroll_amount)
                          elif event.y < 0: # Scroll down (show newer)
                              self.scroll_offset = max(0, self.scroll_offset - scroll_amount)
                     elif event.type == pygame.VIDEORESIZE: self.resize_screen(event.w, event.h)

            self.update()
            self.draw()
            self.clock.tick(30)

        self.quit_game()

    def _on_display_message(self, event_type: str, data: Any) -> None:
        """Handles messages published by plugins/events."""
        if isinstance(data, str): message = data
        elif isinstance(data, dict) and "message" in data: message = data["message"]
        else:
            try: message = str(data)
            except: message = "Unprintable message"

        # Sanitize and add the message
        self.text_buffer.append(self._sanitize_text(message))
        self._trim_text_buffer() # <-- Call trim after adding event message

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

    def _draw_status_indicators(self):
        """Draws health, mana, XP, etc. in the status area."""
        if not hasattr(self.world, 'player') or not self.world.player: return
        player = self.world.player

        status_y_offset = 5 # How far down from the top of the status area the bars/text start
        bar_height = 10 # Standard height for bars
        bar_width = 100 # Standard width for bars
        text_padding = 10 # Space between bar and text
        bar_padding = 25 # Space between bar sections (e.g., HP text and Mana bar)

        # --- Health Bar ---
        health_x = self.text_formatter.margin # Start at margin
        # Use the calculated Y for the status area
        health_y = self.layout["status_area"]["y"] + status_y_offset

        # Background
        pygame.draw.rect(self.screen, (80, 0, 0), (health_x, health_y, bar_width, bar_height))

        # Foreground (Filled portion)
        health_percent = player.health / player.max_health if player.max_health > 0 else 0
        filled_health_width = int(bar_width * health_percent)
        if health_percent < 0.3: health_color = (200, 0, 0)      # Red
        elif health_percent < 0.7: health_color = (200, 200, 0)  # Yellow
        else: health_color = (0, 200, 0)                         # Green
        pygame.draw.rect(self.screen, health_color, (health_x, health_y, filled_health_width, bar_height))

        # Health Text
        health_text = f"HP: {player.health}/{player.max_health}"
        health_surface = self.font.render(health_text, True, TEXT_COLOR)
        hp_text_x = health_x + bar_width + text_padding
        # Center text vertically with the bar center
        hp_text_y = health_y + (bar_height // 2) - (health_surface.get_height() // 2)
        self.screen.blit(health_surface, (hp_text_x, hp_text_y))


        # --- Mana Bar ---
        # Position mana bar after HP text, with bar padding
        mana_x = hp_text_x + health_surface.get_width() + bar_padding
        mana_y = health_y # Same vertical position as HP bar

        # Mana Background
        mana_bg_color = (0, 0, 80) # Dark Blue
        pygame.draw.rect(self.screen, mana_bg_color, (mana_x, mana_y, bar_width, bar_height))

        # Mana Foreground (Filled portion)
        mana_percent = player.mana / player.max_mana if player.max_mana > 0 else 0
        filled_mana_width = int(bar_width * mana_percent)
        mana_fill_color = (50, 100, 255) # Bright Blue
        pygame.draw.rect(self.screen, mana_fill_color, (mana_x, mana_y, filled_mana_width, bar_height))

        # Mana Text
        mana_text = f"MP: {player.mana}/{player.max_mana}"
        mana_surface = self.font.render(mana_text, True, TEXT_COLOR)
        mp_text_x = mana_x + bar_width + text_padding
        # Center text vertically with the bar center
        mp_text_y = mana_y + (bar_height // 2) - (mana_surface.get_height() // 2)
        self.screen.blit(mana_surface, (mp_text_x, mp_text_y))


        # --- Experience (XP) Bar (NEW) ---
        xp_x = mp_text_x + mana_surface.get_width() + bar_padding
        xp_y = mana_y # Same vertical position

        # XP Background
        xp_bg_color = (100, 60, 0) # Dark Orange/Brown
        pygame.draw.rect(self.screen, xp_bg_color, (xp_x, xp_y, bar_width, bar_height))

        # XP Foreground
        xp = player.experience
        xp_needed = player.experience_to_level
        xp_percent = xp / xp_needed if xp_needed > 0 else 0
        # Ensure percent doesn't exceed 1 visually even if xp > xp_needed briefly
        filled_xp_width = int(bar_width * min(1.0, xp_percent))
        xp_fill_color = COLOR_ORANGE # Use orange from config
        pygame.draw.rect(self.screen, xp_fill_color, (xp_x, xp_y, filled_xp_width, bar_height))

        # XP Text
        xp_text = f"XP: {xp}/{xp_needed} (Lvl {player.level})"
        xp_surface = self.font.render(xp_text, True, TEXT_COLOR)
        xp_text_x = xp_x + bar_width + text_padding
        xp_text_y = xp_y + (bar_height // 2) - (xp_surface.get_height() // 2)
        self.screen.blit(xp_surface, (xp_text_x, xp_text_y))
        # --- End XP Bar ---

        # --- Separator Line ---
        line_y = self.layout["status_area"]["y"]
        pygame.draw.line(self.screen, (80, 80, 100), (0, line_y - 1), (self.layout["screen_width"], line_y - 1), 1)

    # --- Scroll Indicator uses max_scroll ---
    def _draw_scroll_indicator(self):
        """Draws arrows if scrolling is possible."""
        # Ensure layout and total_rendered_height are calculated before calling this
        if not hasattr(self, 'layout') or not hasattr(self, 'total_rendered_height'):
            return # Cannot draw indicators without layout/height info

        visible_height = self.layout["text_area"]["height"]
        max_scroll = max(0, self.total_rendered_height - visible_height)

        # Show up arrow if scrolling up is possible (not at the very top)
        if self.scroll_offset < max_scroll:
             # Define points for the UP arrow
             arrow_points_up = [
                 (self.layout["screen_width"] - 25, self.layout["text_area"]["y"] + 15), # Bottom left base
                 (self.layout["screen_width"] - 15, self.layout["text_area"]["y"] + 5),  # Top point
                 (self.layout["screen_width"] - 5, self.layout["text_area"]["y"] + 15)   # Bottom right base
             ]
             # Check if points are valid before drawing
             if len(arrow_points_up) >= 3:
                  pygame.draw.polygon(self.screen, (200, 200, 200), arrow_points_up)

        # Show down arrow if scrolling down is possible (not at the very bottom)
        if self.scroll_offset > 0:
            # Define points for the DOWN arrow
            bottom_y = self.layout["input_area"]["y"]
            arrow_points_down = [
                (self.layout["screen_width"] - 25, bottom_y - 15), # Top left base
                (self.layout["screen_width"] - 15, bottom_y - 5),  # Bottom point
                (self.layout["screen_width"] - 5, bottom_y - 15)   # Top right base
            ]
            # Check if points are valid before drawing
            if len(arrow_points_down) >= 3:
                 pygame.draw.polygon(self.screen, (200, 200, 200), arrow_points_down)

    # Ensure _calculate_layout correctly sets text_area height
    def _calculate_layout(self):
        """Recalculates UI element positions and sizes."""
        time_bar_height = 30 # Or get from self.layout if exists
        input_area_height = INPUT_HEIGHT
        status_area_height = 30 # Or keep flexible if needed

        self.layout = {
            "screen_width": SCREEN_WIDTH,
            "screen_height": SCREEN_HEIGHT,
            "time_bar": {"height": time_bar_height, "y": 0},
            "status_area": {"height": status_area_height, "y": SCREEN_HEIGHT - status_area_height},
            "input_area": {"height": input_area_height, "y": SCREEN_HEIGHT - status_area_height - input_area_height}
        }

        # Calculate text area position and dimensions
        text_area_y = self.layout["time_bar"]["height"] + self.text_formatter.margin
        # Text area bottom boundary is now the top of the INPUT area
        text_area_bottom = self.layout["input_area"]["y"]
        text_area_height = text_area_bottom - text_area_y - self.text_formatter.margin
        text_area_height = max(10, text_area_height) # Ensure positive height

        self.layout["text_area"] = {
            "x": self.text_formatter.margin,
            "y": text_area_y,
            "width": self.text_formatter.usable_width, # Assumes usable_width is updated correctly
            "height": text_area_height
        }
        # Update text formatter's usable width based on potentially changed screen width
        # (This line might be redundant if update_screen_width called elsewhere on resize)
        self.text_formatter.update_screen_width(SCREEN_WIDTH)

    def _draw_input_area(self):
        pygame.draw.rect(self.screen, INPUT_BG_COLOR,
                         (0, self.layout["input_area"]["y"], self.layout["screen_width"], self.layout["input_area"]["height"]))
        input_display = "> " + self.input_text
        if self.cursor_visible: input_display += "|"
        input_surface = self.font.render(input_display, True, TEXT_COLOR)
        input_y_pos = self.layout["input_area"]["y"] + (self.layout["input_area"]["height"] - input_surface.get_height()) // 2
        self.screen.blit(input_surface, (self.text_formatter.margin, input_y_pos))

    def _trim_text_buffer(self):
        """Removes older entries from the text buffer if it exceeds the limit."""
        # print(f"[DEBUG TRIM] Check: Buffer size = {len(self.text_buffer)}, Limit = {MAX_BUFFER_LINES}")
        if len(self.text_buffer) > MAX_BUFFER_LINES:
            excess = len(self.text_buffer) - MAX_BUFFER_LINES
            self.text_buffer = self.text_buffer[excess:] # Keep the latest entries

            # # Add a notification only once, at the *new* top
            # trim_notice = f"{FORMAT_HIGHLIGHT}(Older messages removed to prevent slowdown){FORMAT_RESET}"
            # # Avoid adding duplicate trim notices consecutively
            # if not self.text_buffer or self.text_buffer[0] != trim_notice:
            #      # Insert at the beginning so it's visible when scrolling up
            #      self.text_buffer.append(trim_notice)
