import http.server
import os
import subprocess
import mimetypes
import sys
import time
import json
import threading
from pathlib import Path
import socket
import ssl
from urllib.parse import unquote, urlparse, parse_qs
import shlex
import tempfile
from arcade_scanner.config import config, IS_WIN, MAX_REQUEST_SIZE, ALLOWED_THUMBNAIL_PREFIX, SETTINGS_FILE, DUPLICATES_CACHE_FILE
from arcade_scanner.database import db, user_db
from arcade_scanner.security import session_manager
from http.cookies import SimpleCookie
from arcade_scanner.scanner import get_scanner_manager
from arcade_scanner.server.streaming_util import serve_file_range
from arcade_scanner.templates.dashboard_template import generate_html_report
from arcade_scanner.security import sanitize_path, is_path_allowed, validate_filename, is_safe_directory_traversal, SecurityError

# Global state for duplicate scanning
DUPLICATE_SCAN_STATE = {
    "is_running": False,
    "progress": 0,
    "message": "",
}
DUPLICATE_RESULTS_CACHE = None

class ReportDebouncer:
    def __init__(self, delay=1.0):
        self.delay = delay
        self._timer = None
        self._lock = threading.Lock()

    def schedule(self, port):
        with self._lock:
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(self.delay, self._generate, args=[port])
            self._timer.daemon = True
            self._timer.start()

    def _generate(self, port):
        try:
            # Re-fetch results to ensure freshness
            results = [e.model_dump(by_alias=True) for e in db.get_all()]
            generate_html_report(results, config.report_file, server_port=port)
            # print(f"✅ HTML Report regenerated (debounced)")
        except Exception as e:
            print(f"⚠️ Report generation failed: {e}")

report_debouncer = ReportDebouncer(delay=1.0)

