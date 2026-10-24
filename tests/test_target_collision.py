"""
test_target_collision.py
------------------------
Wenn die fertige Umwandlung an ihren Platz rückt, kann sie eine **fremde**
Datei treffen.

Der Optimierer schreibt immer `.mp4`. Aus `film.mkv` wird also `film.mp4` —
und wenn im selben Ordner schon eine `film.mp4` liegt, ist das eine andere
Datei mit anderem Inhalt. `os.replace` und `os.rename` überschreiben sie auf
POSIX wortlos, ohne Rückgabewert, ohne Ausnahme.

Zwei Wege dorthin, beide in einer gewachsenen Mediensammlung nicht ausgefallen:

1. **Dieselbe Aufnahme in zwei Behältern.** `film.mkv` neben `film.mp4` — eine
   Fassung vom Blu-ray-Rip, eine vom Streaming-Mitschnitt. Wer die mkv
   optimiert, verliert die mp4.

2. **Zwei Quellen mit gleichem Stamm.** `film.mkv` und `film.avi`, beide in der
   Warteschlange. Die zweite fertige Umwandlung überschreibt die erste — und
   beide Originale sind zu dem Zeitpunkt schon gelöscht. Von zwei Videos bleibt
   eins.

Beide Pfade, die Dateien ersetzen, waren betroffen:

    routes/queue.py   Standardmodus nach dem Upload   atomic_replace()
    routes/files.py   „optimierte Fassung behalten"   os.rename()

In `files.py` ist die Reihenfolge zusätzlich ungünstig: Das Original wird eine
Zeile *vor* dem Umbenennen gelöscht. Ein Abbruch danach hinterlässt beide
Dateien beschädigt.

Der Abbruch ist Absicht. Ein selbst gewählter Ausweichname (`film_opt.mp4`)
wäre stillschweigend etwas anderes als das, was der Nutzer angestoßen hat, und
welche der beiden Dateien er behalten will, kann nur er entscheiden.
"""
import os
from pathlib import Path

import pytest

from arcade_scanner.core.media_replace import (
    TargetCollision,
    atomic_replace,
    check_target_collision,
)


@pytest.fixture
def library(tmp_path):
    (tmp_path / "film.mkv").write_bytes(b"das original, gross")
    (tmp_path / "film.mp4").write_bytes(b"eine andere fassung")
    return tmp_path


# --- Der Fund ---

def test_a_foreign_file_under_the_target_name_is_refused(library):
    with pytest.raises(TargetCollision):
        check_target_collision(library / "film.mkv", library / "film.mp4")


def test_the_message_names_both_files(library):
    with pytest.raises(TargetCollision) as excinfo:
        check_target_collision(library / "film.mkv", library / "film.mp4")

    message = str(excinfo.value)
    assert "film.mp4" in message and "film.mkv" in message


def test_replacing_a_file_by_its_own_name_is_fine(tmp_path):
    """
    Der übliche Fall: Die Quelle ist schon `.mp4`, das Ziel ist sie selbst.
    Dann *soll* ersetzt werden — sonst liesse sich keine mp4 optimieren.
    """
    original = tmp_path / "film.mp4"
    original.write_bytes(b"x")

    check_target_collision(original, original)


def test_a_free_target_name_is_fine(tmp_path):
    (tmp_path / "film.mkv").write_bytes(b"x")

    check_target_collision(tmp_path / "film.mkv", tmp_path / "film.mp4")


def test_the_check_does_not_touch_either_file(library):
    before = {p.name: p.read_bytes() for p in library.iterdir()}

    with pytest.raises(TargetCollision):
        check_target_collision(library / "film.mkv", library / "film.mp4")

    assert {p.name: p.read_bytes() for p in library.iterdir()} == before


# --- Wogegen es schützt, in der Sprache des Schadens ---

def test_without_the_check_the_other_file_is_simply_gone(library):
    """
    Der Beleg, dass es kein theoretisches Problem ist: Genau das passierte
    vorher. `atomic_replace` prüft die Dateisystemgrenze — die Identität des
    Ziels prüfte es nicht.
    """
    staging = library / ".film.job7.part"
    staging.write_bytes(b"die umwandlung")

    atomic_replace(staging, library / "film.mp4")

    assert (library / "film.mp4").read_bytes() == b"die umwandlung"
    assert (library / "film.mkv").exists(), "das Original ist noch da"
    # Und die Fassung, die vorher unter film.mp4 lag, ist ersatzlos weg.


