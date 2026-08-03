"""Characterization tests for arcade_scanner/scanner/media_probe.py.

MediaProbe spawns ffprobe via asyncio.create_subprocess_exec. That call is
replaced with a fake process here, so no ffprobe binary and no media file are
involved. There is no pytest-asyncio in this project, so coroutines are driven
with asyncio.run().
"""
import asyncio
import json
from unittest.mock import MagicMock, patch

import pytest

from arcade_scanner.scanner.media_probe import MediaProbe

# ---------------------------------------------------------------------------
# Fake ffprobe process
# ---------------------------------------------------------------------------

class FakeProcess:
    def __init__(self, stdout=b"", stderr=b"", returncode=0, hang=False):
        self._stdout = stdout
        self._stderr = stderr
        # asyncio reports returncode None while the child is still running.
        self.returncode = None if hang else returncode
        self._hang = hang
        self.kill_calls = 0
        self.wait_calls = 0

    async def communicate(self):
        if self._hang:
            await asyncio.sleep(3600)
        return self._stdout, self._stderr

    def kill(self):
        self.kill_calls += 1

    async def wait(self):
        self.wait_calls += 1


def run_probe(payload=None, *, returncode=0, raw_stdout=None, ffprobe_path="",
              process=None, capture=None):
    """Run _run_ffprobe against a fake process; returns its result."""
    stdout = raw_stdout if raw_stdout is not None else json.dumps(payload or {}).encode()
    proc = process or FakeProcess(stdout=stdout, returncode=returncode)

    cfg = MagicMock()
    cfg.settings.ffprobe_path = ffprobe_path

    async def fake_exec(*cmd, **kwargs):
        if capture is not None:
            capture.append(list(cmd))
        return proc

    with patch("arcade_scanner.scanner.media_probe.config", cfg), \
         patch("arcade_scanner.scanner.media_probe.asyncio.create_subprocess_exec",
               side_effect=fake_exec):
        return asyncio.run(MediaProbe()._run_ffprobe("/fake/clip.mp4"))


def run_metadata(payload, ffprobe_path=""):
    """Run get_metadata against a fake ffprobe returning `payload`."""
    proc = FakeProcess(stdout=json.dumps(payload).encode(), returncode=0)

    cfg = MagicMock()
    cfg.settings.ffprobe_path = ffprobe_path

    async def fake_exec(*cmd, **kwargs):
        return proc

    with patch("arcade_scanner.scanner.media_probe.config", cfg), \
         patch("arcade_scanner.scanner.media_probe.asyncio.create_subprocess_exec",
               side_effect=fake_exec):
        return asyncio.run(MediaProbe().get_metadata("/fake/clip.mp4"))


def probe_payload(video=None, audio=None, fmt=None):
    streams = []
    if video is not None:
        streams.append({"codec_type": "video", **video})
    if audio is not None:
        streams.append({"codec_type": "audio", **audio})
    return {"streams": streams, "format": fmt if fmt is not None else {}}


VIDEO = {"codec_name": "h264", "width": 1920, "height": 1080,
         "profile": "High", "level": 41, "pix_fmt": "yuv420p",
         "avg_frame_rate": "30000/1001"}
AUDIO = {"codec_name": "aac", "channels": 2}
FORMAT = {"duration": "120.5", "bit_rate": "5000000",
          "size": "78643200", "format_name": "mov,mp4,m4a"}


# ---------------------------------------------------------------------------
# _run_ffprobe
# ---------------------------------------------------------------------------

class TestRunFfprobe:
    def test_returns_parsed_json(self):
        assert run_probe({"streams": [], "format": {}}) == {"streams": [], "format": {}}

    def test_uses_configured_ffprobe_path(self):
        capture = []
        run_probe({}, ffprobe_path="/opt/bin/ffprobe", capture=capture)
        assert capture[0][0] == "/opt/bin/ffprobe"

    def test_falls_back_to_bare_ffprobe(self):
        capture = []
        run_probe({}, ffprobe_path="", capture=capture)
        assert capture[0][0] == "ffprobe"

    def test_target_file_is_the_last_argument(self):
        capture = []
        run_probe({}, capture=capture)
        assert capture[0][-1] == "/fake/clip.mp4"
        assert "-of" in capture[0] and "json" in capture[0]

    def test_nonzero_exit_yields_empty_dict(self):
        assert run_probe({"streams": [{"codec_type": "video"}]}, returncode=1) == {}

    def test_malformed_json_yields_empty_dict(self):
        assert run_probe(raw_stdout=b"not json at all") == {}

    def test_spawn_failure_yields_empty_dict(self):
        cfg = MagicMock()
        cfg.settings.ffprobe_path = ""

        async def boom(*cmd, **kwargs):
            raise FileNotFoundError("ffprobe missing")

        with patch("arcade_scanner.scanner.media_probe.config", cfg), \
             patch("arcade_scanner.scanner.media_probe.asyncio.create_subprocess_exec",
                   side_effect=boom):
            assert asyncio.run(MediaProbe()._run_ffprobe("/fake/clip.mp4")) == {}


