"""
test_optimizer_utils.py
-----------------------
Unit tests for scripts/optimizer_utils.py — the pure (subprocess-free) helper
logic behind the video optimizer: encode history Q seeding, HDR detection,
loudnorm filter building, scene-window selection, and worker scheduling.
"""
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from optimizer_utils import (  # noqa: E402
    bitrate_class,
    resolution_class,
    append_encode_history,
    suggest_q_from_history,
    nearest_quality_index,
)


class TestHistory:
    def test_bitrate_class_buckets(self):
        assert bitrate_class(1000) == "low"
        assert bitrate_class(5000) == "med"
        assert bitrate_class(15000) == "high"
        assert bitrate_class(50000) == "ultra"

    def test_resolution_class_buckets(self):
        assert resolution_class(480) == "sd"
        assert resolution_class(720) == "720"
        assert resolution_class(1080) == "1080"
        assert resolution_class(1440) == "1440"
        assert resolution_class(2160) == "2160"

    def test_append_and_suggest_median(self, tmp_path):
        hist = tmp_path / "h.jsonl"
        for q in (55, 65, 60, 60, 58):
            append_encode_history(
                {"encoder": "videotoolbox", "height": 1080,
                 "source_kbps": 12000, "q": q, "ssim": 0.97, "saved_pct": 40.0},
                history_path=hist,
            )
        assert suggest_q_from_history("videotoolbox", 1080, 12000, hist) == 60

    def test_suggest_needs_min_samples(self, tmp_path):
        hist = tmp_path / "h.jsonl"
        append_encode_history(
            {"encoder": "videotoolbox", "height": 1080,
             "source_kbps": 12000, "q": 60, "ssim": 0.97, "saved_pct": 40.0},
            history_path=hist,
        )
        assert suggest_q_from_history("videotoolbox", 1080, 12000, hist) is None

    def test_suggest_ignores_other_buckets(self, tmp_path):
        hist = tmp_path / "h.jsonl"
        for _ in range(5):
            append_encode_history(
                {"encoder": "nvenc", "height": 2160,
                 "source_kbps": 40000, "q": 30, "ssim": 0.97, "saved_pct": 40.0},
                history_path=hist,
            )
        assert suggest_q_from_history("videotoolbox", 1080, 12000, hist) is None

    def test_suggest_missing_file_returns_none(self, tmp_path):
        assert suggest_q_from_history("videotoolbox", 1080, 12000, tmp_path / "nope.jsonl") is None

    def test_suggest_survives_corrupt_lines(self, tmp_path):
        hist = tmp_path / "h.jsonl"
        hist.write_text('not json\n{"broken":\n')
        assert suggest_q_from_history("videotoolbox", 1080, 12000, hist) is None

    def test_nearest_quality_index(self):
        assert nearest_quality_index([75, 65, 55, 45], 58) == 2
        assert nearest_quality_index([24, 28, 32, 36, 40, 44], 30) == 1
