"""Characterization tests for arcade_scanner/scanner/manager.py.

ScannerManager orchestrates discovery, cache validation, probing and
persistence. Every collaborator it touches is a module-level import, so the
tests patch `db`, `config` and `fs_scanner` inside the manager's namespace and
stub the inspectors. Nothing touches the real database, the real media library
or ffprobe.

There is no pytest-asyncio here, so `run_scan` is driven with asyncio.run().
"""
import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.models.media_asset import MediaAsset, MediaType, VideoMetadata
from arcade_scanner.models.video_entry import VideoEntry
from arcade_scanner.scanner.manager import ScannerManager

# ---------------------------------------------------------------------------
# Doubles
# ---------------------------------------------------------------------------

class FakeDB:
    def __init__(self, entries=()):
        self.entries = {e.file_path: e for e in entries}
        self.removed = []
        self.upserted = []
        self.load_calls = 0

    def load(self):
        self.load_calls += 1

    def get_all(self):
        return list(self.entries.values())

    def get(self, path):
        return self.entries.get(path)

    def bulk_upsert(self, entries):
        self.upserted.extend(entries)

    def remove(self, path):
        self.removed.append(path)
        self.entries.pop(path, None)


class FakeScanner:
    """Stands in for the module-level fs_scanner singleton."""

    def __init__(self, items, on_yield=None):
        self.items = items
        self.on_yield = on_yield
        self.allow_images = False
        self.saved_scan_time = 0

    async def scan_directories(self, targets):
        for index, item in enumerate(self.items):
            yield item
            if self.on_yield:
                self.on_yield(index)

    def save_last_scan_time(self):
        self.saved_scan_time += 1


def make_asset(path, bitrate_mbps=5.0):
    return MediaAsset(
        FilePath=path,
        Size_MB=100.0,
        media_type=MediaType.VIDEO,
        video_metadata=VideoMetadata(codec="h264", bitrate_mbps=bitrate_mbps,
                                     duration_sec=60.0, width=1920, height=1080),
        Status="OK",
    )


def make_cached(path, mtime=1000, size_mb=100.0, **kw):
    return VideoEntry(FilePath=path, Size_MB=size_mb, mtime=mtime, **kw)


# The scan targets only have to exist — the fake scanner supplies the paths.
# A real directory is used so the "unavailable target" guard is not tripped by
# accident in tests that are about something else.
EXISTING_DIR = os.path.dirname(os.path.abspath(__file__))


def make_config(targets=(EXISTING_DIR,), **overrides):
    cfg = MagicMock()
    cfg.active_scan_targets = list(targets)
    cfg.settings.max_concurrent_video_scans = 2
    cfg.settings.max_concurrent_image_scans = 2
    cfg.settings.enable_resource_watchdog = False
    cfg.settings.verbose_scanning = False
    cfg.settings.precompute_thumbnails = False
    cfg.settings.bitrate_threshold_kbps = 15000
    cfg.settings.source_bitrate_threshold_mbps = 100
    for key, value in overrides.items():
        setattr(cfg.settings, key, value)
    return cfg


def run_scan(manager, fake_db, fake_scanner, cfg, stat_size=100.0, stat_mtime=1000,
             inspect_result="asset", stat_raises=None):
    """Drive run_scan with every collaborator stubbed out."""
    def fake_inspect_factory():
        async def fake_inspect(path):
            if inspect_result is None:
                return None
            if isinstance(inspect_result, Exception):
                raise inspect_result
            return make_asset(path)
        return fake_inspect

    manager.video_inspector.inspect = fake_inspect_factory()
    manager.image_inspector.inspect = fake_inspect_factory()

    # Only the synthetic media paths get a fake stat. Everything else falls
    # through to the real one — os.path.exists() is built on os.stat, and
    # faking it wholesale would make every path look like it exists, including
    # the deliberately absent scan targets.
    media_paths = {path for path, _ in fake_scanner.items}
    real_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        if str(path) not in media_paths:
            return real_stat(path, *args, **kwargs)
        if stat_raises is not None:
            raise stat_raises
        st = MagicMock()
        st.st_size = stat_size * 1024 * 1024
        st.st_mtime = stat_mtime
        return st

    user_db = MagicMock()
    user_db.get_all_users.return_value = []

    with patch("arcade_scanner.scanner.manager.db", fake_db), \
         patch("arcade_scanner.scanner.manager.config", cfg), \
         patch("arcade_scanner.scanner.manager.fs_scanner", fake_scanner), \
         patch("arcade_scanner.database.user_store.user_db", user_db), \
         patch("arcade_scanner.scanner.manager.os.stat", side_effect=fake_stat):
        return asyncio.run(manager.run_scan())


