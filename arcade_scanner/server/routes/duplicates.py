"""routes/duplicates.py — Duplicate-Detection-Endpunkte (GET + POST).

Extrahiert aus api_handler.py inkl. zwei Bug-Fixes:
  BUG-FIX 1: GET /api/duplicates/status referenzierte ``DUPLICATE_SCAN_STATE``
              (undefinierte globale Variable) statt ``_dup_mgr.get_state()``.
  BUG-FIX 2: POST /api/duplicates/delete fehlte ``_media_cache.invalidate()``
              nach dem Löschen — der Cache blieb veraltet.

Endpunkte:
  GET  /api/duplicates/status  → aktuellen Scan-Status abrufen
  GET  /api/duplicates         → gecachte Duplicate-Gruppen abrufen
  POST /api/duplicates/scan    → Hintergrund-Scan starten
  POST /api/duplicates/delete  → eine oder mehrere Dateien löschen
  POST /api/duplicates/clear   → Duplicate-Cache leeren
  POST /api/bulk_delete        → mehrere Dateien ohne Duplicate-Kontext löschen
"""
from __future__ import annotations

import os
import threading

from arcade_scanner.database import db, user_db
from arcade_scanner.security import is_path_allowed

from arcade_scanner.server.response_helpers import (
    send_json,
    send_json_error,
    require_auth,
    read_json_body,
)


def _get_dup_mgr():
    """Lazy-import um zirkuläre Importe zu vermeiden."""
    from arcade_scanner.server import api_handler
    return api_handler._dup_mgr


def _get_media_cache():
    from arcade_scanner.server import api_handler
    return api_handler._media_cache


def _get_bg_scan():
    from arcade_scanner.server.api_handler import background_duplicate_scan
    return background_duplicate_scan


def _get_clear_fn():
    from arcade_scanner.server.api_handler import clear_duplicate_cache
    return clear_duplicate_cache


# ---------------------------------------------------------------------------
# GET handler
# ---------------------------------------------------------------------------

def handle_get(handler) -> bool:
    """Behandelt GET-Requests für Duplicate-Endpunkte.

    Returns:
        True wenn der Request behandelt wurde, sonst False.
    """
    path = handler.path

    # GET /api/duplicates/status — BUG-FIX: war DUPLICATE_SCAN_STATE (undefined)
    if path == "/api/duplicates/status":
        state = _get_dup_mgr().get_state()
        send_json(handler, state)
        return True

    # GET /api/duplicates  — BUG-FIX: war DUPLICATE_RESULTS_CACHE (undefined)
    if path in ("/api/duplicates", "/api/duplicates/"):
        user_name = require_auth(handler)
        if user_name is None:
            return True

        try:
            dup_mgr = _get_dup_mgr()
            groups_data = dup_mgr.cache if dup_mgr.cache is not None else []

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
                    "scan_run": dup_mgr.cache is not None,
                },
                "groups": groups_data,
            }
            send_json(handler, response)
        except Exception as e:
            print(f"❌ Error returning duplicates: {e}")
            handler.send_error(500, str(e))
        return True

    return False


# ---------------------------------------------------------------------------
# POST handler
# ---------------------------------------------------------------------------

