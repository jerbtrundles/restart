"""
plugins/npc_schedule_plugin/schedule_templates.py
Creates more dynamic schedules with NPCs moving between different locations
"""
import random

def create_example_schedules(plugin):
    """Create example schedules for NPCs in the world."""
    if not plugin.world:
        return
    
    # First collect all available rooms for use in schedules
    available_rooms = collect_available_rooms(plugin.world)
    
    # Designate special rooms for common activities
    town_spaces = designate_town_spaces(plugin.world, available_rooms)
    
    # Debug information
    if hasattr(plugin.world, "game") and hasattr(plugin.world.game, "debug_mode") and plugin.world.game.debug_mode:
        debug_msg = f"Found {len(available_rooms)} total rooms and designated special locations:\n"
        for space_type, locations in town_spaces.items():
            if locations:
                sample = locations[0]
                debug_msg += f"- {space_type}: {sample['region_id']}:{sample['room_id']} and {len(locations)-1} others\n"
        
        if plugin.event_system:
            plugin.event_system.publish("display_message", debug_msg)
        
    # Find existing NPCs and create schedules based on their types
    for obj_id, npc in plugin.world.npcs.items():
        # Store original behavior
        if not hasattr(npc, "ai_state"):
            npc.ai_state = {}
        
        # Only set this if not already set
        if "original_behavior_type" not in npc.ai_state:
            npc.ai_state["original_behavior_type"] = getattr(npc, "behavior_type", "wanderer")
        
        # Create schedules based on NPC type
        if "guard" in obj_id.lower() or "guard" in npc.name.lower():
            create_guard_schedule(plugin, obj_id, town_spaces)
        elif "shopkeeper" in obj_id.lower() or "merchant" in npc.name.lower():
            create_merchant_schedule(plugin, obj_id, town_spaces)
        elif "elder" in obj_id.lower() or "elder" in npc.name.lower():
            create_elder_schedule(plugin, obj_id, town_spaces)
        elif "bartender" in obj_id.lower() or "bartender" in npc.name.lower():
            create_bartender_schedule(plugin, obj_id, town_spaces)
        elif "villager" in obj_id.lower() or "villager" in npc.name.lower():
            create_villager_schedule(plugin, obj_id, town_spaces)
        # Default schedule for other NPCs
        else:
            create_default_schedule(plugin, obj_id, town_spaces)
        
        # Now that the NPC has a schedule, set behavior type to scheduled
        npc.behavior_type = "scheduled"
        
        # Initialize current activity
        current_hour = plugin.current_hour if hasattr(plugin, "current_hour") else 12
        schedule = plugin.get_npc_schedule(obj_id)
        
        if current_hour in schedule:
            activity = schedule[current_hour].get("activity", "idle")
            npc.ai_state["current_activity"] = activity
            
            # Set specific activity flags
            for state in ["is_sleeping", "is_eating", "is_working", "is_socializing"]:
                npc.ai_state[state] = False
            
            if activity == "sleeping":
                npc.ai_state["is_sleeping"] = True
            elif activity == "eating":
                npc.ai_state["is_eating"] = True
            elif activity == "working":
                npc.ai_state["is_working"] = True
            elif activity == "socializing":
                npc.ai_state["is_socializing"] = True
            
            # Add tracking for last notification
            npc.ai_state["last_notified_activity"] = ""
        
        # Reset move cooldown to ensure immediate movement if needed
        npc.last_moved = 0

def collect_available_rooms(world):
    """Collect all available rooms in the world."""
    available_rooms = []
    
    for region_id, region in world.regions.items():
        for room_id, room in region.rooms.items():
            available_rooms.append({
                "region_id": region_id,
                "room_id": room_id,
                "room_name": room.name,
                "properties": getattr(room, "properties", {})
            })
    
    return available_rooms

