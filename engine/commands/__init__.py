# engine/commands/__init__.py
"""
Commands package initializer.
"""
import os
import importlib
from .movement import register_movement_commands

# Get the directory of this file
package_dir = os.path.dirname(__file__)

# CRITICAL CHANGE: Use __name__ to get the full dotted path (e.g., 'engine.commands')
# instead of calculating it from the folder name.
package_name = __name__

print(f"--- Loading Command Modules from '{package_name}' ---")

for item in os.listdir(package_dir):
    item_path = os.path.join(package_dir, item)
    
    # Case 1: Standard .py files
    if os.path.isfile(item_path) and item.endswith(".py") and not item.startswith("__"):
        module_name = item[:-3]
        try:
            # The '.' indicates a relative import within 'engine.commands'
            importlib.import_module(f".{module_name}", package=package_name)
            print(f"  -> Loaded module: {module_name}")
        except ImportError as e:
            print(f"  -> FAILED to load module '{module_name}': {e}")

    # Case 2: Sub-packages (e.g., interaction/)
    elif os.path.isdir(item_path) and not item.startswith("__"):
        if os.path.exists(os.path.join(item_path, "__init__.py")):
            try:
                importlib.import_module(f".{item}", package=package_name)
                print(f"  -> Loaded package: {item}")
            except ImportError as e:
                print(f"  -> FAILED to load package '{item}': {e}")

print("--- Registering Dynamic Movement Commands ---")
register_movement_commands()
print("--- Command Loading Complete ---")