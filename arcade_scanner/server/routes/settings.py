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
import time

from arcade_scanner.server.response_helpers import send_json

# ---------------------------------------------------------------------------
# Lazy singletons (imported inside functions to avoid circular imports)
# ---------------------------------------------------------------------------

def _get_singletons():
    from arcade_scanner.server.api_handler import (
        MAX_REQUEST_SIZE,
        config,
        report_debouncer,
        user_db,
    )
    return config, user_db, report_debouncer, MAX_REQUEST_SIZE


# ---------------------------------------------------------------------------
# GET /api/settings
# ---------------------------------------------------------------------------

def handle_get_settings(handler) -> None:
    """Return merged global + user-specific settings as JSON."""
    config, user_db, _, _ = _get_singletons()

    # Anonym gab es hier die globalen Einstellungen: gespeicherte Ansichten
    # samt Filtern, proxy_root, review_dir, ffmpeg-Pfade — die
    # Verzeichnisstruktur des Servers. Kein Client fragt vor der Anmeldung.
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return

    settings_dump = config.settings.model_dump()

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

    # Der Dialog blendet globale Abschnitte für Nicht-Admins aus — der Server
    # verwirft deren globale Schlüssel ohnehin (handle_post_settings).
    account = user_db.get_user(user_name)
    settings_dump["is_admin"] = bool(account is not None and getattr(account, "is_admin", False))

    # Docker detection
    settings_dump["is_docker"] = bool(os.getenv("CONFIG_DIR"))

    # Welche der eigenen Scan-Ziele es gerade nicht gibt.
    #
    # Der Scanner weiß das längst und schreibt es ins Protokoll — dorthin, wo
    # niemand hinsieht, der den Server als Dienst laufen lässt. Der Nutzer
    # sieht stattdessen eine vollständige Bibliothek, in der nichts abspielt,
    # und das sieht nach einem kaputten Programm aus statt nach einem nicht
    # eingehängten Laufwerk.
    #
    # Ausdrücklich nur die Ziele **dieses** Kontos: Die Liste geht an den
    # Browser, und fremde Pfade gehören dort nicht hinein.
    settings_dump["unavailable_targets"] = _unreachable(
        settings_dump.get("scan_targets") or [])

    send_json(handler, settings_dump)


def _unreachable(targets) -> list:
    """Die Teilmenge der Pfade, die es gerade nicht gibt.

    Fehler beim Nachsehen (fehlende Rechte auf einem Elternverzeichnis, ein
    hängender Netzwerk-Mount) gelten hier **nicht** als „nicht vorhanden": Eine
    falsche Warnung über ein in Wahrheit erreichbares Ziel wäre schlimmer als
    gar keine.
    """
    fehlend = []
    for target in targets:
        if not target:
            continue
        try:
            if not os.path.exists(os.path.abspath(os.path.expanduser(target))):
                fehlend.append(target)
        except OSError:
            continue
    return fehlend


# ---------------------------------------------------------------------------
# POST /api/settings
# ---------------------------------------------------------------------------

# Globale Schlüssel, die jedes Konto schreiben darf. Gespeicherte Ansichten
# legt jeder an; nutzereigen werden sie mit Phase 2 (UMSETZUNGSPLAN).
SHARED_KEYS_FOR_EVERYONE = frozenset({"saved_views"})


def handle_post_settings(handler) -> None:
    """Save global config and user-specific overrides, then schedule report rebuild."""
    config, user_db, report_debouncer, MAX_REQUEST_SIZE = _get_singletons()

    # Sitzungsprüfung vor allem anderen.
    #
    # Sie stand bisher *hinter* `config.save(new_settings)` — eine anonyme
    # Anfrage konnte also die globalen Einstellungen schreiben (Scan-Schwellen,
    # ffmpeg-Pfade, proxy_root, review_dir) und scheiterte erst danach still am
    # fehlenden Nutzer. Es gibt kein globales Auth-Gate in diesem Server; jede
    # Route prüft selbst, und diese prüfte zu spät.
    #
    # Der Mangel war seit einem früheren Nachtlauf als xfail in
    # tests/test_routes_settings.py dokumentiert und ungefixt geblieben.
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return

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

        # Globale Schlüssel nur für Admins. Vorher schrieb jedes angemeldete
        # Konto Scan-Schwellen, proxy_root, review_dir und ffprobe_path —
        # also auch, welches Programm der Server ausführt. Ein 403 ginge
        # nicht: Der Dialog schickt bei jedem Speichern alles mit, die
        # eigenen Felder eingeschlossen. Also verwerfen und nennen.
        account = user_db.get_user(user_name)
        ignored: list = []
        if not (account is not None and getattr(account, "is_admin", False)):
            ignored = sorted(k for k in new_settings if k not in SHARED_KEYS_FOR_EVERYONE)
            for key in ignored:
                new_settings.pop(key)

        if config.save(new_settings):
            if user_name:
                # Über update_user(): Der Datensatz wird als Ganzes
                # zurückgeschrieben, eine gleichzeitige Anfrage desselben
                # Kontos verwürfe sonst die Änderung der jeweils anderen.
                changes = {
                    "smart_collections": user_collections,
                    "scan_targets": user_targets,
                    "exclude_paths": user_excludes,
                    "available_tags": user_tags,
                    "scan_images": user_scan_images,
                    "sensitive_dirs": user_sensitive_dirs,
                    "sensitive_tags": user_sensitive_tags,
                    "sensitive_collections": user_sensitive_collections,
                }
                pending = {k: v for k, v in changes.items() if v is not None}

                if pending:
                    def apply_settings(u):
                        for field, value in pending.items():
                            setattr(u.data, field, value)

                    user_db.update_user(user_name, apply_settings)

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
            handler.wfile.write(json.dumps({"success": True, "ignored": ignored}).encode())
        else:
            handler.send_error(500, "Failed to save settings")

    except Exception as e:
        print(f"Error saving settings: {e}")
        handler.send_error(500)


