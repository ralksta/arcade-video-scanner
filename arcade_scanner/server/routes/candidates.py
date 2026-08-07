"""GET /api/candidates — re-encode candidates ranked by expected savings."""
import os
from urllib.parse import parse_qs, urlparse

from arcade_scanner.core.optimization_advisor import EncodeHistory, build_candidates
from arcade_scanner.server.response_helpers import send_json

VALID_CODECS = {"hevc", "av1"}

# Module-level: EncodeHistory caches by mtime, so reuse across requests.
_history = EncodeHistory()


def _get_deps():
    from arcade_scanner.server.api_handler import db, user_db
    return db, user_db


def handle_get(handler) -> bool:
    parsed = urlparse(handler.path)
    if parsed.path != "/api/candidates":
        return False

    user_name = handler.get_current_user()
    if not user_name:
        handler.send_error(401, "Unauthorized")
        return True

    params = parse_qs(parsed.query)
    codec = params.get("codec", ["hevc"])[0]
    if codec not in VALID_CODECS:
        handler.send_error(400, "Invalid codec (hevc|av1)")
        return True
    try:
        limit = max(1, min(int(params.get("limit", ["100"])[0]), 500))
    except ValueError:
        limit = 100

    try:
        db, user_db = _get_deps()
        exclude = set(db.get_active_queue_paths())
        u = user_db.get_user(user_name)
        if u and u.data.vaulted:
            exclude.update(os.path.abspath(p) for p in u.data.vaulted)
        payload = build_candidates(db.get_all(), codec, _history, exclude, limit)
        send_json(handler, payload)
    except Exception as e:
        print(f"❌ Error building candidates: {e}")
        handler.send_error(500, str(e))
    return True
