"""Tests for the threaded image-hashing phase.

Hashing dominates a first duplicate scan, and it is the one part of the scan
that parallelises: PIL and numpy both drop the GIL while decoding. What must
survive the pool is the *result* — grouping has to stay byte-for-byte what a
single-threaded run produces, whatever order the pool finishes in.
"""
import os

import pytest

from arcade_scanner.core.duplicate_detector import (
    IMAGEHASH_AVAILABLE,
    DuplicateDetector,
    _is_hex,
)

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


def real_images(tmp_path, count, dup_of=None):
    """Write `count` genuinely decodable JPEGs; `dup_of` maps i -> source index.

    Content is seeded noise rather than a gradient: smooth synthetic patterns
    land within phash distance of each other and chain into one big group, which
    says nothing about the code under test.
    """
    import random

    from PIL import Image

    paths = []
    for i in range(count):
        path = tmp_path / f"img_{i:03d}.jpg"
        source = (dup_of or {}).get(i)
        if source is not None:
            path.write_bytes(paths[source].read_bytes())
        else:
            rng = random.Random(1000 + i)
            img = Image.new("RGB", (64, 64))
            px = img.load()
            for y in range(0, 64, 8):
                for x in range(0, 64, 8):
                    colour = (rng.randrange(256), rng.randrange(256), rng.randrange(256))
                    for dy in range(8):
                        for dx in range(8):
                            px[x + dx, y + dy] = colour
            img.save(path, quality=95)
        paths.append(path)
    return [FakeImage(str(p)) for p in paths]


def detector_for(tmp_path, workers, name="cache"):
    detector = DuplicateDetector()
    detector._image_hashes.path = str(tmp_path / f".{name}.json")
    detector._hash_worker_count = lambda pending, w=workers: w
    return detector


def grouped(groups):
    return sorted(
        sorted(os.path.basename(f.path) for f in g.files) for g in groups
    )


def test_pool_result_matches_single_threaded(tmp_path):
    """The core guarantee: threads change the timing, not the answer."""
    images = real_images(tmp_path, 12, dup_of={4: 0, 9: 2, 11: 0})

    single, _ = detector_for(tmp_path, 1, "single")._find_image_duplicates_by_hash(images)
    pooled, _ = detector_for(tmp_path, 4, "pooled")._find_image_duplicates_by_hash(images)

    assert grouped(single) == grouped(pooled)
    assert grouped(single) == [
        ["img_000.jpg", "img_004.jpg", "img_011.jpg"],
        ["img_002.jpg", "img_009.jpg"],
    ]


def test_hashes_written_to_cache_match_single_threaded(tmp_path):
    images = real_images(tmp_path, 8)

    single = detector_for(tmp_path, 1, "single")
    pooled = detector_for(tmp_path, 4, "pooled")
    single._find_image_duplicates_by_hash(images)
    pooled._find_image_duplicates_by_hash(images)

    for img in images:
        assert single._image_hashes.get(img.file_path) == pooled._image_hashes.get(
            img.file_path
        )


def test_only_cache_misses_are_hashed(tmp_path):
    """A second run must not decode anything again."""
    images = real_images(tmp_path, 6)
    detector = detector_for(tmp_path, 4)
    detector._find_image_duplicates_by_hash(images)

    hashed = []
    original = DuplicateDetector._phash_file
    detector._phash_file = lambda path: hashed.append(path) or original(path)

    detector._find_image_duplicates_by_hash(images)

    assert hashed == []


def test_undecodable_files_do_not_sink_the_batch(tmp_path):
    """One broken file must not cost the others their hashes.

    They share a pool chunk, so an exception escaping a worker would take the
    whole chunk's results with it.
    """
    images = real_images(tmp_path, 4, dup_of={3: 0})
    broken = tmp_path / "broken.jpg"
    broken.write_bytes(b"\xff\xd8not a jpeg at all")
    images.insert(2, FakeImage(str(broken)))

    detector = detector_for(tmp_path, 4)
    groups, deferred = detector._find_image_duplicates_by_hash(images)

    assert grouped(groups) == [["img_000.jpg", "img_003.jpg"]]
    assert deferred == 0
    assert detector._image_hashes.get(str(broken)) == DuplicateDetector.UNHASHABLE


def test_budget_still_caps_work_under_the_pool(tmp_path):
    images = real_images(tmp_path, 6)
    detector = detector_for(tmp_path, 4)

    detector._find_image_duplicates_by_hash(images, hash_budget=2)

    hashed = sum(
        1 for img in images if detector._image_hashes.get(img.file_path) is not None
    )
    assert hashed == 2


def test_corrupt_cache_entry_is_recomputed(tmp_path):
    """Garbage in the cache must not silently cost an image its match.

    Comparison parses entries with `int(hash_str, 16)`, so an unparseable value
    would either raise or have to be dropped. It is treated as a miss instead.
    """
    images = real_images(tmp_path, 2, dup_of={1: 0})
    detector = detector_for(tmp_path, 2)
    detector._image_hashes.set(images[0].file_path, "not-a-hash")

    groups, _ = detector._find_image_duplicates_by_hash(images)

    assert grouped(groups) == [["img_000.jpg", "img_001.jpg"]]
    assert _is_hex(detector._image_hashes.get(images[0].file_path))


def test_worker_count_stays_within_bounds():
    count = DuplicateDetector._hash_worker_count
    cpus = os.cpu_count() or 1

    assert count(0) == 1, "never a zero-thread pool"
    assert count(1) == 1, "one file needs one thread"
    assert count(10_000) == min(cpus, 8), "capped at cores, and at 8 overall"
    assert count(2) <= 2, "never more threads than there is work"


def test_is_hex_rejects_the_unhashable_marker():
    """The failure marker must never be mistaken for a hash."""
    assert not _is_hex(DuplicateDetector.UNHASHABLE)
    assert not _is_hex("")
    assert _is_hex("f0f0f0f0f0f0f0f0")
