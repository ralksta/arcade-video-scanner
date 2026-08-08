"""Characterization tests for arcade_scanner/core/duplicate_detector.py.

These pin down the near-miss image matching behaviour of
`DuplicateDetector._find_image_duplicates_by_hash`. All fixtures live in tmp
dirs; no real media library or arcade_data/ is touched.

The detector is driven through its hash cache rather than through real images:
`_StatValidatedHashCache.load()` returns early once `path` is set, and `save()`
returns early while the cache is not dirty, so a pre-populated cache lets a test
choose exact phash values without decoding anything.
"""
import os

import pytest

from arcade_scanner.core.duplicate_detector import (
    IMAGEHASH_AVAILABLE,
    DuplicateDetector,
    _StatValidatedHashCache,
)

pytestmark = pytest.mark.skipif(
    not IMAGEHASH_AVAILABLE, reason="imagehash/Pillow not installed"
)


class FakeImage:
    """Minimal stand-in for a scanned image entry."""

    def __init__(self, file_path, size_mb=1.0, width=1920, height=1080):
        self.file_path = file_path
        self.size_mb = size_mb
        self.width = width
        self.height = height
        self.thumb = ""


def make_detector(tmp_path, hashes):
    """Build a detector whose hash cache maps real tmp files to given phashes.

    `hashes` is a list of 16-char hex phash strings; one tmp file is created per
    entry. Returns (detector, [FakeImage, ...]) in the same order.
    """
    detector = DuplicateDetector()
    # Point the cache at a tmp file so load() short-circuits and nothing is
    # ever read from or written to the real arcade_data/ dir.
    detector._image_hashes.path = str(tmp_path / ".phash_cache.json")

    images = []
    for i, hash_str in enumerate(hashes):
        path = tmp_path / f"img_{i:03d}.jpg"
        path.write_bytes(b"\xff\xd8\xff\xd9")  # not a real JPEG; never decoded
        detector._image_hashes.set(str(path), hash_str)
        images.append(FakeImage(str(path)))

    detector._image_hashes.dirty = False  # keep save() a no-op
    return detector, images


def grouped_paths(groups):
    """Set of frozensets of basenames, one per duplicate group."""
    return {
        frozenset(os.path.basename(f.path) for f in g.files)
        for g in groups
    }


def test_identical_hashes_are_grouped(tmp_path):
    """Exact-hash duplicates are found by the O(n) exact bucket pass."""
    detector, images = make_detector(
        tmp_path, ["f0f0f0f0f0f0f0f0", "f0f0f0f0f0f0f0f0", "0123456789abcdef"]
    )

    groups, _ = detector._find_image_duplicates_by_hash(images, threshold=5)

    assert grouped_paths(groups) == {frozenset({"img_000.jpg", "img_001.jpg"})}


def test_near_miss_in_hash_tail_is_grouped(tmp_path):
    """A 1-bit difference in the LAST bit is detected.

    Both hashes share the first 4 hex chars, so prefix bucketing puts them in
    the same bucket and the pairwise comparison runs.
    """
    detector, images = make_detector(
        tmp_path, ["0000000000000000", "0000000000000001"]
    )

    groups, _ = detector._find_image_duplicates_by_hash(images, threshold=5)

    assert grouped_paths(groups) == {frozenset({"img_000.jpg", "img_001.jpg"})}


def test_near_miss_in_hash_head_is_grouped(tmp_path):
    """A 1-bit difference in the FIRST bit must also be detected.

    Hamming distance is 1 — identical to the tail case above and far below the
    threshold of 5 — but the two hashes fall into different 4-char prefix
    buckets. Recall must not depend on *where* in the hash the bits differ.
    """
    detector, images = make_detector(
        tmp_path, ["0000000000000000", "8000000000000000"]
    )

    groups, _ = detector._find_image_duplicates_by_hash(images, threshold=5)

    assert grouped_paths(groups) == {frozenset({"img_000.jpg", "img_001.jpg"})}


def test_distant_hashes_are_not_grouped(tmp_path):
    """Hashes far apart in Hamming distance must stay separate."""
    detector, images = make_detector(
        tmp_path, ["0000000000000000", "ffffffffffffffff"]
    )

    groups, _ = detector._find_image_duplicates_by_hash(images, threshold=5)

    assert groups == []


def test_threshold_zero_skips_near_miss_pass(tmp_path):
    """threshold=0 disables near-miss detection; only exact matches survive."""
    detector, images = make_detector(
        tmp_path, ["0000000000000000", "0000000000000001"]
    )

    groups, _ = detector._find_image_duplicates_by_hash(images, threshold=0)

    assert groups == []


