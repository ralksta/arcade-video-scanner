import os
import sys
import subprocess
import logging

logger = logging.getLogger(__name__)

def get_available_ffmpeg_encoders() -> str:
    """Run ffmpeg -encoders and return stdout."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except Exception as e:
        logger.debug("Failed to get ffmpeg encoders: %s", e)
        return ""

def test_ffmpeg_encoder(codec: str, extra_args: list = None) -> bool:
    """Test if an encoder actually works by performing a tiny lavfi encode."""
    if extra_args is None:
        extra_args = []
    
    cmd = ["ffmpeg", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1"]
    cmd.extend(extra_args)
    cmd.extend(["-c:v", codec, "-f", "null", "-", "-y", "-loglevel", "quiet"])
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=10)
        return result.returncode == 0
    except Exception:
        return False

def get_vaapi_device(log_fn=None) -> str:
    """Detect the best VAAPI device, testing common paths."""
    if log_fn is None:
        log_fn = logger.info
    devices = ["/dev/dri/renderD128", "/dev/dri/card0"]
    for dev in devices:
        if not os.path.exists(dev):
            continue
            
        log_fn(f"🕵️ Testing VAAPI on {dev}...")
        if test_ffmpeg_encoder("h264_vaapi", ["-vaapi_device", dev, "-vf", "format=nv12,hwupload"]):
            log_fn(f"✅ VAAPI Working on {dev}")
            return dev
        else:
            log_fn(f"❌ Failed on {dev}")
            
    log_fn("⚠️ VAAPI failed on all devices.")
    return None

def detect_h264_encoder(log_fn=None) -> tuple:
    """
    Detect the best H.264 hardware encoder for the web UI (fast processing).
    Returns: (codec_name, list_of_extra_ffmpeg_args)
    """
    if log_fn is None:
        log_fn = logger.info
        
    encoders = get_available_ffmpeg_encoders()
    
    # NVIDIA
    if "h264_nvenc" in encoders and test_ffmpeg_encoder("h264_nvenc", ["-preset", "p1", "-tune", "ll"]):
        return ("h264_nvenc", ["-preset", "p1", "-tune", "ll"])
    if "hevc_nvenc" in encoders and test_ffmpeg_encoder("hevc_nvenc", ["-preset", "p1"]):
        return ("hevc_nvenc", ["-preset", "p1"])
        
    # Apple Silicon / Mac
    if sys.platform == "darwin" and "h264_videotoolbox" in encoders:
        return ("h264_videotoolbox", ["-q:v", "65"])
        
    # Intel QSV
    if "h264_qsv" in encoders and test_ffmpeg_encoder("h264_qsv", ["-preset", "veryfast"]):
        return ("h264_qsv", ["-preset", "veryfast"])
        
    # Linux VAAPI
    if "h264_vaapi" in encoders:
        dev = get_vaapi_device(log_fn)
        if dev:
            return ("h264_vaapi", ["-vaapi_device", dev, "-vf", "format=nv12,hwupload"])
            
    log_fn("⚠️ Falling back to software encoding (libx264)")
    return ("libx264", ["-preset", "ultrafast", "-crf", "28"])

_cached_h264_encoder = None
def get_best_h264_encoder(log_fn=None) -> tuple:
    global _cached_h264_encoder
    if log_fn is None:
        log_fn = logger.info
    if _cached_h264_encoder is None:
        _cached_h264_encoder = detect_h264_encoder(log_fn=log_fn)
        encoder_name = _cached_h264_encoder[0]
        if encoder_name != "libx264":
            log_fn(f"🚀 Using hardware encoder: {encoder_name}")
        else:
            log_fn(f"📦 Using software encoder: {encoder_name}")
    return _cached_h264_encoder

def detect_hevc_optimizer_encoder() -> str:
    """
    Detect the best HEVC hardware encoder profile key for the standalone video optimizer.
    Returns strings matching the ENCODER_PROFILES dict.
    """
    if sys.platform == 'darwin':
        return 'videotoolbox'
        
    encoders_stdout = get_available_ffmpeg_encoders()
    
    if 'hevc_nvenc' in encoders_stdout:
        return 'nvenc'
    if 'hevc_qsv' in encoders_stdout:
        return 'qsv'
    if 'hevc_vaapi' in encoders_stdout:
        if os.path.exists("/dev/dri/renderD128") or os.path.exists("/dev/dri/card0"):
            return 'vaapi'
    if 'hevc_videotoolbox' in encoders_stdout:
        return 'videotoolbox'
        
    return 'libx265'

_cached_workers = None
def get_optimal_workers(log_fn=None) -> int:
    """
    Detect optimal worker count based on hardware.
    """
    global _cached_workers
    if log_fn is None:
        log_fn = logger.info
    if _cached_workers is not None:
        return _cached_workers
    
    encoder, _ = get_best_h264_encoder(log_fn)
    cpu_cores = os.cpu_count() or 4
    
    if encoder in ("h264_nvenc", "hevc_nvenc"):
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                vram_mb = int(result.stdout.strip().split('\n')[0])
                workers = max(4, min(12, vram_mb // 3000))
                _cached_workers = workers
                log_fn(f"Detected {vram_mb}MB GPU VRAM → using {workers} parallel workers")
                return workers
        except Exception as e:
            logger.debug(f"nvidia-smi query failed: {e}")
        _cached_workers = 6
        log_fn("NVIDIA GPU detected → using 6 parallel workers")
        return 6
    
    elif encoder == "h264_videotoolbox":
        p_cores = None
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                p_cores = int(result.stdout.strip())
        except Exception as e:
            logger.debug(f"sysctl P-core query failed: {e}")

        if p_cores is None:
            p_cores = cpu_cores

        workers = min(16, p_cores)
        _cached_workers = workers
        log_fn(f"Apple Silicon detected → {p_cores} P-cores → using {workers} parallel workers")
        return workers
    
    elif encoder == "h264_qsv":
        _cached_workers = 4
        log_fn("Intel QuickSync detected → using 4 parallel workers")
        return 4

    elif encoder == "h264_vaapi":
        _cached_workers = 4
        log_fn("VAAPI Hardware Acceleration detected → using 4 parallel workers")
        return 4
    
    else:
        workers = max(2, cpu_cores // 2)
        _cached_workers = workers
        log_fn(f"Using {workers} parallel workers (CPU-based)")
        return workers
