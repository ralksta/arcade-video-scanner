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
from arcade_scanner.database import db, user_db
from arcade_scanner.security import session_manager
from http.cookies import SimpleCookie
from arcade_scanner.scanner import get_scanner_manager
from arcade_scanner.server.streaming_util import serve_file_range
from arcade_scanner.templates.dashboard_template import generate_html_report
from arcade_scanner.security import sanitize_path, is_path_allowed, validate_filename, is_safe_directory_traversal, SecurityError

class FinderHandler(http.server.SimpleHTTPRequestHandler):
    def get_current_user(self):
        """Returns the username from the session cookie, or None."""
        if "Cookie" in self.headers:
            cookie = SimpleCookie(self.headers["Cookie"])
            if "session_token" in cookie:
                return session_manager.get_username(cookie["session_token"].value)
        return None


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
                
                # AUTH CHECK for Root
                user = self.get_current_user()
                if not user:
                    # Serve Login Page
                    login_path = os.path.join(os.path.dirname(__file__), "static", "login.html")
                    if os.path.exists(login_path):
                        self.send_response(200)
                        self.send_header("Content-type", "text/html; charset=utf-8")
                        with open(login_path, 'rb') as f:
                            data = f.read()
                            self.send_header("Content-Length", str(len(data)))
                            self.end_headers()
                            self.wfile.write(data)
                        return
                    else:
                        self.send_error(404, "Login page not found")
                        return

                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                
                if os.path.exists(config.report_file):
                    fs = os.stat(config.report_file)
                    self.send_header("Content-Length", str(fs.st_size))
                    self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                    # Add User Header for debug
                    self.send_header("X-Arcade-User", user)
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
            elif self.path == "/api/user/data":
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return
                
                u = user_db.get_user(user_name)
                if u:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(u.data.model_dump_json().encode())
                else:
                     self.send_error(404, "User not found")
                return
            
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
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return

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
                    q_val = params.get("q", [None])[0]
                    ss = params.get("ss", [None])[0]  # Trim start time
                    to = params.get("to", [None])[0]  # Trim end time
                    
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
                    print(f"⚡ Optimize: {file_path} | Video: {video_mode} | Audio: {audio_mode} | Q: {q_val} | Trim: {ss}-{to}")
                    
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
                    if q_val:
                         cmd_parts.extend(["--q", q_val])
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
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return

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
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return

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
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return

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
                    user_name = self.get_current_user()
                    if not user_name:
                        self.send_error(401, "Unauthorized")
                        return

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
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return

                try:
                    # Use ||| as separator to avoid issues with commas in filenames
                    paths = unquote(self.path.split("paths=")[1]).split("|||")
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
                        # Escape backslashes and quotes for AppleScript string
                        escaped_cmd = safe_cmd.replace('\\', '\\\\').replace('"', '\\"')
                        applescript = f'tell application "Terminal" to do script "{escaped_cmd}"'
                        subprocess.run(["osascript", "-e", applescript])
                    
                    self.send_response(204)
                    self.end_headers()
                except Exception as e:
                    print(f"❌ Error in batch_compress: {e}")
                    self.send_error(500)
            elif self.path.startswith("/hide?"):
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                state = params.get("state", ["true"])[0].lower() == "true"
                
                if path:
                    abs_path = os.path.abspath(path)
                    u = user_db.get_user(user_name)
                    if u:
                        if state:
                            if abs_path not in u.data.vaulted:
                                u.data.vaulted.append(abs_path)
                        else:
                            if abs_path in u.data.vaulted:
                                u.data.vaulted.remove(abs_path)
                        user_db.add_user(u)
                        print(f"Updated vault state for {user_name}: {os.path.basename(abs_path)} -> hidden={state}")
                    
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_hide?paths="):
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                    
                paths_str = unquote(self.path.split("paths=")[1])
                paths_list = paths_str.split("&state=")[0].split(",")
                state = "state=false" not in self.path
                
                u = user_db.get_user(user_name)
                if u:
                    updated_count = 0
                    for p in paths_list:
                        abs_p = os.path.abspath(p)
                        if state:
                            if abs_p not in u.data.vaulted:
                                u.data.vaulted.append(abs_p)
                                updated_count += 1
                        else:
                            if abs_p in u.data.vaulted:
                                u.data.vaulted.remove(abs_p)
                                updated_count += 1
                    user_db.add_user(u)
                    print(f"Batch updated vault state for {user_name} ({updated_count} files) -> hidden={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/favorite?"):
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                    
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                state = params.get("state", ["true"])[0].lower() == "true"
                if path:
                    abs_path = os.path.abspath(path)
                    u = user_db.get_user(user_name)
                    if u:
                        if state:
                            if abs_path not in u.data.favorites:
                                u.data.favorites.append(abs_path)
                        else:
                            if abs_path in u.data.favorites:
                                u.data.favorites.remove(abs_path)
                        user_db.add_user(u)
                        print(f"Updated favorite state for {user_name}: {os.path.basename(abs_path)} -> favorite={state}")
                        
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_favorite?"):
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                
                params = parse_qs(urlparse(self.path).query)
                paths = params.get("paths", [""])[0].split(",")
                state = params.get("state", ["true"])[0].lower() == "true"
                
                u = user_db.get_user(user_name)
                if u:
                    updated_count = 0
                    for p in paths:
                        if p:
                            abs_path = os.path.abspath(p)
                            if state:
                                if abs_path not in u.data.favorites:
                                    u.data.favorites.append(abs_path)
                                    updated_count += 1
                            else:
                                if abs_path in u.data.favorites:
                                    u.data.favorites.remove(abs_path)
                                    updated_count += 1
                    user_db.add_user(u)
                    print(f"Batch updated favorite state for {user_name} ({updated_count} files) -> favorite={state}")
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

                # GET Settings
                # Interceptor: Inject user-specific smart_collections into the response
                settings_dump = config.settings.model_dump()
                
                user_name = self.get_current_user()
                if user_name:
                    u = user_db.get_user(user_name)
                    if u:
                        settings_dump["smart_collections"] = u.data.smart_collections
                        settings_dump["scan_targets"] = u.data.scan_targets
                        settings_dump["exclude_paths"] = u.data.exclude_paths
                        settings_dump["available_tags"] = u.data.available_tags
                        
                        # Inject User-Specific Settings
                        settings_dump["scan_images"] = u.data.scan_images
                        settings_dump["sensitive_dirs"] = u.data.sensitive_dirs
                        settings_dump["sensitive_tags"] = u.data.sensitive_tags
                        settings_dump["sensitive_collections"] = u.data.sensitive_collections
                    else:
                        settings_dump["smart_collections"] = []
                        settings_dump["scan_targets"] = []
                        settings_dump["exclude_paths"] = []
                        settings_dump["available_tags"] = []
                else:
                    settings_dump["smart_collections"] = []
                    settings_dump["scan_targets"] = []
                    settings_dump["exclude_paths"] = []
                    settings_dump["available_tags"] = []

                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(settings_dump, default=str).encode())
                return
            
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
                # GET: Return all available tags from User data
                user_name = self.get_current_user()
                if not user_name:
                    # Return empty if not auth? Or return default global?
                    # For now, require auth.
                    self.send_error(401)
                    return

                u = user_db.get_user(user_name)
                tags = u.data.available_tags if u else []
                
                print(f"DEBUG: GET /api/tags returning: {tags}", flush=True)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(tags).encode("utf-8"))
            
            elif self.path == "/api/videos":
                # GET: Return all videos, filtered by user's scan targets
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                
                u = user_db.get_user(user_name)
                if not u:
                    self.send_error(401)
                    return
                
                # Filter videos
                all_videos = [e.model_dump(by_alias=True) for e in db.get_all()]
                user_targets = [os.path.abspath(t) for t in u.data.scan_targets if t]
                
                # If user has no targets, they see nothing (or maybe we allow strict isolation?)
                # If user is admin? Admin typically sees all? 
                # Request was "include and excludes already different for every user?".
                # Implies users only see what they define.
                
                filtered_videos = []
                # ADMIN OVERRIDE: If no targets defined, Admin sees all.
                if not user_targets and u.is_admin:
                    filtered_videos = all_videos
                elif user_targets:
                    for v in all_videos:
                        v_path = os.path.abspath(v["FilePath"])
                        if any(v_path.startswith(t) for t in user_targets):
                             filtered_videos.append(v)
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(filtered_videos, default=str).encode("utf-8"))
            
            elif self.path.startswith("/api/video/tags?"):
                # GET: Return tags for a specific video
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                
                if not path:
                    self.send_error(400, "Missing path parameter")
                    return
                
                abs_path = os.path.abspath(path)
                u = user_db.get_user(user_name)
                tags = []
                if u and abs_path in u.data.tags:
                    tags = u.data.tags[abs_path]
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"tags": tags}).encode("utf-8"))
            
            elif self.path.startswith("/api/tags?"):
                # DELETE: Remove a tag (handled in do_GET for simplicity with query params)
                # Auth Check
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                # Admin check? Or anyone can delete global tags? 
                # Let's restrict to implicit admin (authenticated) for now.
                
                params = parse_qs(urlparse(self.path).query)
                action = params.get("action", [None])[0]
                tag_name = params.get("name", [None])[0]
                
                if action == "delete" and tag_name:
                    # Remove tag from USER's available_tags
                    u = user_db.get_user(user_name)
                    if u:
                        current_tags = list(u.data.available_tags)
                        updated_tags = [t for t in current_tags if t.get("name") != tag_name]
                        u.data.available_tags = updated_tags
                        
                        # Remove this tag from this User's video data as well?
                        # Usually yes, if we delete the definition.
                        modified = False
                        for path, tags in u.data.tags.items():
                            if tag_name in tags:
                                u.data.tags[path] = [t for t in tags if t != tag_name]
                                modified = True
                        
                        user_db.add_user(u)
                    
                    print(f"🏷️ Deleted tag for user {user_name}: {tag_name}")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                else:
                    self.send_error(400, "Invalid action or missing name")
            
            # ================================================================
            # DUPLICATE DETECTION API
            # ================================================================
            elif self.path == "/api/duplicates" or self.path == "/api/duplicates/":
                # GET: Find and return all duplicate groups
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return
                
                try:
                    from arcade_scanner.core.duplicate_detector import duplicate_detector
                    
                    # Get all media entries
                    all_entries = db.get_all()
                    
                    # Find duplicates
                    groups = duplicate_detector.find_all_duplicates(all_entries)
                    
                    # Calculate summary stats
                    total_groups = len(groups)
                    total_savings = sum(g.potential_savings_mb for g in groups)
                    video_groups = len([g for g in groups if g.media_type == "video"])
                    image_groups = len([g for g in groups if g.media_type == "image"])
                    
                    response = {
                        "groups": [g.to_dict() for g in groups],
                        "summary": {
                            "total_groups": total_groups,
                            "video_groups": video_groups,
                            "image_groups": image_groups,
                            "potential_savings_mb": round(total_savings, 2),
                            "potential_savings_gb": round(total_savings / 1024, 2),
                        }
                    }
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode("utf-8"))
                    print(f"🔍 Duplicate scan: {total_groups} groups, {total_savings:.1f} MB potential savings")
                    
                except Exception as e:
                    print(f"❌ Error in duplicate detection: {e}")
                    import traceback
                    traceback.print_exc()
                    self.send_error(500, str(e))
            
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


    def do_POST(self):
        print(f"DEBUG: POST Request received for path: {self.path}", flush=True)

        try:
            if self.path.startswith("/api/login"):
                content_len = int(self.headers.get('Content-Length', 0))
                post_body = self.rfile.read(content_len)
                try:
                    data = json.loads(post_body)
                    username = data.get("username")
                    password = data.get("password")
                    
                    # Check auth
                    username = username.strip() if username else ""
                    # password = password.strip() if password else "" # Passwords might have spaces

                    print(f"LOGIN DEBUG: Attempting login for user: '{username}'", flush=True)
                    
                    u = user_db.get_user(username)
                    if u:
                        print(f"LOGIN DEBUG: User found in DB. Salt: {u.salt}", flush=True)
                    else:
                        print(f"LOGIN DEBUG: User '{username}' NOT found", flush=True)

                    is_valid = user_db.verify_password(username, password)
                    print(f"LOGIN DEBUG: verify_password result: {is_valid}", flush=True)
                    
                    if is_valid:
                        token = session_manager.create_session(username)
                        
                        self.send_response(200)
                        cookie = SimpleCookie()
                        cookie["session_token"] = token
                        cookie["session_token"]["path"] = "/"
                        cookie["session_token"]["httponly"] = True
                        cookie["session_token"]["max-age"] = 86400 * 30
                        
                        for morsel in cookie.values():
                            self.send_header("Set-Cookie", morsel.OutputString())
                        
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": True}).encode())
                    else:
                        self.send_error(401, "Invalid credentials")
                        
                except Exception as e:
                    print(f"Login error: {e}")
                    self.send_error(400)
                return

            elif self.path == "/api/logout":
                if "Cookie" in self.headers:
                    cookie = SimpleCookie(self.headers["Cookie"])
                    if "session_token" in cookie:
                        session_manager.revoke_session(cookie["session_token"].value)
                
                self.send_response(200)
                cookie = SimpleCookie()
                cookie["session_token"] = ""
                cookie["session_token"]["path"] = "/"
                cookie["session_token"]["expires"] = "Thu, 01 Jan 1970 00:00:00 GMT"
                for morsel in cookie.values():
                    self.send_header("Set-Cookie", morsel.OutputString())
                self.end_headers()
                return

            if self.path == "/api/settings":
                try:
                    # Security Fix H-2: DoS Protection - Limit request size
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > MAX_REQUEST_SIZE:
                        self.send_error(413, "Request payload too large")
                        return

                    post_body = self.rfile.read(content_length)
                    new_settings = json.loads(post_body)
                    
                    # Interceptor: Extract smart_collections for user_db
                    # Interceptor: Extract smart_collections for user_db
                    user_collections = new_settings.pop("smart_collections", None)
                    user_targets = new_settings.pop("scan_targets", None)
                    user_excludes = new_settings.pop("exclude_paths", None)
                    user_tags = new_settings.pop("available_tags", None)
                    
                    # New User-Specific Settings
                    user_scan_images = new_settings.pop("scan_images", None)
                    user_sensitive_dirs = new_settings.pop("sensitive_dirs", None)
                    user_sensitive_tags = new_settings.pop("sensitive_tags", None)
                    user_sensitive_collections = new_settings.pop("sensitive_collections", None)
                    
                    if config.save(new_settings):
                        # Save user collections if present
                        user_name = self.get_current_user()
                        if user_name:
                            u = user_db.get_user(user_name)
                            if u:
                                modified = False
                                if user_collections is not None:
                                    u.data.smart_collections = user_collections
                                    modified = True
                                if user_targets is not None:
                                    u.data.scan_targets = user_targets
                                    modified = True
                                if user_excludes is not None:
                                    u.data.exclude_paths = user_excludes
                                    modified = True
                                if user_tags is not None:
                                    u.data.available_tags = user_tags
                                    modified = True
                                
                                if user_scan_images is not None:
                                    u.data.scan_images = user_scan_images
                                    modified = True
                                    
                                if user_sensitive_dirs is not None:
                                    u.data.sensitive_dirs = user_sensitive_dirs
                                    modified = True
                                if user_sensitive_tags is not None:
                                    u.data.sensitive_tags = user_sensitive_tags
                                    modified = True
                                if user_sensitive_collections is not None:
                                    u.data.sensitive_collections = user_sensitive_collections
                                    modified = True
                                
                                if modified:
                                    user_db.add_user(u)

                        # Regenerate HTML report to bake in new settings (Theme, etc.)
                        try:
                            # We need to import db to get results
                            # results = [e.model_dump(by_alias=True) for e in db.get_all()]
                            # But simple way is to rely on scanner manager or just trigger a re-render if possible.
                            # Actually, we can just fetch db here since it's imported.
                            results = [e.model_dump(by_alias=True) for e in db.get_all()]
                            current_port = config.PORT if hasattr(config, 'PORT') else 8000
                            # generate_html_report is imported
                            generate_html_report(results, config.report_file, server_port=current_port)
                            print("✅ HTML Report regenerated with new settings")
                        except Exception as e:
                            print(f"⚠️ Settings saved but report gen failed: {e}")

                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                    else:
                        self.send_error(500, "Failed to save settings")
                except Exception as e:
                    print(f"Error saving settings: {e}")
                    self.send_error(500)
                return
            
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
                    
                    # Auth Check
                    user_name = self.get_current_user()
                    if not user_name:
                        self.send_error(401, "Unauthorized")
                        return

                    u = user_db.get_user(user_name)
                    if not u:
                        self.send_error(404, "User not found")
                        return

                    # Check if tag already exists
                    current_tags = u.data.available_tags
                    existing_names = [t.get("name", "").lower() for t in current_tags]
                    
                    if tag_name.lower() in existing_names:
                        self.send_error(409, "Tag already exists")
                        return
                    
                    # Add new tag
                    new_tag = {"name": tag_name, "color": tag_color}
                    u.data.available_tags.append(new_tag)
                    user_db.add_user(u)
                    
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
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                
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
                         self.send_error(400, "Path required")
                         return

                    abs_path = os.path.abspath(video_path)
                    u = user_db.get_user(user_name)
                    if u:
                        u.data.tags[abs_path] = tags
                        user_db.add_user(u)
                        print(f"Updated tags for {user_name} on {os.path.basename(abs_path)}: {tags}")
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "tags": tags}).encode("utf-8"))
                except Exception as e:
                    print(f"Error setting tags: {e}")
                    self.send_error(500, str(e))
            
            # ================================================================
            # DUPLICATE DETECTION - DELETE FILES
            # ================================================================
            elif self.path == "/api/duplicates/delete":
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return
                
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > MAX_REQUEST_SIZE:
                        self.send_error(413, "Request too large")
                        return
                    
                    body = self.rfile.read(content_length).decode("utf-8")
                    data = json.loads(body)
                    
                    paths_to_delete = data.get("paths", [])
                    
                    if not paths_to_delete:
                        self.send_error(400, "No paths provided")
                        return
                    
                    deleted = []
                    failed = []
                    total_freed_mb = 0.0
                    
                    for path in paths_to_delete:
                        try:
                            abs_path = os.path.abspath(path)
                            
                            # Security check
                            if not is_path_allowed(abs_path):
                                failed.append({"path": path, "error": "Path not allowed"})
                                continue
                            
                            if os.path.exists(abs_path):
                                # Get size before deletion
                                size_mb = os.path.getsize(abs_path) / (1024 * 1024)
                                
                                # Delete file
                                os.remove(abs_path)
                                
                                # Remove from database
                                db.remove(abs_path)
                                
                                deleted.append(abs_path)
                                total_freed_mb += size_mb
                                print(f"🗑️ Deleted duplicate: {os.path.basename(abs_path)} ({size_mb:.1f} MB)")
                            else:
                                failed.append({"path": path, "error": "File not found"})
                                
                        except Exception as e:
                            failed.append({"path": path, "error": str(e)})
                    
                    # Save database changes
                    if deleted:
                        db.save()
                    
                    response = {
                        "success": True,
                        "deleted": deleted,
                        "failed": failed,
                        "freed_mb": round(total_freed_mb, 2),
                        "freed_gb": round(total_freed_mb / 1024, 2),
                    }
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode("utf-8"))
                    print(f"✅ Deleted {len(deleted)} duplicates, freed {total_freed_mb:.1f} MB")
                    
                except json.JSONDecodeError:
                    self.send_error(400, "Invalid JSON")
                except Exception as e:
                    print(f"❌ Error deleting duplicates: {e}")
                    self.send_error(500, str(e))
            
            else:
                self.send_error(404)
        except Exception as e:
            print(f"Error handling POST request: {e}")
            self.send_response(500)
            self.end_headers()