def test_matches_brute_force_on_random_hashes(tmp_path):
    """Candidate search must find exactly what an all-pairs scan would find.

    This is the general form of the head/tail asymmetry above: for random
    hashes, every pair the detector groups must be within the threshold, and
    every pair within the threshold must end up in *some* group together --
    unless one of them was already consumed by an earlier group (the grouping
    pass is greedy, and this test pins that down rather than fighting it).
    """
    import random

    import imagehash

    rng = random.Random(20260802)
    threshold = 5

    # Seed clusters of near-identical hashes, then flip bits at random
    # positions -- including leading ones -- plus unrelated noise hashes.
    hashes = []
    for _ in range(12):
        base = rng.getrandbits(64)
        hashes.append(f"{base:016x}")
        for _ in range(rng.randint(1, 3)):
            variant = base
            for _ in range(rng.randint(1, threshold)):
                variant ^= 1 << rng.randrange(64)
            hashes.append(f"{variant:016x}")
    hashes.extend(f"{rng.getrandbits(64):016x}" for _ in range(40))
    rng.shuffle(hashes)

    detector, images = make_detector(tmp_path, hashes)
    groups, _ = detector._find_image_duplicates_by_hash(images, threshold=threshold)

    parsed = [imagehash.hex_to_hash(h) for h in hashes]
    grouped = grouped_paths(groups)

    # Every grouped pair really is within the threshold.
    index_of = {f"img_{i:03d}.jpg": i for i in range(len(hashes))}
    for group in grouped:
        members = sorted(index_of[name] for name in group)
        anchor = members[0]
        for other in members[1:]:
            assert parsed[anchor] - parsed[other] <= threshold, (
                f"grouped {anchor} and {other} at distance "
                f"{parsed[anchor] - parsed[other]} > {threshold}"
            )

    # No near pair is missed outright: for every brute-force pair, at least one
    # of the two must have landed in a group.
    in_a_group = {name for group in grouped for name in group}
    for a in range(len(hashes)):
        for b in range(a + 1, len(hashes)):
            if parsed[a] - parsed[b] <= threshold:
                assert (
                    f"img_{a:03d}.jpg" in in_a_group or f"img_{b:03d}.jpg" in in_a_group
                ), f"pair ({a}, {b}) at distance {parsed[a] - parsed[b]} was dropped entirely"


def test_missing_files_are_skipped(tmp_path):
    """Entries whose file vanished between scan and dedup are ignored."""
    detector, images = make_detector(
        tmp_path, ["f0f0f0f0f0f0f0f0", "f0f0f0f0f0f0f0f0"]
    )
    os.remove(images[1].file_path)

    groups, _ = detector._find_image_duplicates_by_hash(images, threshold=5)

    assert groups == []


# --- hash cache identity -----------------------------------------------------


def test_cached_hash_is_reused_while_file_is_unchanged(tmp_path):
    detector, images = make_detector(tmp_path, ["f0f0f0f0f0f0f0f0"])

    assert detector._image_hashes.get(images[0].file_path) == "f0f0f0f0f0f0f0f0"


def test_cached_hash_is_dropped_when_file_content_changes(tmp_path):
    """An edited-in-place image must not keep serving its old hash.

    A stale hash puts the file in the wrong duplicate group, and the UI offers
    to delete members of that group — so this is a data-loss path, not just a
    stale-cache annoyance.
    """
    detector, images = make_detector(tmp_path, ["f0f0f0f0f0f0f0f0"])
    path = images[0].file_path

    with open(path, "wb") as f:
        f.write(b"\xff\xd8completely different bytes\xff\xd9")

    assert detector._image_hashes.get(path) is None


def test_cached_hash_is_dropped_when_only_mtime_changes(tmp_path):
    """Same size, new mtime — still a re-hash, since the bytes may differ."""
    detector, images = make_detector(tmp_path, ["f0f0f0f0f0f0f0f0"])
    path = images[0].file_path

    st = os.stat(path)
    os.utime(path, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000_000))

    assert detector._image_hashes.get(path) is None


def test_changed_file_is_regrouped_by_its_new_hash(tmp_path):
    """End to end: a changed file drops out of the group its old hash implied."""
    detector, images = make_detector(
        tmp_path, ["f0f0f0f0f0f0f0f0", "f0f0f0f0f0f0f0f0"]
    )
    # Rewrite one file, then pin its new content to a distant hash — as a real
    # re-hash of the changed bytes would.
    path = images[1].file_path
    with open(path, "wb") as f:
        f.write(b"\xff\xd8other\xff\xd9")
    detector._image_hashes.set(path, "0f0f0f0f0f0f0f0f")

    groups, _ = detector._find_image_duplicates_by_hash(images, threshold=5)

    assert groups == []


def test_legacy_flat_cache_is_migrated_and_stamped(tmp_path):
    """v1 caches ({path: hash}) keep working instead of forcing a full re-hash."""
    detector = DuplicateDetector()
    path = tmp_path / "legacy.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")

    entries, purged, migrated = _StatValidatedHashCache.decode(
        {str(path): "f0f0f0f0f0f0f0f0"}
    )

    st = os.stat(path)
    assert entries == {str(path): ("f0f0f0f0f0f0f0f0", st.st_mtime_ns, st.st_size)}
    assert (purged, migrated) == (0, 1)


def test_decode_purges_orphans_and_malformed_entries(tmp_path):
    detector = DuplicateDetector()
    present = tmp_path / "present.jpg"
    present.write_bytes(b"\xff\xd8\xff\xd9")
    st = os.stat(present)

    entries, purged, migrated = _StatValidatedHashCache.decode({
        "version": 2,
        "entries": {
            str(present): ["f0f0f0f0f0f0f0f0", st.st_mtime_ns, st.st_size],
            str(tmp_path / "gone.jpg"): ["aaaaaaaaaaaaaaaa", 1, 2],
            str(present) + ".bad": None,
        },
    })

    assert list(entries) == [str(present)]
    assert purged == 2
    assert migrated == 0


def test_cache_roundtrips_through_disk(tmp_path):
    detector, images = make_detector(tmp_path, ["f0f0f0f0f0f0f0f0"])
    detector._image_hashes.dirty = True
    detector._image_hashes.save()

    import json
    with open(detector._image_hashes.path) as f:
        raw = json.load(f)

    reloaded = _StatValidatedHashCache(".phash_cache.json", "image hashes")
    reloaded.path = detector._image_hashes.path
    reloaded._entries, _, _ = _StatValidatedHashCache.decode(raw)

    assert raw["version"] == _StatValidatedHashCache.VERSION
    assert reloaded.get(images[0].file_path) == "f0f0f0f0f0f0f0f0"
