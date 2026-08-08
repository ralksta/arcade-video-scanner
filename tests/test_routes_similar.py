# tests/test_routes_similar.py
"""Route tests for /api/similar — FakeHandler pattern from test_routes_queue.py."""
import json
from unittest.mock import MagicMock, patch

from arcade_scanner.core.similarity import encode_vector
from arcade_scanner.server.routes import similar


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


class FakeMediaDB:
    def __init__(self, vectors=()):
        # vectors: list of (path, raw_values)
        self._vectors = [(p, "m", encode_vector(v)) for p, v in vectors]
        self.callbacks = []

    def get_mean_vectors(self):
        return list(self._vectors)

    def register_on_change(self, cb):
        self.callbacks.append(cb)


def _user_db(vaulted=()):
    user_db = MagicMock()
    u = MagicMock()
    u.data.vaulted = list(vaulted)
    user_db.get_user.return_value = u
    return user_db


def run(handler, media_db=None, user_db=None):
    media_db = media_db if media_db is not None else FakeMediaDB()
    user_db = user_db or _user_db()
    similar._cache.invalidate()
    similar._cache._hooked = False
    with patch.object(similar, "_get_deps", return_value=(media_db, user_db)):
        handled = similar.handle_get(handler)
    return handled


def test_unrelated_path_not_handled():
    assert run(FakeHandler("/api/other")) is False


def test_requires_session():
    h = FakeHandler("/api/similar?path=/lib/a.mp4", user=None)
    assert run(h) is True
    assert h.error == 401


def test_missing_path_is_400():
    h = FakeHandler("/api/similar")
    assert run(h) is True
    assert h.error == 400


def test_empty_index_reports_not_indexed():
    h = FakeHandler("/api/similar?path=/lib/a.mp4")
    assert run(h, FakeMediaDB()) is True
    assert h.body() == {"status": "not_indexed"}


def test_unknown_path_is_404():
    h = FakeHandler("/api/similar?path=/lib/missing.mp4")
    db = FakeMediaDB([("/lib/a.mp4", [1.0, 0.0])])
    assert run(h, db) is True
    assert h.error == 404


def test_ranked_results_exclude_query_and_respect_limit():
    db = FakeMediaDB([
        ("/lib/query.mp4", [1.0, 0.0]),
        ("/lib/close.mp4", [0.9, 0.1]),
        ("/lib/mid.mp4", [0.5, 0.5]),
        ("/lib/far.mp4", [0.0, 1.0]),
    ])
    h = FakeHandler("/api/similar?path=/lib/query.mp4&limit=2")
    assert run(h, db) is True
    body = h.body()
    assert body["status"] == "ok"
    paths = [r["file_path"] for r in body["results"]]
    assert paths == ["/lib/close.mp4", "/lib/mid.mp4"]
    assert "/lib/query.mp4" not in paths
    assert body["results"][0]["score"] >= body["results"][1]["score"]


def test_vaulted_results_omitted():
    db = FakeMediaDB([
        ("/lib/query.mp4", [1.0, 0.0]),
        ("/lib/secret.mp4", [1.0, 0.0]),
        ("/lib/ok.mp4", [0.5, 0.5]),
    ])
    h = FakeHandler("/api/similar?path=/lib/query.mp4")
    assert run(h, db, _user_db(vaulted=["/lib/secret.mp4"])) is True
    paths = [r["file_path"] for r in h.body()["results"]]
    assert paths == ["/lib/ok.mp4"]


def test_cache_invalidated_via_on_change_hook():
    db = FakeMediaDB([("/lib/query.mp4", [1.0, 0.0]), ("/lib/a.mp4", [0.9, 0.1])])
    h = FakeHandler("/api/similar?path=/lib/query.mp4")
    run(h, db)
    assert db.callbacks, "cache must register an on_change hook"
    # simulate an indexer write: new vector appears after invalidation
    db._vectors.append(("/lib/new.mp4", "m", encode_vector([0.95, 0.05])))
    for cb in db.callbacks:
        cb()
    h2 = FakeHandler("/api/similar?path=/lib/query.mp4")
    with patch.object(similar, "_get_deps", return_value=(db, _user_db())):
        similar.handle_get(h2)
    paths = [r["file_path"] for r in h2.body()["results"]]
    assert "/lib/new.mp4" in paths
