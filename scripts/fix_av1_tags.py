#!/usr/bin/env python3
"""
AV1 Tag Fixer
Identifies files that were incorrectly tagged as 'hvc1' (HEVC) by video_optimizer.py
but actually contain AV1 video bitstreams.

It does this by attempting to decode the first second of the video.
If decoding throws errors (because ffmpeg tries to decode AV1 with an HEVC decoder),
it creates a temporary remux with the correct 'av01' tag and tests again.
If the errors disappear, the file is confirmed as AV1 and fixed in-place.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# Colors
G = '\033[92m'
R = '\033[91m'
Y = '\033[93m'
C = '\033[96m'
NC = '\033[0m'

def test_decode(file_path: Path) -> bool:
    """Returns True if the file decodes without any ffmpeg errors."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(file_path), "-t", "2", "-f", "null", "-"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        # Any stderr output from ffmpeg -v error indicates decoder problems
        return len(res.stderr.strip()) == 0
    except subprocess.TimeoutExpired:
        # If it takes more than 10 seconds for 2 seconds of video, something is very wrong
        return False
    except Exception as e:
        print(f"  {R}Failed to run ffmpeg: {e}{NC}")
        return False

def fix_file(file_path: Path):
    print(f"\n{C}Analyzing: {file_path.name}{NC}")
    
    # Check if we already have it correctly as AV1
    probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)]
    try:
        codec_out = subprocess.run(probe_cmd, capture_output=True, text=True).stdout.strip()
        if "av1" in codec_out.lower():
            print(f"  {G}✓ Already identified as AV1. Skipping.{NC}")
            return
    except Exception:
        pass

    # 1. Test decode as-is
    if test_decode(file_path):
        print(f"  {G}✓ File decodes perfectly with current tags. Skipping.{NC}")
        return

    print(f"  {Y}⚠ Decode errors detected. Testing AV1 container remux...{NC}")
    tmp_path = file_path.with_suffix('.tmp_remux.mp4')
    
    # 2. Remux with 'av01' tag
    remux_cmd = [
        "ffmpeg", "-v", "error", "-i", str(file_path), 
        "-c", "copy", "-tag:v", "av01", "-y", str(tmp_path)
    ]
    subprocess.run(remux_cmd, capture_output=True)

    # 3. Test decode the remuxed 'av01' file
    if os.path.exists(tmp_path) and test_decode(tmp_path):
        print(f"  {G}✓ SUCCESS! Video is indeed AV1 disguised as HEVC.{NC}")
        print(f"  {G}✓ Replacing original file with fixed container metadata...{NC}")
        shutil.move(str(tmp_path), str(file_path))
    else:
        print(f"  {R}✗ Still broken. Not a simple AV1 tag issue. Leaving untouched.{NC}")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def main():
    print(f"{C}======================================================{NC}")
    print(f"{C} Arcade-Scanner AV1 Tag Fixer{NC}")
    print(f"{C}======================================================{NC}")
    
    if len(sys.argv) > 1:
        directories = [Path(d) for d in sys.argv[1:]]
    else:
        # Default user configuration if none provided
        try:
            # Let's try to pull paths from settings.json
            import json
            settings_path = Path(__file__).parent.parent / "arcade_data" / "settings.json"
            if settings_path.exists():
                with open(settings_path, 'r') as f:
                    data = json.load(f)
                    targets = data.get("scan_targets", [])
                    directories = [Path(p) for p in targets if p]
            else:
                directories = []
        except Exception:
            directories = []

        if not directories:
            print(f"{R}No scan directories found. Please provide path as argument:{NC}")
            print(f"  python3 fix_av1_tags.py /path/to/videos")
            sys.exit(1)

    print(f"Scanning provided paths:")
    for path_arg in sys.argv[1:] if len(sys.argv) > 1 else directories:
        p = Path(path_arg)
        if not p.exists():
            continue
            
        if p.is_file():
            # Support direct files passed via arguments
            fix_file(p)
        elif p.is_dir():
            for ext in ['mp4', 'mkv', 'mov']:
                for f in p.rglob(f"*_opt.{ext}"):
                    fix_file(f)

    print(f"\n{C}Done! The arcade scanner will pick up the changes on its next scan.{NC}")

if __name__ == "__main__":
    main()
