import os
import sys
import json
import socket
from typing import List, Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

# ==============================================================================
# CONSTANTS & PATHS
# ==============================================================================

IS_WIN = sys.platform == "win32"
HOME_DIR = os.path.expanduser("~")
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8000

def find_free_port(start_port: int) -> int:
    """Finds the next available port starting from start_port."""
    port = start_port
    while port < 65535:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("localhost", port)) != 0:
                return port
            port += 1
    return start_port

# Data Directories
# Support Docker volume mounts via environment variables
_CONFIG_DIR_OVERRIDE = os.getenv("CONFIG_DIR")
_CACHE_DIR_OVERRIDE = os.getenv("CACHE_DIR")

if _CONFIG_DIR_OVERRIDE:
    # Docker mode: use /config for all persistent data
    HIDDEN_DATA_DIR = _CONFIG_DIR_OVERRIDE
    THUMB_DIR = os.path.join(_CACHE_DIR_OVERRIDE or _CONFIG_DIR_OVERRIDE, "thumbnails")
else:
    # Local mode: use project directory
    HIDDEN_DATA_DIR = os.path.join(PROJECT_ROOT, "arcade_data")
    THUMB_DIR = os.path.join(HIDDEN_DATA_DIR, "thumbnails")

CACHE_FILE = os.path.join(HIDDEN_DATA_DIR, "video_cache.json")
REPORT_FILE = os.path.join(HIDDEN_DATA_DIR, "index.html")
SETTINGS_FILE = os.path.join(HIDDEN_DATA_DIR, "settings.json")
DUPLICATES_CACHE_FILE = os.path.join(HIDDEN_DATA_DIR, "duplicates_cache.json")
STATIC_DIR = os.path.join(PROJECT_ROOT, "arcade_scanner", "server", "static")

# Security Constants
MAX_REQUEST_SIZE = 1024 * 1024  # 1 MB limit for API requests
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']
ALLOWED_THUMBNAIL_PREFIX = "thumb_"



# Default Exclusions
DEFAULT_EXCLUSIONS = [
    {"path": "@eaDir", "desc": "Synology NAS metadata"},
    {"path": "#recycle", "desc": "Synology recycle bin"},
    {"path": "Temporary Items", "desc": "macOS temp files"},
    {"path": "Network Trash Folder", "desc": "Network trash"},
]

