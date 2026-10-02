"""
test_thumbnails_require_session.py
----------------------------------
/thumbnails verlangt eine Sitzung (UMSETZUNGSPLAN Phase 6, entschieden
2026-10-02).

Bis dahin war die Route bewusst offen, weil der TV-Client kein Cookie hat und
`thumbnailUrl()` kein Token anhängte. Entschieden war ursprünglich „offen nur im
LAN" — mit dem TV-Build aus Phase 1 ging es sauberer: Der TV-Client hängt sein
Token an, und die Route schützt ohne Ausnahme. Ein LAN-Sonderfall hätte an der
Client-Adresse gehangen, und die lässt sich per X-Forwarded-For fälschen.

Dabei aufgefallen: Die Route schnitt den Dateinamen mit `self.path[12:]` aus
und nahm einen Query-String mit — `thumb_x.jpg?token=…` scheiterte an der
Namensprüfung (400). Erst die Trennung von Pfad und Query macht das Token
benutzbar.
"""
import io
from pathlib import Path
from unittest.mock import patch

import pytest

from arcade_scanner.security.auth import session_manager

ROOT = Path(__file__).parent.parent
THUMB = "thumb_0123456789abcdef0123456789abcdef.jpg"


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def _get(path, tmp_path, headers=None):
    from arcade_scanner.server import api_handler

    (tmp_path / THUMB).write_bytes(b"\xff\xd8JPEG\xff\xd9")
    h = api_handler.FinderHandler.__new__(api_handler.FinderHandler)
    h.request_version = "HTTP/1.1"
    h.requestline = f"GET {path} HTTP/1.1"
    h.client_address = ("192.168.2.50", 40000)   # LAN — macht keinen Unterschied
    h.command = "GET"
    h.path = path
    h.headers = Headers(headers or {})
    h.wfile = io.BytesIO()
    h.close_connection = False
    with patch.object(type(api_handler.config), "thumb_dir",
                      new_callable=lambda: property(lambda self: str(tmp_path))):
        h.do_GET()
    raw = h.wfile.getvalue()
    status = int(raw.split(b" ", 2)[1])
    return status, raw


@pytest.fixture
def token():
    t = session_manager.create_session("alice")
    yield t
    session_manager.revoke_session(t)


def test_anonymous_requests_are_refused_even_from_the_lan(tmp_path):
    status, raw = _get(f"/thumbnails/{THUMB}", tmp_path)
    assert status == 401
    assert b"JPEG" not in raw


def test_a_token_in_the_query_is_accepted(tmp_path, token):
    """So fragt der TV-Client (serverConfig.thumbnailUrl)."""
    status, raw = _get(f"/thumbnails/{THUMB}?token={token}", tmp_path)
    assert status == 200, raw[:200]
    assert raw.endswith(b"\xff\xd8JPEG\xff\xd9")


def test_the_session_cookie_is_accepted(tmp_path, token):
    """So fragt der Browser."""
    status, _ = _get(f"/thumbnails/{THUMB}", tmp_path, {"Cookie": f"session_token={token}"})
    assert status == 200


def test_a_forged_forwarded_header_changes_nothing(tmp_path):
    status, _ = _get(f"/thumbnails/{THUMB}", tmp_path, {"X-Forwarded-For": "127.0.0.1"})
    assert status == 401


def test_the_tv_client_sends_its_token():
    src = (ROOT / "tv_client" / "src" / "serverConfig.js").read_text(encoding="utf-8")
    fn = src.split("export const thumbnailUrl", 1)[1].split("\n};", 1)[0]
    assert "getItem('arcade_session_token'" in fn
    assert "?token=${encodeURIComponent(token)}" in fn
