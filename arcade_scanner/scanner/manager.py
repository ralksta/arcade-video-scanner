import asyncio
import os
import time
from typing import Callable, Optional, List, Set

from ..config import config
from ..database import db
from ..models.video_entry import VideoEntry
from .file_system import fs_scanner
from .media_probe import MediaProbe
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
        
        # 1. Load Cache
        db.load()
        existing_paths = {entry.file_path for entry in db.get_all()}
        found_paths: Set[str] = set()
        
        processed_count = 0
        
        # Concurrency Control
        concurrency = os.cpu_count() or 4
        # We allow multiple tasks to be in flight; actual CPU work limit is handled by MediaProbe's ProcessPoolExecutor
        sem = asyncio.Semaphore(concurrency * 3)
        pending_tasks = set()

        async def _process_path(path: str):
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
                        # Basic existence check (cheap)
                        os.stat(path)
                    except OSError:
                        needs_update = True

                if needs_update or force_rescan:
                    if progress_callback:
                        progress_callback(f"Analyzing {os.path.basename(path)}")
                    
                    # 3. Probe with concurrency limit handled by MediaProbe's pool (WAITING)
                    entry = await self.probe.get_metadata(path)
                    
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
                        
                        # ASSET GENERATION (Thumbnails & Previews)
                        loop = asyncio.get_event_loop()
                        
                        # We execute thumbnail generation concurrently
                        thumb_name = await loop.run_in_executor(self.probe.executor, create_thumbnail, path)
                        if thumb_name:
                            entry.thumb = thumb_name
                        

                            
                        # Upsert AFTER populating assets
                        db.upsert(entry)
                        
                        nonlocal processed_count
                        processed_count += 1
                        
                        # Quick Save periodically?
                        if processed_count % 50 == 0:
                            db.save()

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
