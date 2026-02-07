import asyncio
import time
import webbrowser
import argparse
import os
from arcade_scanner.config import config
from arcade_scanner.database import db, user_db
from arcade_scanner.scanner import get_scanner_manager
from arcade_scanner.templates.dashboard_template import generate_html_report
from arcade_scanner.server.web_server import start_server
from arcade_scanner.core.maintenance import purge_media, cleanup_orphans, purge_broken_media, purge_thumbnails

def run_scanner(args_list=None):
    parser = argparse.ArgumentParser(description="Arcade Media Scanner 6.3")
    parser.add_argument("--rebuild", action="store_true", help="Delete all thumbnails and previews and regenerate them.")
    parser.add_argument("--rebuild-thumbs", action="store_true", help="Delete only thumbnails and regenerate them.")

    parser.add_argument("--cleanup", action="store_true", help="Remove orphan thumbnails and previews.")
    parser.add_argument("--ssl", action="store_true", help="Enable HTTPS mode with self-signed certificate.")
    parser.add_argument("--skip-setup", action="store_true", help="Skip the first-run setup wizard.")
    args, unknown = parser.parse_known_args(args_list)

    # 0. First-Run Setup Wizard
    if not args.skip_setup:
        from arcade_scanner.onboarding import run_onboarding
        run_onboarding()

    print("--- Arcade Media Scanner 6.7 ---")
    
    # 0. Maintenance
    if args.rebuild:
        purge_media()
    elif args.rebuild_thumbs:
        purge_thumbnails()

    
    purge_broken_media()
    
    # 0.5 Data Migration
    print("📦 Checking for legacy user data to migrate...")
    user_db.migrate_from_db(db)

    # 1. Load cached data (fast — just reads JSON from disk)
    db.load()
    cached_count = len(db.get_all())
    print(f"📂 Loaded {cached_count} cached entries")

    # 2. Start Server FIRST — user sees dashboard immediately with cached data
    print("🌐 Starting server...")
    server, port = start_server(use_ssl=args.ssl)
    
    # 3. Generate initial report from cache
    results = [e.model_dump(by_alias=True) for e in db.get_all()]
    generate_html_report(results, config.report_file, server_port=port)

    # 4. Open browser immediately
    protocol = "https" if args.ssl else "http"
    url = f"{protocol}://localhost:{port}/"
    print(f"Opening dashboard: {url}")
    webbrowser.open(url)

    # 5. Run scan in BACKGROUND thread
    def background_scan():
        try:
            mgr = get_scanner_manager()
            should_force = args.rebuild or args.rebuild_thumbs
            if should_force:
                print("Usage of rebuild flags will force a re-scan of metadata and assets.")
            
            scan_counter = 0
            def print_progress(msg):
                nonlocal scan_counter
                scan_counter += 1
                filename = msg.replace("Analyzing ", "")
                if len(filename) > 60:
                    filename = filename[:57] + "..."
                import sys
                sys.stdout.write(f"\r\033[K  🔍 Scanned {scan_counter} files... {filename}")
                sys.stdout.flush()
            
            print("🚀 Starting Library Scan (background)...")
            asyncio.run(mgr.run_scan(
                progress_callback=print_progress,
                force_rescan=should_force
            ))
            print()  # Newline after scan completion
            
            # Regenerate report with fresh data
            results = [e.model_dump(by_alias=True) for e in db.get_all()]
            generate_html_report(results, config.report_file, server_port=port)
            
            # DeoVR JSON Generation (if enabled)
            if config.settings.enable_deovr:
                from arcade_scanner.core.deovr_generator import save_deovr_library
                deovr_path = os.path.join(config.hidden_data_dir, "deovr_library.json")
                server_url = f"{protocol}://localhost:{port}"
                print("🥽 Generating DeoVR library...")
                save_deovr_library(deovr_path, db.get_all(), server_url)
                
        except KeyboardInterrupt:
            print("\n⚠️ Scan interrupted.")
        except Exception as e:
            print(f"❌ Scan error: {e}")

    import threading
    scan_thread = threading.Thread(target=background_scan, daemon=True)
    scan_thread.start()

    # Keep alive
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
