"""
Commands package initializer.

This module dynamically discovers and imports all Python files in this
directory that contain command definitions. This allows for easy extension
by simply adding a new file with @command decorators, without needing to
manually register it elsewhere.
"""
import os
import importlib
from .movement import register_movement_commands

# Get the path of the 'commands' package directory
package_dir = os.path.dirname(__file__)
package_name = os.path.basename(package_dir)

print(f"--- Loading Command Modules from '{package_name}' ---")

# Iterate over all files in the directory
for filename in os.listdir(package_dir):
    # Check if it's a Python file and not this __init__ file or the core system
    if filename.endswith(".py") and not filename.startswith("__"):
        module_name = filename[:-3]  # Remove the '.py' extension
        
        try:
            # Dynamically import the module relative to the current package
            # Example: from . import system, from . import interaction, etc.
            importlib.import_module(f".{module_name}", package=package_name)
            print(f"  -> Successfully loaded command module: {module_name}")
        except ImportError as e:
            print(f"  -> FAILED to load command module '{module_name}': {e}")

# After all modules are loaded, the decorators have run.
# Now, we can call any setup functions that rely on those decorators.
# The movement commands are created dynamically, so we call their registration function here.
print("--- Registering Dynamic Movement Commands ---")
register_movement_commands()
print("--- Command Loading Complete ---")