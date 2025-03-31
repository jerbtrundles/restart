"""
utils/debug.py
Debugging utilities for the MUD game.
"""
import os
import sys
import json

def debug_world_file():
    """
    Debug function to help locate the world.json file and understand the working directory.
    """
    print("\n===== DEBUG: WORLD FILE DETECTION =====")
    print("Current working directory:", os.getcwd())
    
    # Try to find world.json in various locations
    possible_paths = [
        "world.json",
        os.path.join(os.getcwd(), "world.json"),
        os.path.join(os.path.dirname(os.getcwd()), "world.json"),
        os.path.join(os.path.dirname(__file__), "..", "world.json"),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "world.json")
    ]
    
    print("\nSearching for world.json:")
    found_paths = []
    for path in possible_paths:
        exists = os.path.exists(path)
        status = 'FOUND' if exists else 'not found'
        print(f"- {path}: {status}")
        
        if exists:
            found_paths.append(path)
            try:
                # Check file size
                size = os.path.getsize(path)
                print(f"  Size: {size} bytes")
                
                # Try to read a bit of the file
                with open(path, 'r') as f:
                    first_few_chars = f.read(100)
                print(f"  First few characters: {first_few_chars}")
            except Exception as e:
                print(f"  Error examining file: {e}")
    
    # List files in current directory to help debugging
    print("\nFiles in current directory:")
    try:
        for f in os.listdir(os.getcwd()):
            print(f"- {f}")
    except Exception as e:
        print(f"Error listing directory: {e}")
    
    # List files in parent directory
    print("\nFiles in parent directory:")
    try:
        parent_dir = os.path.dirname(os.getcwd())
        for f in os.listdir(parent_dir):
            print(f"- {f}")
    except Exception as e:
        print(f"Error listing parent directory: {e}")
    
    if found_paths:
        print("\nFound world.json at:")
        for path in found_paths:
            print(f"- {path}")
        print("\nWill try to use: " + found_paths[0])
    else:
        print("\nWARNING: Could not find world.json in any expected location!")
        
    print("===== END DEBUG =====\n")
    
    return found_paths[0] if found_paths else None

def validate_world_json(file_path):
    """
    Validate the structure of a world.json file and print any issues found.
    """
    print(f"\n===== VALIDATING WORLD FILE: {file_path} =====")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Check required top-level keys
        required_keys = ["current_region_id", "current_room_id", "player", "regions"]
        for key in required_keys:
            if key not in data:
                print(f"ERROR: Missing required key '{key}'")
        
        # Check current location validity
        current_region = data.get("current_region_id")
        current_room = data.get("current_room_id")
        
        if current_region and current_room:
            if current_region in data.get("regions", {}):
                if current_room in data["regions"][current_region].get("rooms", {}):
                    print(f"Current location is valid: {current_region}:{current_room}")
                else:
                    print(f"ERROR: Room '{current_room}' not found in region '{current_region}'")
            else:
                print(f"ERROR: Region '{current_region}' not found")
        
        # Validate all items have proper IDs
        print("\nChecking item IDs...")
        items_checked = 0
        items_with_issues = 0
        
        # Check player inventory items
        if "player" in data and "inventory" in data["player"] and "slots" in data["player"]["inventory"]:
            for i, slot in enumerate(data["player"]["inventory"]["slots"]):
                if slot.get("item"):
                    items_checked += 1
                    if not (slot["item"].get("id") or slot["item"].get("obj_id")):
                        print(f"ERROR: Player inventory item {i} has no ID")
                        items_with_issues += 1
        
        # Check room items
        for region_id, region in data.get("regions", {}).items():
            for room_id, room in region.get("rooms", {}).items():
                for i, item in enumerate(room.get("items", [])):
                    items_checked += 1
                    if not (item.get("id") or item.get("obj_id")):
                        print(f"ERROR: Item {i} in {region_id}:{room_id} has no ID")
                        items_with_issues += 1
        
        print(f"Checked {items_checked} items, found {items_with_issues} with issues")
        
        # Validate NPCs
        npc_count = len(data.get("npcs", {}))
        print(f"\nFound {npc_count} NPCs")
        
        if items_with_issues == 0:
            print("\nWorld file appears to be valid!")
        else:
            print(f"\nWorld file has {items_with_issues} issues that should be fixed")
        
        print("===== VALIDATION COMPLETE =====\n")
        return items_with_issues == 0
        
    except Exception as e:
        print(f"ERROR validating world file: {e}")
        import traceback
        traceback.print_exc()
        print("===== VALIDATION FAILED =====\n")
        return False