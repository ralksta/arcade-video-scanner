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
import os
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
        self.progress_updates = []

    def get_queue_status(self, limit=20):
        return self.jobs

    def get_job(self, job_id):
        return next((j for j in self.jobs if j["id"] == job_id), None)

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

    def update_job_status(self, job_id, status, guard_active=False, **kwargs):
        self.status_updates.append((job_id, status))
        self.status_kwargs = kwargs
        return True

    def update_job_progress(self, job_id, progress_pct=0.0, eta_seconds=0, phase=""):
        self.progress_updates.append((job_id, progress_pct, eta_seconds, phase))
        return True


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
    ("/api/queue/progress", {"job_id": 1, "progress_pct": 42, "phase": "encode Q=60"}),
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
        jobs = [{"id": 1, "file_path": "/media/a.mp4", "status": "encoding"}]

        with patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            run_route(handler, fake_db=FakeDB(jobs=jobs))

        assert send_json.call_args[0][1] == {"cancelled": False}

    def test_a_deleted_job_counts_as_cancelled(self):
        """Otherwise the worker keeps encoding for a row that no longer exists."""
        handler = FakeHandler("/api/queue/check?job_id=1")

        with patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            run_route(handler, fake_db=FakeDB(jobs=[]))

        assert send_json.call_args[0][1] == {"cancelled": True}


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


def db_status(fake_db):
    return fake_db.status_updates


class TestQueueComplete:
    def test_intermediate_report_does_not_clear_saved_bytes(self):
        """The worker posts 'encoding' with no savings yet — that must not
        overwrite the real number a later 'done' will carry."""
        handler = FakeHandler("/api/queue/complete",
                              body={"job_id": 1, "status": "encoding"})

        _, db = run_route(handler, post=True)

        assert db.status_updates == [(1, "encoding")]
        assert "saved_bytes" not in db.status_kwargs

    def test_reported_saved_bytes_are_passed_through(self):
        handler = FakeHandler("/api/queue/complete",
                              body={"job_id": 1, "status": "failed", "saved_bytes": 512})

        _, db = run_route(handler, post=True)

        assert db.status_kwargs["saved_bytes"] == 512


class TestQueueProgress:
    def test_a_heartbeat_is_stored(self):
        handler = FakeHandler("/api/queue/progress",
                              body={"job_id": 3, "progress_pct": 42.5,
                                    "eta_seconds": 90, "phase": "encode Q=60"})

        with patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            _, db = run_route(handler, post=True)

        assert db.progress_updates == [(3, 42.5, 90, "encode Q=60")]
        assert send_json.call_args[0][1] == {"success": True, "cancelled": False}


class TestQueueUpload:
    """The upload handler replaces real files, so these run against tmp_path."""

    def test_an_oversized_body_is_refused(self, tmp_path):
        src = tmp_path / "a.mp4"
        src.write_bytes(b"x" * 100)
        jobs = [{"id": 1, "file_path": str(src), "size_bytes": 100}]
        handler = FakeHandler("/api/queue/upload?job_id=1")
        handler.headers = {"Content-Length": str(10 * 1024)}

        _, db = run_route(handler, fake_db=FakeDB(jobs=jobs), post=True)

        assert handler.error == 413
        assert db.status_updates == [(1, "failed")]
        assert not list(tmp_path.glob(".*part"))

    def test_a_truncated_upload_never_touches_the_original(self, tmp_path):
        src = tmp_path / "a.mp4"
        src.write_bytes(b"original")
        jobs = [{"id": 1, "file_path": str(src), "size_bytes": 8}]
        handler = FakeHandler("/api/queue/upload?job_id=1")
        handler.rfile = FakeRFile(b"half")          # promises 8, delivers 4
        handler.headers = {"Content-Length": "8"}

        fake_db = FakeDB(jobs=jobs)
        with patch("arcade_scanner.server.routes.queue.db", fake_db):
            queue.handle_post(handler)

        assert handler.error == 400
        assert src.read_bytes() == b"original"
        assert db_status(fake_db) == [(1, "failed")]
        assert not list(tmp_path.glob(".*part"))

    def test_standard_mode_replaces_the_original(self, tmp_path):
        src = tmp_path / "a.mkv"
        src.write_bytes(b"original-bytes-long")
        jobs = [{"id": 1, "file_path": str(src), "size_bytes": 19, "target_codec": "hevc"}]
        handler = FakeHandler("/api/queue/upload?job_id=1")
        handler.rfile = FakeRFile(b"opt")
        handler.headers = {"Content-Length": "3"}

        fake_db = FakeDB(jobs=jobs)
        fake_db.get = MagicMock(return_value=None)   # no media row → no bookkeeping
        settings = MagicMock()
        settings.settings.enable_review_mode = False

        with patch("arcade_scanner.server.routes.queue.db", fake_db), \
             patch("arcade_scanner.server.routes.queue.config", settings), \
             patch("arcade_scanner.server.routes.queue.verify_media_integrity",
                   return_value=(True, "ok")), \
             patch("arcade_scanner.server.routes.queue._media_cache"), \
             patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            queue.handle_post(handler)

        assert not src.exists(), "the .mkv original must be gone after the replace"
        assert (tmp_path / "a.mp4").read_bytes() == b"opt"
        assert not list(tmp_path.glob("*_opt.mp4")), "no leftover _opt.mp4 sidecar"
        assert not list(tmp_path.glob(".*part"))
        assert send_json.call_args[0][1]["success"] is True
        assert db_status(fake_db) == [(1, "done")]

    def test_a_failed_integrity_check_keeps_the_original(self, tmp_path):
        src = tmp_path / "a.mp4"
        src.write_bytes(b"original")
        jobs = [{"id": 1, "file_path": str(src), "size_bytes": 8}]
        handler = FakeHandler("/api/queue/upload?job_id=1")
        handler.rfile = FakeRFile(b"broken!!")
        handler.headers = {"Content-Length": "8"}

        fake_db = FakeDB(jobs=jobs)
        fake_db.get = MagicMock(return_value=None)
        settings = MagicMock()
        settings.settings.enable_review_mode = False

        with patch("arcade_scanner.server.routes.queue.db", fake_db), \
             patch("arcade_scanner.server.routes.queue.config", settings), \
             patch("arcade_scanner.server.routes.queue.verify_media_integrity",
                   return_value=(False, "decode errors")), \
             patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            queue.handle_post(handler)

        assert src.read_bytes() == b"original"
        assert not list(tmp_path.glob(".*part"))
        assert send_json.call_args[0][1]["success"] is False
        assert db_status(fake_db) == [(1, "failed")]


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


