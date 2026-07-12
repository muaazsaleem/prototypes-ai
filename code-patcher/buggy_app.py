import os
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
def calculate_average(numbers_list):
    if not isinstance(numbers_list, (list, tuple)):
        raise TypeError("Input 'numbers_list' must be a list or tuple of numbers.")
    for item in numbers_list:
        if not isinstance(item, (int, float)):
            raise TypeError("All elements in 'numbers_list' must be numbers (int or float).")
    if not numbers_list:
        return 0.0
    val = sum(numbers_list)
    return val / len(numbers_list)

def load_settings(config_path):
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning(f"Configuration file not found at '{config_path}'. Returning empty settings.")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Configuration file at '{config_path}' is malformed JSON. Returning empty settings.")
        return {}

def main():
    logger.info("System Starting...")
    
    config_file = os.getenv("APP_CONFIG_PATH", "settings.json")
    data = load_settings(config_file)
    
    avg = calculate_average(data.get("scores", []))
    
    logger.info(f"Result: {avg}")

if __name__ == "__main__":
    main()