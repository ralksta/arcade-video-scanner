import asyncio
import os
import subprocess
import shutil
from typing import Optional, Dict, List, Tuple

from ..models.media_asset import MediaAsset, MediaType, ImageMetadata
from .inspector import MediaInspector

class ImageInspector(MediaInspector):
    """
    Inspector for Image Files.
    Uses native macOS 'sips' for high performance metadata extraction without heavy dependencies.
    Falls back to Pillow if sips is missing (cross-platform safety).
    
    Performance: Batches up to BATCH_SIZE files per sips subprocess call,
    reducing process overhead from ~50K spawns to ~500 for large libraries.
    """
    BATCH_SIZE = 100  # Max files per sips call

    def __init__(self):
        self.IMAGE_EXTENSIONS = (
            # Standard formats
            '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.heic',
            # RAW formats
            '.cr2',   # Canon RAW
            '.cr3',   # Canon RAW (newer)
            '.nef',   # Nikon RAW
            '.arw',   # Sony RAW
            '.dng',   # Adobe Digital Negative (universal RAW)
            '.raf',   # Fujifilm RAW
            '.orf',   # Olympus RAW
            '.rw2',   # Panasonic RAW
            '.pef',   # Pentax RAW
            '.srw',   # Samsung RAW
            '.raw',   # Generic RAW
            '.rwl'    # Leica RAW
        )
        self.has_sips = shutil.which('sips') is not None
        
        # Batch queue for sips calls
        self._batch_queue: asyncio.Queue = None  # Created lazily per event loop
        self._batch_results: Dict[str, asyncio.Future] = {}
        self._batch_lock: asyncio.Lock = None
        self._batch_worker_started = False

    def _ensure_batch_infra(self):
        """Lazily create batch infrastructure bound to the current event loop."""
        if self._batch_queue is None:
            self._batch_queue = asyncio.Queue()
            self._batch_lock = asyncio.Lock()
            self._batch_results = {}

    def can_handle(self, filepath: str) -> bool:
        return any(filepath.lower().endswith(ext) for ext in self.IMAGE_EXTENSIONS)

    async def inspect(self, filepath: str) -> Optional[MediaAsset]:
        if self.has_sips:
            return await self._inspect_sips_batched(filepath)
        else:
            return await self._inspect_ffmpeg(filepath)

    async def _inspect_sips_batched(self, filepath: str) -> Optional[MediaAsset]:
        """Queue a file for batch sips inspection and wait for the result."""
        self._ensure_batch_infra()
        
        # Create a future for this file's result
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        
        async with self._batch_lock:
            self._batch_results[filepath] = future
            self._batch_queue.put_nowait(filepath)
            queue_size = self._batch_queue.qsize()
        
        # If we've hit batch size, flush immediately
        if queue_size >= self.BATCH_SIZE:
            asyncio.ensure_future(self._flush_batch())
        elif not self._batch_worker_started:
            # Start a background worker that flushes on a timer
            self._batch_worker_started = True
            asyncio.ensure_future(self._batch_timer_worker())
        
        # Wait for our result
        return await future

    async def _batch_timer_worker(self):
        """Background worker that flushes the batch queue periodically."""
        try:
            while True:
                await asyncio.sleep(0.05)  # 50ms flush interval
                if self._batch_queue and not self._batch_queue.empty():
                    await self._flush_batch()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"⚠️ Batch timer error: {e}")

    async def _flush_batch(self):
        """Drain the queue and run a single sips call for all queued files."""
        async with self._batch_lock:
            files = []
            while not self._batch_queue.empty() and len(files) < self.BATCH_SIZE:
                try:
                    files.append(self._batch_queue.get_nowait())
                except asyncio.QueueEmpty:
                    break
        
        if not files:
            return
        
        # Run single sips call for the entire batch
        try:
            cmd = ['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', '-g', 'format'] + files
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                # Some files may have failed — resolve with None
                for filepath in files:
                    future = self._batch_results.pop(filepath, None)
                    if future and not future.done():
                        future.set_result(None)
                return
            
            # Parse multi-file sips output
            output = stdout.decode()
            file_properties = self._parse_batch_sips_output(output)
            
            # Create MediaAssets and resolve futures
            for filepath in files:
                future = self._batch_results.pop(filepath, None)
                if not future or future.done():
                    continue
                
                props = file_properties.get(filepath)
                if not props:
                    future.set_result(None)
                    continue
                
                try:
                    asset = await self._build_asset_from_props(filepath, props)
                    future.set_result(asset)
                except Exception as e:
                    future.set_result(None)
                    
        except Exception as e:
            print(f"❌ Batch sips error: {e}")
            # Resolve all pending futures with None
            for filepath in files:
                future = self._batch_results.pop(filepath, None)
                if future and not future.done():
                    future.set_result(None)

    async def _build_asset_from_props(self, filepath: str, props: Dict[str, str]) -> Optional[MediaAsset]:
        """Build a MediaAsset from parsed sips properties."""
        w = int(props.get('pixelWidth', 0))
        h = int(props.get('pixelHeight', 0))
        fmt = props.get('format', 'unknown')
        
        i_meta = ImageMetadata(width=w, height=h, format=fmt)
        
        file_stat = await asyncio.to_thread(os.stat, filepath)
        size_mb = file_stat.st_size / (1024 * 1024)
        mtime = int(file_stat.st_mtime)
        
        return MediaAsset(
            FilePath=filepath,
            Size_MB=size_mb,
            media_type=MediaType.IMAGE,
            image_metadata=i_meta,
            mtime=mtime,
            imported_at=0
        )

    def _parse_batch_sips_output(self, output: str) -> Dict[str, Dict[str, str]]:
        """
        Parse multi-file sips output. Each file section starts with the filepath:
        
        /path/to/file1.png
          pixelWidth: 1920
          pixelHeight: 1080
          format: png
        /path/to/file2.jpg
          pixelWidth: 3840
          pixelHeight: 2160
          format: jpeg
        """
        result = {}
        current_file = None
        current_props = {}
        
        for line in output.strip().split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            
            # Property lines have "key: value" format with leading whitespace
            if ': ' in line and (line.startswith('  ') or line.startswith('\t')):
                parts = stripped.split(': ', 1)
                if len(parts) == 2:
                    current_props[parts[0]] = parts[1]
            else:
                # This is a filepath line — save previous file's props
                if current_file and current_props:
                    result[current_file] = current_props
                current_file = stripped
                current_props = {}
        
        # Don't forget the last file
        if current_file and current_props:
            result[current_file] = current_props
        
        return result

    def _parse_sips_output(self, output: str) -> Dict[str, str]:
        """Parse single-file sips output (kept for compatibility)."""
        data = {}
        lines = output.strip().split('\n')
        for line in lines:
            parts = line.split(': ', 1)
            if len(parts) == 2:
                key = parts[0].strip()
                val = parts[1].strip()
                data[key] = val
        return data

    async def _inspect_ffmpeg(self, filepath: str) -> Optional[MediaAsset]:
        """
        Fallback for non-macOS environments (Docker/Linux).
        Uses Pillow (PIL) for cross-platform image inspection.
        """
        try:
            from PIL import Image
            
            loop = asyncio.get_event_loop()
            
            def _load_image():
                with Image.open(filepath) as img:
                    width, height = img.size
                    fmt = img.format or 'unknown'
                    return width, height, fmt
            
            width, height, fmt = await loop.run_in_executor(None, _load_image)
            
            i_meta = ImageMetadata(
                width=width,
                height=height,
                format=fmt.lower()
            )
            
            file_stat = await asyncio.to_thread(os.stat, filepath)
            size_mb = file_stat.st_size / (1024 * 1024)
            mtime = int(file_stat.st_mtime)
            
            return MediaAsset(
                FilePath=filepath,
                Size_MB=size_mb,
                media_type=MediaType.IMAGE,
                image_metadata=i_meta,
                mtime=mtime,
                imported_at=0
            )
            
        except Exception as e:
            print(f"❌ Error inspecting image {filepath}: {e}")
            return None
