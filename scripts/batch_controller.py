#!/usr/bin/env python3
"""
Batch Controller V2.1 - Clean Summary Table Display with Logging
Shows a live-updating status table for all parallel encodes.
Writes detailed results to a persistent log file.
"""
import os
import sys
import argparse
import time
import threading
import subprocess
import re
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Logs directory
LOG_DIR = Path.home() / ".arcade-scanner" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Add parent path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from arcade_scanner.core.video_processor import get_optimal_workers, get_best_encoder

# --- COLORS ---
G = '\033[0;32m'
BG = '\033[1;32m'
R = '\033[0;31m'
Y = '\033[0;33m'
NC = '\033[0m'
CYAN = '\033[0;36m'
DIM = '\033[2m'
CLEAR_LINE = '\033[K'

# Shared state for display
worker_status = {}  # {worker_id: {"file": str, "status": str, "progress": int, "q": int}}
stats = {"completed": 0, "succeeded": 0, "failed": 0, "total": 0}
file_results = []  # Detailed results for logging: [{filename, status, quality, ssim, saved_pct, duration}]
display_lock = threading.Lock()
stop_display = threading.Event()


def truncate(text, max_len=35):
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[:max_len-3] + "..."


def draw_table(start_time, max_workers):
    """Draw the status table (called repeatedly)."""
    elapsed = time.time() - start_time
    mins, secs = divmod(int(elapsed), 60)
    
    lines = []
    lines.append(f"{BG}┌{'─'*62}┐{NC}")
    lines.append(f"{BG}│{NC} 🎮 {CYAN}BATCH ENCODER{NC} - {stats['total']} files, {max_workers} workers" + " " * 20 + f"{BG}│{NC}")
    lines.append(f"{BG}├{'─'*62}┤{NC}")
    
    with display_lock:
        for wid in sorted(worker_status.keys()):
            ws = worker_status[wid]
            filename = truncate(ws.get("file", ""), 30)
            status = ws.get("status", "idle")
            progress = ws.get("progress", 0)
            q = ws.get("q", 0)
            
            if status == "done":
                status_str = f"{BG}✓ Done{NC}"
            elif status == "failed":
                status_str = f"{R}✗ Failed{NC}"
            elif status == "skipped":
                status_str = f"{Y}⊘ Skip{NC}"
            elif status == "encoding":
                bar_len = 10
                filled = int(progress / 100 * bar_len)
                bar = "█" * filled + "░" * (bar_len - filled)
                status_str = f"Q={q} [{bar}] {progress:2d}%"
            else:
                status_str = f"{DIM}waiting...{NC}"
            
            line = f"{BG}│{NC} [{wid}] {filename:<32} {status_str:<25}{BG}│{NC}"
            lines.append(line)
    
    lines.append(f"{BG}├{'─'*62}┤{NC}")
    lines.append(f"{BG}│{NC} {G}✓ {stats['succeeded']}{NC}  {R}✗ {stats['failed']}{NC}  ⏱ {mins:02d}:{secs:02d}" + " " * 35 + f"{BG}│{NC}")
    lines.append(f"{BG}└{'─'*62}┘{NC}")
    
    return lines


def display_loop(start_time, max_workers):
    """Background thread to refresh display."""
    num_lines = 0
    while not stop_display.is_set():
        # Move cursor up and redraw
        if num_lines > 0:
            sys.stdout.write(f"\033[{num_lines}A")
        
        lines = draw_table(start_time, max_workers)
        for line in lines:
            sys.stdout.write(f"\r{CLEAR_LINE}{line}\n")
        sys.stdout.flush()
        num_lines = len(lines)
        
        time.sleep(0.5)


