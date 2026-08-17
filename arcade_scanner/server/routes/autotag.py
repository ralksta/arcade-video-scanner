# arcade_scanner/server/routes/autotag.py
"""Auto-tagging rules: CRUD (GET/POST /api/autotag/rules) + manual run."""
import json
import uuid

from arcade_scanner.config import MAX_REQUEST_SIZE
from arcade_scanner.core.auto_tagger import run_auto_tag_rules
from arcade_scanner.core.criteria_eval import narrows_the_selection
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
            # Ein Kriterium, das nichts einschränkt, passt auf jede Datei der
            # Bibliothek. Die Regel würde den Tag an alles schreiben, und weil
            # jeder Tag nur einmal vergeben wird, wäre er anschliessend nur
            # einzeln von Hand wieder zu entfernen. Ein leeres Objekt reicht
            # dafür — und ein Tippfehler im Schlüsselnamen ebenso.
            if not narrows_the_selection(criteria):
                handler.send_error(
                    400,
                    "criteria must narrow the selection - a rule that matches "
                    "everything would tag the entire library"
                )
                return True
            rule = {"id": uuid.uuid4().hex,
                    "name": str(body.get("name") or tag),
                    "tag": tag, "criteria": criteria, "enabled": True}
            # Über update_user(): Der Datensatz wird als Ganzes zurückgeschrieben,
            # eine gleichzeitige Anfrage desselben Kontos verwürfe sonst die
            # Änderung der jeweils anderen.
            user_db.update_user(user_name, lambda usr: usr.data.auto_tag_rules.append(rule))
            send_json(handler, {"success": True, "rule": rule})
            return True

        if action == "delete":
            rule_id = str(body.get("id") or "")
            outcome = {"removed": False}

            def drop_rule(usr):
                before = len(usr.data.auto_tag_rules)
                usr.data.auto_tag_rules = [
                    r for r in usr.data.auto_tag_rules if r.get("id") != rule_id
                ]
                outcome["removed"] = len(usr.data.auto_tag_rules) != before

            user_db.update_user(user_name, drop_rule)
            if not outcome["removed"]:
                handler.send_error(404, "Rule not found")
                return True
            media_db.clear_auto_tag_applied(user_name, rule_id)
            send_json(handler, {"success": True})
            return True

        if action == "toggle":
            rule_id = str(body.get("id") or "")
            outcome = {"rule": None}

            def flip(usr):
                for r in usr.data.auto_tag_rules:
                    if r.get("id") == rule_id:
                        r["enabled"] = bool(body.get("enabled"))
                        outcome["rule"] = r
                        break

            user_db.update_user(user_name, flip)
            if outcome["rule"] is None:
                handler.send_error(404, "Rule not found")
                return True
            send_json(handler, {"success": True, "rule": outcome["rule"]})
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