def load_duplicate_cache():
    """Load cached duplicate results from disk."""
    global DUPLICATE_RESULTS_CACHE
    try:
        if os.path.exists(DUPLICATES_CACHE_FILE):
            with open(DUPLICATES_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                DUPLICATE_RESULTS_CACHE = data.get('groups', [])
                print(f"✅ Loaded {len(DUPLICATE_RESULTS_CACHE)} duplicate groups from cache")
                return True
    except Exception as e:
        print(f"⚠️ Could not load duplicate cache: {e}")
    return False

def save_duplicate_cache():
    """Save duplicate results to disk."""
    try:
        if DUPLICATE_RESULTS_CACHE is not None:
            cache_data = {
                'groups': DUPLICATE_RESULTS_CACHE,
                'timestamp': time.time()
            }
            with open(DUPLICATES_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
            print(f"✅ Saved {len(DUPLICATE_RESULTS_CACHE)} duplicate groups to cache")
    except Exception as e:
        print(f"⚠️ Could not save duplicate cache: {e}")

def clear_duplicate_cache():
    """Clear the duplicate cache from memory and disk."""
    global DUPLICATE_RESULTS_CACHE
    DUPLICATE_RESULTS_CACHE = None
    try:
        if os.path.exists(DUPLICATES_CACHE_FILE):
            os.remove(DUPLICATES_CACHE_FILE)
            print("🗑️ Cleared duplicate cache")
    except Exception as e:
        print(f"⚠️ Could not remove duplicate cache file: {e}")

def background_duplicate_scan(user_scan_targets=None, batch_offset: int = 0):
    """Background worker for duplicate detection.

    Args:
        user_scan_targets: Optional list of absolute paths to filter files by user's scan targets.
                          If None, scans all files in database.
        batch_offset: Starting offset for image batching (default 0 = first batch)
    """
    global DUPLICATE_RESULTS_CACHE
    from arcade_scanner.core.duplicate_detector import DuplicateDetector
    import threading

    DUPLICATE_SCAN_STATE["is_running"] = True
    DUPLICATE_SCAN_STATE["progress"] = 0
    DUPLICATE_SCAN_STATE["message"] = "Initializing scan..."
    DUPLICATE_SCAN_STATE["has_more"] = False
    DUPLICATE_SCAN_STATE["batch_offset"] = batch_offset

    try:
        def progress_cb(msg, pct):
            DUPLICATE_SCAN_STATE["message"] = msg
            DUPLICATE_SCAN_STATE["progress"] = int(pct)

        detector = DuplicateDetector()
        # Get all videos (thread-safe enough for read)
        all_videos = db.get_all()
        print(f"🔍 Duplicate scan: {len(all_videos)} total files in database")

        # Filter by user's scan targets if provided
        if user_scan_targets:
            all_videos = [v for v in all_videos
                         if any(os.path.abspath(v.file_path).startswith(t) for t in user_scan_targets)]
            print(f"🔍 After user filter: {len(all_videos)} files match scan targets")

        # Count by media type
        videos = [v for v in all_videos if getattr(v, 'media_type', 'video') == 'video']
        images = [v for v in all_videos if getattr(v, 'media_type', 'video') == 'image']
        print(f"🔍 Scanning {len(videos)} videos + {len(images)} images (batch offset: {batch_offset})")

        results, has_more = detector.find_all_duplicates(all_videos, progress_cb, batch_offset=batch_offset)
        print(f"🔍 Found {len(results)} duplicate groups (has_more: {has_more})")

        # Serialize results slightly earlier to avoid main thread blocking later
        DUPLICATE_RESULTS_CACHE = [g.to_dict() for g in results]
        DUPLICATE_SCAN_STATE["has_more"] = has_more
        DUPLICATE_SCAN_STATE["next_offset"] = batch_offset + 5000 if has_more else 0

        # Save to disk for future sessions
        save_duplicate_cache()

        DUPLICATE_SCAN_STATE["message"] = "Scan complete" + (" - more batches available" if has_more else "")
        DUPLICATE_SCAN_STATE["progress"] = 100

    except Exception as e:
        print(f"❌ Error in duplicate scan: {e}")
        DUPLICATE_SCAN_STATE["message"] = f"Error: {e}"
    finally:
        DUPLICATE_SCAN_STATE["is_running"] = False


class FinderHandler(http.server.SimpleHTTPRequestHandler):
    # Suppress logging for noisy polling endpoints
    QUIET_PATHS = {"/api/duplicates/status"}

    def log_message(self, format, *args):
        """Override to suppress noisy requests (static files, thumbnails, polling)."""
        if self.path in self.QUIET_PATHS or self.path.startswith(("/thumbnails/", "/static/")):
            return  # Suppress logging
        super().log_message(format, *args)

    def get_current_user(self):
        """Returns the username from the session cookie, or None."""
        if "Cookie" in self.headers:
            cookie = SimpleCookie(self.headers["Cookie"])
            if "session_token" in cookie:
                return session_manager.get_username(cookie["session_token"].value)
        return None

    # Cache: thumb filename → source file path (shared across all handler instances)
    _thumb_source_cache: dict = {}

    def _resolve_thumb_source(self, thumb_filename: str):
        """Reverse-lookup: given 'thumb_<hash>.jpg', find the source media file path."""
        import hashlib
        # Check cache first
        if thumb_filename in FinderHandler._thumb_source_cache:
            path = FinderHandler._thumb_source_cache[thumb_filename]
            if os.path.exists(path):
                return path
            else:
                del FinderHandler._thumb_source_cache[thumb_filename]

        # Build/rebuild cache from DB entries
        if not FinderHandler._thumb_source_cache:
            for entry in db.get_all():
                file_hash = hashlib.md5(entry.file_path.encode()).hexdigest()
                t_name = f"thumb_{file_hash}.jpg"
                FinderHandler._thumb_source_cache[t_name] = entry.file_path

        return FinderHandler._thumb_source_cache.get(thumb_filename)


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
            
            # 1a. VR MUSEUM -> Serve VR museum HTML
            # Normalize path to ignore query parameters for routing
            clean_path = self.path.split('?')[0]

            if clean_path == "/vr":
                user = self.get_current_user()
                if not user:
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

                vr_path = os.path.join(os.path.dirname(__file__), "static", "vr_museum.html")
                if os.path.exists(vr_path):
                    self.send_response(200)
                    self.send_header("Content-type", "text/html; charset=utf-8")
                    with open(vr_path, 'rb') as f:
                        data = f.read()
                        self.send_header("Content-Length", str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                else:
                    self.send_error(404, "VR Museum page not found")
                return
            
            # 1b. ROOT / INDEX -> Serve REPORT_FILE
            spa_routes = ["/", "/index.html", "/lobby", "/favorites", "/review", "/vault", "/treeview", "/duplicates"]
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

            # 2. THUMBNAILS -> Serve from THUMB_DIR (with security checks + lazy generation)
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
                    
                    # Lazy generation: if thumb doesn't exist on disk, generate on-demand
                    if not (os.path.exists(file_path) and os.path.isfile(file_path)):
                        source_path = self._resolve_thumb_source(filename)
                        if source_path:
                            from arcade_scanner.core.video_processor import create_thumbnail
                            create_thumbnail(source_path)
                    
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
            
            elif self.path.startswith("/reveal?"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    file_path = params.get("path", [None])[0]
                    if not file_path:
                         self.send_error(400, "Missing path parameter")
                         return
                         
                    print(f"🔍 Reveal requested for: {file_path}")

                    # Check if file is in a hidden folder (starts with .)
                    abs_path = os.path.abspath(file_path)
                    is_hidden = any(part.startswith('.') for part in Path(abs_path).parts if part != '/')

                    if is_hidden:
                        # File exists in hidden folder - return helpful response instead of blocking
                        print(f"📁 File in hidden folder: {abs_path}")
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        response = json.dumps({
                            "status": "hidden_folder",
                            "path": abs_path,
                            "message": "This file is located in a hidden system folder"
                        })
                        self.wfile.write(response.encode())
                        return

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
                        report_debouncer.schedule(current_port)
                        print(f"✅ Marked as optimized and report update scheduled: {os.path.basename(abs_path)}")
                    except Exception as e:
                        print(f"⚠️ Cache updated but report scheduling failed: {e}")

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

                    print(f"🔄 keep_optimized: original={original_path}")
                    print(f"🔄 keep_optimized: optimized={optimized_path}")

                    if original_path and optimized_path:
                        orig_abs = os.path.abspath(original_path)
                        opt_abs = os.path.abspath(optimized_path)

                        print(f"🔄 keep_optimized: orig_abs={orig_abs} exists={os.path.exists(orig_abs)}")
                        print(f"🔄 keep_optimized: opt_abs={opt_abs} exists={os.path.exists(opt_abs)}")
                        
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
                                report_debouncer.schedule(current_port)
                            except Exception as e:
                                print(f"⚠️ Report gen scheduling failed: {e}")
                                
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
            elif self.path.startswith("/stream?"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    file_path = params.get("path", [None])[0]
                    
                    if not file_path:
                        self.send_error(400, "Missing path parameter")
                        return

                    # Security Fix C-2: Prevent arbitrary file read
                    if not is_path_allowed(file_path):
                        # Detailed error message for owner (masked with 403 status for consistency)
                        error_msg = "Forbidden - Path outside allowed scan directories"
                        if not os.path.exists(os.path.realpath(os.path.abspath(file_path))):
                            error_msg = "Forbidden - File not found on disk"
                            
                        print(f"🚨 Unauthorized stream access blocked ({error_msg}): {file_path}")
                        self.send_error(403, error_msg)
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
                        
                        # Inject User-Specific Settings (Override Global)
                        settings_dump["enable_image_scanning"] = getattr(u.data, 'scan_images', False)
                        settings_dump["sensitive_dirs"] = u.data.sensitive_dirs
                        settings_dump["sensitive_tags"] = u.data.sensitive_tags
                        settings_dump["sensitive_collections"] = u.data.sensitive_collections
                    else:
                        settings_dump["smart_collections"] = []
                        settings_dump["scan_targets"] = []
                        settings_dump["exclude_paths"] = []
                        settings_dump["available_tags"] = []
                        settings_dump["enable_image_scanning"] = False
                else:
                    settings_dump["smart_collections"] = []
                    settings_dump["scan_targets"] = []
                    settings_dump["exclude_paths"] = []
                    settings_dump["available_tags"] = []

                # Add Docker detection
                settings_dump["is_docker"] = bool(os.getenv("CONFIG_DIR"))

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
            # --- TAG SYSTEM ENDPOINTS ---
            elif self.path.startswith("/api/tags"):
                # GET: Return all available tags OR handle delete action
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                
                params = parse_qs(urlparse(self.path).query)
                action = params.get("action", [None])[0]

                # HANDLE DELETE ACTION
                if action == "delete":
                    tag_name = params.get("name", [None])[0]
                    if tag_name:
                         u = user_db.get_user(user_name)
                         if u:
                             current_tags = list(u.data.available_tags)
                             updated_tags = [t for t in current_tags if t.get("name") != tag_name]
                             u.data.available_tags = updated_tags
                             
                             # Remove this tag from user's videos
                             for path, tags in u.data.tags.items():
                                 if tag_name in tags:
                                     u.data.tags[path] = [t for t in tags if t != tag_name]
                             
                             user_db.add_user(u)
                             print(f"🏷️ Deleted tag for user {user_name}: {tag_name}")
                        
                         self.send_response(200)
                         self.send_header("Content-Type", "application/json")
                         self.end_headers()
                         self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                         return
                    else:
                        self.send_error(400, "Missing name for delete")
                        return

                # DEFAULT: RETURN ALL TAGS
                u = user_db.get_user(user_name)
                tags = u.data.available_tags if u else []
                
                # print(f"DEBUG: GET /api/tags returning: {tags}", flush=True)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(tags).encode("utf-8"))
            
            elif self.path == "/api/setup/directories":
                # GET: List available directories in /media for setup wizard
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return

                directories = []
                media_root = "/media"
                
                try:
                    if os.path.exists(media_root) and os.path.isdir(media_root):
                        # Add root /media directory
                        try:
                            total_size = sum(os.path.getsize(os.path.join(media_root, f)) 
                                           for f in os.listdir(media_root) if os.path.isfile(os.path.join(media_root, f)))
                            file_count = sum(1 for f in os.listdir(media_root) if os.path.isfile(os.path.join(media_root, f)))
                            
                            directories.append({
                                "path": media_root,
                                "size_bytes": total_size,
                                "file_count": file_count,
                                "is_root": True
                            })
                        except PermissionError:
                            pass
                        
                        # Add immediate subdirectories
                        for item in os.listdir(media_root):
                            item_path = os.path.join(media_root, item)
                            if os.path.isdir(item_path):
                                try:
                                    total_size = sum(os.path.getsize(os.path.join(dp, f)) 
                                                   for dp, dn, filenames in os.walk(item_path) 
                                                   for f in filenames)
                                    file_count = sum(len(filenames) for dp, dn, filenames in os.walk(item_path))
                                    
                                    directories.append({
                                        "path": item_path,
                                        "name": item,
                                        "size_bytes": total_size,
                                        "file_count": file_count,
                                        "is_root": False
                                    })
                                except (PermissionError, OSError):
                                    pass
                except Exception as e:
                    print(f"⚠️ Error scanning /media: {e}")
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"directories": directories}).encode("utf-8"))
            
            elif self.path == "/api/setup/status":
                # GET: Check if setup is complete
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return
                
                u = user_db.get_user(user_name)
                setup_complete = getattr(u.data, 'setup_complete', True) if u else True
                
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"setup_complete": setup_complete}).encode("utf-8"))
            

            
            elif self.path == "/api/vr/gallery":
                # VR Museum: Return gallery rooms structured from smart collections
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401)
                    return

                u = user_db.get_user(user_name)
                if not u:
                    self.send_error(401)
                    return

                from arcade_scanner.core.deovr_generator import _video_matches_criteria
                from urllib.parse import quote as url_quote

                host = self.headers.get("Host", "localhost:8000")
                protocol = "https" if self.headers.get("X-Forwarded-Proto") == "https" else "http"
                if isinstance(self.connection, ssl.SSLSocket):
                    protocol = "https"
                server_url = f"{protocol}://{host}"

                # Get all videos
                all_videos = db.get_all()
                # Filter by user scan targets
                user_targets = [os.path.abspath(t) for t in u.data.scan_targets if t]
                if user_targets:
                    all_videos = [v for v in all_videos if any(
                        os.path.abspath(v.file_path).startswith(t) for t in user_targets
                    )]
                elif not u.is_admin:
                    all_videos = []

                # Build rooms from smart collections
                rooms = []
                collections = u.data.smart_collections or []

                for coll in collections:
                    coll_name = coll.get("name", "Collection")
                    criteria = coll.get("criteria", {})

                    # Only include video collections (skip photos-only)
                    inc_media = criteria.get("include", {}).get("media_type", [])
                    if inc_media and "video" not in inc_media:
                        continue

                    room_videos = []
                    for video in all_videos:
                        # Filter by duration (min 5 minutes / 300 seconds)
                        if not video.duration_sec or video.duration_sec < 300:
                            continue
                        if video.vaulted:
                            continue
                        if _video_matches_criteria(video, criteria):
                            filename = video.file_path.split('/')[-1].split('\\')[-1]
                            title = filename.rsplit('.', 1)[0] if '.' in filename else filename
                            v_obj = {
                                "title": title,
                                "stream_url": f"{server_url}/stream?path={url_quote(video.file_path)}",
                                "thumbnail": f"{server_url}/thumbnails/{video.thumb}" if video.thumb else None,
                                "duration": int(video.duration_sec) if video.duration_sec else 0,
                            }
                            room_videos.append(v_obj)

                    if room_videos:
                        rooms.append({
                            "name": coll_name,
                            "id": coll.get("id", coll_name),
                            "color": coll.get("color", "#d4a574"),
                            "video_count": len(room_videos),
                            "videos": room_videos[:14]  # Max 14 per room (4 walls)
                        })

                gallery_data = {"rooms": rooms}
                print(f"🏛️ VR Gallery: {len(rooms)} rooms, {sum(r['video_count'] for r in rooms)} total videos")

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps(gallery_data).encode("utf-8"))

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
                user_targets = [os.path.abspath(t) for t in u.data.scan_targets if t]
                filtered_videos = []

                # If user has no targets, they see nothing (or maybe we allow strict isolation?)
                # If user is admin? Admin typically sees all? 
                # Request was "include and excludes already different for every user?".
                # Implies users only see what they define.
                
                # ADMIN OVERRIDE: If no targets defined, Admin sees all.
                if not user_targets and u.is_admin:
                    filtered_videos = [e.model_dump(by_alias=True) for e in db.get_all()]
                elif user_targets:
                    # Optimized: Check path BEFORE serialization
                    for entry in db.get_all():
                        v_path = os.path.abspath(entry.file_path)
                        if any(v_path.startswith(t) for t in user_targets):
                             filtered_videos.append(entry.model_dump(by_alias=True))
                
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
            
            # Unreachable block removed

            
            # ================================================================
            # DUPLICATE DETECTION API
            # ================================================================
            elif self.path == "/api/duplicates/status":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(DUPLICATE_SCAN_STATE).encode("utf-8"))
                return

            elif self.path == "/api/duplicates" or self.path == "/api/duplicates/":
                # GET: Return cached duplicate results
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return
                
                try:
                    # Return cached results or empty list if not run yet
                    groups_data = DUPLICATE_RESULTS_CACHE if DUPLICATE_RESULTS_CACHE is not None else []
                    
                    # Calculate summary stats
                    total_groups = len(groups_data)
                    total_videos = sum(1 for g in groups_data if g.get("media_type") == "video")
                    total_images = sum(1 for g in groups_data if g.get("media_type") == "image")
                    potential_savings = sum(g.get("potential_savings_mb", 0) for g in groups_data)
                    
                    response = {
                        "summary": {
                            "total_groups": total_groups,
                            "video_groups": total_videos,
                            "image_groups": total_images,
                            "potential_savings_mb": potential_savings,
                            "scan_run": DUPLICATE_RESULTS_CACHE is not None
                        },
                        "groups": groups_data
                    }
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode("utf-8"))
                    
                except Exception as e:
                    print(f"❌ Error returning duplicates: {e}")
                    self.send_error(500, str(e))
            
            elif self.path.startswith("/download_gif?"):
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return
                
                try:
                    params = parse_qs(urlparse(self.path).query)
                    filename = params.get("file", [None])[0]
                    if not filename:
                        self.send_error(400, "Missing file parameter")
                        return
                    
                    # Security: Validate filename (no path traversal)
                    if "/" in filename or "\\" in filename or ".." in filename:
                        self.send_error(403, "Invalid filename")
                        return
                    
                    gif_export_dir = os.path.join(tempfile.gettempdir(), "arcade_gif_exports")
                    file_path = os.path.join(gif_export_dir, filename)
                    
                    if not os.path.exists(file_path):
                        self.send_error(404, "GIF file not found or still processing")
                        return
                    
                    # Serve the file
                    self.send_response(200)
                    self.send_header("Content-Type", "image/gif")
                    self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                    
                    file_size = os.path.getsize(file_path)
                    self.send_header("Content-Length", str(file_size))
                    self.end_headers()
                    
                    with open(file_path, 'rb') as f:
                        self.wfile.write(f.read())
                    
                    print(f"📥 Downloaded GIF: {filename} ({file_size / (1024*1024):.1f} MB)")
                    
                except Exception as e:
                    print(f"❌ Error downloading GIF: {e}")
                    self.send_error(500, str(e))
            
            # --- ENCODING QUEUE GET ENDPOINTS ---
            elif self.path == "/api/queue/status":
                try:
                    jobs = db.get_queue_status()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(jobs).encode())
                except Exception as e:
                    print(f"❌ Error in queue/status: {e}")
                    self.send_error(500, str(e))

            elif self.path.startswith("/api/queue/next"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    worker_id = params.get("worker_id", [socket.gethostname()])[0]
                    job = db.get_next_pending(worker_id=worker_id)
                    if job:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps(job).encode())
                    else:
                        self.send_response(204)
                        self.end_headers()
                except Exception as e:
                    print(f"❌ Error in queue/next: {e}")
                    self.send_error(500, str(e))

            elif self.path.startswith("/api/queue/download?"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    job_id = int(params.get("job_id", [0])[0])
                    if not job_id:
                        self.send_error(400, "Missing job_id")
                        return

                    # Look up job to get file path
                    jobs = db.get_queue_status(limit=100)
                    job = next((j for j in jobs if j["id"] == job_id), None)
                    if not job:
                        self.send_error(404, "Job not found")
                        return

                    file_path = job["file_path"]
                    if not os.path.exists(file_path):
                        db.update_job_status(job_id, "failed", result_message="Source file not found")
                        self.send_error(404, "Source file not found")
                        return

                    file_size = os.path.getsize(file_path)
                    filename = os.path.basename(file_path)
                    mime, _ = mimetypes.guess_type(file_path)

                    self.send_response(200)
                    self.send_header("Content-Type", mime or "application/octet-stream")
                    self.send_header("Content-Length", str(file_size))
                    self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
                    self.send_header("X-Original-Path", file_path)
                    self.end_headers()

                    # Stream in 8KB chunks
                    with open(file_path, 'rb') as f:
                        while True:
                            chunk = f.read(8192)
                            if not chunk:
                                break
                            self.wfile.write(chunk)

                    print(f"📤 Queue download: {filename} ({file_size / (1024*1024):.1f} MB) for job {job_id}")
                except Exception as e:
                    print(f"❌ Error in queue/download: {e}")
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
                    # Fix: Frontend sends 'enable_image_scanning', map to 'scan_images'
                    user_scan_images = new_settings.pop("scan_images", None)
                    if user_scan_images is None:
                        user_scan_images = new_settings.pop("enable_image_scanning", None)
                        
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
                            current_port = config.PORT if hasattr(config, 'PORT') else 8000
                            report_debouncer.schedule(current_port)
                            print("✅ HTML Report scheduled for regeneration with new settings")
                        except Exception as e:
                            print(f"⚠️ Settings saved but report gen scheduling failed: {e}")

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
            
            elif self.path == "/api/setup/complete":
                # POST: Complete first-run setup wizard
                try:
                    content_len = int(self.headers.get('Content-Length', 0))
                    post_body = self.rfile.read(content_len)
                    payload = json.loads(post_body)
                    
                    user_name = self.get_current_user()
                    if not user_name:
                        self.send_error(401)
                        return
                    
                    u = user_db.get_user(user_name)
                    if not u:
                        self.send_error(401)
                        return
                    
                    # Extract configuration
                    scan_targets = payload.get("scan_targets", [])
                    scan_images = payload.get("scan_images", False)
                    
                    # Validate
                    if not scan_targets:
                        self.send_error(400, "At least one scan target required")
                        return
                    
                    # Save configuration
                    u.data.scan_targets = scan_targets
                    u.data.scan_images = scan_images
                    u.data.setup_complete = True
                    user_db.add_user(u)
                    
                    print(f"✅ Setup completed for {user_name}: {scan_targets}")
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                except Exception as e:
                    print(f"Error completing setup: {e}")
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
            
            elif self.path == "/api/tags/update":
                try:
                    user_name = self.get_current_user()
                    if not user_name:
                        self.send_error(401)
                        return
                        
                    data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                    tag_name = data.get("name")
                    new_shortcut = data.get("shortcut")
                    
                    if not tag_name:
                        self.send_error(400, "Missing tag name")
                        return
                    
                    u = user_db.get_user(user_name)
                    if not u:
                        self.send_error(404, "User not found")
                        return
                    
                    # Find and update the tag
                    tag_found = False
                    for tag in u.data.available_tags:
                        if tag.get("name") == tag_name:
                            tag["shortcut"] = new_shortcut
                            tag_found = True
                            break
                    
                    if not tag_found:
                        self.send_error(404, "Tag not found")
                        return
                    
                    user_db.add_user(u)
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                except Exception as e:
                    print(f"Error updating tag: {e}")
                    self.send_error(500, str(e))
            
            # ================================================================
            # DUPLICATE DETECTION - DELETE FILES
            # ================================================================
            elif self.path == "/api/duplicates/scan":
                # POST: Start duplicate scan (supports batch_offset for pagination)
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return

                if DUPLICATE_SCAN_STATE["is_running"]:
                    self.send_error(409, "Scan already in progress")
                    return

                # Parse optional batch_offset from request body
                batch_offset = 0
                content_length = int(self.headers.get("Content-Length", 0))
                if content_length > 0 and content_length <= MAX_REQUEST_SIZE:
                    try:
                        body = self.rfile.read(content_length).decode("utf-8")
                        data = json.loads(body)
                        batch_offset = int(data.get("batch_offset", 0))
                    except:
                        pass  # Default to 0 if parsing fails

                # Get user's scan targets for filtering
                u = user_db.get_user(user_name)
                user_targets = None
                if u and u.data.scan_targets:
                    user_targets = [os.path.abspath(t) for t in u.data.scan_targets if t]

                # Start background thread with user's scan targets and batch offset
                import threading
                t = threading.Thread(target=background_duplicate_scan, args=(user_targets, batch_offset))
                t.daemon = True
                t.start()
                
                self.send_response(202)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "started", "batch_offset": batch_offset}).encode("utf-8"))

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

            elif self.path == "/api/duplicates/clear":
                # Clear duplicate cache and force rescan
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return

                clear_duplicate_cache()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "cleared"}).encode("utf-8"))

            # ================================================================
            # GIF EXPORT
            # ================================================================
            elif self.path == "/api/export/gif":
                user_name = self.get_current_user()
                if not user_name:
                    self.send_error(401, "Unauthorized")
                    return
                
                try:
                    content_length = int(self.headers.get("Content-Length", 0))
                    if content_length > MAX_REQUEST_SIZE:
                        self.send_error(413, "Request Entity Too Large")
                        return
                    
                    body = self.rfile.read(content_length).decode("utf-8")
                    data = json.loads(body)
                    
                    video_path = data.get("path")
                    preset = data.get("preset", "720p")
                    fps = data.get("fps", 15)
                    quality = data.get("quality", 80)
                    start_time = data.get("start_time")  # Optional trim start
                    end_time = data.get("end_time")      # Optional trim end
                    
                    if not video_path:
                        self.send_error(400, "Missing video path")
                        return
                    
                    # Security: Validate path
                    try:
                        video_path = sanitize_path(video_path)
                    except (SecurityError, ValueError) as e:
                        print(f"🚨 Security violation in GIF export: {e}")
                        self.send_error(403, "Forbidden - Invalid path")
                        return
                    
                    if not os.path.exists(video_path):
                        self.send_error(404, "Video file not found")
                        return
                    
                    # Get video info from database
                    video_entry = db.get(os.path.abspath(video_path))
                    if not video_entry:
                        self.send_error(404, "Video not in database")
                        return
                    
                    # Determine output dimensions based on preset
                    presets = {
                        "original": (video_entry.width or 1920, video_entry.height or 1080),
                        "1080p": (1920, 1080),
                        "720p": (1280, 720),
                        "480p": (854, 480),
                        "360p": (640, 360),
                    }
                    
                    width, height = presets.get(preset, presets["720p"])
                    
                    # Calculate duration for size estimation
                    duration = video_entry.duration_sec or 10
                    if start_time is not None and end_time is not None:
                        duration = max(0.1, end_time - start_time)
                    elif start_time is not None:
                        duration = max(0.1, duration - start_time)
                    elif end_time is not None:
                        duration = min(duration, end_time)
                    
                    estimated_size_mb = (width * height * fps * duration * (quality / 100) * 0.3) / (1024 * 1024)
                    
                    # Generate output filename
                    base_name = os.path.splitext(os.path.basename(video_path))[0]
                    output_filename = f"{base_name}_{preset}_{fps}fps.gif"
                    
                    # Create temp directory for GIF exports
                    gif_export_dir = os.path.join(tempfile.gettempdir(), "arcade_gif_exports")
                    os.makedirs(gif_export_dir, exist_ok=True)
                    
                    output_path = os.path.join(gif_export_dir, output_filename)
                    
                    # Generate unique job ID
                    import uuid
                    job_id = str(uuid.uuid4())[:8]
                    
                    # Start async conversion
                    import threading
                    
                    def convert_to_gif():
                        try:
                            print(f"🎞️ Starting GIF conversion: {output_filename}", flush=True)
                            
                            # Build FFmpeg input args with optional trim
                            input_args = ["ffmpeg", "-y"]
                            
                            # Add trim parameters if specified
                            if start_time is not None:
                                input_args.extend(["-ss", str(start_time)])
                            if end_time is not None:
                                input_args.extend(["-to", str(end_time)])
                            
                            input_args.extend(["-i", video_path])
                            
                            # Step 1: Generate palette
                            palette_path = os.path.join(gif_export_dir, f"palette_{job_id}.png")
                            palette_cmd = input_args + [
                                "-vf", f"fps={fps},scale={width}:{height}:flags=lanczos,palettegen=stats_mode=diff",
                                palette_path
                            ]
                            
                            print(f"🎨 Generating palette...", flush=True)
                            result = subprocess.run(palette_cmd, capture_output=True, text=True)
                            if result.returncode != 0:
                                print(f"❌ Palette generation failed: {result.stderr}", flush=True)
                                return
                            
                            # Step 2: Generate GIF with palette
                            bayer_scale = int((quality / 100) * 5)  # 0-5 scale
                            
                            gif_input_args = ["ffmpeg", "-y"]
                            if start_time is not None:
                                gif_input_args.extend(["-ss", str(start_time)])
                            if end_time is not None:
                                gif_input_args.extend(["-to", str(end_time)])
                            
                            gif_cmd = gif_input_args + [
                                "-i", video_path,
                                "-i", palette_path,
                                "-lavfi", f"fps={fps},scale={width}:{height}:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale={bayer_scale}",
                                "-loop", "0",  # Loop forever
                                output_path
                            ]
                            
                            print(f"🎬 Creating GIF...", flush=True)
                            result = subprocess.run(gif_cmd, capture_output=True, text=True)
                            if result.returncode != 0:
                                print(f"❌ GIF conversion failed: {result.stderr}", flush=True)
                                return
                            
                            # Cleanup palette
                            if os.path.exists(palette_path):
                                os.remove(palette_path)
                            
                            actual_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                            print(f"✅ GIF created: {output_filename} ({actual_size_mb:.1f} MB)", flush=True)
                            
                        except Exception as e:
                            print(f"❌ Error in GIF conversion: {e}", flush=True)
                            import traceback
                            traceback.print_exc()
                    
                    # Start conversion in background
                    thread = threading.Thread(target=convert_to_gif, daemon=True)
                    thread.start()
                    
                    # Return response immediately
                    response = {
                        "status": "processing",
                        "job_id": job_id,
                        "output_filename": output_filename,
                        "output_path": output_path,
                        "estimated_size_mb": round(estimated_size_mb, 2),
                        "download_url": f"/download_gif?file={output_filename}"
                    }
                    
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(response).encode("utf-8"))
                    
                except json.JSONDecodeError:
                    self.send_error(400, "Invalid JSON")
                except Exception as e:
                    print(f"❌ Error in GIF export: {e}")
                    import traceback
                    traceback.print_exc()
                    self.send_error(500, str(e))

            # --- ENCODING QUEUE POST ENDPOINTS ---
            elif self.path == "/api/queue/add":
                try:
                    content_len = int(self.headers.get('Content-Length', 0))
                    post_body = self.rfile.read(content_len)
                    data = json.loads(post_body)
                    file_path = data.get("file_path", "")

                    if not file_path:
                        self.send_error(400, "Missing file_path")
                        return

                    # Get file size
                    size_bytes = 0
                    if os.path.exists(file_path):
                        size_bytes = os.path.getsize(file_path)

                    job_id = db.queue_encode(file_path, size_bytes)
                    if job_id:
                        print(f"📋 Queued for remote encoding: {os.path.basename(file_path)} (job {job_id})")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": True, "job_id": job_id}).encode())
                    else:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": False, "error": "Already queued"}).encode())
                except Exception as e:
                    print(f"❌ Error in queue/add: {e}")
                    self.send_error(500, str(e))

            elif self.path == "/api/queue/cancel":
                try:
                    content_len = int(self.headers.get('Content-Length', 0))
                    post_body = self.rfile.read(content_len)
                    data = json.loads(post_body)
                    job_id = int(data.get("job_id", 0))

                    if db.cancel_job(job_id):
                        print(f"🗑️ Cancelled queue job {job_id}")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": True}).encode())
                    else:
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()
                        self.wfile.write(json.dumps({"success": False, "error": "Job not pending"}).encode())
                except Exception as e:
                    print(f"❌ Error in queue/cancel: {e}")
                    self.send_error(500, str(e))

            elif self.path.startswith("/api/queue/upload?"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    job_id = int(params.get("job_id", [0])[0])
                    if not job_id:
                        self.send_error(400, "Missing job_id")
                        return

                    # Look up job
                    jobs = db.get_queue_status(limit=100)
                    job = next((j for j in jobs if j["id"] == job_id), None)
                    if not job:
                        self.send_error(404, "Job not found")
                        return

                    original_path = job["file_path"]
                    orig_stem = Path(original_path).stem
                    orig_dir = os.path.dirname(original_path)
                    opt_path = os.path.join(orig_dir, f"{orig_stem}_opt.mp4")

                    content_len = int(self.headers.get('Content-Length', 0))

                    # Stream upload to disk in chunks
                    with open(opt_path, 'wb') as out:
                        remaining = content_len
                        while remaining > 0:
                            chunk_size = min(8192, remaining)
                            chunk = self.rfile.read(chunk_size)
                            if not chunk:
                                break
                            out.write(chunk)
                            remaining -= len(chunk)

                    opt_size = os.path.getsize(opt_path)
                    orig_size = os.path.getsize(original_path) if os.path.exists(original_path) else 0
                    saved = orig_size - opt_size

                    db.update_job_status(job_id, "done", saved_bytes=saved,
                                        result_message=f"Optimized: {opt_size/(1024*1024):.1f}MB (saved {saved/(1024*1024):.1f}MB)")

                    print(f"✅ Upload received for job {job_id}: {os.path.basename(opt_path)} ({opt_size/(1024*1024):.1f} MB, saved {saved/(1024*1024):.1f} MB)")

                    # Trigger report regeneration
                    try:
                        current_port = self.server.server_address[1]
                        report_debouncer.schedule(current_port)
                    except Exception as e:
                        print(f"⚠️ Report scheduling after upload failed: {e}")

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True, "opt_path": opt_path, "saved_bytes": saved}).encode())

                except Exception as e:
                    print(f"❌ Error in queue/upload: {e}")
                    self.send_error(500, str(e))

            elif self.path == "/api/queue/complete":
                try:
                    content_len = int(self.headers.get('Content-Length', 0))
                    post_body = self.rfile.read(content_len)
                    data = json.loads(post_body)

                    job_id = int(data.get("job_id", 0))
                    status = data.get("status", "done")
                    message = data.get("message", "")
                    saved_bytes = int(data.get("saved_bytes", 0))

                    db.update_job_status(job_id, status, result_message=message, saved_bytes=saved_bytes)
                    print(f"📋 Job {job_id} completed: {status} — {message}")

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode())
                except Exception as e:
                    print(f"❌ Error in queue/complete: {e}")
                    self.send_error(500, str(e))

            else:
                self.send_error(404)
        except Exception as e:
            print(f"Error handling POST request: {e}")
            self.send_response(500)
            self.end_headers()
