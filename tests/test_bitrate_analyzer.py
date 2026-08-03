"""Characterization tests for arcade_scanner/core/bitrate_analyzer.py.

analyze_bitrate() shells out to ffprobe three times (stream info, packets,
audio). These tests replace subprocess.run with a dispatcher keyed on the
ffprobe arguments, so no media file and no ffprobe binary are needed.

Production only consumes `max_bitrate_kbps` and `is_variable_bitrate` from the
profile (scripts/video_optimizer.py:957 uses them to cap maxrate and size the
VBR buffer), so those two get the closest attention.
"""
import json
import subprocess
from unittest.mock import patch

import pytest

from arcade_scanner.core.bitrate_analyzer import (
    CODEC_EFFICIENCY,
    BitrateProfile,
    EncodingParams,
    analyze_bitrate,
    calculate_encoding_params,
)

# ---------------------------------------------------------------------------
# ffprobe stubbing
# ---------------------------------------------------------------------------

def make_ffprobe_stub(stream_json=None, packets_json=None, audio_json=None,
                      packets_raises=None):
    """Build a subprocess.run replacement that answers each ffprobe call.

    The three calls are told apart by their arguments, the same way the module
    builds them: '-show_packets' for the packet pass, '-select_streams a:0' for
    audio, everything else is the stream-info pass.
    """
    def fake_run(cmd, **kwargs):
        if "-show_packets" in cmd:
            if packets_raises is not None:
                raise packets_raises
            payload = packets_json
        elif "a:0" in cmd:
            payload = audio_json
        else:
            payload = stream_json

        if payload is None:
            raise subprocess.CalledProcessError(1, cmd)

        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(payload), stderr="")

    return fake_run


def stream_payload(codec="h264", width=1920, height=1080, fps="30000/1001",
                   stream_bitrate=None, duration="60.0", format_bitrate=None):
    stream = {"codec_name": codec, "width": width, "height": height,
              "r_frame_rate": fps}
    if stream_bitrate is not None:
        stream["bit_rate"] = str(stream_bitrate)
    fmt = {"duration": duration}
    if format_bitrate is not None:
        fmt["bit_rate"] = str(format_bitrate)
    return {"streams": [stream], "format": fmt}


def packets_payload(per_second_bytes):
    """One packet per second; per_second_bytes[i] is that second's byte total."""
    return {"packets": [
        {"pts_time": str(float(sec)), "size": str(size), "duration_time": "1.0"}
        for sec, size in enumerate(per_second_bytes)
    ]}


def analyze_with(**kwargs):
    with patch("arcade_scanner.core.bitrate_analyzer.subprocess.run",
               side_effect=make_ffprobe_stub(**kwargs)):
        return analyze_bitrate("/fake/video.mp4")


# ---------------------------------------------------------------------------
# analyze_bitrate — stream metadata
# ---------------------------------------------------------------------------

class TestAnalyzeStreamInfo:
    def test_parses_codec_resolution_and_duration(self):
        profile = analyze_with(stream_json=stream_payload(), packets_json=None,
                               audio_json=None)
        assert profile.source_codec == "h264"
        assert profile.resolution == (1920, 1080)
        assert profile.duration_s == 60.0

    def test_fractional_frame_rate_is_divided(self):
        profile = analyze_with(stream_json=stream_payload(fps="30000/1001"))
        assert profile.fps == pytest.approx(29.97, abs=0.01)

    def test_integer_frame_rate_string(self):
        profile = analyze_with(stream_json=stream_payload(fps="25"))
        assert profile.fps == 25.0

    def test_zero_denominator_frame_rate_does_not_raise(self):
        profile = analyze_with(stream_json=stream_payload(fps="0/0"))
        assert profile.fps == 0

    def test_stream_bitrate_wins_over_format_bitrate(self):
        profile = analyze_with(
            stream_json=stream_payload(stream_bitrate=5_000_000,
                                       format_bitrate=9_000_000)
        )
        assert profile.avg_bitrate_kbps == 5000

    def test_format_bitrate_used_when_stream_has_none(self):
        profile = analyze_with(stream_json=stream_payload(format_bitrate=9_000_000))
        assert profile.avg_bitrate_kbps == 9000

    def test_ffprobe_failure_yields_empty_profile_not_an_exception(self):
        """Every ffprobe call failing must still return a usable profile."""
        profile = analyze_with(stream_json=None, packets_json=None, audio_json=None)
        assert profile.source_codec == "unknown"
        assert profile.avg_bitrate_kbps == 0
        assert profile.resolution == (0, 0)
        assert profile.has_audio is False