if not IS_WIN:
    DEFAULT_EXCLUSIONS += [
        {"path": "~/Pictures/Photos Library.photoslibrary", "desc": "Apple Photos library"},
        {"path": "~/Library/", "desc": "iCloud & cloud services"},
        {"path": "~/Library/Containers/", "desc": "App sandbox data"},
        {"path": "~/.Trash/", "desc": "Trash Folder"},
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

# Default Settings (with documentation keys)
DEFAULT_SETTINGS_JSON = {
    "_comment_scan_targets": "List of absolute paths to scan for videos.",
    "scan_targets": [],
    "_comment_exclude_paths": "List of paths to ignore during scan.",
    "exclude_paths": [],
    "disabled_defaults": [],
    "saved_views": [],
    "_comment_min_size_mb": "Ignore videos smaller than this size.",
    "min_size_mb": 100,
    "_comment_min_image_size_kb": "Ignore images smaller than this (KB). E.g., 500 filters out tiny icons.",
    "min_image_size_kb": 100,
    "_comment_bitrate": "Mark videos above this kbps as HIGH bitrate.",
    "bitrate_threshold_kbps": 15000,

    "_comment_fun_facts": "Show educational overlays during optimization.",
    "enable_fun_facts": True,
    "_comment_optimizer": "Master toggle for optimization features.",
    "enable_optimizer": True,
    "_comment_tags": "User-created tags for video categorization.",
    "available_tags": [],
    "_comment_theme": "Application theme (arcade, professional, candy).",
    "theme": "arcade",
    "_comment_sensitive_dirs": "List of paths considered sensitive (NSFW) to be hidden in safe mode.",
    "sensitive_dirs": [],
    "_comment_sensitive_tags": "List of tags considered sensitive (NSFW) to be hidden in safe mode.",
    "sensitive_tags": ["nsfw", "adult", "18+"],
    "_comment_sensitive_collections": "List of collection names to be hidden in safe mode.",
    "sensitive_collections": [],
    "_comment_deovr": "Generate DeoVR-compatible JSON for VR headset viewing.",
    "enable_deovr": False,
    "_comment_image_scanning": "Include image files in the scanning process.",
    "enable_image_scanning": False
}

# ==============================================================================
# SETTINGS MODEL
# ==============================================================================

class AppSettings(BaseSettings):
    """
    Pydantic model for user settings.
    Loads from env vars (ARCADE_*) or defaults.
    File loading is handled manually to preserve JSON comments.
    """
    disabled_defaults: List[str] = Field(default_factory=list)

    saved_views: List[Dict[str, Any]] = Field(default_factory=list)

    min_size_mb: int = Field(100)
    min_image_size_kb: int = Field(100)
    bitrate_threshold_kbps: int = Field(15000)


    enable_fun_facts: bool = Field(True)
    enable_optimizer: bool = Field(True)

    theme: str = Field("arcade")
    enable_deovr: bool = Field(False)
    enable_image_scanning: bool = Field(False)

    class Config:
        env_prefix = "ARCADE_"
        extra = "ignore"

# ==============================================================================
# CONFIG MANAGER
# ==============================================================================

class ConfigManager:
    def __init__(self):
        self._ensure_directories()
        self.settings = self._load_settings()

    def _ensure_directories(self):
        for d in [HIDDEN_DATA_DIR, THUMB_DIR]:
            if not os.path.exists(d):
                os.makedirs(d)

    def _load_settings(self) -> AppSettings:
        # Load from JSON if exists
        file_data = {}
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    file_data = json.load(f)

                # Check for missing defaults and update file if needed
                dirty = False
                for k, v in DEFAULT_SETTINGS_JSON.items():
                    if k not in file_data:
                        file_data[k] = v
                        dirty = True

                if dirty:
                    self._save_json_raw(file_data)

            except Exception as e:
                print(f"⚠️ Warning: Could not read settings.json: {e}")

        # Initialize proper settings from file data (env vars will override defaults if set)
        # Note: Pydantic BaseSettings usually loads files via _env_file, but here we explicitly pass dict
        settings = AppSettings(**file_data)

        return settings

    def _save_json_raw(self, data: Dict[str, Any]):
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Error saving settings: {e}")

    def save(self, updates: Dict[str, Any]) -> bool:
        """
        Updates current settings with new values and saves to disk.
        Preserves existing keys (like comments).
        """
        try:
            # Reload raw file to preserve comments
            current_raw = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    current_raw = json.load(f)

            # Update raw dict
            current_raw.update(updates)

            # Save raw dict
            self._save_json_raw(current_raw)

            # Update internal model
            self.settings = AppSettings(**current_raw)
            return True
        except Exception as e:
            print(f"❌ Save failed: {e}")
            return False

    @property
    def default_exclusions(self) -> List[str]:
        """Returns the default exclusions, filtered by disabled_defaults."""
        return [e["path"] for e in DEFAULT_EXCLUSIONS
                if e["path"] not in self.settings.disabled_defaults]

    @property
    def active_scan_targets(self) -> List[str]:
        """
        Returns unique scan targets aggregated from ALL users + default HOME.
        The scanner needs to know EVERYTHING it should watch.
        """
        targets = set()
        
        # 1. Add Default Home if needed
        # targets.add(HOME_DIR) 
        
        # 2. Add User Targets
        # We need to import user_db here to avoid circular init issues at top level if possible
        # Or better, verify if user_db is ready.
        try:
            from arcade_scanner.database.user_store import user_db
            for user in user_db.get_all_users():
                for t in user.data.scan_targets:
                    if t:
                        targets.add(t)
        except ImportError:
            pass # Startup case
            
        if not targets:
            targets.add(HOME_DIR)
            
        return list(targets)

    @property
    def active_exclude_paths(self) -> List[str]:
        """
        Returns unique exclude paths from ALL users + defaults.
        """
        excludes = set(self.default_exclusions) # Start with defaults!
        
        try:
            from arcade_scanner.database.user_store import user_db
            for user in user_db.get_all_users():
                for e in user.data.exclude_paths:
                    if e:
                        excludes.add(e)
        except ImportError:
            pass
            
        return list(excludes)

    @property
    def optimizer_path(self) -> str:
        return os.getenv("ARCADE_OPTIMIZER_PATH", os.path.join(PROJECT_ROOT, "scripts", "video_optimizer.py"))

    @property
    def optimizer_available(self) -> bool:
        return os.path.exists(self.optimizer_path)

    @property
    def cache_file(self) -> str:
        return CACHE_FILE

    @property
    def report_file(self) -> str:
        return REPORT_FILE

    @property
    def thumb_dir(self) -> str:
        return THUMB_DIR



    @property
    def static_dir(self) -> str:
        return STATIC_DIR

    @property
    def hidden_data_dir(self) -> str:
        return HIDDEN_DATA_DIR

# Global Instance
config = ConfigManager()
