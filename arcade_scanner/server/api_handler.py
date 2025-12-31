import http.server
import os
import subprocess
import mimetypes
import sys
import time
import json
from pathlib import Path
import socket
from urllib.parse import unquote, urlparse, parse_qs
import shlex
from arcade_scanner.config import config, IS_WIN, MAX_REQUEST_SIZE, ALLOWED_THUMBNAIL_PREFIX
from arcade_scanner.database import db
from arcade_scanner.scanner import get_scanner_manager
from arcade_scanner.server.streaming_util import serve_file_range
from arcade_scanner.templates.dashboard_template import generate_html_report
from arcade_scanner.security import sanitize_path, is_path_allowed, validate_filename, is_safe_directory_traversal, SecurityError

class FinderHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            # 1. ROOT / INDEX -> Serve REPORT_FILE
            spa_routes = ["/", "/index.html", "/lobby", "/favorites", "/review", "/vault", "/treeview"]
            if self.path in spa_routes or self.path.startswith("/index.html?"):
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
                        results = list(c.values())
                        generate_html_report(results, REPORT_FILE, server_port=current_port)
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
                    ss = params.get("ss", [None])[0]
                    to = params.get("to", [None])[0]
                    
                    # Validate audio_mode (whitelist)
                    if audio_mode not in ["enhanced", "standard"]:
                        print(f"🚨 Invalid audio mode: {audio_mode}")
                        self.send_error(400, "Invalid audio mode")
                        return
                    
                    # Get current running port
                    current_port = self.server.server_address[1]
                    print(f"🔌 Current Server Port: {current_port}")
                    print(f"⚡ Optimize: {file_path} | Audio: {audio_mode} | Trim: {ss}-{to}")
                    
                    # Load latest settings to check fun facts preference
                    enable_fun_facts = config.settings.enable_fun_facts

                    # Build command as list (NEVER use shell=True!)
                    cmd_parts = [sys.executable, config.optimizer_path, file_path,
                                 "--port", str(current_port),
                                 "--audio-mode", audio_mode]
                    
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

            elif self.path.startswith("/batch_compress?paths="):
                try:
                    paths = unquote(self.path.split("paths=")[1]).split(",")
                    current_port = self.server.server_address[1]
                    
                    for p in paths:
                        # Security: Validate each path
                        try:
                            validated_path = sanitize_path(p)
                        except (SecurityError, ValueError) as e:
                            print(f"🚨 Skipping invalid path in batch: {p} - {e}")
                            continue
                        
                        if not os.path.exists(validated_path):
                            print(f"⚠️ Skipping non-existent file: {validated_path}")
                            continue
                        
                        # Build safe command
                        cmd_parts = [sys.executable, config.optimizer_path, validated_path,
                                     "--port", str(current_port)]
                        
                        if IS_WIN:
                            subprocess.Popen(cmd_parts, creationflags=subprocess.CREATE_NEW_CONSOLE)
                        else:
                            safe_cmd = ' '.join(shlex.quote(str(p)) for p in cmd_parts)
                            applescript = f'tell application "Terminal" to do script "{safe_cmd}"'
                            subprocess.run(["osascript", "-e", applescript])
                        
                        time.sleep(1)  # Avoid overwhelming the system
                    
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
                    
                    entry.hidden = state
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
                    entry.hidden = state
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
            elif self.path.startswith("/preview?name="):
                try:
                    name = unquote(self.path.split("name=")[1])
                    
                    # Security: Validate filename pattern
                    from arcade_scanner.config import ALLOWED_PREVIEW_PREFIX
                    if not validate_filename(name, prefix=ALLOWED_PREVIEW_PREFIX, suffix=".mp4"):
                        print(f"🚨 Invalid preview name: {name}")
                        self.send_error(400, "Invalid preview name")
                        return
                    
                    prev_path = os.path.join(config.preview_dir, name)
                    
                    # Additional check: Ensure path stays in preview_dir
                    if not is_safe_directory_traversal(config.preview_dir, prev_path):
                        self.send_error(403, "Forbidden")
                        return
                    
                    serve_file_range(self, prev_path, method="GET")
                except SecurityError as e:
                    print(f"🚨 Security violation in preview: {e}")
                    self.send_error(403, "Forbidden")
                except Exception as e:
                    print(f"❌ Error in preview endpoint: {e}")
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
                    "min_size_mb": s.min_size_mb,
                    "bitrate_threshold_kbps": s.bitrate_threshold_kbps,
                    "enable_previews": s.enable_previews,
                    "enable_fun_facts": s.enable_fun_facts,
                    "enable_optimizer": s.enable_optimizer,
                    "default_scan_targets": [HOME_DIR],
                    "default_exclusions": DEFAULT_EXCLUSIONS
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode("utf-8"))
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
                preview_size = get_dir_size(config.preview_dir) / (1024 * 1024)  # MB
                total_size = thumb_size + preview_size
                
                stats = {
                    "thumbnails_mb": round(thumb_size, 2),
                    "previews_mb": round(preview_size, 2),
                    "total_mb": round(total_size, 2)
                }
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(stats).encode("utf-8"))
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
            elif self.path.startswith("/preview?name="):
                name = unquote(self.path.split("name=")[1])
                
                # Security: Validate filename pattern
                from arcade_scanner.config import ALLOWED_PREVIEW_PREFIX
                if not validate_filename(name, prefix=ALLOWED_PREVIEW_PREFIX, suffix=".mp4"):
                    print(f"🚨 Invalid preview name: {name}")
                    self.send_error(400, "Invalid preview name")
                    return
                
                prev_path = os.path.join(config.preview_dir, name)
                
                # Additional check: Ensure path stays in preview_dir
                if not is_safe_directory_traversal(config.preview_dir, prev_path):
                    self.send_error(403, "Forbidden")
                    return
                
                serve_file_range(self, prev_path, method="HEAD")
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
                        "saved_views": new_settings.get("saved_views", []),
                        "min_size_mb": new_settings.get("min_size_mb", 100),
                        "bitrate_threshold_kbps": new_settings.get("bitrate_threshold_kbps", 15000),
                        "enable_previews": new_settings.get("enable_previews", False),
                        "enable_fun_facts": new_settings.get("enable_fun_facts", True),
                        "enable_optimizer": new_settings.get("enable_optimizer", True)
                    }
                    
                    if config.save(update_data):
                        print(f"✅ Settings saved: {len(update_data['scan_targets'])} targets, {len(update_data['exclude_paths'])} excludes")
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
            else:
                self.send_error(404)
        except Exception as e:
            print(f"Error handling POST request: {e}")
            self.send_response(500)
            self.end_headers()
