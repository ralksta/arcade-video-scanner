"""
test_date_sorting.py
--------------------
Nachtrag zur vorigen Iteration — und eine Korrektur an mir selbst.

Dort habe ich „Sortieren: Datum" von `mtime` auf `entryDate()` umgestellt, weil
der Datumsfilter und die Sammlungen schon so rechnen. Der Grund stimmt. Die
Umstellung allein war trotzdem zu kurz gedacht: Beim **ersten** Scan bekommen
alle Dateien ihr `imported_at` innerhalb weniger Minuten. Die Reihenfolge
innerhalb eines solchen Blocks ist dann die des Verzeichnisdurchlaufs — also
keine.

An der echten Bibliothek nachgesehen: 8788 Einträge, verteilt auf **zehn**
Import-Tage, aber 2858 davon allein am 07.08.2026. Für diese 2858 hätte die
Umstellung „nach Datum" durch „nach Scan-Reihenfolge" ersetzt, während `mtime`
dort etwas Echtes aussagt.

Es sind eben zwei verschiedene Fragen, und beide sind berechtigt:

    „Was habe ich zuletzt hinzugefügt?"      → imported_at
    „Was sind meine neuesten Aufnahmen?"     → mtime

Also stehen jetzt beide im Auswahlfeld, mit Namen, die sie unterscheiden.
Der gespeicherte Wert `date` bleibt, was er war — gespeicherte Ansichten tragen
ihn —, und meint das Hinzufügen; neu ist `file_date`.

Geprüft wird ausgeführt: `vault_guard_harness.js` führt `filterAndSort()` mit
dem jeweiligen Sortierschlüssel aus.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HARNESS = Path(__file__).parent / "vault_guard_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def sort_by(key, videos):
    fixture = Path(__file__).parent / "_date_sort_fixture.json"
    fixture.write_text(json.dumps({
        "videos": videos,
        "userDataLoaded": True,
        "sortKey": key,
    }), encoding="utf-8")
    try:
        out = subprocess.run([node, str(HARNESS), str(fixture)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)["shownPaths"]
    finally:
        fixture.unlink(missing_ok=True)


def video(name, imported_at, mtime):
    return {
        "FilePath": f"/media/{name}",
        "Size_MB": 100.0,
        "Bitrate_Mbps": 5.0,
        "Status": "OK",
        "imported_at": imported_at,
        "mtime": mtime,
    }


# Eine alte Aufnahme, heute hinzugefügt — und eine neue, die schon länger
# in der Bibliothek steht. Die beiden Sortierungen müssen sie umgekehrt
# anordnen, sonst prüft der Test nichts.
ALT_NEU_HINZUGEFUEGT = video("alte_aufnahme.mp4", imported_at=1_700_000_000,
                             mtime=1_400_000_000)
NEU_LAENGER_DABEI = video("neue_aufnahme.mp4", imported_at=1_600_000_000,
                          mtime=1_690_000_000)


# --- Die beiden Fragen ---

def test_date_added_puts_the_newly_added_file_first():
    reihenfolge = sort_by("date", [NEU_LAENGER_DABEI, ALT_NEU_HINZUGEFUEGT])

    assert reihenfolge[0] == "/media/alte_aufnahme.mp4"


def test_file_date_puts_the_newer_recording_first():
    reihenfolge = sort_by("file_date", [ALT_NEU_HINZUGEFUEGT, NEU_LAENGER_DABEI])

    assert reihenfolge[0] == "/media/neue_aufnahme.mp4"


def test_the_two_really_differ():
    """
    Der eigentliche Punkt: Gäben beide dieselbe Reihenfolge, wäre die zweite
    Option überflüssig — und der ursprüngliche Fund keiner.
    """
    videos = [NEU_LAENGER_DABEI, ALT_NEU_HINZUGEFUEGT]

    assert sort_by("date", videos) != sort_by("file_date", videos)


# --- Der Ersatz für alte Einträge ---

def test_an_entry_without_an_import_date_falls_back_to_the_file():
    """
    Einträge aus der Zeit vor dem Feld haben `imported_at == 0`. Ohne den
    Ersatz stünden sie alle gemeinsam bei 1970 — also am Ende, für immer.
    """
    ohne = video("ohne_import.mp4", imported_at=0, mtime=1_750_000_000)
    mit = video("mit_import.mp4", imported_at=1_600_000_000, mtime=1_500_000_000)

    assert sort_by("date", [mit, ohne])[0] == "/media/ohne_import.mp4"


def test_an_entry_without_any_date_ends_up_last():
    ohne_alles = video("ohne_alles.mp4", imported_at=0, mtime=0)
    normal = video("normal.mp4", imported_at=1_600_000_000, mtime=1_500_000_000)

    assert sort_by("date", [ohne_alles, normal])[-1] == "/media/ohne_alles.mp4"


# --- Was bestehen bleiben muss ---

def test_the_stored_value_of_saved_views_still_works():
    """
    Gespeicherte Ansichten tragen `sort: "date"`. Hätte ich den Wert
    umbenannt, wären sie alle stillschweigend auf die Voreinstellung
    zurückgefallen.
    """
    source = (ROOT / "arcade_scanner" / "server" / "static"
              / "filter_engine.js").read_text(encoding="utf-8")

    assert "currentSort === 'date'" in source

    settings = (ROOT / "arcade_scanner" / "server" / "static"
                / "settings.js").read_text(encoding="utf-8")
    assert "sort: window.currentSort" in settings


def test_both_options_are_offered_and_named_apart():
    from arcade_scanner.templates.components import FILTER_BAR_COMPONENT

    assert '<option value="date">Sort: date added</option>' in FILTER_BAR_COMPONENT
    assert '<option value="file_date">Sort: file date</option>' in FILTER_BAR_COMPONENT


def test_the_other_sortings_are_untouched():
    videos = [
        video("klein.mp4", 1_600_000_000, 1_500_000_000) | {"Size_MB": 10.0},
        video("gross.mp4", 1_600_000_000, 1_500_000_000) | {"Size_MB": 900.0},
    ]

    assert sort_by("size", videos)[0] == "/media/gross.mp4"
    assert sort_by("name", videos)[0] == "/media/gross.mp4"
