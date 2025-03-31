"""
npcs/npc_factory.py
NPC Factory for the MUD game.
Creates NPCs from templates and manages NPC instances.
"""
from typing import Dict, List, Optional, Any
from npcs.npc import NPC
from items.item_factory import ItemFactory


class NPCFactory:
    """Factory class for creating NPCs from templates."""
    
    # Template library
    _templates = {
        "shopkeeper": {
            "name": "Shopkeeper",
            "description": "A friendly merchant with various goods to sell.",
            "health": 100,
            "friendly": True,
            "behavior_type": "stationary",
            "dialog": {
                "greeting": "Welcome to my shop! What can I help you with?",
                "buy": "I have many items for sale. What would you like to buy?",
                "sell": "I'll give you a fair price for your items.",
                "goods": "I have various goods for sale. Take a look!",
                "price": "All my prices are fair and reasonable.",
                "haggle": "I don't haggle, my prices are already quite fair."
            },
            "default_dialog": "The {name} doesn't seem interested in that topic."
        },
        
        "guard": {
            "name": "Guard",
            "description": "A vigilant guard patrolling the area.",
            "health": 150,
            "friendly": True,
            "behavior_type": "patrol",
            "dialog": {
                "greeting": "Greetings, citizen. All is well, I hope?",
                "trouble": "Report any trouble you see, and I'll handle it.",
                "law": "Keep the peace and we'll get along just fine.",
                "directions": "I know this area well. Where are you trying to go?",
                "threat": "I'm watching you. Don't cause any trouble."
            },
            "default_dialog": "The {name} nods but doesn't respond."
        },
        
        "villager": {
            "name": "Villager",
            "description": "A simple villager going about their business.",
            "health": 80,
            "friendly": True,
            "behavior_type": "wanderer",
            "wander_chance": 0.4,
            "dialog": {
                "greeting": "Hello there! Nice day, isn't it?",
                "weather": "The weather has been quite typical for this time of year.",
                "news": "I haven't heard anything interesting lately.",
                "gossip": "Well, between you and me, there have been some strange happenings...",
                "life": "Life is simple here, but I enjoy it."
            },
            "default_dialog": "The {name} shrugs."
        },
        
        "quest_giver": {
            "name": "Village Elder",
            "description": "An elderly person with an air of wisdom and authority.",
            "health": 70,
            "friendly": True,
            "behavior_type": "scheduled",
            "dialog": {
                "greeting": "Ah, a traveler! Welcome to our humble village.",
                "quest": "We have a problem that needs solving. Are you interested in helping?",
                "reward": "Help us and you'll be well rewarded, I assure you.",
                "history": "This village has stood for generations. Let me tell you about it...",
                "advice": "Listen carefully to what the locals tell you. They know this area well."
            },
            "default_dialog": "The {name} ponders for a moment but doesn't respond to that."
        },
        
        "bartender": {
            "name": "Bartender",
            "description": "A friendly bartender serving drinks and tales.",
            "health": 90,
            "friendly": True,
            "behavior_type": "stationary",
            "dialog": {
                "greeting": "Welcome to my tavern! What'll it be?",
                "drink": "I've got ale, wine, and mead. What's your poison?",
                "rumors": "I hear all sorts of things in this place. Like just yesterday...",
                "news": "News? Well, they say the mountain pass has been having trouble with bandits.",
                "gossip": "I don't like to gossip... but between us..."
            },
            "default_dialog": "The {name} wipes a glass clean but doesn't respond."
        },
        
        "hostile_bandit": {
            "name": "Bandit",
            "description": "A rough-looking character with weapons at the ready.",
            "health": 80,
            "friendly": False,
            "behavior_type": "wanderer",
            "wander_chance": 0.3,
            "dialog": {
                "greeting": "Your money or your life!",
                "threat": "Don't try anything stupid if you want to live.",
                "mercy": "Maybe I'll let you go if you give me something valuable...",
                "fight": "You want a fight? I'll be happy to oblige!",
                "flee": "This isn't worth my time. I'm out of here!"
            },
            "default_dialog": "The {name} snarls threateningly."
        }
    }
    
    @classmethod
    def create_npc(cls, template_name: str, **kwargs) -> Optional[NPC]:
        """
        Create an NPC from a template.
        
        Args:
            template_name: The name of the template to use.
            **kwargs: Additional arguments to override template values.
            
        Returns:
            An NPC instance, or None if the template doesn't exist.
        """
        if template_name not in cls._templates:
            return None
            
        # Start with the template
        template = cls._templates[template_name].copy()
        
        # Override with any provided values
        template.update(kwargs)
        
        # Create the NPC
        npc = NPC(
            obj_id=template.get("obj_id"),
            name=template.get("name", "Unknown NPC"),
            description=template.get("description", "No description"),
            health=template.get("health", 100),
            friendly=template.get("friendly", True)
        )
        
        # Set behavior properties
        npc.behavior_type = template.get("behavior_type", "stationary")
        npc.patrol_points = template.get("patrol_points", [])
        npc.wander_chance = template.get("wander_chance", 0.3)
        npc.schedule = template.get("schedule", {})
        npc.follow_target = template.get("follow_target")
        
        # Set dialog
        npc.dialog = template.get("dialog", {})
        npc.default_dialog = template.get("default_dialog", "The {name} doesn't respond.")
        
        # Add items to inventory if specified
        if "inventory_items" in template:
            for item_data in template["inventory_items"]:
                item = ItemFactory.from_dict(item_data)
                quantity = item_data.get("quantity", 1)
                npc.inventory.add_item(item, quantity)
        
        return npc
    
    @classmethod
    def get_template_names(cls) -> List[str]:
        """
        Get a list of available template names.
        
        Returns:
            A list of template names.
        """
        return list(cls._templates.keys())
    
    @classmethod
    def get_template(cls, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a copy of a template.
        
        Args:
            template_name: The name of the template.
            
        Returns:
            A copy of the template, or None if it doesn't exist.
        """
        if template_name not in cls._templates:
            return None
            
        return cls._templates[template_name].copy()
    
    @classmethod
    def add_template(cls, name: str, template: Dict[str, Any]) -> None:
        """
        Add a new template or update an existing one.
        
        Args:
            name: The name of the template.
            template: The template data.
        """
        cls._templates[name] = template.copy()