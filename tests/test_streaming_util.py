"""
test_streaming_util.py
----------------------
Unit tests for the HTTP range/streaming implementation.

Why this exists:
    Video seeking depends entirely on correct Range handling. A wrong
    Content-Length (e.g. from an unclamped "bytes=0-999999999" request)
    makes a keep-alive client hang forever waiting for promised bytes.
    These tests pin down range parsing, clamping, suffix ranges, 416
    handling, and the sendfile/chunk-loop fallback paths.
"""
import email.utils
import io

import pytest

from arcade_scanner.server.streaming_util import (
    CHUNK_SIZE,
    parse_range_header,
    serve_file_range,
)

# ---------------------------------------------------------------------------
# parse_range_header
# ---------------------------------------------------------------------------

class TestParseRangeHeader:
    def test_no_header_returns_none(self):
        assert parse_range_header(None, 1000) is None

    def test_simple_range(self):
        assert parse_range_header("bytes=0-499", 1000) == (0, 499)

    def test_open_ended_range(self):
        assert parse_range_header("bytes=500-", 1000) == (500, 999)

    def test_end_clamped_to_file_size(self):
        # Over-long end must be clamped, otherwise Content-Length lies
        assert parse_range_header("bytes=0-999999", 1000) == (0, 999)

    def test_suffix_range(self):
        # "last 200 bytes" of a 1000-byte file
        assert parse_range_header("bytes=-200", 1000) == (800, 999)

    def test_suffix_range_larger_than_file(self):
        assert parse_range_header("bytes=-5000", 1000) == (0, 999)

    def test_start_beyond_file_is_unsatisfiable(self):
        assert parse_range_header("bytes=1000-", 1000) == "unsatisfiable"

    def test_inverted_range_is_unsatisfiable(self):
        assert parse_range_header("bytes=500-100", 1000) == "unsatisfiable"

    def test_zero_suffix_is_unsatisfiable(self):
        assert parse_range_header("bytes=-0", 1000) == "unsatisfiable"

    def test_malformed_header_returns_none(self):
        assert parse_range_header("bytes=abc-def", 1000) is None
        assert parse_range_header("bites=0-100", 1000) is None
        assert parse_range_header("bytes=-", 1000) is None


# ---------------------------------------------------------------------------
# serve_file_range with a fake handler
# ---------------------------------------------------------------------------

class FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class FakeHandler:
    """Mimics the BaseHTTPRequestHandler surface serve_file_range touches."""

    def __init__(self, range_header=None, with_sendfile=False):
        self.headers = FakeHeaders()
        if range_header:
            self.headers["Range"] = range_header
        self.wfile = io.BytesIO()
        self.status = None
        self.sent_headers = {}
        self.error = None
        self.close_connection = False
        self.command = "GET"
        if with_sendfile:
            self.connection = _FakeConnection(self.wfile)
        # no `connection` attribute at all otherwise → chunk-loop fallback

    def send_response(self, code, message=None):
        self.status = code

    def send_header(self, key, value):
        self.sent_headers[key.lower()] = value

    def end_headers(self):
        pass

    def send_error(self, code, message=None):
        self.error = code

    def date_time_string(self, timestamp=None):
        return email.utils.formatdate(timestamp, usegmt=True)


class _FakeConnection:
    def __init__(self, wfile):
        self._wfile = wfile
        self.sendfile_calls = []

    def sendfile(self, f, offset=0, count=None):
        self.sendfile_calls.append((offset, count))
        f.seek(offset)
        self._wfile.write(f.read(count))
        return count


@pytest.fixture
def video_file(tmp_path):
    p = tmp_path / "clip.mp4"
    p.write_bytes(bytes(range(256)) * 40)  # 10240 bytes, recognizable pattern
    return p


