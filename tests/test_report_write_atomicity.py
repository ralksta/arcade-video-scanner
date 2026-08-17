"""
test_report_write_atomicity.py
------------------------------
Wer die Seite im falschen Moment lud, bekam eine halbe.

`generate_html_report()` schrieb mit `open(report_file, "w")`. Das kürzt die
Datei sofort auf null und füllt sie langsam wieder — und genau diese Datei
liefert der Server unter `/` aus.

Erzeugt wird sie nach **jedem** Schreibvorgang: Tag gesetzt, Einstellung
gespeichert, Optimierung fertig, Scan durch. Im Haushalt fällt das also
regelmäßig mit dem Augenblick zusammen, in dem jemand hinsieht — beim Scan-Ende
sogar systematisch, weil dann alle Geräte etwas Neues erwarten.

Dazu der zweite Fall: Zwei Erzeugungen gleichzeitig (der Entprellungs-Timer und
das Scan-Ende) schrieben beide in dieselbe Datei, ineinander.

Geschrieben wird jetzt daneben und dann getauscht — dasselbe Muster, das
`config.save()` und der Duplikat-Erkenner im selben Projekt schon benutzen.
Die Zwischendatei trägt Prozess- und Thread-Nummer, damit zwei gleichzeitige
Läufe sich nicht gegenseitig die halbfertige Datei wegziehen.
"""
import os
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from arcade_scanner.templates.dashboard_template import _write_atomically


@pytest.fixture
def ziel(tmp_path):
    return tmp_path / "index.html"


DOKUMENT = "<html>" + ("x" * 200_000) + "</html>"


# --- Der Fund ---

def test_a_reader_never_sees_a_half_written_file(ziel):
    """
    Der Kern, und der einzige Test, der den Fehler wirklich abbildet: Während
    geschrieben wird, liest jemand. Vorher war jede dieser Lesungen ein
    Glücksspiel.
    """
    ziel.write_text("<html>alt</html>", encoding="utf-8")
    gelesen = []
    stopp = threading.Event()

    def liest():
        while not stopp.is_set():
            try:
                gelesen.append(ziel.read_text(encoding="utf-8"))
            except FileNotFoundError:
                gelesen.append(None)

    leser = threading.Thread(target=liest)
    leser.start()
    try:
        for _ in range(20):
            _write_atomically(str(ziel), DOKUMENT)
    finally:
        stopp.set()
        leser.join()

    assert gelesen, "Der Leser kam nie zum Zug"
    unvollstaendig = [g for g in gelesen
                      if g is None or not g.endswith("</html>")]
    assert unvollstaendig == [], f"{len(unvollstaendig)} halbe Seiten gelesen"


def test_two_writers_leave_a_complete_document(ziel):
    """
    Zwei Erzeugungen gleichzeitig: der Entprellungs-Timer und das Scan-Ende.
    Der Verlierer darf höchstens dasselbe schreiben, nicht die Hälfte.
    """
    def schreibt(text):
        for _ in range(10):
            _write_atomically(str(ziel), text)

    a = threading.Thread(target=schreibt, args=("<html>A</html>",))
    b = threading.Thread(target=schreibt, args=("<html>B</html>",))
    a.start()
    b.start()
    a.join()
    b.join()

    assert ziel.read_text(encoding="utf-8") in ("<html>A</html>", "<html>B</html>")


# --- Wenn das Schreiben scheitert ---

def test_a_failing_write_leaves_the_old_file_intact(ziel):
    """
    Eine veraltete Seite ist besser als eine halbe — und mit `open(w)` war die
    alte beim ersten Byte weg.
    """
    ziel.write_text("<html>alt</html>", encoding="utf-8")

    echtes_open = open

    def bricht_bei_der_zwischendatei(pfad, *args, **kwargs):
        if ".tmp-" in str(pfad):
            raise OSError("kein Platz auf dem Gerät")
        return echtes_open(pfad, *args, **kwargs)

    with patch("builtins.open", bricht_bei_der_zwischendatei):
        with pytest.raises(OSError):
            _write_atomically(str(ziel), DOKUMENT)

    assert ziel.read_text(encoding="utf-8") == "<html>alt</html>"


