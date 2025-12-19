import os
import shutil
import hashlib
from typing import List
from arcade_scanner.app_config import HIDDEN_DATA_DIR, THUMB_DIR, PREVIEW_DIR

def is_safe_to_delete(path: str, expected_parent: str, prefix: str, ext: str) -> bool:
    """Strict check to ensure the file is where we expect and named correctly."""
    abs_path = os.path.abspath(path)
    abs_parent = os.path.abspath(expected_parent)
    
    # Check if file is actually inside the expected directory
    if not abs_path.startswith(abs_parent):
        return False
        
    filename = os.path.basename(path)
    # Check naming pattern
    if not (filename.startswith(prefix) and filename.lower().endswith(ext)):
        return False
        
    return True

def purge_media():
    """Deletes all files in the thumbnail and preview directories with safety checks."""
    print(f"🧹 Purging media in {HIDDEN_DATA_DIR}...")
    
    # Double check that HIDDEN_DATA_DIR is what we think it is (should be inside project)
    if "arcade_data" not in HIDDEN_DATA_DIR:
        print("❌ [Safety] HIDDEN_DATA_DIR looks suspicious. Aborting purge.")
        return

    targets = [
        (THUMB_DIR, "thumb_", ".jpg"),
        (PREVIEW_DIR, "prev_", ".mp4")
    ]

    for folder, prefix, ext in targets:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if is_safe_to_delete(file_path, folder, prefix, ext):
                    try:
                        os.remove(file_path)
                    except Exception as e:
                        print(f"  [Error] Failed to delete {file_path}: {e}")
                else:
                    print(f"  ⚠️ [Safety] Skipping unexpected file: {filename}")
    print("✅ Media purge complete.")

def purge_thumbnails():
    """Deletes all thumbnail files only."""
    print(f"🧹 Purging thumbnails...")
    
    if "arcade_data" not in HIDDEN_DATA_DIR:
        print("❌ [Safety] HIDDEN_DATA_DIR looks suspicious. Aborting purge.")
        return

    if os.path.exists(THUMB_DIR):
        count = 0
        for filename in os.listdir(THUMB_DIR):
            file_path = os.path.join(THUMB_DIR, filename)
            if is_safe_to_delete(file_path, THUMB_DIR, "thumb_", ".jpg"):
                try:
                    os.remove(file_path)
                    count += 1
                except Exception as e:
                    print(f"  [Error] Failed to delete {file_path}: {e}")
        print(f"✅ Thumbnails purge complete. Removed {count} files.")

def purge_previews():
    """Deletes all preview clip files only."""
    print(f"🧹 Purging preview clips...")
    
    if "arcade_data" not in HIDDEN_DATA_DIR:
        print("❌ [Safety] HIDDEN_DATA_DIR looks suspicious. Aborting purge.")
        return

    if os.path.exists(PREVIEW_DIR):
        count = 0
        for filename in os.listdir(PREVIEW_DIR):
            file_path = os.path.join(PREVIEW_DIR, filename)
            if is_safe_to_delete(file_path, PREVIEW_DIR, "prev_", ".mp4"):
                try:
                    os.remove(file_path)
                    count += 1
                except Exception as e:
                    print(f"  [Error] Failed to delete {file_path}: {e}")
        print(f"✅ Preview clips purge complete. Removed {count} files.")

def purge_broken_media():
    """Removes media files that are 0 bytes or corrupted."""
    removed_count = 0
    targets = [
        (THUMB_DIR, "thumb_", ".jpg"),
        (PREVIEW_DIR, "prev_", ".mp4")
    ]
    for folder, prefix, ext in targets:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if is_safe_to_delete(file_path, folder, prefix, ext):
                    if os.path.getsize(file_path) == 0:
                        try:
                            os.remove(file_path)
                            removed_count += 1
                        except:
                            pass
    if removed_count > 0:
        print(f"🧹 Cleaned up {removed_count} failed media generation(s)")

def cleanup_orphans(video_files: List[str]):
    """Removes orphan media files with strict safety checks."""
    print("🧹 Cleaning up orphan media files...")
    
    valid_hashes = set()
    for vf in video_files:
        valid_hashes.add(hashlib.md5(vf.encode()).hexdigest())
    
    removed_count = 0
    targets = [
        (THUMB_DIR, "thumb_", ".jpg"),
        (PREVIEW_DIR, "prev_", ".mp4")
    ]
    
    for folder, prefix, ext in targets:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if not is_safe_to_delete(file_path, folder, prefix, ext):
                    continue
                    
                file_hash = filename.replace(prefix, "").replace(ext, "")
                if file_hash not in valid_hashes:
                    try:
                        os.remove(file_path)
                        removed_count += 1
                    except:
                        pass
                    
    print(f"✅ Cleanup complete. Removed {removed_count} orphan files.")