# ---------------------------------------------------------------------------
# analyze_bitrate — packet analysis, which drives max/variance
# ---------------------------------------------------------------------------

class TestAnalyzePackets:
    def test_constant_bitrate_has_no_variance(self):
        # 125000 bytes/s = 1 000 000 bits/s = 1000 kbps
        profile = analyze_with(
            stream_json=stream_payload(stream_bitrate=1_000_000),
            packets_json=packets_payload([125000] * 10),
        )
        assert profile.max_bitrate_kbps == pytest.approx(1000)
        assert profile.min_bitrate_kbps == pytest.approx(1000)
        assert profile.bitrate_variance == pytest.approx(0)
        assert profile.is_variable_bitrate is False

    def test_variable_bitrate_is_detected(self):
        # Alternating 500/1500 kbps — swing far beyond the 0.25 ratio
        sizes = [62500, 187500] * 5
        profile = analyze_with(
            stream_json=stream_payload(stream_bitrate=1_000_000),
            packets_json=packets_payload(sizes),
        )
        assert profile.max_bitrate_kbps == pytest.approx(1500)
        assert profile.min_bitrate_kbps == pytest.approx(500)
        assert profile.is_variable_bitrate is True

    def test_packets_supply_average_when_stream_bitrate_missing(self):
        profile = analyze_with(
            stream_json=stream_payload(),  # no stream or format bitrate
            packets_json=packets_payload([125000] * 4),
        )
        assert profile.avg_bitrate_kbps == pytest.approx(1000)

    def test_packets_in_same_second_are_summed(self):
        """Sub-second packets aggregate into one-second windows."""
        packets = {"packets": [
            {"pts_time": "0.0", "size": "50000"},
            {"pts_time": "0.5", "size": "75000"},
            {"pts_time": "1.0", "size": "125000"},
        ]}
        profile = analyze_with(stream_json=stream_payload(), packets_json=packets)
        # Second 0 holds 125000 bytes total, same as second 1 → flat.
        assert profile.max_bitrate_kbps == pytest.approx(1000)
        assert profile.min_bitrate_kbps == pytest.approx(1000)

    def test_unparseable_packets_are_skipped(self):
        packets = {"packets": [
            {"pts_time": "0.0", "size": "125000"},
            {"pts_time": "not-a-number", "size": "999999"},
            {"pts_time": "1.0", "size": "125000"},
        ]}
        profile = analyze_with(stream_json=stream_payload(), packets_json=packets)
        assert profile.max_bitrate_kbps == pytest.approx(1000)

    def test_timeout_falls_back_to_double_the_average(self):
        profile = analyze_with(
            stream_json=stream_payload(stream_bitrate=4_000_000),
            packets_raises=subprocess.TimeoutExpired(cmd="ffprobe", timeout=30),
        )
        assert profile.max_bitrate_kbps == pytest.approx(8000)
        assert profile.bitrate_variance == pytest.approx(1200)

    def test_no_packets_falls_back_to_ratios_of_the_average(self):
        profile = analyze_with(
            stream_json=stream_payload(stream_bitrate=2_000_000),
            packets_json={"packets": []},
        )
        assert profile.max_bitrate_kbps == pytest.approx(3000)  # 1.5x
        assert profile.min_bitrate_kbps == pytest.approx(600)   # 0.3x

    def test_trailing_partial_second_lowers_min_and_raises_variance(self):
        """A short final window is treated as a full second of low bitrate.

        Packet timestamps are bucketed by int(pts_time), so a clip that does not
        end on a second boundary leaves a partial last bucket. That bucket is
        compared against full ones, which drags min_bitrate down and inflates
        the variance. Pinned as current behaviour, not endorsed as correct.
        """
        flat = analyze_with(
            stream_json=stream_payload(stream_bitrate=1_000_000),
            packets_json=packets_payload([125000] * 10),
        )
        # Same constant-bitrate content, but the clip stops a fifth of the way
        # into second 10.
        with_tail = analyze_with(
            stream_json=stream_payload(stream_bitrate=1_000_000),
            packets_json=packets_payload([125000] * 10 + [25000]),
        )

        assert flat.min_bitrate_kbps == pytest.approx(1000)
        assert flat.bitrate_variance == pytest.approx(0)

        assert with_tail.min_bitrate_kbps == pytest.approx(200)
        assert with_tail.bitrate_variance > 200

    def test_a_short_enough_tail_flips_the_vbr_flag(self):
        """Constant-bitrate content can be reported as variable.

        Ten identical seconds plus a very short tail push the variance ratio past
        0.25, so is_variable_bitrate turns True for a source with no actual
        bitrate variation. Production reads exactly this flag to decide the VBR
        buffer size (scripts/video_optimizer.py:961), so such a clip gets a 2.0x
        buffer instead of 1.5x.
        """
        profile = analyze_with(
            stream_json=stream_payload(stream_bitrate=1_000_000),
            packets_json=packets_payload([125000] * 10 + [1250]),
        )

        assert profile.min_bitrate_kbps == pytest.approx(10)
        assert profile.is_variable_bitrate is True


