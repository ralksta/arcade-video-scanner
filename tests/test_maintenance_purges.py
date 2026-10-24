"""
test_maintenance_purges.py
--------------------------
`core/maintenance.py` löscht Dateien — hinter `--rebuild`, `--rebuild-thumbs`
und `--cleanup`. Vorher ohne einen einzigen Test.

Drei Funde:

**1. Jede Wartung brach im Docker-Betrieb still ab.**

    if "arcade_data" not in config.hidden_data_dir:
        print("❌ [Safety] HIDDEN_DATA_DIR looks suspicious. Aborting purge.")
        return

Der Name „arcade_data" kommt nur in der lokalen Installation vor. Setzt
`CONFIG_DIR` das Verzeichnis auf ``/config``, trifft die Bedingung — und
`--rebuild` wie `--cleanup` taten nichts, ohne dass es so aussah. Geprüft wird
jetzt, was der Name prüfen sollte: dass nicht das Wurzel- oder
Home-Verzeichnis ausgefegt wird.

**2. Dieselbe Zeile stand zweimal in der Zielliste.**

    targets = [
        (config.thumb_dir, "thumb_", ".jpg"),
        (config.thumb_dir, "thumb_", ".jpg")
    ]

In `purge_media()` **und** in `purge_broken_media()`. Der Docstring sprach von
„thumbnail and preview directories" — ein Vorschau-Verzeichnis kennt der Code
nirgends; `arcade_data/previews` ist ein leerer Überrest. Die Schleife lief
also zweimal über dasselbe, und die Beschreibung stimmte nicht.

**3. `is_safe_to_delete()` verglich ohne Verzeichnisgrenze** — die fünfte
Fundstelle derselben Rechnung in dieser Nacht. Über den Aufrufweg nicht
erreichbar (die Schleifen listen immer das erwartete Verzeichnis), aber die
Funktion heisst „is_safe_to_delete" und wird gelesen wie eine Zusage.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.core import maintenance


@pytest.fixture
def data_dir(tmp_path):
    """Ein Datenverzeichnis mit Vorschaubildern und Fremdkörpern."""
    thumbs = tmp_path / "thumbnails"
    thumbs.mkdir()
    (thumbs / "thumb_aaa.jpg").write_bytes(b"jpeg")
    (thumbs / "thumb_leer.jpg").write_bytes(b"")
    (thumbs / "wichtig.txt").write_text("nicht anfassen", encoding="utf-8")
    (thumbs / "thumb_falsch.png").write_bytes(b"png")

    mock_config = MagicMock()
    mock_config.hidden_data_dir = str(tmp_path)
    mock_config.thumb_dir = str(thumbs)
    with patch.object(maintenance, "config", mock_config):
        yield thumbs


def names(folder):
    return sorted(p.name for p in folder.iterdir())


# --- 1. Der Docker-Fall ---

def test_a_path_without_the_word_arcade_data_still_works(data_dir, tmp_path):
    """
    Der Fund: Vorher entschied der **Name** des Verzeichnisses, ob überhaupt
    etwas passiert. Hier heisst es nicht „arcade_data" — und trotzdem muss die
    Wartung laufen.
    """
    assert "arcade_data" not in str(tmp_path)

    maintenance.purge_thumbnails()

    assert "thumb_aaa.jpg" not in names(data_dir)


def test_the_sanity_check_passes_for_an_ordinary_directory(data_dir):
    assert maintenance.data_dir_looks_sane() is True


@pytest.mark.parametrize("suspicious", [
    os.path.abspath(os.sep),
    os.path.abspath(os.path.expanduser("~")),
])
def test_the_sanity_check_refuses_root_and_home(suspicious, capsys):
    mock_config = MagicMock()
    mock_config.thumb_dir = suspicious
    mock_config.hidden_data_dir = suspicious

    with patch.object(maintenance, "config", mock_config):
        assert maintenance.data_dir_looks_sane() is False

    assert "Safety" in capsys.readouterr().out


def test_a_refused_directory_deletes_nothing(data_dir, capsys):
    before = names(data_dir)

    with patch.object(maintenance, "data_dir_looks_sane", return_value=False):
        maintenance.purge_media()
        maintenance.purge_thumbnails()
        maintenance.purge_broken_media()

    assert names(data_dir) == before


# --- 2. Die doppelte Zielliste ---

def test_the_target_list_has_no_duplicates():
    """
    Dieselbe Zeile stand zweimal da, in beiden Funktionen. Sie hat nichts
    kaputtgemacht — nur die Schleife doppelt laufen lassen und den Docstring
    zur Lüge.
    """
    import inspect

    for fn in (maintenance.purge_media, maintenance.purge_broken_media):
        source = inspect.getsource(fn)
        block = source.split("targets = [", 1)[1].split("]", 1)[0]
        assert block.count('config.thumb_dir') == 1, (
            f"{fn.__name__}: dasselbe Verzeichnis steht mehrfach in der Zielliste"
        )


def test_the_docstring_no_longer_promises_previews():
    """
    Ein Vorschau-Verzeichnis gibt es im Code nirgends. `arcade_data/previews`
    ist ein leerer Überrest einer früheren Fassung.

    Geprüft wird die **erste Zeile** — sie ist die Zusage. Der Rest des
    Docstrings darf „preview" nennen, weil er erklärt, was früher dort stand;
    ein Test über den ganzen Text wäre über genau diese Erklärung gestolpert
    (und ist es beim ersten Versuch auch).
    """
    summary = (maintenance.purge_media.__doc__ or "").strip().splitlines()[0]

    assert "preview" not in summary.lower()
    assert "vorschau-verzeichnis" not in summary.lower()


def test_the_cli_help_no_longer_promises_previews():
    from pathlib import Path

    main = (
        Path(__file__).parent.parent / "arcade_scanner" / "main.py"
    ).read_text(encoding="utf-8")

    assert "thumbnails and previews" not in main


# --- 3. Was gelöscht wird und was nicht ---

def test_only_thumbnails_are_removed(data_dir):
    maintenance.purge_thumbnails()

    assert names(data_dir) == ["thumb_falsch.png", "wichtig.txt"]


def test_a_foreign_file_is_never_touched(data_dir, capsys):
    maintenance.purge_media()

    assert (data_dir / "wichtig.txt").exists()


def test_broken_media_removes_only_empty_thumbnails(data_dir):
    maintenance.purge_broken_media()

    remaining = names(data_dir)
    assert "thumb_leer.jpg" not in remaining
    assert "thumb_aaa.jpg" in remaining
    assert "wichtig.txt" in remaining


# --- is_safe_to_delete ---

@pytest.mark.parametrize("filename,expected", [
    ("thumb_x.jpg", True),
    ("thumb_x.JPG", True),
    ("thumb_x.png", False),
    ("vorschau_x.jpg", False),
    ("wichtig.txt", False),
    (".thumb_x.jpg", False),
])
def test_the_naming_pattern_decides(tmp_path, filename, expected):
    folder = tmp_path / "thumbnails"
    folder.mkdir()

    assert maintenance.is_safe_to_delete(
        str(folder / filename), str(folder), "thumb_", ".jpg") is expected


def test_a_sibling_directory_with_a_shared_prefix_is_refused(tmp_path):
    """
    Die fünfte Fundstelle derselben Rechnung in dieser Nacht:
    `/…/thumbnails_alt/thumb_x.jpg` fängt buchstäblich mit `/…/thumbnails` an.
    Über den Aufrufweg nicht erreichbar — die Funktion heisst trotzdem
    „is_safe_to_delete".
    """
    folder = tmp_path / "thumbnails"
    sibling = tmp_path / "thumbnails_alt"
    folder.mkdir()
    sibling.mkdir()

    assert maintenance.is_safe_to_delete(
        str(sibling / "thumb_x.jpg"), str(folder), "thumb_", ".jpg") is False


def test_a_path_outside_is_refused(tmp_path):
    folder = tmp_path / "thumbnails"
    folder.mkdir()

    assert maintenance.is_safe_to_delete(
        "/etc/thumb_passwd.jpg", str(folder), "thumb_", ".jpg") is False


def test_it_uses_the_shared_boundary_helper():
    """Damit die Rechnung nicht zum sechsten Mal einzeln dasteht."""
    import inspect

    assert "path_is_within(" in inspect.getsource(maintenance.is_safe_to_delete)
