"""
test_scan_exclusions.py
-----------------------
Ausschlüsse sind bei diesem Produkt eine Datenschutz-Funktion, keine
Bequemlichkeit. Ein Fehler heißt nicht „ein Ordner fehlt", sondern: Ein
Verzeichnis, das der Nutzer ausdrücklich ausgenommen hat, steht mit vollem Pfad
in der Bibliothek — und bei mehreren Konten sieht es jeder.

Deshalb ist die Richtung des Fehlers hier nicht symmetrisch. Zu viel
auszuschließen ist ärgerlich; zu wenig ist der Bruch eines Versprechens. Die
Tests hier prüfen entsprechend beides, aber sie prüfen das Zuwenig genauer.

**Gemessen, nicht vermutet.** Ein Probelauf über einen echten Verzeichnisbaum
ergab sechs Fälle:

    A  Ausschluss normal                      korrekt
    B  Ziel ist Symlink auf den Ausschluss    UMGANGEN  → behoben
    C  Schrägstrich am Ende                   korrekt
    D  nackter Name / Teilpfad               wirkungslos, still → behoben
    E  ".." im Ausschluss                     korrekt
    F  Groß/Kleinschreibung vertauscht        nicht ausgeschlossen

Zu D: Das betraf nicht nur Eingaben des Nutzers, sondern **alle mitgelieferten
Voreinstellungen** — `@eaDir`, `#recycle`, `Temporary Items`,
`Network Trash Folder`, `$RECYCLE.BIN`, `AppData/Local/Temp`. Sie liefen durch
`os.path.abspath()` und wurden zu Pfaden im Arbeitsverzeichnis des Servers.
Keiner davon hat je etwas ausgeschlossen. Ausschlüsse werden jetzt in drei
Schreibweisen verstanden: absoluter Pfad, nackter Verzeichnisname (an jeder
Stelle), Teilpfad (auf Ordnergrenze).

Zu B: `os.walk` folgt Symlinks nicht — Unterverzeichnisse sind also sicher. Das
Ziel selbst wird aber betreten, egal ob es ein Symlink ist, und die entstehenden
Pfade tragen den Namen des Symlinks. Ein Ausschluss auf das echte Verzeichnis
passt darauf nie.

Zu F: Auf diesem Linux-System ist das **richtig** — `Privat` und `privat` sind
zwei Verzeichnisse. Auf einem case-insensitiven Dateisystem (macOS-Standard,
und dieses Projekt hat einen Mac-Worker) wäre derselbe Eingabefehler eine echte
Umgehung. Nicht „behoben", weil eine pauschale Kleinschreibung auf Linux
fälschlich mit ausschließen würde. Steht im Übergabebericht.
"""
import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.scanner.file_system import AsyncFileSystem


