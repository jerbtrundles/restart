# items/consumable.py
import time
from typing import Optional
from core.config import FORMAT_ERROR, FORMAT_RESET, FORMAT_SUCCESS
from items.item import Item

class Consumable(Item):
    def __init__(self, obj_id: Optional[str] = None, name: str = "Unknown Consumable",
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
        print(f"[DEBUG Consumable.use] Attempting to use '{self.name}'. Uses left: {current_uses}")
        if current_uses <= 0:
            return f"The {self.name} has already been used up."

        effect_type = self.get_property("effect_type")
        effect_value = self.get_property("effect_value")
        print(f"[DEBUG Consumable.use] Effect type found: '{effect_type}'") # <<< ADD

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

        elif effect_type == "apply_dot":
            print(f"[DEBUG Consumable.use] Found 'apply_dot' effect type for '{self.name}'.") # <<< ADD
            dot_name = self.get_property("dot_name")
            dot_duration = self.get_property("dot_duration")
            dot_damage_per_tick = self.get_property("dot_damage_per_tick")
            dot_tick_interval = self.get_property("dot_tick_interval")
            dot_damage_type = self.get_property("dot_damage_type")

            if not all([dot_name, dot_duration, dot_damage_per_tick, dot_tick_interval, dot_damage_type]):
                print(f"{FORMAT_ERROR}[DEBUG Consumable.use] Error: Missing required dot_* properties on '{self.name}'.{FORMAT_RESET}") # <<< ADD Error Check
                message = f"The {self.name} seems improperly configured."
                # Decrement uses even if misconfigured? Maybe not. Let's return early.
                self.update_property("uses", current_uses - 1) # Still consume the item
                return message
            else:
                 print(f"[DEBUG Consumable.use] Dot props: Name='{dot_name}', Duration={dot_duration}, Dmg={dot_damage_per_tick}, Interval={dot_tick_interval}, Type='{dot_damage_type}'") # <<< ADD

            # For self-use, the target is the user
            target = user
            if hasattr(target, 'apply_effect'):
                dot_data = {
                    "type": "dot", "name": dot_name, "base_duration": dot_duration,
                    "damage_per_tick": dot_damage_per_tick, "tick_interval": dot_tick_interval,
                    "damage_type": dot_damage_type, "source_id": getattr(user, 'obj_id', None)
                }
                print(f"[DEBUG Consumable.use] Calling apply_effect on '{target.name}' with data: {dot_data}") # <<< ADD
                # Pass current time
                success, _ = target.apply_effect(dot_data, time.time())
                if success:
                    message = f"You feel a sickly sensation as you use the {self.name}."
                    self.update_property("uses", current_uses - 1) # Decrement uses *only on success*
                else:
                    # apply_effect on Player currently always returns True, but good practice
                    message = f"You use the {self.name}, but nothing seems to happen."
                    # Don't decrement uses if applying failed? Or maybe consume anyway?
                    # Let's consume it for now.
                    self.update_property("uses", current_uses - 1)
            else:
                print(f"[DEBUG Consumable.use] Error: Target '{target.name}' has no apply_effect method.") # <<< ADD
                message = f"You can't seem to apply the effect of {self.name}."
                # Consume the item even if target is invalid?
                self.update_property("uses", current_uses - 1)

        else:
            # Default message for unhandled types
             print(f"[DEBUG Consumable.use] Unhandled effect type: '{effect_type}'") # <<< ADD
             pass # Keep existing else logic

        # Decrement uses only if not handled above specifically (like successful dot apply)
        # OR if it was an unhandled type
        # if effect_type != "apply_dot" and effect_type != "learn_spell": # Avoid double decrement
        #     self.update_property("uses", current_uses - 1)

        # --- ADD other effect types here later (e.g., mana potion, buff scroll) ---
        # elif effect_type == "mana_restore":
        #     ...
        # elif effect_type == "apply_buff":
        #     ...

        new_uses = self.get_property("uses")
        max_uses = self.get_property("max_uses", 1)
        if max_uses > 1 and new_uses > 0: message += f" ({new_uses}/{max_uses} uses remaining)."
        elif new_uses <= 0: message += f" The {self.name} is used up."

        print(f"[DEBUG Consumable.use] Final Message: '{message}'") # <<< ADD
        return message

    def examine(self) -> str:
        """Get a detailed description of the consumable."""
        base_desc = super().examine()
        if self.properties["max_uses"] > 1:
            return f"{base_desc}\n\nUses remaining: {self.properties['uses']}/{self.properties['max_uses']}"
        return base_desc