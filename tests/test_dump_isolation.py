"""
test_dump_isolation.py
----------------------
Der statische HTML-Dump darf keine Medien- und keine Nutzerdaten enthalten.

Das ist die Grundlage der Mehrbenutzer-Trennung: `arcade_data/index.html` wird
*einmal* erzeugt und an jeden ausgeliefert, der die Seite öffnet. Stünden dort
Dateipfade, Favoriten oder Tags drin, sähe jeder Nutzer die Bibliothek des
anderen — unabhängig davon, was `/api/videos` später pfadgefiltert nachliefert.

Bis hierher gab es dafür keinen Test. Im Template stand eine Schleife, die von
jedem Eintrag eine Kopie zog und favorite/hidden/tags zurücksetzte; das Ergebnis
wurde aber nirgends eingebettet — die Bereinigung lief für den Papierkorb, und
CLAUDE.md beschrieb sie trotzdem als den Mechanismus der Trennung.
"""
import re

import pytest

from arcade_scanner.templates.dashboard_template import generate_html_report

# Diese Angaben werden dem Dump **nicht mehr übergeben** — die Funktion nimmt
# gar keine Einträge mehr entgegen. Sie stehen hier trotzdem, weil die Tests
# unten prüfen, dass nichts davon in der erzeugten Datei auftaucht: Der Dump
# könnte sie sich auch selbst beschaffen.
GEHEIM = {
    "pfad": "/geheim/privat/urlaub_2019.mp4",
    "tags": ["intim", "nicht_teilen"],
}


@pytest.fixture
def rendered(tmp_path):
    out = tmp_path / "index.html"
    generate_html_report(str(out), server_port=8000)
    return out.read_text(encoding="utf-8")


def test_the_dump_cannot_be_handed_any_entries():
    """
    Die stärkste Form der Trennung: nicht „die Einträge werden nicht
    eingebettet", sondern „es gibt keine Einträge zu übergeben".

    Der Parameter existierte noch, wurde aber von keiner Zeile mehr gelesen —
    und von fünf Aufrufern mit 8788 Pydantic-Umwandlungen befüllt. Ein
    Parameter, der Mediendaten annimmt und nichts damit tut, ist eine
    Einladung, ihn zu benutzen.
    """
    import inspect

    parameters = inspect.signature(generate_html_report).parameters

    assert "results" not in parameters
    assert list(parameters) == ["report_file", "server_port"]


def test_no_media_entries_are_embedded(rendered):
    assert "window.ALL_VIDEOS = [];" in rendered, (
        "ALL_VIDEOS wird nicht mehr leer initialisiert — der Dump könnte "
        "Medien-Einträge enthalten."
    )


def test_no_file_paths_leak_into_the_dump(rendered):
    assert "urlaub_2019.mp4" not in rendered
    assert "/geheim/privat" not in rendered
    assert GEHEIM["pfad"] not in rendered


@pytest.mark.parametrize("secret", ["intim", "nicht_teilen"])
def test_no_tags_leak_into_the_dump(rendered, secret):
    assert secret not in rendered


def test_folders_data_is_not_embedded(rendered):
    """
    FOLDERS_DATA enthielt die Ordner-Aggregation der *gesamten* Bibliothek und
    landete damit in der Seite, die jeder Nutzer bekommt — Verzeichnisnamen
    anderer Nutzer inklusive, samt vollem Pfad im title-Attribut der Sidebar.
    Der Ordner-Baum baut sich jetzt clientseitig aus ALL_VIDEOS auf.
    """
    match = re.search(r"window\.FOLDERS_DATA = (\{.*?\});", rendered, re.S)
    assert match, "FOLDERS_DATA-Zuweisung fehlt ganz — folder_browser.js erwartet sie"
    assert match.group(1).strip() == "{}", (
        f"FOLDERS_DATA ist im Dump befüllt: {match.group(1)[:120]}"
    )


def test_folder_tree_is_built_from_the_per_user_video_list():
    """Gegenprobe: die Aggregation muss clientseitig aus ALL_VIDEOS kommen."""
    from pathlib import Path

    js = (
        Path(__file__).parent.parent
        / "arcade_scanner" / "server" / "static" / "folder_browser.js"
    ).read_text(encoding="utf-8")
    assert "function buildFoldersData()" in js
    assert "window.ALL_VIDEOS" in js.split("function buildFoldersData()", 1)[1][:900]


def _code_only(source: str) -> str:
    """Kommentare und Docstrings raus, nur ausführbarer Code bleibt.

    Ohne das prüfen die Muster-Tests hier die Erklärung statt des Codes: Der
    Kommentar, der beschreibt, *warum* etwas entfernt wurde, nennt das
    Entfernte beim Namen. Genau daran ist dieser Test schon gescheitert — und
    das ist kein Einzelfall, sondern die Regel: Wer einen alten Weg abschafft,
    schreibt seinen Namen in die Begründung.

    Über den AST statt über Zeichenketten, weil ein Docstring selbst
    Anführungszeichen enthalten darf.
    """
    import ast

    # `ast.unparse()` gibt nur Code zurück — Kommentare kennt der Baum gar
    # nicht. Zu entfernen bleiben also die Docstrings.
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
                             ast.Module)) and ast.get_docstring(node):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def test_dead_stripping_loop_is_gone():
    """
    Die Schleife baute 8788 Dict-Kopien pro Neugenerierung und verwarf sie.
    Kommt sie zurück, ist entweder der Dump wieder gefährlich — oder es ist
    wieder toter Code.
    """
    import inspect
    import textwrap as _tw

    source = _code_only(_tw.dedent(inspect.getsource(generate_html_report)))
    assert "clean_results" not in source


def test_the_dump_asserts_no_library_wide_numbers():
    """
    Die Kopfzeile zeigt Anzahl und Größe als `...`; gefüllt wird zur Laufzeit
    aus `ALL_VIDEOS`, das pro Nutzer gefiltert ist.

    `render_header()` nahm dafür einmal zwei Argumente entgegen und benutzte
    beide nicht — der Aufrufer rechnete die Gesamtgröße der Bibliothek aus, um
    sie zu übergeben. Das war eine Einladung: Diese Datei wird EINMAL erzeugt
    und an jedes Konto ausgeliefert. Wer die Platzhalter „repariert", indem er
    die Argumente einsetzt, schreibt die Zahlen der gesamten Bibliothek in die
    Kopfzeile jedes Nutzers.
    """
    import inspect

    from arcade_scanner.templates.ui_components import render_header

    parameters = inspect.signature(render_header).parameters
    assert "count" not in parameters
    assert "size_gb" not in parameters

    body = inspect.getsource(render_header)
    assert 'id="header-video-count">...' in body
    assert 'id="header-size">...' in body


def test_claude_md_describes_the_actual_mechanism():
    """
    Die Doku behauptete, der Dump werde von Nutzerfeldern *bereinigt*. Er
    enthält gar keine Einträge — wer sich auf die Bereinigung verlässt, baut
    auf einer Zusage, die der Code nicht gibt.
    """
    from pathlib import Path

    doc = (Path(__file__).parent.parent / "CLAUDE.md").read_text(encoding="utf-8")
    isolation = [line for line in doc.splitlines() if "Multi-user isolation" in line]
    assert isolation, "Abschnitt zur Mehrbenutzer-Trennung fehlt in CLAUDE.md"
    assert "no** media entries" in isolation[0] or "no media entries" in isolation[0]
