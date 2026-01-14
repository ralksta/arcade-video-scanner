
import sqlite3
import json
import os
import sys

# Path to DB
DB_PATH = os.path.expanduser("~/git/arcade-video-scanner/arcade_data/users.db")

def check_admin_scan_images():
    if not os.path.exists(DB_PATH):
        print(f"❌ DB not found at {DB_PATH}")
        return

    print(f"📂 Opening DB at {DB_PATH}")
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM users WHERE username = 'admin'")
        row = cursor.fetchone()
        
        if row:
            print(f"👤 Found user: {row['username']}")
            data_json = row['user_data']
            if data_json:
                data = json.loads(data_json)
                scan_images = data.get('scan_images')
                print(f"📸 scan_images setting: {scan_images} (Type: {type(scan_images)})")
                print(f"📄 Full Data: {json.dumps(data, indent=2)}")
            else:
                print("⚠️ User data is NULL")
        else:
            print("❌ Admin user not found")
            
        conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    check_admin_scan_images()
