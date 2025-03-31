"""
player.py
Enhanced Player module for the MUD game with improved text formatting.
"""
from typing import List, Dict, Optional, Any
from items.inventory import Inventory
from utils.text_formatter import TextFormatter


class Player:
    """
    Represents the player character in the game.
    """
    def __init__(self, name: str):
        """
        Initialize a player.
        
        Args:
            name: The player's name.
        """
        self.name = name
        self.inventory = Inventory(max_slots=20, max_weight=100.0)
        self.health = 100
        self.max_health = 100
        self.stats = {
            "strength": 10,
            "dexterity": 10,
            "intelligence": 10
        }
        self.level = 1
        self.experience = 0
        self.experience_to_level = 100
        self.skills = {}  # Skill name to proficiency level mapping
        self.effects = []  # Temporary effects on the player
        self.quest_log = {}  # Quest ID to progress mapping
    
    def get_status(self) -> str:
        """
        Returns a string with the player's current status.
        
        Returns:
            A formatted status string.
        """
        # Format health with color based on percentage
        health_percent = (self.health / self.max_health) * 100
        health_text = f"{self.health}/{self.max_health}"
        
        if health_percent <= 25:
            health_display = f"{TextFormatter.FORMAT_ERROR}{health_text}{TextFormatter.FORMAT_RESET}"
        elif health_percent <= 50:
            health_display = f"{TextFormatter.FORMAT_HIGHLIGHT}{health_text}{TextFormatter.FORMAT_RESET}"
        else:
            health_display = f"{TextFormatter.FORMAT_SUCCESS}{health_text}{TextFormatter.FORMAT_RESET}"
        
        # Basic status information
        status = f"{TextFormatter.FORMAT_CATEGORY}Name:{TextFormatter.FORMAT_RESET} {self.name}\n"
        status += f"{TextFormatter.FORMAT_CATEGORY}Level:{TextFormatter.FORMAT_RESET} {self.level} (XP: {self.experience}/{self.experience_to_level})\n"
        status += f"{TextFormatter.FORMAT_CATEGORY}Health:{TextFormatter.FORMAT_RESET} {health_display}\n"
        
        # Stats with formatted title
        status += f"{TextFormatter.FORMAT_CATEGORY}Stats:{TextFormatter.FORMAT_RESET} "
        status += f"STR {self.stats['strength']}, "
        status += f"DEX {self.stats['dexterity']}, "
        status += f"INT {self.stats['intelligence']}\n"
        
        # Add effect information if there are any
        if self.effects:
            status += f"\n{TextFormatter.FORMAT_TITLE}Active Effects:{TextFormatter.FORMAT_RESET}\n"
            for effect in self.effects:
                # Show duration if present
                duration_text = ""
                if "duration" in effect and effect["duration"] > 0:
                    duration_text = f" ({effect['duration']} turns remaining)"
                
                status += f"- {effect['name']}{duration_text}: {effect['description']}\n"
        
        # Skills information if the player has any skills
        if self.skills:
            status += f"\n{TextFormatter.FORMAT_TITLE}Skills:{TextFormatter.FORMAT_RESET}\n"
            for skill, level in self.skills.items():
                status += f"- {skill}: {level}\n"
        
        # Quest log summary if the player has active quests
        if self.quest_log:
            status += f"\n{TextFormatter.FORMAT_TITLE}Active Quests:{TextFormatter.FORMAT_RESET} {len(self.quest_log)}\n"
        
        return status
    
    def gain_experience(self, amount: int) -> bool:
        """
        Award experience points to the player and check for level up.
        
        Args:
            amount: The amount of experience to gain.
            
        Returns:
            True if the player leveled up, False otherwise.
        """
        self.experience += amount
        
        if self.experience >= self.experience_to_level:
            self.level_up()
            return True
            
        return False
    
    def level_up(self) -> None:
        """Level up the player, increasing stats and resetting experience."""
        self.level += 1
        self.experience -= self.experience_to_level
        self.experience_to_level = int(self.experience_to_level * 1.5)  # Increase XP required for next level
        
        # Increase stats
        self.stats["strength"] += 1
        self.stats["dexterity"] += 1
        self.stats["intelligence"] += 1
        
        # Increase max health
        old_max_health = self.max_health
        self.max_health = int(self.max_health * 1.1)  # 10% health increase per level
        self.health += (self.max_health - old_max_health)  # Heal by the amount of max health increase
    
    def add_effect(self, name: str, description: str, duration: int, 
                  stat_modifiers: Dict[str, int] = None) -> None:
        """
        Add a temporary effect to the player.
        
        Args:
            name: The name of the effect.
            description: A description of what the effect does.
            duration: How many turns the effect lasts.
            stat_modifiers: Modifications to player stats while the effect is active.
        """
        self.effects.append({
            "name": name,
            "description": description,
            "duration": duration,
            "stat_modifiers": stat_modifiers or {}
        })
        
        # Apply stat modifiers
        if stat_modifiers:
            for stat, modifier in stat_modifiers.items():
                if stat in self.stats:
                    self.stats[stat] += modifier
    
    def update_effects(self) -> List[str]:
        """
        Update all active effects, reducing their duration and removing expired ones.
        
        Returns:
            A list of messages about effects that have expired.
        """
        messages = []
        expired_effects = []
        
        for effect in self.effects:
            effect["duration"] -= 1
            
            if effect["duration"] <= 0:
                expired_effects.append(effect)
                messages.append(f"The {effect['name']} effect has worn off.")
        
        # Remove expired effects and their stat modifiers
        for effect in expired_effects:
            self.effects.remove(effect)
            
            # Remove stat modifiers
            if "stat_modifiers" in effect:
                for stat, modifier in effect["stat_modifiers"].items():
                    if stat in self.stats:
                        self.stats[stat] -= modifier
        
        return messages
    
    def add_skill(self, skill_name: str, level: int = 1) -> None:
        """
        Add a new skill or increase an existing skill's level.
        
        Args:
            skill_name: The name of the skill.
            level: The level to set or add.
        """
        if skill_name in self.skills:
            self.skills[skill_name] += level
        else:
            self.skills[skill_name] = level
    
    def get_skill_level(self, skill_name: str) -> int:
        """
        Get the player's level in a specific skill.
        
        Args:
            skill_name: The name of the skill.
            
        Returns:
            The skill level, or 0 if the player doesn't have the skill.
        """
        return self.skills.get(skill_name, 0)
    
    def update_quest(self, quest_id: str, progress: Any) -> None:
        """
        Update the progress of a quest.
        
        Args:
            quest_id: The ID of the quest.
            progress: The new progress value.
        """
        self.quest_log[quest_id] = progress
    
    def get_quest_progress(self, quest_id: str) -> Optional[Any]:
        """
        Get the progress of a quest.
        
        Args:
            quest_id: The ID of the quest.
            
        Returns:
            The quest progress, or None if the quest is not in the log.
        """
        return self.quest_log.get(quest_id)
    
    def heal(self, amount: int) -> int:
        """
        Heal the player by the specified amount.
        
        Args:
            amount: Amount of health to restore
            
        Returns:
            The actual amount healed
        """
        old_health = self.health
        self.health = min(self.health + amount, self.max_health)
        return self.health - old_health
    
    def take_damage(self, amount: int) -> int:
        """
        Deal damage to the player.
        
        Args:
            amount: Amount of damage to deal
            
        Returns:
            The actual amount of damage taken
        """
        old_health = self.health
        self.health = max(self.health - amount, 0)
        return old_health - self.health
    
    def is_alive(self) -> bool:
        """
        Check if the player is alive.
        
        Returns:
            True if player has more than 0 health, False otherwise
        """
        return self.health > 0
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the player to a dictionary for serialization.
        
        Returns:
            A dictionary representation of the player.
        """
        return {
            "name": self.name,
            "inventory": self.inventory.to_dict(),
            "health": self.health,
            "max_health": self.max_health,
            "stats": self.stats,
            "level": self.level,
            "experience": self.experience,
            "experience_to_level": self.experience_to_level,
            "skills": self.skills,
            "effects": self.effects,
            "quest_log": self.quest_log
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Player':
        """
        Create a player from a dictionary.
        
        Args:
            data: The dictionary containing player data.
            
        Returns:
            A Player instance.
        """
        player = cls(data["name"])
        
        player.health = data.get("health", 100)
        player.max_health = data.get("max_health", 100)
        player.stats = data.get("stats", {"strength": 10, "dexterity": 10, "intelligence": 10})
        player.level = data.get("level", 1)
        player.experience = data.get("experience", 0)
        player.experience_to_level = data.get("experience_to_level", 100)
        player.skills = data.get("skills", {})
        player.effects = data.get("effects", [])
        player.quest_log = data.get("quest_log", {})
        
        # Load inventory if present
        if "inventory" in data:
            from items.inventory import Inventory
            player.inventory = Inventory.from_dict(data["inventory"])
        
        return player