"""Eine Quelle für Bild- und RAW-Endungen.

`file_system.py`, `image_inspector.py` und `video_processor.py` führten ihre
Listen getrennt. Genau deshalb fehlten RAW-Dateien im Walker, obwohl der
Inspector sie längst kannte: Der Walker entschied vor dem Inspector, was
überhaupt einen Eintrag bekommt.

Die Trennung ist bewusst: `STANDARD_IMAGE_EXTENSIONS` hängt an „Include
Photos“, `RAW_EXTENSIONS` am eigenen RAW-Schalter. `ALL_IMAGE_EXTENSIONS` ist
die Vereinigung für Inspector und Thumbnail-Pfad.
"""
from __future__ import annotations

STANDARD_IMAGE_EXTENSIONS = frozenset({
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".heic", ".avif",
})

RAW_EXTENSIONS = frozenset({
    ".cr2",   # Canon RAW
    ".cr3",   # Canon RAW (neuer)
    ".nef",   # Nikon RAW
    ".arw",   # Sony RAW
    ".dng",   # Adobe Digital Negative
    ".raf",   # Fujifilm RAW
    ".orf",   # Olympus RAW
    ".rw2",   # Panasonic RAW
    ".pef",   # Pentax RAW
    ".srw",   # Samsung RAW
    ".raw",   # generisch
    ".rwl",   # Leica RAW
})

ALL_IMAGE_EXTENSIONS = STANDARD_IMAGE_EXTENSIONS | RAW_EXTENSIONS
