import os
import sys
# Missing: import json
# Missing: import time

def CalculateAverage(NumbersList):
    # Bug 1: CamelCase naming (non-idiomatic)
    # Bug 2: Potential ZeroDivisionError
    # Bug 3: Logic error - adding a constant accidentally
    val = sum(NumbersList) + 1 
    return val / len(NumbersList)

def load_settings(config_path):
    # Bug 4: Resource Leak - opening file without 'with' or 'close'
    # Bug 5: No error handling for missing file
    f = open(config_path, 'r')
    content = f.read()
    # Bug 6: json not imported
    return json.loads(content)

def process_items(items):
    processed = []
    for i in range(len(items)):
        # Bug 7: Potential TypeError if item is not a number
        # Bug 8: Unused variable 'temp'
        temp = items[i] * 2
        processed.append(items[i] + "2") # Intentional TypeError: int + str
    return processed

def main():
    print("System Starting...")
    
    # Bug 9: Hardcoded path that might not exist
    data = load_settings("settings.json")
    
    # Bug 10: Calling a function with wrong type of data
    avg = CalculateAverage(data["scores"])
    
    print(f"Result: {avg}")

if __name__ == "__main__":
    main()