def test_no_temp_file_is_left_behind_on_failure(ziel, tmp_path):
    with patch("arcade_scanner.templates.dashboard_template.os.replace",
               side_effect=OSError("kaputt")):
        with pytest.raises(OSError):
            _write_atomically(str(ziel), DOKUMENT)

    uebrig = [p.name for p in tmp_path.iterdir() if ".tmp-" in p.name]
    assert uebrig == []


def test_no_temp_file_is_left_behind_on_success(ziel, tmp_path):
    _write_atomically(str(ziel), DOKUMENT)

    uebrig = [p.name for p in tmp_path.iterdir() if ".tmp-" in p.name]
    assert uebrig == []


# --- Der gewöhnliche Fall ---

def test_the_content_arrives(ziel):
    _write_atomically(str(ziel), "<html>neu</html>")

    assert ziel.read_text(encoding="utf-8") == "<html>neu</html>"


def test_it_works_without_an_existing_file(ziel):
    assert not ziel.exists()

    _write_atomically(str(ziel), "<html>neu</html>")

    assert ziel.read_text(encoding="utf-8") == "<html>neu</html>"


def test_the_swap_is_a_replace(ziel):
    """
    `os.replace` ist auf beiden Systemen unteilbar, `os.rename` unter Windows
    nicht — und der Optimierer läuft auch dort.
    """
    with patch("arcade_scanner.templates.dashboard_template.os.replace") as tausch:
        _write_atomically(str(ziel), "<html>neu</html>")

    assert tausch.call_count == 1


def test_temp_names_of_simultaneous_writers_differ(ziel):
    """
    Zwei gleichzeitige Läufe dürfen nicht dieselbe Zwischendatei benutzen —
    sonst zieht der eine dem anderen die halbfertige unter den Füßen weg.

    Die Threads werden an einer Schranke zusammengehalten. Ohne sie liefe
    einer nach dem anderen, und Python vergibt die Thread-Nummer eines
    beendeten Threads wieder — der Test wäre dann grün oder rot je nach
    Laufzeit, und beides sagte nichts.
    """
    namen = []
    schranke = threading.Barrier(5)
    echtes_replace = os.replace

    def merkt_sich(src, dst):
        namen.append(os.path.basename(src))
        echtes_replace(src, dst)

    def schreibt():
        schranke.wait()
        _write_atomically(str(ziel), "<html>x</html>")

    with patch("arcade_scanner.templates.dashboard_template.os.replace", merkt_sich):
        threads = [threading.Thread(target=schreibt) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert len(set(namen)) == 5, namen


# --- Struktur ---

def test_the_generator_uses_it():
    """
    Auf entkommentiertem Text geprüft: Der Docstring der neuen Funktion nennt
    den alten Weg beim Namen — wie jede Begründung für eine Abschaffung. Das
    ist heute Nacht schon mehrfach über meine eigenen Muster-Tests gestolpert.
    """
    from test_dump_isolation import _code_only

    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "templates"
              / "dashboard_template.py").read_text(encoding="utf-8")

    assert "_write_atomically(report_file, final_html)" in quelle
    assert 'open(report_file, "w"' not in _code_only(quelle)


def test_the_debouncer_does_not_build_twice_at_once():
    quelle = (Path(__file__).parent.parent / "arcade_scanner" / "server"
              / "api_handler.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("class ReportDebouncer"):]
    block = block[:block.index("report_debouncer = ")]

    assert "self._generate_lock" in block
    assert "with self._generate_lock:" in block


def test_the_pattern_was_already_in_the_project():
    """
    Der Beleg, dass es keine Erfindung ist: Zwei Stellen machen es seit jeher
    genauso.
    """
    root = Path(__file__).parent.parent / "arcade_scanner"

    for datei in ("config.py", "core/duplicate_detector.py"):
        quelle = (root / datei).read_text(encoding="utf-8")
        assert "os.replace(" in quelle, datei
