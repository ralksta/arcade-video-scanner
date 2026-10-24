"""RAW-Vorschaubilder und Poster: Pillow statt ffmpeg."""
import io
import struct
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image


@pytest.fixture
def processor(tmp_path):
    from arcade_scanner.core import video_processor

    thumbs = tmp_path / "thumbnails"
    thumbs.mkdir()
    mock_config = MagicMock()
    mock_config.thumb_dir = str(thumbs)
    with patch.object(video_processor, "config", mock_config):
        yield video_processor, thumbs


def tiff_raw(path, size=(40, 20)):
    Image.new("RGB", size, "red").save(
        path, format="TIFF", compression="jpeg")
    return path


def raf_raw(path, size=(60, 30)):
    buf = io.BytesIO()
    Image.new("RGB", size, "blue").save(buf, format="JPEG")
    jpeg = buf.getvalue()
    data = bytearray(84)
    data[0:16] = b"FUJIFILMCCD-RAW "
    data += struct.pack(">II", 92, len(jpeg))
    path.write_bytes(bytes(data) + jpeg)
    return path


def open_size_and_format(path):
    with Image.open(path) as img:
        return img.size, img.format


def test_dng_thumbnail_uses_pillow_not_ffmpeg(processor, tmp_path):
    video_processor, thumbs = processor
    raw = tiff_raw(tmp_path / "photo.dng")

    with patch.object(video_processor.subprocess, "run",
                      side_effect=AssertionError("ffmpeg darf für RAW nicht laufen")):
        name = video_processor.create_thumbnail(str(raw))

    assert name == video_processor.thumbnail_name_for(str(raw))
    size, fmt = open_size_and_format(thumbs / name)
    assert size == (480, 270)
    assert fmt == "JPEG"


def test_raf_thumbnail_uses_the_embedded_preview(processor, tmp_path):
    video_processor, thumbs = processor
    raw = raf_raw(tmp_path / "photo.raf")

    name = video_processor.create_thumbnail(str(raw))

    assert name
    size, fmt = open_size_and_format(thumbs / name)
    assert size == (480, 270)
    assert fmt == "JPEG"


def test_raw_poster_is_1280x720(processor, tmp_path):
    video_processor, _ = processor
    raw = tiff_raw(tmp_path / "photo.dng")

    out = video_processor.create_poster(str(raw))

    assert out
    size, fmt = open_size_and_format(out)
    assert size == (1280, 720)
    assert fmt == "JPEG"


def test_unreadable_raw_leaves_no_thumbnail(processor, tmp_path):
    video_processor, thumbs = processor
    raw = tmp_path / "kaputt.cr2"
    raw.write_bytes(b"not a raw")

    assert video_processor.create_thumbnail(str(raw)) == ""
    assert list(thumbs.iterdir()) == []
