#!/usr/bin/env python3
"""
Video Optimizer V2.2 - Multi-Platform Hardware Encoder
Supports: NVIDIA NVENC (RTX 4090), Apple VideoToolbox (M4 Max), Intel QuickSync (QSV)
"""
import os
import sys
import subprocess
import argparse
import json
import re
import time
from pathlib import Path

# --- CONFIGURATION ---
MIN_SAVINGS = 20.0
MIN_QUALITY = 0.960
SAMPLE_DURATION = 5
DEFAULT_MIN_SIZE_MB = 50  # Skip files smaller than this
ENABLE_FUNFACTS = True    # Show fun facts during long encodes (>5 min)
FUNFACT_INTERVAL = 30     # Seconds between fun facts
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

def get_ssim(original, optimized, start_time, duration):
    """Calculate SSIM between original and optimized file."""
    cmd = [
        'ffmpeg', '-ss', str(start_time), '-t', str(duration), '-i', str(original),
        '-ss', str(start_time), '-t', str(duration), '-i', str(optimized),
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

def build_ffmpeg_command(input_path, output_path, profile, quality_value, copy_audio=False):
    """Build the ffmpeg command based on encoder profile."""
    cmd = ['ffmpeg', '-y']
    
    cmd.extend(profile['hwaccel_input'])
    cmd.extend(['-i', str(input_path)])
    cmd.extend(['-c:v', profile['codec']])
    cmd.extend(profile['encoder_args'])
    cmd.extend([profile['quality_flag'], str(quality_value)])
    cmd.extend(['-vf', profile['video_filter']])
    
    # Audio settings
    if copy_audio:
        cmd.extend(['-c:a', 'copy'])
    else:
        # Audio Pipeline: 
        # 1. High-pass (100Hz): Remove low rumble
        # 2. Gate (below -55dB): Silence hiss/noise so it doesn't get boosted
        # 3. Loudnorm: Normalize volume
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

def process_file(input_path, profile, min_size_mb=50, copy_audio=False, port=None):
    """Process a single video file. Returns (success, bytes_saved)."""
    input_path = Path(input_path)
    
    if not input_path.exists():
        return (False, 0)

    # Skip already optimized or marked files
    if "_opt.mp4" in input_path.name or "NO-OPT" in input_path.name:
        print(f"{Y}Skipping:{NC} {input_path.name} (already optimized marker)")
        batch_stats['skipped'] += 1
        return (False, 0)

    output_path = input_path.parent / f"{input_path.stem}_opt.mp4"
    
    # Skip if output already exists
    if output_path.exists():
        print(f"{Y}Skipping:{NC} {input_path.name} (_opt.mp4 already exists)")
        batch_stats['skipped'] += 1
        return (False, 0)
    
    size_before = input_path.stat().st_size
    size_mb = size_before / (1024 * 1024)
    
    # Skip small files
    if size_mb < min_size_mb:
        print(f"{Y}Skipping:{NC} {input_path.name} ({size_mb:.1f} MB < {min_size_mb} MB min)")
        batch_stats['skipped'] += 1
        return (False, 0)
    
    print(f"\n{G}Target:{NC} {input_path.name} ({format_size(size_before)})")
    print("-" * 52)
    
    info = get_video_info(input_path)
    if not info or info['duration'] <= 0:
        batch_stats['failed'] += 1
        return (False, 0)

    start_q, end_q, step = profile['quality_range']
    quality = start_q
    file_start_time = time.time()
    
    def should_continue(q):
        if profile['quality_direction'] > 0:
            return q <= end_q
        else:
            return q >= end_q
    
    while should_continue(quality):
        print(f"{G}Pass:{NC} Q={quality}")
        
        cmd = build_ffmpeg_command(input_path, output_path, profile, quality, copy_audio)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        cur_stats = {"bitrate": "0kb/s", "speed": "0x"}
        encode_start = time.time()
        
        try:
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
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
                            show_progress(ms / 1000000, info['duration'], profile['codec'], cur_stats["bitrate"], cur_stats["speed"], elapsed)
                        except ValueError:
                            pass
            
            process.wait()
            print()
            
            if process.returncode != 0:
                print(f"{R}FFmpeg error during encoding.{NC}")
                if output_path.exists(): output_path.unlink()
                batch_stats['failed'] += 1
                return (False, 0)

            size_after = output_path.stat().st_size
            if size_after >= size_before:
                print(f" {R}-> File larger. Adjusting quality...{NC}")
                quality += step
                continue

            # SSIM verification
            p1 = info['duration'] * 0.25
            p2 = info['duration'] * 0.75
            if p2 + SAMPLE_DURATION > info['duration']:
                p2 = max(0, info['duration'] - SAMPLE_DURATION - 1)
            
            ssim1 = get_ssim(input_path, output_path, p1, SAMPLE_DURATION)
            ssim2 = get_ssim(input_path, output_path, p2, SAMPLE_DURATION)
            ssim = min(ssim1, ssim2)
            
            saved_bytes = size_before - size_after
            saved_pct = saved_bytes * 100 / size_before
            print(f" {G}-> Result:{NC} Q={quality} | Saved: {saved_pct:.2f}% | SSIM: {ssim:.4f}")

            if (saved_pct >= MIN_SAVINGS and ssim >= MIN_QUALITY) or \
               (saved_pct >= 50.0 and ssim >= 0.945):
                file_time = time.time() - file_start_time
                print(f" {BG}>>> SUCCESS! {format_size(saved_bytes)} saved in {format_time(file_time)}.{NC}")
                batch_stats['total_saved_bytes'] += saved_bytes
                batch_stats['total_time'] += file_time
                batch_stats['success'] += 1
                
                if port:
                    notify_server(port, input_path)
                    
                return (True, saved_bytes)
            
            if ssim < 0.940:
                print(f" {R}   -> Quality too low. Aborting.{NC}")
                if output_path.exists(): output_path.unlink()
                batch_stats['failed'] += 1
                return (False, 0)

            print(f" {R}   -> Not optimal. Next pass...{NC}")
            quality += step

        except KeyboardInterrupt:
            print(f"\n{R}>>> Abort. Cleaning up...{NC}")
            process.terminate()
            if output_path.exists(): output_path.unlink()
            sys.exit(1)
    
    batch_stats['failed'] += 1
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

def main():
    parser = argparse.ArgumentParser(description='Multi-Platform Video Optimizer V2.1')
    parser.add_argument('files', nargs='*', help='Video files to optimize')
    parser.add_argument('--encoder', choices=['auto', 'nvenc', 'videotoolbox', 'qsv', 'libx265'], default='auto',
                        help='Encoder to use (default: auto-detect)')
    parser.add_argument('--min-size', type=int, default=DEFAULT_MIN_SIZE_MB,
                        help=f'Skip files smaller than N MB (default: {DEFAULT_MIN_SIZE_MB})')
    parser.add_argument('--copy-audio', action='store_true',
                        help='Copy audio without re-encoding (faster, preserves original audio)')
    parser.add_argument('--port', type=int, help='Port of the running Arcade Server to notify')
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
    
    profile = ENCODER_PROFILES[encoder_key]
    print(f"{BG}VIDEO OPTIMIZER V2.1{NC} - {G}{profile['name']}{NC}")
    if args.copy_audio:
        print(f"{Y}Audio: Copy (passthrough){NC}")
    if args.min_size != DEFAULT_MIN_SIZE_MB:
        print(f"{Y}Min size: {args.min_size} MB{NC}")
    
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
        process_file(f, profile, min_size_mb=args.min_size, copy_audio=args.copy_audio, port=args.port)

    # Print batch summary if multiple files
    if len(files) > 1:
        print_batch_summary()
    
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
