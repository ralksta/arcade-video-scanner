import http.server
import os
import subprocess
import mimetypes
import sys
import time
import json
from pathlib import Path
import socket
import ssl
from urllib.parse import unquote, urlparse, parse_qs
import shlex
from arcade_scanner.config import config, IS_WIN, MAX_REQUEST_SIZE, ALLOWED_THUMBNAIL_PREFIX, SETTINGS_FILE
from arcade_scanner.database import db
from arcade_scanner.scanner import get_scanner_manager
from arcade_scanner.server.streaming_util import serve_file_range
from arcade_scanner.templates.dashboard_template import generate_html_report
from arcade_scanner.security import sanitize_path, is_path_allowed, validate_filename, is_safe_directory_traversal, SecurityError

class FinderHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            # 0. DeoVR AUTO-DETECTION ENDPOINT: /deovr serves library JSON
            # DeoVR browser checks for this endpoint when navigating to any site
            if self.path == "/deovr" or self.path == "/deovr/":
                from arcade_scanner.core.deovr_generator import generate_deovr_json
                
                host = self.headers.get("Host", "localhost:8000")
                
                # Detect protocol: Check proxy header OR native SSL socket
                protocol = "http"
                if self.headers.get("X-Forwarded-Proto") == "https":
                    protocol = "https"
                elif isinstance(self.connection, ssl.SSLSocket):
                    protocol = "https"
                    
                server_url = f"{protocol}://{host}"
                
                all_videos = db.get_all()
                smart_collections = list(config.settings.smart_collections)
                
                deovr_data = generate_deovr_json(all_videos, server_url, smart_collections)
                
                scene_count = len(deovr_data.get('scenes', []))
                video_count = sum(len(s.get('list', [])) for s in deovr_data.get('scenes', []))
                print(f"🥽 DeoVR endpoint accessed! Serving {scene_count} scenes ({video_count} total videos)")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.end_headers()
                self.wfile.write(json.dumps(deovr_data).encode("utf-8"))
                return
            
            # 1. ROOT / INDEX -> Serve REPORT_FILE
            # Normalize path to ignore query parameters for routing
            clean_path = self.path.split('?')[0]
            
            spa_routes = ["/", "/index.html", "/lobby", "/favorites", "/review", "/vault", "/treeview"]
            if clean_path in spa_routes or clean_path.startswith("/collections/"):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                
                if os.path.exists(config.report_file):
                    fs = os.stat(config.report_file)
                    self.send_header("Content-Length", str(fs.st_size))
                    self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                    self.end_headers()
                    with open(config.report_file, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    self.send_error(404, "Report file not found")
                return

            # 2. THUMBNAILS -> Serve from THUMB_DIR (with security checks)
            elif self.path.startswith("/thumbnails/"):
                try:
                    rel_path = unquote(self.path[12:])  # remove /thumbnails/
                    print(f"📸 Thumbnail request: {rel_path}")
                    
                    # Security Fix C-4: Prevent path traversal
                    thumb_dir_abs = os.path.abspath(config.thumb_dir)
                    file_path = os.path.abspath(os.path.join(thumb_dir_abs, rel_path))
                    
                    # Ensure result is still inside thumb_dir (prevents ../ attacks)
                    if not file_path.startswith(thumb_dir_abs):
                        print(f"🚨 Path traversal attempt blocked: {rel_path}")
                        self.send_error(403, "Forbidden")
                        return
                    
                    # Additional filename validation (must match thumbnail pattern)
                    filename = os.path.basename(file_path)
                    if not validate_filename(filename, prefix=ALLOWED_THUMBNAIL_PREFIX, suffix=".jpg"):
                        print(f"🚨 Invalid thumbnail name: {filename}")
                        self.send_error(400, "Invalid thumbnail name")
                        return
                    
                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        self.send_response(200)
                        self.send_header("Content-type", "image/jpeg")
                        self.send_header("Access-Control-Allow-Origin", "*")  # Allow VR headsets
                        fs = os.stat(file_path)
                        self.send_header("Content-Length", str(fs.st_size))
                        self.end_headers()
                        with open(file_path, 'rb') as f:
                            self.wfile.write(f.read())
                        return
                    else:
                        self.send_error(404)
                        return
                except Exception as e:
                    print(f"❌ Error serving thumbnail: {e}")
                    self.send_error(500)
                    return

            # 3. STATIC ASSETS -> Catch-all for any path containing /static/
            elif "/static/" in self.path:
                try:
                    # Robustly extract relative path: get everything after the last "/static/"
                    # This handles paths like /static/styles.css AND /arcade_scanner/server/static/styles.css
                    rel_path = self.path.split("/static/")[-1].split('?')[0]
                    file_path = os.path.normpath(os.path.join(config.static_dir, rel_path))
                    
                    # Security check: Ensure the resolved path is inside STATIC_DIR
                    if not file_path.lower().startswith(os.path.normpath(config.static_dir).lower()):
                        self.send_error(403)
                        return

                    if os.path.exists(file_path) and os.path.isfile(file_path):
                        self.send_response(200)
                        if file_path.lower().endswith(".css"):
                            self.send_header("Content-type", "text/css")
                        elif file_path.lower().endswith(".js"):
                            self.send_header("Content-type", "application/javascript")
                        else:
                            mime, _ = mimetypes.guess_type(file_path)
                            if mime:
                                self.send_header("Content-type", mime)
                        
                        fs = os.stat(file_path)
                        self.send_header("Content-Length", str(fs.st_size))
                        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                        self.end_headers()
                        
                        with open(file_path, 'rb') as f:
                            self.wfile.write(f.read())
                        return
                    else:
                        self.send_error(404)
                        return
                except Exception as e:
                    self.send_error(500)
                    return

            # 4. API Endpoints
            elif self.path.startswith("/reveal?path="):
                try:
                    file_path = unquote(self.path.split("path=")[1])
                    print(f"🔍 Reveal requested for: {file_path}")
                    
                    # Security Fix C-3: Validate path is within allowed directories
                    if not is_path_allowed(file_path):
                        print(f"🚨 Unauthorized reveal attempt blocked: {file_path}")
                        self.send_error(403, "Forbidden - Path not in scan directories")
                        return
                    
                    if not os.path.exists(file_path):
                        print(f"❌ Error: File does not exist: {file_path}")
                        self.send_error(404, "File not found")
                        return

                    if IS_WIN:
                        subprocess.run(["explorer", "/select,", os.path.normpath(file_path)])
                    elif sys.platform == "darwin":
                        print(f"🚀 Running: open -R '{file_path}'")
                        result = subprocess.run(["open", "-R", file_path], capture_output=True, text=True)
                        if result.returncode != 0:
                            print(f"❌ Error revealing file: {result.stderr}")
                        else:
                            print("✅ Reveal command successful")
                    else:
                        # Linux / Other: Open parent directory since standard reveal is non-standard
                        parent_dir = os.path.dirname(file_path)
                        print(f"🚀 Running: xdg-open '{parent_dir}'")
                        subprocess.run(["xdg-open", parent_dir])
                            
                    self.send_response(204)
                    self.end_headers()
                except SecurityError as e:
                    print(f"🚨 Security violation: {e}")
                    self.send_error(403, "Forbidden")
                except Exception as e:
                    print(f"❌ Critical error in reveal endpoint: {e}")
                    self.send_error(500, str(e))
            elif self.path.startswith("/api/mark_optimized?"):
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                if path:
                    abs_path = os.path.abspath(path)
                    
                    # Use new DB layer
                    entry = db.get(abs_path)
                    if entry:
                        entry.status = "OK"
                    else:
                        # Create new if missing
                        size_mb = 0
                        try:
                            if os.path.exists(abs_path):
                                size_mb = os.path.getsize(abs_path) / (1024 * 1024)
                        except:
                            pass
                        from arcade_scanner.models.video_entry import VideoEntry
                        entry = VideoEntry(
                            FilePath=abs_path,
                            Size_MB=size_mb,
                            Status="OK"
                        )
                    db.upsert(entry)
                    db.save()
                    
                    # Regenerate HTML report so refresh works
                    try:
                        current_port = self.server.server_address[1]
                        results = [e.model_dump(by_alias=True) for e in db.get_all()]
                        generate_html_report(results, config.report_file, server_port=current_port)
                        print(f"✅ Marked as optimized and report updated: {os.path.basename(abs_path)}")
                    except Exception as e:
                        print(f"⚠️ Cache updated but report gen failed: {e}")

                self.send_response(204)
                self.end_headers()

            elif self.path.startswith("/compress?"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    file_path = params.get("path", [None])[0]
                    
                    if not file_path:
                         print("❌ No path provided for compression")
                         self.send_error(400, "Missing path parameter")
                         return
                    
                    # Security Fix C-1: Sanitize and validate path
                    try:
                        file_path = sanitize_path(file_path)
                    except (SecurityError, ValueError) as e:
                        print(f"🚨 Security violation in compress: {e}")
                        self.send_error(403, "Forbidden - Invalid path")
                        return

                    audio_mode = params.get("audio", ["enhanced"])[0]
                    video_mode = params.get("video", ["compress"])[0]
                    ss = params.get("ss", [None])[0]
                    to = params.get("to", [None])[0]
                    
                    # Validate audio_mode (whitelist)
                    if audio_mode not in ["enhanced", "standard"]:
                        print(f"🚨 Invalid audio mode: {audio_mode}")
                        self.send_error(400, "Invalid audio mode")
                        return
                        
                    # Validate video_mode
                    if video_mode not in ["compress", "copy"]:
                        print(f"🚨 Invalid video mode: {video_mode}")
                        self.send_error(400, "Invalid video mode")
                        return
                    
                    # Get current running port
                    current_port = self.server.server_address[1]
                    print(f"🔌 Current Server Port: {current_port}")
                    print(f"⚡ Optimize: {file_path} | Video: {video_mode} | Audio: {audio_mode} | Trim: {ss}-{to}")
                    
                    # Load latest settings to check fun facts preference
                    enable_fun_facts = config.settings.enable_fun_facts

                    # Build command as list (NEVER use shell=True!)
                    cmd_parts = [sys.executable, config.optimizer_path, file_path,
                                 "--port", str(current_port),
                                 "--audio-mode", audio_mode,
                                 "--video-mode", video_mode]
                    
                    if ss: 
                        cmd_parts.extend(["--ss", ss])
                    if to:
                        cmd_parts.extend(["--to", to])
                    if not enable_fun_facts:
                        cmd_parts.append("--no-fun-facts")
                    
                    if IS_WIN:
                        # Windows: Launch in new console WITHOUT shell=True
                        print(f"🚀 Launching Optimizer (Win): {' '.join(cmd_parts)}")
                        subprocess.Popen(
                            cmd_parts,
                            creationflags=subprocess.CREATE_NEW_CONSOLE
                        )
                    else:
                        # macOS: Use shlex.quote() for safe AppleScript string building
                        safe_cmd = ' '.join(shlex.quote(str(p)) for p in cmd_parts)
                        print(f"🚀 Launching Optimizer (Mac): {safe_cmd}")
                        applescript = f'tell application "Terminal" to do script "{safe_cmd}"'
                        subprocess.run(["osascript", "-e", applescript])
                        
                    self.send_response(204)
                    self.end_headers()
                except SecurityError as e:
                    print(f"🚨 Security violation: {e}")
                    self.send_error(403, "Forbidden")
                except ValueError as e:
                    print(f"❌ Validation error: {e}")
                    self.send_error(400, str(e))
                except Exception as e:
                    print(f"❌ Error in compress endpoint: {e}")
                    self.send_error(500, str(e))

            elif self.path.startswith("/api/keep_optimized?"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    original_path = params.get("original", [None])[0]
                    optimized_path = params.get("optimized", [None])[0]
                    
                    if original_path and optimized_path:
                        orig_abs = os.path.abspath(original_path)
                        opt_abs = os.path.abspath(optimized_path)
                        
                        if os.path.exists(opt_abs):
                            # Move opt to original (replace)
                            # We might want to handle extension changes if they differ, 
                            # but "overwrite" usually implies keeping the original filename?
                            # Actually, if we convert mkv -> mp4, "Keep" should probably keep the mp4 extension.
                            # But for now, let's assume we replace the content of the original if same ext, 
                            # or replace the file entirely if diff ext.
                            
                            # Safest: Remove original, move optimized to original name?
                            # Wait, if we change ext, we should probably rename to original_stem.new_ext
                            # But then we have a dangling original entry in cache.
                            # Let's simple Rename optimized -> original_path (this forces original extension if we are not careful)
                            
                            # Better approach for mixed extensions:
                            # 1. Delete original file.
                            # 2. Rename optimized file to original_stem + optimized_ext.
                            # 3. BUT user expects "Replace". If I have movie.mkv and movie_opt.mp4.
                            #    If I keep opt, I expect movie.mp4? Or movie.mkv (container swap)?
                            #    FFmpeg optimization usually keeps container or standardizes to mp4.
                            #    Let's go with: Rename optimized to (original_dir / original_stem . optimized_ext).
                            
                            # However, to keep it simple and robust matching the user's "overwrite" mental model:
                            # If we just replace the original file, we preserve the original entry in the DB/Cache key?
                            # No, cache key is path.
                            
                            # Let's strictly follow: REPLACE original with optimized.
                            # If extensions differ, we delete original, and rename optimized to original's stem + opt's extension.
                            
                            orig_path_obj = Path(orig_abs)
                            opt_path_obj = Path(opt_abs)
                            
                            new_path = orig_path_obj.with_suffix(opt_path_obj.suffix)
                            
                            # Delete original
                            if os.path.exists(orig_abs):
                                os.remove(orig_abs)
                            
                            # Rename optimized to new path
                            os.rename(opt_abs, new_path)
                            
                            # Update Cache
                            
                            # Remove optimized entry
                            db.remove(opt_abs)
                                
                            # Remove old original entry if path changed (ext changed)
                            if orig_abs != str(new_path):
                                db.remove(orig_abs)
                                
                            db.save()
                            
                        else:
                            print(f"❌ Optimized file not found: {opt_abs}")
                        
                    self.send_response(204)
                    self.end_headers()
                except Exception as e:
                    print(f"❌ Error in keep_optimized: {e}")
                    self.send_error(500, str(e))

            elif self.path.startswith("/api/discard_optimized?"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    path = params.get("path", [None])[0]
                    
                    if path:
                        abs_path = os.path.abspath(path)
                        if os.path.exists(abs_path):
                            os.remove(abs_path)
                            db.remove(abs_path)
                            db.save()
                                
                            # Regenerate Report
                            try:
                                current_port = self.server.server_address[1]
                                results = [e.model_dump(by_alias=True) for e in db.get_all()]
                                generate_html_report(results, config.report_file, server_port=current_port)
                            except Exception as e:
                                print(f"⚠️ Report gen failed: {e}")
                                
                            print(f"🗑️ Discarded optimized: {os.path.basename(abs_path)}")
                            
                    self.send_response(204)
                    self.end_headers()
                except Exception as e:
                    print(f"❌ Error in discard_optimized: {e}")
                    self.send_error(500, str(e))

            # --- RESCAN ---
            elif self.path == "/api/rescan":
                print("🔄 Scan requested via API...")
                try:
                    # Run Async Scanner via sync wrapper or asyncio.run_coroutine_threadsafe if we had a loop.
                    # Given simplehttp server is threaded, we can just run the scanner loop.
                    # BUT `scanner_mgr` uses asyncio.
                    
                    import asyncio
                    mgr = get_scanner_manager()
                    new_count = asyncio.run(mgr.run_scan())
                    
                    # Generate Report
                    port = self.server.server_address[1]
                    results = [e.model_dump(by_alias=True) for e in db.get_all()]
                    generate_html_report(results, config.report_file, server_port=port)
                    
                    self.send_response(200)
                    self.send_header("Content-type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "complete", "count": new_count}).encode())
                    print("✅ Rescan complete.")
                    
                except Exception as e:
                    print(f"❌ Rescan failed: {e}")
                    self.send_error(500, str(e))
                    
                except Exception as e:
                    print(f"❌ Rescan failed: {e}")
                    self.send_error(500, str(e))

            elif self.path == "/api/backup":
                try:
                    # Security Fix: Ensure only authenticated/local users (implicitly local)
                    print("💾 Backup requested...")
                    
                    # Force save first to ensure latest memory state is on disk?
                    # config.save({}) # No-op save to flush? No, config.save updates logic.
                    # Just read the file.
                    
                    if os.path.exists(SETTINGS_FILE):
                        with open(SETTINGS_FILE, 'rb') as f:
                            data = f.read()
                            
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Disposition", 'attachment; filename="arcade_settings_backup.json"')
                        self.end_headers()
                        self.wfile.write(data)
                        print("✅ Backup sent.")
                    else:
                        self.send_error(404, "Settings file not found")
                        
                except Exception as e:
                    print(f"❌ Backup failed: {e}")
                    self.send_error(500, str(e))

            elif self.path.startswith("/batch_compress?paths="):
                try:
                    paths = unquote(self.path.split("paths=")[1]).split(",")
                    current_port = self.server.server_address[1]
                    
                    # Validate all paths first
                    validated_paths = []
                    for p in paths:
                        try:
                            validated_path = sanitize_path(p)
                            if os.path.exists(validated_path):
                                validated_paths.append(validated_path)
                            else:
                                print(f"⚠️ Skipping non-existent file: {validated_path}")
                        except (SecurityError, ValueError) as e:
                            print(f"🚨 Skipping invalid path in batch: {p} - {e}")
                            continue
                    
                    if not validated_paths:
                        print("❌ No valid files to process in batch")
                        self.send_response(204)
                        self.end_headers()
                        return
                    
                    # Build batch controller command
                    batch_controller_path = os.path.join(
                        os.path.dirname(config.optimizer_path), 
                        "batch_controller.py"
                    )
                    
                    # Comma-separate paths for the controller
                    files_arg = ",".join(validated_paths)
                    
                    cmd_parts = [
                        sys.executable,
                        batch_controller_path,
                        f"--files={files_arg}",
                        f"--port={current_port}"
                    ]
                    
                    if IS_WIN:
                        # Windows: Launch in new console
                        subprocess.Popen(cmd_parts, creationflags=subprocess.CREATE_NEW_CONSOLE)
                    else:
                        # macOS: Single terminal window
                        safe_cmd = ' '.join(shlex.quote(str(p)) for p in cmd_parts)
                        print(f"🚀 Launching Batch Controller: {len(validated_paths)} files")
                        applescript = f'tell application "Terminal" to do script "{safe_cmd}"'
                        subprocess.run(["osascript", "-e", applescript])
                    
                    self.send_response(204)
                    self.end_headers()
                except Exception as e:
                    print(f"❌ Error in batch_compress: {e}")
                    self.send_error(500)
            elif self.path.startswith("/hide?"):
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                state = params.get("state", ["true"])[0].lower() == "true"
                if path:
                    abs_path = os.path.abspath(path)
                    entry = db.get(abs_path)
                    if not entry:
                         # Create generic entry if not found (rare but possible)
                        entry = VideoEntry(FilePath=abs_path)
                    
                    entry.vaulted = state
                    db.upsert(entry)
                    db.save()
                    print(f"Updated vault state for: {os.path.basename(abs_path)} -> hidden={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_hide?paths="):
                paths_str = unquote(self.path.split("paths=")[1])
                paths_list = paths_str.split("&state=")[0].split(",")
                state = "state=false" not in self.path
                updated_count = 0
                for p in paths_list:
                    abs_p = os.path.abspath(p)
                    entry = db.get(abs_p)
                    if not entry:
                         entry = VideoEntry(FilePath=abs_p)
                    entry.vaulted = state
                    db.upsert(entry)
                    updated_count += 1
                db.save()
                print(f"Batch updated vault state for {updated_count} files -> hidden={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/favorite?"):
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                state = params.get("state", ["true"])[0].lower() == "true"
                if path:
                    abs_path = os.path.abspath(path)
                    entry = db.get(abs_path)
                    if not entry:
                        entry = VideoEntry(FilePath=abs_path)
                    entry.favorite = state
                    db.upsert(entry)
                    db.save()
                    print(f"Updated favorite state for: {os.path.basename(abs_path)} -> favorite={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_favorite?"):
                params = parse_qs(urlparse(self.path).query)
                paths = params.get("paths", [""])[0].split(",")
                state = params.get("state", ["true"])[0].lower() == "true"
                updated_count = 0
                for p in paths:
                    if p:
                        abs_path = os.path.abspath(p)
                        entry = db.get(abs_path)
                        if entry:
                            entry.favorite = state
                            db.upsert(entry)
                            updated_count += 1
                db.save()
                print(f"Batch updated favorite state for {updated_count} files -> favorite={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/stream?path="):
                try:
                    file_path = unquote(self.path.split("path=")[1])
                    
                    # Security Fix C-2: Prevent arbitrary file read
                    if not is_path_allowed(file_path):
                        print(f"🚨 Unauthorized stream access blocked: {file_path}")
                        self.send_error(403, "Forbidden - Path not in scan directories")
                        return
                    
                    serve_file_range(self, file_path, method="GET")
                except SecurityError as e:
                    print(f"🚨 Security violation in stream: {e}")
                    self.send_error(403, "Forbidden")
                except Exception as e:
                    print(f"❌ Error in stream endpoint: {e}")
                    self.send_error(500)

            elif self.path == "/api/settings":
                # Return current settings as JSON
                # We construct response from config.settings
                s = config.settings
                # We need to access defaults from config module constants if possible, 
                # or just hardcode/use empty for now as frontend might rely on them.
                # In config.py I defined DEFAULT_EXCLUSIONS but didn't expose them on `config` instance.
                # I can import them if I expose them in config module. 
                from arcade_scanner.config import DEFAULT_EXCLUSIONS, HOME_DIR
                
                response = {
                    "scan_targets": s.scan_targets,
                    "exclude_paths": s.exclude_paths,
                    "disabled_defaults": s.disabled_defaults,
                    "saved_views": [v for v in s.saved_views], # Pydantic model to list
                    "smart_collections": [c for c in s.smart_collections],  # Smart collections
                    "min_size_mb": s.min_size_mb,
                    "bitrate_threshold_kbps": s.bitrate_threshold_kbps,
                    "enable_fun_facts": s.enable_fun_facts,
                    "enable_optimizer": s.enable_optimizer,
                    "enable_deovr": s.enable_deovr,
                    "available_tags": s.available_tags,
                    "enable_optimizer": s.enable_optimizer,
                    "available_tags": s.available_tags,
                    "theme": s.theme,
                    "sensitive_dirs": s.sensitive_dirs,
                    "sensitive_tags": s.sensitive_tags,
                    "sensitive_collections": s.sensitive_collections,
                    "default_scan_targets": [HOME_DIR],
                    "default_exclusions": DEFAULT_EXCLUSIONS
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode("utf-8"))
            
            elif self.path == "/api/deovr/library.json":
                # iOS app library endpoint (uses simplified format)
                from arcade_scanner.core.deovr_generator import generate_ios_json
                
                # Get server URL from request
                host = self.headers.get("Host", "localhost:8000")
                protocol = "https" if self.headers.get("X-Forwarded-Proto") == "https" else "http"
                server_url = f"{protocol}://{host}"
                
                # Generate iOS-compatible JSON
                all_videos = db.get_all()
                ios_data = generate_ios_json(all_videos, server_url)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(ios_data).encode("utf-8"))
            
            elif self.path.startswith("/api/deovr/collection/"):
                # DeoVR collection endpoint
                from arcade_scanner.core.deovr_generator import generate_collection_deovr_json
                
                # Extract collection ID from path
                collection_id = self.path.split("/api/deovr/collection/")[1].replace(".json", "")
                
                # Find collection in settings
                collection = None
                for coll in config.settings.smart_collections:
                    if coll.get("id") == collection_id:
                        collection = coll
                        break
                
                if not collection:
                    self.send_error(404, "Collection not found")
                    return
                
                # Get server URL
                host = self.headers.get("Host", "localhost:8000")
                protocol = "https" if self.headers.get("X-Forwarded-Proto") == "https" else "http"
                server_url = f"{protocol}://{host}"
                
                # Generate DeoVR JSON for collection
                all_videos = db.get_all()
                deovr_data = generate_collection_deovr_json(
                    all_videos,
                    collection.get("name", collection_id),
                    collection.get("criteria", {}),
                    server_url
                )
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(deovr_data).encode("utf-8"))
            
            elif self.path == "/api/cache-stats":
                # Calculate cache sizes
                def get_dir_size(path):
                    total = 0
                    try:
                        for entry in os.scandir(path):
                            if entry.is_file():
                                total += entry.stat().st_size
                            elif entry.is_dir():
                                total += get_dir_size(entry.path)
                    except:
                        pass
                    return total
                
                thumb_size = get_dir_size(config.thumb_dir) / (1024 * 1024)  # MB
                total_size = thumb_size
                
                stats = {
                    "thumbnails_mb": round(thumb_size, 2),
                    "total_mb": round(total_size, 2)
                }
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(stats).encode("utf-8"))
            
            # --- TAG SYSTEM ENDPOINTS ---
            elif self.path == "/api/tags":
                # GET: Return all available tags
                tags = config.settings.available_tags
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(tags).encode("utf-8"))
            
            elif self.path.startswith("/api/video/tags?"):
                # GET: Return tags for a specific video
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                
                if not path:
                    self.send_error(400, "Missing path parameter")
                    return
                
                abs_path = os.path.abspath(path)
                entry = db.get(abs_path)
                
                if entry:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"tags": entry.tags}).encode("utf-8"))
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"tags": []}).encode("utf-8"))
            
            elif self.path.startswith("/api/tags?"):
                # DELETE: Remove a tag (handled in do_GET for simplicity with query params)
                # This is a workaround since we're using GET with action=delete
                params = parse_qs(urlparse(self.path).query)
                action = params.get("action", [None])[0]
                tag_name = params.get("name", [None])[0]
                
                if action == "delete" and tag_name:
                    # Remove tag from available_tags
                    current_tags = list(config.settings.available_tags)
                    updated_tags = [t for t in current_tags if t.get("name") != tag_name]
                    
                    # Also remove this tag from all videos
                    for entry in db.get_all():
                        if tag_name in entry.tags:
                            entry.tags = [t for t in entry.tags if t != tag_name]
                            db.upsert(entry)
                    db.save()
                    
                    # Save updated tags list
                    config.save({"available_tags": updated_tags})
                    
                    print(f"🏷️ Deleted tag: {tag_name}")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                else:
                    self.send_error(400, "Invalid action or missing name")
            
            else:
                # 404 for anything else
                self.send_error(404)
        except Exception as e:
            print(f"Error handling request: {e}")

    def do_HEAD(self):
        try:
            if self.path.startswith("/stream?path="):
                file_path = unquote(self.path.split("path=")[1])
                
                # Security: Validate path
                if not is_path_allowed(file_path):
                    self.send_error(403, "Forbidden")
                    return
                
                serve_file_range(self, file_path, method="HEAD")

            else:
                self.send_error(405)
        except Exception as e:
            print(f"Error handling HEAD request: {e}")

    def log_message(self, format, *args):
        return

    def do_POST(self):
        try:
            if self.path == "/api/settings":
                try:
                    # Security Fix H-2: DoS Protection - Limit request size
                    content_length = int(self.headers.get("Content-Length", 0))
                    
                    if content_length > MAX_REQUEST_SIZE:
                        print(f"🚨 Rejected oversized request: {content_length} bytes")
                        self.send_error(413, "Request Entity Too Large")
                        return
                    
                    if content_length == 0:
                        self.send_error(400, "Empty request body")
                        return
                    
                    # Read and parse JSON body
                    body = self.rfile.read(content_length).decode("utf-8")
                    new_settings = json.loads(body)
                    
                    # Type validation via Pydantic
                    from arcade_scanner.config import AppSettings
                    from pydantic import ValidationError
                    
                    # Validate structure before applying
                    try:
                        validated = AppSettings(**new_settings)
                    except ValidationError as e:
                        print(f"🚨 Settings validation failed: {e}")
                        self.send_error(400, f"Invalid settings: {e}")
                        return
                    
                    # Update with validated values
                    update_data = {
                        "scan_targets": new_settings.get("scan_targets", []),
                        "exclude_paths": new_settings.get("exclude_paths", []),
                        "disabled_defaults": new_settings.get("disabled_defaults", []),
                        "saved_views": new_settings.get("saved_views", config.settings.saved_views),
                        "smart_collections": new_settings.get("smart_collections", config.settings.smart_collections),
                        "min_size_mb": new_settings.get("min_size_mb", 100),
                        "bitrate_threshold_kbps": new_settings.get("bitrate_threshold_kbps", 15000),
                        "enable_fun_facts": new_settings.get("enable_fun_facts", True),
                        "enable_optimizer": new_settings.get("enable_optimizer", True),
                        "enable_deovr": new_settings.get("enable_deovr", False),
                        "available_tags": new_settings.get("available_tags", config.settings.available_tags),
                        "theme": new_settings.get("theme", config.settings.theme),
                        "sensitive_dirs": new_settings.get("sensitive_dirs", []),
                        "sensitive_tags": new_settings.get("sensitive_tags", []),
                        "sensitive_collections": new_settings.get("sensitive_collections", [])
                    }
                    
                    if config.save(update_data):
                        print(f"✅ Settings saved: {len(update_data['scan_targets'])} targets, {len(update_data['exclude_paths'])} excludes")
                        
                        # Regenerate HTML report to bake in new settings (Theme, etc.)
                        try:
                            current_port = self.server.server_address[1]
                            results = [e.model_dump(by_alias=True) for e in db.get_all()]
                            generate_html_report(results, config.report_file, server_port=current_port)
                            print("✅ HTML Report regenerated with new settings")
                        except Exception as e:
                            print(f"⚠️ Settings saved but report gen failed: {e}")

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                    else:
                        self.send_response(500)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": False, "error": "Failed to save"}).encode("utf-8"))
                
                except json.JSONDecodeError as e:
                    print(f"🚨 Invalid JSON in settings POST: {e}")
                    self.send_error(400, "Invalid JSON")
                except Exception as e:
                    print(f"❌ Error saving settings: {e}")
                    self.send_error(500, str(e))
            
            elif self.path == "/api/restore":
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    
                    if content_length > MAX_REQUEST_SIZE:
                        self.send_error(413, "Request Entity Too Large")
                        return

                    body = self.rfile.read(content_length).decode('utf-8')
                    try:
                        # Expecting pure JSON body (client parses file and sends JSON)
                        new_settings = json.loads(body)
                    except json.JSONDecodeError:
                        self.send_error(400, "Invalid JSON format")
                        return
                    
                    print("♻️ Restoring settings from backup...")
                    
                    if config.save(new_settings):
                        print("✅ Settings restored successfully.")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": True}).encode())
                    else:
                        print("❌ Failed to save restored settings.")
                        self.send_error(500, "Failed to save settings")
                        
                except Exception as e:
                    print(f"❌ Restore exception: {e}")
                    self.send_error(500, str(e))
            
            # --- TAG SYSTEM POST ENDPOINTS ---
            elif self.path == "/api/tags":
                # POST: Create a new tag
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > MAX_REQUEST_SIZE:
                        self.send_error(413, "Request Entity Too Large")
                        return
                    if content_length == 0:
                        self.send_error(400, "Empty request body")
                        return
                    
                    body = self.rfile.read(content_length).decode("utf-8")
                    data = json.loads(body)
                    
                    tag_name = data.get("name", "").strip()
                    tag_color = data.get("color", "#00ffd0")  # Default cyan
                    
                    if not tag_name:
                        self.send_error(400, "Tag name is required")
                        return
                    
                    # Check if tag already exists
                    current_tags = list(config.settings.available_tags)
                    existing_names = [t.get("name", "").lower() for t in current_tags]
                    
                    if tag_name.lower() in existing_names:
                        self.send_error(409, "Tag already exists")
                        return
                    
                    # Add new tag
                    new_tag = {"name": tag_name, "color": tag_color}
                    current_tags.append(new_tag)
                    config.save({"available_tags": current_tags})
                    
                    print(f"🏷️ Created tag: {tag_name} ({tag_color})")
                    self.send_response(201)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(new_tag).encode("utf-8"))
                    
                except json.JSONDecodeError:
                    self.send_error(400, "Invalid JSON")
                except Exception as e:
                    print(f"❌ Error creating tag: {e}")
                    self.send_error(500, str(e))
            
            elif self.path.startswith("/api/video/tags"):
                # POST: Set tags for a video
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > MAX_REQUEST_SIZE:
                        self.send_error(413, "Request Entity Too Large")
                        return
                    
                    body = self.rfile.read(content_length).decode("utf-8")
                    data = json.loads(body)
                    
                    video_path = data.get("path")
                    tags = data.get("tags", [])
                    
                    if not video_path:
                        self.send_error(400, "Video path is required")
                        return
                    
                    abs_path = os.path.abspath(video_path)
                    entry = db.get(abs_path)
                    
                    if not entry:
                        # Create minimal entry if not found
                        from arcade_scanner.models.video_entry import VideoEntry
                        entry = VideoEntry(FilePath=abs_path, Size_MB=0)
                    
                    # Validate tags exist in available_tags
                    available_tag_names = [t.get("name") for t in config.settings.available_tags]
                    valid_tags = [t for t in tags if t in available_tag_names]
                    
                    entry.tags = valid_tags
                    db.upsert(entry)
                    db.save()
                    
                    print(f"🏷️ Updated tags for {os.path.basename(abs_path)}: {valid_tags}")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"tags": valid_tags}).encode("utf-8"))
                    
                except json.JSONDecodeError:
                    self.send_error(400, "Invalid JSON")
                except Exception as e:
                    print(f"❌ Error setting video tags: {e}")
                    self.send_error(500, str(e))
            
            else:
                self.send_error(404)
        except Exception as e:
            print(f"Error handling POST request: {e}")
            self.send_response(500)
            self.end_headers()
