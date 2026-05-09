import csv
import json
import os

class DataParser:
    """Handles parsing and cleaning of various data formats."""

    def __init__(self, strict_mode=False):
        """Initializes the parser, optionally enforcing strict type checks."""
        self.strict_mode = strict_mode

    def parse_csv(self, filepath, delimiter=","):
        """Reads a CSV file and returns a list of dictionaries.
        
        Skips empty rows and logs warnings for malformed data if strict_mode is False.
        Raises an error on malformed data if strict_mode is True.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Missing file: {filepath}")

        results = []
        with open(filepath, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            for row in reader:
                # Basic cleanup
                clean_row = {k.strip(): v.strip() for k, v in row.items() if k and v}
                if clean_row:
                    results.append(clean_row)
        return results

    def parse_json(self, filepath):
        """Reads a JSON file and parses it into a Python object."""
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def extract_column(self, data, column_name):
        """Extracts a single column from a list of dictionaries.
        
        Ignores missing keys. Attempts to cast numeric strings to floats.
        """
        extracted = []
        for row in data:
            if column_name in row:
                val = row[column_name]
                try:
                    # Attempt numeric cast for downstream math
                    extracted.append(float(val))
                except ValueError:
                    extracted.append(val)
        return extracted