class TestServeFileRange:
    def test_missing_file_sends_404(self, tmp_path):
        h = FakeHandler()
        serve_file_range(h, str(tmp_path / "nope.mp4"))
        assert h.error == 404

    def test_full_file_without_range(self, video_file):
        h = FakeHandler()
        serve_file_range(h, str(video_file))
        assert h.status == 200
        assert h.sent_headers["content-length"] == "10240"
        assert h.sent_headers["accept-ranges"] == "bytes"
        assert "last-modified" in h.sent_headers
        assert h.wfile.getvalue() == video_file.read_bytes()

    def test_range_request_sends_exact_slice(self, video_file):
        h = FakeHandler(range_header="bytes=100-199")
        serve_file_range(h, str(video_file))
        assert h.status == 206
        assert h.sent_headers["content-range"] == "bytes 100-199/10240"
        assert h.sent_headers["content-length"] == "100"
        assert h.wfile.getvalue() == video_file.read_bytes()[100:200]

    def test_range_bytes_written_match_content_length(self, video_file):
        # Keep-alive correctness: announced length == bytes on the wire
        h = FakeHandler(range_header="bytes=5000-")
        serve_file_range(h, str(video_file))
        assert len(h.wfile.getvalue()) == int(h.sent_headers["content-length"])

    def test_overlong_range_is_clamped(self, video_file):
        h = FakeHandler(range_header="bytes=0-99999999")
        serve_file_range(h, str(video_file))
        assert h.status == 206
        assert h.sent_headers["content-length"] == "10240"
        assert len(h.wfile.getvalue()) == 10240

    def test_suffix_range(self, video_file):
        h = FakeHandler(range_header="bytes=-100")
        serve_file_range(h, str(video_file))
        assert h.status == 206
        assert h.sent_headers["content-range"] == "bytes 10140-10239/10240"
        assert h.wfile.getvalue() == video_file.read_bytes()[-100:]

    def test_unsatisfiable_range_sends_416(self, video_file):
        h = FakeHandler(range_header="bytes=99999-")
        serve_file_range(h, str(video_file))
        assert h.status == 416
        assert h.sent_headers["content-range"] == "bytes */10240"
        assert h.sent_headers["content-length"] == "0"
        assert h.wfile.getvalue() == b""

    def test_head_request_sends_headers_only(self, video_file):
        h = FakeHandler(range_header="bytes=0-499")
        serve_file_range(h, str(video_file), method="HEAD")
        assert h.status == 206
        assert h.sent_headers["content-length"] == "500"
        assert h.wfile.getvalue() == b""

    def test_sendfile_path_used_when_available(self, video_file):
        h = FakeHandler(range_header="bytes=200-299", with_sendfile=True)
        serve_file_range(h, str(video_file))
        assert h.connection.sendfile_calls == [(200, 100)]
        assert h.wfile.getvalue() == video_file.read_bytes()[200:300]

    def test_broken_pipe_flags_connection_close(self, video_file):
        class BrokenPipeWfile:
            def write(self, data):
                raise BrokenPipeError()

            def flush(self):
                pass

        h = FakeHandler(range_header="bytes=0-499")
        h.wfile = BrokenPipeWfile()
        serve_file_range(h, str(video_file))
        # Partial write → connection must never be reused for keep-alive
        assert h.close_connection is True

    def test_large_file_chunk_loop(self, tmp_path):
        # File larger than one chunk exercises the loop arithmetic
        big = tmp_path / "big.mp4"
        big.write_bytes(b"x" * (CHUNK_SIZE + 4096))
        h = FakeHandler()
        serve_file_range(h, str(big))
        assert len(h.wfile.getvalue()) == CHUNK_SIZE + 4096


