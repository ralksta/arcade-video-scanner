import asyncio
import subprocess
import shutil
from typing import Optional, Dict

from ..models.media_asset import MediaAsset, MediaType, ImageMetadata
from .inspector import MediaInspector

class ImageInspector(MediaInspector):
    """
    Inspector for Image Files.
    Uses native macOS 'sips' for high performance metadata extraction without heavy dependencies.
    Falls back to ffmpeg if sips is missing (cross-platform safety).
    """
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

    def can_handle(self, filepath: str) -> bool:
        return any(filepath.lower().endswith(ext) for ext in self.IMAGE_EXTENSIONS)

    async def inspect(self, filepath: str) -> Optional[MediaAsset]:
        if self.has_sips:
            return await self._inspect_sips(filepath)
        else:
            return await self._inspect_ffmpeg(filepath)

    async def _inspect_sips(self, filepath: str) -> Optional[MediaAsset]:
        # sips -g pixelWidth -g pixelHeight -g format [file]
        try:
            cmd = ['sips', '-g', 'pixelWidth', '-g', 'pixelHeight', '-g', 'format', filepath]
            
            # Run asynchronously
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode != 0:
                print(f"⚠️ sips failed for {filepath}: {stderr.decode()}")
                return None

            output = stdout.decode()
            properties = self._parse_sips_output(output)
            
            # Construct Metadata
            w = int(properties.get('pixelWidth', 0))
            h = int(properties.get('pixelHeight', 0))
            fmt = properties.get('format', 'unknown')
            
            i_meta = ImageMetadata(
                width=w,
                height=h,
                format=fmt
            )
            
            # Get file size safely
            file_stat = await asyncio.to_thread(lambda: __import__('os').stat(filepath))
            size_mb = file_stat.st_size / (1024 * 1024)
            mtime = int(file_stat.st_mtime)

            return MediaAsset(
                FilePath=filepath,
                Size_MB=size_mb,
                media_type=MediaType.IMAGE,
                image_metadata=i_meta,
                mtime=mtime,
                imported_at=0 # Will be set by manager
            )
            
        except Exception as e:
            print(f"Error inspecting image {filepath}: {e}")
            return None

    def _parse_sips_output(self, output: str) -> Dict[str, str]:
        """
        Parse sips output like:
        /path/to/file.png
          pixelWidth: 1920
          pixelHeight: 1080
          format: png
        """
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
        # Implementation placeholder / fallback
        # Can use similar logic to VideoInspector but simplified
        return None
