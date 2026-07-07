"""File operation route handlers (compress, hide, favorite, reveal, etc.).

Extracted from api_handler.py – delegates to _media_cache and db directly via
the lazy-import helpers shared with other route modules.
"""
from __future__ import annotations

import os
import sys
import shlex
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse, unquote

from arcade_scanner.config import config, IS_WIN
from arcade_scanner.database import db, user_db
from arcade_scanner.security import sanitize_path, is_path_allowed, SecurityError

# ---------------------------------------------------------------------------
# Lazy imports – avoid circular deps with api_handler module-level singletons
# ---------------------------------------------------------------------------

def _get_media_cache():
    from arcade_scanner.server.api_handler import _media_cache  # noqa: PLC0415
    return _media_cache


def _get_report_debouncer():
    from arcade_scanner.server.api_handler import report_debouncer  # noqa: PLC0415
    return report_debouncer


# ---------------------------------------------------------------------------
# GET handler
# ---------------------------------------------------------------------------

def handle_get(handler) -> bool:
    """Handle file-operation GET requests.

    Returns True if the request was handled, False otherwise.
    """
    path = handler.path

    # /reveal?path=...
    if path.startswith("/reveal?"):
        _handle_reveal(handler)
        return True

    # /api/mark_optimized?path=...
    if path.startswith("/api/mark_optimized?"):
        _handle_mark_optimized(handler)
        return True

    # /compress?path=...
    if path.startswith("/compress?"):
        _handle_compress(handler)
        return True

    # /api/keep_optimized?original=...&optimized=...
    if path.startswith("/api/keep_optimized?"):
        _handle_keep_optimized(handler)
        return True

    # /api/discard_optimized?path=...
    if path.startswith("/api/discard_optimized?"):
        _handle_discard_optimized(handler)
        return True

    # /hide?path=...&state=...
    if path.startswith("/hide?"):
        _handle_hide(handler)
        return True

    # /batch_hide?paths=...
    if path.startswith("/batch_hide?paths="):
        _handle_batch_hide(handler)
        return True

    # /favorite?path=...&state=...
    if path.startswith("/favorite?"):
        _handle_favorite(handler)
        return True

    # /batch_favorite?paths=...
    if path.startswith("/batch_favorite?"):
        _handle_batch_favorite(handler)
        return True

    # /batch_compress?paths=...
    if path.startswith("/batch_compress?paths="):
        _handle_batch_compress(handler)
        return True

    # /api/rescan
    if path == "/api/rescan":
        _handle_rescan(handler)
        return True

    # /api/backup
    if path == "/api/backup":
        _handle_backup(handler)
        return True

    return False


# ---------------------------------------------------------------------------
# Individual handlers
# ---------------------------------------------------------------------------

def _handle_reveal(handler) -> None:
    from arcade_scanner.server.response_helpers import require_auth  # noqa: PLC0415

    try:
        params = parse_qs(urlparse(handler.path).query)
        file_path = params.get("path", [None])[0]
        if not file_path:
            handler.send_error(400, "Missing path parameter")
            return

        print(f"🔍 Reveal requested for: {file_path}")

        abs_path = os.path.abspath(file_path)
        is_hidden = any(part.startswith('.') for part in Path(abs_path).parts if part != '/')

        if is_hidden:
            print(f"📁 File in hidden folder: {abs_path}")
            handler.send_response(200)
            handler.send_header('Content-Type', 'application/json')
            handler.end_headers()
            import json
            response = json.dumps({
                "status": "hidden_folder",
                "path": abs_path,
                "message": "This file is located in a hidden system folder"
            })
            handler.wfile.write(response.encode())
            return

        if not is_path_allowed(file_path):
            print(f"🚨 Unauthorized reveal attempt blocked: {file_path}")
            handler.send_error(403, "Forbidden - Path not in scan directories")
            return

        if not os.path.exists(file_path):
            print(f"❌ Error: File does not exist: {file_path}")
            handler.send_error(404, "File not found")
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
            parent_dir = os.path.dirname(file_path)
            print(f"🚀 Running: xdg-open '{parent_dir}'")
            subprocess.run(["xdg-open", parent_dir])

        handler.send_response(204)
        handler.end_headers()
    except SecurityError as e:
        print(f"🚨 Security violation: {e}")
        handler.send_error(403, "Forbidden")
    except Exception as e:
        print(f"❌ Critical error in reveal endpoint: {e}")
        handler.send_error(500, str(e))


