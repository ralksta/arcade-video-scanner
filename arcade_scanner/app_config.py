import os
import socket
import sys

IS_WIN = sys.platform == "win32"

# --- PATHS ---
HOME_DIR = os.path.expanduser("~")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIDDEN_DATA_DIR = os.path.join(PROJECT_ROOT, "arcade_data")
THUMB_DIR = os.path.join(HIDDEN_DATA_DIR, "thumbnails")
PREVIEW_DIR = os.path.join(HIDDEN_DATA_DIR, "previews")
CACHE_FILE = os.path.join(HIDDEN_DATA_DIR, "video_cache.json")
REPORT_FILE = os.path.join(HIDDEN_DATA_DIR, "index.html")
OPTIMIZER_SCRIPT = os.getenv("ARCADE_OPTIMIZER_PATH", os.path.join(HOME_DIR, "scripts", "video_optimizer.sh"))

# Ensure directories exist
for d in [HIDDEN_DATA_DIR, THUMB_DIR, PREVIEW_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

# --- SCAN SETTINGS ---
SCAN_TARGETS = [HOME_DIR] if IS_WIN else [HOME_DIR, "/Volumes/T5 Media"]
MIN_SIZE_MB = 100
BITRATE_THRESHOLD_KBPS = 15000
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts')
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
        "Windows/Temp"
    ]

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
