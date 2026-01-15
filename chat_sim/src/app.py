import pygame
import random
import threading
from .config import *
from .ui_kit import Button, TextInput
from .models import Character, ChatMessage
from .storage import load_characters, save_characters
from .llm_client import generate_response

class App:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("AOL Sim 98")
        self.font = pygame.font.SysFont("arial", 16)
        self.header_font = pygame.font.SysFont("arial", 20, bold=True)
        
        self.clock = pygame.time.Clock()
        self.running = True
        self.mode = "CHAT" # CHAT or CREATOR
        
        # Data
        self.characters = load_characters()
        self.chat_history = []
        
        # Simulation Logic
        self.is_generating = False
        self.last_turn_time = pygame.time.get_ticks()
        self.turn_delay = 1  # ms between bots talking

        # UI Setup
        self.setup_creator_ui()
        self.setup_chat_ui()

    def setup_creator_ui(self):
        self.inp_name = TextInput(200, 100, 300, 30, "Name:")
        self.inp_prompt = TextInput(200, 180, 400, 30, "Personality Prompt:")
        
        self.btn_save = Button(200, 240, 100, 30, "Save", self.save_character)
        self.btn_cancel = Button(320, 240, 100, 30, "Back to Chat", self.switch_to_chat)
        
        self.creator_ui_elements = [self.inp_name, self.inp_prompt, self.btn_save, self.btn_cancel]

    def setup_chat_ui(self):
        # Move button to the right to align with new Roster column
        # x=800 puts it nicely under the new roster window
        self.btn_create = Button(800, 530, 120, 30, "Create Person", self.switch_to_creator)
        self.chat_ui_elements = [self.btn_create]

    def save_character(self):
        if self.inp_name.text and self.inp_prompt.text:
            print(f"--- [CREATOR] Saving new character: {self.inp_name.text} ---")
            new_char = Character(self.inp_name.text, self.inp_prompt.text)
            self.characters.append(new_char)
            save_characters(self.characters)
            self.inp_name.text = ""
            self.inp_prompt.text = ""
            self.switch_to_chat()

    def switch_to_creator(self):
        print("--- [UI] Switching to Creator Mode ---")
        self.mode = "CREATOR"

    def switch_to_chat(self):
        print("--- [UI] Switching to Chat Mode ---")
        self.mode = "CHAT"

    def bot_turn(self):
        if not self.characters: return
        
        # 1. Identify who spoke last
        last_sender = None
        if self.chat_history:
            last_sender = self.chat_history[-1].sender
        
        # 2. Create a list of allowed speakers (everyone except the last person)
        candidates = [c for c in self.characters if c.name != last_sender]
        
        # 3. Fallback: If only 1 person is in the room, they have to talk to themselves
        if not candidates:
            candidates = self.characters

        speaker = random.choice(candidates)
        
        print(f"--- [GAME] Selected speaker: {speaker.name} (excluded: {last_sender}) ---")
        
        self.current_speaker_name = speaker.name 
        self.is_generating = True

        def task():
            # Pass the selected speaker and history to the LLM
            text = generate_response(speaker, self.chat_history[-HISTORY_LIMIT:])
            self.chat_history.append(ChatMessage(speaker.name, text))
            self.is_generating = False
            self.current_speaker_name = None
            
        t = threading.Thread(target=task)
        t.start()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            current_time = pygame.time.get_ticks()

            # --- Event Handling ---
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                
                ui_list = self.creator_ui_elements if self.mode == "CREATOR" else self.chat_ui_elements
                for el in ui_list:
                    el.handle_event(event)

            # --- Logic ---
            if self.mode == "CHAT":
                # Auto-conversation logic
                if len(self.characters) > 1 and not self.is_generating:
                    if current_time - self.last_turn_time > self.turn_delay:
                        self.bot_turn()
                        self.last_turn_time = current_time
                        self.turn_delay = 1 # random.randint(2000, 6000)

            # --- Drawing ---
            self.screen.fill(COLOR_BG)

            if self.mode == "CREATOR":
                self.draw_creator()
            else:
                self.draw_chat()

            pygame.display.flip()

        pygame.quit()

    def draw_window_frame(self, x, y, w, h, title):
        pygame.draw.rect(self.screen, COLOR_WINDOW, (x, y, w, h))
        pygame.draw.rect(self.screen, (0,0,0), (x, y, w, h), 1)
        # Title bar
        pygame.draw.rect(self.screen, COLOR_TITLE_BAR, (x+2, y+2, w-4, 20))
        lbl = self.font.render(title, True, COLOR_TITLE_TEXT)
        self.screen.blit(lbl, (x+5, y+2))

    def draw_creator(self):
        # Optional: Center the creator window on the new wider screen
        # Window width 600, Screen 1024 -> x = (1024-600)/2 = 212
        self.draw_window_frame(212, 50, 600, 400, "Character Creator v1.0")
        
        # We also need to offset the input fields if we move the window, 
        # but for now, the inputs are hardcoded in setup_creator_ui(). 
        # If the inputs look off-center, you can leave this window at x=100 
        # or update setup_creator_ui positions. 
        # For simplicity, let's keep the inputs where they are and just widen the frame:
        # self.draw_window_frame(100, 50, 800, 400, "Character Creator v1.0") 
        # Or just leave the previous draw_creator code alone, it will just be left-aligned.
        
        # Let's keep the original draw_creator logic from previous steps unless you want to re-math the buttons.
        self.draw_window_frame(100, 50, 600, 400, "Character Creator v1.0")
        for el in self.creator_ui_elements:
            el.draw(self.screen, self.font)

    def draw_chat(self):
        # --- 1. Draw Windows ---
        # Main Chat Window (Widen to 750px)
        chat_x, chat_y, chat_w, chat_h = 20, 20, 750, 500
        self.draw_window_frame(chat_x, chat_y, chat_w, chat_h, "Chat Room - Main Lobby")
        
        # Roster Window
        self.draw_window_frame(790, 20, 210, 500, "Online")

        # --- 2. Draw Roster Names ---
        y_off = 50
        for char in self.characters:
            display_name = char.name if len(char.name) < 22 else char.name[:19] + "..."
            txt = self.font.render(display_name, True, COLOR_TEXT)
            self.screen.blit(txt, (800, y_off))
            y_off += 20

        # --- 3. Draw Chat Messages (With Text Wrapping) ---
        
        # Helper: text wrapping logic
        def get_wrapped_lines(text, font, max_width):
            words = text.split(' ')
            lines = []
            current_line = []
            
            for word in words:
                # Test if adding the next word exceeds width
                test_line = ' '.join(current_line + [word])
                w, h = font.size(test_line)
                if w < max_width:
                    current_line.append(word)
                else:
                    # Line is full, push it and start new one
                    lines.append(' '.join(current_line))
                    current_line = [word]
            
            # Append the remainder
            if current_line:
                lines.append(' '.join(current_line))
            return lines

        # Area where text can actually go
        text_area_width = chat_w - 20  # Padding
        line_height = 20
        max_lines_visible = (chat_h - 40) // line_height  # How many lines fit vertically?

        # Convert recent history into a flat list of visual lines
        visual_lines = []
        
        # We look at the last 15 messages to ensure we have enough content to fill the screen
        # (If messages are long, 15 is plenty. If short, it might leave space at top, which is fine)
        for msg in self.chat_history[-15:]:
            full_text = f"{msg.sender}: {msg.text}"
            wrapped = get_wrapped_lines(full_text, self.font, text_area_width)
            visual_lines.extend(wrapped)

        # Slice to keep only the lines that fit in the window (Bottom-up view)
        lines_to_draw = visual_lines[-max_lines_visible:]

        # Render them
        y_text = 50 # Start y position inside the window
        for line in lines_to_draw:
            txt_surf = self.font.render(line, True, COLOR_TEXT)
            self.screen.blit(txt_surf, (30, y_text))
            y_text += line_height

        # --- 4. Draw UI Buttons & Status ---
        for el in self.chat_ui_elements:
            el.draw(self.screen, self.font)
            
        if self.is_generating:
            lbl_text = f"{self.current_speaker_name} is typing..." if hasattr(self, 'current_speaker_name') and self.current_speaker_name else "Someone is typing..."
            # Draw this slightly above the bottom border so it doesn't overlap text
            loading = self.font.render(lbl_text, True, (100, 100, 100))
            self.screen.blit(loading, (30, chat_y + chat_h - 25))