class TestAnalyzeAudio:
    def test_audio_stream_detected_with_bitrate(self):
        profile = analyze_with(
            stream_json=stream_payload(),
            audio_json={"streams": [{"bit_rate": "192000"}]},
        )
        assert profile.has_audio is True
        assert profile.audio_bitrate_kbps == 192

    def test_audio_stream_without_bitrate_still_counts_as_audio(self):
        profile = analyze_with(
            stream_json=stream_payload(),
            audio_json={"streams": [{}]},
        )
        assert profile.has_audio is True
        assert profile.audio_bitrate_kbps == 0

    def test_no_audio_stream(self):
        profile = analyze_with(stream_json=stream_payload(),
                               audio_json={"streams": []})
        assert profile.has_audio is False


# ---------------------------------------------------------------------------
# BitrateProfile properties
# ---------------------------------------------------------------------------

class TestProfileProperties:
    def test_pixel_count(self):
        assert BitrateProfile("/f", resolution=(1920, 1080)).pixel_count == 2073600

    def test_variable_bitrate_needs_a_nonzero_average(self):
        profile = BitrateProfile("/f", avg_bitrate_kbps=0, bitrate_variance=500)
        assert profile.is_variable_bitrate is False

    @pytest.mark.parametrize("variance,expected", [
        (240, False),   # ratio 0.24
        (250, False),   # ratio 0.25 — boundary is exclusive
        (260, True),    # ratio 0.26
    ])
    def test_variable_bitrate_threshold(self, variance, expected):
        profile = BitrateProfile("/f", avg_bitrate_kbps=1000,
                                 bitrate_variance=variance)
        assert profile.is_variable_bitrate is expected


# ---------------------------------------------------------------------------
# calculate_encoding_params
# ---------------------------------------------------------------------------

def flat_profile(codec="h264", avg=5000, mx=8000):
    """A profile with no bitrate variance, so VBR branches stay off."""
    return BitrateProfile("/f", source_codec=codec, avg_bitrate_kbps=avg,
                          max_bitrate_kbps=mx, bitrate_variance=0.0)


class TestTargetCodecDerivation:
    @pytest.mark.parametrize("encoder,expected", [
        ("hevc_nvenc", "hevc"),
        ("h265_something", "hevc"),
        ("libsvtav1", "av1"),
        ("h264_videotoolbox", "h264"),
        ("libx264", "h264"),
        ("totally_unknown", "h264"),  # default
    ])
    def test_codec_derived_from_encoder_name(self, encoder, expected):
        params = calculate_encoding_params(flat_profile(), encoder, [])
        assert params.target_codec == expected

    def test_explicit_target_codec_overrides_the_encoder_name(self):
        params = calculate_encoding_params(flat_profile(), "hevc_nvenc", [],
                                           target_codec="av1")
        assert params.target_codec == "av1"


