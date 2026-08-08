"""Tests for scripts/mac_worker.py — the remote encoding worker.

The worker talks to the server over plain urllib, so everything here mocks
``urllib.request.urlopen``. The interesting cases are the ones that used to
strand a worker silently: an expired session (server sessions are in-memory,
so every restart invalidates the token) and a cancel check that cannot reach
the server.
"""
import io
import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import mac_worker  # noqa: E402


class FakeResponse(io.BytesIO):
    """Minimal stand-in for the object urlopen returns."""

    def __init__(self, payload=b"{}", status=200, headers=None):
        super().__init__(payload)
        self.status = status
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def login_response(token="tok-1"):
    return FakeResponse(b"{}", headers={"Set-Cookie": f"session_token={token}; Path=/"})


def http_error(code):
    return urllib.error.HTTPError("http://x", code, "err", {}, None)


@pytest.fixture
def client():
    with patch("urllib.request.urlopen", return_value=login_response()):
        return mac_worker.WorkerClient("http://srv:8000", "admin", "pw")


class TestAuthentication:
    def test_login_stores_the_session_token(self, client):
        assert client.session_token == "tok-1"

    def test_bad_credentials_raise_instead_of_exiting(self):
        """sys.exit() in a library method would kill callers that can retry."""
        with patch("urllib.request.urlopen", side_effect=http_error(401)):
            with pytest.raises(mac_worker.AuthError):
                mac_worker.WorkerClient("http://srv:8000", "admin", "wrong")

    def test_a_401_triggers_exactly_one_re_login_and_retry(self, client):
        """A server restart drops the in-memory session; the worker must not
        spin on 401 forever."""
        responses = [
            http_error(401),                       # first poll: session gone
            login_response("tok-2"),               # re-login
            FakeResponse(json.dumps({"id": 7}).encode()),  # retried poll
        ]

        def fake_open(req, timeout=None):
            item = responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch("urllib.request.urlopen", side_effect=fake_open):
            job = client.poll_next_job()

        assert job == {"id": 7}
        assert client.session_token == "tok-2"
        assert responses == []

    def test_a_failed_re_login_does_not_hide_the_error(self, client):
        with patch("urllib.request.urlopen", side_effect=http_error(401)):
            assert client.poll_next_job() is None  # reported, not crashed


class TestCancelCheck:
    def test_a_cancelled_job_is_reported(self, client):
        with patch("urllib.request.urlopen",
                   return_value=FakeResponse(b'{"cancelled": true}')):
            assert client.check_cancelled(1) is True

    def test_a_network_error_is_unknown_not_false(self, client):
        """False would mean 'definitely still running' — a dropped packet must
        not be able to state that."""
        with patch("urllib.request.urlopen", side_effect=OSError("boom")):
            assert client.check_cancelled(1) is None

    def test_a_vanished_job_counts_as_cancelled(self, client):
        with patch("urllib.request.urlopen", side_effect=http_error(404)):
            assert client.check_cancelled(1) is True

    def test_unknown_cancel_state_keeps_the_job_running(self, client):
        """_is_cancelled must not throw away a finished encode over a blip."""
        reporter = MagicMock()
        reporter.cancelled.is_set.return_value = False
        with patch.object(client, "check_cancelled", return_value=None):
            assert mac_worker._is_cancelled(client, reporter, 1) is False


class TestUpload:
    def test_the_body_is_streamed_not_read_into_memory(self, client, tmp_path):
        """A multi-GB encode read via f.read() would blow up the worker."""
        payload = tmp_path / "out.mp4"
        payload.write_bytes(b"z" * 4096)
        captured = {}

        def fake_open(req, timeout=None):
            captured["data"] = req.data
            captured["length"] = req.get_header("Content-length")
            return FakeResponse(b'{"success": true}')

        with patch("urllib.request.urlopen", side_effect=fake_open):
            assert client.upload_file(1, str(payload)) is True

        assert hasattr(captured["data"], "read"), "body must be a file object"
        assert captured["length"] == "4096"

    def test_a_rejected_upload_is_not_reported_as_success(self, client, tmp_path):
        payload = tmp_path / "out.mp4"
        payload.write_bytes(b"z")
        with patch("urllib.request.urlopen",
                   return_value=FakeResponse(b'{"success": false, "error": "corrupt"}')):
            assert client.upload_file(1, str(payload)) is False


class TestJobReporter:
    def test_a_cancelled_heartbeat_sets_the_event(self, client):
        reporter = mac_worker.JobReporter(client, 5)
        reporter.INTERVAL = 0.01
        with patch.object(client, "report_progress", return_value=False):
            reporter.start()
            assert reporter.cancelled.wait(2.0) is True
        reporter.stop()

    def test_the_encode_callback_only_touches_local_state(self, client):
        """It runs inside the ffmpeg reader loop — network I/O there stalls
        the progress pipe."""
        reporter = mac_worker.JobReporter(client, 5)
        with patch("urllib.request.urlopen", side_effect=AssertionError("no I/O here")):
            reporter.on_encode_progress(30.0, 60.0, "encode Q=60")
        assert reporter._state == {"pct": 50.0, "eta": 0, "phase": "encode Q=60"}

    def test_progress_survives_a_zero_length_source(self, client):
        reporter = mac_worker.JobReporter(client, 5)
        reporter.on_encode_progress(0.0, 0.0, "encode")
        assert reporter._state["pct"] == 0.0

    def test_an_unreachable_server_is_not_a_cancellation(self, client):
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            assert client.report_progress(1, 10.0, 0, "encode") is True
