
import subprocess
import os

try:
    path = os.path.abspath('arcade_scanner/server/static/client.js')
    # Check if node exists
    if subprocess.run(['which', 'node'], capture_output=True).returncode == 0:
        result = subprocess.run(['node', '--check', path], 
                                capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ client.js syntax OK")
        else:
            print(f"❌ client.js syntax ERROR:\n{result.stderr}")
    else:
         print("⚠️ Node not found, skipping syntax check.")

except Exception as e:
    print(f"⚠️ Error running check: {e}")