def run_optimizer(args_tuple):
    """Worker function - captures output and updates shared state. Returns detailed results for logging."""
    file_path, port, audio_mode, worker_id = args_tuple
    
    optimizer_path = Path(__file__).parent / "video_optimizer.py"
    filename = Path(file_path).name
    file_start = time.time()
    
    # Result structure for logging
    result = {
        "filename": filename,
        "path": file_path,
        "status": "failed",
        "quality": None,
        "ssim": None,
        "saved_pct": None,
        "saved_bytes": None,
        "duration": 0,
        "reason": None
    }
    
    with display_lock:
        worker_status[worker_id] = {"file": filename, "status": "encoding", "progress": 0, "q": 75}
    
    cmd = [
        sys.executable,
        str(optimizer_path),
        file_path,
        "--audio-mode", audio_mode,
    ]
    if port:
        cmd.extend(["--port", str(port)])
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        success = False
        failed = False  # Track explicit failures
        last_quality = None
        last_ssim = None
        last_saved_pct = None
        last_saved_bytes = None
        failure_reason = None
        
        for line in process.stdout:
            line = line.strip()
            
            # Parse progress: look for percentage
            if '%' in line and 'Saved' not in line:
                match = re.search(r'(\d+)%', line)
                if match:
                    with display_lock:
                        worker_status[worker_id]["progress"] = int(match.group(1))
            
            # Parse Q value: "Q=75" or "-> Result: Q=65"
            if 'Q=' in line:
                match = re.search(r'Q=(\d+)', line)
                if match:
                    last_quality = int(match.group(1))
                    with display_lock:
                        worker_status[worker_id]["q"] = last_quality
            
            # Parse SSIM: "SSIM: 0.9823"
            if 'SSIM:' in line:
                match = re.search(r'SSIM:\s*([\d.]+)', line)
                if match:
                    last_ssim = float(match.group(1))
            
            # Parse savings: "Saved: 45.23%"
            if 'Saved:' in line and '%' in line:
                match = re.search(r'Saved:\s*([\d.]+)%', line)
                if match:
                    last_saved_pct = float(match.group(1))
            
            # Parse bytes saved from SUCCESS line: ">>> SUCCESS! 1.23 GB saved"
            if 'SUCCESS' in line:
                success = True
                # Try to parse saved bytes: "1.23 GB saved" or "456.7 MB saved"
                match = re.search(r'([\d.]+)\s*(GB|MB|KB)\s*saved', line)
                if match:
                    val = float(match.group(1))
                    unit = match.group(2)
                    if unit == 'GB':
                        last_saved_bytes = int(val * 1024 * 1024 * 1024)
                    elif unit == 'MB':
                        last_saved_bytes = int(val * 1024 * 1024)
                    else:
                        last_saved_bytes = int(val * 1024)
            
            # Detect explicit failures
            if 'Quality too low' in line or 'Aborting' in line:
                failed = True
                failure_reason = 'Quality too low (SSIM check failed)'
            
            # Handle skipped files
            if 'Skipping' in line:
                result["status"] = "skipped"
                result["reason"] = line
                result["duration"] = time.time() - file_start
                with display_lock:
                    worker_status[worker_id]["status"] = "skipped"
                    worker_status[worker_id]["progress"] = 100
                    file_results.append(result)
                return (file_path, True, result)
        
        process.wait()
        result["duration"] = time.time() - file_start
        
        with display_lock:
            # Only mark as success if explicit SUCCESS marker was found AND no failure detected
            if success and not failed:
                worker_status[worker_id]["status"] = "done"
                worker_status[worker_id]["progress"] = 100
                result["status"] = "success"
                result["quality"] = last_quality
                result["ssim"] = last_ssim
                result["saved_pct"] = last_saved_pct
                result["saved_bytes"] = last_saved_bytes
                file_results.append(result)
                return (file_path, True, result)
            else:
                worker_status[worker_id]["status"] = "failed"
                result["status"] = "failed"
                result["quality"] = last_quality
                result["ssim"] = last_ssim
                result["reason"] = failure_reason or "Encoding failed"
                file_results.append(result)
                return (file_path, False, result)
            
    except Exception as e:
        result["duration"] = time.time() - file_start
        result["reason"] = str(e)
        with display_lock:
            worker_status[worker_id]["status"] = "failed"
            file_results.append(result)
        return (file_path, False, result)


def format_time(seconds):
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_bytes(bytes_val):
    """Format bytes into human readable string."""
    if bytes_val is None:
        return "N/A"
    if bytes_val >= 1024**3:
        return f"{bytes_val / 1024**3:.2f} GB"
    elif bytes_val >= 1024**2:
        return f"{bytes_val / 1024**2:.1f} MB"
    else:
        return f"{bytes_val / 1024:.0f} KB"


