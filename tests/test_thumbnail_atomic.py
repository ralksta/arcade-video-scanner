"""
test_thumbnail_atomic.py
------------------------
ffmpeg schrieb das Vorschaubild **direkt** in die Datei, die der Server unter
``/thumbnails/`` ausliefert. Zwei Wege zu einem halben Bild:

* Ein veraltetes Bild wird neu erzeugt (Optimierer, Zuschnitt): ``-y`` kürzt
  die ausgelieferte Datei sofort auf null, dann füllt ffmpeg sie langsam.
* Lazy-Erzeugung im Request-Thread: Der zweite Request sieht „existiert"
  und liefert aus, während der erste ffmpeg noch schreibt.

Ausgeliefert wird mit ``max-age=604800`` — der Browser behält das halbe Bild
eine Woche. Dasselbe Muster wie beim HTML-Dump in Nachtlauf 3: erst daneben
schreiben, dann an die Stelle setzen.
"""
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def processor(tmp_path):
    from arcade_scanner.core import video_processor

    thumbs = tmp_path / "thumbnails"
    thumbs.mkdir()
    mock_config = MagicMock()
    mock_config.thumb_dir = str(thumbs)
    with patch.object(video_processor, "config", mock_config):
        yield video_processor, thumbs


def _output_arg(cmd):
    """Der Ausgabepfad steht in beiden ffmpeg-Aufrufen direkt vor ``-y``."""
    args = [os.fsdecode(a) for a in cmd]
    return args[args.index("-y") - 1]


def _slow_ffmpeg(seen_during_write, served_path):
    """Schreibt in zwei Hälften und merkt sich, was dazwischen ausgeliefert würde."""
    def run(cmd, **kwargs):
        out = _output_arg(cmd)
        with open(out, "wb") as f:
            f.write(b"\xff\xd8HALF")
            f.flush()
            seen_during_write.append(
                open(served_path, "rb").read() if os.path.exists(served_path) else None
            )
            f.write(b"-REST\xff\xd9")
        return MagicMock(returncode=0)
    return run


def test_a_rebuild_never_exposes_a_half_written_thumbnail(processor, tmp_path):
    video_processor, thumbs = processor
    video = tmp_path / "film.mp4"
    video.write_bytes(b"v")
    served = thumbs / video_processor.thumbnail_name_for(str(video))
    served.write_bytes(b"OLD-COMPLETE-JPEG")
    old = os.path.getmtime(video) - 3600
    os.utime(served, (old, old))  # veraltet → wird neu erzeugt

    seen = []
    with patch.object(video_processor.subprocess, "run", _slow_ffmpeg(seen, str(served))):
        name = video_processor.create_thumbnail(str(video), duration=100.0)

    assert name == served.name
    assert seen == [b"OLD-COMPLETE-JPEG"], (
        f"Während ffmpeg schrieb, hätte ein Request das bekommen: {seen}"
    )
    assert served.read_bytes() == b"\xff\xd8HALF-REST\xff\xd9"


def test_a_first_build_is_invisible_until_complete(processor, tmp_path):
    video_processor, thumbs = processor
    video = tmp_path / "film.mp4"
    video.write_bytes(b"v")
    served = thumbs / video_processor.thumbnail_name_for(str(video))

    seen = []
    with patch.object(video_processor.subprocess, "run", _slow_ffmpeg(seen, str(served))):
        video_processor.create_thumbnail(str(video), duration=100.0)

    assert seen == [None], "Die halbe Datei war unter dem ausgelieferten Namen sichtbar"
    assert served.read_bytes().endswith(b"\xff\xd9")


def test_a_failed_build_leaves_no_temp_file_and_keeps_the_old_one(processor, tmp_path):
    video_processor, thumbs = processor
    video = tmp_path / "film.mp4"
    video.write_bytes(b"v")
    served = thumbs / video_processor.thumbnail_name_for(str(video))
    served.write_bytes(b"OLD")
    old = os.path.getmtime(video) - 3600
    os.utime(served, (old, old))

    def failing(cmd, **kwargs):
        open(_output_arg(cmd), "wb").close()  # ffmpeg hinterlässt eine leere Datei
        return MagicMock(returncode=1)

    with patch.object(video_processor.subprocess, "run", failing):
        assert video_processor.create_thumbnail(str(video), duration=100.0) == ""

    assert served.read_bytes() == b"OLD"
    assert sorted(p.name for p in thumbs.iterdir()) == [served.name]
