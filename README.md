# Pygame Text RPG Engine

A robust, modular, and data-driven Text-Based RPG engine built with Python and Pygame. While visually presented as a classic MUD (Multi-User Dungeon), it features a modern hybrid UI with clickable text, hotbars, and mouse interaction, sitting on top of a deep simulation of world mechanics.

## 🚀 Getting Started

### Prerequisites
*   Python 3.11+
*   Pygame (`pip install pygame`)
*   Transformers / PyTorch (Optional, for LLM-based ambient flavor text)

### Running the Game
```bash
python main.py
```
*   **Arguments:**
    *   `--save <filename>`: Load a specific save file (default: `default_save.json`).

## ⚙️ Engine Systems

This engine is built on a Component-Entity-System architecture heavily reliant on JSON data definitions.

### 1. World & Environment
*   **Dynamic Region Generation:** Procedural generation of dungeons and areas using 3D geometric algorithms.
*   **Time System:** Full calendar cycle (Day/Night, Seasons, Years). Time passes in "ticks" or via specific actions.
*   **Dynamic Weather:** Weather patterns (Rain, Storm, Snow, Clear) flow based on the season and can affect gameplay (e.g., fire damage is weaker in rain).
*   **Reactive Environment:** Rooms act as game objects. Casting "Ice" on a water room freezes it; "Fire" burns webs.
*   **Hazard System:** Rooms can contain hazards (Heat, Poison Gas) that deal DoT unless the player has specific resistances.

### 2. Entities & AI
*   **NPC Schedules:** NPCs have daily routines (Sleep, Work, Eat, Socialize) and physically move between rooms based on the time of day.
*   **Faction & Reputation:** A relationship matrix tracks how factions feel about each other. Player actions (killing friendlies or enemies) dynamically alter reputation, changing NPCs from Neutral to Hostile or Friendly.
*   **Combat AI:** Enemies can flee when low on health, retreat to mana fonts, assist allies (Social Aggro), or use specific spells based on the situation.
*   **Minions:** Players can summon minions that follow them, attack aggressors, and persist across regions.

### 3. Combat & Magic
*   **Grand Elemental System:** 11+ Damage types (Physical, Fire, Ice, Holy, Shadow, etc.) with a rock-paper-scissors relationship logic (e.g., Water douses Fire).
*   **Spell Engine:** Support for Single Target, AoE, HoT (Heal over Time), DoT (Damage over Time), Buffs, Debuffs, and Utility (Unlock, Cleanse).
*   **Status Effects:** Complex tagging system. Effects like "Blind" cap hit chance; "Silence" prevents casting.
*   **Interactions:** Effects interact (e.g., casting "Cleanse" removes tags `poison` and `curse` but leaves `buffs` intact).

### 4. Items & Economy
*   **Procedural Loot:** Diablo-style item generation with Prefixes (e.g., "Sharp", "Fiery") and Suffixes (e.g., "of the Bear", "of Vampirism") that modify stats and add passive effects.
*   **Set Bonuses:** Equipping multiple items from the same named set grants cumulative stat bonuses.
*   **Crafting & Salvaging:** Breakdown items into raw materials (`salvage`) and build new ones using recipes (`craft`) at specific stations (Anvil, Alchemy Table).
*   **Economy:** Vendors have dynamic inventories, buy/sell multipliers, and persistent stock (items you sell stay on the vendor).
*   **Durability:** Weapons and armor degrade on use and require repair.

### 5. Quest System
*   **Dynamic Generation:** NPCs procedurally generate quests based on their interests and the world state (Kill, Fetch, Deliver).
*   **Instance Quests:** Accepting specific quests generates a temporary, instanced dungeon region with a portal entrance.
*   **Quest Board:** A refreshing board of tasks available in major hubs.

---

## 🎮 Controls & UI

*   **Keyboard:** Type commands and press `ENTER`.
    *   `UP/DOWN`: Scroll through command history.
    *   `TAB`: Auto-complete commands.
    *   `PAGE UP/DOWN`: Scroll the text log.
*   **Mouse:**
    *   **Clickable Text:** Click highlighted text (Items, NPCs, Exits) to interact immediately.
    *   **Panels:** Drag and drop UI panels to customize your layout.
    *   **Context Menu:** Right-click objects for a list of actions (Look, Take, Attack).

---

