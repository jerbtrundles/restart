# commands/inventory.py
"""
Contains all commands related to the player's inventory and equipment.
"""
from commands.command_system import command
from config import EQUIP_COMMAND_SLOT_PREPOSITION, FORMAT_ERROR, FORMAT_HIGHLIGHT, FORMAT_SUCCESS, FORMAT_TITLE, FORMAT_RESET
from items.item import Item
from items.weapon import Weapon
from items.consumable import Consumable
from items.container import Container
from items.junk import Junk
from items.key import Key
from utils.utils import get_article, simple_plural

@command("inventory", ["i", "inv"], "inventory", "Show items you are carrying.")
def inventory_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"

    inventory_text = f"{FORMAT_TITLE}INVENTORY{FORMAT_RESET}\n\n"
    inventory_text += player.inventory.list_items()
    equipped_text = f"\n{FORMAT_TITLE}EQUIPPED{FORMAT_RESET}\n"
    equipped_items_found = False
    for slot, item in player.equipment.items():
        if item:
            equipped_text += f"- {slot.replace('_', ' ').capitalize()}: {item.name}\n"
            equipped_items_found = True
    if not equipped_items_found:
        equipped_text += "  (Nothing equipped)\n"
    return inventory_text + equipped_text

@command("status", ["stat", "st"], "inventory", "Display character status.")
def status_handler(args, context):
    world = context["world"]
    player = world.player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    return player.get_status()

@command("equip", ["wear", "wield"], "inventory", "Equip an item from your inventory.\nUsage: equip <item_name> [to <slot_name>]")
def equip_handler(args, context):
    player = context["world"].player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot equip items.{FORMAT_RESET}"
    if not args: return f"{FORMAT_ERROR}What do you want to equip?{FORMAT_RESET}"
    item_name = ""; slot_name = None
    if EQUIP_COMMAND_SLOT_PREPOSITION in [a.lower() for a in args]:
        try:
            to_index = [a.lower() for a in args].index(EQUIP_COMMAND_SLOT_PREPOSITION)
            item_name = " ".join(args[:to_index]).lower()
            slot_name = " ".join(args[to_index + 1:]).lower().replace(" ", "_")
        except ValueError: item_name = " ".join(args).lower()
    else: item_name = " ".join(args).lower()
    item_to_equip = player.inventory.find_item_by_name(item_name)
    if not item_to_equip: return f"{FORMAT_ERROR}You don't have '{item_name}' in your inventory.{FORMAT_RESET}"
    success, message = player.equip_item(item_to_equip, slot_name)
    return f"{FORMAT_SUCCESS}{message}{FORMAT_RESET}" if success else f"{FORMAT_ERROR}{message}{FORMAT_RESET}"

@command("unequip", ["remove"], "inventory", "Unequip an item.\nUsage: unequip <slot_name>")
def unequip_handler(args, context):
    player = context["world"].player
    if not player: return f"{FORMAT_ERROR}You must start or load a game first.{FORMAT_RESET}"
    if not player.is_alive: return f"{FORMAT_ERROR}You are dead. You cannot unequip items.{FORMAT_RESET}"
    if not args:
        equipped_text = f"{FORMAT_TITLE}EQUIPPED ITEMS{FORMAT_RESET}\n"
        has_equipped = False
        for slot, item in player.equipment.items():
            if item:
                equipped_text += f"- {slot.replace('_', ' ').capitalize()}: {item.name}\n"
                has_equipped = True
        if not has_equipped: equipped_text += "  (Nothing equipped)\n"
        equipped_text += "\nUsage: unequip <slot_name>"
        return equipped_text
    slot_name = " ".join(args).lower().replace(" ", "_")
    if slot_name not in player.equipment:
        valid_slots = ", ".join(player.equipment.keys())
        return f"{FORMAT_ERROR}Invalid slot '{slot_name}'. Valid slots: {valid_slots}{FORMAT_RESET}"
    success, message = player.unequip_item(slot_name)
    return f"{FORMAT_SUCCESS}{message}{FORMAT_RESET}" if success else f"{FORMAT_ERROR}{message}{FORMAT_RESET}"