class TestFfprobeTimeout:
    def test_a_hung_ffprobe_is_killed(self):
        """A probe that exceeds its timeout must not leave the child running.

        asyncio.wait_for only cancels the communicate() coroutine; the spawned
        process keeps going unless it is killed explicitly. On a large library
        that would strand one ffprobe per hung file.
        """
        proc = FakeProcess(hang=True)
        cfg = MagicMock()
        cfg.settings.ffprobe_path = ""

        async def fake_exec(*cmd, **kwargs):
            return proc

        real_wait_for = asyncio.wait_for

        async def instant_timeout(awaitable, timeout=None):
            # Give the real machinery a moment, then time out deterministically
            # instead of waiting out the module's 20 second budget.
            return await real_wait_for(awaitable, timeout=0.05)

        with patch("arcade_scanner.scanner.media_probe.config", cfg), \
             patch("arcade_scanner.scanner.media_probe.asyncio.create_subprocess_exec",
                   side_effect=fake_exec), \
             patch("arcade_scanner.scanner.media_probe.asyncio.wait_for",
                   side_effect=instant_timeout):
            result = asyncio.run(MediaProbe()._run_ffprobe("/fake/clip.mp4"))

        assert result == {}
        assert proc.kill_calls == 1, "timed-out ffprobe process was never killed"
        assert proc.wait_calls == 1, "killed process was never reaped"

    def test_a_process_that_already_exited_is_not_killed_again(self):
        """A normal failure path must not call kill() on a finished process."""
        proc = FakeProcess(stdout=b"not json", returncode=0)
        cfg = MagicMock()
        cfg.settings.ffprobe_path = ""

        async def fake_exec(*cmd, **kwargs):
            return proc

        with patch("arcade_scanner.scanner.media_probe.config", cfg), \
             patch("arcade_scanner.scanner.media_probe.asyncio.create_subprocess_exec",
                   side_effect=fake_exec):
            result = asyncio.run(MediaProbe()._run_ffprobe("/fake/clip.mp4"))

        assert result == {}
        assert proc.kill_calls == 0


# ---------------------------------------------------------------------------
# get_metadata — happy path
# ---------------------------------------------------------------------------

class TestMetadataHappyPath:
    def test_full_payload_populates_every_field(self):
        entry = run_metadata(probe_payload(VIDEO, AUDIO, FORMAT))

        assert entry is not None
        assert entry.file_path == "/fake/clip.mp4"
        assert entry.codec == "h264"
        assert entry.width == 1920
        assert entry.height == 1080
        assert entry.profile == "High"
        assert entry.pixel_format == "yuv420p"
        assert entry.level == 41.0
        assert entry.audio_codec == "aac"
        assert entry.audio_channels == 2
        assert entry.container_format == "mov,mp4,m4a"
        assert entry.status == "OK"

    def test_size_is_converted_to_megabytes_and_rounded(self):
        entry = run_metadata(probe_payload(VIDEO, AUDIO, FORMAT))
        assert entry.size_mb == 75.0  # 78643200 bytes

    def test_bitrate_is_converted_to_megabits_and_rounded(self):
        entry = run_metadata(probe_payload(VIDEO, AUDIO, FORMAT))
        assert entry.bitrate_mbps == 5.0

    def test_duration_is_rounded_to_two_places(self):
        entry = run_metadata(probe_payload(VIDEO, AUDIO, {"duration": "12.3456"}))
        assert entry.duration_sec == 12.35

    def test_first_video_stream_wins(self):
        payload = {"streams": [
            {"codec_type": "audio", "codec_name": "aac", "channels": 6},
            {"codec_type": "video", "codec_name": "hevc", "width": 3840, "height": 2160},
            {"codec_type": "video", "codec_name": "h264", "width": 640, "height": 480},
        ], "format": {}}
        entry = run_metadata(payload)
        assert entry.codec == "hevc"
        assert entry.width == 3840
        assert entry.audio_channels == 6


