"""
test_watch_progress.py
----------------------
Wiedergabefortschritt pro Konto: Store (users.db) und Route /api/progress.

Vorher lag der Fortschritt nur im localStorage des Fernsehers. Der Browser
kannte kein „Weiterschauen", und was am TV angefangen war, ließ sich am
Rechner nicht fortsetzen. Die Schwellen — ab 20 s „angefangen", ab 95 %
„gesehen" — sind dieselben, die vorher in tv_client/src/watchProgress.js
standen.
"""
import io
import json
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.server.routes import progress


@pytest.fixture
def store(tmp_path):
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.user_store.config", mock_config):
        from arcade_scanner.database.user_store import UserStore
        yield UserStore()


# ── Store ─────────────────────────────────────────────────────────────────────

def test_saves_and_lists_newest_first(store):
    store.save_progress("alice", "/lib/a.mp4", 120, 600, now=1)
    store.save_progress("alice", "/lib/b.mp4", 30, 600, now=2)
    items = store.list_progress("alice")
    assert [i["path"] for i in items] == ["/lib/b.mp4", "/lib/a.mp4"]
    assert items[1]["position"] == 120
    assert items[1]["watched"] is False


def test_accounts_are_separate(store):
    store.save_progress("alice", "/lib/a.mp4", 120, 600)
    assert store.list_progress("bob") == []


def test_short_peek_does_not_overwrite_a_real_position(store):
    """Kurz hineinschauen (< 20 s) soll einen gespeicherten Stand nicht löschen."""
    store.save_progress("alice", "/lib/a.mp4", 300, 600)
    assert store.save_progress("alice", "/lib/a.mp4", 5, 600) is None
    assert store.list_progress("alice")[0]["position"] == 300


def test_near_the_end_counts_as_watched(store):
    state = store.save_progress("alice", "/lib/a.mp4", 580, 600)
    assert state["watched"] is True
    assert state["position"] == 0


def test_watched_stays_set_when_rewatching(store):
    store.save_progress("alice", "/lib/a.mp4", 590, 600)
    state = store.save_progress("alice", "/lib/a.mp4", 100, 600)
    assert state["watched"] is True
    assert state["position"] == 100


@pytest.mark.parametrize("position,duration", [
    (100, 0), (100, None), ("x", 600), (float("nan"), 600), (100, float("inf")), (-5, 600),
])
def test_garbage_is_ignored(store, position, duration):
    assert store.save_progress("alice", "/lib/a.mp4", position, duration) is None
    assert store.list_progress("alice") == []


def test_clear_keeps_watched_but_drops_unwatched(store):
    store.save_progress("alice", "/lib/seen.mp4", 590, 600)
    store.save_progress("alice", "/lib/seen.mp4", 100, 600)
    store.save_progress("alice", "/lib/half.mp4", 100, 600)
    store.clear_progress("alice", "/lib/seen.mp4")
    store.clear_progress("alice", "/lib/half.mp4")
    items = store.list_progress("alice")
    assert [(i["path"], i["position"], i["watched"]) for i in items] == [
        ("/lib/seen.mp4", 0, True)]


def test_moved_file_takes_its_progress_along(store):
    store.save_progress("alice", "/lib/old.mp4", 100, 600)
    store.remap_paths_in_user_data({"/lib/old.mp4": "/lib/new.mp4"})
    assert [i["path"] for i in store.list_progress("alice")] == ["/lib/new.mp4"]


def test_move_does_not_overwrite_progress_already_on_the_new_path(store):
    store.save_progress("alice", "/lib/old.mp4", 100, 600)
    store.save_progress("alice", "/lib/new.mp4", 200, 600)
    store.remap_paths_in_user_data({"/lib/old.mp4": "/lib/new.mp4"})
    items = store.list_progress("alice")
    assert [(i["path"], i["position"]) for i in items] == [("/lib/new.mp4", 200)]


