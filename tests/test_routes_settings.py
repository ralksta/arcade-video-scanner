# tests/test_routes_settings.py
"""Characterization tests for arcade_scanner/server/routes/settings.py.

Written during the 2026-08-08 night hardening run. These pin CURRENT behavior;
one xfail documents a real security gap (see below) without fixing it blind.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.server.routes import settings


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
        self.server = MagicMock()
        self.server.server_address = ("", 8000)

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


def _singletons(save_result=True):
    config = MagicMock()
    config.settings.model_dump.return_value = {"bitrate_threshold_kbps": 8000}
    config.save.return_value = save_result
    user_db = MagicMock()
    user = MagicMock()
    user_db.get_user.return_value = user
    debouncer = MagicMock()
    return config, user_db, debouncer, 1024 * 1024


def run(handler, singletons=None, post=False):
    singletons = singletons or _singletons()
    with patch.object(settings, "_get_singletons", return_value=singletons):
        handled = settings.handle_post(handler) if post else settings.handle_get(handler)
    return handled, singletons


def test_get_settings_anonymous_returns_global_dump():
    # Characterization: GET /api/settings needs NO session — anonymous clients
    # receive the global config dump (without per-user fields).
    h = FakeHandler("/api/settings", user=None)
    handled, _ = run(h)
    assert handled is True
    assert h.status == 200
    assert h.body()["bitrate_threshold_kbps"] == 8000


def test_get_settings_merges_user_fields_for_session():
    h = FakeHandler("/api/settings")
    singletons = _singletons()
    singletons[1].get_user.return_value.data.smart_collections = [{"id": "c1"}]
    handled, _ = run(h, singletons)
    assert handled is True
    assert h.body()["smart_collections"] == [{"id": "c1"}]


@pytest.mark.xfail(
    reason="SECURITY: POST /api/settings hat keinen Session-Check — config.save() "
           "läuft auch für anonyme Requests (settings.py:80-108, user-Check erst "
           "danach). Im Nachtlauf bewusst nur dokumentiert, nicht gefixt; "
           "Fix-Muster analog c1caa24 (Queue-Endpoints).",
    strict=False,
)
def test_post_settings_anonymous_is_rejected():
    h = FakeHandler("/api/settings", user=None, body={"bitrate_threshold_kbps": 1})
    handled, singletons = run(h, post=True)
    assert handled is True
    assert h.error == 401
    singletons[0].save.assert_not_called()


def test_post_settings_splits_user_fields_from_global_config():
    h = FakeHandler("/api/settings", body={
        "bitrate_threshold_kbps": 9000,
        "smart_collections": [{"id": "c1"}],
        "scan_targets": ["/lib"],
    })
    handled, singletons = run(h, post=True)
    assert handled is True
    config, user_db = singletons[0], singletons[1]
    saved = config.save.call_args.args[0]
    assert "smart_collections" not in saved
    assert "scan_targets" not in saved
    assert saved["bitrate_threshold_kbps"] == 9000
    user_db.add_user.assert_called_once()


def test_post_settings_oversized_body_rejected():
    h = FakeHandler("/api/settings", body={})
    h.headers = {"Content-Length": str(10 * 1024 * 1024)}
    handled, singletons = run(h, post=True)
    assert handled is True
    assert h.error == 413
    singletons[0].save.assert_not_called()
