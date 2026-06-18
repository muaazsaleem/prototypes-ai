import os
import json
import time

DEFAULT_CONFIG_PATH = "settings.json"
def calculate_average(numbers_list):
    # Bug 1: CamelCase naming (non-idiomatic)
    # Bug 2: Potential ZeroDivisionError
    # Bug 3: Logic error - adding a constant accidentally
    if not numbers_list:
        return 0
    val = sum(numbers_list)
    return val / len(numbers_list)

def load_settings(config_path):
    # Bug 4: Resource Leak - opening file without 'with' or 'close'
    # Bug 5: No error handling for missing file - FIXED
    try:
        with open(config_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Config file '{config_path}' not found. Returning empty settings.")
        return {}
    # Bug 6: json not imported
    return json.loads(content)

def process_items(items):
    processed = []
    for item in items:
        # Bug 7: Potential TypeError if item is not a number; now handled.
        # Bug 8: "Unused variable 'temp'" comment was misleading, 'temp' was used.
        if isinstance(item, (int, float)):
            processed.append(item * 2)
    return processed

def main():
    print("System Starting...")
    
    # Bug 9: Hardcoded path that might not exist
    data = load_settings(DEFAULT_CONFIG_PATH)
    
    # Bug 10: Calling a function with wrong type of data
    avg = calculate_average(data.get("scores", []))
    
    print(f"Result: {avg}")

if __name__ == "__main__":
    main()
