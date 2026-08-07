"""Characterization tests for arcade_scanner/server/routes/files.py.

The handlers take the raw HTTP handler object, so tests drive them with a fake
that records the response instead of writing to a socket. `db`, `config` and the
lazily-imported api_handler singletons are patched; nothing touches the real
database or the real media library.

do_GET dispatches straight into these route modules with no authentication gate
of its own (api_handler.py:391-395), so each handler is responsible for its own
session check. That makes the auth test below the important one.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.models.video_entry import VideoEntry
from arcade_scanner.server.routes import files


class FakeWFile:
    def __init__(self):
        self.written = b""

    def write(self, payload):
        self.written += payload


class FakeHandler:
    """Records what a route handler did instead of touching a socket."""

    def __init__(self, path, user="alice"):
        self.path = path
        self._user = user
        self.wfile = FakeWFile()
        self.status = None
        self.error = None
        self.error_message = None
        self.headers_sent = []
        self.server = MagicMock()
        self.server.server_address = ("", 8000)

    def get_current_user(self):
        return self._user

    def send_response(self, code):
        self.status = code

    def send_error(self, code, message=""):
        self.error = code
        self.error_message = message

    def send_header(self, key, value):
        self.headers_sent.append((key, value))

    def end_headers(self):
        pass

    @property
    def body(self):
        return json.loads(self.wfile.written.decode()) if self.wfile.written else None


class FakeDB:
    def __init__(self, entries=()):
        self.entries = {e.file_path: e for e in entries}
        self.upserted = []
        self.saved = 0

    def get(self, path):
        return self.entries.get(path)

    def upsert(self, entry):
        self.upserted.append(entry)
        self.entries[entry.file_path] = entry

    def save(self):
        self.saved += 1


def _stub_scanner_manager():
    """A scanner manager whose run_scan is an async no-op.

    /api/rescan really does call `get_scanner_manager().run_scan()` on a fresh
    event loop, which would scan the user's configured targets and rewrite the
    live database. It must never run from a test.
    """
    manager = MagicMock()

    async def no_scan():
        return 0

    manager.run_scan = no_scan
    return manager


def run_route(handler, fake_db=None, path_allowed=True, exists=True):
    """Invoke files.handle_get with the module's collaborators stubbed."""
    fake_db = fake_db if fake_db is not None else FakeDB()
    media_cache = MagicMock()
    media_cache.get.return_value = []
    debouncer = MagicMock()

    with patch("arcade_scanner.server.routes.files.db", fake_db), \
         patch("arcade_scanner.server.routes.files.is_path_allowed",
               return_value=path_allowed), \
         patch("arcade_scanner.server.routes.files._get_media_cache",
               return_value=media_cache), \
         patch("arcade_scanner.server.routes.files._get_report_debouncer",
               return_value=debouncer), \
         patch("arcade_scanner.server.routes.files.os.path.exists",
               return_value=exists), \
         patch("arcade_scanner.scanner.get_scanner_manager",
               return_value=_stub_scanner_manager()), \
         patch("arcade_scanner.templates.dashboard_template.generate_html_report"), \
         patch("arcade_scanner.server.routes.files.subprocess.run") as run:
        handled = files.handle_get(handler)
    return handled, fake_db, media_cache, run


# ---------------------------------------------------------------------------
# Routing table
# ---------------------------------------------------------------------------

ROUTES = [
    "/reveal?path=/media/a.mp4",
    "/api/mark_optimized?path=/media/a.mp4",
    "/compress?path=/media/a.mp4",
    "/api/keep_optimized?original=/media/a.mp4&optimized=/media/a_opt.mp4",
    "/api/discard_optimized?path=/media/a_opt.mp4",
    "/hide?path=/media/a.mp4&state=true",
    "/batch_hide?paths=/media/a.mp4",
    "/favorite?path=/media/a.mp4&state=true",
    "/batch_favorite?paths=/media/a.mp4",
    "/batch_compress?paths=/media/a.mp4",
    "/api/rescan",
    "/api/backup",
]


class TestRouting:
    @pytest.mark.parametrize("route", ROUTES)
    def test_known_routes_are_claimed(self, route):
        handled, *_ = run_route(FakeHandler(route))
        assert handled is True

    @pytest.mark.parametrize("route", [
        "/", "/api/files", "/api/queue/status", "/static/engine.js",
        "/revealed?path=x", "/api/mark_optimized",  # no query string
    ])
    def test_foreign_routes_are_declined(self, route):
        handled, *_ = run_route(FakeHandler(route))
        assert handled is False

    def test_declining_leaves_the_response_untouched(self):
        handler = FakeHandler("/api/something_else")
        run_route(handler)
        assert handler.status is None
        assert handler.error is None


# ---------------------------------------------------------------------------
# Authentication
#
# do_GET has no auth gate, so a handler that forgets its own session check is
# reachable by anyone who can open a socket to the server.
# ---------------------------------------------------------------------------

