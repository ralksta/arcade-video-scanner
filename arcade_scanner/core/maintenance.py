import os
import shutil
import hashlib
from typing import List
from arcade_scanner.config import config

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
    print(f"🧹 Purging media in {config.hidden_data_dir}...")
    
    # Double check that hidden_data_dir is what we think it is (should be inside project)
    if "arcade_data" not in config.hidden_data_dir:
        print("❌ [Safety] HIDDEN_DATA_DIR looks suspicious. Aborting purge.")
        return

    targets = [
        (config.thumb_dir, "thumb_", ".jpg"),
        (config.preview_dir, "prev_", ".mp4")
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
    
    if "arcade_data" not in config.hidden_data_dir:
        print("❌ [Safety] HIDDEN_DATA_DIR looks suspicious. Aborting purge.")
        return

    if os.path.exists(config.thumb_dir):
        count = 0
        for filename in os.listdir(config.thumb_dir):
            file_path = os.path.join(config.thumb_dir, filename)
            if is_safe_to_delete(file_path, config.thumb_dir, "thumb_", ".jpg"):
                try:
                    os.remove(file_path)
                    count += 1
                except Exception as e:
                    print(f"  [Error] Failed to delete {file_path}: {e}")
        print(f"✅ Thumbnails purge complete. Removed {count} files.")

def purge_previews():
    """Deletes all preview clip files only."""
    print(f"🧹 Purging preview clips...")
    
    if "arcade_data" not in config.hidden_data_dir:
        print("❌ [Safety] HIDDEN_DATA_DIR looks suspicious. Aborting purge.")
        return

    if os.path.exists(config.preview_dir):
        count = 0
        for filename in os.listdir(config.preview_dir):
            file_path = os.path.join(config.preview_dir, filename)
            if is_safe_to_delete(file_path, config.preview_dir, "prev_", ".mp4"):
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
        (config.thumb_dir, "thumb_", ".jpg"),
        (config.preview_dir, "prev_", ".mp4")
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
        (config.thumb_dir, "thumb_", ".jpg"),
        (config.preview_dir, "prev_", ".mp4")
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
