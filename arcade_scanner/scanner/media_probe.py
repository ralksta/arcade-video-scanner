import json
import asyncio
from typing import Dict, Any, Optional
from ..models.video_entry import VideoEntry
from ..config import config

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
            return {}

    async def _check_decoder_errors(self, filepath: str) -> bool:
        """
        Runs a fast decode pass via `ffmpeg -f null -` and returns True if
        decoder errors (corrupt frames, missing references, etc.) are found.
        Only checks the first 30 seconds to keep scan performance acceptable.
        """
        cmd = [
            config.settings.ffmpeg_path or "ffmpeg",
            "-v", "error",
            "-t", "30",        # Only probe first 30 seconds — fast even for large files
            "-i", filepath,
            "-f", "null", "-",
        ]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
            
            # Any output on stderr = decoder errors/warnings
            return bool(stderr.decode('utf-8').strip())
        except Exception:
            return False

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

            # Corruption check: decode pass to detect broken frames/streams
            # Only run on actual video files (skip images, audio-only, etc.)
            has_error = False
            if video_stream:
                has_error = await self._check_decoder_errors(filepath)
                
            if has_error:
                status = "CORRUPT"
            
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
        # Kept for compatibility but no longer needed
        pass

# Singleton instance removed to avoid multiprocessing side-effects.
# Instantiate MediaProbe explicitly or via ScannerManager.