# ---------------------------------------------------------------------------
# Kurz gelieferte Streams
#
# `socket.sendfile()` wirft nicht, wenn die Datei kürzer ist als erwartet — sie
# gibt die tatsächlich gesendete Zahl zurück. Nachgemessen mit einem echten
# Socket-Paar: bei einer auf 100 Bytes gekürzten Datei meldet sie 100, obwohl
# 10000 angefordert waren. Kein Fehler, keine Ausnahme.
#
# Der Content-Length-Kopf ist zu dem Zeitpunkt längst raus. Der Client wartet
# also auf Bytes, die nie kommen: bei Keep-Alive bis zum Timeout, und danach
# wird die Verbindung in verdorbenem Zustand wiederverwendet — genau das
# Szenario, gegen das die Clamping-Tests weiter oben schützen sollten.
#
# Erreichbar ist das hier ganz konkret: Zwischen `os.stat()` und dem Senden
# liegt ein Zeitfenster, und der Optimierer ersetzt Mediendateien an Ort und
# Stelle (`atomic_replace`, `keep_optimized`). Wer ein Video ansieht, während
# es umgewandelt wird, landet hier.
#
# Verhindern lässt es sich nicht — die Datei *ist* dann kürzer. Aus einem
# hängenden Client wird aber ein sauber abgebrochener.
# ---------------------------------------------------------------------------

class _ShortSendConnection(_FakeConnection):
    """Ein sendfile, das weniger liefert als angefordert."""

    def __init__(self, wfile, actually_sends):
        super().__init__(wfile)
        self._actually_sends = actually_sends

    def sendfile(self, f, offset=0, count=None):
        self.sendfile_calls.append((offset, count))
        f.seek(offset)
        self._wfile.write(f.read(self._actually_sends))
        return self._actually_sends


class TestShortSend:
    def test_a_short_sendfile_closes_the_connection(self, video_file):
        h = FakeHandler(with_sendfile=True)
        h.connection = _ShortSendConnection(h.wfile, actually_sends=100)

        serve_file_range(h, str(video_file))

        assert h.close_connection is True, (
            "Der Client wartet sonst auf 10140 Bytes, die nie kommen"
        )

    def test_a_complete_sendfile_keeps_the_connection(self, video_file):
        h = FakeHandler(with_sendfile=True)

        serve_file_range(h, str(video_file))

        assert h.close_connection is False

    def test_the_short_send_is_reported(self, video_file, capsys):
        h = FakeHandler(with_sendfile=True)
        h.connection = _ShortSendConnection(h.wfile, actually_sends=100)

        serve_file_range(h, str(video_file))

        out = capsys.readouterr().out
        assert "verkürzt" in out
        assert "100" in out and "10240" in out

    def test_a_short_range_send_closes_the_connection(self, video_file):
        """Auch im 206-Fall — dort ist die angekündigte Länge der Bereich."""
        h = FakeHandler(range_header="bytes=0-999", with_sendfile=True)
        h.connection = _ShortSendConnection(h.wfile, actually_sends=10)

        serve_file_range(h, str(video_file))

        assert h.close_connection is True

    def test_a_truncated_file_in_the_chunk_loop_also_closes(self, tmp_path):
        """
        Der Rückfallweg ohne sendfile bricht bei EOF genauso still ab. Hier
        wird die Datei zwischen `os.stat()` und dem Lesen wirklich gekürzt.
        """
        path = tmp_path / "clip.mp4"
        path.write_bytes(b"X" * 10000)

        h = FakeHandler()  # kein `connection` → Leseschleife

        import arcade_scanner.server.streaming_util as su

        real_open = open

        def shrinking_open(p, *args, **kwargs):
            # Genau im Moment des Öffnens ist die Datei nur noch 100 Bytes lang
            if str(p) == str(path):
                path.write_bytes(b"X" * 100)
            return real_open(p, *args, **kwargs)

        su_open = getattr(su, "open", None)
        try:
            su.open = shrinking_open
            serve_file_range(h, str(path))
        finally:
            if su_open is None:
                del su.open
            else:
                su.open = su_open

        assert h.close_connection is True

    def test_a_client_that_hangs_up_still_closes_the_connection(self, video_file):
        """Das Verhalten, das schon vorher stimmte, darf nicht verloren gehen."""
        h = FakeHandler()

        class Exploding(io.BytesIO):
            def write(self, data):
                raise BrokenPipeError("client weg")

        h.wfile = Exploding()
        serve_file_range(h, str(video_file))

        assert h.close_connection is True
