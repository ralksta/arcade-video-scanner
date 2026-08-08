"""Tests for the re-encoded-video pass in `DuplicateDetector`.

The exact-match pass buckets videos by rounded size + duration + resolution, so
a re-encoded copy — same content, different codec/CRF/resolution — never shares
a bucket with its original. This module covers the second pass that catches
them: duration bucketing plus multi-frame perceptual hashes.

No ffmpeg runs here. Frame signatures are pre-seeded into the detector's video
hash cache, which `_video_frame_signature` consults before shelling out; the
cache is stat-validated, so the tmp files it points at have to actually exist.
"""
import os

import pytest

from arcade_scanner.core.duplicate_detector import (
    IMAGEHASH_AVAILABLE,
    DuplicateDetector,
    _UnionFind,
)

pytestmark = pytest.mark.skipif(
    not IMAGEHASH_AVAILABLE, reason="imagehash/Pillow not installed"
)


class FakeVideo:
    """Minimal stand-in for a scanned video entry."""

    def __init__(self, file_path, duration_sec, size_mb=100.0,
                 width=1920, height=1080, codec="h264", bitrate_mbps=8.0):
        self.file_path = file_path
        self.duration_sec = duration_sec
        self.size_mb = size_mb
        self.width = width
        self.height = height
        self.codec = codec
        self.bitrate_mbps = bitrate_mbps
        self.media_type = "video"
        self.thumb = ""


