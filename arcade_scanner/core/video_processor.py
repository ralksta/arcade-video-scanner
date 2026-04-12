import hashlib
import json
import logging
import os
import subprocess
from typing import Any, Dict, Optional
from arcade_scanner.config import config

logger = logging.getLogger(__name__)

# Module-level constants (not recreated on every call)
IMAGE_EXTENSIONS = frozenset({'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.heic', '.avif'})


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
        # Use os.fsencode for path to handle surrogates safely in subprocess
        safe_path = os.fsencode(filepath)
        cmd[cmd.index(filepath)] = safe_path
        
        result = subprocess.run(
            cmd, capture_output=True, text=False, check=True, timeout=60
        )
        data = json.loads(result.stdout.decode('utf-8', 'ignore'))
        if "streams" in data and len(data["streams"]) > 0:
            return data
    except Exception as e:
        logger.debug("get_video_metadata failed for %s: %s", filepath, e)
    return {}

def create_thumbnail(video_path: str) -> str:
    # Use surrogateescape to handle Windows-originating surrogate characters in paths
    file_hash = hashlib.md5(video_path.encode('utf-8', 'surrogateescape')).hexdigest()
    thumb_name = f"thumb_{file_hash}.jpg"
    thumb_path = os.path.join(config.thumb_dir, thumb_name)
    
    if not os.path.exists(thumb_path) or os.path.getsize(thumb_path) == 0:
        # Check if image (Image processing without seeking)
        is_image = any(video_path.lower().endswith(ext) for ext in IMAGE_EXTENSIONS)
        
        if is_image:
             vf_filter = "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:black"
             try:
                # Use os.fsencode to handle surrogates safely in subprocess
                encoded_cmd = [os.fsencode(arg) if isinstance(arg, str) else arg for arg in cmd]
                subprocess.run(encoded_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
                    return thumb_name
             except Exception as e:
                logger.warning("Image thumbnail failed for %s: %s", video_path, e)
             return ""

        # Get duration for smart seeking
        duration = 0
        try:
            cmd_dur = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", os.fsencode(video_path)]
            duration = float(subprocess.check_output(cmd_dur, stderr=subprocess.DEVNULL, timeout=60).decode().strip())
        except Exception as e:
            logger.debug("Duration probe failed for %s: %s", video_path, e)

        # Smart seek: 10% into the video, max 60s
        ss = "0"
        if duration > 5:
            ss = str(min(60, int(duration * 0.1)))

        def try_extract(seek_time, use_scene_detect=False):
            vf_filter = "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:black"
            if use_scene_detect:
                vf_filter = f"select='gt(scene\\,0.4)',{vf_filter}"
            
            cmd = ["ffmpeg", "-ss", seek_time]
            if use_scene_detect:
                cmd.extend(["-t", "10"])  # Search up to 10 seconds for a scene change
                
            cmd.extend([
                "-i", video_path,
                "-vframes", "1", "-q:v", "4",
                "-vf", vf_filter,
                thumb_path, "-y", "-loglevel", "quiet"
            ])
            try:
                # Use os.fsencode to handle surrogates safely in subprocess
                encoded_cmd = [os.fsencode(arg) if isinstance(arg, str) else arg for arg in cmd]
                subprocess.run(encoded_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
                return os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0
            except Exception as e:
                logger.warning("Thumbnail extract failed at %s (scene_detect=%s) for %s: %s", seek_time, use_scene_detect, video_path, e)
                return False

        # Attempt 1: Smart Seek with Scene Detection
        success = try_extract(ss, use_scene_detect=True)
        
        # Attempt 2: Smart Seek without Scene Detection
        if not success:
            success = try_extract(ss, use_scene_detect=False)
        
        # Attempt 3: Fallback to 0s if failed
        if not success and ss != "0":
            success = try_extract("0", use_scene_detect=False)

        if not success:
            return ""
            
    return thumb_name




# --- HARDWARE ENCODER DETECTION ---
from arcade_scanner.core.hw_encode_detect import get_best_h264_encoder as get_best_encoder, get_optimal_workers

def process_video(filepath: str, cache: Dict[str, Any], rebuild_mode: str = None) -> Optional[Dict[str, Any]]:
    """
    Legacy method kept for compatibility if needed, but updated to use new config.
    """
    filepath = os.path.abspath(filepath)
    try:
        stats = os.stat(filepath)
        size_mb = stats.st_size / (1024 * 1024)
        mtime = stats.st_mtime

        cached_entry = cache.get(filepath, {})
        
        if rebuild_mode == 'thumbs':
            existing_preview = cached_entry.get("preview", "")
        elif rebuild_mode == 'previews':
            existing_thumb = cached_entry.get("thumb", "")
        else:
            if filepath in cache:
                entry = cached_entry
                if entry.get("mtime") == mtime and entry.get("size_mb") == size_mb and "codec" in entry:
                    thumb_path = os.path.join(config.thumb_dir, entry["thumb"])
                    if os.path.exists(thumb_path):
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

        if rebuild_mode == 'thumbs':
            thumb = create_thumbnail(filepath)
        else:
            thumb = existing_thumb if rebuild_mode == 'previews' else create_thumbnail(filepath)
            
        # Preview generation removed
        preview = ""

        is_hidden = cached_entry.get("hidden", False)
        is_favorite = cached_entry.get("favorite", False)

        result = {
            "Status": "HIGH" if (mbps * 1000) > config.settings.bitrate_threshold_kbps else "OK",
            "Bitrate_Mbps": mbps,
            "Size_MB": size_mb,
            "FilePath": filepath,
            "thumb": thumb,
            "preview": preview,
            "mtime": mtime,
            "size_mb": size_mb,
            "codec": codec,
            "hidden": is_hidden,
            "favorite": is_favorite
        }
        return result
    except Exception as e:
        logger.error("process_video failed for %s: %s", filepath, e)
        return None
