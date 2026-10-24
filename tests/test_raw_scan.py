"""
test_raw_scan.py
----------------
End-to-End: echter Walker → ImageInspector → create_thumbnail.

Die synthetische Bibliothek enthält CR2, DNG, RAF und JPG. Geprüft werden die
vier Schalterkombinationen:
- nur RAW  → nur die drei RAW-Einträge, jeder mit Vorschau
- nichts   → keine Einträge
- nur Fotos → nur die JPG
- beides   → alle vier

Ein zweiter Scan derselben Bibliothek darf keine Duplikate erzeugen.
"""
import asyncio
import io
import os
import struct
from unittest.mock import MagicMock, patch

from PIL import Image

from arcade_scanner.scanner.manager import ScannerManager


class FakeDB:
    def __init__(self):
        self.entries = {}
        self.upserted = []
        self.removed = []

    def load(self):
        pass

    def get_all(self):
        return list(self.entries.values())

    def get(self, path):
        return self.entries.get(path)

    def bulk_upsert(self, entries):
        self.upserted.extend(entries)
        for entry in entries:
            self.entries[entry.file_path] = entry

    def upsert(self, entry):
        self.entries[entry.file_path] = entry

    def remove(self, path):
        self.removed.append(path)
        self.entries.pop(path, None)


def make_tiff(path):
    Image.new("RGB", (40, 20), "red").save(
        path, format="TIFF", compression="jpeg")


def make_raf(path):
    buf = io.BytesIO()
    Image.new("RGB", (60, 30), "blue").save(buf, format="JPEG")
    jpeg = buf.getvalue()
    data = bytearray(84)
    data[0:16] = b"FUJIFILMCCD-RAW "
    data += struct.pack(">II", 92, len(jpeg))
    path.write_bytes(bytes(data) + jpeg)


def make_library(root):
    library = root / "library"
    library.mkdir()
    make_tiff(library / "photo.cr2")
    make_tiff(library / "photo.dng")
    make_raf(library / "photo.raf")
    Image.new("RGB", (40, 20), "green").save(
        library / "photo.jpg", format="JPEG")
    return library


def make_config(library, thumbs, data_dir):
    cfg = MagicMock()
    cfg.active_scan_targets = [str(library)]
    cfg.active_exclude_paths = []
    cfg.hidden_data_dir = str(data_dir)
    cfg.thumb_dir = str(thumbs)
    cfg.settings.min_size_mb = 0
    cfg.settings.min_image_size_kb = 0
    cfg.settings.max_concurrent_video_scans = 2
    cfg.settings.max_concurrent_image_scans = 2
    cfg.settings.enable_resource_watchdog = False
    cfg.settings.verbose_scanning = False
    cfg.settings.precompute_thumbnails = True
    cfg.settings.bitrate_threshold_kbps = 15000
    cfg.settings.source_bitrate_threshold_mbps = 100
    return cfg


def run_scan(root, library, *, scan_images, scan_raw, db=None):
    thumbs = root / "thumbs"
    thumbs.mkdir(exist_ok=True)
    data_dir = root / "_data"
    cfg = make_config(library, thumbs, data_dir)
    db = db or FakeDB()

    user = MagicMock()
    user.data.scan_images = scan_images
    user.data.scan_raw = scan_raw
    user_db = MagicMock()
    user_db.get_all_users.return_value = [user]

    manager = ScannerManager()
    manager.image_inspector.has_sips = False  # Pillow-Pfad erzwingen

    video_config = MagicMock()
    video_config.thumb_dir = str(thumbs)

    with patch("arcade_scanner.scanner.manager.db", db), \
         patch("arcade_scanner.scanner.manager.config", cfg), \
         patch("arcade_scanner.scanner.file_system.config", cfg), \
         patch("arcade_scanner.core.video_processor.config", video_config), \
         patch("arcade_scanner.database.user_store.user_db", user_db):
        asyncio.run(manager.run_scan())

    return db, thumbs


def names(db):
    return sorted(os.path.basename(a.file_path) for a in db.upserted)


def test_raw_only_scans_raw_and_writes_thumbnails(tmp_path):
    library = make_library(tmp_path)
    db, thumbs = run_scan(tmp_path, library, scan_images=False, scan_raw=True)

    assert names(db) == ["photo.cr2", "photo.dng", "photo.raf"]
    for asset in db.upserted:
        assert asset.thumb
        assert (thumbs / asset.thumb).is_file(), f"keine Vorschau für {asset.file_path}"


def test_neither_toggle_scans_nothing(tmp_path):
    library = make_library(tmp_path)
    db, _ = run_scan(tmp_path, library, scan_images=False, scan_raw=False)

    assert names(db) == []


def test_images_only_scans_the_jpeg(tmp_path):
    library = make_library(tmp_path)
    db, _ = run_scan(tmp_path, library, scan_images=True, scan_raw=False)

    assert names(db) == ["photo.jpg"]


def test_both_toggles_scan_everything(tmp_path):
    library = make_library(tmp_path)
    db, _ = run_scan(tmp_path, library, scan_images=True, scan_raw=True)

    assert names(db) == ["photo.cr2", "photo.dng", "photo.jpg", "photo.raf"]


def test_a_second_scan_does_not_duplicate_entries(tmp_path):
    library = make_library(tmp_path)
    db, _ = run_scan(tmp_path, library, scan_images=False, scan_raw=True)
    first = len(db.upserted)

    run_scan(tmp_path, library, scan_images=False, scan_raw=True, db=db)

    assert len(db.upserted) == first
    assert names(db) == ["photo.cr2", "photo.dng", "photo.raf"]
