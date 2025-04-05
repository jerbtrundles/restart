# npcs/npc_factory.py
import inspect
import time
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from core.config import FORMAT_ERROR, FORMAT_RESET
# ItemFactory needed if NPCs have initial inventory defined by references
from items.item_factory import ItemFactory
from npcs.npc import NPC # Import NPC class

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
    
    @staticmethod
    def get_template_names(world: 'World') -> List[str]:
        """Get a list of available NPC template names from the world."""
        if world and hasattr(world, 'npc_templates'):
             return list(world.npc_templates.keys())
        return []

    @staticmethod
    def get_template(template_id: str, world: 'World') -> Optional[Dict[str, Any]]:
         """Get a copy of an NPC template from the world."""
         if world and hasattr(world, 'npc_templates'):
              template = world.npc_templates.get(template_id)
              return template.copy() if template else None
         return None
    
    # --- MODIFIED: create_npc_from_template ---
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
            # 1. Prepare base arguments from template
            creation_args = template.copy()
            npc_instance_id = instance_id if instance_id else f"{template_id}_{uuid.uuid4().hex[:8]}"
            # Ensure overrides take precedence
            creation_args.update(overrides)

            # 2. Create the base NPC instance using known __init__ args
            init_args = {
                 "obj_id": npc_instance_id,
                 "name": creation_args.get("name", "Unknown NPC"),
                 "description": creation_args.get("description", "No description"),
                 "health": creation_args.get("health", 100),
                 "friendly": creation_args.get("friendly", True),
                 "level": creation_args.get("level", 1)
            }
            npc = NPC(**init_args)
            npc.template_id = template_id # Store template reference

            # 3. Apply remaining attributes from template and overrides directly
            npc.max_health = creation_args.get("max_health", npc.health) # Set max_health based on initial health
            npc.faction = creation_args.get("faction", "neutral")
            npc.behavior_type = creation_args.get("behavior_type", "stationary")
            npc.attack_power = creation_args.get("attack_power", 3)
            npc.defense = creation_args.get("defense", 2)
            npc.current_region_id = creation_args.get("current_region_id")
            npc.current_room_id = creation_args.get("current_room_id")
            npc.home_region_id = creation_args.get("home_region_id", npc.current_region_id) # Default home to current
            npc.home_room_id = creation_args.get("home_room_id", npc.current_room_id)
            npc.dialog = creation_args.get("dialog", {}).copy()
            npc.default_dialog = creation_args.get("default_dialog", "The {name} doesn't respond.")
            npc.loot_table = creation_args.get("loot_table", {}).copy() # Ensure loot table uses item_ids now
            npc.usable_spells = creation_args.get("usable_spells", [])[:] # Copy list
            npc.schedule = creation_args.get("schedule", {}).copy()
            npc.patrol_points = creation_args.get("patrol_points", [])[:]
            npc.patrol_index = creation_args.get("patrol_index", 0)

            # Apply stateful attributes from overrides (these come from save data)
            npc.health = overrides.get("health", npc.health) # Load saved health
            npc.is_alive = overrides.get("is_alive", npc.is_alive)
            npc.ai_state = overrides.get("ai_state", {}).copy()
            npc.spell_cooldowns = overrides.get("spell_cooldowns", {}).copy()
            # Apply location overrides explicitly if provided in `overrides`
            if "current_region_id" in overrides: npc.current_region_id = overrides["current_region_id"]
            if "current_room_id" in overrides: npc.current_room_id = overrides["current_room_id"]


            # 4. Apply properties from template and overrides
            npc.properties = template.get("properties", {}).copy()
            # Apply specific property overrides if they exist in the 'overrides' dict directly
            # (e.g., if save_game saved overrides["properties_override"])
            prop_overrides = overrides.get("properties_override", {})
            npc.properties.update(prop_overrides)
            # Ensure core combat/movement props reflect final values in properties dict
            npc.update_property("aggression", npc.properties.get("aggression", 0.0))
            npc.update_property("flee_threshold", npc.properties.get("flee_threshold", 0.2))
            npc.update_property("respawn_cooldown", npc.properties.get("respawn_cooldown", 600))
            npc.update_property("wander_chance", npc.properties.get("wander_chance", 0.3))
            npc.update_property("move_cooldown", npc.properties.get("move_cooldown", 10))
            npc.update_property("spell_cast_chance", npc.properties.get("spell_cast_chance", 0.3))
            # Set the actual attributes from the final properties values
            npc.aggression = npc.get_property("aggression")
            npc.flee_threshold = npc.get_property("flee_threshold")
            npc.respawn_cooldown = npc.get_property("respawn_cooldown")
            npc.wander_chance = npc.get_property("wander_chance")
            npc.move_cooldown = npc.get_property("move_cooldown")
            npc.spell_cast_chance = npc.get_property("spell_cast_chance")


            # 5. Initialize Inventory and add initial items
            from items.inventory import Inventory # Local import
            npc.inventory = Inventory(max_slots=10, max_weight=50.0) # Start fresh
            template_inventory = template.get("initial_inventory", [])
            for item_ref in template_inventory:
                 item_id = item_ref.get("item_id")
                 quantity = item_ref.get("quantity", 1)
                 if item_id:
                      item = ItemFactory.create_item_from_template(item_id, world) # Pass world
                      if item:
                           npc.inventory.add_item(item, quantity)
                      else: print(f"Warning: Failed to create initial inventory item '{item_id}' for NPC '{npc.name}'.")

            # Apply inventory overrides from saved state (if implemented)
            # saved_inv_data = overrides.get("inventory") # Check if full inventory state was saved
            # if saved_inv_data:
            #     npc.inventory = Inventory.from_dict(saved_inv_data, world)


            # Initialize timers/state
            npc.last_moved = time.time() - getattr(world, 'start_time', time.time())
            npc.world = world # Give NPC world reference

            return npc

        except Exception as e:
            print(f"{FORMAT_ERROR}Error instantiating NPC '{template_id}' from template: {e}{FORMAT_RESET}")
            import traceback
            traceback.print_exc()
            return None
    # --- END MODIFIED ---
