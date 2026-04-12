import asyncio
import hashlib
import os
import time
from typing import Callable, Optional, List, Set

from ..config import config
from ..database import db
from ..models.video_entry import VideoEntry
from ..models.media_asset import MediaAsset
from .file_system import fs_scanner
from .media_probe import MediaProbe
from .video_inspector import VideoInspector
from .image_inspector import ImageInspector

class ScannerManager:
    """
    Orchestrates the scanning process:
    1. File Discovery (AsyncFileSystem)
    2. Cache Validation (DB)
    3. Metadata Extraction (MediaProbe)
    4. Persistence (DB)
    """
    def __init__(self):
        self.is_scanning = False
        self._stop_event = asyncio.Event()
        self.probe = MediaProbe() # Own the probe (ProcessPool)
        self.video_inspector = VideoInspector(self.probe)
        self.image_inspector = ImageInspector()
        
        # Concurrency Lanes (created lazily in run_scan to bind to correct event loop)
        self.sem_video = None
        self.sem_image = None 

    async def run_scan(self, progress_callback: Optional[Callable[[str], None]] = None, force_rescan: bool = False) -> int:
        """
        Full scan pipeline. Returns number of new/updated files processed.
        """
        if self.is_scanning:
            return 0
            
        self.is_scanning = True
        self._stop_event.clear()
        
        start_time = time.time()
        print(f"🚀 Starting Scan on: {config.active_scan_targets}")
        
        # Create semaphores bound to current event loop (fixes asyncio event loop mismatch)
        # Heavy Lane (FFprobe/FFmpeg) - CPU bound
        # Create semaphores bound to current event loop
        # Use configured limits to prevent OOM/PID exhaustion
        self.sem_video = asyncio.Semaphore(config.settings.max_concurrent_video_scans)
        self.sem_image = asyncio.Semaphore(config.settings.max_concurrent_image_scans)
        try:
            from ..database.user_store import user_db
            scan_images = False
            for u in user_db.get_all_users():
                if getattr(u.data, 'scan_images', False):
                    scan_images = True
                    break
            fs_scanner.allow_images = scan_images
            if scan_images:
                print("📸 Image scanning enabled (Fast Lane Active)")
        except Exception as e:
            pass
        
        # 1. Load Cache
        db.load()
        existing_paths = {entry.file_path for entry in db.get_all()}
        found_paths: Set[str] = set()
        
        processed_count = 0
        last_save_time = time.time()
        
        # 2. Worker Queue Pattern
        queue = asyncio.Queue(maxsize=100) # Buffer for discovered paths
        workers = []
        num_workers = config.settings.max_concurrent_video_scans + 2 # A few extra workers to manage the queue

        async def _check_system_load():
            """Simple Watchdog using load average."""
            if not config.settings.enable_resource_watchdog:
                return
            
            try:
                # os.getloadavg() returns 1, 5, 15 min averages
                load = os.getloadavg()[0]
                cpu_count = os.cpu_count() or 1
                
                # If load is 2x CPU count, we are heavily saturated
                if load > cpu_count * 2:
                    if config.settings.verbose_scanning:
                        print(f"⚠️ High system load ({load:.2f}), throttling scanner...")
                    await asyncio.sleep(2)
            except Exception:
                pass

        async def _worker():
            nonlocal processed_count, last_save_time
            while True:
                try:
                    item = await queue.get()
                    if item is None: # Poison pill
                        queue.task_done()
                        break
                    
                    path, dir_changed, idx, total = item
                    
                    await _check_system_load()
                    await _process_path(path, dir_changed, idx, total)
                    
                    processed_count += 1
                    queue.task_done()
                except Exception as e:
                    print(f"❌ Worker error: {e}")
                    queue.task_done()

        # ... (we'll move _process_path to a method or keep it as helper)

        async def _process_path(path: str, dir_changed: bool, current_idx: int = 0, total_count: int = 0):
            # 1. Lane Selection
            inspector = None
            sem = None
            if self.video_inspector.can_handle(path):
                inspector = self.video_inspector
                sem = self.sem_video
            elif self.image_inspector.can_handle(path):
                inspector = self.image_inspector
                sem = self.sem_image
            
            if not inspector or not sem:
                return

            async with sem:
                if self._stop_event.is_set():
                    return
                
                # Check cache state
                cached_entry = db.get(path)
                needs_update = False
                
                # Fast Path: If dir hasn't changed AND we have it in DB, we can skip os.stat
                # This is "Ultra Fast" because it avoids the filesystem overhead.
                if not dir_changed and cached_entry and not force_rescan:
                    # File exists and its parent dir hasn't changed structure-wise.
                    # We still track it as found_paths to avoid orphans.
                    return

                # Normal Path: Directory changed or new file - we need to stat it
                try:
                    file_stat = await asyncio.to_thread(os.stat, path)
                except OSError:
                    return  # file gone

                if not cached_entry:
                    needs_update = True
                else:
                    # Strict validation: mtime or size change
                    current_size_mb = file_stat.st_size / (1024 * 1024)
                    mtime_changed = int(file_stat.st_mtime) != cached_entry.mtime
                    size_changed = abs(current_size_mb - cached_entry.size_mb) > 0.01

                    if mtime_changed or size_changed:
                        needs_update = True
                        reason = "MTime changed" if mtime_changed else "Size changed"
                        if config.settings.verbose_scanning:
                            print(f"📊 {reason}: {os.path.basename(path)}")

                if needs_update or force_rescan:
                    progress_prefix = f"[{current_idx}/{total_count}] " if total_count > 0 else ""
                    
                    if progress_callback:
                        progress_callback(f"Analyzing {os.path.basename(path)}")
                    
                    # Log based on verbose setting
                    if config.settings.verbose_scanning:
                        print(f"🔍 {progress_prefix}Analyzing: {os.path.basename(path)}")
                    elif (processed_count > 0 and processed_count % 50 == 0) or current_idx == total_count:
                        # Only print indexing if we actually found something new/updated and processed it
                        if processed_count > 0:
                            print(f"📊 {progress_prefix}Indexing media... ({processed_count} new/updated)")
                    
                    # 3. Probe using Selected Inspector
                    entry: Optional[MediaAsset] = None
                    try:
                        entry = await inspector.inspect(path)
                    except Exception as e:
                        print(f"❌ {progress_prefix}Inspect failed for {path}: {e}")
                        entry = None
                    
                    if entry:
                        # ...
                        # Apply business logic (Bitrate Threshold)
                        params_bitrate = config.settings.bitrate_threshold_kbps
                        if entry.bitrate_mbps * 1000 > params_bitrate and entry.status == "OK":
                            entry.status = "HIGH"
                            
                        # Preserve user flags if existed (re-entry)
                        if cached_entry:
                            entry.favorite = cached_entry.favorite
                            entry.vaulted = cached_entry.vaulted
                            entry.tags = cached_entry.tags
                            if cached_entry.imported_at > 0:
                                entry.imported_at = cached_entry.imported_at
                        
                        # Populate date fields (reuse file_stat from above)
                        entry.mtime = int(file_stat.st_mtime)
                        
                        # If imported_at is still 0 (new file), set to now
                        if entry.imported_at == 0:
                            entry.imported_at = int(time.time())
                        
                        # Deterministic thumb name
                        file_hash = hashlib.md5(path.encode('utf-8', 'surrogateescape')).hexdigest()
                        entry.thumb = f"thumb_{file_hash}.jpg"

                        # Pre-generate thumbnail during scan if enabled
                        if config.settings.precompute_thumbnails:
                            thumb_path = os.path.join(config.thumb_dir, entry.thumb)
                            if not os.path.exists(thumb_path) or os.path.getsize(thumb_path) == 0:
                                from ..core.video_processor import create_thumbnail
                                # Pass duration to avoid redundant ffprobe
                                duration = entry.duration_sec if hasattr(entry, 'duration_sec') else None
                                await asyncio.to_thread(create_thumbnail, path, duration)

                            
                        # Upsert AFTER populating assets
                        db.upsert(entry)
                        
                        nonlocal last_save_time
                        
                        # Quick Save periodically (every 500 for speed)
                        # Optimized to avoid quadratic write overhead:
                        # Only save if 500 items processed AND > 60s passed
                        if processed_count % 500 == 0:
                            current_time = time.time()
                            if current_time - last_save_time > 60:
                                db.save()
                                last_save_time = current_time

        try:
            # Start Workers
            for _ in range(num_workers):
                workers.append(asyncio.create_task(_worker()))

            # 2. Discovery Loop -> Feed Queue
            print("🔍 Walking directories to count files...")
            total_discovered = 0
            
            # First pass: count for progress (if we want real totals, otherwise we can stream)
            all_items = []
            async for item in fs_scanner.scan_directories(config.active_scan_targets):
                if self._stop_event.is_set():
                    break
                all_items.append(item)
            
            total_discovered = len(all_items)
            if total_discovered > 0:
                print(f"📂 Found {total_discovered} files. Starting processing...")
            
            for idx, (file_path, dir_changed) in enumerate(all_items, 1):
                if self._stop_event.is_set():
                    break
                found_paths.add(file_path)
                await queue.put((file_path, dir_changed, idx, total_discovered))

            # Stop Workers
            for _ in range(num_workers):
                await queue.put(None)
            
            await asyncio.gather(*workers)

            # 4. Prune Orphans (files deleted OR now excluded)
            if found_paths:
                orphans = existing_paths - found_paths
                removed_count = 0
                for orphan in orphans:
                    db.remove(orphan)
                    removed_count += 1
                
                if removed_count > 0:
                    print(f"🗑 Removed {removed_count} files (deleted or now excluded).")

            db.save()
            
            # Save scan timestamp for incremental scanning
            fs_scanner.save_last_scan_time()
            
        except Exception as e:
            print(f"❌ Scan failed: {e}")
        finally:
            self.is_scanning = False
            duration = time.time() - start_time
            print(f"✅ Scan completed in {duration:.2f}s. Processed {processed_count} new/updated files.")
            
        return processed_count

    def stop(self):
        self._stop_event.set()

_scanner_instance = None
def get_scanner_manager() -> ScannerManager:
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = ScannerManager()
    return _scanner_instance

