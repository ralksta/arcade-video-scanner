"""
test_raw_preview.py
-------------------
Synthetische RAW-artige Dateien für `core/raw_preview.py`. Echte Fotos kommen
nicht ins Repo.

Geprüft wird der gemessene Weg aus `dev-docs/raw-on-linux.md`: TIFF-basiert
direkt über Pillow, RAF über den Kopf bei Byte 84–91, sonst das größte
eingebettete JPEG — jeweils mit EXIF-Ausrichtung.
"""
import io
import struct

from PIL import Image

from arcade_scanner.core.raw_preview import open_raw_preview


def jpeg_bytes(size=(40, 20), color="red", orientation=None):
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    kwargs = {}
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation  # 0x0112 Orientation
        kwargs["exif"] = exif.tobytes()
    img.save(buf, format="JPEG", **kwargs)
    return buf.getvalue()


def raf_container(jpeg, offset=92):
    data = bytearray(84)
    data[0:16] = b"FUJIFILMCCD-RAW "
    data += struct.pack(">II", offset, len(jpeg))
    assert len(data) == offset
    return bytes(data) + jpeg


def test_tiff_based_raw_is_read_directly(tmp_path):
    """CR2/DNG sind TIFF-basiert; Pillow liest den Kopf selbst."""
    path = tmp_path / "photo.cr2"
    Image.new("RGB", (40, 20), "red").save(
        path, format="TIFF", compression="jpeg")

    preview = open_raw_preview(str(path))

    assert preview is not None
    assert preview.size == (40, 20)


def test_raf_header_is_used(tmp_path):
    """Pillow erkennt RAF nicht — Offset/Länge stehen bei Byte 84–91."""
    jpeg = jpeg_bytes((40, 20), "green")
    path = tmp_path / "photo.raf"
    path.write_bytes(raf_container(jpeg))

    preview = open_raw_preview(str(path))

    assert preview is not None
    assert preview.size == (40, 20)


def test_largest_embedded_jpeg_is_used(tmp_path):
    """Wenn Pillow die Datei nicht öffnet: größtes SOI…EOI-Stück nehmen."""
    small = jpeg_bytes((10, 10), "red")
    large = jpeg_bytes((60, 30), "blue")
    path = tmp_path / "photo.cr3"
    path.write_bytes(b"\x00" * 20 + small + b"\x00" * 20 + large + b"\x00" * 20)

    preview = open_raw_preview(str(path))

    assert preview is not None
    assert preview.size == (60, 30)


def test_exif_orientation_is_applied(tmp_path):
    """DNG/ProRAW-Vorschauen tragen die Drehung im EXIF."""
    jpeg = jpeg_bytes((40, 20), "red", orientation=6)
    path = tmp_path / "photo.dng"
    path.write_bytes(b"\x00" * 20 + jpeg)

    preview = open_raw_preview(str(path))

    assert preview is not None
    assert preview.size == (20, 40)


def test_missing_file_returns_none(tmp_path):
    assert open_raw_preview(str(tmp_path / "gibtsnicht.cr2")) is None


def test_corrupt_file_returns_none(tmp_path):
    path = tmp_path / "kaputt.cr2"
    path.write_bytes(b"not a raw file")

    assert open_raw_preview(str(path)) is None


def test_raf_with_invalid_offset_returns_none(tmp_path):
    data = bytearray(92)
    data[0:8] = b"FUJIFILM"
    data[84:92] = struct.pack(">II", 5000, 100)
    path = tmp_path / "kaputt.raf"
    path.write_bytes(bytes(data))

    assert open_raw_preview(str(path)) is None


def test_a_file_without_preview_returns_none(tmp_path):
    path = tmp_path / "leer.dng"
    path.write_bytes(b"\x00" * 4096)

    assert open_raw_preview(str(path)) is None
