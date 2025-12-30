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
            # Use pad filter to add letterboxing/pillarboxing while preserving aspect ratio
            # scale: fit within 480x270 while preserving aspect ratio
            # pad: add black bars to reach exactly 480x270
            vf_filter = "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2:black"
            cmd = [
                "ffmpeg", "-ss", seek_time, "-i", video_path,
                "-vframes", "1", "-q:v", "4",
                "-vf", vf_filter,
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

        # Get the best available encoder
        encoder, encoder_opts = get_best_encoder()
        
        cmd = [
            "ffmpeg",
            "-ss", ss,
            "-t", "5",
            "-i", video_path,
            "-vf", "scale=480:-2",
            "-an",
            "-c:v", encoder,
            *encoder_opts,
            prev_path,
            "-y",
            "-loglevel", "quiet"
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)
        except:
            return ""
    return prev_name


# --- HARDWARE ENCODER DETECTION ---
_cached_encoder = None

def detect_hw_encoder() -> tuple:
    """
    Detect available hardware encoders.
    Returns: (encoder_name, encoder_options_list)
    """
    import sys
    
    # Try NVIDIA NVENC first (fastest)
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5
        )
        encoders_output = result.stdout
        
        # Check for NVIDIA NVENC H.264 (Windows/Linux with NVIDIA GPU)
        if "h264_nvenc" in encoders_output:
            # Verify it actually works with larger dimensions (NVENC has minimum size)
            test_cmd = ["ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1", 
                       "-c:v", "h264_nvenc", "-f", "null", "-", "-y", "-loglevel", "quiet"]
            test_result = subprocess.run(test_cmd, capture_output=True, timeout=10)
            if test_result.returncode == 0:
                return ("h264_nvenc", ["-preset", "p1", "-tune", "ll"])
        
        # Check for NVIDIA NVENC HEVC (fallback if h264_nvenc not available)
        if "hevc_nvenc" in encoders_output:
            test_cmd = ["ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1", 
                       "-c:v", "hevc_nvenc", "-f", "null", "-", "-y", "-loglevel", "quiet"]
            test_result = subprocess.run(test_cmd, capture_output=True, timeout=10)
            if test_result.returncode == 0:
                return ("hevc_nvenc", ["-preset", "p1"])
        
        # Check for Apple VideoToolbox (macOS)
        if sys.platform == "darwin" and "h264_videotoolbox" in encoders_output:
            return ("h264_videotoolbox", ["-q:v", "65"])
        
        # Check for Intel QuickSync (Windows/Linux with Intel iGPU)
        if "h264_qsv" in encoders_output:
            test_cmd = ["ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
                       "-c:v", "h264_qsv", "-f", "null", "-", "-y", "-loglevel", "quiet"]
            test_result = subprocess.run(test_cmd, capture_output=True, timeout=10)
            if test_result.returncode == 0:
                return ("h264_qsv", ["-preset", "veryfast"])
        
        # Check for VAAPI (Linux Intel/AMD standard)
        if "h264_vaapi" in encoders_output:
            # Check if we can actually open the device (often /dev/dri/renderD128)
            test_cmd = [
                "ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
                "-vaapi_device", "/dev/dri/renderD128",
                "-vf", "format=nv12,hwupload",
                "-c:v", "h264_vaapi",
                "-f", "null", "-", "-y", "-loglevel", "error"
            ]
            test_result = subprocess.run(test_cmd, capture_output=True, timeout=10)
            if test_result.returncode == 0:
                print("✅ VAAPI Test Passed")
                return ("h264_vaapi", [
                    "-vaapi_device", "/dev/dri/renderD128", 
                    "-vf", "format=nv12,hwupload"
                ])
            else:
                print(f"⚠️ VAAPI Test Failed: {test_result.stderr.decode().strip()}")
        else:
             print("ℹ️ h264_vaapi not found in ffmpeg encoders")
            
    except Exception as e:
        print(f"⚠️ Encoder detection critical error: {e}")
    
    # Fallback to software encoder
    print("⚠️ Falling back to software encoding (libx264)")
    return ("libx264", ["-preset", "ultrafast", "-crf", "28"])


def get_best_encoder() -> tuple:
    """Get cached best encoder, detecting on first call."""
    global _cached_encoder
    if _cached_encoder is None:
        _cached_encoder = detect_hw_encoder()
        encoder_name = _cached_encoder[0]
        if encoder_name != "libx264":
            print(f"🚀 Using hardware encoder: {encoder_name}")
        else:
            print(f"📦 Using software encoder: {encoder_name}")
    return _cached_encoder


