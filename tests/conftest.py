# tests/conftest.py
"""
Shared pytest fixtures for arcade-video-scanner tests.
"""
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _no_background_report_generation(monkeypatch):
    """Hält den Report-Debouncer aus der Test-Suite heraus.

    ``ReportDebouncer.schedule()`` startet einen ``threading.Timer``, der eine
    Sekunde später auf einem Daemon-Thread ``_media_cache.get()`` aufruft. Zu
    diesem Zeitpunkt ist der ``config``-Patch des auslösenden Tests längst
    wieder abgeräumt — der Timer greift also auf das echte ``db``-Singleton zu,
    öffnet ``arcade_data/media_library.db`` (und wendet dabei alle
    Schema-Migrationen an) und überschreibt ``arcade_data/index.html``.

    Nachgewiesen über einen Stack-Trace aus ``_generate``: ein voller
    ``pytest``-Lauf hat die Produktivdatenbank des Entwicklers migriert und
    dessen index.html neu geschrieben. Ein einzelner Testlauf reproduziert das
    nicht zuverlässig, weil der Prozess oft schon vor Ablauf der Sekunde endet
    — genau deshalb ist es so lange unbemerkt geblieben.

    Der Ersatz merkt sich die Aufrufe, damit Tests weiterhin prüfen können,
    *dass* eine Route den Report anstößt.
    """
    from arcade_scanner.server import api_handler

    calls = []
    monkeypatch.setattr(
        api_handler.report_debouncer, "schedule", lambda port: calls.append(port)
    )
    yield calls


@pytest.fixture
def tmp_db(tmp_path) -> Path:
    """Return a path for a temporary SQLite database (isolated per test)."""
    return tmp_path / "test_media.db"


@pytest.fixture
def sample_video_entry():
    """Minimal valid VideoEntry-like dict."""
    return {
        "FilePath": "/fake/video.mp4",
        "Status": "OK",
        "Size_MB": 100.0,
        "Codec": "h264",
        "Bitrate_kbps": 3000,
        "Width": 1920,
        "Height": 1080,
        "Duration": 60.0,
        "mtime": 1700000000.0,
        "favorite": False,
        "vaulted": False,
        "tags": [],
    }
