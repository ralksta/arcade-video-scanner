"""
test_no_stray_test_files.py
---------------------------
Außerhalb von `tests/` darf nichts `test_*.py` heißen.

Im Wurzelverzeichnis lagen `test_api.py`, `test_dump.py`, `test_probe.py`,
`test_probe2.py` und `test_probe3.py` — Ad-hoc-Skripte aus früheren
Fehlersuchen. Alle öffnen die **echte** Datenbank in `arcade_data/`, und ihr
Code läuft beim Import.

`pytest` sammelt Dateien mit `test_`-Präfix ein, und Einsammeln heißt
Importieren. Nachgewiesen gegen eine Kopie im Altzustand:

    $ pytest --collect-only test_dump.py
    collected 0 items

...und die Datenbank war danach migriert. Es braucht also nicht einmal einen
gefundenen Test.

Dass es bisher gutging, lag allein an `testpaths = ["tests"]`. Ein
`pytest test_dump.py`, ein `pytest .` oder eine geänderte Konfiguration hätte
gereicht. Die Skripte liegen jetzt unter `scripts/adhoc/` mit sprechenden Namen.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
TESTS_DIR = ROOT / "tests"

# Verzeichnisse, die keine eigenen Python-Tests enthalten sollen.
SEARCHED = ["", "scripts", "arcade_scanner", "dev-docs", "docs"]


def _stray_files():
    stray = []
    for relative in SEARCHED:
        base = ROOT / relative if relative else ROOT
        if not base.is_dir():
            continue
        for path in base.rglob("test_*.py"):
            if TESTS_DIR in path.parents or path.name.startswith("._"):
                continue
            if ".venv" in path.parts or "node_modules" in path.parts:
                continue
            stray.append(path.relative_to(ROOT))
    return stray


def test_no_test_prefixed_files_outside_the_suite():
    stray = _stray_files()
    assert not stray, (
        "Datei mit test_-Präfix außerhalb von tests/:\n  "
        + "\n  ".join(str(p) for p in stray)
        + "\n\npytest sammelt sie ein, und Einsammeln heißt Importieren. Läuft "
          "dabei Modulcode gegen arcade_data/, trifft es die echte Bibliothek. "
          "Ad-hoc-Skripte gehören nach scripts/adhoc/ (oder tragen eines der in "
          ".gitignore vorgesehenen Präfixe debug_/check_/verify_)."
    )


def test_the_moved_scripts_are_still_there():
    """
    Gegenprobe: verschoben, nicht gelöscht. Es sind die Diagnosewerkzeuge des
    Entwicklers, auch wenn sie am falschen Ort lagen.
    """
    adhoc = ROOT / "scripts" / "adhoc"
    assert adhoc.is_dir()

    expected = {
        "dump_library.py",
        "inspect_user_targets.py",
        "probe_smoke.py",
        "probe_ffprobe_raw.py",
        "probe_without_swallowing.py",
        "retag_av1_opt_files.py",
    }
    present = {p.name for p in adhoc.glob("*.py")}
    assert expected <= present, f"Fehlt: {sorted(expected - present)}"


def test_the_adhoc_directory_warns_about_the_real_database():
    readme = ROOT / "scripts" / "adhoc" / "README.md"
    assert readme.is_file(), "Ohne README weiß niemand, was diese Skripte anfassen"

    text = readme.read_text(encoding="utf-8")
    assert "arcade_data" in text
    assert "CONFIG_DIR" in text, "Der Weg zur gefahrlosen Ausführung fehlt"


@pytest.mark.parametrize("prefix", ["debug_", "check_", "verify_"])
def test_gitignore_still_reserves_the_adhoc_prefixes(prefix):
    """
    Das Projekt hat bereits eine Konvention für Wegwerf-Skripte. `test_` gehört
    ausdrücklich nicht dazu — genau deshalb war die Ablage im Wurzelverzeichnis
    ein Problem.
    """
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert f"{prefix}*.py" in gitignore
