import os
import sys

# Simulation of main.py scanning
HOME_DIR = os.path.expanduser("~")
SCAN_TARGETS = [HOME_DIR]
MIN_SIZE_MB = 100
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts')
EXCLUDE_PATHS = [
    "~/Pictures/Photos Library.photoslibrary",
    "~/Library/CloudStorage/",
    "~/Library/Containers/",
    "~/Library/Mobile Documents/",
    "@eaDir",
    "#recycle",
    "Temporary Items",
    "Network Trash Folder"
]

def debug_scan():
    video_files = []
    exclude_abs = [os.path.abspath(os.path.expanduser(p)) for p in EXCLUDE_PATHS]
    
    for target in SCAN_TARGETS:
        abs_t = os.path.abspath(os.path.expanduser(target))
        print(f"DEBUG: Scanning {abs_t}")
        for root, dirs, files in os.walk(abs_t):
            # Prune
            pruned = []
            for d in dirs:
                full_d = os.path.abspath(os.path.join(root, d))
                is_excl = full_d in exclude_abs or any(ex in full_d for ex in exclude_abs if "/" in ex) or d.startswith(".")
                if is_excl:
                    pruned.append(d)
            
            dirs[:] = [d for d in dirs if d not in pruned]
            
            if any(ex in root for ex in EXCLUDE_PATHS if not ex.startswith("~")):
                continue

            for file in files:
                if any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS):
                    filepath = os.path.join(root, file)
                    try:
                        sz = os.path.getsize(filepath)
                        if sz >= (MIN_SIZE_MB * 1024 * 1024):
                            print(f"DEBUG: Found {filepath} (Size: {sz/(1024*1024):.1f} MB)")
                            video_files.append(filepath)
                    except:
                        pass
            
            # Limit scan for debug
            if len(video_files) > 10: break
        if len(video_files) > 10: break

    print(f"DEBUG: Found {len(video_files)} total.")

if __name__ == "__main__":
    debug_scan()