def designate_town_spaces(world, available_rooms):
    """Designate special rooms for common activities."""
    # Categories we need
    town_spaces = {
        "homes": [],
        "shops": [],
        "taverns": [],
        "markets": [],
        "town_square": [],
        "gardens": [],
        "temple": [],
        "guard_posts": [],
        "work_areas": [],
        "social_areas": []
    }
    
    # First pass: identify rooms by name hints
    for room_info in available_rooms:
        room_name = room_info["room_name"].lower()
        
        if "home" in room_name or "house" in room_name or "cottage" in room_name:
            town_spaces["homes"].append(room_info)
        
        if "shop" in room_name or "store" in room_name:
            town_spaces["shops"].append(room_info)
        
        if "tavern" in room_name or "inn" in room_name or "pub" in room_name:
            town_spaces["taverns"].append(room_info)
        
        if "market" in room_name or "bazaar" in room_name:
            town_spaces["markets"].append(room_info)
        
        if "square" in room_name or "plaza" in room_name or "center" in room_name:
            town_spaces["town_square"].append(room_info)
        
        if "garden" in room_name or "park" in room_name:
            town_spaces["gardens"].append(room_info)
        
        if "temple" in room_name or "church" in room_name or "shrine" in room_name:
            town_spaces["temple"].append(room_info)
        
        if "guard" in room_name or "post" in room_name or "watch" in room_name:
            town_spaces["guard_posts"].append(room_info)
        
        if "workshop" in room_name or "forge" in room_name or "mill" in room_name:
            town_spaces["work_areas"].append(room_info)
        
        if "hall" in room_name or "social" in room_name or "meeting" in room_name:
            town_spaces["social_areas"].append(room_info)
    
    # Second pass: ensure we have at least some locations for each type
    # If not enough specific rooms, allocate some generic ones
    for space_type in town_spaces.keys():
        if len(town_spaces[space_type]) < 2:
            # For each missing type, find some suitable rooms
            available_count = min(3, len(available_rooms))  # Take up to 3 rooms
            if available_count > 0:
                selected_rooms = random.sample(available_rooms, available_count)
                town_spaces[space_type].extend(selected_rooms)
    
    # If there's a "garden" in the room names, make sure it's in the gardens category
    for room_info in available_rooms:
        if "garden" in room_info["room_name"].lower() and room_info not in town_spaces["gardens"]:
            town_spaces["gardens"].append(room_info)
    
    # If there's an "entrance" room, make sure it's in town_square
    for room_info in available_rooms:
        if "entrance" in room_info["room_id"].lower() and room_info not in town_spaces["town_square"]:
            town_spaces["town_square"].append(room_info)
    
    return town_spaces

def get_random_location(locations, exclude_region=None, exclude_room=None):
    """Get a random location, excluding specified region/room if provided."""
    if not locations:
        return None
        
    valid_locations = [loc for loc in locations 
                      if (exclude_region is None or loc["region_id"] != exclude_region) 
                      and (exclude_room is None or loc["room_id"] != exclude_room)]
    
    if valid_locations:
        return random.choice(valid_locations)
    elif locations:
        return random.choice(locations)
    else:
        return None

