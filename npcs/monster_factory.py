"""
monster_factory.py
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
            "respawn_cooldown": 300,  # 5 minutes
            "loot_table": {
                "Gold Coin": 0.8,
                "Dagger": 0.3,
                "Goblin Ear": 0.9
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
                "Wolf Pelt": 0.9,
                "Wolf Fang": 0.7,
                "Raw Meat": 0.5
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
            "respawn_cooldown": 420,  # 7 minutes
            "loot_table": {
                "Bone": 0.9,
                "Rusty Sword": 0.4,
                "Ancient Coin": 0.2
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
                "Rat Tail": 0.8,
                "Rat Fur": 0.6
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
                "Gold Coin": 0.9,
                "Dagger": 0.5,
                "Leather Armor": 0.3,
                "Healing Potion": 0.2
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
                "Troll Hide": 0.9,
                "Club": 0.5,
                "Gold Coin": 0.7,
                "Healing Potion": 0.4
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
        """
        Create a monster from a template.
        
        Args:
            monster_type: The type of monster to create
            **kwargs: Overrides for template values
            
        Returns:
            An NPC instance configured as a monster, or None if template doesn't exist
        """
        if monster_type not in cls._templates:
            return None
            
        # Start with the template
        template = cls._templates[monster_type].copy()
        
        # Override with any provided values
        template.update(kwargs)
        
        # Create NPC with monster configuration
        monster = NPC(
            obj_id=template.get("obj_id"),
            name=template.get("name", "Unknown Monster"),
            description=template.get("description", "No description"),
            health=template.get("health", 50),
            friendly=template.get("friendly", False)
        )
        
        # Set combat properties
        monster.aggression = template.get("aggression", 0.7)
        monster.attack_power = template.get("attack_power", 5)
        monster.defense = template.get("defense", 2)
        monster.faction = template.get("faction", "hostile")
        monster.behavior_type = template.get("behavior_type", "aggressive")
        monster.respawn_cooldown = template.get("respawn_cooldown", 300)
        
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