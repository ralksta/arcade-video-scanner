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
from pathlib import Path
from datetime import datetime, timedelta
import threading
import queue

# Import bitrate analyzer for maxrate caps
# Use sys.path to avoid circular dependencies through arcade_scanner's __init__.py
try:
    import sys as _sys
    _analyzer_path = Path(__file__).parent.parent / "arcade_scanner" / "core"
    if _analyzer_path.exists():
        _sys.path.insert(0, str(_analyzer_path))
        from bitrate_analyzer import analyze_bitrate, BitrateProfile
        _sys.path.pop(0)
        BITRATE_ANALYZER_AVAILABLE = True
    else:
        BITRATE_ANALYZER_AVAILABLE = False
except ImportError:
    BITRATE_ANALYZER_AVAILABLE = False

# Logs directory
LOG_DIR = Path.home() / ".arcade-scanner" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# --- CONFIGURATION ---
MIN_SAVINGS = 20.0
MIN_QUALITY = 0.960
SAMPLE_DURATION = 5
DEFAULT_MIN_SIZE_MB = 50  # Skip files smaller than this
FUNFACT_INTERVAL = 30     # Seconds between fun facts
ENABLE_FUNFACTS = True    # Default, overridden by main args
FUNFACT_THRESHOLD = 300   # Start showing facts after 5 minutes (300 seconds)

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
            '-b_ref_mode', 'middle',
            '-bf', '4',
            '-spatial-aq', '1',
            '-temporal-aq', '1',
            '-aq-strength', '8',
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
            '-preset', 'medium',
            '-x265-params', 'log-level=error',
        ],
        'quality_flag': '-crf',
        'video_filter': 'format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2',
    }
}

# --- COLORS ---
G = '\033[0;32m'
BG = '\033[1;32m'
R = '\033[0;31m'
Y = '\033[0;33m'
NC = '\033[0m'

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

# --- FUN FACTS ---
import random

def load_funfacts():
    """Load fun facts from external JSON file."""
    facts_file = Path(__file__).parent / 'funfacts.json'
    try:
        if facts_file.exists():
            with open(facts_file, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return ["Did you know? HEVC can achieve 50% better compression than H.264!"]

funfacts = load_funfacts() if ENABLE_FUNFACTS else []
last_funfact_time = 0
current_funfact = ""

def detect_encoder():
    """Auto-detect the best available encoder based on platform and hardware."""
    if sys.platform == 'darwin':
        return 'videotoolbox'
    elif sys.platform == 'win32':
        try:
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-encoders'],
                capture_output=True, text=True, timeout=5
            )
            if 'hevc_nvenc' in result.stdout:
                return 'nvenc'
        except:
            pass
    # Linux or fallback


    # Generic Linux/Windows Detection
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=5
        )
        if 'hevc_nvenc' in result.stdout:
            return 'nvenc'
        if 'hevc_qsv' in result.stdout:
            return 'qsv'
        if 'hevc_vaapi' in result.stdout:
            # Simple check for device existence
            if os.path.exists("/dev/dri/renderD128"):
                 return 'vaapi'
            elif os.path.exists("/dev/dri/card0"):
                 # Update profile to use card0 if needed, but for now just return profile
                 # Note: The profile hardcodes renderD128. Ideally we should dynamic update.
                 # For simplicity in this script, we assume renderD128 is the target for headless.
                 return 'vaapi'
            return 'vaapi'
        if 'hevc_videotoolbox' in result.stdout:
            return 'videotoolbox'
    except:
        pass
    
    print(f"{R}No hardware encoder detected. Using software encoder (slower).{NC}")
    return 'libx265'

def get_video_info(file_path):
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
            fps_val = n / d if d != 0 else 0
        else:
            fps_val = float(fps)
            
        return {
            'duration': duration,
            'width': width,
            'height': height,
            'codec': codec,
            'fps': int(fps_val + 0.5)
        }
    except Exception as e:
        print(f"{R}Error probing {file_path}: {e}{NC}")
        return None

