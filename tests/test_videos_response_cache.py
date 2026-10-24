"""
test_videos_response_cache.py
-----------------------------
Der Antwort-Cache für ``/api/videos``.

Gemessen an der echten Bibliothek (8788 Einträge, 4,95 MB JSON): ``json.dumps``
kostet ~40 ms, ``gzip.compress(level=6)`` ~54 ms — und beides lief bei *jedem*
Request neu, obwohl sich zwischen zwei Requests meist nichts ändert. Drei
Clients (Browser, TV, iOS) zahlen den Posten unabhängig voneinander.

Ein Cache auf so einem Pfad ist nur so gut wie seine Invalidierung. Die Tests
hier zielen deshalb weniger auf „ist es schnell" als auf „liefert es nie etwas
Veraltetes oder etwas, das einem anderen Nutzer gehört".
"""
import gzip
import json

import pytest

from arcade_scanner.server.api_handler import _VideosResponseCache
from arcade_scanner.server.response_helpers import GZIP_MIN_SIZE, send_json_precompressed


@pytest.fixture
def cache():
    return _VideosResponseCache()


def _payload(items):
    raw = json.dumps(items).encode("utf-8")
    return raw, gzip.compress(raw, compresslevel=6)


def test_returns_none_for_unknown_key(cache):
    assert cache.get((("/media",), False)) is None


def test_round_trip(cache):
    raw, gz = _payload([{"FilePath": "/media/a.mp4"}])
    key = (("/media",), False)
    cache.put(key, raw, gz)
    assert cache.get(key) == (raw, gz)


def test_different_scan_targets_never_share_an_entry(cache):
    """
    Der Schlüssel trennt Nutzer mit unterschiedlichen Scan-Zielen. Ohne das
    bekäme ein Nutzer die Bibliothek eines anderen zu sehen.
    """
    a_raw, a_gz = _payload([{"FilePath": "/media/a.mp4"}])
    b_raw, b_gz = _payload([{"FilePath": "/privat/b.mp4"}])

    cache.put((("/media",), False), a_raw, a_gz)
    cache.put((("/privat",), False), b_raw, b_gz)

    assert cache.get((("/media",), False))[0] == a_raw
    assert cache.get((("/privat",), False))[0] == b_raw


def test_admin_flag_is_part_of_the_key(cache):
    """Ein Admin ohne Targets sieht alles — ein Nicht-Admin nicht."""
    raw, gz = _payload([{"FilePath": "/media/a.mp4"}])
    cache.put(((), True), raw, gz)
    assert cache.get(((), False)) is None


def test_invalidate_clears_everything(cache):
    raw, gz = _payload([{"FilePath": "/media/a.mp4"}])
    cache.put((("/media",), False), raw, gz)
    cache.put((("/privat",), False), raw, gz)

    cache.invalidate()

    assert cache.get((("/media",), False)) is None
    assert cache.get((("/privat",), False)) is None


def test_cache_is_bounded(cache):
    """Viele unterschiedliche Target-Sätze dürfen den Speicher nicht sprengen."""
    raw, gz = _payload([{"FilePath": "/media/a.mp4"}])
    for i in range(cache.MAX_ENTRIES + 5):
        cache.put(((f"/t{i}",), False), raw, gz)

    assert len(cache._entries) <= cache.MAX_ENTRIES
    # Der zuletzt geschriebene Eintrag ist noch da, der erste nicht mehr.
    assert cache.get(((f"/t{cache.MAX_ENTRIES + 4}",), False)) is not None
    assert cache.get((("/t0",), False)) is None


def test_media_cache_invalidation_cascades_to_the_response_cache():
    """
    Der Antwort-Cache ist aus dem Medien-Cache abgeleitet und muss mit ihm
    verfallen. Zwei Aufrufer (routes/settings.py, routes/queue.py) rufen
    ``_media_cache.invalidate()`` direkt auf, nicht über
    ``db.register_on_change`` — ohne die Kopplung lieferte das Dashboard dort
    nach dem Löschen aller Fotos bzw. nach einem Encode-Upload alte Daten.
    """
    from arcade_scanner.server.api_handler import _MediaCache

    media = _MediaCache()
    response = _VideosResponseCache()
    media.register_dependent(response)

    raw, gz = _payload([{"FilePath": "/media/a.mp4"}])
    response.put((("/media",), False), raw, gz)

    media.invalidate()

    assert response.get((("/media",), False)) is None


