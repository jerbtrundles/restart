# items/consumable.py
from core.config import FORMAT_ERROR, FORMAT_RESET, FORMAT_SUCCESS
from items.item import Item

class Consumable(Item):
    def __init__(self, obj_id: str = None, name: str = "Unknown Consumable",
                 description: str = "No description", weight: float = 0.5,
                 value: int = 5, uses: int = 1, effect_value: int = 10,
                 effect_type: str = "heal"):
        # Call super without stackable
        super().__init__(
            obj_id=obj_id, name=name, description=description, weight=weight,
            value=value, # Pass weight and value
            # Pass other kwargs specific to this subclass for properties
            uses=uses, max_uses=uses, effect_value=effect_value, effect_type=effect_type
        )
        # Set stackable based on uses *after* super init
        self.stackable = (uses == 1)
        self.update_property("stackable", self.stackable)
    
    def use(self, user, **kwargs) -> str: # Added **kwargs to potentially accept target later if needed
        """Use the consumable item."""
        current_uses = self.get_property("uses")
        if current_uses <= 0:
            return f"The {self.name} has already been used up."

        effect_type = self.get_property("effect_type")
        effect_value = self.get_property("effect_value")

        message = f"You use the {self.name}." # Default message if effect type isn't handled

        # --- Original Heal Logic ---
        if effect_type == "heal":
            if hasattr(user, "heal"):
                healed_amount = user.heal(effect_value)
                if healed_amount > 0:
                    message = f"You consume the {self.name} and regain {healed_amount} health."
                else:
                    message = f"You consume the {self.name}, but feel no different."
            else:
                message = f"You consume the {self.name}, but it has no effect."

        # --- ADD Learn Spell Logic ---
        elif effect_type == "learn_spell":
            spell_id_to_learn = self.get_property("spell_to_learn")
            if not spell_id_to_learn:
                message = f"The {self.name} seems inert or misconfigured."
            elif not hasattr(user, "learn_spell"):
                message = f"You try to learn from the {self.name}, but cannot."
            else:
                # Call the modified player.learn_spell
                learned, learn_message = user.learn_spell(spell_id_to_learn)
                # Format the message from learn_spell
                if learned:
                    message = f"{FORMAT_SUCCESS}{learn_message}{FORMAT_RESET}"
                    # Only decrement uses if learning was successful
                    self.update_property("uses", current_uses - 1)
                else:
                    message = f"{FORMAT_ERROR}{learn_message}{FORMAT_RESET}"
                    # Do NOT decrement uses if learning failed (level too low, already known, etc.)
                    # The scroll is not consumed if it couldn't be used.
                    return message # Return immediately, don't process use decrement below

        # --- ADD other effect types here later (e.g., mana potion, buff scroll) ---
        # elif effect_type == "mana_restore":
        #     ...
        # elif effect_type == "apply_buff":
        #     ...

        else:
            # Default message for unhandled types (already set above)
            pass

        # Decrement uses (only if not returned early by a failed learn attempt)
        # This check prevents double-decrementing if learn succeeded above.
        if message.startswith(FORMAT_SUCCESS): # Simple check if learning succeeded
            pass # Uses already decremented inside the learn_spell block on success
        elif effect_type != "learn_spell": # Decrement for non-learning effects
             self.update_property("uses", current_uses - 1)


        # Append remaining uses if applicable
        new_uses = self.get_property("uses")
        max_uses = self.get_property("max_uses", 1)
        if max_uses > 1 and new_uses > 0:
            message += f" ({new_uses}/{max_uses} uses remaining)."
        elif new_uses <= 0:
            message += f" The {self.name} is used up."

        return message
    
    def examine(self) -> str:
        """Get a detailed description of the consumable."""
        base_desc = super().examine()
        if self.properties["max_uses"] > 1:
            return f"{base_desc}\n\nUses remaining: {self.properties['uses']}/{self.properties['max_uses']}"
        return base_desc