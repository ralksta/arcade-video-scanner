import os
import asyncio
import time
import json
from typing import List, AsyncIterator, Set
from ..config import config

class AsyncFileSystem:
    """
    Handles asynchronous file system traversal.
    Uses asyncio to prevent blocking the main event loop during long scans.
    """
    
    VIDEO_EXTENSIONS = frozenset({'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts'})
    IMAGE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.heic'})

    def __init__(self):
        self.allow_images = False # Toggled by ScannerManager based on user settings
        self._last_scan_time = 0.0
        self._scan_time_file = None  # Set lazily when config is available
        self._skipped_dirs = 0

    def _load_settings(self):
        """Reload settings from config (called at scan start)."""
        self.min_size_bytes = config.settings.min_size_mb * 1024 * 1024
        
        # Resolve excluded paths to absolute for robust matching
        self.exclude_abs: Set[str] = set()
        for p in config.active_exclude_paths:
            resolved = os.path.abspath(os.path.expanduser(p))
            self.exclude_abs.add(resolved)
        
        # Load last scan time
        self._scan_time_file = os.path.join(config.hidden_data_dir, ".last_scan_time")
        self._load_last_scan_time()
        self._skipped_dirs = 0

    def _load_last_scan_time(self):
        """Load the timestamp of the last successful scan."""
        try:
            if self._scan_time_file and os.path.exists(self._scan_time_file):
                with open(self._scan_time_file, 'r') as f:
                    data = json.load(f)
                    self._last_scan_time = float(data.get('last_scan_time', 0))
        except Exception:
            self._last_scan_time = 0.0

    def save_last_scan_time(self):
        """Save the current time as last scan timestamp."""
        try:
            if self._scan_time_file:
                os.makedirs(os.path.dirname(self._scan_time_file), exist_ok=True)
                with open(self._scan_time_file, 'w') as f:
                    json.dump({'last_scan_time': time.time()}, f)
        except Exception as e:
            print(f"⚠️ Could not save scan time: {e}")

    async def scan_directories(self, targets: List[str]) -> AsyncIterator[str]:
        """
        Asynchronously yields absolute paths of valid video files found in targets.
        """
        # Reload settings fresh (picks up any changes to exclusions/min_size)
        self._load_settings()
        
        for target in targets:
            abs_target = os.path.abspath(os.path.expanduser(target))
            if not os.path.exists(abs_target):
                print(f"⚠️ Warning: Scan target not found: {abs_target}")
                continue
                
            # Offload blocking os.walk to a thread
            queue = asyncio.Queue()
            
            # Start the synchronous walker in a thread
            # We use a sentinel 'None' to indicate completion
            asyncio.create_task(self._walker_worker(abs_target, queue))
            
            while True:
                path = await queue.get()
                if path is None:
                    break
                yield path
        
        if self._skipped_dirs > 0:
            print(f"\n⚡ Skipped {self._skipped_dirs} unchanged directories (incremental scan)")

    async def _walker_worker(self, root_dir: str, queue: asyncio.Queue) -> None:
        """
        Worker that runs in a thread. 
        Streams results to the queue immediately to avoid blocking for long periods.
        """
        loop = asyncio.get_event_loop()
        
        def sync_walk():
            try:
                for root, dirs, files in os.walk(root_dir):
                    # 1. Prune exclusions (in-place modification of dirs)
                    dirs[:] = [d for d in dirs if not self._is_excluded(root, d)]
                    
                    # Check root itself
                    if self._should_skip_root(root):
                        continue
                    
                    # 2. Incremental scan: skip directories unchanged since last scan
                    #    Only yield files from dirs that have been modified
                    dir_changed = True
                    if self._last_scan_time > 0:
                        try:
                            dir_mtime = os.stat(root).st_mtime
                            if dir_mtime < self._last_scan_time:
                                dir_changed = False
                                self._skipped_dirs += 1
                        except OSError:
                            pass  # If we can't stat, assume changed
                        
                    for file in files:
                        if self._is_video(file):
                            full_path = os.path.join(root, file)
                            if dir_changed:
                                # Directory changed — yield for full inspection
                                if self._is_valid_size(full_path):
                                    loop.call_soon_threadsafe(queue.put_nowait, full_path)
                            else:
                                # Directory unchanged — still yield so orphan pruning 
                                # knows the file exists, but manager will skip inspection
                                # because cache entry is still valid
                                loop.call_soon_threadsafe(queue.put_nowait, full_path)
            except Exception as e:
                print(f"❌ Error walking {root_dir}: {e}")

        # Run in default executor
        await loop.run_in_executor(None, sync_walk)
        await queue.put(None)

    def _is_excluded(self, parent: str, dirname: str) -> bool:
        """Check if directory is excluded."""
        full = os.path.abspath(os.path.join(parent, dirname))
        
        # Exact match
        if full in self.exclude_abs:
            return True
        
        # Parent match (substring) logic from legacy scanner
        return False

    def _should_skip_root(self, root: str) -> bool:
        # Check if any exclude path is a substring (legacy behavior)
        # Optimized: Only check if exclude path is inside? 
        # Actually legacy `_is_excluded_root` checked `if ex in root`.
        for ex in self.exclude_abs:
             if ex in root:
                 return True
        return False

    def _is_video(self, filename: str) -> bool:
        # Skip macOS resource fork files (e.g., ._video.mp4)
        if filename.startswith("._"):
            return False
        
        ext = os.path.splitext(filename)[1].lower()
        if ext in self.VIDEO_EXTENSIONS:
            return True
        if self.allow_images and ext in self.IMAGE_EXTENSIONS:
            return True
        return False

    def _is_valid_size(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        
        # Images use KB threshold (configurable, e.g., 500 KB)
        if ext in self.IMAGE_EXTENSIONS:
            try:
                return os.path.getsize(path) >= config.settings.min_image_size_kb * 1024
            except OSError:
                return False
            
        # Optimization check for videos
        basename = os.path.basename(path)
        if "_opt." in basename or "_trim." in basename:
            return True
            
        try:
            return os.path.getsize(path) >= self.min_size_bytes
        except OSError:
            return False

# Singleton
fs_scanner = AsyncFileSystem()