def test_direct_invalidation_callers_are_covered():
    """
    Gegenprobe am echten Code: Wer den Medien-Cache direkt invalidiert, muss
    den Antwort-Cache nicht kennen.
    """
    root = __import__("pathlib").Path(__file__).parent.parent
    handler_src = (root / "arcade_scanner" / "server" / "api_handler.py").read_text(encoding="utf-8")
    assert "_media_cache.register_dependent(_videos_response_cache)" in handler_src

    for route in ("settings.py", "queue.py"):
        src = (root / "arcade_scanner" / "server" / "routes" / route).read_text(encoding="utf-8")
        if "_media_cache.invalidate()" in src:
            assert "_videos_response_cache" not in src, (
                f"{route} kennt den abgeleiteten Cache direkt — die Kopplung "
                "über register_dependent macht das unnötig."
            )


# --- Auslieferung ---

class _FakeHandler:
    """Minimaler Handler, der nur mitschreibt, was gesendet wurde."""

    def __init__(self, accept_encoding=""):
        self.headers = {"Accept-Encoding": accept_encoding}
        self.command = "GET"
        self.status = None
        self.sent_headers = {}
        self.body = b""

    def send_response(self, status):
        self.status = status

    def send_header(self, key, value):
        self.sent_headers[key] = value

    def end_headers(self):
        pass

    @property
    def wfile(self):
        handler = self

        class _Writer:
            def write(self, data):
                handler.body = data

        return _Writer()


def test_gzip_client_gets_the_compressed_body():
    raw, gz = _payload([{"FilePath": f"/media/{i}.mp4"} for i in range(200)])
    assert len(raw) >= GZIP_MIN_SIZE, "Testdaten zu klein, um Kompression auszulösen"

    handler = _FakeHandler(accept_encoding="gzip, deflate")
    send_json_precompressed(handler, raw, gz)

    assert handler.sent_headers["Content-Encoding"] == "gzip"
    assert handler.body == gz
    assert handler.sent_headers["Content-Length"] == str(len(gz))


def test_client_without_gzip_gets_the_raw_body():
    raw, gz = _payload([{"FilePath": f"/media/{i}.mp4"} for i in range(200)])

    handler = _FakeHandler(accept_encoding="")
    send_json_precompressed(handler, raw, gz)

    assert "Content-Encoding" not in handler.sent_headers
    assert handler.body == raw


def test_vary_header_is_always_set():
    """
    Ohne ``Vary: Accept-Encoding`` liefert ein Proxy einem Client ohne
    gzip-Unterstützung die komprimierte Antwort aus.
    """
    raw, gz = _payload([{"FilePath": f"/media/{i}.mp4"} for i in range(200)])
    for accept in ("gzip", ""):
        handler = _FakeHandler(accept_encoding=accept)
        send_json_precompressed(handler, raw, gz)
        assert handler.sent_headers["Vary"] == "Accept-Encoding"


def test_head_request_sends_headers_but_no_body():
    raw, gz = _payload([{"FilePath": f"/media/{i}.mp4"} for i in range(200)])
    handler = _FakeHandler(accept_encoding="gzip")
    handler.command = "HEAD"

    send_json_precompressed(handler, raw, gz)

    assert handler.sent_headers["Content-Length"] == str(len(gz))
    assert handler.body == b""


def test_small_bodies_are_sent_uncompressed():
    """Unter GZIP_MIN_SIZE lohnt der Header-Overhead nicht."""
    raw, gz = _payload([{"a": 1}])
    assert len(raw) < GZIP_MIN_SIZE

    handler = _FakeHandler(accept_encoding="gzip")
    send_json_precompressed(handler, raw, gz)

    assert "Content-Encoding" not in handler.sent_headers
    assert handler.body == raw