# ---------------------------------------------------------------------------
# Basic pipeline
# ---------------------------------------------------------------------------

class TestScanPipeline:
    def test_new_files_are_probed_and_stored(self):
        manager = ScannerManager()
        db = FakeDB()
        scanner = FakeScanner([("/media/a.mp4", True), ("/media/b.mp4", True)])

        run_scan(manager, db, scanner, make_config())

        assert sorted(a.file_path for a in db.upserted) == ["/media/a.mp4", "/media/b.mp4"]

    def test_cache_is_loaded_once(self):
        manager = ScannerManager()
        db = FakeDB()
        run_scan(manager, db, FakeScanner([("/media/a.mp4", True)]), make_config())
        assert db.load_calls == 1

    def test_scan_timestamp_is_saved_after_a_full_pass(self):
        manager = ScannerManager()
        scanner = FakeScanner([("/media/a.mp4", True)])
        run_scan(manager, FakeDB(), scanner, make_config())
        assert scanner.saved_scan_time == 1

    def test_is_scanning_is_cleared_afterwards(self):
        manager = ScannerManager()
        run_scan(manager, FakeDB(), FakeScanner([("/media/a.mp4", True)]), make_config())
        assert manager.is_scanning is False

    def test_a_second_concurrent_scan_returns_immediately(self):
        manager = ScannerManager()
        manager.is_scanning = True
        db = FakeDB()

        result = run_scan(manager, db, FakeScanner([("/media/a.mp4", True)]), make_config())

        assert result == 0
        assert db.load_calls == 0

    def test_unsupported_extensions_are_ignored(self):
        manager = ScannerManager()
        db = FakeDB()
        scanner = FakeScanner([("/media/notes.txt", True), ("/media/a.mp4", True)])

        run_scan(manager, db, scanner, make_config())

        assert [a.file_path for a in db.upserted] == ["/media/a.mp4"]

    def test_vanished_file_is_skipped(self):
        manager = ScannerManager()
        db = FakeDB()
        scanner = FakeScanner([("/media/a.mp4", True)])

        run_scan(manager, db, scanner, make_config(), stat_raises=OSError("gone"))

        assert db.upserted == []

    def test_failed_probe_stores_nothing(self):
        manager = ScannerManager()
        db = FakeDB()

        run_scan(manager, db, FakeScanner([("/media/a.mp4", True)]), make_config(),
                 inspect_result=None)

        assert db.upserted == []

    def test_inspector_exception_does_not_abort_the_scan(self):
        manager = ScannerManager()
        db = FakeDB()
        scanner = FakeScanner([("/media/a.mp4", True)])

        run_scan(manager, db, scanner, make_config(),
                 inspect_result=RuntimeError("ffprobe exploded"))

        assert db.upserted == []
        assert manager.is_scanning is False


# ---------------------------------------------------------------------------
# Cache validation
# ---------------------------------------------------------------------------

