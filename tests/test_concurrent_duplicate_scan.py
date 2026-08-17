"""
test_concurrent_duplicate_scan.py
---------------------------------
Zwei Anfragen konnten zwei Duplikat-Suchen starten — derselbe Fehler wie beim
Scanner, an der zweiten Stelle.

Die Route prüft `is_running` und startet dann einen Thread; der Thread setzte
`is_running=True` bedingungslos. Zwei Anfragen kurz hintereinander sahen beide
„läuft nicht".

Hier ist die Folge unangenehmer als beim Scanner: Beide Läufe rechnen
Wahrnehmungs-Hashes über die ganze Bibliothek — teuer —, und beide schreiben in
**denselben** Fortschritt und **dieselbe** Ergebnisliste. Der Balken springt
zwischen zwei Zählungen hin und her, und wer zuletzt fertig wird, überschreibt
die Funde des anderen. Für den Nutzer sieht das aus, als hätte die Suche etwas
übersehen.

Belegen und Nachsehen steckt jetzt in `try_begin()` unter derselben Sperre, die
der Zustand ohnehin hat — wie `ScannerManager._claim()`.
"""
import threading

import pytest

from arcade_scanner.server.api_handler import DuplicateScanManager


@pytest.fixture
def mgr():
    return DuplicateScanManager()


# --- Der Fund ---

def test_only_one_of_many_threads_may_begin(mgr):
    ergebnisse = []
    start = threading.Barrier(20)

    def versucht():
        start.wait()
        ergebnisse.append(mgr.try_begin())

    threads = [threading.Thread(target=versucht) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert ergebnisse.count(True) == 1, ergebnisse


def test_beginning_marks_it_running(mgr):
    assert mgr.try_begin() is True

    assert mgr.get_state()["is_running"] is True


def test_a_second_attempt_is_refused_until_it_ends(mgr):
    mgr.try_begin()

    assert mgr.try_begin() is False

    mgr.update_state(is_running=False)
    assert mgr.try_begin() is True


# --- Der Anfangszustand kommt mit ---

def test_the_initial_state_is_set_in_the_same_step(mgr):
    """
    Sonst stünde zwischen „belegt" und „Fortschritt zurückgesetzt" ein
    Augenblick, in dem die Statusabfrage den Rest des vorigen Laufs zeigt.
    """
    mgr.update_state(progress=100, message="Scan complete", has_more=True)

    mgr.try_begin(progress=0, message="Initializing scan...", has_more=False,
                  batch_offset=0)

    zustand = mgr.get_state()
    assert zustand["progress"] == 0
    assert zustand["message"] == "Initializing scan..."
    assert zustand["has_more"] is False


def test_a_refused_attempt_changes_nothing(mgr):
    """
    Der zweite Aufruf darf den laufenden nicht zurücksetzen — sonst springt
    der Balken des ersten auf null.
    """
    mgr.try_begin(progress=0)
    mgr.update_state(progress=42, message="Hashing images")

    mgr.try_begin(progress=0, message="Initializing scan...")

    zustand = mgr.get_state()
    assert zustand["progress"] == 42
    assert zustand["message"] == "Hashing images"


# --- Am echten Einstieg ---

def test_the_worker_returns_immediately_when_one_is_running(monkeypatch):
    """
    Nicht nur die Sperre für sich: Der Hintergrundlauf selbst muss abbrechen,
    bevor er die Datenbank anfasst.
    """
    from arcade_scanner.server import api_handler

    api_handler._dup_mgr.update_state(is_running=True)
    angefasst = []
    monkeypatch.setattr(api_handler.db, "get_all",
                        lambda: angefasst.append(1) or [])

    try:
        api_handler.background_duplicate_scan()
    finally:
        api_handler._dup_mgr.update_state(is_running=False)

    assert angefasst == []


def test_the_refused_worker_does_not_clear_the_flag(monkeypatch):
    """
    Der Fehler, den man beim Umbauen macht: Der abgewiesene Lauf fällt ins
    `finally` und meldet den laufenden als beendet.
    """
    from arcade_scanner.server import api_handler

    api_handler._dup_mgr.update_state(is_running=True)
    try:
        api_handler.background_duplicate_scan()

        assert api_handler._dup_mgr.get_state()["is_running"] is True
    finally:
        api_handler._dup_mgr.update_state(is_running=False)


# --- Struktur ---

def test_the_route_still_answers_409():
    """
    Die Vorprüfung bleibt: Sie gibt dem Nutzer die ehrliche Antwort, statt
    202 zu melden und nichts zu tun.
    """
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "server"
              / "routes" / "duplicates.py").read_text(encoding="utf-8")

    assert 'handler.send_error(409, "Scan already in progress")' in quelle


def test_both_managers_use_the_same_shape():
    """
    Derselbe Fehler stand an zwei Stellen. Wenn die Lösung verschieden
    aussieht, findet die nächste Person nur eine davon.
    """
    from pathlib import Path

    root = Path(__file__).parent.parent / "arcade_scanner"
    scanner = (root / "scanner" / "manager.py").read_text(encoding="utf-8")
    server = (root / "server" / "api_handler.py").read_text(encoding="utf-8")

    assert "def _claim(self) -> bool:" in scanner
    assert "def try_begin(self, **kwargs) -> bool:" in server
