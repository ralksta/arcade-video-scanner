"""Characterization tests for arcade_scanner/scanner/video_inspector.py.

VideoInspector is the adapter between the legacy VideoEntry that MediaProbe
returns and the MediaAsset the scanner stores. It sits on the live scan path
(scanner/manager.py:196), so the mapping is worth pinning field by field.

The probe is stubbed; no ffprobe and no media file are involved.
"""
import asyncio

import pytest

from arcade_scanner.models.media_asset import MediaType
from arcade_scanner.models.video_entry import VideoEntry
from arcade_scanner.scanner.video_inspector import VideoInspector


class StubProbe:
    """Stands in for MediaProbe; returns a canned VideoEntry (or None)."""

    def __init__(self, entry=None):
        self.entry = entry
        self.calls = []

    async def get_metadata(self, filepath):
        self.calls.append(filepath)
        return self.entry


def full_entry(**overrides):
    fields = dict(
        FilePath="/media/clip.mp4",
        Size_MB=75.0,
        Bitrate_Mbps=5.0,
        Status="OK",
        codec="h264",
        Duration_Sec=120.5,
        Width=1920,
        Height=1080,
        AudioCodec="aac",
        AudioChannels=2,
        Container="mov,mp4,m4a",
        Profile="High",
        Level=41.0,
        PixelFormat="yuv420p",
        FrameRate=29.97,
    )
    fields.update(overrides)
    return VideoEntry(**fields)


def inspect(entry, filepath="/media/clip.mp4"):
    inspector = VideoInspector(StubProbe(entry))
    return asyncio.run(inspector.inspect(filepath))


# ---------------------------------------------------------------------------
# can_handle
# ---------------------------------------------------------------------------

class TestCanHandle:
    @pytest.mark.parametrize("name", [
        "a.mp4", "a.mkv", "a.avi", "a.mov", "a.m4v",
        "a.wmv", "a.flv", "a.webm", "a.ts",
    ])
    def test_accepts_every_video_extension(self, name):
        assert VideoInspector(StubProbe()).can_handle(f"/media/{name}") is True

    def test_extension_check_is_case_insensitive(self):
        assert VideoInspector(StubProbe()).can_handle("/media/CLIP.MP4") is True

    @pytest.mark.parametrize("name", ["a.jpg", "a.png", "a.txt", "a.mp3", "noext"])
    def test_rejects_non_video_files(self, name):
        assert VideoInspector(StubProbe()).can_handle(f"/media/{name}") is False

    def test_extension_must_be_at_the_end(self):
        """A path merely containing '.mp4' mid-name is not a video."""
        assert VideoInspector(StubProbe()).can_handle("/media/.mp4_notes.txt") is False


# ---------------------------------------------------------------------------
# inspect — mapping VideoEntry onto MediaAsset
# ---------------------------------------------------------------------------

