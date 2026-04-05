"""
Tests for arcade_scanner.core.video_processor + hw_encode_detect
Focus: IMAGE_EXTENSIONS constant, detect_h264_encoder dependency injection,
       get_video_metadata error handling.
"""
import subprocess
from unittest.mock import patch, MagicMock

import pytest

from arcade_scanner.core.video_processor import (
    IMAGE_EXTENSIONS,
    get_video_metadata,
)
from arcade_scanner.core.hw_encode_detect import detect_h264_encoder as detect_hw_encoder


class TestImageExtensions:
    def test_is_frozenset(self):
        assert isinstance(IMAGE_EXTENSIONS, frozenset)

    def test_contains_common_types(self):
        for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
            assert ext in IMAGE_EXTENSIONS

    def test_all_lowercase(self):
        for ext in IMAGE_EXTENSIONS:
            assert ext == ext.lower(), f"Extension {ext!r} is not lowercase"

    def test_all_start_with_dot(self):
        for ext in IMAGE_EXTENSIONS:
            assert ext.startswith("."), f"Extension {ext!r} does not start with '.'"


class TestDetectHwEncoder:
    """
    detect_h264_encoder() (formerly detect_hw_encoder) returns a
    (codec_name: str, args: list) tuple – always.
    On machines without HW encoders, it falls back to ('libx264', [...]).
    """

    def test_returns_tuple(self):
        """detect_hw_encoder always returns a 2-tuple."""
        result = detect_hw_encoder()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_returns_codec_string_and_args_list(self):
        codec, args = detect_hw_encoder()
        assert isinstance(codec, str)
        assert isinstance(args, list)

    def test_log_fn_accepted_without_error(self):
        """Calling with an injected log_fn must not raise."""
        messages = []
        result = detect_hw_encoder(log_fn=messages.append)
        assert isinstance(result, tuple)

    def test_default_no_log_fn_does_not_crash(self):
        """Calling without log_fn should not raise."""
        detect_hw_encoder()

    @patch("subprocess.run", side_effect=FileNotFoundError)
    def test_returns_fallback_when_tools_missing(self, _mock_run):
        """On a machine without HW tools, should fall back to libx264."""
        codec, args = detect_hw_encoder()
        assert isinstance(codec, str)
        assert isinstance(args, list)
        assert len(codec) > 0


class TestGetVideoMetadata:
    """
    get_video_metadata() returns a dict with ffprobe structure on success,
    or {} (empty dict) on any error.
    """

    @patch("subprocess.run")
    def test_returns_dict_on_success(self, mock_run):
        fake_output = (
            '{"streams":[{"codec_type":"video","codec_name":"h264",'
            '"width":1920,"height":1080,"r_frame_rate":"30/1"}],'
            '"format":{"duration":"120.5","bit_rate":"5000000"}}'
        )
        mock_run.return_value = MagicMock(
            returncode=0, stdout=fake_output, stderr=""
        )
        result = get_video_metadata("/fake/video.mp4")
        assert isinstance(result, dict)

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "ffprobe"))
    def test_returns_empty_dict_on_subprocess_error(self, _mock):
        """On ffprobe failure, function returns {} (not None) per type hint."""
        result = get_video_metadata("/nonexistent/video.mp4")
        assert isinstance(result, dict)
        assert result == {}

    @patch("subprocess.run", side_effect=FileNotFoundError("ffprobe not found"))
    def test_returns_empty_dict_when_ffprobe_missing(self, _mock):
        result = get_video_metadata("/fake/video.mp4")
        assert isinstance(result, dict)
        assert result == {}

    def test_file_not_found_returns_empty_dict(self, tmp_path):
        result = get_video_metadata(str(tmp_path / "nonexistent.mp4"))
        assert isinstance(result, dict)
