# tests/test_routes_duplicates.py
"""Characterization tests for arcade_scanner/server/routes/duplicates.py.

Written during the 2026-08-08 night hardening run: pins session enforcement
and the public status endpoint's current behavior.
"""
import json
from unittest.mock import MagicMock, patch

from arcade_scanner.server.routes import duplicates


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


def _deps(cache=None, is_running=False):
    dup_mgr = MagicMock()
    dup_mgr.cache = cache
    dup_mgr.get_state.return_value = {"is_running": is_running}
    db = MagicMock()
    user_db = MagicMock()
    return (dup_mgr, db, user_db, 1024 * 1024, MagicMock(), MagicMock(), MagicMock(return_value=True))


def run(handler, deps=None, post=False):
    deps = deps or _deps()
    with patch.object(duplicates, "_get_deps", return_value=deps):
        handled = duplicates.handle_post(handler) if post else duplicates.handle_get(handler)
    return handled, deps


def test_status_is_public():
    # Characterization: /api/duplicates/status has NO session check — it only
    # exposes scan-progress state, but reviewers should know it is public.
    h = FakeHandler("/api/duplicates/status", user=None)
    handled, _ = run(h)
    assert handled is True
    assert h.body() == {"is_running": False}


def test_duplicates_list_requires_session():
    h = FakeHandler("/api/duplicates", user=None)
    handled, _ = run(h)
    assert handled is True
    assert h.error == 401


def test_duplicates_list_summarizes_cache():
    cache = [{"media_type": "video", "potential_savings_mb": 100.0},
             {"media_type": "image", "potential_savings_mb": 50.0}]
    h = FakeHandler("/api/duplicates")
    handled, _ = run(h, _deps(cache=cache))
    assert handled is True
    body = h.body()
    assert body["summary"]["total_groups"] == 2
    assert body["summary"]["potential_savings_mb"] == 150.0
    assert body["summary"]["scan_run"] is True


def test_scan_requires_session():
    h = FakeHandler("/api/duplicates/scan", user=None, body={})
    handled, _ = run(h, post=True)
    assert handled is True
    assert h.error == 401


def test_scan_conflict_while_running():
    h = FakeHandler("/api/duplicates/scan", body={})
    handled, _ = run(h, _deps(is_running=True), post=True)
    assert handled is True
    assert h.error == 409


def test_delete_requires_session():
    h = FakeHandler("/api/duplicates/delete", user=None, body={"paths": ["/x"]})
    handled, _ = run(h, post=True)
    assert handled is True
    assert h.error == 401


def test_bulk_delete_requires_session():
    h = FakeHandler("/api/bulk_delete", user=None, body={"paths": ["/x"]})
    handled, _ = run(h, post=True)
    assert handled is True
    assert h.error == 401


def test_delete_empty_paths_rejected():
    h = FakeHandler("/api/duplicates/delete", body={"paths": []})
    handled, _ = run(h, post=True)
    assert handled is True
    assert h.error == 400