def create_default_schedule(plugin, obj_id, town_spaces):
    """Create a default dynamic schedule for an NPC."""
    npc = plugin.world.get_npc(obj_id)
    if not npc:
        return
    
    # Use the NPC's current room as their home
    home_region = npc.current_region_id
    home_room = npc.current_room_id
    
    # Find potential activity locations
    work_location = get_random_location(town_spaces["work_areas"], home_region, home_room)
    market_location = get_random_location(town_spaces["markets"])
    social_location = get_random_location(town_spaces["social_areas"])
    garden_location = get_random_location(town_spaces["gardens"])
    
    # If any locations weren't found, use a generic location
    if not work_location:
        work_location = {"region_id": home_region, "room_id": home_room}
    if not market_location:
        market_location = work_location
    if not social_location:
        social_location = work_location
    if not garden_location:
        garden_location = social_location
    
    # Create a dynamic schedule with movement between locations
    schedule = {
        7: {"activity": "waking up", "region_id": home_region, "room_id": home_room},
        8: {"activity": "eating", "region_id": home_region, "room_id": home_room},
        9: {"activity": "going to work", "region_id": work_location["region_id"], "room_id": work_location["room_id"]},
        10: {"activity": "working", "region_id": work_location["region_id"], "room_id": work_location["room_id"]},
        12: {"activity": "visiting the market", "region_id": market_location["region_id"], "room_id": market_location["room_id"]},
        13: {"activity": "eating", "region_id": home_region, "room_id": home_room},
        14: {"activity": "working", "region_id": work_location["region_id"], "room_id": work_location["room_id"]},
        17: {"activity": "walking in the garden", "region_id": garden_location["region_id"], "room_id": garden_location["room_id"]},
        18: {"activity": "socializing", "region_id": social_location["region_id"], "room_id": social_location["room_id"]},
        20: {"activity": "heading home", "region_id": home_region, "room_id": home_room},
        21: {"activity": "eating", "region_id": home_region, "room_id": home_room},
        22: {"activity": "sleeping", "region_id": home_region, "room_id": home_room}
    }
    
    # Set sleeping responses
    npc.ai_state["sleeping_responses"] = [
        "The {name} is sleeping soundly.",
        "The {name} mumbles something in their sleep.",
        "The {name} doesn't respond, being fast asleep."
    ]
    
    # Set eating responses
    npc.ai_state["eating_responses"] = [
        "The {name} is busy eating right now.",
        "The {name} talks to you between bites of food.",
        "The {name} gestures for you to wait until they finish eating."
    ]
    
    # Set working responses
    npc.ai_state["working_responses"] = [
        "The {name} is busy with their work at the moment.",
        "The {name} briefly pauses their work to acknowledge you.",
        "The {name} seems focused on the task at hand."
    ]
    
    # Register the schedule
    plugin.add_npc_schedule(obj_id, schedule)

