import os
import socket
import sys

IS_WIN = sys.platform == "win32"
HOME_DIR = os.path.expanduser("~")


# ==============================================================================
# INTERNAL SETTINGS & PATHS
# (Do not modify these unless you know what you are doing)
# ==============================================================================

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIDDEN_DATA_DIR = os.path.join(PROJECT_ROOT, "arcade_data")
THUMB_DIR = os.path.join(HIDDEN_DATA_DIR, "thumbnails")
PREVIEW_DIR = os.path.join(HIDDEN_DATA_DIR, "previews")
CACHE_FILE = os.path.join(HIDDEN_DATA_DIR, "video_cache.json")
REPORT_FILE = os.path.join(HIDDEN_DATA_DIR, "index.html")

# ==============================================================================
# USER CONFIGURATION
# You can change the settings below to customize the scan and application behavior.
# ==============================================================================

# Directories to scan for video files.
# You can add absolute paths here.
SCAN_TARGETS = [HOME_DIR] if IS_WIN else [HOME_DIR, "/Volumes/T5 Media"]

# --- LOCAL TARGETS (NOT SYNCED TO GITHUB) ---
def load_local_config(filename):
    """Checks both PROJECT_ROOT and arcade_data for a config file."""
    paths_to_check = [
        os.path.join(PROJECT_ROOT, filename),
        os.path.join(HIDDEN_DATA_DIR, filename)
    ]
    for p in paths_to_check:
        if os.path.exists(p):
            try:
                # Use 'utf-8-sig' to handle BOM
                with open(p, "r", encoding="utf-8-sig", errors="replace") as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]
                    if lines:
                        print(f"ℹ️  Loaded {len(lines)} paths from {os.path.relpath(p, PROJECT_ROOT)}")
                        return lines
            except Exception as e:
                print(f"⚠️  Warning: Could not read {p}: {e}")
    return []

SCAN_TARGETS.extend(load_local_config("local_targets.txt"))

# Minimum video size in Megabytes to include in the scan.
MIN_SIZE_MB = 100

# Bitrate threshold in kbps (videos above this might be considered for optimization/transcoding).
BITRATE_THRESHOLD_KBPS = 15000

# Video file extensions to scan for.
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts')

# Folders to exclude from scanning. Patterns can be used if supported, or exact names.
EXCLUDE_PATHS = [
    "@eaDir",
    "#recycle",
    "Temporary Items",
    "Network Trash Folder"
]

if not IS_WIN:
    EXCLUDE_PATHS += [
        "~/Pictures/Photos Library.photoslibrary",
        "~/Library/CloudStorage/",
        "~/Library/Containers/",
        "~/Library/Mobile Documents/"
    ]
else:
    EXCLUDE_PATHS += [
        "AppData/Local/Temp",
        "Windows/Temp",
        "iCloudDrive",
        "iCloud Photos",
        "Proton Drive",
        "Proton Drive Cloud Files"
    ]

# --- LOCAL EXCLUDES (NOT SYNCED TO GITHUB) ---
EXCLUDE_PATHS.extend(load_local_config("local_excludes.txt"))

OPTIMIZER_SCRIPT = os.getenv("ARCADE_OPTIMIZER_PATH", os.path.join(HOME_DIR, "scripts", "video_optimizer.sh"))
OPTIMIZER_AVAILABLE = os.path.exists(OPTIMIZER_SCRIPT)

# Ensure directories exist
for d in [HIDDEN_DATA_DIR, THUMB_DIR, PREVIEW_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# --- SERVER SETTINGS ---

def find_free_port(start_port: int) -> int:
    port = start_port
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                # Use SO_REUSEADDR to check if we can bind even if in TIME_WAIT
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("", port))
                return port
            except OSError:
                port += 1

PORT = find_free_port(8000)
