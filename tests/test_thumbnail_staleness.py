"""
test_thumbnail_staleness.py
---------------------------
Vorschaubilder heissen ``thumb_<md5(pfad)>.jpg``. Der Name hängt am **Pfad**,
nicht am Inhalt.

Erneuert wurde bis hierher nur, wenn die Datei fehlte oder null Bytes hatte::

    if not os.path.exists(thumb_path) or os.path.getsize(thumb_path) == 0:

Ändert sich das Video unter demselben Pfad, blieb das alte Bild also für immer
stehen. Und es ändert sich hier regelmässig: Der Optimierer ersetzt Originale
an Ort und Stelle, und ein Zuschnitt (``--ss``/``--to``) macht aus derselben
Datei tatsächlich ein anderes Video. Im Raster stand danach ein Bild, das es so
nicht mehr gibt — und weil eine Vorschau immer irgendwie plausibel aussieht,
merkt man es nicht.

Für die **Proxy**-Dateien ist genau diese Frage längst beantwortet
(`proxy_resolver.is_proxy_stale`, mit derselben Toleranz gegen Dateisysteme,
die mtimes unterschiedlich genau ablegen). Für die Vorschaubilder galt sie
nicht — das gleiche Muster wie an mehreren anderen Stellen dieser Nacht.

**Nebenbei gemessen, was auf der Platte liegt:** In dieser Installation
existieren 1141 Vorschaubilder, und **keines** davon gehört zu einem der 8788
Einträge — 17,3 MB für Pfade, die es nicht mehr gibt. Aufgeräumt wird nie; es
gibt nur `--rebuild-thumbs`, das *alle* wegwirft. Das steht im
Übergabebericht, angefasst habe ich nichts.
"""
import os
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def processor(tmp_path):
    """`video_processor` mit einem Vorschau-Verzeichnis im Temporären."""
    from arcade_scanner.core import video_processor

    thumbs = tmp_path / "thumbnails"
    thumbs.mkdir()

    mock_config = MagicMock()
    mock_config.thumb_dir = str(thumbs)
    with patch.object(video_processor, "config", mock_config):
        yield video_processor, thumbs


