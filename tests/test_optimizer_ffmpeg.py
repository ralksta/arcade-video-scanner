"""
test_optimizer_ffmpeg.py
------------------------
Integration tests for the ffmpeg-invoking optimizer helpers (output
integrity verification, probe clip extraction). Skipped entirely when
ffmpeg/ffprobe are not on PATH.
"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg/ffprobe not installed",
)


@pytest.fixture(scope="module")
def tiny_clip(tmp_path_factory):
    """2s synthetic H.264 clip with audio."""
    path = tmp_path_factory.mktemp("clips") / "tiny.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=24",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac",
         "-shortest", str(path)],
        check=True, capture_output=True,
    )
    return path


class TestGetVideoInfo:
    def test_returns_real_stream_fields(self, tiny_clip):
        # Regression: codec_type must be in -show_entries or the video-stream
        # lookup silently fails and width/height/pix_fmt are always empty.
        from video_optimizer import get_video_info
        info = get_video_info(tiny_clip)
        assert info["width"] == 320
        assert info["height"] == 240
        assert info["codec"] == "h264"
        assert info["pix_fmt"] != ""

    def test_10bit_clip_detected_as_hdr(self, tmp_path):
        from video_optimizer import get_video_info
        from optimizer_utils import is_hdr_or_10bit
        clip = tmp_path / "ten_bit.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=24",
             "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p10le", str(clip)],
            check=True, capture_output=True,
        )
        info = get_video_info(clip)
        assert is_hdr_or_10bit(info) is True


class TestVerifyIntegrity:
    def test_valid_file_passes(self, tiny_clip):
        from video_optimizer import verify_output_integrity
        ok, reason = verify_output_integrity(tiny_clip, expected_duration=2.0)
        assert ok, reason

    def test_wrong_duration_fails(self, tiny_clip):
        from video_optimizer import verify_output_integrity
        ok, reason = verify_output_integrity(tiny_clip, expected_duration=60.0)
        assert not ok
        assert "duration" in reason.lower()

    def test_truncated_file_fails(self, tiny_clip, tmp_path):
        from video_optimizer import verify_output_integrity
        broken = tmp_path / "broken.mp4"
        data = tiny_clip.read_bytes()
        broken.write_bytes(data[: len(data) // 3])
        ok, _reason = verify_output_integrity(broken, expected_duration=2.0)
        assert not ok

    def test_promote_staging_renames_on_success(self, tiny_clip, tmp_path):
        from video_optimizer import promote_staging
        staging = tmp_path / "s.mp4"
        shutil.copy(tiny_clip, staging)
        out = tmp_path / "final.mp4"
        assert promote_staging(staging, out, expected_duration=2.0) is True
        assert out.exists() and not staging.exists()

    def test_promote_staging_refuses_broken_file(self, tiny_clip, tmp_path):
        from video_optimizer import promote_staging
        staging = tmp_path / "s.mp4"
        data = tiny_clip.read_bytes()
        staging.write_bytes(data[: len(data) // 3])
        out = tmp_path / "final.mp4"
        assert promote_staging(staging, out, expected_duration=2.0) is False
        assert not out.exists() and not staging.exists()


@pytest.fixture(scope="module")
def long_clip(tmp_path_factory):
    """30s synthetic clip for probe extraction."""
    path = tmp_path_factory.mktemp("clips") / "long.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=30:size=320x240:rate=24",
         "-c:v", "libx264", "-preset", "ultrafast", "-g", "24", str(path)],
        check=True, capture_output=True,
    )
    return path


class TestProbeExtraction:
    def test_probe_is_short_and_valid(self, long_clip, tmp_path):
        from video_optimizer import extract_probe_clip, get_video_info
        probe = extract_probe_clip(long_clip, [2.0, 12.0, 22.0], segment_sec=4.0, work_dir=tmp_path)
        assert probe is not None and probe.exists()
        info = get_video_info(probe)
        assert 6.0 <= info["duration"] <= 18.0  # ~3x4s, keyframe-aligned slack

    def test_probe_segments_cleaned_up(self, long_clip, tmp_path):
        from video_optimizer import extract_probe_clip
        extract_probe_clip(long_clip, [2.0, 12.0, 22.0], segment_sec=4.0, work_dir=tmp_path)
        leftovers = list(tmp_path.glob("_probe_seg*")) + list(tmp_path.glob("_probe_list*"))
        assert leftovers == []

    def test_missing_input_returns_none(self, tmp_path):
        from video_optimizer import extract_probe_clip
        probe = extract_probe_clip(tmp_path / "nope.mp4", [1.0], segment_sec=4.0, work_dir=tmp_path)
        assert probe is None
