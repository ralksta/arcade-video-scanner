import json
import os
from urllib.parse import parse_qs, urlparse

from arcade_scanner.server.response_helpers import send_json


def _get_deps():
    from arcade_scanner.server.api_handler import MAX_REQUEST_SIZE, user_db
    return user_db, MAX_REQUEST_SIZE

def handle_get(handler) -> bool:
    if handler.path.startswith("/api/tags"):
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401)
            return True

        user_db, _ = _get_deps()
        params = parse_qs(urlparse(handler.path).query)
        action = params.get("action", [None])[0]

        if action == "delete":
            tag_name = params.get("name", [None])[0]
            if tag_name:
                 def drop_tag(u):
                     u.data.available_tags = [
                         t for t in u.data.available_tags if t.get("name") != tag_name
                     ]
                     for path, tags in u.data.tags.items():
                         if tag_name in tags:
                             u.data.tags[path] = [t for t in tags if t != tag_name]

                 if user_db.update_user(user_name, drop_tag):
                     print(f"🏷️ Deleted tag for user {user_name}: {tag_name}")

                 send_json(handler, {"success": True})
                 return True
            else:
                handler.send_error(400, "Missing name for delete")
                return True

        u = user_db.get_user(user_name)
        tags = u.data.available_tags if u else []

        send_json(handler, tags)
        return True

    return False


def handle_post(handler) -> bool:
    if handler.path == "/api/tags":
        try:
            user_db, MAX_REQUEST_SIZE = _get_deps()
            content_length = int(handler.headers.get("Content-Length", 0))
            if content_length > MAX_REQUEST_SIZE:
                handler.send_error(413, "Request Entity Too Large")
                return True
            if content_length == 0:
                handler.send_error(400, "Empty request body")
                return True

            body = handler.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            tag_name = data.get("name", "").strip()
            tag_color = data.get("color", "#00ffd0")

            if not tag_name:
                handler.send_error(400, "Tag name is required")
                return True

            user_name = handler.get_current_user()
            if not user_name:
                handler.send_error(401, "Unauthorized")
                return True

            # Die Prüfung auf einen bereits vorhandenen Namen gehört mit unter
            # die Sperre: Getrennt gelesen könnten zwei gleichzeitige Anfragen
            # beide „gibt es noch nicht" feststellen und den Tag doppelt
            # anlegen.
            outcome = {"duplicate": False}
            new_tag = {"name": tag_name, "color": tag_color}

            def add_tag(u):
                existing = [t.get("name", "").lower() for t in u.data.available_tags]
                if tag_name.lower() in existing:
                    outcome["duplicate"] = True
                    return
                u.data.available_tags.append(new_tag)

            if not user_db.update_user(user_name, add_tag):
                handler.send_error(404, "User not found")
                return True

            if outcome["duplicate"]:
                handler.send_error(409, "Tag already exists")
                return True

            print(f"🏷️ Created tag: {tag_name} ({tag_color})")
            handler.send_response(201)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(new_tag).encode("utf-8"))

        except json.JSONDecodeError:
            handler.send_error(400, "Invalid JSON")
        except Exception as e:
            print(f"❌ Error creating tag: {e}")
            handler.send_error(500, str(e))
        return True

    elif handler.path.startswith("/api/video/tags"):
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401)
            return True

        try:
            user_db, MAX_REQUEST_SIZE = _get_deps()
            content_length = int(handler.headers.get("Content-Length", 0))
            if content_length > MAX_REQUEST_SIZE:
                handler.send_error(413, "Request Entity Too Large")
                return True

            body = handler.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)

            video_path = data.get("path")
            tags = data.get("tags", [])

            if not video_path:
                 handler.send_error(400, "Path required")
                 return True

            abs_path = os.path.abspath(video_path)
            def set_tags(u):
                u.data.tags[abs_path] = tags

            if user_db.update_user(user_name, set_tags):
                print(f"Updated tags for {user_name} on {os.path.basename(abs_path)}: {tags}")

            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": True, "tags": tags}).encode("utf-8"))
        except Exception as e:
            print(f"Error setting tags: {e}")
            handler.send_error(500, str(e))
        return True

    elif handler.path == "/api/tags/update":
        try:
            user_name = handler.get_current_user()
            if not user_name:
                handler.send_error(401)
                return True

            user_db, MAX_REQUEST_SIZE = _get_deps()
            data = json.loads(handler.rfile.read(int(handler.headers.get("Content-Length", 0))))
            tag_name = data.get("name")
            new_shortcut = data.get("shortcut")

            if not tag_name:
                handler.send_error(400, "Missing tag name")
                return True

            outcome = {"found": False}

            def set_shortcut(u):
                for tag in u.data.available_tags:
                    if tag.get("name") == tag_name:
                        tag["shortcut"] = new_shortcut
                        outcome["found"] = True
                        break

            if not user_db.update_user(user_name, set_shortcut):
                handler.send_error(404, "User not found")
                return True

            if not outcome["found"]:
                handler.send_error(404, "Tag not found")
                return True

            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": True}).encode("utf-8"))
        except Exception as e:
            print(f"Error updating tag: {e}")
            handler.send_error(500, str(e))
        return True

    return False
