import asyncio
import time
import webbrowser
import argparse
import os
from arcade_scanner.config import config
from arcade_scanner.database import db
from arcade_scanner.scanner import get_scanner_manager
from arcade_scanner.templates.dashboard_template import generate_html_report
from arcade_scanner.server.web_server import start_server
from arcade_scanner.core.maintenance import purge_media, cleanup_orphans, purge_broken_media, purge_thumbnails, purge_previews

def run_scanner(args_list=None):
    parser = argparse.ArgumentParser(description="Arcade Video Scanner 6.0")
    parser.add_argument("--rebuild", action="store_true", help="Delete all thumbnails and previews and regenerate them.")
    parser.add_argument("--rebuild-thumbs", action="store_true", help="Delete only thumbnails and regenerate them.")
    parser.add_argument("--rebuild-previews", action="store_true", help="Delete only preview clips and regenerate them.")
    parser.add_argument("--cleanup", action="store_true", help="Remove orphan thumbnails and previews.")
    args, unknown = parser.parse_known_args(args_list)

    print("--- Arcade Video Scanner 6.0 (Refactored) ---")
    
    # 0. Maintenance
    if args.rebuild:
        purge_media()
    elif args.rebuild_thumbs:
        purge_thumbnails()
    elif args.rebuild_previews:
        purge_previews()
    
    purge_broken_media()
    
    # 1. Run Async Scan
    try:
        # Run the metadata scan
        print("🚀 Starting Library Scan...")
        mgr = get_scanner_manager()
        
        should_force = args.rebuild or args.rebuild_thumbs or args.rebuild_previews
        if should_force:
            print("Usage of rebuild flags will force a re-scan of metadata and assets.")
            
        asyncio.run(mgr.run_scan(
            progress_callback=lambda x: print(f"  {x}"),
            force_rescan=should_force
        ))
        
        # 2. Asset Generation (Thumbs/Previews)
        pass # Handled in run_scan now
    except KeyboardInterrupt:
        print("\n⚠️ Scan interrupted.")
    except Exception as e:
        print(f"❌ Error: {e}")

    # 3. Report Generation
    print("📊 Generating Report...")
    results = [e.model_dump(by_alias=True) for e in db.get_all()]
    
    # Start Server first to know port
    server, port = start_server()
    
    generate_html_report(results, config.report_file, server_port=port)
    
    # 4. Open Browser
    url = f"http://localhost:{port}/"
    print(f"Opening dashboard: {url}")
    webbrowser.open(url)
    
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