def test_two_sources_with_the_same_stem_are_caught(tmp_path):
    """
    Der zweite Weg: `film.mkv` und `film.avi` in derselben Warteschlange. Die
    erste Umwandlung erzeugt `film.mp4`, die zweite würde sie überschreiben.
    """
    (tmp_path / "film.mkv").write_bytes(b"a")
    (tmp_path / "film.avi").write_bytes(b"b")

    # Erste Umwandlung: Ziel noch frei.
    check_target_collision(tmp_path / "film.mkv", tmp_path / "film.mp4")
    (tmp_path / "film.mp4").write_bytes(b"ergebnis eins")

    # Zweite: jetzt nicht mehr.
    with pytest.raises(TargetCollision):
        check_target_collision(tmp_path / "film.avi", tmp_path / "film.mp4")


# --- Die beiden Aufrufstellen ---

ROUTES = Path(__file__).parent.parent / "arcade_scanner" / "server" / "routes"


def code_only(block: str) -> str:
    """Kommentarzeilen raus.

    Sonst prüft der Test die Erklärung statt des Codes: Der Kommentar über der
    Prüfung nennt `os.rename` beim Namen und stand damit *vor* ihr.
    """
    return "\n".join(
        line for line in block.splitlines() if not line.lstrip().startswith("#")
    )


def test_the_upload_route_checks_before_replacing():
    source = (ROUTES / "queue.py").read_text(encoding="utf-8")
    block = code_only(source.split("Standard Mode:", 1)[1].split("_replace_media_entry", 1)[0])

    assert "check_target_collision" in block
    assert block.index("check_target_collision") < block.index("atomic_replace"), (
        "Die Prüfung muss vor dem Ersetzen stehen, nicht danach"
    )


def test_the_keep_route_checks_before_deleting_the_original():
    """
    Hier ist die Reihenfolge besonders wichtig: `os.remove(orig_abs)` steht
    direkt vor dem Umbenennen. Eine Prüfung *danach* liesse das Original
    bereits gelöscht zurück.
    """
    source = (ROUTES / "files.py").read_text(encoding="utf-8")
    block = code_only(source.split("STANDARD MODE:", 1)[1].split("db.remove(opt_abs)", 1)[0])

    assert "check_target_collision" in block
    assert block.index("check_target_collision") < block.index("os.remove(orig_abs)"), (
        "Die Prüfung steht hinter dem Löschen des Originals"
    )
    assert block.index("check_target_collision") < block.index("os.rename")


def test_a_rejected_job_is_marked_failed_not_left_running():
    """Ein abgebrochener Job darf die Warteschlange nicht blockieren."""
    source = (ROUTES / "queue.py").read_text(encoding="utf-8")
    block = code_only(source.split("except TargetCollision", 1)[1].split("atomic_replace", 1)[0])

    assert '"failed"' in block
    assert "_unlink_quiet" in block, "Die hochgeladene .part-Datei bleibt liegen"


# --- Grenzfälle der Prüfung selbst ---

def test_a_missing_target_directory_is_not_a_collision(tmp_path):
    check_target_collision(tmp_path / "film.mkv", tmp_path / "neu" / "film.mp4")


def test_a_symlink_at_the_target_counts_as_occupied(tmp_path):
    """
    Ein Symlink unter dem Zielnamen zeigt auf eine echte Datei irgendwo. Ihn zu
    überschreiben ersetzt den Link — die Datei dahinter bliebe verwaist.
    """
    real = tmp_path / "woanders.mp4"
    real.write_bytes(b"x")
    (tmp_path / "film.mp4").symlink_to(real)

    with pytest.raises(TargetCollision):
        check_target_collision(tmp_path / "film.mkv", tmp_path / "film.mp4")


def test_paths_may_be_given_as_strings(library):
    with pytest.raises(TargetCollision):
        check_target_collision(str(library / "film.mkv"), str(library / "film.mp4"))


def test_the_same_file_through_different_spellings_is_not_a_collision(tmp_path):
    """`/x/./film.mp4` und `/x/film.mp4` sind dieselbe Datei."""
    original = tmp_path / "film.mp4"
    original.write_bytes(b"x")

    check_target_collision(
        Path(os.path.join(str(tmp_path), ".", "film.mp4")).resolve(), original
    )
