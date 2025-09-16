# ui/panels.py
"""
Contains functions for rendering specific UI panels like status, room info, etc.
"""
import time
import pygame
from typing import TYPE_CHECKING, Optional, Any
import math

from config import *
from items.item import Item
from magic.spell_registry import get_spell
from utils.text_formatter import format_target_name

if TYPE_CHECKING:
    from player import Player
    from world.world import World
    from ui.renderer import Renderer


def draw_time_bar(renderer: 'Renderer', time_data: dict):
    time_str = time_data.get("time_str", "??:??")
    date_str = time_data.get("date_str", "Unknown Date")
    time_period = time_data.get("time_period", "unknown")
    pygame.draw.rect(renderer.screen, (40, 40, 60), (0, 0, renderer.layout["screen_width"], renderer.layout["time_bar"]["height"]))
    time_color = {"dawn": (255, 165, 0), "day": (255, 255, 150), "dusk": (255, 100, 100), "night": (100, 100, 255)}.get(time_period, TEXT_COLOR)
    time_surface = renderer.font.render(time_str, True, time_color)
    renderer.screen.blit(time_surface, (10, 5))
    date_surface = renderer.font.render(date_str, True, TEXT_COLOR)
    date_x = (renderer.layout["screen_width"] - date_surface.get_width()) // 2
    renderer.screen.blit(date_surface, (date_x, 5))
    period_surface = renderer.font.render(time_period.capitalize(), True, time_color)
    period_x = renderer.layout["screen_width"] - period_surface.get_width() - 10
    renderer.screen.blit(period_surface, (period_x, 5))
    pygame.draw.line(renderer.screen, (80, 80, 100), (0, renderer.layout["time_bar"]["height"]), (renderer.layout["screen_width"], renderer.layout["time_bar"]["height"]), 1)

