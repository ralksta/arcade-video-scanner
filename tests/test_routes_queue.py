"""Characterization tests for arcade_scanner/server/routes/queue.py.

These are the endpoints scripts/mac_worker.py polls: claim a job, download the
source file, upload the result, report completion. do_GET / do_POST dispatch
into this module without an authentication gate of their own
(api_handler.py:391-395), so each handler must check the session itself — which
makes the parametrised auth test the important one here.

Nothing touches the real database, the real media library or the filesystem
outside tmp_path.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.server.routes import queue


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

    @property
    def answered(self):
        """The status this handler replied with, however it was sent.

        require_auth answers through send_json(status=401), the hand-written
        handlers use send_error — both are a 401 to the client.
        """
        return self.error if self.error is not None else self.status

    def send_header(self, key, value):
        pass

    def end_headers(self):
        pass


class FakeDB:
    def __init__(self, jobs=(), next_job=None):
        self.jobs = list(jobs)
        self.next_job = next_job
        self.queued = []
        self.cancelled = []
        self.status_updates = []

    def get_queue_status(self, limit=20):
        return self.jobs

    def get_next_pending(self, worker_id=""):
        return self.next_job

    def is_job_cancelled(self, job_id):
        return job_id == 99

    def queue_encode(self, file_path, size_bytes=0, target_codec="hevc"):
        self.queued.append((file_path, target_codec))
        return len(self.queued)

    def cancel_job(self, job_id):
        self.cancelled.append(job_id)
        return True

    def update_job_status(self, job_id, status, **kwargs):
        self.status_updates.append((job_id, status))


def run_route(handler, fake_db=None, path_allowed=True, post=False):
    fake_db = fake_db if fake_db is not None else FakeDB()
    with patch("arcade_scanner.server.routes.queue.db", fake_db), \
         patch("arcade_scanner.server.routes.queue.os.path.exists", return_value=False):
        try:
            from arcade_scanner.server.routes.queue import is_path_allowed  # noqa: F401
            allowed_patch = patch("arcade_scanner.server.routes.queue.is_path_allowed",
                                  return_value=path_allowed)
        except ImportError:
            allowed_patch = None

        if allowed_patch is not None:
            with allowed_patch:
                handled = queue.handle_post(handler) if post else queue.handle_get(handler)
        else:
            handled = queue.handle_post(handler) if post else queue.handle_get(handler)
    return handled, fake_db


GET_ROUTES = [
    "/api/export/gif/status/abc123",
    "/download_gif?file=out.gif",
    "/api/queue/status",
    "/api/queue/next?worker_id=mac-mini",
    "/api/queue/check?job_id=1",
    "/api/queue/download?job_id=1",
]

POST_ROUTES = [
    ("/api/queue/add", {"file_path": "/media/a.mp4"}),
    ("/api/queue/cancel", {"job_id": 1}),
    ("/api/queue/upload?job_id=1", None),
    ("/api/queue/complete", {"job_id": 1, "status": "done"}),
]


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

class TestRouting:
    @pytest.mark.parametrize("route", GET_ROUTES)
    def test_known_get_routes_are_claimed(self, route):
        handled, _ = run_route(FakeHandler(route))
        assert handled is True

    @pytest.mark.parametrize("route,body", POST_ROUTES)
    def test_known_post_routes_are_claimed(self, route, body):
        handled, _ = run_route(FakeHandler(route, body=body), post=True)
        assert handled is True

    @pytest.mark.parametrize("route", [
        "/", "/api/files", "/reveal?path=x", "/api/queue", "/api/queued/status",
    ])
    def test_foreign_get_routes_are_declined(self, route):
        handled, _ = run_route(FakeHandler(route))
        assert handled is False

    def test_foreign_post_routes_are_declined(self):
        handled, _ = run_route(FakeHandler("/api/something", body={}), post=True)
        assert handled is False


# ---------------------------------------------------------------------------
# Authentication
#
# scripts/mac_worker.py logs in and sends `Cookie: session_token=...` on every
# request (mac_worker.py:109-112), and the browser calls these same-origin, so
# requiring a session costs no client anything.
# ---------------------------------------------------------------------------

class TestAuthentication:
    @pytest.mark.parametrize("route", GET_ROUTES)
    def test_every_get_route_requires_a_session(self, route):
        handler = FakeHandler(route, user=None)

        run_route(handler)

        assert handler.answered == 401, (
            f"{route.split('?')[0]} answered {handler.answered} "
            "for an unauthenticated caller"
        )

    @pytest.mark.parametrize("route,body", POST_ROUTES)
    def test_every_post_route_requires_a_session(self, route, body):
        handler = FakeHandler(route, user=None, body=body)

        run_route(handler, post=True)

        assert handler.answered == 401, (
            f"{route.split('?')[0]} answered {handler.answered} "
            "for an unauthenticated caller"
        )

    def test_an_unauthenticated_caller_cannot_queue_a_file(self):
        """/api/queue/add takes a path and, with /download, yields its contents."""
        handler = FakeHandler("/api/queue/add", user=None,
                              body={"file_path": "/Users/someone/private.pdf"})

        _, db = run_route(handler, post=True)

        assert db.queued == []

    def test_an_unauthenticated_caller_cannot_claim_a_job(self):
        """Claiming jobs from outside would stall the real workers."""
        handler = FakeHandler("/api/queue/next", user=None)

        run_route(handler, fake_db=FakeDB(next_job={"id": 1, "file_path": "/media/a.mp4"}))

        assert handler.answered == 401

    def test_an_unauthenticated_caller_cannot_cancel_a_job(self):
        handler = FakeHandler("/api/queue/cancel", user=None, body={"job_id": 7})

        _, db = run_route(handler, post=True)

        assert db.cancelled == []

    def test_an_unauthenticated_caller_cannot_report_completion(self):
        handler = FakeHandler("/api/queue/complete", user=None,
                              body={"job_id": 7, "status": "failed"})

        _, db = run_route(handler, post=True)

        assert db.status_updates == []


# ---------------------------------------------------------------------------
# Behaviour of the authenticated endpoints
# ---------------------------------------------------------------------------

class TestQueueAdd:
    def test_a_library_file_is_queued(self):
        handler = FakeHandler("/api/queue/add", body={"file_path": "/media/a.mp4"})

        _, db = run_route(handler, post=True)

        assert db.queued == [("/media/a.mp4", "hevc")]

    def test_path_outside_the_scan_directories_is_refused(self):
        """The queued path is what /download streams and /upload writes back."""
        handler = FakeHandler("/api/queue/add",
                              body={"file_path": "/Users/someone/private.pdf"})

        _, db = run_route(handler, post=True, path_allowed=False)

        assert handler.answered == 403
        assert db.queued == []

    def test_unknown_codec_falls_back_to_hevc(self):
        handler = FakeHandler("/api/queue/add",
                              body={"file_path": "/media/a.mp4", "codec": "vp9"})

        _, db = run_route(handler, post=True)

        assert db.queued == [("/media/a.mp4", "hevc")]

    def test_av1_is_accepted(self):
        handler = FakeHandler("/api/queue/add",
                              body={"file_path": "/media/a.mp4", "codec": "av1"})

        _, db = run_route(handler, post=True)

        assert db.queued == [("/media/a.mp4", "av1")]

    def test_missing_file_path_is_rejected(self):
        handler = FakeHandler("/api/queue/add", body={})

        _, db = run_route(handler, post=True)

        assert handler.answered == 400
        assert db.queued == []


class TestQueueStatus:
    def test_status_returns_the_job_list(self):
        jobs = [{"id": 1, "status": "pending"}, {"id": 2, "status": "done"}]
        handler = FakeHandler("/api/queue/status")

        with patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            run_route(handler, fake_db=FakeDB(jobs=jobs))

        send_json.assert_called_once()
        assert send_json.call_args[0][1] == jobs


class TestQueueNext:
    def test_a_claimed_job_is_returned(self):
        job = {"id": 4, "file_path": "/media/a.mp4"}
        handler = FakeHandler("/api/queue/next?worker_id=mac-mini")

        with patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            run_route(handler, fake_db=FakeDB(next_job=job))

        assert send_json.call_args[0][1] == job

    def test_an_empty_queue_answers_204(self):
        handler = FakeHandler("/api/queue/next?worker_id=mac-mini")
        run_route(handler, fake_db=FakeDB(next_job=None))
        assert handler.status == 204


class TestQueueCheck:
    def test_cancelled_job_is_reported(self):
        handler = FakeHandler("/api/queue/check?job_id=99")

        with patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            run_route(handler)

        assert send_json.call_args[0][1] == {"cancelled": True}

    def test_running_job_is_not_reported_as_cancelled(self):
        handler = FakeHandler("/api/queue/check?job_id=1")

        with patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            run_route(handler)

        assert send_json.call_args[0][1] == {"cancelled": False}


class TestQueueDownload:
    def test_missing_job_id_is_rejected(self):
        handler = FakeHandler("/api/queue/download?job_id=0")
        run_route(handler)
        assert handler.error == 400

    def test_unknown_job_is_not_found(self):
        handler = FakeHandler("/api/queue/download?job_id=42")
        run_route(handler, fake_db=FakeDB(jobs=[]))
        assert handler.error == 404

    def test_vanished_source_marks_the_job_failed(self):
        jobs = [{"id": 1, "file_path": "/media/gone.mp4"}]
        handler = FakeHandler("/api/queue/download?job_id=1")

        _, db = run_route(handler, fake_db=FakeDB(jobs=jobs))

        assert handler.error == 404
        assert db.status_updates == [(1, "failed")]


class TestDownloadGif:
    def test_missing_filename_is_rejected(self):
        handler = FakeHandler("/download_gif?other=1")
        run_route(handler)
        assert handler.error == 400

    @pytest.mark.parametrize("name", ["../../etc/passwd", "sub/dir.gif", "a\\b.gif"])
    def test_path_traversal_in_the_filename_is_refused(self, name):
        handler = FakeHandler(f"/download_gif?file={name}")
        run_route(handler)
        assert handler.error == 403