class TestGifOutputIsPerJob:
    """
    Der Ausgabepfad hing nur an Basename, Preset und fps. Zwei Exporte von
    ``VID_0001.mp4`` aus zwei Ordnern — oder derselbe Clip mit einem anderen
    Ausschnitt — schrieben in **dieselbe** Datei. ``ffmpeg -y`` kürzt sie beim
    Start des zweiten Laufs; wer zuerst „done" sah, lud ein halbes oder das
    fremde GIF herunter. Über Kontogrenzen hinweg: Das Temp-Verzeichnis und
    ``/download_gif`` kennen keine Besitzer.
    """

    def _export(self, video_path):
        handler = FakeHandler("/api/export/gif",
                              body={"path": str(video_path), "preset": "720p", "fps": 15})
        entry = MagicMock(width=1920, height=1080, duration_sec=10.0)
        fake_db = MagicMock()
        fake_db.get.return_value = entry
        started = []

        class NoThread:
            def __init__(self, target, args, daemon):
                started.append(args)

            def start(self):
                pass

        with patch("arcade_scanner.server.routes.queue.db", fake_db), \
             patch("arcade_scanner.server.routes.queue.sanitize_path", side_effect=lambda p: p), \
             patch("arcade_scanner.server.routes.queue.threading.Thread", NoThread), \
             patch("arcade_scanner.server.routes.queue.send_json") as send_json:
            queue.handle_post(handler)

        assert handler.error is None, handler.error
        output_path = started[0][1]
        return output_path, send_json.call_args[0][1]

    def test_two_videos_with_the_same_name_get_different_files(self, tmp_path):
        for sub in ("a", "b"):
            (tmp_path / sub).mkdir()
            (tmp_path / sub / "VID_0001.mp4").write_bytes(b"x")

        out_a, resp_a = self._export(tmp_path / "a" / "VID_0001.mp4")
        out_b, resp_b = self._export(tmp_path / "b" / "VID_0001.mp4")

        assert out_a != out_b
        assert resp_a["download_url"] != resp_b["download_url"]

    def test_the_same_video_twice_gets_different_files(self, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"x")

        out_1, _ = self._export(video)
        out_2, _ = self._export(video)

        assert out_1 != out_2

    def test_the_file_name_carries_the_job_id(self, tmp_path):
        video = tmp_path / "clip.mp4"
        video.write_bytes(b"x")

        out, resp = self._export(video)

        assert resp["job_id"] in resp["output_filename"]
        assert out.endswith(resp["output_filename"])


