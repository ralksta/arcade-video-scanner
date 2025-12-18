import os
import sys
import subprocess
import time
import json
import re
import shutil
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
MIN_SAVINGS = 20.0
MIN_QUALITY = 0.960
START_CQ = 24  # NVENC CQ: lower is better quality (approx 0-51)
STEP = 4
MAX_CQ = 44    # Equivalent to MIN_Q in shell (but inverted)
SAMPLE_DURATION = 5

# --- COLORS ---
G = '\033[0;32m'
BG = '\033[1;32m'
R = '\033[0;31m'
NC = '\033[0m'

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
        
        # Parse FPS
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
    """Calculate SSIM between original and optimized file for a specific segment."""
    cmd = [
        'ffmpeg', '-ss', str(start_time), '-t', str(duration), '-i', str(original),
        '-ss', str(start_time), '-t', str(duration), '-i', str(optimized),
        '-filter_complex', 'ssim', '-f', 'null', '-'
    ]
    try:
        # SSIM output goes to stderr
        result = subprocess.run(cmd, capture_output=True, text=True)
        # Look for "All:0.9xxx"
        match = re.search(r'All:([\d.]+)', result.stderr)
        if match:
            return float(match.group(1))
    except Exception as e:
        print(f"{R}Error calculating SSIM: {e}{NC}")
    return 0.0

def show_progress(msg, current, total, bar_length=30):
    """Simple console progress bar."""
    percent = float(current) * 100 / total if total > 0 else 0
    percent = min(100.0, percent)
    arrow = '█' * int(percent/100 * bar_length)
    spaces = '░' * (bar_length - len(arrow))
    sys.stdout.write(f"\r {G}{msg}:{NC} [{arrow}{spaces}] {BG}{int(percent)}%{NC}")
    sys.stdout.flush()

def process_file(input_path):
    input_path = Path(input_path)
    if not input_path.exists():
        return

    # Skip already optimized or marked files
    if "_opt.mp4" in input_path.name or "NO-OPT" in input_path.name:
        return

    output_path = input_path.parent / f"{input_path.stem}_opt.mp4"
    size_before = input_path.stat().st_size
    
    print(f"\n{G}Target:{NC} {input_path.name}")
    print("-" * 52)
    
    info = get_video_info(input_path)
    if not info or info['duration'] <= 0:
        return

    cq = START_CQ
    while cq <= MAX_CQ:
        print(f"{G}Pass:{NC} CQ={cq}")
        
        # Use NVENC HEVC with high quality settings
        # -preset p7: slowest/highest quality
        # -rc vbr: variable bitrate
        # -cq: constant quality parameter
        # -profile:v main10 for better color if input is 10-bit
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-c:v', 'hevc_nvenc',
            '-preset', 'p7',
            '-rc', 'vbr',
            '-cq', str(cq),
            '-vf', "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2",
            '-tag:v', 'hvc1',
            '-movflags', '+faststart',
            '-c:a', 'aac', '-b:a', '256k',
            '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11',
            '-progress', 'pipe:1',
            '-loglevel', 'error',
            str(output_path)
        ]
        
        # Run ffmpeg and parse progress
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        try:
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if 'out_time_ms=' in line:
                    ms = int(line.split('=')[1])
                    show_progress("STATUS", ms / 1000000, info['duration'])
            
            process.wait()
            print() # New line after status bar
            
            if process.returncode != 0:
                print(f"{R}FFmpeg error during encoding.{NC}")
                if output_path.exists(): output_path.unlink()
                return

            size_after = output_path.stat().st_size
            if size_after >= size_before:
                print(f" {R}-> File larger. Increasing CQ...{NC}")
                cq += 6
                continue

            # SSIM verification (2 points)
            p1 = info['duration'] * 0.25
            p2 = info['duration'] * 0.75
            
            # Ensure p2 + sample doesn't exceed duration
            if p2 + SAMPLE_DURATION > info['duration']:
                p2 = max(0, info['duration'] - SAMPLE_DURATION - 1)
            
            ssim1 = get_ssim(input_path, output_path, p1, SAMPLE_DURATION)
            ssim2 = get_ssim(input_path, output_path, p2, SAMPLE_DURATION)
            ssim = min(ssim1, ssim2)
            
            saved_pct = (size_before - size_after) * 100 / size_before
            print(f" {G}-> Result:{NC} CQ={cq} | Saved: {saved_pct:.2f}% | SSIM: {ssim:.4f}")

            # Check success conditions
            if (saved_pct >= MIN_SAVINGS and ssim >= MIN_QUALITY) or \
               (saved_pct >= 50.0 and ssim >= 0.945):
                print(f" {BG}>>> SUCCESS! {int((size_before - size_after)/1024/1024)} MB saved.{NC}")
                return
            
            if ssim < 0.940:
                print(f" {R}   -> Quality too low. Aborting.{NC}")
                if output_path.exists(): output_path.unlink()
                return

            print(f" {R}   -> Not optimal. Next pass...{NC}")
            cq += STEP

        except KeyboardInterrupt:
            print(f"\n{R}>>> Abort. Cleaning up...{NC}")
            process.terminate()
            if output_path.exists(): output_path.unlink()
            sys.exit(1)

def main():
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            process_file(arg)
    else:
        print(f"{BG}NVIDIA NVENC VIDEO OPTIMIZER V1.0{NC}")
        print(f"{G}Drag and drop files or enter paths (space separated):{NC}")
        try:
            raw_input = input()
            # Basic handling for drag & drop filenames with spaces
            # (Matches what typical shells do)
            import shlex
            files = shlex.split(raw_input)
            for f in files:
                process_file(f)
        except EOFError:
            pass

    # Play completion sound (Windows)
    try:
        import winsound
        winsound.MessageBeep()
    except:
        pass

if __name__ == "__main__":
    main()
