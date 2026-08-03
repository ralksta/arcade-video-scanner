import asyncio
import json
from typing import Any, Dict, Optional

from ..config import config
from ..models.video_entry import VideoEntry


def _as_float(value, default: float = 0.0) -> float:
    """Parse an ffprobe number, tolerating the "N/A" it emits for unknowns."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _as_int(value, default: int = 0) -> int:
    """Integer counterpart to _as_float; also accepts "1920.0" style values."""
    try:
        return int(value)
    except (TypeError, ValueError):
        pass
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


class MediaProbe:
    """
    Asynchronous wrapper for media analysis tools (FFmpeg/FFprobe).
    """
    def __init__(self, max_workers: int = 4):
        # max_workers is kept for backwards compatibility but not used,
        # concurrency is handled by ScannerManager's Semaphores.
        pass

    async def _run_ffprobe(self, filepath: str) -> Dict[str, Any]:
        """
        Async function to run FFprobe.
        """
        cmd = [
            config.settings.ffprobe_path or "ffprobe",
            "-v", "error",
            "-show_entries", "stream=index,codec_type,codec_name,width,height,profile,level,pix_fmt,channels,avg_frame_rate:format=duration,bit_rate,size,format_name",
            "-of", "json",
            filepath,
        ]
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=20.0)

            if process.returncode != 0:
                return {}

            data = json.loads(stdout.decode('utf-8'))
            return data
        except Exception:
            # A timeout only cancels communicate() — ffprobe itself keeps
            # running. Reap it, or a library with a few unreadable files leaves
            # one stray process behind per probe.
            if process is not None and process.returncode is None:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            return {}



    async def get_metadata(self, filepath: str) -> Optional[VideoEntry]:
        """
        Extracts metadata and returns a populated VideoEntry (or None if failed).
        """
        try:
            raw_data = await self._run_ffprobe(filepath)

            if not raw_data or "streams" not in raw_data or not raw_data["streams"]:
                return None
            # Find video and audio streams
            video_stream = next((s for s in raw_data["streams"] if s.get("codec_type") == "video"), {})
            audio_stream = next((s for s in raw_data["streams"] if s.get("codec_type") == "audio"), {})

            fmt = raw_data.get("format", {})

            # Safe extraction with defaults. ffprobe writes "N/A" for values it
            # cannot determine; a single such field must zero itself, not cost
            # the whole file — get_metadata returning None means the video never
            # reaches the library at all.
            size_mb = _as_float(fmt.get("size", 0)) / (1024 * 1024)
            duration = _as_float(fmt.get("duration", 0))
            bitrate_bps = _as_float(fmt.get("bit_rate", 0))

            # Video Details
            width = _as_int(video_stream.get("width", 0))
            height = _as_int(video_stream.get("height", 0))
            video_codec = video_stream.get("codec_name", "unknown")
            profile = video_stream.get("profile", "")
            pixel_format = video_stream.get("pix_fmt", "")

            # Level can be numeric or string, handle gracefully
            level = _as_float(video_stream.get("level", 0))

            # Frame Rate
            fps_str = str(video_stream.get("avg_frame_rate", "0/0"))
            if "/" in fps_str:
                numerator, _, denominator = fps_str.partition("/")
                den = _as_float(denominator)
                fps = _as_float(numerator) / den if den > 0 else 0.0
            else:
                fps = _as_float(fps_str)

            # Audio Details
            audio_codec = audio_stream.get("codec_name", "unknown")
            audio_channels = _as_int(audio_stream.get("channels", 0))

            # Container
            container = fmt.get("format_name", "unknown")

            # Determine status (legacy logic: > threshold = HIGH)
            # We will refine this later with config injection, but for now defaults.
            # We rely on ffprobe returning valid metadata as the health check.
            # Deep decoding pass was removed to optimize scan speed.
            status = "OK"

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

        except Exception:
            return None

    def shutdown(self):
        # Kept for compatibility but no longer needed
        pass

# Singleton instance removed to avoid multiprocessing side-effects.
# Instantiate MediaProbe explicitly or via ScannerManager.

