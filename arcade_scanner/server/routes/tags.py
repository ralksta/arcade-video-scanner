import json
import os
from urllib.parse import urlparse, parse_qs

def _get_deps():
    from arcade_scanner.server.api_handler import user_db, MAX_REQUEST_SIZE
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
                 u = user_db.get_user(user_name)
                 if u:
                     current_tags = list(u.data.available_tags)
                     updated_tags = [t for t in current_tags if t.get("name") != tag_name]
                     u.data.available_tags = updated_tags
                     
                     for path, tags in u.data.tags.items():
                         if tag_name in tags:
                             u.data.tags[path] = [t for t in tags if t != tag_name]
                     
                     user_db.add_user(u)
                     print(f"🏷️ Deleted tag for user {user_name}: {tag_name}")
                
                 handler.send_response(200)
                 handler.send_header("Content-Type", "application/json")
                 handler.end_headers()
                 handler.wfile.write(json.dumps({"success": True}).encode("utf-8"))
                 return True
            else:
                handler.send_error(400, "Missing name for delete")
                return True

        u = user_db.get_user(user_name)
        tags = u.data.available_tags if u else []
        
        handler.send_response(200)
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(json.dumps(tags).encode("utf-8"))
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

            u = user_db.get_user(user_name)
            if not u:
                handler.send_error(404, "User not found")
                return True

            current_tags = u.data.available_tags
            existing_names = [t.get("name", "").lower() for t in current_tags]
            
            if tag_name.lower() in existing_names:
                handler.send_error(409, "Tag already exists")
                return True
            
            new_tag = {"name": tag_name, "color": tag_color}
            u.data.available_tags.append(new_tag)
            user_db.add_user(u)
            
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
            u = user_db.get_user(user_name)
            if u:
                u.data.tags[abs_path] = tags
                user_db.add_user(u)
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
            
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps({"success": True}).encode("utf-8"))
        except Exception as e:
            print(f"Error updating tag: {e}")
            handler.send_error(500, str(e))
        return True

    return False
