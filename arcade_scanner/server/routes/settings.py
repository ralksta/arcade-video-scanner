"""
routes/settings.py
------------------
Handles API endpoints for application settings, first-run setup wizard, and restore:

GET  /api/settings           -> Return merged global + user settings
POST /api/settings           -> Save global config + user-specific overrides
POST /api/setup/complete     -> Finish the first-run setup wizard
GET  /api/setup/directories  -> List /media sub-directories (setup wizard)
GET  /api/setup/status       -> Check whether setup is complete for the current user
POST /api/restore            -> Restore settings from a JSON backup file
"""

from __future__ import annotations

import json
import os


# ---------------------------------------------------------------------------
# Lazy singletons (imported inside functions to avoid circular imports)
# ---------------------------------------------------------------------------

def _get_singletons():
    from arcade_scanner.server.api_handler import (
        config,
        user_db,
        report_debouncer,
        MAX_REQUEST_SIZE,
    )
    return config, user_db, report_debouncer, MAX_REQUEST_SIZE


# ---------------------------------------------------------------------------
# GET /api/settings
# ---------------------------------------------------------------------------

def handle_get_settings(handler) -> None:
    """Return merged global + user-specific settings as JSON."""
    config, user_db, _, _ = _get_singletons()

    settings_dump = config.settings.model_dump()

    user_name = handler.get_current_user()
    if user_name:
        u = user_db.get_user(user_name)
        if u:
            settings_dump["smart_collections"]    = u.data.smart_collections
            settings_dump["scan_targets"]         = u.data.scan_targets
            settings_dump["exclude_paths"]        = u.data.exclude_paths
            settings_dump["available_tags"]       = u.data.available_tags
            # User-specific overrides
            settings_dump["enable_image_scanning"] = getattr(u.data, "scan_images", False)
            settings_dump["sensitive_dirs"]        = u.data.sensitive_dirs
            settings_dump["sensitive_tags"]        = u.data.sensitive_tags
            settings_dump["sensitive_collections"] = u.data.sensitive_collections
        else:
            settings_dump["smart_collections"]     = []
            settings_dump["scan_targets"]          = []
            settings_dump["exclude_paths"]         = []
            settings_dump["available_tags"]        = []
            settings_dump["enable_image_scanning"] = False
    else:
        settings_dump["smart_collections"] = []
        settings_dump["scan_targets"]      = []
        settings_dump["exclude_paths"]     = []
        settings_dump["available_tags"]    = []

    # Docker detection
    settings_dump["is_docker"] = bool(os.getenv("CONFIG_DIR"))

    handler.send_response(200)
    handler.send_header("Content-type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps(settings_dump, default=str).encode())


# ---------------------------------------------------------------------------
# POST /api/settings
# ---------------------------------------------------------------------------

def handle_post_settings(handler) -> None:
    """Save global config and user-specific overrides, then schedule report rebuild."""
    config, user_db, report_debouncer, MAX_REQUEST_SIZE = _get_singletons()

    try:
        content_length = int(handler.headers.get("Content-Length", 0))
        if content_length > MAX_REQUEST_SIZE:
            handler.send_error(413, "Request payload too large")
            return

        post_body = handler.rfile.read(content_length)
        new_settings = json.loads(post_body)

        # Pop user-specific fields before saving to global config
        user_collections        = new_settings.pop("smart_collections", None)
        user_targets            = new_settings.pop("scan_targets", None)
        user_excludes           = new_settings.pop("exclude_paths", None)
        user_tags               = new_settings.pop("available_tags", None)

        # Frontend may send either key name
        user_scan_images = new_settings.pop("scan_images", None)
        if user_scan_images is None:
            user_scan_images = new_settings.pop("enable_image_scanning", None)

        user_sensitive_dirs        = new_settings.pop("sensitive_dirs", None)
        user_sensitive_tags        = new_settings.pop("sensitive_tags", None)
        user_sensitive_collections = new_settings.pop("sensitive_collections", None)

        if config.save(new_settings):
            user_name = handler.get_current_user()
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

            # Schedule HTML report regeneration (picks up theme changes, etc.)
            try:
                current_port = config.PORT if hasattr(config, "PORT") else 8000
                report_debouncer.schedule(current_port)
                print("✅ HTML Report scheduled for regeneration with new settings")
            except Exception as e:
                print(f"⚠️ Settings saved but report regen scheduling failed: {e}")

            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": True}).encode())
        else:
            handler.send_error(500, "Failed to save settings")

    except Exception as e:
        print(f"Error saving settings: {e}")
        handler.send_error(500)


# ---------------------------------------------------------------------------
# GET /api/setup/directories
# ---------------------------------------------------------------------------

def handle_get_setup_directories(handler) -> None:
    """List available directories under /media for the setup wizard."""
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401)
        return

    directories = []
    media_root = "/media"

    try:
        if os.path.exists(media_root) and os.path.isdir(media_root):
            # Root /media itself
            try:
                total_size = sum(
                    os.path.getsize(os.path.join(media_root, f))
                    for f in os.listdir(media_root)
                    if os.path.isfile(os.path.join(media_root, f))
                )
                file_count = sum(
                    1
                    for f in os.listdir(media_root)
                    if os.path.isfile(os.path.join(media_root, f))
                )
                directories.append({
                    "path": media_root,
                    "size_bytes": total_size,
                    "file_count": file_count,
                    "is_root": True,
                })
            except PermissionError:
                pass

            # Immediate sub-directories
            for item in os.listdir(media_root):
                item_path = os.path.join(media_root, item)
                if os.path.isdir(item_path):
                    try:
                        total_size = sum(
                            os.path.getsize(os.path.join(dp, f))
                            for dp, dn, filenames in os.walk(item_path)
                            for f in filenames
                        )
                        file_count = sum(
                            len(filenames)
                            for dp, dn, filenames in os.walk(item_path)
                        )
                        directories.append({
                            "path": item_path,
                            "name": item,
                            "size_bytes": total_size,
                            "file_count": file_count,
                            "is_root": False,
                        })
                    except (PermissionError, OSError):
                        pass
    except Exception as e:
        print(f"⚠️ Error scanning /media: {e}")

    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps({"directories": directories}).encode())


