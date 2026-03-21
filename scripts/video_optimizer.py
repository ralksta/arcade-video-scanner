#!/usr/bin/env python3
"""
Video Optimizer V2.4 - Multi-Platform Hardware Encoder with Bitrate Analysis
Supports: NVIDIA NVENC (RTX 4090), Apple VideoToolbox (M4 Max), Intel QuickSync (QSV)

New in V2.4: Bitrate analyzer integration ensures output never exceeds source bitrate.
"""
import os
import sys
import subprocess
import argparse
import json
import re
import time
import textwrap
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import threading
import queue

# Import arcade_scanner core utilities
# Use sys.path to avoid circular dependencies and keep script standalone
try:
    import sys as _sys
    _core_path = Path(__file__).parent.parent / "arcade_scanner" / "core"
    if _core_path.exists():
        _sys.path.insert(0, str(_core_path))
        from bitrate_analyzer import analyze_bitrate, BitrateProfile
        from hw_encode_detect import detect_hevc_optimizer_encoder
        _sys.path.pop(0)
        BITRATE_ANALYZER_AVAILABLE = True
        HW_DETECT_AVAILABLE = True
    else:
        BITRATE_ANALYZER_AVAILABLE = False
        HW_DETECT_AVAILABLE = False
except ImportError:
    BITRATE_ANALYZER_AVAILABLE = False
    HW_DETECT_AVAILABLE = False

# Logs directory
LOG_DIR = Path.home() / ".arcade-scanner" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- CONFIGURATION ---
MIN_SAVINGS = 20.0
MIN_QUALITY = 0.960
SAMPLE_DURATION = 5
DEFAULT_MIN_SIZE_MB = 0  # No minimum file size – process all files


# --- SSIM / SAVINGS THRESHOLDS ---
SSIM_MIN = 0.940           # Hard lower bound – reject anything below this
SSIM_ACCEPTABLE = 0.945    # Acceptable quality for fallback results
EXCELLENT_SAVINGS_PCT = 50.0  # Savings % considered excellent (early-exit in binary search)
EARLY_ABORT_RATIO = 0.95   # Abort encode early if output reaches this fraction of source size

# Quality ranges differ per encoder
# NVENC: CQ 0-51 (lower = better quality)
# VideoToolbox: q:v 0-100 (higher = better quality)
ENCODER_PROFILES = {
    'nvenc': {
        'name': 'NVIDIA NVENC (RTX 4090)',
        'codec': 'hevc_nvenc',
        'quality_range': (24, 44, 4),  # (start, max, step) - lower is better
        'quality_direction': 1,  # +1 means increase CQ = worse quality
        'hwaccel_input': ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'],
        'encoder_args': [
            '-preset', 'p5',
            '-tune', 'hq',
            '-rc', 'vbr',
            '-multipass', 'fullres',   # Two-pass encode: better quality at same bitrate
            '-tier', 'high',           # High Tier: lifts bitrate ceiling 6x vs Main (critical for 4K)
            '-b_ref_mode', 'middle',
            '-bf', '4',
            '-spatial-aq', '1',
            '-temporal-aq', '1',
            '-aq-strength', '15',      # Max (was 8) - protects fine detail in dark areas
            '-weighted_pred', '1',     # Better prediction for text/UI elements
            '-rc-lookahead', '32',
        ],
        'quality_flag': '-cq',
        'video_filter': 'scale_cuda=trunc(iw/2)*2:trunc(ih/2)*2:format=yuv420p',
    },
    'videotoolbox': {
        'name': 'Apple VideoToolbox (M4 Max)',
        'codec': 'hevc_videotoolbox',
        'quality_range': (75, 45, -10),  # (start, min, step) - higher is better
        'quality_direction': -1,  # -1 means decrease q = worse quality
        'hwaccel_input': [],  # VideoToolbox handles this implicitly
        'encoder_args': [
            '-profile:v', 'main',
            '-alpha_quality', '0.75',
            '-allow_sw', '0',  # Disable software fallback
            '-realtime', '0',          # Allow encoder more time -> better compression on M4 Max
        ],
        'quality_flag': '-q:v',
        'video_filter': 'format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2',
    },
    'qsv': {
        'name': 'Intel QuickSync (QSV)',
        'codec': 'hevc_qsv',
        'quality_range': (20, 32, 2),  # ICQ: lower is better quality
        'quality_direction': 1,        # +1 means increase val = worse quality
        'hwaccel_input': ['-hwaccel', 'auto'],
        'encoder_args': [
            '-preset', 'medium',
            '-look_ahead', '1',
        ],
        'quality_flag': '-global_quality',
        'video_filter': 'format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2',
    },
    'vaapi': {
        'name': 'Intel/AMD VAAPI (Linux)',
        'codec': 'hevc_vaapi',
        'quality_range': (24, 34, 2),  # QP: lower is better quality
        'quality_direction': 1,        # +1 means increase QP = worse quality
        'hwaccel_input': ['-hwaccel', 'vaapi', '-hwaccel_output_format', 'vaapi', '-vaapi_device', '/dev/dri/renderD128'],
        'encoder_args': [
            '-compression_level', '20',  # Slower preset for better compression
        ],
        'quality_flag': '-qp',
        'video_filter': 'scale_vaapi=w=iw:h=ih:format=nv12',  # VAAPI needs NV12 surface
    },
    'libx265': {
        'name': 'Software (libx265 CPU)',
        'codec': 'libx265',
        'quality_range': (24, 32, 2),  # CRF: lower is better quality
        'quality_direction': 1,  # +1 means increase CRF = worse quality
        'hwaccel_input': [],  # No hardware acceleration
        'encoder_args': [
            '-threads', '0',
            '-preset', 'medium',
            '-x265-params', 'log-level=error',
        ],
        'quality_flag': '-crf',
        'video_filter': 'format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2',
    },
    # --- AV1 Profiles (Experimental) ---
    'av1_videotoolbox': {
        'name': 'Apple VideoToolbox AV1 (M3/M4)',
        'codec': 'av1_videotoolbox',
        'quality_range': (60, 35, -10),  # q:v – higher is better
        'quality_direction': -1,
        'hwaccel_input': [],
        'encoder_args': [
            '-allow_sw', '0',
            '-realtime', '0',
        ],
        'quality_flag': '-q:v',
        'video_filter': 'format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2',
    },
    'av1_nvenc': {
        'name': 'NVIDIA NVENC AV1 (RTX 40xx)',
        'codec': 'av1_nvenc',
        'quality_range': (28, 48, 4),  # CQ – lower is better
        'quality_direction': 1,
        'hwaccel_input': ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda'],
        'encoder_args': [
            '-preset', 'p5',
            '-tune', 'hq',
            '-rc', 'vbr',
            '-multipass', 'fullres',
            '-tier', 'high',
            '-spatial-aq', '1',
            '-temporal-aq', '1',
            '-rc-lookahead', '32',
        ],
        'quality_flag': '-cq',
        'video_filter': 'scale_cuda=trunc(iw/2)*2:trunc(ih/2)*2:format=yuv420p',
    },
}

# --- ENCODING PRESET MAP ---
# Maps user-friendly preset names to encoder-specific ffmpeg preset strings.
# Keys are user presets: 'fast' | 'balanced' | 'best'
ENCODING_PRESET_MAP = {
    # libx265 (CPU software encoder)
    'libx265': {'fast': 'veryfast', 'balanced': 'medium', 'best': 'slow'},
    # NVIDIA NVENC: p1=fastest, p7=slowest/best quality
    'nvenc':   {'fast': 'p2',      'balanced': 'p5',    'best': 'p7'},
    # Intel QSV: veryfast/fast/medium/slow/veryslow
    'qsv':     {'fast': 'veryfast','balanced': 'medium', 'best': 'slow'},
    # AV1 NVENC inherits same as nvenc
    'av1_nvenc': {'fast': 'p2',    'balanced': 'p5',    'best': 'p7'},
    # VideoToolbox / VAAPI / AV1 VideoToolbox: no standard preset arg – handled separately
}