## 📜 Command Reference

### Movement
*   `go <dir>`, `n`, `s`, `e`, `w`, `u`, `d` - Move in a direction.
*   `enter`, `out` - Enter or exit buildings/portals.
*   `climb`, `swim` - Traverse specific terrain (may require skills).

### Interaction & Items
*   `look` / `l` - Look at the room.
*   `look <target>` / `x <target>` - Examine an item or NPC.
*   `take <item>` / `get <item>` - Pick up an item (supports `take all`).
*   `drop <item>` - Drop an item on the ground.
*   `put <item> in <container>` - Store items.
*   `open <container>` / `close <container>` - Interact with chests/doors.
*   `use <item>` - Drink potions, read scrolls, etc.
*   `equip <item>` / `unequip <item>` - Manage gear.
*   `pick <direction/container>` - Attempt to pick a lock (requires Lockpick).
*   `pull <object>` - Interact with levers or switches.
*   `gather <node>` - Harvest resources (requires tools like Pickaxe).

### Combat
*   `attack <target>` / `kill <target>` - Initiate physical combat.
*   `cast <spell> [on <target>]` - Cast a spell. Target defaults to enemy if in combat.
*   `stop` - Stop attacking or auto-traveling.

### Social & Trade
*   `talk <npc>` - Start a conversation.
*   `ask <npc> <topic>` - Ask about a specific keyword (e.g., "job", "rumors").
*   `trade <npc>` - Open the trade interface.
*   `buy <item> [qty]` / `sell <item> [qty]` - Transact with vendors.
*   `repair <item>` - Pay an NPC to repair gear.
*   `give <item> to <npc>` - Hand over items (used for quests).
*   `follow <npc>` - Start following an NPC.
*   `guide <npc>` - Ask a quest giver to lead you to the quest location.

### Crafting & Skills
*   `recipes` - List known recipes and nearby stations.
*   `craft <recipe_id>` - Create an item.
*   `salvage <item>` - Break an item down into materials.
*   `skills` - View your skill proficiency (e.g., Mining, Lockpicking).

### Information
*   `inventory` / `i` - Show inventory.
*   `status` / `st` - Show health, mana, stats, and active effects.
*   `spells` - List known spells and cooldowns.
*   `quest` / `journal` - View active quests.
*   `time` / `calendar` - Check game time and date.
*   `weather` - Check current weather conditions.
*   `map` / `minimap` - Toggle the ASCII minimap panel.
*   `help` - Show command categories.

### System
*   `save [filename]` - Save the game.
*   `load [filename]` - Load a game.
*   `quit` - Return to title screen.
*   `view <panel> <on/off>` - Toggle UI panels.
*   `invmode <text/icon/hybrid>` - Change inventory display style.

---

## 🕹️ Gameplay Example

**1. The Setup**
You start in the Town Square. You check your status and gear up.
```text
> status
Name: Adventurer | Class: Warrior | Level: 1
Health: 100/100 | Mana: 50/50
Stats: STR 12, DEX 10, INT 8
Equipped: Worn Sword (Main Hand)

> i
You are carrying:
- 2x Small Healing Potion
- 1x Iron Ration
```

**2. Getting a Quest**
You see a board and an Elder.
```text
> look board
Available Quests:
1. Bounty: Giant Rats (Kill 5) - Reward: 50g
2. Investigation: The Old Cellar (Instance) - Reward: Rare Item

> accept quest 2
You accept the quest. A shimmering portal appears to the North!
Elder Thorne approaches you. "The cellar has been overrun. Please clear it out."
```

**3. The Dungeon**
You enter the procedural instance.
```text
> north
You enter The Old Cellar.
It is very dark here. The air smells of rot.

> cast light
You cast Light! The room brightens.
You see: 2x Giant Rat, 1x Rusty Chest (Locked).

> attack rat
You attack the Giant Rat with your Worn Sword for 8 physical damage.
The Giant Rat bites you for 3 physical damage.
```

**4. Loot and Mechanics**
After the fight, you find loot.
```text
> loot rat
You find:
- Rat Tail
- 2 Gold

> pick chest
You successfully pick the lock! (Skill: Lockpicking increased to 2)
You open the chest. Inside you see:
- Sharp Iron Dagger of Fire

> look dagger
Sharp Iron Dagger of Fire
Damage: 12 (+2 Fire)
Value: 150g
```

