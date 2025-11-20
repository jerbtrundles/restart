# ui/panel_content.py
import pygame
from typing import List, Any
from config import *
from utils.text_formatter import ClickableZone, format_target_name
from ui import minimap
from ui.icons import get_item_icon, ICON_SIZE

# Cache fonts
_font_cache = {}
def get_font(size=16, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont(FONT_FAMILY, size, bold=bold)
    return _font_cache[key]

# --- Helper to add a text line with a click command ---
def _draw_clickable_text(surface: pygame.Surface, font, text: str, x: int, y: int, color: tuple, 
                        command: str, hotspots: List[ClickableZone]):
    surf = font.render(text, True, color)
    surface.blit(surf, (x, y))
    if command:
        rect = pygame.Rect(x, y, surf.get_width(), surf.get_height())
        hotspots.append(ClickableZone(rect, command))
    return y + surf.get_height()

# --- Render Functions ---

def render_minimap_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    world = context.get("world")
    if not world: return
    rect = surface.get_rect()
    minimap.draw_minimap(surface, rect, world)

def render_stats_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    player = context.get("player")
    if not player: return
    font = get_font(14)
    y, padding, width = 5, 5, surface.get_width()
    
    # Basic Stats (No interaction needed)
    def draw_stat(txt, col=TEXT_COLOR):
        nonlocal y
        s = font.render(txt, True, col)
        surface.blit(s, (padding, y))
        y += 16

    draw_stat(f"Health: {int(player.health)}/{int(player.max_health)}", DEFAULT_COLORS[FORMAT_SUCCESS])
    draw_stat(f"Mana:   {int(player.mana)}/{int(player.max_mana)}", DEFAULT_COLORS[FORMAT_BLUE])
    draw_stat(f"XP:     {player.experience}/{player.experience_to_level}", DEFAULT_COLORS[FORMAT_ORANGE])
    y += 5
    
    stats = ["strength", "dexterity", "constitution", "agility", "intelligence", "wisdom"]
    col_width = width // 2
    start_y = y
    for i, stat in enumerate(stats):
        val = player.get_effective_stat(stat)
        abbr = stat[:3].upper()
        pos_x = padding + ((i % 2) * col_width)
        pos_y = start_y + ((i // 2) * 16)
        
        s = font.render(f"{abbr}: {val}", True, TEXT_COLOR)
        surface.blit(s, (pos_x, pos_y))
        
    y = start_y + (3 * 16) + 5
    draw_stat(f"Gold: {player.gold}", DEFAULT_COLORS[FORMAT_YELLOW])

def render_skills_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    player = context.get("player")
    if not player: return
    font = get_font(14)
    y, padding = 5, 5
    
    if not player.skills:
        surface.blit(font.render("(No skills)", True, (150, 150, 150)), (padding, y))
        return

    for skill, level in sorted(player.skills.items()):
        surface.blit(font.render(f"{skill.replace('_', ' ').title()}: {level}", True, TEXT_COLOR), (padding, y))
        y += 18

def render_equipment_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    player = context.get("player")
    if not player: return
    font = get_font(14)
    y, padding = 5, 5
    
    for slot in EQUIPMENT_SLOTS:
        item = player.equipment.get(slot)
        slot_name = slot.replace('_', ' ').title()
        
        if item:
            text = f"{slot_name}: {item.name}"
            # Click to look at equipped item
            _draw_clickable_text(surface, font, text, padding, y, TEXT_COLOR, f"look {item.name}", hotspots)
        else:
            text = f"{slot_name}: (Empty)"
            surface.blit(font.render(text, True, (100, 100, 100)), (padding, y))
        y += 18

def render_spells_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    player = context.get("player")
    if not player: return
    font = get_font(14)
    y, padding = 5, 5
    
    if not player.known_spells:
        surface.blit(font.render("(No spells)", True, (150, 150, 150)), (padding, y))
        return

    from magic.spell_registry import get_spell
    import time
    current_time = time.time()

    for spell_id in sorted(player.known_spells):
        spell = get_spell(spell_id)
        if not spell: continue
        
        color = TEXT_COLOR
        cd_end = player.spell_cooldowns.get(spell_id, 0)
        if current_time < cd_end:
            color = (150, 50, 50)
            text = f"{spell.name} ({cd_end - current_time:.1f}s)"
        else:
            text = f"{spell.name} ({spell.mana_cost} MP)"
        
        # Click to prepare/cast hint? Or just look? Let's do cast for QoL
        cmd = f"cast {spell.name}"
        _draw_clickable_text(surface, font, text, padding, y, color, cmd, hotspots)
        y += 18

def render_inventory_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    player = context.get("player")
    game = context.get("game")
    if not player or not game: return
    
    mode = game.inventory_mode # "text", "icon", "hybrid"
    font = get_font(14)
    y, x, padding = 5, 5, 5
    
    # --- Text Mode ---
    if mode == "text":
        for slot in player.inventory.slots:
            if not slot.item: continue
            item = slot.item
            name = f"{item.name} (x{slot.quantity})" if slot.quantity > 1 else item.name
            
            # Click to look
            cmd = f"look {item.name}"
            _draw_clickable_text(surface, font, name, padding, y, TEXT_COLOR, cmd, hotspots)
            y += 18

    # --- Icon Mode ---
    elif mode == "icon":
        col_w = ICON_SIZE + padding
        row_h = ICON_SIZE + padding
        cols = max(1, surface.get_width() // col_w)
        
        current_col = 0
        for slot in player.inventory.slots:
            # Draw slot background
            r = pygame.Rect(x, y, ICON_SIZE, ICON_SIZE)
            pygame.draw.rect(surface, (40, 40, 50), r)
            pygame.draw.rect(surface, (80, 80, 90), r, 1)
            
            if slot.item:
                # Draw Icon
                icon = get_item_icon(slot.item)
                surface.blit(icon, (x, y))
                
                # Quantity Overlay
                if slot.quantity > 1:
                    q_surf = font.render(str(slot.quantity), True, (255, 255, 255))
                    surface.blit(q_surf, (x + ICON_SIZE - q_surf.get_width(), y + ICON_SIZE - q_surf.get_height()))
                
                # Hotspot
                hotspots.append(ClickableZone(r, f"look {slot.item.name}"))
            
            x += col_w
            current_col += 1
            if current_col >= cols:
                current_col = 0
                x = padding
                y += row_h

    # --- Hybrid Mode (Default) ---
    else:
        row_h = ICON_SIZE + 2
        for slot in player.inventory.slots:
            if not slot.item: continue
            item = slot.item
            
            # Background strip for row
            row_rect = pygame.Rect(0, y, surface.get_width(), row_h)
            # (Optional: Alternating colors could go here)

            # Icon
            icon = get_item_icon(item)
            surface.blit(icon, (padding, y))
            
            # Text
            name_str = item.name
            if slot.quantity > 1: name_str += f" (x{slot.quantity})"
            
            # Centered vertically relative to icon
            text_y = y + (ICON_SIZE // 2) - 7 
            
            # Hotspot covers whole row
            hotspots.append(ClickableZone(row_rect, f"look {item.name}"))
            
            surface.blit(font.render(name_str, True, TEXT_COLOR), (padding + ICON_SIZE + 5, text_y))
            y += row_h + 2

def render_hostiles_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    world = context.get("world")
    player = context.get("player")
    if not world: return
    font = get_font(14)
    y, padding = 5, 5
    
    npcs = world.get_current_room_npcs()
    hostiles = [n for n in npcs if n.faction == 'hostile']
    
    if not hostiles:
        surface.blit(font.render("(None)", True, (100, 100, 100)), (padding, y))
        return

    for npc in hostiles:
        txt = f"- {npc.name} ({int(npc.health)}/{npc.max_health})"
        # Click to Attack
        _draw_clickable_text(surface, font, txt, padding, y, (255, 150, 150), f"attack {npc.name}", hotspots)
        y += 16

def render_friendlies_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    world = context.get("world")
    if not world: return
    font = get_font(14)
    y, padding = 5, 5
    
    npcs = world.get_current_room_npcs()
    friendlies = [n for n in npcs if n.faction != 'hostile']
    
    if not friendlies:
        surface.blit(font.render("(None)", True, (100, 100, 100)), (padding, y))
        return

    for npc in friendlies:
        txt = f"- {npc.name}"
        if hasattr(npc, "ai_state") and "current_activity" in npc.ai_state:
            txt += f" ({npc.ai_state['current_activity']})"
        # Click to Look/Talk
        _draw_clickable_text(surface, font, txt, padding, y, (200, 255, 200), f"look {npc.name}", hotspots)
        y += 16

def render_quests_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    player = context.get("player")
    if not player: return
    font = get_font(14)
    y, padding = 5, 5
    
    active = [q for q in player.quest_log.values() if q.get("state") in ["active", "ready_to_complete"]]
    
    if not active:
        surface.blit(font.render("(No active quests)", True, (100, 100, 100)), (padding, y))
        return

    for q in active:
        title = q.get("title", "Quest")
        color = TEXT_COLOR
        if q.get("state") == "ready_to_complete":
            color = (100, 255, 100)
            title = "! " + title
        if len(title) > 28: title = title[:25] + "..."
        
        # Click opens journal
        _draw_clickable_text(surface, font, title, padding, y, color, "journal", hotspots)
        y += 18

def render_effects_content(surface: pygame.Surface, context: dict, hotspots: List[ClickableZone]):
    player = context.get("player")
    if not player: return
    font = get_font(14)
    y, padding = 5, 5

    if not player.active_effects:
        surface.blit(font.render("(No effects)", True, (100, 100, 100)), (padding, y))
        return

    for eff in sorted(player.active_effects, key=lambda e: e.get("name", "z")):
        name = eff.get('name', 'Unknown')
        dur = f"{eff.get('duration_remaining', 0):.0f}s"
        color = (255, 100, 100) if eff.get("type") == "dot" else (100, 255, 100)
        
        surface.blit(font.render(f"{name} ({dur})", True, color), (padding, y))
        y += 18