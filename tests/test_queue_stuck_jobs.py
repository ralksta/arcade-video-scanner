"""
test_queue_stuck_jobs.py
------------------------
Was passiert mit einem Job, dessen Arbeiter verschwindet?

Die Warteschlange hat dafür eine Antwort: `_reclaim_stale_locked()` setzt Jobs
zurück, die seit 15 Minuten nichts mehr gemeldet haben, und gibt nach drei
Versuchen auf. Sauber gebaut.

Sie hing nur an genau einer Stelle — `get_next_pending()`, also daran, dass ein
Arbeiter nach Arbeit fragt. Damit war sie in dem einen Fall wirkungslos, für
den sie gedacht ist:

    Der Server wird mitten im Encode neu gestartet.
    Der Mac, auf dem `mac_worker.py` lief, geht aus.
    Der Batch-Controller wird abgeschossen.

Danach steht der Job auf `encoding`, und es gibt niemanden mehr, der nach
Arbeit fragt — also auch niemanden, der aufräumt. Die Folgen greifen
ineinander:

    * das Dashboard zeigt den Job für immer als laufend
    * `get_active_queue_paths()` meldet die Datei dauerhaft als belegt
    * `queue_encode()` verweigert deshalb jedes erneute Einreihen

Die Datei liess sich danach nie wieder optimieren. Der einzige Ausweg wäre
gewesen, in der Datenbank von Hand aufzuräumen.

Aufgeräumt wird jetzt auch beim Lesen des Status. Das ist ein Lesezugriff, der
schreibt — vertretbar, weil der Entwurf ohnehin keinen Hintergrund-Scheduler
kennt („There is no background scheduler in this app, so reclaim lazily here")
und weil das Dashboard regelmässig fragt: Ein verwaister Job heilt sich, sobald
jemand hinsieht.
"""
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def store(tmp_path):
    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    with patch("arcade_scanner.database.sqlite_store.config", mock_config):
        from arcade_scanner.database.sqlite_store import SQLiteStore

        s = SQLiteStore()
        s._ensure_connection()
        yield s


def abandon(store, job_id, minutes_ago=30):
    """Versetzt einen laufenden Job in den Zustand „Arbeiter weg"."""
    long_ago = int(time.time()) - minutes_ago * 60
    conn = store._ensure_connection()
    with store._write_lock:
        conn.execute(
            "UPDATE encoding_queue SET status = 'encoding', started_at = ?, "
            "last_seen = ?, worker_id = 'toter-mac' WHERE id = ?",
            (long_ago, long_ago, job_id),
        )


def status_of(store, job_id):
    return store.get_job(job_id)["status"]


# --- Der Fund ---

def test_reading_the_queue_status_reclaims_an_abandoned_job(store):
    """
    Vorher blieb der Job auf `encoding` stehen, solange niemand nach Arbeit
    fragte — und nach einem Neustart fragt niemand mehr.
    """
    job_id = store.queue_encode("/media/film.mkv", size_bytes=100)
    store.get_next_pending(worker_id="mac")
    abandon(store, job_id)

    store.get_queue_status()

    assert status_of(store, job_id) == "pending"


def test_an_abandoned_job_returns_to_the_queue_when_the_paths_are_read(store):
    """
    Die eigentliche Sackgasse: `get_active_queue_paths()` entscheidet, ob eine
    Datei erneut eingereiht werden darf — und meldete sie unbegrenzt als
    „in Bearbeitung".

    Danach gilt die Datei weiterhin als aktiv, und das ist richtig: Der Job ist
    wieder `pending`, wird also erneut abgearbeitet. Entscheidend ist der
    Unterschied zwischen „wartet auf einen Arbeiter" und „hängt an einem
    Arbeiter, den es nicht mehr gibt".
    """
    store.queue_encode("/media/film.mkv", size_bytes=100)
    job_id = store.get_next_pending(worker_id="mac")["id"]
    abandon(store, job_id)

    store.get_active_queue_paths()

    assert status_of(store, job_id) == "pending"
    assert store.get_job(job_id)["attempts"] == 1, "Der Fehlversuch wird nicht gezählt"


def test_the_dashboard_no_longer_shows_it_as_running(store):
    store.queue_encode("/media/film.mkv", size_bytes=100)
    job_id = store.get_next_pending(worker_id="mac")["id"]
    abandon(store, job_id)

    jobs = {j["id"]: j for j in store.get_queue_status()}

    assert jobs[job_id]["status"] == "pending"
    assert jobs[job_id]["worker_id"] == "", "Der tote Arbeiter klebt noch am Job"


# --- Das Verhalten, das schon stimmte, darf sich nicht ändern ---

def test_a_job_that_still_reports_is_left_alone(store):
    """15 Minuten Frist — ein Encode darf lange dauern, ohne für tot zu gelten."""
    store.queue_encode("/media/film.mkv", size_bytes=100)
    job_id = store.get_next_pending(worker_id="mac")["id"]
    store.update_job_progress(job_id, progress_pct=42.0, phase="encode")

    store.get_queue_status()

    assert status_of(store, job_id) == "encoding" or status_of(store, job_id) == "downloading"


def test_a_pending_job_is_not_touched(store):
    job_id = store.queue_encode("/media/film.mkv", size_bytes=100)

    store.get_queue_status()

    assert status_of(store, job_id) == "pending"


def test_a_finished_job_is_not_resurrected(store):
    store.queue_encode("/media/film.mkv", size_bytes=100)
    job_id = store.get_next_pending(worker_id="mac")["id"]
    store.update_job_status(job_id, "done", saved_bytes=1234)

    store.get_queue_status()
    store.get_active_queue_paths()

    assert status_of(store, job_id) == "done"


def test_a_job_gives_up_after_the_configured_attempts(store):
    """
    Nach drei Anläufen ist Schluss — sonst kreist eine kaputte Datei ewig
    zwischen `pending` und `encoding`.
    """
    store.queue_encode("/media/film.mkv", size_bytes=100)

    for _ in range(4):
        job = store.get_next_pending(worker_id="mac")
        if job is None:
            break
        abandon(store, job["id"])
        store.get_queue_status()

    job_id = store.get_queue_status()[0]["id"]
    assert status_of(store, job_id) == "failed"
    assert "vanished" in (store.get_job(job_id)["result_message"] or "").lower()


def test_a_failed_job_frees_the_file_again(store):
    """Damit eine Datei nach dem Aufgeben erneut eingereiht werden kann."""
    store.queue_encode("/media/film.mkv", size_bytes=100)
    job_id = store.get_next_pending(worker_id="mac")["id"]
    store.update_job_status(job_id, "failed", result_message="kaputt")

    assert "/media/film.mkv" not in store.get_active_queue_paths()
    assert store.queue_encode("/media/film.mkv", size_bytes=100) is not None


# --- Der Weg, der schon vorher funktionierte ---

def test_a_new_worker_still_reclaims_when_asking_for_work(store):
    """Die ursprüngliche Stelle bleibt bestehen, sie war nur nicht genug."""
    store.queue_encode("/media/film.mkv", size_bytes=100)
    job_id = store.get_next_pending(worker_id="toter-mac")["id"]
    abandon(store, job_id)

    reclaimed = store.get_next_pending(worker_id="frischer-mac")

    assert reclaimed is not None
    assert reclaimed["id"] == job_id
