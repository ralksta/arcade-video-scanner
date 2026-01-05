import sys
import os
import json

# Add project root to path
sys.path.append(os.getcwd())

from arcade_scanner.database import db
from arcade_scanner.config import config
from arcade_scanner.templates.dashboard_template import generate_html_report

print(f"📂 Cache File: {config.cache_file}")

try:
    print("🔄 Loading Database...")
    db.load()
    entries = db.get_all()
    print(f"✅ Loaded {len(entries)} entries.")
    
    if len(entries) > 0:
        first = entries[0]
        print(f"ℹ️ First Entry: {first.file_path}")
        print(f"   imported_at: {first.imported_at}")
        print(f"   mtime: {first.mtime}")
        
        # Test serialization
        dump = first.model_dump(by_alias=True)
        print(f"   JSON Dump keys: {list(dump.keys())}")
        
    # Test HTML Generation
    print("🔄 Generating HTML Report...")
    results = [e.model_dump(by_alias=True) for e in entries]
    generate_html_report(results, "debug_report.html", server_port=8000)
    print("✅ HTML Report Generated successfully.")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