class TestInspectMapping:
    def test_probe_receives_the_requested_path(self):
        probe = VideoInspector(StubProbe(full_entry()))
        asyncio.run(probe.inspect("/media/other.mp4"))
        assert probe.probe.calls == ["/media/other.mp4"]

    def test_failed_probe_yields_none(self):
        assert inspect(None) is None

    def test_asset_identity_and_type(self):
        asset = inspect(full_entry())
        assert asset.file_path == "/media/clip.mp4"
        assert asset.size_mb == 75.0
        assert asset.media_type == MediaType.VIDEO
        assert asset.image_metadata is None

    def test_every_video_metadata_field_is_carried_over(self):
        meta = inspect(full_entry()).video_metadata
        assert meta.codec == "h264"
        assert meta.duration_sec == 120.5
        assert meta.bitrate_mbps == 5.0
        assert meta.width == 1920
        assert meta.height == 1080
        assert meta.audio_codec == "aac"
        assert meta.audio_channels == 2
        assert meta.container == "mov,mp4,m4a"
        assert meta.profile == "High"
        assert meta.level == 41.0
        assert meta.pixel_format == "yuv420p"
        assert meta.frame_rate == 29.97

    def test_status_is_preserved(self):
        assert inspect(full_entry(Status="HIGH")).status == "HIGH"

    def test_user_state_is_carried_over(self):
        entry = full_entry()
        entry.favorite = True
        entry.vaulted = True
        entry.tags = ["holiday", "4k"]
        entry.thumb = "thumb_abc.jpg"

        asset = inspect(entry)

        assert asset.favorite is True
        assert asset.vaulted is True
        assert asset.tags == ["holiday", "4k"]
        assert asset.thumb == "thumb_abc.jpg"

    def test_tags_are_not_shared_with_the_source_entry(self):
        """Mutating the asset's tags must not reach back into the probe result."""
        entry = full_entry()
        entry.tags = ["original"]

        asset = inspect(entry)
        asset.tags.append("added-later")

        assert entry.tags == ["original"]

    def test_mtime_is_carried_over(self):
        entry = full_entry()
        entry.mtime = 1700000000
        assert inspect(entry).mtime == 1700000000

    def test_unset_imported_at_stays_zero(self):
        """The adapter forwards 0 rather than letting MediaAsset stamp 'now'.

        MediaAsset defaults imported_at to the current time, but the inspector
        passes the legacy value explicitly, so a fresh probe yields 0.
        scanner/manager.py:222 relies on that, filling in the timestamp itself
        only when it is still 0 — which is what preserves the original import
        date for a re-scanned file.
        """
        assert inspect(full_entry()).imported_at == 0

    def test_explicit_imported_at_is_preserved(self):
        entry = full_entry()
        entry.imported_at = 1600000000
        assert inspect(entry).imported_at == 1600000000


class TestInspectDefaults:
    def test_blank_codec_becomes_unknown(self):
        assert inspect(full_entry(codec="")).video_metadata.codec == "unknown"

    def test_blank_audio_codec_becomes_unknown(self):
        assert inspect(full_entry(AudioCodec="")).video_metadata.audio_codec == "unknown"

    def test_blank_container_becomes_unknown(self):
        assert inspect(full_entry(Container="")).video_metadata.container == "unknown"

    def test_zeroed_numeric_fields_stay_zero(self):
        meta = inspect(full_entry(
            Duration_Sec=0.0, Bitrate_Mbps=0.0, Width=0, Height=0,
            AudioChannels=0, Level=0.0, FrameRate=0.0,
        )).video_metadata
        assert meta.duration_sec == 0.0
        assert meta.bitrate_mbps == 0.0
        assert meta.width == 0
        assert meta.height == 0
        assert meta.audio_channels == 0
        assert meta.level == 0.0
        assert meta.frame_rate == 0.0

    def test_none_valued_optionals_fall_back_to_defaults(self):
        """VideoEntry declares most metadata Optional, so None is representable."""
        entry = full_entry()
        entry.codec = None
        entry.width = None
        entry.frame_rate = None

        meta = inspect(entry).video_metadata

        assert meta.codec == "unknown"
        assert meta.width == 0
        assert meta.frame_rate == 0.0


class TestLegacyCompatibilityView:
    """manager.py reads entry.bitrate_mbps straight off the asset (line 211)."""

    def test_flattened_properties_read_through_to_video_metadata(self):
        asset = inspect(full_entry())
        assert asset.bitrate_mbps == 5.0
        assert asset.duration_sec == 120.5
        assert asset.codec == "h264"
        assert asset.Width == 1920
        assert asset.Height == 1080

    def test_dict_export_includes_the_flattened_fields(self):
        """MediaAsset.dict() flattens video metadata for the frontend shape.

        Nothing in production calls it: every serialisation path uses
        `model_dump(by_alias=True)`, which does *not* run this override, and the
        store converts assets to VideoEntry before they are ever dumped. Pinned
        because the method exists — see the note in the night log about it
        overriding a Pydantic method that V3 removes.
        """
        with pytest.warns(DeprecationWarning):
            exported = inspect(full_entry()).dict()

        assert exported["codec"] == "h264"
        assert exported["Duration_Sec"] == 120.5
        assert exported["Bitrate_Mbps"] == 5.0
        assert exported["Width"] == 1920
        assert exported["Height"] == 1080
