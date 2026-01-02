
import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from arcade_scanner.config import config

print(f"Current Smart Collections: {config.settings.smart_collections}")

# Define known collections to restore
# Using standard icons for now
collections_to_restore = [
    {
        "id": "poppers",
        "name": "Poppers", 
        "icon": "science", # Poppers -> Science/Chemistry bottle
        "criteria": {"tags": ["poppers"]}
    },
    {
        "id": "korea",
        "name": "Korea",
        "icon": "public", # Korea -> World/Public
        "criteria": {"tags": ["Korea"]}
    },
    {
        "id": "pantyhose",
        "name": "Pantyhose", 
        "icon": "checkroom", # Pantyhose -> Clothes
        "criteria": {"tags": ["pantyhose"]}
    },
    {
        "id": "femdom",
        "name": "Femdom",
        "icon": "health_and_safety", # Generic
        "criteria": {"tags": ["femdom"]}
    }
]

print("Restoring collections...")
config.save({"smart_collections": collections_to_restore})
print("✅ Success! You may need to restart the server or refresh the page.")