def write_log(start_time, elapsed, encoder_name):
    """Write detailed encoding results to a log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file = LOG_DIR / f"batch_{timestamp}.log"
    
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write("="*70 + "\n")
        f.write(f"ARCADE BATCH ENCODER LOG\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Encoder: {encoder_name}\n")
        f.write(f"Total Time: {format_time(elapsed)}\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"SUMMARY\n")
        f.write(f"--------\n")
        f.write(f"Total Files: {stats['total']}\n")
        f.write(f"Succeeded:   {stats['succeeded']}\n")
        f.write(f"Failed:      {stats['failed']}\n")
        
        # Calculate total savings
        total_saved = sum(r.get('saved_bytes', 0) or 0 for r in file_results if r['status'] == 'success')
        if total_saved > 0:
            f.write(f"Total Saved: {format_bytes(total_saved)}\n")
        f.write("\n")
        
        f.write("DETAILED RESULTS\n")
        f.write("-"*70 + "\n")
        
        for r in file_results:
            f.write(f"\nFile: {r['filename']}\n")
            f.write(f"  Status:   {r['status'].upper()}\n")
            
            if r['status'] == 'success':
                if r['quality']:
                    f.write(f"  Quality:  Q={r['quality']}\n")
                if r['ssim']:
                    f.write(f"  SSIM:     {r['ssim']:.4f}\n")
                if r['saved_pct']:
                    f.write(f"  Savings:  {r['saved_pct']:.1f}%\n")
                if r['saved_bytes']:
                    f.write(f"  Saved:    {format_bytes(r['saved_bytes'])}\n")
            elif r['status'] == 'skipped' and r.get('reason'):
                f.write(f"  Reason:   {r['reason']}\n")
            elif r['status'] == 'failed' and r.get('reason'):
                f.write(f"  Error:    {r['reason']}\n")
            
            f.write(f"  Duration: {format_time(r['duration'])}\n")
        
        f.write("\n" + "="*70 + "\n")
        f.write(f"Log saved to: {log_file}\n")
    
    return log_file


def main():
    parser = argparse.ArgumentParser(description='Batch Controller V2.0')
    parser.add_argument('--files', required=True, help='Comma-separated file paths')
    parser.add_argument('--port', type=int, help='Server port')
    parser.add_argument('--audio-mode', choices=['enhanced', 'standard'], default='enhanced')
    args = parser.parse_args()
    
    files = [f.strip() for f in args.files.split(',') if f.strip()]
    
    if not files:
        print(f"{R}No files provided.{NC}")
        return
    
    encoder, _ = get_best_encoder()
    max_workers = min(get_optimal_workers(), len(files))
    
    stats["total"] = len(files)
    
    # Initialize worker slots
    for i in range(1, max_workers + 1):
        worker_status[i] = {"file": "", "status": "idle", "progress": 0, "q": 0}
    
    # Print initial info
    print(f"\n{Y}Each file: Q=75→65→55→45 loop + SSIM quality check{NC}\n")
    
    start_time = time.time()
    
    # Start display thread
    display_thread = threading.Thread(target=display_loop, args=(start_time, max_workers), daemon=True)
    display_thread.start()
    
    # Prepare work items
    work_items = [(f, args.port, args.audio_mode, (i % max_workers) + 1) for i, f in enumerate(files)]
    
    # Process files
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_optimizer, item): item[0] for item in work_items}
        
        for future in as_completed(futures):
            try:
                _, success, _ = future.result()  # 3 values now: (path, success, result)
                with display_lock:
                    stats["completed"] += 1
                    if success:
                        stats["succeeded"] += 1
                    else:
                        stats["failed"] += 1
            except Exception:
                with display_lock:
                    stats["completed"] += 1
                    stats["failed"] += 1
    
    # Stop display and show final
    stop_display.set()
    time.sleep(0.6)
    
    elapsed = time.time() - start_time
    print(f"\n\n{BG}╔{'═'*62}╗{NC}")
    print(f"{BG}║{NC}                    📊 {CYAN}BATCH COMPLETE{NC} 📊                       {BG}║{NC}")
    print(f"{BG}╠{'═'*62}╣{NC}")
    print(f"{BG}║{NC}  ✓ Succeeded:  {G}{stats['succeeded']}{NC}                                       {BG}║{NC}")
    print(f"{BG}║{NC}  ✗ Failed:     {R}{stats['failed']}{NC}                                         {BG}║{NC}")
    print(f"{BG}║{NC}  ⏱ Time:       {Y}{format_time(elapsed)}{NC}                            {BG}║{NC}")
    print(f"{BG}╚{'═'*62}╝{NC}")
    
    # Write detailed log file
    log_file = write_log(start_time, elapsed, encoder)
    print(f"\n{G}📝 Log saved:{NC} {log_file}")
    
    print(f"\n{Y}Window will close in 10 seconds (Ctrl+C to close now)...{NC}")
    try:
        for i in range(10, 0, -1):
            print(f"\r{DIM}Closing in {i}...{NC}", end="", flush=True)
            time.sleep(1)
        print()
    except KeyboardInterrupt:
        print(f"\n{G}Closing...{NC}")


if __name__ == "__main__":
    main()
