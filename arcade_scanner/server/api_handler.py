import http.server
import os
import subprocess
import mimetypes
import sys
import time
import json
from urllib.parse import unquote, parse_qs, urlparse
from arcade_scanner.app_config import (
    OPTIMIZER_SCRIPT, PREVIEW_DIR, IS_WIN, STATIC_DIR, REPORT_FILE, THUMB_DIR,
    load_user_settings, save_user_settings, DEFAULT_SCAN_TARGETS, DEFAULT_EXCLUSIONS
)
from arcade_scanner.core.cache_manager import load_cache, save_cache
from arcade_scanner.server.streaming_util import serve_file_range

class FinderHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            # 1. ROOT / INDEX -> Serve REPORT_FILE
            if self.path == "/" or self.path == "/index.html" or self.path.startswith("/index.html?"):
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                
                if os.path.exists(REPORT_FILE):
                    fs = os.stat(REPORT_FILE)
                    self.send_header("Content-Length", str(fs.st_size))
                    self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                    self.end_headers()
                    with open(REPORT_FILE, 'rb') as f:
                        self.wfile.write(f.read())
                else:
                    self.send_error(404, "Report file not found")
                return

            # 2. THUMBNAILS -> Serve from THUMB_DIR
            elif self.path.startswith("/thumbnails/"):
                rel_path = unquote(self.path[12:]) # remove /thumbnails/
                file_path = os.path.normpath(os.path.join(THUMB_DIR, rel_path))
                
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

            # 3. STATIC ASSETS -> Catch-all for any path containing /static/
            elif "/static/" in self.path:
                try:
                    # Robustly extract relative path: get everything after the last "/static/"
                    # This handles paths like /static/styles.css AND /arcade_scanner/server/static/styles.css
                    rel_path = self.path.split("/static/")[-1].split('?')[0]
                    file_path = os.path.normpath(os.path.join(STATIC_DIR, rel_path))
                    
                    # Security check: Ensure the resolved path is inside STATIC_DIR
                    if not file_path.lower().startswith(os.path.normpath(STATIC_DIR).lower()):
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
                file_path = unquote(self.path.split("path=")[1])
                if IS_WIN:
                    subprocess.run(["explorer", "/select,", os.path.normpath(file_path)])
                else:
                    subprocess.run(["open", "-R", file_path])
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/compress?path="):
                file_path = unquote(self.path.split("path=")[1])
                if IS_WIN:
                    cmd = f'start "Video Optimizer" cmd /k ""{sys.executable}" "{OPTIMIZER_SCRIPT}" "{file_path}""'
                    subprocess.run(cmd, shell=True)
                else:
                    applescript = f'tell application "Terminal" to do script "{OPTIMIZER_SCRIPT} \\"{file_path}\\""'
                    subprocess.run(["osascript", "-e", applescript])
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_compress?paths="):
                paths = unquote(self.path.split("paths=")[1]).split(",")
                for p in paths:
                    if os.path.exists(p):
                        if IS_WIN:
                            cmd = f'start "Video Optimizer" cmd /k ""{sys.executable}" "{OPTIMIZER_SCRIPT}" "{p}""'
                            subprocess.run(cmd, shell=True)
                        else:
                            applescript = f'tell application "Terminal" to do script "{OPTIMIZER_SCRIPT} \\"{p}\\""'
                            subprocess.run(["osascript", "-e", applescript])
                        time.sleep(1)
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/hide?"):
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                state = params.get("state", ["true"])[0].lower() == "true"
                if path:
                    abs_path = os.path.abspath(path)
                    c = load_cache()
                    if abs_path in c:
                        c[abs_path]["hidden"] = state
                    else:
                        c[abs_path] = {"hidden": state, "FilePath": abs_path}
                    save_cache(c)
                    print(f"Updated vault state for: {os.path.basename(abs_path)} -> hidden={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_hide?paths="):
                paths_str = unquote(self.path.split("paths=")[1])
                paths_list = paths_str.split("&state=")[0].split(",")
                state = "state=false" not in self.path
                c = load_cache()
                updated_count = 0
                for p in paths_list:
                    abs_p = os.path.abspath(p)
                    if abs_p in c:
                        c[abs_p]["hidden"] = state
                    else:
                        c[abs_p] = {"hidden": state, "FilePath": abs_p}
                    updated_count += 1
                save_cache(c)
                print(f"Batch updated vault state for {updated_count} files -> hidden={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/favorite?"):
                params = parse_qs(urlparse(self.path).query)
                path = params.get("path", [None])[0]
                state = params.get("state", ["true"])[0].lower() == "true"
                if path:
                    abs_path = os.path.abspath(path)
                    c = load_cache()
                    if abs_path in c:
                        c[abs_path]["favorite"] = state
                    else:
                        c[abs_path] = {"favorite": state, "FilePath": abs_path}
                    save_cache(c)
                    print(f"Updated favorite state for: {os.path.basename(abs_path)} -> favorite={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_favorite?"):
                params = parse_qs(urlparse(self.path).query)
                paths = params.get("paths", [""])[0].split(",")
                state = params.get("state", ["true"])[0].lower() == "true"
                c = load_cache()
                updated_count = 0
                for p in paths:
                    if p:
                        abs_path = os.path.abspath(p)
                        if abs_path in c:
                            c[abs_path]["favorite"] = state
                        else:
                            c[abs_path] = {"favorite": state, "FilePath": abs_path}
                        updated_count += 1
                save_cache(c)
                print(f"Batch updated favorite state for {updated_count} files -> favorite={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/stream?path="):
                file_path = unquote(self.path.split("path=")[1])
                serve_file_range(self, file_path, method="GET")
            elif self.path.startswith("/preview?name="):
                name = unquote(self.path.split("name=")[1])
                prev_path = os.path.join(PREVIEW_DIR, name)
                serve_file_range(self, prev_path, method="GET")
            elif self.path == "/api/settings":
                # Return current settings as JSON
                settings = load_user_settings()
                response = {
                    "scan_targets": settings.get("scan_targets", []),
                    "exclude_paths": settings.get("exclude_paths", []),
                    "disabled_defaults": settings.get("disabled_defaults", []),
                    "min_size_mb": settings.get("min_size_mb", 100),
                    "bitrate_threshold_kbps": settings.get("bitrate_threshold_kbps", 15000),
                    "default_scan_targets": DEFAULT_SCAN_TARGETS,
                    "default_exclusions": DEFAULT_EXCLUSIONS  # With path + desc
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
                
                thumb_size = get_dir_size(THUMB_DIR) / (1024 * 1024)  # MB
                preview_size = get_dir_size(PREVIEW_DIR) / (1024 * 1024)  # MB
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
                serve_file_range(self, file_path, method="HEAD")
            elif self.path.startswith("/preview?name="):
                name = unquote(self.path.split("name=")[1])
                prev_path = os.path.join(PREVIEW_DIR, name)
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
                # Read and parse JSON body
                content_length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(content_length).decode("utf-8")
                new_settings = json.loads(body)
                
                # Validate and save
                settings_to_save = {
                    "scan_targets": new_settings.get("scan_targets", []),
                    "exclude_paths": new_settings.get("exclude_paths", []),
                    "disabled_defaults": new_settings.get("disabled_defaults", []),
                    "min_size_mb": new_settings.get("min_size_mb", 100),
                    "bitrate_threshold_kbps": new_settings.get("bitrate_threshold_kbps", 15000)
                }
                
                if save_user_settings(settings_to_save):
                    print(f"✅ Settings saved: {len(settings_to_save['scan_targets'])} targets, {len(settings_to_save['exclude_paths'])} excludes")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                else:
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"success": False, "error": "Failed to save"}).encode("utf-8"))
            else:
                self.send_error(404)
        except Exception as e:
            print(f"Error handling POST request: {e}")
            self.send_response(500)
            self.end_headers()
