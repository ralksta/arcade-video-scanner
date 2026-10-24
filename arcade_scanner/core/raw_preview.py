"""Eingebettete JPEG-Vorschauen aus RAW-Dateien lesen.

Nur mit Pillow, ohne neue Laufzeitabhängigkeit. Reihenfolge:

1. ``Image.open()`` direkt — funktioniert für TIFF-basierte Formate wie CR2
   und DNG, weil Pillow den TIFF-Kopf bzw. die eingebettete Vorschau liest.
2. RAF-Kopf — Fujifilm legt Offset und Länge der JPEG-Vorschau als zwei
   Big-Endian-``uint32`` bei Byte 84–91 ab; Pillow erkennt RAF selbst nicht.
3. Größtes eingebettetes JPEG — SOI (``FF D8``) bis EOI (``FF D9``) suchen.
   Fängt CR3 und andere Formate, die Pillow nicht öffnet.

Vor der Rückgabe läuft ``ImageOps.exif_transpose``: DNG/ProRAW-Vorschauen
tragen die Ausrichtung im EXIF und wären sonst gedreht. Jeder Fehler endet in
``None`` — eine unlesbare RAW-Datei darf den Scan nicht abbrechen.
"""
from __future__ import annotations

import io
import struct
from pathlib import Path
from typing import Optional

from PIL import Image, ImageOps

_RAF_MAGIC = b"FUJIFILM"
_RAF_OFFSET_POS = 84
_RAF_HEADER_LEN = 92


def _oriented(img: Image.Image) -> Image.Image:
    """EXIF-Ausrichtung anwenden und das Bild von der Datei lösen."""
    try:
        return ImageOps.exif_transpose(img).copy()
    except Exception:
        return img.copy()


def _from_direct(path: str) -> Optional[Image.Image]:
    try:
        with Image.open(path) as img:
            img.load()
            return _oriented(img)
    except Exception:
        return None


def _from_raf(data: bytes) -> Optional[Image.Image]:
    if len(data) < _RAF_HEADER_LEN or not data.startswith(_RAF_MAGIC):
        return None
    try:
        offset, length = struct.unpack(
            ">II", data[_RAF_OFFSET_POS:_RAF_HEADER_LEN])
        if offset <= 0 or length <= 0 or offset + length > len(data):
            return None
        with Image.open(io.BytesIO(data[offset:offset + length])) as img:
            img.load()
            return _oriented(img)
    except Exception:
        return None


def _largest_jpeg(data: bytes) -> bytes:
    """Größtes vollständiges SOI…EOI-Stück in ``data``."""
    best = b""
    start = 0
    while True:
        soi = data.find(b"\xff\xd8", start)
        if soi == -1:
            break
        eoi = data.find(b"\xff\xd9", soi + 2)
        if eoi == -1:
            break
        chunk = data[soi:eoi + 2]
        if len(chunk) > len(best):
            best = chunk
        start = eoi + 2
    return best


def _from_embedded_jpeg(data: bytes) -> Optional[Image.Image]:
    jpeg = _largest_jpeg(data)
    if not jpeg:
        return None
    try:
        with Image.open(io.BytesIO(jpeg)) as img:
            img.load()
            return _oriented(img)
    except Exception:
        return None


def open_raw_preview(path: str) -> Optional[Image.Image]:
    """Vorschau eines RAW-Bildes als ausgerichtetes PIL-Bild — oder ``None``.

    Der Aufrufer schließt das zurückgegebene Bild nicht; es ist bereits von
    der Datei gelöst (``copy()``).
    """
    direct = _from_direct(path)
    if direct is not None:
        return direct

    try:
        data = Path(path).read_bytes()
    except OSError:
        return None

    if data.startswith(_RAF_MAGIC):
        raf = _from_raf(data)
        if raf is not None:
            return raf

    return _from_embedded_jpeg(data)