class TestCacheValidation:
    def test_unchanged_directory_skips_known_files(self):
        manager = ScannerManager()
        db = FakeDB([make_cached("/media/a.mp4")])
        scanner = FakeScanner([("/media/a.mp4", False)])

        run_scan(manager, db, scanner, make_config())

        assert db.upserted == []

    def test_unchanged_directory_still_probes_unknown_files(self):
        manager = ScannerManager()
        db = FakeDB()
        scanner = FakeScanner([("/media/new.mp4", False)])

        run_scan(manager, db, scanner, make_config())

        assert [a.file_path for a in db.upserted] == ["/media/new.mp4"]

    def test_identical_mtime_and_size_are_not_reprobed(self):
        manager = ScannerManager()
        db = FakeDB([make_cached("/media/a.mp4", mtime=1000, size_mb=100.0)])
        scanner = FakeScanner([("/media/a.mp4", True)])

        run_scan(manager, db, scanner, make_config(), stat_mtime=1000, stat_size=100.0)

        assert db.upserted == []

    def test_changed_mtime_triggers_a_reprobe(self):
        manager = ScannerManager()
        db = FakeDB([make_cached("/media/a.mp4", mtime=1000)])
        scanner = FakeScanner([("/media/a.mp4", True)])

        run_scan(manager, db, scanner, make_config(), stat_mtime=2000)

        assert len(db.upserted) == 1

    def test_changed_size_triggers_a_reprobe(self):
        manager = ScannerManager()
        db = FakeDB([make_cached("/media/a.mp4", mtime=1000, size_mb=100.0)])
        scanner = FakeScanner([("/media/a.mp4", True)])

        run_scan(manager, db, scanner, make_config(), stat_mtime=1000, stat_size=250.0)

        assert len(db.upserted) == 1

    def test_user_state_survives_a_reprobe(self):
        manager = ScannerManager()
        cached = make_cached("/media/a.mp4", mtime=1000, favorite=True,
                             hidden=True, tags=["keep"], imported_at=1600000000)
        db = FakeDB([cached])
        scanner = FakeScanner([("/media/a.mp4", True)])

        run_scan(manager, db, scanner, make_config(), stat_mtime=2000)

        stored = db.upserted[0]
        assert stored.favorite is True
        assert stored.vaulted is True
        assert stored.tags == ["keep"]
        assert stored.imported_at == 1600000000


class TestStatusClassification:
    def test_high_bitrate_is_flagged_high(self):
        manager = ScannerManager()
        db = FakeDB()

        with patch.object(ScannerManager, "__init__", ScannerManager.__init__):
            manager.video_inspector.inspect = None  # replaced inside run_scan
        run_scan(manager, db, FakeScanner([("/media/a.mp4", True)]),
                 make_config(bitrate_threshold_kbps=1000))

        assert db.upserted[0].status == "HIGH"

    def test_very_high_bitrate_is_flagged_source(self):
        manager = ScannerManager()
        db = FakeDB()

        run_scan(manager, db, FakeScanner([("/media/a.mp4", True)]),
                 make_config(source_bitrate_threshold_mbps=1))

        assert db.upserted[0].status == "SOURCE"

    @pytest.mark.parametrize("folder", ["source", "originals", "raw"])
    def test_files_in_source_folders_are_flagged_source(self, folder):
        manager = ScannerManager()
        db = FakeDB()

        run_scan(manager, db, FakeScanner([(f"/media/{folder}/a.mp4", True)]),
                 make_config())

        assert db.upserted[0].status == "SOURCE"

    def test_ordinary_bitrate_stays_ok(self):
        manager = ScannerManager()
        db = FakeDB()

        run_scan(manager, db, FakeScanner([("/media/a.mp4", True)]), make_config())

        assert db.upserted[0].status == "OK"


# ---------------------------------------------------------------------------
# Orphan pruning — deletes rows, so the guard conditions matter most
# ---------------------------------------------------------------------------

