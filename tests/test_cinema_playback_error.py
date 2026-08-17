"""
test_cinema_playback_error.py
-----------------------------
Der Wiedergabe-Dialog schwieg, wenn nichts abspielte.

Weder `<video>` noch `<img>` hatten einen error-Handler. Ist die Datei
verschoben, gelöscht oder das Laufwerk gerade nicht eingehängt, öffnete sich
der Dialog mit einem schwarzen Bild und tat nichts. Der einzige Hinweis stand
in der Entwicklerkonsole.

Das ist genau die Lage, in der ein Programm kaputt wirkt, obwohl es
funktioniert — und sie ist häufiger als es klingt: Ein Netzlaufwerk, das nach
dem Ruhezustand nicht wieder da ist, reicht schon. Für den Nutzer sieht das
identisch aus zu einem Codec-Problem, einem Server-Fehler und einem defekten
Download. Diese Fälle brauchen aber völlig verschiedene Reaktionen.

Deshalb wird der Grund nachgeschlagen statt geraten: Ein HEAD auf dieselbe
Adresse unterscheidet „Datei nicht da" (404) von „Server sagt nein" (403) und
von „Datei ist da, der Browser kann sie nicht" (200). Kommt auch der HEAD nicht
durch, liegt es an der Verbindung, und es bleibt bei der allgemeinen Meldung —
raten wäre hier schlimmer als schweigen.

Nebenbei behoben: `video.play()` fing beim ersten Fehlschlag ab, schaltete auf
stumm und rief `play()` erneut auf — ohne Absicherung. Bei einer fehlenden
Datei scheitert auch dieser Aufruf, und die abgewiesene Zusage stand
unbehandelt in der Konsole.

Geprüft wird ausgeführt: `cinema_error_harness.js` lädt cinema.js in einen
node-Kontext, gibt den Statuscode der HEAD-Anfrage vor und meldet, was der
Kasten danach anzeigt.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
CINEMA_JS = (ROOT / "arcade_scanner" / "server" / "static" / "cinema.js").read_text(
    encoding="utf-8")
HARNESS = Path(__file__).parent / "cinema_error_harness.js"

node = shutil.which("node")
pytestmark = pytest.mark.skipif(node is None, reason="node not on PATH")


def render(modus):
    out = subprocess.run([node, str(HARNESS), modus],
                         capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


# --- Es steht überhaupt etwas da ---

def test_the_box_becomes_visible():
    assert render("404")["sichtbar"] is True


def test_the_path_is_shown():
    """
    Ohne den Pfad ist die Meldung nutzlos: Der ganze Zweck ist zu sagen,
    *welche* Datei fehlt.
    """
    assert render("404")["pfad"] == "/media/urlaub.mp4"


# --- Der Grund wird nachgeschlagen, nicht geraten ---

def test_a_missing_file_says_so():
    text = render("404")["text"]

    assert "moved, renamed or deleted" in text
    assert "not mounted" in text


def test_a_refused_path_says_something_else():
    assert "refused" in render("403")["text"]


def test_a_file_that_is_there_points_at_the_codec():
    """
    Der Fall, den man sonst mit dem fehlenden Laufwerk verwechselt: Die Datei
    liegt da, der Browser kann sie nur nicht.
    """
    text = render("200")["text"]

    assert "cannot" in text
    assert "codec" in text


def test_an_unreachable_server_keeps_the_general_message():
    """
    Kommt der HEAD nicht durch, liegt es an der Verbindung. Dann etwas über
    die Datei zu behaupten wäre geraten.
    """
    assert render("reject")["text"] == "The file could not be played."


# --- Struktur ---

def test_both_elements_report_errors():
    """
    Bilder sind derselbe Fall wie Videos — und der `<img>`-Zweig ist der
    stillere von beiden.
    """
    assert "video.onerror" in CINEMA_JS
    assert "image.onerror" in CINEMA_JS


def test_an_empty_src_is_not_treated_as_an_error():
    """
    Beim Schließen und beim Umschalten auf Bild wird `src` geleert. Das löst
    ein error-Ereignis aus und ist keines.
    """
    block = CINEMA_JS[CINEMA_JS.index("function initCinemaErrorReporting"):]
    block = block[:block.index("\n}\n")]

    assert block.count("getAttribute('src')") == 2


def test_the_handlers_are_assigned_not_added():
    """
    `addEventListener` würde bei jedem Öffnen einen weiteren Handler anhängen.
    """
    block = CINEMA_JS[CINEMA_JS.index("function initCinemaErrorReporting"):]
    block = block[:block.index("\n}\n")]

    assert "addEventListener" not in block


def test_the_box_is_cleared_when_the_dialog_opens_and_closes():
    """
    Sonst bliebe die Meldung der vorigen Datei beim Weiterblättern stehen.
    """
    assert CINEMA_JS.count("hideCinemaPlaybackError()") >= 2


def test_the_second_play_attempt_is_guarded():
    """
    Der stumme zweite Versuch scheitert bei einer fehlenden Datei ebenfalls.
    Ohne catch stand dort eine unbehandelte abgewiesene Zusage.
    """
    block = CINEMA_JS[CINEMA_JS.index("video.play().catch"):]
    block = block[:block.index("\n    }")]

    assert block.count(".catch(") == 2


def test_the_markup_has_the_elements():
    from arcade_scanner.templates.components import CINEMA_MODAL_COMPONENT

    for ident in ("cinemaPlaybackError", "cinemaPlaybackErrorText",
                  "cinemaPlaybackErrorPath"):
        assert f'id="{ident}"' in CINEMA_MODAL_COMPONENT
