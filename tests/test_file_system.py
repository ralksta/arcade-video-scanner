"""Characterization tests for arcade_scanner/scanner/file_system.py.

Everything runs against a synthetic tree under pytest's tmp_path; the real
media library and arcade_data/ are never touched. `config` is patched inside the
module's namespace so scan targets, exclusions and size thresholds are all test
controlled.

There is no pytest-asyncio in this project, so the async generator is driven
with asyncio.run() through the `collect` helper rather than by adding a plugin.
"""
import asyncio
import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.scanner.file_system import AsyncFileSystem


@pytest.fixture
def fake_config(tmp_path):
    """A config double with the fields file_system.py actually reads."""
    cfg = MagicMock()
    cfg.settings.min_size_mb = 0
    cfg.settings.min_image_size_kb = 0
    cfg.active_exclude_paths = []
    cfg.hidden_data_dir = str(tmp_path / "_data")
    with patch("arcade_scanner.scanner.file_system.config", cfg):
        yield cfg


@pytest.fixture
def fs(fake_config):
    return AsyncFileSystem()


def write_file(path, size_bytes=1024):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size_bytes)
    return path


def collect(scanner, targets):
    """Drain the async generator into a list of (path, dir_changed) tuples."""
    async def run():
        return [item async for item in scanner.scan_directories(targets)]
    return asyncio.run(run())


def names(results):
    return sorted(os.path.basename(path) for path, _ in results)


# ---------------------------------------------------------------------------
# _is_video
# ---------------------------------------------------------------------------

class TestIsVideo:
    @pytest.mark.parametrize("name", [
        "clip.mp4", "clip.mkv", "clip.avi", "clip.mov", "clip.m4v",
        "clip.wmv", "clip.flv", "clip.webm", "clip.ts",
    ])
    def test_video_extensions_accepted(self, fs, name):
        assert fs._is_video(name) is True

    def test_extension_match_is_case_insensitive(self, fs):
        assert fs._is_video("CLIP.MP4") is True

    @pytest.mark.parametrize("name", ["notes.txt", "archive.zip", "clip.mp3", "clip"])
    def test_non_video_extensions_rejected(self, fs, name):
        assert fs._is_video(name) is False

    def test_macos_resource_forks_are_skipped(self, fs):
        """AppleDouble sidecars mirror the real name and must not be scanned."""
        assert fs._is_video("._clip.mp4") is False

    def test_images_rejected_until_allow_images_is_set(self, fs):
        assert fs._is_video("photo.jpg") is False
        fs.allow_images = True
        assert fs._is_video("photo.jpg") is True

    @pytest.mark.parametrize("name", [
        "p.jpg", "p.jpeg", "p.png", "p.gif", "p.webp",
        "p.bmp", "p.tiff", "p.heic", "p.avif",
    ])
    def test_image_extensions_when_enabled(self, fs, name):
        fs.allow_images = True
        assert fs._is_video(name) is True


# ---------------------------------------------------------------------------
# _is_valid_size
# ---------------------------------------------------------------------------

class TestIsValidSize:
    def test_video_below_threshold_rejected(self, fs, fake_config, tmp_path):
        fake_config.settings.min_size_mb = 1
        fs._load_settings()
        small = write_file(tmp_path / "small.mp4", 1024)
        assert fs._is_valid_size(str(small)) is False

    def test_video_at_threshold_accepted(self, fs, fake_config, tmp_path):
        fake_config.settings.min_size_mb = 1
        fs._load_settings()
        big = write_file(tmp_path / "big.mp4", 1024 * 1024)
        assert fs._is_valid_size(str(big)) is True

    def test_images_use_the_kilobyte_threshold(self, fs, fake_config, tmp_path):
        fake_config.settings.min_size_mb = 100  # would reject everything
        fake_config.settings.min_image_size_kb = 2
        fs._load_settings()
        small = write_file(tmp_path / "small.jpg", 1024)
        big = write_file(tmp_path / "big.jpg", 4096)
        assert fs._is_valid_size(str(small)) is False
        assert fs._is_valid_size(str(big)) is True

    @pytest.mark.parametrize("name", ["clip_opt.mp4", "clip_trim.mp4"])
    def test_optimizer_outputs_bypass_the_size_floor(self, fs, fake_config, tmp_path, name):
        """_opt./_trim. files are the tool's own output and always qualify."""
        fake_config.settings.min_size_mb = 1000
        fs._load_settings()
        tiny = write_file(tmp_path / name, 10)
        assert fs._is_valid_size(str(tiny)) is True

    def test_missing_file_is_not_valid(self, fs, fake_config, tmp_path):
        fs._load_settings()
        assert fs._is_valid_size(str(tmp_path / "gone.mp4")) is False

    def test_missing_image_is_not_valid(self, fs, fake_config, tmp_path):
        fs._load_settings()
        assert fs._is_valid_size(str(tmp_path / "gone.jpg")) is False


# ---------------------------------------------------------------------------
# Settings and scan-time persistence
# ---------------------------------------------------------------------------

