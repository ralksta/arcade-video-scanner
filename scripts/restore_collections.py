
import os
import sys

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

# config.save() meldet über den Rückgabewert, ob das Schreiben geklappt hat.
# Ohne die Prüfung stand hier auch dann "Success", wenn die Datei nicht
# beschreibbar war — und die Collections waren trotzdem weg.
if config.save({"smart_collections": collections_to_restore}):
    print("✅ Success! You may need to restart the server or refresh the page.")
else:
    print("❌ Speichern fehlgeschlagen — die Collections wurden NICHT wiederhergestellt.")
    sys.exit(1)
