import json
import subprocess
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, Any, Optional
import signal
from ..models.video_entry import VideoEntry

def _init_worker():
    """Ignore SIGINT in worker processes so main process handles shutdown."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def _run_ffprobe(filepath: str) -> Dict[str, Any]:
    """
    Sync function to run FFprobe.
    Executed in a separate process to avoid GIL blocking.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height:format=duration,bit_rate,size",
        "-of", "json",
        filepath,
    ]
    try:
        # Reduced timeout to avoid hanging processes
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=10
        )
        data = json.loads(result.stdout)
        return data
    except Exception:
        return {}

class MediaProbe:
    """
    Asynchronous wrapper for media analysis tools (FFmpeg/FFprobe).
    """
    def __init__(self, max_workers: int = 4):
        self.executor = ProcessPoolExecutor(max_workers=max_workers, initializer=_init_worker)

    async def get_metadata(self, filepath: str) -> Optional[VideoEntry]:
        """
        Extracts metadata and returns a populated VideoEntry (or None if failed).
        """
        loop = asyncio.get_event_loop()
        try:
            # Offload subprocess call to process pool
            raw_data = await loop.run_in_executor(self.executor, _run_ffprobe, filepath)
            
            if not raw_data or "streams" not in raw_data or not raw_data["streams"]:
                return None

            stream = raw_data["streams"][0]
            fmt = raw_data.get("format", {})

            # Safe extraction with defaults
            size_mb = float(fmt.get("size", 0)) / (1024 * 1024)
            duration = float(fmt.get("duration", 0))
            bitrate_bps = float(fmt.get("bit_rate", 0))
            width = int(stream.get("width", 0))
            height = int(stream.get("height", 0))
            codec = stream.get("codec_name", "unknown")

            # Determine status (legacy logic: > threshold = HIGH)
            # We will refine this later with config injection, but for now defaults.
            status = "OK" # Default, updated by manager logic typically
            
            return VideoEntry(
                FilePath=filepath,
                Size_MB=round(size_mb, 2),
                Bitrate_Mbps=round(bitrate_bps / 1_000_000, 2),
                Status=status,
                codec=codec,
                Duration_Sec=round(duration, 2),
                Width=width,
                Height=height
            )
            
        except Exception as e:
            # print(f"Probe failed for {filepath}: {e}")
            return None

    def shutdown(self):
        self.executor.shutdown(wait=True)

# Singleton instance removed to avoid multiprocessing side-effects.
# Instantiate MediaProbe explicitly or via ScannerManager.

