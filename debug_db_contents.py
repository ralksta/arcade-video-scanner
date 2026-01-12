
import sys
import os
import json
import logging

# Add project root to path
sys.path.append(os.getcwd())

from arcade_scanner.database import db

# Minimal mock of the API logic
def check_videos():
    print("--- CHECKING DB ---")
    videos = db.get_all()
    print(f"Total entries in DB: {len(videos)}")
    
    if not videos:
        print("❌ DB is empty!")
        return

    images = [v for v in videos if v.media_type == 'image']
    videos_only = [v for v in videos if v.media_type != 'image']
    
    print(f"Videos: {len(videos_only)}")
    print(f"Images: {len(images)}")
    
    if images:
        print("\nSample Image:")
        print(images[0].model_dump_json(indent=2))
        
    if videos_only:
        print("\nSample Video:")
        print(videos_only[0].model_dump_json(indent=2))

if __name__ == "__main__":
    check_videos()