def _handle_mark_optimized(handler) -> None:
    import json
    from arcade_scanner.models.video_entry import VideoEntry  # lazy

    params = parse_qs(urlparse(handler.path).query)
    path = params.get("path", [None])[0]
    if path:
        abs_path = os.path.abspath(path)

        entry = db.get(abs_path)
        if entry:
            entry.status = "OK"
        else:
            size_mb = 0
            try:
                if os.path.exists(abs_path):
                    size_mb = os.path.getsize(abs_path) / (1024 * 1024)
            except OSError as e:
                print(f"⚠️ Could not stat file {abs_path}: {e}")
            entry = VideoEntry(FilePath=abs_path, Size_MB=size_mb, Status="OK")
        db.upsert(entry)
        db.save()
        _get_media_cache().invalidate()

        try:
            current_port = handler.server.server_address[1]
            _get_report_debouncer().schedule(current_port)
            print(f"✅ Marked as optimized and report update scheduled: {os.path.basename(abs_path)}")
        except Exception as e:
            print(f"⚠️ Cache updated but report scheduling failed: {e}")

    handler.send_response(204)
    handler.end_headers()


def _handle_compress(handler) -> None:
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return

    try:
        params = parse_qs(urlparse(handler.path).query)
        file_path = params.get("path", [None])[0]

        if not file_path:
            print("❌ No path provided for compression")
            handler.send_error(400, "Missing path parameter")
            return

        try:
            file_path = sanitize_path(file_path)
        except (SecurityError, ValueError) as e:
            print(f"🚨 Security violation in compress: {e}")
            handler.send_error(403, "Forbidden - Invalid path")
            return

        audio_mode = params.get("audio", ["enhanced"])[0]
        video_mode = params.get("video", ["compress"])[0]
        target_codec = params.get("codec", ["hevc"])[0]
        q_val = params.get("q", [None])[0]
        ss = params.get("ss", [None])[0]
        to = params.get("to", [None])[0]

        if audio_mode not in ["enhanced", "standard"]:
            print(f"🚨 Invalid audio mode: {audio_mode}")
            handler.send_error(400, "Invalid audio mode")
            return

        if video_mode not in ["compress", "copy"]:
            print(f"🚨 Invalid video mode: {video_mode}")
            handler.send_error(400, "Invalid video mode")
            return

        current_port = handler.server.server_address[1]
        print(f"⚡ Optimize: {file_path} | Video: {video_mode} | Audio: {audio_mode} | Q: {q_val} | Trim: {ss}-{to}")

        encoding_preset = getattr(config.settings, 'encoding_preset', 'balanced')
        cmd_parts = [
            sys.executable, config.optimizer_path, file_path,
            "--port", str(current_port),
            "--audio-mode", audio_mode,
            "--video-mode", video_mode,
            "--preset", encoding_preset,
            "--codec", target_codec,
        ]

        if ss:
            cmd_parts.extend(["--ss", ss])
        if to:
            cmd_parts.extend(["--to", to])
        if q_val:
            cmd_parts.extend(["--q", q_val])

        if IS_WIN:
            print(f"🚀 Launching Optimizer (Win): {' '.join(cmd_parts)}")
            subprocess.Popen(cmd_parts, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            safe_cmd = ' '.join(shlex.quote(str(p)) for p in cmd_parts)
            print(f"🚀 Launching Optimizer (Mac): {safe_cmd}")
            applescript = (
                'tell application "Terminal"\n'
                '    activate\n'
                f'    do script "{safe_cmd}"\n'
                'end tell'
            )
            subprocess.run(["osascript", "-e", applescript])

        handler.send_response(204)
        handler.end_headers()
    except SecurityError as e:
        print(f"🚨 Security violation: {e}")
        handler.send_error(403, "Forbidden")
    except ValueError as e:
        print(f"❌ Validation error: {e}")
        handler.send_error(400, str(e))
    except Exception as e:
        print(f"❌ Error in compress endpoint: {e}")
        handler.send_error(500, str(e))


def _handle_keep_optimized(handler) -> None:
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return

    try:
        import shutil
        from arcade_scanner.models.video_entry import VideoEntry # lazy
        
        params = parse_qs(urlparse(handler.path).query)
        original_path = unquote(params.get("original", [None])[0])
        optimized_path = unquote(params.get("optimized", [None])[0])

        print(f"🔄 keep_optimized: original={original_path}")
        print(f"🔄 keep_optimized: optimized={optimized_path}")

        if original_path and optimized_path:
            orig_abs = os.path.abspath(original_path)
            opt_abs = os.path.abspath(optimized_path)

            if os.path.exists(opt_abs):
                # Review Mode Check
                entry_orig = db.get(orig_abs)
                if entry_orig and entry_orig.status == "REVIEW" and entry_orig.original_path:
                    # REVIEW MODE: Restoring to original path on disk
                    final_dest = entry_orig.original_path
                    print(f"🚀 Review Mode Keep: Moving {opt_abs} to {final_dest}")
                    
                    os.makedirs(os.path.dirname(final_dest), exist_ok=True)
                    shutil.move(opt_abs, final_dest)
                    
                    # Cleanup review versions
                    if os.path.exists(orig_abs):
                        os.remove(orig_abs)
                    
                    # DB Update: Use optimized metadata but destination path
                    entry_opt = db.get(opt_abs)
                    if entry_opt:
                        opt_dict = entry_opt.model_dump(by_alias=True)
                        opt_dict["FilePath"] = final_dest
                        opt_dict["Status"] = "OK"
                        opt_dict["OriginalPath"] = None
                        db.upsert(VideoEntry(**opt_dict))
                    
                    db.remove(opt_abs)
                    db.remove(orig_abs)
                    
                    # Cleanup empty review directory
                    try:
                        job_dir = os.path.dirname(orig_abs)
                        if os.path.exists(job_dir) and not os.listdir(job_dir):
                            os.rmdir(job_dir)
                    except Exception as e:
                        print(f"⚠️ Cleanup failed: {e}")
                else:
                    # STANDARD MODE: Legacy overwrite
                    orig_path_obj = Path(orig_abs)
                    opt_path_obj = Path(opt_abs)
                    new_path = orig_path_obj.with_suffix(opt_path_obj.suffix)

                    if os.path.exists(orig_abs):
                        os.remove(orig_abs)

                    os.rename(opt_abs, new_path)

                    db.remove(opt_abs)
                    if orig_abs != str(new_path):
                        db.remove(orig_abs)

                db.save()
                _get_media_cache().invalidate()
            else:
                print(f"❌ Optimized file not found: {opt_abs}")

        handler.send_response(204)
        handler.end_headers()
    except Exception as e:
        print(f"❌ Error in keep_optimized: {e}")
        handler.send_error(500, str(e))


def _handle_discard_optimized(handler) -> None:
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return

    try:
        import shutil
        from arcade_scanner.models.video_entry import VideoEntry # lazy
        
        params = parse_qs(urlparse(handler.path).query)
        path = unquote(params.get("path", [None])[0])

        if path:
            abs_path = os.path.abspath(path)
            
            # Review Mode Check: If this is an optimized file in a review folder, 
            # we must also restore the original file.
            entry = db.get(abs_path)
            if entry and entry.status == "REVIEW":
                job_dir = os.path.dirname(abs_path)
                orig_file = None
                # Search for the original sibling in DB
                for v in db.get_all():
                    if v.status == "REVIEW" and os.path.dirname(v.file_path) == job_dir and "_original" in v.file_path:
                        orig_file = v
                        break
                
                if orig_file and orig_file.original_path:
                    print(f"⏪ Review Mode Discard: Restoring original to {orig_file.original_path}")
                    shutil.move(orig_file.file_path, orig_file.original_path)
                    
                    # Restore DB entry
                    orig_dict = orig_file.model_dump(by_alias=True)
                    orig_dict["FilePath"] = orig_file.original_path
                    orig_dict["Status"] = "OK"
                    orig_dict["OriginalPath"] = None
                    db.upsert(VideoEntry(**orig_dict))
                    
                    # Cleanup
                    if os.path.exists(abs_path): os.remove(abs_path)
                    db.remove(abs_path)
                    db.remove(orig_file.file_path)
                    
                    try:
                        if os.path.exists(job_dir) and not os.listdir(job_dir):
                            os.rmdir(job_dir)
                    except Exception: pass
                else:
                    # Just discard this file
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        db.remove(abs_path)
            else:
                # Standard Mode discard
                if os.path.exists(abs_path):
                    os.remove(abs_path)
                    db.remove(abs_path)
            
            db.save()
            _get_media_cache().invalidate()

            try:
                current_port = handler.server.server_address[1]
                _get_report_debouncer().schedule(current_port)
            except Exception as e:
                print(f"⚠️ Report gen scheduling failed: {e}")

            print(f"🗑️ Discarded optimized/reviewed: {os.path.basename(abs_path)}")

        handler.send_response(204)
        handler.end_headers()
    except Exception as e:
        print(f"❌ Error in discard_optimized: {e}")
        handler.send_error(500, str(e))


def _handle_hide(handler) -> None:
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401)
        return

    params = parse_qs(urlparse(handler.path).query)
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

    handler.send_response(204)
    handler.end_headers()