def create_guard_schedule(plugin, obj_id, town_spaces):
    """Create a dynamic guard schedule."""
    npc = plugin.world.get_npc(obj_id)
    if not npc:
        return
    
    # Guards patrol between different posts
    patrol_points = getattr(npc, "patrol_points", [])
    
    # Find guard posts to patrol between
    guard_posts = town_spaces["guard_posts"]
    town_square = town_spaces["town_square"]
    market = town_spaces["markets"]
    
    # Create the list of patrol locations
    patrol_locations = []
    
    # Add existing patrol points first
    for point in patrol_points:
        patrol_locations.append({"region_id": npc.current_region_id, "room_id": point})
    
    # Add guard posts
    for post in guard_posts:
        if post not in patrol_locations:
            patrol_locations.append(post)
    
    # Add town square
    for square in town_square:
        if square not in patrol_locations:
            patrol_locations.append(square)
    
    # Add market areas during daytime hours
    for m in market:
        if m not in patrol_locations:
            patrol_locations.append(m)
    
    # If we don't have enough patrol points, add the current room
    if not patrol_locations:
        patrol_locations.append({"region_id": npc.current_region_id, "room_id": npc.current_room_id})
    
    # Get barracks or resting area
    barracks = get_random_location(guard_posts)
    if not barracks:
        barracks = {"region_id": npc.current_region_id, "room_id": npc.current_room_id}
    
    # Get tavern for evening break
    tavern = get_random_location(town_spaces["taverns"])
    if not tavern:
        tavern = barracks
    
    # Create a dynamic schedule with patrols
    schedule = {}
    
    # Morning shift
    schedule[6] = {"activity": "waking up", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    schedule[7] = {"activity": "eating breakfast", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    
    # Morning patrol covering different areas
    if len(patrol_locations) >= 3:
        schedule[8] = {"activity": "morning patrol", "region_id": patrol_locations[0]["region_id"], "room_id": patrol_locations[0]["room_id"]}
        schedule[9] = {"activity": "morning patrol", "region_id": patrol_locations[1]["region_id"], "room_id": patrol_locations[1]["room_id"]}
        schedule[10] = {"activity": "morning patrol", "region_id": patrol_locations[2]["region_id"], "room_id": patrol_locations[2]["room_id"]}
    else:
        # Use what we have and cycle if needed
        for hour, i in zip(range(8, 11), range(len(patrol_locations))):
            idx = i % len(patrol_locations)
            schedule[hour] = {"activity": "morning patrol", "region_id": patrol_locations[idx]["region_id"], "room_id": patrol_locations[idx]["room_id"]}
    
    # Midday break
    schedule[12] = {"activity": "lunch break", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    
    # Afternoon patrol
    if len(patrol_locations) >= 3:
        schedule[13] = {"activity": "afternoon patrol", "region_id": patrol_locations[2]["region_id"], "room_id": patrol_locations[2]["room_id"]}
        schedule[14] = {"activity": "afternoon patrol", "region_id": patrol_locations[1]["region_id"], "room_id": patrol_locations[1]["room_id"]}
        schedule[15] = {"activity": "afternoon patrol", "region_id": patrol_locations[0]["region_id"], "room_id": patrol_locations[0]["room_id"]}
    else:
        # Use what we have and cycle if needed
        for hour, i in zip(range(13, 16), range(len(patrol_locations))):
            idx = (len(patrol_locations) - 1 - i) % len(patrol_locations)  # Reverse order
            schedule[hour] = {"activity": "afternoon patrol", "region_id": patrol_locations[idx]["region_id"], "room_id": patrol_locations[idx]["room_id"]}
    
    # Evening routine
    schedule[17] = {"activity": "shift change", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    schedule[18] = {"activity": "eating dinner", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    schedule[19] = {"activity": "relaxing", "region_id": tavern["region_id"], "room_id": tavern["room_id"]}
    
    # Night patrol (if night guard)
    night_shift = random.choice([True, False])
    if night_shift:
        if len(patrol_locations) >= 2:
            schedule[21] = {"activity": "night patrol", "region_id": patrol_locations[0]["region_id"], "room_id": patrol_locations[0]["room_id"]}
            schedule[23] = {"activity": "night patrol", "region_id": patrol_locations[1]["region_id"], "room_id": patrol_locations[1]["room_id"]}
        else:
            schedule[21] = {"activity": "night patrol", "region_id": patrol_locations[0]["region_id"], "room_id": patrol_locations[0]["room_id"]}
        schedule[1] = {"activity": "sleeping", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    else:
        schedule[21] = {"activity": "sleeping", "region_id": barracks["region_id"], "room_id": barracks["room_id"]}
    
    # Set custom responses
    npc.ai_state["sleeping_responses"] = [
        "The {name} is resting after a long shift.",
        "Even guards need sleep. The {name} is off duty right now."
    ]
    
    # Register the schedule
    plugin.add_npc_schedule(obj_id, schedule)

def create_merchant_schedule(plugin, obj_id, town_spaces):
    """Create a dynamic merchant schedule."""
    npc = plugin.world.get_npc(obj_id)
    if not npc:
        return
    
    # Use current room as shop
    shop_region = npc.current_region_id
    shop_room = npc.current_room_id
    
    # Find a home for the merchant
    homes = town_spaces["homes"]
    home = get_random_location(homes, shop_region, shop_room)
    if not home:
        home = {"region_id": shop_region, "room_id": shop_room}
    
    # Find market and social spaces
    market = get_random_location(town_spaces["markets"], shop_region, shop_room)
    if not market:
        market = {"region_id": shop_region, "room_id": shop_room}
    
    tavern = get_random_location(town_spaces["taverns"])
    if not tavern:
        tavern = home
    
    # Create a dynamic schedule
    schedule = {
        6: {"activity": "waking up", "region_id": home["region_id"], "room_id": home["room_id"]},
        7: {"activity": "eating breakfast", "region_id": home["region_id"], "room_id": home["room_id"]},
        8: {"activity": "walking to shop", "region_id": shop_region, "room_id": shop_room},
        9: {"activity": "preparing shop", "region_id": shop_region, "room_id": shop_room},
        10: {"activity": "working", "region_id": shop_region, "room_id": shop_room},
        12: {"activity": "shopping for supplies", "region_id": market["region_id"], "room_id": market["room_id"]},
        13: {"activity": "eating lunch", "region_id": shop_region, "room_id": shop_room},
        14: {"activity": "working", "region_id": shop_region, "room_id": shop_room},
        17: {"activity": "closing shop", "region_id": shop_region, "room_id": shop_room},
        18: {"activity": "heading to dinner", "region_id": tavern["region_id"], "room_id": tavern["room_id"]},
        20: {"activity": "walking home", "region_id": home["region_id"], "room_id": home["room_id"]},
        21: {"activity": "counting coins", "region_id": home["region_id"], "room_id": home["room_id"]},
        22: {"activity": "sleeping", "region_id": home["region_id"], "room_id": home["room_id"]}
    }
    
    # Set custom responses
    npc.ai_state["working_responses"] = [
        "The {name} says, 'Welcome! Are you looking to buy something?'",
        "The {name} says, 'I have the finest wares in the region!'",
        "The {name} says, 'Feel free to browse, but please don't touch the merchandise unless you're buying.'"
    ]
    
    # Register the schedule
    plugin.add_npc_schedule(obj_id, schedule)

def create_elder_schedule(plugin, obj_id, town_spaces):
    """Create a dynamic elder schedule."""
    npc = plugin.world.get_npc(obj_id)
    if not npc:
        return
    
    # Elders spend time in important town locations
    home_region = npc.current_region_id
    home_room = npc.current_room_id
    
    # Find key locations
    temple = get_random_location(town_spaces["temple"])
    if not temple:
        temple = {"region_id": home_region, "room_id": home_room}
        
    town_square = get_random_location(town_spaces["town_square"])
    if not town_square:
        town_square = {"region_id": home_region, "room_id": home_room}
    
    garden = get_random_location(town_spaces["gardens"])
    if not garden:
        garden = town_square
    
    # Create a thoughtful schedule with quiet contemplation and community guidance
    schedule = {
        7: {"activity": "waking up", "region_id": home_region, "room_id": home_room},
        8: {"activity": "morning meditation", "region_id": home_region, "room_id": home_room},
        9: {"activity": "eating breakfast", "region_id": home_region, "room_id": home_room},
        10: {"activity": "visiting the temple", "region_id": temple["region_id"], "room_id": temple["room_id"]},
        11: {"activity": "praying", "region_id": temple["region_id"], "room_id": temple["room_id"]},
        12: {"activity": "walking to the square", "region_id": town_square["region_id"], "room_id": town_square["room_id"]},
        13: {"activity": "counseling villagers", "region_id": town_square["region_id"], "room_id": town_square["room_id"]},
        15: {"activity": "walking in the garden", "region_id": garden["region_id"], "room_id": garden["room_id"]},
        16: {"activity": "resting", "region_id": garden["region_id"], "room_id": garden["room_id"]},
        17: {"activity": "returning home", "region_id": home_region, "room_id": home_room},
        18: {"activity": "eating dinner", "region_id": home_region, "room_id": home_room},
        19: {"activity": "evening reflection", "region_id": home_region, "room_id": home_room},
        21: {"activity": "sleeping", "region_id": home_region, "room_id": home_room}
    }
    
    # Register the schedule
    plugin.add_npc_schedule(obj_id, schedule)

def create_villager_schedule(plugin, obj_id, town_spaces):
    """Create a dynamic villager schedule with varied activities."""
    npc = plugin.world.get_npc(obj_id)
    if not npc:
        return
    
    # Villagers have a variety of possible patterns
    home_region = npc.current_region_id
    home_room = npc.current_room_id
    
    # Find a separate home if possible
    possible_home = get_random_location(town_spaces["homes"])
    if possible_home and possible_home["room_id"] != home_room:
        home = possible_home
    else:
        home = {"region_id": home_region, "room_id": home_room}
    
    # Find work location (different for each villager)
    possible_work_places = [
        town_spaces["work_areas"],
        town_spaces["shops"],
        town_spaces["markets"],
        town_spaces["gardens"]
    ]
    
    # Select a work category randomly
    work_category = random.choice(possible_work_places)
    work_place = get_random_location(work_category, home["region_id"], home["room_id"])
    if not work_place:
        work_place = {"region_id": home_region, "room_id": home_room}
    
    # Social locations
    tavern = get_random_location(town_spaces["taverns"])
    if not tavern:
        tavern = home
    
    market = get_random_location(town_spaces["markets"])
    if not market:
        market = work_place
    
    square = get_random_location(town_spaces["town_square"])
    if not square:
        square = market
    
    # Special location (shop, garden, temple etc.)
    special_categories = [cat for cat in town_spaces.keys() if cat not in ["homes", "work_areas"]]
    if special_categories:
        special_category = random.choice(special_categories)
        special_place = get_random_location(town_spaces[special_category])
    else:
        special_place = square
    
    # Create a varied schedule
    schedule = {
        7: {"activity": "waking up", "region_id": home["region_id"], "room_id": home["room_id"]},
        8: {"activity": "eating breakfast", "region_id": home["region_id"], "room_id": home["room_id"]},
        9: {"activity": "heading to work", "region_id": work_place["region_id"], "room_id": work_place["room_id"]},
        11: {"activity": "working", "region_id": work_place["region_id"], "room_id": work_place["room_id"]},
        13: {"activity": "lunch break", "region_id": market["region_id"], "room_id": market["room_id"]},
        14: {"activity": "shopping", "region_id": market["region_id"], "room_id": market["room_id"]},
        15: {"activity": "working", "region_id": work_place["region_id"], "room_id": work_place["room_id"]},
        17: {"activity": "visiting", "region_id": special_place["region_id"], "room_id": special_place["room_id"]},
        18: {"activity": "socializing", "region_id": tavern["region_id"], "room_id": tavern["room_id"]},
        20: {"activity": "heading home", "region_id": home["region_id"], "room_id": home["room_id"]},
        21: {"activity": "relaxing", "region_id": home["region_id"], "room_id": home["room_id"]},
        22: {"activity": "sleeping", "region_id": home["region_id"], "room_id": home["room_id"]}
    }
    
    # Randomize: sometimes villagers have a different pattern on specific days
    # This is just a placeholder for future day-specific scheduling
    if random.random() < 0.3:  # 30% chance of having some variation
        # For now, just add a minor variation in the late afternoon
        schedule[16] = {"activity": "taking a walk", "region_id": square["region_id"], "room_id": square["room_id"]}
    
    # Register the schedule
    plugin.add_npc_schedule(obj_id, schedule)

def create_bartender_schedule(plugin, obj_id, town_spaces):
    """Create a dynamic bartender schedule."""
    npc = plugin.world.get_npc(obj_id)
    if not npc:
        return
    
    # Bartenders work in taverns but may live elsewhere
    tavern_region = npc.current_region_id
    tavern_room = npc.current_room_id
    
    # Find a home separate from the tavern if possible
    home = get_random_location(town_spaces["homes"], tavern_region, tavern_room)
    if not home:
        home = {"region_id": tavern_region, "room_id": tavern_room}
    
    # Market for supplies
    market = get_random_location(town_spaces["markets"])
    if not market:
        market = {"region_id": tavern_region, "room_id": tavern_room}
    
    # Create a schedule with later hours
    schedule = {
        9: {"activity": "waking up", "region_id": home["region_id"], "room_id": home["room_id"]},
        10: {"activity": "eating breakfast", "region_id": home["region_id"], "room_id": home["room_id"]},
        11: {"activity": "shopping for supplies", "region_id": market["region_id"], "room_id": market["room_id"]},
        12: {"activity": "heading to tavern", "region_id": tavern_region, "room_id": tavern_room},
        13: {"activity": "preparing the tavern", "region_id": tavern_region, "room_id": tavern_room},
        14: {"activity": "working", "region_id": tavern_region, "room_id": tavern_room},
        16: {"activity": "serving customers", "region_id": tavern_region, "room_id": tavern_room},
        18: {"activity": "busy hour", "region_id": tavern_region, "room_id": tavern_room},
        20: {"activity": "entertaining patrons", "region_id": tavern_region, "room_id": tavern_room},
        23: {"activity": "closing up", "region_id": tavern_region, "room_id": tavern_room},
        0: {"activity": "walking home", "region_id": home["region_id"], "room_id": home["room_id"]},
        1: {"activity": "sleeping", "region_id": home["region_id"], "room_id": home["room_id"]}
    }
    
    # Set custom responses
    npc.ai_state["working_responses"] = [
        "The {name} says, 'What'll it be?'",
        "The {name} wipes down the counter while listening to you.",
        "The {name} says, 'I've heard all sorts of stories working here...'"
    ]
    
    # Register the schedule
    plugin.add_npc_schedule(obj_id, schedule)

def create_town_activity(plugin, town_spaces):
    """
    Create a dynamic town routine with NPCs meeting each other at various times.
    This helps create a sense of a living town where NPCs interact.
    
    Call this after creating individual schedules.
    """
    if not plugin.world:
        return
    
    # Get all NPCs with schedules
    scheduled_npcs = [obj_id for obj_id in plugin.npc_schedules.keys()]
    
    # If not enough NPCs, do nothing
    if len(scheduled_npcs) < 2:
        return
    
    # Create special meeting events
    # For example: scheduled gatherings, meetings between NPCs
    
    # 1. Morning market gathering
    morning_market_hour = 10
    market_location = None
    if town_spaces["markets"]:
        market_location = random.choice(town_spaces["markets"])
    elif town_spaces["town_square"]:
        market_location = random.choice(town_spaces["town_square"])
    
    # 2. Evening tavern gathering
    evening_tavern_hour = 19
    tavern_location = None
    if town_spaces["taverns"]:
        tavern_location = random.choice(town_spaces["taverns"])
    
    # 3. Afternoon garden/square meeting
    afternoon_meeting_hour = 16
    meeting_location = None
    if town_spaces["gardens"]:
        meeting_location = random.choice(town_spaces["gardens"])
    elif town_spaces["town_square"]:
        meeting_location = random.choice(town_spaces["town_square"])
    
    # Apply gatherings to some NPCs
    if market_location:
        # Select random NPCs to visit the market
        market_visitors = random.sample(scheduled_npcs, min(3, len(scheduled_npcs)))
        for obj_id in market_visitors:
            if obj_id in plugin.npc_schedules:
                schedule = plugin.npc_schedules[obj_id]
                # Only override if they're not already doing something critical
                if morning_market_hour not in schedule or "working" not in schedule[morning_market_hour].get("activity", ""):
                    schedule[morning_market_hour] = {
                        "activity": "visiting the morning market",
                        "region_id": market_location["region_id"],
                        "room_id": market_location["room_id"]
                    }
                    # Update the NPC's schedule
                    plugin.add_npc_schedule(obj_id, schedule)
    
    if tavern_location:
        # Select random NPCs to visit the tavern
        tavern_visitors = random.sample(scheduled_npcs, min(5, len(scheduled_npcs)))
        for obj_id in tavern_visitors:
            if obj_id in plugin.npc_schedules:
                schedule = plugin.npc_schedules[obj_id]
                # Only override if they're not already doing something critical
                if evening_tavern_hour not in schedule or "sleeping" not in schedule[evening_tavern_hour].get("activity", ""):
                    schedule[evening_tavern_hour] = {
                        "activity": "visiting the tavern",
                        "region_id": tavern_location["region_id"],
                        "room_id": tavern_location["room_id"]
                    }
                    # Update the NPC's schedule
                    plugin.add_npc_schedule(obj_id, schedule)
    
    if meeting_location:
        # Select random NPCs for afternoon gathering
        meeting_attendees = random.sample(scheduled_npcs, min(4, len(scheduled_npcs)))
        for obj_id in meeting_attendees:
            if obj_id in plugin.npc_schedules:
                schedule = plugin.npc_schedules[obj_id]
                # Only override if they're not already doing something critical
                if afternoon_meeting_hour not in schedule or "working" not in schedule[afternoon_meeting_hour].get("activity", ""):
                    schedule[afternoon_meeting_hour] = {
                        "activity": "meeting with friends",
                        "region_id": meeting_location["region_id"],
                        "room_id": meeting_location["room_id"]
                    }
                    # Update the NPC's schedule
                    plugin.add_npc_schedule(obj_id, schedule)