class TestBitrateMath:
    def test_more_efficient_target_codec_lowers_the_target(self):
        # h264 → hevc is 0.65, then 5% headroom
        params = calculate_encoding_params(flat_profile(), "hevc_nvenc", [])
        assert params.codec_efficiency_ratio == 0.65
        assert params.target_bitrate_kbps == pytest.approx(5000 * 0.65 * 0.95)

    def test_unknown_codec_pair_defaults_to_ratio_one(self):
        params = calculate_encoding_params(flat_profile(codec="prores"),
                                           "libx264", [])
        assert params.codec_efficiency_ratio == 1.0

    def test_headroom_is_applied_to_the_target(self):
        params = calculate_encoding_params(flat_profile(), "hevc_nvenc", [],
                                           headroom_pct=0.20)
        assert params.target_bitrate_kbps == pytest.approx(5000 * 0.65 * 0.80)

    def test_source_codec_matching_is_case_insensitive(self):
        params = calculate_encoding_params(flat_profile(codec="H264"),
                                           "hevc_nvenc", [])
        assert params.codec_efficiency_ratio == 0.65

    def test_constant_bitrate_source_gets_the_tighter_peak_margin(self):
        params = calculate_encoding_params(flat_profile(), "hevc_nvenc", [])
        assert params.max_bitrate_kbps == pytest.approx(8000 * 0.65 * 0.90)
        assert params.bufsize_kbps == pytest.approx(params.max_bitrate_kbps * 1.5)

    def test_variable_bitrate_source_gets_a_looser_peak_and_bigger_buffer(self):
        profile = BitrateProfile("/f", source_codec="h264", avg_bitrate_kbps=5000,
                                 max_bitrate_kbps=8000, bitrate_variance=2000)
        params = calculate_encoding_params(profile, "hevc_nvenc", [])
        assert params.max_bitrate_kbps == pytest.approx(8000 * 0.65 * 0.95)
        assert params.bufsize_kbps == pytest.approx(params.max_bitrate_kbps * 2.0)

    def test_maxrate_never_falls_below_target(self):
        # Source peak barely above average — the 1.2x rule must lift maxrate.
        profile = flat_profile(codec="prores", avg=5000, mx=5000)
        params = calculate_encoding_params(profile, "libx264", [])
        assert params.max_bitrate_kbps >= params.target_bitrate_kbps

    def test_same_efficiency_codec_is_capped_at_source(self):
        """A ratio >= 1.0 must never produce a bitrate above the source."""
        profile = flat_profile(codec="hevc", avg=5000, mx=8000)  # hevc → hevc
        params = calculate_encoding_params(profile, "hevc_nvenc", [])
        assert params.codec_efficiency_ratio == 1.0
        assert params.target_bitrate_kbps <= 5000
        assert params.max_bitrate_kbps <= 8000

    def test_less_efficient_codec_is_also_capped(self):
        # hevc → h264 has ratio 1.40, which would otherwise inflate the target.
        profile = flat_profile(codec="hevc", avg=5000, mx=8000)
        params = calculate_encoding_params(profile, "libx264", [])
        assert params.codec_efficiency_ratio == 1.40
        assert params.target_bitrate_kbps == 5000
        assert params.max_bitrate_kbps == 8000

    def test_floors_apply_to_tiny_sources(self):
        profile = flat_profile(codec="h264", avg=50, mx=80)
        params = calculate_encoding_params(profile, "hevc_nvenc", [])
        assert params.target_bitrate_kbps == 200
        assert params.max_bitrate_kbps == 300
        assert params.bufsize_kbps == 500

    def test_zero_bitrate_source_still_yields_floors(self):
        params = calculate_encoding_params(BitrateProfile("/f"), "libx264", [])
        assert params.target_bitrate_kbps == 200
        assert params.max_bitrate_kbps == 300

    def test_encoder_options_are_copied_not_aliased(self):
        opts = ["-preset", "slow"]
        params = calculate_encoding_params(flat_profile(), "libx264", opts)
        opts.append("-tune")
        assert params.encoder_options == ["-preset", "slow"]

    def test_every_efficiency_table_entry_is_reachable(self):
        for (src, tgt), ratio in CODEC_EFFICIENCY.items():
            params = calculate_encoding_params(
                flat_profile(codec=src), "irrelevant", [], target_codec=tgt
            )
            assert params.codec_efficiency_ratio == ratio, f"{src}->{tgt}"


