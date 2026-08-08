"""Route tests for /api/candidates — FakeHandler pattern from test_routes_queue.py."""
import json
from unittest.mock import MagicMock, patch

from arcade_scanner.models.video_entry import VideoEntry
from arcade_scanner.server.routes import candidates


class FakeHandler:
    def __init__(self, path, user="alice"):
        self.path = path
        self._user = user
        self.wfile = MagicMock()
        self.status = None
        self.error = None
        self.headers = {}

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


class FakeDB:
    def __init__(self, entries=(), active=()):
        self._entries = list(entries)
        self._active = set(active)

    def get_all(self):
        return self._entries

    def get_active_queue_paths(self):
        return self._active


class FakeUserDB:
    def __init__(self, vaulted=()):
        u = MagicMock()
        u.data.vaulted = list(vaulted)
        self._u = u

    def get_user(self, name):
        return self._u


def _entry(path="/lib/a.mp4", **kw):
    base = dict(file_path=path, size_mb=1000.0, bitrate_mbps=45.0, codec="h264",
                width=3840, height=2160, frame_rate=30.0, media_type="video")
    base.update(kw)
    return VideoEntry(**base)


def run(handler, db=None, user_db=None, tmp_path=None):
    db = db or FakeDB([_entry()])
    user_db = user_db or FakeUserDB()
    with patch.object(candidates, "_get_deps", return_value=(db, user_db)):
        handled = candidates.handle_get(handler)
    return handled


def test_unrelated_path_not_handled():
    assert run(FakeHandler("/api/other")) is False


def test_requires_session():
    h = FakeHandler("/api/candidates", user=None)
    assert run(h) is True
    assert h.error == 401


def test_invalid_codec_400():
    h = FakeHandler("/api/candidates?codec=vp9")
    assert run(h) is True
    assert h.error == 400


def test_returns_ranked_results():
    h = FakeHandler("/api/candidates?codec=hevc")
    db = FakeDB([_entry("/lib/big.mp4", size_mb=8000.0), _entry("/lib/small.mp4", size_mb=100.0)])
    assert run(h, db=db) is True
    body = h.body()
    assert body["summary"]["total_files"] == 2
    assert [r["file_path"] for r in body["results"]] == ["/lib/big.mp4", "/lib/small.mp4"]


def test_excludes_active_queue_and_vaulted():
    h = FakeHandler("/api/candidates")
    db = FakeDB([_entry("/lib/q.mp4"), _entry("/lib/v.mp4"), _entry("/lib/ok.mp4")],
                active={"/lib/q.mp4"})
    udb = FakeUserDB(vaulted=["/lib/v.mp4"])
    run(h, db=db, user_db=udb)
    assert [r["file_path"] for r in h.body()["results"]] == ["/lib/ok.mp4"]


def test_limit_param():
    h = FakeHandler("/api/candidates?limit=1")
    db = FakeDB([_entry(f"/lib/v{i}.mp4") for i in range(3)])
    run(h, db=db)
    body = h.body()
    assert len(body["results"]) == 1
    assert body["summary"]["total_files"] == 3
