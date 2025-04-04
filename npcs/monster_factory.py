"""
npcs/monster_factory.py
Factory for creating monster NPCs with predefined templates
"""
from typing import TYPE_CHECKING, Dict, List, Optional, Any, Tuple
import random # Needed for random level/spawn
from npcs.npc import NPC
from npcs.npc_factory import NPCFactory # Use the main factory now

if TYPE_CHECKING:
    from world.world import World

class MonsterFactory:
    """Factory for creating monster NPCs from templates"""
    
    # Monster templates library
    _templates = {
        "goblin": {
            "name": "Goblin",
            "description": "A small, green-skinned creature with sharp teeth and claws.",
            "health": 30,
            "friendly": False,
            "behavior_type": "aggressive",
            "aggression": 0.7,
            "attack_power": 5,
            "defense": 2,
            "faction": "hostile",
            "usable_spells": ["zap"], # Goblins can zap!
            "spell_cast_chance": 0.2, # Lower chance for goblins
            "respawn_cooldown": 300,  # 5 minutes
            "loot_table": {
                # Item Name: { chance: float, type: str, [value: int], [weight: float], [description: str] }
                "Gold Coin": {"chance": 0.8, "type": "Treasure", "value": 1}, # Keep specific types if needed
                "Rusty Dagger": {"chance": 0.3, "type": "Weapon", "value": 2, "damage": 2}, # Can override props
                "Goblin Ear": {"chance": 0.9, "type": "Junk", "value": 1, "weight": 0.1} # *** Type is Junk ***
            },
            "dialog": {
                "greeting": "The {name} snarls at you!",
                "threat": "The {name} raises its rusty dagger!",
                "flee": "The {name} tries to escape!"
            }
        },
        
        "wolf": {
            "name": "Wolf",
            "description": "A fierce wolf with sharp fangs and a hungry look.",
            "health": 25,
            "friendly": False,
            "behavior_type": "aggressive",
            "aggression": 0.6,
            "attack_power": 6,
            "defense": 1,
            "faction": "hostile",
            "respawn_cooldown": 360,  # 6 minutes
            "loot_table": {
                "Wolf Pelt": {"chance": 0.9, "type": "Junk", "value": 3, "weight": 0.5}, # *** Type is Junk ***
                "Wolf Fang": {"chance": 0.7, "type": "Junk", "value": 2, "weight": 0.1}, # *** Type is Junk ***
                "Raw Meat": {"chance": 0.5, "type": "Consumable", "value": 1, "weight": 0.4, "effect_type": "heal", "effect_value": 4} # Raw meat is consumable
            },
            "dialog": {
                "greeting": "The {name} growls menacingly!",
                "threat": "The {name} bares its fangs!",
                "flee": "The {name} whimpers and tries to escape!"
            }
        },
        
        "skeleton": {
            "name": "Skeleton",
            "description": "A walking skeleton animated by dark magic.",
            "health": 40,
            "friendly": False,
            "behavior_type": "aggressive",
            "aggression": 0.8,
            "attack_power": 7,
            "defense": 3,
            "faction": "hostile",
            "usable_spells": ["zap"], # Skeletons might retain some magic
            "spell_cast_chance": 0.25,
            "respawn_cooldown": 420,  # 7 minutes
             "loot_table": {
                  "Bone": {"chance": 0.9, "type": "Junk", "value": 1, "weight": 0.3},
                  "Rusty Sword": {"chance": 0.4, "type": "Weapon", "value": 5, "damage": 4},
                  "Ancient Coin": {"chance": 0.2, "type": "Treasure", "value": 5}
             },
            "dialog": {
                "greeting": "The {name} rattles its bones!",
                "threat": "The {name} raises its weapon!",
                "flee": "The {name} retreats!"
            }
        },
        
        "giant_rat": {
            "name": "Giant Rat",
            "description": "An oversized rodent with mangy fur and sharp teeth.",
            "health": 15,
            "friendly": False,
            "behavior_type": "aggressive",
            "aggression": 0.5,
            "attack_power": 3,
            "defense": 1,
            "faction": "hostile",
            "respawn_cooldown": 240,  # 4 minutes
             "loot_table": {
                  "Rat Tail": {"chance": 0.8, "type": "Junk", "value": 1, "weight": 0.1},
                  "Rat Fur": {"chance": 0.6, "type": "Junk", "value": 1, "weight": 0.2}
             },
            "dialog": {
                "greeting": "The {name} squeaks aggressively!",
                "threat": "The {name} bares its teeth!",
                "flee": "The {name} scurries away!"
            }
        },
        "bandit": {
            "name": "Bandit",
            "description": "A rough-looking human armed with weapons.",
            "health": 45,
            "friendly": False,
            "behavior_type": "aggressive",
            "aggression": 0.6,
            "attack_power": 8,
            "defense": 4,
            "faction": "hostile",
            "respawn_cooldown": 600,  # 10 minutes
             "loot_table": {
                  "Gold Coin": {"chance": 0.9, "type": "Treasure", "value": 1},
                  "Dagger": {"chance": 0.5, "type": "Weapon", "value": 5, "damage": 3},
                  "Leather Armor": {"chance": 0.3, "type": "Armor", "value": 20, "defense": 2, "equip_slot": ["body"]}, # Example if you add Armor type
                  "Stolen Pouch": {"chance": 0.2, "type": "Junk", "value": 4, "weight": 0.1} # Could be junk
             },
            "dialog": {
                "greeting": "\"Your money or your life!\" threatens the {name}.",
                "threat": "\"You'll regret this!\" shouts the {name}.",
                "flee": "\"This isn't worth dying for!\" cries the {name}."
            }
        },
        
        "troll": {
            "name": "Troll",
            "description": "A massive, green-skinned brute with regenerative abilities.",
            "health": 80,
            "friendly": False,
            "behavior_type": "aggressive",
            "aggression": 0.7,
            "attack_power": 12,
            "defense": 6,
            "faction": "hostile",
            "respawn_cooldown": 900,  # 15 minutes
             "loot_table": {
                  "Troll Hide": {"chance": 0.9, "type": "Junk", "value": 10, "weight": 2.0},
                  "Crude Club": {"chance": 0.5, "type": "Weapon", "value": 8, "damage": 7},
                  "Shiny Rock": {"chance": 0.7, "type": "Junk", "value": 3, "weight": 0.5},
                  # Trolls might drop potions they stole?
             },
            "dialog": {
                "greeting": "The {name} roars loudly!",
                "threat": "The {name} pounds its chest!",
                "flee": "The {name} retreats, looking for easier prey!"
            }
        }
    }
    
    @staticmethod
    def create_monster(monster_template_id: str, world: 'World', **kwargs) -> Optional[NPC]:
        """Creates a monster instance using the main NPCFactory."""
        # Just delegate to the main NPCFactory
        # Ensure 'faction' is correctly set if not in template/overrides
        if 'faction' not in kwargs and monster_template_id in world.npc_templates:
             if 'faction' not in world.npc_templates[monster_template_id]:
                  kwargs['faction'] = 'hostile' # Default monsters to hostile
        elif 'faction' not in kwargs:
             kwargs['faction'] = 'hostile'

        return NPCFactory.create_npc_from_template(monster_template_id, world, **kwargs)
    
    @classmethod
    def get_template_names(cls) -> List[str]:
        """
        Get a list of available monster template names.
        
        Returns:
            A list of template names.
        """
        return list(cls._templates.keys())
    
    @classmethod
    def get_template(cls, monster_type: str) -> Optional[Dict[str, Any]]:
        """
        Get a copy of a monster template.
        
        Args:
            monster_type: The type of monster template.
            
        Returns:
            A copy of the template, or None if it doesn't exist.
        """
        if monster_type not in cls._templates:
            return None
            
        return cls._templates[monster_type].copy()
    
    @classmethod
    def add_template(cls, monster_type: str, template: Dict[str, Any]) -> None:
        """
        Add a new monster template or update an existing one.
        
        Args:
            monster_type: The type of monster template.
            template: The template data.
        """
        cls._templates[monster_type] = template.copy()
    
    @classmethod
    def spawn_random_monster(cls, region_id: str, room_id: str, level_range: Tuple[int, int] = (1, 5)) -> Optional[NPC]:
        """
        Spawn a random monster appropriate for the given level range
        
        Args:
            region_id: The region to spawn in
            room_id: The room to spawn in
            level_range: Tuple of (min_level, max_level)
            
        Returns:
            A randomly chosen and configured monster NPC
        """
        import random
        
        # Get available monster types
        monster_types = cls.get_template_names()
        if not monster_types:
            return None
            
        # Choose a random monster type
        monster_type = random.choice(monster_types)
        
        # Choose a level within the given range
        level = random.randint(level_range[0], level_range[1])
        
        # Create the monster
        monster = cls.create_monster(monster_type)
        if not monster:
            return None
            
        # Scale stats based on level
        base_health = monster.health
        base_attack = monster.attack_power
        base_defense = monster.defense
        
        # Simple scaling formula
        monster.health = int(base_health * (1 + (level - 1) * 0.5))
        monster.max_health = monster.health
        monster.attack_power = int(base_attack * (1 + (level - 1) * 0.3))
        monster.defense = int(base_defense * (1 + (level - 1) * 0.2))
        
        # Add level to name if > 1
        if level > 1:
            monster.name = f"{monster.name} (Level {level})"
        
        # Set spawn location
        monster.current_region_id = region_id
        monster.current_room_id = room_id
        monster.spawn_region_id = region_id
        monster.spawn_room_id = room_id
        
        return monster

    @staticmethod
    def get_monster_template_names(world: 'World') -> List[str]:
        """Get names of templates likely representing monsters."""
        if not world or not hasattr(world, 'npc_templates'):
            return []
        # Filter based on faction or naming convention?
        monster_names = []
        for tid, template in world.npc_templates.items():
             # Assume templates with faction 'hostile' are monsters
             if template.get('faction') == 'hostile':
                  monster_names.append(tid)
             # Add other heuristics if needed (e.g., if tid starts with 'monster_')
        return monster_names

    @staticmethod
    def spawn_random_monster(region_id: str, room_id: str, world: 'World', level_range: Tuple[int, int] = (1, 5)) -> Optional[NPC]:
        """Spawns a random monster appropriate for the level range."""

        monster_types = MonsterFactory.get_monster_template_names(world)
        if not monster_types:
            print("Warning: No monster templates found for random spawn.")
            return None

        monster_type = random.choice(monster_types)
        level = random.randint(level_range[0], level_range[1])

        # Prepare overrides for NPCFactory
        overrides = {
            "level": level,
            "current_region_id": region_id,
            "current_room_id": room_id,
            "home_region_id": region_id, # Spawn point is home
            "home_room_id": room_id
        }

        # Create using the main factory
        monster = NPCFactory.create_npc_from_template(monster_type, world, **overrides)

        if not monster:
             print(f"Warning: Failed to spawn random monster of type '{monster_type}'.")
             return None

        # Optional: Scale stats further based on the *final* level if needed
        # (NPCFactory already handles basic level setting)
        # If more complex scaling is desired, do it here after creation.
        # E.g., monster.health = monster.template_base_health * (1 + (level - 1) * 0.5)
        # This would require storing base stats in the template distinctly.
        # For now, the simple scaling in NPCFactory might suffice.

        # Add level to name if desired (NPCFactory doesn't do this automatically)
        if level > 1:
             monster.name = f"{monster.name} (Level {level})"

        return monster