# ---------------------------------------------------------------------------
# GET /api/setup/directories
# ---------------------------------------------------------------------------

# Wurzel, unter der der Einrichtungs-Assistent Ordner vorschlägt (Docker-Mount).
SETUP_MEDIA_ROOT = "/media"

# Gesamtbudget für das Zählen. Die Antwort lief vorher über die ganze
# Bibliothek, zweimal: auf dieser Installation 711.512 Dateien, über 30 s, bei
# jedem Aufruf. Der Assistent braucht eine Größenordnung, keine Inventur.
SETUP_SCAN_BUDGET_SEC = 3.0


def _summarize_directory(path: str, deadline: float) -> tuple[int, int, bool]:
    """Größe, Dateizahl und ob vollständig gezählt — in **einem** Durchlauf.

    Eine Datei, die sich nicht messen lässt (während des Laufs verschwunden,
    etwa eine `.part`-Datei des Optimierers), wird übersprungen. Vorher warf
    sie den ganzen Ordner aus der Liste.
    """
    size = count = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        if time.monotonic() > deadline:
            return size, count, False
        for name in filenames:
            try:
                size += os.lstat(os.path.join(dirpath, name)).st_size
            except OSError:
                continue
            count += 1
    return size, count, True


def handle_get_setup_directories(handler) -> None:
    """List available directories under /media for the setup wizard."""
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401)
        return

    directories = []
    media_root = SETUP_MEDIA_ROOT
    deadline = time.monotonic() + SETUP_SCAN_BUDGET_SEC

    try:
        if os.path.exists(media_root) and os.path.isdir(media_root):
            entries = sorted(os.listdir(media_root))

            # Root /media itself — nur die Dateien direkt darin
            root_size = root_count = 0
            for name in entries:
                full = os.path.join(media_root, name)
                try:
                    if os.path.isfile(full):
                        root_size += os.lstat(full).st_size
                        root_count += 1
                except OSError:
                    continue
            directories.append({
                "path": media_root,
                "size_bytes": root_size,
                "file_count": root_count,
                "is_root": True,
                "complete": True,
            })

            # Immediate sub-directories
            for item in entries:
                item_path = os.path.join(media_root, item)
                if not os.path.isdir(item_path):
                    continue
                size, count, complete = _summarize_directory(item_path, deadline)
                directories.append({
                    "path": item_path,
                    "name": item,
                    "size_bytes": size,
                    "file_count": count,
                    "is_root": False,
                    # False: Budget erschöpft, die Zahlen sind eine Untergrenze.
                    "complete": complete,
                })
    except Exception as e:
        print(f"⚠️ Error scanning /media: {e}")

    send_json(handler, {"directories": directories})


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

    send_json(handler, {"setup_complete": setup_complete})


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

        scan_targets = payload.get("scan_targets", [])
        scan_images  = payload.get("scan_images", False)

        if not scan_targets:
            handler.send_error(400, "At least one scan target required")
            return

        def finish_setup(u):
            u.data.scan_targets   = scan_targets
            u.data.scan_images    = scan_images
            u.data.setup_complete = True

        if not user_db.update_user(user_name, finish_setup):
            handler.send_error(401)
            return

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
    config, user_db, _, MAX_REQUEST_SIZE = _get_singletons()

    # Die Route hatte gar keine Prüfung: Wer den Port erreichte, überschrieb
    # ohne Anmeldung die globalen Einstellungen — darunter ffprobe_path, das
    # Programm, das der Scanner ausführt. POST /api/settings hatte denselben
    # Fehler und wurde behoben; diese Nachbar-Route behielt ihn.
    #
    # Admin, nicht nur angemeldet: Restore ersetzt, was alle Konten betrifft.
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return
    account = user_db.get_user(user_name)
    if account is None or not getattr(account, "is_admin", False):
        handler.send_error(403, "Restore requires an admin account")
        return

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
