# tests/test_routes_autotag.py
"""Route tests for /api/autotag/* — FakeHandler pattern from test_routes_queue.py."""
import json
from unittest.mock import MagicMock, patch

from arcade_scanner.models.user import User, UserVideoData
from arcade_scanner.server.routes import autotag


class FakeRFile:
    def __init__(self, payload=b""):
        self._payload = payload
        self._pos = 0

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._payload) - self._pos
        chunk = self._payload[self._pos:self._pos + size]
        self._pos += len(chunk)
        return chunk


class FakeHandler:
    def __init__(self, path, user="alice", body=None):
        self.path = path
        self._user = user
        payload = json.dumps(body).encode() if body is not None else b""
        self.rfile = FakeRFile(payload)
        self.headers = {"Content-Length": str(len(payload))}
        self.wfile = MagicMock()
        self.status = None
        self.error = None

    def get_current_user(self):
        return self._user

    def send_response(self, code):
        self.status = code

    def send_error(self, code, message=""):
        self.error = code

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass

    def body(self):
        raw = b"".join(c.args[0] for c in self.wfile.write.call_args_list)
        return json.loads(raw)


def _user(rules=()):
    return User(username="alice", password_hash="x", salt="y",
                data=UserVideoData(auto_tag_rules=list(rules)))


def _rule(rule_id="r1", tag="gopro", enabled=True):
    return {"id": rule_id, "name": tag, "tag": tag, "enabled": enabled, "criteria": {"search": tag}}


def run(handler, user=None, media_db=None, post=False):
    user = user if user is not None else _user()
    user_db = MagicMock()
    user_db.get_user.return_value = user
    media_db = media_db or MagicMock()
    with patch.object(autotag, "_get_deps", return_value=(media_db, user_db)):
        handled = autotag.handle_post(handler) if post else autotag.handle_get(handler)
    return handled, user, user_db, media_db


def test_unrelated_paths_not_handled():
    assert run(FakeHandler("/api/other"))[0] is False
    assert run(FakeHandler("/api/other", body={}), post=True)[0] is False


def test_rules_require_session():
    h = FakeHandler("/api/autotag/rules", user=None)
    handled, *_ = run(h)
    assert handled is True
    assert h.error == 401
    h2 = FakeHandler("/api/autotag/run", user=None, body={})
    handled2, *_ = run(h2, post=True)
    assert handled2 is True
    assert h2.error == 401


def test_list_rules():
    h = FakeHandler("/api/autotag/rules")
    handled, *_ = run(h, user=_user([_rule()]))
    assert handled is True
    assert h.body()["rules"][0]["tag"] == "gopro"


def test_create_rule():
    h = FakeHandler("/api/autotag/rules", body={"action": "create", "name": "GoPro",
                                                "tag": "gopro", "criteria": {"search": "gopro"}})
    handled, user, user_db, _ = run(h, post=True)
    assert handled is True
    body = h.body()
    assert body["success"] is True
    assert body["rule"]["enabled"] is True
    assert len(body["rule"]["id"]) == 32  # uuid4().hex
    assert len(user.data.auto_tag_rules) == 1
    user_db.add_user.assert_called_once()


def test_create_rejects_missing_tag():
    h = FakeHandler("/api/autotag/rules", body={"action": "create", "name": "x", "criteria": {}})
    handled, *_ = run(h, post=True)
    assert handled is True
    assert h.error == 400


def test_delete_rule_clears_bookkeeping():
    h = FakeHandler("/api/autotag/rules", body={"action": "delete", "id": "r1"})
    handled, user, user_db, media_db = run(h, user=_user([_rule()]), post=True)
    assert handled is True
    assert user.data.auto_tag_rules == []
    media_db.clear_auto_tag_applied.assert_called_once_with("alice", "r1")
    user_db.add_user.assert_called_once()


def test_toggle_rule():
    h = FakeHandler("/api/autotag/rules", body={"action": "toggle", "id": "r1", "enabled": False})
    handled, user, *_ = run(h, user=_user([_rule()]), post=True)
    assert handled is True
    assert user.data.auto_tag_rules[0]["enabled"] is False


def test_unknown_action_400():
    h = FakeHandler("/api/autotag/rules", body={"action": "frobnicate"})
    handled, *_ = run(h, post=True)
    assert handled is True
    assert h.error == 400


def test_run_endpoint():
    h = FakeHandler("/api/autotag/run", body={})
    with patch.object(autotag, "run_auto_tag_rules", return_value={"r1": 3}) as mock_run:
        handled, _, user_db, media_db = run(h, post=True)
    assert handled is True
    body = h.body()
    assert body == {"success": True, "results": {"r1": 3}, "total": 3}
    mock_run.assert_called_once_with("alice", user_db=user_db, media_db=media_db)
