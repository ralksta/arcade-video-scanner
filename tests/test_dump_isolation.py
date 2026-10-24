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


@pytest.fixture
def rendered(tmp_path):
    entries = [
        {
            "FilePath": "/geheim/privat/urlaub_2019.mp4",
            "Size_MB": 512.0,
            "Bitrate_Mbps": 8.0,
            "Status": "OK",
            "media_type": "video",
            "codec": "h264",
            "Duration_Sec": 120.0,
            "Width": 1920,
            "Height": 1080,
            "favorite": True,
            "hidden": True,
            "tags": ["intim", "nicht_teilen"],
            "thumb": "thumb_x.jpg",
            "mtime": 1_700_000_000.0,
        }
    ]
    out = tmp_path / "index.html"
    generate_html_report(entries, str(out), server_port=8000)
    return out.read_text(encoding="utf-8")


def test_no_media_entries_are_embedded(rendered):
    assert "window.ALL_VIDEOS = [];" in rendered, (
        "ALL_VIDEOS wird nicht mehr leer initialisiert — der Dump könnte "
        "Medien-Einträge enthalten."
    )


def test_no_file_paths_leak_into_the_dump(rendered):
    assert "urlaub_2019.mp4" not in rendered
    assert "/geheim/privat" not in rendered


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


def test_dead_stripping_loop_is_gone():
    """
    Die Schleife baute 8788 Dict-Kopien pro Neugenerierung und verwarf sie.
    Kommt sie zurück, ist entweder der Dump wieder gefährlich — oder es ist
    wieder toter Code.
    """
    import inspect

    source = inspect.getsource(generate_html_report)
    assert "clean_results" not in source


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
