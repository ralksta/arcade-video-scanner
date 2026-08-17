"""
test_concurrent_scans.py
------------------------
Zwei Anfragen konnten zwei vollständige Scans starten.

`run_scan()` begann mit zwei einzelnen Zeilen:

    if self.is_scanning:
        return 0
    self.is_scanning = True

Dazwischen kann ein anderer Thread laufen. Und er tut es: Die Route
(`_handle_rescan`) prüft ihrerseits nur `mgr.is_scanning` und startet dann
einen eigenen Thread — der Server ist ein `ThreadingTCPServer`, jede Anfrage
hat einen. Zweimal geklickt, oder der Fernseher und der Browser kurz
hintereinander, und beide sahen „läuft nicht".

Die Folge ist kein stiller Datenfehler, sondern eine laute Belastung: zwei
vollständige Durchläufe über 8788 Dateien, doppelte ffprobe-Prozesse auf allen
Kernen, zwei Schreiber auf derselben SQLite-Datei. Auf einem Heimserver, der
nebenbei noch Videos ausliefert, merkt man das.

Nachsehen und Belegen läuft jetzt unter einer Sperre.

Geprüft wird mit echten Threads: Ein nachgestelltes „genau hier dazwischen"
würde nur zeigen, dass man das Fenster kennt — nicht, dass es zu ist.
"""
import asyncio
import threading
import time

import pytest


@pytest.fixture
def manager():
    """Ein ScannerManager ohne die schweren Bestandteile."""
    from unittest.mock import MagicMock, patch

    with patch("arcade_scanner.scanner.manager.MediaProbe", MagicMock()), \
            patch("arcade_scanner.scanner.manager.VideoInspector", MagicMock()), \
            patch("arcade_scanner.scanner.manager.ImageInspector", MagicMock()):
        from arcade_scanner.scanner.manager import ScannerManager

        yield ScannerManager()


def belege(manager, dauer=0.05):
    """Belegt den Scanner über den Weg, den `run_scan()` selbst geht.

    Absichtlich `manager._claim()` und keine Nachbildung: Eine Nachbildung
    würde zeigen, dass ich die Sperre kenne — nicht, dass der Ablauf sie
    benutzt.
    """
    if not manager._claim():
        return False
    time.sleep(dauer)
    manager.is_scanning = False
    return True


# --- Der Fund ---

def test_only_one_of_many_threads_gets_the_scanner(manager):
    """
    Zwanzig gleichzeitige Anfragen, einer darf loslaufen.
    """
    ergebnisse = []
    start = threading.Barrier(20)

    def versucht():
        start.wait()
        ergebnisse.append(belege(manager))

    threads = [threading.Thread(target=versucht) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert ergebnisse.count(True) == 1, ergebnisse


def test_the_scanner_is_free_again_afterwards(manager):
    assert belege(manager) is True

    assert manager.is_scanning is False
    assert belege(manager) is True


# --- Am echten Einstieg ---

def test_a_second_run_scan_returns_immediately(manager):
    """
    Nicht nur die Sperre für sich — der Einstieg selbst muss den zweiten
    Aufruf abweisen, ohne irgendetwas anzufassen.
    """
    manager.is_scanning = True

    ergebnis = asyncio.run(manager.run_scan())

    assert ergebnis == 0
    # Und der laufende Durchlauf ist dabei nicht freigegeben worden.
    assert manager.is_scanning is True


def test_the_rejected_call_does_not_clear_the_flag(manager):
    """
    Der Fehler, den man beim Umbauen leicht macht: Der abgewiesene Aufruf
    landet im `finally` und setzt `is_scanning` auf False — womit der dritte
    Aufruf mitten in den laufenden Scan hineinstartet.
    """
    manager.is_scanning = True

    asyncio.run(manager.run_scan())
    asyncio.run(manager.run_scan())

    assert manager.is_scanning is True


# --- Struktur ---

def test_check_and_claim_happen_under_the_same_lock():
    """
    Stünden sie wieder einzeln da, wäre das Fenster zurück — und dieser Test
    ist die einzige Stelle, an der das auffiele.
    """
    import re
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "scanner"
              / "manager.py").read_text(encoding="utf-8")
    quelle = re.sub(r"#.*$", "", quelle, flags=re.M)

    block = quelle[quelle.index("def _claim"):]
    block = block[:block.index("async def run_scan")]

    assert "with self._state_lock:" in block
    sperre = block.index("with self._state_lock:")
    assert block.index("if self.is_scanning:") > sperre
    assert block.index("self.is_scanning = True") > sperre

    # Und der Ablauf benutzt sie auch.
    ablauf = quelle[quelle.index("async def run_scan"):]
    ablauf = ablauf[:ablauf.index("self._stop_event.clear()")]
    assert "self._claim()" in ablauf


def test_the_route_still_answers_409_for_the_obvious_case():
    """
    Die Vorprüfung in der Route bleibt: Sie liefert dem Nutzer die ehrliche
    Antwort „läuft schon", statt ihm 202 zu sagen und nichts zu tun.
    """
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "server"
              / "routes" / "files.py").read_text(encoding="utf-8")

    assert 'handler.send_error(409, "Scan already in progress")' in quelle
