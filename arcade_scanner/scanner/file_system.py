import os
import asyncio
from typing import List, AsyncIterator, Set
from ..config import config

class AsyncFileSystem:
    """
    Handles asynchronous file system traversal.
    Uses asyncio to prevent blocking the main event loop during long scans.
    """
    
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov', '.m4v', '.wmv', '.flv', '.webm', '.ts')
    IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.heic')

    def __init__(self):
        self.allow_images = False # Toggled by ScannerManager based on user settings

    def _load_settings(self):
        """Reload settings from config (called at scan start)."""
        self.min_size_bytes = config.settings.min_size_mb * 1024 * 1024
        
        # Resolve excluded paths to absolute for robust matching
        self.exclude_abs: Set[str] = set()
        for p in config.active_exclude_paths:
            resolved = os.path.abspath(os.path.expanduser(p))
            self.exclude_abs.add(resolved)

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
                        
                    for file in files:
                        if self._is_video(file):
                            full_path = os.path.join(root, file)
                            if self._is_valid_size(full_path):
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
        
        is_video = any(filename.lower().endswith(ext) for ext in self.VIDEO_EXTENSIONS)
        if is_video:
            return True
            
        if self.allow_images:
            return any(filename.lower().endswith(ext) for ext in self.IMAGE_EXTENSIONS)
            
        return False

    def _is_valid_size(self, path: str) -> bool:
        # Images use KB threshold (configurable, e.g., 500 KB)
        if any(path.lower().endswith(ext) for ext in self.IMAGE_EXTENSIONS):
            try:
                size_bytes = os.path.getsize(path)
                min_image_bytes = config.settings.min_image_size_kb * 1024
                return size_bytes >= min_image_bytes
            except OSError:
                return False
            
        # Optimization check for videos
        if "_opt." in os.path.basename(path) or "_trim." in os.path.basename(path):
            return True
            
        try:
            return os.path.getsize(path) >= self.min_size_bytes
        except OSError:
            return False

# Singleton
fs_scanner = AsyncFileSystem()
