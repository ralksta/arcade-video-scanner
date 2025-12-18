import json
import os
from arcade_scanner.app_config import CACHE_FILE

def load_cache(path=CACHE_FILE):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"Error loading cache from {path}: {e}")
    return {}

def save_cache(cache, path=CACHE_FILE):
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(cache, f, indent=4)
        print(f"✅ Cache saved to {path} ({len(cache)} entries)")
    except Exception as e:
        print(f"Error saving cache to {path}: {e}")
