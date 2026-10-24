"""
test_entry_date.py
------------------
„Sortieren: Datum" und „hinzugefügt: letzte 7 Tage" meinten zwei verschiedene
Daten.

Es gibt zwei Zeitangaben je Eintrag:

    imported_at   wann der erste Scan die Datei gesehen hat
    mtime         wann die Datei zuletzt geschrieben wurde

Drei Stellen benutzten dieselbe Regel — `imported_at`, ersatzweise `mtime`:
der Datumsfilter in `filter_engine.js`, die Sammlungen in `collections.js` und
deren Python-Gegenstück `criteria_eval.py`. Die vierte, die Sortierung, rechnete
allein mit `mtime`. Beide heissen in der Oberfläche „Datum".

Zwei Folgen im Alltag:

1. **Optimieren schiebt alte Filme nach oben.** Beim Umkodieren wird die Datei
   neu geschrieben, `mtime` ist damit von heute. Ein Film von 2019 steht danach
   unter „Sortieren: Datum" an erster Stelle — nicht weil er neu ist, sondern
   weil er angefasst wurde. Mit dem Fernarbeiter kann das über Nacht die halbe
   Bibliothek betreffen.

2. **Frisch Hinzugefügtes findet man nicht über die Sortierung.** Eine alte
   Aufnahme, die man heute in die Bibliothek legt, erscheint im Filter „letzte
   7 Tage" — und steht in der Sortierung ganz unten.

Die Regel steht jetzt einmal als `entryDate()` in `utils.js`; Datumsfilter,
Sortierung und Sammlungen rufen sie auf. Der TV-Client führt sie als eigene
Zeile mit, weil er ein getrennter Build ist — ein Test hält beide Seiten
zusammen.

Geprüft wird ausgeführt: `entry_date_harness.js` lädt die echte Funktion aus
utils.js.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
STATIC = ROOT / "arcade_scanner" / "server" / "static"
HARNESS = Path(__file__).parent / "entry_date_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def entry_date(video):
    fixture = Path(__file__).parent / "_entry_date_fixture.json"
    fixture.write_text(json.dumps({"cases": [video]}), encoding="utf-8")
    try:
        out = subprocess.run([node, str(HARNESS), str(fixture)],
                             capture_output=True, text=True, timeout=30)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)[0]
    finally:
        fixture.unlink(missing_ok=True)


# --- Welches Datum gilt ---

def test_the_import_date_wins():
    assert entry_date({"imported_at": 1700000000, "mtime": 1500000000}) == 1700000000


def test_the_import_date_wins_even_when_the_file_is_newer():
    """
    Der Fall, um den es geht: Die Datei wurde nach dem Import neu geschrieben —
    beim Optimieren zum Beispiel. Für „wann kam das in die Bibliothek" ändert
    das nichts.
    """
    assert entry_date({"imported_at": 1600000000, "mtime": 1799999999}) == 1600000000


def test_mtime_fills_in_for_older_entries():
    """
    Einträge aus der Zeit vor dem Feld haben `imported_at == 0`. Ohne den
    Ersatz stünden sie alle gemeinsam bei 1970.
    """
    assert entry_date({"imported_at": 0, "mtime": 1500000000}) == 1500000000


def test_nothing_known_is_zero():
    assert entry_date({}) == 0


def test_a_missing_entry_is_zero():
    assert entry_date(None) == 0


@pytest.mark.parametrize("kaputt", [
    {"imported_at": "vorgestern", "mtime": 1500000000},
    {"imported_at": None, "mtime": 1500000000},
])
def test_an_unreadable_import_date_falls_back(kaputt):
    """
    Sonst führte ein einzelner beschädigter Wert zu `NaN` — und ein Vergleich
    mit NaN ist immer falsch, was die Sortierung stillschweigend zerlegt.
    """
    assert entry_date(kaputt) == 1500000000


# --- Alle Stellen benutzen dieselbe Regel ---

def test_the_browser_has_exactly_one_definition():
    definitionen = []
    for js in sorted(STATIC.glob("*.js")):
        if js.name == "aframe.min.js":
            continue
        source = js.read_text(encoding="utf-8")
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        code = "\n".join(
            re.sub(r"(^|\s)//.*$", "", line) for line in source.splitlines()
        )
        if "function entryDate" in code:
            definitionen.append(js.name)

    assert definitionen == ["utils.js"], definitionen


def test_no_file_spells_the_rule_out_again():
    """
    Genau so ist die Sortierung auseinandergelaufen: Die Regel stand
    ausgeschrieben da, und an einer Stelle eben anders.
    """
    muster = re.compile(r"imported_at\s*>\s*0\s*\?")
    offenders = []
    for js in sorted(STATIC.glob("*.js")):
        source = js.read_text(encoding="utf-8")
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        code = "\n".join(
            re.sub(r"(^|\s)//.*$", "", line) for line in source.splitlines()
        )
        if muster.search(code):
            offenders.append(js.name)

    assert offenders == [], offenders


def test_the_sort_and_the_filter_use_it():
    source = (STATIC / "filter_engine.js").read_text(encoding="utf-8")

    assert "const fileTime = entryDate(v);" in source
    assert "entryDate(b) - entryDate(a)" in source


def test_the_collections_use_it():
    source = (STATIC / "collections.js").read_text(encoding="utf-8")

    assert "entryDate(video)" in source


def test_it_is_loaded_before_its_users():
    from arcade_scanner.templates.dashboard_template import SCRIPT_MODULES

    utils = SCRIPT_MODULES.index("utils.js")
    for name in ("filter_engine.js", "collections.js"):
        assert SCRIPT_MODULES.index(name) > utils, name


def test_the_python_port_agrees():
    """
    `criteria_eval.py` rechnet dasselbe für die Sammlungen auf der
    Serverseite. Ein Differenztest hält die beiden schon gegeneinander; hier
    geht es nur darum, dass die Regel dieselbe ist.
    """
    from arcade_scanner.core.criteria_eval import matches_date_filter

    jetzt = 1_700_000_000
    gestern_importiert = {"imported_at": jetzt - 86400, "mtime": 0}
    alt_importiert_neu_geschrieben = {"imported_at": jetzt - 86400 * 300,
                                      "mtime": jetzt - 60}

    assert matches_date_filter(gestern_importiert, "7d", jetzt) is True
    assert matches_date_filter(alt_importiert_neu_geschrieben, "7d", jetzt) is False