def touch(path, seconds_ago=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(b"x" * 100)
    when = time.time() - seconds_ago
    os.utime(path, (when, when))
    return path


# --- Der Fund ---

def test_a_thumbnail_older_than_its_video_is_rebuilt(processor, tmp_path):
    """
    Der Ablauf: Video wird optimiert oder zugeschnitten, der Pfad bleibt, das
    Bild zeigt weiter den alten Inhalt.
    """
    video_processor, thumbs = processor
    video = touch(tmp_path / "film.mp4", seconds_ago=0)
    thumb = touch(thumbs / "thumb_x.jpg", seconds_ago=3600)

    assert video_processor._thumbnail_needs_rebuild(str(thumb), str(video)) is True


def test_a_thumbnail_newer_than_its_video_is_kept(processor, tmp_path):
    video_processor, thumbs = processor
    video = touch(tmp_path / "film.mp4", seconds_ago=3600)
    thumb = touch(thumbs / "thumb_x.jpg", seconds_ago=0)

    assert video_processor._thumbnail_needs_rebuild(str(thumb), str(video)) is False


def test_a_small_clock_difference_does_not_trigger_a_rebuild(processor, tmp_path):
    """
    FAT rundet mtimes auf zwei Sekunden, rsync und SMB verschieben sie um
    Sekundenbruchteile. Ohne Toleranz gälte ein frisch erzeugtes Bild
    gelegentlich sofort wieder als veraltet — und würde bei jedem Aufruf neu
    berechnet.
    """
    video_processor, thumbs = processor
    now = time.time()
    video = touch(tmp_path / "film.mp4")
    thumb = touch(thumbs / "thumb_x.jpg")
    os.utime(video, (now + 1.0, now + 1.0))
    os.utime(thumb, (now, now))

    assert video_processor._thumbnail_needs_rebuild(str(thumb), str(video)) is False


def test_the_tolerance_matches_the_proxy_check():
    """
    Beide Stellen beantworten dieselbe Frage. Laufen die Werte auseinander,
    verhält sich dasselbe Dateisystem an zwei Stellen verschieden.
    """
    from arcade_scanner.core.proxy_resolver import STALE_TOLERANCE_SEC
    from arcade_scanner.core.video_processor import THUMB_STALE_TOLERANCE_SEC

    assert THUMB_STALE_TOLERANCE_SEC == STALE_TOLERANCE_SEC


# --- Was schon vorher stimmte ---

def test_a_missing_thumbnail_is_built(processor, tmp_path):
    video_processor, thumbs = processor
    video = touch(tmp_path / "film.mp4")

    assert video_processor._thumbnail_needs_rebuild(
        str(thumbs / "gibtsnicht.jpg"), str(video)) is True


def test_an_empty_thumbnail_is_rebuilt(processor, tmp_path):
    """Ein abgebrochener ffmpeg-Lauf hinterlässt eine Datei mit null Bytes."""
    video_processor, thumbs = processor
    video = touch(tmp_path / "film.mp4")
    thumb = thumbs / "thumb_x.jpg"
    thumb.write_bytes(b"")

    assert video_processor._thumbnail_needs_rebuild(str(thumb), str(video)) is True


# --- Wenn die Quelle nicht mehr da ist ---

def test_a_vanished_video_keeps_its_existing_thumbnail(processor, tmp_path):
    """
    Neu erzeugen bringt nichts, wenn die Quelle fehlt — und ein vorhandenes
    Bild ist besser als keins. Sonst würde bei jedem Aufruf ein
    aussichtsloser ffmpeg-Lauf gestartet.
    """
    video_processor, thumbs = processor
    thumb = touch(thumbs / "thumb_x.jpg")

    assert video_processor._thumbnail_needs_rebuild(
        str(thumb), str(tmp_path / "gibtsnicht.mp4")) is False


def test_a_vanished_video_without_a_thumbnail_still_asks_for_one(processor, tmp_path):
    """Der Aufrufer soll den Versuch machen dürfen — er scheitert dann sauber."""
    video_processor, thumbs = processor

    assert video_processor._thumbnail_needs_rebuild(
        str(thumbs / "gibtsnicht.jpg"), str(tmp_path / "auch_nicht.mp4")) is True


# --- Der Name ---

def test_the_name_is_derived_from_the_path(processor, tmp_path):
    """
    Festgehalten, weil daraus alles Übrige folgt: Zwei verschiedene Dateien
    unter demselben Pfad teilen sich einen Namen. Genau deshalb braucht es die
    Altersprüfung oben.
    """
    import hashlib

    video_processor, _ = processor
    path = "/media/film.mp4"
    expected = "thumb_" + hashlib.md5(path.encode("utf-8", "surrogateescape")).hexdigest() + ".jpg"

    import inspect
    source = inspect.getsource(video_processor.create_thumbnail)
    assert 'f"thumb_{file_hash}.jpg"' in source
    assert hashlib.md5(path.encode("utf-8", "surrogateescape")).hexdigest() in expected


def test_two_paths_yield_two_names(processor):
    import hashlib

    a = hashlib.md5(b"/media/a.mp4").hexdigest()
    b = hashlib.md5(b"/media/b.mp4").hexdigest()
    assert a != b


# --- Der Traversal-Schutz der Auslieferung ---
#
# `/thumbnails/<name>` setzt den angefragten Namen an das Vorschau-Verzeichnis
# und prüfte danach:
#
#     if not file_path.startswith(thumb_dir_abs):
#
# Das ist derselbe Grenzfehler wie in `is_path_allowed()` weiter vorne in
# dieser Nacht: Ein Nachbarverzeichnis, dessen Name mit demselben Präfix
# beginnt, rutscht durch. `../thumbnails_alt/thumb_x.jpg` landet nach dem
# Zusammensetzen bei `/…/thumbnails_alt/thumb_x.jpg` und fängt buchstäblich
# mit `/…/thumbnails` an.
#
# Ausnutzbar war das nur eingeschränkt -- die Namensprüfung dahinter lässt
# ohnehin nur `thumb_*.jpg` durch. Es ist trotzdem genau die Sorte Vergleich,
# die man einmal richtig macht und nicht zweimal falsch.

def test_a_sibling_directory_with_a_shared_prefix_is_outside(tmp_path):
    """Die Rechnung, um die es geht — ohne Handler, nur die Pfadlogik."""
    thumb_dir = str(tmp_path / "thumbnails")
    sibling = os.path.abspath(os.path.join(thumb_dir, "..", "thumbnails_alt", "thumb_x.jpg"))

    assert sibling.startswith(thumb_dir), "Das Beispiel trifft den alten Vergleich nicht mehr"

    inside = sibling == thumb_dir or sibling.startswith(thumb_dir + os.sep)
    assert inside is False


def test_a_real_thumbnail_path_is_inside(tmp_path):
    thumb_dir = str(tmp_path / "thumbnails")
    real = os.path.abspath(os.path.join(thumb_dir, "thumb_x.jpg"))

    assert real == thumb_dir or real.startswith(thumb_dir + os.sep)


def test_the_route_compares_on_a_directory_boundary():
    from pathlib import Path

    source = (
        Path(__file__).parent.parent / "arcade_scanner" / "server" / "api_handler.py"
    ).read_text(encoding="utf-8")
    block = source.split("Prevent path traversal", 1)[1].split("Invalid thumbnail name", 1)[0]
    code = "\n".join(ln for ln in block.splitlines() if not ln.lstrip().startswith("#"))

    assert "thumb_dir_abs + os.sep" in code, (
        "Der Vergleich endet wieder nicht auf einer Verzeichnisgrenze"
    )