class TestAuthentication:
    @pytest.mark.parametrize("route", ROUTES)
    def test_every_file_route_requires_a_session(self, route):
        handler = FakeHandler(route, user=None)

        run_route(handler)

        assert handler.error == 401, (
            f"{route.split('?')[0]} answered {handler.error or handler.status} "
            "for an unauthenticated caller"
        )

    def test_an_unauthenticated_caller_cannot_write_to_the_database(self):
        """/api/mark_optimized upserts whatever path it is handed."""
        handler = FakeHandler("/api/mark_optimized?path=/etc/passwd", user=None)

        _, db, media_cache, _ = run_route(handler)

        assert db.upserted == []
        assert db.saved == 0

    def test_an_unauthenticated_caller_cannot_trigger_reveal(self):
        """/reveal shells out to open/explorer/xdg-open on the host."""
        handler = FakeHandler("/reveal?path=/media/a.mp4", user=None)

        _, _, _, subprocess_run = run_route(handler)

        assert subprocess_run.call_count == 0


# ---------------------------------------------------------------------------
# /reveal
# ---------------------------------------------------------------------------

class TestReveal:
    def test_missing_path_is_rejected(self):
        handler = FakeHandler("/reveal?other=1")
        run_route(handler)
        assert handler.error == 400

    def test_path_outside_the_scan_directories_is_forbidden(self):
        handler = FakeHandler("/reveal?path=/etc/passwd")
        run_route(handler, path_allowed=False)
        assert handler.error == 403

    def test_missing_file_reports_not_found(self):
        handler = FakeHandler("/reveal?path=/media/gone.mp4")
        run_route(handler, exists=False)
        assert handler.error == 404

    def test_hidden_folder_answers_with_a_status_payload(self):
        handler = FakeHandler("/reveal?path=/media/.hidden/a.mp4")
        run_route(handler)
        assert handler.status == 200
        assert handler.body["status"] == "hidden_folder"

    def test_successful_reveal_answers_204(self):
        handler = FakeHandler("/reveal?path=/media/a.mp4")
        _, _, _, subprocess_run = run_route(handler)
        assert handler.status == 204
        assert subprocess_run.call_count == 1


# ---------------------------------------------------------------------------
# /api/mark_optimized
# ---------------------------------------------------------------------------

class TestMarkOptimized:
    def test_existing_entry_is_flipped_to_ok(self):
        entry = VideoEntry(FilePath="/media/a.mp4", Size_MB=10.0, Status="HIGH")
        db = FakeDB([entry])
        handler = FakeHandler("/api/mark_optimized?path=/media/a.mp4")

        run_route(handler, fake_db=db)

        assert db.upserted[0].status == "OK"
        assert handler.status == 204

    def test_unknown_path_creates_an_entry(self):
        db = FakeDB()
        handler = FakeHandler("/api/mark_optimized?path=/media/new.mp4")

        with patch("arcade_scanner.server.routes.files.os.path.getsize",
                   return_value=5 * 1024 * 1024):
            run_route(handler, fake_db=db)

        assert db.upserted[0].file_path == "/media/new.mp4"
        assert db.upserted[0].status == "OK"

    def test_media_cache_is_invalidated(self):
        db = FakeDB([VideoEntry(FilePath="/media/a.mp4", Size_MB=1.0)])
        handler = FakeHandler("/api/mark_optimized?path=/media/a.mp4")

        _, _, media_cache, _ = run_route(handler, fake_db=db)

        assert media_cache.invalidate.call_count == 1

    def test_path_outside_the_scan_directories_is_rejected(self):
        """The database should only ever describe files in the library."""
        db = FakeDB()
        handler = FakeHandler("/api/mark_optimized?path=/etc/passwd")

        run_route(handler, fake_db=db, path_allowed=False)

        assert handler.error == 403
        assert db.upserted == []

    def test_missing_path_parameter_still_answers(self):
        handler = FakeHandler("/api/mark_optimized?path=")
        _, db, _, _ = run_route(handler)
        assert db.upserted == []
        assert handler.status == 204

    def test_existing_entry_gets_optimized_timestamp(self):
        entry = VideoEntry(FilePath="/media/a.mp4", Size_MB=10.0, Status="HIGH")
        db = FakeDB([entry])
        handler = FakeHandler("/api/mark_optimized?path=/media/a.mp4")

        run_route(handler, fake_db=db)

        assert db.upserted[0].status == "OK"
        assert db.upserted[0].optimized_at > 0
        assert handler.status == 204

    def test_new_entry_gets_optimized_timestamp(self):
        db = FakeDB()
        handler = FakeHandler("/api/mark_optimized?path=/media/new.mp4")

        with patch("arcade_scanner.server.routes.files.os.path.getsize",
                   return_value=5 * 1024 * 1024):
            run_route(handler, fake_db=db)

        assert db.upserted[0].optimized_at > 0
