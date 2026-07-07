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
    is_hdr_or_10bit,
    apply_hdr_adjustments,
    parse_loudnorm_json,
    build_audio_filter_chain,
    select_top_windows,
    narrow_quality_window,
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


SDR = {"pix_fmt": "yuv420p", "color_transfer": "bt709", "color_primaries": "bt709"}
HDR10 = {"pix_fmt": "yuv420p10le", "color_transfer": "smpte2084", "color_primaries": "bt2020"}
HLG = {"pix_fmt": "yuv420p10le", "color_transfer": "arib-std-b67", "color_primaries": "bt2020"}


class TestHdr:
    def test_sdr_not_flagged(self):
        assert is_hdr_or_10bit(SDR) is False

    def test_hdr10_and_hlg_flagged(self):
        assert is_hdr_or_10bit(HDR10) is True
        assert is_hdr_or_10bit(HLG) is True

    def test_10bit_sdr_flagged(self):
        assert is_hdr_or_10bit({**SDR, "pix_fmt": "yuv420p10le"}) is True

    def test_missing_fields_not_flagged(self):
        assert is_hdr_or_10bit({}) is False

    def test_videotoolbox_gets_main10_p010(self):
        profile = {"codec": "hevc_videotoolbox",
                   "encoder_args": ["-profile:v", "main", "-allow_sw", "0"],
                   "video_filter": "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2"}
        adj = apply_hdr_adjustments(profile, HDR10)
        assert adj is not None
        assert "main10" in adj["encoder_args"]
        assert "main" not in [a for a in adj["encoder_args"] if a == "main"]
        assert "p010le" in adj["video_filter"]
        assert "-color_trc" in adj["color_args"]
        assert "smpte2084" in adj["color_args"]
        assert "bt2020" in " ".join(adj["color_args"])

    def test_hlg_transfer_passes_through(self):
        profile = {"codec": "libx265",
                   "encoder_args": ["-preset", "medium"],
                   "video_filter": "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2"}
        adj = apply_hdr_adjustments(profile, HLG)
        assert adj is not None
        assert "arib-std-b67" in adj["color_args"]
        assert "yuv420p10le" in adj["video_filter"]
        assert "main10" in adj["encoder_args"]

    def test_original_profile_not_mutated(self):
        profile = {"codec": "hevc_videotoolbox",
                   "encoder_args": ["-profile:v", "main"],
                   "video_filter": "format=yuv420p,scale=trunc(iw/2)*2:trunc(ih/2)*2"}
        apply_hdr_adjustments(profile, HDR10)
        assert profile["encoder_args"] == ["-profile:v", "main"]

    def test_unsupported_encoder_returns_none(self):
        profile = {"codec": "hevc_qsv", "encoder_args": [], "video_filter": "format=yuv420p"}
        assert apply_hdr_adjustments(profile, HDR10) is None


LOUDNORM_STDERR = """
[Parsed_loudnorm_3 @ 0x600002]
{
\t"input_i" : "-23.61",
\t"input_tp" : "-6.53",
\t"input_lra" : "5.90",
\t"input_thresh" : "-33.79",
\t"output_i" : "-19.02",
\t"output_tp" : "-2.03",
\t"output_lra" : "5.10",
\t"output_thresh" : "-29.13",
\t"normalization_type" : "dynamic",
\t"target_offset" : "0.02"
}
"""


class TestLoudnorm:
    def test_parse_extracts_measurements(self):
        m = parse_loudnorm_json(LOUDNORM_STDERR)
        assert m["input_i"] == "-23.61"
        assert m["target_offset"] == "0.02"

    def test_parse_garbage_returns_none(self):
        assert parse_loudnorm_json("no json here") is None

    def test_dynamic_chain_without_measurement(self):
        chain = build_audio_filter_chain("moderate")
        assert "loudnorm=I=-19:TP=-1.5:LRA=11" in chain
        assert "measured_I" not in chain
        assert chain.startswith("aformat=channel_layouts=stereo")

    def test_linear_chain_with_measurement(self):
        m = parse_loudnorm_json(LOUDNORM_STDERR)
        chain = build_audio_filter_chain("enhanced", measured=m)
        assert "loudnorm=I=-16" in chain
        assert "measured_I=-23.61" in chain
        assert "measured_TP=-6.53" in chain
        assert "measured_LRA=5.90" in chain
        assert "measured_thresh=-33.79" in chain
        assert "offset=0.02" in chain
        assert "linear=true" in chain

    def test_silent_audio_falls_back_to_dynamic(self):
        m = {"input_i": "-inf", "input_tp": "-inf",
             "input_lra": "0.00", "input_thresh": "-inf", "target_offset": "0.00"}
        chain = build_audio_filter_chain("moderate", measured=m)
        assert "measured_I" not in chain

    def test_standard_mode_returns_none(self):
        assert build_audio_filter_chain("standard") is None


class TestSceneWindows:
    def test_picks_heaviest_bucket_per_third(self):
        # 300s video, 5s buckets: heavy spots at 10s, 150s, 250s
        buckets = {i: 100 for i in range(60)}
        buckets[2] = 9000    # 10-15s (first third)
        buckets[30] = 8000   # 150-155s (second third)
        buckets[50] = 7000   # 250-255s (last third)
        starts = select_top_windows(buckets, 300.0, n=3, window=3.0, bucket_len=5.0)
        assert starts == [10.0, 150.0, 250.0]

    def test_empty_buckets_fall_back_to_percentages(self):
        starts = select_top_windows({}, 100.0, n=3, window=3.0)
        assert starts == [25.0, 50.0, 75.0]

    def test_starts_clamped_inside_duration(self):
        buckets = {19: 9999}  # 95-100s of a 100s video
        starts = select_top_windows(buckets, 100.0, n=3, window=3.0, bucket_len=5.0)
        for s in starts:
            assert 0.0 <= s <= 100.0 - 3.0 - 0.5

    def test_returns_sorted_unique(self):
        buckets = {0: 500, 1: 400, 2: 300}
        starts = select_top_windows(buckets, 15.0, n=3, window=3.0, bucket_len=5.0)
        assert starts == sorted(starts)
        assert len(set(starts)) == len(starts)

    def test_zero_duration_falls_back(self):
        assert select_top_windows({0: 100}, 0.0, n=3, window=3.0) == [0.0]


class TestNarrowWindow:
    def test_center(self):
        assert narrow_quality_window(6, 3, radius=1) == (2, 4)

    def test_clamped_at_edges(self):
        assert narrow_quality_window(6, 0, radius=1) == (0, 1)
        assert narrow_quality_window(6, 5, radius=1) == (4, 5)

    def test_single_value(self):
        assert narrow_quality_window(1, 0, radius=1) == (0, 0)
