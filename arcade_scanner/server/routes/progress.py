# arcade_scanner/server/routes/progress.py
"""Wiedergabefortschritt pro Konto — Grundlage für „Weiterschauen".

GET  /api/progress  → {"items": [{path, position, duration, watched, updated_at}]}
POST /api/progress  ← {"path", "position", "duration"}  oder  {"path", "clear": true}

Vorher lag der Fortschritt nur im localStorage des Fernsehers: Der Browser
kannte ihn nicht, und was man am TV angefangen hatte, ließ sich am Rechner
nicht fortsetzen. Die Schwellen (ab wann „angefangen", ab wann „gesehen")
stehen im Nutzer-Store, nicht hier und nicht in den Clients.
"""
import json
import os

from arcade_scanner.core.user_scope import visible_path_filter
from arcade_scanner.server.response_helpers import send_json


def _is_route(path: str) -> bool:
    # Wörtlich ausgeschrieben, damit der anonyme Rundum-Test
    # (tests/anon_sweep_server.py) die Route findet.
    return path == "/api/progress" or path.startswith("/api/progress?")


def _get_deps():
    from arcade_scanner.config import MAX_REQUEST_SIZE
    from arcade_scanner.server.api_handler import db, user_db
    return db, user_db, MAX_REQUEST_SIZE


def handle_get(handler) -> bool:
    if not _is_route(handler.path):
        return False

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return True

    _media_db, user_db, _ = _get_deps()
    user = user_db.get_user(user_name)
    if user is None:
        handler.send_error(503, "User data unavailable")
        return True

    # Ein Pfad, der dem Konto inzwischen nicht mehr gehört (Scan-Ziel
    # entfernt), bleibt gespeichert, wird aber nicht mehr ausgeliefert.
    may_see = visible_path_filter(user)
    items = [p for p in user_db.list_progress(user_name) if may_see(p["path"])]
    send_json(handler, {"items": items})
    return True


def handle_post(handler) -> bool:
    if not _is_route(handler.path):
        return False

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return True

    media_db, user_db, max_size = _get_deps()
    try:
        length = int(handler.headers.get("Content-Length", 0))
    except (TypeError, ValueError):
        length = 0
    if length > max_size:
        handler.send_error(413, "Request Entity Too Large")
        return True
    try:
        data = json.loads(handler.rfile.read(length).decode("utf-8")) if length else None
    except (ValueError, UnicodeDecodeError):
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("path"), str) or not data["path"]:
        handler.send_error(400, "Missing path")
        return True

    path = os.path.abspath(data["path"])
    user = user_db.get_user(user_name)
    if user is None:
        handler.send_error(503, "User data unavailable")
        return True
    # Nur Dateien, die es gibt und die das Konto sehen darf — sonst ließe sich
    # die Tabelle mit beliebigen Pfaden füllen.
    if not visible_path_filter(user)(path) or media_db.get(path) is None:
        handler.send_error(404, "Unknown file")
        return True

    if data.get("clear"):
        user_db.clear_progress(user_name, path)
        send_json(handler, {"progress": None})
        return True

    state = user_db.save_progress(user_name, path, data.get("position"), data.get("duration"))
    send_json(handler, {"progress": state})
    return True