def _handle_batch_hide(handler) -> None:
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401)
        return

    paths_str = unquote(handler.path.split("paths=")[1])
    paths_list = paths_str.split("&state=")[0].split(",")
    state = "state=false" not in handler.path

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
    handler.send_response(204)
    handler.end_headers()


def _handle_favorite(handler) -> None:
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401)
        return

    params = parse_qs(urlparse(handler.path).query)
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

    handler.send_response(204)
    handler.end_headers()


def _handle_batch_favorite(handler) -> None:
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401)
        return

    params = parse_qs(urlparse(handler.path).query)
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
    handler.send_response(204)
    handler.end_headers()


def _handle_batch_compress(handler) -> None:
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return

    try:
        paths = unquote(handler.path.split("paths=")[1]).split("|||")
        current_port = handler.server.server_address[1]

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
            handler.send_response(204)
            handler.end_headers()
            return

        batch_controller_path = os.path.join(
            os.path.dirname(config.optimizer_path),
            "batch_controller.py"
        )
        files_arg = ",".join(validated_paths)
        cmd_parts = [
            sys.executable,
            batch_controller_path,
            f"--files={files_arg}",
            f"--port={current_port}",
        ]

        if IS_WIN:
            subprocess.Popen(cmd_parts, creationflags=subprocess.CREATE_NEW_CONSOLE)
        else:
            safe_cmd = ' '.join(shlex.quote(str(p)) for p in cmd_parts)
            print(f"🚀 Launching Batch Controller: {len(validated_paths)} files")
            escaped_cmd = safe_cmd.replace('\\', '\\\\').replace('"', '\\"')
            applescript = f'tell application "Terminal" to do script "{escaped_cmd}"'
            subprocess.run(["osascript", "-e", applescript])

        handler.send_response(204)
        handler.end_headers()
    except Exception as e:
        print(f"❌ Error in batch_compress: {e}")
        handler.send_error(500)


