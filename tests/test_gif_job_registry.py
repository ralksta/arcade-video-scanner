"""
test_gif_job_registry.py
------------------------
Der Zustandsspeicher der GIF-Aufträge wächst nicht unbegrenzt.

`GIF_JOBS` war ein nacktes Modul-Dict: jeder Export schrieb hinein, entfernt
wurde nie etwas. Auf einem Server, der monatelang läuft — und darum geht es bei
einem selbst gehosteten Werkzeug —, sammeln sich dort Dateinamen und Pfade
sämtlicher je erzeugter GIFs an. Kein dramatisches Leck, aber eines, das
niemals aufhört.

Dazu kam: geschrieben wird aus Worker-Threads, gelesen aus Request-Threads.
"""
import threading
import time

import pytest

from arcade_scanner.server.routes.queue import _GifJobRegistry


@pytest.fixture
def registry():
    return _GifJobRegistry()


def test_round_trip(registry):
    registry["job-1"] = {"status": "processing"}
    assert registry.get("job-1") == {"status": "processing"}
    assert "job-1" in registry


def test_unknown_job_returns_the_default(registry):
    assert registry.get("gibtsnicht") is None
    assert registry.get("gibtsnicht", {"status": "?"}) == {"status": "?"}
    assert "gibtsnicht" not in registry


def test_in_place_progress_updates_still_work(registry):
    """
    Der Worker schreibt Fortschritt als ``GIF_JOBS[id]["progress"] = ...`` —
    eine Mutation am zurückgegebenen Dict. Das muss weiterhin durchschlagen.
    """
    registry["job-1"] = {"status": "processing", "progress": "Starting..."}
    registry["job-1"]["progress"] = "Rendering GIF..."

    assert registry.get("job-1")["progress"] == "Rendering GIF..."


def test_entry_count_is_capped(registry):
    for i in range(registry.MAX_ENTRIES + 50):
        registry[f"job-{i}"] = {"status": "done"}

    assert len(registry) <= registry.MAX_ENTRIES


def test_the_newest_entries_survive_the_cap(registry):
    """
    Verdrängt werden die ältesten — der gerade laufende Auftrag darf nicht
    verschwinden, während sein Client noch pollt.
    """
    for i in range(registry.MAX_ENTRIES + 10):
        registry[f"job-{i}"] = {"status": "done"}

    newest = f"job-{registry.MAX_ENTRIES + 9}"
    assert registry.get(newest) is not None
    assert registry.get("job-0") is None


def test_old_entries_expire(registry, monkeypatch):
    registry["alt"] = {"status": "done"}

    # Eine Stunde und eine Sekunde später
    real_time = time.time
    monkeypatch.setattr(time, "time", lambda: real_time() + registry.TTL_SECONDS + 1)

    registry["neu"] = {"status": "processing"}   # Schreibzugriff räumt auf

    assert registry.get("alt") is None
    assert registry.get("neu") is not None


def test_fresh_entries_are_not_expired(registry):
    registry["job-1"] = {"status": "done"}
    registry["job-2"] = {"status": "done"}

    assert registry.get("job-1") is not None
    assert registry.get("job-2") is not None


def test_concurrent_writers_do_not_lose_entries(registry):
    """
    Worker-Threads schreiben, Request-Threads lesen. Unter dem Lock darf dabei
    nichts verloren gehen und nichts hängen bleiben.
    """
    errors = []

    def write(start):
        try:
            for i in range(start, start + 20):
                registry[f"job-{i}"] = {"status": "done"}
                registry.get(f"job-{i}")
        except Exception as e:  # pragma: no cover — soll nicht eintreten
            errors.append(e)

    threads = [threading.Thread(target=write, args=(n * 20,)) for n in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors
    assert len(registry) == 100   # unter MAX_ENTRIES, also alle erhalten


def test_registry_is_used_by_the_route():
    from arcade_scanner.server.routes.queue import GIF_JOBS

    assert isinstance(GIF_JOBS, _GifJobRegistry)


def test_ttl_outlives_a_normal_export():
    """
    Der Client pollt im Sekundentakt bis „done" und lädt dann herunter. Die
    Aufbewahrung muss deutlich darüber liegen, sonst verschwindet ein Auftrag
    unter dem Client weg.
    """
    assert _GifJobRegistry.TTL_SECONDS >= 600