class TestUploadRespectsCancellation:
    """
    Der Upload sah den Status des Jobs nie an. Wer in der Oberfläche auf
    „Abbrechen" klickte, während der Worker hochlud — bei einer großen Datei
    Minuten —, verlor das Original trotzdem: Der Server ersetzte es nach dem
    Empfang und setzte den Job von ``cancelled`` zurück auf ``done``.
    """

    def _upload(self, tmp_path, fake_db):
        handler = FakeHandler("/api/queue/upload?job_id=1")
        handler.rfile = FakeRFile(b"opt")
        handler.headers = {"Content-Length": "3"}
        fake_db.get = MagicMock(return_value=None)
        settings = MagicMock()
        settings.settings.enable_review_mode = False
        with patch("arcade_scanner.server.routes.queue.db", fake_db), \
             patch("arcade_scanner.server.routes.queue.config", settings), \
             patch("arcade_scanner.server.routes.queue.verify_media_integrity",
                   return_value=(True, "ok")), \
             patch("arcade_scanner.server.routes.queue._media_cache"), \
             patch("arcade_scanner.server.routes.queue.send_json"):
            queue.handle_post(handler)
        return handler

    @pytest.mark.parametrize("status", ["cancelled", "done", "failed"])
    def test_a_finished_job_takes_no_upload(self, tmp_path, status):
        src = tmp_path / "a.mp4"
        src.write_bytes(b"original")
        fake_db = FakeDB(jobs=[{"id": 1, "file_path": str(src), "size_bytes": 8,
                                "status": status}])

        handler = self._upload(tmp_path, fake_db)

        assert handler.error == 409
        assert src.read_bytes() == b"original"
        assert ("done" not in [s for _, s in fake_db.status_updates])
        assert not list(tmp_path.glob(".*part"))

    def test_a_cancel_during_the_transfer_keeps_the_original(self, tmp_path):
        """Beim Start noch aktiv, nach dem Empfang abgebrochen."""
        src = tmp_path / "a.mp4"
        src.write_bytes(b"original")
        job = {"id": 1, "file_path": str(src), "size_bytes": 8, "status": "uploading"}

        class CancelledMidway(FakeDB):
            calls = 0

            def get_job(self, job_id):
                self.calls += 1
                return dict(job, status="uploading" if self.calls == 1 else "cancelled")

        fake_db = CancelledMidway(jobs=[job])
        handler = self._upload(tmp_path, fake_db)

        assert handler.error == 409
        assert src.read_bytes() == b"original"
        assert "done" not in [s for _, s in fake_db.status_updates]
        assert not list(tmp_path.glob(".*part"))

    def test_an_active_job_is_still_accepted(self, tmp_path):
        src = tmp_path / "a.mp4"
        src.write_bytes(b"original")
        fake_db = FakeDB(jobs=[{"id": 1, "file_path": str(src), "size_bytes": 8,
                                "status": "uploading"}])

        handler = self._upload(tmp_path, fake_db)

        assert handler.error is None
        assert src.read_bytes() == b"opt"
        assert db_status(fake_db) == [(1, "done")]


def test_a_job_is_applied_by_one_upload_at_a_time():
    """
    Nach einem Reclaim hat ein Job zwei Worker. Beide lesen ``uploading``,
    bevor einer ``done`` setzt — der Status allein trennt sie nicht.
    """
    assert queue._claim_finalize(7)
    try:
        assert not queue._claim_finalize(7), "Zweiter Upload desselben Jobs kam durch"
        assert queue._claim_finalize(8), "Ein anderer Job darf nicht warten"
        queue._release_finalize(8)
    finally:
        queue._release_finalize(7)
    assert queue._claim_finalize(7), "Nach dem Freigeben muss es wieder gehen"
    queue._release_finalize(7)


class TestNamesAtTheLengthLimit:
    """
    Dateinamen dürfen höchstens 255 **Bytes** lang sein. Zwei Stellen hängen
    etwas an den Namen des Videos: der GIF-Export (``_720p_15fps_<job>.gif``)
    und der Upload (``.<stem>.job<id>.part``). Bei einem Video mit langem Namen
    scheiterte das mit ENAMETOOLONG — beim Upload bei **jedem** Versuch, die
    Datei ließ sich nie optimieren, und der Job hieß nur „failed".
    """

    STEM = "ä" * 120 + "x" * 8   # 248 Bytes, 128 Zeichen — Umlaute zählen doppelt

    def test_the_gif_name_fits(self, tmp_path):
        video = tmp_path / f"{self.STEM}.mp4"
        video.write_bytes(b"x")
        out, resp = TestGifOutputIsPerJob()._export(video)
        name = os.path.basename(out)
        assert len(name.encode("utf-8")) <= 255, len(name.encode("utf-8"))
        assert name.endswith(".gif") and resp["job_id"] in name
        name.encode("utf-8").decode("utf-8")  # an einer Zeichengrenze gekürzt

    def test_the_upload_part_file_fits(self, tmp_path):
        src = tmp_path / f"{self.STEM}.mp4"
        src.write_bytes(b"original")
        jobs = [{"id": 123456, "file_path": str(src), "size_bytes": 8}]
        handler = FakeHandler("/api/queue/upload?job_id=123456")
        handler.rfile = FakeRFile(b"opt")
        handler.headers = {"Content-Length": "3"}
        fake_db = FakeDB(jobs=jobs)
        fake_db.get = MagicMock(return_value=None)
        settings = MagicMock()
        settings.settings.enable_review_mode = False
        with patch("arcade_scanner.server.routes.queue.db", fake_db), \
             patch("arcade_scanner.server.routes.queue.config", settings), \
             patch("arcade_scanner.server.routes.queue.verify_media_integrity",
                   return_value=(True, "ok")), \
             patch("arcade_scanner.server.routes.queue._media_cache"), \
             patch("arcade_scanner.server.routes.queue.send_json"):
            queue.handle_post(handler)

        assert handler.error is None, handler.error
        assert src.read_bytes() == b"opt"
        assert db_status(fake_db) == [(123456, "done")]