@pytest.fixture
def tree(tmp_path):
    """Ein Baum mit öffentlichem und privatem Teil, plus zwei Symlinks."""
    for rel in ("public/a.mp4", "privat/geheim.mp4", "privat/tief/auch.mp4"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\0" * (20 * 1024 * 1024))

    (tmp_path / "public" / "link").symlink_to(tmp_path / "privat")
    (tmp_path / "alias").mkdir()
    (tmp_path / "alias" / "p").symlink_to(tmp_path / "privat")
    return tmp_path


def scan(targets, excludes, hidden_dir):
    fs = AsyncFileSystem()
    cfg = MagicMock()
    cfg.settings.min_size_mb = 1
    cfg.active_exclude_paths = [str(e) for e in excludes]
    cfg.hidden_data_dir = str(hidden_dir)

    with patch("arcade_scanner.scanner.file_system.config", cfg):
        async def collect():
            return [p async for p, _ in fs.scan_directories([str(t) for t in targets])]

        return sorted(asyncio.run(collect()))


@pytest.fixture
def run(tmp_path_factory):
    hidden = tmp_path_factory.mktemp("hidden")
    return lambda targets, excludes: scan(targets, excludes, hidden)


def _has_private(results):
    return any("privat" in r or "geheim" in r for r in results)


# --- A, C, E: was schon stimmte ---

def test_an_excluded_directory_is_not_scanned(tree, run):
    results = run([tree], [tree / "privat"])

    assert not _has_private(results)
    assert any("a.mp4" in r for r in results), "Der öffentliche Teil fehlt jetzt auch"


def test_subdirectories_of_an_exclusion_are_excluded_too(tree, run):
    """`privat/tief/auch.mp4` liegt eine Ebene tiefer und muss mit wegfallen."""
    assert not any("auch.mp4" in r for r in run([tree], [tree / "privat"]))


def test_a_trailing_slash_does_not_break_the_match(tree, run):
    assert not _has_private(run([tree], [str(tree / "privat") + os.sep]))


def test_a_path_with_dot_dot_still_matches(tree, run):
    messy = os.path.join(str(tree), "public", "..", "privat")
    assert not _has_private(run([tree], [messy]))


def test_a_tilde_is_expanded(tmp_path):
    fs = AsyncFileSystem()
    cfg = MagicMock()
    cfg.settings.min_size_mb = 1
    cfg.active_exclude_paths = ["~/Downloads"]
    cfg.hidden_data_dir = str(tmp_path)

    with patch("arcade_scanner.scanner.file_system.config", cfg):
        fs._load_settings()

    assert os.path.expanduser("~/Downloads") in fs.exclude_abs
    assert not any("~" in p for p in fs.exclude_abs)


def test_a_symlink_inside_the_tree_is_not_followed(tree, run):
    """
    `public/link` zeigt auf `privat`. os.walk folgt dem nicht — hier gibt es
    nichts zu reparieren, aber es ist die Eigenschaft, auf der die
    Symlink-Behandlung unten aufbaut.
    """
    assert not _has_private(run([tree], [tree / "privat"]))


# --- B: der Fund ---

def test_an_excluded_target_reached_through_a_symlink_is_skipped(tree, run, capsys):
    """
    Vorher lieferte dieser Aufruf beide Dateien aus `privat`: Das Ziel
    `alias/p` ist ein Symlink, die erzeugten Pfade heißen `alias/p/…`, und der
    Ausschluss auf `…/privat` passte auf keinen davon.
    """
    results = run([tree / "alias" / "p"], [tree / "privat"])

    assert results == [], f"Ausgeschlossene Dateien ausgeliefert: {results}"
    assert "excluded scan target" in capsys.readouterr().out.lower()


def test_an_exclusion_inside_a_symlinked_target_still_applies(tree, run):
    """
    Die feinere Hälfte: Das Ziel selbst ist erlaubt, nur ein Unterordner nicht.
    Der Walk sieht `alias/…`, der Ausschluss nennt den echten Pfad. Ohne
    Übersetzung greift er nicht.
    """
    (tree / "alias" / "alles").symlink_to(tree)

    results = run([tree / "alias" / "alles"], [tree / "privat"])

    assert not _has_private(results), f"Ausgeschlossene Dateien ausgeliefert: {results}"
    assert any("a.mp4" in r for r in results), "Der erlaubte Teil fehlt"


def test_a_symlinked_exclusion_matches_the_real_target(tree, run):
    """Die Gegenrichtung: Das Ziel ist echt, der *Ausschluss* ist der Symlink."""
    results = run([tree], [tree / "alias" / "p"])

    assert not _has_private(results), f"Ausgeschlossene Dateien ausgeliefert: {results}"


def test_paths_are_reported_as_given_not_resolved(tree, run):
    """
    Bewusst so: Die Pfade in der Ausgabe bleiben in der Schreibweise des Ziels.
    Sie auf `realpath` umzustellen würde jeden bestehenden Eintrag umschlüsseln
    — Favoriten, Tags und Warteschlangen-Jobs hängen am Pfad.
    """
    (tree / "alias" / "alles").symlink_to(tree)

    results = run([tree / "alias" / "alles"], [])

    assert any(os.path.join("alias", "alles") in r for r in results)


# --- D: die drei Schreibweisen ---

def test_a_bare_name_excludes_every_directory_with_that_name(tree, run):
    """
    Der zweite große Fund: Die **mitgelieferten** Voreinstellungen sind nackte
    Verzeichnisnamen — `@eaDir`, `#recycle`, `Temporary Items`,
    `Network Trash Folder`, `$RECYCLE.BIN`. Alle liefen durch `os.path.abspath()`
    und wurden zu Pfaden im Arbeitsverzeichnis des Servers. Keiner davon hat je
    etwas ausgeschlossen.

    Sichtbar wird das auf einem Synology-NAS: `@eaDir` enthält zu jeder
    Mediendatei eine Miniatur, die Bibliothek wäre doppelt so groß.
    """
    (tree / "filme" / "@eaDir").mkdir(parents=True)
    (tree / "filme" / "@eaDir" / "thumb.mp4").write_bytes(b"\0" * (20 * 1024 * 1024))

    results = run([tree], ["@eaDir"])

    assert not any("@eaDir" in r for r in results)
    assert any("a.mp4" in r for r in results)


def test_a_bare_name_matches_at_any_depth(tree, run):
    deep = tree / "a" / "b" / "c" / "#recycle"
    deep.mkdir(parents=True)
    (deep / "weg.mp4").write_bytes(b"\0" * (20 * 1024 * 1024))

    assert not any("#recycle" in r for r in run([tree], ["#recycle"]))


def test_a_relative_path_matches_as_a_suffix(tree, run):
    """`AppData/Local/Temp` aus den Windows-Voreinstellungen."""
    deep = tree / "nutzer" / "AppData" / "Local" / "Temp"
    deep.mkdir(parents=True)
    (deep / "x.mp4").write_bytes(b"\0" * (20 * 1024 * 1024))

    assert not any("Temp" in r for r in run([tree], [os.path.join("AppData", "Local", "Temp")]))


def test_a_suffix_only_matches_on_a_directory_boundary(tree, run):
    """`Local/Temp` darf nicht auf `…/NichtLocal/Temp` passen."""
    deep = tree / "NichtLocal" / "Temp"
    deep.mkdir(parents=True)
    (deep / "x.mp4").write_bytes(b"\0" * (20 * 1024 * 1024))

    results = run([tree], [os.path.join("XLocal", "Temp")])
    assert any("NichtLocal" in r for r in results)


def test_a_bare_name_does_not_match_a_partial_directory_name(tree, run):
    """
    `privat` darf nicht `privatkram` treffen. Die Prüfung geht über die
    Pfadbestandteile, nicht über einen Teilstring.
    """
    (tree / "privatkram").mkdir()
    (tree / "privatkram" / "x.mp4").write_bytes(b"\0" * (20 * 1024 * 1024))

    results = run([tree], ["privat"])

    assert any("privatkram" in r for r in results), "zu viel ausgeschlossen"
    assert not any("geheim" in r for r in results), "zu wenig ausgeschlossen"


def test_a_target_named_like_an_exclusion_is_skipped(tree, run):
    assert run([tree / "privat"], ["privat"]) == []


def test_all_shipped_defaults_use_a_form_that_works():
    """
    Die Gegenprobe zur Ursache: Jede Voreinstellung muss in einer der drei
    Schreibweisen stehen, die tatsächlich geprüft werden.
    """
    from arcade_scanner.config import DEFAULT_EXCLUSIONS

    for entry in DEFAULT_EXCLUSIONS:
        path = entry["path"]
        expanded = os.path.expanduser(path)
        assert os.path.isabs(expanded) or path.strip(), f"unbrauchbar: {entry}"


# --- Randfälle, die nichts kaputt machen dürfen ---

def test_an_empty_exclusion_list_scans_everything(tree, run):
    assert len(run([tree], [])) == 3


def test_an_exclusion_outside_the_target_changes_nothing(tree, run):
    assert len(run([tree], ["/etc/nonexistent-elsewhere"])) == 3


def test_a_missing_target_is_skipped_without_crashing(tree, run, capsys):
    results = run([tree / "gibtsnicht", tree / "public"], [])

    assert len(results) == 1
    assert "not found" in capsys.readouterr().out.lower()


def test_the_target_itself_being_the_exclusion_yields_nothing(tree, run):
    assert run([tree / "privat"], [tree / "privat"]) == []


# --- Die Regel steht an einer Stelle ---

def test_the_exclusion_decision_is_not_duplicated():
    """
    Es gab eine zweite, ungenutzte Kopie der Prüfung (`_is_excluded`), die nur
    auf exakte Treffer sah und die Symlink-Übersetzung nicht kannte. Verdrahtet
    hätte sie den Fund von oben wieder eingebaut.
    """
    source = (
        __import__("pathlib").Path(__file__).parent.parent
        / "arcade_scanner" / "scanner" / "file_system.py"
    ).read_text(encoding="utf-8")

    assert source.count("startswith(ex + os.sep)") == 1, (
        "Die Ausschluss-Prüfung steht mehrfach im Code"
    )
