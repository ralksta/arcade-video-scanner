"""routes/tags.py — Tag-System-Endpunkte (GET + POST).

Extrahiert aus api_handler.py:
  GET  /api/tags          → alle Tags des Benutzers; ?action=delete löscht einen Tag
  GET  /api/video/tags    → (deferred — serviert via GET /api/videos-Endpunkt)
  POST /api/tags          → neuen Tag erstellen
  POST /api/tags/update   → Tag-Shortcut aktualisieren
  POST /api/video/tags    → Tags für ein Video setzen
"""
from __future__ import annotations

import os
from urllib.parse import urlparse, parse_qs

from arcade_scanner.database import user_db
from arcade_scanner.server.response_helpers import (
    send_json,
    send_json_error,
    require_auth,
    read_json_body,
)


def handle_get(handler) -> bool:
    """Behandelt GET-Requests für Tag-Endpunkte.

    Returns:
        True wenn der Request behandelt wurde, sonst False.
    """
    path = handler.path

    # GET /api/tags  (inkl. ?action=delete)
    if path.startswith("/api/tags"):
        user_name = require_auth(handler)
        if user_name is None:
            return True

        params = parse_qs(urlparse(path).query)
        action = params.get("action", [None])[0]

        if action == "delete":
            tag_name = params.get("name", [None])[0]
            if not tag_name:
                handler.send_error(400, "Missing name for delete")
                return True

            u = user_db.get_user(user_name)
            if u:
                u.data.available_tags = [
                    t for t in u.data.available_tags if t.get("name") != tag_name
                ]
                # Auch aus allen Videos des Users entfernen
                for video_path, tags in u.data.tags.items():
                    if tag_name in tags:
                        u.data.tags[video_path] = [t for t in tags if t != tag_name]
                user_db.add_user(u)
                print(f"🏷️ Deleted tag for user {user_name}: {tag_name}")

            send_json(handler, {"success": True})
            return True

        # Default: alle Tags zurückgeben
        u = user_db.get_user(user_name)
        tags = u.data.available_tags if u else []
        send_json(handler, tags)
        return True

    return False


def handle_post(handler) -> bool:
    """Behandelt POST-Requests für Tag-Endpunkte.

    Returns:
        True wenn der Request behandelt wurde, sonst False.
    """
    path = handler.path

    # POST /api/tags — neuen Tag erstellen
    if path == "/api/tags":
        try:
            user_name = require_auth(handler)
            if user_name is None:
                return True

            data = read_json_body(handler)
            if data is None:
                return True

            tag_name = str(data.get("name", "")).strip()
            tag_color = data.get("color", "#00ffd0")

            if not tag_name:
                handler.send_error(400, "Tag name is required")
                return True

            u = user_db.get_user(user_name)
            if not u:
                handler.send_error(404, "User not found")
                return True

            existing_names = [t.get("name", "").lower() for t in u.data.available_tags]
            if tag_name.lower() in existing_names:
                handler.send_error(409, "Tag already exists")
                return True

            new_tag = {"name": tag_name, "color": tag_color}
            u.data.available_tags.append(new_tag)
            user_db.add_user(u)
            print(f"🏷️ Created tag: {tag_name} ({tag_color})")
            send_json(handler, new_tag, status=201)

        except Exception as e:
            print(f"❌ Error creating tag: {e}")
            handler.send_error(500, str(e))
        return True

    # POST /api/tags/update — Shortcut eines Tags ändern
    if path == "/api/tags/update":
        try:
            user_name = require_auth(handler)
            if user_name is None:
                return True

            data = read_json_body(handler)
            if data is None:
                return True

            tag_name = data.get("name")
            new_shortcut = data.get("shortcut")

            if not tag_name:
                handler.send_error(400, "Missing tag name")
                return True

            u = user_db.get_user(user_name)
            if not u:
                handler.send_error(404, "User not found")
                return True

            tag_found = False
            for tag in u.data.available_tags:
                if tag.get("name") == tag_name:
                    tag["shortcut"] = new_shortcut
                    tag_found = True
                    break

            if not tag_found:
                handler.send_error(404, "Tag not found")
                return True

            user_db.add_user(u)
            send_json(handler, {"success": True})

        except Exception as e:
            print(f"Error updating tag: {e}")
            handler.send_error(500, str(e))
        return True

    # POST /api/video/tags — Tags für ein Video setzen
    if path.startswith("/api/video/tags"):
        user_name = require_auth(handler)
        if user_name is None:
            return True

        try:
            data = read_json_body(handler)
            if data is None:
                return True

            video_path = data.get("path")
            tags = data.get("tags", [])

            if not video_path:
                handler.send_error(400, "Path required")
                return True

            abs_path = os.path.abspath(video_path)
            u = user_db.get_user(user_name)
            if u:
                u.data.tags[abs_path] = tags
                user_db.add_user(u)
                print(f"Updated tags for {user_name} on {os.path.basename(abs_path)}: {tags}")

            send_json(handler, {"success": True, "tags": tags})

        except Exception as e:
            print(f"Error setting tags: {e}")
            handler.send_error(500, str(e))
        return True

    return False
