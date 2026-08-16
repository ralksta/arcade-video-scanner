"""
test_export_view.py
-------------------
Export der aktuellen Ansicht als CSV und M3U.

Der Kern ist die Maskierung. Dateinamen mit Komma, Anführungszeichen oder
Zeilenumbruch sind hier kein exotischer Sonderfall — auf Unix ist jedes davon
in einem Dateinamen erlaubt, und in einer gewachsenen Medienbibliothek kommt
es vor. Unmaskiert verschiebt ein einziger solcher Name alle folgenden Spalten,
und das fällt in einer Tabelle mit 8000 Zeilen niemandem auf.

Geprüft wird gegen Pythons ``csv``-Modul: nicht gegen die eigene Erwartung,
sondern gegen einen unabhängigen RFC-4180-Leser.
"""
import csv
import io
import json
import shutil
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC_DIR = ROOT / "arcade_scanner" / "server" / "static"
EXPORT_JS = (STATIC_DIR / "export_view.js").read_text(encoding="utf-8")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not on PATH")


def _build(fn: str, videos: list[dict]) -> str:
    """Ruft buildCsv() bzw. buildM3u() in node auf."""
    harness = textwrap.dedent(f"""
        const window = globalThis;
        {EXPORT_JS.split("// ====")[0]}
        console.log(JSON.stringify({fn}({json.dumps(videos)})));
    """)
    proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True, timeout=20)
    assert proc.returncode == 0, f"node failed:\n{proc.stderr}"
    return json.loads(proc.stdout.strip().splitlines()[-1])


def _video(**overrides):
    base = {
        "FilePath": "/media/clip.mp4",
        "media_type": "video",
        "Size_MB": 512.34,
        "Duration_Sec": 61.6,
        "codec": "h264",
        "Bitrate_Mbps": 8.125,
        "Width": 1920,
        "Height": 1080,
        "Status": "OK",
        "favorite": False,
        "tags": [],
    }
    base.update(overrides)
    return base


def _parse(csv_text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(csv_text)))


def test_header_and_one_row():
    rows = _parse(_build("buildCsv", [_video()]))
    assert rows[0][0] == "Pfad"
    assert rows[1][0] == "/media/clip.mp4"
    assert len(rows) == 2


@pytest.mark.parametrize("name", [
    "Urlaub, Italien.mp4",
    'Er sagte "hallo".mp4',
    "Zeile1\nZeile2.mp4",
    "Semikolon;Test.mp4",
    'Alles, "gemischt";\nund umbrochen.mp4',
])
def test_special_characters_survive_a_round_trip(name):
    """
    Gegen Pythons csv-Leser geprüft: was hier herauskommt, muss ein
    unabhängiger RFC-4180-Parser wieder als genau ein Feld erkennen.
    """
    path = f"/media/{name}"
    rows = _parse(_build("buildCsv", [_video(FilePath=path)]))

    assert len(rows) == 2, f"Zeilenumbruch im Namen hat die Zeile zerrissen: {rows}"
    assert rows[1][0] == path
    assert len(rows[1]) == len(rows[0]), "Spaltenzahl verschoben"


def test_quotes_are_doubled_not_stripped():
    rows = _parse(_build("buildCsv", [_video(FilePath='/media/a"b.mp4')]))
    assert rows[1][0] == '/media/a"b.mp4'


def test_tags_are_joined_and_escaped():
    rows = _parse(_build("buildCsv", [_video(tags=["urlaub", "familie, privat"])]))
    assert rows[1][-1] == "urlaub; familie, privat"


def test_numbers_are_formatted_predictably():
    rows = _parse(_build("buildCsv", [_video()]))
    header, row = rows[0], rows[1]
    assert row[header.index("Größe_MB")] == "512.3"
    assert row[header.index("Dauer_Sek")] == "62"
    assert row[header.index("Bitrate_Mbps")] == "8.13"


def test_favorite_is_human_readable():
    rows = _parse(_build("buildCsv", [_video(favorite=True)]))
    assert rows[1][_parse(_build("buildCsv", [_video()]))[0].index("Favorit")] == "ja"


def test_empty_list_still_has_a_header():
    rows = _parse(_build("buildCsv", []))
    assert len(rows) == 1
    assert rows[0][0] == "Pfad"


# --- M3U ---

def test_m3u_has_header_and_entries():
    text = _build("buildM3u", [_video(FilePath="/media/a.mp4", Duration_Sec=90.4)])
    lines = text.strip().split("\n")
    assert lines[0] == "#EXTM3U"
    assert lines[1] == "#EXTINF:90,a.mp4"
    assert lines[2] == "/media/a.mp4"


def test_m3u_uses_local_paths_not_stream_urls():
    """Ein externer Player hat keine Sitzung und käme an /stream nicht heran."""
    text = _build("buildM3u", [_video()])
    assert "/stream" not in text
    assert "/media/clip.mp4" in text


# --- Verdrahtung ---

def test_script_is_loaded():
    from arcade_scanner.templates.dashboard_template import SCRIPT_MODULES

    assert "export_view.js" in SCRIPT_MODULES


def test_export_is_reachable_from_the_command_palette():
    palette = (STATIC_DIR / "context_menu.js").read_text(encoding="utf-8")
    assert "exportCurrentView('csv')" in palette
    assert "exportCurrentView('m3u')" in palette


def test_export_uses_the_filtered_view_not_the_whole_library():
    """Exportiert wird, was zu sehen ist — sonst ignoriert der Export alle Filter."""
    block = EXPORT_JS.split("function exportCurrentView", 1)[1]
    assert "window.filteredVideos" in block
    assert "window.ALL_VIDEOS" not in block


def test_excel_bom_is_written():
    """Ohne BOM liest Excel die Umlaute in den Spaltennamen als Latin-1."""
    assert "﻿" in EXPORT_JS
