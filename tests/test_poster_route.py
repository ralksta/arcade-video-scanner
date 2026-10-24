"""
test_poster_route.py
--------------------
`GET /poster?path=` — grosses Standbild (bis 1280×720) für Titelbild und
Detailansicht der TV-App.

Die Vorschaubilder sind 480×270. Auf dem Fernseher füllt das Titelbild die
halbe Fläche, dort wirkten sie verwaschen. Das Standbild entsteht erst auf
Anfrage und liegt neben den Vorschaubildern (`poster_<hash>.jpg`).

Weil ein Standbild den Inhalt zeigt, gelten dieselben Regeln wie für die
Bibliothek: Sitzung, nur Einträge der Datenbank, nur die eigenen Pfade.
"""
import io
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from arcade_scanner.core import video_processor
from arcade_scanner.security.auth import session_manager

POSTER_BYTES = b"\xff\xd8POSTER\xff\xd9"


class Headers(dict):
    def get(self, key, default=None):
        return super().get(key, default)


def _get(path, tmp_path, *, entry=None, may_see=True, poster=None):
    from arcade_scanner.server import api_handler

    h = api_handler.FinderHandler.__new__(api_handler.FinderHandler)
    h.request_version = "HTTP/1.1"
    h.requestline = f"GET {path} HTTP/1.1"
    h.client_address = ("192.168.2.50", 40000)
    h.command = "GET"
    h.path = path
    h.headers = Headers({})
    h.wfile = io.BytesIO()
    h.close_connection = False

    calls = []

    def fake_create(p, duration=None):
        calls.append(p)
        return poster or ""

    with patch.object(api_handler.db, "get", lambda p: entry), \
            patch.object(api_handler, "is_path_allowed", lambda p: True), \
            patch.object(api_handler.user_db, "get_user", lambda n: SimpleNamespace(name=n)), \
            patch("arcade_scanner.core.user_scope.visible_path_filter",
                  lambda u: (lambda p: may_see)), \
            patch.object(video_processor, "create_poster", fake_create):
        h.do_GET()
    raw = h.wfile.getvalue()
    return int(raw.split(b" ", 2)[1]), raw, calls


@pytest.fixture
def token():
    t = session_manager.create_session("alice")
    yield t
    session_manager.revoke_session(t)


ENTRY = SimpleNamespace(duration_sec=120.0)


def test_anonymous_requests_are_refused(tmp_path):
    status, _, calls = _get("/poster?path=/media/a.mp4", tmp_path, entry=ENTRY)
    assert status == 401
    assert not calls


def test_paths_outside_the_library_start_no_ffmpeg(tmp_path, token):
    status, _, calls = _get(f"/poster?path=/etc/passwd&token={token}", tmp_path, entry=None)
    assert status == 404
    assert not calls


def test_other_accounts_files_are_hidden(tmp_path, token):
    status, raw, calls = _get(f"/poster?path=/media/bob/a.mp4&token={token}", tmp_path,
                              entry=ENTRY, may_see=False)
    assert status == 404
    assert not calls
    assert POSTER_BYTES not in raw


def test_own_entries_get_their_poster(tmp_path, token):
    poster = tmp_path / "poster_x.jpg"
    poster.write_bytes(POSTER_BYTES)
    status, raw, calls = _get(f"/poster?path=/media/a.mp4&token={token}", tmp_path,
                              entry=ENTRY, poster=str(poster))
    assert status == 200, raw[:200]
    assert raw.endswith(POSTER_BYTES)
    assert calls == ["/media/a.mp4"]
    assert b"private" in raw.split(b"\r\n\r\n", 1)[0]


def test_poster_and_thumbnail_share_the_hash():
    p = "/media/Ordner/Film.mp4"
    thumb = video_processor.thumbnail_name_for(p)
    assert video_processor.poster_name_for(p) == "poster_" + thumb[len("thumb_"):]


def test_rebuild_thumbs_also_removes_posters(tmp_path):
    from arcade_scanner.core import maintenance

    (tmp_path / "thumb_a.jpg").write_bytes(b"x")
    (tmp_path / "poster_a.jpg").write_bytes(b"x")
    (tmp_path / "keep.txt").write_bytes(b"x")
    with patch.object(maintenance, "data_dir_looks_sane", lambda: True), \
            patch.object(type(maintenance.config), "thumb_dir",
                         new_callable=lambda: property(lambda self: str(tmp_path))):
        maintenance.purge_thumbnails()
    assert sorted(f.name for f in tmp_path.iterdir()) == ["keep.txt"]


def test_purge_media_also_removes_posters(tmp_path):
    from arcade_scanner.core import maintenance

    (tmp_path / "thumb_a.jpg").write_bytes(b"x")
    (tmp_path / "poster_a.jpg").write_bytes(b"x")
    (tmp_path / "keep.txt").write_bytes(b"x")
    with patch.object(maintenance, "data_dir_looks_sane", lambda: True), \
            patch.object(type(maintenance.config), "thumb_dir",
                         new_callable=lambda: property(lambda self: str(tmp_path))):
        maintenance.purge_media()
    assert sorted(f.name for f in tmp_path.iterdir()) == ["keep.txt"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")
def test_a_real_poster_is_large_and_bounded(tmp_path):
    """Echtes ffmpeg: 1920×1080 rein, höchstens 1280×720 raus, kein Rest."""
    from PIL import Image

    video = tmp_path / "clip.mp4"
    subprocess.run(["ffmpeg", "-f", "lavfi", "-i", "testsrc=size=1920x1080:rate=10",
                    "-t", "2", "-pix_fmt", "yuv420p", str(video), "-y", "-loglevel", "error"],
                   check=True, timeout=60)
    thumbs = tmp_path / "thumbs"
    thumbs.mkdir()
    with patch.object(type(video_processor.config), "thumb_dir",
                      new_callable=lambda: property(lambda self: str(thumbs))):
        out = video_processor.create_poster(str(video), 2.0)
    assert out and Path(out).name == video_processor.poster_name_for(str(video))
    with Image.open(out) as im:
        assert im.size == (1280, 720)
    assert [f.name for f in thumbs.iterdir()] == [Path(out).name]   # keine .tmp-Reste
