"""Unit tests for the optimization advisor (pure logic, no ffmpeg/fs)."""
import json
import sys
from pathlib import Path

import pytest

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


# --- build_candidates tests -----------------------------------------------


def _empty_history(tmp_path):
    return adv.EncodeHistory(tmp_path / "none.jsonl")


def test_build_candidates_sorted_by_absolute_mb(tmp_path):
    entries = [
        _entry(file_path="/lib/small.mp4", size_mb=100.0),            # same pct, less MB
        _entry(file_path="/lib/big.mp4", size_mb=8000.0),
        _entry(file_path="/lib/lean.mp4", size_mb=5000.0, bitrate_mbps=1.2,
               width=1280, height=720),                                # included, lower pct
    ]
    out = adv.build_candidates(entries, "hevc", _empty_history(tmp_path), set())
    paths = [r["file_path"] for r in out["results"]]
    # Sorted by absolute MB savings (desc): big > lean > small
    assert paths == ["/lib/big.mp4", "/lib/lean.mp4", "/lib/small.mp4"]
    assert out["results"][0]["estimated_saved_mb"] > out["results"][1]["estimated_saved_mb"]
    assert out["results"][1]["estimated_saved_mb"] > out["results"][2]["estimated_saved_mb"]


@pytest.mark.xfail(reason="optimized_at field lands in Task 4", strict=False)
def test_build_candidates_exclusions(tmp_path):
    entries = [
        _entry(file_path="/lib/queued.mp4"),
        _entry(file_path="/lib/done.mp4", optimized_at=1723000000),
        _entry(file_path="/lib/photo.jpg", media_type="image"),
        _entry(file_path="/lib/nodata.mp4", bitrate_mbps=0.0),
        _entry(file_path="/lib/ok.mp4"),
    ]
    out = adv.build_candidates(entries, "hevc", _empty_history(tmp_path),
                               exclude_paths={"/lib/queued.mp4"})
    assert [r["file_path"] for r in out["results"]] == ["/lib/ok.mp4"]


def test_build_candidates_history_beats_heuristic(tmp_path):
    p = _write_history(tmp_path, [_rec(saved_pct=40.0), _rec(saved_pct=42.0),
                                  _rec(saved_pct=44.0)])
    out = adv.build_candidates([_entry()], "hevc", adv.EncodeHistory(p), set())
    r = out["results"][0]
    assert r["source"] == "history"
    assert r["confidence"] == "high"
    assert r["estimated_saved_pct"] == 42.0
    assert r["estimated_saved_mb"] == 420.0  # 1000 MB * 42%
    assert out["summary"]["history_based"] == 1


def test_build_candidates_confidence_levels(tmp_path):
    out = adv.build_candidates(
        [_entry(file_path="/lib/known.mp4"),
         _entry(file_path="/lib/odd.mp4", codec="prores")],
        "hevc", _empty_history(tmp_path), set())
    by_path = {r["file_path"]: r for r in out["results"]}
    assert by_path["/lib/known.mp4"]["confidence"] == "medium"
    assert by_path["/lib/odd.mp4"]["confidence"] == "low"
    assert all(r["source"] == "heuristic" for r in out["results"])


def test_build_candidates_summary_counts_all_but_results_capped(tmp_path):
    entries = [_entry(file_path=f"/lib/v{i}.mp4") for i in range(5)]
    out = adv.build_candidates(entries, "hevc", _empty_history(tmp_path), set(), limit=2)
    assert len(out["results"]) == 2
    assert out["summary"]["total_files"] == 5
    assert out["summary"]["total_estimated_saved_mb"] > out["results"][0]["estimated_saved_mb"]


def test_build_candidates_reason_mentions_codec_and_resolution(tmp_path):
    out = adv.build_candidates([_entry()], "hevc", _empty_history(tmp_path), set())
    reason = out["results"][0]["reason"]
    assert "h264" in reason.lower()
    assert "2160" in reason or "4k" in reason.lower()
