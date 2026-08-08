# tests/test_routes_tags.py
"""Characterization tests for arcade_scanner/server/routes/tags.py.

Written during the 2026-08-08 night hardening run. One xfail documents the
broken MAX_REQUEST_SIZE re-export on dev (removed by cf62272) without fixing
it here — the restore lands separately with PR #33.
"""
import json
from unittest.mock import MagicMock, patch

from arcade_scanner.server.routes import tags


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


def _user_deps():
    user_db = MagicMock()
    u = MagicMock()
    u.data.available_tags = [{"name": "work", "color": "#fff"}]
    u.data.tags = {}
    user_db.get_user.return_value = u
    return user_db, 1024 * 1024


def test_get_tags_anonymous_is_401():
    h = FakeHandler("/api/tags", user=None)
    assert tags.handle_get(h) is True
    assert h.error == 401


def test_unrelated_path_not_handled():
    assert tags.handle_get(FakeHandler("/api/other")) is False
    assert tags.handle_post(FakeHandler("/api/other", body={})) is False


def test_get_tags_with_session_returns_definitions():
    # Grün seit PR #33 den MAX_REQUEST_SIZE-Reexport wiederhergestellt hat
    # (cf62272 hatte ihn entfernt und /api/tags damit auf 404 gelegt).
    h = FakeHandler("/api/tags")
    assert tags.handle_get(h) is True
    assert h.status == 200


def test_get_tags_with_session_and_patched_deps():
    # Same endpoint with the broken lazy import bypassed: the handler logic
    # itself works — proving the 404 is purely the re-export regression.
    h = FakeHandler("/api/tags")
    with patch.object(tags, "_get_deps", return_value=_user_deps()):
        assert tags.handle_get(h) is True
    assert h.status == 200


def test_create_tag_anonymous_is_401():
    h = FakeHandler("/api/tags", user=None, body={"name": "neu"})
    with patch.object(tags, "_get_deps", return_value=_user_deps()):
        assert tags.handle_post(h) is True
    assert h.error == 401


def test_create_duplicate_tag_conflicts():
    h = FakeHandler("/api/tags", body={"name": "Work"})
    with patch.object(tags, "_get_deps", return_value=_user_deps()):
        assert tags.handle_post(h) is True
    assert h.error == 409


def test_set_video_tags_anonymous_is_401():
    h = FakeHandler("/api/video/tags", user=None, body={"path": "/lib/a.mp4", "tags": ["x"]})
    assert tags.handle_post(h) is True
    assert h.error == 401


def test_set_video_tags_replaces_list():
    h = FakeHandler("/api/video/tags", body={"path": "/lib/a.mp4", "tags": ["x", "y"]})
    user_db, max_size = _user_deps()
    with patch.object(tags, "_get_deps", return_value=(user_db, max_size)):
        assert tags.handle_post(h) is True
    assert h.status == 200
    u = user_db.get_user.return_value
    assert list(u.data.tags.values()) == [["x", "y"]]
    user_db.add_user.assert_called_once()
