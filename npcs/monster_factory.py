"""
npcs/monster_factory.py
Factory for creating monster NPCs with predefined templates
"""
from typing import Dict, List, Optional, Any, Tuple
from npcs.npc import NPC
from items.item_factory import ItemFactory

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
    
    @classmethod
    def create_monster(cls, monster_type: str, **kwargs) -> Optional[NPC]:
        if monster_type not in cls._templates: return None
        template = cls._templates[monster_type].copy()
        template.update(kwargs)

        monster = NPC( # Existing creation
             obj_id=template.get("obj_id"),
             name=template.get("name", "Unknown Monster"),
             description=template.get("description", "No description"),
             health=template.get("health", 50),
             friendly=template.get("friendly", False)
        )
        monster.max_health = monster.health # Ensure max_health is set
        
        # Set combat properties
        monster.aggression = template.get("aggression", 0.7)
        monster.attack_power = template.get("attack_power", 5)
        monster.defense = template.get("defense", 2)
        monster.faction = template.get("faction", "hostile")
        monster.behavior_type = template.get("behavior_type", "aggressive")
        monster.respawn_cooldown = template.get("respawn_cooldown", 300)

        monster.usable_spells = template.get("usable_spells", [])
        monster.spell_cast_chance = template.get("spell_cast_chance", 0.3) # Default chance if not specified
        monster.spell_cooldowns = {} # Initialize empty cooldowns

        # Set dialog
        monster.dialog = template.get("dialog", {})
        monster.default_dialog = template.get("default_dialog", "The {name} growls menacingly.")
        
        # Set loot table
        monster.loot_table = template.get("loot_table", {})
        
        # Register spawn point
        if "spawn_region_id" in template and "spawn_room_id" in template:
            monster.spawn_region_id = template["spawn_region_id"]
            monster.spawn_room_id = template["spawn_room_id"]
        
        return monster
    
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