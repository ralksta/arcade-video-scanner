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
HIDDEN_DATA_DIR = os.path.join(PROJECT_ROOT, "arcade_data")
THUMB_DIR = os.path.join(HIDDEN_DATA_DIR, "thumbnails")
PREVIEW_DIR = os.path.join(HIDDEN_DATA_DIR, "previews")
CACHE_FILE = os.path.join(HIDDEN_DATA_DIR, "video_cache.json")
REPORT_FILE = os.path.join(HIDDEN_DATA_DIR, "index.html")
SETTINGS_FILE = os.path.join(HIDDEN_DATA_DIR, "settings.json")
STATIC_DIR = os.path.join(PROJECT_ROOT, "arcade_scanner", "server", "static")

# Security Constants
MAX_REQUEST_SIZE = 1024 * 1024  # 1 MB limit for API requests
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']
ALLOWED_THUMBNAIL_PREFIX = "thumb_"
ALLOWED_PREVIEW_PREFIX = "prev_"


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
    "_comment_bitrate": "Mark videos above this kbps as HIGH bitrate.",
    "bitrate_threshold_kbps": 15000,
    "_comment_previews": "Set to true to generate hover previews (CPU intensive).",
    "enable_previews": False,
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
    "sensitive_collections": []
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
    scan_targets: List[str] = Field(default_factory=list)
    exclude_paths: List[str] = Field(default_factory=list)
    disabled_defaults: List[str] = Field(default_factory=list)
    saved_views: List[Dict[str, Any]] = Field(default_factory=list)
    smart_collections: List[Dict[str, Any]] = Field(default_factory=list)  # Smart collections with filter criteria
    
    min_size_mb: int = Field(100)
    bitrate_threshold_kbps: int = Field(15000)
    
    enable_previews: bool = Field(False)
    enable_fun_facts: bool = Field(True)
    enable_optimizer: bool = Field(True)
    enable_optimizer: bool = Field(True)
    available_tags: List[Dict[str, str]] = Field(default_factory=list)  # [{"name": "Gaming", "color": "#00ffd0"}]
    theme: str = Field("arcade")
    sensitive_dirs: List[str] = Field(default_factory=list)
    sensitive_tags: List[str] = Field(default_factory=list)
    sensitive_collections: List[str] = Field(default_factory=list)

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
        for d in [HIDDEN_DATA_DIR, THUMB_DIR, PREVIEW_DIR]:
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
        
        # SECURITY FIX: If scan_targets is empty, default to HOME_DIR
        # This prevents the security whitelist from blocking everything
        if not settings.scan_targets:
            settings.scan_targets = [HOME_DIR]
            print(f"ℹ️ No scan targets configured, defaulting to: {HOME_DIR}")
        
        # Remove duplicates while preserving order
        seen = set()
        settings.scan_targets = [x for x in settings.scan_targets if not (x in seen or seen.add(x))]
        
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
    def active_scan_targets(self) -> List[str]:
        # Add HOME_DIR as default if not already present
        targets = self.settings.scan_targets if self.settings.scan_targets else [HOME_DIR]
        
        # Ensure HOME_DIR is included (but avoid duplicates)
        if HOME_DIR not in targets:
            targets = [HOME_DIR] + targets
        
        return targets
        
    @property
    def active_exclude_paths(self) -> List[str]:
        default_paths = [e["path"] for e in DEFAULT_EXCLUSIONS 
                        if e["path"] not in self.settings.disabled_defaults]
        return default_paths + self.settings.exclude_paths

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
    def preview_dir(self) -> str:
        return PREVIEW_DIR
        
    @property
    def static_dir(self) -> str:
        return STATIC_DIR

    @property
    def hidden_data_dir(self) -> str:
        return HIDDEN_DATA_DIR

# Global Instance
config = ConfigManager()