def test_deleted_file_loses_its_progress(store):
    store.save_progress("alice", "/lib/a.mp4", 100, 600)
    store.save_progress("bob", "/lib/a.mp4", 100, 600)
    store.purge_paths_from_user_data(["/lib/a.mp4"])
    assert store.list_progress("alice") == []
    assert store.list_progress("bob") == []


# ── Route ─────────────────────────────────────────────────────────────────────

class FakeHandler:
    def __init__(self, path="/api/progress", user="alice", body=None):
        self.path = path
        self._user = user
        raw = json.dumps(body).encode() if body is not None else b""
        self.rfile = io.BytesIO(raw)
        self.headers = {"Content-Length": str(len(raw))}
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
        return json.loads(b"".join(c.args[0] for c in self.wfile.write.call_args_list))


def _user(targets=("/lib",)):
    u = MagicMock()
    u.is_admin = False
    u.data.scan_targets = list(targets)
    return u


def _media_db(known=("/lib/a.mp4",)):
    media_db = MagicMock()
    media_db.get.side_effect = lambda p: object() if p in known else None
    return media_db


def run(handler, method, store, user=None, media_db=None):
    user_db = MagicMock(wraps=store)
    user_db.get_user.return_value = user if user is not None else _user()
    deps = (media_db or _media_db(), user_db, 1024 * 1024)
    with patch.object(progress, "_get_deps", return_value=deps):
        return getattr(progress, f"handle_{method}")(handler)


def test_other_paths_are_not_handled(store):
    assert run(FakeHandler("/api/progressive"), "get", store) is False
    assert run(FakeHandler("/api/other"), "post", store) is False


@pytest.mark.parametrize("method", ["get", "post"])
def test_requires_session(store, method):
    h = FakeHandler(user=None, body={"path": "/lib/a.mp4"})
    assert run(h, method, store) is True
    assert h.error == 401


def test_post_then_get(store):
    h = FakeHandler(body={"path": "/lib/a.mp4", "position": 120, "duration": 600})
    run(h, "post", store)
    assert h.body()["progress"]["position"] == 120

    h = FakeHandler("/api/progress")
    run(h, "get", store)
    assert [i["path"] for i in h.body()["items"]] == ["/lib/a.mp4"]


def test_post_rejects_unknown_files(store):
    """Sonst ließe sich die Tabelle mit beliebigen Pfaden füllen."""
    h = FakeHandler(body={"path": "/lib/nope.mp4", "position": 120, "duration": 600})
    run(h, "post", store)
    assert h.error == 404
    assert store.list_progress("alice") == []


def test_post_rejects_files_outside_the_accounts_targets(store):
    h = FakeHandler(body={"path": "/other/a.mp4", "position": 120, "duration": 600})
    run(h, "post", store, media_db=_media_db(known=("/other/a.mp4",)))
    assert h.error == 404


@pytest.mark.parametrize("body", [None, {}, {"path": ""}, {"path": 5}, ["x"]])
def test_post_without_path_is_400(store, body):
    h = FakeHandler(body=body)
    run(h, "post", store)
    assert h.error == 400


def test_get_hides_paths_the_account_no_longer_sees(store):
    store.save_progress("alice", "/lib/a.mp4", 120, 600)
    store.save_progress("alice", "/old/b.mp4", 120, 600)
    h = FakeHandler("/api/progress")
    run(h, "get", store)
    assert [i["path"] for i in h.body()["items"]] == ["/lib/a.mp4"]


def test_get_without_user_record_fails_closed(store):
    store.save_progress("alice", "/lib/a.mp4", 120, 600)
    user_db = MagicMock(wraps=store)
    user_db.get_user.return_value = None
    h = FakeHandler("/api/progress")
    with patch.object(progress, "_get_deps", return_value=(_media_db(), user_db, 1)):
        progress.handle_get(h)
    assert h.error == 503


def test_clear(store):
    store.save_progress("alice", "/lib/a.mp4", 120, 600)
    h = FakeHandler(body={"path": "/lib/a.mp4", "clear": True})
    run(h, "post", store)
    assert h.body() == {"progress": None}
    assert store.list_progress("alice") == []
