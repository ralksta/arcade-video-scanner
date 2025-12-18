import hashlib
import json
import os
import subprocess
from typing import Any, Dict, Optional
from arcade_scanner.app_config import (
    THUMB_DIR, PREVIEW_DIR, BITRATE_THRESHOLD_KBPS
)

def get_video_metadata(filepath: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name:format=duration,bit_rate",
        "-of",
        "json",
        filepath,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=10
        )
        data = json.loads(result.stdout)
        if "streams" in data and len(data["streams"]) > 0:
            return data
    except:
        pass
    return {}

def create_thumbnail(video_path: str) -> str:
    file_hash = hashlib.md5(video_path.encode()).hexdigest()
    thumb_name = f"thumb_{file_hash}.jpg"
    thumb_path = os.path.join(THUMB_DIR, thumb_name)
    
    if not os.path.exists(thumb_path) or os.path.getsize(thumb_path) == 0:
        # Get duration for smart seeking
        duration = 0
        try:
            cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            duration = float(subprocess.check_output(cmd_dur, stderr=subprocess.DEVNULL, timeout=5).decode().strip())
        except:
            pass

        # Smart seek: 10% into the video, max 60s
        ss = "0"
        if duration > 5:
            ss = str(min(60, int(duration * 0.1)))

        def try_extract(seek_time):
            cmd = [
                "ffmpeg", "-ss", seek_time, "-i", video_path,
                "-vframes", "1", "-q:v", "4", "-s", "480x270",
                thumb_path, "-y", "-loglevel", "quiet"
            ]
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                return os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0
            except:
                return False

        # Attempt 1: Smart Seek
        success = try_extract(ss)
        
        # Attempt 2: Fallback to 0s if failed
        if not success and ss != "0":
            success = try_extract("0")

        if not success:
            return ""
            
    return thumb_name

def create_preview_clip(video_path: str) -> str:
    file_hash = hashlib.md5(video_path.encode()).hexdigest()
    prev_name = f"prev_{file_hash}.mp4"
    prev_path = os.path.join(PREVIEW_DIR, prev_name)
    
    if not os.path.exists(prev_path) or os.path.getsize(prev_path) < 1000:
        duration = 0
        try:
            cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path]
            duration = float(subprocess.check_output(cmd_dur, stderr=subprocess.DEVNULL).decode().strip())
        except:
            pass

        ss = "0"
        if duration > 30:
            ss = str(min(60, int(duration * 0.1)))

        cmd = [
            "ffmpeg",
            "-ss", ss,
            "-t", "5",
            "-i", video_path,
            "-vf", "scale=480:-2",
            "-an",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            prev_path,
            "-y",
            "-loglevel", "quiet"
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        except:
            return ""
    return prev_name

def process_video(filepath: str, cache: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    filepath = os.path.abspath(filepath)
    try:
        stats = os.stat(filepath)
        size_mb = stats.st_size / (1024 * 1024)
        mtime = stats.st_mtime

        if filepath in cache:
            entry = cache[filepath]
            if entry.get("mtime") == mtime and entry.get("size_mb") == size_mb and "codec" in entry and "preview" in entry:
                thumb_path = os.path.join(THUMB_DIR, entry["thumb"])
                prev_path = os.path.join(PREVIEW_DIR, entry["preview"])
                if os.path.exists(thumb_path) and os.path.exists(prev_path) and os.path.getsize(prev_path) > 1000:
                    # Ensure hidden state is preserved in the returned cached entry
                    if "hidden" not in entry:
                        entry["hidden"] = False
                    return entry

        meta = get_video_metadata(filepath)
        mbps = 0.0
        codec = "unknown"
        if meta:
            if "format" in meta and meta["format"].get("bit_rate"):
                mbps = int(meta["format"].get("bit_rate")) / 1000000
            if "streams" in meta and len(meta["streams"]) > 0:
                codec = meta["streams"][0].get("codec_name", "unknown")

        thumb = create_thumbnail(filepath)
        preview = create_preview_clip(filepath)

        # Preserve the hidden state if it exists in the cache
        is_hidden = False
        if filepath in cache:
            is_hidden = cache[filepath].get("hidden", False)

        result = {
            "Status": "HIGH" if (mbps * 1000) > BITRATE_THRESHOLD_KBPS else "OK",
            "Bitrate_Mbps": mbps,
            "Size_MB": size_mb,
            "FilePath": filepath,
            "thumb": thumb,
            "preview": preview,
            "mtime": mtime,
            "size_mb": size_mb,
            "codec": codec,
            "hidden": is_hidden
        }
        return result
    except:
        return None
