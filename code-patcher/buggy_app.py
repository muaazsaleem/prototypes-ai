import os
import json
import logging
logging.basicConfig(level=logging.INFO)

CONFIG_ENV_VAR = "APP_CONFIG_PATH"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CONFIG_PATH = os.getenv(CONFIG_ENV_VAR, os.path.join(SCRIPT_DIR, "settings.json"))
def calculate_average(numbers):
    # NOTE: ZeroDivisionError is prevented by returning 0 for an empty list.
    if not numbers:
        return 0
    for num in numbers:
        if not isinstance(num, (int, float)):
            raise TypeError("All elements in numbers must be numeric (int or float).")
    val = sum(numbers)
    return val / len(numbers)

def load_settings(config_path):
    # Bug 5: No error handling for missing file - FIXED
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Config file '{config_path}' not found. Returning empty settings.")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from '{config_path}': {e}. Returning empty settings.")
        return {}

def process_items(items):
    processed = []
    for item in items:
        # Bug 7: Potential TypeError if item is not a number; now handled.
        if not isinstance(item, (int, float)):
            raise TypeError("All elements in items must be numeric (int or float).")
        processed.append(item * 2)
    return processed

def main():
    logging.info("System Starting...")
    data = load_settings(DEFAULT_CONFIG_PATH)
    try:
        avg = calculate_average(data.get("scores", []))
    except TypeError as e:
        logging.error(f"Failed to calculate average due to invalid data type: {e}")
        avg = 0.0 # Default or error value
    
    logging.info(f"Result: {avg}")

if __name__ == "__main__":
    main()