**5. Crafting & Economy**
You return to town to sell junk and salvage gear.
```text
> salvage worn sword
You break down the Worn Sword into: 1x Iron Scrap.

> trade merchant
> sell rat tail
You sell Rat Tail for 2 gold.

> craft
Nearby: Anvil
Recipes:
- Iron Dagger (Requires: 2x Iron Scrap, 1x Leather Scrap) [Locked]
- Iron Sword (Requires: 3x Iron Scrap, 1x Leather Scrap) [Ready]

> craft craft_iron_sword
You hammer the metal violently... (Rolled 45 vs DC 20)
Successfully crafted 1 x Iron Sword! Your Crafting skill increased to 2!

> equip iron sword
(You unequip the Worn Sword)
You equip the Iron Sword in your Main Hand.
```

---

## 📂 Project Structure

The engine is designed to be data-driven. Logic resides in `engine/`, while content resides in `data/`.

```text
├── main.py                 # Entry point
├── engine/
│   ├── config/             # Configuration constants (combat, display, etc.)
│   ├── core/               # Main game loop, input handling, time, weather
│   ├── commands/           # Command parsing and logic handlers
│   ├── items/              # Item classes, Inventory, Loot Generation
│   ├── magic/              # Spells, Effects, and Registry
│   ├── npcs/               # NPC logic, AI, and pathfinding
│   ├── player/             # Player class and persistence logic
│   ├── ui/                 # Pygame rendering, panels, and menus
│   ├── utils/              # Pathfinding (A*), text formatting
│   └── world/              # Room, Region, and Spawner logic
├── data/
│   ├── combat/             # Elemental relationships and flavor text
│   ├── crafting/           # Recipe definitions (*.json)
│   ├── items/              # Item templates (*.json) & Sets
│   ├── magic/              # Spell definitions (*.json)
│   ├── npcs/               # NPC templates (*.json)
│   ├── player/             # Class definitions (Warrior, Mage, etc.)
│   ├── quests/             # Instance quest templates
│   └── regions/            # Region definitions and dynamic themes
└── tests/                  # Unit and integration tests
```

---

## 🛠️ Modding & Adding Content

Because the engine uses JSON for almost all content, you can add new items, monsters, and spells without writing Python code.

### 1. Adding a New Item
Create a file in `data/items/my_items.json`:
```json
{
  "item_fire_brand": {
    "type": "Weapon",
    "name": "Fire Brand",
    "description": "A sword wreathed in flame.",
    "weight": 4.0,
    "value": 500,
    "properties": {
      "damage": 12,
      "equip_slot": ["main_hand"],
      "equip_effect": {
        "type": "stat_mod",
        "modifiers": {"damage_fire": 5}
      }
    }
  }
}
```

### 2. Adding a New Spell
Create a file in `data/magic/my_spells.json`:
```json
{
  "meteor_swarm": {
    "name": "Meteor Swarm",
    "description": "Calls down meteors on all enemies.",
    "mana_cost": 50,
    "cooldown": 30.0,
    "level_required": 10,
    "target_type": "all_enemies",
    "effects": [
      {"type": "damage", "value": 40, "damage_type": "fire"},
      {"type": "apply_dot", "dot_name": "Burn", "dot_damage_per_tick": 5}
    ]
  }
}
```

### 3. Creating a New Region
Create `data/regions/my_dungeon.json`:
```json
{
  "name": "The Dark Hold",
  "description": "An ancient fortress.",
  "rooms": {
    "entry": {
      "name": "The Gate",
      "description": "A massive iron gate stands here.",
      "exits": {"north": "hallway"}
    },
    "hallway": {
      "name": "Dark Hallway",
      "description": "Torches flicker on the walls.",
      "exits": {"south": "entry"},
      "initial_npcs": [{"template_id": "goblin"}]
    }
  },
  "spawner": {
    "monster_types": {"goblin": 5, "orc": 1},
    "level_range": [2, 5]
  }
}
```

---

## 🧪 Testing

The engine includes a comprehensive suite of unit and batch tests.

```bash
# Run all tests
python -m unittest discover tests

# Run specific batch tests (e.g., Loot System)
python -m unittest tests.batch.test_batch_loot
```

---

## 📄 License

This project is provided as-is for educational and development purposes.
```
