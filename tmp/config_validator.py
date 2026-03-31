import json
import sys

def validate(file_path):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            print("Config JSON: Valid")
            # Minimal checks
            if "strategy" not in data and "exchange" not in data:
                print("Config Error: Missing strategy or exchange keys.")
            else:
                print("Config structure: OK")
    except Exception as e:
        print(f"Config JSON Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        validate(sys.argv[1])
    else:
        print("Usage: python config_validator.py <file>")
