"""Unit tests for the optimization advisor (pure logic, no ffmpeg/fs)."""
import sys
from pathlib import Path

from arcade_scanner.core import optimization_advisor as adv
from arcade_scanner.models.video_entry import VideoEntry

# Add scripts to path for optimizer_utils import
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from optimizer_utils import (  # noqa: E402, I001
    bitrate_class as ou_bitrate_class,
    resolution_class as ou_resolution_class,
)


def _entry(**kw) -> VideoEntry:
    base = dict(file_path="/lib/a.mp4", size_mb=1000.0, bitrate_mbps=45.0,
                codec="h264", width=3840, height=2160, frame_rate=30.0,
                media_type="video")
    base.update(kw)
    return VideoEntry(**base)


def test_bucket_helpers_parity_with_optimizer_utils():
    for kbps in (0, 1000, 2499, 2500, 7999, 8000, 19999, 20000, 50000):
        assert adv.bitrate_class(kbps) == ou_bitrate_class(kbps)
    for h in (0, 480, 576, 577, 720, 800, 801, 1080, 1200, 1201, 1440, 1600, 1601, 2160):
        assert adv.resolution_class(h) == ou_resolution_class(h)


def test_heuristic_high_bitrate_4k_h264_saves_a_lot():
    result = adv.estimate_heuristic(_entry(), "hevc")
    assert result is not None
    saved_pct, known = result
    assert known is True
    assert saved_pct > 60  # 45 Mbit/s 4K h264 is far above the ~12 Mbit/s reference


def test_heuristic_lean_1080p_h264_saves_moderately():
    result = adv.estimate_heuristic(
        _entry(bitrate_mbps=3.5, width=1920, height=1080), "hevc")
    assert result is not None
    saved_pct, _ = result
    assert 20 < saved_pct < 50  # bounded by the codec factor, not the reference


def test_heuristic_same_codec_saves_little():
    fat = adv.estimate_heuristic(_entry(), "hevc")
    same = adv.estimate_heuristic(_entry(codec="hevc"), "hevc")
    assert same is not None and fat is not None
    assert same[0] < fat[0]


def test_heuristic_av1_target_beats_hevc_target():
    h = adv.estimate_heuristic(_entry(), "hevc")
    a = adv.estimate_heuristic(_entry(), "av1")
    assert a is not None and h is not None
    assert a[0] >= h[0]


def test_heuristic_unknown_codec_pair_flagged():
    result = adv.estimate_heuristic(_entry(codec="prores"), "hevc")
    assert result is not None
    assert result[1] is False


def test_heuristic_missing_data_returns_none():
    assert adv.estimate_heuristic(_entry(bitrate_mbps=0.0), "hevc") is None
    assert adv.estimate_heuristic(_entry(height=0), "hevc") is None


def test_heuristic_savings_capped():
    result = adv.estimate_heuristic(_entry(bitrate_mbps=200.0), "hevc")
    assert result is not None
    assert result[0] <= 85.0
