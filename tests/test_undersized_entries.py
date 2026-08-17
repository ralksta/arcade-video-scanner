"""
test_undersized_entries.py
--------------------------
Eine zu kleine Datei war für den Aufräumschritt nicht von einer gelöschten zu
unterscheiden.

Der Walker filterte Dateien unter der Mindestgrösse heraus — aber **nur in
Verzeichnissen, deren Änderungszeit neuer war als der letzte Scan**:

    if dir_changed and not self._is_valid_size(full_path):
        continue

Was nicht gemeldet wird, fehlt in `found_paths`, und was dort fehlt, hält der
Aufräumschritt für verschwunden. Er löschte also den Eintrag samt
Vorschaubild, obwohl die Datei unverändert auf der Platte lag.

In unveränderten Verzeichnissen griff der Filter gar nicht — dort blieben
dieselben Einträge stehen. Dasselbe Video war damit mal in der Bibliothek und
mal nicht, je nachdem, ob zufällig jemand im selben Ordner etwas angefasst
hatte.

**An dieser Bibliothek gemessen:** 515 Einträge verschwanden, weil in drei
Ordnern gelöscht wurde. Alle 515 lagen unter der eingestellten Mindestgrösse
von 20 MB, der grösste bei 19,9 MB. Alle 515 Dateien existierten weiterhin.
2949 gleichartige Einträge standen zur selben Zeit unangetastet in der
Bibliothek — in Ordnern, die sich nicht geändert hatten.

Jetzt meldet der Walker **jede** Mediendatei, mit einem Vermerk `too_small`.
Der Eintrag wird weiterhin entfernt, wenn die Datei unter der Schwelle liegt —
das ist der Sinn der Einstellung — aber:

* berechenbar, unabhängig von der Änderungszeit des Ordners,
* mit einer eigenen Meldung, die „unter der Mindestgrösse" von „gelöscht"
  unterscheidet,
* und ohne die Schutzbedingungen des Verwaisten-Aufräumens zu umgehen, denn
  hier ist nichts zu vermuten: Die Datei wurde gesehen und vermessen.
"""
from unittest.mock import MagicMock, patch

from test_scanner_manager import FakeDB, FakeScanner, make_cached, make_config, run_scan

from arcade_scanner.scanner.manager import ScannerManager

# --- Der Walker meldet, statt zu verschweigen ---

def test_a_small_file_is_reported_with_a_flag(tmp_path):
    from arcade_scanner.scanner.file_system import AsyncFileSystem

    cfg = MagicMock()
    cfg.settings.min_size_mb = 1
    cfg.settings.min_image_size_kb = 0
    cfg.hidden_data_dir = str(tmp_path / "data")

    (tmp_path / "media").mkdir()
    (tmp_path / "media" / "winzig.mp4").write_bytes(b"x" * 1024)

    import asyncio

    async def sammeln():
        scanner = AsyncFileSystem()
        return [item async for item in scanner.scan_directories([str(tmp_path / "media")])]

    with patch("arcade_scanner.scanner.file_system.config", cfg):
        ergebnis = asyncio.run(sammeln())

    assert len(ergebnis) == 1, "die Datei wurde verschwiegen"
    pfad, _dir_changed, too_small = ergebnis[0]
    assert pfad.endswith("winzig.mp4")
    assert too_small is True


# --- Der Scanner hält sie nicht für verschwunden ---

def test_a_small_file_is_not_treated_as_deleted(capsys):
    """
    Der Kern des Fundes: Die Meldung muss „unter der Mindestgrösse" lauten,
    nicht „gelöscht oder ausgeschlossen".
    """
    cached = make_cached("/media/winzig.mp4", size_mb=5.0)
    db = FakeDB([cached])

    run_scan(ScannerManager(), db, FakeScanner([("/media/winzig.mp4", True, True)]),
             make_config())

    out = capsys.readouterr().out
    assert "Mindestgr" in out
    assert "deleted or now excluded" not in out


def test_the_entry_is_removed_but_the_file_is_left_alone(capsys):
    cached = make_cached("/media/winzig.mp4", size_mb=5.0)
    db = FakeDB([cached])

    run_scan(ScannerManager(), db, FakeScanner([("/media/winzig.mp4", True, True)]),
             make_config())

    assert db.removed == ["/media/winzig.mp4"]
    assert "Dateien selbst bleiben unangetastet" in capsys.readouterr().out


def test_an_unknown_small_file_is_simply_ignored(capsys):
    """
    Eine zu kleine Datei, die nie in der Bibliothek stand, ist kein Ereignis —
    darüber muss auch nichts gemeldet werden.
    """
    db = FakeDB([])

    run_scan(ScannerManager(), db, FakeScanner([("/media/winzig.mp4", True, True)]),
             make_config())

    assert db.removed == []
    assert "Mindestgr" not in capsys.readouterr().out


def test_a_small_file_is_never_probed(capsys):
    """
    Der Zweck des Filters bleibt: kein ffprobe auf Winzlinge. Sichtbar daran,
    dass die Datei nicht unter den untersuchten auftaucht.
    """
    db = FakeDB([])

    run_scan(ScannerManager(), db, FakeScanner([("/media/winzig.mp4", True, True)]),
             make_config())

    assert "davon 0 neu oder geändert" in capsys.readouterr().out
    assert db.upserted == []


# --- Was daneben weiter gelten muss ---

def test_a_normal_file_is_untouched(capsys):
    cached = make_cached("/media/gross.mp4", size_mb=500.0, mtime=1000)
    db = FakeDB([cached])

    run_scan(ScannerManager(), db, FakeScanner([("/media/gross.mp4", True, False)]),
             make_config(), stat_size=500.0, stat_mtime=1000)

    assert db.removed == []
    assert "Mindestgr" not in capsys.readouterr().out


def test_a_genuinely_missing_file_is_still_pruned(capsys):
    """
    Die andere Hälfte: Was der Walker gar nicht meldet, ist tatsächlich weg
    und wird weiterhin entfernt.
    """
    db = FakeDB([make_cached("/media/weg.mp4"), make_cached("/media/da.mp4")])

    run_scan(ScannerManager(), db, FakeScanner([("/media/da.mp4", True, False)]),
             make_config(), stat_size=100.0, stat_mtime=1000)

    assert db.removed == ["/media/weg.mp4"]


# --- Struktur ---

def test_the_walker_no_longer_swallows_small_files():
    """
    Käme das `continue` zurück, wäre der schleichende Verlust wieder da — und
    dieser Test ist die einzige Stelle, an der das auffiele.
    """
    from pathlib import Path

    from test_dump_isolation import _code_only

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "scanner"
              / "file_system.py").read_text(encoding="utf-8")

    assert "if dir_changed and not self._is_valid_size" not in _code_only(quelle)
    assert "too_small = not self._is_valid_size(full_path)" in quelle