# --- OPTIMAL WORKER COUNT ---
_cached_workers = None

def get_optimal_workers() -> int:
    """
    Detect optimal worker count based on hardware.
    - NVIDIA GPUs: Based on VRAM (more VRAM = more concurrent encodes)
    - Apple Silicon: Based on CPU cores
    - Software fallback: Based on CPU cores / 2
    """
    global _cached_workers
    if _cached_workers is not None:
        return _cached_workers
    
    import os
    import sys
    
    encoder, _ = get_best_encoder()
    cpu_cores = os.cpu_count() or 4
    
    # For hardware encoders, try to detect GPU capabilities
    if encoder in ("h264_nvenc", "hevc_nvenc"):
        try:
            # Query NVIDIA GPU memory using nvidia-smi
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                # Get first GPU's memory in MB
                vram_mb = int(result.stdout.strip().split('\n')[0])
                # RTX 4090 = 24GB, 3090 = 24GB, 3080 = 10GB, 3060 = 12GB
                # Rule: 1 worker per 3GB of VRAM, max 12, min 4
                workers = max(4, min(12, vram_mb // 3000))
                _cached_workers = workers
                print(f"🎮 Detected {vram_mb}MB GPU VRAM → using {workers} parallel workers")
                return workers
        except Exception:
            pass
        # NVENC default fallback
        _cached_workers = 6
        print(f"🎮 NVIDIA GPU detected → using 6 parallel workers")
        return 6
    
    elif encoder == "h264_videotoolbox":
        # Apple Silicon: use more workers, it handles it well
        workers = min(8, cpu_cores)
        _cached_workers = workers
        print(f"🍎 Apple Silicon detected → using {workers} parallel workers")
        return workers
    
    elif encoder == "h264_qsv":
        # Intel QuickSync: moderate parallelism
        _cached_workers = 4
        print(f"🔵 Intel QuickSync detected → using 4 parallel workers")
        return 4

    elif encoder == "h264_vaapi":
        # VAAPI: moderate parallelism
        _cached_workers = 4
        print(f"🐧 VAAPI Hardware Acceleration detected → using 4 parallel workers")
        return 4
    
    else:
        # Software encoding: CPU bound, use half the cores
        workers = max(2, cpu_cores // 2)
        _cached_workers = workers
        print(f"💻 Using {workers} parallel workers (CPU-based)")
        return workers

def process_video(filepath: str, cache: Dict[str, Any], rebuild_mode: str = None) -> Optional[Dict[str, Any]]:
    """
    Process a video file and generate metadata, thumbnail, and preview.
    
    Args:
        filepath: Path to the video file
        cache: The cache dictionary
        rebuild_mode: 'thumbs' to only regenerate thumbnails, 
                      'previews' to only regenerate previews,
                      None for normal operation (generate missing only)
    """
    filepath = os.path.abspath(filepath)
    try:
        stats = os.stat(filepath)
        size_mb = stats.st_size / (1024 * 1024)
        mtime = stats.st_mtime

        # Check cache for existing data
        cached_entry = cache.get(filepath, {})
        
        # For rebuild modes, use cached values for the other type
        if rebuild_mode == 'thumbs':
            # Only regenerate thumbnail, keep existing preview from cache
            existing_preview = cached_entry.get("preview", "")
        elif rebuild_mode == 'previews':
            # Only regenerate preview, keep existing thumbnail from cache
            existing_thumb = cached_entry.get("thumb", "")
        else:
            # Normal mode - check if fully cached and files exist
            if filepath in cache:
                entry = cached_entry
                if entry.get("mtime") == mtime and entry.get("size_mb") == size_mb and "codec" in entry and "preview" in entry:
                    thumb_path = os.path.join(THUMB_DIR, entry["thumb"])
                    prev_path = os.path.join(PREVIEW_DIR, entry["preview"])
                    if os.path.exists(thumb_path) and os.path.exists(prev_path) and os.path.getsize(prev_path) > 1000:
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

        # Generate media based on rebuild mode
        if rebuild_mode == 'thumbs':
            thumb = create_thumbnail(filepath)
            preview = existing_preview
        elif rebuild_mode == 'previews':
            thumb = existing_thumb
            preview = create_preview_clip(filepath)
        else:
            thumb = create_thumbnail(filepath)
            preview = create_preview_clip(filepath)

        # Preserve the hidden state if it exists in the cache
        is_hidden = cached_entry.get("hidden", False)
        is_favorite = cached_entry.get("favorite", False)

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
            "hidden": is_hidden,
            "favorite": is_favorite
        }
        return result
    except:
        return None
