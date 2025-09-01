# commands/magic.py
"""
Contains all commands related to casting spells and managing magical abilities.
"""
import time
from typing import Any, Dict, List, Optional
from commands.command_system import command
from core.config import (
    CAST_COMMAND_PREPOSITION, FORMAT_CATEGORY, FORMAT_ERROR, FORMAT_HIGHLIGHT,
    FORMAT_RESET, FORMAT_SUCCESS, FORMAT_TITLE, TARGET_SELF_ALIASES
)
from magic.spell import Spell
from magic.spell_registry import get_spell, get_spell_by_name
from npcs.npc import NPC

@command("cast", ["c"], "magic", "Cast a known spell.\nUsage: cast <spell_name> [on <target_name>]")
def cast_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You cannot cast spells while dead.{FORMAT_RESET}"

    current_time = time.time()

    if not args:
        # List known spells if no args given, reusing the logic from the spells command
        spells_known_text = player.get_status().split(f"{FORMAT_TITLE}SPELLS KNOWN{FORMAT_RESET}")
        if len(spells_known_text) > 1:
             return f"{FORMAT_TITLE}SPELLS KNOWN{FORMAT_RESET}\n" + spells_known_text[1].strip() + "\n\nUsage: cast <spell_name> [on <target_name>]"
        else:
             return f"{FORMAT_ERROR}You don't know any spells.{FORMAT_RESET}\n\nUsage: cast <spell_name> [on <target_name>]"

    target_name = ""
    spell_name = ""
    if CAST_COMMAND_PREPOSITION in [a.lower() for a in args]:
         try:
              on_index = [a.lower() for a in args].index(CAST_COMMAND_PREPOSITION)
              spell_name = " ".join(args[:on_index]).lower()
              target_name = " ".join(args[on_index + 1:]).lower()
         except ValueError:
              spell_name = " ".join(args).lower()
    else:
        spell_name = " ".join(args).lower()

    spell = get_spell_by_name(spell_name)
    if not spell: return f"{FORMAT_ERROR}You don't know a spell called '{spell_name}'.{FORMAT_RESET}"

    target = None
    if spell.target_type == "self":
        target = player
    elif target_name:
        target = world.find_npc_in_room(target_name)
        if not target and target_name in TARGET_SELF_ALIASES + [player.name.lower()]: target = player
        if not target: return f"{FORMAT_ERROR}You don't see '{target_name}' here to target.{FORMAT_RESET}"
    elif spell.target_type == "enemy":
         if player.in_combat and player.combat_target and player.combat_target.is_alive:
              target = player.combat_target
              if target not in world.get_current_room_npcs(): target = None
         if not target:
              hostiles = [npc for npc in world.get_current_room_npcs() if npc.faction == 'hostile']
              if hostiles: target = hostiles[0]
              else: return f"{FORMAT_ERROR}Who do you want to cast {spell.name} on?{FORMAT_RESET}"
    else: # Default target for friendly/other spells if no name given
        target = player

    if not target: return f"{FORMAT_ERROR}Invalid target for {spell.name}.{FORMAT_RESET}"

    # Validate target type vs spell requirement
    is_enemy = isinstance(target, NPC) and target.faction == "hostile"
    is_friendly_npc = isinstance(target, NPC) and target.faction != "hostile"
    is_self = target == player
    if spell.target_type == "enemy" and not is_enemy: return f"{FORMAT_ERROR}You can only cast {spell.name} on hostile targets.{FORMAT_RESET}"
    if spell.target_type == "friendly" and not (is_friendly_npc or is_self): return f"{FORMAT_ERROR}You can only cast {spell.name} on yourself or friendly targets.{FORMAT_RESET}"

    result = player.cast_spell(spell, target, current_time, world)
    return result["message"]

@command("spells", ["spl", "magic"], "magic", "List spells you know.\nUsage: spells [spell_name]")
def spells_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"

    current_time = time.time()

    if not player.known_spells:
        return f"{FORMAT_ERROR}You don't know any spells.{FORMAT_RESET}"

    if args:
        spell_name = " ".join(args).lower()
        found_spell = None
        for spell_id in player.known_spells:
            spell = get_spell(spell_id)
            if spell and (spell.name.lower() == spell_name or spell_name in spell.name.lower()):
                found_spell = spell; break

        if found_spell:
            spell = found_spell
            cooldown_end = player.spell_cooldowns.get(spell.spell_id, 0)
            cooldown_status = f" [{FORMAT_ERROR}On Cooldown: {max(0, cooldown_end - current_time):.1f}s{FORMAT_RESET}]" if current_time < cooldown_end else ""
            info = f"{FORMAT_TITLE}{spell.name.upper()}{FORMAT_RESET}\n\n"
            info += f"{FORMAT_CATEGORY}Description:{FORMAT_RESET} {spell.description}\n"
            info += f"{FORMAT_CATEGORY}Mana Cost:{FORMAT_RESET} {spell.mana_cost}\n"
            info += f"{FORMAT_CATEGORY}Cooldown:{FORMAT_RESET} {spell.cooldown:.1f}s{cooldown_status}\n"
            info += f"{FORMAT_CATEGORY}Target:{FORMAT_RESET} {spell.target_type.capitalize()}\n"
            info += f"{FORMAT_CATEGORY}Effect:{FORMAT_RESET} {spell.effect_type.capitalize()} ({spell.effect_value} base value)\n"
            if spell.level_required > 1:
                 req_color = FORMAT_SUCCESS if player.level >= spell.level_required else FORMAT_ERROR
                 info += f"{FORMAT_CATEGORY}Level Req:{FORMAT_RESET} {req_color}{spell.level_required}{FORMAT_RESET}\n"
            return info
        else:
            return f"{FORMAT_ERROR}You don't know a spell called '{' '.join(args)}'.{FORMAT_RESET}\nType 'spells' to see all known spells."
    else:
        response = f"{FORMAT_TITLE}KNOWN SPELLS{FORMAT_RESET}\n\n"
        spell_lines = []
        sorted_spells = sorted(list(player.known_spells), key=lambda sid: getattr(get_spell(sid), 'name', sid))
        for spell_id in sorted_spells:
            spell = get_spell(spell_id)
            if spell:
                cooldown_end = player.spell_cooldowns.get(spell_id, 0)
                cooldown_status = f" [{FORMAT_ERROR}CD {max(0, cooldown_end - current_time):.1f}s{FORMAT_RESET}]" if current_time < cooldown_end else ""
                req_color = FORMAT_SUCCESS if player.level >= spell.level_required else FORMAT_ERROR
                level_req_display = f" ({req_color}L{spell.level_required}{FORMAT_RESET})" if spell.level_required > 1 else ""
                spell_lines.append(f"- {FORMAT_HIGHLIGHT}{spell.name}{FORMAT_RESET}{level_req_display}: {spell.mana_cost} MP{cooldown_status}")
            else:
                spell_lines.append(f"- {FORMAT_ERROR}Unknown Spell ID: {spell_id}{FORMAT_RESET}")
        response += "\n".join(spell_lines)
        response += f"\n\n{FORMAT_CATEGORY}Mana:{FORMAT_RESET} {player.mana}/{player.max_mana}\n\nType 'spells <spell_name>' for more details."
        return response