"""
test_safe_mode.py
-----------------
Der abgesicherte Modus (`isSensitive()` in utils.js, benutzt von
`filter_engine.js:197`).

Zuerst das Wichtigste, damit niemand mehr davon erwartet, als da ist:
**Der abgesicherte Modus blendet aus, er hält nichts zurück.** Die Einträge
stehen vollständig im Browser und in der API-Antwort; gefiltert wird beim
Rendern. Als Schutz gegen einen Blick über die Schulter taugt das, als
Zugriffsschutz nicht. Das ist eine Aussage über den Entwurf, kein Fehler —
festgehalten, damit es eine bewusste Grenze bleibt.

Zwei Fehler in der Funktion selbst:

1. **Der Tag-Vergleich war einseitig.** Der Tag des Videos wurde
   kleingeschrieben, die eingestellte Liste nicht::

       sensitiveTags.includes(t.toLowerCase())     // ['NSFW'].includes('nsfw')

   Wer „NSFW" in die Einstellungen tippte — die naheliegende Schreibweise —
   bekam nie einen Treffer. Aufgefallen ist es niemandem, weil die
   Voreinstellungen (`nsfw`, `adult`, `18+`) klein geschrieben sind und für die
   der Vergleich zufällig aufging.

2. **`video.FilePath` wurde ungeprüft dereferenziert.** Bei einem Eintrag ohne
   Pfad warf die Zeile — und zwar mitten in `filterAndSort()`. Der Filter fiel
   damit ganz aus, und der abgesicherte Modus zeigte *alles*. Ein Schutz, der
   im Fehlerfall in die offene Richtung versagt, ist der falsche Fehler.

Geprüft wird ausgeführt, nicht gelesen: `sensitive_eval_harness.js` lädt
utils.js in einen node-Kontext und ruft `isSensitive()` mit echten Eingaben auf.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARNESS = Path(__file__).parent / "sensitive_eval_harness.js"
node = shutil.which("node")

pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def evaluate(cases, **user_settings):
    payload = {"userSettings": user_settings or {}, "cases": cases}
    fixture = Path(__file__).parent / "_sensitive_fixtures.json"
    fixture.write_text(json.dumps(payload), encoding="utf-8")
    try:
        out = subprocess.run(
            [node, str(HARNESS), str(fixture)],
            capture_output=True, text=True, timeout=30,
        )
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    finally:
        fixture.unlink(missing_ok=True)


def video(path="/home/ralf/videos/a.mp4", tags=None):
    return {"FilePath": path, "tags": tags or []}


# --- 1. Der Tag-Vergleich ---

@pytest.mark.parametrize("configured", ["NSFW", "nsfw", "NsFw", " nsfw "])
def test_a_configured_tag_matches_however_it_was_typed(configured):
    """
    Der Fund. Vorher traf nur die exakt kleingeschriebene Schreibweise.
    """
    result = evaluate([video(tags=["nsfw"])], sensitive_tags=[configured])
    assert result == [True], f"'{configured}' in den Einstellungen greift nicht"


@pytest.mark.parametrize("on_the_video", ["NSFW", "nsfw", "Nsfw"])
def test_the_tag_on_the_video_may_be_written_any_way_too(on_the_video):
    assert evaluate([video(tags=[on_the_video])], sensitive_tags=["nsfw"]) == [True]


def test_an_unrelated_tag_does_not_match():
    assert evaluate([video(tags=["urlaub"])], sensitive_tags=["nsfw"]) == [False]


def test_the_defaults_apply_when_nothing_is_configured():
    cases = [video(tags=["nsfw"]), video(tags=["adult"]), video(tags=["18+"]),
             video(tags=["urlaub"])]
    assert evaluate(cases) == [True, True, True, False]


def test_an_empty_tag_list_disables_the_tag_check():
    """
    Wer die Liste bewusst leert, will keinen Tag-Filter — nicht die
    Voreinstellungen zurück. In JS ist `[]` wahr, `[] || defaults` liefert also
    `[]`; festgehalten, weil das leicht zu einem `?.length` verschlimmbessert
    wird.
    """
    assert evaluate([video(tags=["nsfw"])], sensitive_tags=[]) == [False]


# --- 2. Einträge ohne Pfad ---

def test_an_entry_without_a_path_does_not_break_the_filter():
    """
    Vorher warf `video.FilePath.replace(...)` — mitten im Filter, der damit
    ganz ausfiel und im abgesicherten Modus alles zeigte.
    """
    result = evaluate([{"tags": []}], sensitive_dirs=["/home/ralf/privat"])
    assert result == [False], f"Fehler statt Ergebnis: {result}"


def test_the_tag_check_still_works_without_a_path():
    """Nur der Pfad-Teil entfällt, nicht die ganze Beurteilung."""
    assert evaluate([{"tags": ["nsfw"]}], sensitive_tags=["nsfw"]) == [True]


def test_null_is_handled():
    assert evaluate([None]) == [False]


# --- Pfad-Vergleich ---

def test_a_file_inside_a_sensitive_directory_is_hidden():
    result = evaluate(
        [video("/home/ralf/privat/x.mp4")], sensitive_dirs=["/home/ralf/privat"]
    )
    assert result == [True]


def test_a_file_in_a_deeper_subdirectory_is_hidden_too():
    result = evaluate(
        [video("/home/ralf/privat/2024/x.mp4")], sensitive_dirs=["/home/ralf/privat"]
    )
    assert result == [True]


def test_a_file_outside_stays_visible():
    result = evaluate(
        [video("/home/ralf/urlaub/x.mp4")], sensitive_dirs=["/home/ralf/privat"]
    )
    assert result == [False]


def test_the_path_comparison_ignores_case():
    result = evaluate(
        [video("/home/ralf/Privat/x.mp4")], sensitive_dirs=["/home/ralf/privat"]
    )
    assert result == [True]


def test_backslashes_and_forward_slashes_are_treated_alike():
    result = evaluate(
        [video("C:\\Users\\Ralf\\Privat\\x.mp4")],
        sensitive_dirs=["C:/Users/Ralf/Privat"],
    )
    assert result == [True]


def test_an_empty_directory_entry_hides_nothing():
    """
    Eine leere Zeile im Einstellungsfeld darf nicht auf jeden Pfad passen —
    `startswith('')` ist immer wahr.
    """
    result = evaluate([video("/home/ralf/urlaub/x.mp4")], sensitive_dirs=["", "  "])
    assert result == [False]


def test_a_tilde_path_is_documented_as_not_matching():
    """
    Kein Fehler, den ich hier beheben kann: Im Browser ist nicht bekannt, wofür
    `~` steht. Wer `~/Privat` in die Einstellungen schreibt, bekommt still
    keinen Treffer — dieselbe Klasse wie der relative Scan-Ausschluss in
    `tests/test_scan_exclusions.py`. Steht im Übergabebericht.
    """
    result = evaluate([video("/home/ralf/Privat/x.mp4")], sensitive_dirs=["~/Privat"])
    assert result == [False], "Verhalten hat sich geändert — Bericht anpassen"


# --- Die Grenze des Entwurfs ---

def test_safe_mode_is_a_display_filter_only():
    """
    Festgehalten, damit die Grenze bewusst bleibt: Die Prüfung läuft
    ausschließlich im Browser. Gäbe es sie auch serverseitig, stünde sie in
    einer Route — dann müsste dieser Test angepasst werden, und genau dann soll
    jemand hinsehen.
    """
    routes = Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes"
    hits = [
        p.name for p in routes.glob("*.py")
        if "sensitive_dirs" in p.read_text(encoding="utf-8")
        and "u.data.sensitive_dirs" not in p.read_text(encoding="utf-8")
    ]
    assert hits == [], (
        f"Serverseitige Nutzung von sensitive_dirs in {hits} — der abgesicherte "
        "Modus ist bislang reine Anzeige, das wäre eine echte Änderung"
    )