class TestFrameRate:
    def test_fractional_frame_rate(self):
        entry = run_metadata(probe_payload({**VIDEO, "avg_frame_rate": "30000/1001"},
                                           AUDIO, FORMAT))
        assert entry.frame_rate == 29.97

    def test_integer_frame_rate_string(self):
        entry = run_metadata(probe_payload({**VIDEO, "avg_frame_rate": "25"},
                                           AUDIO, FORMAT))
        assert entry.frame_rate == 25.0

    def test_zero_denominator_yields_zero(self):
        entry = run_metadata(probe_payload({**VIDEO, "avg_frame_rate": "0/0"},
                                           AUDIO, FORMAT))
        assert entry.frame_rate == 0.0

    def test_unparseable_frame_rate_yields_zero(self):
        entry = run_metadata(probe_payload({**VIDEO, "avg_frame_rate": "N/A"},
                                           AUDIO, FORMAT))
        assert entry.frame_rate == 0.0

    def test_missing_frame_rate_yields_zero(self):
        video = {k: v for k, v in VIDEO.items() if k != "avg_frame_rate"}
        entry = run_metadata(probe_payload(video, AUDIO, FORMAT))
        assert entry.frame_rate == 0.0


class TestLevel:
    def test_numeric_level(self):
        entry = run_metadata(probe_payload({**VIDEO, "level": 51}, AUDIO, FORMAT))
        assert entry.level == 51.0

    def test_string_level_is_parsed(self):
        entry = run_metadata(probe_payload({**VIDEO, "level": "40"}, AUDIO, FORMAT))
        assert entry.level == 40.0

    def test_unparseable_level_falls_back_to_zero(self):
        entry = run_metadata(probe_payload({**VIDEO, "level": "unknown"}, AUDIO, FORMAT))
        assert entry.level == 0.0


# ---------------------------------------------------------------------------
# get_metadata — degraded and failing inputs
# ---------------------------------------------------------------------------

class TestMetadataDegradedInput:
    def test_no_streams_key_returns_none(self):
        assert run_metadata({"format": FORMAT}) is None

    def test_empty_stream_list_returns_none(self):
        assert run_metadata({"streams": [], "format": FORMAT}) is None

    def test_empty_probe_result_returns_none(self):
        assert run_metadata({}) is None

    def test_audio_only_file_still_produces_an_entry(self):
        """No video stream means zeroed video fields, not a dropped file."""
        entry = run_metadata(probe_payload(None, AUDIO, FORMAT))
        assert entry is not None
        assert entry.codec == "unknown"
        assert entry.width == 0
        assert entry.height == 0
        assert entry.audio_codec == "aac"

    def test_video_without_audio_gets_unknown_audio_codec(self):
        entry = run_metadata(probe_payload(VIDEO, None, FORMAT))
        assert entry.audio_codec == "unknown"
        assert entry.audio_channels == 0

    def test_missing_format_block_falls_back_to_zeros(self):
        entry = run_metadata(probe_payload(VIDEO, AUDIO, {}))
        assert entry.size_mb == 0.0
        assert entry.duration_sec == 0.0
        assert entry.bitrate_mbps == 0.0
        assert entry.container_format == "unknown"

    @pytest.mark.parametrize("field,attribute", [
        ("duration", "duration_sec"),
        ("bit_rate", "bitrate_mbps"),
        ("size", "size_mb"),
    ])
    def test_non_numeric_format_field_zeroes_only_that_field(self, field, attribute):
        """ffprobe writes "N/A" for values it cannot determine.

        One such field must not cost the whole file: a media inventory that
        silently omits a video is worse than one that shows it with a zeroed
        duration.
        """
        fmt = {**FORMAT, field: "N/A"}
        entry = run_metadata(probe_payload(VIDEO, AUDIO, fmt))

        assert entry is not None, f'"N/A" in {field} dropped the file entirely'
        assert getattr(entry, attribute) == 0.0
        # The rest of the metadata survives.
        assert entry.codec == "h264"
        assert entry.width == 1920

    def test_non_numeric_dimensions_zero_only_those_fields(self):
        payload = probe_payload({**VIDEO, "width": "N/A", "height": "N/A"},
                                AUDIO, FORMAT)
        entry = run_metadata(payload)

        assert entry is not None
        assert entry.width == 0
        assert entry.height == 0
        assert entry.codec == "h264"
        assert entry.duration_sec == 120.5

    def test_non_numeric_audio_channels_zeroes_only_that_field(self):
        entry = run_metadata(probe_payload(VIDEO, {**AUDIO, "channels": "N/A"},
                                           FORMAT))
        assert entry is not None
        assert entry.audio_channels == 0
        assert entry.audio_codec == "aac"

    def test_float_valued_dimensions_are_accepted(self):
        entry = run_metadata(probe_payload({**VIDEO, "width": "1920.0"},
                                           AUDIO, FORMAT))
        assert entry is not None
        assert entry.width == 1920