def apply_encoding_preset(profile: dict, preset: str) -> dict:
    """
    Return a modified copy of *profile* with the encoding preset applied.
    For encoders that support a -preset arg (nvenc, qsv, libx265) the mapped
    value replaces the existing entry.  For VideoToolbox / VAAPI we only
    touch the -realtime flag (0 = quality, 1 = speed).
    """
    import copy
    profile = copy.deepcopy(profile)
    codec = profile.get('codec', '')

    # Determine encoder family from codec name
    encoder_family = None
    for family in ENCODING_PRESET_MAP:
        if family in codec or codec.startswith(family.replace('_', '_')):
            encoder_family = family
            break
    # Special case: hevc_nvenc → nvenc family
    if codec == 'hevc_nvenc':
        encoder_family = 'nvenc'
    elif codec == 'hevc_qsv':
        encoder_family = 'qsv'
    elif codec == 'libx265':
        encoder_family = 'libx265'
    elif codec == 'av1_nvenc':
        encoder_family = 'av1_nvenc'

    preset_map = ENCODING_PRESET_MAP.get(encoder_family) if encoder_family else None
    target_preset = preset_map.get(preset, 'medium') if preset_map else None

    args = profile.get('encoder_args', [])

    if target_preset:
        # Replace or inject -preset VALUE
        if '-preset' in args:
            idx = args.index('-preset')
            args[idx + 1] = target_preset
        else:
            args = ['-preset', target_preset] + args
    elif codec in ('hevc_videotoolbox', 'av1_videotoolbox', 'hevc_vaapi'):
        # VideoToolbox / VAAPI: use -realtime as speed proxy
        realtime_val = '1' if preset == 'fast' else '0'
        if '-realtime' in args:
            idx = args.index('-realtime')
            args[idx + 1] = realtime_val
        # VAAPI only: use -compression_level for fine-tuning
        if codec == 'hevc_vaapi' and '-compression_level' in args:
            level_val = '32' if preset == 'fast' else ('20' if preset == 'best' else '24')
            idx = args.index('-compression_level')
            args[idx + 1] = level_val

    profile['encoder_args'] = args
    return profile


# --- COLORS ---
G = '\033[0;32m'
BG = '\033[1;32m'
R = '\033[0;31m'
Y = '\033[0;33m'
NC = '\033[0m'

# --- QUALITY METRIC (auto-detected: mssim or ssim) ---
_QUALITY_FILTER: Optional[str] = None  # Cached on first encode

# --- BATCH STATS ---
batch_stats = {
    'processed': 0,
    'skipped': 0,
    'success': 0,
    'failed': 0,
    'total_saved_bytes': 0,
    'total_time': 0
}

# --- LAST ENCODE RESULT (for logging) ---
last_encode_result = {
    'filename': None,
    'status': None,
    'quality': None,
    'ssim': None,
    'saved_pct': None,
    'saved_bytes': None,
    'duration': 0,
    'reason': None
}



def detect_encoder() -> str:
    """Auto-detect the best available encoder based on platform and hardware."""
    # Attempt to use the unified hardware encoder detection from arcade_scanner core
    if HW_DETECT_AVAILABLE:
        encoder = detect_hevc_optimizer_encoder()
        if encoder == 'libx265':
            print(f"{R}No hardware encoder detected. Using software encoder (slower).{NC}")
        return encoder
        
    # --- FALLBACK if running completely isolated ---
    if sys.platform == 'darwin':
        return 'videotoolbox'

    # Query ffmpeg encoder list once for all non-macOS platforms
    encoders_stdout = ""
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=5
        )
        encoders_stdout = result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    if 'hevc_nvenc' in encoders_stdout:
        return 'nvenc'
    if 'hevc_qsv' in encoders_stdout:
        return 'qsv'
    if 'hevc_vaapi' in encoders_stdout:
        # Prefer renderD128 for headless; card0 is a reasonable fallback
        if os.path.exists("/dev/dri/renderD128") or os.path.exists("/dev/dri/card0"):
            return 'vaapi'
    if 'hevc_videotoolbox' in encoders_stdout:
        return 'videotoolbox'

    print(f"{R}No hardware encoder detected. Using software encoder (slower).{NC}")
    return 'libx265'

