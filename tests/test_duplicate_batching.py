"""Tests for how the duplicate scan splits work across runs.

The scan used to slice the image list per batch and compare only within the
slice, which made a pair straddling a boundary permanently unfindable. These
tests pin down the replacement rule: a run caps how many *new hashes* it
computes, never which images may be compared with which.
"""
import os

import pytest

from arcade_scanner.core.duplicate_detector import IMAGEHASH_AVAILABLE, DuplicateDetector

pytestmark = pytest.mark.skipif(
    not IMAGEHASH_AVAILABLE, reason="imagehash/Pillow not installed"
)


class FakeImage:
    def __init__(self, file_path, size_mb=1.0, width=1920, height=1080):
        self.file_path = file_path
        self.size_mb = size_mb
        self.width = width
        self.height = height
        self.media_type = "image"
        self.thumb = ""


def make_images(tmp_path, hashes, detector=None):
    """Create tmp files; seed the detector's cache for non-None hashes.

    A None hash models an image that has not been hashed yet — the file exists
    but nothing in the cache describes it, so it costs budget to process.
    """
    detector = detector or DuplicateDetector()
    detector._image_hashes.path = str(tmp_path / ".phash_cache.json")

    images = []
    for i, hash_str in enumerate(hashes):
        path = tmp_path / f"img_{i:03d}.jpg"
        path.write_bytes(b"\xff\xd8\xff\xd9")  # not decodable as a real JPEG
        if hash_str is not None:
            detector._image_hashes.set(str(path), hash_str)
        images.append(FakeImage(str(path)))

    detector._image_hashes.dirty = False  # keep save() a no-op
    return detector, images


def grouped(groups):
    return {frozenset(os.path.basename(f.path) for f in g.files) for g in groups}


DUP = "f0f0f0f0f0f0f0f0"


def test_duplicates_across_a_batch_boundary_are_found(tmp_path):
    """The bug this module exists for.

    With the old `all_images[offset:offset + size]` slicing and a batch size of
    2, these two copies land in different batches and are never compared —
    not in batch 1, not in batch 2, not ever. Comparison must not be scoped to
    a batch.
    """
    detector, images = make_images(
        tmp_path, [DUP, "0123456789abcdef", DUP, "1122334455667788"]
    )

    groups, _ = detector.find_all_duplicates(images, batch_size=2)

    assert grouped(groups) == {frozenset({"img_000.jpg", "img_002.jpg"})}


def test_earlier_results_are_not_lost_by_a_later_run(tmp_path):
    """Each run returns the complete picture, not just its own slice.

    The old code overwrote the group cache with each run's slice-local result,
    so completing batch 2 discarded everything batch 1 had found.
    """
    detector, images = make_images(tmp_path, [DUP, DUP, "aaaabbbbccccdddd", "aaaabbbbccccdddd"])

    first, _ = detector.find_all_duplicates(images, batch_size=2)
    second, _ = detector.find_all_duplicates(images, batch_size=2)

    assert grouped(first) == grouped(second) == {
        frozenset({"img_000.jpg", "img_001.jpg"}),
        frozenset({"img_002.jpg", "img_003.jpg"}),
    }


def test_budget_limits_new_hashes_not_comparisons(tmp_path):
    """Unhashed images are deferred; already-hashed ones still all compare."""
    detector, images = make_images(tmp_path, [DUP, DUP, None, None])

    groups, has_more = detector.find_all_duplicates(images, batch_size=0)

    assert grouped(groups) == {frozenset({"img_000.jpg", "img_001.jpg"})}
    assert has_more is True, "two images still lack a hash"


def test_has_more_is_false_once_everything_is_hashed(tmp_path):
    detector, images = make_images(tmp_path, [DUP, DUP])

    _, has_more = detector.find_all_duplicates(images, batch_size=5000)

    assert has_more is False


def test_undecodable_files_do_not_keep_has_more_true(tmp_path):
    """Broken files must be recorded, or the UI loops on 'more batches'.

    The tmp fixtures are not real JPEGs, so hashing them genuinely fails. If a
    failure left no trace, every run would retry the same files, spend the same
    budget, and report more work remaining forever.
    """
    detector, images = make_images(tmp_path, [None, None])

    _, first_has_more = detector.find_all_duplicates(images, batch_size=1)
    _, second_has_more = detector.find_all_duplicates(images, batch_size=1)

    assert first_has_more is True   # one still unattempted
    assert second_has_more is False  # both now known-undecodable
    assert detector._image_hashes.get(images[0].file_path) == DuplicateDetector.UNHASHABLE


def test_a_repaired_file_is_retried(tmp_path):
    """The failure marker is stat-validated like any other cache entry."""
    detector, images = make_images(tmp_path, [None])
    detector.find_all_duplicates(images, batch_size=1)
    assert detector._image_hashes.get(images[0].file_path) == DuplicateDetector.UNHASHABLE

    with open(images[0].file_path, "wb") as f:
        f.write(b"\xff\xd8\xff\xd9\x00")  # different bytes, new size

    assert detector._image_hashes.get(images[0].file_path) is None


def test_unhashable_marker_never_matches_a_real_hash(tmp_path):
    """Two broken files must not be reported as duplicates of each other."""
    detector, images = make_images(tmp_path, [None, None])

    groups, _ = detector.find_all_duplicates(images, batch_size=10)

    assert groups == []