def _handle_rescan(handler) -> None:
    import asyncio
    import json
    from arcade_scanner.scanner import get_scanner_manager
    from arcade_scanner.templates.dashboard_template import generate_html_report

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return

    print("🔄 Scan requested via API...")
    try:
        mgr = get_scanner_manager()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            new_count = loop.run_until_complete(mgr.run_scan())
        finally:
            loop.close()
            asyncio.set_event_loop(None)

        media_cache = _get_media_cache()
        port = handler.server.server_address[1]
        results = [e.model_dump(by_alias=True) for e in media_cache.get()]
        media_cache.invalidate()
        generate_html_report(results, config.report_file, server_port=port)

        handler.send_response(200)
        handler.send_header("Content-type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"status": "complete", "count": new_count}).encode())
        print("✅ Rescan complete.")

    except Exception as e:
        print(f"❌ Rescan failed: {e}")
        handler.send_error(500, str(e))


def _handle_backup(handler) -> None:
    from arcade_scanner.config import SETTINGS_FILE

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return

    try:
        print("💾 Backup requested...")
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'rb') as f:
                data = f.read()

            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.send_header("Content-Disposition", 'attachment; filename="arcade_settings_backup.json"')
            handler.end_headers()
            handler.wfile.write(data)
            print("✅ Backup sent.")
        else:
            handler.send_error(404, "Settings file not found")
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        handler.send_error(500, str(e))

# ---------------------------------------------------------------------------
# POST handler — files.py has no POST endpoints; returns False to pass through
# ---------------------------------------------------------------------------

def handle_post(handler) -> bool:
    """files.py has no POST endpoints. Always returns False."""
    return False
