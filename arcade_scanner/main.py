import os
import time
import webbrowser
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from .app_config import SCAN_TARGETS, VIDEO_EXTENSIONS, EXCLUDE_PATHS, CACHE_FILE, REPORT_FILE, MIN_SIZE_MB
from .core.cache_manager import load_cache, save_cache
from .core.video_processor import process_video, get_optimal_workers
from .core.maintenance import purge_media, cleanup_orphans, purge_broken_media, purge_thumbnails, purge_previews
from .templates.dashboard_template import generate_html_report
from .server.web_server import start_server

def run_scanner(args_list=None):
    parser = argparse.ArgumentParser(description="Arcade Video Scanner 5.1.1")
    parser.add_argument("--rebuild", action="store_true", help="Delete all thumbnails and previews and regenerate them.")
    parser.add_argument("--rebuild-thumbs", action="store_true", help="Delete only thumbnails and regenerate them.")
    parser.add_argument("--rebuild-previews", action="store_true", help="Delete only preview clips and regenerate them.")
    parser.add_argument("--cleanup", action="store_true", help="Remove orphan thumbnails and previews.")
    args, unknown = parser.parse_known_args(args_list)

    print("--- Arcade Video Scanner 5.1.1 ---")
    
    if args.rebuild:
        purge_media()
    elif args.rebuild_thumbs:
        purge_thumbnails()
    elif args.rebuild_previews:
        purge_previews()
    
    # Always cleanup zero-byte files to allow regeneration
    purge_broken_media()
    
    # 1. Load Cache
    cache = load_cache(CACHE_FILE)
    print(f"📦 Loaded {len(cache)} items from cache.")
    
    # 2. Scan Files
    video_files = []
    exclude_abs = [os.path.abspath(os.path.expanduser(p)) for p in EXCLUDE_PATHS]
    
    print("🔍 Scanning directories...")
    for target in SCAN_TARGETS:
        abs_t = os.path.abspath(os.path.expanduser(target))
        if not os.path.exists(abs_t):
            print(f"Warning: Scan target not found: {abs_t}")
            continue
            
        print(f"Scanning: {abs_t}")
        for root, dirs, files in os.walk(abs_t):
            # Prune excluded directories
            dirs[:] = [
                d for d in dirs 
                if not d.startswith(".") 
                and os.path.abspath(os.path.join(root, d)) not in exclude_abs
                and not any(ex in os.path.join(root, d) for ex in exclude_abs if "/" in ex) # Handle substring matches for specific names
            ]
            
            # Additional substring check for common exclusion patterns
            if any(ex in root for ex in EXCLUDE_PATHS if not ex.startswith("~")):
                continue

            for file in files:
                if any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS) and not file.endswith("_opt.mp4"):
                    filepath = os.path.join(root, file)
                    try:
                        sz = os.path.getsize(filepath)
                        if sz >= (MIN_SIZE_MB * 1024 * 1024):
                            video_files.append(filepath)
                    except:
                        continue

    print(f"Found {len(video_files)} video files.")
    
    # 2.1 Prune Cache (Remove entries for files that no longer exist)
    stale_keys = [k for k in cache.keys() if k not in video_files and os.path.isabs(k)]
    if stale_keys:
        print(f"🧹 Pruning {len(stale_keys)} stale entries from cache...")
        for k in stale_keys:
            del cache[k]
    
    # Always cleanup orphans if anything was pruned or if requested
    if args.cleanup or stale_keys:
        cleanup_orphans(video_files)

    # 3. Determine rebuild mode
    rebuild_mode = None
    if args.rebuild:
        rebuild_mode = None  # Full rebuild - regenerate everything
        print(f"📊 Regenerating {len(video_files)} videos (thumbnails + previews)...")
    elif args.rebuild_thumbs:
        rebuild_mode = 'thumbs'
        print(f"🖼️  Regenerating thumbnails only for {len(video_files)} videos...")
    elif args.rebuild_previews:
        rebuild_mode = 'previews'
        print(f"🎬 Regenerating preview clips only for {len(video_files)} videos...")
    else:
        print(f"📊 Analyzing {len(video_files)} videos...")
    
    # 4. Process Videos (Multi-threaded)
    results = []
    
    try:
        num_workers = get_optimal_workers()
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_file = {executor.submit(process_video, f, cache, rebuild_mode): f for f in video_files}
            count = 0
            for future in as_completed(future_to_file):
                try:
                    res = future.result()
                    if res:
                        results.append(res)
                        # CRITICAL: Update cache so progress is saved
                        cache[res["FilePath"]] = res
                except Exception as e:
                    filename = os.path.basename(future_to_file[future])
                    print(f"\n  [Error] Failed to process {filename}: {e}")
                
                count += 1
                if count % 10 == 0 or count == len(video_files):
                    action = "thumbnails" if rebuild_mode == 'thumbs' else "previews" if rebuild_mode == 'previews' else "processed"
                    print(f"  [{count}/{len(video_files)}] {action}...")
    except KeyboardInterrupt:
        print("\n\n⚠️  Scan interrupted by user. Saving progress...")
    except Exception as e:
        print(f"\n\n❌ Unexpected error during scan: {e}")

    # 4. Save Cache
    save_cache(cache, CACHE_FILE)
    
    # 5. Generate Report
    print(f"Generating report: {REPORT_FILE}")
    generate_html_report(results, REPORT_FILE)
    
    # 6. Start Server
    server, port = start_server()
    
    # 7. Open Browser
    url = f"http://localhost:{port}/"
    print(f"Opening dashboard: {url}")
    webbrowser.open(url)
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping server...")
        server.shutdown()
        server.server_close()
        print("Server stopped. Goodbye!")

if __name__ == "__main__":
    run_scanner()