# ---------------------------------------------------------------------------
# GET /api/setup/status
# ---------------------------------------------------------------------------

def handle_get_setup_status(handler) -> None:
    """Return whether the first-run setup wizard has been completed."""
    _, user_db, _, _ = _get_singletons()

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401)
        return

    u = user_db.get_user(user_name)
    setup_complete = getattr(u.data, "setup_complete", True) if u else True

    handler.send_response(200)
    handler.send_header("Content-Type", "application/json")
    handler.end_headers()
    handler.wfile.write(json.dumps({"setup_complete": setup_complete}).encode())


# ---------------------------------------------------------------------------
# POST /api/setup/complete
# ---------------------------------------------------------------------------

def handle_post_setup_complete(handler) -> None:
    """Finish the first-run setup wizard and persist the user's choices."""
    _, user_db, _, _ = _get_singletons()

    try:
        content_len = int(handler.headers.get("Content-Length", 0))
        post_body   = handler.rfile.read(content_len)
        payload     = json.loads(post_body)

        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401)
            return

        u = user_db.get_user(user_name)
        if not u:
            handler.send_error(401)
            return

        scan_targets = payload.get("scan_targets", [])
        scan_images  = payload.get("scan_images", False)

        if not scan_targets:
            handler.send_error(400, "At least one scan target required")
            return

        u.data.scan_targets   = scan_targets
        u.data.scan_images    = scan_images
        u.data.setup_complete = True
        user_db.add_user(u)

        print(f"✅ Setup completed for {user_name}: {scan_targets}")

        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"success": True}).encode())

    except Exception as e:
        print(f"Error completing setup: {e}")
        handler.send_error(500)


# ---------------------------------------------------------------------------
# POST /api/restore
# ---------------------------------------------------------------------------

def handle_post_restore(handler) -> None:
    """Restore application settings from a JSON backup sent by the client."""
    config, _, _, MAX_REQUEST_SIZE = _get_singletons()

    try:
        content_length = int(handler.headers.get("Content-Length", 0))

        if content_length > MAX_REQUEST_SIZE:
            handler.send_error(413, "Request Entity Too Large")
            return

        body = handler.rfile.read(content_length).decode("utf-8")
        try:
            new_settings = json.loads(body)
        except json.JSONDecodeError:
            handler.send_error(400, "Invalid JSON format")
            return

        print("♻️ Restoring settings from backup...")

        if config.save(new_settings):
            print("✅ Settings restored successfully.")
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": True}).encode())
        else:
            print("❌ Failed to save restored settings.")
            handler.send_error(500, "Failed to save settings")

    except Exception as e:
        print(f"❌ Restore exception: {e}")
        handler.send_error(500, str(e))


# ---------------------------------------------------------------------------
# POST /api/settings/remove-photos
# ---------------------------------------------------------------------------

def handle_post_remove_photos(handler) -> None:
    """Remove all photo entries from the DB (called after user confirms the modal)."""
    import json
    from arcade_scanner.database.sqlite_store import db

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401)
        return

    try:
        deleted = db.delete_all_photos()
        print(f"🗑️ Removed {deleted} photo entries from DB for user '{user_name}'")

        # Invalidate the media cache so the UI reflects the change immediately
        try:
            from arcade_scanner.server.api_handler import _media_cache
            _media_cache.invalidate()
        except Exception:
            pass  # Cache invalidation is best-effort

        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps({"success": True, "deleted": deleted}).encode())

    except Exception as e:
        print(f"❌ remove-photos error: {e}")
        handler.send_error(500, str(e))

# ---------------------------------------------------------------------------
# Router interface — called by api_handler.py
# ---------------------------------------------------------------------------

def handle_get(handler) -> bool:
    """Dispatch GET requests for /api/settings and /api/setup/* endpoints."""
    path = handler.path.split("?")[0]

    if path == "/api/settings":
        handle_get_settings(handler)
        return True

    if path == "/api/setup/directories":
        handle_get_setup_directories(handler)
        return True

    if path == "/api/setup/status":
        handle_get_setup_status(handler)
        return True

    return False


def handle_post(handler) -> bool:
    """Dispatch POST requests for /api/settings and /api/setup/* endpoints."""
    path = handler.path.split("?")[0]

    if path == "/api/settings":
        handle_post_settings(handler)
        return True

    if path == "/api/setup/complete":
        handle_post_setup_complete(handler)
        return True

    if path == "/api/restore":
        handle_post_restore(handler)
        return True

    if path == "/api/settings/remove-photos":
        handle_post_remove_photos(handler)
        return True

    return False
