import sys
import json
DEFAULT_CONFIG_PATH = "settings.json"

def calculate_average(numbers_list):
    if not numbers_list:
        return 0.0 # Return 0.0 for an empty list to prevent ZeroDivisionError
    return sum(numbers_list) / len(numbers_list)

def load_settings(config_path):
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{config_path}' not found. Returning default settings.", file=sys.stderr)
        return {"scores": []}
    except json.JSONDecodeError:
        print(f"Error: Configuration file '{config_path}' contains invalid JSON. Returning default settings.", file=sys.stderr)
        return {"scores": []}

def process_items(items):
    return [item + 2 for item in items if isinstance(item, (int, float))]

def main():
    print("System Starting...")
    
    if len(sys.argv) > 2:
        print("Usage: python buggy_app.py [config_path]", file=sys.stderr)
        sys.exit(1)
    config_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    data = load_settings(config_path)
    
    processed_scores = process_items(data.get("scores", []))
    avg = calculate_average(processed_scores)
    
    print(f"Result: {avg}")

if __name__ == "__main__":
    main()