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

    def __init__(self):
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
        Worker that runs in a thread (via asyncio.to_thread in Python 3.9+ or loop.run_in_executor).
        For backward compatibility, we'll wrap the loop here.
        Actually, simpler pattern: Iterate synchronously and put to queue from thread?
        Or just use run_in_executor for the whole os.walk list? 
        
        For massive libraries, accumulating a full list in memory is bad.
        We want a streaming generator.
        
        Best approach for Python < 3.9 mixed ecosystem:
        Run os.walk in thread, push to a thread-safe synchronized queue? 
        asyncio.Queue is NOT thread-safe for calls from other threads.
        
        Refined Strategy:
        We will use `await asyncio.to_thread(self._sync_scan, ...)` if Python 3.9+.
        Given requirements say Python 3.10+, we can use `to_thread`.
        But `to_thread` runs a function. We want an iterator.
        
        Simpler Async approach: 
        Just wrap specific blocking calls? No, traversing huge directory trees has overhead.
        
        Let's use a simpler batching approach:
        Run `os.walk` in chunks or just yield results? 
        
        Actually, standard os.walk is fast enough if we don't block THE LOOP.
        We can run a recursive scanner that yields to the event loop periodically?
        Or just run the whole thing in a thread executor and return a list?
        Phase goals said "non-blocking".
        
        Let's yield list chunks from a thread executor to avoid complex queue handling.
        """
        loop = asyncio.get_event_loop()
        
        # We will dispatch the heavy lifting to a thread
        # Because generators cannot be easily passed across run_in_executor boundaries
        # We will collect files in batches.
        
        def sync_walk():
            found_files = []
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
                            found_files.append(full_path)
            
            # Return full list for this target (simplest safe implementation first)
            # Memory usage is usually negligible for file list (strings), 
            # metadata is the heavy part.
            return found_files

        # Run in default executor
        files = await loop.run_in_executor(None, sync_walk)
        for f in files:
            await queue.put(f)
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
        return any(filename.lower().endswith(ext) for ext in self.VIDEO_EXTENSIONS)

    def _is_valid_size(self, path: str) -> bool:
        # Optimization check
        if "_opt." in os.path.basename(path):
            return True
            
        try:
            return os.path.getsize(path) >= self.min_size_bytes
        except OSError:
            return False

# Singleton
fs_scanner = AsyncFileSystem()