def get_video_info(file_path: Path) -> Optional[Dict[str, Any]]:
    """Get video duration and stream info using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration:stream=width,height,codec_name,r_frame_rate',
        '-of', 'json', str(file_path)
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        duration = float(data.get('format', {}).get('duration', 0))
        video_stream = next((s for s in data.get('streams', []) if s.get('codec_type') == 'video'), {})

        width = int(video_stream.get('width', 0))
        height = int(video_stream.get('height', 0))
        codec = video_stream.get('codec_name', 'unknown')
        fps = video_stream.get('r_frame_rate', '0/0')

        if '/' in fps:
            n, d = map(int, fps.split('/'))
            fps_val = n / d if d != 0 else 0.0
        else:
            fps_val = float(fps)

        return {
            'duration': duration,
            'width': width,
            'height': height,
            'codec': codec,
            'fps': int(fps_val + 0.5)
        }
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError, OSError) as e:
        print(f"{R}Error probing {file_path}: {e}{NC}")
        return None

def parse_time_to_seconds(time_str: Optional[str]) -> float:
    """Convert time string (HH:MM:SS or SS) to seconds."""
    if not time_str:
        return 0.0
    try:
        if ':' in str(time_str):
            t = datetime.strptime(str(time_str), "%H:%M:%S")
            delta = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
            return delta.total_seconds()
        return float(time_str)
    except (ValueError, TypeError):
        return 0.0

def _detect_quality_filter() -> str:
    """Detect best available quality metric filter: MS-SSIM if available, else SSIM."""
    global _QUALITY_FILTER
    if _QUALITY_FILTER is not None:
        return _QUALITY_FILTER
    try:
        result = subprocess.run(
            ['ffmpeg', '-filters'],
            capture_output=True, text=True, timeout=5
        )
        _QUALITY_FILTER = 'mssim' if 'mssim' in result.stdout else 'ssim'
    except (subprocess.SubprocessError, FileNotFoundError):
        _QUALITY_FILTER = 'ssim'
    return _QUALITY_FILTER


def get_multi_ssim(
    original: Path,
    optimized: Path,
    orig_starts: list,
    opt_starts: list,
    duration: float,
) -> float:
    """
    Calculate quality score across N sample segments in ONE ffmpeg pass.

    Segments are trimmed from both inputs, concatenated pair-wise, then
    compared with a single ssim/mssim filter.  This is:
      - Faster: one subprocess instead of N sequential ones
      - More accurate: 3 sample points (25 / 50 / 75 %%) cover more content
      - Better score: natural mean over all segments (vs. fragile min() that
        was easily skewed by black fade frames)

    Uses MS-SSIM (perceptually better for fast game footage) if available,
    with automatic fallback to SSIM.
    """
    quality_filter = _detect_quality_filter()
    n = len(orig_starts)
    total_sample_duration = n * duration  # total frames to compare

    # Build filter_complex: trim segments, concat pairs, compare once
    fc: list = []
    for i, s in enumerate(orig_starts):
        fc.append(f"[0:v]trim=start={s:.3f}:end={s + duration:.3f},setpts=PTS-STARTPTS[oa{i}]")
    for i, s in enumerate(opt_starts):
        fc.append(f"[1:v]trim=start={s:.3f}:end={s + duration:.3f},setpts=PTS-STARTPTS[na{i}]")
    fc.append(''.join(f'[oa{i}]' for i in range(n)) + f"concat=n={n}:v=1:a=0[ocat]")
    fc.append(''.join(f'[na{i}]' for i in range(n)) + f"concat=n={n}:v=1:a=0[ncat]")
    fc.append(f"[ocat][ncat]{quality_filter}")

    cmd = [
        'ffmpeg', '-progress', 'pipe:1',
        '-i', str(original),
        '-i', str(optimized),
        '-filter_complex', ';'.join(fc),
        '-f', 'null', '-'
    ]
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        stderr_chunks = []
        out_time_us = 0
        total_us = total_sample_duration * 1_000_000

        try:
            term_cols = os.get_terminal_size().columns
            bar_length = max(10, min(30, term_cols - 50))
        except OSError:
            bar_length = 20

        while True:
            line = process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if line.startswith("out_time_us="):
                try:
                    out_time_us = int(line.split("=", 1)[1])
                except ValueError:
                    pass
                pct = min(100.0, out_time_us * 100 / total_us) if total_us > 0 else 0
                arrow = '█' * int(pct / 100 * bar_length)
                spaces = '░' * (bar_length - len(arrow))
                sys.stdout.write(f"\r\033[2K {Y}-> Checking quality... [{arrow}{spaces}] {int(pct)}%{NC}")
                sys.stdout.flush()

        # Drain stderr for SSIM result
        stderr_out = process.stderr.read()
        process.wait()

        # Clear the progress line
        sys.stdout.write(f"\r\033[2K")
        sys.stdout.flush()

        match = re.search(r'All:([\d.]+)', stderr_out)
        if match:
            return float(match.group(1))
    except (subprocess.SubprocessError, OSError) as e:
        print(f"{R}Error calculating quality score: {e}{NC}")
    return 0.0

def format_time(seconds):
    """Format seconds into MM:SS or HH:MM:SS."""
    if seconds < 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def format_size(bytes_val):
    """Format bytes into human readable string."""
    if bytes_val >= 1024**3:
        return f"{bytes_val / 1024**3:.2f} GB"
    elif bytes_val >= 1024**2:
        return f"{bytes_val / 1024**2:.1f} MB"
    else:
        return f"{bytes_val / 1024:.0f} KB"

def show_progress(current, total, encoder="", bitrate="0kb/s", speed="0x", elapsed=0):
    """Enhanced console progress bar with encoder info, elapsed time and ETA."""
    percent = float(current) * 100 / total if total > 0 else 0
    percent = min(100.0, percent)

    # Dynamically adapt bar_length to terminal width to prevent wrapping artefacts
    try:
        term_cols = os.get_terminal_size().columns
        # Reserve space for encoder name (~20), percent/speed/bitrate/time (~40) + margins
        bar_length = max(10, min(40, term_cols - 70))
    except OSError:
        bar_length = 20  # fallback if no TTY

    arrow = '█' * int(percent/100 * bar_length)
    spaces = '░' * (bar_length - len(arrow))
    
    if current > 0 and elapsed > 0:
        eta = (elapsed / current) * (total - current)
    else:
        eta = -1
    
    elapsed_str = format_time(elapsed)
    eta_str = format_time(eta)
    
    # \r = go to line start, \033[2K = erase entire line → no resize artefacts
    sys.stdout.write(f"\r\033[2K {G}{encoder}{NC} [{arrow}{spaces}] {BG}{int(percent)}%{NC} | {speed} | {bitrate} | {elapsed_str} / {eta_str}")
    sys.stdout.flush()

def build_ffmpeg_command(input_path, output_path, profile, quality_value, copy_audio=False, audio_mode='enhanced', ss=None, to=None, video_mode='compress', maxrate_kbps=None, bufsize_kbps=None, target_bitrate_kbps=None):
    """Build the ffmpeg command based on encoder profile.
    
    Args:
        maxrate_kbps: Optional peak bitrate cap (from bitrate analyzer) to prevent exceeding source
        bufsize_kbps: Optional buffer size for VBR smoothing
        target_bitrate_kbps: Optional target average bitrate (-b:v) for constrained-VBR.
            When set, this is the primary size control mechanism. Use this to force
            the encoder to target a specific average bitrate so output file size is predictable.
            Without this, quality-mode VBR (-q:v) can produce arbitrary bitrates.
    """
    cmd = ['ffmpeg', '-y']
    
    # Trim input if needed (fast seek)
    if ss: cmd.extend(['-ss', str(ss)])
    if to: cmd.extend(['-to', str(to)])
    
    if video_mode == 'copy':
        # Passthrough video
        cmd.extend(['-i', str(input_path)])
        cmd.extend(['-c:v', 'copy'])
    else:
        # Re-encode video
        cmd.extend(profile['hwaccel_input'])
        cmd.extend(['-i', str(input_path)])
        
        # Map video codec
        cmd.extend(['-c:v', profile['codec']])
        cmd.extend(profile['encoder_args'])

        # VideoToolbox mode selection:
        # -q:v (quality VBR) and -b:v (bitrate-controlled VBR) are MUTUALLY EXCLUSIVE.
        # When both are present, VideoToolbox ignores -b:v and uses quality mode only.
        # → Only add -q:v when we do NOT have a target bitrate; otherwise use pure -b:v mode.
        if not (target_bitrate_kbps and target_bitrate_kbps > 0):
            cmd.extend([profile['quality_flag'], str(quality_value)])

        cmd.extend(['-vf', profile['video_filter']])
        
        # Bitrate-controlled VBR: -b:v sets the average target, -maxrate caps the peak.
        # This is the PRIMARY size control mechanism when target_bitrate_kbps is set.
        if target_bitrate_kbps and target_bitrate_kbps > 0:
            cmd.extend(['-b:v', f'{int(target_bitrate_kbps)}k'])
        
        # Peak limiter: caps instantaneous bitrate spikes above the target average.
        if maxrate_kbps and maxrate_kbps > 0:
            cmd.extend(['-maxrate', f'{int(maxrate_kbps)}k'])
            if bufsize_kbps and bufsize_kbps > 0:
                cmd.extend(['-bufsize', f'{int(bufsize_kbps)}k'])
            else:
                cmd.extend(['-bufsize', f'{int(maxrate_kbps * 2)}k'])
    
    # Audio settings
    if copy_audio:
        cmd.extend(['-c:a', 'copy'])
    elif audio_mode == 'standard':
        # Standard AAC re-encode without normalization (flat)
        cmd.extend(['-c:a', 'aac', '-b:a', '192k', '-ar', '48000'])
    else:
        # Enhanced: Normalize channel layout → High-pass → Gate → Loudnorm
        # aformat=stereo: converts mono/5.1/any source to stereo before processing
        # -16 LUFS = YouTube/Twitch/streaming target (was -20 which is broadcast/radio)
        audio_filters = 'aformat=channel_layouts=stereo,highpass=f=100,agate=threshold=-55dB:range=0.05:ratio=2,loudnorm=I=-16:TP=-1.5:LRA=11'
        cmd.extend(['-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-af', audio_filters])

    cmd.extend([
        '-tag:v', 'hvc1',
        '-movflags', '+faststart+delay_moov',  # delay_moov: prevents partial/corrupt moov on aborted encodes
        '-fps_mode', 'vfr',                    # Preserve source timestamps; no dup/drop (any VFR source)
        # Explicit BT.709 color metadata - ensures correct rendering in browsers/players
        '-colorspace', 'bt709',
        '-color_primaries', 'bt709',
        '-color_trc', 'bt709',
        '-progress', 'pipe:1',
        '-loglevel', 'error',
        str(output_path)
    ])
    
    return cmd

def enqueue_output(out, q):
    """Read lines from stream and populate queue."""
    for line in iter(out.readline, ''):
        q.put(line)
    out.close()

def process_file(input_path, profile, min_size_mb=0, copy_audio=False, port=None, audio_mode='enhanced', ss=None, to=None, video_mode='compress', q_override=None):
    """Process a single video file. Returns (success, bytes_saved)."""
    input_path = Path(input_path)
    is_trim = ss is not None or to is not None
    
    if not input_path.exists():
        return (False, 0)

    # Skip already optimized or marked files (UNLESS trimming is active, then we allow re-processing)
    if not is_trim and ("_opt.mp4" in input_path.name or "NO-OPT" in input_path.name):
        print(f"{Y}Skipping:{NC} {input_path.name} (already optimized marker)")
        batch_stats['skipped'] += 1
        last_encode_result['filename'] = input_path.name
        last_encode_result['status'] = 'skipped'
        last_encode_result['reason'] = 'Already optimized marker'
        last_encode_result['duration'] = 0
        return (False, 0)

    # Determine Output Path
    if video_mode == 'copy':
        # "Copy" mode (Passthrough/Trim) -> Use _trim suffix
        suffix = "_trim.mp4"
        output_path = input_path.parent / f"{input_path.stem}{suffix}"
    elif is_trim:
        # Re-encode + Trim -> Use _opt suffix (standard)
        output_path = input_path.parent / f"{input_path.stem}_opt.mp4"
    else:
        output_path = input_path.parent / f"{input_path.stem}_opt.mp4"
        
        # Skip if output already exists (Skip check if trimming)
        if output_path.exists():
            print(f"{Y}Skipping:{NC} {input_path.name} (_opt.mp4 already exists)")
            batch_stats['skipped'] += 1
            last_encode_result['filename'] = input_path.name
            last_encode_result['status'] = 'skipped'
            last_encode_result['reason'] = 'Output file already exists'
            last_encode_result['duration'] = 0
            return (False, 0)
    
    size_before = input_path.stat().st_size
    size_mb = size_before / (1024 * 1024)

    info = get_video_info(input_path)
    if not info or info['duration'] <= 0:
        batch_stats['failed'] += 1
        return (False, 0)
    
    # --- BITRATE ANALYSIS for maxrate caps ---
    maxrate_kbps = None
    bufsize_kbps = None
    if BITRATE_ANALYZER_AVAILABLE and video_mode == 'compress':
        try:
            bitrate_profile = analyze_bitrate(str(input_path))
            if bitrate_profile.max_bitrate_kbps > 0:
                # Use source max bitrate as our ceiling (with 5% safety margin)
                maxrate_kbps = bitrate_profile.max_bitrate_kbps * 0.95
                # Bufsize for VBR smoothing - larger for variable content
                if bitrate_profile.is_variable_bitrate:
                    bufsize_kbps = maxrate_kbps * 2.0
                else:
                    bufsize_kbps = maxrate_kbps * 1.5
                
                print(f"{Y}Bitrate Analysis:{NC} Source avg={bitrate_profile.avg_bitrate_kbps:.0f}kbps, max={bitrate_profile.max_bitrate_kbps:.0f}kbps, VBR={bitrate_profile.is_variable_bitrate}")
                print(f"{Y}Maxrate Cap:{NC} {maxrate_kbps:.0f}kbps (ensures output ≤ source)")
        except Exception as e:
            print(f"{Y}⚠️ Bitrate analysis skipped:{NC} {e}")
    
    # Calculate Trim Duration and Projected Size
    trim_start_sec = parse_time_to_seconds(ss)
    trim_end_sec = parse_time_to_seconds(to)
    
    start_offset = trim_start_sec # Original starts at this offset
    
    if trim_end_sec > 0:
        trim_duration = trim_end_sec - trim_start_sec
    else:
        trim_duration = info['duration'] - trim_start_sec
        
    if trim_duration <= 0:
        trim_duration = info['duration'] # Fallback
    
    # Prorate original size for fair comparison
    projected_original_size = size_before * (trim_duration / info['duration']) if info['duration'] > 0 else size_before
    
    # Skip small files (UNLESS trimming - user intent overrides size check usually, but let's keep it sane)
    # If projected size is tiny, maybe skip? But for explicit trim, we usually want it done.
    if not is_trim and size_mb < min_size_mb:
        print(f"{Y}Skipping:{NC} {input_path.name} ({size_mb:.1f} MB < {min_size_mb} MB min)")
        batch_stats['skipped'] += 1
        last_encode_result['filename'] = input_path.name
        last_encode_result['status'] = 'skipped'
        last_encode_result['reason'] = f'File too small ({size_mb:.1f} MB < {min_size_mb} MB)'
        last_encode_result['duration'] = 0
        return (False, 0)
    
    print(f"\n{G}Target:{NC} {input_path.name} ({format_size(size_before)})")
    if is_trim:
        print(f" {Y}Trim Segment:{NC} {format_time(trim_start_sec)} - {format_time(trim_start_sec + trim_duration)} (Dur: {format_time(trim_duration)})")
        print(f" {Y}Projected Orig Size:{NC} ~{format_size(projected_original_size)}")
        size_to_compare = projected_original_size
    else:
        size_to_compare = size_before
        
    print("-" * 52)

    # --- Cap maxrate to target bitrate if source is higher ---
    # If maxrate (from source analysis) > what we need to fit in size_to_compare,
    # the encoder will still produce a file at source bitrate, making Q changes useless.
    # We must cap maxrate to the target bitrate ceiling so quality levels have real effect.
    if maxrate_kbps is not None:
        effective_duration = trim_duration if is_trim else info['duration']
        if effective_duration > 0:
            # Estimate target avg bitrate from size target (×8 for bits, ÷1000 for kbps)
            # Use 90% of audio overhead allowance (assume audio ~5% of total)
            target_avg_kbps = (size_to_compare * 8) / (effective_duration * 1000) * 0.90
            # Target peak is typically 3-4× avg for VBR (generous headroom)
            target_maxrate = target_avg_kbps * 3.5
            if target_maxrate < maxrate_kbps:
                old_maxrate = maxrate_kbps
                maxrate_kbps = target_maxrate
                bufsize_kbps = maxrate_kbps * 2.0
                print(f"{Y}Maxrate adjusted:{NC} {old_maxrate:.0f}k → {maxrate_kbps:.0f}k (capped to target bitrate ceiling)")
            else:
                print(f"{Y}Maxrate OK:{NC} {maxrate_kbps:.0f}k ≤ target ceiling {target_maxrate:.0f}k")

    start_q, end_q, step = profile['quality_range']

    # Build list of quality values for binary search
    # quality_direction > 0: higher Q = worse quality (NVENC, QSV, libx265)
    # quality_direction < 0: higher Q = better quality (VideoToolbox)
    if profile['quality_direction'] > 0:
        quality_values = list(range(start_q, end_q + 1, abs(step)))
    else:
        quality_values = list(range(start_q, end_q - 1, step))  # step is negative

    # --- Build per-pass target bitrate values for constrained-VBR ---
    # VideoToolbox (and some other encoders) don't reliably control average bitrate
    # via -q:v alone. We compute a target -b:v for each quality level so the binary
    # search actually changes output file size meaningfully across passes.
    #
    # Reduction factors per pass position: top quality → 85% of source avg (5% smaller),
    # bottom quality → 45% of source avg (55% smaller). Linear interpolation in between.
    # This gives the binary search real leverage over output file size.
    _effective_duration_for_br = trim_duration if is_trim else info['duration']
    _source_avg_kbps = (size_to_compare * 8) / (_effective_duration_for_br * 1000) if _effective_duration_for_br > 0 else None
    bitrate_values: list = []  # Parallel to quality_values; None = use encoder default VBR
    if _source_avg_kbps and _source_avg_kbps > 0:
        n = max(1, len(quality_values))
        # Factor range: from 0.85 (least compression) down to 0.45 (most compression)
        BR_TOP, BR_BOT = 0.85, 0.45
        for i, _qv in enumerate(quality_values):
            # i=0 is highest quality (least compression), i=n-1 is lowest quality (most)
            frac = i / max(1, n - 1)  # 0.0 → 1.0
            factor = BR_TOP - frac * (BR_TOP - BR_BOT)  # 0.85 → 0.45
            bitrate_values.append(_source_avg_kbps * factor)
        br_range = f"{bitrate_values[0]:.0f}k–{bitrate_values[-1]:.0f}k"
        print(f"{Y}Constrained-VBR:{NC} target bitrate per pass {br_range} (source avg ~{_source_avg_kbps:.0f}k)")
    else:
        bitrate_values = [None] * len(quality_values)  # Fallback: pure quality VBR

    # Override with manual quality if provided (use linear search from that point)
    use_binary_search = q_override is None
    if q_override is not None:
        print(f"{Y}Manual Start Quality:{NC} Q={q_override} (linear search)")
        quality = q_override

    file_start_time = time.time()

    def should_continue(q):
        if video_mode == 'copy':
            return False # Only one pass for copy mode

        if profile['quality_direction'] > 0:
            return q <= end_q
        else:
            return q >= end_q
    
    # Video Copy Mode Bypass
    if video_mode == 'copy':
        print(f"{BG}>>> COPY MODE: Skipping re-encode logic.{NC}")
        file_start_time = time.time()
        
        cmd = build_ffmpeg_command(input_path, output_path, profile, quality, copy_audio, audio_mode, ss, to, video_mode='copy')
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # Simple progress loop (copy/trim tends to be fast but we still want feedback)
        # Note: ffmpeg output parsing logic below relies partially on encoding stats.
        # Copy mode outputs less stats, but we can try reuse the existing loop.
        
        cur_stats = {"bitrate": "copy", "speed": "N/A"}
        encode_start = time.time()
        captured_errors = []
        
        # Start Non-Blocking Reader
        q = queue.Queue()
        t = threading.Thread(target=enqueue_output, args=(process.stdout, q))
        t.daemon = True
        t.start()
        
        try:
             while True:
                try:
                    line = q.get(timeout=2.0)
                except queue.Empty:
                    if process.poll() is not None:
                        break
                    # Still running but silent? likely faststart
                    sys.stdout.write(f"\r {G}copy{NC} [Moving Atoms / Finalizing...] ({time.time()-encode_start:.0f}s)    ")
                    sys.stdout.flush()
                    continue

                if not line:
                    break
                
                # Capture potential errors
                if line.strip() and not any(k in line for k in ['bitrate=', 'speed=', 'out_time_ms=', 'total_size=']):
                     captured_errors.append(line.strip())
                     
                # Only duration/size is really reliable in copy mode progress?
                if 'out_time_ms=' in line:
                    val = line.split('=')[1].strip()
                    if val != 'N/A':
                         try:
                            ms = int(val)
                            elapsed = time.time() - encode_start
                            duration_to_show = trim_duration if is_trim else info['duration']
                            show_progress(ms / 1000000, duration_to_show, 'copy', "copy", "fast", elapsed)
                         except ValueError:
                            pass
        
        except KeyboardInterrupt:
            process.terminate()
            if output_path.exists(): output_path.unlink()
            return (False, 0)
            
        process.wait()
        
        if process.returncode == 0:
             file_time = time.time() - file_start_time
             print(f" {BG}>>> SUCCESS (COPY)! Saved to {output_path.name} in {format_time(file_time)}.{NC}")
             batch_stats['total_time'] += file_time
             batch_stats['success'] += 1
             
             # Calculate size diff just for logs, though savings aren't guaranteed
             size_after = output_path.stat().st_size
             saved_bytes = size_before - size_after
             
             last_encode_result['filename'] = input_path.name
             last_encode_result['status'] = 'success'
             last_encode_result['reason'] = 'Video Copy (Passthrough)'
             last_encode_result['duration'] = file_time
             last_encode_result['saved_bytes'] = saved_bytes # Might be negative if container overhead
             
             if port: notify_server(port, input_path)
             return (True, 0)
        else:

             print(f"{R}FFmpeg error during copy.{NC}")
             for err in captured_errors[-10:]: # Print last 10 lines of error
                 print(f"  {R}{err}{NC}")
             batch_stats['failed'] += 1
             return (False, 0)

    # Helper: clean up any leftover staging files for current output
    def _cleanup_staging():
        for f in output_path.parent.glob(f"{output_path.stem}._staging_q*{output_path.suffix}"):
            try:
                f.unlink()
            except OSError:
                pass

    # Helper function to run a single encode pass
    def run_encode_pass(quality_val, out_path=None, target_bitrate_kbps=None):
        """Run a single encode pass and return (success, size_after, ssim, error_reason, overshoot_ratio)."""
        effective_out = out_path or output_path
        br_info = f", target={target_bitrate_kbps:.0f}k" if target_bitrate_kbps else ""
        maxrate_info = f" (maxrate={maxrate_kbps:.0f}k{br_info})" if maxrate_kbps else (f" (target={target_bitrate_kbps:.0f}k)" if target_bitrate_kbps else "")
        print(f"{G}Pass:{NC} Q={quality_val}{maxrate_info}")

        cmd = build_ffmpeg_command(input_path, effective_out, profile, quality_val, copy_audio, audio_mode, ss, to, video_mode='compress', maxrate_kbps=maxrate_kbps, bufsize_kbps=bufsize_kbps, target_bitrate_kbps=target_bitrate_kbps)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        cur_stats = {"bitrate": "0kb/s", "speed": "0x"}
        encode_start = time.time()
        captured_errors = []
        early_abort = False
        abort_threshold = size_to_compare * EARLY_ABORT_RATIO
        _effective_out_ref = effective_out  # captured for cleanup in inner scope

        # Track mid-encode progress for educated quality jump on early abort
        _last_out_time_ms = 0
        _abort_size = 0

        # Start Non-Blocking Reader
        prog_queue = queue.Queue()
        reader_thread = threading.Thread(target=enqueue_output, args=(process.stdout, prog_queue))
        reader_thread.daemon = True
        reader_thread.start()

        try:
            while True:
                try:
                    line = prog_queue.get(timeout=2.0)
                except queue.Empty:
                    if process.poll() is not None:
                        break
                    sys.stdout.write(f"\r {G}{profile['codec']}{NC} [Moving Atoms / Finalizing...] ({time.time()-encode_start:.0f}s)    ")
                    sys.stdout.flush()
                    continue

                if not line:
                    if process.poll() is not None:
                        break

                if line.strip() and not any(k in line for k in ['bitrate=', 'speed=', 'out_time_ms=', 'total_size=', 'frame=']):
                    captured_errors.append(line.strip())

                if 'bitrate=' in line:
                    cur_stats["bitrate"] = line.split('=')[1].strip()
                elif 'speed=' in line:
                    cur_stats["speed"] = line.split('=')[1].strip()
                elif 'out_time_ms=' in line:
                    val = line.split('=')[1].strip()
                    if val != 'N/A':
                        try:
                            ms = int(val)
                            _last_out_time_ms = ms
                            elapsed = time.time() - encode_start
                            duration_to_show = trim_duration if is_trim else info['duration']
                            show_progress(ms / 1000000, duration_to_show, profile['codec'], cur_stats["bitrate"], cur_stats["speed"], elapsed)

                            # Rolling projection: predict final size from current progress.
                            # Use out_time_ms + _abort_size (updated from total_size= just before).
                            # Trust estimate only after 25% encoded – HEVC VBR is too volatile
                            # in the first 15-20% (scene complexity, encoder warmup, I-frames).
                            duration_us = duration_to_show * 1_000_000
                            if _abort_size > 0 and duration_us > 0 and ms > 0:
                                encoded_fraction = ms / duration_us
                                if encoded_fraction >= 0.25:  # Trust only after 25% encoded
                                    projected_final = _abort_size / encoded_fraction
                                    # Only abort if projection is significantly over target (>10% margin)
                                    # to avoid false positives from bitrate spikes
                                    if projected_final >= size_to_compare * 1.10:
                                        pct_done = encoded_fraction * 100
                                        print(f"\n {R}-> Projected ~{format_size(int(projected_final))} at {pct_done:.0f}% done (>= target). Aborting early!{NC}")
                                        process.terminate()
                                        _last_out_time_ms = ms
                                        early_abort = True
                                        break
                        except ValueError:
                            pass
                elif 'total_size=' in line:
                    val = line.split('=')[1].strip()
                    if val != 'N/A':
                        try:
                            current_size = int(val)
                            _abort_size = current_size
                            if current_size >= abort_threshold:
                                print(f"\n {R}-> Size exceeded mid-encode ({format_size(current_size)} >= {format_size(abort_threshold)}). Aborting pass...{NC}")
                                process.terminate()
                                early_abort = True
                                break
                        except ValueError:
                            pass

            process.wait()
            print()

            if early_abort:
                if effective_out.exists(): effective_out.unlink()
                # Estimate how far over the target we projected to be.
                # mid-encode: we wrote _abort_size bytes after _last_out_time_ms µs of video.
                # total_duration_us = encode duration in µs.
                # projected_final = _abort_size / (encoded_fraction)
                overshoot_ratio = 1.0
                duration_us = (trim_duration if is_trim else info['duration']) * 1_000_000
                if _last_out_time_ms > 0 and duration_us > 0:
                    encoded_fraction = min(1.0, _last_out_time_ms / duration_us)
                    if encoded_fraction > 0.20:  # only trust estimate if >20% encoded
                        projected_final = _abort_size / encoded_fraction
                        overshoot_ratio = projected_final / size_to_compare
                        print(f" {Y}   -> Projection: ~{format_size(int(projected_final))} at {encoded_fraction*100:.0f}% done (×{overshoot_ratio:.2f} over target){NC}")
                    else:
                        # Aborted before we could get a reliable estimate → use size-based ratio
                        if _abort_size > 0 and size_to_compare > 0:
                            overshoot_ratio = max(1.0, _abort_size / (size_to_compare * max(0.05, encoded_fraction or 0.10)))
                        encoded_fraction_str = f"{encoded_fraction*100:.0f}" if encoded_fraction > 0 else "??"
                        print(f" {Y}   -> Aborted too early ({encoded_fraction_str}%) for projection – using size-based estimate{NC}")
                return (False, 0, 0, 'early_abort', overshoot_ratio)

            if process.returncode != 0:
                print(f"{R}FFmpeg error during encoding.{NC}")
                for err in captured_errors[-10:]:
                    print(f"  {R}{err}{NC}")
                if effective_out.exists(): effective_out.unlink()
                return (False, 0, 0, 'ffmpeg_error')

            size_after = effective_out.stat().st_size

            if size_after >= size_to_compare:
                print(f" {R}-> File larger ({format_size(size_after)} > {format_size(size_to_compare)}).{NC}")
                if effective_out != output_path and effective_out.exists(): effective_out.unlink()
                return (False, size_after, 0, 'too_large')

            # Early savings check: skip SSIM if compression is not worth it
            saved_bytes_pre = size_to_compare - size_after
            saved_pct_pre = saved_bytes_pre * 100 / size_to_compare
            MIN_SAVINGS_FOR_SSIM = 10.0  # Only run SSIM if we saved at least 10%
            if saved_pct_pre < MIN_SAVINGS_FOR_SSIM:
                print(f" {Y}-> Saved only {saved_pct_pre:.2f}% – skipping SSIM (below {MIN_SAVINGS_FOR_SSIM:.0f}% threshold). Not optimal.{NC}")
                if effective_out != output_path and effective_out.exists(): effective_out.unlink()
                return (False, size_after, 0.0, 'poor_savings')

            # Quality verification: single ffmpeg pass over 3 segments (25 / 50 / 75 %)
            # concat-based comparison → natural mean, no skew from fades like min() had
            dur_for_samples = trim_duration if is_trim else info['duration']
            raw_pts = [dur_for_samples * p for p in (0.25, 0.50, 0.75)]
            opt_starts = [
                max(0.0, min(s, dur_for_samples - SAMPLE_DURATION - 0.5))
                for s in raw_pts
            ]
            orig_starts = [start_offset + s for s in opt_starts]

            ssim = get_multi_ssim(
                input_path, effective_out, orig_starts, opt_starts, SAMPLE_DURATION
            )
            quality_label = _detect_quality_filter().upper()

            saved_bytes = size_to_compare - size_after
            saved_pct = saved_bytes * 100 / size_to_compare
            print(f" {G}-> Result:{NC} Q={quality_val} | Saved: {saved_pct:.2f}% | {quality_label}: {ssim:.4f}")

            return (True, size_after, ssim, None)

        except KeyboardInterrupt:
            print(f"\n{R}>>> Abort. Cleaning up...{NC}")
            process.terminate()
            if effective_out.exists(): effective_out.unlink()
            _cleanup_staging()
            sys.exit(1)

    # Binary search for optimal quality
    if use_binary_search and len(quality_values) > 1:
        print(f"{Y}Binary Search Mode:{NC} Testing {len(quality_values)} quality levels [{quality_values[0]}..{quality_values[-1]}]")

        # Binary search: find the best (most compression) quality that meets SSIM threshold
        # Each pass encodes to a unique staging file; the best is renamed at the end.
        # No re-encode needed – we reuse the cached staging file directly.
        low, high = 0, len(quality_values) - 1
        best_result = None       # (quality, size_after, ssim, saved_bytes, saved_pct)
        best_acceptable = None   # Backup: best result with acceptable SSIM even if savings not met
        best_candidate_path: 'Path | None' = None       # staging file for best_result
        best_acceptable_path: 'Path | None' = None      # staging file for best_acceptable

        def _staging_path(q):
            return output_path.with_name(f"{output_path.stem}._staging_q{q}{output_path.suffix}")

        while low <= high:
            mid = (low + high) // 2
            quality = quality_values[mid]
            staging = _staging_path(quality)
            pass_bitrate = bitrate_values[mid] if bitrate_values and mid < len(bitrate_values) else None

            result = run_encode_pass(quality, out_path=staging, target_bitrate_kbps=pass_bitrate)
            success, size_after, ssim, error = result[0], result[1], result[2], result[3]
            overshoot_ratio = result[4] if len(result) > 4 else 1.0

            if error == 'ffmpeg_error':
                _cleanup_staging()
                batch_stats['failed'] += 1
                return (False, 0)

            if error in ('early_abort', 'too_large'):
                # Educated quality jump: if we have an overshoot ratio, skip ahead
                # proportionally instead of always just going to mid-1.
                #
                # overshoot_ratio = projected_final / target
                # e.g. 2.0 → projected twice as large → need ~2 quality steps, not 1
                # We clamp to [1, remaining_range] to avoid overshooting the index.
                overshoot_ratio = result[4] if len(result) > 4 else 1.0
                if overshoot_ratio > 1.05 and (high - low) > 1:
                    # Each binary step halves the range; estimate how many halvings needed.
                    import math
                    steps_needed = max(1, int(math.log2(overshoot_ratio) + 0.5))
                    new_high = mid - steps_needed
                    if new_high < low:
                        new_high = low  # Don't go below binary search floor
                    if new_high < high:
                        print(f" {Y}   -> Educated jump: skipping {mid - new_high} quality step(s) (overshoot ×{overshoot_ratio:.2f}){NC}")
                        high = new_high
                    else:
                        high = mid - 1
                else:
                    high = mid - 1
                continue

            if error == 'poor_savings':
                # Not enough compression achieved – push toward more compression
                # (same direction as early_abort / too_large would, but opposite of quality failure)
                if profile['quality_direction'] > 0:
                    low = mid + 1   # VideoToolbox: lower Q = more compression
                else:
                    high = mid - 1  # NVENC: higher CQ = more compression
                if staging.exists(): staging.unlink()
                continue

            if not success:
                # Unexpected failure – push toward better quality to stay safe
                if profile['quality_direction'] > 0:
                    high = mid - 1
                else:
                    low = mid + 1
                continue

            # Check SSIM threshold
            if ssim < SSIM_MIN:
                print(f" {R}   -> Quality too low for this level.{NC}")
                # Need better quality (less compression) → move towards index 0 (best quality).
                high = mid - 1
                if staging.exists(): staging.unlink()
                continue

            saved_bytes = size_to_compare - size_after
            saved_pct = saved_bytes * 100 / size_to_compare

            # Check if meets targets
            meets_targets = (saved_pct >= MIN_SAVINGS and ssim >= MIN_QUALITY) or \
                           (saved_pct >= EXCELLENT_SAVINGS_PCT and ssim >= SSIM_ACCEPTABLE)

            # Track best acceptable result as backup (retain its staging file)
            if ssim >= SSIM_ACCEPTABLE and saved_pct > 0:
                if best_acceptable is None or saved_pct > best_acceptable[4]:
                    # Discard old backup staging file
                    if best_acceptable_path and best_acceptable_path != best_candidate_path and best_acceptable_path.exists():
                        best_acceptable_path.unlink()
                    best_acceptable = (quality, size_after, ssim, saved_bytes, saved_pct)
                    best_acceptable_path = staging
                else:
                    # We already have a better acceptable one
                    if staging != best_candidate_path and staging.exists():
                        staging.unlink()

            if meets_targets:
                # Discard old best candidate staging file (keep backup if different)
                if best_candidate_path and best_candidate_path != best_acceptable_path and best_candidate_path.exists():
                    best_candidate_path.unlink()
                best_result = (quality, size_after, ssim, saved_bytes, saved_pct)
                best_candidate_path = staging

                # EARLY EXIT: No point searching further when we've already saved excellently
                if saved_pct >= EXCELLENT_SAVINGS_PCT and ssim >= MIN_QUALITY:
                    print(f" {BG}   -> Early exit: {saved_pct:.1f}% savings is excellent! (cached)  {NC}")
                    break

                # Otherwise try for more compression
                low = mid + 1
            else:
                # SSIM OK but savings not enough, need more compression
                low = mid + 1
                # staging already handled under best_acceptable tracking above
                if staging != best_acceptable_path and staging != best_candidate_path and staging.exists():
                    staging.unlink()

        # Use best result if found, or fall back to best acceptable
        final_result = best_result or best_acceptable
        final_path = best_candidate_path or best_acceptable_path

        if final_result and final_path and final_path.exists():
            quality, size_after, ssim, saved_bytes, saved_pct = final_result
            is_fallback = best_result is None

            if is_fallback:
                print(f"\n{Y}>>> No perfect match. Using best acceptable Q={quality} (saved {saved_pct:.1f}%, SSIM {ssim:.4f}){NC}")
            else:
                print(f"\n{BG}>>> Finalizing: re-using cached encode Q={quality}{NC}")

            # Promote staging file to final output path (no re-encode!)
            final_path.rename(output_path)

            # Clean up any remaining staging files
            _cleanup_staging()

            file_time = time.time() - file_start_time
            print(f" {BG}>>> SUCCESS! {format_size(saved_bytes)} ({saved_bytes*100/size_to_compare:.1f}%) saved in {format_time(file_time)}.{NC}")
            batch_stats['total_saved_bytes'] += saved_bytes
            batch_stats['total_time'] += file_time
            batch_stats['success'] += 1

            last_encode_result['filename'] = input_path.name
            last_encode_result['status'] = 'success'
            last_encode_result['quality'] = quality
            last_encode_result['ssim'] = ssim
            last_encode_result['saved_pct'] = saved_pct
            last_encode_result['saved_bytes'] = saved_bytes
            last_encode_result['duration'] = file_time
            last_encode_result['reason'] = None

            if port:
                notify_server(port, input_path)

            return (True, saved_bytes)

        # Binary search found nothing usable – clean up any staging leftovers
        _cleanup_staging()
        batch_stats['failed'] += 1
        file_time = time.time() - file_start_time
        last_encode_result['filename'] = input_path.name
        last_encode_result['status'] = 'failed'
        if best_acceptable:
            last_encode_result['reason'] = f'Best result (Q={best_acceptable[0]}) had {best_acceptable[4]:.1f}% savings, SSIM {best_acceptable[2]:.4f} - did not meet targets'
        else:
            last_encode_result['reason'] = 'Binary search: no quality level produced acceptable results'
        last_encode_result['duration'] = file_time
        print(f" {R}>>> FAILED: {last_encode_result['reason']}{NC}")
        return (False, 0)

    # Fallback: Linear search (used when q_override is set or only 1 quality value)
    # Uses same staging strategy: encode to a temp file, promote if good, discard otherwise.
    quality = q_override if q_override is not None else quality_values[0]
    linear_best_path: 'Path | None' = None
    linear_best_result = None
    # Track best acceptable result: (quality, size_after, ssim, saved_pct, staging_path)
    linear_best_acceptable: 'tuple | None' = None
    linear_best_acceptable_path: 'Path | None' = None

    while should_continue(quality):
        staging = output_path.with_name(f"{output_path.stem}._staging_q{quality}{output_path.suffix}")
        # Find this quality's index in quality_values to pick the right target bitrate.
        # For --q overrides not in the list, find the nearest entry or interpolate.
        try:
            _q_idx = quality_values.index(quality)
            _pass_bitrate = bitrate_values[_q_idx] if bitrate_values and _q_idx < len(bitrate_values) else None
        except ValueError:
            # Quality not in list (e.g. manual override) – interpolate bitrate from range
            if bitrate_values and len(quality_values) >= 2:
                q_min, q_max = min(quality_values), max(quality_values)
                q_frac = (quality - q_min) / max(1, q_max - q_min)
                # For VideoToolbox: high Q = high quality = high bitrate, so br_top at high Q
                if profile['quality_direction'] < 0:  # higher Q = better quality
                    q_frac = 1.0 - q_frac  # flip: high Q → high bitrate (low frac)
                br_top_val = bitrate_values[0]
                br_bot_val = bitrate_values[-1]
                _pass_bitrate = br_top_val - q_frac * (br_top_val - br_bot_val)
            else:
                _pass_bitrate = None
        _res = run_encode_pass(quality, out_path=staging, target_bitrate_kbps=_pass_bitrate)
        success, size_after, ssim, error = _res[0], _res[1], _res[2], _res[3]

        if error == 'ffmpeg_error':
            _cleanup_staging()
            batch_stats['failed'] += 1
            return (False, 0)

        if error in ('early_abort', 'too_large'):
            quality += step
            continue

        if error == 'poor_savings':
            # SSIM skipped – savings too low. Try next quality step (more compression).
            # staging already deleted by run_encode_pass()
            quality += step
            continue

        if not success:
            quality += step
            continue

        if ssim < SSIM_MIN:
            print(f" {R}   -> Quality too low. Aborting.{NC}")
            if staging.exists(): staging.unlink()

            # Rescue best acceptable result found in previous passes
            if linear_best_acceptable and linear_best_acceptable_path and linear_best_acceptable_path.exists():
                _ba_quality, _ba_size, _ba_ssim, _ba_saved_pct = linear_best_acceptable
                _ba_saved_bytes = size_to_compare - _ba_size
                linear_best_acceptable_path.rename(output_path)
                _cleanup_staging()
                file_time = time.time() - file_start_time
                print(f" {Y}   -> Using best acceptable result: Q={_ba_quality} | "
                      f"Saved: {_ba_saved_pct:.1f}% | SSIM: {_ba_ssim:.4f}{NC}")
                print(f" {BG}>>> SUCCESS (fallback)! {format_size(_ba_saved_bytes)} "
                      f"({_ba_saved_bytes*100/size_to_compare:.1f}%) saved in {format_time(file_time)}.{NC}")
                batch_stats['total_saved_bytes'] += _ba_saved_bytes
                batch_stats['total_time'] += file_time
                batch_stats['success'] += 1
                last_encode_result['filename'] = input_path.name
                last_encode_result['status'] = 'success'
                last_encode_result['quality'] = _ba_quality
                last_encode_result['ssim'] = _ba_ssim
                last_encode_result['saved_pct'] = _ba_saved_pct
                last_encode_result['saved_bytes'] = _ba_saved_bytes
                last_encode_result['duration'] = file_time
                last_encode_result['reason'] = 'fallback_acceptable'
                if port:
                    notify_server(port, input_path)
                return (True, _ba_saved_bytes)

            _cleanup_staging()
            batch_stats['failed'] += 1
            file_time = time.time() - file_start_time
            last_encode_result['filename'] = input_path.name
            last_encode_result['status'] = 'failed'
            last_encode_result['quality'] = quality
            last_encode_result['ssim'] = ssim
            last_encode_result['reason'] = f'Quality too low (SSIM {ssim:.4f} < {SSIM_MIN:.3f})'
            last_encode_result['duration'] = file_time
            return (False, 0)

        saved_bytes = size_to_compare - size_after
        saved_pct = saved_bytes * 100 / size_to_compare

        if (saved_pct >= MIN_SAVINGS and ssim >= MIN_QUALITY) or \
           (saved_pct >= EXCELLENT_SAVINGS_PCT and ssim >= SSIM_ACCEPTABLE):
            # Great result – promote staging file to final output
            # Discard any previously saved fallback
            if linear_best_acceptable_path and linear_best_acceptable_path.exists():
                linear_best_acceptable_path.unlink()
            staging.rename(output_path)
            _cleanup_staging()
            file_time = time.time() - file_start_time
            print(f" {BG}>>> SUCCESS! {format_size(saved_bytes)} ({saved_bytes*100/size_to_compare:.1f}%) saved in {format_time(file_time)}.{NC}")
            batch_stats['total_saved_bytes'] += saved_bytes
            batch_stats['total_time'] += file_time
            batch_stats['success'] += 1

            last_encode_result['filename'] = input_path.name
            last_encode_result['status'] = 'success'
            last_encode_result['quality'] = quality
            last_encode_result['ssim'] = ssim
            last_encode_result['saved_pct'] = saved_pct
            last_encode_result['saved_bytes'] = saved_bytes
            last_encode_result['duration'] = file_time
            last_encode_result['reason'] = None

            if port:
                notify_server(port, input_path)

            return (True, saved_bytes)

        # Not ideal, but worth keeping as a fallback?
        if saved_pct >= MIN_SAVINGS and ssim >= SSIM_ACCEPTABLE:
            # Save this as the best fallback so far
            if linear_best_acceptable_path and linear_best_acceptable_path.exists():
                linear_best_acceptable_path.unlink()  # discard older, worse fallback
            linear_best_acceptable = (quality, size_after, ssim, saved_pct)
            linear_best_acceptable_path = staging
            print(f" {Y}   -> Not optimal (SSIM {ssim:.4f}, saved {saved_pct:.1f}%). Trying more compression...{NC}")
        else:
            print(f" {R}   -> Not optimal. Next pass...{NC}")
            if staging.exists(): staging.unlink()
        quality += step

    # Loop exhausted – try the best acceptable fallback if we have one
    if linear_best_acceptable and linear_best_acceptable_path and linear_best_acceptable_path.exists():
        _ba_quality, _ba_size, _ba_ssim, _ba_saved_pct = linear_best_acceptable
        _ba_saved_bytes = size_to_compare - _ba_size
        linear_best_acceptable_path.rename(output_path)
        _cleanup_staging()
        file_time = time.time() - file_start_time
        print(f" {Y}   -> Using best acceptable result: Q={_ba_quality} | "
              f"Saved: {_ba_saved_pct:.1f}% | SSIM: {_ba_ssim:.4f}{NC}")
        print(f" {BG}>>> SUCCESS (fallback)! {format_size(_ba_saved_bytes)} "
              f"({_ba_saved_bytes*100/size_to_compare:.1f}%) saved.{NC}")
        batch_stats['total_saved_bytes'] += _ba_saved_bytes
        batch_stats['success'] += 1
        last_encode_result['filename'] = input_path.name
        last_encode_result['status'] = 'success'
        last_encode_result['quality'] = _ba_quality
        last_encode_result['ssim'] = _ba_ssim
        last_encode_result['saved_pct'] = _ba_saved_pct
        last_encode_result['saved_bytes'] = _ba_saved_bytes
        last_encode_result['reason'] = 'fallback_acceptable'
        if port:
            notify_server(port, input_path)
        return (True, _ba_saved_bytes)

    if linear_best_acceptable_path and linear_best_acceptable_path.exists():
        linear_best_acceptable_path.unlink()
    _cleanup_staging()
    batch_stats['failed'] += 1
    file_time = time.time() - file_start_time
    last_encode_result['filename'] = input_path.name
    last_encode_result['status'] = 'failed'
    last_encode_result['reason'] = 'Exhausted all quality levels without meeting targets'
    last_encode_result['duration'] = file_time
    return (False, 0)

def print_batch_summary():
    """Print summary of batch processing."""
    print(f"\n{'='*52}")
    print(f"{BG}BATCH SUMMARY{NC}")
    print(f"{'='*52}")
    print(f" {G}Processed:{NC} {batch_stats['processed']} files")
    print(f" {G}Success:{NC}   {batch_stats['success']} files")
    print(f" {Y}Skipped:{NC}   {batch_stats['skipped']} files")
    print(f" {R}Failed:{NC}    {batch_stats['failed']} files")
    print(f" {BG}Saved:{NC}     {format_size(batch_stats['total_saved_bytes'])}")
    print(f" {G}Time:{NC}      {format_time(batch_stats['total_time'])}")
    print(f"{'='*52}")


def write_encode_log(filename, status, encoder_name, quality=None, ssim=None, 
                     saved_pct=None, saved_bytes=None, duration=0, reason=None):
    """Write encoding result to a persistent log file. Appends to daily log."""
    log_date = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"encode_{log_date}.log"
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"\n[{timestamp}] {filename}\n")
        f.write(f"  Status:   {status.upper()}\n")
        f.write(f"  Encoder:  {encoder_name}\n")
        
        if status == 'success':
            if quality:
                f.write(f"  Quality:  Q={quality}\n")
            if ssim:
                f.write(f"  SSIM:     {ssim:.4f}\n")
            if saved_pct:
                f.write(f"  Savings:  {saved_pct:.1f}%\n")
            if saved_bytes:
                f.write(f"  Saved:    {format_size(saved_bytes)}\n")
        elif reason:
            f.write(f"  Reason:   {reason}\n")
        
        f.write(f"  Duration: {format_time(duration)}\n")
        f.write("-" * 50 + "\n")
    
    return log_file


def main():
    parser = argparse.ArgumentParser(description='Multi-Platform Video Optimizer V2.1')
    parser.add_argument('files', nargs='*', help='Video files to optimize')
    parser.add_argument('--encoder', choices=['auto', 'nvenc', 'videotoolbox', 'qsv', 'libx265'], default='auto',
                        help='Encoder to use (default: auto-detect)')
    parser.add_argument('--codec', choices=['hevc', 'av1'], default='hevc',
                        help='Target codec: hevc (default) or av1 (experimental, requires modern GPU)')
    parser.add_argument('--min-size', type=int, default=DEFAULT_MIN_SIZE_MB,
                        help=f'Skip files smaller than N MB (default: {DEFAULT_MIN_SIZE_MB})')
    parser.add_argument('--copy-audio', action='store_true',
                        help='Copy audio without re-encoding (faster, preserves original audio)')
    parser.add_argument('--audio-mode', choices=['enhanced', 'standard'], default='enhanced',
                        help='Audio processing mode (default: enhanced)')
    parser.add_argument('--ss', type=str, help='Start time (e.g. 00:00:10 or 10)')
    parser.add_argument('--to', type=str, help='End time (e.g. 00:00:20 or 20)')
    parser.add_argument('--video-mode', choices=['compress', 'copy'], default='compress',
                        help='Video processing mode: compress (default) or copy (passthrough)')
    parser.add_argument('--q', type=int, help='Manual starting quality value')
    parser.add_argument('--port', type=int, help='Port of the running Arcade Server to notify')
    parser.add_argument('--preset', choices=['fast', 'balanced', 'best'], default='balanced',
                        help='Encoding quality preset: fast (speed), balanced (default), best (quality/size)')
    args = parser.parse_args()

    if args.port:
        print(f"🔌 Notification Port: {args.port}")
    else:
        print(f"⚠️ No notification port provided. Status updates will be disabled.")

    # Select encoder
    if args.encoder == 'auto':
        encoder_key = detect_encoder()
    else:
        encoder_key = args.encoder

    # AV1 codec override: map hardware encoder → AV1 variant
    if getattr(args, 'codec', 'hevc') == 'av1':
        av1_map = {
            'videotoolbox': 'av1_videotoolbox',
            'nvenc': 'av1_nvenc',
        }
        av1_key = av1_map.get(encoder_key)
        if av1_key and av1_key in ENCODER_PROFILES:
            print(f"{Y}🧪 AV1 Experimental: switching from {encoder_key} → {av1_key}{NC}")
            encoder_key = av1_key
        else:
            print(f"{Y}⚠️  AV1 not supported for encoder '{encoder_key}', falling back to HEVC.{NC}")

    profile = ENCODER_PROFILES[encoder_key]

    # Apply user-selected encoding preset (fast / balanced / best)
    preset = getattr(args, 'preset', 'balanced')
    profile = apply_encoding_preset(profile, preset)
    preset_labels = {'fast': '⚡ Fast', 'balanced': '⚖️  Balanced', 'best': '🏆 Best'}
    print(f"{BG}VIDEO OPTIMIZER V2.1{NC} - {G}{profile['name']}{NC} | Preset: {preset_labels.get(preset, preset)}")
    if args.copy_audio:
        print(f"{Y}Audio: Copy (passthrough){NC}")
    elif args.audio_mode:
        print(f"{Y}Audio Mode: {args.audio_mode}{NC}")

    if args.video_mode == 'copy':
        print(f"{Y}Video Mode: Copy (Passthrough){NC}")

    if args.min_size != DEFAULT_MIN_SIZE_MB:
        print(f"{Y}Min size: {args.min_size} MB{NC}")
        
    if args.ss or args.to:
        print(f"{Y}Trim Active: {args.ss} -> {args.to}{NC}")
    
    files = args.files
    if not files:
        print(f"{G}Drag and drop files or enter paths (space separated):{NC}")
        try:
            import shlex
            raw_input = input()
            files = shlex.split(raw_input)
        except EOFError:
            return
    
    # Filter out flags from files
    files = [f for f in files if not f.startswith('-')]
    
    for f in files:
        batch_stats['processed'] += 1
        success, saved_bytes = process_file(
            f, profile, 
            min_size_mb=args.min_size, 
            copy_audio=args.copy_audio, 
            port=args.port, 
            audio_mode=args.audio_mode, 
            ss=args.ss, 
            to=args.to,
            video_mode=args.video_mode,
            q_override=args.q
        )
        
        # Write to encode log (for both batch controller and single-file calls)
        if last_encode_result['filename']:
            log_file = write_encode_log(
                filename=last_encode_result['filename'],
                status=last_encode_result['status'],
                encoder_name=profile['name'],
                quality=last_encode_result['quality'],
                ssim=last_encode_result['ssim'],
                saved_pct=last_encode_result['saved_pct'],
                saved_bytes=last_encode_result['saved_bytes'],
                duration=last_encode_result['duration'],
                reason=last_encode_result['reason']
            )

    # Print batch summary if multiple files
    if len(files) > 1:
        print_batch_summary()
    
    # Show log file location
    if files and last_encode_result['filename']:
        log_date = datetime.now().strftime("%Y-%m-%d")
        log_path = LOG_DIR / f"encode_{log_date}.log"
        print(f"\n{G}📝 Log:{NC} {log_path}")
    
    # Open folder and play sound
    if files:
        last_path = files[-1]
        folder = Path(last_path).parent
        if folder.exists():
            print(f"\n{G}Opening folder:{NC} {folder}")
            if sys.platform == 'win32':
                os.startfile(str(folder))
            elif sys.platform == 'darwin':
                subprocess.run(['open', str(folder)])
            else:
                subprocess.run(['xdg-open', str(folder)])

    try:
        import winsound
        winsound.MessageBeep()
    except:
        pass

def notify_server(port, file_path):
    """Notify the local server that a file has been optimized."""
    if not port:
        return
    
    try:
        import urllib.request
        from urllib.parse import quote
        
        encoded_path = quote(str(Path(file_path).resolve()))
        url = f"http://localhost:{port}/api/mark_optimized?path={encoded_path}"
        
        # Simple fire and forget request with short timeout
        with urllib.request.urlopen(url, timeout=2):
            pass
        print(f"{G}Server notified of optimization.{NC}")
    except Exception as e:
        print(f"{Y}Could not notify server: {e}{NC}")

if __name__ == "__main__":
    main()
