"""RAW-Metadaten über den Pillow-Pfad des ImageInspectors."""
import asyncio
import io
import struct

from PIL import Image

from arcade_scanner.scanner.image_inspector import ImageInspector


def jpeg_bytes(size=(40, 20), color="red"):
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def raf_bytes(jpeg, offset=92):
    data = bytearray(84)
    data[0:16] = b"FUJIFILMCCD-RAW "
    data += struct.pack(">II", offset, len(jpeg))
    return bytes(data) + jpeg


def inspect(path):
    inspector = ImageInspector()
    inspector.has_sips = False  # Linux/Docker-Pfad erzwingen
    return asyncio.run(inspector.inspect(str(path)))


def test_tiff_based_raw_reports_dimensions_and_extension(tmp_path):
    path = tmp_path / "photo.cr2"
    Image.new("RGB", (40, 20), "red").save(
        path, format="TIFF", compression="jpeg")

    asset = inspect(path)

    assert asset is not None
    assert asset.image_metadata.width == 40
    assert asset.image_metadata.height == 20
    assert asset.image_metadata.format == "cr2"


def test_raf_uses_the_embedded_preview(tmp_path):
    path = tmp_path / "photo.raf"
    path.write_bytes(raf_bytes(jpeg_bytes((60, 30))))

    asset = inspect(path)

    assert asset is not None
    assert asset.image_metadata.width == 60
    assert asset.image_metadata.height == 30
    assert asset.image_metadata.format == "raf"


def test_unreadable_raw_is_skipped_without_crashing(tmp_path):
    path = tmp_path / "kaputt.dng"
    path.write_bytes(b"not a raw")

    assert inspect(path) is None
