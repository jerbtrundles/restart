"""
core/config.py
Configuration settings for the game with enhanced text system support.
"""

# Display settings
import os


SCREEN_WIDTH = 1600
SCREEN_HEIGHT = 920
FONT_SIZE = 18
LINE_SPACING = 5
INPUT_HEIGHT = 30

# Colors
TEXT_COLOR = (255, 255, 255)  # White
BG_COLOR = (0, 0, 0)  # Black
INPUT_BG_COLOR = (50, 50, 50)  # Dark gray

COLOR_PURPLE = (255, 0, 255)
COLOR_RED = (255, 0, 0)
COLOR_ORANGE = (255, 165, 0)
COLOR_YELLOW = (255, 255, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_BLUE = (0, 0, 255)
COLOR_DARK_BLUE = (0, 0, 128)
COLOR_CYAN = (0, 255, 255)
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (192, 192, 192)
COLOR_BEIGE = (245, 222, 179)
COLOR_STEEL_BLUE = (173, 216, 230)
COLOR_DEFAULT = COLOR_WHITE

FORMAT_PURPLE = "[[PURPLE]]"
FORMAT_RED = "[[RED]]"
FORMAT_ORANGE = "[[ORANGE]]"
FORMAT_YELLOW = "[[YELLOW]]"
FORMAT_GREEN = "[[GREEN]]"
FORMAT_BLUE = "[[BLUE]]"
FORMAT_DARK_BLUE = "[[DARK_BLUE]]"
FORMAT_GRAY = "[[GRAY]]"
FORMAT_BEIGE = "[[BEIGE]]"
FORMAT_STEEL_BLUE = "[[STEEL_BLUE]]"
FORMAT_CYAN = "[[CYAN]]"
FORMAT_WHITE = "[[WHITE]]"
FORMAT_RESET = "[[/]]"

FORMAT_ERROR = FORMAT_RED
FORMAT_TITLE = FORMAT_YELLOW
FORMAT_HIGHLIGHT = FORMAT_GREEN
FORMAT_SUCCESS = FORMAT_GREEN
FORMAT_CATEGORY = FORMAT_CYAN
FORMAT_FRIENDLY_NPC = FORMAT_BEIGE

# Default color values for format codes (RGB)
DEFAULT_COLORS = {
    FORMAT_PURPLE: COLOR_PURPLE,
    FORMAT_RED: COLOR_RED,
    FORMAT_ORANGE: COLOR_ORANGE,
    FORMAT_YELLOW: COLOR_YELLOW,
    FORMAT_GREEN: COLOR_GREEN,
    FORMAT_BLUE: COLOR_BLUE,
    FORMAT_DARK_BLUE: COLOR_DARK_BLUE,
    FORMAT_STEEL_BLUE: COLOR_STEEL_BLUE,
    FORMAT_GRAY: COLOR_GRAY,
    FORMAT_CYAN: COLOR_CYAN,
    FORMAT_WHITE: COLOR_WHITE,
    FORMAT_RESET: COLOR_DEFAULT,
    FORMAT_FRIENDLY_NPC: COLOR_BEIGE
}

SEMANTIC_FORMAT = {
    "TITLE": FORMAT_ORANGE,
    "CATEGORY": FORMAT_BLUE,
    "HIGHLIGHT": FORMAT_CYAN,
    "SUCCESS": FORMAT_GREEN,
    "ERROR": FORMAT_RED,
    "NEUTRAL": FORMAT_YELLOW,
    "DEFAULT": FORMAT_RESET
}

# Scrolling settings
SCROLL_SPEED = 3  # Lines to scroll per mouse wheel movement
MAX_SCROLL_HISTORY = 1000  # Maximum number of lines to keep in scroll history

# Game settings
DEFAULT_WORLD_FILE = "world.json"

# Text display settings
MAX_PARAGRAPH_WIDTH = 80  # Maximum width for wrapped text
TEXT_MARGIN = 10  # Margin from edge of screen
PARAGRAPH_SPACING = 10  # Space between paragraphs

# History settings
COMMAND_HISTORY_SIZE = 50  # Number of commands to keep in history

# Debug settings
DEBUG_COLOR = (255, 0, 0)  # Red for debug text
DEBUG_IGNORE_PLAYER_COMBAT = False
DEBUG_SHOW_LEVEL = True

DEFAULT_SAVE_FILE = "default_save.json"
DATA_DIR = "data"
SAVE_GAME_DIR = os.path.join(DATA_DIR, "saves")
REGION_DIR = os.path.join(DATA_DIR, "regions")
ITEM_TEMPLATE_DIR = os.path.join(DATA_DIR, "items")
NPC_TEMPLATE_DIR = os.path.join(DATA_DIR, "npcs")

# --- Player Health Calculation ---
PLAYER_BASE_HEALTH = 80
PLAYER_CON_HEALTH_MULTIPLIER = 2.0 # HP gained per point of CON at level 1
PLAYER_LEVEL_HEALTH_BASE_INCREASE = 5 # Base HP gain per level (before CON)
PLAYER_LEVEL_CON_HEALTH_MULTIPLIER = 0.5 # Extra HP gain per level per point of CON

# --- NPC Health Calculation ---
NPC_BASE_HEALTH = 30 # Lower base for NPCs?
NPC_CON_HEALTH_MULTIPLIER = 1.5
NPC_LEVEL_HEALTH_BASE_INCREASE = 3
NPC_LEVEL_CON_HEALTH_MULTIPLIER = 0.3

# Multipliers applied based on Attacker's level relative to Target's level
# Example: If Player attacks a RED target, player's hit chance is multiplied by 0.85, damage by 0.75.
# Example: If Player defeats a GREEN target, XP gained is multiplied by 0.5.
LEVEL_DIFF_COMBAT_MODIFIERS = {
    # Tier:   (Hit Chance Multiplier, Damage Dealt Multiplier, XP Multiplier)
    "purple": (0.70, 0.60, 2.50), # Hardest to hit, deal much less dmg, gain most XP
    "red":    (0.85, 0.75, 1.75),
    "orange": (0.95, 0.90, 1.25),
    "yellow": (1.00, 1.00, 1.00), # Baseline
    "blue":   (1.05, 1.10, 0.80),
    "green":  (1.15, 1.25, 0.50),
    "gray":   (1.25, 1.40, 0.20), # Easiest to hit, deal much more dmg, gain least XP
}

# Define Min/Max values for clamping
MIN_HIT_CHANCE = 0.05 # 5% minimum chance to hit
MAX_HIT_CHANCE = 0.95 # 95% maximum chance to hit
MIN_XP_GAIN = 1       # Always gain at least 1 XP
MIN_ATTACK_COOLDOWN = 0.5 # Prevent excessively fast attacks

MAX_BUFFER_LINES = 50 # keep this much history

# --- Trading Settings ---
DEFAULT_VENDOR_SELL_MULTIPLIER = 2.0  # Player Buys: Item Value * 2.0 (default)
DEFAULT_VENDOR_BUY_MULTIPLIER = 0.4   # Player Sells: Item Value * 0.4 (default)
VENDOR_CAN_BUY_JUNK = True
VENDOR_CAN_BUY_ALL_ITEMS = False # Should vendors only buy certain types?

REPAIR_COST_PER_VALUE_POINT = 0.1 # e.g., 10% of item value to repair fully
REPAIR_MINIMUM_COST = 1

# core/config.py
# ... (existing imports and constants) ...

# --- Player Defaults & Base Values ---
PLAYER_DEFAULT_NAME = "Adventurer"
PLAYER_DEFAULT_MAX_MANA = 50
PLAYER_DEFAULT_RESPAWN_REGION = "town"
PLAYER_DEFAULT_RESPAWN_ROOM = "town_square"
PLAYER_BASE_XP_TO_LEVEL = 100
PLAYER_BASE_ATTACK_POWER = 5
PLAYER_BASE_DEFENSE = 3
PLAYER_BASE_ATTACK_COOLDOWN = 2.0 # Base cooldown in seconds
PLAYER_BASE_MANA_REGEN_RATE = 1.0 # Per second
PLAYER_BASE_HEALTH_REGEN_RATE = 1.0 # Per second (Example, adjust as needed)
PLAYER_DEFAULT_KNOWN_SPELLS = ["magic_missile", "minor_heal"] # Use a list or tuple
PLAYER_MAX_COMBAT_MESSAGES = 10
PLAYER_DEFAULT_STATS = {
    "strength": 10, "dexterity": 10, "intelligence": 10,
    "wisdom": 10, "constitution": 10, "agility": 10,
    "spell_power": 5, "magic_resist": 2
}

# --- Player Leveling & Stats ---
PLAYER_XP_TO_LEVEL_MULTIPLIER = 1.5
PLAYER_LEVEL_UP_STAT_INCREASE = 1 # Assuming uniform increase for now
PLAYER_MANA_LEVEL_UP_MULTIPLIER = 1.15
PLAYER_MANA_LEVEL_UP_INT_DIVISOR = 2 # Higher INT gives more mana per level
PLAYER_MANA_REGEN_WISDOM_DIVISOR = 20 # Higher WIS gives faster mana regen
PLAYER_HEALTH_REGEN_STRENGTH_DIVISOR = 25 # Higher STR gives faster health regen (example)
PLAYER_ATTACK_POWER_STR_DIVISOR = 3 # Higher STR increases attack power
PLAYER_DEFENSE_DEX_DIVISOR = 4 # Higher DEX increases defense

# --- Player Combat ---
PLAYER_BASE_HIT_CHANCE = 0.85 # Base chance before modifiers
PLAYER_ATTACK_DAMAGE_VARIATION_RANGE = (-1, 2) # Min/Max added/subtracted from base attack

# --- NPC Defaults & Base Values ---
NPC_DEFAULT_BEHAVIOR = "stationary"
NPC_DEFAULT_MAX_MANA = 0 # <<< NEW
NPC_MANA_LEVEL_UP_MULTIPLIER = 1.10 # <<< NEW
NPC_MANA_LEVEL_UP_INT_DIVISOR = 3 # <<< NEW
NPC_MANA_REGEN_WISDOM_DIVISOR = 22 # <<< NEW
NPC_BASE_MANA_REGEN_RATE = 0.5 # <<< NEW
NPC_LOW_MANA_RETREAT_THRESHOLD = 0.20 # Retreat if below 20% mana <<< NEW
NPC_DEFAULT_WANDER_CHANCE = 0.3
NPC_DEFAULT_MOVE_COOLDOWN = 10 # Seconds
NPC_DEFAULT_AGGRESSION = 0.0
NPC_DEFAULT_WANDER = 0.3
NPC_DEFAULT_FLEE_THRESHOLD = 0.2 # Flee below 20% health
NPC_DEFAULT_RESPAWN_COOLDOWN = 600 # Seconds (10 minutes)
NAMED_NPC_RESPAWN_COOLDOWN = 60 # seconds until important NPC respawn after death
NPC_DEFAULT_COMBAT_COOLDOWN = 3.0 # Seconds between any combat action
NPC_DEFAULT_ATTACK_COOLDOWN = 3.0 # Seconds between physical attacks
NPC_DEFAULT_SPELL_CAST_CHANCE = 0.0 # 30% chance to try casting a spell if available
NPC_BASE_ATTACK_POWER = 3
NPC_BASE_DEFENSE = 2
NPC_MAX_COMBAT_MESSAGES = 5
NPC_DEFAULT_STATS = { # Defaults if template is missing them
    "strength": 8, "dexterity": 8, "intelligence": 5,
    "wisdom": 5, "constitution": 8, "agility": 8,
    "spell_power": 0, "magic_resist": 0
}
NPC_HEALTH_DESC_THRESHOLDS = (0.25, 0.50, 0.75) # Corresponds to severely injured, wounded, minor injuries

# --- NPC Combat ---
NPC_BASE_HIT_CHANCE = 0.80 # Slightly lower than player base?
NPC_ATTACK_DAMAGE_VARIATION_RANGE = (-1, 1)

# --- Combat Mechanics (Shared) ---
HIT_CHANCE_AGILITY_FACTOR = 0.02 # 2% hit change per point of Agility difference
MINIMUM_DAMAGE_TAKEN = 1 # Minimum damage applied after reduction (if any damage got through)

# --- Item Defaults & Mechanics ---
ITEM_DURABILITY_LOSS_ON_HIT = 1 # How much durability weapon loses per hit
ITEM_DURABILITY_LOW_THRESHOLD = 0.30 # % for 'worn' status display

# --- Experience Point Calculation ---
XP_GAIN_HEALTH_DIVISOR = 5 # Base XP = Target Max Health / Divisor
XP_GAIN_LEVEL_MULTIPLIER = 5 # Base XP += Target Level * Multiplier
SPELL_XP_GAIN_HEALTH_DIVISOR = 4 # Different divisor for spell kills?
SPELL_XP_GAIN_LEVEL_MULTIPLIER = 6 # Different multiplier for spell kills?

# --- Magic ---
SPELL_DEFAULT_DAMAGE_TYPE = "magical"
SPELL_DAMAGE_VARIATION_FACTOR = 0.1 # e.g., +/- 10%
MINIMUM_SPELL_EFFECT_VALUE = 1

# --- UI & Display ---
FONT_FAMILY = "helvetica"
TITLE_FONT_SIZE_MULTIPLIER = 2
TARGET_FPS = 30
LOAD_SCREEN_MAX_SAVES = 10
LOAD_SCREEN_COLUMN_WIDTH_FACTOR = 0.6 # 60% of screen width
STATUS_AREA_HEIGHT = 30 # Pixel height for HP/MP/XP bars area
GAME_OVER_MESSAGE_LINE1 = "YOU HAVE DIED"
GAME_OVER_MESSAGE_LINE2 = "Press 'R' to Respawn or 'Q' to Quit to Title"
HELP_MAX_COMMANDS_PER_CATEGORY = 5
VENDOR_LIST_ITEM_NAME_WIDTH = 25 # Character width for item names in 'list'
VENDOR_LIST_PRICE_WIDTH = 4 # Character width for prices in 'list'

# --- Command Settings ---
QUEST_BOARD_ALIASES = ["board", "quest board", "notice board"] # For 'look' command
USE_COMMAND_PREPOSITIONS = ["on"]
FOLLOW_COMMAND_STOP_ALIASES = ["stop", "none"]
EQUIP_COMMAND_SLOT_PREPOSITION = "to"
PUT_COMMAND_PREPOSITION = "in"
CAST_COMMAND_PREPOSITION = "on"
TARGET_SELF_ALIASES = ["self", "me"] # Player name is checked separately
GET_COMMAND_PREPOSITION = "from"
STOPTRADE_COMMAND_ALIASES = ["stop", "done"]
GIVE_COMMAND_PREPOSITION = "to"

# --- Inventory Defaults ---
DEFAULT_INVENTORY_MAX_SLOTS = 20
DEFAULT_INVENTORY_MAX_WEIGHT = 100.0

# --- Container Defaults ---
CONTAINER_EMPTY_MESSAGE = "  (Empty)"

# --- Vendor Settings ---
VENDOR_MIN_BUY_PRICE = 1 # Minimum price player pays when buying
VENDOR_MIN_SELL_PRICE = 0 # Minimum price player gets when selling (can be 0)
VENDOR_ID_HINTS = ["shop", "merchant", "bartender"] # Lowercase hints in NPC IDs

# --- World Settings ---
WORLD_UPDATE_INTERVAL = 0.5 # Seconds between world update ticks

# --- Monster Spawner Core Settings ---
SPAWN_INTERVAL_SECONDS = 1.0
SPAWN_CHANCE_PER_TICK = 1.0
SPAWN_ROOMS_PER_MONSTER = 5
SPAWN_MIN_MONSTERS_PER_REGION = 1
SPAWN_MAX_MONSTERS_PER_REGION_CAP = 10
SPAWN_NO_SPAWN_ROOM_KEYWORDS = [
    "town_square", "tavern", "inn", "shop", "temple", "shrine", "home",
    "general_store", "blacksmith", "farmhouse_yard", "shepherds_hut"
]
SPAWN_DEBUG = False

# --- Time Plugin Settings ---
TIME_PLUGIN_UPDATE_THRESHOLD = 0.001 # Minimum game_time difference to trigger update
TIME_PLUGIN_MAX_CATCHUP_SECONDS = 5.0 # Max real seconds to process in one tick

# --- Weather Plugin Settings ---
WEATHER_PERSISTENCE_CHANCE = 0.3 # Chance weather *doesn't* change
WEATHER_TRANSITION_CHANGE_CHANCE = 0.5 # Chance weather changes at dawn/dusk
WEATHER_INTENSITY_WEIGHTS = [0.4, 0.3, 0.2, 0.1] # Weights for mild, moderate, strong, severe

# --- Equipment Slots Definition ---
# Defines the standard slots and the types primarily associated with them
# Player.valid_slots_for_type uses this as a base
EQUIPMENT_SLOTS = [
    "main_hand", "off_hand", "head", "body", "hands", "feet", "neck"
]
# Mapping from Item base class name to default valid slots
EQUIPMENT_VALID_SLOTS_BY_TYPE = {
    "Weapon": ["main_hand", "off_hand"],
    "Armor": ["body", "head", "feet", "hands", "neck"], # Neck for Amulets maybe?
    "Shield": ["off_hand"], # Example if you add Shield class later
    "Item": [] # Base Item has no default slot unless properties define it
}

PLAYER_REGEN_TICK_INTERVAL = 1.0
PLAYER_STATUS_HEALTH_CRITICAL_THRESHOLD = 25
PLAYER_STATUS_HEALTH_LOW_THRESHOLD = 50
DEFAULT_PLAYER_NAME = 'Adventurer'

FACTIONS = ["player", "friendly", "neutral", "hostile", "player_minion"]

# Defines the default relationship score from the "viewer" faction (outer key)
# to the "target" faction (inner key).
# 100: Allied, 0: Neutral, -100: Hostile
FACTION_RELATIONSHIP_MATRIX = {
    "player": {
        "player": 100, "player_minion": 100, "friendly": 100,
        "neutral": 0, "hostile": -100
    },
    "player_minion": {
        "player": 100, "player_minion": 100, "friendly": 100,
        "neutral": 0, "hostile": -100
    },
    "friendly": { # Villagers, etc.
        "player": 100, "player_minion": 100, "friendly": 100,
        "neutral": 0, "hostile": -100
    },
    "neutral": { # Animals, ambient creatures
        "player": 0, "player_minion": 0, "friendly": 0,
        "neutral": 0, "hostile": 0
    },
    "hostile": { # Goblins, skeletons, etc.
        "player": -100, "player_minion": -100, "friendly": -100,
        "neutral": -100, "hostile": 0  # <<< THE KEY FIX: Hostiles are NEUTRAL to each other
    }
}

SPELL_EFFECT_TYPES = ["damage", "heal", "buff", "debuff", "summon"] # Added summon
NPC_BEHAVIOR_TYPES = ["stationary", "wanderer", "patrol", "follower", "scheduled", "aggressive", "minion"] # Added minion
PLAYER_DEFAULT_MAX_TOTAL_SUMMONS = 100 # Example total limit

# --- NPC Naming ---
# Example lists - expand these considerably!
VILLAGER_FIRST_NAMES_MALE = [
    "Alden", "Bram", "Corbin", "Darian", "Edric", "Finnian", "Gareth", "Hal", "Ivor", "Joric",
    "Kael", "Loric", "Merrick", "Nyle", "Orin", "Perrin", "Quill", "Roric", "Sten", "Torvin", "Ulric", "Vance"
]
VILLAGER_FIRST_NAMES_FEMALE = [
    "Anya", "Briar", "Carys", "Dena", "Elara", "Fiora", "Gwyn", "Helsa", "Isolde", "Jessa",
    "Kyra", "Lyra", "Moira", "Nerys", "Oriana", "Petra", "Quenna", "Rowan", "Seraphina", "Tamsin", "Una", "Verna"
]
VILLAGER_LAST_NAMES = [
    "Applewood", "Briarwood", "Cobblestone", "Deepwater", "Eastcroft", "Fairwind", "Greenbottle", "Highhill",
    "Ironhand", "Jumblewood", "Keeneye", "Longbridge", "Meadowlight", "Northgate", "Oakhart", "Puddlefoot",
    "Quickstep", "Riverbend", "Stonehand", "Tanglebrook", "Underhill", "Vale", "Westwater", "Yarrow"
]

# --- Status Effect Settings ---
EFFECT_DEFAULT_TICK_INTERVAL = 3.0 # How often DoTs tick by default (seconds)
EFFECT_POISON_DAMAGE_TYPE = "poison" # Damage type for standard poison
EFFECT_FIRE_DAMAGE_TYPE = "fire"
EFFECT_COLD_DAMAGE_TYPE = "cold"
EFFECT_ELECTRIC_DAMAGE_TYPE = "electric"
EFFECT_DISEASE_DAMAGE_TYPE = "disease" # <<< ADDED THIS LINE

STATUS_PANEL_WIDTH = 400
STATUS_PANEL_PADDING = 5

SIDE_PANEL_WIDTH = 250 # <<< NEW: Width for left and right status panels
STATUS_PANEL_PADDING = 5

NPC_BASE_XP_TO_LEVEL = 150 # NPCs might level a bit slower?
NPC_XP_TO_LEVEL_MULTIPLIER = 1.6
NPC_LEVEL_UP_STAT_INCREASE = 1 # Simple stat gain for now
NPC_LEVEL_UP_HEALTH_HEAL_PERCENT = 0.5 # Heal 50% on level up

# --- Status Effect Flavor Text ---
# Used for displaying DoT effects on NPCs to the player.
NPC_DOT_FLAVOR_MESSAGES = [
    "{npc_name} winces in pain from the {effect_name}.",
    "The {effect_name} visibly weakens {npc_name}.",
    "{npc_name} stumbles as the {effect_name} takes its toll.",
    "A flicker of pain crosses {npc_name}'s face due to the {effect_name}.",
    "{npc_name} lets out a pained grunt from the effects of the {effect_name}."
]

# --- Quest System Settings (Migrated from Plugin) ---
QUEST_SYSTEM_CONFIG = {
    "quest_board_locations": [
        "town:town_square",
        "portbridge:harbor_district" # Example of a second location
    ],
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
    "npc_quest_interests": {
        "blacksmith": ["kill", "deliver", "fetch", "kill_nearby_threats", "fetch_materials_metal", "fetch_materials_ore", "fetch_materials_hide", "fetch_simple", "kill_pests"],
        "tavern_keeper": ["kill", "deliver", "fetch", "fetch_ingredients", "fetch_consumables", "kill_pests", "deliver_messages", "fetch_simple"],
        "merchant": ["kill", "deliver", "fetch", "fetch_trade_goods", "deliver_cargo", "kill_bandits", "fetch_materials_rare", "fetch_simple", "deliver_local"],
        "village_elder": ["kill", "deliver", "fetch", "kill_major_threats", "investigate_problems", "deliver_official", "fetch_historical", "kill_nearby_threats", "deliver_local"],
        "guard": ["kill", "deliver", "fetch", "kill_any_hostile", "patrol_area", "deliver_reports", "kill_nearby_threats"],
        "villager": ["kill", "deliver", "fetch", "fetch_simple", "kill_pests", "deliver_local", "fetch_ingredients"]
    },
    # --- Mapping from broad quest types to specific interests for giver selection ---
    "quest_type_interest_map": {
        "kill": ["kill_nearby_threats", "kill_pests", "kill_major_threats", "kill_any_hostile", "kill_bandits"],
        "fetch": ["fetch_materials_metal", "fetch_materials_ore", "fetch_materials_hide", "fetch_ingredients", "fetch_consumables", "fetch_trade_goods", "fetch_materials_rare", "fetch_historical", "fetch_simple"],
        "deliver": ["deliver_messages", "deliver_cargo", "deliver_official", "deliver_local", "deliver_reports"]
    },
    # --- Debug mode for quest generation/tracking ---
    "debug": True
}

# --- Core Time System Settings (Migrated from Plugin) ---
TIME_REAL_SECONDS_PER_GAME_DAY = 1200  # 20 minutes
TIME_DAYS_PER_WEEK = 7
TIME_DAYS_PER_MONTH = 30
TIME_MONTHS_PER_YEAR = 12
TIME_DAY_NAMES = [
    "Moonday", "Tideday", "Windday", "Thunderday",
    "Fireday", "Starday", "Sunday"
]
TIME_MONTH_NAMES = [
    "Deepwinter", "Icemelt", "Springbloom", "Rainshower",
    "Meadowgrow", "Highsun", "Fireheat", "Goldenfield",
    "Harvestide", "Leaffall", "Frostwind", "Darknight"
]
TIME_DAWN_HOUR = 6
TIME_DAY_HOUR = 8
TIME_DUSK_HOUR = 18
TIME_NIGHT_HOUR = 20
TIME_UPDATE_THRESHOLD = 0.001
TIME_MAX_CATCHUP_SECONDS = 5.0

NPC_HEALTH_DESC_THRESHOLDS = (0.25, 0.50, 0.75) # Corresponds to severely injured, wounded, minor injuries
NPC_HEALER_HEAL_THRESHOLD = 0.75 # NEW: Priests will heal allies below this health %
