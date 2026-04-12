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


class _MediaCache:
    """Thread-safe in-memory cache für db.get_all() mit 30s TTL.
    
    Verhindert wiederholte Full-Table-Scans für API-Requests, die in kurzer
    Zeit mehrfach alle Einträge lesen. Wird explizit invalidiert wenn Daten
    verändert werden (upsert, remove etc.).
    """
    TTL = 30.0  # Sekunden

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data: list | None = None
        self._timestamp: float = 0.0

    def get(self) -> list:
        """Gibt gecachte Resultate zurück (max. TTL alt) oder liest frisch aus DB."""
        now = time.monotonic()
        with self._lock:
            if self._data is not None and (now - self._timestamp) < self.TTL:
                return self._data
        # Cache-Miss: außerhalb des Locks lesen um Blocking zu minimieren
        fresh = db.get_all()
        with self._lock:
            self._data = fresh
            self._timestamp = time.monotonic()
        return fresh

    def invalidate(self) -> None:
        """Muss nach jeder Schreiboperation aufgerufen werden."""
        with self._lock:
            self._data = None
            self._timestamp = 0.0


_media_cache = _MediaCache()


class DuplicateScanManager:
    """Thread-safe manager for duplicate scan state and cached results."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state: dict = {
            "is_running": False,
            "progress": 0,
            "message": "",
            "has_more": False,
            "batch_offset": 0,
            "next_offset": 0,
        }
        self._cache = None

    def update_state(self, **kwargs) -> None:
        with self._lock:
            self._state.update(kwargs)

    def get_state(self) -> dict:
        with self._lock:
            return dict(self._state)

    @property
    def cache(self):
        with self._lock:
            return self._cache

    @cache.setter
    def cache(self, value) -> None:
        with self._lock:
            self._cache = value


# Module-level singleton – replaces bare global dicts
_dup_mgr = DuplicateScanManager()



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
            results = [e.model_dump(by_alias=True) for e in _media_cache.get()]
            generate_html_report(results, config.report_file, server_port=port)
            # print(f"✅ HTML Report regenerated (debounced)")
        except Exception as e:
            print(f"⚠️ Report generation failed: {e}")

report_debouncer = ReportDebouncer(delay=1.0)

def load_duplicate_cache() -> bool:
    """Load cached duplicate results from disk."""
    try:
        if os.path.exists(DUPLICATES_CACHE_FILE):
            with open(DUPLICATES_CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _dup_mgr.cache = data.get('groups', [])
                print(f"✅ Loaded {len(_dup_mgr.cache)} duplicate groups from cache")
                return True
    except Exception as e:
        print(f"⚠️ Could not load duplicate cache: {e}")
    return False

def save_duplicate_cache() -> None:
    """Save duplicate results to disk."""
    try:
        cache = _dup_mgr.cache
        if cache is not None:
            cache_data = {'groups': cache, 'timestamp': time.time()}
            with open(DUPLICATES_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f)
            print(f"✅ Saved {len(cache)} duplicate groups to cache")
    except Exception as e:
        print(f"⚠️ Could not save duplicate cache: {e}")

def clear_duplicate_cache() -> None:
    """Clear the duplicate cache from memory and disk."""
    _dup_mgr.cache = None
    try:
        if os.path.exists(DUPLICATES_CACHE_FILE):
            os.remove(DUPLICATES_CACHE_FILE)
            print("🗑️ Cleared duplicate cache")
    except Exception as e:
        print(f"⚠️ Could not remove duplicate cache file: {e}")

def background_duplicate_scan(
    user_scan_targets=None,
    batch_offset: int = 0,
) -> None:
    """Background worker for duplicate detection.

    Args:
        user_scan_targets: Optional list of absolute paths to filter files by user's
                          scan targets.  If None, scans all files in database.
        batch_offset: Starting offset for image batching (default 0 = first batch).
    """
    from arcade_scanner.core.duplicate_detector import DuplicateDetector

    _dup_mgr.update_state(
        is_running=True,
        progress=0,
        message="Initializing scan...",
        has_more=False,
        batch_offset=batch_offset,
    )

    try:
        def progress_cb(msg: str, pct: float) -> None:
            _dup_mgr.update_state(message=msg, progress=int(pct))

        detector = DuplicateDetector()
        all_videos = _media_cache.get()
        print(f"🔍 Duplicate scan: {len(all_videos)} total files in database")

        if user_scan_targets:
            all_videos = [
                v for v in all_videos
                if any(os.path.abspath(v.file_path).startswith(t) for t in user_scan_targets)
            ]
            print(f"🔍 After user filter: {len(all_videos)} files match scan targets")

        videos = [v for v in all_videos if getattr(v, 'media_type', 'video') == 'video']
        images = [v for v in all_videos if getattr(v, 'media_type', 'video') == 'image']
        print(f"🔍 Scanning {len(videos)} videos + {len(images)} images (batch offset: {batch_offset})")

        results, has_more = detector.find_all_duplicates(
            all_videos, progress_cb, batch_offset=batch_offset
        )
        print(f"🔍 Found {len(results)} duplicate groups (has_more: {has_more})")

        _dup_mgr.cache = [g.to_dict() for g in results]
        _dup_mgr.update_state(
            has_more=has_more,
            next_offset=batch_offset + 5000 if has_more else 0,
        )
        save_duplicate_cache()

        _dup_mgr.update_state(
            message="Scan complete" + (" - more batches available" if has_more else ""),
            progress=100,
        )

    except Exception as e:
        print(f"❌ Error in duplicate scan: {e}")
        _dup_mgr.update_state(message=f"Error: {e}")
    finally:
        _dup_mgr.update_state(is_running=False)


class FinderHandler(http.server.SimpleHTTPRequestHandler):
    # Suppress logging for noisy polling endpoints
    QUIET_PATHS = {"/api/duplicates/status"}

    def log_message(self, format, *args):
        """Override to suppress noisy requests (static files, thumbnails, polling)."""
        try:
            path = getattr(self, 'path', None)
            
            # Paths that are ALWAYS quiet (polling, thumbnails, static assets)
            if path and (path in self.QUIET_PATHS or path.startswith(("/thumbnails/", "/static/"))):
                return

            # If verbose is disabled, also suppress streaming and main hits to keep terminal clean
            # Use getattr for safety during early initialization or reload
            verbose = getattr(getattr(config, 'settings', None), 'verbose_scanning', False)
            if not verbose and path:
                if path.startswith("/stream?") or path == "/":
                    return
        except Exception:
            # Never let logging crash the request
            pass
            
        super().log_message(format, *args)

    def get_current_user(self):
        """Returns the username from the session cookie, or None."""
        if "Cookie" in self.headers:
            cookie = SimpleCookie(self.headers["Cookie"])
            if "session_token" in cookie:
                return session_manager.get_username(cookie["session_token"].value)
        return None

    # LRU thumb filename → source file path (shared across handler instances, bounded size)
    _thumb_source_cache: dict = {}
    _THUMB_CACHE_MAX = 2000

    def _resolve_thumb_source(self, thumb_filename: str):
        """Reverse-lookup: given 'thumb_<hash>.jpg', find the source media file path.
        
        Strategy:
        1. Check in-memory LRU cache (fast path)
        2. On miss: do a full cache warm from DB (first call) or a targeted scan for new entries
        3. On persistent miss: scan full DB once more (catches entries added after server start)
        """
        import hashlib
        from collections import OrderedDict

        cache = FinderHandler._thumb_source_cache

        # Promote to OrderedDict if still a plain dict (happens once)
        if not isinstance(cache, OrderedDict):
            FinderHandler._thumb_source_cache = OrderedDict(cache)
            cache = FinderHandler._thumb_source_cache

        # Fast path: LRU hit
        if thumb_filename in cache:
            path = cache[thumb_filename]
            if os.path.exists(path):
                cache.move_to_end(thumb_filename)
                return path
            else:
                del cache[thumb_filename]

        # Slow path: populate/refresh from DB
        # Always re-read DB on miss so entries added after server start are found.
        # Using a set to track known entries avoids re-hashing already cached paths.
        known_paths = set(cache.values())
        for entry in _media_cache.get():
            if entry.file_path not in known_paths:
                # Use surrogateescape to handle Windows-originating surrogate characters
                file_hash = hashlib.md5(entry.file_path.encode('utf-8', 'surrogateescape')).hexdigest()
                t_name = f"thumb_{file_hash}.jpg"
                cache[t_name] = entry.file_path
                known_paths.add(entry.file_path)

        # Evict oldest entries when over capacity
        while len(cache) > FinderHandler._THUMB_CACHE_MAX:
            cache.popitem(last=False)

        return cache.get(thumb_filename)


    def do_GET(self):
        try:
            from .routes import queue, settings, duplicates, tags, files
            if queue.handle_get(self): return
            if settings.handle_get(self): return
            if duplicates.handle_get(self): return
            if tags.handle_get(self): return
            if files.handle_get(self): return
        except Exception as e:
            print(f"Module route error GET: {e}")
        try:
            # 0. Health check endpoint - no auth required
            if self.path == "/api/health" or self.path == "/api/health/":
                try:
                    total = db.count()
                except Exception:
                    total = -1
                health = {
                    "status": "ok",
                    "version": "1.0",
                    "db_entries": total,
                }
                body = json.dumps(health).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            
            
            # 1. ROOT / INDEX -> Serve REPORT_FILE
            spa_routes = ["/", "/index.html", "/lobby", "/favorites", "/review", "/vault", "/treeview", "/duplicates"]
            clean_path = self.path.split('?')[0]
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
                        self.send_header("Access-Control-Allow-Origin", "*")
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

            # Routes below are handled by routes/files.py (registered above in the
            # module dispatcher). The following elif chain is legacy code kept for
            # reference during the transition phase. It is unreachable because
            # files.handle_get() returns True for all these paths.
            #
            # Paths migrated to routes/files.py:
            #   /reveal?         /api/mark_optimized?   /compress?
            #   /api/keep_optimized?  /api/discard_optimized?
            #   /api/rescan      /api/backup
            #   /batch_compress?  /hide?  /batch_hide?  /favorite?  /batch_favorite?
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
                    except OSError:
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
                
                # Fetch once, use in both branches below
                all_entries = _media_cache.get()

                # ADMIN OVERRIDE: If no targets defined, Admin sees all.
                if not user_targets and u.is_admin:
                    filtered_videos = [e.model_dump(by_alias=True) for e in all_entries]
                elif user_targets:
                    # Optimized: Check path BEFORE serialization
                    for entry in all_entries:
                        v_path = os.path.abspath(entry.file_path)
                        # Always show items in Review mode, regardless of scan targets
                        if entry.status == "REVIEW" or any(v_path.startswith(t) for t in user_targets):
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

            elif self.path.startswith("/api/queue/check?"):
                try:
                    params = parse_qs(urlparse(self.path).query)
                    job_id = int(params.get("job_id", [0])[0])
                    cancelled = db.is_job_cancelled(job_id) if job_id else False
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"cancelled": cancelled}).encode())
                except Exception as e:
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
        try:
            from .routes import queue, settings, duplicates, tags
            if queue.handle_post(self): return
            if settings.handle_post(self): return
            if duplicates.handle_post(self): return
            if tags.handle_post(self): return
        except Exception as e:
            print(f"Module route error POST: {e}")
        print(f"DEBUG: POST Request received for path: {self.path}", flush=True)

        try:
            if self.path.startswith("/api/login"):
                content_len = int(self.headers.get('Content-Length', 0))
                post_body = self.rfile.read(content_len)
                try:
                    data = json.loads(post_body)
                    username = data.get("username", "")
                    password = data.get("password", "")
                    remember = data.get("remember", True)  # Default: remember me

                    username = username.strip() if username else ""

                    # ── Brute-force rate limiting ────────────────────────────
                    client_ip = (
                        self.headers.get("X-Forwarded-For", "").split(",")[0].strip()
                        or self.client_address[0]
                    )

                    if session_manager.is_locked_out(client_ip):
                        print(f"🔒 Blocked login attempt from locked-out IP {client_ip}")
                        self.send_error(429, "Too many failed attempts. Try again in 15 minutes.")
                        return

                    # ── Verify credentials ───────────────────────────────────
                    is_valid = user_db.verify_password(username, password)

                    if is_valid:
                        session_manager.record_success(client_ip)
                        token = session_manager.create_session(username)
                        print(f"✅ Login succeeded for user: '{username}' from {client_ip}")

                        # Detect whether we're serving over HTTPS
                        is_https = (
                            self.headers.get("X-Forwarded-Proto") == "https"
                            or isinstance(self.connection, ssl.SSLSocket)
                        )

                        self.send_response(200)
                        cookie = SimpleCookie()
                        cookie["session_token"] = token
                        cookie["session_token"]["path"] = "/"
                        cookie["session_token"]["httponly"] = True
                        if remember:
                            cookie["session_token"]["max-age"] = 86400 * 30  # 30 days
                        # (no max-age = session cookie, expires on browser close)
                        # Only set Secure over HTTPS — plain HTTP drops the cookie silently
                        if is_https:
                            cookie["session_token"]["secure"] = True
                            cookie["session_token"]["samesite"] = "Strict"
                        else:
                            cookie["session_token"]["samesite"] = "Lax"

                        for morsel in cookie.values():
                            self.send_header("Set-Cookie", morsel.OutputString())

                        self.end_headers()
                        self.wfile.write(json.dumps({"success": True}).encode())
                    else:
                        remaining = session_manager.record_failure(client_ip)
                        print(f"❌ Login failed for IP {client_ip} ({remaining} attempts remaining)")
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

            if self.path == "/api/settings/remove-photos":
                from .routes.settings import handle_post_remove_photos
                handle_post_remove_photos(self)
                return

            # ================================================================
            # DUPLICATE DETECTION - DELETE FILES
            # ================================================================
            # ================================================================
            # GIF EXPORT
            # ================================================================
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
                        self.wfile.write(json.dumps({"success": False, "error": "Job not cancellable"}).encode())
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
