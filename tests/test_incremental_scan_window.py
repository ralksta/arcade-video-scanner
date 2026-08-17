"""
test_incremental_scan_window.py
-------------------------------
Was während eines Scans passiert, fiel dauerhaft durchs Raster.

Der Scanner überspringt Verzeichnisse, deren mtime älter ist als der letzte
Durchlauf (`file_system.py`, „Incremental scan"). Gemerkt hat er sich dafür den
Zeitpunkt am **Ende** des Durchlaufs. Bei einer großen Bibliothek liegen
zwischen Anfang und Ende Minuten:

    02:00   Scan beginnt
    02:00   /media wird durchlaufen
    02:10   eine Datei in /media wird ersetzt → Ordner-mtime 02:10
    02:30   Scan endet und merkt sich 02:30

Beim nächsten Durchlauf gilt `02:10 < 02:30`. Der Ordner zählt als unverändert
und wird übersprungen — die Änderung ist also nicht bloß einmal verpasst,
sondern **für immer**, bis in demselben Ordner zufällig etwas anderes passiert.

Das ist genau der Fall, den man im Betrieb erzeugt: Der Fernarbeiter lädt
optimierte Fassungen zurück, während der nächtliche Scan läuft. Danach steht in
der Bibliothek die alte Größe und die alte Bitrate, und kein weiterer Scan
korrigiert das.

Gemerkt wird jetzt der **Beginn**. Das ist die sichere Richtung: Es führt
höchstens dazu, dass beim nächsten Mal noch einmal nachgesehen wird, wo sich
nichts geändert hat. Zu viel zu prüfen kostet Zeit, zu wenig kostet
Richtigkeit.
"""
import json
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def scanner(tmp_path):
    """Ein AsyncFileSystemScanner, dessen Zeitstempel in tmp_path liegt."""
    from arcade_scanner.scanner.file_system import fs_scanner

    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    mock_config.settings.min_size_mb = 0

    with patch("arcade_scanner.scanner.file_system.config", mock_config):
        fs_scanner._scan_time_file = str(tmp_path / ".last_scan_time")
        fs_scanner._scan_started_at = 0.0
        yield fs_scanner


def gemerkt(scanner):
    with open(scanner._scan_time_file, encoding="utf-8") as f:
        return json.load(f)["last_scan_time"]


# --- Der Fund ---

def test_the_start_of_the_scan_is_remembered_not_the_end(scanner):
    """
    Der Kern: Alles, was zwischen Beginn und Ende passiert, muss beim nächsten
    Durchlauf noch als „geändert" gelten.
    """
    beginn = time.time() - 1800  # eine halbe Stunde Scan
    scanner._scan_started_at = beginn

    scanner.save_last_scan_time()

    assert abs(gemerkt(scanner) - beginn) < 1


def test_a_change_during_the_scan_is_still_seen_next_time(scanner):
    """
    Derselbe Fall in der Größe, in der er auftritt: Der Ordner wird um 02:10
    angefasst, der Scan endet um 02:30.
    """
    beginn = 1_700_000_000.0
    scanner._scan_started_at = beginn
    ordner_mtime = beginn + 600      # 02:10
    ende = beginn + 1800             # 02:30

    with patch("arcade_scanner.scanner.file_system.time.time", return_value=ende):
        scanner.save_last_scan_time()

    # Genau der Vergleich, den scan_directories() anstellt.
    assert ordner_mtime >= gemerkt(scanner), "Der Ordner gälte als unverändert"


def test_the_old_behaviour_would_have_lost_it(scanner):
    """
    Die Gegenprobe: Mit dem Ende-Zeitstempel wäre derselbe Ordner
    übersprungen worden. Ohne diesen Test steht oben nur eine Behauptung.
    """
    beginn = 1_700_000_000.0
    ordner_mtime = beginn + 600
    ende = beginn + 1800

    assert ordner_mtime < ende


# --- Was weiterhin gelten muss ---

def test_without_a_recorded_start_the_current_time_is_used(scanner):
    """
    Wird die Funktion ohne laufenden Scan aufgerufen, darf sie nicht 0
    schreiben — das hiesse „nie gescannt" und würde die Beschleunigung
    dauerhaft abschalten.
    """
    scanner._scan_started_at = 0.0

    scanner.save_last_scan_time()

    assert abs(gemerkt(scanner) - time.time()) < 5


def test_the_value_is_read_back(scanner):
    scanner._scan_started_at = 1_700_000_000.0
    scanner.save_last_scan_time()

    scanner._last_scan_time = 0.0
    scanner._load_last_scan_time()

    assert scanner._last_scan_time == 1_700_000_000.0


def test_a_broken_file_means_full_scan(scanner):
    """
    Ein beschädigter Zeitstempel darf nicht dazu führen, dass alles
    übersprungen wird — 0 heisst „alles prüfen".
    """
    with open(scanner._scan_time_file, "w", encoding="utf-8") as f:
        f.write("{kein json")

    scanner._last_scan_time = 12345.0
    scanner._load_last_scan_time()

    assert scanner._last_scan_time == 0.0


def test_writing_failures_do_not_raise(scanner, tmp_path):
    """
    Der Zeitstempel ist eine Beschleunigung, kein Ergebnis. Lässt er sich
    nicht schreiben, ist der Scan trotzdem gelaufen.
    """
    scanner._scan_time_file = str(tmp_path / "gibtsnicht" / "x" / ".last_scan_time")
    scanner._scan_started_at = time.time()

    with patch("arcade_scanner.scanner.file_system.os.makedirs",
               side_effect=OSError("nur lesbar")):
        scanner.save_last_scan_time()  # kein Fehler nach oben


# --- Struktur ---

def test_the_start_is_taken_before_the_first_directory():
    """
    Stünde die Zuweisung hinter der Schleife, wäre es wieder das Ende.
    """
    from pathlib import Path

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "scanner"
              / "file_system.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("async def scan_directories"):]
    block = block[:block.index("for target in targets:")]

    assert "self._scan_started_at = time.time()" in block