def draw_left_status_panel(renderer: 'Renderer', player: 'Player'):
    panel_layout = renderer.layout.get("left_status_panel")
    if not panel_layout: return
    panel_rect = pygame.Rect(panel_layout["x"], panel_layout["y"], panel_layout["width"], panel_layout["height"])
    pygame.draw.rect(renderer.screen, (20, 20, 20), panel_rect)
    pygame.draw.rect(renderer.screen, (80, 80, 80), panel_rect, 1)

    padding = STATUS_PANEL_PADDING
    line_height = renderer.text_formatter.line_height_with_text
    current_y = panel_rect.y + padding
    max_y = panel_rect.bottom - padding

    # --- 1. PLAYER INFO ---
    current_y = renderer.text_formatter.render(renderer.screen, f"{FORMAT_TITLE}{player.name}{FORMAT_RESET}", (panel_rect.x + padding, current_y), max_height=(max_y - current_y))
    if current_y < max_y: renderer.screen.blit(renderer.font.render(f"Level: {player.level}", True, TEXT_COLOR), (panel_rect.x + padding, current_y)); current_y += line_height
    if current_y < max_y: current_y = renderer.text_formatter.render(renderer.screen, f"Gold: {FORMAT_YELLOW}{player.gold}{FORMAT_RESET}", (panel_rect.x + padding, current_y), max_height=(max_y - current_y))
    current_y += line_height // 2

    # --- 2. HP/MP/XP BARS ---
    bar_height = 10; bar_x = panel_rect.x + padding
    bar_label_width = renderer.font.size("HP: 9999/9999")[0] + 5 # Add padding
    max_bar_width = max(20, panel_layout["width"] - (padding * 2) - bar_label_width)
    
    # HP Bar
    if current_y + bar_height <= max_y:
        hp_text = f"HP: {int(player.health)}/{int(player.max_health)}"; hp_percent = player.health / player.max_health if player.max_health > 0 else 0
        hp_color = DEFAULT_COLORS[FORMAT_SUCCESS]
        if hp_percent <= PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD / 100: hp_color = DEFAULT_COLORS[FORMAT_ERROR]
        elif hp_percent <= PLAYER_STATUS_HEALTH_LOW_THRESHOLD / 100: hp_color = DEFAULT_COLORS[FORMAT_YELLOW]
        pygame.draw.rect(renderer.screen, (80, 0, 0), (bar_x, current_y, max_bar_width, bar_height))
        pygame.draw.rect(renderer.screen, hp_color, (bar_x, current_y, int(max_bar_width * hp_percent), bar_height))
        hp_surface = renderer.font.render(hp_text, True, hp_color)
        renderer.screen.blit(hp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (hp_surface.get_height() // 2))); current_y += bar_height + 3
    
    # MP Bar
    if current_y + bar_height <= max_y:
        mp_text = f"MP: {int(player.mana)}/{int(player.max_mana)}"; mp_percent = player.mana / player.max_mana if player.max_mana > 0 else 0
        mp_color = DEFAULT_COLORS[FORMAT_CYAN]
        pygame.draw.rect(renderer.screen, (0, 0, 80), (bar_x, current_y, max_bar_width, bar_height))
        pygame.draw.rect(renderer.screen, mp_color, (bar_x, current_y, int(max_bar_width * mp_percent), bar_height))
        mp_surface = renderer.font.render(mp_text, True, mp_color)
        renderer.screen.blit(mp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (mp_surface.get_height() // 2))); current_y += bar_height + 3

    # XP Bar
    if current_y + bar_height <= max_y:
        xp_text = f"XP: {int(player.experience)}/{int(player.experience_to_level)}"; xp_percent = player.experience / player.experience_to_level if player.experience_to_level > 0 else 0
        xp_color = DEFAULT_COLORS[FORMAT_ORANGE]
        pygame.draw.rect(renderer.screen, (80, 50, 0), (bar_x, current_y, max_bar_width, bar_height))
        pygame.draw.rect(renderer.screen, xp_color, (bar_x, current_y, int(max_bar_width * xp_percent), bar_height))
        xp_surface = renderer.font.render(xp_text, True, xp_color)
        renderer.screen.blit(xp_surface, (bar_x + max_bar_width + padding, current_y + (bar_height // 2) - (xp_surface.get_height() // 2))); current_y += bar_height + padding
    
    # --- 3. STATS ---
    text_color = DEFAULT_COLORS.get(FORMAT_RESET, TEXT_COLOR)
    title_color = DEFAULT_COLORS.get(FORMAT_TITLE, (255, 255, 0))
    gray_color = DEFAULT_COLORS.get(FORMAT_GRAY, (128, 128, 128))
    error_color = DEFAULT_COLORS.get(FORMAT_ERROR, (255,0,0))
    if current_y + line_height <= max_y: renderer.screen.blit(renderer.font.render("STATS", True, title_color), (panel_rect.x + padding, current_y)); current_y += line_height
    stats_to_show = {"strength": "STR", "dexterity": "DEX", "constitution": "CON", "agility": "AGI", "intelligence": "INT", "wisdom": "WIS", "spell_power": "SP", "magic_resist": "MR"}
    stats_per_col = math.ceil(len(stats_to_show) / 2)
    col1_x = panel_rect.x + padding + 5; col2_x = col1_x + (panel_rect.width - padding*2 - 20) // 2
    col1_y, col2_y = current_y, current_y
    for i, (stat_key, stat_abbr) in enumerate(stats_to_show.items()):
        if max(col1_y, col2_y) >= max_y: break
        stat_text = f"{stat_abbr}: {player.stats.get(stat_key, 0)}"; stat_surface = renderer.font.render(stat_text, True, text_color)
        if i < stats_per_col:
            if col1_y + line_height <= max_y: renderer.screen.blit(stat_surface, (col1_x, col1_y)); col1_y += line_height
        else:
            if col2_y + line_height <= max_y: renderer.screen.blit(stat_surface, (col2_x, col2_y)); col2_y += line_height
    current_y = max(col1_y, col2_y) + line_height // 2

    # --- 4. EQUIPMENT ---
    if current_y + line_height <= max_y: renderer.screen.blit(renderer.font.render("EQUIPPED", True, title_color), (panel_rect.x + padding, current_y)); current_y += line_height
    def format_equip_slot(slot_abbr: str, item: Optional[Item]) -> str:
        if not item: return f"{slot_abbr}: {FORMAT_GRAY}(Empty){FORMAT_RESET}"
        durability_str = ""
        max_durability = item.get_property("max_durability", 0); current_durability = item.get_property("durability", max_durability)
        if max_durability > 0:
            ratio = current_durability / max_durability if max_durability else 0; dura_color = FORMAT_SUCCESS
            if ratio <= 0.1: dura_color = FORMAT_ERROR
            elif ratio <= 0.3: dura_color = FORMAT_YELLOW
            durability_str = f" [{dura_color}{int(current_durability)}/{int(max_durability)}{FORMAT_RESET}]"
        return f"{slot_abbr}: {item.name}{durability_str}"
    slot_abbrs = {"main_hand": "MH", "off_hand": "OH", "head": "Hd", "body": "Bd", "hands": "Hn", "feet": "Ft", "neck": "Nk"}
    for slot_key in EQUIPMENT_SLOTS:
        if current_y >= max_y: break
        current_y = renderer.text_formatter.render(renderer.screen, f"- {format_equip_slot(slot_abbrs[slot_key], player.equipment.get(slot_key))}", (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y))
    current_y += line_height // 2

    # --- 5. SPELLS ---
    if current_y + line_height <= max_y: renderer.screen.blit(renderer.font.render("SPELLS", True, title_color), (panel_rect.x + padding, current_y)); current_y += line_height
    if player.known_spells:
        current_time = time.time()
        for spell_id in sorted(list(player.known_spells), key=lambda sid: getattr(get_spell(sid), 'name', sid)):
            if current_y + line_height > max_y: break
            spell = get_spell(spell_id)
            if spell:
                cooldown_end = player.spell_cooldowns.get(spell_id, 0)
                cd_status = f" (CD {max(0, cooldown_end - current_time):.1f}s)" if current_time < cooldown_end else ""
                spell_text = f"- {spell.name} ({spell.mana_cost} MP)"
                renderer.screen.blit(renderer.font.render(spell_text, True, text_color), (panel_rect.x + padding + 5, current_y))
                if cd_status:
                     renderer.screen.blit(renderer.font.render(cd_status, True, error_color), (panel_rect.x + padding + 5 + renderer.font.size(spell_text)[0], current_y))
                current_y += line_height
    else:
        if current_y + line_height <= max_y: renderer.screen.blit(renderer.font.render("(None known)", True, gray_color), (panel_rect.x + padding + 5, current_y)); current_y += line_height
    current_y += line_height // 2

    # --- 6. SKILLS ---
    if current_y + line_height <= max_y: renderer.screen.blit(renderer.font.render("SKILLS", True, title_color), (panel_rect.x + padding, current_y)); current_y += line_height
    if player.skills:
        for skill_name, level in sorted(player.skills.items()):
            if current_y + line_height > max_y: break
            renderer.screen.blit(renderer.font.render(f"- {skill_name.capitalize()}: {level}", True, text_color), (panel_rect.x + padding + 5, current_y)); current_y += line_height
    else:
        if current_y + line_height <= max_y: renderer.screen.blit(renderer.font.render("(None known)", True, gray_color), (panel_rect.x + padding + 5, current_y)); current_y += line_height
    current_y += line_height // 2
    
    # --- 7. ACTIVE EFFECTS ---
    if current_y + line_height <= max_y: renderer.screen.blit(renderer.font.render("EFFECTS", True, title_color), (panel_rect.x + padding, current_y)); current_y += line_height
    if player.active_effects:
        for effect in sorted(player.active_effects, key=lambda e: e.get("name", "zzz")):
            if current_y >= max_y: break
            name = effect.get('name', 'Unknown Effect'); duration = effect.get('duration_remaining', 0)
            duration_str = f"{duration / 60:.1f}m" if duration > 60 else f"{duration:.1f}s"
            details = ""
            if effect.get("type") == "dot":
                 details = f" ({FORMAT_ERROR}{effect.get('damage_per_tick', 0)}/tick{FORMAT_RESET})"
            elif effect.get("type") == "hot":
                 details = f" ({FORMAT_SUCCESS}+{effect.get('heal_per_tick', 0)}/tick{FORMAT_RESET})"
            current_y = renderer.text_formatter.render(renderer.screen, f"- {name}{details} ({duration_str})", (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y))
    else:
        if current_y + line_height <= max_y:
            renderer.screen.blit(renderer.font.render("- (None)", True, gray_color), (panel_rect.x + padding + 5, current_y)); current_y += line_height

def draw_right_status_panel(renderer: 'Renderer', player: 'Player', world: 'World'):
    panel_layout = renderer.layout.get("right_status_panel")
    if not panel_layout: return
    panel_rect = pygame.Rect(panel_layout["x"], panel_layout["y"], panel_layout["width"], panel_layout["height"])
    pygame.draw.rect(renderer.screen, (20, 20, 20), panel_rect)
    pygame.draw.rect(renderer.screen, (80, 80, 80), panel_rect, 1)
    
    padding = STATUS_PANEL_PADDING
    line_height = renderer.text_formatter.line_height_with_text
    current_y = panel_rect.y + padding
    max_y = panel_rect.bottom - padding
    title_color = DEFAULT_COLORS.get(FORMAT_TITLE, (255, 255, 0))
    gray_color = DEFAULT_COLORS.get(FORMAT_GRAY, (128, 128, 128))

    all_npcs_in_room = world.get_current_room_npcs()

    # --- PEOPLE (Friendlies/Neutrals) ---
    if current_y + line_height <= max_y:
        renderer.screen.blit(renderer.font.render("PEOPLE", True, title_color), (panel_rect.x + padding, current_y))
        current_y += line_height
    
    friendly_targets = [npc for npc in all_npcs_in_room if npc.is_alive and npc.faction in ["friendly", "neutral"]]
    if friendly_targets:
        for target in friendly_targets:
            if current_y >= max_y: break
            formatted_target_name = format_target_name(player, target) # This will just show the name with level-based color
            current_y = renderer.text_formatter.render(renderer.screen, f"- {formatted_target_name}", (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y))
    else:
        if current_y + line_height <= max_y:
            renderer.screen.blit(renderer.font.render("- (None)", True, gray_color), (panel_rect.x + padding + 5, current_y))
            current_y += line_height
    current_y += line_height // 2

    # --- HOSTILES ---
    if current_y + line_height <= max_y:
        renderer.screen.blit(renderer.font.render("HOSTILES", True, title_color), (panel_rect.x + padding, current_y))
        current_y += line_height
    
    hostile_targets = [npc for npc in all_npcs_in_room if npc.is_alive and npc.faction == "hostile"]
    if hostile_targets:
        for target in hostile_targets:
             if current_y >= max_y: break
             formatted_target_name = format_target_name(player, target)
             current_y = renderer.text_formatter.render(renderer.screen, f"- {formatted_target_name}", (panel_rect.x + padding + 5, current_y), max_height=(max_y - current_y))
    else:
        if current_y + line_height <= max_y:
            renderer.screen.blit(renderer.font.render("- (None)", True, gray_color), (panel_rect.x + padding + 5, current_y))
            current_y += line_height

def draw_room_info_panel(renderer: 'Renderer', world: 'World'):
    panel_layout = renderer.layout.get("room_info_panel");
    if not panel_layout: return
    panel_rect = pygame.Rect(panel_layout["x"], panel_layout["y"], panel_layout["width"], panel_layout["height"])
    pygame.draw.rect(renderer.screen, (15, 15, 15), panel_rect); pygame.draw.rect(renderer.screen, (70, 70, 70), panel_rect, 1)
    padding = 5; current_y = panel_rect.y + padding; max_y = panel_rect.bottom - padding
    
    room_description_text = world.get_room_description_for_display()
    
    original_formatter_width = renderer.text_formatter.usable_width; panel_usable_width = max(1, panel_rect.width - padding * 2)
    
    renderer.text_formatter.update_screen_width(panel_usable_width)
    renderer.text_formatter.render(renderer.screen, room_description_text, (panel_rect.x + padding, current_y), max_height=max_y - current_y)
    renderer.text_formatter.update_screen_width(original_formatter_width)