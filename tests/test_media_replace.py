"""Tests for arcade_scanner/core/media_replace.py.

This is the last gate before an uploaded encode overwrites a library file, so
the failure modes matter more than the happy path.
"""
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.core.media_replace import atomic_replace, verify_media_integrity


class TestAtomicReplace:
    def test_the_target_is_overwritten(self, tmp_path):
        target = tmp_path / "a.mp4"
        target.write_bytes(b"old")
        staging = tmp_path / ".a.part"
        staging.write_bytes(b"new")

        atomic_replace(staging, target)

        assert target.read_bytes() == b"new"
        assert not staging.exists()

    def test_a_missing_target_is_created(self, tmp_path):
        staging = tmp_path / ".a.part"
        staging.write_bytes(b"new")
        target = tmp_path / "a.mp4"

        atomic_replace(staging, target)

        assert target.read_bytes() == b"new"

    def test_a_cross_filesystem_move_is_refused(self, tmp_path):
        """os.replace degrades to copy+delete across mounts — that is not
        atomic, and a crash mid-copy would destroy the original."""
        staging = tmp_path / ".a.part"
        staging.write_bytes(b"new")
        target = tmp_path / "a.mp4"
        target.write_bytes(b"old")

        devs = {str(staging): 1, str(target): 2}
        real_stat = Path(staging).stat()

        def fake_stat(path, **kwargs):
            st = MagicMock()
            st.st_dev = devs.get(str(path), real_stat.st_dev)
            return st

        with patch("arcade_scanner.core.media_replace.os.stat", side_effect=fake_stat):
            with pytest.raises(RuntimeError, match="filesystems"):
                atomic_replace(staging, target)

        assert target.read_bytes() == b"old"


class TestVerifyMediaIntegrity:
    def _probe(self, duration):
        return MagicMock(stdout=str(duration), returncode=0)

    def test_a_matching_duration_and_clean_decode_pass(self, tmp_path):
        path = tmp_path / "a.mp4"
        path.write_bytes(b"x")
        with patch("arcade_scanner.core.media_replace.subprocess.run",
                   side_effect=[self._probe(60.0), MagicMock(returncode=0, stderr="")]):
            assert verify_media_integrity(path, 60.0) == (True, "ok")

    def test_a_short_file_is_rejected(self, tmp_path):
        """The classic truncated upload: valid header, missing tail."""
        path = tmp_path / "a.mp4"
        path.write_bytes(b"x")
        with patch("arcade_scanner.core.media_replace.subprocess.run",
                   return_value=self._probe(12.0)):
            ok, reason = verify_media_integrity(path, 60.0)
        assert ok is False
        assert "duration mismatch" in reason

    def test_decode_errors_are_rejected(self, tmp_path):
        path = tmp_path / "a.mp4"
        path.write_bytes(b"x")
        with patch("arcade_scanner.core.media_replace.subprocess.run",
                   side_effect=[self._probe(60.0),
                                MagicMock(returncode=1, stderr="moov atom not found")]):
            ok, reason = verify_media_integrity(path, 60.0)
        assert ok is False
        assert "moov atom" in reason

    def test_an_unparseable_probe_is_rejected(self, tmp_path):
        path = tmp_path / "a.mp4"
        path.write_bytes(b"x")
        with patch("arcade_scanner.core.media_replace.subprocess.run",
                   return_value=MagicMock(stdout="N/A", returncode=0)):
            ok, reason = verify_media_integrity(path, 60.0)
        assert ok is False
        assert "ffprobe failed" in reason

    def test_an_unknown_expected_duration_skips_the_comparison(self, tmp_path):
        """Files the scanner never probed still get the decode check."""
        path = tmp_path / "a.mp4"
        path.write_bytes(b"x")
        with patch("arcade_scanner.core.media_replace.subprocess.run",
                   side_effect=[self._probe(3.0), MagicMock(returncode=0, stderr="")]):
            assert verify_media_integrity(path, 0)[0] is True

    def test_a_hanging_ffmpeg_is_reported_not_raised(self, tmp_path):
        path = tmp_path / "a.mp4"
        path.write_bytes(b"x")
        with patch("arcade_scanner.core.media_replace.subprocess.run",
                   side_effect=[self._probe(60.0),
                                subprocess.TimeoutExpired("ffmpeg", 1800)]):
            ok, reason = verify_media_integrity(path, 60.0)
        assert ok is False
        assert "decode check failed to run" in reason
