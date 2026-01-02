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
        "-show_entries", "stream=index,codec_type,codec_name,width,height,profile,level,pix_fmt,channels,avg_frame_rate:format=duration,bit_rate,size,format_name",
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

            # Find video and audio streams
            video_stream = next((s for s in raw_data["streams"] if s.get("codec_type") == "video"), {})
            audio_stream = next((s for s in raw_data["streams"] if s.get("codec_type") == "audio"), {})
            
            fmt = raw_data.get("format", {})

            # Safe extraction with defaults
            size_mb = float(fmt.get("size", 0)) / (1024 * 1024)
            duration = float(fmt.get("duration", 0))
            bitrate_bps = float(fmt.get("bit_rate", 0))
            
            # Video Details
            width = int(video_stream.get("width", 0))
            height = int(video_stream.get("height", 0))
            video_codec = video_stream.get("codec_name", "unknown")
            profile = video_stream.get("profile", "")
            pixel_format = video_stream.get("pix_fmt", "")
            
            # Level can be numeric or string, handle gracefully
            level_raw = video_stream.get("level", 0)
            try:
                level = float(level_raw)
            except:
                level = 0.0
            
            # Frame Rate
            fps_str = video_stream.get("avg_frame_rate", "0/0")
            fps = 0.0
            if "/" in fps_str:
                try:
                    num, den = fps_str.split("/")
                    if float(den) > 0:
                        fps = float(num) / float(den)
                except:
                    pass
            else:
                try:
                    fps = float(fps_str)
                except:
                    pass

            # Audio Details
            audio_codec = audio_stream.get("codec_name", "unknown")
            audio_channels = int(audio_stream.get("channels", 0))
            
            # Container
            container = fmt.get("format_name", "unknown")

            # Determine status (legacy logic: > threshold = HIGH)
            # We will refine this later with config injection, but for now defaults.
            status = "OK" # Default, updated by manager logic typically
            
            return VideoEntry(
                FilePath=filepath,
                Size_MB=round(size_mb, 2),
                Bitrate_Mbps=round(bitrate_bps / 1_000_000, 2),
                Status=status,
                codec=video_codec,
                Duration_Sec=round(duration, 2),
                Width=width,
                Height=height,
                AudioCodec=audio_codec,
                AudioChannels=audio_channels,
                Container=container,
                Profile=profile,
                Level=level,
                PixelFormat=pixel_format,
                FrameRate=round(fps, 2)
            )
            
        except Exception as e:
            # print(f"Probe failed for {filepath}: {e}")
            return None

    def shutdown(self):
        self.executor.shutdown(wait=True)

# Singleton instance removed to avoid multiprocessing side-effects.
# Instantiate MediaProbe explicitly or via ScannerManager.

