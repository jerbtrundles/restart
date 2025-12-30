# engine/magic/spell_registry.py
"""
Registry of all available spells in the game, loaded from data files.
"""
import json
import os
from typing import Dict, Optional
from engine.config import DATA_DIR, FORMAT_ERROR, FORMAT_RESET
from engine.magic.spell import Spell

# The registry is now populated at runtime by the loader.
SPELL_REGISTRY: Dict[str, Spell] = {}

def load_spells_from_json():
    """
    Scans the data/magic directory for all .json files, loads them,
    creates Spell objects, and populates the SPELL_REGISTRY.
    """
    magic_dir = os.path.join(DATA_DIR, "magic")
    if not os.path.isdir(magic_dir):
        print(f"{FORMAT_ERROR}Error: Magic data directory not found at '{magic_dir}'.{FORMAT_RESET}")
        return

    for filename in os.listdir(magic_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(magic_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    for spell_id, spell_data in data.items():
                        spell_object = Spell.from_dict(spell_id, spell_data)
                        register_spell(spell_object)
            except json.JSONDecodeError:
                print(f"{FORMAT_ERROR}Error: Could not decode JSON from '{file_path}'. Check for syntax errors.{FORMAT_RESET}")
            except Exception as e:
                print(f"{FORMAT_ERROR}An unexpected error occurred while loading spells from '{filename}': {e}{FORMAT_RESET}")

def register_spell(spell: Spell):
    """Adds a spell to the registry."""
    if spell.spell_id in SPELL_REGISTRY:
        print(f"Warning: Overwriting spell with ID {spell.spell_id}")
    SPELL_REGISTRY[spell.spell_id] = spell

def get_spell(spell_id: str) -> Optional[Spell]:
    """Retrieves a spell definition from the registry."""
    return SPELL_REGISTRY.get(spell_id)

def get_spell_by_name(spell_name: str) -> Optional[Spell]:
    """Finds a spell by its name (case-insensitive)."""
    search_name = spell_name.lower()
    for spell in SPELL_REGISTRY.values():
        if spell.name.lower() == search_name:
            return spell
    return None
