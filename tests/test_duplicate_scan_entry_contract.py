"""
test_duplicate_scan_entry_contract.py
-------------------------------------
Contract test: der Duplicate-Scan muss objektbasierte Einträge bekommen.

Why this exists:
    _media_cache.get() liefert seit dem OOM-Fix (5e33ebd) API-Dicts mit
    UI-Aliasen ("FilePath"), nicht mehr VideoEntry-Modelle. Der
    DuplicateDetector arbeitet aber durchgängig objektbasiert:
    v.file_path, v.size_mb, getattr(v, 'media_type', ...).

    Wird der Cache in run_duplicate_scan() verwendet, passiert zweierlei:
      1. Der Scan-Target-Filter stirbt mit
         "'dict' object has no attribute 'file_path'"
      2. Selbst ohne Filter liefe der Detector still falsch --
         getattr(dict, 'media_type', 'video') ergibt IMMER 'video',
         Bilder würden nie als Bilder erkannt und nie verglichen.

    Punkt 2 ist der gefährlichere: er wirft keinen Fehler. Deshalb prüft
    dieser Test die Quelle, nicht nur das Laufzeitverhalten.
"""
import inspect
import re

from arcade_scanner.database import db
from arcade_scanner.models.video_entry import VideoEntry
from arcade_scanner.server import api_handler


def _duplicate_scan_source() -> str:
    """Quelltext der Duplicate-Scan-Funktion, ohne Kommentare.

    Die Kommentare fliegen raus, weil genau dort erklärt steht, warum
    _media_cache.get() hier falsch ist – der erklärende Text würde sonst
    denselben Test auslösen, den er beschreibt.
    """
    for name, obj in inspect.getmembers(api_handler, inspect.isfunction):
        if "duplicate" in name.lower() and "scan" in name.lower():
            quelle = inspect.getsource(obj)
            return "\n".join(
                re.sub(r"#.*$", "", zeile) for zeile in quelle.splitlines()
            )
    raise AssertionError("Keine Duplicate-Scan-Funktion in api_handler gefunden")


def test_duplicate_scan_does_not_use_the_dict_cache():
    """_media_cache.get() liefert Dicts – im Duplicate-Pfad unbrauchbar."""
    source = _duplicate_scan_source()
    assert "_media_cache.get()" not in source, (
        "run_duplicate_scan() nutzt _media_cache.get(); das liefert API-Dicts "
        "mit UI-Aliasen. Der DuplicateDetector braucht VideoEntry-Objekte – "
        "nutze db.get_all()."
    )


def test_duplicate_scan_reads_entries_as_objects():
    """Der Scan greift attributbasiert zu, muss also db.get_all() verwenden."""
    source = _duplicate_scan_source()
    assert re.search(r"\bdb\.get_all\(\)", source), (
        "run_duplicate_scan() muss die Einträge über db.get_all() holen, "
        "damit die Attributzugriffe (v.file_path, v.media_type) tragen."
    )


def test_get_all_returns_objects_with_the_attributes_the_detector_uses():
    """Gegenprobe an der Datenquelle: die Felder müssen wirklich existieren."""
    assert db.get_all.__annotations__.get("return") is not None

    # Ein Modell genügt – geprüft wird der Vertrag, nicht der Datenbestand.
    entry = VideoEntry(FilePath="/tmp/a.mp4", Size_MB=1.0)
    for attribut in ("file_path", "size_mb", "media_type"):
        assert hasattr(entry, attribut), f"VideoEntry fehlt '{attribut}'"

    # get_all_dicts() liefert dagegen bewusst Aliase – wer die beiden
    # verwechselt, baut den Fehler von 5e33ebd nach.
    assert "FilePath" in VideoEntry.model_json_schema()["properties"]