def parse_time_to_seconds(time_str):
    """Convert time string (HH:MM:SS or SS) to seconds."""
    if not time_str:
        return 0.0
    try:
        if ':' in str(time_str):
            t = datetime.strptime(str(time_str), "%H:%M:%S")
            delta = timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)
            return delta.total_seconds()
        return float(time_str)
    except:
        return 0.0

def get_ssim(original, optimized, orig_start, opt_start, duration):
    """Calculate SSIM between original (at orig_start) and optimized (at opt_start)."""
    cmd = [
        'ffmpeg', '-ss', str(orig_start), '-t', str(duration), '-i', str(original),
        '-ss', str(opt_start), '-t', str(duration), '-i', str(optimized),
        '-filter_complex', 'ssim', '-f', 'null', '-'
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        match = re.search(r'All:([\d.]+)', result.stderr)
        if match:
            return float(match.group(1))
    except Exception as e:
        print(f"{R}Error calculating SSIM: {e}{NC}")
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

def show_progress(current, total, encoder="", bitrate="0kb/s", speed="0x", elapsed=0, bar_length=20):
    """Enhanced console progress bar with encoder info, elapsed time and ETA."""
    global last_funfact_time, current_funfact
    
    percent = float(current) * 100 / total if total > 0 else 0
    percent = min(100.0, percent)
    arrow = '█' * int(percent/100 * bar_length)
    spaces = '░' * (bar_length - len(arrow))
    
    if current > 0 and elapsed > 0:
        eta = (elapsed / current) * (total - current)
    else:
        eta = -1
    
    elapsed_str = format_time(elapsed)
    eta_str = format_time(eta)
    
    # Clear line and print progress
    sys.stdout.write(f"\r {G}{encoder}{NC} [{arrow}{spaces}] {BG}{int(percent)}%{NC} | {speed} | {bitrate} | {elapsed_str} / {eta_str}    ")
    
    # Fun facts widget for long encodes
    if ENABLE_FUNFACTS and funfacts and elapsed >= FUNFACT_THRESHOLD:
        if elapsed - last_funfact_time >= FUNFACT_INTERVAL or current_funfact == "":
            current_funfact = random.choice(funfacts)
            last_funfact_time = elapsed
        
        # Wrap text to fit in box (max ~82 chars per line)
        import textwrap
        wrapped = textwrap.wrap(current_funfact, width=82)
        
        # Build the retro BBS widget (90 chars wide)
        widget_lines = [
            "",
            f" {Y}╔══════════════════════════════════════════════════════════════════════════════════════════╗{NC}",
            f" {Y}║{NC}             🕹️  {BG}D I D   Y O U   K N O W ?{NC}  🎮                                           {Y}║{NC}",
            f" {Y}╠══════════════════════════════════════════════════════════════════════════════════════════╣{NC}",
        ]
        for line in wrapped:
            padded = line.center(86)
            widget_lines.append(f" {Y}║{NC}  {G}{padded}{NC}{Y}║{NC}")
        widget_lines.append(f" {Y}╠══════════════════════════════════════════════════════════════════════════════════════════╣{NC}")
        widget_lines.append(f" {Y}║{NC}     👾 RETRO GAMING TRIVIA 👾     ⭐ ARCADE CLASSICS ⭐     🏆 HIGH SCORE 🏆            {Y}║{NC}")
        widget_lines.append(f" {Y}╚══════════════════════════════════════════════════════════════════════════════════════════╝{NC}")
        
        # Print widget below progress bar
        for wl in widget_lines:
            sys.stdout.write(f"\n{wl}")
        # Move cursor back up
        sys.stdout.write(f"\033[{len(widget_lines)}F")
    
    sys.stdout.flush()

def build_ffmpeg_command(input_path, output_path, profile, quality_value, copy_audio=False, audio_mode='enhanced', ss=None, to=None, video_mode='compress', maxrate_kbps=None, bufsize_kbps=None):
    """Build the ffmpeg command based on encoder profile.
    
    Args:
        maxrate_kbps: Optional max bitrate cap (from bitrate analyzer) to prevent exceeding source
        bufsize_kbps: Optional buffer size for VBR smoothing
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
        cmd.extend([profile['quality_flag'], str(quality_value)])
        cmd.extend(['-vf', profile['video_filter']])
        
        # Add maxrate/bufsize caps if provided (from bitrate analyzer)
        # This ensures output never exceeds source bitrate even with high quality settings
        if maxrate_kbps and maxrate_kbps > 0:
            cmd.extend(['-maxrate', f'{int(maxrate_kbps)}k'])
            if bufsize_kbps and bufsize_kbps > 0:
                cmd.extend(['-bufsize', f'{int(bufsize_kbps)}k'])
            else:
                # Default bufsize = 2x maxrate for VBR headroom
                cmd.extend(['-bufsize', f'{int(maxrate_kbps * 2)}k'])
    
    # Audio settings
    if copy_audio:
        cmd.extend(['-c:a', 'copy'])
    elif audio_mode == 'standard':
        # Standard AAC re-encode without normalization (flat)
        cmd.extend(['-c:a', 'aac', '-b:a', '192k'])
    else:
        # Enhanced: High-pass + Gate + Loudnorm
        audio_filters = 'highpass=f=100,agate=threshold=-55dB:range=0.05:ratio=2,loudnorm=I=-20:TP=-1.5:LRA=11'
        cmd.extend(['-c:a', 'aac', '-b:a', '192k', '-af', audio_filters])
    
    cmd.extend([
        '-tag:v', 'hvc1',
        '-movflags', '+faststart',
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

    start_q, end_q, step = profile['quality_range']

    # Build list of quality values for binary search
    # quality_direction > 0: higher Q = worse quality (NVENC, QSV, libx265)
    # quality_direction < 0: higher Q = better quality (VideoToolbox)
    if profile['quality_direction'] > 0:
        quality_values = list(range(start_q, end_q + 1, abs(step)))
    else:
        quality_values = list(range(start_q, end_q - 1, step))  # step is negative

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

    # Helper function to run a single encode pass
    def run_encode_pass(quality_val):
        """Run a single encode pass and return (success, size_after, ssim, error_reason)."""
        print(f"{G}Pass:{NC} Q={quality_val}" + (f" (maxrate={maxrate_kbps:.0f}k)" if maxrate_kbps else ""))

        cmd = build_ffmpeg_command(input_path, output_path, profile, quality_val, copy_audio, audio_mode, ss, to, video_mode='compress', maxrate_kbps=maxrate_kbps, bufsize_kbps=bufsize_kbps)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        cur_stats = {"bitrate": "0kb/s", "speed": "0x"}
        encode_start = time.time()
        captured_errors = []
        early_abort = False
        abort_threshold = size_to_compare * 0.95

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
                            elapsed = time.time() - encode_start
                            duration_to_show = trim_duration if is_trim else info['duration']
                            show_progress(ms / 1000000, duration_to_show, profile['codec'], cur_stats["bitrate"], cur_stats["speed"], elapsed)
                        except ValueError:
                            pass
                elif 'total_size=' in line:
                    val = line.split('=')[1].strip()
                    if val != 'N/A':
                        try:
                            current_size = int(val)
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
                if output_path.exists(): output_path.unlink()
                return (False, 0, 0, 'early_abort')

            if process.returncode != 0:
                print(f"{R}FFmpeg error during encoding.{NC}")
                for err in captured_errors[-10:]:
                    print(f"  {R}{err}{NC}")
                if output_path.exists(): output_path.unlink()
                return (False, 0, 0, 'ffmpeg_error')

            size_after = output_path.stat().st_size

            if size_after >= size_to_compare:
                print(f" {R}-> File larger ({format_size(size_after)} > {format_size(size_to_compare)}).{NC}")
                return (False, size_after, 0, 'too_large')

            # SSIM verification
            dur_for_samples = trim_duration if is_trim else info['duration']
            p1 = dur_for_samples * 0.25
            p2 = dur_for_samples * 0.75
            if p2 + SAMPLE_DURATION > dur_for_samples:
                p2 = max(0, dur_for_samples - SAMPLE_DURATION - 1)

            orig_p1 = start_offset + p1
            orig_p2 = start_offset + p2

            ssim1 = get_ssim(input_path, output_path, orig_p1, p1, SAMPLE_DURATION)
            ssim2 = get_ssim(input_path, output_path, orig_p2, p2, SAMPLE_DURATION)
            ssim = min(ssim1, ssim2)

            saved_bytes = size_to_compare - size_after
            saved_pct = saved_bytes * 100 / size_to_compare
            print(f" {G}-> Result:{NC} Q={quality_val} | Saved: {saved_pct:.2f}% | SSIM: {ssim:.4f}")

            return (True, size_after, ssim, None)

        except KeyboardInterrupt:
            print(f"\n{R}>>> Abort. Cleaning up...{NC}")
            process.terminate()
            if output_path.exists(): output_path.unlink()
            sys.exit(1)

    # Binary search for optimal quality
    if use_binary_search and len(quality_values) > 1:
        print(f"{Y}Binary Search Mode:{NC} Testing {len(quality_values)} quality levels [{quality_values[0]}..{quality_values[-1]}]")

        # Binary search: find the best (most compression) quality that meets SSIM threshold
        # For direction > 0: higher index = worse quality = more compression
        # For direction < 0: lower index = worse quality = more compression
        low, high = 0, len(quality_values) - 1
        best_result = None  # (quality, size_after, ssim, saved_bytes, saved_pct)
        best_acceptable = None  # Backup: best result with acceptable SSIM even if savings not met

        while low <= high:
            mid = (low + high) // 2
            quality = quality_values[mid]

            success, size_after, ssim, error = run_encode_pass(quality)

            if error == 'ffmpeg_error':
                batch_stats['failed'] += 1
                return (False, 0)

            if error in ('early_abort', 'too_large'):
                # Need less compression (better quality)
                if profile['quality_direction'] > 0:
                    high = mid - 1  # Try lower Q values
                else:
                    low = mid + 1   # Try higher Q values
                continue

            if not success:
                # Unexpected failure
                if profile['quality_direction'] > 0:
                    high = mid - 1
                else:
                    low = mid + 1
                continue

            # Check SSIM threshold
            if ssim < 0.940:
                print(f" {R}   -> Quality too low for this level.{NC}")
                # Need better quality (less compression)
                if profile['quality_direction'] > 0:
                    high = mid - 1
                else:
                    low = mid + 1
                if output_path.exists(): output_path.unlink()
                continue

            saved_bytes = size_to_compare - size_after
            saved_pct = saved_bytes * 100 / size_to_compare

            # Check if meets targets
            meets_targets = (saved_pct >= MIN_SAVINGS and ssim >= MIN_QUALITY) or \
                           (saved_pct >= 50.0 and ssim >= 0.945)

            # Track best acceptable result (SSIM >= 0.945 and some savings) as backup
            if ssim >= 0.945 and saved_pct > 0:
                if best_acceptable is None or saved_pct > best_acceptable[4]:
                    best_acceptable = (quality, size_after, ssim, saved_bytes, saved_pct)

            if meets_targets:
                best_result = (quality, size_after, ssim, saved_bytes, saved_pct)
                
                # EARLY EXIT: If savings are already excellent, stop searching
                # No point searching further when we've already saved 50%+ with good quality
                if saved_pct >= 50.0 and ssim >= MIN_QUALITY:
                    print(f" {BG}   -> Early exit: {saved_pct:.1f}% savings is excellent!{NC}")
                    break
                
                # Otherwise try for more compression - move to higher indices
                low = mid + 1
                if output_path.exists(): output_path.unlink()
            else:
                # SSIM OK but savings not enough, need more compression
                low = mid + 1
                if output_path.exists(): output_path.unlink()

        # Use best result if found, or fall back to best acceptable
        final_result = best_result or best_acceptable
        if final_result:
            quality, size_after, ssim, saved_bytes, saved_pct = final_result
            is_fallback = best_result is None

            # Re-encode at best quality to get final file
            if is_fallback:
                print(f"\n{Y}>>> No perfect match. Using best acceptable Q={quality} (saved {saved_pct:.1f}%, SSIM {ssim:.4f}){NC}")
            else:
                print(f"\n{BG}>>> Final encode at optimal Q={quality}{NC}")

            success, size_after, ssim, error = run_encode_pass(quality)

            if success and ssim >= 0.940:
                saved_bytes = size_to_compare - size_after
                saved_pct = saved_bytes * 100 / size_to_compare
                file_time = time.time() - file_start_time
                print(f" {BG}>>> SUCCESS! {format_size(saved_bytes)} saved in {format_time(file_time)}.{NC}")
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

        # Binary search failed - show why
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
    quality = q_override if q_override is not None else quality_values[0]

    while should_continue(quality):
        success, size_after, ssim, error = run_encode_pass(quality)

        if error == 'ffmpeg_error':
            batch_stats['failed'] += 1
            return (False, 0)

        if error in ('early_abort', 'too_large'):
            quality += step
            continue

        if not success:
            quality += step
            continue

        if ssim < 0.940:
            print(f" {R}   -> Quality too low. Aborting.{NC}")
            if output_path.exists(): output_path.unlink()
            batch_stats['failed'] += 1
            file_time = time.time() - file_start_time
            last_encode_result['filename'] = input_path.name
            last_encode_result['status'] = 'failed'
            last_encode_result['quality'] = quality
            last_encode_result['ssim'] = ssim
            last_encode_result['reason'] = f'Quality too low (SSIM {ssim:.4f} < 0.940)'
            last_encode_result['duration'] = file_time
            return (False, 0)

        saved_bytes = size_to_compare - size_after
        saved_pct = saved_bytes * 100 / size_to_compare

        if (saved_pct >= MIN_SAVINGS and ssim >= MIN_QUALITY) or \
           (saved_pct >= 50.0 and ssim >= 0.945):
            file_time = time.time() - file_start_time
            print(f" {BG}>>> SUCCESS! {format_size(saved_bytes)} saved in {format_time(file_time)}.{NC}")
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

        print(f" {R}   -> Not optimal. Next pass...{NC}")
        if output_path.exists(): output_path.unlink()
        quality += step

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
    parser.add_argument('--min-size', type=int, default=DEFAULT_MIN_SIZE_MB,
                        help=f'Skip files smaller than N MB (default: {DEFAULT_MIN_SIZE_MB})')
    parser.add_argument('--copy-audio', action='store_true',
                        help='Copy audio without re-encoding (faster, preserves original audio)')
    parser.add_argument('--audio-mode', choices=['enhanced', 'standard'], default='enhanced',
                        help='Audio processing mode (default: enhanced)')
    parser.add_argument('--ss', type=str, help='Start time (e.g. 00:00:10 or 10)')
    parser.add_argument('--to', type=str, help='End time (e.g. 00:00:20 or 20)')
    parser.add_argument('--no-fun-facts', action='store_true', help='Disable fun facts display')
    parser.add_argument('--video-mode', choices=['compress', 'copy'], default='compress',
                        help='Video processing mode: compress (default) or copy (passthrough)')
    parser.add_argument('--q', type=int, help='Manual starting quality value')
    parser.add_argument('--port', type=int, help='Port of the running Arcade Server to notify')
    args = parser.parse_args()
    
    global ENABLE_FUNFACTS
    ENABLE_FUNFACTS = not args.no_fun_facts

    if args.port:
        print(f"🔌 Notification Port: {args.port}")
    else:
        print(f"⚠️ No notification port provided. Status updates will be disabled.")

    # Select encoder
    if args.encoder == 'auto':
        encoder_key = detect_encoder()
    else:
        encoder_key = args.encoder
    
    profile = ENCODER_PROFILES[encoder_key]
    print(f"{BG}VIDEO OPTIMIZER V2.1{NC} - {G}{profile['name']}{NC}")
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