def handle_post(handler) -> bool:
    """Behandelt POST-Requests für Duplicate-Endpunkte.

    Returns:
        True wenn der Request behandelt wurde, sonst False.
    """
    path = handler.path

    # POST /api/duplicates/scan — Hintergrund-Scan starten
    if path == "/api/duplicates/scan":
        user_name = require_auth(handler)
        if user_name is None:
            return True

        dup_mgr = _get_dup_mgr()
        if dup_mgr.get_state()["is_running"]:
            handler.send_error(409, "Scan already in progress")
            return True

        # Optionalen batch_offset aus Body lesen
        batch_offset = 0
        from arcade_scanner.config import MAX_REQUEST_SIZE
        content_length = int(handler.headers.get("Content-Length", 0))
        if 0 < content_length <= MAX_REQUEST_SIZE:
            try:
                import json
                raw = handler.rfile.read(content_length)
                data = json.loads(raw)
                batch_offset = int(data.get("batch_offset", 0))
            except (ValueError, Exception) as e:
                print(f"⚠️ Could not parse duplicate scan body: {e}")

        u = user_db.get_user(user_name)
        user_targets = None
        if u and u.data.scan_targets:
            user_targets = [os.path.abspath(t) for t in u.data.scan_targets if t]

        bg_scan = _get_bg_scan()
        t = threading.Thread(target=bg_scan, args=(user_targets, batch_offset))
        t.daemon = True
        t.start()

        send_json(handler, {"status": "started", "batch_offset": batch_offset}, status=202)
        return True

    # POST /api/duplicates/delete — Dateien löschen (mit Cache-Invalidate!)
    if path == "/api/duplicates/delete":
        user_name = require_auth(handler)
        if user_name is None:
            return True

        try:
            data = read_json_body(handler)
            if data is None:
                return True

            paths_to_delete = data.get("paths", [])
            if not paths_to_delete:
                handler.send_error(400, "No paths provided")
                return True

            deleted = []
            failed = []
            total_freed_mb = 0.0

            for path_str in paths_to_delete:
                try:
                    abs_path = os.path.abspath(path_str)
                    if not is_path_allowed(abs_path):
                        failed.append({"path": path_str, "error": "Path not allowed"})
                        continue

                    if os.path.exists(abs_path):
                        size_mb = os.path.getsize(abs_path) / (1024 * 1024)
                        os.remove(abs_path)
                        db.remove(abs_path)
                        deleted.append(abs_path)
                        total_freed_mb += size_mb
                        print(f"🗑️ Deleted duplicate: {os.path.basename(abs_path)} ({size_mb:.1f} MB)")
                    else:
                        failed.append({"path": path_str, "error": "File not found"})
                except Exception as e:
                    failed.append({"path": path_str, "error": str(e)})

            if deleted:
                db.save()
                # BUG-FIX 2: Cache nach Löschen invalidieren (fehlte bisher!)
                _get_media_cache().invalidate()

            response = {
                "success": True,
                "deleted": deleted,
                "failed": failed,
                "freed_mb": round(total_freed_mb, 2),
                "freed_gb": round(total_freed_mb / 1024, 2),
            }
            send_json(handler, response)
            print(f"✅ Deleted {len(deleted)} duplicates, freed {total_freed_mb:.1f} MB")

        except Exception as e:
            print(f"❌ Error deleting duplicates: {e}")
            handler.send_error(500, str(e))
        return True

    # POST /api/duplicates/clear — Cache leeren
    if path == "/api/duplicates/clear":
        user_name = require_auth(handler)
        if user_name is None:
            return True

        _get_clear_fn()()
        send_json(handler, {"status": "cleared"})
        return True

    # POST /api/bulk_delete — allgemeines Massen-Löschen
    if path == "/api/bulk_delete":
        user_name = require_auth(handler)
        if user_name is None:
            return True

        try:
            data = read_json_body(handler)
            if data is None:
                return True

            paths_to_delete = data.get("paths", [])
            if not paths_to_delete:
                handler.send_error(400, "No paths provided")
                return True

            deleted = []
            failed = []

            for path_str in paths_to_delete:
                try:
                    abs_path = os.path.abspath(path_str)
                    if not is_path_allowed(abs_path):
                        failed.append({"path": path_str, "error": "Path not allowed"})
                        continue

                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        db.remove(abs_path)
                        deleted.append(abs_path)
                        print(f"🗑️ Bulk Deleted: {os.path.basename(abs_path)}")
                    else:
                        db.remove(abs_path)
                        failed.append({"path": path_str, "error": "File not found"})
                except Exception as e:
                    failed.append({"path": path_str, "error": str(e)})

            if deleted:
                db.save()
                _get_media_cache().invalidate()

            send_json(handler, {"success": True, "deleted": deleted, "failed": failed})
            print(f"✅ Bulk Deleted {len(deleted)} files")

        except Exception as e:
            print(f"❌ Error in bulk delete: {e}")
            handler.send_error(500, str(e))
        return True

    return False
