"""Unit tests for the optimization advisor (pure logic, no ffmpeg/fs)."""
import json
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


# --- EncodeHistory tests --------------------------------------------------


def _write_history(tmp_path, records):
    p = tmp_path / "encode_history.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return p


def _rec(**kw):
    base = dict(ts="2026-08-01T00:00:00", file="x.mp4", encoder="hevc_nvenc",
                codec="hevc_nvenc", height=2160, source_kbps=45000, q=30,
                ssim=0.97, saved_pct=70.0)
    base.update(kw)
    return base


def test_history_median_with_enough_samples(tmp_path):
    p = _write_history(tmp_path, [_rec(saved_pct=60.0), _rec(saved_pct=70.0),
                                  _rec(saved_pct=80.0)])
    h = adv.EncodeHistory(p)
    result = h.median_saved_pct("hevc", 2160, 45000)
    assert result == (70.0, 3)


def test_history_too_few_samples_returns_none(tmp_path):
    p = _write_history(tmp_path, [_rec(), _rec()])
    assert adv.EncodeHistory(p).median_saved_pct("hevc", 2160, 45000) is None


def test_history_bucket_mismatch_returns_none(tmp_path):
    p = _write_history(tmp_path, [_rec(), _rec(), _rec()])
    h = adv.EncodeHistory(p)
    assert h.median_saved_pct("hevc", 720, 45000) is None      # other resolution class
    assert h.median_saved_pct("hevc", 2160, 3000) is None      # other bitrate class


def test_history_target_codec_matching(tmp_path):
    p = _write_history(tmp_path, [
        _rec(codec="av1_nvenc", saved_pct=80.0), _rec(codec="av1_nvenc", saved_pct=80.0),
        _rec(codec="av1_nvenc", saved_pct=80.0),
        _rec(codec="libx265", saved_pct=50.0), _rec(codec="libx265", saved_pct=50.0),
        _rec(codec="libx265", saved_pct=50.0),
    ])
    h = adv.EncodeHistory(p)
    assert h.median_saved_pct("av1", 2160, 45000) == (80.0, 3)
    assert h.median_saved_pct("hevc", 2160, 45000) == (50.0, 3)


def test_history_corrupt_lines_and_missing_file(tmp_path):
    p = tmp_path / "encode_history.jsonl"
    p.write_text('not json\n{"broken": \n' + json.dumps(_rec()) + "\n", encoding="utf-8")
    assert adv.EncodeHistory(p).median_saved_pct("hevc", 2160, 45000) is None  # 1 < 3
    missing = adv.EncodeHistory(tmp_path / "nope.jsonl")
    assert missing.median_saved_pct("hevc", 2160, 45000) is None


def test_history_mtime_cache_reloads_on_change(tmp_path):
    p = _write_history(tmp_path, [_rec(), _rec(), _rec()])
    h = adv.EncodeHistory(p)
    assert h.median_saved_pct("hevc", 2160, 45000) is not None
    import os
    _write_history(tmp_path, [_rec(saved_pct=10.0)] * 3)
    os.utime(p, (1, 1))  # force a different mtime either way
    assert h.median_saved_pct("hevc", 2160, 45000) == (10.0, 3)
