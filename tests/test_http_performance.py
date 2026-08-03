"""
test_http_performance.py
------------------------
Contract tests for the HTTP performance layer:

1. gzip compression in response_helpers (send_bytes / send_json)
2. If-Modified-Since → 304 revalidation
3. HTTP/1.1 keep-alive safety net in FinderHandler:
   every response either carries a Content-Length/Transfer-Encoding or
   is flagged Connection: close. A body without length delimiter on a
   kept-alive connection makes the browser hang forever — this is the
   invariant that makes protocol_version = "HTTP/1.1" safe.
"""
import email.utils
import gzip
import io

import pytest

from arcade_scanner.server.response_helpers import (
    GZIP_MIN_SIZE,
    client_accepts_gzip,
    send_bytes,
    send_json,
    send_not_modified_if_unchanged,
)


class FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeHandler:
    def __init__(self, accept_gzip=False, if_modified_since=None, command="GET"):
        self.headers = FakeHeaders()
        if accept_gzip:
            self.headers["Accept-Encoding"] = "gzip, deflate, br"
        if if_modified_since:
            self.headers["If-Modified-Since"] = if_modified_since
        self.command = command
        self.wfile = io.BytesIO()
        self.status = None
        self.sent_headers = {}

    def send_response(self, code, message=None):
        self.status = code

    def send_header(self, key, value):
        self.sent_headers[key.lower()] = value

    def end_headers(self):
        pass

    def date_time_string(self, timestamp=None):
        return email.utils.formatdate(timestamp, usegmt=True)


# ---------------------------------------------------------------------------
# gzip compression
# ---------------------------------------------------------------------------

class TestGzip:
    def test_client_accepts_gzip_detection(self):
        assert client_accepts_gzip(FakeHandler(accept_gzip=True)) is True
        assert client_accepts_gzip(FakeHandler(accept_gzip=False)) is False

    def test_large_body_is_compressed_when_accepted(self):
        h = FakeHandler(accept_gzip=True)
        body = b"a" * (GZIP_MIN_SIZE * 10)
        send_bytes(h, body, "text/html", compress=True)
        assert h.sent_headers["content-encoding"] == "gzip"
        wire = h.wfile.getvalue()
        assert gzip.decompress(wire) == body
        # Content-Length must describe the *compressed* bytes on the wire
        assert int(h.sent_headers["content-length"]) == len(wire)
        assert len(wire) < len(body)
        assert h.sent_headers["vary"] == "Accept-Encoding"

    def test_no_compression_without_accept_encoding(self):
        h = FakeHandler(accept_gzip=False)
        body = b"a" * (GZIP_MIN_SIZE * 10)
        send_bytes(h, body, "text/html", compress=True)
        assert "content-encoding" not in h.sent_headers
        assert h.wfile.getvalue() == body

    def test_tiny_body_not_compressed(self):
        h = FakeHandler(accept_gzip=True)
        send_bytes(h, b"ok", "text/plain", compress=True)
        assert "content-encoding" not in h.sent_headers
        assert h.wfile.getvalue() == b"ok"

    def test_compress_false_never_compresses(self):
        # Binary content (JPEG thumbnails) must not be gzipped
        h = FakeHandler(accept_gzip=True)
        body = b"\xff\xd8" + b"j" * (GZIP_MIN_SIZE * 4)
        send_bytes(h, body, "image/jpeg", compress=False)
        assert "content-encoding" not in h.sent_headers
        assert h.wfile.getvalue() == body

    def test_send_json_gzips_large_payload(self):
        h = FakeHandler(accept_gzip=True)
        data = [{"FilePath": f"/videos/{i}.mp4", "Size_MB": i} for i in range(500)]
        send_json(h, data)
        assert h.sent_headers["content-type"] == "application/json"
        assert h.sent_headers["content-encoding"] == "gzip"
        assert int(h.sent_headers["content-length"]) == len(h.wfile.getvalue())

    def test_send_json_always_has_content_length(self):
        h = FakeHandler()
        send_json(h, {"ok": True})
        assert int(h.sent_headers["content-length"]) == len(h.wfile.getvalue())

    def test_head_request_sends_no_body(self):
        h = FakeHandler(command="HEAD")
        send_bytes(h, b"hello world", "text/plain")
        assert h.wfile.getvalue() == b""
        assert h.sent_headers["content-length"] == "11"

    def test_cache_and_modified_headers(self):
        h = FakeHandler()
        send_bytes(
            h, b"x", "image/jpeg",
            cache_control="public, max-age=604800",
            last_modified=1700000000.0,
            extra_headers={"X-Test": "1"},
        )
        assert h.sent_headers["cache-control"] == "public, max-age=604800"
        assert h.sent_headers["last-modified"] == h.date_time_string(1700000000.0)
        assert h.sent_headers["x-test"] == "1"


