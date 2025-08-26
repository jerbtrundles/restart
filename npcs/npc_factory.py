# npcs/npc_factory.py
import inspect
import random
import time
import uuid
from typing import TYPE_CHECKING, Dict, List, Optional, Any
from core.config import (
    FORMAT_ERROR, FORMAT_RESET,
    NPC_BASE_HEALTH, NPC_BASE_XP_TO_LEVEL, NPC_CON_HEALTH_MULTIPLIER, NPC_DEFAULT_AGGRESSION, NPC_DEFAULT_FLEE_THRESHOLD, NPC_DEFAULT_MOVE_COOLDOWN, NPC_DEFAULT_SPELL_CAST_CHANCE, NPC_DEFAULT_WANDER, NPC_LEVEL_HEALTH_BASE_INCREASE, NPC_LEVEL_CON_HEALTH_MULTIPLIER, NPC_XP_TO_LEVEL_MULTIPLIER, VILLAGER_FIRST_NAMES_FEMALE, VILLAGER_FIRST_NAMES_MALE, VILLAGER_LAST_NAMES # Import NPC health constants
)
# ItemFactory needed if NPCs have initial inventory defined by references
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
            # 1. Prepare base arguments from template & overrides
            creation_args = template.copy()
            npc_instance_id = instance_id if instance_id else f"{template_id}_{uuid.uuid4().hex[:8]}"
            creation_args.update(overrides) # Overrides take precedence

            # --- *** Start Name Generation Logic *** ---
            final_npc_name = None
            # # Prioritize name from overrides (saved state)
            # if "name" in overrides and overrides["name"] != template.get("name"): # Check if override is different from template default
            #      final_npc_name = overrides["name"]
            #      # print(f"[NPC Factory Debug] Using overridden name: {final_npc_name}") # Debug
            # # If template is 'wandering_villager' AND no specific name was provided by overrides
            # elif template_id == "wandering_villager" and "name" not in overrides:
            if(template_id == "wandering_villager"):
                try:
                    # Combine male and female names for now
                    first_names = VILLAGER_FIRST_NAMES_MALE + VILLAGER_FIRST_NAMES_FEMALE
                    if first_names and VILLAGER_LAST_NAMES:
                        first = random.choice(first_names)
                        last = random.choice(VILLAGER_LAST_NAMES)
                        final_npc_name = f"{first} {last}"
                        # print(f"[NPC Factory Debug] Generated random name: {final_npc_name}") # Debug
                    else:
                        print(f"{FORMAT_ERROR}Warning: Villager name lists empty in config. Using template name.{FORMAT_RESET}")
                        final_npc_name = template.get("name", "Villager") # Fallback
                except Exception as name_err:
                     print(f"{FORMAT_ERROR}Error generating random name: {name_err}. Using template name.{FORMAT_RESET}")
                     final_npc_name = template.get("name", "Villager") # Fallback
            else:
                 # Use template name as default if no override and not randomizing
                 final_npc_name = template.get("name", "Unknown NPC")
                 # print(f"[NPC Factory Debug] Using template name: {final_npc_name}") # Debug
            # --- *** End Name Generation Logic *** ---

            # 2. Create base NPC instance
            init_args = {
                "obj_id": npc_instance_id,
                "name": final_npc_name, # <<< Use the final determined name
                "description": creation_args.get("description", template.get("description", "No description")),
                "level": overrides.get("level", template.get("level", 1)),
                "friendly": creation_args.get("friendly", template.get("friendly", True)),
            }
            npc = NPC(**init_args)
            npc.template_id = template_id # Store template reference

            # 3. Apply Stats
            base_stats = npc.stats.copy()
            template_stats = template.get("stats", {})
            saved_stats = overrides.get("stats", {})
            npc.stats = {**base_stats, **template_stats, **saved_stats}

            # 4. Recalculate Max Health
            npc.level = init_args["level"] # Ensure level is set from overrides/template *before* recalc
            npc_level = npc.level
            final_con = npc.stats.get('constitution', 8)
            base_hp = NPC_BASE_HEALTH + int(final_con * NPC_CON_HEALTH_MULTIPLIER)
            level_hp_bonus = (npc_level - 1) * (NPC_LEVEL_HEALTH_BASE_INCREASE + int(final_con * NPC_LEVEL_CON_HEALTH_MULTIPLIER))
            npc.max_health = base_hp + level_hp_bonus
            explicit_max_health = creation_args.get("max_health")
            if explicit_max_health: npc.max_health = max(npc.max_health, explicit_max_health)

            npc.health = creation_args.get("health", npc.max_health) # Prioritize saved health
            npc.health = max(0, min(npc.health, npc.max_health))

            # <<< Load/Initialize XP attributes >>>
            npc.experience = overrides.get("experience", 0) # Load saved XP if present
            # Load saved threshold, or calculate based on current level if loading a new NPC or old save
            npc.experience_to_level = overrides.get("experience_to_level",
                                                int(NPC_BASE_XP_TO_LEVEL * (NPC_XP_TO_LEVEL_MULTIPLIER**(npc.level - 1))))
            # --- <<< End XP Handling >>> ---

            # 5. Apply remaining attributes
            npc.faction = creation_args.get("faction", npc.faction)
            npc.behavior_type = creation_args.get("behavior_type", npc.behavior_type)
            npc.attack_power = creation_args.get("attack_power", 3) + npc.stats.get('strength', 8) // 3
            npc.defense = creation_args.get("defense", 2)

            npc.current_region_id = creation_args.get("current_region_id", npc.current_region_id)
            npc.current_room_id = creation_args.get("current_room_id", npc.current_room_id)
            npc.home_region_id = creation_args.get("home_region_id", npc.current_region_id)
            npc.home_room_id = creation_args.get("home_room_id", npc.current_room_id)

            npc.dialog = creation_args.get("dialog", {}).copy()
            npc.default_dialog = creation_args.get("default_dialog", npc.default_dialog)

            npc.loot_table = creation_args.get("loot_table", {}).copy()
            npc.usable_spells = creation_args.get("usable_spells", [])[:]

            npc.schedule = creation_args.get("schedule", {}).copy()
            npc.patrol_index = creation_args.get("patrol_index", 0)
            npc.patrol_points = creation_args.get("patrol_points", [])[:]

            # 6. Apply stateful attributes from overrides
            npc.is_alive = creation_args.get("is_alive", npc.is_alive) if npc.health > 0 else False
            npc.ai_state = creation_args.get("ai_state", {}).copy() # Important: use creation_args which has overrides
            npc.spell_cooldowns = creation_args.get("spell_cooldowns", {}).copy() # Same here

            # 7. Apply properties
            npc.properties = template.get("properties", {}).copy()
            prop_overrides = overrides.get("properties_override", {}) # properties_override from save data
            # Also consider properties directly in the main overrides dict (if any were saved there)
            for key, val in overrides.items():
                 if key not in init_args and key not in ["stats", "health", "level", "faction", "behavior_type", "dialog", "loot_table", "usable_spells", "schedule", "patrol_points", "ai_state", "spell_cooldowns", "inventory", "template_id", "obj_id", "description"]:
                      # If it's not a standard attribute handled above, treat it as a property override
                      prop_overrides[key] = val

            npc.properties.update(prop_overrides)

            # --- Set attributes derived from properties (with warnings if missing) ---
            # (Keep the warning logic as it was)
            default_aggression = NPC_DEFAULT_AGGRESSION
            default_wander = NPC_DEFAULT_WANDER
            default_cooldown = NPC_DEFAULT_MOVE_COOLDOWN
            default_spell_chance = NPC_DEFAULT_SPELL_CAST_CHANCE
            default_flee_threshold = NPC_DEFAULT_FLEE_THRESHOLD

            if "aggression" in npc.properties: npc.aggression = npc.properties["aggression"]
            else:
                if npc.faction == "hostile": print(f"{FORMAT_ERROR}Warning:{FORMAT_RESET} NPC '{template_id}'/'{npc.obj_id}' missing 'aggression' property. Using default: {default_aggression}")
                npc.aggression = default_aggression

            if "flee_threshold" in npc.properties: npc.flee_threshold = npc.properties["flee_threshold"]
            else:
                if npc.faction == "hostile": print(f"{FORMAT_ERROR}Warning:{FORMAT_RESET} NPC '{template_id}'/'{npc.obj_id}' missing 'flee_threshold' property. Using default: {default_flee_threshold}")
                npc.flee_threshold = default_flee_threshold

            if "respawn_cooldown" in npc.properties: npc.respawn_cooldown = npc.properties["respawn_cooldown"]
            else:
                 if npc.faction == "hostile": print(f"{FORMAT_ERROR}Warning:{FORMAT_RESET} NPC '{template_id}'/'{npc.obj_id}' missing 'respawn_cooldown' property. Using default: 600")
                 npc.respawn_cooldown = 600

            if "wander_chance" in npc.properties: npc.wander_chance = npc.properties["wander_chance"]
            else:
                 # Only warn if behavior expects wandering
                 if npc.behavior_type in ["wanderer", "aggressive"]: # Aggressive also wanders
                      print(f"{FORMAT_ERROR}Warning:{FORMAT_RESET} NPC '{template_id}'/'{npc.obj_id}' missing 'wander_chance' property. Using default: {default_wander}")
                 npc.wander_chance = default_wander

            if "move_cooldown" in npc.properties: npc.move_cooldown = npc.properties["move_cooldown"]
            else:
                 print(f"{FORMAT_ERROR}Warning:{FORMAT_RESET} NPC '{template_id}'/'{npc.obj_id}' missing 'move_cooldown' property. Using default: {default_cooldown}")
                 npc.move_cooldown = default_cooldown

            if "spell_cast_chance" in npc.properties: npc.spell_cast_chance = npc.properties["spell_cast_chance"]
            else:
                if npc.usable_spells: print(f"{FORMAT_ERROR}Warning:{FORMAT_RESET} NPC '{template_id}'/'{npc.obj_id}' missing 'spell_cast_chance' property. Using default: {default_spell_chance}")
                npc.spell_cast_chance = default_spell_chance


            # 8. Initialize Inventory
            from items.inventory import Inventory
            saved_inv_data = overrides.get("inventory")
            if saved_inv_data and isinstance(saved_inv_data, dict):
                npc.inventory = Inventory.from_dict(saved_inv_data, world)
            else:
                npc.inventory = Inventory(max_slots=10, max_weight=50.0)
                template_inventory = template.get("initial_inventory", [])
                for item_ref in template_inventory:
                    item_id = item_ref.get("item_id")
                    quantity = item_ref.get("quantity", 1)
                    if item_id:
                        item = ItemFactory.create_item_from_template(item_id, world)
                        if item: npc.inventory.add_item(item, quantity)
                        else: print(f"Warning: Failed to create initial inventory item '{item_id}' for NPC '{npc.name}'.")

            # Assign world reference
            npc.world = world

            return npc

        except Exception as e:
            print(f"{FORMAT_ERROR}Error instantiating NPC '{template_id}' from template: {e}{FORMAT_RESET}")
            import traceback
            traceback.print_exc()
            return None
