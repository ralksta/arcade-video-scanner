import asyncio
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
from ..core.video_processor import create_thumbnail

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
        
        # Concurrency Lanes
        # Heavy Lane (FFprobe/FFmpeg) - CPU bound
        self.sem_video = asyncio.Semaphore(os.cpu_count() or 4)
        # Fast Lane (Pillow) - IO bound, increased for image speed
        self.sem_image = asyncio.Semaphore(200) 

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
        
        # Configure Image Scanning (Phase 2 Check)
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
        
        # Concurrency: Using self.sem_video and self.sem_image defined in __init__
        pending_tasks = set()

        async def _process_path(path: str):
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
                if not cached_entry:
                    needs_update = True
                else:
                    try:
                        # Basic existence check and stat
                        file_stat = await asyncio.to_thread(os.stat, path)
                        # Check if file size changed significantly (more than 10MB difference)
                        # This catches files that were optimized/replaced
                        current_size_mb = file_stat.st_size / (1024 * 1024)
                        if abs(current_size_mb - cached_entry.size_mb) > 10:  # 10MB threshold
                            needs_update = True
                            print(f"📊 Size changed: {os.path.basename(path)} ({cached_entry.size_mb:.1f}MB → {current_size_mb:.1f}MB)")
                    except OSError:
                        needs_update = True

                if needs_update or force_rescan:
                    if progress_callback:
                        progress_callback(f"Analyzing {os.path.basename(path)}")
                    
                    # 3. Probe using Selected Inspector
                    entry: Optional[MediaAsset] = None
                    try:
                        entry = await inspector.inspect(path)
                    except Exception as e:
                        print(f"❌ Inspect failed for {path}: {e}")
                        entry = None
                    
                    if entry:
                        # Apply business logic (Bitrate Threshold)
                        params_bitrate = config.settings.bitrate_threshold_kbps
                        if entry.bitrate_mbps * 1000 > params_bitrate and entry.status == "OK":
                            entry.status = "HIGH"
                            
                        # Preserve user flags if existed (re-entry)
                        if cached_entry:
                            entry.favorite = cached_entry.favorite
                            entry.vaulted = cached_entry.vaulted
                            entry.tags = cached_entry.tags
                            # Preserve original import time if available, otherwise it stays what get_metadata gave (0 or now?)
                            # Actually get_metadata creates fresh. We should copy from cache if exists.
                            if cached_entry.imported_at > 0:
                                entry.imported_at = cached_entry.imported_at
                        
                        # Populate date fields
                        try:
                            # We need to re-stat if we didn't get it above (e.g. if needs_update was True from start)
                            # But optimization: we can just stat here.
                            if not 'file_stat' in locals():
                                file_stat = await asyncio.to_thread(os.stat, path)
                            
                            entry.mtime = int(file_stat.st_mtime)
                            
                            # If imported_at is still 0 (new file), set to now
                            if entry.imported_at == 0:
                                entry.imported_at = int(time.time())
                        except:
                            pass
                        
                        # ASSET GENERATION (Thumbnails & Previews)
                        loop = asyncio.get_event_loop()
                        
                        # We execute thumbnail generation concurrently
                        thumb_name = await loop.run_in_executor(self.probe.executor, create_thumbnail, path)
                        if thumb_name:
                            entry.thumb = thumb_name
                        

                            
                        # Upsert AFTER populating assets
                        db.upsert(entry)
                        
                        nonlocal processed_count
                        nonlocal last_save_time
                        processed_count += 1
                        
                        # Quick Save periodically (every 500 for speed)
                        # Optimized to avoid quadratic write overhead:
                        # Only save if 500 items processed AND > 60s passed
                        if processed_count % 500 == 0:
                            current_time = time.time()
                            if current_time - last_save_time > 60:
                                snapshot = db.get_data_snapshot()
                                await asyncio.to_thread(db.save, snapshot)
                                last_save_time = current_time

        try:
            # 2. Discovery Loop
            async for file_path in fs_scanner.scan_directories(config.active_scan_targets):
                if self._stop_event.is_set():
                    break
                    
                found_paths.add(file_path)
                
                # Spawn task
                task = asyncio.create_task(_process_path(file_path))
                pending_tasks.add(task)
                
                # Moderate task list size
                if len(pending_tasks) > 200:
                    done, pending = await asyncio.wait(pending_tasks, timeout=0.01, return_when=asyncio.FIRST_COMPLETED)
                    pending_tasks = pending

            # Wait for remaining
            if pending_tasks:
                await asyncio.gather(*pending_tasks)

            # 4. Prune Orphans (files deleted OR now excluded)
            if found_paths:
                orphans = [p for p in existing_paths if p not in found_paths]
                removed_count = 0
                for orphan in orphans:
                    db.remove(orphan)
                    removed_count += 1
                
                if removed_count > 0:
                    print(f"🗑 Removed {removed_count} files (deleted or now excluded).")

            db.save()
            
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

# Deprecated access
scanner_mgr = None