# ---------------------------------------------------------------------------
# 304 Not Modified revalidation
# ---------------------------------------------------------------------------

class TestNotModified:
    MTIME = 1700000000.0

    def test_matching_validator_sends_304(self):
        stamp = email.utils.formatdate(self.MTIME, usegmt=True)
        h = FakeHandler(if_modified_since=stamp)
        assert send_not_modified_if_unchanged(h, self.MTIME) is True
        assert h.status == 304
        assert h.wfile.getvalue() == b""

    def test_stale_validator_returns_false(self):
        stamp = email.utils.formatdate(self.MTIME - 1000, usegmt=True)
        h = FakeHandler(if_modified_since=stamp)
        assert send_not_modified_if_unchanged(h, self.MTIME) is False
        assert h.status is None

    def test_no_header_returns_false(self):
        h = FakeHandler()
        assert send_not_modified_if_unchanged(h, self.MTIME) is False


# ---------------------------------------------------------------------------
# FinderHandler keep-alive safety net
# ---------------------------------------------------------------------------

def _make_finder_handler(command="GET"):
    """Build a FinderHandler without a real socket."""
    from arcade_scanner.server.api_handler import FinderHandler

    h = FinderHandler.__new__(FinderHandler)
    h.request_version = "HTTP/1.1"
    h.requestline = f"{command} /test HTTP/1.1"
    h.client_address = ("127.0.0.1", 12345)
    h.command = command
    h.path = "/test"
    h.headers = FakeHeaders()
    h.wfile = io.BytesIO()
    h.close_connection = False
    return h


def _sent_header_block(h):
    return h.wfile.getvalue().decode("latin-1")


class TestKeepAliveSafetyNet:
    def test_protocol_is_http_1_1(self):
        from arcade_scanner.server.api_handler import FinderHandler
        assert FinderHandler.protocol_version == "HTTP/1.1"

    def test_handler_has_idle_timeout(self):
        # Without a timeout, idle keep-alive connections pin threads forever
        from arcade_scanner.server.api_handler import FinderHandler
        assert FinderHandler.timeout is not None
        assert FinderHandler.timeout > 0

    def test_response_with_content_length_keeps_alive(self):
        h = _make_finder_handler()
        h.send_response(200)
        h.send_header("Content-Length", "5")
        h.end_headers()
        assert "Connection: close" not in _sent_header_block(h)
        assert h.close_connection is False

    def test_response_without_content_length_closes(self):
        h = _make_finder_handler()
        h.send_response(200)
        h.send_header("Content-Type", "application/json")
        h.end_headers()
        assert "Connection: close" in _sent_header_block(h)
        assert h.close_connection is True

    def test_post_always_closes(self):
        # POST closes even with Content-Length: an aborted handler that
        # didn't drain the request body must not poison the next request.
        h = _make_finder_handler(command="POST")
        h.send_response(200)
        h.send_header("Content-Length", "5")
        h.end_headers()
        assert "Connection: close" in _sent_header_block(h)

    def test_204_and_304_keep_alive_without_length(self):
        for status in (204, 304):
            h = _make_finder_handler()
            h.send_response(status)
            h.end_headers()
            assert "Connection: close" not in _sent_header_block(h), status
            assert h.close_connection is False, status

    def test_cors_headers_still_present(self):
        h = _make_finder_handler()
        h.headers["Origin"] = "http://tv.local"
        h.send_response(200)
        h.send_header("Content-Length", "0")
        h.end_headers()
        block = _sent_header_block(h)
        assert "Access-Control-Allow-Origin: http://tv.local" in block
        assert "Access-Control-Allow-Credentials: true" in block
