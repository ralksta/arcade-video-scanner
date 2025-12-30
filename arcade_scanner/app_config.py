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
STATIC_DIR = os.path.join(PROJECT_ROOT, "arcade_scanner", "server", "static")

# ==============================================================================
# USER CONFIGURATION
# You can change the settings below to customize the scan and application behavior.
# ==============================================================================

# Directories to scan for video files.
# You can add absolute paths here.
DEFAULT_SCAN_TARGETS = [HOME_DIR]

# Default folders to exclude from scanning - with descriptions for UI
DEFAULT_EXCLUSIONS = [
    {"path": "@eaDir", "desc": "Synology NAS metadata"},
    {"path": "#recycle", "desc": "Synology recycle bin"},
    {"path": "Temporary Items", "desc": "macOS temp files"},
    {"path": "Network Trash Folder", "desc": "Network trash"},
]

if not IS_WIN:
    DEFAULT_EXCLUSIONS += [
        {"path": "~/Pictures/Photos Library.photoslibrary", "desc": "Apple Photos library"},
        {"path": "~/Library/CloudStorage/", "desc": "iCloud & cloud services"},
        {"path": "~/Library/Containers/", "desc": "App sandbox data"},
        {"path": "~/Library/Mobile Documents/", "desc": "iCloud documents"},
    ]
else:
    DEFAULT_EXCLUSIONS += [
        {"path": "AppData/Local/Temp", "desc": "Windows temp files"},
        {"path": "Windows/Temp", "desc": "System temp folder"},
        {"path": "iCloudDrive", "desc": "iCloud Drive folder"},
        {"path": "iCloud Photos", "desc": "iCloud Photos sync"},
        {"path": "Proton Drive", "desc": "Proton Drive folder"},
        {"path": "$RECYCLE.BIN", "desc": "Windows recycle bin"},
        {"path": "Proton Drive Cloud Files", "desc": "Proton Drive cloud"},
    ]

# Build the flat list for backwards compatibility
DEFAULT_EXCLUDE_PATHS = [e["path"] for e in DEFAULT_EXCLUSIONS]

# Video file extensions to scan for.
VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts')

# --- USER SETTINGS JSON ---
SETTINGS_FILE = os.path.join(HIDDEN_DATA_DIR, "settings.json")

def load_user_settings():
    """Load user settings from settings.json, creating defaults if not exists."""
    import json
    
    default_settings = {
        "scan_targets": [],
        "exclude_paths": [],
        "disabled_defaults": [],  # Default exclusions user has turned off
        "saved_views": [],
        "min_size_mb": 100,
        "bitrate_threshold_kbps": 15000
    }
    
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
                # Merge with defaults for any missing keys
                for key, value in default_settings.items():
                    if key not in settings:
                        settings[key] = value
                return settings
        except Exception as e:
            print(f"⚠️  Warning: Could not read settings.json: {e}")
    
    return default_settings

def save_user_settings(settings):
    """Save user settings to settings.json."""
    import json
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving settings: {e}")
        return False

# Load user settings
USER_SETTINGS = load_user_settings()

# Build active default exclusions (excluding any disabled by user)
disabled_defaults = USER_SETTINGS.get("disabled_defaults", [])
ACTIVE_DEFAULT_EXCLUDES = [e["path"] for e in DEFAULT_EXCLUSIONS if e["path"] not in disabled_defaults]

# Combine defaults with user settings
SCAN_TARGETS = DEFAULT_SCAN_TARGETS + USER_SETTINGS.get("scan_targets", [])
EXCLUDE_PATHS = ACTIVE_DEFAULT_EXCLUDES + USER_SETTINGS.get("exclude_paths", [])
MIN_SIZE_MB = USER_SETTINGS.get("min_size_mb", 100)
BITRATE_THRESHOLD_KBPS = USER_SETTINGS.get("bitrate_threshold_kbps", 15000)

# Print loaded user paths
if USER_SETTINGS.get("scan_targets"):
    print(f"ℹ️  Loaded {len(USER_SETTINGS['scan_targets'])} custom scan targets from settings.json")
if USER_SETTINGS.get("exclude_paths"):
    print(f"ℹ️  Loaded {len(USER_SETTINGS['exclude_paths'])} custom exclude paths from settings.json")
if disabled_defaults:
    print(f"ℹ️  {len(disabled_defaults)} default exclusions disabled by user")

OPTIMIZER_SCRIPT = os.getenv("ARCADE_OPTIMIZER_PATH", os.path.join(PROJECT_ROOT, "scripts", "video_optimizer.py"))
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
