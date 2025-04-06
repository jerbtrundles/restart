# plugins/quest_system_plugin/config.py
"""Default configuration for the Quest System plugin."""

DEFAULT_CONFIG = {
    "quest_board_location": "town:town_square", # Where the quest board is located
    "max_quests_on_board": 5,             # How many quests are visible at once
    "min_quests_on_board": 2,             # Always try to have at least this many
    "initial_quests_per_type": 1,       # How many of each type to generate initially
    "quest_level_range_player": 3,        # Generate quests +/- this many levels from player
    "quest_level_min": 1,                 # Minimum level for any generated quest objective
    # --- Reward Scaling ---
    "reward_base_xp": 50,
    "reward_xp_per_level": 15,
    "reward_xp_per_quantity": 5, # For kill/fetch
    "reward_base_gold": 10,
    "reward_gold_per_level": 5,
    "reward_gold_per_quantity": 2, # For kill/fetch
    # --- Generation Tuning ---
    "kill_quest_quantity_base": 3,
    "kill_quest_quantity_per_level": 0.5, # e.g., level 10 player might need 3 + 5 = 8 kills
    "fetch_quest_quantity_base": 5,
    "fetch_quest_quantity_per_level": 1,
    # --- NPC Quest Giver Interests (Example Mapping) ---
    # Maps NPC template ID to list of interests/quest types they can generate
    # This might be better loaded dynamically from NPC templates later, but define defaults here
    "npc_quest_interests": {
        # Ensure these lists contain the values used in quest_type_interest_map
        "blacksmith": ["kill", "deliver", "fetch", "kill_nearby_threats", "fetch_materials_metal", "fetch_materials_ore", "fetch_materials_hide", "fetch_simple", "kill_pests"], # Added some generic ones
        "tavern_keeper": ["kill", "deliver", "fetch", "fetch_ingredients", "fetch_consumables", "kill_pests", "deliver_messages", "fetch_simple"], # Added generic fetch
        "merchant": ["kill", "deliver", "fetch", "fetch_trade_goods", "deliver_cargo", "kill_bandits", "fetch_materials_rare", "fetch_simple", "deliver_local"], # Added generic fetch/deliver
        "village_elder": ["kill", "deliver", "fetch", "kill_major_threats", "investigate_problems", "deliver_official", "fetch_historical", "kill_nearby_threats", "deliver_local"], # Added generic kill/deliver
        "guard": ["kill", "deliver", "fetch", "kill_any_hostile", "patrol_area", "deliver_reports", "kill_nearby_threats"], # Added generic kill
        "villager": ["kill", "deliver", "fetch", "fetch_simple", "kill_pests", "deliver_local", "fetch_ingredients"] # Broadened slightly
    },

    # Mapping from broad quest types to specific interests for giver selection
    "quest_type_interest_map": {
        "kill": ["kill_nearby_threats", "kill_pests", "kill_major_threats", "kill_any_hostile", "kill_bandits"],
        "fetch": ["fetch_materials_metal", "fetch_materials_ore", "fetch_materials_hide", "fetch_ingredients", "fetch_consumables", "fetch_trade_goods", "fetch_materials_rare", "fetch_historical", "fetch_simple"],
        "deliver": ["deliver_messages", "deliver_cargo", "deliver_official", "deliver_local", "deliver_reports"]
    },
    # Debug mode for quest generation/tracking
    "debug": True
}