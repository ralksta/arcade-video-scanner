"""
test_tv_sorting.py
------------------
Die Standard-Sortierung des TV-Clients hiess „newest" und sortierte nicht nach
Datum.

    case 'newest':
    default:
        return sorted.reverse();

Umgedreht wird damit die Reihenfolge, in der `/api/videos` liefert — und das
ist `SELECT * FROM media` ohne `ORDER BY`, also die Einfügereihenfolge des
ersten Scans. Mit dem Alter der Dateien hat sie nichts zu tun.

An der echten Bibliothek nachgemessen (8788 Einträge):

    „newest" laut TV-Client      wirklich neueste (nach mtime)
    2025-10-27  VID_2025…        2026-08-05  madame-svea…
    2025-11-06  VID_2025…        2026-08-03  0hpwqyyup6i…
    2025-10-31  VID_2025…        2026-08-02  CIOUS_FEMDOM…

**Null Überschneidung in den ersten zehn.** Und weil es die Vorgabe ist, war es
das, was beim Einschalten auf dem Fernseher stand.

Derselbe Denkfehler steckte in „Zuletzt hinzugefügt": `slice(-48)` nahm die
letzten 48 Zeilen der Einfügereihenfolge statt der 48 neuesten Dateien.

Der Browser-Client rechnet an derselben Stelle `(b.mtime || 0) - (a.mtime || 0)`
— die Vorlage lag also daneben.

Geprüft wird ausgeführt: `tv_sort_harness.js` schneidet `sortVideos()` samt
Hilfsfunktion aus dem React-Modul und lässt sie in node laufen, wie es
`tv_eval_harness.js` für den Sammlungs-Matcher tut.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
HARNESS = Path(__file__).parent / "tv_sort_harness.js"
MAIN_PANEL = (ROOT / "tv_client" / "src" / "views" / "MainPanel.js").read_text(
    encoding="utf-8")

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def sort_videos(videos, sort_key):
    fixture = Path(__file__).parent / "_tv_sort_fixtures.json"
    fixture.write_text(json.dumps({"videos": videos, "sortKey": sort_key}),
                       encoding="utf-8")
    try:
        out = subprocess.run([node, str(HARNESS), str(fixture)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    finally:
        fixture.unlink(missing_ok=True)


def video(name, mtime, size_mb=100.0):
    return {"_fileName": name, "mtime": mtime, "Size_MB": size_mb,
            "FilePath": "/media/" + name}


# In Einfügereihenfolge, also so wie /api/videos liefert: das älteste zuletzt.
LIBRARY = [
    video("alt_2025.mp4", 1730000000),      # Okt 2025
    video("mittel_2026.mp4", 1760000000),   # Okt 2025 + etwas
    video("neu_2026.mp4", 1786000000),      # Aug 2026
    video("aeltestes.mp4", 1700000000),     # Nov 2023
]


# --- Der Fund ---

def test_newest_really_means_newest():
    """
    Vorher lieferte diese Sortierung schlicht die umgedrehte Eingabe — hier
    also `aeltestes.mp4` zuerst.
    """
    assert sort_videos(LIBRARY, "newest")[0] == "neu_2026.mp4"


def test_newest_orders_the_whole_list_by_date():
    assert sort_videos(LIBRARY, "newest") == [
        "neu_2026.mp4", "mittel_2026.mp4", "alt_2025.mp4", "aeltestes.mp4",
    ]


def test_the_default_sort_key_behaves_like_newest():
    """
    `newest` ist der Vorgabefall — was hier steht, sieht man beim Einschalten.
    """
    assert sort_videos(LIBRARY, "newest") == sort_videos(LIBRARY, "gibtsnicht")


def test_it_is_not_merely_the_reversed_input():
    """
    Die Gegenprobe zum alten Verhalten: Wäre es weiterhin ein `reverse()`,
    stünde `aeltestes.mp4` vorn — und dieser Test wäre trotzdem grün, wenn ich
    nur nach „das Neueste ist dabei" fragen würde.
    """
    reversed_input = [v["_fileName"] for v in reversed(LIBRARY)]

    assert sort_videos(LIBRARY, "newest") != reversed_input


def test_entries_without_a_date_sort_last():
    """
    `mtime || 0` — ein fehlendes Datum macht den Eintrag zum ältesten, statt
    die Sortierung durcheinanderzubringen.
    """
    result = sort_videos(LIBRARY + [video("ohne_datum.mp4", None)], "newest")

    assert result[-1] == "ohne_datum.mp4"


def test_the_recent_list_takes_the_newest_not_the_last_rows():
    """
    Derselbe Denkfehler an zweiter Stelle: `slice(-48)` nahm das Ende der
    Einfügereihenfolge. Geprüft am Quelltext, weil die Liste in einem
    `useMemo` steckt und nicht als reine Funktion vorliegt.
    """
    code = "\n".join(
        re.sub(r"(^|\s)//.*$", "", line) for line in MAIN_PANEL.splitlines()
    )
    block = code.split("const recent = useMemo(", 1)[1].split("[allVideos", 1)[0]

    assert "slice(-48)" not in block, "Nimmt weiterhin die letzten Datenbankzeilen"
    assert "entryDate(b) - entryDate(a)" in block
    assert "slice(0, 48)" in block


# --- Die übrigen Sortierungen dürfen sich nicht ändern ---

def test_sorting_by_name_ascending():
    assert sort_videos(LIBRARY, "name_az")[0] == "aeltestes.mp4"


def test_sorting_by_name_descending():
    assert sort_videos(LIBRARY, "name_za")[0] == "neu_2026.mp4"


def test_sorting_by_size():
    videos = [video("klein.mp4", 1, 10.0), video("gross.mp4", 2, 900.0)]

    assert sort_videos(videos, "size_desc")[0] == "gross.mp4"
    assert sort_videos(videos, "size_asc")[0] == "klein.mp4"


def test_the_input_list_is_not_modified():
    """`[...list]` — sonst würde eine Sortierung die Reihenfolge für alle
    anderen Ansichten mitverändern, die dieselbe Liste benutzen."""
    before = [v["_fileName"] for v in LIBRARY]
    sort_videos(LIBRARY, "newest")

    assert [v["_fileName"] for v in LIBRARY] == before


# --- Gleichstand mit dem Browser-Client ---

def test_both_clients_use_the_same_date_for_the_order():
    """
    Beide rechnen jetzt mit `imported_at`, ersatzweise `mtime` — dieselbe
    Regel, die auch der Datumsfilter und die Sammlungen benutzen. Vorher stand
    hier auf beiden Seiten das blosse `mtime`, und das ist eine andere Frage:
    „zuletzt geschrieben" statt „in die Bibliothek gekommen".
    """
    browser = (
        ROOT / "arcade_scanner" / "server" / "static" / "filter_engine.js"
    ).read_text(encoding="utf-8")

    assert "entryDate(b) - entryDate(a)" in browser
    assert "entryDate(b) - entryDate(a)" in MAIN_PANEL


def test_the_api_really_returns_an_unsorted_list():
    """
    Der Beleg für die Diagnose: Käme `/api/videos` nach Datum sortiert, wäre
    `reverse()` nur die falsche Richtung gewesen und nicht die falsche Grösse.
    """
    store = (
        ROOT / "arcade_scanner" / "database" / "sqlite_store.py"
    ).read_text(encoding="utf-8")
    block = store.split("def get_all(self)", 1)[1].split("def ", 1)[0]

    assert 'conn.execute("SELECT * FROM media")' in block
    assert "ORDER BY" not in block