class TestSettings:
    def test_exclusions_are_resolved_to_absolute_paths(self, fs, fake_config, tmp_path):
        fake_config.active_exclude_paths = [str(tmp_path / "skip") + "/./"]
        fs._load_settings()
        assert str(tmp_path / "skip") in fs.exclude_abs

    def test_user_home_is_expanded_in_exclusions(self, fs, fake_config):
        fake_config.active_exclude_paths = ["~/Movies"]
        fs._load_settings()
        assert os.path.expanduser("~/Movies") in fs.exclude_abs

    def test_last_scan_time_defaults_to_zero(self, fs, fake_config):
        fs._load_settings()
        assert fs._last_scan_time == 0.0

    def test_last_scan_time_is_read_from_disk(self, fs, fake_config, tmp_path):
        data_dir = tmp_path / "_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / ".last_scan_time").write_text(json.dumps({"last_scan_time": 1234.5}))
        fs._load_settings()
        assert fs._last_scan_time == 1234.5

    def test_corrupt_scan_time_file_falls_back_to_zero(self, fs, fake_config, tmp_path):
        data_dir = tmp_path / "_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / ".last_scan_time").write_text("not json at all")
        fs._load_settings()
        assert fs._last_scan_time == 0.0

    def test_save_then_load_round_trip(self, fs, fake_config, tmp_path):
        fs._load_settings()
        fs.save_last_scan_time()
        assert (tmp_path / "_data" / ".last_scan_time").exists()

        fresh = AsyncFileSystem()
        fresh._load_settings()
        assert fresh._last_scan_time == pytest.approx(time.time(), abs=10)


# ---------------------------------------------------------------------------
# scan_directories — the async walk
# ---------------------------------------------------------------------------

class TestScanDirectories:
    def test_finds_videos_recursively(self, fs, fake_config, tmp_path):
        write_file(tmp_path / "a.mp4")
        write_file(tmp_path / "sub" / "b.mkv")
        write_file(tmp_path / "sub" / "deep" / "c.mov")
        write_file(tmp_path / "sub" / "notes.txt")

        results = collect(fs, [str(tmp_path)])

        assert names(results) == ["a.mp4", "b.mkv", "c.mov"]

    def test_yields_path_and_dir_changed_pairs(self, fs, fake_config, tmp_path):
        """The consumer in scanner/manager.py unpacks two values per item."""
        write_file(tmp_path / "a.mp4")

        results = collect(fs, [str(tmp_path)])

        assert len(results) == 1
        path, dir_changed = results[0]
        assert path.endswith("a.mp4")
        assert dir_changed is True

    def test_missing_target_is_skipped_without_raising(self, fs, fake_config, tmp_path):
        write_file(tmp_path / "real" / "a.mp4")

        results = collect(fs, [str(tmp_path / "does_not_exist"), str(tmp_path / "real")])

        assert names(results) == ["a.mp4"]

    def test_multiple_targets_are_all_scanned(self, fs, fake_config, tmp_path):
        write_file(tmp_path / "one" / "a.mp4")
        write_file(tmp_path / "two" / "b.mp4")

        results = collect(fs, [str(tmp_path / "one"), str(tmp_path / "two")])

        assert names(results) == ["a.mp4", "b.mp4"]

    def test_excluded_directory_is_pruned(self, fs, fake_config, tmp_path):
        write_file(tmp_path / "keep" / "a.mp4")
        write_file(tmp_path / "skip" / "b.mp4")
        fake_config.active_exclude_paths = [str(tmp_path / "skip")]

        results = collect(fs, [str(tmp_path)])

        assert names(results) == ["a.mp4"]

    def test_exclusion_covers_the_whole_subtree(self, fs, fake_config, tmp_path):
        write_file(tmp_path / "skip" / "deep" / "deeper" / "b.mp4")
        write_file(tmp_path / "keep.mp4")
        fake_config.active_exclude_paths = [str(tmp_path / "skip")]

        results = collect(fs, [str(tmp_path)])

        assert names(results) == ["keep.mp4"]

    def test_exclusion_does_not_match_by_name_prefix(self, fs, fake_config, tmp_path):
        """Excluding 'skip' must not also exclude a sibling named 'skipper'."""
        write_file(tmp_path / "skip" / "a.mp4")
        write_file(tmp_path / "skipper" / "b.mp4")
        fake_config.active_exclude_paths = [str(tmp_path / "skip")]

        results = collect(fs, [str(tmp_path)])

        assert names(results) == ["b.mp4"]

    def test_size_filter_applies_during_the_walk(self, fs, fake_config, tmp_path):
        fake_config.settings.min_size_mb = 1
        write_file(tmp_path / "small.mp4", 1024)
        write_file(tmp_path / "large.mp4", 2 * 1024 * 1024)

        results = collect(fs, [str(tmp_path)])

        assert names(results) == ["large.mp4"]

    def test_images_are_excluded_unless_enabled(self, fs, fake_config, tmp_path):
        write_file(tmp_path / "a.mp4")
        write_file(tmp_path / "photo.jpg")

        assert names(collect(fs, [str(tmp_path)])) == ["a.mp4"]

        fs.allow_images = True
        assert names(collect(fs, [str(tmp_path)])) == ["a.mp4", "photo.jpg"]

    def test_resource_forks_are_not_yielded(self, fs, fake_config, tmp_path):
        write_file(tmp_path / "a.mp4")
        write_file(tmp_path / "._a.mp4")

        results = collect(fs, [str(tmp_path)])

        assert names(results) == ["a.mp4"]

    def test_empty_directory_yields_nothing(self, fs, fake_config, tmp_path):
        (tmp_path / "empty").mkdir()
        assert collect(fs, [str(tmp_path / "empty")]) == []

    def test_more_files_than_the_queue_bound_all_arrive(self, fs, fake_config, tmp_path):
        """The walker's queue is bounded at 500; backpressure must not drop items."""
        for i in range(600):
            write_file(tmp_path / f"clip_{i:04d}.mp4", 16)

        results = collect(fs, [str(tmp_path)])

        assert len(results) == 600