class TestOrphanPruning:
    def test_vanished_files_are_pruned_after_a_complete_scan(self):
        manager = ScannerManager()
        db = FakeDB([make_cached("/media/a.mp4"), make_cached("/media/gone.mp4")])
        scanner = FakeScanner([("/media/a.mp4", True)])

        run_scan(manager, db, scanner, make_config())

        assert db.removed == ["/media/gone.mp4"]

    def test_nothing_is_pruned_when_discovery_found_nothing(self):
        """An empty discovery must not wipe the library."""
        manager = ScannerManager()
        db = FakeDB([make_cached("/media/a.mp4")])

        run_scan(manager, db, FakeScanner([]), make_config())

        assert db.removed == []

    def test_a_stopped_scan_prunes_nothing(self):
        """Stopping mid-scan leaves an incomplete picture of what exists.

        Discovery streams paths, so a stop event means most of the library was
        never seen. Treating those unseen files as deleted would drop their rows
        — and with them the favorites, tags and vault flags the scan is supposed
        to preserve.
        """
        manager = ScannerManager()
        db = FakeDB([make_cached(f"/media/{n}.mp4") for n in "abcdef"])

        # Stop as soon as the first path has been handed over.
        scanner = FakeScanner(
            [(f"/media/{n}.mp4", True) for n in "abcdef"],
            on_yield=lambda index: manager.stop() if index == 0 else None,
        )

        run_scan(manager, db, scanner, make_config())

        assert db.removed == [], (
            f"a stopped scan deleted {len(db.removed)} rows it never re-checked"
        )

    def test_an_empty_target_list_prunes_nothing(self):
        """Ohne Ziele hat der Walk nichts gesehen — das ist kein Beleg dafür,
        dass die Dateien weg sind.

        Dieser Zustand ist neu erreichbar: `config.active_scan_targets` liefert
        seit dem Fail-Closed-Fix eine leere Liste, wenn die Benutzerdatenbank
        nicht lesbar ist (siehe tests/test_scan_targets_fallback.py). Genau dann
        darf nicht die ganze Bibliothek als verschwunden gelten.
        """
        manager = ScannerManager()
        db = FakeDB([make_cached(f"/media/{n}.mp4") for n in "abcdef"])

        run_scan(manager, db, FakeScanner([]), make_config(targets=()))

        assert db.removed == [], (
            f"ohne Scan-Ziele wurden {len(db.removed)} Einträge gelöscht"
        )

    def test_an_unavailable_scan_target_prunes_nothing(self, tmp_path):
        """An unmounted drive must not look like a mass deletion.

        AsyncFileSystem skips a missing target with a warning and moves on, so
        its files simply never appear in the discovered set. Pruning on that
        basis would delete every row belonging to the drive the moment it is
        not mounted — the single most destructive thing a scan can do, since
        those rows carry user tags and favorites.
        """
        mounted = tmp_path / "mounted"
        mounted.mkdir()
        unmounted = tmp_path / "external_drive"  # deliberately absent

        db = FakeDB([
            make_cached(str(mounted / "a.mp4")),
            make_cached(str(unmounted / "holiday.mp4")),
            make_cached(str(unmounted / "wedding.mp4")),
        ])
        manager = ScannerManager()
        scanner = FakeScanner([(str(mounted / "a.mp4"), True)])

        run_scan(manager, db, scanner,
                 make_config(targets=(str(mounted), str(unmounted))))

        assert db.removed == [], (
            f"an unmounted target cost {len(db.removed)} library rows"
        )


# ---------------------------------------------------------------------------
# Stopping a scan from another thread
#
# main.py:100 runs the startup scan inside a daemon thread with its own event
# loop, while the server serves requests on other threads. So stop() is called
# from a different thread than the one running the scan — which is what the
# stop signal has to survive.
# ---------------------------------------------------------------------------

class TestStopFromAnotherThread:
    def test_stop_signal_crosses_thread_boundaries(self):
        """A stop raised on another thread must actually end the scan."""
        import threading

        manager = ScannerManager()
        db = FakeDB()
        started = threading.Event()
        release = threading.Event()

        def on_yield(index):
            if index == 0:
                started.set()
                # Hold the scan open until the other thread has called stop().
                release.wait(timeout=5)

        scanner = FakeScanner(
            [(f"/media/clip_{i:03d}.mp4", True) for i in range(50)],
            on_yield=on_yield,
        )

        result = {}

        def run_in_thread():
            # Mirrors main.py: asyncio.run inside a plain worker thread.
            result["processed"] = run_scan(manager, db, scanner, make_config())

        worker = threading.Thread(target=run_in_thread)
        worker.start()

        assert started.wait(timeout=5), "scan never started"
        manager.stop()          # called from the main thread, not the scan's
        release.set()
        worker.join(timeout=15)

        assert not worker.is_alive(), "scan did not finish after stop()"
        assert len(db.upserted) < 50, (
            f"stop() was ignored — {len(db.upserted)} of 50 files were still processed"
        )

    def test_stop_event_is_safe_to_set_across_threads(self):
        """asyncio.Event.set() is not thread-safe; the stop flag must not be one."""
        import asyncio as _asyncio

        manager = ScannerManager()

        assert not isinstance(manager._stop_event, _asyncio.Event), (
            "stop() is called from request threads while the scan owns another "
            "event loop, so the flag must be a threading primitive"
        )
        manager.stop()
        assert manager._stop_event.is_set() is True
