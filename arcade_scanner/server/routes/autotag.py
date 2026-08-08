# arcade_scanner/server/routes/autotag.py
"""Auto-tagging rules: CRUD (GET/POST /api/autotag/rules) + manual run."""
import json
import uuid

from arcade_scanner.config import MAX_REQUEST_SIZE
from arcade_scanner.core.auto_tagger import run_auto_tag_rules
from arcade_scanner.server.response_helpers import send_json


def _get_deps():
    from arcade_scanner.server.api_handler import db, user_db
    return db, user_db


def _read_body(handler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length <= 0 or length > MAX_REQUEST_SIZE:
        return {}
    data = json.loads(handler.rfile.read(length).decode("utf-8"))
    return data if isinstance(data, dict) else {}


def handle_get(handler) -> bool:
    if handler.path != "/api/autotag/rules":
        return False
    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return True
    _, user_db = _get_deps()
    u = user_db.get_user(user_name)
    rules = u.data.auto_tag_rules if u else []
    send_json(handler, {"rules": rules})
    return True


def handle_post(handler) -> bool:
    if handler.path == "/api/autotag/rules":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True
        try:
            body = _read_body(handler)
        except (json.JSONDecodeError, ValueError):
            handler.send_error(400, "Invalid JSON")
            return True

        media_db, user_db = _get_deps()
        u = user_db.get_user(user_name)
        if not u:
            handler.send_error(401, "Unauthorized")
            return True

        action = body.get("action")
        if action == "create":
            tag = str(body.get("tag") or "").strip()
            criteria = body.get("criteria")
            if not tag or not isinstance(criteria, dict):
                handler.send_error(400, "tag and criteria required")
                return True
            rule = {"id": uuid.uuid4().hex,
                    "name": str(body.get("name") or tag),
                    "tag": tag, "criteria": criteria, "enabled": True}
            u.data.auto_tag_rules.append(rule)
            user_db.add_user(u)
            send_json(handler, {"success": True, "rule": rule})
            return True

        if action == "delete":
            rule_id = str(body.get("id") or "")
            before = len(u.data.auto_tag_rules)
            u.data.auto_tag_rules = [r for r in u.data.auto_tag_rules if r.get("id") != rule_id]
            if len(u.data.auto_tag_rules) == before:
                handler.send_error(404, "Rule not found")
                return True
            media_db.clear_auto_tag_applied(user_name, rule_id)
            user_db.add_user(u)
            send_json(handler, {"success": True})
            return True

        if action == "toggle":
            rule_id = str(body.get("id") or "")
            for r in u.data.auto_tag_rules:
                if r.get("id") == rule_id:
                    r["enabled"] = bool(body.get("enabled"))
                    user_db.add_user(u)
                    send_json(handler, {"success": True, "rule": r})
                    return True
            handler.send_error(404, "Rule not found")
            return True

        handler.send_error(400, "Unknown action")
        return True

    if handler.path == "/api/autotag/run":
        user_name = handler.get_current_user()
        if not user_name:
            handler.send_error(401, "Unauthorized")
            return True
        try:
            media_db, user_db = _get_deps()
            results = run_auto_tag_rules(user_name, user_db=user_db, media_db=media_db)
            send_json(handler, {"success": True, "results": results,
                                "total": sum(results.values())})
        except Exception as e:
            print(f"❌ Auto-tag run failed: {e}")
            handler.send_error(500, str(e))
        return True

    return False