# ---------------------------------------------------------------------------
# Incremental scanning
# ---------------------------------------------------------------------------

class TestIncrementalScan:
    def _seed_scan_time(self, tmp_path, when):
        data_dir = tmp_path / "_data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / ".last_scan_time").write_text(json.dumps({"last_scan_time": when}))

    def test_unchanged_directory_is_reported_as_not_changed(self, fs, fake_config, tmp_path):
        media = tmp_path / "media"
        write_file(media / "a.mp4")
        # Pretend the last scan happened well after this directory was written.
        self._seed_scan_time(tmp_path, time.time() + 3600)

        results = collect(fs, [str(media)])

        assert len(results) == 1
        assert results[0][1] is False
        assert fs._skipped_dirs == 1

    def test_changed_directory_is_reported_as_changed(self, fs, fake_config, tmp_path):
        media = tmp_path / "media"
        write_file(media / "a.mp4")
        self._seed_scan_time(tmp_path, time.time() - 3600)

        results = collect(fs, [str(media)])

        assert results[0][1] is True
        assert fs._skipped_dirs == 0

    def test_unchanged_directories_bypass_the_size_filter(self, fs, fake_config, tmp_path):
        """A file too small to qualify is still yielded from an unchanged dir.

        The walk only consults _is_valid_size when dir_changed is True, so on an
        incremental pass an undersized file reaches the consumer with
        dir_changed=False. Pinned as current behaviour: downstream is expected
        to reuse its cached entry rather than re-probe.
        """
        fake_config.settings.min_size_mb = 100
        media = tmp_path / "media"
        write_file(media / "tiny.mp4", 512)
        self._seed_scan_time(tmp_path, time.time() + 3600)

        results = collect(fs, [str(media)])

        assert names(results) == ["tiny.mp4"]
        assert results[0][1] is False

    def test_skipped_counter_resets_between_scans(self, fs, fake_config, tmp_path):
        media = tmp_path / "media"
        write_file(media / "a.mp4")
        self._seed_scan_time(tmp_path, time.time() + 3600)

        collect(fs, [str(media)])
        first = fs._skipped_dirs
        collect(fs, [str(media)])

        assert first == 1
        assert fs._skipped_dirs == 1


# ---------------------------------------------------------------------------
# Consumer abandoning the scan
#
# scanner/manager.py breaks out of `async for ... in scan_directories(...)` when
# its stop event fires. The walker runs in an executor thread and blocks on a
# bounded queue, so it has to notice that nobody is draining any more —
# otherwise it holds its worker thread for the lifetime of the event loop.
# ---------------------------------------------------------------------------

class TestAbandonedScan:
    def test_abandoned_scan_releases_its_worker_thread(self, fs, fake_config, tmp_path):
        """A stopped scan must not strand the executor thread it borrowed.

        Driven with a single-worker executor so the effect is deterministic: if
        the abandoned walker never returns, the next scan can never start and
        this test times out instead of hanging forever.
        """
        from concurrent.futures import ThreadPoolExecutor

        # More files than the queue bound (500), so the walker is mid-put when
        # the consumer walks away.
        for i in range(600):
            write_file(tmp_path / f"clip_{i:04d}.mp4", 16)

        async def scenario():
            asyncio.get_running_loop().set_default_executor(
                ThreadPoolExecutor(max_workers=1)
            )

            abandoned = fs.scan_directories([str(tmp_path)])
            consumed = 0
            async for _ in abandoned:
                consumed += 1
                if consumed >= 3:
                    break
            await abandoned.aclose()

            # The single worker must be free again for a second scan.
            return [item async for item in fs.scan_directories([str(tmp_path)])]

        async def guarded():
            return await asyncio.wait_for(scenario(), timeout=15)

        results = asyncio.run(guarded())

        assert len(results) == 600
