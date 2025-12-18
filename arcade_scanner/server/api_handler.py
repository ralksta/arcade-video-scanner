import http.server
import os
import subprocess
import time
from urllib.parse import unquote, parse_qs, urlparse
from arcade_scanner.app_config import (
    OPTIMIZER_SCRIPT, PREVIEW_DIR, IS_WIN
)
from arcade_scanner.core.cache_manager import load_cache, save_cache
from arcade_scanner.server.streaming_util import serve_file_range

class FinderHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == "/" or self.path == "":
                self.path = "/index.html"
                return super().do_GET()
            elif self.path.startswith("/reveal?path="):
                file_path = unquote(self.path.split("path=")[1])
                if IS_WIN:
                    # Windows: explorer /select,path
                    subprocess.run(["explorer", "/select,", os.path.normpath(file_path)])
                else:
                    # macOS: open -R path
                    subprocess.run(["open", "-R", file_path])
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/compress?path="):
                file_path = unquote(self.path.split("path=")[1])
                if IS_WIN:
                    # Windows: Launch cmd.exe and run the script
                    cmd = f'start cmd.exe /k "{OPTIMIZER_SCRIPT}" "{file_path}"'
                    subprocess.run(cmd, shell=True)
                else:
                    # macOS: Use AppleScript to open Terminal
                    applescript = f'tell application "Terminal" to do script "{OPTIMIZER_SCRIPT} \\"{file_path}\\""'
                    subprocess.run(["osascript", "-e", applescript])
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_compress?paths="):
                paths = unquote(self.path.split("paths=")[1]).split(",")
                for p in paths:
                    if os.path.exists(p):
                        if IS_WIN:
                            cmd = f'start cmd.exe /k "{OPTIMIZER_SCRIPT}" "{p}"'
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
                    # Normalize path for matching cache keys
                    abs_path = os.path.abspath(path)
                    c = load_cache()
                    if abs_path in c:
                        c[abs_path]["hidden"] = state
                    else:
                        # Fallback: if not in cache, create a minimal entry
                        c[abs_path] = {"hidden": state, "FilePath": abs_path}
                    save_cache(c)
                    print(f"Updated vault state for: {os.path.basename(abs_path)} -> hidden={state}")
                self.send_response(204)
                self.end_headers()
            elif self.path.startswith("/batch_hide?paths="):
                paths_str = unquote(self.path.split("paths=")[1])
                # Filter out the state param if it was appended as &state=true
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
            elif self.path.startswith("/stream?path="):
                file_path = unquote(self.path.split("path=")[1])
                serve_file_range(self, file_path, method="GET")
            elif self.path.startswith("/preview?name="):
                name = unquote(self.path.split("name=")[1])
                prev_path = os.path.join(PREVIEW_DIR, name)
                serve_file_range(self, prev_path, method="GET")
            else:
                super().do_GET()
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
                super().do_HEAD()
        except Exception as e:
            print(f"Error handling HEAD request: {e}")

    def log_message(self, format, *args):
        return