def make_detector(tmp_path, specs):
    """Build a detector plus videos from (duration, signature, **kwargs) specs.

    `signature` is a ':'-joined list of hex frame hashes, or None to model a
    video whose frames could not be extracted.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    detector = DuplicateDetector()
    # Point both caches at tmp so nothing touches the real arcade_data/ dir.
    detector._image_hashes.path = str(tmp_path / ".phash_cache.json")
    detector._video_hashes.path = str(tmp_path / ".vframe_cache.json")

    videos = []
    for i, spec in enumerate(specs):
        duration, signature = spec[0], spec[1]
        kwargs = spec[2] if len(spec) > 2 else {}
        path = tmp_path / f"vid_{i:03d}.mp4"
        path.write_bytes(b"\x00" * (16 + i))  # never decoded
        if signature:
            detector._video_hashes.set(str(path), signature)
        videos.append(FakeVideo(str(path), duration, **kwargs))

    detector._video_hashes.dirty = False  # keep save() a no-op
    return detector, videos


def grouped(groups):
    """Set of frozensets of basenames, one per duplicate group."""
    return {frozenset(os.path.basename(f.path) for f in g.files) for g in groups}


SIG_A = "0000000000000000:1111111111111111:2222222222222222"
SIG_A_NEAR = "0000000000000001:1111111111111111:2222222222222222"  # 1 bit off
SIG_B = "ffffffffffffffff:eeeeeeeeeeeeeeee:dddddddddddddddd"


# --- the gap this pass exists to close ---------------------------------------


def test_reencode_with_different_size_and_codec_is_found(tmp_path):
    """The case the exact pass structurally cannot see.

    Same film, transcoded: half the size, HEVC instead of H.264, 720p instead of
    1080p. Nothing in the exact signature (size + duration + resolution) matches,
    so before this pass the pair was simply invisible.
    """
    detector, videos = make_detector(tmp_path, [
        (3600.0, SIG_A, {"size_mb": 4000.0, "codec": "h264", "width": 1920, "height": 1080}),
        (3600.2, SIG_A_NEAR, {"size_mb": 1200.0, "codec": "hevc", "width": 1280, "height": 720}),
    ])

    exact = detector._find_video_duplicates(videos)
    assert exact == [], "precondition: the exact pass must not find this pair"

    groups = detector._find_reencoded_video_duplicates(videos, set())

    assert grouped(groups) == {frozenset({"vid_000.mp4", "vid_001.mp4"})}
    assert groups[0].match_type == "reencode"
    assert groups[0].confidence < 0.95, "a frame match is weaker evidence than bytes"


def test_savings_and_keep_are_reported_for_reencode_groups(tmp_path):
    detector, videos = make_detector(tmp_path, [
        (600.0, SIG_A, {"size_mb": 1000.0, "bitrate_mbps": 12.0}),
        (600.0, SIG_A_NEAR, {"size_mb": 400.0, "bitrate_mbps": 4.0}),
    ])

    group = detector._find_reencoded_video_duplicates(videos, set())[0]

    assert os.path.basename(group.recommended_keep) == "vid_000.mp4"  # higher bitrate
    assert group.potential_savings_mb == pytest.approx(400.0)


def test_codec_bonus_does_not_recommend_keeping_the_lossy_copy(tmp_path):
    """The HEVC member of a re-encode group is the derivative, not the source.

    `_calculate_video_quality_score` hands modern codecs +20, which is right
    when choosing between byte-identical copies and wrong here: it would
    recommend keeping the shrunken transcode over the original it came from.
    """
    detector, videos = make_detector(tmp_path, [
        (600.0, SIG_A, {"codec": "h264", "width": 1920, "height": 1080,
                        "bitrate_mbps": 8.0, "size_mb": 600.0}),
        (600.0, SIG_A_NEAR, {"codec": "hevc", "width": 1920, "height": 1080,
                             "bitrate_mbps": 2.0, "size_mb": 150.0}),
    ])

    group = detector._find_reencoded_video_duplicates(videos, set())[0]

    assert os.path.basename(group.recommended_keep) == "vid_000.mp4"


def test_codec_bonus_still_applies_to_exact_groups(tmp_path):
    """Only the re-encode path drops the codec term."""
    detector, videos = make_detector(tmp_path, [
        (600.0, None, {"codec": "hevc", "bitrate_mbps": 1.0}),
    ])

    with_bonus = detector._calculate_video_quality_score(videos[0])
    without = detector._calculate_video_quality_score(videos[0], codec_bonus=False)

    assert with_bonus > without


# --- precision ---------------------------------------------------------------


def test_same_duration_different_content_is_not_grouped(tmp_path):
    """Two 22-minute episodes are not duplicates of each other."""
    detector, videos = make_detector(tmp_path, [
        (1320.0, SIG_A),
        (1320.0, SIG_B),
    ])

    assert detector._find_reencoded_video_duplicates(videos, set()) == []


def test_one_matching_frame_is_not_enough(tmp_path):
    """A shared intro must not group a whole series together.

    Frame 1 matches exactly; the later positions do not. Requiring *every*
    sampled position is what separates "same intro" from "same film".
    """
    shared_intro = "0000000000000000:aaaaaaaaaaaaaaaa:bbbbbbbbbbbbbbbb"
    detector, videos = make_detector(tmp_path, [
        (1320.0, SIG_A),
        (1320.0, shared_intro),
    ])

    assert detector._find_reencoded_video_duplicates(videos, set()) == []


def test_durations_beyond_tolerance_are_not_compared(tmp_path):
    """Identical frames but a 30s runtime gap — a trailer, not the film."""
    detector, videos = make_detector(tmp_path, [
        (600.0, SIG_A),
        (630.0, SIG_A),
    ])

    assert detector._find_reencoded_video_duplicates(videos, set()) == []


# --- bookkeeping -------------------------------------------------------------


def test_files_already_grouped_exactly_are_skipped(tmp_path):
    """No file may appear in two groups; the exact pass wins."""
    detector, videos = make_detector(tmp_path, [
        (600.0, SIG_A),
        (600.0, SIG_A),
    ])

    groups = detector._find_reencoded_video_duplicates(
        videos, {videos[0].file_path}
    )

    assert groups == []


def test_videos_without_a_signature_are_ignored(tmp_path):
    """A video whose frames could not be extracted is dropped, not guessed at."""
    detector, videos = make_detector(tmp_path, [
        (600.0, SIG_A),
        (600.0, None),
    ])
    # Duration 0 also means "no seek position to sample", so nothing is written.
    detector._video_hashes.set(videos[1].file_path, "")

    assert detector._find_reencoded_video_duplicates(videos, set()) == []


def test_transitive_reencodes_form_one_group(tmp_path):
    """Three encodes of the same source belong in a single group, not three."""
    detector, videos = make_detector(tmp_path, [
        (600.0, SIG_A),
        (600.5, SIG_A_NEAR),
        (601.0, SIG_A),
    ])

    groups = detector._find_reencoded_video_duplicates(videos, set())

    assert grouped(groups) == {
        frozenset({"vid_000.mp4", "vid_001.mp4", "vid_002.mp4"})
    }


def test_grouping_is_independent_of_input_order(tmp_path):
    """Whether A and B land together must not depend on iteration order."""
    specs = [
        (600.0, SIG_A),
        (600.4, SIG_A_NEAR),
        (600.8, SIG_A),
        (1320.0, SIG_B),
    ]
    detector_a, videos_a = make_detector(tmp_path / "a", specs)
    detector_b, videos_b = make_detector(tmp_path / "b", list(reversed(specs)))

    groups_a = detector_a._find_reencoded_video_duplicates(videos_a, set())
    groups_b = detector_b._find_reencoded_video_duplicates(videos_b, set())

    def by_index(groups):
        return {
            frozenset(os.path.basename(f.path) for f in g.files) for g in groups
        }

    # Same three-member cluster either way, just under mirrored filenames.
    assert len(by_index(groups_a)) == len(by_index(groups_b)) == 1
    assert {len(g) for g in by_index(groups_a)} == {3}
    assert {len(g) for g in by_index(groups_b)} == {3}


def test_frame_hashing_is_skipped_for_unique_durations(tmp_path, monkeypatch):
    """Videos with no duration neighbour never reach ffmpeg.

    Each signature costs three ffmpeg seeks, so hashing a file that provably
    cannot have a twin is pure waste on a large library.
    """
    detector, videos = make_detector(tmp_path, [
        (600.0, SIG_A),
        (600.2, SIG_A_NEAR),
        (9999.0, None),  # unique runtime
    ])

    hashed = []
    original = detector._video_frame_signature

    def spy(video):
        hashed.append(os.path.basename(video.file_path))
        return original(video)

    monkeypatch.setattr(detector, "_video_frame_signature", spy)
    detector._find_reencoded_video_duplicates(videos, set())

    assert "vid_002.mp4" not in hashed


def test_detect_reencodes_flag_disables_the_pass(tmp_path, monkeypatch):
    detector, videos = make_detector(tmp_path, [
        (600.0, SIG_A),
        (600.2, SIG_A_NEAR),
    ])

    called = []
    monkeypatch.setattr(
        detector,
        "_find_reencoded_video_duplicates",
        lambda *a, **kw: called.append(1) or [],
    )

    detector.find_all_duplicates(videos, detect_reencodes=False)
    assert called == []

    detector.find_all_duplicates(videos, detect_reencodes=True)
    assert called == [1]


# --- helpers -----------------------------------------------------------------


def test_signature_length_mismatch_never_matches():
    two_frames = "0000000000000000:1111111111111111"
    assert not DuplicateDetector._signatures_match(SIG_A, two_frames, threshold=64)


def test_malformed_signature_never_matches():
    assert not DuplicateDetector._signatures_match(SIG_A, "zz:zz:zz", threshold=64)


def test_union_find_clusters_are_sorted_and_complete():
    uf = _UnionFind(6)
    uf.union(4, 1)
    uf.union(1, 0)
    uf.union(3, 5)

    assert uf.clusters() == [[0, 1, 4], [2], [3, 5]]
