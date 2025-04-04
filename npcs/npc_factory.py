"""
npcs/npc_factory.py
NPC Factory for the MUD game.
Creates NPCs from templates and manages NPC instances.
"""
import inspect # To inspect constructor arguments
import time
import uuid   # To generate unique instance IDs
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from core.config import FORMAT_ERROR, FORMAT_RESET
from items.item_factory import ItemFactory
from npcs.npc import NPC

if TYPE_CHECKING:
    from world.world import World

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
            "properties": { "is_vendor": True }, # <<< ADD is_vendor property
            "dialog": {
                "greeting": "Welcome to my shop! What can I help you with?",
                "trade": "Looking to buy or sell?", # <<< ADD specific trade dialog key
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
            "properties": { "is_vendor": True }, # <<< ADD is_vendor property
            "dialog": {
                "greeting": "Welcome to my tavern! What'll it be?",
                "trade": "Need a drink, or perhaps selling something?", # <<< ADD specific trade dialog key
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

        template_properties = template.get("properties", {})
        for key, value in template_properties.items():
            npc.update_property(key, value) # Use the update_property method
        
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
    
    # Keep static methods for template management if desired, but they'd need world context now
    @staticmethod
    def get_template_names(world: 'World') -> List[str]:
        """Get a list of available NPC template names."""
        if world and hasattr(world, 'npc_templates'):
             return list(world.npc_templates.keys())
        return []

    @staticmethod
    def get_template(template_id: str, world: 'World') -> Optional[Dict[str, Any]]:
         """Get a copy of an NPC template."""
         if world and hasattr(world, 'npc_templates'):
              template = world.npc_templates.get(template_id)
              return template.copy() if template else None
         return None
    
    @classmethod
    def add_template(cls, name: str, template: Dict[str, Any]) -> None:
        """
        Add a new template or update an existing one.
        
        Args:
            name: The name of the template.
            template: The template data.
        """
        cls._templates[name] = template.copy()

    @staticmethod
    def create_npc_from_template(template_id: str, world: 'World', instance_id: Optional[str] = None, **overrides) -> Optional[NPC]:
        """Creates an NPC instance from a template ID and applies overrides."""
        if not world or not hasattr(world, 'npc_templates'):
            print(f"{FORMAT_ERROR}Error: World context with npc_templates required.{FORMAT_RESET}")
            return None

        template = world.npc_templates.get(template_id)
        if not template:
            print(f"{FORMAT_ERROR}Error: NPC template '{template_id}' not found.{FORMAT_RESET}")
            return None

        try:
            # 1. Prepare arguments from template
            creation_args = template.copy()
            # Generate instance ID if not provided
            npc_instance_id = instance_id if instance_id else f"{template_id}_{uuid.uuid4().hex[:8]}"
            creation_args["obj_id"] = npc_instance_id # Use instance ID for the object
            creation_args["template_id"] = template_id # Store template ref if needed later

            # Separate complex structures
            template_properties = creation_args.pop("properties", {})
            template_dialog = creation_args.pop("dialog", {})
            template_loot = creation_args.pop("loot_table", {})
            template_schedule = creation_args.pop("schedule", {})
            template_inventory = creation_args.pop("initial_inventory", [])
            template_spells = creation_args.pop("usable_spells", [])

            # 2. Apply overrides to the creation args
            # Prioritize overrides passed via kwargs
            prop_overrides = overrides.pop("properties_override", {})
            dialog_overrides = overrides.pop("dialog_override", {})
            # Location is a key override
            current_region_id = overrides.pop("current_region_id", template.get("current_region_id"))
            current_room_id = overrides.pop("current_room_id", template.get("current_room_id"))
            health_override = overrides.get("health") # Check if health is overridden

            creation_args.update(overrides) # Apply remaining top-level overrides

            # 3. Create the base NPC instance
            # Pass only known __init__ args. NPC class is simple.
            init_args = {
                 "obj_id": npc_instance_id,
                 "name": creation_args.get("name", "Unknown NPC"),
                 "description": creation_args.get("description", "No description"),
                 # Use override health if provided, else template health
                 "health": health_override if health_override is not None else creation_args.get("health", 100),
                 "friendly": creation_args.get("friendly", True),
                 "level": creation_args.get("level", 1)
            }
            npc = NPC(**init_args)
            # Set max_health based on initial health
            npc.max_health = npc.health

            # 4. Apply attributes from template and overrides
            npc.faction = creation_args.get("faction", "neutral")
            npc.behavior_type = creation_args.get("behavior_type", "stationary")
            npc.attack_power = creation_args.get("attack_power", 3)
            npc.defense = creation_args.get("defense", 2)

            # Location (important override)
            npc.current_region_id = current_region_id
            npc.current_room_id = current_room_id
            # Set home location if not overridden
            npc.home_region_id = overrides.get("home_region_id", current_region_id)
            npc.home_room_id = overrides.get("home_room_id", current_room_id)

            # Apply properties (template + overrides)
            if not hasattr(npc, 'properties'): npc.properties = {}
            npc.properties.update(template_properties)
            npc.properties.update(prop_overrides) # Apply specific property overrides

            # Apply dialog (template + overrides)
            npc.dialog = template_dialog.copy()
            npc.dialog.update(dialog_overrides)
            npc.default_dialog = creation_args.get("default_dialog", template.get("default_dialog", "The {name} doesn't respond."))

            # Apply loot table, schedule, spells (usually just from template)
            npc.loot_table = template_loot.copy()
            npc.schedule = template_schedule.copy() # Schedule loaded from template
            npc.usable_spells = template_spells[:]
            npc.spell_cast_chance = npc.properties.get("spell_cast_chance", 0.3) # Get from properties or default
            npc.aggression = npc.properties.get("aggression", 0.0)
            npc.flee_threshold = npc.properties.get("flee_threshold", 0.2)
            npc.respawn_cooldown = npc.properties.get("respawn_cooldown", 600)
            npc.wander_chance = npc.properties.get("wander_chance", 0.3)
            npc.move_cooldown = npc.properties.get("move_cooldown", 10)

            # Initialize state attributes
            npc.is_alive = overrides.get("is_alive", True)
            npc.ai_state = overrides.get("ai_state", {}) # Load saved AI state if provided
            npc.last_moved = time.time() - world.start_time # Initialize timer

            # 5. Initialize Inventory
            from items.inventory import Inventory # Local import
            from items.item_factory import ItemFactory # Local import
            npc.inventory = Inventory(max_slots=10, max_weight=50.0) # Default empty inventory

            # Add items from template's initial_inventory
            for item_ref in template_inventory:
                 item_id = item_ref.get("item_id")
                 quantity = item_ref.get("quantity", 1)
                 if item_id:
                      # Use ItemFactory with world context
                      item = ItemFactory.create_item_from_template(item_id, world)
                      if item:
                           npc.inventory.add_item(item, quantity)
                      else:
                           print(f"Warning: Failed to create initial inventory item '{item_id}' for NPC '{npc.name}'.")

            # Apply inventory overrides from saved state (if any)
            inv_overrides = overrides.get("inventory_overrides", {})
            if inv_overrides:
                 # This requires more complex logic: modify existing items or add/remove
                 # For simplicity now, let's just print a warning
                 print(f"Warning: inventory_overrides loading not fully implemented for NPC '{npc.name}'.")
                 # TODO: Implement proper inventory override application

            return npc

        except Exception as e:
            print(f"{FORMAT_ERROR}Error instantiating NPC '{template_id}' from template: {e}{FORMAT_RESET}")
            import traceback
            traceback.print_exc()
            return None