# ---------------------------------------------------------------------------
# EncodingParams.as_ffmpeg_args
# ---------------------------------------------------------------------------

class TestFfmpegArgs:
    def _params(self, encoder, **kw):
        return EncodingParams(
            encoder_name=encoder,
            target_bitrate_kbps=kw.get("target", 3000),
            max_bitrate_kbps=kw.get("maxrate", 5000),
            bufsize_kbps=kw.get("bufsize", 7500),
            encoder_options=kw.get("options", []),
        )

    def test_encoder_and_options_come_first(self):
        args = self._params("libx264", options=["-preset", "slow"]).as_ffmpeg_args()
        assert args[:4] == ["-c:v", "libx264", "-preset", "slow"]

    def test_libx264_uses_crf_and_no_average_bitrate(self):
        args = self._params("libx264").as_ffmpeg_args()
        assert "-crf" in args
        assert "-b:v" not in args
        assert "-maxrate" in args and "-bufsize" in args

    def test_nvenc_uses_constrained_quality_mode(self):
        args = self._params("hevc_nvenc").as_ffmpeg_args()
        assert args[args.index("-rc") + 1] == "vbr"
        assert args[args.index("-cq") + 1] == "23"
        assert args[args.index("-b:v") + 1] == "3000k"

    @pytest.mark.parametrize("encoder", [
        "h264_videotoolbox", "hevc_videotoolbox", "h264_qsv", "hevc_qsv",
        "h264_vaapi", "hevc_vaapi", "some_unknown_encoder",
    ])
    def test_bitrate_encoders_emit_plain_abr_flags(self, encoder):
        args = self._params(encoder).as_ffmpeg_args()
        assert args[args.index("-b:v") + 1] == "3000k"
        assert args[args.index("-maxrate") + 1] == "5000k"
        assert args[args.index("-bufsize") + 1] == "7500k"
        assert "-crf" not in args

    def test_bitrates_are_truncated_to_whole_kbps(self):
        args = self._params("h264_qsv", target=2999.7, maxrate=4999.9,
                            bufsize=7499.5).as_ffmpeg_args()
        assert args[args.index("-b:v") + 1] == "2999k"
        assert args[args.index("-maxrate") + 1] == "4999k"

    @pytest.mark.parametrize("target,crf", [
        (9000, 18), (8001, 18),
        (8000, 20), (4001, 20),
        (4000, 23), (2001, 23),
        (2000, 26), (1001, 26),
        (1000, 28), (501, 28),
        (500, 30), (100, 30),
    ])
    def test_crf_thresholds(self, target, crf):
        args = self._params("libx264", target=target).as_ffmpeg_args()
        assert args[args.index("-crf") + 1] == str(crf)

    def test_caller_supplied_crf_is_overridden_by_the_estimate(self):
        """libx264 options carrying -crf get a second -crf appended.

        The module's own CLI does exactly this (main() sets
        ["-preset", "ultrafast", "-crf", "28"] for libx264), and ffmpeg honours
        the last occurrence — so the caller's value silently loses. Pinned as
        current behaviour.
        """
        args = self._params("libx264", target=9000,
                            options=["-crf", "28"]).as_ffmpeg_args()
        assert args.count("-crf") == 2
        assert args[-5:-4] != ["28"]
        assert args[args.index("-crf", args.index("-crf") + 1) + 1] == "18"


class TestSummary:
    def test_summary_renders_without_raising(self):
        profile = flat_profile()
        params = calculate_encoding_params(profile, "hevc_nvenc", [])
        text = params.summary(profile)
        assert "Bitrate Analysis Summary" in text
        assert "hevc" in text
